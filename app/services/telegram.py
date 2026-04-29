import logging

import httpx

from app.config import Settings, get_settings


logger = logging.getLogger("uvicorn.error")


async def send_budget_alert(message: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    chat_ids = [
        chat_id
        for chat_id in (settings.telegram_chat_id_primary, settings.telegram_chat_id_secondary)
        if chat_id
    ]

    if settings.telegram_dry_run or not settings.telegram_bot_token or not chat_ids:
        logger.warning("telegram dry-run budget alert: %s", message)
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        for chat_id in chat_ids:
            await client.post(url, json={"chat_id": chat_id, "text": message})
