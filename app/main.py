import logging
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import jobs
from app.course.router import router as course_router
from app.db.session import DBSession, dispose_engine
from app.errors import ConflictError, NotFoundError
from app.llm import LLMError, get_llm
from app.llm.exceptions import LLMConfigurationError, LLMRateLimitError, LLMRefusalError
from app.settings import settings
from app.tutor.router import router as tutor_router

try:
    __version__ = version("marginalia")
except PackageNotFoundError:
    __version__ = "0.0.0"

meta_router = APIRouter(prefix="/api", tags=["meta"])


@meta_router.get("/health")
async def health(db: DBSession) -> dict:
    await db.exec(text("select 1"))
    return {"status": "ok", "version": __version__}


@meta_router.get("/config")
async def config() -> dict:
    """What the UI needs to know about the configured model."""
    llm = get_llm()
    return {
        "provider": llm.name,
        "model": llm.model,
        "research": settings.RESEARCH_BACKEND == "web" and llm.supports_web_search,
        "demo": llm.name == "fake",
    }


def _llm_error_status(error: LLMError) -> int:
    if isinstance(error, LLMConfigurationError):
        return 503
    if isinstance(error, LLMRateLimitError):
        return 429
    if isinstance(error, LLMRefusalError):
        return 422
    return 502


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await jobs.cancel_all()
    await dispose_engine()


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built single-page app (frontend/dist) from the same origin as the API."""
    dist = settings.FRONTEND_DIST_DIR.resolve()
    index = dist / "index.html"
    if not index.is_file():

        @app.get("/", include_in_schema=False)
        async def frontend_missing() -> dict:
            return {
                "message": "The web UI isn't built. Run `npm run build` in frontend/, or use the "
                "Vite dev server (npm run dev) on port 5173. The API is under /api; docs at /docs."
            }

        return

    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def single_page_app(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        return FileResponse(index)  # Client-side routes all load the app


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = FastAPI(title="Marginalia", version=__version__, lifespan=lifespan)

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(LLMError)
    async def llm_error(request: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(status_code=_llm_error_status(exc), content={"detail": str(exc)})

    app.include_router(meta_router)
    app.include_router(course_router)
    app.include_router(tutor_router)
    _mount_frontend(app)
    return app


app = create_app()
