import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nomnom.api.routes import router
from nomnom.config import settings
from nomnom.db.connection import run_migrations
from nomnom.repositories.submission_repository import SubmissionRepository
from nomnom.services.ingestion_service import IngestionService


def _configure_logging() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("NomNom receiver starting | db=%s | port=%s", settings.DB_PATH, settings.PORT)
    run_migrations(settings.DB_PATH)
    app.state.repository = SubmissionRepository(settings.DB_PATH)
    app.state.ingestion_service = IngestionService(app.state.repository)
    yield
    logger.info("NomNom receiver shutting down")


def create_app() -> FastAPI:
    app = FastAPI(title="NomNom Receiver", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger(__name__).exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("nomnom.main:app", host="0.0.0.0", port=settings.PORT, log_level=settings.LOG_LEVEL)
