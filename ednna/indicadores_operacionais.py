"""Indicadores operacionais comprovaveis, separados de diagnosticos e estimativas."""
from __future__ import annotations


def calcular_indicadores(registros: list[dict]) -> dict:
    """Contagens de registros transacionais; nao inferir horas ou trabalho evitado."""
    confirmados = [x for x in registros if int(x.get("envio_confirmado") or 0) == 1]
    return {
        "registros_transacionais": len(registros),
        "envios_iniciais_confirmados": len(confirmados),
        "respostas_registradas": sum(bool(x.get("resposta_recebida_em")) for x in registros),
        "followups_registrados": sum(max(0, int(x.get("followup_count") or 0)) for x in registros),
        "redmine_pendente": sum(bool(x.get("redmine_pendente_nota") or x.get("redmine_erro")) and not x.get("redmine_atualizado_em") for x in registros),
        "intervencoes_humanas_evitadas": None,
        "tempo_economizado_minutos": None,
        "observacao": "Contagens transacionais; nao incluem reconstrucao de journals como atuacao nem estimam economia sem baseline.",
    }


def consultar_indicadores() -> dict:
    from ednna.acompanhamento_acoes import inicializar_acompanhamento, _conectar
    inicializar_acompanhamento()
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT envio_confirmado, resposta_recebida_em, followup_count, redmine_pendente_nota, redmine_erro, redmine_atualizado_em FROM acoes_operacionais"
        ).fetchall()
    return calcular_indicadores([dict(x) for x in rows])
