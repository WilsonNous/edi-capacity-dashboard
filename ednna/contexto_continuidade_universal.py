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

 

def reconciliar_graph(chamado_id, *, caixa_postal, houve_atuacao=False,
                      buscar_enviados=None, buscar_resposta=None):
    """Reconciliação somente leitura. Falha Graph não autoriza envio."""
    if buscar_enviados is None or buscar_resposta is None:
        from ednna.email_sender import listar_emails_enviados_por_chamado, localizar_resposta_por_chamado
        buscar_enviados = buscar_enviados or listar_emails_enviados_por_chamado
        buscar_resposta = buscar_resposta or localizar_resposta_por_chamado
    try:
        enviados = buscar_enviados(remetente=caixa_postal, chamado_id=int(chamado_id), top=500)
        resposta = buscar_resposta(caixa_postal=caixa_postal, chamado_id=int(chamado_id))
    except Exception as exc:
        return {'chamado_id': int(chamado_id), 'estado': 'GRAPH_INDISPONIVEL',
                'erro': type(exc).__name__, 'primeiro_envio_automatico_permitido': False,
                'reconciliacao_graph_necessaria': True}
    enviados = enviados or []
    resposta = resposta or {}
    # A resposta pode chegar na Inbox sem correspondência na janela recente de Sent Items.
    resultado = avaliar_contexto(
        chamado_id, houve_atuacao=houve_atuacao or bool(enviados),
        envio_confirmado=bool(enviados),
        retorno={'classificacao': 'RESPOSTA_ENCONTRADA_GRAPH'} if resposta else {},
    )
    resultado['graph_consultado'] = True
    resultado['enviados_encontrados'] = len(enviados)
    resultado['resposta_encontrada'] = bool(resposta)
    resultado['ultimo_envio_em'] = str(enviados[-1].get('sentDateTime') or '') if enviados else ''
    resultado['resposta_recebida_em'] = str(resposta.get('receivedDateTime') or '')
    resultado['conversation_id'] = str(resposta.get('conversationId') or (enviados[-1].get('conversationId') if enviados else '') or '')
    resultado['resposta_message_id'] = str(resposta.get('id') or '')
    resultado['janela_limitada'] = True
    return resultado
