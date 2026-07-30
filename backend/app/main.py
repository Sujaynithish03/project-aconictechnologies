"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, chat, documents
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import init_db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Importing `base` registers every model on Base.metadata before create_all.
    import app.db.base  # noqa: F401,PLC0415

    if settings.auto_init_db:
        try:
            init_db()
            logger.info("Database ready")
        except Exception:
            # Let the app boot so /health can report; DB calls will surface the error.
            logger.exception("Database initialisation failed")
    else:
        # Serverless: the schema is created once out of band, not on every
        # cold start. See scripts/init_db.py.
        logger.info("Skipping schema init (AUTO_INIT_DB=false)")

    if not settings.llm_configured:
        logger.warning("GEMINI_API_KEY is not set — /ask and ingestion will fail")

    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Upload PDF, DOCX, or TXT documents and ask questions answered from "
        "their contents using retrieval-augmented generation.\n\n"
        "Authenticate via `POST /signup` or `POST /login`, then send the "
        "returned token as `Authorization: Bearer <token>`."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Paths are mounted at the root to match the specified API contract exactly.
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/health", tags=["system"], summary="Liveness and dependency check")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_configured": settings.llm_configured,
    }


@app.get("/", tags=["system"], include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs", "health": "/health"}
