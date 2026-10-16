"""Helpdesk API: tickets and ticket statistics over the live neerus.tickets collection."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import ExecutionTimeout, NetworkTimeout, OperationFailure, PyMongoError, ServerSelectionTimeoutError

from config import get_settings
from database import get_tickets
from routers import stats, tickets

app = FastAPI(title="Helpdesk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(tickets.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.exception_handler(PyMongoError)
async def database_error(_: Request, exc: PyMongoError):
    """Map database failures to generic responses; never leak URIs, credentials or details."""
    if isinstance(exc, (ServerSelectionTimeoutError,)):
        return JSONResponse({"detail": "Database unavailable."}, status_code=503)
    if isinstance(exc, (NetworkTimeout, ExecutionTimeout)):
        return JSONResponse({"detail": "Database timed out."}, status_code=504)
    if isinstance(exc, OperationFailure) and exc.code in (13, 18):
        return JSONResponse({"detail": "Database access denied."}, status_code=403)
    return JSONResponse({"detail": "Database error."}, status_code=503)


@app.exception_handler(RuntimeError)
async def config_error(_: Request, __: RuntimeError):
    return JSONResponse({"detail": "Server is not configured."}, status_code=503)


@app.get("/api/health")
def health():
    try:
        count = get_tickets().estimated_document_count()
    except Exception:
        return JSONResponse({"status": "degraded", "database": "unreachable"}, status_code=503)
    return {"status": "ok", "tickets": count}
