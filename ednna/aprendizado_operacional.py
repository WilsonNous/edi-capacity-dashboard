    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT regra_id FROM aprendizados_operacionais WHERE upper(player)='SAFRAPAY' AND operacao='INCLUSAO' ORDER BY atualizado_em DESC LIMIT 1").fetchone()
        if row:
            regra_id = str(row["regra_id"])
        else:
            payload = {
                "regra_id": regra_id, "player": "SAFRAPAY", "operacao": "INCLUSAO",
                "estado": "REGRA_PRONTA", "completude": 100,
                "procedimento_confirmado": True, "workflow": workflow,
                "variaveis": ["cliente","cnpjs","estabelecimento","contatos_cliente"],
                "fontes": {"autoridade":"PROCEDIMENTO_HOMOLOGADO_OPERACAO", "chamado_historico":45956},
                "aprendido_em": agora,
            }
            conn.execute("""INSERT INTO aprendizados_operacionais
                (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
                VALUES (?,?,?,?,?,?,?)""",
                (regra_id,"SAFRAPAY","INCLUSAO","REGRA_PRONTA",100,json.dumps(payload,ensure_ascii=False),agora))
    rev = obter_revisao(regra_id)
    if rev.get("estado") != "HOMOLOGADA":
        salvar_revisao_assistida(regra_id, destinatario_confirmado="conciliador.safrapay@safra.com.br", observacoes="Inclusão SAFRAPAY homologada pelo #45956. VAN Supply Mídia; custo Netunna; padrão V2.0 Ed.13. Checkpoints humanos: Termo SAFRAPAY, planilha Supply e validação final dos arquivos.", revisado_por="MIGRACAO_EDNNA_3_34_6")
        homologar_regra_assistida(regra_id, revisado_por="MIGRACAO_EDNNA_3_34_6")
    migracao_id = "3.34.6-SAFRAPAY-WORKFLOW-CHECKPOINTS"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    if not aplicada:
        autorizar_regra_motor(regra_id, modo="AUTOMATICA", autorizado_por="MIGRACAO_EDNNA_3_34_6", observacoes="Workflow automático com checkpoints humanos explícitos; o worker não pode ultrapassar checkpoint sem confirmação humana.")
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return {"regra_id": regra_id, "revisao": obter_revisao(regra_id), "autorizacao": obter_autorizacao_motor(regra_id)}


def garantir_itau_pronto() -> dict:
    """Promove para AUTOMATICA somente regras ITAU que já estejam homologadas.

    Não cria conhecimento novo e não inventa destinatários/modelos. A migração
    apenas remove o bloqueio técnico do workflow e autoriza as regras existentes
    de ABERTURA e INCLUSAO, preservando a aprendizagem homologada como fonte.
    """
    if _mysql():
        # Historical bootstrap is not replayed against MySQL. Do not silently
        # grant AUTOMATICA or re-homologate rules on service startup.
        return {op: {"estado": "MIGRACAO_HISTORICA_PENDENTE",
                     "autorizacao": {"modo": "BLOQUEADA"}}
                for op in ("ABERTURA", "INCLUSAO")}
    resultados = {}
    migracao_id = "4.4-ITAU-ABERTURA-INCLUSAO-AUTOMATICA"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    for operacao in ("ABERTURA", "INCLUSAO"):
        regra = obter_regra_homologada("ITAU", operacao) or {}
        rid = str(regra.get("regra_id") or "")
        if not rid:
            resultados[operacao] = {"estado": "NAO_ENCONTRADA_HOMOLOGADA"}
            continue
        aut = obter_autorizacao_motor(rid)
        if not aplicada and str(aut.get("modo") or "BLOQUEADA").upper() != "AUTOMATICA":
            autorizar_regra_motor(
                rid,
                modo="AUTOMATICA",
                autorizado_por="MIGRACAO_EDDY_4_4",
                observacoes=f"Regra ITAU {operacao} já homologada pela aprendizagem; promovida para operação automática usando exclusivamente procedimento/modelo homologado.",
            )
            aut = obter_autorizacao_motor(rid)
        resultados[operacao] = {"regra_id": rid, "estado": "HOMOLOGADA", "autorizacao": aut}
    if not aplicada:
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return resultados
    if _mysql():
        # The legacy bootstrap implicitly grants AUTOMATICA. Until historical
        # migration is reconciled, never recreate or promote that permission.
        from ednna.motores_mysql_repository import obter_autorizacao
        return {"regra_id": "INCLUSAO-GREENCARD-001",
                "estado": "MIGRACAO_HISTORICA_PENDENTE",
                "autorizacao": obter_autorizacao("INCLUSAO-GREENCARD-001")}
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
        salvar_revisao_assistida(regra_id, destinatario_confirmado="suporte.credenciado@grupogreencard.com.br", observacoes="Inclusão Greencard homologada pelo caso #46968: enviar diretamente a suporte.credenciado@grupogreencard.com.br com cliente, CNPJ e EC; solicitar arquivos na CAIXA POSTAL NETUNNA; contatos do cliente via Blueprint entram em CC; acompanhar retorno e arquivos.", revisado_por="MIGRACAO_EDNNA_3_32_4")
        homologar_regra_assistida(regra_id, revisado_por="MIGRACAO_EDNNA_3_32_4")
    # Promoção automática é migração de uma única execução. Depois disso, uma
    # decisão posterior do operador (ASSISTIDA/BLOQUEADA) não pode ser desfeita
    # silenciosamente a cada restart da aplicação.
    migracao_id = "3.32.4-GREENCARD-INCLUSAO-DIRETA-AUTOMATICA"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    if not aplicada:
        aut = obter_autorizacao_motor(regra_id)
        if str(aut.get("modo") or "BLOQUEADA").upper() != "AUTOMATICA":
            autorizar_regra_motor(regra_id, modo="AUTOMATICA", autorizado_por="MIGRACAO_EDNNA_3_32_4", observacoes="Inclusão Greencard autorizada para execução automática após homologação do procedimento real #46968. Abertura de relacionamento permanece fluxo separado.")
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return {"regra_id": regra_id, "revisao": obter_revisao(regra_id), "autorizacao": obter_autorizacao_motor(regra_id)}


def garantir_safrapay_pronta() -> dict:
    """v3.34.6 — registra/homologa SAFRAPAY com checkpoints humanos seguros.

    Evidência operacional: #45956. A regra é AUTOMATICA no sentido de que a
    EDNNA continua dona do workflow, mas checkpoints humanos nunca são pulados.
    """
    regra_id = "INCLUSAO-SAFRAPAY-001"
    agora = agora_brasil_iso()
    workflow = obter_workflow("SAFRAPAY")
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT regra_id FROM aprendizados_operacionais WHERE upper(player)='SAFRAPAY' AND operacao='INCLUSAO' ORDER BY atualizado_em DESC LIMIT 1").fetchone()
        if row:
            regra_id = str(row["regra_id"])
        else:
            payload = {
                "regra_id": regra_id, "player": "SAFRAPAY", "operacao": "INCLUSAO",
                "estado": "REGRA_PRONTA", "completude": 100,
                "procedimento_confirmado": True, "workflow": workflow,
                "variaveis": ["cliente","cnpjs","estabelecimento","contatos_cliente"],
                "fontes": {"autoridade":"PROCEDIMENTO_HOMOLOGADO_OPERACAO", "chamado_historico":45956},
                "aprendido_em": agora,
            }
            conn.execute("""INSERT INTO aprendizados_operacionais
                (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
                VALUES (?,?,?,?,?,?,?)""",
                (regra_id,"SAFRAPAY","INCLUSAO","REGRA_PRONTA",100,json.dumps(payload,ensure_ascii=False),agora))
    rev = obter_revisao(regra_id)
    if rev.get("estado") != "HOMOLOGADA":
        salvar_revisao_assistida(regra_id, destinatario_confirmado="conciliador.safrapay@safra.com.br", observacoes="Inclusão SAFRAPAY homologada pelo #45956. VAN Supply Mídia; custo Netunna; padrão V2.0 Ed.13. Checkpoints humanos: Termo SAFRAPAY, planilha Supply e validação final dos arquivos.", revisado_por="MIGRACAO_EDNNA_3_34_6")
        homologar_regra_assistida(regra_id, revisado_por="MIGRACAO_EDNNA_3_34_6")
    migracao_id = "3.34.6-SAFRAPAY-WORKFLOW-CHECKPOINTS"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    if not aplicada:
        autorizar_regra_motor(regra_id, modo="AUTOMATICA", autorizado_por="MIGRACAO_EDNNA_3_34_6", observacoes="Workflow automático com checkpoints humanos explícitos; o worker não pode ultrapassar checkpoint sem confirmação humana.")
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return {"regra_id": regra_id, "revisao": obter_revisao(regra_id), "autorizacao": obter_autorizacao_motor(regra_id)}


def garantir_itau_pronto() -> dict:
    """Promove para AUTOMATICA somente regras ITAU que já estejam homologadas.

    Não cria conhecimento novo e não inventa destinatários/modelos. A migração
    apenas remove o bloqueio técnico do workflow e autoriza as regras existentes
    de ABERTURA e INCLUSAO, preservando a aprendizagem homologada como fonte.
    """
    resultados = {}
    migracao_id = "4.4-ITAU-ABERTURA-INCLUSAO-AUTOMATICA"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    for operacao in ("ABERTURA", "INCLUSAO"):
        regra = obter_regra_homologada("ITAU", operacao) or {}
        rid = str(regra.get("regra_id") or "")
        if not rid:
            resultados[operacao] = {"estado": "NAO_ENCONTRADA_HOMOLOGADA"}
            continue
        aut = obter_autorizacao_motor(rid)
        if not aplicada and str(aut.get("modo") or "BLOQUEADA").upper() != "AUTOMATICA":
            autorizar_regra_motor(
                rid,
                modo="AUTOMATICA",
                autorizado_por="MIGRACAO_EDDY_4_4",
                observacoes=f"Regra ITAU {operacao} já homologada pela aprendizagem; promovida para operação automática usando exclusivamente procedimento/modelo homologado.",
            )
            aut = obter_autorizacao_motor(rid)
        resultados[operacao] = {"regra_id": rid, "estado": "HOMOLOGADA", "autorizacao": aut}
    if not aplicada:
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return resultados
    if _mysql():
        # The legacy bootstrap implicitly grants AUTOMATICA. Until historical
        # migration is reconciled, never recreate or promote that permission.
        from ednna.motores_mysql_repository import obter_autorizacao
        return {"regra_id": "INCLUSAO-SAFRAPAY-001",
                "estado": "MIGRACAO_HISTORICA_PENDENTE",
                "autorizacao": obter_autorizacao("INCLUSAO-SAFRAPAY-001")}
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT regra_id FROM aprendizados_operacionais WHERE upper(player)='SAFRAPAY' AND operacao='INCLUSAO' ORDER BY atualizado_em DESC LIMIT 1").fetchone()
        if row:
            regra_id = str(row["regra_id"])
        else:
            payload = {
                "regra_id": regra_id, "player": "SAFRAPAY", "operacao": "INCLUSAO",
                "estado": "REGRA_PRONTA", "completude": 100,
                "procedimento_confirmado": True, "workflow": workflow,
                "variaveis": ["cliente","cnpjs","estabelecimento","contatos_cliente"],
                "fontes": {"autoridade":"PROCEDIMENTO_HOMOLOGADO_OPERACAO", "chamado_historico":45956},
                "aprendido_em": agora,
            }
            conn.execute("""INSERT INTO aprendizados_operacionais
                (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
                VALUES (?,?,?,?,?,?,?)""",
                (regra_id,"SAFRAPAY","INCLUSAO","REGRA_PRONTA",100,json.dumps(payload,ensure_ascii=False),agora))
    rev = obter_revisao(regra_id)
    if rev.get("estado") != "HOMOLOGADA":
        salvar_revisao_assistida(regra_id, destinatario_confirmado="conciliador.safrapay@safra.com.br", observacoes="Inclusão SAFRAPAY homologada pelo #45956. VAN Supply Mídia; custo Netunna; padrão V2.0 Ed.13. Checkpoints humanos: Termo SAFRAPAY, planilha Supply e validação final dos arquivos.", revisado_por="MIGRACAO_EDNNA_3_34_6")
        homologar_regra_assistida(regra_id, revisado_por="MIGRACAO_EDNNA_3_34_6")
    migracao_id = "3.34.6-SAFRAPAY-WORKFLOW-CHECKPOINTS"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    if not aplicada:
        autorizar_regra_motor(regra_id, modo="AUTOMATICA", autorizado_por="MIGRACAO_EDNNA_3_34_6", observacoes="Workflow automático com checkpoints humanos explícitos; o worker não pode ultrapassar checkpoint sem confirmação humana.")
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return {"regra_id": regra_id, "revisao": obter_revisao(regra_id), "autorizacao": obter_autorizacao_motor(regra_id)}


def garantir_itau_pronto() -> dict:
    """Promove para AUTOMATICA somente regras ITAU que já estejam homologadas.

    Não cria conhecimento novo e não inventa destinatários/modelos. A migração
    apenas remove o bloqueio técnico do workflow e autoriza as regras existentes
    de ABERTURA e INCLUSAO, preservando a aprendizagem homologada como fonte.
    """
    resultados = {}
    migracao_id = "4.4-ITAU-ABERTURA-INCLUSAO-AUTOMATICA"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    for operacao in ("ABERTURA", "INCLUSAO"):
        regra = obter_regra_homologada("ITAU", operacao) or {}
        rid = str(regra.get("regra_id") or "")
        if not rid:
            resultados[operacao] = {"estado": "NAO_ENCONTRADA_HOMOLOGADA"}
            continue
        aut = obter_autorizacao_motor(rid)
        if not aplicada and str(aut.get("modo") or "BLOQUEADA").upper() != "AUTOMATICA":
            autorizar_regra_motor(
                rid,
                modo="AUTOMATICA",
                autorizado_por="MIGRACAO_EDDY_4_4",
                observacoes=f"Regra ITAU {operacao} já homologada pela aprendizagem; promovida para operação automática usando exclusivamente procedimento/modelo homologado.",
            )
            aut = obter_autorizacao_motor(rid)
        resultados[operacao] = {"regra_id": rid, "estado": "HOMOLOGADA", "autorizacao": aut}
    if not aplicada:
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return resultados
    if _mysql():
        # The legacy bootstrap implicitly grants AUTOMATICA. Until historical
        # migration is reconciled, never recreate or promote that permission.
        from ednna.motores_mysql_repository import obter_autorizacao
        return {"regra_id": "INCLUSAO-GREENCARD-001",
                "estado": "MIGRACAO_HISTORICA_PENDENTE",
                "autorizacao": obter_autorizacao("INCLUSAO-GREENCARD-001")}
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
        salvar_revisao_assistida(regra_id, destinatario_confirmado="suporte.credenciado@grupogreencard.com.br", observacoes="Inclusão Greencard homologada pelo caso #46968: enviar diretamente a suporte.credenciado@grupogreencard.com.br com cliente, CNPJ e EC; solicitar arquivos na CAIXA POSTAL NETUNNA; contatos do cliente via Blueprint entram em CC; acompanhar retorno e arquivos.", revisado_por="MIGRACAO_EDNNA_3_32_4")
        homologar_regra_assistida(regra_id, revisado_por="MIGRACAO_EDNNA_3_32_4")
    # Promoção automática é migração de uma única execução. Depois disso, uma
    # decisão posterior do operador (ASSISTIDA/BLOQUEADA) não pode ser desfeita
    # silenciosamente a cada restart da aplicação.
    migracao_id = "3.32.4-GREENCARD-INCLUSAO-DIRETA-AUTOMATICA"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    if not aplicada:
        aut = obter_autorizacao_motor(regra_id)
        if str(aut.get("modo") or "BLOQUEADA").upper() != "AUTOMATICA":
            autorizar_regra_motor(regra_id, modo="AUTOMATICA", autorizado_por="MIGRACAO_EDNNA_3_32_4", observacoes="Inclusão Greencard autorizada para execução automática após homologação do procedimento real #46968. Abertura de relacionamento permanece fluxo separado.")
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return {"regra_id": regra_id, "revisao": obter_revisao(regra_id), "autorizacao": obter_autorizacao_motor(regra_id)}


def garantir_safrapay_pronta() -> dict:
    """v3.34.6 — registra/homologa SAFRAPAY com checkpoints humanos seguros.

    Evidência operacional: #45956. A regra é AUTOMATICA no sentido de que a
    EDNNA continua dona do workflow, mas checkpoints humanos nunca são pulados.
    """
    regra_id = "INCLUSAO-SAFRAPAY-001"
    agora = agora_brasil_iso()
    workflow = obter_workflow("SAFRAPAY")
    with conectar() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS aprendizados_operacionais (
            regra_id TEXT PRIMARY KEY, player TEXT NOT NULL, operacao TEXT NOT NULL,
            estado TEXT NOT NULL, completude INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL, atualizado_em TEXT NOT NULL)""")
        row = conn.execute("SELECT regra_id FROM aprendizados_operacionais WHERE upper(player)='SAFRAPAY' AND operacao='INCLUSAO' ORDER BY atualizado_em DESC LIMIT 1").fetchone()
        if row:
            regra_id = str(row["regra_id"])
        else:
            payload = {
                "regra_id": regra_id, "player": "SAFRAPAY", "operacao": "INCLUSAO",
                "estado": "REGRA_PRONTA", "completude": 100,
                "procedimento_confirmado": True, "workflow": workflow,
                "variaveis": ["cliente","cnpjs","estabelecimento","contatos_cliente"],
                "fontes": {"autoridade":"PROCEDIMENTO_HOMOLOGADO_OPERACAO", "chamado_historico":45956},
                "aprendido_em": agora,
            }
            conn.execute("""INSERT INTO aprendizados_operacionais
                (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
                VALUES (?,?,?,?,?,?,?)""",
                (regra_id,"SAFRAPAY","INCLUSAO","REGRA_PRONTA",100,json.dumps(payload,ensure_ascii=False),agora))
    rev = obter_revisao(regra_id)
    if rev.get("estado") != "HOMOLOGADA":
        salvar_revisao_assistida(regra_id, destinatario_confirmado="conciliador.safrapay@safra.com.br", observacoes="Inclusão SAFRAPAY homologada pelo #45956. VAN Supply Mídia; custo Netunna; padrão V2.0 Ed.13. Checkpoints humanos: Termo SAFRAPAY, planilha Supply e validação final dos arquivos.", revisado_por="MIGRACAO_EDNNA_3_34_6")
        homologar_regra_assistida(regra_id, revisado_por="MIGRACAO_EDNNA_3_34_6")
    migracao_id = "3.34.6-SAFRAPAY-WORKFLOW-CHECKPOINTS"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    if not aplicada:
        autorizar_regra_motor(regra_id, modo="AUTOMATICA", autorizado_por="MIGRACAO_EDNNA_3_34_6", observacoes="Workflow automático com checkpoints humanos explícitos; o worker não pode ultrapassar checkpoint sem confirmação humana.")
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return {"regra_id": regra_id, "revisao": obter_revisao(regra_id), "autorizacao": obter_autorizacao_motor(regra_id)}


def garantir_itau_pronto() -> dict:
    """Promove para AUTOMATICA somente regras ITAU que já estejam homologadas.

    Não cria conhecimento novo e não inventa destinatários/modelos. A migração
    apenas remove o bloqueio técnico do workflow e autoriza as regras existentes
    de ABERTURA e INCLUSAO, preservando a aprendizagem homologada como fonte.
    """
    resultados = {}
    migracao_id = "4.4-ITAU-ABERTURA-INCLUSAO-AUTOMATICA"
    with conectar() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS migracoes_ednna (migracao_id TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
        aplicada = conn.execute("SELECT 1 FROM migracoes_ednna WHERE migracao_id=?", (migracao_id,)).fetchone()
    for operacao in ("ABERTURA", "INCLUSAO"):
        regra = obter_regra_homologada("ITAU", operacao) or {}
        rid = str(regra.get("regra_id") or "")
        if not rid:
            resultados[operacao] = {"estado": "NAO_ENCONTRADA_HOMOLOGADA"}
            continue
        aut = obter_autorizacao_motor(rid)
        if not aplicada and str(aut.get("modo") or "BLOQUEADA").upper() != "AUTOMATICA":
            autorizar_regra_motor(
                rid,
                modo="AUTOMATICA",
                autorizado_por="MIGRACAO_EDDY_4_4",
                observacoes=f"Regra ITAU {operacao} já homologada pela aprendizagem; promovida para operação automática usando exclusivamente procedimento/modelo homologado.",
            )
            aut = obter_autorizacao_motor(rid)
        resultados[operacao] = {"regra_id": rid, "estado": "HOMOLOGADA", "autorizacao": aut}
    if not aplicada:
        with conectar() as conn:
            conn.execute("INSERT OR IGNORE INTO migracoes_ednna(migracao_id,aplicada_em) VALUES(?,?)", (migracao_id, agora_brasil_iso()))
    return resultados
