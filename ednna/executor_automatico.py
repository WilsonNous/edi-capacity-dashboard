from __future__ import annotations

import os
from typing import Any

import pandas as pd

from ednna.acompanhamento_acoes import (
    adquirir_envio,
    confirmar_envio_real,
    marcar_redmine_atualizado,
    marcar_status_redmine,
    registrar_falha_envio,
    registrar_falha_redmine,
)
from ednna.email_sender import (
    enviar_email_graph,
)
from ednna.motor_acoes import (
    avaliar_acao,
    gerar_rascunho,
    localizar_regra_operacional,
)
from ednna.redmine_writer import (
    montar_nota_email_enviado,
    registrar_email_e_status_chamado,
)


def _bool_env(
    nome: str,
    padrao: bool,
) -> bool:
    valor = str(
        os.getenv(
            nome,
            "true" if padrao else "false",
        )
        or ""
    ).strip().casefold()

    return valor in {
        "1",
        "true",
        "sim",
        "yes",
        "on",
    }


def _chamado_int(
    valor: Any,
) -> int:
    return int(
        float(
            str(
                valor
            )
        )
    )


def executar_acoes_automaticas(
    frame: pd.DataFrame,
) -> dict:
    """
    Executa apenas regras explicitamente marcadas como:
      auto_executar=true
      executavel=true

    Segurança:
      - usa lock SQLite por chamado/regra;
      - chamado já enviado não é reenviado;
      - falha de Redmine não reabre o envio de e-mail;
      - exceções da regra continuam sendo respeitadas.
    """
    resumo = {
        "habilitado": _bool_env(
            "EDNNA_AUTO_EXECUTE",
            True,
        ),
        "avaliados": 0,
        "enviados": 0,
        "ja_processados": 0,
        "ignorados": 0,
        "erros_envio": 0,
        "redmine_ok": 0,
        "redmine_pendente": 0,
        "detalhes": [],
    }

    if not resumo["habilitado"]:
        return resumo

    if (
        frame is None
        or not isinstance(
            frame,
            pd.DataFrame,
        )
        or frame.empty
    ):
        return resumo

    limite = int(
        os.getenv(
            "EDNNA_AUTO_MAX_PER_RUN",
            "20",
        )
        or 20
    )

    enviados_nesta_execucao = 0

    for _, row in frame.iterrows():
        if enviados_nesta_execucao >= limite:
            break

        resumo[
            "avaliados"
        ] += 1

        avaliacao = avaliar_acao(
            row
        )

        if not avaliacao.get(
            "apto_rascunho"
        ):
            resumo[
                "ignorados"
            ] += 1
            continue

        regra = localizar_regra_operacional(
            row
        ) or {}

        if not (
            regra.get(
                "auto_executar",
                False,
            )
            and regra.get(
                "executavel",
                False,
            )
        ):
            resumo[
                "ignorados"
            ] += 1
            continue

        chamado_id = _chamado_int(
            row.get("#")
        )

        regra_id = str(
            regra.get(
                "id",
                ""
            )
            or ""
        )

        adquirido, estado_lock = adquirir_envio(
            chamado_id,
            regra_id,
        )

        if not adquirido:
            resumo[
                "ja_processados"
            ] += 1
            continue

        rascunho = gerar_rascunho(
            row
        )

        try:
            enviar_email_graph(
                remetente=rascunho.get(
                    "remetente",
                    "edi@netunna.com.br",
                ),
                para=rascunho.get(
                    "destinatarios",
                    [],
                ),
                cc=rascunho.get(
                    "cc",
                    [],
                ),
                assunto=rascunho.get(
                    "assunto",
                    "",
                ),
                corpo=rascunho.get(
                    "corpo",
                    "",
                ),
            )

            acompanhamento = confirmar_envio_real(
                chamado_id,
                regra_id,
                prazo_dias_uteis=(
                    rascunho.get(
                        "prazo_resposta_dias_uteis",
                        1,
                    )
                ),
            )

            resumo[
                "enviados"
            ] += 1
            enviados_nesta_execucao += 1

        except Exception as exc:
            registrar_falha_envio(
                chamado_id,
                regra_id,
                str(
                    exc
                ),
            )

            resumo[
                "erros_envio"
            ] += 1

            resumo[
                "detalhes"
            ].append(
                {
                    "chamado": chamado_id,
                    "regra": regra_id,
                    "etapa": "EMAIL",
                    "erro": str(
                        exc
                    ),
                }
            )

            continue

        try:
            nota = montar_nota_email_enviado(
                remetente=rascunho.get(
                    "remetente",
                    "edi@netunna.com.br",
                ),
                para=rascunho.get(
                    "destinatarios",
                    [],
                ),
                cc=rascunho.get(
                    "cc",
                    [],
                ),
                assunto=rascunho.get(
                    "assunto",
                    "",
                ),
                corpo=rascunho.get(
                    "corpo",
                    "",
                ),
                enviado_em=acompanhamento.get(
                    "enviado_em",
                    "",
                ),
                prazo_resposta_em=acompanhamento.get(
                    "prazo_resposta_em",
                    "",
                ),
            )

            registrar_email_e_status_chamado(
                chamado_id=chamado_id,
                nota=nota,
                status_nome=str(
                    regra.get(
                        "status_pos_envio",
                        "Aguardando Retorno Cliente",
                    )
                    or "Aguardando Retorno Cliente"
                ),
                data_inicio=acompanhamento.get(
                    "enviado_em",
                    "",
                ),
                data_fim=acompanhamento.get(
                    "prazo_resposta_em",
                    "",
                ),
            )

            marcar_redmine_atualizado(
                chamado_id,
                regra_id,
            )

            marcar_status_redmine(
                chamado_id,
                regra_id,
                str(
                    regra.get(
                        "status_pos_envio",
                        "Aguardando Retorno Cliente",
                    )
                    or "Aguardando Retorno Cliente"
                ),
            )

            resumo[
                "redmine_ok"
            ] += 1

        except Exception as exc:
            registrar_falha_redmine(
                chamado_id,
                regra_id,
                str(
                    exc
                ),
            )

            resumo[
                "redmine_pendente"
            ] += 1

            resumo[
                "detalhes"
            ].append(
                {
                    "chamado": chamado_id,
                    "regra": regra_id,
                    "etapa": "REDMINE",
                    "erro": str(
                        exc
                    ),
                }
            )

    return resumo
