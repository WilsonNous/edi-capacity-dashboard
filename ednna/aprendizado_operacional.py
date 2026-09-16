from __future__ import annotations

import json
import re
from collections import Counter

from ednna.armazenamento import conectar, agora_brasil_iso
from ednna.contexto_relacionamentos import buscar_issue_contexto

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CNPJ_RE = re.compile(r"(?<!\d)\d{2}[.\s]?\d{3}[.\s]?\d{3}[\s/.-]?\d{4}[-.\s]?\d{2}(?!\d)")
_NUM_RE = re.compile(r"\b\d{4,}\b")


def _texto_issue(issue: dict) -> str:
    partes = [str(issue.get("subject") or ""), str(issue.get("description") or "")]
    partes += [str(j.get("notes") or "") for j in issue.get("journals", []) or [] if j.get("notes")]
    return "\n".join(p for p in partes if p.strip())


def _emails(issue: dict) -> list[str]:
    return sorted(set(_EMAIL_RE.findall(_texto_issue(issue))), key=str.lower)


def _linhas_procedimento(issue: dict) -> list[str]:
    saida = []
    for linha in _texto_issue(issue).splitlines():
        s = " ".join(linha.strip().split())
        if len(s) < 12:
            continue
        n = _EMAIL_RE.sub("<EMAIL>", s)
        n = _CNPJ_RE.sub("<CNPJ>", n)
        n = _NUM_RE.sub("<NUM>", n)
        saida.append(n[:500])
    return saida


def _inferir_constantes(issues_historicos: list[dict]) -> list[str]:
    if len(issues_historicos) < 2:
        return []
    por_issue = [set(_linhas_procedimento(i)) for i in issues_historicos]
    cont = Counter(x for grupo in por_issue for x in grupo)
    return [x for x, qtd in cont.most_common() if qtd >= 2][:12]


def _inferir_variaveis(issues: list[dict]) -> list[str]:
    texto = "\n".join(_texto_issue(i) for i in issues)
    vars_ = []
    if _CNPJ_RE.search(texto): vars_.append("CNPJ")
    if re.search(r"(?i)\b(?:EC|estabelecimento|conv[eê]nio|filia[cç][aã]o)\b", texto): vars_.append("EC/Convênio")
    vars_ += ["Cliente", "Chamado Redmine"]
    return list(dict.fromkeys(vars_))


def _fonte_parcial(issue: dict) -> bool:
    return bool((issue.get("_ednna_contexto") or {}).get("parcial"))


def _sinais_semanticos(hist: list[dict], recorrentes: list[str], constantes: list[str]) -> dict:
    texto = "\n".join(_texto_issue(i) for i in hist)
    return {
        "destinatario_recorrente": bool(recorrentes),
        "padrao_assunto": len(hist) >= 2 and all(str(i.get("subject") or "").strip() for i in hist),
        "estrutura_mensagem": bool(constantes),
        "campos_operacionais": bool(re.search(r"(?i)\b(?:EC|estabelecimento|conv[eê]nio|filia[cç][aã]o|CNPJ)\b", texto)),
        "evidencia_conclusao": bool(re.search(r"(?i)\b(?:conclu[ií]d|confirm|ativad|inclu[ií]d|cadastrad|processad|realizad)\w*\b", texto)),
    }


def aprender_procedimento_inclusao(aprendizado: dict, regra: dict, *, force: bool = False) -> dict:
    regra_id = str(regra.get("regra_sugerida") or "").strip()
    player = str(regra.get("player") or "").strip()
    atual_id = int(aprendizado.get("chamado_id") or 0)
    ars = [int(x) for x in regra.get("aberturas_relacionamento", []) or []]
    anteriores = [int(x) for x in regra.get("inclusoes_anteriores", []) or []]
    ids = list(dict.fromkeys(ars + anteriores + ([atual_id] if atual_id else [])))

    fontes, erros = [], []
    for iid in ids:
        try:
            fontes.append(buscar_issue_contexto(iid, force=force))
        except Exception as exc:
            erros.append({"id": iid, "erro": str(exc)})

    hist = [i for i in fontes if int(i.get("id") or 0) in anteriores]
    email_counts = Counter(e.lower() for i in hist for e in _emails(i))
    recorrentes = [e for e, n in email_counts.most_common() if n >= 2]
    todos_emails = sorted(set(e for i in fontes for e in _emails(i)), key=str.lower)
    constantes = _inferir_constantes(hist)
    variaveis = _inferir_variaveis(fontes)
    fontes_parciais = sorted(int(i.get("id") or 0) for i in fontes if _fonte_parcial(i) and i.get("id"))
    sinais = _sinais_semanticos(hist, recorrentes, constantes)

    # v3.28.15: completude mede procedimento operacional, não apenas quantidade de fontes.
    pesos = {"destinatario_recorrente": 25, "padrao_assunto": 15, "estrutura_mensagem": 25,
             "campos_operacionais": 15, "evidencia_conclusao": 20}
    completude = sum(pesos[k] for k, ok in sinais.items() if ok)
    bloqueios = []
    if len(anteriores) < 2: bloqueios.append("HISTORICO_INSUFICIENTE")
    if not constantes: bloqueios.append("SEM_PROCEDIMENTO_RECORRENTE")
    if fontes_parciais or erros: bloqueios.append("FONTES_PENDENTES_ENRIQUECIMENTO")
    if not recorrentes: bloqueios.append("DESTINATARIO_NAO_CONFIRMADO")
    if not sinais["evidencia_conclusao"]: bloqueios.append("EVIDENCIA_CONCLUSAO_NAO_CONFIRMADA")

    pronto = completude >= 70 and len(anteriores) >= 2 and bool(constantes) and not fontes_parciais and not erros
    estado = "PRONTA_PARA_REVISAO" if pronto else "APRENDIZADO_INCOMPLETO"
    resultado = {
        "regra_id": regra_id, "player": player, "operacao": "INCLUSAO", "estado": estado,
        "completude": min(completude, 100), "canal": "EMAIL" if todos_emails else "NAO_IDENTIFICADO",
        "fontes": {"bp": aprendizado.get("blueprint_id"), "ar": ars, "historicos": anteriores, "atual": atual_id},
        "destinatarios_recorrentes": recorrentes, "emails_encontrados": todos_emails,
        "constantes": constantes, "variaveis": variaveis, "sinais_semanticos": sinais,
        "fontes_parciais": fontes_parciais, "bloqueios": bloqueios, "erros": erros,
        "pode_homologar": pronto, "pode_executar": False, "aprendido_em": agora_brasil_iso(),
    }
    salvar_aprendizado(resultado)
    print(f"[EDNNA] Aprendizado | regra={regra_id} | fontes={ids}", flush=True)
    print(f"[EDNNA] Procedimento semântico | constantes={len(constantes)} | sinais={sum(sinais.values())}/{len(sinais)} | completude={resultado['completude']}% | parciais={fontes_parciais}", flush=True)
    print(f"[EDNNA] Regra | {regra_id} | {estado} | bloqueios={bloqueios}", flush=True)
    return resultado


def salvar_aprendizado(resultado: dict) -> None:
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        conn.execute("""INSERT INTO aprendizados_operacionais
        (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
        VALUES (?,?,?,?,?,?,?) ON CONFLICT(regra_id) DO UPDATE SET
        player=excluded.player,operacao=excluded.operacao,estado=excluded.estado,
        completude=excluded.completude,payload_json=excluded.payload_json,atualizado_em=excluded.atualizado_em""",
        (resultado["regra_id"], resultado["player"], resultado["operacao"], resultado["estado"], resultado["completude"], json.dumps(resultado, ensure_ascii=False), resultado["aprendido_em"]))


def obter_aprendizado(regra_id: str) -> dict | None:
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT payload_json FROM aprendizados_operacionais WHERE regra_id=?", (regra_id,)).fetchone()
    return json.loads(row["payload_json"]) if row else None


def reprocessar_aprendizados_incompletos(ids_atualizados: list[int] | None = None) -> dict:
    """Reavalia regras incompletas após o worker enriquecer suas fontes."""
    atualizados = {int(x) for x in (ids_atualizados or [])}
    with conectar() as conn:
        rows = conn.execute("SELECT payload_json FROM aprendizados_operacionais WHERE estado='APRENDIZADO_INCOMPLETO'").fetchall()
    reprocessadas, erros = [], []
    for row in rows:
        try:
            antigo = json.loads(row["payload_json"])
            f = antigo.get("fontes") or {}
            ids_regra = set(int(x) for x in ((f.get("ar") or []) + (f.get("historicos") or []) + ([f.get("atual")] if f.get("atual") else [])))
            if atualizados and not (ids_regra & atualizados):
                continue
            aprendizado = {"chamado_id": f.get("atual"), "blueprint_id": f.get("bp")}
            regra = {"regra_sugerida": antigo.get("regra_id"), "player": antigo.get("player"),
                     "aberturas_relacionamento": f.get("ar") or [], "inclusoes_anteriores": f.get("historicos") or []}
            novo = aprender_procedimento_inclusao(aprendizado, regra, force=False)
            reprocessadas.append({"regra": novo.get("regra_id"), "estado": novo.get("estado")})
        except Exception as exc:
            erros.append(str(exc))
    if reprocessadas:
        print(f"[EDNNA] Aprendizado automático | reprocessadas={reprocessadas}", flush=True)
    return {"reprocessadas": reprocessadas, "erros": erros}
