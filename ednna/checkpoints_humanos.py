from __future__ import annotations

"""Checkpoints humanos estruturados da EDNNA.

A EDNNA continua dona do workflow. O operador executa somente a etapa que ainda
não pode ser automatizada, informa o resultado, e a EDNNA registra a evidência
no Redmine antes de liberar a próxima etapa.
"""
import json
from ednna.acompanhamento_acoes import _conectar, _agora, _iso

STATUS_PENDENTE = "PENDENTE"
STATUS_REDMINE_PENDENTE = "REDMINE_PENDENTE"
STATUS_CONCLUIDO = "CONCLUIDO"
STATUS_FALHOU = "FALHOU"


def inicializar_checkpoints() -> None:
    with _conectar() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints_humanos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chamado_id INTEGER NOT NULL,
            regra_id TEXT NOT NULL,
            codigo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDENTE',
            solicitado_em TEXT NOT NULL,
            concluido_em TEXT,
            executado_por_email TEXT,
            executado_por_nome TEXT,
            resultado TEXT,
            relato_humano TEXT,
            dados_json TEXT,
            redmine_registrado_em TEXT,
            redmine_erro TEXT,
            UNIQUE(chamado_id, regra_id, codigo)
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON checkpoints_humanos(status)")


def garantir_checkpoint(chamado_id: int, regra_id: str, codigo: str, titulo: str) -> dict:
    inicializar_checkpoints()
    agora = _iso(_agora())
    with _conectar() as conn:
        conn.execute("""INSERT OR IGNORE INTO checkpoints_humanos
            (chamado_id,regra_id,codigo,titulo,status,solicitado_em)
            VALUES(?,?,?,?,?,?)""",
            (int(chamado_id), str(regra_id), str(codigo), str(titulo), STATUS_PENDENTE, agora))
        row = conn.execute("SELECT * FROM checkpoints_humanos WHERE chamado_id=? AND regra_id=? AND codigo=?",
                           (int(chamado_id), str(regra_id), str(codigo))).fetchone()
    return dict(row) if row else {}


def obter_checkpoint(chamado_id: int, regra_id: str, codigo: str) -> dict:
    inicializar_checkpoints()
    with _conectar() as conn:
        row = conn.execute("SELECT * FROM checkpoints_humanos WHERE chamado_id=? AND regra_id=? AND codigo=?",
                           (int(chamado_id), str(regra_id), str(codigo))).fetchone()
    return dict(row) if row else {}


def checkpoint_concluido(chamado_id: int, regra_id: str, codigo: str) -> bool:
    return str(obter_checkpoint(chamado_id, regra_id, codigo).get("status") or "").upper() == STATUS_CONCLUIDO


def registrar_resultado_checkpoint(*, chamado_id: int, regra_id: str, codigo: str, titulo: str,
                                   resultado: str, relato: str, usuario_email: str, usuario_nome: str,
                                   dados: dict | None = None) -> dict:
    """Registra a resposta humana e só conclui o checkpoint após journal no Redmine.

    Fail-safe: se o pre-flight ou o journal falhar, o checkpoint NÃO avança o workflow.
    O relato fica persistido como REDMINE_PENDENTE para não se perder.
    """
    cp = garantir_checkpoint(chamado_id, regra_id, codigo, titulo)
    if str(cp.get("status") or "").upper() == STATUS_CONCLUIDO:
        return {"ok": True, "ja_concluido": True, "checkpoint": cp}
    relato = str(relato or "").strip()
    resultado = str(resultado or "").strip().upper()
    if not relato:
        return {"ok": False, "motivo": "Informe o que foi feito e como foi feito."}
    if resultado not in {"CONCLUIDO", "NAO_CONSEGUI", "REAVALIAR"}:
        return {"ok": False, "motivo": "Resultado do checkpoint inválido."}

    agora = _iso(_agora())
    dados = dict(dados or {})
    with _conectar() as conn:
        conn.execute("""UPDATE checkpoints_humanos SET status=?, executado_por_email=?, executado_por_nome=?,
            resultado=?, relato_humano=?, dados_json=?, redmine_erro=NULL WHERE chamado_id=? AND regra_id=? AND codigo=?""",
            (STATUS_REDMINE_PENDENTE, usuario_email, usuario_nome, resultado, relato,
             json.dumps(dados, ensure_ascii=False), int(chamado_id), str(regra_id), str(codigo)))

    from ednna.status_guard import validar_efeito_externo
    pf = validar_efeito_externo(int(chamado_id), "CHECKPOINT_HUMANO_REDMINE")
    if pf.get("bloquear"):
        erro = f"Pre-flight bloqueou o registro: {pf.get('motivo') or 'indisponível'}"
        with _conectar() as conn:
            conn.execute("UPDATE checkpoints_humanos SET redmine_erro=? WHERE chamado_id=? AND regra_id=? AND codigo=?",
                         (erro, int(chamado_id), str(regra_id), str(codigo)))
        return {"ok": False, "pendente": True, "motivo": erro, "preflight": pf}

    nota = "\n".join([
        "*EDNNA — Checkpoint humano*", "",
        f"*Etapa:* {titulo}",
        f"*Executado por:* {usuario_nome or usuario_email}",
        f"*Resultado:* {resultado.replace('_', ' ').title()}", "",
        "*O que foi feito / como foi feito:*", relato,
        "", "*Workflow EDNNA:* " + ("checkpoint concluído; EDNNA retoma a próxima etapa." if resultado == "CONCLUIDO" else "checkpoint não concluído; EDNNA aguarda reavaliação."),
        f"*Marcador:* EDNNA-CHECKPOINT:{regra_id}:{codigo}",
    ])
    try:
        from ednna.redmine_writer import adicionar_nota_chamado
        adicionar_nota_chamado(chamado_id=int(chamado_id), nota=nota)
    except Exception as exc:
        erro = f"{type(exc).__name__}: {exc}"
        with _conectar() as conn:
            conn.execute("UPDATE checkpoints_humanos SET redmine_erro=? WHERE chamado_id=? AND regra_id=? AND codigo=?",
                         (erro, int(chamado_id), str(regra_id), str(codigo)))
        return {"ok": False, "pendente": True, "motivo": "Relato salvo localmente; Redmine pendente.", "erro": erro}

    status_final = STATUS_CONCLUIDO if resultado == "CONCLUIDO" else STATUS_FALHOU
    with _conectar() as conn:
        conn.execute("""UPDATE checkpoints_humanos SET status=?, concluido_em=?, redmine_registrado_em=?, redmine_erro=NULL
            WHERE chamado_id=? AND regra_id=? AND codigo=?""",
            (status_final, agora, agora, int(chamado_id), str(regra_id), str(codigo)))
    try:
        from ednna.observabilidade import log_event
        log_event("CHECKPOINT", "Checkpoint humano registrado", nivel="INFO", chamado_id=int(chamado_id),
                  detalhe=f"regra={regra_id} | codigo={codigo} | resultado={resultado} | operador={usuario_email}")
    except Exception:
        pass
    return {"ok": True, "status": status_final, "retomar": status_final == STATUS_CONCLUIDO}
