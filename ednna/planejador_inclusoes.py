from __future__ import annotations

import re
from typing import Any

from ednna.contexto_relacionamentos import analisar_contexto_operacional, buscar_issue_contexto

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CNPJ_RE = re.compile(r"(?<!\d)(\d{2}[.\s]?\d{3}[.\s]?\d{3}[\s/.-]?\d{4}[-.\s]?\d{2})(?!\d)")
_EC_ROTULADO_RE = re.compile(
    r"(?im)\b(?:EC|ESTABELECIMENTO|CONVENIO|CONVÊNIO|FILIACAO|FILIAÇÃO)\s*(?:/\s*(?:CONVENIO|CONVÊNIO))?\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{2,30})"
)


def _texto_issue(issue: dict) -> str:
    partes = [str(issue.get("subject") or ""), str(issue.get("description") or "")]
    for journal in issue.get("journals", []) or []:
        notas = str(journal.get("notes") or "").strip()
        if notas:
            partes.append(notas)
    return "\n".join(partes)


def _unicos(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    saida: list[str] = []
    for valor in valores:
        v = str(valor or "").strip().strip(".,;:()[]<>")
        chave = v.upper()
        if v and chave not in vistos:
            vistos.add(chave)
            saida.append(v)
    return saida


def _extrair_dados(issue: dict) -> dict:
    texto = _texto_issue(issue)
    emails = _unicos(_EMAIL_RE.findall(texto))
    cnpjs = _unicos(_CNPJ_RE.findall(texto))
    ecs = []
    for valor in _EC_ROTULADO_RE.findall(texto):
        limpo = valor.strip().strip(".,;:()[]<>")
        # Evita transformar palavras comuns em EC quando o texto está mal formatado.
        if any(ch.isdigit() for ch in limpo) and 3 <= len(limpo) <= 31:
            ecs.append(limpo)
    return {"emails": emails, "cnpjs": cnpjs, "ecs": _unicos(ecs)}


def _eh_abertura(evento: dict) -> bool:
    return str(evento.get("evento") or "").upper() == "ABERTURA"


def _eh_inclusao(evento: dict) -> bool:
    return str(evento.get("evento") or "").upper() == "INCLUSAO"


def preparar_aprendizado_inclusao(chamado_id: int, *, force: bool = False) -> dict:
    """Monta uma regra candidata de inclusão, sem enviar e-mail ou alterar Redmine.

    Ordem de confiança: relações explícitas/BP -> abertura de relacionamento ->
    inclusões anteriores do mesmo player -> conteúdo do chamado atual.
    """
    chamado_id = int(chamado_id)
    contexto = analisar_contexto_operacional(chamado_id, force=force)
    if str(contexto.get("evento_atual") or "").upper() != "INCLUSAO":
        return {
            "chamado_id": chamado_id,
            "estado": "NAO_E_INCLUSAO",
            "motivo": "O chamado selecionado não foi reconhecido como inclusão.",
            "contexto": contexto,
        }

    eventos = list(contexto.get("eventos") or [])
    players_atuais: list[str] = []
    for evento in eventos:
        if int(evento.get("id") or 0) == chamado_id:
            players_atuais = list(evento.get("players") or [])
            break
    if not players_atuais:
        # fallback: relacionamentos reconstruídos para o contexto
        players_atuais = [str(x.get("player")) for x in contexto.get("relacionamentos", []) if x.get("player")]

    aberturas = [e for e in eventos if _eh_abertura(e)]
    inclusoes = [e for e in eventos if _eh_inclusao(e)]

    regras: list[dict[str, Any]] = []
    for player in sorted(set(players_atuais)):
        inclusoes_player = [e for e in inclusoes if player in (e.get("players") or [])]
        anteriores = [e for e in inclusoes_player if int(e.get("id") or 0) != chamado_id]
        fontes_prioritarias = aberturas + anteriores
        atual = [e for e in inclusoes_player if int(e.get("id") or 0) == chamado_id]
        fontes_prioritarias += atual

        agregados = {"emails": [], "cnpjs": [], "ecs": []}
        fontes_detalhadas = []
        for resumo in fontes_prioritarias:
            fid = int(resumo.get("id") or 0)
            if not fid:
                continue
            try:
                issue = buscar_issue_contexto(fid, force=force)
                dados = _extrair_dados(issue)
                fontes_detalhadas.append({
                    "id": fid,
                    "evento": resumo.get("evento"),
                    "estado": resumo.get("estado"),
                    "assunto": resumo.get("assunto"),
                    **dados,
                })
                for chave in agregados:
                    agregados[chave].extend(dados[chave])
            except Exception as exc:
                fontes_detalhadas.append({"id": fid, "erro": str(exc)})

        for chave in agregados:
            agregados[chave] = _unicos(agregados[chave])

        evidencia_historica = bool(aberturas or anteriores)
        regras.append({
            "player": player,
            "regra_sugerida": f"INCLUSAO-{player.replace(' ', '-')}-001",
            "status_regra": "CANDIDATA_NAO_HOMOLOGADA",
            "canal_sugerido": "EMAIL" if agregados["emails"] else "NAO_IDENTIFICADO",
            "dados_identificados": agregados,
            "aberturas_relacionamento": [int(e["id"]) for e in aberturas if e.get("id")],
            "inclusoes_anteriores": [int(e["id"]) for e in anteriores if e.get("id")],
            "fontes": fontes_detalhadas,
            "confianca": "MEDIA" if evidencia_historica else "BAIXA",
            "pode_executar": False,
            "motivo_bloqueio": "Regra ainda não homologada. A EDNNA está somente aprendendo o procedimento.",
        })

    estado = "REGRA_CANDIDATA" if regras else "DADOS_INSUFICIENTES"
    return {
        "chamado_id": chamado_id,
        "cliente": contexto.get("cliente"),
        "blueprint_id": contexto.get("blueprint_id"),
        "estado": estado,
        "regras": regras,
        "contexto": contexto,
        "modo": "SOMENTE_LEITURA",
    }


def descobrir_candidatos_inclusao(snapshot) -> dict:
    """Descobre inclusões no snapshot sem exigir regra operacional prévia.

    Não consulta o Redmine e não executa ações. Serve como inventário barato para
    escolher quais chamados merecem reconstrução histórica/homologação.
    """
    if snapshot is None or getattr(snapshot, "empty", True):
        return {"total": 0, "players": [], "candidatos": []}

    candidatos: list[dict[str, Any]] = []
    for _, row in snapshot.iterrows():
        tipo = str(row.get("Tipo", "") or "")
        assunto = str(row.get("Assunto", "") or "")
        descricao = str(row.get("Descrição", "") or "")
        texto = "\n".join([tipo, assunto, descricao])
        norm = texto.upper()
        if "INCLUS" not in norm and "HABILITA" not in norm:
            continue
        # Evita trazer outros trackers que apenas mencionam uma inclusão no texto.
        if "INCLUS" not in tipo.upper() and "INCLUS" not in assunto.upper() and "HABILITA" not in assunto.upper():
            continue

        # Reusa o catálogo de aliases do contexto histórico, mantendo uma única
        # taxonomia de players para descoberta e reconstrução.
        from ednna.contexto_relacionamentos import _players_no_texto
        players = _players_no_texto(texto)
        # REDECARD possui o alias histórico "REDE". Em clientes como REDE SANTA
        # LUCIA isso gera falso positivo. Na descoberta, só aceitamos REDECARD
        # por "REDE" quando o assunto o apresenta como player delimitado.
        assunto_up = assunto.upper()
        if "REDECARD" in players and "REDECARD" not in assunto_up:
            rede_como_player = bool(re.search(r"(?:^|[-–—|])\s*REDE\s*(?:[-–—|]|$)", assunto_up))
            if not rede_como_player:
                players = [p for p in players if p != "REDECARD"]
        cid_raw = row.get("#", 0)
        try:
            cid = int(float(cid_raw))
        except Exception:
            continue
        candidatos.append({
            "id": cid,
            "cliente": str(row.get("Clientes", "") or ""),
            "estado": str(row.get("Estado", "") or ""),
            "tipo": tipo,
            "assunto": assunto,
            "players": players,
            "player": players[0] if len(players) == 1 else (" / ".join(players) if players else "NÃO IDENTIFICADO"),
            "status_descoberta": "DESCOBERTO",
            "pode_executar": False,
        })

    agrupados: dict[str, list[int]] = {}
    for c in candidatos:
        nomes = c["players"] or ["NÃO IDENTIFICADO"]
        for player in nomes:
            agrupados.setdefault(player, []).append(c["id"])
    players = [
        {"player": p, "quantidade": len(ids), "chamados": sorted(set(ids))}
        for p, ids in sorted(agrupados.items(), key=lambda kv: (-len(set(kv[1])), kv[0]))
    ]
    return {"total": len(candidatos), "players": players, "candidatos": candidatos}
