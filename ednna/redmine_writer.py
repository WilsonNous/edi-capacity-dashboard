from __future__ import annotations

import os
from datetime import datetime
from time import sleep
from zoneinfo import ZoneInfo

import requests


TZ_BRASIL = ZoneInfo("America/Sao_Paulo")

REDMINE_URL = str(
    os.getenv(
        "REDMINE_URL",
        "https://chamados.nteia.com",
    )
    or ""
).rstrip("/")

REDMINE_API_KEY = str(
    os.getenv(
        "REDMINE_API_KEY",
        "",
    )
    or ""
).strip()

REDMINE_AUTHORIZATION = str(
    os.getenv(
        "REDMINE_AUTHORIZATION",
        "",
    )
    or ""
).strip()


class RedmineWriteError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not REDMINE_API_KEY:
        raise RedmineWriteError(
            "REDMINE_API_KEY não configurada."
        )

    headers = {
        "X-Redmine-API-Key": REDMINE_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if REDMINE_AUTHORIZATION:
        headers[
            "Authorization"
        ] = REDMINE_AUTHORIZATION

    return headers


def _formatar_data_hora(
    valor_iso: str,
) -> str:
    if not valor_iso:
        return ""

    try:
        dt = datetime.fromisoformat(
            valor_iso
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=TZ_BRASIL
            )

        dt = dt.astimezone(
            TZ_BRASIL
        )

        return dt.strftime(
            "%d/%m/%Y %H:%M"
        )

    except Exception:
        return str(
            valor_iso
        )


def montar_nota_email_enviado(
    *,
    remetente: str,
    para: list[str],
    cc: list[str],
    assunto: str,
    corpo: str,
    enviado_em: str,
    prazo_resposta_em: str,
) -> str:
    enviado_fmt = _formatar_data_hora(
        enviado_em
    )

    prazo_fmt = _formatar_data_hora(
        prazo_resposta_em
    )

    para_txt = "; ".join(
        para
        or []
    )

    cc_txt = "; ".join(
        cc
        or []
    )

    linhas = [
        "*EDNNA — E-mail enviado*",
        "",
        f"*De:* {remetente}",
        f"*Para:* {para_txt}",
    ]

    if cc_txt:
        linhas.append(
            f"*Cc:* {cc_txt}"
        )

    linhas.extend(
        [
            f"*Assunto:* {assunto}",
            "",
            corpo.strip(),
            "",
            "----",
            "",
            "*Acompanhamento EDNNA:* Aguardando resposta.",
            f"*Envio realizado em:* {enviado_fmt}",
            f"*Prazo previsto para resposta:* {prazo_fmt}",
        ]
    )

    return "\n".join(
        linhas
    ).strip()


def adicionar_nota_chamado(
    *,
    chamado_id: int,
    nota: str,
    tentativas: int = 3,
) -> dict:
    if not nota.strip():
        raise RedmineWriteError(
            "Nota do Redmine está vazia."
        )

    url = (
        f"{REDMINE_URL}/issues/"
        f"{int(chamado_id)}.json"
    )

    payload = {
        "issue": {
            "notes": nota,
        }
    }

    esperas = [
        0,
        2,
        5,
    ]

    ultimo_erro = None

    for tentativa in range(
        1,
        tentativas + 1,
    ):
        if tentativa > 1:
            espera = esperas[
                min(
                    tentativa - 1,
                    len(esperas) - 1,
                )
            ]

            print(
                "[EDNNA] Redmine journal | "
                f"nova tentativa em {espera}s | "
                f"chamado={chamado_id}",
                flush=True,
            )

            sleep(
                espera
            )

        try:
            print(
                "[EDNNA] Redmine journal | "
                f"PUT chamado={chamado_id} | "
                f"tentativa {tentativa}/{tentativas}",
                flush=True,
            )

            resposta = requests.put(
                url,
                headers=_headers(),
                json=payload,
                timeout=(
                    20,
                    60,
                ),
            )

            if resposta.status_code not in {
                200,
                204,
            }:
                raise RedmineWriteError(
                    "Falha ao atualizar chamado no Redmine: "
                    f"HTTP {resposta.status_code} - "
                    f"{resposta.text[:800]}"
                )

            print(
                "[EDNNA] Redmine journal | "
                f"OK chamado={chamado_id}",
                flush=True,
            )

            return {
                "ok": True,
                "status_code": resposta.status_code,
                "chamado_id": int(
                    chamado_id
                ),
            }

        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
            RedmineWriteError,
        ) as exc:
            ultimo_erro = exc

            print(
                "[EDNNA] Redmine journal | "
                f"falha chamado={chamado_id} | "
                f"tentativa {tentativa}/{tentativas} | "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

            if isinstance(
                exc,
                RedmineWriteError,
            ):
                # Erro HTTP funcional não deve ser repetido
                # indiscriminadamente, exceto 5xx.
                texto = str(
                    exc
                )

                if (
                    "HTTP 5" not in texto
                    and tentativa < tentativas
                ):
                    break

            if tentativa >= tentativas:
                break

    raise RedmineWriteError(
        str(
            ultimo_erro
            or "Falha desconhecida ao atualizar Redmine."
        )
    )
