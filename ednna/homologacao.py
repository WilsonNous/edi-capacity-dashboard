from __future__ import annotations
import hashlib, json
from ednna.armazenamento import conectar, agora_brasil_iso

ESTADOS={'ATIVA','EM_OBSERVACAO','SUSPENSA'}
NOTA_AUTONOMIA=90
NOTA_EXCECAO_HUMANA=85
NOTA_AUTO_HOMOLOGACAO=100

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
    """Homologa conhecimento preservando a nota ponderada obtida pelo EDDY.

    >=90: professor pode homologar normalmente (ATIVA).
    85-89: professor pode homologar excepcionalmente, com justificativa (EM_OBSERVACAO).
    <85: continua em estudo.
    Divergência crítica recente bloqueia homologação em qualquer faixa.

    A decisão humana não depende do campo legado ``situacao`` da prova: a fonte de
    verdade é a nota ponderada + criticidade. Isso evita bloquear uma prova que a
    própria Escola já classificou como apta.
    """
    _init(); rid=str(regra.get('regra_id') or '').strip(); professor=str(professor or '').strip(); justificativa_excecao=str(justificativa_excecao or '').strip()
    if not rid or not professor: raise ValueError('Regra e professor são obrigatórios.')
    if prova.get('criticas_recentes'): raise ValueError('Existem divergências críticas recentes; a matéria precisa ser corrigida antes da homologação.')
    nota=int(prova.get('nota_ponderada_pct') or 0)
    if nota<NOTA_EXCECAO_HUMANA: raise ValueError(f'Nota abaixo de {NOTA_EXCECAO_HUMANA}%. O EDDY precisa reestudar esta matéria.')
    excepcional=nota<NOTA_AUTONOMIA
    if excepcional and not justificativa_excecao:
        raise ValueError(f'Entre {NOTA_EXCECAO_HUMANA}% e {NOTA_AUTONOMIA-1}% a homologação exige justificativa do professor.')
    raw,sha=_snapshot(regra,prova); agora=agora_brasil_iso(); estado='EM_OBSERVACAO' if excepcional else 'ATIVA'
    motivo=(f'Homologação excepcional pelo professor: {justificativa_excecao}' if excepcional else 'Homologada pelo professor após prova ponderada')
    with conectar() as c:
        row=c.execute('SELECT COALESCE(MAX(versao),0) FROM homologacoes_regras WHERE regra_id=?',(rid,)).fetchone(); versao=int(row[0])+1
        c.execute("UPDATE homologacoes_regras SET estado='SUSPENSA', atualizado_em=? WHERE regra_id=? AND estado IN ('ATIVA','EM_OBSERVACAO')",(agora,rid))
        c.execute('''INSERT INTO homologacoes_regras(regra_id,versao,player,estado,homologado_por,homologado_em,nota,snapshot_json,snapshot_sha256,motivo,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(rid,versao,str(regra.get('player') or ''),estado,professor,agora,nota,raw,sha,motivo,agora))
    return {'regra_id':rid,'versao':versao,'estado':estado,'nota':nota,'homologado_por':professor,'homologado_em':agora,'snapshot_sha256':sha,'excepcional':excepcional}

def auto_homologar_se_perfeito(regra:dict, prova:dict):
    """Permite ao EDDY auto-homologar somente prova perfeita e sem crítica recente."""
    nota=int(prova.get('nota_ponderada_pct') or 0)
    if nota < NOTA_AUTO_HOMOLOGACAO or prova.get('criticas_recentes'):
        return None
    rid=str(regra.get('regra_id') or '').strip()
    atual=estado_regra(rid) if rid else None
    if atual and atual.get('estado') in ('ATIVA','EM_OBSERVACAO'):
        return atual
    resultado=homologar_e_ativar(regra,prova,'EDDY · auto-homologação')
    # Mantém rastreabilidade explícita da decisão autônoma no motivo persistido.
    with conectar() as c:
        c.execute('UPDATE homologacoes_regras SET motivo=?, atualizado_em=? WHERE regra_id=? AND versao=?',('Auto-homologada pelo EDDY após prova ponderada perfeita (100%) e sem divergência crítica recente',agora_brasil_iso(),rid,resultado['versao']))
    resultado['auto_homologada']=True
    return resultado

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

def homologar_por_decisao_humana(regra:dict, professor:str, justificativa:str, *, nota:int=0):
    """Exceção explícita do administrador: homologação em observação, sem ativar executor."""
    _init()
    rid=str(regra.get("regra_id") or "").strip()
    professor=str(professor or "").strip()
    justificativa=str(justificativa or "").strip()
    if not rid or not professor or len(justificativa)<20:
        raise ValueError("Regra, responsável e justificativa de pelo menos 20 caracteres são obrigatórios.")
    nota=max(0,min(100,int(nota or 0)))
    raw,sha=_snapshot(regra,{"nota_ponderada_pct":nota,"excecao_manual":True,"justificativa":justificativa})
    agora=agora_brasil_iso()
    with conectar() as c:
        versao=int(c.execute("SELECT COALESCE(MAX(versao),0) FROM homologacoes_regras WHERE regra_id=?",(rid,)).fetchone()[0])+1
        c.execute("UPDATE homologacoes_regras SET estado='SUSPENSA',atualizado_em=? WHERE regra_id=? AND estado IN ('ATIVA','EM_OBSERVACAO')",(agora,rid))
        c.execute("""INSERT INTO homologacoes_regras
          (regra_id,versao,player,estado,homologado_por,homologado_em,nota,snapshot_json,snapshot_sha256,motivo,atualizado_em)
          VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
          (rid,versao,str(regra.get("player") or ""),"EM_OBSERVACAO",professor,agora,nota,raw,sha,"EXCECAO HUMANA: "+justificativa,agora))
    return estado_regra(rid)


def listar_homologacoes_mais_recentes()->list[dict]:
    _init()
    with conectar() as c:
        rows=c.execute("""SELECT h.regra_id,h.versao,h.player,h.estado,h.homologado_por,h.homologado_em,h.nota,h.motivo
          FROM homologacoes_regras h
          WHERE h.versao=(SELECT MAX(h2.versao) FROM homologacoes_regras h2 WHERE h2.regra_id=h.regra_id)
          ORDER BY h.player,h.regra_id""").fetchall()
    return [dict(row) for row in rows]
