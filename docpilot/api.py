"""FastAPI service.  Run:  uvicorn docpilot.api:create_app --factory --port 8080

Covered by tests/test_api.py and scripts/smoke_api.py.

Do not add `from __future__ import annotations` here: FastAPI resolves string annotations
against module globals, and `Request` / `AskRequest` are local to create_app, so every
endpoint would then reject requests with 422 (missing query params `request`/`req`).
"""
import json

from .config import Settings
from .security import ApiKeyAuth, RateLimiter
from .service import DocPilot


def create_app(settings: Settings | None = None, system: DocPilot | None = None):
    from fastapi import Depends, FastAPI, Header, HTTPException, Request
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field

    settings = settings or Settings()
    system = system or DocPilot(settings)
    auth = ApiKeyAuth(settings.api_keys)
    limiter = RateLimiter(settings.rate_per_min)

    class AskRequest(BaseModel):
        question: str = Field(min_length=3, max_length=1000)
        topic: str | None = None

    def guard(request: Request, x_api_key: str | None = Header(default=None)):
        if not auth.check(x_api_key):
            raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
        who = x_api_key or (request.client.host if request.client else "anon")
        if not limiter.allow(who):
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        return who

    app = FastAPI(title="DocPilot", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "chunks": len(system.chunks)}

    @app.get("/stats", dependencies=[Depends(guard)])
    def stats():
        return system.stats()

    @app.post("/ask", dependencies=[Depends(guard)])
    def ask(req: AskRequest):
        return system.ask(req.question, req.topic).to_dict()

    @app.post("/ask/stream", dependencies=[Depends(guard)])
    def ask_stream(req: AskRequest):
        # The guard needs the full answer, so we verify first and then stream the verified text.
        result = system.ask(req.question, req.topic)

        def events():
            for word in result.answer.split():
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
            yield f"event: done\ndata: {json.dumps(result.to_dict())}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    return app
