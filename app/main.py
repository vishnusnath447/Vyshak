from fastapi import FastAPI

from app.api.v1.endpoints import router as api_router
from app.db.session import Base, engine


def create_app() -> FastAPI:
    app = FastAPI(title="Vyshak Demo API")
    app.include_router(api_router)
    return app


app = create_app()

# create tables automatically for this demo (SQLite)
Base.metadata.create_all(bind=engine)
