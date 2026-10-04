from ednna.security import require_edi
import streamlit as st
from ui.operational_shell import setup,footer
from ui.operational_data import regras_df
from ednna.homologacao import estado_regra

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

    st.caption('Esta visão mostra o patrimônio operacional efetivamente autorizado. Regras de abertura homologadas aparecem aqui como prática do EDDY, sem misturar aprendizado com autorização.')
    st.subheader('🏢 Aberturas de relacionamento em prática')
    if not aberturas:
        st.warning('Ainda não há regra de abertura homologada em estado ATIVA ou EM OBSERVAÇÃO. O EDDY pode estudar aberturas, mas não deve executá-las antes da homologação do professor.')
    for x,hom in aberturas:
        estado=(hom or {}).get('estado') or 'HOMOLOGADA_LEGADO'
        modo='Ativo assistido' if estado=='EM_OBSERVACAO' else 'Ativa'
        st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br><span class="pill">{modo}</span> · Abertura de relacionamento<br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)

    st.subheader('⚙️ Demais regras em operação')
    demais=[(x,h) for x,h in itens if (x,h) not in aberturas]
    if not demais: st.info('Nenhuma outra regra operacional autorizada neste momento.')
    for x,hom in demais:
        estado=(hom or {}).get('estado') or 'HOMOLOGADA_LEGADO'
        st.markdown(f'<div class="rule"><b>{x.get("player") or x.get("regra_id")}</b><br>{x.get("operacao") or "Operação EDI"} · <span class="pill">{estado.replace("_"," ").title()}</span><br><small>{x.get("regra_id")}</small></div>',unsafe_allow_html=True)
footer()
