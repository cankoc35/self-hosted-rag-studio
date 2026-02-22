from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from core import db
from generation import router as generation_router
from ingestion import router as ingestion_router
from models import router as models_router
from retrieval import router as retrieval_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Initialize the DB pool once per process.
    await db.init_pool()
    try:
        yield
    finally:
        await db.close_pool()


app = FastAPI(lifespan=lifespan)

# Allow local frontend dev server to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router, tags=["ingestion"])
app.include_router(retrieval_router, tags=["retrieval"])
app.include_router(generation_router, tags=["generation"])
app.include_router(models_router.router, tags=["models"])
app.include_router(auth_router.router, tags=["auth"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def root() -> dict:
    return {"message": "local-rag-stack api"}
