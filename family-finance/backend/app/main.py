from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.db import init_db
from app.routers import accounts, categories, dashboard, networth, statements, transactions

app = FastAPI(title="Family Finance Tracker", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(networth.router)
app.include_router(statements.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
