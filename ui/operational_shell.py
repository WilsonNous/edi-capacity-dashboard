from pathlib import Path
import streamlit as st
from version import APP_VERSION, APP_RELEASE

def setup(title):
    st.set_page_config(page_title=f'{title} — EDNNA',page_icon='🤖',layout='wide',initial_sidebar_state='collapsed')
    st.markdown('''<style>[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}.block-container{max-width:1280px;padding:1.4rem 2rem}.stApp{background:#f5f7fb;color:#172b4d}div.stButton>button{border-radius:14px;min-height:46px;font-weight:750}.op-card{background:white;border:1px solid #dfe6ef;border-radius:18px;padding:18px;box-shadow:0 4px 14px rgba(20,50,90,.05)}.op-k{font-size:.75rem;color:#718096;font-weight:800;text-transform:uppercase}.op-n{font-size:1.8rem;font-weight:900}.op-note{color:#718096;font-size:.82rem}.op-title{font-size:1.75rem;font-weight:900;margin:.2rem 0}.op-sub{color:#65758b;margin-bottom:1rem}.rule{background:#fff;border:1px solid #dfe6ef;border-radius:16px;padding:16px;margin:8px 0}.pill{display:inline-block;border-radius:999px;background:#eaf2ff;color:#1769d2;padding:4px 9px;font-size:.72rem;font-weight:800}.foot{color:#8996a8;font-size:.72rem;text-align:center;margin-top:24px}</style>''',unsafe_allow_html=True)
    a,b=st.columns([1,6])
    with a:
        if st.button('← EDNNA',use_container_width=True): st.switch_page('app.py')
    with b: st.markdown(f'<div class="op-title">{title}</div>',unsafe_allow_html=True)

def footer(): st.markdown(f'<div class="foot">EDNNA v{APP_VERSION} · {APP_RELEASE}</div>',unsafe_allow_html=True)
