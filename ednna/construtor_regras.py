from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from ednna.armazenamento import conectar, agora_brasil_iso

ESTADOS = ("RASCUNHO", "EM_TESTE", "HOMOLOGADA")
TIPOS = ("ADQUIRENTE", "BENEFICIO", "BANCO", "OUTRO")
CANAIS = ("EMAIL", "DOCUMENTO+EMAIL", "API", "CHAMADO", "RELACIONAMENTO_BANCARIO")
FONTES = ("CHAMADO_ATUAL", "BLUEPRINT", "BLUEPRINT_PARTICIPANTES", "BLUEPRINT_DOMICILIOS_BANCARIOS", "ABERTURA_RELACIONAMENTO")
VARIAVEIS = {
    "cliente": "Cliente", "cnpjs": "CNPJ(s)", "cnpj_matriz": "CNPJ matriz",
    "estabelecimento": "Estabelecimento / EC", "participante": "Participante do cliente",
    "email_participante": "E-mail do participante", "contas_bancarias": "Conta(s) bancária(s)",
    "contato_gerente": "Gerente / contato bancário", "email_gerente": "E-mail do gerente",
    "agencia": "Agência", "banco": "Banco", "chamado": "Número do chamado",
}
ACOES = {
    "EXTRAIR_DADOS": "Extrair dados do chamado",
    "CONSULTAR_BLUEPRINT": "Consultar Base de Conhecimento / Blueprint",
    "PREPARAR_EMAIL": "Preparar e-mail",
    "ENVIAR_EMAIL": "Enviar e-mail",
    "ENVIAR_FORMULARIO": "Gerar/enviar formulário",
    "AGUARDAR_RESPOSTA": "Aguardar resposta",
    "FOLLOWUP": "Fazer follow-up",
    "VALIDAR_DOCUMENTO": "Validar documento",
    "VALIDAR_ARQUIVO": "Validar arquivo / EC",
    "ATUALIZAR_REDMINE": "Atualizar Redmine",
    "ATUALIZAR_BP": "Registrar movimentação no BP",
    "ABRIR_CHAMADO": "Abrir chamado de implantação/suporte",
    "CONCLUIR": "Concluir processo",
}

def _init() -> None:
    with conectar() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS regras_treinaveis (
            id TEXT PRIMARY KEY, player TEXT NOT NULL, nome TEXT NOT NULL,
            tipo_player TEXT NOT NULL DEFAULT 'OUTRO', aliases_json TEXT NOT NULL DEFAULT '[]',
            tipos_chamado_json TEXT NOT NULL DEFAULT '[]', canal TEXT NOT NULL DEFAULT 'EMAIL',
            fonte_dados TEXT NOT NULL DEFAULT 'CHAMADO_ATUAL', destinatario TEXT,
            variaveis_json TEXT NOT NULL DEFAULT '[]', etapas_json TEXT NOT NULL DEFAULT '[]',
            assunto_template TEXT, corpo_template TEXT, followup_template TEXT,
            descricao TEXT, estado TEXT NOT NULL DEFAULT 'RASCUNHO',
            criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS testes_regras_treinaveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT, regra_id TEXT NOT NULL, chamado_id INTEGER,
            assunto TEXT, descricao TEXT, resultado_json TEXT NOT NULL, testado_em TEXT NOT NULL
        );
        """)
        conn.commit()

_init()

def salvar_regra(dados: dict[str, Any]) -> str:
    rid = str(dados.get("id") or f"TREINO-{uuid.uuid4().hex[:10].upper()}")
    now = agora_brasil_iso()
    with conectar() as conn:
        existe = conn.execute("SELECT 1 FROM regras_treinaveis WHERE id=?", (rid,)).fetchone()
        criado = now if not existe else conn.execute("SELECT criado_em FROM regras_treinaveis WHERE id=?", (rid,)).fetchone()[0]
        vals = (
            rid, str(dados.get("player") or "").strip().upper(), str(dados.get("nome") or "").strip(),
            str(dados.get("tipo_player") or "OUTRO"), json.dumps(dados.get("aliases") or [], ensure_ascii=False),
            json.dumps(dados.get("tipos_chamado") or [], ensure_ascii=False), str(dados.get("canal") or "EMAIL"),
            str(dados.get("fonte_dados") or "CHAMADO_ATUAL"), str(dados.get("destinatario") or "").strip(),
            json.dumps(dados.get("variaveis") or [], ensure_ascii=False), json.dumps(dados.get("etapas") or [], ensure_ascii=False),
            str(dados.get("assunto_template") or ""), str(dados.get("corpo_template") or ""), str(dados.get("followup_template") or ""),
            str(dados.get("descricao") or ""), str(dados.get("estado") or "RASCUNHO"), criado, now,
        )
        conn.execute("""INSERT OR REPLACE INTO regras_treinaveis
        (id,player,nome,tipo_player,aliases_json,tipos_chamado_json,canal,fonte_dados,destinatario,variaveis_json,etapas_json,assunto_template,corpo_template,followup_template,descricao,estado,criado_em,atualizado_em)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", vals)
        conn.commit()
    return rid

def _row(r) -> dict:
    d = dict(r)
    for k in ("aliases_json","tipos_chamado_json","variaveis_json","etapas_json"):
        d[k[:-5]] = json.loads(d.pop(k) or "[]")
    return d

def listar_regras_treinaveis() -> list[dict]:
    with conectar() as conn:
        return [_row(r) for r in conn.execute("SELECT * FROM regras_treinaveis ORDER BY atualizado_em DESC").fetchall()]

def obter_regra_treinavel(rid: str) -> dict | None:
    with conectar() as conn:
        r = conn.execute("SELECT * FROM regras_treinaveis WHERE id=?", (rid,)).fetchone()
    return _row(r) if r else None

def obter_workflow_treinavel(player: str) -> dict | None:
    p = str(player or "").strip().upper()
    with conectar() as conn:
        rows = conn.execute("SELECT * FROM regras_treinaveis WHERE estado='HOMOLOGADA' ORDER BY atualizado_em DESC").fetchall()
    for rr in rows:
        d = _row(rr)
        nomes = [d["player"], *d.get("aliases", [])]
        if p in {str(x).strip().upper() for x in nomes}:
            return {
                "tipo_player": d["tipo_player"], "workflow": f"TREINAVEL_{d['id']}", "canal": d["canal"],
                "fonte_dados": d["fonte_dados"], "executor": "EMAIL_GRAPH" if d["canal"] == "EMAIL" else "NAO_IMPLEMENTADO",
                "campos_obrigatorios": d.get("variaveis", []), "destinatario_padrao": d.get("destinatario") or "",
                "etapas": d.get("etapas", []), "regra_dados": d.get("descricao") or "Regra criada pelo Construtor de Regras.",
                "fonte_autoridade": "CONSTRUTOR_REGRAS", "procedimento_confirmado": True, "regra_treinavel_id": d["id"],
            }
    return None

def testar_regra(regra: dict, assunto: str, descricao: str, chamado_id: int | None = None) -> dict:
    texto = f"{assunto}\n{descricao}".upper()
    termos = [regra.get("player"), *(regra.get("aliases") or [])]
    encontrados = [t for t in termos if t and str(t).upper() in texto]
    variaveis = {}
    cnpjs = re.findall(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", descricao)
    if cnpjs: variaveis["cnpjs"] = cnpjs
    ecs = re.findall(r"(?i)(?:EC|ESTABELECIMENTO|CONVENIO)\s*[:#-]?\s*([0-9]{5,20})", descricao)
    if ecs: variaveis["estabelecimento"] = list(dict.fromkeys(ecs))
    contas = re.findall(r"(?i)\bconta\s*[:#-]?\s*([0-9][0-9.\- ]{2,20})", descricao)
    if contas: variaveis["contas_bancarias"] = [x.strip() for x in contas]
    obrig = regra.get("variaveis") or []
    faltam = [v for v in obrig if v not in variaveis and v not in {"cliente","participante","email_participante","contato_gerente","email_gerente","banco","agencia","chamado"}]
    resultado = {"identificada": bool(encontrados), "termos_encontrados": encontrados, "variaveis_extraidas": variaveis, "faltantes_no_texto": faltam, "executavel_textualmente": bool(encontrados) and not faltam}
    with conectar() as conn:
        conn.execute("INSERT INTO testes_regras_treinaveis(regra_id,chamado_id,assunto,descricao,resultado_json,testado_em) VALUES(?,?,?,?,?,?)",
                     (regra["id"], chamado_id, assunto, descricao, json.dumps(resultado, ensure_ascii=False), agora_brasil_iso()))
        conn.commit()
    return resultado

def explicar_regra(r: dict) -> str:
    vars_txt = ", ".join(VARIAVEIS.get(x,x) for x in r.get("variaveis", [])) or "nenhuma variável obrigatória declarada"
    etapas = " → ".join(ACOES.get(x,x) for x in r.get("etapas", [])) or "nenhuma etapa definida"
    aliases = ", ".join(r.get("aliases", [])) or "sem aliases adicionais"
    return (f"Reconheço esta regra como {r.get('player')} ({aliases}). Ela atende {', '.join(r.get('tipos_chamado', [])) or 'os tipos ainda não informados'}, "
            f"usa {r.get('fonte_dados')} como fonte principal e trabalha pelo canal {r.get('canal')}. "
            f"Antes de agir preciso de: {vars_txt}. O procedimento ensinado é: {etapas}. "
            f"Estado atual: {r.get('estado')}.")
