from __future__ import annotations

"""EDNNA v3.34.9 — mineração histórica orientada à automação.

Governança:
- EVIDENCIA_HISTORICA: fato observado em chamados/journals/anexos;
- POLITICA_HOMOLOGADA: decisão operacional Netunna;
- INFERENCIA_EDNNA: padrão sugerido pela EDNNA, sujeito a revisão.

Este módulo nunca homologa nem autoriza execução automaticamente.
"""

import json
import re
from collections import Counter, defaultdict
from typing import Iterable

from ednna.armazenamento import conectar, agora_brasil_iso

ABERTURA_RE = re.compile(r"(?i)abertura\s+(?:de\s+)?relacionamento|abrir\s+relacionamento|credenciamento")
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
CNPJ_RE = re.compile(r"(?<!\d)\d{2}[.\s]?\d{3}[.\s]?\d{3}[\s/.-]?\d{4}[-.\s]?\d{2}(?!\d)")
EC_RE = re.compile(r"(?i)(?:\bEC\b|estabelecimento|conv[eê]nio)\s*[:#-]?\s*([0-9]{5,20})")
CONTA_RE = re.compile(r"(?i)\bconta(?:\s+corrente)?\s*[:#-]?\s*([0-9][0-9.\- ]{2,20})")
AGENCIA_RE = re.compile(r"(?i)\bag[eê]ncia\s*[:#-]?\s*([0-9.\-]{2,12})")

EVIDENCIA_HISTORICA = "EVIDENCIA_HISTORICA"
POLITICA_HOMOLOGADA = "POLITICA_HOMOLOGADA"
INFERENCIA_EDNNA = "INFERENCIA_EDNNA"

CAPACIDADES = {
    "IDENTIFICAR_CONTEXTO": ("EDNNA", "Identificar cliente, player e tipo de abertura"),
    "CONSULTAR_BLUEPRINT": ("EDNNA", "Resolver Blueprint, participantes e contatos"),
    "EXTRAIR_DADOS": ("EDNNA", "Extrair CNPJ, EC, agência e contas"),
    "PREPARAR_SOLICITACAO": ("EDNNA", "Preparar solicitação conforme regra homologada"),
    "ENVIAR_EMAIL": ("EDNNA", "Enviar pelo Microsoft Graph após pre-flight"),
    "REGISTRAR_REDMINE": ("EDNNA", "Registrar journal/evidências e estado"),
    "MONITORAR_RESPOSTA": ("EDNNA", "Monitorar resposta do terceiro"),
    "FOLLOWUP_48H": ("EDNNA", "Executar primeiro follow-up em 48 horas"),
    "INTERPRETAR_RETORNO": ("EDNNA", "Interpretar retornos conhecidos"),
    "EXECUTAR_API_PORTAL": ("CHECKPOINT_HUMANO", "Executar API/portal ainda não integrado"),
    "ASSINATURA_DOCUMENTO": ("CHECKPOINT_HUMANO", "Obter assinatura/documento externo"),
    "ATUALIZAR_PLANILHA": ("CHECKPOINT_HUMANO", "Atualizar planilha externa não integrada"),
    "VALIDAR_ARQUIVOS": ("CHECKPOINT_HUMANO", "Confirmar recepção física dos arquivos"),
    "DECISAO_AMBIGUA": ("CHECKPOINT_HUMANO", "Resolver ambiguidade real de dados/procedimento"),
}

POLITICAS_HOMOLOGADAS = {
    "FOLLOWUP_48H": {
        "responsavel": "EDNNA",
        "descricao": CAPACIDADES["FOLLOWUP_48H"][1],
        "origem": POLITICA_HOMOLOGADA,
        "confianca": "HOMOLOGADA",
        "parametros": {"primeiro_followup_horas": 48},
        "evidencia": "Padrão operacional Netunna/EDNNA: primeiro follow-up em 48 horas.",
    }
}

PLAYER_ALIASES = {
    "ITAU": ["ITAÚ", "ITAU"], "SICREDI": ["SICREDI"], "SAFRAPAY": ["SAFRAPAY", "SAFRA PAY"],
    "CIELO": ["CIELO"], "REDECARD": ["REDECARD", "USEREDE"],
    "SANTANDER": ["SANTANDER"], "BRADESCO": ["BRADESCO"], "BANRISUL": ["BANRISUL"],
    "ALELO": ["ALELO"], "PLUXEE": ["PLUXEE", "SODEXO"], "GREENCARD": ["GREENCARD", "GREEN CARD"],
    "TICKET": ["TICKET"], "SENFF": ["SENFF"], "VALECARD": ["VALECARD"], "WIZEO": ["WIZEO"],
    "TRUCKPAG": ["TRUCKPAG"], "FITCARD": ["FITCARD"], "EXPERS": ["EXPERS"], "SHELLBOX": ["SHELLBOX", "SHELL BOX"],
    "PICPAY": ["PICPAY"], "PROFROTAS": ["PROFROTAS"],
}
REDE_EXPLICITA_RE = re.compile(r"(?i)(?:^|[\[\]():;,_/\-\s])REDE(?:$|[\[\]():;,_/\-\s])")


def _init() -> None:
    with conectar() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS mineracao_aberturas (
            chamado_id INTEGER PRIMARY KEY, player TEXT NOT NULL, status TEXT, assunto TEXT,
            score INTEGER NOT NULL DEFAULT 0, payload_json TEXT NOT NULL, minerado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS propostas_regras_abertura (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'CANDIDATA',
            evidencias INTEGER NOT NULL DEFAULT 0, compatibilidade INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        """)


def _texto(issue: dict) -> str:
    partes = [str(issue.get("subject") or ""), str(issue.get("description") or "")]
    partes.extend(str(j.get("notes")) for j in (issue.get("journals") or []) if j.get("notes"))
    return "\n".join(partes)


def _player_em_texto(texto: str, *, aceitar_rede: bool = False) -> str:
    up = str(texto or "").upper()
    for player, aliases in PLAYER_ALIASES.items():
        if any(alias.upper() in up for alias in aliases):
            return player
    if aceitar_rede and REDE_EXPLICITA_RE.search(str(texto or "")):
        return "REDECARD"
    return "NAO_IDENTIFICADO"


def identificar_player(issue: dict) -> str:
    """Prioridade: campo estruturado > assunto explícito > narrativa/journals."""
    estruturados = []
    for cf in issue.get("custom_fields", []) or []:
        nome = str(cf.get("name") or "").upper()
        if "ORIGEM" in nome or "ADQUIREN" in nome or "BANCO" in nome:
            valor = cf.get("value")
            if isinstance(valor, (list, tuple, set)):
                estruturados.extend(str(v) for v in valor if v not in (None, ""))
            elif valor not in (None, ""):
                estruturados.append(str(valor))
    for valor in estruturados:
        player = _player_em_texto(valor, aceitar_rede=True)
        if player != "NAO_IDENTIFICADO":
            return player

    assunto = str(issue.get("subject") or "")
    player = _player_em_texto(assunto, aceitar_rede=True)
    if player != "NAO_IDENTIFICADO":
        return player

    # Na narrativa, REDE isolado é ambíguo (ex.: "Rede Santa Lúcia").
    narrativa = "\n".join([str(issue.get("description") or "")] + [
        str(j.get("notes")) for j in (issue.get("journals") or []) if j.get("notes")
    ])
    return _player_em_texto(narrativa, aceitar_rede=False)


def eh_abertura(issue: dict) -> bool:
    return bool(ABERTURA_RE.search(_texto(issue)))


def _status_nome(issue: dict) -> str:
    s = issue.get("status") or {}
    return str(s.get("name") if isinstance(s, dict) else s or "")


def _terminal_positivo(issue: dict) -> bool:
    status = _status_nome(issue).upper()
    return any(x in status for x in ("CONCLU", "FECHAD"))


def _score(issue: dict) -> tuple[int, dict]:
    texto = _texto(issue)
    journals = len(issue.get("journals", []) or [])
    anexos = len(issue.get("attachments", []) or [])
    emails = sorted(set(e.lower() for e in EMAIL_RE.findall(texto)))
    cnpjs = sorted(set(CNPJ_RE.findall(texto)))
    ecs = sorted(set(EC_RE.findall(texto)))
    contas = sorted(set(x.strip() for x in CONTA_RE.findall(texto)))
    agencias = sorted(set(AGENCIA_RE.findall(texto)))
    terminal = _terminal_positivo(issue)
    score = (30 if terminal else 0) + min(journals, 10) * 3 + min(anexos, 5) * 3
    score += 10 if emails else 0
    score += 8 if cnpjs else 0
    score += 6 if (ecs or contas) else 0
    score += 5 if "BLUEPRINT" in texto.upper() or "BP " in texto.upper() else 0
    return min(100, score), {"terminal_positivo": terminal, "journals": journals, "anexos": anexos,
                            "emails": emails, "cnpjs": cnpjs, "ecs": ecs, "contas": contas, "agencias": agencias}


def _etapas_evidenciadas(issue: dict) -> list[dict]:
    texto = _texto(issue); up = texto.upper(); etapas = []
    def add(cod: str, evidencia: str) -> None:
        resp, desc = CAPACIDADES[cod]
        etapas.append({"codigo": cod, "responsavel": resp, "descricao": desc,
                       "evidencia": evidencia, "origem": EVIDENCIA_HISTORICA})
    add("IDENTIFICAR_CONTEXTO", "Chamado classificado como Abertura de Relacionamento")
    if "BLUEPRINT" in up or "BP " in up: add("CONSULTAR_BLUEPRINT", "Blueprint/BP referenciado no histórico")
    if CNPJ_RE.search(texto) or EC_RE.search(texto) or CONTA_RE.search(texto): add("EXTRAIR_DADOS", "Dados operacionais presentes no histórico")
    if re.search(r"(?i)assunto\s*:|para\s*:|solicitamos|gostar[ií]amos de habilitar|abertura", texto): add("PREPARAR_SOLICITACAO", "Solicitação/e-mail encontrado")
    if EMAIL_RE.search(texto): add("ENVIAR_EMAIL", "Destinatários/remetentes encontrados")
    add("REGISTRAR_REDMINE", "Histórico está registrado no Redmine")
    if re.search(r"(?i)retorno|respond|protocolo|aguardando", texto): add("MONITORAR_RESPOSTA", "Há sinais de acompanhamento/retorno")
    if re.search(r"(?i)retorno|confirmad|habilitad|conclu[ií]d|liberad", texto): add("INTERPRETAR_RETORNO", "Há retorno operacional no histórico")
    if re.search(r"(?i)\bapi\b|opt[- ]?in|portal", texto): add("EXECUTAR_API_PORTAL", "Histórico menciona API/opt-in/portal")
    if re.search(r"(?i)assin|termo|formul[aá]rio", texto): add("ASSINATURA_DOCUMENTO", "Histórico menciona termo/formulário/assinatura")
    if re.search(r"(?i)planilha|sharepoint", texto): add("ATUALIZAR_PLANILHA", "Histórico menciona planilha")
    if re.search(r"(?i)arquivo.{0,50}(recebid|cheg|movimento)|recep[cç][aã]o.{0,30}arquivo", texto): add("VALIDAR_ARQUIVOS", "Histórico menciona validação/recepção de arquivos")
    seen = set()
    return [x for x in etapas if not (x["codigo"] in seen or seen.add(x["codigo"]))]


def minerar_issue(issue: dict) -> dict:
    score, sinais = _score(issue); player = identificar_player(issue)
    return {"chamado_id": int(issue.get("id") or 0), "player": player, "status": _status_nome(issue),
            "assunto": str(issue.get("subject") or ""), "score": score, "sinais": sinais,
            "etapas": _etapas_evidenciadas(issue), "minerar_em": agora_brasil_iso()}


def salvar_mineracao(resultado: dict) -> None:
    _init()
    with conectar() as conn:
        conn.execute("""INSERT INTO mineracao_aberturas(chamado_id,player,status,assunto,score,payload_json,minerado_em)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(chamado_id) DO UPDATE SET player=excluded.player,status=excluded.status,
          assunto=excluded.assunto,score=excluded.score,payload_json=excluded.payload_json,minerado_em=excluded.minerado_em""",
          (resultado["chamado_id"], resultado["player"], resultado["status"], resultado["assunto"], resultado["score"],
           json.dumps(resultado, ensure_ascii=False), agora_brasil_iso()))


def _politicas_da_proposta() -> list[dict]:
    return [{"codigo": cod, **dados} for cod, dados in POLITICAS_HOMOLOGADAS.items()]


def gerar_propostas(resultados: Iterable[dict], minimo_evidencias: int = 2) -> list[dict]:
    _init(); grupos = defaultdict(list)
    for r in resultados:
        if r.get("player") and r.get("player") != "NAO_IDENTIFICADO": grupos[r["player"]].append(r)
    propostas = []
    for player, casos in sorted(grupos.items()):
        bons = [c for c in casos if c.get("score", 0) >= 55 and c.get("sinais", {}).get("terminal_positivo")]
        base = bons or sorted(casos, key=lambda x: x.get("score", 0), reverse=True)[:3]
        freq = Counter(e["codigo"] for c in base for e in c.get("etapas", []) if e.get("origem") == EVIDENCIA_HISTORICA)
        etapas = []
        for cod, n in freq.most_common():
            resp, desc = CAPACIDADES[cod]; recorrencia = round(100 * n / max(1, len(base)))
            etapas.append({"codigo": cod, "responsavel": resp, "descricao": desc, "ocorrencias": n,
                           "recorrencia_pct": recorrencia, "origem": INFERENCIA_EDNNA, "base_origem": EVIDENCIA_HISTORICA,
                           "confianca": "ALTA" if n >= minimo_evidencias and recorrencia >= 60 else "A_VALIDAR"})
        politicas = _politicas_da_proposta()
        automaticas = sum(1 for e in etapas if e["responsavel"] == "EDNNA" and e["confianca"] == "ALTA") + sum(1 for e in politicas if e["responsavel"] == "EDNNA")
        checkpoints = sum(1 for e in etapas if e["responsavel"] == "CHECKPOINT_HUMANO" and e["confianca"] == "ALTA")
        compat = round(sum(c.get("score", 0) for c in base) / max(1, len(base)))
        proposta = {"regra_id": f"ABERTURA-{player}-001", "player": player, "estado": "CANDIDATA",
                    "evidencias": len(base), "casos_ids": [c["chamado_id"] for c in base], "compatibilidade": compat,
                    "etapas": etapas, "politicas_homologadas": politicas, "automatizaveis_agora": automaticas,
                    "checkpoints_humanos": checkpoints,
                    "pronta_para_revisao": len(base) >= minimo_evidencias and any(e["confianca"] == "ALTA" for e in etapas),
                    "governanca": {"historico": EVIDENCIA_HISTORICA, "inferencias": INFERENCIA_EDNNA, "politicas": POLITICA_HOMOLOGADA},
                    "nota": "Candidata inferida do histórico; políticas homologadas são anexadas separadamente. Não autorizada para execução."}
        propostas.append(proposta)
        with conectar() as conn:
            conn.execute("""INSERT INTO propostas_regras_abertura(regra_id,player,estado,evidencias,compatibilidade,payload_json,atualizado_em)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(regra_id) DO UPDATE SET player=excluded.player,estado=excluded.estado,
              evidencias=excluded.evidencias,compatibilidade=excluded.compatibilidade,payload_json=excluded.payload_json,atualizado_em=excluded.atualizado_em""",
              (proposta["regra_id"], player, "CANDIDATA", len(base), compat, json.dumps(proposta, ensure_ascii=False), agora_brasil_iso()))
    return propostas


def listar_propostas() -> list[dict]:
    _init()
    with conectar() as conn:
        rows = conn.execute("SELECT payload_json FROM propostas_regras_abertura ORDER BY player").fetchall()
    return [json.loads(r[0]) for r in rows]


def _ordem_shortlist(issue: dict) -> tuple[int, int]:
    """Casos terminais primeiro; recência apenas desempata."""
    return (1 if _terminal_positivo(issue) else 0, int(issue.get("id") or 0))


def descobrir_no_redmine(*, limite_detalhes_por_player: int = 6) -> dict:
    from redmine_api import REDMINE_PROJECT_IDS, buscar_chamados_projeto, buscar_detalhes_chamado
    rasos = []
    for pid in REDMINE_PROJECT_IDS:
        rasos.extend(buscar_chamados_projeto(pid, status_id="*", max_workers_paginas=2))
    candidatos = [x for x in rasos if eh_abertura(x)]
    por_player = defaultdict(list)
    for c in candidatos: por_player[identificar_player(c)].append(c)
    detalhados = []; erros = []
    for player, itens in por_player.items():
        if player == "NAO_IDENTIFICADO":
            continue
        itens = sorted(itens, key=_ordem_shortlist, reverse=True)[:max(1, limite_detalhes_por_player)]
        for item in itens:
            try:
                d = buscar_detalhes_chamado(int(item["id"]), incluir_journals=True, incluir_relacoes=True,
                                            incluir_anexos=True, consulta_pontual=False, tentativas=1)
                if d:
                    r = minerar_issue(d); salvar_mineracao(r); detalhados.append(r)
            except Exception as exc:
                erros.append({"chamado_id": item.get("id"), "erro": f"{type(exc).__name__}: {exc}"})
    propostas = gerar_propostas(detalhados)
    return {"candidatos_rasos": len(candidatos), "detalhados": len(detalhados), "players": len([p for p in por_player if p != "NAO_IDENTIFICADO"]),
            "propostas": propostas, "erros": erros, "executado_em": agora_brasil_iso()}


def simular_proposta(proposta: dict) -> dict:
    ids = set(int(x) for x in proposta.get("casos_ids", [])); _init(); casos = []
    with conectar() as conn:
        rows = conn.execute("SELECT payload_json FROM mineracao_aberturas WHERE player=?", (proposta.get("player"),)).fetchall()
    for r in rows:
        c = json.loads(r[0])
        if not ids or int(c.get("chamado_id", 0)) in ids: casos.append(c)
    esperadas = {e["codigo"] for e in proposta.get("etapas", []) if e.get("confianca") == "ALTA" and e.get("origem") == INFERENCIA_EDNNA}
    detalhes = []
    for c in casos:
        presentes = {e["codigo"] for e in c.get("etapas", []) if e.get("origem") == EVIDENCIA_HISTORICA}
        cob = round(100 * len(esperadas & presentes) / max(1, len(esperadas)))
        detalhes.append({"chamado_id": c["chamado_id"], "cobertura_pct": cob, "faltantes": sorted(esperadas - presentes)})
    compativeis = sum(1 for d in detalhes if d["cobertura_pct"] >= 80)
    return {"casos": len(detalhes), "compativeis": compativeis,
            "compatibilidade_pct": round(100 * compativeis / max(1, len(detalhes))),
            "politicas_excluidas_do_backtest": sorted(POLITICAS_HOMOLOGADAS.keys()), "detalhes": detalhes}
