from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

from ednna.armazenamento import (
    listar_classificacoes_demandas,
    obter_classificacao_demanda,
    salvar_classificacao_demanda,
    salvar_metadado,
    agora_brasil_iso,
)
from ednna.sincronizador import normalizar_marca_alteracao

CATALOGO_PATH = Path(__file__).with_name("catalogo_automacoes.json")

PADROES = {
    "RELACIONAMENTO_CREDENCIAMENTO": [
        (r"\bcredenciamento\b", 5), (r"\bcredenciar\b", 5),
        (r"\bafiliação\b|\bafiliacao\b", 4), (r"\brelacionamento\b", 4),
        (r"\bhabilita(?:ção|cao)\b", 3), (r"\badquirente\b", 1),
    ],
    "INCLUSAO_ESTABELECIMENTO": [
        (r"\binclus[aã]o\b.*\bestabelecimento\b", 6),
        (r"\badicionar\b.*\bestabelecimento\b", 5),
        (r"\bnovo estabelecimento\b", 5), (r"\bincluir\b.*\bloja\b", 4),
        (r"\binclus[aã]o\b.*\bloja\b", 4), (r"\bestabelecimento\b", 1),
    ],
    "FALTA_ARQUIVO": [
        (r"\bfalta\b.*\barquivo\b", 6),
        (r"\barquivo\b.*\bn[aã]o\b.*\b(?:recebido|chegou|dispon[ií]vel)\b", 6),
        (r"\bn[aã]o recebemos\b", 5), (r"\bn[aã]o chegou\b", 5),
        (r"\baus[eê]ncia\b.*\barquivo\b", 5), (r"\barquivo faltante\b", 6),
        (r"\bfaltante\b", 3),
    ],
    "REPROCESSAMENTO": [
        (r"\breprocess", 6), (r"\bprocessar novamente\b", 5),
        (r"\bprocessamento novamente\b", 5), (r"\breenvio\b", 3),
        (r"\breenviar\b", 3),
    ],
    "ALTERACAO_CADASTRAL": [
        (r"\baltera(?:ç[aã]o|cao)\b.*\bcadastr", 6),
        (r"\batualiza(?:ç[aã]o|cao)\b.*\bcadastr", 6),
        (r"\balterar\b.*\b(?:cnpj|filia(?:ç[aã]o|cao)|estabelecimento|loja)\b", 4),
        (r"\bcadastro\b", 2),
    ],
    "DUVIDA_ORIENTACAO": [
        (r"\bd[uú]vida\b", 5), (r"\borienta(?:ç[aã]o|cao)\b", 5),
        (r"\bcomo\b.*\b(?:fazer|proceder|funciona)\b", 3),
        (r"\besclarecimento\b", 4),
    ],
}

TIPO_OFICIAL = [
    (r"abertura\s+relacionamento|credenciamento|relacionamento", "RELACIONAMENTO_CREDENCIAMENTO"),
    (r"inclus[aã]o.*estabelecimento|inclus[aã]o.*loja", "INCLUSAO_ESTABELECIMENTO"),
    (r"falta.*arquivo|arquivo.*falt", "FALTA_ARQUIVO"),
    (r"reprocess", "REPROCESSAMENTO"),
    (r"altera(?:ç[aã]o|cao).*cadastr", "ALTERACAO_CADASTRAL"),
    (r"d[uú]vida|orienta(?:ç[aã]o|cao)", "DUVIDA_ORIENTACAO"),
]

SUBTIPOS = [
    ("ARQUIVO_CORROMPIDO", [r"corrompid", r"arquivo\s+inv[aá]lid", r"arquivo\s+danific"]),
    ("FALTA_REGISTRO", [r"falta\s+(?:de\s+)?registro", r"registro\s+falt", r"movimento\s+falt", r"transa(?:ç[aã]o|cao).*falt"]),
    ("ARQUIVO_NAO_RECEBIDO", [r"falta.*arquivo", r"arquivo.*n[aã]o.*(?:recebido|chegou|dispon[ií]vel)", r"n[aã]o recebemos", r"n[aã]o chegou", r"aus[eê]ncia.*arquivo"]),
    ("RELACIONAMENTO_PENDENTE", [r"relacionamento", r"credenciamento", r"credenciar", r"habilita(?:ç[aã]o|cao)", r"afiliação|afiliacao"]),
    ("INCLUSAO_ESTABELECIMENTO", [r"inclus[aã]o.*estabelecimento", r"novo estabelecimento", r"incluir.*loja"]),
    ("REPROCESSAMENTO_SOLICITADO", [r"reprocess", r"processar novamente"]),
    ("ALTERACAO_CADASTRAL", [r"altera(?:ç[aã]o|cao).*cadastr", r"atualiza(?:ç[aã]o|cao).*cadastr"]),
    ("DUVIDA_ORIENTACAO", [r"d[uú]vida", r"orienta(?:ç[aã]o|cao)", r"esclarecimento"]),
]

# v3.13 começa conservadora: nenhuma origem é considerada homologada implicitamente.
ORIGENS_HOMOLOGADAS: set[str] = set()


def _texto(valor: Any) -> str:
    if valor is None: return ""
    try:
        if pd.isna(valor): return ""
    except Exception: pass
    return str(valor).strip()


def _normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def carregar_catalogo() -> dict:
    try:
        return json.loads(CATALOGO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"versao": "desconhecida", "modo": "OBSERVACAO", "regras": []}


def _mapa_regras() -> dict[str, dict]:
    return {item.get("intencao", ""): item for item in carregar_catalogo().get("regras", []) if item.get("intencao")}


def _intencao_por_tipo(tipo: str) -> str:
    for regex, intencao in TIPO_OFICIAL:
        if re.search(regex, tipo, flags=re.IGNORECASE): return intencao
    return ""


def _extrair_subtipo(texto: str, intencao: str) -> str:
    for subtipo, padroes in SUBTIPOS:
        if any(re.search(p, texto, flags=re.IGNORECASE) for p in padroes):
            # Arquivo corrompido/falta registro prevalecem como natureza operacional.
            return subtipo
    return {
        "RELACIONAMENTO_CREDENCIAMENTO": "RELACIONAMENTO_PENDENTE",
        "FALTA_ARQUIVO": "ARQUIVO_NAO_RECEBIDO",
        "INCLUSAO_ESTABELECIMENTO": "INCLUSAO_ESTABELECIMENTO",
        "REPROCESSAMENTO": "REPROCESSAMENTO_SOLICITADO",
        "ALTERACAO_CADASTRAL": "ALTERACAO_CADASTRAL",
        "DUVIDA_ORIENTACAO": "DUVIDA_ORIENTACAO",
    }.get(intencao, "NAO_IDENTIFICADO")


def _extrair_referencia(texto: str) -> str:
    padroes = [
        r"\bdesde\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"\b(?:dia|data|refer[eê]ncia|referencia)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
    ]
    for p in padroes:
        m = re.search(p, texto, flags=re.IGNORECASE)
        if m: return m.group(1)
    return ""


def _origem_operacional(linha: pd.Series | dict, texto: str) -> str:
    origem = _texto(linha.get("Origem"))
    if origem: return origem
    # fallback simples para siglas/nome em assunto quando Origem não veio do Redmine
    conhecidos = ["SODEXO", "SICREDI", "REDE", "CIELO", "STONE", "VR", "VERO", "CABAL", "MGCARD", "GETNET", "ALELO", "TICKET"]
    texto_up = _sem_acentos(texto).upper()
    for nome in conhecidos:
        if re.search(rf"\b{re.escape(nome)}\b", texto_up): return nome
    return ""


def _procedimento_homologado(origem: str, regra: dict) -> bool:
    if bool(regra.get("homologada", False)) and origem and origem.upper() in ORIGENS_HOMOLOGADAS:
        return True
    return False


def classificar_linha(linha: pd.Series | dict) -> dict:
    get = linha.get
    campos = {"assunto": _texto(get("Assunto")), "descricao": _texto(get("Descrição")), "tipo": _texto(get("Tipo")), "origem": _texto(get("Origem")), "cliente": _texto(get("Clientes"))}
    texto = _normalizar_texto(" | ".join(v for v in campos.values() if v))

    pontuacoes, evidencias = {}, {}
    for intencao, padroes in PADROES.items():
        pontos, hits = 0, []
        for regex, peso in padroes:
            if re.search(regex, texto, flags=re.IGNORECASE):
                pontos += peso; hits.append(regex)
        if pontos: pontuacoes[intencao], evidencias[intencao] = pontos, hits

    tipo_oficial = _intencao_por_tipo(campos["tipo"])
    ranking = sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)
    intencao_texto = ranking[0][0] if ranking else ""
    melhor_pontuacao = ranking[0][1] if ranking else 0
    segundo = ranking[1][1] if len(ranking) > 1 else 0

    # Precedência v3.13: o Tipo oficial do Redmine ganha da inferência textual.
    intencao = tipo_oficial or (intencao_texto if melhor_pontuacao >= 4 else "NAO_CLASSIFICADO")
    conflito = bool(tipo_oficial and intencao_texto and tipo_oficial != intencao_texto and melhor_pontuacao >= 4)
    sinal_secundario = intencao_texto if conflito else ""

    confianca = 0.0 if intencao == "NAO_CLASSIFICADO" else min(0.99, 0.62 + (0.12 if tipo_oficial else 0) + melhor_pontuacao*0.04 + max(0, melhor_pontuacao-segundo)*0.02)
    regra = _mapa_regras().get(intencao, {})
    subtipo = _extrair_subtipo(texto, intencao)
    origem = _origem_operacional(linha, texto)
    referencia = _extrair_referencia(texto)

    bloqueio_natureza = subtipo in {"ARQUIVO_CORROMPIDO", "FALTA_REGISTRO"}
    homologado = _procedimento_homologado(origem, regra)
    dados_suficientes = bool(origem and (referencia or intencao not in {"FALTA_ARQUIVO", "REPROCESSAMENTO"}))
    automatizavel = bool(intencao != "NAO_CLASSIFICADO" and not conflito and not bloqueio_natureza and homologado and dados_suficientes)

    if intencao == "NAO_CLASSIFICADO": motivo = "Intenção operacional não reconhecida com segurança."
    elif conflito: motivo = f"Conflito entre o Tipo oficial ({tipo_oficial}) e o texto do chamado ({intencao_texto})."
    elif bloqueio_natureza: motivo = f"Subtipo {subtipo} exige tratamento específico e não pode usar a rotina de arquivo ausente."
    elif not origem: motivo = "Origem operacional não identificada."
    elif not homologado: motivo = f"Procedimento da origem {origem} ainda não homologado."
    elif not dados_suficientes: motivo = "Dados insuficientes para uma automação segura."
    else: motivo = "Procedimento homologado e dados mínimos identificados."

    return {
        "intencao": intencao, "confianca": round(confianca, 2), "regra_candidata": regra.get("id", ""),
        "acao_sugerida": regra.get("acao_sugerida", "Encaminhar para análise humana."), "executavel": False,
        "evidencias": evidencias.get(intencao_texto or intencao, []), "subtipo": subtipo,
        "origem_operacional": origem, "referencia": referencia, "conflito": conflito,
        "sinal_secundario": sinal_secundario, "automatizavel": automatizavel, "motivo": motivo,
    }


def classificacao_precisa_atualizar(chamado_id: int, alterado_em: str) -> bool:
    atual = obter_classificacao_demanda(chamado_id)
    if atual is None: return True
    return normalizar_marca_alteracao(atual.get("alterado_em_redmine")) != normalizar_marca_alteracao(alterado_em)


def classificar_dataframe(frame: pd.DataFrame) -> dict:
    resultado = {"recebidos":0,"classificados":0,"reaproveitados":0,"nao_classificados":0,"erros":0}
    if frame is None or not isinstance(frame,pd.DataFrame) or frame.empty or "#" not in frame.columns: return resultado
    resultado["recebidos"] = len(frame)
    for _, row in frame.iterrows():
        try: chamado_id = int(float(row.get("#")))
        except Exception: resultado["erros"] += 1; continue
        alterado = normalizar_marca_alteracao(row.get("Alterado"))
        if not classificacao_precisa_atualizar(chamado_id, alterado): resultado["reaproveitados"] += 1; continue
        try:
            item = classificar_linha(row)
            salvar_classificacao_demanda(chamado_id=chamado_id, alterado_em_redmine=alterado, intencao=item["intencao"], confianca=item["confianca"], regra_candidata=item["regra_candidata"], acao_sugerida=item["acao_sugerida"], executavel=False, evidencias=item["evidencias"])
            resultado["classificados"] += 1
            if item["intencao"] == "NAO_CLASSIFICADO": resultado["nao_classificados"] += 1
        except Exception as exc:
            resultado["erros"] += 1; print(f"[EDNNA] Erro classificando demanda | chamado={chamado_id} | erro={exc}", flush=True)
    salvar_metadado("ultima_classificacao_demandas", agora_brasil_iso())
    print("[EDNNA] Classificação de demandas | " + " | ".join(f"{k}={v}" for k,v in resultado.items()), flush=True)
    return resultado


def enriquecer_dataframe_com_classificacoes(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or not isinstance(frame,pd.DataFrame): return pd.DataFrame()
    resultado = frame.copy()
    if resultado.empty: return resultado
    mapa = {int(item["chamado_id"]): item for item in listar_classificacoes_demandas() if item.get("chamado_id") is not None}
    dados = {k:[] for k in ["intencao","confianca","regra","acao","subtipo","origem","referencia","conflito","sinal","automatizavel","motivo"]}
    for _, row in resultado.iterrows():
        try: chamado_id=int(float(row.get("#")))
        except Exception: chamado_id=-1
        item_db=mapa.get(chamado_id) or {}
        # Campos v3.13 são derivados do snapshot atual, sem migration no SQLite.
        derivado=classificar_linha(row)
        dados["intencao"].append(derivado["intencao"] if derivado else item_db.get("intencao","NAO_CLASSIFICADO"))
        dados["confianca"].append(float(derivado.get("confianca", item_db.get("confianca",0)) or 0))
        dados["regra"].append(derivado.get("regra_candidata", item_db.get("regra_candidata","")))
        dados["acao"].append(derivado.get("acao_sugerida", item_db.get("acao_sugerida","")))
        dados["subtipo"].append(derivado["subtipo"]); dados["origem"].append(derivado["origem_operacional"])
        dados["referencia"].append(derivado["referencia"]); dados["conflito"].append("SIM" if derivado["conflito"] else "NÃO")
        dados["sinal"].append(derivado["sinal_secundario"]); dados["automatizavel"].append("SIM" if derivado["automatizavel"] else "NÃO")
        dados["motivo"].append(derivado["motivo"])
    resultado["EDNNA - Intenção"]=dados["intencao"]; resultado["EDNNA - Confiança"]=dados["confianca"]
    resultado["EDNNA - Regra"]=dados["regra"]; resultado["EDNNA - Ação sugerida"]=dados["acao"]
    resultado["EDNNA - Subtipo"]=dados["subtipo"]; resultado["EDNNA - Origem operacional"]=dados["origem"]
    resultado["EDNNA - Referência"]=dados["referencia"]; resultado["EDNNA - Conflito de classificação"]=dados["conflito"]
    resultado["EDNNA - Sinal secundário"]=dados["sinal"]; resultado["EDNNA - Automatizável"]=dados["automatizavel"]
    resultado["EDNNA - Motivo"]=dados["motivo"]
    return resultado


def calcular_prontidao_automacao(frame: pd.DataFrame) -> pd.DataFrame:
    cols=['Intenção','Chamados','Confiança média','Com regra candidata','Automatizáveis','Conflitos','Prontidão','Faixa']
    if frame is None or not isinstance(frame,pd.DataFrame) or frame.empty or 'EDNNA - Intenção' not in frame.columns: return pd.DataFrame(columns=cols)
    base=frame.copy()
    for c,v in [('EDNNA - Confiança',0.0),('EDNNA - Regra',''),('EDNNA - Automatizável','NÃO'),('EDNNA - Conflito de classificação','NÃO')]:
        if c not in base.columns: base[c]=v
    linhas=[]
    for intencao,grupo in base.groupby('EDNNA - Intenção',dropna=False):
        intencao=str(intencao if pd.notna(intencao) else 'NAO_CLASSIFICADO'); total=len(grupo)
        conf=float(pd.to_numeric(grupo['EDNNA - Confiança'],errors='coerce').fillna(0).mean())
        regras=int((grupo['EDNNA - Regra'].fillna('').astype(str).str.strip()!='').sum())
        autos=int((grupo['EDNNA - Automatizável'].astype(str)=='SIM').sum()); conflitos=int((grupo['EDNNA - Conflito de classificação'].astype(str)=='SIM').sum())
        score=min(1,total/20)*0.35+conf*0.35+(regras/total if total else 0)*0.15+(autos/total if total else 0)*0.15-(conflitos/total if total else 0)*0.20
        if intencao=='NAO_CLASSIFICADO': score=0.0
        score=max(0,score); faixa='Alta' if score>=.80 else 'Média' if score>=.60 else 'Baixa' if score>0 else 'Não aplicável'
        linhas.append({'Intenção':intencao,'Chamados':total,'Confiança média':round(conf,2),'Com regra candidata':regras,'Automatizáveis':autos,'Conflitos':conflitos,'Prontidão':round(score,2),'Faixa':faixa})
    return pd.DataFrame(linhas).sort_values(['Prontidão','Chamados','Confiança média'],ascending=[False,False,False]).reset_index(drop=True)


def resumo_oportunidades(frame: pd.DataFrame) -> dict:
    if frame is None or not isinstance(frame,pd.DataFrame) or frame.empty: return {'total':0,'reconhecidos':0,'nao_classificados':0,'com_regra':0,'alta_prontidao':0,'automatizaveis':0,'conflitos':0}
    total=len(frame); reconhecidos=int((frame['EDNNA - Intenção'].fillna('NAO_CLASSIFICADO').astype(str)!='NAO_CLASSIFICADO').sum())
    com_regra=int((frame['EDNNA - Regra'].fillna('').astype(str).str.strip()!='').sum()); prontidao=calcular_prontidao_automacao(frame)
    return {'total':total,'reconhecidos':reconhecidos,'nao_classificados':total-reconhecidos,'com_regra':com_regra,'alta_prontidao':int((prontidao['Faixa']=='Alta').sum()) if not prontidao.empty else 0,'automatizaveis':int((frame.get('EDNNA - Automatizável',pd.Series('',index=frame.index)).astype(str)=='SIM').sum()),'conflitos':int((frame.get('EDNNA - Conflito de classificação',pd.Series('',index=frame.index)).astype(str)=='SIM').sum())}
