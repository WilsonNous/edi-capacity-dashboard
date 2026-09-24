from __future__ import annotations

import re
from typing import Any

from ednna.contexto_relacionamentos import analisar_contexto_operacional, buscar_issue_contexto, PLAYER_ALIASES
from ednna.workflows_inclusao import obter_workflow, planejar_workflow

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CNPJ_RE = re.compile(r"(?<!\d)(\d{2}[.\s]?\d{3}[.\s]?\d{3}[\s/.-]?\d{4}[-.\s]?\d{2})(?!\d)")

# v3.28.17 — matriz de contexto por intenção.
# A intenção define quais famílias de chamados podem ensinar a regra.
CONTEXT_TYPES = {
    "INCLUSAO": {
        "principais": {"ABERTURA", "INCLUSAO"},
        "complementares": {"FALTA_ARQUIVO", "FALTA_REGISTROS"},
    }
}

def _evento_permitido_inclusao(evento: dict) -> bool:
    return str(evento.get("evento") or "").upper() in (
        CONTEXT_TYPES["INCLUSAO"]["principais"] | CONTEXT_TYPES["INCLUSAO"]["complementares"]
    )

_EC_ROTULADO_RE = re.compile(
    r"(?im)\b(?:EC|ESTABELECIMENTO|CONVENIO|CONVÊNIO|FILIACAO|FILIAÇÃO)\s*(?:/\s*(?:CONVENIO|CONVÊNIO))?\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{2,30})"
)
# ECs podem aparecer em sequência no assunto/descrição (ex.: EC 123 - 456 - 789).
# Aceitamos somente blocos numéricos de 5 a 13 dígitos para não confundir CNPJ (14)
# nem códigos curtos auxiliares.
_EC_NUMERICO_RE = re.compile(r"(?<!\d)(\d{5,18})(?!\d)")


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


def _texto_operacional_issue(issue: dict) -> str:
    """Texto confiável para identificadores operacionais.

    EC/convênio nunca é extraído de journals, URLs ou nomes de anexos. O Redmine
    costuma inserir IDs numéricos de screenshots/attachments no histórico e esses
    números não podem virar estabelecimento por mera coincidência de regex.
    """
    return "\n".join([str(issue.get("subject") or ""), str(issue.get("description") or "")])


def _extrair_ecs_contextuais(issue: dict) -> list[str]:
    texto = _texto_operacional_issue(issue)
    encontrados: list[str] = []

    # Somente linhas/frases que declaram semanticamente EC/estabelecimento/convênio.
    # Dentro desse contexto preservamos todos os identificadores de 5..13 dígitos.
    for linha in texto.splitlines():
        if not re.search(r"(?i)\b(?:EC|ESTABELECIMENTO|CONVENIO|CONVÊNIO|FILIACAO|FILIAÇÃO)\b", linha):
            continue
        encontrados.extend(_EC_NUMERICO_RE.findall(linha))

    # O assunto pode conter a sequência completa sem quebras de linha.
    assunto = str(issue.get("subject") or "")
    if re.search(r"(?i)\b(?:EC|ESTABELECIMENTO|CONVENIO|CONVÊNIO|FILIACAO|FILIAÇÃO)\b", assunto):
        encontrados.extend(_EC_NUMERICO_RE.findall(assunto))

    # v3.29.5 — alguns players informam o EC em uma linha própria, no formato
    # "VERO - 041131200978800". A frase anterior do chamado já estabelece o
    # contexto de inclusão de estabelecimento, mas o identificador não repete a
    # palavra "estabelecimento" na mesma linha. Só aceitamos este formato quando
    # a linha começa por um alias conhecido de player e descartamos blocos de 14
    # dígitos (CNPJ), preservando a proteção contra números soltos/anexos.
    aliases = sorted(
        {str(alias) for valores in PLAYER_ALIASES.values() for alias in valores},
        key=len, reverse=True,
    )
    alias_re = "|".join(re.escape(a) for a in aliases)
    player_ec_re = re.compile(
        rf"(?im)^\s*(?:{alias_re})\s*[-:–—]\s*(\d{{5,18}})\s*[.;,]?\s*$"
    )
    for valor in player_ec_re.findall(texto):
        if len(re.sub(r"\D", "", valor)) != 14:
            encontrados.append(valor)

    return _unicos(encontrados)


def _extrair_dados(issue: dict) -> dict:
    texto_completo = _texto_issue(issue)
    # E-mails e CNPJs podem ser úteis no histórico. ECs, porém, usam apenas
    # assunto+descrição e exigem contexto semântico explícito.
    emails = _unicos(_EMAIL_RE.findall(texto_completo))
    cnpjs = _unicos(_CNPJ_RE.findall(texto_completo))
    ecs = _extrair_ecs_contextuais(issue)
    return {"emails": emails, "cnpjs": cnpjs, "ecs": ecs}




def _normalizar_cnpj(valor: str) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    if len(digitos) != 14:
        return ""
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def _identificar_cnpj_matriz(cnpjs: list[str]) -> str:
    """Identifica matriz somente quando o CNPJ explicita filial 0001.

    Não escolhe arbitrariamente o primeiro CNPJ: se nenhum /0001 estiver
    presente, o workflow ALELO permanece bloqueado aguardando dado seguro.
    """
    for valor in cnpjs or []:
        normalizado = _normalizar_cnpj(valor)
        digitos = re.sub(r"\D", "", normalizado)
        if len(digitos) == 14 and digitos[8:12] == "0001":
            return normalizado
    return ""


def _eh_abertura(evento: dict) -> bool:
    return str(evento.get("evento") or "").upper() == "ABERTURA"


def _eh_inclusao(evento: dict) -> bool:
    return str(evento.get("evento") or "").upper() == "INCLUSAO"


def _norm_player_texto(valor: Any) -> str:
    import unicodedata
    texto = str(valor or "").upper().strip()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _players_explicitos_assunto(assunto: str) -> list[str]:
    """Extrai o player-alvo do assunto sem deixar aliases genéricos vencerem.

    O alias histórico REDE de REDECARD é útil na reconstrução ampla, mas não pode
    transformar nomes de cliente como REDE SANTA LUCIA em REDECARD.
    """
    texto = _norm_player_texto(assunto)
    encontrados: list[str] = []
    for player, aliases in PLAYER_ALIASES.items():
        aliases_ordenados = sorted(aliases, key=lambda x: len(_norm_player_texto(x)), reverse=True)
        for alias in aliases_ordenados:
            alias_n = _norm_player_texto(alias)
            if player == "REDECARD" and alias_n == "REDE":
                # REDE só vale como adquirente quando aparece delimitada como bloco
                # do assunto (ex.: CLIENTE - REDE - Inclusão), nunca em REDE SANTA LUCIA.
                if not re.search(r"(?:^|[-–—|])\s*REDE\s*(?:[-–—|]|$)", texto):
                    continue
            if re.search(rf"(?<![A-Z0-9]){re.escape(alias_n)}(?![A-Z0-9])", texto):
                encontrados.append(player)
                break
    return _unicos(encontrados)


def _selecionar_player_alvo(chamado_id: int, contexto: dict, eventos: list[dict], *, force: bool = False) -> tuple[list[str], str]:
    """Define PLAYER_ALVO. O chamado atual é soberano sobre BP/histórico."""
    assunto = str(contexto.get("assunto") or "")
    explicitos = _players_explicitos_assunto(assunto)
    if explicitos:
        return explicitos, "CHAMADO_ATUAL_ASSUNTO"

    # Se o contexto não trouxe o assunto completo, consulta o próprio chamado.
    try:
        issue_atual = buscar_issue_contexto(chamado_id, force=force)
        explicitos = _players_explicitos_assunto(str(issue_atual.get("subject") or ""))
        if explicitos:
            return explicitos, "CHAMADO_ATUAL_ASSUNTO"
    except Exception:
        pass

    # Fallback compatível com versões anteriores: somente players do evento atual.
    for evento in eventos:
        if int(evento.get("id") or 0) == chamado_id:
            atuais = [str(x) for x in (evento.get("players") or []) if x]
            if atuais:
                return _unicos(atuais), "EVENTO_ATUAL_FALLBACK"
    return [], "NAO_IDENTIFICADO"


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

    eventos_brutos = list(contexto.get("eventos") or [])
    eventos = [e for e in eventos_brutos if _evento_permitido_inclusao(e)]
    ignorados_tipo = [e for e in eventos_brutos if not _evento_permitido_inclusao(e)]
    players_atuais, origem_player_alvo = _selecionar_player_alvo(chamado_id, contexto, eventos, force=force)
    if not players_atuais:
        # Último fallback: relacionamentos reconstruídos. Só é usado quando o
        # chamado atual realmente não identifica um player.
        players_atuais = [str(x.get("player")) for x in contexto.get("relacionamentos", []) if x.get("player")]
        origem_player_alvo = "CONTEXTO_HISTORICO_FALLBACK"

    print(f"[EDNNA] Inclusão | chamado={chamado_id}", flush=True)
    print(f"[EDNNA] Player alvo | {','.join(players_atuais) if players_atuais else 'NAO_IDENTIFICADO'} | origem={origem_player_alvo}", flush=True)
    if contexto.get("blueprint_id"):
        print(f"[EDNNA] BP confirmado | chamado={int(contexto['blueprint_id'])} | player={','.join(players_atuais)}", flush=True)

    aberturas = [e for e in eventos if _eh_abertura(e)]
    inclusoes = [e for e in eventos if _eh_inclusao(e)]
    complementares = [e for e in eventos if str(e.get("evento") or "").upper() in CONTEXT_TYPES["INCLUSAO"]["complementares"]]

    regras: list[dict[str, Any]] = []
    for player in sorted(set(players_atuais)):
        # v3.28.12 — a investigação é orientada ao player do chamado atual.
        # Relações de outros adquirentes permanecem no contexto bruto, mas não
        # concorrem com o player investigado nem poluem a síntese operacional.
        aberturas_player = [e for e in aberturas if player in (e.get("players") or [])]
        inclusoes_player = [e for e in inclusoes if player in (e.get("players") or [])]
        anteriores = [e for e in inclusoes_player if int(e.get("id") or 0) != chamado_id]
        complementares_player = [e for e in complementares if player in (e.get("players") or [])]
        fontes_prioritarias = aberturas_player + anteriores + complementares_player
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

        # Dados canônicos consumidos pelo motor. O CNPJ Matriz só é inferido
        # quando o identificador de filial é 0001; caso contrário exige revisão.
        agregados["estabelecimento"] = list(agregados.get("ecs") or [])
        agregados["cnpj_matriz"] = _identificar_cnpj_matriz(agregados.get("cnpjs") or [])

        evidencia_historica = bool(aberturas_player or anteriores)
        ar_ids = [int(e["id"]) for e in aberturas_player if e.get("id")]
        ant_ids = [int(e["id"]) for e in anteriores if e.get("id")]
        if ar_ids:
            print(f"[EDNNA] AR selecionada | chamado={ar_ids[0]} | player={player}", flush=True)
        comp_ids = [int(e["id"]) for e in complementares_player if e.get("id")]
        print(f"[EDNNA] Corpus inclusão | player={player} | principais={{'abertura':{ar_ids},'inclusoes':{ant_ids}}} | complementares={comp_ids} | tipos_ignorados={len(ignorados_tipo)}", flush=True)
        secundarios = sorted({str(p) for e in eventos for p in (e.get("players") or []) if p and str(p) not in players_atuais})
        if secundarios:
            print(f"[EDNNA] Players secundários ignorados | {', '.join(secundarios)}", flush=True)
        print(f"[EDNNA] Regra candidata | INCLUSAO-{player.replace(' ', '-')}-001 | estado=CANDIDATA_NAO_HOMOLOGADA", flush=True)
        workflow_cfg = obter_workflow(player)
        regras.append({
            "player": player,
            "regra_sugerida": f"INCLUSAO-{player.replace(' ', '-')}-001",
            "status_regra": "CANDIDATA_NAO_HOMOLOGADA",
            "canal_sugerido": workflow_cfg.get("canal") or ("EMAIL" if agregados["emails"] else "NAO_IDENTIFICADO"),
            "workflow_sugerido": workflow_cfg,
            "dados_identificados": agregados,
            "player_alvo": player,
            "origem_player_alvo": origem_player_alvo,
            "aberturas_relacionamento": ar_ids,
            "inclusoes_anteriores": ant_ids,
            "fontes_complementares": comp_ids,
            "tipos_contexto": {"principais": sorted(CONTEXT_TYPES["INCLUSAO"]["principais"]), "complementares": sorted(CONTEXT_TYPES["INCLUSAO"]["complementares"])},
            "tipos_ignorados": len(ignorados_tipo),
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
        # O motor nasceu para inclusões. Greencard é o primeiro workflow composto
        # em que Abertura de Relacionamento e Inclusão compartilham o mesmo
        # orquestrador documental. Não ampliamos abertura genericamente para
        # evitar classificar workflows bancários como inclusão.
        abertura_greencard = ("GREENCARD" in norm or "GREEN CARD" in norm) and "ABERTURA" in norm and "RELACION" in norm
        if "INCLUS" not in norm and "HABILITA" not in norm and not abertura_greencard:
            continue
        # Evita trazer outros trackers que apenas mencionam uma inclusão no texto.
        if "INCLUS" not in tipo.upper() and "INCLUS" not in assunto.upper() and "HABILITA" not in assunto.upper() and not abertura_greencard:
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


# v3.28.24 — plano operacional de regra homologada.
def preparar_operacao_inclusao(chamado_id: int, player: str, dados: dict | None = None) -> dict:
    """Monta o workflow operacional sem executar ações externas.

    A camada de execução consulta este plano. Workflows com executor ainda não
    implementado ficam explicitamente em AGUARDANDO_EXECUTOR.
    """
    from ednna.aprendizado_operacional import obter_regra_homologada, obter_autorizacao_motor
    regra = obter_regra_homologada(player)
    if not regra:
        return {"chamado_id": int(chamado_id), "player": player, "estado":"REGRA_NAO_HOMOLOGADA", "pode_operar":False}
    autorizacao = obter_autorizacao_motor(regra.get("regra_id"))
    if str(autorizacao.get("modo") or "BLOQUEADA") == "BLOQUEADA":
        return {"chamado_id": int(chamado_id), "player": player, "regra_id": regra.get("regra_id"), "estado":"REGRA_HOMOLOGADA_NAO_AUTORIZADA", "pode_operar":False, "autorizacao_motor":autorizacao}
    dados_motor = dict(dados or {})
    if not dados_motor:
        try:
            extraidos = _extrair_dados(buscar_issue_contexto(int(chamado_id), force=False))
            dados_motor.update(extraidos)
            dados_motor["estabelecimento"] = list(extraidos.get("ecs") or [])
            dados_motor["cnpj_matriz"] = _identificar_cnpj_matriz(extraidos.get("cnpjs") or [])
        except Exception as exc:
            dados_motor["erro_extracao"] = str(exc)
    plano = planejar_workflow(player, dados=dados_motor)
    estado = plano.get("estado_planejamento") or ("PRONTO_OPERACAO_ASSISTIDA" if plano.get("pode_operar_assistido") else "AGUARDANDO_EXECUTOR")
    return {"chamado_id":int(chamado_id), "player":player, "regra_id":regra.get("regra_id"), "estado":estado, "pode_operar":plano.get("pode_operar_assistido",False), "workflow":plano, "autorizacao_motor":autorizacao}
