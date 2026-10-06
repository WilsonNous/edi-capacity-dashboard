from __future__ import annotations

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

async def _proxy(request: Request, base: str) -> Response:
    url = f"{base}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in {"host", "content-length", "connection", "upgrade"}}
    body = await request.body()
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        upstream = await client.request(request.method, url, headers=headers, content=body)
    excluded = {"content-encoding", "transfer-encoding", "connection", "content-length"}
    response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}
    return Response(upstream.content, status_code=upstream.status_code,
                    headers=response_headers, media_type=upstream.headers.get("content-type"))

@app.get("/healthz")
async def healthz():
    checks = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in {
            "streamlit": f"{UI_BASE}/_stcore/health",
            "intelligence_api": f"{API_BASE}/api/intelligence/handshake",
        }.items():
            try:
                response = await client.get(url)
                # API handshake is authenticated; 401 proves the process is alive.
                checks[name] = response.status_code in ({200} if name == "streamlit" else {200, 401, 422})
            except Exception:
                checks[name] = False
    ok = all(checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", "component": "eddy-gateway",
                         "checks": checks}, status_code=200 if ok else 503)

@app.api_route("/api/intelligence/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def intelligence(request: Request, path: str):
    return await _proxy(request, API_BASE)

@app.websocket("/{path:path}")
async def streamlit_websocket(websocket: WebSocket, path: str):
    query = f"?{websocket.url.query}" if websocket.url.query else ""
    upstream_url = f"{UI_WS_BASE}/{path}{query}"
    headers = []
    for key, value in websocket.headers.items():
        if key.lower() not in {"host", "connection", "upgrade", "sec-websocket-key",
                               "sec-websocket-version", "sec-websocket-extensions",
                               "sec-websocket-protocol"}:
            headers.append((key, value))
    subprotocols = list(websocket.scope.get("subprotocols") or [])
    await websocket.accept(subprotocol=subprotocols[0] if subprotocols else None)
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

            import asyncio
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
            await websocket.close(code=1011)
        except Exception:
            pass

@app.api_route("/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def streamlit(request: Request, path: str):
    return await _proxy(request, UI_BASE)
