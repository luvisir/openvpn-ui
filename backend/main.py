from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import connections, logs, system, users

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="OpenVPN UI", version="0.1.0")
    app.include_router(system.router, prefix="/api/system", tags=["system"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(connections.router, prefix="/api/connections", tags=["connections"])
    app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
    mount_frontend(app)
    return app


def mount_frontend(app: FastAPI) -> None:
    assets_dir = FRONTEND_DIST / "assets"
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.exists():
        return

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{path:path}", include_in_schema=False)
    def frontend_fallback(path: str) -> FileResponse:
        return FileResponse(index_file)


app = create_app()
