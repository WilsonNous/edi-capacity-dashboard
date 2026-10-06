from __future__ import annotations

import os
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI(title="EDDY Gateway", docs_url=None, redoc_url=None)
API_BASE = os.getenv("EDDY_API_INTERNAL_URL", "http://127.0.0.1:8001")
UI_BASE = os.getenv("EDDY_UI_INTERNAL_URL", "http://127.0.0.1:8501")
TIMEOUT = httpx.Timeout(65.0, connect=5.0)

async def _proxy(request: Request, base: str) -> Response:
    url = f"{base}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length"}}
    body = await request.body()
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        upstream = await client.request(request.method, url, headers=headers, content=body)
    excluded = {"content-encoding", "transfer-encoding", "connection", "content-length"}
    response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}
    return Response(upstream.content, status_code=upstream.status_code,
                    headers=response_headers, media_type=upstream.headers.get("content-type"))

@app.get("/healthz")
def healthz():
    return {"status": "ok", "component": "eddy-gateway"}

@app.api_route("/api/intelligence/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def intelligence(request: Request, path: str):
    return await _proxy(request, API_BASE)

@app.api_route("/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def streamlit(request: Request, path: str):
    return await _proxy(request, UI_BASE)
