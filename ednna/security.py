"""Autenticação/autorização do EDDY sobre Azure App Service Easy Auth.

O package mantém o nome histórico `ednna` por compatibilidade técnica.
"""
from __future__ import annotations
import base64,json,os,sqlite3
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; AUDIT_DB=DATA/'ednna_security.db'
ROLE_ADMIN='ADMIN'; ROLE_EDI='EDI'; ROLE_VIEWER='VIEWER'; ROLE_BLOCKED='BLOCKED'
def _csv_env(name):
    raw=os.getenv(name,''); return {x.strip().lower() for x in raw.replace(';',',').split(',') if x.strip()}
def _headers():
    try:return {str(k).lower():str(v) for k,v in st.context.headers.items()}
    except Exception:return {}
def _decode_principal(raw):
    if not raw:return {}
    try:return json.loads(base64.b64decode(raw+'='*(-len(raw)%4)).decode('utf-8'))
    except Exception:return {}
def _claim(p,*types):
    wanted={x.lower() for x in types}
    for item in p.get('claims',[]) or []:
        if str(item.get('typ') or '').lower() in wanted:return str(item.get('val') or '').strip()
    return ''
def _groups(p):
    vals=set()
    for item in p.get('claims',[]) or []:
        if str(item.get('typ') or '').lower() in {'groups','http://schemas.microsoft.com/ws/2008/06/identity/claims/groups'}: vals.add(str(item.get('val') or '').strip().lower())
    return {x for x in vals if x}
def _is_azure():return bool(os.getenv('WEBSITE_INSTANCE_ID') or os.getenv('WEBSITE_SITE_NAME'))
@dataclass(frozen=True)
class UserContext:
    authenticated:bool; email:str; name:str; role:str; groups:frozenset[str]; source:str='easy_auth'
    @property
    def is_admin(self):return self.role==ROLE_ADMIN
    @property
    def is_edi(self):return self.role in {ROLE_ADMIN,ROLE_EDI}
    @property
    def is_viewer(self):return self.role==ROLE_VIEWER
def current_user():
    h=_headers(); p=_decode_principal(h.get('x-ms-client-principal',''))
    email=(h.get('x-ms-client-principal-name') or _claim(p,'preferred_username','email','emails','http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress','http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn')).strip().lower()
    name=(_claim(p,'name','http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name') or email).strip(); groups=_groups(p)
    if not email and not _is_azure() and os.getenv('EDNNA_DEV_BYPASS_AUTH','').lower() in {'1','true','yes','sim'}:
        email=os.getenv('EDNNA_DEV_USER','dev@localhost').strip().lower(); name=os.getenv('EDNNA_DEV_NAME','Desenvolvimento local').strip(); role=os.getenv('EDNNA_DEV_ROLE',ROLE_ADMIN).strip().upper()
        if role not in {ROLE_ADMIN,ROLE_EDI,ROLE_VIEWER}:role=ROLE_ADMIN
        return UserContext(True,email,name,role,frozenset(),'dev_bypass')
    if not email:return UserContext(False,'','',ROLE_BLOCKED,frozenset(groups))
    domains=_csv_env('EDNNA_ALLOWED_EMAIL_DOMAINS') or {'netunna.com.br'}; domain=email.rsplit('@',1)[-1] if '@' in email else ''
    if domain not in domains:return UserContext(True,email,name or email,ROLE_BLOCKED,frozenset(groups))
    admins=_csv_env('EDNNA_ADMIN_EMAILS'); edi=_csv_env('EDNNA_EDI_EMAILS'); ag=_csv_env('EDNNA_ADMIN_GROUP_IDS'); eg=_csv_env('EDNNA_EDI_GROUP_IDS')
    role=ROLE_ADMIN if email in admins or bool(groups&ag) else ROLE_EDI if email in edi or bool(groups&eg) else ROLE_VIEWER
    return UserContext(True,email,name or email,role,frozenset(groups))
def audit(event,detail='',user=None):
    try:
        DATA.mkdir(parents=True,exist_ok=True); u=user or current_user()
        with sqlite3.connect(AUDIT_DB) as con:
            con.execute('CREATE TABLE IF NOT EXISTS security_audit (id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,email TEXT,role TEXT,event TEXT NOT NULL,detail TEXT)')
            con.execute('INSERT INTO security_audit(created_at,email,role,event,detail) VALUES(?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),u.email,u.role,event,detail[:2000]))
    except Exception:pass
def require_roles(*roles):
    user=current_user(); allowed={r.upper() for r in roles}
    if not user.authenticated:audit('ACCESS_BLOCKED','Identidade Easy Auth ausente',user); st.error('Acesso não autenticado. Entre novamente com sua conta corporativa Netunna.'); st.stop()
    if user.role not in allowed:
        audit('ACCESS_DENIED',f"Perfis permitidos: {','.join(sorted(allowed))}",user); st.warning('Esta área é restrita ao seu perfil. Você pode consultar o painel geral do EDDY.')
        if st.button('← Voltar ao EDDY',key='security_back_home'):st.switch_page('app.py')
        st.stop()
    return user
def require_admin():return require_roles(ROLE_ADMIN)
def require_edi():return require_roles(ROLE_ADMIN,ROLE_EDI)
def display_name(user):
    from ednna.linguagem import primeiro_nome_por_email
    return primeiro_nome_por_email(user.email,user.name)
def role_label(role):return {ROLE_ADMIN:'Administrador EDDY',ROLE_EDI:'Equipe EDI',ROLE_VIEWER:'Visualizador'}.get(role,role)
