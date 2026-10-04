from __future__ import annotations
import hashlib, json
from ednna.armazenamento import conectar, agora_brasil_iso

ESTADOS={'ATIVA','EM_OBSERVACAO','SUSPENSA'}
NOTA_AUTONOMIA=90
NOTA_EXCECAO_HUMANA=85

def _init():
    with conectar() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS homologacoes_regras (
          id INTEGER PRIMARY KEY AUTOINCREMENT, regra_id TEXT NOT NULL, versao INTEGER NOT NULL,
          player TEXT, estado TEXT NOT NULL, homologado_por TEXT NOT NULL, homologado_em TEXT NOT NULL,
          nota INTEGER NOT NULL, snapshot_json TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
          motivo TEXT, atualizado_em TEXT NOT NULL, UNIQUE(regra_id,versao));
        CREATE INDEX IF NOT EXISTS idx_homologacoes_regra ON homologacoes_regras(regra_id,versao DESC);
        ''')

def _snapshot(regra, prova):
    payload={'regra':regra,'prova':prova,'capturado_em':agora_brasil_iso()}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return raw,hashlib.sha256(raw.encode('utf-8')).hexdigest()

def homologar_e_ativar(regra:dict, prova:dict, professor:str, justificativa_excecao:str=''):
    """Homologa conhecimento sem alterar a nota obtida pelo EDDY.

    >=90: apto à autonomia normal (ATIVA).
    85-89: professor pode excepcionalmente homologar, com justificativa, em EM_OBSERVACAO.
    <85: continua em estudo.
    Divergência crítica recente bloqueia homologação em qualquer faixa.
    """
    _init(); rid=str(regra.get('regra_id') or '').strip(); professor=str(professor or '').strip(); justificativa_excecao=str(justificativa_excecao or '').strip()
    if not rid or not professor: raise ValueError('Regra e professor são obrigatórios.')
    if prova.get('criticas_recentes'): raise ValueError('Existem divergências críticas recentes; a matéria precisa ser corrigida antes da homologação.')
    nota=int(prova.get('nota_ponderada_pct') or 0)
    if nota<NOTA_EXCECAO_HUMANA: raise ValueError(f'Nota abaixo de {NOTA_EXCECAO_HUMANA}%. O EDDY precisa reestudar esta matéria.')
    excepcional=nota<NOTA_AUTONOMIA
    if excepcional and not justificativa_excecao:
        raise ValueError(f'Entre {NOTA_EXCECAO_HUMANA}% e {NOTA_AUTONOMIA-1}% a homologação exige justificativa do professor.')
    if not excepcional and prova.get('situacao') not in ('APROVADA_PARA_PROFESSOR','APROVADA'):
        raise ValueError('A prova ainda não habilita homologação automática.')
    raw,sha=_snapshot(regra,prova); agora=agora_brasil_iso(); estado='EM_OBSERVACAO' if excepcional else 'ATIVA'
    motivo=(f'Homologação excepcional pelo professor: {justificativa_excecao}' if excepcional else 'Homologada pelo professor após prova ponderada')
    with conectar() as c:
        row=c.execute('SELECT COALESCE(MAX(versao),0) FROM homologacoes_regras WHERE regra_id=?',(rid,)).fetchone(); versao=int(row[0])+1
        c.execute("UPDATE homologacoes_regras SET estado='SUSPENSA', atualizado_em=? WHERE regra_id=? AND estado IN ('ATIVA','EM_OBSERVACAO')",(agora,rid))
        c.execute('''INSERT INTO homologacoes_regras(regra_id,versao,player,estado,homologado_por,homologado_em,nota,snapshot_json,snapshot_sha256,motivo,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(rid,versao,str(regra.get('player') or ''),estado,professor,agora,nota,raw,sha,motivo,agora))
    return {'regra_id':rid,'versao':versao,'estado':estado,'nota':nota,'homologado_por':professor,'homologado_em':agora,'snapshot_sha256':sha,'excepcional':excepcional}

def estado_regra(regra_id):
    _init()
    with conectar() as c:r=c.execute('SELECT regra_id,versao,player,estado,homologado_por,homologado_em,nota,snapshot_sha256,motivo FROM homologacoes_regras WHERE regra_id=? ORDER BY versao DESC LIMIT 1',(regra_id,)).fetchone()
    return dict(r) if r else None

def alterar_estado(regra_id,estado,professor,motivo=''):
    _init(); estado=str(estado or '').upper()
    if estado not in ESTADOS: raise ValueError('Estado operacional inválido.')
    agora=agora_brasil_iso()
    with conectar() as c:
        r=c.execute('SELECT id FROM homologacoes_regras WHERE regra_id=? ORDER BY versao DESC LIMIT 1',(regra_id,)).fetchone()
        if not r: raise ValueError('Regra ainda não homologada.')
        c.execute('UPDATE homologacoes_regras SET estado=?,motivo=?,atualizado_em=? WHERE id=?',(estado,f'{professor}: {motivo}'.strip(),agora,r[0]))
    return estado_regra(regra_id)

def regra_pode_executar(regra_id):
    r=estado_regra(regra_id); return bool(r and r.get('estado') in ('ATIVA','EM_OBSERVACAO'))
