from __future__ import annotations

"""Escola Contínua da EDNNA.

Persistência simples e segura da vida escolar das regras. O módulo registra
matrícula/revisões e calcula situação acadêmica, mas nunca homologa, autoriza
ou altera a execução de uma regra.
"""

from datetime import date, datetime, timedelta
from typing import Any

from ednna.armazenamento import conectar, agora_brasil_iso

CICLO_PADRAO_DIAS = 30


def _init() -> None:
    with conectar() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS escola_matriculas (
            regra_id TEXT PRIMARY KEY,
            player TEXT,
            matriculada_em TEXT NOT NULL,
            ultima_revisao_em TEXT,
            proxima_revisao_em TEXT NOT NULL,
            ciclo_dias INTEGER NOT NULL DEFAULT 30,
            status TEXT NOT NULL DEFAULT 'MATRICULADA',
            evidencias_desde_revisao INTEGER NOT NULL DEFAULT 0,
            divergencias_abertas INTEGER NOT NULL DEFAULT 0,
            aderencia_atual REAL,
            atualizado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS escola_revisoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regra_id TEXT NOT NULL,
            revisada_em TEXT NOT NULL,
            resultado TEXT NOT NULL,
            aderencia REAL,
            evidencias INTEGER NOT NULL DEFAULT 0,
            divergencias INTEGER NOT NULL DEFAULT 0,
            observacao TEXT
        );
        """)


def _iso_dia(valor: Any) -> str:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor or '').strip()
    return texto[:10] if texto else date.today().isoformat()


def matricular(regra_id: str, player: str = '', *, ciclo_dias: int = CICLO_PADRAO_DIAS, matriculada_em: Any = None) -> None:
    """Matricula sem sobrescrever a história de uma regra já matriculada."""
    _init()
    inicio = date.fromisoformat(_iso_dia(matriculada_em))
    ciclo = max(1, int(ciclo_dias or CICLO_PADRAO_DIAS))
    proxima = (inicio + timedelta(days=ciclo)).isoformat()
    agora = agora_brasil_iso()
    with conectar() as conn:
        conn.execute("""
            INSERT INTO escola_matriculas
              (regra_id, player, matriculada_em, proxima_revisao_em, ciclo_dias, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(regra_id) DO UPDATE SET
              player=CASE WHEN excluded.player <> '' THEN excluded.player ELSE escola_matriculas.player END,
              ciclo_dias=excluded.ciclo_dias,
              atualizado_em=excluded.atualizado_em
        """, (regra_id, player or '', inicio.isoformat(), proxima, ciclo, agora))


def registrar_revisao(regra_id: str, *, resultado: str, aderencia: float | None = None,
                      evidencias: int = 0, divergencias: int = 0, observacao: str = '',
                      revisada_em: Any = None) -> None:
    """Registra uma revisão; não muda homologação/autorização operacional."""
    _init()
    dia = date.fromisoformat(_iso_dia(revisada_em))
    with conectar() as conn:
        row = conn.execute('SELECT ciclo_dias FROM escola_matriculas WHERE regra_id=?', (regra_id,)).fetchone()
        ciclo = int(row[0]) if row else CICLO_PADRAO_DIAS
    if not row:
        matricular(regra_id, ciclo_dias=ciclo, matriculada_em=dia)
    proxima = (dia + timedelta(days=ciclo)).isoformat()
    divergencias = max(0, int(divergencias or 0))
    situacao = 'DIVERGENCIA_DETECTADA' if divergencias else 'CONHECIMENTO_SAUDAVEL'
    agora = agora_brasil_iso()
    with conectar() as conn:
        conn.execute("""INSERT INTO escola_revisoes
          (regra_id,revisada_em,resultado,aderencia,evidencias,divergencias,observacao)
          VALUES(?,?,?,?,?,?,?)""",
          (regra_id, dia.isoformat(), resultado, aderencia, int(evidencias or 0), divergencias, observacao or ''))
        conn.execute("""UPDATE escola_matriculas SET ultima_revisao_em=?, proxima_revisao_em=?, status=?,
          evidencias_desde_revisao=0, divergencias_abertas=?, aderencia_atual=?, atualizado_em=? WHERE regra_id=?""",
          (dia.isoformat(), proxima, situacao, divergencias, aderencia, agora, regra_id))


def registrar_evidencia(regra_id: str, *, divergente: bool = False) -> None:
    _init()
    with conectar() as conn:
        conn.execute("""UPDATE escola_matriculas SET
          evidencias_desde_revisao=evidencias_desde_revisao+1,
          divergencias_abertas=divergencias_abertas+?,
          status=CASE WHEN ?=1 THEN 'DIVERGENCIA_DETECTADA' ELSE status END,
          atualizado_em=? WHERE regra_id=?""",
          (1 if divergente else 0, 1 if divergente else 0, agora_brasil_iso(), regra_id))


def listar_matriculas() -> list[dict]:
    _init()
    hoje = date.today()
    with conectar() as conn:
        rows = conn.execute("""SELECT regra_id,player,matriculada_em,ultima_revisao_em,proxima_revisao_em,
          ciclo_dias,status,evidencias_desde_revisao,divergencias_abertas,aderencia_atual
          FROM escola_matriculas ORDER BY proxima_revisao_em, player, regra_id""").fetchall()
    saida = []
    for row in rows:
        d = dict(row)
        proxima = date.fromisoformat(d['proxima_revisao_em'])
        d['dias_para_revisao'] = (proxima - hoje).days
        if d['divergencias_abertas']:
            d['situacao_visual'] = 'PRECISO_DO_PROFESSOR'
        elif proxima < hoje:
            d['situacao_visual'] = 'REVISAO_ATRASADA'
        elif proxima <= hoje + timedelta(days=7):
            d['situacao_visual'] = 'REVISAO_PROXIMA'
        else:
            d['situacao_visual'] = 'CONHECIMENTO_SAUDAVEL'
        saida.append(d)
    return saida


def sincronizar_regras_homologadas(regras) -> int:
    """Matricula conhecimento homologado sem inferir autorização nova."""
    if regras is None or getattr(regras, 'empty', True):
        return 0
    total = 0
    for _, x in regras.iterrows():
        estado = str(x.get('estado') or '')
        revisao = str(x.get('estado_revisao') or '')
        if estado == 'HOMOLOGADA' or revisao == 'HOMOLOGADA':
            regra_id = str(x.get('regra_id') or '').strip()
            if regra_id:
                matricular(regra_id, str(x.get('player') or ''))
                total += 1
    return total
