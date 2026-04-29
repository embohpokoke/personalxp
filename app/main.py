from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db import lifespan
from app.routers import auth, categories, receipts, transactions


app = FastAPI(title="personal-xp", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(receipts.router)


@app.get("/api/v1/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})
