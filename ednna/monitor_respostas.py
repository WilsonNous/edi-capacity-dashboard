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
)
from ednna.email_sender import (
    listar_mensagens_conversa,
    localizar_email_enviado,
)
from ednna.redmine_writer import registrar_email_e_status_chamado


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
            "*Acompanhamento EDNNA:* Resposta recebida. Chamado devolvido para andamento operacional.",
        ]
    ).strip()


def _resolver_conversation_id(acao: dict, caixa: str) -> tuple[str, dict]:
    conversation_id = str(acao.get("graph_conversation_id", "") or "").strip()
    if conversation_id:
        return conversation_id, {}

    assunto = str(acao.get("email_assunto", "") or "").strip()
    if not assunto:
        return "", {}

    enviado = localizar_email_enviado(remetente=caixa, assunto=assunto)
    return str(enviado.get("conversationId", "") or "").strip(), enviado


def executar_monitoramento_respostas() -> dict:
    resumo = {
        "habilitado": _bool_env("EDNNA_MONITOR_EMAIL_ENABLED", True),
        "aguardando": 0,
        "consultados": 0,
        "respostas": 0,
        "sem_resposta": 0,
        "erros": 0,
        "detalhes": [],
    }
    if not resumo["habilitado"]:
        return resumo

    caixa = str(os.getenv("EDNNA_EMAIL_FROM", "edi@netunna.com.br") or "").strip()
    status_retorno = str(os.getenv("EDNNA_STATUS_RESPOSTA_RECEBIDA", "Em andamento") or "Em andamento").strip()
    acoes = listar_acoes_aguardando_resposta()
    resumo["aguardando"] = len(acoes)

    for acao in acoes:
        chamado_id = int(acao["chamado_id"])
        regra_id = str(acao["regra_id"])
        try:
            conversation_id, enviado = _resolver_conversation_id(acao, caixa)
            if not conversation_id:
                resumo["sem_resposta"] += 1
                resumo["detalhes"].append({
                    "chamado": chamado_id,
                    "regra": regra_id,
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

            mensagens = listar_mensagens_conversa(
                caixa_postal=caixa,
                conversation_id=conversation_id,
                recebidas_apos=str(acao.get("enviado_em", "") or ""),
            )
            resumo["consultados"] += 1

            resposta = None
            for msg in mensagens:
                if _remetente(msg).casefold() != caixa.casefold():
                    resposta = msg
                    break

            if not resposta:
                resumo["sem_resposta"] += 1
                continue

            remetente = _remetente(resposta)
            assunto = str(resposta.get("subject", "") or "").strip()
            corpo = _texto_corpo(resposta)
            recebida_em = str(resposta.get("receivedDateTime", "") or "")
            nota = _nota_retorno(
                remetente=remetente,
                assunto=assunto,
                corpo=corpo,
                recebida_em=recebida_em,
            )

            # Primeiro atualiza o sistema oficial. Só depois encerra o acompanhamento local.
            registrar_email_e_status_chamado(
                chamado_id=chamado_id,
                nota=nota,
                status_nome=status_retorno,
            )
            marcar_status_redmine(chamado_id, regra_id, status_retorno)
            registrar_resposta(
                chamado_id,
                regra_id,
                graph_message_id=str(resposta.get("id", "") or ""),
                remetente=remetente,
                assunto=assunto,
                corpo=corpo,
                recebida_em=recebida_em,
            )
            resumo["respostas"] += 1

            print(
                "[EDNNA] Monitor e-mail | resposta recebida | "
                f"chamado={chamado_id} | regra={regra_id} | de={remetente}",
                flush=True,
            )

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
