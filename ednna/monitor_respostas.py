from __future__ import annotations

import html
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

from ednna.acompanhamento_acoes import (
    listar_acoes_aguardando_resposta,
    marcar_monitorado,
    marcar_status_redmine,
    registrar_falha_redmine,
    registrar_resposta,
    obter_responsavel_original_cancelamento,
    obter_acompanhamento,
    adquirir_envio,
    confirmar_envio_real,
    registrar_resposta_pendente_redmine,
    listar_respostas_pendentes_redmine,
    marcar_resposta_sincronizada_redmine,
    marcar_evidencia_anexada,
    registrar_falha_evidencia,
)
from ednna.email_sender import (
    listar_mensagens_conversa,
    localizar_email_enviado,
    localizar_resposta_por_chamado,
    localizar_email_enviado_por_chamado,
    listar_envios_cancelamento_getnet,
    baixar_mensagem_eml,
)
from ednna.redmine_writer import (
    registrar_email_e_status_chamado, atribuir_chamado_responsavel,
    registrar_email_evidencia_e_status_chamado,
)
from ednna.contexto_relacionamentos import buscar_issue_contexto, analisar_contexto_cancelamento, processar_enriquecimentos_pendentes
from ednna.planejador_cancelamentos import extrair_dados_getnet, preparar_plano_cancelamento
from ednna.orquestrador_cancelamentos import (
    marcar_etapa, resumo_orquestracao, listar_etapas_pendentes_monitoramento,
)
from ednna.armazenamento import carregar_snapshot_chamados
from ednna.aprendizado_operacional import reprocessar_aprendizados_incompletos


_THREAD: threading.Thread | None = None
_THREAD_LOCK = threading.Lock()
_STOP = threading.Event()


def _bool_env(nome: str, padrao: bool) -> bool:
    valor = str(os.getenv(nome, "true" if padrao else "false") or "").strip().casefold()
    return valor in {"1", "true", "sim", "yes", "on"}


def _texto_corpo(message: dict[str, Any]) -> str:
    body = message.get("body") or {}
    conteudo = str(body.get("content", "") or "")
    tipo = str(body.get("contentType", "") or "").casefold()

    if tipo == "html":
        conteudo = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", conteudo)
        conteudo = re.sub(r"(?i)<br\\s*/?>", "\n", conteudo)
        conteudo = re.sub(r"(?i)</p>", "\n", conteudo)
        conteudo = re.sub(r"<[^>]+>", " ", conteudo)
        conteudo = html.unescape(conteudo)

    conteudo = re.sub(r"[ \t]+", " ", conteudo)
    conteudo = re.sub(r"\n\s*\n\s*\n+", "\n\n", conteudo)
    return conteudo.strip()[:12000]


def _somente_resposta_nova(conteudo: str) -> str:
    """Remove a mensagem original citada, preservando somente o retorno novo do remetente."""
    texto = str(conteudo or "").strip()
    if not texto:
        return ""

    # Delimitadores explícitos mais comuns em Outlook/Exchange e clientes de e-mail.
    delimitadores = [
        r"(?im)^\s*-{2,}\s*Mensagem original\s*-{2,}\s*$",
        r"(?im)^\s*-{2,}\s*Original Message\s*-{2,}\s*$",
        r"(?im)^\s*_{2,}\s*$",
    ]
    cortes = []
    for padrao in delimitadores:
        m = re.search(padrao, texto)
        if m:
            cortes.append(m.start())

    # Outlook às vezes omite o título 'Mensagem original' e inicia o bloco citado por
    # De/From + Enviado/Sent + Para/To. Só cortamos quando a sequência aparece em bloco.
    cabecalho_citado = re.search(
        r"(?ims)^\s*(?:De|From):\s+.+?\n\s*(?:Enviado|Sent):\s+.+?\n\s*(?:Para|To):\s+",
        texto,
    )
    if cabecalho_citado:
        cortes.append(cabecalho_citado.start())

    if cortes:
        texto = texto[:min(cortes)].rstrip()

    # Remove apenas linhas de citação que sobraram no final, sem reescrever a resposta.
    linhas = texto.splitlines()
    while linhas and (not linhas[-1].strip() or linhas[-1].lstrip().startswith(">")):
        linhas.pop()
    return "\n".join(linhas).strip()[:12000]


def _remetente(message: dict[str, Any]) -> str:
    return str(
        (((message.get("from") or {}).get("emailAddress") or {}).get("address"))
        or ""
    ).strip()


def _nota_retorno(*, remetente: str, assunto: str, corpo: str, recebida_em: str) -> str:
    try:
        dt = datetime.fromisoformat(str(recebida_em).replace("Z", "+00:00"))
        recebido_fmt = dt.astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        recebido_fmt = str(recebida_em or "")

    return "\n".join(
        [
            "*EDNNA — Retorno de e-mail recebido*",
            "",
            f"*De:* {remetente}",
            f"*Assunto:* {assunto}",
            f"*Recebido em:* {recebido_fmt}",
            "",
            corpo or "(Mensagem sem conteúdo textual.)",
            "",
            "----",
            "",
            "*Evidência:* E-mail original anexado ao chamado pela EDNNA.",
        ]
    ).strip()



def _nome_evidencia(chamado_id: int, recebida_em: str, regra_id: str = "") -> str:
    try:
        dt = datetime.fromisoformat(str(recebida_em).replace("Z", "+00:00"))
        data = dt.strftime("%Y%m%d_%H%M%S")
    except Exception:
        data = datetime.now().strftime("%Y%m%d_%H%M%S")
    regra = re.sub(r"[^A-Z0-9]+", "_", str(regra_id or "RETORNO").upper()).strip("_")
    partes = [p for p in regra.split("_") if p and p not in {"001", "002", "003"}]
    if partes and partes[0] in {"INCLUSAO", "ABERTURA", "CANCELAMENTO", "HABILITACAO"}:
        acao = partes[0]
        player = "_".join(partes[1:]) or "EMAIL"
    else:
        acao = "RETORNO"
        player = "_".join(partes) or "EMAIL"
    return f"{player}_RETORNO_{acao}_{int(chamado_id)}_{data}.eml"

def _anexar_evidencia_retorno(*, caixa: str, chamado_id: int, regra_id: str, message_id: str,
                               nota: str, status: str, assigned_to: int, recebida_em: str) -> str:
    filename = _nome_evidencia(chamado_id, recebida_em, regra_id)
    eml = baixar_mensagem_eml(caixa_postal=caixa, message_id=message_id)
    registrar_email_evidencia_e_status_chamado(
        chamado_id=chamado_id, nota=nota, status_nome=status, assigned_to_id=assigned_to,
        evidencia=eml, evidencia_filename=filename,
    )
    marcar_evidencia_anexada(chamado_id, regra_id, filename)
    try:
        from ednna.observabilidade import log_event
        log_event("EMAIL", "Evidência de retorno anexada", chamado_id=chamado_id, regra_id=regra_id, detalhe=filename)
    except Exception:
        pass
    return filename

def _complemento_getnet(chamado_id: int, corpo: str) -> str:
    texto = str(corpo or "").casefold()
    if not ("cnpj" in texto or re.search(r"\bec\b", texto)):
        return ""
    issues = []
    try:
        issues.append(buscar_issue_contexto(int(chamado_id), force=False))
    except Exception:
        pass
    dados = extrair_dados_getnet(issues)
    if not dados["ecs"]:
        try:
            ctx = analisar_contexto_cancelamento(int(chamado_id), force=False)
            fontes = []
            for rel in ctx.get("relacionamentos", []) or []:
                if str(rel.get("player", "")).upper() == "GETNET":
                    fontes.extend(rel.get("fontes", []) or [])
            for fonte in dict.fromkeys(fontes):
                try:
                    issues.append(buscar_issue_contexto(int(fonte), force=False))
                except Exception:
                    pass
            dados = extrair_dados_getnet(issues)
        except Exception:
            pass
    linhas = ["", "*EDNNA — Complementação solicitada pela GETNET*", ""]
    if dados["ecs"]:
        linhas.append("*EC(s) localizado(s):* " + ", ".join(dados["ecs"]))
    if dados["cnpjs"]:
        linhas.append("*CNPJ(s) relacionado(s):* " + ", ".join(dados["cnpjs"]))
    if dados["ecs"] or dados["cnpjs"]:
        linhas.extend(["", "*Próxima ação EDNNA:* Dados localizados para preparação da resposta à GETNET. Envio permanece sujeito à revisão humana."] )
    else:
        linhas.extend(["*Resultado:* Não foi possível localizar EC/CNPJ com segurança.", "", "*Próxima ação EDNNA:* Requer intervenção humana."])
    return "\n".join(linhas)


def _getnet_cancelamento_confirmado(corpo: str) -> bool:
    t = re.sub(r"\s+", " ", str(corpo or "").casefold())
    confirmacoes = [
        "foram desativados", "foram desativadas", "foi desativado", "foi desativada",
        "cancelamento concluído", "cancelamento concluido", "cancelamento realizado",
        "tráfego cancelado", "trafego cancelado", "desativados para o envio",
    ]
    return any(x in t for x in confirmacoes)


def _processar_retorno_getnet(chamado_id: int, corpo: str) -> tuple[str, int | None, str]:
    """Retorna (nota_extra, assigned_to_id, status). Mantém EDNNA enquanto houver etapas externas pendentes."""
    ednna_id = int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
    if not _getnet_cancelamento_confirmado(corpo):
        return _complemento_getnet(chamado_id, corpo), ednna_id, "Em andamento"

    # Reconstrói/sincroniza todas as etapas antes de decidir handoff. Evita tratar GETNET
    # como se fosse o único player de um cancelamento total (ex.: MAIS CAMPUS).
    try:
        preparar_plano_cancelamento(int(chamado_id), force=False)
    except Exception as exc:
        print(f"[EDNNA] Orquestrador | sincronização parcial | chamado={chamado_id} | {exc}", flush=True)
    marcar_etapa(chamado_id, "GETNET", "CANCELAMENTO_CONFIRMADO", "Retorno da GETNET confirmou desativação/cancelamento.")
    resumo = resumo_orquestracao(chamado_id)
    linhas = ["", "*EDNNA — Resultado GETNET*", "", "*Resultado:* Cancelamento confirmado pela adquirente.",
              f"*Progresso externo:* {resumo['concluidas']} de {resumo['total']} etapa(s) concluída(s)."]
    if resumo['todas_concluidas']:
        original = obter_responsavel_original_cancelamento(chamado_id)
        if original.get('id'):
            linhas += ["", "*Handoff EDNNA:* Etapas externas concluídas. Chamado devolvido ao responsável operacional original para ações internas (BATs, diretórios, servidor e demais procedimentos físicos)."]
            return "\n".join(linhas), int(original['id']), "Em andamento"
        linhas += ["", "*Handoff EDNNA:* Etapas externas concluídas, mas o responsável original não está disponível na memória. Requer revisão humana."]
    else:
        linhas += ["", "*Acompanhamento EDNNA:* A etapa GETNET foi concluída. A EDNNA permanece responsável porque ainda existem etapas externas pendentes por player."]
    return "\n".join(linhas), ednna_id, "Em andamento"


def _processar_retorno_vr(chamado_id: int, corpo: str) -> tuple[str, int | None, str]:
    """Interpretação conservadora do retorno do cliente no fluxo VR.

    Não conclui o chamado: após a habilitação ainda é necessário acompanhar os
    primeiros arquivos/vendas. Apenas registra a próxima etapa no Redmine.
    """
    ednna_id = int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
    t = re.sub(r"\s+", " ", str(corpo or "").casefold())
    sinais_habilitado = ("habilitad", "adicionei", "adicionado", "add o cnpj", "já esta tudo habilitado", "já está tudo habilitado", "concluí", "conclui")
    if any(x in t for x in sinais_habilitado):
        extra = (
            "\n\n*EDNNA — Interpretação VR Benefícios*\n\n"
            "*Resultado:* retorno do cliente indica que a habilitação no Portal VR foi realizada.\n"
            "*Próxima etapa:* acompanhar o início da operação e a chegada dos primeiros arquivos com vendas. "
            "O chamado não deve ser concluído apenas pela confirmação da habilitação."
        )
        if any(x in t for x in ("inaugur", "prevista", "previsto", "abre dia", "início", "inicio")):
            extra += "\n*Observação:* o retorno também contém informação sobre início/inauguração; usar essa data como referência para o acompanhamento dos arquivos."
        return extra, ednna_id, "Em andamento"
    return (
        "\n\n*EDNNA — Interpretação VR Benefícios*\n\n"
        "*Resultado:* retorno do cliente recebido, mas a confirmação da habilitação no Portal VR não foi identificada com segurança. "
        "Manter o chamado em acompanhamento e revisar o conteúdo antes de avançar para a espera dos arquivos."
    ), ednna_id, "Em andamento"



def _processar_retorno_sicredi(chamado_id: int, corpo: str) -> tuple[str, int | None, str]:
    from ednna.sicredi_workflow import interpretar_retorno_sicredi
    ednna_id=int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
    r=interpretar_retorno_sicredi(corpo)
    evento=r.get("evento") or "RETORNO_NAO_CLASSIFICADO"
    estado=r.get("estado") or "AGUARDANDO_BANCO"
    acao=r.get("acao") or "REVISAR_RETORNO"
    extra=(f"\n\n*EDNNA — Interpretação SICREDI Banco*\n\n*Evento:* {evento}\n*Estado operacional:* {estado}\n*Próxima ação:* {acao}.")
    if r.get("requer_humano"):
        extra += "\n*Segurança:* decisão mantida para revisão humana; a EDNNA não assumirá mudança de VAN/custo automaticamente."
    if r.get("emails_substitutos"):
        extra += "\n*Contatos substitutos encontrados:* " + ", ".join(r['emails_substitutos'])
    return extra, ednna_id, "Em andamento"

def _resolver_conversation_id(acao: dict, caixa: str) -> tuple[str, dict]:
    conversation_id = str(acao.get("graph_conversation_id", "") or "").strip()
    if conversation_id:
        return conversation_id, {}

    assunto = str(acao.get("email_assunto", "") or "").strip()
    if not assunto:
        return "", {}

    enviado = localizar_email_enviado(remetente=caixa, assunto=assunto)
    return str(enviado.get("conversationId", "") or "").strip(), enviado



def _id_linha_snapshot(linha: dict) -> int:
    for chave in ("#", "ID", "id", "Chamado"):
        valor = linha.get(chave)
        try:
            if valor is not None and str(valor).strip():
                return int(str(valor).replace("#", "").strip())
        except Exception:
            continue
    return 0


def _linha_atribuida_ednna(linha: dict) -> bool:
    ednna_id = int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
    for chave in ("_Atribuído a ID", "assigned_to_id", "Atribuído a ID"):
        try:
            if int(linha.get(chave) or 0) == ednna_id:
                return True
        except Exception:
            pass
    nome = str(linha.get("Atribuído a") or linha.get("Responsável") or "").casefold()
    return "ednna" in nome


def _candidato_cancelamento_getnet(linha: dict) -> bool:
    texto = " ".join(str(linha.get(k) or "") for k in (
        "Tipo", "Assunto", "Descrição", "Origem", "Clientes"
    )).casefold()
    return "getnet" in texto and any(x in texto for x in ("cancel", "inativ", "excluir", "desativ"))


def _descobrir_orfaos_getnet_snapshot() -> list[int]:
    """Descobre legados atribuídos à EDNNA sem depender do orquestrador.

    A fonte é o snapshot persistente da própria EDNNA, portanto o monitor não abre
    uma nova avalanche de GETs no Redmine apenas para reconstruir sua fila.
    """
    ids: list[int] = []
    for linha in carregar_snapshot_chamados() or []:
        if not isinstance(linha, dict) or not _linha_atribuida_ednna(linha):
            continue
        if not _candidato_cancelamento_getnet(linha):
            continue
        chamado_id = _id_linha_snapshot(linha)
        if chamado_id and chamado_id not in ids:
            ids.append(chamado_id)
    return ids


def _reconciliar_cancelamentos_getnet_orfaos(caixa: str) -> list[dict]:
    """Reconcilia atuações GETNET usando Redmine/snapshot, SQLite e Sent Items.

    v3.28.7.3:
      * não considera RESPOSTA_RECEBIDA/RESPOSTA_PENDENTE_REDMINE como órfão;
      * recupera registros presos em ENVIANDO quando o e-mail real existe em Sent Items;
      * usa o envio real como evidência principal para reconstrução;
      * registra logs por etapa para diagnosticar correlação Sent Items -> Inbox.
    """
    recuperadas: list[dict] = []
    regra_id = "CANCELAMENTO-GETNET-001"

    etapas = listar_etapas_pendentes_monitoramento("GETNET")
    candidatos = {int(e.get("chamado_id") or 0) for e in etapas if int(e.get("chamado_id") or 0)}
    candidatos.update(_descobrir_orfaos_getnet_snapshot())

    print("[EDNNA] Reconciliação | consultando Sent Items GETNET", flush=True)
    envios_descobertos = listar_envios_cancelamento_getnet(remetente=caixa, top=500)
    envios_por_chamado = {
        int(x.get("chamado_id") or 0): x
        for x in envios_descobertos
        if int(x.get("chamado_id") or 0)
    }
    candidatos.update(envios_por_chamado.keys())

    acoes_atuais = listar_acoes_aguardando_resposta()
    monitorados = {int(a.get("chamado_id") or 0) for a in acoes_atuais if int(a.get("chamado_id") or 0)}

    processados: set[int] = set()
    pendentes_redmine: set[int] = set()
    presos_enviando: set[int] = set()
    orfaos_reais: list[int] = []

    for chamado_id in sorted(candidatos):
        atual = obter_acompanhamento(chamado_id, regra_id)
        estado = str(atual.get("estado") or "RASCUNHO").strip().upper()
        if estado == "RESPOSTA_RECEBIDA":
            processados.add(chamado_id)
            continue
        if estado == "RESPOSTA_PENDENTE_REDMINE":
            pendentes_redmine.add(chamado_id)
            continue
        if chamado_id in monitorados:
            continue
        if estado == "ENVIANDO":
            presos_enviando.add(chamado_id)
        orfaos_reais.append(chamado_id)

    monitorando_ids = sorted(candidatos & monitorados)
    processados_ids = sorted(processados)
    pendentes_redmine_ids = sorted(pendentes_redmine)
    presos_enviando_ids = sorted(presos_enviando)
    orfaos_reais_ids = sorted(orfaos_reais)

    print(
        f"[EDNNA] Reconciliação | enviados_descobertos={len(envios_por_chamado)} | "
        f"candidatos={len(candidatos)} | monitorando={len(monitorando_ids)} | "
        f"processados={len(processados_ids)} | pendentes_redmine={len(pendentes_redmine_ids)} | "
        f"presos_enviando={len(presos_enviando_ids)} | órfãos_reais={len(orfaos_reais_ids)}",
        flush=True,
    )
    print(f"[EDNNA] Reconciliação | monitorando_ids={monitorando_ids}", flush=True)
    print(f"[EDNNA] Reconciliação | processados_ids={processados_ids}", flush=True)
    print(f"[EDNNA] Reconciliação | pendentes_redmine_ids={pendentes_redmine_ids}", flush=True)
    print(f"[EDNNA] Reconciliação | presos_enviando_ids={presos_enviando_ids}", flush=True)
    print(f"[EDNNA] Reconciliação | orfaos_reais_ids={orfaos_reais_ids}", flush=True)

    for chamado_id in orfaos_reais:
        atual = obter_acompanhamento(chamado_id, regra_id)
        estado_anterior = str(atual.get("estado") or "RASCUNHO").strip().upper()
        print(
            f"[EDNNA] Reconciliação | avaliando chamado={chamado_id} | estado_sqlite={estado_anterior}",
            flush=True,
        )

        enviado = envios_por_chamado.get(chamado_id)
        if enviado:
            print(
                f"[EDNNA] Reconciliação | Sent Items HIT | chamado={chamado_id} | "
                f"sent={str(enviado.get('sentDateTime','') or '')} | "
                f"conversation={str(enviado.get('conversationId','') or '')[:24]}",
                flush=True,
            )
        else:
            print(f"[EDNNA] Reconciliação | Sent Items cache MISS | chamado={chamado_id} | busca direta", flush=True)
            enviado = localizar_email_enviado_por_chamado(remetente=caixa, chamado_id=chamado_id)

        if not enviado:
            print(f"[EDNNA] Reconciliação | enviado não localizado | chamado={chamado_id}", flush=True)
            continue

        print(f"[EDNNA] Reconciliação | enviado localizado | chamado={chamado_id}", flush=True)
        marcar_etapa(
            chamado_id,
            "GETNET",
            "AGUARDANDO_RESPOSTA",
            "Acompanhamento reconstruído a partir de Sent Items.",
        )

        # ENVIANDO pode ter ficado gravado por uma execução interrompida. Se o envio
        # existe de fato em Sent Items, ele é a fonte de verdade e podemos confirmá-lo.
        if estado_anterior == "ENVIANDO":
            confirmar_envio_real(
                chamado_id,
                regra_id,
                prazo_dias_uteis=1,
                email_assunto=str(enviado.get("subject", "") or ""),
                graph_message_id=str(enviado.get("id", "") or ""),
                graph_conversation_id=str(enviado.get("conversationId", "") or ""),
                graph_internet_message_id=str(enviado.get("internetMessageId", "") or ""),
                enviado_em_real=str(enviado.get("sentDateTime", "") or ""),
            )
            recuperadas.append({"chamado": chamado_id, "situacao": "ENVIANDO_RECUPERADO"})
            print(f"[EDNNA] Reconciliação | ENVIANDO recuperado pelo Sent Items | chamado={chamado_id}", flush=True)
        else:
            adquirido, _ = adquirir_envio(chamado_id, regra_id)
            if adquirido:
                confirmar_envio_real(
                    chamado_id,
                    regra_id,
                    prazo_dias_uteis=1,
                    email_assunto=str(enviado.get("subject", "") or ""),
                    graph_message_id=str(enviado.get("id", "") or ""),
                    graph_conversation_id=str(enviado.get("conversationId", "") or ""),
                    graph_internet_message_id=str(enviado.get("internetMessageId", "") or ""),
                    enviado_em_real=str(enviado.get("sentDateTime", "") or ""),
                )
                recuperadas.append({"chamado": chamado_id, "situacao": "ACOMPANHAMENTO_RECONSTRUIDO"})
                print(f"[EDNNA] Reconciliação | acompanhamento reconstruído | chamado={chamado_id}", flush=True)

        enviado_em = str(enviado.get("sentDateTime", "") or "")
        print(
            f"[EDNNA] Reconciliação | buscando Inbox | chamado={chamado_id} | após={enviado_em}",
            flush=True,
        )
        resposta = localizar_resposta_por_chamado(
            caixa_postal=caixa,
            chamado_id=chamado_id,
            recebidas_apos=enviado_em,
        )
        if resposta:
            recuperadas.append({"chamado": chamado_id, "situacao": "RESPOSTA_LOCALIZADA"})
            print(
                f"[EDNNA] Reconciliação | resposta localizada | chamado={chamado_id} | "
                f"received={str(resposta.get('receivedDateTime','') or '')} | "
                f"message={str(resposta.get('id','') or '')[:24]}",
                flush=True,
            )
        else:
            print(f"[EDNNA] Reconciliação | resposta ainda não localizada | chamado={chamado_id}", flush=True)

    return recuperadas

def _texto_redmine_issue(issue: dict) -> str:
    partes = [str(issue.get("subject") or ""), str(issue.get("description") or "")]
    for journal in issue.get("journals", []) or []:
        nota = str(journal.get("notes") or "").strip()
        if nota:
            partes.append(nota)
    return "\n".join(partes)


def _normalizar_auditoria(texto: str) -> str:
    return re.sub(r"\\s+", " ", str(texto or "")).strip().casefold()


def _redmine_tem_retorno_ednna(issue: dict, acao: dict) -> bool:
    """Confirma no próprio Redmine que o efeito do retorno realmente foi aplicado.

    Não confia apenas no estado RESPOSTA_RECEBIDA do SQLite. Procura a assinatura
    da nota EDNNA e, quando possível, elementos do retorno persistido.
    """
    texto = _normalizar_auditoria(_texto_redmine_issue(issue))
    if "ednna — retorno de e-mail recebido" not in texto and "ednna - retorno de e-mail recebido" not in texto:
        return False

    assunto = _normalizar_auditoria(acao.get("resposta_assunto") or "")
    if assunto and assunto[:80] in texto:
        return True

    corpo = _normalizar_auditoria(acao.get("resposta_corpo") or "")
    # Usa um fragmento significativo do retorno, evitando depender de assinatura.
    palavras = corpo.split()
    fragmento = " ".join(palavras[:14])
    if len(fragmento) >= 25 and fragmento in texto:
        return True

    # A assinatura EDNNA no histórico já é evidência suficiente para legados em que
    # assunto/corpo foram normalizados de forma diferente.
    return True


def _auditar_processados_redmine(caixa: str) -> dict:
    """v3.28.7.5 — audita PROCESSADO contra o efeito real no Redmine.

    Se o SQLite diz RESPOSTA_RECEBIDA mas a nota não existe no chamado, reabre
    somente a sincronização Redmine usando a resposta já preservada. Não relê nem
    reinterpreta o e-mail e não dispara novo envio.
    """
    regra_id = "CANCELAMENTO-GETNET-001"
    envios = listar_envios_cancelamento_getnet(remetente=caixa, top=500)
    ids = sorted({int(x.get("chamado_id") or 0) for x in envios if int(x.get("chamado_id") or 0)})
    confirmados: list[int] = []
    reparo: list[int] = []
    indisponiveis: list[int] = []

    for chamado_id in ids:
        acao = obter_acompanhamento(chamado_id, regra_id)
        if str(acao.get("estado") or "").strip().upper() != "RESPOSTA_RECEBIDA":
            continue
        try:
            issue = buscar_issue_contexto(chamado_id, force=True)
        except Exception as exc:
            indisponiveis.append(chamado_id)
            print(f"[EDNNA] Auditoria conclusão | Redmine indisponível | chamado={chamado_id} | {type(exc).__name__}: {exc}", flush=True)
            continue

        if _redmine_tem_retorno_ednna(issue, acao):
            confirmados.append(chamado_id)
            continue

        # Estado local dizia concluído, mas o efeito não existe no Redmine.
        # Recria somente a pendência de sincronização com os dados já preservados.
        registrar_resposta_pendente_redmine(
            chamado_id, regra_id,
            graph_message_id=str(acao.get("resposta_graph_message_id") or ""),
            remetente=str(acao.get("resposta_remetente") or ""),
            assunto=str(acao.get("resposta_assunto") or ""),
            corpo=str(acao.get("resposta_corpo") or ""),
            recebida_em=str(acao.get("resposta_recebida_em") or ""),
            erro="Auditoria v3.28.7.5: resposta processada localmente sem evidência da nota no Redmine.",
        )
        reparo.append(chamado_id)
        print(f"[EDNNA] Auditoria conclusão | REPARO_PENDENTE | chamado={chamado_id}", flush=True)

    print(f"[EDNNA] Auditoria conclusão | confirmados_ids={confirmados}", flush=True)
    print(f"[EDNNA] Auditoria conclusão | reparo_pendente_ids={reparo}", flush=True)
    print(f"[EDNNA] Auditoria conclusão | indisponiveis_ids={indisponiveis}", flush=True)
    return {"confirmados": confirmados, "reparo": reparo, "indisponiveis": indisponiveis}



def _reconciliar_evidencias_processadas(caixa: str) -> dict:
    """Anexa .eml retroativamente aos retornos GETNET já processados e ainda sem evidência."""
    regra_id = "CANCELAMENTO-GETNET-001"
    envios = listar_envios_cancelamento_getnet(remetente=caixa, top=500)
    ids = sorted({int(x.get("chamado_id") or 0) for x in envios if int(x.get("chamado_id") or 0)})
    anexadas, pendentes, erros = [], [], []
    for chamado_id in ids:
        acao = obter_acompanhamento(chamado_id, regra_id)
        if str(acao.get("estado") or "").upper() != "RESPOSTA_RECEBIDA":
            continue
        if str(acao.get("evidencia_anexada_em") or "").strip():
            continue
        message_id = str(acao.get("resposta_graph_message_id") or "").strip()
        if not message_id:
            resposta = localizar_resposta_por_chamado(
                caixa_postal=caixa, chamado_id=chamado_id, recebidas_apos=str(acao.get("enviado_em") or "")
            )
            message_id = str(resposta.get("id") or "").strip() if resposta else ""
        if not message_id:
            pendentes.append(chamado_id)
            continue
        try:
            # Não duplica a nota histórica: neste reparo anexa somente a evidência, com nota curta de auditoria.
            filename = _nome_evidencia(chamado_id, str(acao.get("resposta_recebida_em") or ""), regra_id)
            eml = baixar_mensagem_eml(caixa_postal=caixa, message_id=message_id)
            from ednna.redmine_writer import upload_arquivo_redmine
            upload = upload_arquivo_redmine(conteudo=eml, filename=filename)
            # PUT específico para anexar o token, sem alterar status/responsável.
            import requests as _requests
            from ednna.redmine_writer import REDMINE_URL as _RU, _headers as _rh
            r = _requests.put(
                f"{_RU}/issues/{chamado_id}.json", headers=_rh(),
                json={"issue": {"notes": "*EDNNA — Evidência documental*\n\nE-mail original do retorno da GETNET anexado ao chamado para rastreabilidade.",
                                "uploads": [{"token": upload["token"], "filename": filename,
                                             "content_type": "message/rfc822",
                                             "description": "Evidência original do retorno da GETNET"}]}},
                timeout=(20, 60),
            )
            if r.status_code not in {200, 204}:
                raise RuntimeError(f"HTTP {r.status_code} - {r.text[:500]}")
            marcar_evidencia_anexada(chamado_id, regra_id, filename)
            anexadas.append(chamado_id)
            print(f"[EDNNA] Evidência Redmine | anexada retroativamente | chamado={chamado_id} | arquivo={filename}", flush=True)
        except Exception as exc:
            registrar_falha_evidencia(chamado_id, regra_id, str(exc))
            erros.append(chamado_id)
            print(f"[EDNNA] Evidência Redmine | falha | chamado={chamado_id} | {type(exc).__name__}: {exc}", flush=True)
    print(f"[EDNNA] Evidência auditoria | anexadas_ids={anexadas} | pendentes_ids={pendentes} | erros_ids={erros}", flush=True)
    return {"anexadas": anexadas, "pendentes": pendentes, "erros": erros}

def _sincronizar_respostas_pendentes_redmine() -> int:
    """Tenta descarregar no Redmine respostas já preservadas no SQLite."""
    sincronizadas = 0
    for acao in listar_respostas_pendentes_redmine():
        chamado_id = int(acao.get("chamado_id") or 0)
        regra_id = str(acao.get("regra_id") or "")
        corpo = str(acao.get("resposta_corpo") or "")
        remetente = str(acao.get("resposta_remetente") or "")
        assunto = str(acao.get("resposta_assunto") or "")
        recebida_em = str(acao.get("resposta_recebida_em") or "")
        nota = _nota_retorno(remetente=remetente, assunto=assunto, corpo=corpo, recebida_em=recebida_em)
        assigned_to = int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
        status = str(os.getenv("EDNNA_STATUS_RESPOSTA_RECEBIDA", "Em andamento") or "Em andamento")
        if regra_id == "CANCELAMENTO-GETNET-001":
            extra, assigned_to, status = _processar_retorno_getnet(chamado_id, corpo)
            nota += extra
        elif "VR-BENEFICIOS" in regra_id.upper():
            extra, assigned_to, status = _processar_retorno_vr(chamado_id, corpo)
            nota += extra
        elif "SICREDI" in regra_id.upper():
            extra, assigned_to, status = _processar_retorno_sicredi(chamado_id, corpo)
            nota += extra
        try:
            message_id = str(acao.get("resposta_graph_message_id") or "")
            if message_id and not str(acao.get("evidencia_anexada_em") or ""):
                _anexar_evidencia_retorno(
                    caixa=str(os.getenv("EDNNA_EMAIL_FROM", "edi@netunna.com.br") or ""),
                    chamado_id=chamado_id, regra_id=regra_id, message_id=message_id,
                    nota=nota, status=status, assigned_to=assigned_to, recebida_em=recebida_em,
                )
            else:
                registrar_email_e_status_chamado(
                    chamado_id=chamado_id, nota=nota, status_nome=status, assigned_to_id=assigned_to,
                )
            marcar_status_redmine(chamado_id, regra_id, status)
            marcar_resposta_sincronizada_redmine(chamado_id, regra_id)
            sincronizadas += 1
            print(f"[EDNNA] Redmine pendente | sincronizado | chamado={chamado_id}", flush=True)
        except Exception as exc:
            registrar_falha_redmine(chamado_id, regra_id, f"Sincronização pendente: {exc}")
            print(f"[EDNNA] Redmine pendente | ainda indisponível | chamado={chamado_id} | {type(exc).__name__}: {exc}", flush=True)
    return sincronizadas


def executar_monitoramento_respostas() -> dict:
    resumo = {
        "habilitado": _bool_env("EDNNA_MONITOR_EMAIL_ENABLED", True),
        "aguardando": 0,
        "consultados": 0,
        "respostas": 0,
        "sem_resposta": 0,
        "erros": 0,
        "detalhes": [],
        "reconciliados": 0,
    }
    if not resumo["habilitado"]:
        return resumo

    # EDDY 4.2.1 — operação primeiro. Aprendizado/enriquecimento remoto não
    # disputa o gateway quando o Redmine já está degradado.
    try:
        from painel_cache import circuit_breaker_ativo as _redmine_breaker_ativo
        if _redmine_breaker_ativo():
            print("[EDDY] Aprendizado remoto suspenso | motivo=CIRCUIT_BREAKER | prioridade=OPERACAO", flush=True)
        else:
            limite_enriquecimento = max(0, int(os.getenv("EDDY_LEARNING_ENRICH_MAX_PER_CYCLE", "2") or 2))
            enriquecimento = processar_enriquecimentos_pendentes(limite=limite_enriquecimento) if limite_enriquecimento else {}
            if enriquecimento.get("consultados"):
                resumo["detalhes"].append({"enriquecimento_contexto": enriquecimento})
            if enriquecimento.get("atualizados"):
                reaprendizado = reprocessar_aprendizados_incompletos(enriquecimento.get("atualizados"))
                if reaprendizado.get("reprocessadas"):
                    resumo["detalhes"].append({"reaprendizado": reaprendizado})
    except Exception as exc:
        print(f"[EDNNA] Enriquecimento assíncrono | falha geral | {type(exc).__name__}: {exc}", flush=True)

    caixa = str(os.getenv("EDNNA_EMAIL_FROM", "edi@netunna.com.br") or "").strip()
    try:
        auditoria = _auditar_processados_redmine(caixa)
        if auditoria.get("reparo"):
            resumo["detalhes"].append({"reparo_pendente": auditoria.get("reparo")})
    except Exception as exc:
        print(f"[EDNNA] Auditoria conclusão | falha | {type(exc).__name__}: {exc}", flush=True)
    try:
        evidencias = _reconciliar_evidencias_processadas(caixa)
        if evidencias.get("anexadas"):
            resumo["detalhes"].append({"evidencias_anexadas": evidencias.get("anexadas")})
    except Exception as exc:
        print(f"[EDNNA] Evidência auditoria | falha | {type(exc).__name__}: {exc}", flush=True)
    try:
        pendentes_sync = _sincronizar_respostas_pendentes_redmine()
        if pendentes_sync:
            resumo["detalhes"].append({"redmine_pendentes_sincronizados": pendentes_sync})
    except Exception as exc:
        print(f"[EDNNA] Redmine pendente | falha na fila | {type(exc).__name__}: {exc}", flush=True)
    status_retorno = str(os.getenv("EDNNA_STATUS_RESPOSTA_RECEBIDA", "Em andamento") or "Em andamento").strip()
    try:
        reconciliados = _reconciliar_cancelamentos_getnet_orfaos(caixa)
        resumo["reconciliados"] = len({x.get("chamado") for x in reconciliados if x.get("chamado")})
        resumo["detalhes"].extend(reconciliados)
    except Exception as exc:
        resumo["erros"] += 1
        resumo["detalhes"].append({"reconciliacao": f"{type(exc).__name__}: {exc}"})
        print(f"[EDNNA] Monitor e-mail | reconciliação falhou | {type(exc).__name__}: {exc}", flush=True)

    acoes = listar_acoes_aguardando_resposta()
    resumo["aguardando"] = len(acoes)

    for acao in acoes:
        chamado_id = int(acao["chamado_id"])
        regra_id = str(acao["regra_id"])
        # v3.32.5 — chamado terminal não é mais acompanhado pela EDNNA.
        # O pre-flight é fresco para impedir que um Rejeitado continue recebendo
        # monitoramento/follow-up por causa de estado local antigo.
        try:
            from ednna.status_guard import preflight_chamado_ativo, encerrar_acompanhamento_terminal
            _pf = preflight_chamado_ativo(chamado_id)
            if _pf.get("bloquear"):
                if _pf.get("motivo") == "ESTADO_TERMINAL":
                    encerrar_acompanhamento_terminal(chamado_id, _pf.get("estado") or "")
                    print(f"[EDNNA] Monitor ignorado | chamado={chamado_id} | estado_terminal={_pf.get('estado')}", flush=True)
                else:
                    print(f"[EDNNA] Monitor adiado | chamado={chamado_id} | preflight={_pf.get('motivo')}", flush=True)
                    try:
                        from ednna.observabilidade import log_event
                        log_event("REDMINE", "Monitor adiado pelo pre-flight", nivel="WARNING", chamado_id=chamado_id,
                                  regra_id=regra_id, detalhe=f"preflight={_pf.get('motivo')}", dedup_seconds=120)
                    except Exception:
                        pass
                continue
        except Exception as _pf_exc:
            print(f"[EDNNA] Monitor adiado | chamado={chamado_id} | preflight_erro={type(_pf_exc).__name__}: {_pf_exc}", flush=True)
            continue
        try:
            conversation_id, enviado = _resolver_conversation_id(acao, caixa)
            resposta_fallback = None
            if not conversation_id:
                resposta_fallback = localizar_resposta_por_chamado(
                    caixa_postal=caixa, chamado_id=chamado_id,
                    recebidas_apos=str(acao.get("enviado_em", "") or ""),
                )
                if not resposta_fallback:
                    resumo["sem_resposta"] += 1
                    resumo["detalhes"].append({
                        "chamado": chamado_id, "regra": regra_id,
                        "situacao": "CONVERSA_NAO_LOCALIZADA",
                    })
                    continue

            marcar_monitorado(
                chamado_id,
                regra_id,
                graph_message_id=str(enviado.get("id", "") or ""),
                graph_conversation_id=conversation_id,
                graph_internet_message_id=str(enviado.get("internetMessageId", "") or ""),
            )

            mensagens = []
            if conversation_id:
                mensagens = listar_mensagens_conversa(
                    caixa_postal=caixa, conversation_id=conversation_id,
                    recebidas_apos=str(acao.get("enviado_em", "") or ""),
                )
            resumo["consultados"] += 1

            resposta = resposta_fallback
            if not resposta:
                for msg in mensagens:
                    if _remetente(msg).casefold() != caixa.casefold():
                        resposta = msg
                        break

            if not resposta:
                resumo["sem_resposta"] += 1
                continue

            remetente = _remetente(resposta)
            assunto = str(resposta.get("subject", "") or "").strip()
            corpo = _somente_resposta_nova(_texto_corpo(resposta))
            recebida_em = str(resposta.get("receivedDateTime", "") or "")
            nota = _nota_retorno(
                remetente=remetente, assunto=assunto, corpo=corpo, recebida_em=recebida_em,
            )
            assigned_to_retorno = int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166)
            status_efetivo = status_retorno
            if regra_id == "CANCELAMENTO-GETNET-001":
                extra, assigned_to_retorno, status_efetivo = _processar_retorno_getnet(chamado_id, corpo)
                nota += extra
            elif "VR-BENEFICIOS" in regra_id.upper():
                extra, assigned_to_retorno, status_efetivo = _processar_retorno_vr(chamado_id, corpo)
                nota += extra
            elif "SICREDI" in regra_id.upper():
                extra, assigned_to_retorno, status_efetivo = _processar_retorno_sicredi(chamado_id, corpo)
                nota += extra

            # v3.28.7.2: o e-mail é persistido ANTES do Redmine. Se o Redmine
            # estiver indisponível, a resposta não se perde e será sincronizada
            # em ciclo posterior.
            registrar_resposta_pendente_redmine(
                chamado_id, regra_id,
                graph_message_id=str(resposta.get("id", "") or ""),
                remetente=remetente, assunto=assunto, corpo=corpo, recebida_em=recebida_em,
            )
            try:
                message_id = str(resposta.get("id", "") or "")
                _anexar_evidencia_retorno(
                    caixa=caixa, chamado_id=chamado_id, regra_id=regra_id, message_id=message_id,
                    nota=nota, status=status_efetivo, assigned_to=assigned_to_retorno, recebida_em=recebida_em,
                )
                marcar_status_redmine(chamado_id, regra_id, status_efetivo)
                marcar_resposta_sincronizada_redmine(chamado_id, regra_id)
                resumo["respostas"] += 1
            except Exception as redmine_exc:
                registrar_falha_redmine(chamado_id, regra_id, f"Resposta preservada; Redmine pendente: {redmine_exc}")
                resumo["detalhes"].append({
                    "chamado": chamado_id, "regra": regra_id,
                    "situacao": "RESPOSTA_PRESERVADA_REDMINE_PENDENTE",
                })
                print(
                    f"[EDNNA] Monitor e-mail | resposta preservada | chamado={chamado_id} | "
                    f"Redmine pendente: {type(redmine_exc).__name__}: {redmine_exc}", flush=True,
                )
                continue

            print(
                "[EDNNA] Monitor e-mail | resposta recebida | "
                f"chamado={chamado_id} | regra={regra_id} | de={remetente}",
                flush=True,
            )
            try:
                from ednna.observabilidade import log_event
                player = str(regra_id or "").replace("-001", "").split("-", 1)[-1]
                log_event("EMAIL", "Resposta recebida", chamado_id=chamado_id, regra_id=regra_id, player=player, detalhe=f"de={remetente}")
            except Exception:
                pass

        except Exception as exc:
            resumo["erros"] += 1
            resumo["detalhes"].append({
                "chamado": chamado_id,
                "regra": regra_id,
                "erro": f"{type(exc).__name__}: {exc}",
            })
            registrar_falha_redmine(chamado_id, regra_id, f"Monitor de respostas: {exc}")
            print(
                "[EDNNA] Monitor e-mail | erro | "
                f"chamado={chamado_id} | {type(exc).__name__}: {exc}",
                flush=True,
            )

    # v3.28.54 — executor automático também roda no worker de background.
    # Assim a EDNNA trabalha mesmo sem alguém abrir/recarregar a tela Streamlit.
    try:
        if _bool_env("EDNNA_AUTO_EXECUTE", True):
            import pandas as pd
            from ednna.classificador_demandas import enriquecer_dataframe_com_classificacoes
            from ednna.executor_automatico import executar_acoes_automaticas
            snapshot_auto = carregar_snapshot_chamados()
            if snapshot_auto:
                # EDDY 4.2: aprender ocorrências comuns usando somente o snapshot
                # local. Isso não consome chamadas pontuais ao Redmine e alimenta
                # a Escola com falta de arquivo/registro e demais padrões.
                try:
                    from ednna.aprendizado_ocorrencias import aprender_snapshot
                    resumo["aprendizado_ocorrencias"] = aprender_snapshot(
                        snapshot_auto,
                        limite=max(25, int(os.getenv("EDDY_OCCURRENCE_LEARNING_MAX_PER_CYCLE", "300") or 300)),
                    )
                    ao = resumo["aprendizado_ocorrencias"]
                    if int(ao.get("persistidos", 0) or 0):
                        print("[EDDY] Aprendizado ocorrências | " + " | ".join(
                            f"{k}={v}" for k,v in (ao.get("tipos") or {}).items()
                        ), flush=True)
                except Exception as occ_exc:
                    print(f"[EDDY] Aprendizado ocorrências | falha | {type(occ_exc).__name__}: {occ_exc}", flush=True)
                # v3.32.1 — histórico é trabalho da EDNNA, não do operador.
                # Antes a inclusão podia parar em AGUARDANDO_VERIFICACAO_HISTORICO
                # indefinidamente se ninguém abrisse a tela antiga que sincronizava journals.
                # Agora o próprio worker atualiza um lote antes de decidir/executar.
                try:
                    from painel_cache import circuit_breaker_ativo as _redmine_breaker_ativo
                    if _redmine_breaker_ativo():
                        resumo['historico_sincronizacao'] = {'suspenso': True, 'motivo': 'CIRCUIT_BREAKER'}
                        print('[EDDY] Histórico remoto suspenso | motivo=CIRCUIT_BREAKER | prioridade=OPERACAO', flush=True)
                    else:
                        from ednna.sincronizador_journals import sincronizar_proximo_lote
                        frame_journals = pd.DataFrame(snapshot_auto)
                        limite_hist = max(0, int(os.getenv('EDNNA_HISTORY_SYNC_MAX_PER_CYCLE', '4') or 4))
                        resumo['historico_sincronizacao'] = sincronizar_proximo_lote(frame_journals, limite=limite_hist) if limite_hist else {}
                        hs = resumo.get('historico_sincronizacao') or {}
                        if int(hs.get('processados', 0) or 0):
                            print(
                                '[EDNNA] Histórico automático | '
                                f"processados={hs.get('processados',0)} | sucesso={hs.get('sucesso',0)} | "
                                f"ja_atuados={hs.get('ja_atuados',0)} | aguardando={hs.get('aguardando',0)} | erros={hs.get('erros',0)}",
                                flush=True,
                            )
                except Exception as hist_exc:
                    print(f'[EDNNA] Histórico automático | falha | {type(hist_exc).__name__}: {hist_exc}', flush=True)
                # P0: materializa primeiro a fila local do EDDY. Assim, mesmo com
                # Redmine lento/indisponível, o operador recebe as demandas em segundos.
                from ednna.motor_inclusoes_operacional import gerar_demandas_operacionais
                limite_demandas = max(1, int(os.getenv("EDDY_DEMAND_MAX_PER_CYCLE", "50") or 50))
                resumo["demandas_operacionais"] = gerar_demandas_operacionais(
                    pd.DataFrame(snapshot_auto), limite=limite_demandas
                )

                # Só depois da fila local partimos para ações que exigem pre-flight remoto.
                frame_auto = enriquecer_dataframe_com_classificacoes(pd.DataFrame(snapshot_auto))
                resumo_auto = executar_acoes_automaticas(frame_auto)
                resumo["execucao_automatica"] = resumo_auto
                from ednna.motor_inclusoes_operacional import executar_inclusoes_automaticas
                resumo["inclusoes_automaticas"] = executar_inclusoes_automaticas(pd.DataFrame(snapshot_auto))

                # A fila de inclusão chama muitos chamados de "continuidade", mas isso
                # não significa que todos estejam efetivamente sendo acompanhados.
                # Explicamos o balde inteiro a cada ciclo para tornar visíveis órfãos,
                # follow-ups vencidos e pendências de Redmine.
                from ednna.motor_inclusoes_operacional import diagnosticar_continuidade_operacional
                continuidade = diagnosticar_continuidade_operacional(pd.DataFrame(snapshot_auto))
                resumo["continuidade_operacional"] = continuidade
                cr = continuidade.get("resumo") or {}
                if int(cr.get("total", 0) or 0):
                    print(
                        "[EDNNA] Continuidade operacional | "
                        f"total={cr.get('total',0)} | aguardando_prazo={cr.get('aguardando_prazo',0)} | "
                        f"followup_auto={cr.get('followup_automatico',0)} | followup_assistido={cr.get('followup_assistido',0)} | "
                        f"redmine_pendente={cr.get('redmine_pendente',0)} | sem_thread={cr.get('sem_thread',0)} | "
                        f"atuacao_sem_acompanhamento={cr.get('atuacao_previa_sem_acompanhamento',0)} | "
                        f"estado_sem_acompanhamento={cr.get('estado_redmine_sem_acompanhamento',0)} | "
                        f"limite_followup={cr.get('limite_followup',0)}",
                        flush=True,
                    )
                    orfaos = [
                        x for x in continuidade.get("itens", [])
                        if x.get("estado_motor") in {"CONTINUIDADE_ATUACAO_PREVIA", "CONTINUIDADE_ESTADO_REDMINE"}
                    ]
                    if orfaos:
                        print(
                            "[EDNNA] Continuidade órfã | "
                            + " | ".join(
                                f"#{x.get('chamado_id')}:{x.get('proxima_acao')}" for x in orfaos[:20]
                            ),
                            flush=True,
                        )
                        # Retoma gradualmente o estoque legado. O primeiro passo
                        # é reconstruir journals/histórico; nenhuma ação externa
                        # é executada nesta fase. Assim chamados como #47543
                        # deixam de ser apenas "continuidade" e passam a ter
                        # evidência suficiente para a próxima decisão.
                        from painel_cache import circuit_breaker_ativo as _redmine_breaker_ativo
                        if _redmine_breaker_ativo():
                            resumo["retomada_continuidade"] = {"suspenso": True, "motivo": "CIRCUIT_BREAKER"}
                            print("[EDDY] Retomada histórica suspensa | motivo=CIRCUIT_BREAKER | classificação=LOCAL_FIRST", flush=True)
                        else:
                            from ednna.motor_inclusoes_operacional import reconstruir_continuidades_orfas
                            limite_retomada = max(0, int(os.getenv("EDNNA_CONTINUITY_REBUILD_MAX_PER_CYCLE", "12") or 12))
                            resumo["retomada_continuidade"] = reconstruir_continuidades_orfas(
                                pd.DataFrame(snapshot_auto), limite=limite_retomada
                            ) if limite_retomada else {}
                        # Depois de reconstruir evidências, classifica quem possui
                        # a próxima responsabilidade. Ainda é decisão read-only:
                        # handoff automático entra somente após observarmos os logs.
                        try:
                            from ednna.continuidade_responsabilidade import classificar_lote
                            responsabilidade = classificar_lote(
                                pd.DataFrame(snapshot_auto), continuidade,
                                limite=max(1, int(os.getenv("EDDY_CONTINUITY_CLASSIFY_MAX_PER_CYCLE", "30") or 30)),
                            )
                            resumo["responsabilidade_continuidade"] = responsabilidade
                            if responsabilidade.get("total"):
                                print(
                                    "[EDDY] Responsabilidade continuidade | "
                                    + " | ".join(f"{k}={v}" for k,v in (responsabilidade.get("decisoes") or {}).items()),
                                    flush=True,
                                )
                                # Decisão individual auditável: permite validar casos reais
                                # antes de habilitar qualquer handoff automático.
                                for x in responsabilidade.get("itens",[])[:30]:
                                    atual=x.get("responsavel_atual") or {}
                                    origem=x.get("responsavel_origem") or {}
                                    print(
                                        "[EDDY] Responsabilidade item | "
                                        f"#{x.get('chamado_id')} | decisao={x.get('decisao')} | "
                                        f"atual={atual.get('nome') or atual.get('id') or '-'} | "
                                        f"atual_id={atual.get('id','-')} | "
                                        f"origem={origem.get('nome') or origem.get('id') or '-'} | "
                                        f"origem_id={origem.get('id','-')} | "
                                        f"confianca={x.get('confianca','-')} | motivo={x.get('motivo','')}",
                                        flush=True,
                                    )
                                pendentes=[x for x in responsabilidade.get("itens",[]) if x.get("decisao") in {"DEVOLVER_ORIGEM","DECISAO_HUMANA","ACAO_EDDY_DUE"}]
                                if pendentes:
                                    print("[EDDY] Próximas responsabilidades | " + " | ".join(
                                        f"#{x.get('chamado_id')}:{x.get('decisao')}:{x.get('responsavel_origem',{}).get('id','-')}"
                                        for x in pendentes[:20]
                                    ), flush=True)
                        except Exception as resp_exc:
                            print(f"[EDDY] Responsabilidade continuidade | falha | {type(resp_exc).__name__}: {resp_exc}", flush=True)
                if int(resumo_auto.get("enviados",0) or 0) or int(resumo_auto.get("redmine_pendente",0) or 0):
                    print(
                        "[EDNNA] Executor background | "
                        f"enviados={resumo_auto.get('enviados',0)} | redmine_ok={resumo_auto.get('redmine_ok',0)} | "
                        f"redmine_pendente={resumo_auto.get('redmine_pendente',0)} | erros={resumo_auto.get('erros_envio',0)}",
                        flush=True,
                    )
    except Exception as exc:
        print(f"[EDNNA] Executor background | falha geral | {type(exc).__name__}: {exc}", flush=True)

    # v3.28.38 — continuidade: após confirmar que não houve resposta, avalia follow-ups vencidos.
    try:
        from ednna.followup_engine import avaliar_followups, executar_followup, followup_automatico
        followups = avaliar_followups()
        resumo["followups_prontos"] = int(followups.get("prontos", 0) or 0)
        resumo["followups_automaticos_prontos"] = int(followups.get("automaticos_prontos", 0) or 0)
        resumo["followups_assistidos_prontos"] = int(followups.get("assistidos_prontos", 0) or 0)
        resumo["followups_enviados"] = 0
        resumo["followups_bloqueados"] = 0
        resumo["followups_falhos"] = 0
        auto = str(os.getenv("EDNNA_FOLLOWUP_AUTO", "true") or "true").strip().casefold() in {"1","true","sim","yes","on"}
        if auto:
            limite = max(1, int(os.getenv("EDNNA_FOLLOWUP_MAX_PER_CYCLE", "3") or 3))
            for item in [x for x in followups.get("itens", []) if x.get("estado_followup") == "FOLLOWUP_PRONTO" and followup_automatico(x)][:limite]:
                try:
                    resultado_followup = executar_followup(item)
                    if resultado_followup.get("ok"):
                        resumo["followups_enviados"] += 1
                    else:
                        resumo["followups_bloqueados"] += 1
                        print(
                            f"[EDNNA] Follow-up não enviado | chamado={item.get('chamado_id')} | "
                            f"estado={resultado_followup.get('estado')} | motivo={resultado_followup.get('motivo')}",
                            flush=True,
                        )
                except Exception as exc:
                    resumo["erros"] += 1
                    resumo["followups_falhos"] += 1
                    print(f"[EDNNA] Follow-up pendente | chamado={item.get('chamado_id')} | {type(exc).__name__}: {exc}", flush=True)
        if resumo.get("followups_prontos") or resumo.get("followups_enviados"):
            print(f"[EDNNA] Continuidade | followups_prontos={resumo.get('followups_prontos',0)} | automaticos_prontos={resumo.get('followups_automaticos_prontos',0)} | assistidos_prontos={resumo.get('followups_assistidos_prontos',0)} | followups_enviados={resumo.get('followups_enviados',0)}", flush=True)
            try:
                from ednna.observabilidade import log_event
                log_event("FOLLOWUP", "Ciclo de follow-ups avaliado",
                          detalhe=f"prontos={resumo.get('followups_prontos',0)} | automaticos={resumo.get('followups_automaticos_prontos',0)} | assistidos={resumo.get('followups_assistidos_prontos',0)} | enviados={resumo.get('followups_enviados',0)} | bloqueados={resumo.get('followups_bloqueados',0)} | falhos={resumo.get('followups_falhos',0)}", dedup_seconds=300)
            except Exception:
                pass
    except Exception as exc:
        print(f"[EDNNA] Continuidade | falha geral | {type(exc).__name__}: {exc}", flush=True)

    # Repara efeitos pós-envio que ficaram pendentes por indisponibilidade do Redmine.
    try:
        from ednna.redmine_outbox import reconciliar_redmine_pendentes
        resumo["redmine_reconciliacao"] = reconciliar_redmine_pendentes(10)
    except Exception as exc:
        print(f"[EDNNA] Redmine reconciliação | falha geral | {type(exc).__name__}: {exc}", flush=True)

    return resumo


def _loop() -> None:
    intervalo = max(300, int(os.getenv("EDNNA_MONITOR_EMAIL_INTERVAL_SECONDS", "900") or 900))
    atraso_inicial = max(10, int(os.getenv("EDNNA_MONITOR_EMAIL_INITIAL_DELAY_SECONDS", "30") or 30))
    print(
        "[EDNNA] Monitor e-mail | aguardando primeiro ciclo | "
        f"em={atraso_inicial}s | intervalo={intervalo}s",
        flush=True,
    )
    if _STOP.wait(atraso_inicial):
        return

    while not _STOP.is_set():
        try:
            print("[EDNNA] Monitor e-mail | iniciando ciclo", flush=True)
            resumo = executar_monitoramento_respostas()
            print(
                "[EDNNA] Monitor e-mail | ciclo concluído | "
                f"aguardando={resumo['aguardando']} | respostas={resumo['respostas']} | "
                f"sem_resposta={resumo['sem_resposta']} | erros={resumo['erros']}",
                flush=True,
            )
            print(
                "[EDNNA] Monitor e-mail | próximo ciclo | "
                f"em={intervalo}s",
                flush=True,
            )
        except Exception as exc:
            print(f"[EDNNA] Monitor e-mail | falha no ciclo | {type(exc).__name__}: {exc}", flush=True)
            print(
                "[EDNNA] Monitor e-mail | próximo ciclo após falha | "
                f"em={intervalo}s",
                flush=True,
            )

        _STOP.wait(intervalo)


def iniciar_monitor_respostas_background() -> bool:
    global _THREAD
    if not _bool_env("EDNNA_MONITOR_EMAIL_ENABLED", True):
        return False

    with _THREAD_LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return False
        _THREAD = threading.Thread(
            target=_loop,
            name="ednna-monitor-respostas",
            daemon=True,
        )
        _THREAD.start()
        print("[EDNNA] Monitor e-mail | background iniciado", flush=True)
        return True
