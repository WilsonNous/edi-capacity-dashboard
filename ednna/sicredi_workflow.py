from __future__ import annotations
import re

def interpretar_retorno_sicredi(corpo: str) -> dict:
    """Classifica conservadoramente eventos conhecidos dos históricos SICREDI.
    Não envia e-mail e não conclui chamado; fornece estado/próxima ação ao monitor.
    """
    t=re.sub(r"\s+"," ",str(corpo or '').casefold())
    if any(x in t for x in ('férias','ferias','estarei ausente','fora do escritório','fora do escritorio')):
        emails=re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",corpo or '',flags=re.I)
        return {'evento':'AUSENCIA_CONTATO','estado':'AGUARDANDO_BANCO','acao':'USAR_CONTATO_SUBSTITUTO_SE_DETERMINISTICO','emails_substitutos':emails}
    if any(x in t for x in ('termo','assinatura','assinar','assinad')):
        return {'evento':'PENDENCIA_ASSINATURA','estado':'AGUARDANDO_CLIENTE','acao':'ACOMPANHAR_ASSINATURA'}
    if 'nexxera' in t and 'supply' not in t:
        return {'evento':'DIVERGENCIA_VAN','estado':'DIVERGENCIA_VAN','acao':'VALIDAR_VAN_COM_BANCO','requer_humano':True}
    if any(x in t for x in ('supply','van')) and any(x in t for x in ('encaminh','portal','caixa postal','caixas postais')):
        return {'evento':'ENCAMINHADO_VAN','estado':'AGUARDANDO_VAN','acao':'ACOMPANHAR_VAN'}
    if any(x in t for x in ('virada de chave','transmissão','transmissao')) and any(x in t for x in ('habilitad','ativad','teste','produção','producao')):
        return {'evento':'TRANSMISSAO','estado':'AGUARDANDO_ARQUIVOS','acao':'VALIDAR_ARQUIVOS_POR_DOMICILIO'}
    if '?' in t or any(x in t for x in ('seria transmissão de cobrança','seria transmissao de cobranca','qual layout','versão','versao')):
        return {'evento':'PEDIDO_ESCLARECIMENTO','estado':'AGUARDANDO_BANCO','acao':'RESPONDER_SE_CONHECIMENTO_HOMOLOGADO'}
    return {'evento':'RETORNO_NAO_CLASSIFICADO','estado':'AGUARDANDO_BANCO','acao':'REVISAR_RETORNO'}
