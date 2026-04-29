from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import lifespan
from app.routers import auth, budgets, categories, receipts, reports, transactions


app = FastAPI(title="personal-xp", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(budgets.router)
app.include_router(categories.router)
app.include_router(reports.router)
app.include_router(transactions.router)
app.include_router(receipts.router)

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/icons", StaticFiles(directory=FRONTEND_DIR / "icons"), name="icons")


@app.get("/api/v1/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/app.js", include_in_schema=False)
async def app_js() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
async def styles_css() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")


@app.get("/manifest.json", include_in_schema=False)
async def manifest() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{path:path}", include_in_schema=False)
async def spa_fallback(path: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
