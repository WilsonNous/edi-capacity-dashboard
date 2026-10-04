from ednna.security import require_edi
import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import regras_df
from ednna.homologacao import estado_regra
from ednna.aberturas_ativas import plano_assistido

setup('⚡ Automações do EDDY')
require_edi()
r=regras_df()
if r.empty:
    st.info('Nenhuma regra operacional disponível.')
else:
    itens=[]
    for _,x in r.iterrows():
        rid=str(x.get('regra_id') or '').strip()
        hom=estado_regra(rid) if rid else None
        legado_homologado=(str(x.get('estado_revisao') or '')=='HOMOLOGADA' or str(x.get('estado') or '')=='HOMOLOGADA')
        if hom and hom.get('estado') in ('ATIVA','EM_OBSERVACAO'):
            itens.append((x,hom))
        elif legado_homologado:
            itens.append((x,None))

    aberturas=[(x,h) for x,h in itens if str(x.get('regra_id') or '').upper().startswith('ABERTURA-') or 'ABERTURA' in str(x.get('operacao') or '').upper()]
    c1,c2,c3=st.columns(3)
    c1.metric('Regras em operação',len(itens))
    c2.metric('Aberturas ativas',len(aberturas))
    c3.metric('Em observação',sum(1 for _,h in itens if h and h.get('estado')=='EM_OBSERVACAO'))

    st.caption('Patrimônio operacional autorizado. Aprender não é executar: somente regras homologadas entram em prática.')
    st.subheader('🏢 Aberturas de relacionamento em prática')
    if not aberturas:
        st.warning('Ainda não há regra de abertura homologada em ATIVA ou EM OBSERVAÇÃO. O EDDY pode estudar, mas não executará antes da decisão do professor.')
    for x,hom in aberturas:
        estado=(hom or {}).get('estado') or 'HOMOLOGADA_LEGADO'
        regra=x.to_dict() if hasattr(x,'to_dict') else dict(x)
        plano=plano_assistido(regra) if hom else None
        modo='Ativo assistido' if estado=='EM_OBSERVACAO' else 'Ativa'
        st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br><span class="pill">{modo}</span> · Abertura de relacionamento<br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)
        if plano:
            etapas=plano.get('etapas') or []
            eddy=sum(1 for e in etapas if e.get('destino_operacional')=='CONTINUIDADE_EDNNA')
            humano=sum(1 for e in etapas if e.get('destino_operacional')=='PRECISO_DE_VOCE')
            a,b,c=st.columns(3); a.metric('Modo',plano.get('modo','—')); b.metric('Etapas EDDY',eddy); c.metric('Checkpoints humanos',humano)
            if estado=='EM_OBSERVACAO': st.info('👀 Regra homologada excepcionalmente ou mantida sob observação. O EDDY pratica dentro do procedimento e devolve evidências à Escola Contínua.')

    st.subheader('⚙️ Demais regras em operação')
    demais=[(x,h) for x,h in itens if (x,h) not in aberturas]
    if not demais: st.info('Nenhuma outra regra operacional autorizada neste momento.')
    for x,hom in demais:
        estado=(hom or {}).get('estado') or 'HOMOLOGADA_LEGADO'
        st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br>{x.get("operacao") or "Operação EDI"} · <span class="pill">{estado.replace("_"," ").title()}</span><br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)
footer()
