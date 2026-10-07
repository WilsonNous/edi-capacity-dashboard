from __future__ import annotations
import re
from ednna.armazenamento import conectar, agora_brasil_iso

REGRA_ID="OCORRENCIA-POLICARD-UPBRASIL-FALTA-VENDAS-001"
DESTINATARIO="conciliacao@upbrasil.com"

def garantir_regra_policard_falta_vendas()->dict:
    """Regra homologada para falta de vendas POLICARD/UP Brasil.

    Evidência operacional de 07/10/2026: UP Brasil orientou que demandas de
    conciliação sejam enviadas exclusivamente a conciliacao@upbrasil.com,
    retirando grandesredesup@upbrasil.com e demais endereços da cópia.
    """
    agora=agora_brasil_iso()
    payload={
        "regra_id":REGRA_ID,"player":"POLICARD","alias":["UPBRASIL","UP BRASIL"],
        "ocorrencia":"FALTA_VENDAS","estado":"HOMOLOGADA","modo_motor":"AUTOMATICA",
        "executor":"EMAIL_GRAPH","para":[DESTINATARIO],"cc":[],
        "remover_destinatarios":["grandesredesup@upbrasil.com","atendimento.granderede@upbrasil.com"],
        "agrupamento":"UM_CHAMADO_POR_PLAYER_OCORRENCIA","multiplos_cnpjs":True,"multiplos_periodos":True,
        "assunto":"POLICARD - Falta de Vendas - {cliente} - CN: {chamado_id}",
        "instrucao":"Enviar a demanda de conciliação somente para conciliacao@upbrasil.com. Agrupar todos os CNPJs/estabelecimentos e períodos da mesma ocorrência no mesmo chamado/e-mail. Não copiar Grandes Redes ou outros endereços UP Brasil.",
        "fonte":"EMAIL_UPBRASIL_2026-10-07",
    }
    import json
    with conectar() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS regras_ocorrencias_operacionais (
          regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, ocorrencia TEXT NOT NULL,
          estado TEXT NOT NULL, modo_motor TEXT NOT NULL, executor TEXT NOT NULL,
          payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        c.execute("""INSERT INTO regras_ocorrencias_operacionais(regra_id,player,ocorrencia,estado,modo_motor,executor,payload_json,atualizado_em)
          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(regra_id) DO UPDATE SET player=excluded.player,ocorrencia=excluded.ocorrencia,
          estado=excluded.estado,modo_motor=excluded.modo_motor,executor=excluded.executor,payload_json=excluded.payload_json,atualizado_em=excluded.atualizado_em""",
          (REGRA_ID,"POLICARD","FALTA_VENDAS","HOMOLOGADA","AUTOMATICA","EMAIL_GRAPH",json.dumps(payload,ensure_ascii=False),agora))
    return payload

def obter_regra_ocorrencia(player:str,tipo:str)->dict|None:
    aliases={"UPBRASIL":"POLICARD","UP BRASIL":"POLICARD","POLICARD":"POLICARD"}
    p=aliases.get(str(player or "").strip().upper(),str(player or "").strip().upper())
    if p=="POLICARD" and str(tipo or "").strip().upper()=="FALTA_VENDAS":
        return garantir_regra_policard_falta_vendas()
    return None
