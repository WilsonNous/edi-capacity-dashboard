from __future__ import annotations

import re
from collections import Counter
from typing import Any

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
        # normaliza elementos naturalmente variáveis para comparar procedimentos.
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
    emails_hist = [_emails(i) for i in hist]
    email_counts = Counter(e.lower() for grupo in emails_hist for e in grupo)
    recorrentes = [e for e, n in email_counts.most_common() if n >= 2]
    todos_emails = sorted(set(e for i in fontes for e in _emails(i)), key=str.lower)
    constantes = _inferir_constantes(hist)
    variaveis = _inferir_variaveis(fontes)

    completude = 0
    completude += 25 if ars else 0
    completude += 25 if len(anteriores) >= 2 else (12 if anteriores else 0)
    completude += 20 if todos_emails else 0
    completude += 20 if constantes else 0
    completude += 10 if not erros else 0
    estado = "PRONTA_PARA_REVISAO" if completude >= 70 and len(anteriores) >= 2 else "APRENDENDO"

    resultado = {
        "regra_id": regra_id, "player": player, "operacao": "INCLUSAO",
        "estado": estado, "completude": min(completude, 100), "canal": "EMAIL" if todos_emails else "NAO_IDENTIFICADO",
        "fontes": {"bp": aprendizado.get("blueprint_id"), "ar": ars, "historicos": anteriores, "atual": atual_id},
        "destinatarios_recorrentes": recorrentes, "emails_encontrados": todos_emails,
        "constantes": constantes, "variaveis": variaveis, "erros": erros,
        "pode_homologar": estado == "PRONTA_PARA_REVISAO",
        "pode_executar": False,
        "aprendido_em": agora_brasil_iso(),
    }
    salvar_aprendizado(resultado)
    print(f"[EDNNA] Aprendizado | regra={regra_id} | fontes={ids}", flush=True)
    print(f"[EDNNA] Procedimento | constantes={len(constantes)} | variaveis={','.join(variaveis)} | completude={resultado['completude']}%", flush=True)
    print(f"[EDNNA] Regra | {regra_id} | {estado}", flush=True)
    return resultado


def salvar_aprendizado(resultado: dict) -> None:
    import json
    with conectar() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL
        )""")
        conn.execute("""INSERT INTO aprendizados_operacionais
        (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
        VALUES (?,?,?,?,?,?,?) ON CONFLICT(regra_id) DO UPDATE SET
        player=excluded.player,operacao=excluded.operacao,estado=excluded.estado,
        completude=excluded.completude,payload_json=excluded.payload_json,atualizado_em=excluded.atualizado_em""",
        (resultado["regra_id"], resultado["player"], resultado["operacao"], resultado["estado"], resultado["completude"], json.dumps(resultado, ensure_ascii=False), resultado["aprendido_em"]))


def obter_aprendizado(regra_id: str) -> dict | None:
    import json
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT payload_json FROM aprendizados_operacionais WHERE regra_id=?", (regra_id,)).fetchone()
    return json.loads(row["payload_json"]) if row else None
