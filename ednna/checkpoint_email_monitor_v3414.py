"""v3.34.14 — inclui checkpoints humanos pendentes na fila do monitor de e-mail.

Esta camada não conclui checkpoint automaticamente. Ela detecta e correlaciona o
retorno, preserva a evidência e sinaliza o checkpoint para interpretação/validação.
"""
from __future__ import annotations

import os
from typing import Any


def listar_checkpoints_email_pendentes() -> list[dict[str, Any]]:
    from ednna.checkpoints_humanos import inicializar_checkpoints, STATUS_PENDENTE
    from ednna.acompanhamento_acoes import _conectar
    inicializar_checkpoints()
    with _conectar() as conn:
        rows = conn.execute(
            """SELECT * FROM checkpoints_humanos
               WHERE status=?
               ORDER BY solicitado_em ASC""",
            (STATUS_PENDENTE,),
        ).fetchall()
    return [dict(r) for r in rows]


def _registrar_retorno_checkpoint(cp: dict, msg: dict, caixa: str) -> dict:
    """Preserva retorno/evidência sem afirmar que o checkpoint foi concluído."""
    from ednna.acompanhamento_acoes import _conectar, _iso, _agora
    from ednna.email_sender import baixar_mensagem_eml
    from ednna.redmine_writer import registrar_email_evidencia_e_status_chamado

    chamado_id = int(cp["chamado_id"])
    regra_id = str(cp["regra_id"])
    codigo = str(cp["codigo"])
    assunto = str(msg.get("subject") or "")
    recebido = str(msg.get("receivedDateTime") or "")
    remetente = str((((msg.get("from") or {}).get("emailAddress") or {}).get("address")) or "")
    message_id = str(msg.get("id") or "")
    filename = f"CHECKPOINT_{codigo}_{chamado_id}.eml"
    nota = "\n".join([
        "*EDNNA — Retorno relacionado a checkpoint humano*", "",
        f"*Checkpoint:* {cp.get('titulo') or codigo}",
        f"*Regra:* {regra_id}", f"*De:* {remetente}", f"*Assunto:* {assunto}",
        f"*Recebido em:* {recebido}", "",
        "*Situação:* retorno localizado e evidência preservada. O checkpoint ainda NÃO foi concluído automaticamente.",
        "*Próxima etapa:* EDNNA deve interpretar/validar o retorno antes de retomar o workflow.",
        f"*Marcador:* EDNNA-CHECKPOINT-RETORNO:{regra_id}:{codigo}",
    ])
    eml = baixar_mensagem_eml(caixa_postal=caixa, message_id=message_id)
    registrar_email_evidencia_e_status_chamado(
        chamado_id=chamado_id, nota=nota,
        status_nome=str(os.getenv("EDNNA_STATUS_RESPOSTA_RECEBIDA", "Em andamento") or "Em andamento"),
        assigned_to_id=int(os.getenv("REDMINE_EDNNA_USER_ID", "166") or 166),
        evidencia=eml, evidencia_filename=filename,
    )
    dados = {}
    try:
        import json
        dados = json.loads(str(cp.get("dados_json") or "{}"))
    except Exception:
        dados = {}
    dados["retorno_email"] = {
        "graph_message_id": message_id, "assunto": assunto, "remetente": remetente,
        "recebido_em": recebido, "evidencia": filename, "detectado_em": _iso(_agora()),
        "estado": "RETORNO_RECEBIDO_AGUARDANDO_VALIDACAO",
    }
    import json
    with _conectar() as conn:
        conn.execute(
            """UPDATE checkpoints_humanos SET dados_json=?
               WHERE id=? AND status='PENDENTE'""",
            (json.dumps(dados, ensure_ascii=False), int(cp["id"])),
        )
    print(f"[EDNNA] Monitor checkpoint | RETORNO_RECEBIDO | chamado={chamado_id} | regra={regra_id} | checkpoint={codigo} | assunto={assunto[:140]}", flush=True)
    return {"chamado_id": chamado_id, "regra_id": regra_id, "checkpoint": codigo, "resposta": True}


def monitorar_checkpoints_email(caixa: str) -> dict:
    from ednna.email_sender import localizar_resposta_por_chamado
    cps = listar_checkpoints_email_pendentes()
    # Se já preservamos retorno, não reprocessa a mesma pendência a cada ciclo.
    elegiveis = []
    for cp in cps:
        if "RETORNO_RECEBIDO_AGUARDANDO_VALIDACAO" in str(cp.get("dados_json") or ""):
            continue
        elegiveis.append(cp)
    ids = sorted({int(cp["chamado_id"]) for cp in elegiveis})
    print(f"[EDNNA] Monitor e-mail | checkpoints_aguardando={len(elegiveis)} | checkpoints_ids={ids}", flush=True)
    respostas, sem_resposta, erros, detalhes = 0, 0, 0, []
    for cp in elegiveis:
        chamado_id = int(cp["chamado_id"])
        codigo = str(cp["codigo"])
        regra_id = str(cp["regra_id"])
        print(f"[EDNNA] Monitor e-mail | candidato checkpoint | chamado={chamado_id} | regra={regra_id} | checkpoint={codigo}", flush=True)
        try:
            msg = localizar_resposta_por_chamado(
                caixa_postal=caixa, chamado_id=chamado_id,
                recebidas_apos=str(cp.get("solicitado_em") or ""),
            )
            if not msg:
                sem_resposta += 1
                continue
            detalhes.append(_registrar_retorno_checkpoint(cp, msg, caixa))
            respostas += 1
        except Exception as exc:
            erros += 1
            print(f"[EDNNA] Monitor checkpoint | ERRO | chamado={chamado_id} | {type(exc).__name__}: {exc}", flush=True)
    return {"aguardando": len(elegiveis), "respostas": respostas, "sem_resposta": sem_resposta, "erros": erros, "detalhes": detalhes}


def instalar() -> None:
    from ednna import monitor_respostas as monitor
    if getattr(monitor, "_V3414_CHECKPOINTS_INSTALADO", False):
        return
    original = monitor.executar_monitoramento_respostas

    def executar_monitoramento_respostas_v3414() -> dict:
        resumo = original()
        if not resumo.get("habilitado", True):
            return resumo
        caixa = str(os.getenv("EDNNA_EMAIL_FROM", "edi@netunna.com.br") or "").strip()
        try:
            cp = monitorar_checkpoints_email(caixa)
            resumo["checkpoints_aguardando"] = cp["aguardando"]
            resumo["checkpoints_respostas"] = cp["respostas"]
            resumo["checkpoints_sem_resposta"] = cp["sem_resposta"]
            resumo["erros"] = int(resumo.get("erros") or 0) + cp["erros"]
            resumo.setdefault("detalhes", []).extend(cp["detalhes"])
        except Exception as exc:
            resumo["erros"] = int(resumo.get("erros") or 0) + 1
            print(f"[EDNNA] Monitor checkpoint | falha geral | {type(exc).__name__}: {exc}", flush=True)
        return resumo

    monitor.executar_monitoramento_respostas = executar_monitoramento_respostas_v3414
    monitor._V3414_CHECKPOINTS_INSTALADO = True
