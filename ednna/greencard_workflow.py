from __future__ import annotations

"""Orquestração Greencard — formulário -> cliente -> Greencard -> arquivos -> conclusão.

A primeira entrega automatiza com segurança a etapa inicial: gera o termo a partir
do conhecimento disponível, envia ao cliente para completar/assinar e persiste o
estado. As etapas posteriores ficam explicitamente modeladas para continuidade.
"""

import io, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ednna.armazenamento import conectar
from ednna.blueprint_knowledge import listar_participantes

TEMPLATE = Path(__file__).resolve().parents[1] / "docs/templates/TERMO_GREEN_BENEFICIOS.docx"

ESTADOS = (
    "PREPARAR_TERMO", "AGUARDANDO_CLIENTE", "VALIDAR_DOCUMENTACAO",
    "AGUARDANDO_GREENCARD", "AGUARDANDO_ARQUIVOS", "VALIDAR_ARQUIVOS",
    "ABRIR_IMPLANTACAO", "CONCLUIDO", "INTERVENCAO",
)

def _agora(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _init():
    with conectar() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS greencard_processos (
          chamado_id INTEGER PRIMARY KEY, cliente TEXT NOT NULL, blueprint_id INTEGER,
          tipo_fluxo TEXT NOT NULL DEFAULT 'INCLUSAO_ESTABELECIMENTO', estado TEXT NOT NULL,
          estabelecimentos_json TEXT, cnpjs_json TEXT, formulario_nome TEXT,
          enviado_cliente_em TEXT, enviado_greencard_em TEXT, arquivos_validados_em TEXT,
          implantacao_chamado_id INTEGER, atualizado_em TEXT NOT NULL, detalhes_json TEXT
        )""")

def _somente_digitos(v: str) -> str: return re.sub(r"\D", "", str(v or ""))

def tipo_fluxo(pacote: dict) -> str:
    texto = " ".join(str(pacote.get(k) or "") for k in ("assunto", "tipo_demanda", "descricao")).upper()
    if "ABERTURA" in texto and "RELACION" in texto:
        return "ABERTURA_RELACIONAMENTO"
    return "INCLUSAO_ESTABELECIMENTO"

def dados_formulario(pacote: dict) -> dict[str, Any]:
    cliente=str(pacote.get("cliente") or "").strip()
    cnpjs=[_somente_digitos(x) for x in (pacote.get("cnpjs") or []) if _somente_digitos(x)]
    matriz=_somente_digitos(pacote.get("cnpj_matriz") or "")
    if matriz and matriz not in cnpjs: cnpjs.insert(0, matriz)
    participantes=listar_participantes(cliente) if cliente else []
    principal=participantes[0] if participantes else {}
    return {
        "razao_social": cliente,
        "nome_fantasia": cliente,
        "cnpj_matriz": matriz or (cnpjs[0] if cnpjs else ""),
        "endereco":"", "bairro":"", "cidade":"", "estado":"", "cep":"",
        "representante_legal": str(principal.get("nome") or ""),
        "rg":"", "fone": str(principal.get("telefone") or ""),
        "email": str(principal.get("email") or ""),
        "relacao_cnpjs": cnpjs,
    }

def _set_cell_label(cell, label: str, value: str):
    txt=cell.text or ""
    if label.casefold() in txt.casefold() and value:
        # preserva a ideia do formulário sem depender de coordenadas fixas.
        cell.text=f"{label} {value}"
        return True
    return False

def gerar_formulario(pacote: dict) -> dict:
    if not TEMPLATE.exists():
        return {"ok":False,"motivo":f"Template Greencard não encontrado: {TEMPLATE}"}
    try:
        from docx import Document
    except Exception as exc:
        return {"ok":False,"motivo":f"python-docx indisponível: {exc}"}
    dados=dados_formulario(pacote)
    doc=Document(str(TEMPLATE))
    labels={
        "Razão social:":dados["razao_social"], "Nome fantasia:":dados["nome_fantasia"],
        "CNPJ Matriz:":dados["cnpj_matriz"], "Endereço:":dados["endereco"],
        "Bairro:":dados["bairro"], "Cidade:":dados["cidade"], "Estado:":dados["estado"],
        "CEP:":dados["cep"], "Nome do Representante Legal:":dados["representante_legal"],
        "Nº RG:":dados["rg"], "Fone(s):":dados["fone"], "E-mail:":dados["email"],
    }
    vistos=set()
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                ident=cell._tc
                if ident in vistos: continue
                vistos.add(ident)
                for label,value in labels.items():
                    if _set_cell_label(cell,label,str(value or "")): break
        # Relação de CNPJs: usa a primeira linha vazia logo após o título.
        for i,row in enumerate(table.rows[:-1]):
            if any("RELAÇÃO DE CNPJS" in (c.text or "").upper() for c in row.cells):
                vals=dados.get("relacao_cnpjs") or []
                if vals:
                    table.rows[i+1].cells[0].text="CNPJ(s): " + "; ".join(vals)
                break
    bio=io.BytesIO(); doc.save(bio)
    cid=int(pacote.get("chamado_id") or 0)
    nome=f"TERMO_GREENCARD_{cid}_{re.sub(r'[^A-Za-z0-9]+','_',str(pacote.get('cliente') or 'CLIENTE')).strip('_')}.docx"
    return {"ok":True,"filename":nome,"content_type":"application/vnd.openxmlformats-officedocument.wordprocessingml.document","conteudo":bio.getvalue(),"dados":dados}

def preparar_primeira_etapa(pacote: dict) -> dict:
    form=gerar_formulario(pacote)
    if not form.get("ok"): return form
    emails=[str(e).strip().lower() for e in (pacote.get("emails_blueprint") or []) if str(e).strip()]
    if not emails:
        return {"ok":False,"estado":"AGUARDANDO_DADOS","motivo":"GREENCARD: Blueprint ainda não possui participante/e-mail do cliente para receber o formulário."}
    cliente=str(pacote.get("cliente") or "Cliente")
    cid=int(pacote.get("chamado_id") or 0)
    fluxo=tipo_fluxo(pacote)
    assunto=f"[GREENCARD - {'Abertura de Relacionamento' if fluxo=='ABERTURA_RELACIONAMENTO' else 'Inclusão de Estabelecimento'} - {cliente} - CN: {cid}]"
    corpo=("Olá, tudo bem?\n\n"
           "Para darmos continuidade ao processo junto à Greencard, encaminhamos em anexo o formulário com os dados que a EDNNA conseguiu pré-preencher.\n\n"
           "Por gentileza, revise as informações, complete os campos que ainda estiverem em branco, assine o documento e nos devolva o formulário acompanhado do documento de identidade do representante legal.\n\n"
           "Após o retorno, faremos a validação e encaminharemos a documentação à Greencard. Em seguida acompanharemos a liberação e a chegada dos arquivos.\n\n"
           "Atenciosamente,\nEquipe EDI Netunna\n\n"
           "Mensagem operacional preparada e acompanhada pela EDNNA — Automação EDI Netunna.")
    return {"ok":True,"para":emails,"cc":[],"assunto":assunto,"corpo":corpo,
            "anexos":[{"filename":form["filename"],"content_type":form["content_type"],"conteudo":form["conteudo"]}],
            "tipo_acao":"GREENCARD_ENVIAR_FORMULARIO_CLIENTE","status_pos_envio":"Aguardando Retorno Cliente",
            "prazo_resposta_dias_uteis":2,"fluxo_greencard":fluxo,"formulario":form}

def registrar_estado(pacote: dict, estado: str, **detalhes):
    _init(); cid=int(pacote.get("chamado_id") or 0); cliente=str(pacote.get("cliente") or "")
    fluxo=detalhes.pop("tipo_fluxo",None) or tipo_fluxo(pacote)
    bp=pacote.get("blueprint_id")
    with conectar() as c:
        c.execute("""INSERT INTO greencard_processos(chamado_id,cliente,blueprint_id,tipo_fluxo,estado,estabelecimentos_json,cnpjs_json,formulario_nome,atualizado_em,detalhes_json)
        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(chamado_id) DO UPDATE SET cliente=excluded.cliente,blueprint_id=COALESCE(excluded.blueprint_id,greencard_processos.blueprint_id),tipo_fluxo=excluded.tipo_fluxo,estado=excluded.estado,estabelecimentos_json=excluded.estabelecimentos_json,cnpjs_json=excluded.cnpjs_json,formulario_nome=COALESCE(excluded.formulario_nome,greencard_processos.formulario_nome),atualizado_em=excluded.atualizado_em,detalhes_json=excluded.detalhes_json""",
        (cid,cliente,bp,fluxo,estado,json.dumps(pacote.get("estabelecimentos") or []),json.dumps(pacote.get("cnpjs") or []),detalhes.get("formulario_nome"),_agora(),json.dumps(detalhes,ensure_ascii=False,default=str)))

def registrar_movimentacao_bp(pacote: dict, mensagem: str) -> dict:
    bp=int(pacote.get("blueprint_id") or 0)
    if not bp: return {"ok":False,"motivo":"BP principal não localizado"}
    try:
        from ednna.redmine_writer import adicionar_nota_chamado
        marcador=f"EDNNA-GREENCARD:{int(pacote.get('chamado_id') or 0)}"
        nota=f"*EDNNA · Movimentação Greencard*\n\n{mensagem}\n\nMarcador: {marcador}"
        return {"ok":True,"resultado":adicionar_nota_chamado(chamado_id=bp,nota=nota)}
    except Exception as exc:
        return {"ok":False,"motivo":f"{type(exc).__name__}: {exc}"}
