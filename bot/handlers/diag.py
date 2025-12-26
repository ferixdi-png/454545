"""
Admin diagnostics command with comprehensive webhook info.
"""
import os
from datetime import datetime
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.utils.runtime_state import runtime_state

router = Router(name="diag")


@router.message(Command("diag"))
async def cmd_diag(message: Message) -> None:
    """Comprehensive diagnostics for admin (bot state + webhook health)."""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id and message.from_user and message.from_user.id != admin_id:
        await message.answer("⛔ Доступ запрещён")
        return

    bot_mode = runtime_state.bot_mode
    storage_mode = runtime_state.storage_mode
    lock_status = runtime_state.lock_acquired
    instance_id = runtime_state.instance_id
    last_start_time = runtime_state.last_start_time or "unknown"

    # Get comprehensive webhook info
    webhook_info = await message.bot.get_webhook_info()
    
    # Format last error timestamp
    last_error_str = "none"
    if webhook_info.last_error_date:
        try:
            error_dt = datetime.fromtimestamp(webhook_info.last_error_date)
            last_error_str = error_dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            last_error_str = str(webhook_info.last_error_date)
    
    # Build diagnostic message
    text = (
        "🩺 <b>Диагностика бота</b>\n\n"
        "<b>🤖 Bot State:</b>\n"
        f"  • Mode: {bot_mode}\n"
        f"  • Storage: {storage_mode}\n"
        f"  • Instance: {instance_id}\n"
        f"  • Lock: {lock_status}\n"
        f"  • Started: {last_start_time}\n\n"
        "<b>🌐 Webhook Info:</b>\n"
        f"  • URL: <code>{webhook_info.url or 'NOT SET'}</code>\n"
        f"  • Pending updates: {webhook_info.pending_update_count}\n"
        f"  • Max connections: {webhook_info.max_connections or 'default'}\n"
        f"  • IP address: {webhook_info.ip_address or 'N/A'}\n"
        f"  • Custom cert: {'✅' if webhook_info.has_custom_certificate else '❌'}\n\n"
    )
    
    # Add error info if present
    if webhook_info.last_error_date or webhook_info.last_error_message:
        text += (
            "<b>⚠️ Last Error:</b>\n"
            f"  • Date: {last_error_str}\n"
            f"  • Message: <code>{webhook_info.last_error_message or 'N/A'}</code>\n\n"
        )
    else:
        text += "<b>✅ No webhook errors</b>\n\n"
    
    # Health status
    if webhook_info.url and webhook_info.pending_update_count == 0:
        text += "🟢 <b>Status: HEALTHY</b>"
    elif not webhook_info.url:
        text += "🔴 <b>Status: NO WEBHOOK</b>"
    elif webhook_info.pending_update_count > 0:
        text += f"🟡 <b>Status: {webhook_info.pending_update_count} pending updates</b>"
    
    await message.answer(text, parse_mode="HTML")
