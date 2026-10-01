from __future__ import annotations

"""EDNNA v3.34.10 — mineração histórica com estudo progressivo.

Governança:
- EVIDENCIA_HISTORICA: fato observado em chamados/journals/anexos;
- POLITICA_HOMOLOGADA: decisão operacional Netunna;
- INFERENCIA_EDNNA: padrão sugerido pela EDNNA, sujeito a revisão.

Amostragem:
- até 6 casos formam o caderno inicial;
- casos adicionais ficam separados para prova surpresa;
- nenhum resultado homologa ou autoriza execução automaticamente.
"""
import json, re
from collections import Counter, defaultdict
from typing import Iterable
from ednna.armazenamento import conectar, agora_brasil_iso

ABERTURA_RE=re.compile(r"(?i)abertura\s+(?:de\s+)?relacionamento|abrir\s+relacionamento|credenciamento")
EMAIL_RE=re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
CNPJ_RE=re.compile(r"(?<!\d)\d{2}[.\s]?\d{3}[.\s]?\d{3}[\s/.-]?\d{4}[-.\s]?\d{2}(?!\d)")
EC_RE=re.compile(r"(?i)(?:\bEC\b|estabelecimento|conv[eê]nio)\s*[:#-]?\s*([0-9]{5,20})")
CONTA_RE=re.compile(r"(?i)\bconta(?:\s+corrente)?\s*[:#-]?\s*([0-9][0-9.\- ]{2,20})")
AGENCIA_RE=re.compile(r"(?i)\bag[eê]ncia\s*[:#-]?\s*([0-9.\-]{2,12})")
EVIDENCIA_HISTORICA='EVIDENCIA_HISTORICA'; POLITICA_HOMOLOGADA='POLITICA_HOMOLOGADA'; INFERENCIA_EDNNA='INFERENCIA_EDNNA'
CAPACIDADES={
'IDENTIFICAR_CONTEXTO':('EDNNA','Identificar cliente, player e tipo de abertura'),'CONSULTAR_BLUEPRINT':('EDNNA','Resolver Blueprint, participantes e contatos'),'EXTRAIR_DADOS':('EDNNA','Extrair CNPJ, EC, agência e contas'),'PREPARAR_SOLICITACAO':('EDNNA','Preparar solicitação conforme regra homologada'),'ENVIAR_EMAIL':('EDNNA','Enviar pelo Microsoft Graph após pre-flight'),'REGISTRAR_REDMINE':('EDNNA','Registrar journal/evidências e estado'),'MONITORAR_RESPOSTA':('EDNNA','Monitorar resposta do terceiro'),'FOLLOWUP_48H':('EDNNA','Executar primeiro follow-up em 48 horas'),'INTERPRETAR_RETORNO':('EDNNA','Interpretar retornos conhecidos'),'EXECUTAR_API_PORTAL':('CHECKPOINT_HUMANO','Executar API/portal ainda não integrado'),'ASSINATURA_DOCUMENTO':('CHECKPOINT_HUMANO','Obter assinatura/documento externo'),'ATUALIZAR_PLANILHA':('CHECKPOINT_HUMANO','Atualizar planilha externa não integrada'),'VALIDAR_ARQUIVOS':('CHECKPOINT_HUMANO','Confirmar recepção física dos arquivos'),'DECISAO_AMBIGUA':('CHECKPOINT_HUMANO','Resolver ambiguidade real de dados/procedimento')}
POLITICAS_HOMOLOGADAS={'FOLLOWUP_48H':{'responsavel':'EDNNA','descricao':CAPACIDADES['FOLLOWUP_48H'][1],'origem':POLITICA_HOMOLOGADA,'confianca':'HOMOLOGADA','parametros':{'primeiro_followup_horas':48},'evidencia':'Padrão operacional Netunna/EDNNA: primeiro follow-up em 48 horas.'}}
PLAYER_ALIASES={'ITAU':['ITAÚ','ITAU'],'SICREDI':['SICREDI'],'SAFRAPAY':['SAFRAPAY','SAFRA PAY'],'CIELO':['CIELO'],'REDECARD':['REDECARD','USEREDE'],'SANTANDER':['SANTANDER'],'BRADESCO':['BRADESCO'],'BANRISUL':['BANRISUL'],'ALELO':['ALELO'],'PLUXEE':['PLUXEE','SODEXO'],'GREENCARD':['GREENCARD','GREEN CARD'],'TICKET':['TICKET'],'SENFF':['SENFF'],'VALECARD':['VALECARD'],'WIZEO':['WIZEO'],'TRUCKPAG':['TRUCKPAG'],'FITCARD':['FITCARD'],'EXPERS':['EXPERS'],'SHELLBOX':['SHELLBOX','SHELL BOX'],'PICPAY':['PICPAY'],'PROFROTAS':['PROFROTAS']}
REDE_EXPLICITA_RE=re.compile(r"(?i)(?:^|[\[\]():;,_/\-\s])REDE(?:$|[\[\]():;,_/\-\s])")

def _init():
    with conectar() as conn:
        conn.executescript('''CREATE TABLE IF NOT EXISTS mineracao_aberturas (chamado_id INTEGER PRIMARY KEY, player TEXT NOT NULL, status TEXT, assunto TEXT, score INTEGER NOT NULL DEFAULT 0, payload_json TEXT NOT NULL, minerado_em TEXT NOT NULL); CREATE TABLE IF NOT EXISTS propostas_regras_abertura (regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'CANDIDATA', evidencias INTEGER NOT NULL DEFAULT 0, compatibilidade INTEGER NOT NULL DEFAULT 0, payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL);''')
def _texto(i): return '\n'.join([str(i.get('subject') or ''),str(i.get('description') or '')]+[str(j.get('notes')) for j in i.get('journals',[]) or [] if j.get('notes')])
def _player_em_texto(t,aceitar_rede=False):
    up=str(t or '').upper()
    for p,aa in PLAYER_ALIASES.items():
        if any(a.upper() in up for a in aa): return p
    return 'REDECARD' if aceitar_rede and REDE_EXPLICITA_RE.search(str(t or '')) else 'NAO_IDENTIFICADO'
def identificar_player(i):
    vals=[]
    for cf in i.get('custom_fields',[]) or []:
        n=str(cf.get('name') or '').upper(); v=cf.get('value')
        if 'ORIGEM' in n or 'ADQUIREN' in n or 'BANCO' in n:
            vals.extend(str(x) for x in v if x not in (None,'')) if isinstance(v,(list,tuple,set)) else vals.append(str(v or ''))
    for v in vals:
        p=_player_em_texto(v,True)
        if p!='NAO_IDENTIFICADO': return p
    p=_player_em_texto(i.get('subject'),True)
    if p!='NAO_IDENTIFICADO': return p
    return _player_em_texto('\n'.join([str(i.get('description') or '')]+[str(j.get('notes')) for j in i.get('journals',[]) or [] if j.get('notes')]),False)
def eh_abertura(i): return bool(ABERTURA_RE.search(_texto(i)))
def _status_nome(i):
    s=i.get('status') or {}; return str(s.get('name') if isinstance(s,dict) else s or '')
def _terminal_positivo(i): return any(x in _status_nome(i).upper() for x in ('CONCLU','FECHAD'))
def _score(i):
    t=_texto(i); js=len(i.get('journals',[]) or []); an=len(i.get('attachments',[]) or []); emails=sorted(set(e.lower() for e in EMAIL_RE.findall(t))); cnpjs=sorted(set(CNPJ_RE.findall(t))); ecs=sorted(set(EC_RE.findall(t))); contas=sorted(set(x.strip() for x in CONTA_RE.findall(t))); agencias=sorted(set(AGENCIA_RE.findall(t))); terminal=_terminal_positivo(i); score=(30 if terminal else 0)+min(js,10)*3+min(an,5)*3+(10 if emails else 0)+(8 if cnpjs else 0)+(6 if ecs or contas else 0)+(5 if 'BLUEPRINT' in t.upper() or 'BP ' in t.upper() else 0); return min(100,score),{'terminal_positivo':terminal,'journals':js,'anexos':an,'emails':emails,'cnpjs':cnpjs,'ecs':ecs,'contas':contas,'agencias':agencias}
def _etapas_evidenciadas(i):
    t=_texto(i); up=t.upper(); out=[]
    def add(c,e):
        r,d=CAPACIDADES[c]; out.append({'codigo':c,'responsavel':r,'descricao':d,'evidencia':e,'origem':EVIDENCIA_HISTORICA})
    add('IDENTIFICAR_CONTEXTO','Chamado classificado como Abertura de Relacionamento')
    if 'BLUEPRINT' in up or 'BP ' in up:add('CONSULTAR_BLUEPRINT','Blueprint/BP referenciado no histórico')
    if CNPJ_RE.search(t) or EC_RE.search(t) or CONTA_RE.search(t):add('EXTRAIR_DADOS','Dados operacionais presentes no histórico')
    if re.search(r'(?i)assunto\s*:|para\s*:|solicitamos|gostar[ií]amos de habilitar|abertura',t):add('PREPARAR_SOLICITACAO','Solicitação/e-mail encontrado')
    if EMAIL_RE.search(t):add('ENVIAR_EMAIL','Destinatários/remetentes encontrados')
    add('REGISTRAR_REDMINE','Histórico está registrado no Redmine')
    if re.search(r'(?i)retorno|respond|protocolo|aguardando',t):add('MONITORAR_RESPOSTA','Há sinais de acompanhamento/retorno')
    if re.search(r'(?i)retorno|confirmad|habilitad|conclu[ií]d|liberad',t):add('INTERPRETAR_RETORNO','Há retorno operacional no histórico')
    if re.search(r'(?i)\bapi\b|opt[- ]?in|portal',t):add('EXECUTAR_API_PORTAL','Histórico menciona API/opt-in/portal')
    if re.search(r'(?i)assin|termo|formul[aá]rio',t):add('ASSINATURA_DOCUMENTO','Histórico menciona termo/formulário/assinatura')
    if re.search(r'(?i)planilha|sharepoint',t):add('ATUALIZAR_PLANILHA','Histórico menciona planilha')
    if re.search(r'(?i)arquivo.{0,50}(recebid|cheg|movimento)|recep[cç][aã]o.{0,30}arquivo',t):add('VALIDAR_ARQUIVOS','Histórico menciona validação/recepção de arquivos')
    seen=set(); return [x for x in out if not (x['codigo'] in seen or seen.add(x['codigo']))]
def minerar_issue(i):
    score,s=_score(i); return {'chamado_id':int(i.get('id') or 0),'player':identificar_player(i),'status':_status_nome(i),'assunto':str(i.get('subject') or ''),'score':score,'sinais':s,'etapas':_etapas_evidenciadas(i),'minerar_em':agora_brasil_iso()}
def salvar_mineracao(r):
    _init()
    with conectar() as c:c.execute('''INSERT INTO mineracao_aberturas(chamado_id,player,status,assunto,score,payload_json,minerado_em) VALUES(?,?,?,?,?,?,?) ON CONFLICT(chamado_id) DO UPDATE SET player=excluded.player,status=excluded.status,assunto=excluded.assunto,score=excluded.score,payload_json=excluded.payload_json,minerado_em=excluded.minerado_em''',(r['chamado_id'],r['player'],r['status'],r['assunto'],r['score'],json.dumps(r,ensure_ascii=False),agora_brasil_iso()))
def _politicas_da_proposta():return [{'codigo':c,**d} for c,d in POLITICAS_HOMOLOGADAS.items()]
def gerar_propostas(resultados:Iterable[dict],minimo_evidencias=2):
    _init(); grupos=defaultdict(list)
    for r in resultados:
        if r.get('player') and r.get('player')!='NAO_IDENTIFICADO':grupos[r['player']].append(r)
    props=[]
    for player,casos in sorted(grupos.items()):
        bons=[c for c in casos if c.get('score',0)>=55 and c.get('sinais',{}).get('terminal_positivo')]; base=bons or sorted(casos,key=lambda x:x.get('score',0),reverse=True)[:3]; freq=Counter(e['codigo'] for c in base for e in c.get('etapas',[]) if e.get('origem')==EVIDENCIA_HISTORICA); etapas=[]
        for cod,n in freq.most_common():
            resp,desc=CAPACIDADES[cod]; rec=round(100*n/max(1,len(base))); etapas.append({'codigo':cod,'responsavel':resp,'descricao':desc,'ocorrencias':n,'recorrencia_pct':rec,'origem':INFERENCIA_EDNNA,'base_origem':EVIDENCIA_HISTORICA,'confianca':'ALTA' if n>=minimo_evidencias and rec>=60 else 'A_VALIDAR'})
        pol=_politicas_da_proposta(); aut=sum(1 for e in etapas if e['responsavel']=='EDNNA' and e['confianca']=='ALTA')+sum(1 for e in pol if e['responsavel']=='EDNNA'); chk=sum(1 for e in etapas if e['responsavel']=='CHECKPOINT_HUMANO' and e['confianca']=='ALTA'); compat=round(sum(c.get('score',0) for c in base)/max(1,len(base))); p={'regra_id':f'ABERTURA-{player}-001','player':player,'estado':'CANDIDATA','evidencias':len(base),'casos_ids':[c['chamado_id'] for c in base],'compatibilidade':compat,'etapas':etapas,'politicas_homologadas':pol,'automatizaveis_agora':aut,'checkpoints_humanos':chk,'pronta_para_revisao':len(base)>=minimo_evidencias and any(e['confianca']=='ALTA' for e in etapas),'governanca':{'historico':EVIDENCIA_HISTORICA,'inferencias':INFERENCIA_EDNNA,'politicas':POLITICA_HOMOLOGADA},'nota':'Candidata inferida do histórico; não autorizada para execução.'}; props.append(p)
        with conectar() as c:c.execute('''INSERT INTO propostas_regras_abertura(regra_id,player,estado,evidencias,compatibilidade,payload_json,atualizado_em) VALUES(?,?,?,?,?,?,?) ON CONFLICT(regra_id) DO UPDATE SET player=excluded.player,estado=excluded.estado,evidencias=excluded.evidencias,compatibilidade=excluded.compatibilidade,payload_json=excluded.payload_json,atualizado_em=excluded.atualizado_em''',(p['regra_id'],player,'CANDIDATA',len(base),compat,json.dumps(p,ensure_ascii=False),agora_brasil_iso()))
    return props
def listar_propostas():
    _init()
    with conectar() as c:rows=c.execute('SELECT payload_json FROM propostas_regras_abertura ORDER BY player').fetchall()
    return [json.loads(r[0]) for r in rows]
def _ordem_shortlist(i):return (1 if _terminal_positivo(i) else 0,int(i.get('id') or 0))
def descobrir_no_redmine(*,limite_detalhes_por_player=6,limite_prova_surpresa_por_player=12):
    from redmine_api import REDMINE_PROJECT_IDS,buscar_chamados_projeto,buscar_detalhes_chamado
    rasos=[]
    for pid in REDMINE_PROJECT_IDS:rasos.extend(buscar_chamados_projeto(pid,status_id='*',max_workers_paginas=2))
    candidatos=[x for x in rasos if eh_abertura(x)]; por=defaultdict(list)
    for c in candidatos:por[identificar_player(c)].append(c)
    detalhados=[]; erros=[]; reservas={}
    for player,itens in por.items():
        if player=='NAO_IDENTIFICADO':continue
        ordenados=sorted(itens,key=_ordem_shortlist,reverse=True); estudo=ordenados[:max(1,limite_detalhes_por_player)]; surpresa=ordenados[max(1,limite_detalhes_por_player):max(1,limite_detalhes_por_player)+max(0,limite_prova_surpresa_por_player)]; reservas[player]={'universo':len(ordenados),'estudo_ids':[int(x['id']) for x in estudo],'prova_surpresa_ids':[int(x['id']) for x in surpresa]}
        for item in estudo+surpresa:
            try:
                d=buscar_detalhes_chamado(int(item['id']),incluir_journals=True,incluir_relacoes=True,incluir_anexos=True,consulta_pontual=False,tentativas=1)
                if d:
                    r=minerar_issue(d); salvar_mineracao(r); detalhados.append(r)
            except Exception as exc:erros.append({'chamado_id':item.get('id'),'erro':f'{type(exc).__name__}: {exc}'})
    # propostas aprendem somente com o caderno inicial, nunca com a prova surpresa
    ids_estudo={i for v in reservas.values() for i in v['estudo_ids']}; propostas=gerar_propostas([r for r in detalhados if r['chamado_id'] in ids_estudo])
    for p in propostas:
        p['universo_encontrado']=reservas.get(p['player'],{}).get('universo',p['evidencias']); p['prova_surpresa_ids']=reservas.get(p['player'],{}).get('prova_surpresa_ids',[])
        with conectar() as c:c.execute('UPDATE propostas_regras_abertura SET payload_json=?,atualizado_em=? WHERE regra_id=?',(json.dumps(p,ensure_ascii=False),agora_brasil_iso(),p['regra_id']))
    return {'candidatos_rasos':len(candidatos),'detalhados':len(detalhados),'players':len([p for p in por if p!='NAO_IDENTIFICADO']),'propostas':propostas,'erros':erros,'executado_em':agora_brasil_iso()}
def _simular_ids(proposta,ids):
    ids=set(int(x) for x in ids); _init(); casos=[]
    with conectar() as c:rows=c.execute('SELECT payload_json FROM mineracao_aberturas WHERE player=?',(proposta.get('player'),)).fetchall()
    for r in rows:
        x=json.loads(r[0]);
        if int(x.get('chamado_id',0)) in ids:casos.append(x)
    esperadas={e['codigo'] for e in proposta.get('etapas',[]) if e.get('confianca')=='ALTA' and e.get('origem')==INFERENCIA_EDNNA}; detalhes=[]
    for c in casos:
        presentes={e['codigo'] for e in c.get('etapas',[]) if e.get('origem')==EVIDENCIA_HISTORICA}; cob=round(100*len(esperadas&presentes)/max(1,len(esperadas))); detalhes.append({'chamado_id':c['chamado_id'],'cobertura_pct':cob,'faltantes':sorted(esperadas-presentes)})
    comp=sum(1 for d in detalhes if d['cobertura_pct']>=80); return {'casos':len(detalhes),'compativeis':comp,'compatibilidade_pct':round(100*comp/max(1,len(detalhes))) if detalhes else 0,'politicas_excluidas_do_backtest':sorted(POLITICAS_HOMOLOGADAS.keys()),'detalhes':detalhes}
def simular_proposta(proposta):return _simular_ids(proposta,proposta.get('casos_ids',[]))
def simular_prova_surpresa(proposta):
    ids=proposta.get('prova_surpresa_ids',[]); r=_simular_ids(proposta,ids); r['tipo']='PROVA_SURPRESA'; r['ineditos']=True; return r
