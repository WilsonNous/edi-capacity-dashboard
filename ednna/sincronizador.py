from __future__ import annotations

from typing import Any

import pandas as pd

from ednna.armazenamento import (
    obter_alterado_em,
    obter_chamado,
    salvar_chamado,
    salvar_metadado,
    agora_brasil_iso,
)


# ============================================================
# EDNNA — INTELIGÊNCIA OPERACIONAL EDI
# Módulo: Sincronizador
# ============================================================


def _inteiro_seguro(
    valor: Any,
) -> int | None:
    """
    Converte IDs vindos do DataFrame em inteiro.
    """

    try:
        valor_int = int(valor)

        if valor_int <= 0:
            return None

        return valor_int

    except (TypeError, ValueError):
        return None


def _texto(valor: Any) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    return str(valor).strip()


def normalizar_marca_alteracao(
    valor: Any,
) -> str:
    """
    Normaliza o campo Alterado para comparação estável.

    Evita considerar o mesmo instante como diferente por causa
    de representações como:
      2026-09-03 18:40:00
      2026-09-03T18:40:00
      2026-09-03T18:40:00+00:00
    """
    texto = _texto(valor)

    if not texto:
        return ""

    try:
        data = pd.to_datetime(
            texto,
            errors="raise",
            utc=True,
        )

        if isinstance(data, pd.Timestamp):
            return data.isoformat()

    except Exception:
        pass

    return texto


# ============================================================
# SINCRONIZAÇÃO DO SNAPSHOT
# ============================================================

def sincronizar_dataframe(
    frame: pd.DataFrame,
    reconciliar_ausentes: bool = True,
) -> dict:
    """
    Salva no SQLite o snapshot que já foi carregado
    pelo dashboard.

    IMPORTANTE:

    Esta função NÃO consulta o Redmine.

    Ela apenas utiliza dados que o dashboard já possui.

    Retorna estatísticas da sincronização.
    """

    resultado = {
        "recebidos": 0,
        "novos": 0,
        "alterados": 0,
        "sem_alteracao": 0,
        "ignorados": 0,
        "erros": 0,
        "ausentes_detectados": 0,
        "ausentes_verificados": 0,
        "encerrados_reconciliados": 0,
        "ausentes_indisponiveis": 0,
    }

    if frame is None:
        return resultado

    if not isinstance(frame, pd.DataFrame):
        return resultado

    if frame.empty:
        return resultado

    if "#" not in frame.columns:
        return resultado

    resultado["recebidos"] = len(frame)

    for _, linha in frame.iterrows():

        chamado_id = _inteiro_seguro(
            linha.get("#")
        )

        if chamado_id is None:
            resultado["ignorados"] += 1
            continue

        try:

            dados = linha.to_dict()

            alterado_atual = normalizar_marca_alteracao(
                dados.get("Alterado")
            )

            alterado_cache = normalizar_marca_alteracao(
                obter_alterado_em(
                    chamado_id
                )
            )

            # ------------------------------------------------
            # CHAMADO NOVO
            # ------------------------------------------------

            if not alterado_cache:

                salvar_chamado(
                    chamado_id,
                    dados,
                )

                resultado["novos"] += 1

                continue

            # ------------------------------------------------
            # CHAMADO ALTERADO
            # ------------------------------------------------

            if alterado_atual != alterado_cache:

                salvar_chamado(
                    chamado_id,
                    dados,
                )

                resultado["alterados"] += 1

                continue

            # ------------------------------------------------
            # SEM ALTERAÇÃO NO REDMINE
            # ------------------------------------------------
            # O catálogo Clientes/Origem pode ter sido enriquecido depois da
            # primeira gravação. Nesse caso o updated_on do chamado não muda,
            # mas precisamos substituir o ID numérico pelo nome resolvido.
            atual_cache = obter_chamado(chamado_id) or {}
            cliente_novo = _texto(dados.get("Clientes"))
            cliente_cache = _texto(atual_cache.get("cliente"))
            origem_nova = _texto(dados.get("Origem"))
            origem_cache = _texto(atual_cache.get("origem"))
            enriquecimento_mudou = (
                (cliente_novo and cliente_novo != cliente_cache)
                or (origem_nova and origem_nova != origem_cache)
            )
            if enriquecimento_mudou:
                salvar_chamado(chamado_id, dados)
                resultado["alterados"] += 1
                continue

            resultado[
                "sem_alteracao"
            ] += 1

        except Exception as exc:

            resultado["erros"] += 1

            print(
                f"[EDNNA] Erro sincronizando chamado "
                f"#{chamado_id}: {exc}"
            )

    # ------------------------------------------------------------
    # RECONCILIAÇÃO DE AUSENTES
    # ------------------------------------------------------------
    # A listagem principal do painel usa status_id=open. Quando um chamado é
    # concluído ele deixa de vir nessa lista; sem esta etapa o SQLite manteria
    # eternamente a última fotografia "Aberto". Ausência nunca é tratada como
    # conclusão automaticamente: confirmamos o chamado individualmente no Redmine.
    if reconciliar_ausentes:
        try:
            ids_atuais = {
                _inteiro_seguro(v) for v in frame["#"].tolist()
            }
            ids_atuais.discard(None)

            from ednna.armazenamento import listar_chamados
            armazenados = listar_chamados() or []
            candidatos = []
            for item in armazenados:
                cid = _inteiro_seguro(item.get("id"))
                estado = _texto(item.get("estado")).lower()
                ja_encerrado = any(x in estado for x in (
                    "conclu", "fechad", "encerrad", "resolvid", "cancelad"
                ))
                if cid and cid not in ids_atuais and not ja_encerrado:
                    candidatos.append(cid)

            resultado["ausentes_detectados"] = len(candidatos)

            # Lote conservador para não pressionar o Redmine. Em ciclos seguintes
            # os resíduos históricos restantes são saneados automaticamente.
            limite = 25
            for cid in candidatos[:limite]:
                try:
                    from redmine_api import buscar_detalhes_chamado, issue_para_linha
                    issue = buscar_detalhes_chamado(
                        cid, consulta_pontual=True, timeout=(4, 12), tentativas=1
                    )
                    if not issue:
                        resultado["ausentes_indisponiveis"] += 1
                        continue
                    linha = issue_para_linha(issue)
                    salvar_chamado(cid, linha)
                    resultado["ausentes_verificados"] += 1
                    estado_novo = _texto(linha.get("Estado")).lower()
                    if any(x in estado_novo for x in (
                        "conclu", "fechad", "encerrad", "resolvid", "cancelad"
                    )):
                        resultado["encerrados_reconciliados"] += 1
                except Exception as exc:
                    resultado["ausentes_indisponiveis"] += 1
                    print(
                        f"[EDNNA] Reconciliação status | indisponível | chamado={cid} | {type(exc).__name__}: {exc}",
                        flush=True,
                    )

            if candidatos:
                print(
                    "[EDNNA] Reconciliação status | "
                    f"ausentes={len(candidatos)} | "
                    f"verificados={resultado['ausentes_verificados']} | "
                    f"encerrados={resultado['encerrados_reconciliados']} | "
                    f"indisponiveis={resultado['ausentes_indisponiveis']}",
                    flush=True,
                )
        except Exception as exc:
            print(f"[EDNNA] Reconciliação status | erro geral: {exc}", flush=True)

    salvar_metadado(
        "ultima_sincronizacao_snapshot",
        agora_brasil_iso(),
    )

    return resultado
