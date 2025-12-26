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
    \"\"\"Comprehensive diagnostics for admin (bot state + webhook health).\"\"\"
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id and message.from_user and message.from_user.id != admin_id:
        await message.answer("\u26d4 \u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043f\u0440\u0435\u0449\u0435\u043d")
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
        "\ud83e\ude7a <b>\u0414\u0438\u0430\u0433\u043d\u043e\u0441\u0442\u0438\u043a\u0430 \u0431\u043e\u0442\u0430</b>\\n\\n"
        "<b>\ud83e\udd16 Bot State:</b>\\n"
        f"  \u2022 Mode: {bot_mode}\\n"
        f"  \u2022 Storage: {storage_mode}\\n"
        f"  \u2022 Instance: {instance_id}\\n"
        f"  \u2022 Lock: {lock_status}\\n"
        f"  \u2022 Started: {last_start_time}\\n\\n"
        "<b>\ud83c\udf10 Webhook Info:</b>\\n"
        f"  \u2022 URL: <code>{webhook_info.url or 'NOT SET'}</code>\\n"
        f"  \u2022 Pending updates: {webhook_info.pending_update_count}\\n"
        f"  \u2022 Max connections: {webhook_info.max_connections or 'default'}\\n"
        f"  \u2022 IP address: {webhook_info.ip_address or 'N/A'}\\n"
        f"  \u2022 Custom cert: {'\u2705' if webhook_info.has_custom_certificate else '\u274c'}\\n\\n"
    )
    
    # Add error info if present
    if webhook_info.last_error_date or webhook_info.last_error_message:
        text += (
            "<b>\u26a0\ufe0f Last Error:</b>\\n"
            f"  \u2022 Date: {last_error_str}\\n"
            f"  \u2022 Message: <code>{webhook_info.last_error_message or 'N/A'}</code>\\n\\n"
        )
    else:
        text += "<b>\u2705 No webhook errors</b>\\n\\n"
    
    # Health status
    if webhook_info.url and webhook_info.pending_update_count == 0:
        text += "\ud83d\udfe2 <b>Status: HEALTHY</b>"
    elif not webhook_info.url:
        text += "\ud83d\udd34 <b>Status: NO WEBHOOK</b>"
    elif webhook_info.pending_update_count > 0:
        text += f"\ud83d\udfe1 <b>Status: {webhook_info.pending_update_count} pending updates</b>"
    
    await message.answer(text, parse_mode="HTML")
