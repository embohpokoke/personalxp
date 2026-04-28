from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="personal-xp")


@app.get("/api/v1/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})
