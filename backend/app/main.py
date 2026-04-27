import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import articles, chat, documents
from app.core.config import get_settings
from app.core.deps import engine
from app.models.db import Base

settings = get_settings()

# Ensure media directory exists before StaticFiles mount (mount happens at import time)
os.makedirs(settings.media_root, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure SQLite data directory exists
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url[len("sqlite:///"):]
        dir_part = os.path.dirname(os.path.abspath(db_path))
        if dir_part:
            os.makedirs(dir_part, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Data Automation RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files and page previews; works in both DEBUG and production
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

app.include_router(documents.router, prefix="/api")
app.include_router(articles.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/")
def health():
    return {"status": "ok", "service": "data-automation-backend"}
