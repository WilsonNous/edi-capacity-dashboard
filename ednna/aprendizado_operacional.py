from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from ednna.armazenamento import conectar, agora_brasil_iso
from ednna.contexto_relacionamentos import buscar_issue_contexto
from ednna.workflows_inclusao import obter_workflow

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

# v3.28.19 — corpus operacional unificado.
def _papel_email(email: str) -> str:
    e = str(email or "").strip().lower()
    if not e:
        return "NAO_IDENTIFICADO"
    return "INTERNO_NETUNNA" if e.endswith("@netunna.com.br") else "EXTERNO_PLAYER"

def _corpus_operacional(fontes: list[dict], atual_id: int, historicos_ids: list[int]) -> dict:
    """Unifica caso-âncora e histórico sem misturar seus pesos de evidência.

    O corpus serve para leitura/aprendizado. A homologação continua dependendo
    de recorrência histórica; um caso-âncora completo enriquece, mas não vota
    sozinho como recorrência.
    """
    hist_ids = {int(x) for x in (historicos_ids or [])}
    casos=[]; participantes={}; externos=set(); internos=set()
    ciclos_hist=0; ciclos_ancora=0
    estados_hist=Counter(); estados_ancora=Counter()
    destinos_hist=Counter(); destinos_ancora=Counter()
    protocolos=set(); prazos=set()
    for issue in fontes:
        iid=int(issue.get("id") or 0)
        thread=_extrair_thread(issue)
        papel_caso = "CASO_ANCORA" if iid == int(atual_id or 0) else ("HISTORICO" if iid in hist_ids else "CONTEXTO_COMPLEMENTAR")
        if thread.get("ciclo_completo"):
            if papel_caso == "CASO_ANCORA": ciclos_ancora += 1
            elif papel_caso == "HISTORICO": ciclos_hist += 1
        for estado in thread.get("estados", []) or []:
            (estados_ancora if papel_caso == "CASO_ANCORA" else estados_hist)[estado] += 1
        for e in thread.get("destinatarios_confirmados_thread", []) or []:
            (destinos_ancora if papel_caso == "CASO_ANCORA" else destinos_hist)[e] += 1
        protocolos.update(thread.get("protocolos", []) or [])
        prazos.update(thread.get("prazos_horas", []) or [])
        for m in thread.get("mensagens", []) or []:
            emails=[]
            if m.get("remetente"): emails.append(m["remetente"])
            emails += list(m.get("para") or []) + list(m.get("cc") or [])
            for e in emails:
                e=str(e).lower(); papel=_papel_email(e)
                participantes[e]=papel
                (internos if papel == "INTERNO_NETUNNA" else externos).add(e)
        casos.append({"chamado_id":iid,"papel":papel_caso,"thread":thread})
    return {
        "casos":casos,
        "participantes":participantes,
        "participantes_internos":sorted(internos),
        "participantes_externos":sorted(externos),
        "destinatarios_player_historico":[{"email":e,"ocorrencias":n} for e,n in destinos_hist.most_common()],
        "destinatarios_player_ancora":[{"email":e,"ocorrencias":n} for e,n in destinos_ancora.most_common()],
        "evidencia_historica":{"casos":len([c for c in casos if c["papel"]=="HISTORICO"]),"ciclos_completos":ciclos_hist,"estados":dict(estados_hist)},
        "evidencia_caso_ancora":{"casos":len([c for c in casos if c["papel"]=="CASO_ANCORA"]),"ciclos_completos":ciclos_ancora,"estados":dict(estados_ancora)},
        "protocolos":sorted(protocolos),"prazos_horas":sorted(prazos),
    }

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
    corpus = _corpus_operacional(fontes, atual_id, anteriores)
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

    # v3.28.25 — fonte parcial é condição transitória, não conclusão do aprendizado.
    # A regra fica aguardando o worker completar o corpus e é reavaliada automaticamente.
    aguardando_enriquecimento = bool(fontes_parciais or erros)
    pronto = completude >= 70 and len(anteriores) >= 2 and bool(constantes) and bool(recorrentes) and not aguardando_enriquecimento
    if aguardando_enriquecimento:
        estado = "AGUARDANDO_ENRIQUECIMENTO"
    else:
        estado = "PRONTA_PARA_REVISAO" if pronto else "APRENDIZADO_INCOMPLETO"
    resultado = {
        "regra_id": regra_id, "player": player, "operacao": "INCLUSAO", "estado": estado,
        "completude": min(completude, 100), "canal": "EMAIL" if todos_emails else "NAO_IDENTIFICADO",
        "fontes": {"bp": aprendizado.get("blueprint_id"), "ar": ars, "historicos": anteriores, "complementares": complementares, "atual": atual_id},
        "destinatarios_recorrentes": recorrentes, "destinatarios_operacionais": destinatarios_operacionais, "emails_encontrados": todos_emails,
        "constantes": constantes, "variaveis": variaveis, "sinais_semanticos": sinais,
        "extracao_operacional": extracao, "threads_operacionais": threads, "thread_ancora": thread_atual,
        "corpus_operacional": corpus,
        "fontes_parciais": fontes_parciais, "bloqueios": bloqueios, "erros": erros,
        "pode_homologar": pronto, "pode_executar": False, "aprendido_em": agora_brasil_iso(),
    }
    salvar_aprendizado(resultado)
    print(f"[EDNNA] Aprendizado | regra={regra_id} | fontes={ids}", flush=True)
    print(f"[EDNNA] Linha do tempo operacional | historicos={anteriores} | solicitacoes={sum(1 for xs in extracao['linha_tempo'].values() for x in xs if x['tipo']=='SOLICITACAO_EXTERNA')} | retornos={sum(1 for xs in extracao['linha_tempo'].values() for x in xs if x['tipo']=='RETORNO_PLAYER')} | acoes_internas={sum(1 for xs in extracao['linha_tempo'].values() for x in xs if x['tipo']=='ACAO_INTERNA')}", flush=True)
    print(f"[EDNNA] Thread operacional | chamado={atual_id} | estados={thread_atual.get('estados', [])} | protocolos={thread_atual.get('protocolos', [])} | prazo_horas={thread_atual.get('prazos_horas', [])} | destinatarios={confirmados_thread} | ciclo_completo={bool(thread_atual.get('ciclo_completo'))}", flush=True)
    print(f"[EDNNA] Corpus operacional | casos={len(corpus.get('casos', []))} | historicos={corpus.get('evidencia_historica', {}).get('casos', 0)} | ancora={corpus.get('evidencia_caso_ancora', {}).get('casos', 0)} | externos={len(corpus.get('participantes_externos', []))} | internos={len(corpus.get('participantes_internos', []))}", flush=True)
    print(f"[EDNNA] Evidência separada | historico_ciclos={corpus.get('evidencia_historica', {}).get('ciclos_completos', 0)} | ancora_ciclos={corpus.get('evidencia_caso_ancora', {}).get('ciclos_completos', 0)} | destinatarios_hist={corpus.get('destinatarios_player_historico', [])} | destinatarios_ancora={corpus.get('destinatarios_player_ancora', [])}", flush=True)
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
        rows = conn.execute("SELECT payload_json FROM aprendizados_operacionais WHERE estado IN ('APRENDIZADO_INCOMPLETO','AGUARDANDO_ENRIQUECIMENTO')").fetchall()
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


# ============================================================
# v3.28.21 — REVISÃO ASSISTIDA E HOMOLOGAÇÃO HUMANA
# ============================================================

def _garantir_tabela_revisoes() -> None:
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS revisoes_regras_operacionais (
            regra_id TEXT PRIMARY KEY,
            estado TEXT NOT NULL DEFAULT 'PENDENTE_REVISAO',
            destinatario_confirmado TEXT,
            observacoes TEXT,
            revisado_por TEXT,
            revisado_em TEXT,
            homologado_em TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            atualizado_em TEXT NOT NULL
        )""")


def obter_revisao(regra_id: str) -> dict:
    _garantir_tabela_revisoes()
    with conectar() as conn:
        row = conn.execute(
            "SELECT * FROM revisoes_regras_operacionais WHERE regra_id=?",
            (str(regra_id),),
        ).fetchone()
    if not row:
        return {"regra_id": str(regra_id), "estado": "PENDENTE_REVISAO"}
    d = dict(row)
    try:
        d["payload"] = json.loads(d.get("payload_json") or "{}")
    except Exception:
        d["payload"] = {}
    return d


def salvar_revisao_assistida(
    regra_id: str, *, destinatario_confirmado: str = "", observacoes: str = "",
    revisado_por: str = "OPERADOR"
) -> dict:
    """Registra confirmação humana sem homologar e sem executar a regra."""
    _garantir_tabela_revisoes()
    aprendido = obter_aprendizado(regra_id) or {}
    email = str(destinatario_confirmado or "").strip().lower()
    if email and not _EMAIL_RE.fullmatch(email):
        raise ValueError("Destinatário informado não possui formato de e-mail válido.")
    payload = {
        "regra_id": regra_id,
        "player": aprendido.get("player"),
        "operacao": aprendido.get("operacao"),
        "completude_aprendizado": aprendido.get("completude"),
        "destinatario_confirmado": email,
        "observacoes": str(observacoes or "").strip(),
        "evidencias": aprendido.get("fontes") or {},
        "variaveis": aprendido.get("variaveis") or [],
        "constantes": aprendido.get("constantes") or [],
        "workflow": obter_workflow(aprendido.get("player")),
    }
    agora = agora_brasil_iso()
    with conectar() as conn:
        conn.execute("""INSERT INTO revisoes_regras_operacionais
        (regra_id,estado,destinatario_confirmado,observacoes,revisado_por,revisado_em,payload_json,atualizado_em)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(regra_id) DO UPDATE SET
          estado='REVISADA', destinatario_confirmado=excluded.destinatario_confirmado,
          observacoes=excluded.observacoes, revisado_por=excluded.revisado_por,
          revisado_em=excluded.revisado_em, payload_json=excluded.payload_json,
          atualizado_em=excluded.atualizado_em""",
        (regra_id,"REVISADA",email,str(observacoes or "").strip(),revisado_por,agora,
         json.dumps(payload,ensure_ascii=False),agora))
    return obter_revisao(regra_id)


def homologar_regra_assistida(regra_id: str, *, revisado_por: str = "OPERADOR") -> dict:
    """Homologa somente após revisão humana explícita. Não dispara ação externa."""
    revisao = obter_revisao(regra_id)
    if revisao.get("estado") not in {"REVISADA", "HOMOLOGADA"}:
        raise ValueError("A regra precisa ser revisada antes da homologação.")
    aprendido = obter_aprendizado(regra_id) or {}
    destinatario = str(revisao.get("destinatario_confirmado") or "").strip()
    workflow = obter_workflow(aprendido.get("player"))
    # E-mail exige destinatário; API, abertura de chamado, banco e workflows
    # compostos podem ser homologados como conhecimento mesmo sem e-mail.
    if "EMAIL" in str(workflow.get("canal") or "") and workflow.get("canal") == "EMAIL":
        if not destinatario and not (aprendido.get("destinatarios_recorrentes") or []):
            raise ValueError("Confirme ao menos um destinatário para este workflow por e-mail.")
    agora = agora_brasil_iso()
    with conectar() as conn:
        conn.execute("""UPDATE revisoes_regras_operacionais
            SET estado='HOMOLOGADA', revisado_por=?, homologado_em=?, atualizado_em=?
            WHERE regra_id=?""", (revisado_por, agora, agora, regra_id))
    print(f"[EDNNA] Homologação humana | regra={regra_id} | workflow={workflow.get('workflow')} | canal={workflow.get('canal')} | prontidao={workflow.get('prontidao')} | execução_automatica=False", flush=True)
    return obter_revisao(regra_id)


# ============================================================
# v3.28.22 — PATRIMÔNIO DE REGRAS HOMOLOGADAS
# ============================================================

def listar_regras_operacionais() -> list[dict]:
    """Inventário persistente do conhecimento de inclusão da EDNNA.

    A homologação humana prevalece sobre o estado de aprendizado: uma regra
    homologada deixa de voltar à fila de descoberta e passa a ser patrimônio
    operacional consultável. Nenhuma execução externa é feita aqui.
    """
    _garantir_tabela_revisoes()
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        rows = conn.execute("""
            SELECT a.regra_id,a.player,a.operacao,a.estado,a.completude,a.payload_json,a.atualizado_em,
                   r.estado AS estado_revisao,r.destinatario_confirmado,r.observacoes,
                   r.revisado_em,r.homologado_em
              FROM aprendizados_operacionais a
              LEFT JOIN revisoes_regras_operacionais r ON r.regra_id=a.regra_id
             WHERE a.operacao='INCLUSAO'
             ORDER BY a.player,a.regra_id
        """).fetchall()
    saida=[]
    for row in rows:
        d=dict(row)
        try: payload=json.loads(d.pop('payload_json') or '{}')
        except Exception: payload={}
        d['payload']=payload
        d['estado_operacional']='HOMOLOGADA' if d.get('estado_revisao')=='HOMOLOGADA' else d.get('estado')
        d['workflow']=obter_workflow(d.get('player'))
        d['autorizacao_motor']=obter_autorizacao_motor(d.get('regra_id'))
        d['modo_motor']=d['autorizacao_motor'].get('modo','BLOQUEADA')
        saida.append(d)
    return saida


def obter_regra_homologada(player: str, operacao: str = 'INCLUSAO') -> dict | None:
    alvo=str(player or '').strip().upper()
    for regra in listar_regras_operacionais():
        if str(regra.get('player') or '').strip().upper()==alvo and str(regra.get('operacao') or '').upper()==str(operacao).upper() and regra.get('estado_revisao')=='HOMOLOGADA':
            return regra
    return None


# ============================================================
# v3.28.35 — AUTORIZAÇÃO OPERACIONAL DO MOTOR
# ============================================================

def _garantir_tabela_autorizacoes_motor() -> None:
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS autorizacoes_motor (
            regra_id TEXT PRIMARY KEY,
            modo TEXT NOT NULL DEFAULT 'BLOQUEADA',
            autorizado_por TEXT,
            autorizado_em TEXT,
            observacoes TEXT,
            atualizado_em TEXT NOT NULL
        )""")


def obter_autorizacao_motor(regra_id: str) -> dict:
    _garantir_tabela_autorizacoes_motor()
    with conectar() as conn:
        row = conn.execute("SELECT * FROM autorizacoes_motor WHERE regra_id=?", (str(regra_id),)).fetchone()
    return dict(row) if row else {"regra_id": str(regra_id), "modo": "BLOQUEADA"}


def autorizar_regra_motor(regra_id: str, *, modo: str = "ASSISTIDA", autorizado_por: str = "OPERADOR_EDNNA", observacoes: str = "") -> dict:
    modo = str(modo or '').upper().strip()
    if modo not in {"ASSISTIDA", "AUTOMATICA", "BLOQUEADA"}:
        raise ValueError("Modo operacional inválido.")
    revisao = obter_revisao(regra_id)
    if revisao.get("estado") != "HOMOLOGADA":
        raise ValueError("Somente regra homologada pode ser autorizada para operação.")
    aprendido = obter_aprendizado(regra_id) or {}
    workflow = obter_workflow(aprendido.get("player"))
    if modo in {"ASSISTIDA", "AUTOMATICA"} and workflow.get("prontidao") != "ASSISTIDA_DISPONIVEL":
        raise ValueError("O executor deste workflow ainda não está disponível para operação.")
    agora = agora_brasil_iso()
    with conectar() as conn:
        conn.execute("""INSERT INTO autorizacoes_motor
            (regra_id,modo,autorizado_por,autorizado_em,observacoes,atualizado_em)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(regra_id) DO UPDATE SET modo=excluded.modo,
              autorizado_por=excluded.autorizado_por, autorizado_em=excluded.autorizado_em,
              observacoes=excluded.observacoes, atualizado_em=excluded.atualizado_em""",
            (regra_id, modo, autorizado_por, agora, str(observacoes or ''), agora))
    print(f"[EDNNA] Motor | regra={regra_id} | autorização={modo} | workflow={workflow.get('workflow')}", flush=True)
    return obter_autorizacao_motor(regra_id)


def garantir_greencard_pronta() -> dict:
    """v3.31.1 — deixa GREENCARD pronta em modo ASSISTIDA.

    Migração idempotente e específica, solicitada pela operação. Não dispara
    e-mail nem executa o workflow. Apenas garante o patrimônio da regra, sua
    homologação e a autorização assistida. A promoção para AUTOMATICA continua
    sendo uma decisão explícita posterior, pois o fluxo envolve documento
    assinado e validação humana.
    """
    regra_id = "INCLUSAO-GREENCARD-001"
    agora = agora_brasil_iso()
    workflow = obter_workflow("GREENCARD")
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT regra_id FROM aprendizados_operacionais WHERE upper(player)='GREENCARD' AND operacao='INCLUSAO' ORDER BY atualizado_em DESC LIMIT 1").fetchone()
        if row:
            regra_id = str(row["regra_id"])
        else:
            payload = {
                "regra_id": regra_id, "player": "GREENCARD", "operacao": "INCLUSAO",
                "estado": "REGRA_PRONTA", "completude": 100,
                "procedimento_confirmado": True, "workflow": workflow,
                "variaveis": ["cliente","cnpjs","participantes","estabelecimento"],
                "fontes": {"autoridade": "PROCEDIMENTO_HOMOLOGADO_OPERACAO"},
                "aprendido_em": agora,
            }
            conn.execute("""INSERT INTO aprendizados_operacionais
                (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
                VALUES (?,?,?,?,?,?,?)""",
                (regra_id,"GREENCARD","INCLUSAO","REGRA_PRONTA",100,json.dumps(payload,ensure_ascii=False),agora))
    rev = obter_revisao(regra_id)
    if rev.get("estado") != "HOMOLOGADA":
        salvar_revisao_assistida(regra_id, observacoes="Procedimento Greencard homologado: preencher formulário com Base de Conhecimento, enviar ao cliente para complemento/assinatura, validar retorno, encaminhar à Greencard, acompanhar arquivos e registrar movimentação no BP principal.", revisado_por="MIGRACAO_EDNNA_3_31_1")
        homologar_regra_assistida(regra_id, revisado_por="MIGRACAO_EDNNA_3_31_1")
    aut = obter_autorizacao_motor(regra_id)
    if str(aut.get("modo") or "BLOQUEADA").upper() == "BLOQUEADA":
        autorizar_regra_motor(regra_id, modo="ASSISTIDA", autorizado_por="MIGRACAO_EDNNA_3_31_1", observacoes="Greencard pronta para operação assistida; promoção automática permanece decisão explícita.")
    return {"regra_id": regra_id, "revisao": obter_revisao(regra_id), "autorizacao": obter_autorizacao_motor(regra_id)}
