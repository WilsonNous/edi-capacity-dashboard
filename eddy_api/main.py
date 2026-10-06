from __future__ import annotations
import hmac
import os
import uuid
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any
from eddy_api import CONTRACT_VERSION, DOMAIN, SPECIALIST_ID
from eddy_api.service import CAPABILITIES, ROUTES

app = FastAPI(title="EDDY Intelligence API", version=CONTRACT_VERSION)

class QueryRequest(BaseModel):
    capability: str
    input: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None
    tenant_id: str | None = None
    conversation_id: str | None = None
    trace_id: str | None = None

class ActionRequest(QueryRequest):
    idempotency_key: str
    dry_run: bool = True

def _auth(authorization: str | None):
    expected = os.getenv("EDDY_INTELLIGENCE_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Autenticação do especialista não configurada.")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "Não autorizado.")

def _contract(version: str | None):
    if version != CONTRACT_VERSION:
        raise HTTPException(422, f"Versão de contrato não suportada. Esperada: {CONTRACT_VERSION}.")

def _base(trace_id: str | None, capability: str):
    return {"contract_version": CONTRACT_VERSION, "specialist_id": SPECIALIST_ID,
            "capability": capability, "trace_id": trace_id or str(uuid.uuid4())}

@app.get("/api/intelligence/handshake")
def handshake(x_ednna_contract_version: str | None = Header(None, alias="X-EDNNA-Contract-Version"),
              authorization: str | None = Header(None)):
    _auth(authorization); _contract(x_ednna_contract_version)
    return {"contract_version": CONTRACT_VERSION, "specialist_id": SPECIALIST_ID, "domain": DOMAIN,
            "status": "ready", "capabilities": list(CAPABILITIES),
            "actions": [{"capability": "edi.operation.execute", "mode": "dry-run-only"}]}

@app.post("/api/intelligence/query")
def query(body: QueryRequest,
          x_ednna_contract_version: str | None = Header(None, alias="X-EDNNA-Contract-Version"),
          authorization: str | None = Header(None)):
    _auth(authorization); _contract(x_ednna_contract_version)
    if body.capability not in ROUTES:
        raise HTTPException(404, "Capability inexistente.")
    try:
        output, confidence, evidence, warnings, requires_human = ROUTES[body.capability](body.input)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Especialista temporariamente indisponível.")
    return {**_base(body.trace_id, body.capability), "status": "success", "output": output,
            "confidence": confidence, "evidence": evidence, "warnings": warnings,
            "requires_human": requires_human}

@app.post("/api/intelligence/action")
def action(body: ActionRequest,
           x_ednna_contract_version: str | None = Header(None, alias="X-EDNNA-Contract-Version"),
           authorization: str | None = Header(None)):
    _auth(authorization); _contract(x_ednna_contract_version)
    if body.capability != "edi.operation.execute":
        raise HTTPException(404, "Capability de ação inexistente.")
    if not body.dry_run:
        raise HTTPException(403, "Execução live está desabilitada.")
    return {**_base(body.trace_id, body.capability), "status": "success", "state": "not_executed",
            "idempotency_key": body.idempotency_key, "dry_run": True,
            "output": {"message": "Dry-run aceito; nenhuma operação EDI foi executada."},
            "confidence": 1.0, "evidence": [], "warnings": [], "requires_human": False}

@app.get("/api/intelligence/actions/{idempotency_key}")
def action_status(idempotency_key: str,
                  x_ednna_contract_version: str | None = Header(None, alias="X-EDNNA-Contract-Version"),
                  authorization: str | None = Header(None)):
    _auth(authorization); _contract(x_ednna_contract_version)
    # Read-only: nunca reexecuta. Persistência de actions entra antes de qualquer live action.
    return {"contract_version": CONTRACT_VERSION, "specialist_id": SPECIALIST_ID,
            "idempotency_key": idempotency_key, "state": "unknown", "trace_id": None,
            "evidence": [], "reference": None}
