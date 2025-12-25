"""
Admin diagnostics command.
"""
import os
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.utils.runtime_state import runtime_state

router = Router(name="diag")


@router.message(Command("diag"))
async def cmd_diag(message: Message) -> None:
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id and message.from_user and message.from_user.id != admin_id:
        await message.answer("⛔ Доступ запрещен")
        return

    bot_mode = runtime_state.bot_mode
    storage_mode = runtime_state.storage_mode
    lock_status = runtime_state.lock_acquired
    instance_id = runtime_state.instance_id
    last_start_time = runtime_state.last_start_time or "unknown"

    webhook_info = await message.bot.get_webhook_info()

    await message.answer(
        "🩺 Диагностика\n\n"
        f"BOT_MODE: {bot_mode}\n"
        f"STORAGE_MODE: {storage_mode}\n"
        f"LOCK_STATUS: {lock_status}\n"
        f"INSTANCE_ID: {instance_id}\n"
        f"LAST_START_TIME: {last_start_time}\n\n"
        "WebhookInfo:\n"
        f"- url: {webhook_info.url}\n"
        f"- has_custom_certificate: {webhook_info.has_custom_certificate}\n"
        f"- pending_update_count: {webhook_info.pending_update_count}\n"
    )
