"""Consolidacao conservadora de contexto de acompanhamento EDI."""


def avaliar_contexto(chamado_id, *, houve_atuacao=False, envio_confirmado=False, retorno=None):
    retorno = retorno or {}
    tipo = str(retorno.get('classificacao') or '').upper()
    if tipo == 'REDIRECIONAMENTO_CANAL':
        estado = 'REDIRECIONAMENTO_PENDENTE'
    elif tipo:
        estado = 'RESPOSTA_A_INTERPRETAR'
    elif envio_confirmado:
        estado = 'ACOMPANHAMENTO_TRANSACIONAL'
    elif houve_atuacao:
        estado = 'ATUACAO_PREVIA_RECONCILIAR_GRAPH'
    else:
        estado = 'HISTORICO_INSUFICIENTE'
    return {'chamado_id': int(chamado_id), 'estado': estado,
            'reconciliacao_graph_necessaria': estado in ('ATUACAO_PREVIA_RECONCILIAR_GRAPH', 'HISTORICO_INSUFICIENTE'),
            'primeiro_envio_automatico_permitido': False}
