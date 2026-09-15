from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ednna.motor_acoes import carregar_catalogo_operacional

TZ = ZoneInfo('America/Sao_Paulo')


def _db_path() -> Path:
    p = os.getenv('EDNNA_DB_PATH')
    if p:
        return Path(p)
    return Path('/home/data/ednna.db') if Path('/home/data').exists() else Path('data/ednna.db')


def _conn():
    p = _db_path(); p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA busy_timeout=10000')
    return c


def _agora() -> str:
    return datetime.now(TZ).isoformat(timespec='seconds')


def inicializar_orquestrador() -> None:
    with _conn() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS cancelamento_etapas (
            chamado_id INTEGER NOT NULL,
            player TEXT NOT NULL,
            regra_id TEXT,
            estado TEXT NOT NULL,
            homologado INTEGER NOT NULL DEFAULT 0,
            identificadores TEXT,
            atualizado_em TEXT NOT NULL,
            observacao TEXT,
            PRIMARY KEY (chamado_id, player)
        )''')


def regra_cancelamento_player(player: str) -> dict | None:
    alvo = str(player or '').strip().upper()
    catalogo = carregar_catalogo_operacional()
    for regra in catalogo.get('regras', []) or []:
        if str(regra.get('intencao', '')).upper() != 'CANCELAMENTO_TRAFEGO':
            continue
        origens = [str(x).strip().upper() for x in regra.get('origens', []) or []]
        if alvo in origens and regra.get('executavel'):
            return regra
    return None


def sincronizar_plano(chamado_id: int, itens: list[dict]) -> list[dict]:
    """Persiste o estado por player. O catálogo decide se uma etapa passou a ser homologada."""
    inicializar_orquestrador()
    agora = _agora()
    with _conn() as c:
        for item in itens or []:
            player = str(item.get('player') or '').strip().upper()
            if not player:
                continue
            regra = regra_cancelamento_player(player)
            regra_id = str((regra or {}).get('id') or '')
            homologado = 1 if regra else 0
            estado_plano = str(item.get('status_plano') or 'PROCEDIMENTO_NAO_HOMOLOGADO')
            if estado_plano == 'JA_CANCELADO':
                estado = 'CONCLUIDO_HISTORICO'
            elif regra and estado_plano == 'PRONTO_REVISAO':
                estado = 'PRONTO_ATUACAO'
            elif regra and estado_plano in {'DADOS_INCOMPLETOS','CONFLITO_HISTORICO'}:
                estado = estado_plano
            elif regra:
                estado = 'HOMOLOGADO_AGUARDANDO_PREPARACAO'
            else:
                estado = 'PROCEDIMENTO_NAO_HOMOLOGADO'
            ids = ','.join(str(x) for x in item.get('identificadores', []) or [])
            c.execute('''INSERT INTO cancelamento_etapas
                (chamado_id,player,regra_id,estado,homologado,identificadores,atualizado_em,observacao)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(chamado_id,player) DO UPDATE SET
                  regra_id=CASE WHEN excluded.regra_id<>'' THEN excluded.regra_id ELSE cancelamento_etapas.regra_id END,
                  homologado=excluded.homologado,
                  identificadores=CASE WHEN excluded.identificadores<>'' THEN excluded.identificadores ELSE cancelamento_etapas.identificadores END,
                  estado=CASE
                    WHEN cancelamento_etapas.estado IN ('CANCELAMENTO_CONFIRMADO','AGUARDANDO_RESPOSTA','ENVIADO') THEN cancelamento_etapas.estado
                    ELSE excluded.estado END,
                  atualizado_em=excluded.atualizado_em''',
                (int(chamado_id),player,regra_id,estado,homologado,ids,agora,str(item.get('motivo') or '')))
    return listar_etapas(chamado_id)


def listar_etapas(chamado_id: int) -> list[dict]:
    inicializar_orquestrador()
    with _conn() as c:
        return [dict(r) for r in c.execute('SELECT * FROM cancelamento_etapas WHERE chamado_id=? ORDER BY player',(int(chamado_id),)).fetchall()]


def marcar_etapa(chamado_id: int, player: str, estado: str, observacao: str = '') -> None:
    inicializar_orquestrador(); agora=_agora(); p=str(player or '').strip().upper()
    regra=regra_cancelamento_player(p); rid=str((regra or {}).get('id') or '')
    with _conn() as c:
        c.execute('''INSERT INTO cancelamento_etapas(chamado_id,player,regra_id,estado,homologado,atualizado_em,observacao)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(chamado_id,player) DO UPDATE SET
          regra_id=CASE WHEN excluded.regra_id<>'' THEN excluded.regra_id ELSE cancelamento_etapas.regra_id END,
          estado=excluded.estado, homologado=MAX(cancelamento_etapas.homologado,excluded.homologado),
          atualizado_em=excluded.atualizado_em, observacao=excluded.observacao''',
          (int(chamado_id),p,rid,str(estado),1 if regra else 0,agora,str(observacao or '')))


def resumo_orquestracao(chamado_id: int) -> dict:
    etapas=listar_etapas(chamado_id)
    finais={'CANCELAMENTO_CONFIRMADO','CONCLUIDO_HISTORICO'}
    concluidas=sum(1 for e in etapas if e['estado'] in finais)
    pendentes=[e for e in etapas if e['estado'] not in finais]
    return {'total':len(etapas),'concluidas':concluidas,'pendentes':len(pendentes),'etapas':etapas,'todas_concluidas':bool(etapas) and not pendentes}


def rotulo_etapa(estado: str) -> str:
    return {
      'CANCELAMENTO_CONFIRMADO':'✅ Cancelamento confirmado',
      'CONCLUIDO_HISTORICO':'⚪ Já cancelado anteriormente',
      'AGUARDANDO_RESPOSTA':'🟡 Aguardando retorno',
      'ENVIADO':'🟡 Solicitação enviada',
      'PRONTO_ATUACAO':'🟢 Pronto para atuação',
      'PROCEDIMENTO_NAO_HOMOLOGADO':'🔵 Procedimento não homologado',
      'HOMOLOGADO_AGUARDANDO_PREPARACAO':'🟣 Homologado — aguardando preparação',
      'DADOS_INCOMPLETOS':'🟠 Dados incompletos',
      'CONFLITO_HISTORICO':'🔴 Conflito histórico',
    }.get(str(estado or ''), str(estado or '—'))
