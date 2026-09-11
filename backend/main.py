from fastapi import FastAPI

from backend.routers import connections, logs, system, users


def create_app() -> FastAPI:
    app = FastAPI(title="OpenVPN UI", version="0.1.0")
    app.include_router(system.router, prefix="/api/system", tags=["system"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(connections.router, prefix="/api/connections", tags=["connections"])
    app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
    return app


app = create_app()
