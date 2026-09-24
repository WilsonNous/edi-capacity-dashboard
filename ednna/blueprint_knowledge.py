from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ednna.armazenamento import conectar
from redmine_api import buscar_detalhes_chamado, baixar_anexo_redmine

ASSINATURA_ABAS = {
    "PARTICIPANTES", "ESTABELECIMENTOS", "ADQUIRENTES", "DOMICILIOS BANCARIOS",
    "LOJAS FISICAS", "ID PROJETO", "INSTALACAO",
}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(v: Any) -> str:
    s = unicodedata.normalize("NFKD", str(v or "").strip().upper())
    return "".join(c for c in s if not unicodedata.combining(c))


def _init() -> None:
    with conectar() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS blueprint_documentos (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          cliente TEXT NOT NULL, chamado_id INTEGER NOT NULL, attachment_id INTEGER,
          nome_arquivo TEXT NOT NULL, content_url TEXT, sha256 TEXT NOT NULL UNIQUE,
          formato TEXT, abas_json TEXT, importado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bp_doc_cliente ON blueprint_documentos(cliente);
        CREATE INDEX IF NOT EXISTS idx_bp_doc_chamado ON blueprint_documentos(chamado_id);
        CREATE TABLE IF NOT EXISTS blueprint_linhas (
          id INTEGER PRIMARY KEY AUTOINCREMENT, documento_id INTEGER NOT NULL,
          cliente TEXT NOT NULL, aba TEXT NOT NULL, linha INTEGER NOT NULL,
          dados_json TEXT NOT NULL, chave_semantica TEXT, importado_em TEXT NOT NULL,
          FOREIGN KEY(documento_id) REFERENCES blueprint_documentos(id)
        );
        CREATE INDEX IF NOT EXISTS idx_bp_linhas_cliente_aba ON blueprint_linhas(cliente, aba);
        CREATE TABLE IF NOT EXISTS blueprint_participantes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT NOT NULL, nome TEXT,
          area TEXT, email TEXT, telefone TEXT, andamento TEXT, status_report TEXT,
          documento_id INTEGER NOT NULL, chamado_id INTEGER NOT NULL, ativo INTEGER NOT NULL DEFAULT 1,
          primeira_ocorrencia_em TEXT NOT NULL, ultima_ocorrencia_em TEXT NOT NULL,
          UNIQUE(cliente, email, documento_id)
        );
        CREATE INDEX IF NOT EXISTS idx_bp_part_cliente ON blueprint_participantes(cliente, ativo);
        CREATE TABLE IF NOT EXISTS blueprint_sync_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, chamado_id INTEGER,
          status TEXT NOT NULL, detalhes TEXT, criado_em TEXT NOT NULL
        );
        """)


def _valor(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _ler_xlsx(data: bytes) -> dict[str, list[list[str]]]:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            vals = [_valor(v) for v in row]
            if any(vals): rows.append(vals)
        out[ws.title] = rows
    return out


def _ler_xls(data: bytes) -> dict[str, list[list[str]]]:
    import xlrd
    wb = xlrd.open_workbook(file_contents=data, on_demand=True)
    out = {}
    for name in wb.sheet_names():
        sh = wb.sheet_by_name(name)
        rows = []
        for i in range(sh.nrows):
            vals = [_valor(sh.cell_value(i, j)) for j in range(sh.ncols)]
            if any(vals): rows.append(vals)
        out[name] = rows
    return out


def ler_excel(data: bytes, nome: str) -> dict[str, list[list[str]]]:
    ext = Path(nome).suffix.lower()
    return _ler_xls(data) if ext == ".xls" else _ler_xlsx(data)


def _eh_blueprint(nome: str, abas: list[str]) -> bool:
    if "BLUEPRINT" in _norm(nome):
        return True
    norm_abas = {_norm(x) for x in abas}
    pontos = len(norm_abas & ASSINATURA_ABAS)
    return "PARTICIPANTES" in norm_abas and pontos >= 3


def _header_e_dados(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    # procura cabeçalho real nas primeiras linhas; tolera títulos/linhas vazias.
    for i, row in enumerate(rows[:20]):
        n = [_norm(x) for x in row]
        if "E-MAIL" in n or "EMAIL" in n or ("NOME" in n and "AREA" in n):
            headers = [x.strip() or f"COL_{j+1}" for j, x in enumerate(row)]
            return headers, rows[i+1:]
    if rows:
        return [x.strip() or f"COL_{j+1}" for j, x in enumerate(rows[0])], rows[1:]
    return [], []


def _dict_rows(rows: list[list[str]]) -> list[dict]:
    headers, dados = _header_e_dados(rows)
    saida=[]
    for row in dados:
        item={headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        if any(str(v).strip() for v in item.values()): saida.append(item)
    return saida


def importar_blueprint(*, cliente: str, chamado_id: int, attachment: dict, conteudo: bytes) -> dict:
    _init()
    nome = str(attachment.get("filename") or "blueprint.xlsx")
    sha = hashlib.sha256(conteudo).hexdigest()
    with conectar() as c:
        existente = c.execute("SELECT id FROM blueprint_documentos WHERE sha256=?", (sha,)).fetchone()
        if existente:
            return {"status":"JA_IMPORTADO", "documento_id": int(existente[0]), "arquivo":nome}
    abas = ler_excel(conteudo, nome)
    if not _eh_blueprint(nome, list(abas)):
        return {"status":"NAO_BLUEPRINT", "arquivo":nome, "abas":list(abas)}
    agora=_agora()
    with conectar() as c:
        cur=c.execute("""INSERT INTO blueprint_documentos
          (cliente,chamado_id,attachment_id,nome_arquivo,content_url,sha256,formato,abas_json,importado_em,atualizado_em)
          VALUES (?,?,?,?,?,?,?,?,?,?)""", (cliente,int(chamado_id),attachment.get("id"),nome,attachment.get("content_url"),sha,Path(nome).suffix.lower(),json.dumps(list(abas),ensure_ascii=False),agora,agora))
        doc=int(cur.lastrowid)
        total=0
        for aba, rows in abas.items():
            for nr, item in enumerate(_dict_rows(rows), start=1):
                c.execute("INSERT INTO blueprint_linhas(documento_id,cliente,aba,linha,dados_json,chave_semantica,importado_em) VALUES(?,?,?,?,?,?,?)",
                          (doc,cliente,aba,nr,json.dumps(item,ensure_ascii=False),None,agora)); total+=1
        # participantes normalizados
        part_name=next((a for a in abas if _norm(a)=="PARTICIPANTES"), None)
        if part_name:
            for item in _dict_rows(abas[part_name]):
                norm={_norm(k):_valor(v) for k,v in item.items()}
                email=norm.get("E-MAIL") or norm.get("EMAIL") or ""
                if not email or "@" not in email: continue
                c.execute("""INSERT OR IGNORE INTO blueprint_participantes
                  (cliente,nome,area,email,telefone,andamento,status_report,documento_id,chamado_id,ativo,primeira_ocorrencia_em,ultima_ocorrencia_em)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (cliente,norm.get("NOME",""),norm.get("AREA",""),email.lower(),norm.get("TELEFONE WAPP") or norm.get("TELEFONE") or "",norm.get("ANDAMENTO",""),norm.get("STATUS REPORT",""),doc,int(chamado_id),1,agora,agora))
    return {"status":"IMPORTADO", "documento_id":doc, "arquivo":nome, "abas":list(abas), "linhas":total}


def sincronizar_blueprints_chamados(cliente: str, chamados_ids: list[int]) -> dict:
    """Procura Blueprints nos chamados do contexto já conhecido e incorpora novidades.

    Não depende do nome da filial. Arquivos Excel com 'blueprint' no nome são
    candidatos prioritários; outros Excel são validados pela assinatura das abas.
    """
    _init(); resultados=[]
    for iid in sorted({int(x) for x in chamados_ids if x}):
        try:
            issue=buscar_detalhes_chamado(iid, incluir_anexos=True, consulta_pontual=True)
            for a in issue.get("attachments",[]) or []:
                nome=str(a.get("filename") or "")
                if Path(nome).suffix.lower() not in {".xls", ".xlsx"}: continue
                attachment_id = int(a.get("id") or 0)
                if attachment_id:
                    with conectar() as c:
                        ja = c.execute("SELECT id FROM blueprint_documentos WHERE attachment_id=?", (attachment_id,)).fetchone()
                    if ja:
                        resultados.append({"chamado_id":iid,"arquivo":nome,"status":"JA_IMPORTADO","documento_id":int(ja[0])})
                        continue
                try:
                    data=baixar_anexo_redmine(str(a.get("content_url") or ""))
                    r=importar_blueprint(cliente=cliente, chamado_id=iid, attachment=a, conteudo=data)
                    if r.get("status") != "NAO_BLUEPRINT": resultados.append({"chamado_id":iid, **r})
                except Exception as exc:
                    resultados.append({"chamado_id":iid,"arquivo":nome,"status":"ERRO","erro":str(exc)[:500]})
        except Exception as exc:
            resultados.append({"chamado_id":iid,"status":"ERRO_CHAMADO","erro":str(exc)[:500]})
    with conectar() as c:
        c.execute("INSERT INTO blueprint_sync_log(cliente,chamado_id,status,detalhes,criado_em) VALUES(?,?,?,?,?)",
                  (cliente, chamados_ids[0] if chamados_ids else None, "OK", json.dumps(resultados,ensure_ascii=False), _agora()))
    return resumo_conhecimento(cliente) | {"sincronizacao":resultados}


def listar_participantes(cliente: str) -> list[dict]:
    _init()
    with conectar() as c:
        c.row_factory = __import__('sqlite3').Row
        rows=c.execute("""SELECT p.*, d.nome_arquivo AS fonte_arquivo, d.attachment_id
          FROM blueprint_participantes p JOIN blueprint_documentos d ON d.id=p.documento_id
          WHERE p.cliente=? AND p.ativo=1 ORDER BY p.area,p.nome,p.email""", (cliente,)).fetchall()
    # dedup por e-mail, preferindo documento mais novo
    out={}
    for r in rows: out[str(r['email']).lower()] = dict(r)
    return list(out.values())



def selecionar_contatos_cliente(cliente: str, limite: int = 1, area_preferida: str = "FINANCEIRO") -> list[dict]:
    """Seleciona contatos confiáveis do Blueprint preservando a ordem do documento.

    Para CC operacional usamos limite=1 (contato principal). Para workflows
    dirigidos ao cliente, como VR Benefícios, o chamador pode solicitar mais.
    Prioriza a área Financeiro e participantes marcados para andamento/status.
    Nunca consulta Redmine: esta função usa somente a base local.
    """
    _init()
    cliente = str(cliente or "").strip()
    if not cliente:
        return []
    with conectar() as c:
        c.row_factory = __import__('sqlite3').Row
        rows = c.execute("""SELECT p.*, d.nome_arquivo AS fonte_arquivo, d.attachment_id, d.importado_em
          FROM blueprint_participantes p JOIN blueprint_documentos d ON d.id=p.documento_id
          WHERE p.cliente=? AND p.ativo=1
          ORDER BY d.importado_em DESC, p.id ASC""", (cliente,)).fetchall()
    unicos=[]; vistos=set()
    for r in rows:
        d=dict(r); email=str(d.get('email') or '').strip().lower()
        if not email or email in vistos: continue
        vistos.add(email); unicos.append(d)
    pref=_norm(area_preferida)
    def score(x):
        area=_norm(x.get('area'))
        andamento=_norm(x.get('andamento')) in {'SIM','S','YES','TRUE','1'}
        status=_norm(x.get('status_report')) in {'SIM','S','YES','TRUE','1'}
        return (0 if area==pref else 1, 0 if andamento else 1, 0 if status else 1)
    unicos.sort(key=score)
    return unicos[:max(1,int(limite or 1))]


def emails_cliente_blueprint(cliente: str, limite: int = 1) -> list[str]:
    return [str(x.get('email') or '').strip().lower() for x in selecionar_contatos_cliente(cliente, limite=limite) if str(x.get('email') or '').strip()]

def resumo_conhecimento(cliente: str) -> dict:
    _init()
    with conectar() as c:
        docs=c.execute("SELECT COUNT(*), MAX(importado_em) FROM blueprint_documentos WHERE cliente=?",(cliente,)).fetchone()
        parts=c.execute("SELECT COUNT(DISTINCT email) FROM blueprint_participantes WHERE cliente=? AND ativo=1",(cliente,)).fetchone()[0]
        abas=c.execute("SELECT aba, COUNT(*) FROM blueprint_linhas WHERE cliente=? GROUP BY aba ORDER BY aba",(cliente,)).fetchall()
    return {"cliente":cliente,"blueprints":int(docs[0] or 0),"ultima_importacao":docs[1],"participantes":int(parts or 0),"abas":{a:int(n) for a,n in abas}}
