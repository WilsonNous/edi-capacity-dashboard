from __future__ import annotations

import asyncio
import os

import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

app = FastAPI(title="EDDY Gateway", docs_url=None, redoc_url=None)
API_BASE = os.getenv("EDDY_API_INTERNAL_URL", "http://127.0.0.1:8001")
UI_BASE = os.getenv("EDDY_UI_INTERNAL_URL", "http://127.0.0.1:8501")
UI_WS_BASE = UI_BASE.replace("https://", "wss://").replace("http://", "ws://")
TIMEOUT = httpx.Timeout(65.0, connect=5.0)
LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=40, keepalive_expiry=30.0)

_http: httpx.AsyncClient | None = None

@app.on_event("startup")
async def _startup() -> None:
    global _http
    _http = httpx.AsyncClient(timeout=TIMEOUT, limits=LIMITS, follow_redirects=False)

@app.on_event("shutdown")
async def _shutdown() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None

def _client() -> httpx.AsyncClient:
    if _http is None:
        raise RuntimeError("gateway HTTP client is not ready")
    return _http

def _headers(request: Request) -> dict[str, str]:
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in {"host", "content-length", "connection", "upgrade"}}
    client_host = request.client.host if request.client else ""
    forwarded_for = request.headers.get("x-forwarded-for")
    if client_host:
        headers["x-forwarded-for"] = f"{forwarded_for}, {client_host}" if forwarded_for else client_host
    headers["x-forwarded-proto"] = request.headers.get("x-forwarded-proto", request.url.scheme)
    if request.headers.get("host"):
        headers["x-forwarded-host"] = request.headers["host"]
    return headers

async def _proxy(request: Request, base: str) -> Response:
    url = f"{base}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    try:
        upstream = await _client().request(
            request.method, url, headers=_headers(request), content=await request.body()
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout):
        return JSONResponse(
            {"status": "unavailable", "component": "eddy-gateway", "upstream": "internal"},
            status_code=503,
            headers={"Retry-After": "2"},
        )

    excluded = {"content-encoding", "transfer-encoding", "connection", "content-length"}
    response_headers: dict[str, str] = {}
    for key, value in upstream.headers.multi_items():
        if key.lower() not in excluded and key.lower() != "set-cookie":
            response_headers[key] = value
    response = Response(
        upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
    for cookie in upstream.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", cookie)
    return response

@app.get("/healthz")
async def healthz():
    checks = {}
    for name, url in {
        "streamlit": f"{UI_BASE}/_stcore/health",
        "intelligence_api": f"{API_BASE}/api/intelligence/handshake",
    }.items():
        try:
            response = await _client().get(url, timeout=3.0)
            checks[name] = response.status_code in ({200} if name == "streamlit" else {200, 401, 422})
        except Exception:
            checks[name] = False
    ok = all(checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "component": "eddy-gateway", "checks": checks},
        status_code=200 if ok else 503,
    )

@app.api_route("/api/intelligence/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def intelligence(request: Request, path: str):
    return await _proxy(request, API_BASE)

@app.websocket("/{path:path}")
async def streamlit_websocket(websocket: WebSocket, path: str):
    query = f"?{websocket.url.query}" if websocket.url.query else ""
    upstream_url = f"{UI_WS_BASE}/{path}{query}"
    headers = []
    for key, value in websocket.headers.items():
        if key.lower() not in {"host", "origin", "connection", "upgrade", "sec-websocket-key",
                               "sec-websocket-version", "sec-websocket-extensions",
                               "sec-websocket-protocol"}:
            headers.append((key, value))
    # Streamlit valida Origin x Host. O salto interno do gateway usa loopback,
    # portanto ambos precisam representar o upstream interno.
    headers.append(("Origin", UI_BASE))
    subprotocols = list(websocket.scope.get("subprotocols") or [])
    try:
        async with websockets.connect(
            upstream_url,
            additional_headers=headers,
            subprotocols=subprotocols or None,
            open_timeout=5,
            ping_interval=20,
            ping_timeout=20,
            max_size=None,
        ) as upstream:
            selected = upstream.subprotocol if upstream.subprotocol in subprotocols else None
            await websocket.accept(subprotocol=selected)

            async def client_to_upstream():
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        break
                    if message.get("bytes") is not None:
                        await upstream.send(message["bytes"])
                    elif message.get("text") is not None:
                        await upstream.send(message["text"])

            async def upstream_to_client():
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
    except (WebSocketDisconnect, websockets.ConnectionClosed):
        pass
    except Exception:
        try:
            await websocket.close(code=1013)
        except Exception:
            pass

@app.api_route("/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def streamlit(request: Request, path: str):
    return await _proxy(request, UI_BASE)
