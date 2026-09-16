from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from ednna.armazenamento import conectar, agora_brasil_iso
from ednna.contexto_relacionamentos import buscar_issue_contexto

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CNPJ_RE = re.compile(r"(?<!\d)\d{2}[.\s]?\d{3}[.\s]?\d{3}[\s/.-]?\d{4}[-.\s]?\d{2}(?!\d)")
_NUM_RE = re.compile(r"\b\d{4,}\b")
_FIELD_PATTERNS = {
    "para": re.compile(r"(?i)^\s*(?:para|to)\s*[:：]\s*(.+)$"),
    "cc": re.compile(r"(?i)^\s*(?:cc|c\.c\.)\s*[:：]\s*(.+)$"),
    "assunto": re.compile(r"(?i)^\s*(?:assunto|subject)\s*[:：]\s*(.+)$"),
}
_SUCCESS_RE = re.compile(r"(?i)\b(?:conclu[ií]d[oa]s?|confirmad[oa]s?|ativad[oa]s?|inclu[ií]d[oa]s?|cadastrad[oa]s?|processad[oa]s?|realizad[oa]s?|liberad[oa]s?|habilitad[oa]s?)\b")
_ACTION_RE = re.compile(r"(?i)\b(?:solicit|pedimos|providenciar|incluir|inclus[aã]o|cadastr|habilit|ativ|tr[aá]fego|estabelecimento|conv[eê]nio|filia[cç][aã]o)\w*\b")


# v3.28.18 — leitura de threads reais de e-mail.
_PROTOCOL_RE = re.compile(r"(?i)\bprotocolo\s*(?:n[º°o.]*)?\s*[:#-]?\s*(\d{4,})\b")
_DEADLINE_RE = re.compile(r"(?i)\b(?:em|at[eé])\s*(\d{1,3})\s*horas?\b")
_FROM_RE = re.compile(r"(?im)^\s*(?:de|from)\s*:\s*(.+)$")
_TO_RE = re.compile(r"(?im)^\s*(?:para|to)\s*:\s*(.+)$")
_CC_RE = re.compile(r"(?im)^\s*(?:cc|c\.c\.)\s*:\s*(.+)$")
_SUBJECT_RE = re.compile(r"(?im)^\s*(?:assunto|subject)\s*:\s*(.+)$")
_IN_PROGRESS_RE = re.compile(r"(?i)\b(?:recebemos sua solicita[cç][aã]o|em acompanhamento|iniciamos? as valida[cç][oõ]es|em tratativa|protocolo)\b")
_COMPLETED_RE = re.compile(r"(?i)\b(?:inclus[aã]o.{0,80}(?:com sucesso|conclu[ií]d)|realizamos? a inclus[aã]o|regulariza[cç][aã]o.{0,50}conclu[ií]d|j[aá] estar[aá] dispon[ií]vel)\b")
_REQUEST_RE = re.compile(r"(?i)\b(?:solicitamos?.{0,120}inclus[aã]o|inclus[aã]o no tr[aá]fego|inclus[aã]o de estabelecimento)\b")

def _blocos_email(texto: str) -> list[str]:
    # Journals do Redmine normalmente preservam mensagens encadeadas. Cada novo
    # cabeçalho De:/From: inicia uma mensagem; se não houver cabeçalho, o texto
    # inteiro continua sendo analisado como um bloco.
    marcas=list(re.finditer(r"(?im)^\s*(?:de|from)\s*:", texto or ""))
    if not marcas:
        return [texto] if str(texto or '').strip() else []
    out=[]
    for i,m in enumerate(marcas):
        fim=marcas[i+1].start() if i+1 < len(marcas) else len(texto)
        out.append(texto[m.start():fim])
    prefixo=texto[:marcas[0].start()].strip()
    if prefixo: out.insert(0,prefixo)
    return out

def _primeiro_email(pat, bloco: str) -> str:
    m=pat.search(bloco or '')
    if not m: return ''
    vals=_EMAIL_RE.findall(m.group(1))
    return vals[0].lower() if vals else ''

def _emails_cabecalho(pat, bloco: str) -> list[str]:
    m=pat.search(bloco or '')
    return sorted(set(e.lower() for e in _EMAIL_RE.findall(m.group(1)))) if m else []

def _extrair_thread(issue: dict) -> dict:
    mensagens=[]
    blocos=[('descricao', str(issue.get('description') or ''))]
    blocos += [(f"journal_{i}", str(j.get('notes') or '')) for i,j in enumerate(issue.get('journals',[]) or [],1) if j.get('notes')]
    for origem,texto in blocos:
        for bloco in _blocos_email(texto):
            remetente=_primeiro_email(_FROM_RE, bloco)
            para=_emails_cabecalho(_TO_RE, bloco); cc=_emails_cabecalho(_CC_RE, bloco)
            sm=_SUBJECT_RE.search(bloco); assunto=_normalizar_template(sm.group(1)) if sm else ''
            externo=bool(remetente and not remetente.endswith('@netunna.com.br'))
            interno=bool(remetente and remetente.endswith('@netunna.com.br'))
            estado='INDEFINIDO'
            if externo and _COMPLETED_RE.search(bloco): estado='CONCLUIDO'
            elif externo and _IN_PROGRESS_RE.search(bloco): estado='EM_TRATATIVA'
            elif interno and _REQUEST_RE.search(bloco): estado='SOLICITADO'
            elif _REQUEST_RE.search(bloco) and any(not e.endswith('@netunna.com.br') for e in para): estado='SOLICITADO'
            protocolo=(_PROTOCOL_RE.search(bloco).group(1) if _PROTOCOL_RE.search(bloco) else None)
            prazo=(_DEADLINE_RE.search(bloco).group(1) if _DEADLINE_RE.search(bloco) else None)
            if estado!='INDEFINIDO' or remetente or para:
                mensagens.append({'origem':origem,'estado':estado,'remetente':remetente,'para':para,'cc':cc,'assunto':assunto,'protocolo':protocolo,'prazo_horas':int(prazo) if prazo else None,'resumo':_normalizar_template(bloco)[:700]})
    # Uma thread completa confirma operacionalmente o endereço do player quando
    # a Netunna envia para ele e o mesmo endereço aparece como remetente externo.
    enviados=set(e for m in mensagens if m['estado']=='SOLICITADO' for e in m['para'] if not e.endswith('@netunna.com.br'))
    remetentes=set(m['remetente'] for m in mensagens if m['remetente'] and not m['remetente'].endswith('@netunna.com.br'))
    confirmados=sorted(enviados & remetentes)
    estados=[m['estado'] for m in mensagens if m['estado']!='INDEFINIDO']
    return {'mensagens':mensagens,'destinatarios_confirmados_thread':confirmados,'protocolos':sorted(set(m['protocolo'] for m in mensagens if m['protocolo'])),'prazos_horas':sorted(set(m['prazo_horas'] for m in mensagens if m['prazo_horas'])),'estados':estados,'ciclo_completo':all(x in estados for x in ('SOLICITADO','EM_TRATATIVA','CONCLUIDO'))}

def _normalizar_template(texto: str) -> str:
    s = " ".join(str(texto or "").strip().split())
    s = _EMAIL_RE.sub("<EMAIL>", s)
    s = _CNPJ_RE.sub("<CNPJ>", s)
    s = re.sub(r"#?\b\d{4,}\b", "<NUM>", s)
    return s[:700]

def _eventos_operacionais(issue: dict) -> dict:
    """Extrai sinais auditáveis de solicitação, resposta e movimentação do chamado."""
    textos = [("descricao", str(issue.get("description") or ""))]
    for idx, j in enumerate(issue.get("journals", []) or [], 1):
        if j.get("notes"):
            textos.append((f"journal_{idx}", str(j.get("notes") or "")))
    para, cc, assuntos, acoes, sucessos = [], [], [], [], []
    for origem, texto in textos:
        for linha in texto.splitlines():
            limpa = " ".join(linha.strip().split())
            if not limpa: continue
            for nome, pat in _FIELD_PATTERNS.items():
                m = pat.match(limpa)
                if m:
                    vals = _EMAIL_RE.findall(m.group(1))
                    if nome == "para": para.extend(e.lower() for e in vals)
                    elif nome == "cc": cc.extend(e.lower() for e in vals)
                    elif nome == "assunto": assuntos.append(_normalizar_template(m.group(1)))
            if _ACTION_RE.search(limpa) and len(limpa) >= 15:
                acoes.append({"origem": origem, "texto": _normalizar_template(limpa)})
            if _SUCCESS_RE.search(limpa) and len(limpa) >= 12:
                sucessos.append({"origem": origem, "texto": _normalizar_template(limpa)})
    # fallback: e-mails presentes em textos de solicitação são evidência, mas não confirmação de destinatário
    return {"para": sorted(set(para)), "cc": sorted(set(cc)), "assuntos": list(dict.fromkeys(assuntos)),
            "acoes": acoes[:30], "sucessos": sucessos[:20]}

def _linha_tempo_operacional(issue: dict) -> list[dict]:
    """Classifica evidências em solicitação externa, retorno do player e ação interna."""
    eventos=[]
    blocos=[("descricao", str(issue.get("description") or ""))]
    blocos += [(f"journal_{i}", str(j.get("notes") or "")) for i,j in enumerate(issue.get("journals",[]) or [],1) if j.get("notes")]
    for origem,texto in blocos:
        low=texto.lower()
        emails=[e.lower() for e in _EMAIL_RE.findall(texto)]
        externos=[e for e in emails if not e.endswith("@netunna.com.br")]
        if externos and re.search(r"(?i)\b(solicit|pedimos|favor|inclus|habilit|ativ)\w*", texto):
            eventos.append({"tipo":"SOLICITACAO_EXTERNA","origem":origem,"emails_externos":sorted(set(externos)),"resumo":_normalizar_template(texto)[:500]})
        if externos and _SUCCESS_RE.search(texto) and re.search(r"(?i)\b(conclu|confirm|ativad|inclu|habilitad|realizad)\w*", texto):
            eventos.append({"tipo":"RETORNO_PLAYER","origem":origem,"emails_externos":sorted(set(externos)),"resumo":_normalizar_template(texto)[:500]})
        if not externos and (_ACTION_RE.search(texto) or _SUCCESS_RE.search(texto)):
            eventos.append({"tipo":"ACAO_INTERNA","origem":origem,"emails_externos":[],"resumo":_normalizar_template(texto)[:500]})
    return eventos[:30]

def _recorrencia_eventos(hist: list[dict]) -> dict:
    eventos = {int(i.get("id") or 0): _eventos_operacionais(i) for i in hist}
    linhas_tempo = {int(i.get("id") or 0): _linha_tempo_operacional(i) for i in hist}
    def recorrentes(campo):
        c=Counter(v for ev in eventos.values() for v in set(ev.get(campo) or []))
        return [{"valor":v,"ocorrencias":n,"confirmado":n>=2} for v,n in c.most_common()]
    ac=Counter(x["texto"] for ev in eventos.values() for x in ev["acoes"]); sc=Counter(x["texto"] for ev in eventos.values() for x in ev["sucessos"]); subj=Counter(v for ev in eventos.values() for v in set(ev["assuntos"]))
    return {"por_chamado": eventos, "linha_tempo": linhas_tempo, "destinatarios": recorrentes("para"), "cc": recorrentes("cc"),
            "assuntos": [{"valor":v,"ocorrencias":n,"confirmado":n>=2} for v,n in subj.most_common()],
            "acoes_recorrentes": [{"valor":v,"ocorrencias":n} for v,n in ac.most_common() if n>=2][:12],
            "evidencias_sucesso": [{"valor":v,"ocorrencias":n} for v,n in sc.most_common() if n>=1][:12]}



def _texto_issue(issue: dict) -> str:
    partes = [str(issue.get("subject") or ""), str(issue.get("description") or "")]
    partes += [str(j.get("notes") or "") for j in issue.get("journals", []) or [] if j.get("notes")]
    return "\n".join(p for p in partes if p.strip())


def _emails(issue: dict) -> list[str]:
    return sorted(set(_EMAIL_RE.findall(_texto_issue(issue))), key=str.lower)


def _linhas_procedimento(issue: dict) -> list[str]:
    saida = []
    for linha in _texto_issue(issue).splitlines():
        s = " ".join(linha.strip().split())
        if len(s) < 12:
            continue
        n = _EMAIL_RE.sub("<EMAIL>", s)
        n = _CNPJ_RE.sub("<CNPJ>", n)
        n = _NUM_RE.sub("<NUM>", n)
        saida.append(n[:500])
    return saida


def _inferir_constantes(issues_historicos: list[dict]) -> list[str]:
    if len(issues_historicos) < 2:
        return []
    por_issue = [set(_linhas_procedimento(i)) for i in issues_historicos]
    cont = Counter(x for grupo in por_issue for x in grupo)
    return [x for x, qtd in cont.most_common() if qtd >= 2][:12]


def _inferir_variaveis(issues: list[dict]) -> list[str]:
    texto = "\n".join(_texto_issue(i) for i in issues)
    vars_ = []
    if _CNPJ_RE.search(texto): vars_.append("CNPJ")
    if re.search(r"(?i)\b(?:EC|estabelecimento|conv[eê]nio|filia[cç][aã]o)\b", texto): vars_.append("EC/Convênio")
    vars_ += ["Cliente", "Chamado Redmine"]
    return list(dict.fromkeys(vars_))


def _fonte_parcial(issue: dict) -> bool:
    return bool((issue.get("_ednna_contexto") or {}).get("parcial"))


def _sinais_semanticos(hist: list[dict], recorrentes: list[str], constantes: list[str]) -> dict:
    texto = "\n".join(_texto_issue(i) for i in hist)
    return {
        "destinatario_recorrente": bool(recorrentes),
        "padrao_assunto": len(hist) >= 2 and all(str(i.get("subject") or "").strip() for i in hist),
        "estrutura_mensagem": bool(constantes),
        "campos_operacionais": bool(re.search(r"(?i)\b(?:EC|estabelecimento|conv[eê]nio|filia[cç][aã]o|CNPJ)\b", texto)),
        "evidencia_conclusao": bool(re.search(r"(?i)\b(?:conclu[ií]d|confirm|ativad|inclu[ií]d|cadastrad|processad|realizad)\w*\b", texto)),
    }


def aprender_procedimento_inclusao(aprendizado: dict, regra: dict, *, force: bool = False) -> dict:
    regra_id = str(regra.get("regra_sugerida") or "").strip()
    player = str(regra.get("player") or "").strip()
    atual_id = int(aprendizado.get("chamado_id") or 0)
    ars = [int(x) for x in regra.get("aberturas_relacionamento", []) or []]
    anteriores = [int(x) for x in regra.get("inclusoes_anteriores", []) or []]
    complementares = [int(x) for x in regra.get("fontes_complementares", []) or []]
    ids = list(dict.fromkeys(ars + anteriores + complementares + ([atual_id] if atual_id else [])))

    fontes, erros = [], []
    for iid in ids:
        try:
            fontes.append(buscar_issue_contexto(iid, force=force))
        except Exception as exc:
            erros.append({"id": iid, "erro": str(exc)})

    # Apenas inclusões históricas votam na recorrência do procedimento.
    # AR e faltas enriquecem contexto; o chamado atual fornece variáveis, mas não vota.
    hist = [i for i in fontes if int(i.get("id") or 0) in anteriores]
    extracao = _recorrencia_eventos(hist)
    # A thread do chamado atual pode ser um caso-âncora completo. Ela confirma
    # operacionalmente o canal, mas não substitui a recorrência histórica para
    # homologação automática da regra.
    threads = {int(i.get("id") or 0): _extrair_thread(i) for i in fontes}
    thread_atual = threads.get(atual_id, {})
    recorrentes = [x["valor"] for x in extracao["destinatarios"] if x.get("confirmado")]
    confirmados_thread = list(thread_atual.get("destinatarios_confirmados_thread") or [])
    destinatarios_operacionais = list(dict.fromkeys(recorrentes + confirmados_thread))
    todos_emails = sorted(set(e for i in fontes for e in _emails(i)), key=str.lower)
    constantes = _inferir_constantes(hist)
    # v3.28.16: recorrência semântica de ações complementa a comparação literal de linhas.
    for x in extracao["acoes_recorrentes"]:
        if x["valor"] not in constantes: constantes.append(x["valor"])
    constantes = constantes[:12]
    variaveis = _inferir_variaveis(fontes)
    fontes_parciais = sorted(int(i.get("id") or 0) for i in fontes if _fonte_parcial(i) and i.get("id"))
    sinais = _sinais_semanticos(hist, destinatarios_operacionais, constantes)
    sinais["padrao_assunto"] = any(x.get("confirmado") for x in extracao["assuntos"]) or sinais["padrao_assunto"]
    sinais["evidencia_conclusao"] = bool(extracao["evidencias_sucesso"]) or bool(thread_atual.get("ciclo_completo"))
    if thread_atual.get("ciclo_completo"):
        sinais["estrutura_mensagem"] = True
        sinais["padrao_assunto"] = sinais["padrao_assunto"] or any(m.get("assunto") for m in thread_atual.get("mensagens",[]) if m.get("estado") == "SOLICITADO")

    # v3.28.15: completude mede procedimento operacional, não apenas quantidade de fontes.
    pesos = {"destinatario_recorrente": 25, "padrao_assunto": 15, "estrutura_mensagem": 25,
             "campos_operacionais": 15, "evidencia_conclusao": 20}
    completude = sum(pesos[k] for k, ok in sinais.items() if ok)
    bloqueios = []
    if len(anteriores) < 2: bloqueios.append("HISTORICO_INSUFICIENTE")
    if not constantes: bloqueios.append("SEM_PROCEDIMENTO_RECORRENTE")
    if fontes_parciais or erros: bloqueios.append("FONTES_PENDENTES_ENRIQUECIMENTO")
    if not destinatarios_operacionais: bloqueios.append("DESTINATARIO_NAO_CONFIRMADO")
    elif not recorrentes: bloqueios.append("DESTINATARIO_CONFIRMADO_APENAS_NO_CASO_ANCORA")
    if not sinais["evidencia_conclusao"]: bloqueios.append("EVIDENCIA_CONCLUSAO_NAO_CONFIRMADA")

    pronto = completude >= 70 and len(anteriores) >= 2 and bool(constantes) and bool(recorrentes) and not fontes_parciais and not erros
    estado = "PRONTA_PARA_REVISAO" if pronto else "APRENDIZADO_INCOMPLETO"
    resultado = {
        "regra_id": regra_id, "player": player, "operacao": "INCLUSAO", "estado": estado,
        "completude": min(completude, 100), "canal": "EMAIL" if todos_emails else "NAO_IDENTIFICADO",
        "fontes": {"bp": aprendizado.get("blueprint_id"), "ar": ars, "historicos": anteriores, "complementares": complementares, "atual": atual_id},
        "destinatarios_recorrentes": recorrentes, "destinatarios_operacionais": destinatarios_operacionais, "emails_encontrados": todos_emails,
        "constantes": constantes, "variaveis": variaveis, "sinais_semanticos": sinais,
        "extracao_operacional": extracao, "threads_operacionais": threads, "thread_ancora": thread_atual,
        "fontes_parciais": fontes_parciais, "bloqueios": bloqueios, "erros": erros,
        "pode_homologar": pronto, "pode_executar": False, "aprendido_em": agora_brasil_iso(),
    }
    salvar_aprendizado(resultado)
    print(f"[EDNNA] Aprendizado | regra={regra_id} | fontes={ids}", flush=True)
    print(f"[EDNNA] Linha do tempo operacional | historicos={anteriores} | solicitacoes={sum(1 for xs in extracao['linha_tempo'].values() for x in xs if x['tipo']=='SOLICITACAO_EXTERNA')} | retornos={sum(1 for xs in extracao['linha_tempo'].values() for x in xs if x['tipo']=='RETORNO_PLAYER')} | acoes_internas={sum(1 for xs in extracao['linha_tempo'].values() for x in xs if x['tipo']=='ACAO_INTERNA')}", flush=True)
    print(f"[EDNNA] Thread operacional | chamado={atual_id} | estados={thread_atual.get('estados', [])} | protocolos={thread_atual.get('protocolos', [])} | prazo_horas={thread_atual.get('prazos_horas', [])} | destinatarios={confirmados_thread} | ciclo_completo={bool(thread_atual.get('ciclo_completo'))}", flush=True)
    print(f"[EDNNA] Extrator operacional | destinatarios_recorrentes={len(recorrentes)} | destinatarios_ancora={len(confirmados_thread)} | acoes_recorrentes={len(extracao['acoes_recorrentes'])} | evidencias_sucesso={len(extracao['evidencias_sucesso'])}", flush=True)
    print(f"[EDNNA] Procedimento semântico | constantes={len(constantes)} | sinais={sum(sinais.values())}/{len(sinais)} | completude={resultado['completude']}% | parciais={fontes_parciais}", flush=True)
    print(f"[EDNNA] Regra | {regra_id} | {estado} | bloqueios={bloqueios}", flush=True)
    return resultado


def salvar_aprendizado(resultado: dict) -> None:
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        conn.execute("""INSERT INTO aprendizados_operacionais
        (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
        VALUES (?,?,?,?,?,?,?) ON CONFLICT(regra_id) DO UPDATE SET
        player=excluded.player,operacao=excluded.operacao,estado=excluded.estado,
        completude=excluded.completude,payload_json=excluded.payload_json,atualizado_em=excluded.atualizado_em""",
        (resultado["regra_id"], resultado["player"], resultado["operacao"], resultado["estado"], resultado["completude"], json.dumps(resultado, ensure_ascii=False), resultado["aprendido_em"]))


def obter_aprendizado(regra_id: str) -> dict | None:
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT payload_json FROM aprendizados_operacionais WHERE regra_id=?", (regra_id,)).fetchone()
    return json.loads(row["payload_json"]) if row else None


def reprocessar_aprendizados_incompletos(ids_atualizados: list[int] | None = None) -> dict:
    """Reavalia regras incompletas após o worker enriquecer suas fontes."""
    atualizados = {int(x) for x in (ids_atualizados or [])}
    with conectar() as conn:
        rows = conn.execute("SELECT payload_json FROM aprendizados_operacionais WHERE estado='APRENDIZADO_INCOMPLETO'").fetchall()
    reprocessadas, erros = [], []
    for row in rows:
        try:
            antigo = json.loads(row["payload_json"])
            f = antigo.get("fontes") or {}
            ids_regra = set(int(x) for x in ((f.get("ar") or []) + (f.get("historicos") or []) + ([f.get("atual")] if f.get("atual") else [])))
            if atualizados and not (ids_regra & atualizados):
                continue
            aprendizado = {"chamado_id": f.get("atual"), "blueprint_id": f.get("bp")}
            regra = {"regra_sugerida": antigo.get("regra_id"), "player": antigo.get("player"),
                     "aberturas_relacionamento": f.get("ar") or [], "inclusoes_anteriores": f.get("historicos") or [], "fontes_complementares": f.get("complementares") or []}
            novo = aprender_procedimento_inclusao(aprendizado, regra, force=False)
            reprocessadas.append({"regra": novo.get("regra_id"), "estado": novo.get("estado")})
        except Exception as exc:
            erros.append(str(exc))
    if reprocessadas:
        print(f"[EDNNA] Aprendizado automático | reprocessadas={reprocessadas}", flush=True)
    return {"reprocessadas": reprocessadas, "erros": erros}
