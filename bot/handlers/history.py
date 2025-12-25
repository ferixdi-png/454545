"""
History handlers - показ истории генераций и транзакций.
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.payments.pricing import format_price_rub

logger = logging.getLogger(__name__)

router = Router(name="history")

# Global database service
_db_service = None


def set_database_service(db_service):
    """Set database service for handlers."""
    global _db_service
    _db_service = db_service


def _get_db_service():
    """Get database service or None."""
    return _db_service


@router.callback_query(F.data == "history:main")
async def cb_history_main(callback: CallbackQuery, state: FSMContext):
    """Show generation history with visual gallery."""
    await state.clear()
    
    db_service = _get_db_service()
    if not db_service:
        await callback.answer("⚠️ База данных недоступна", show_alert=True)
        return
    
    from app.database.services import JobService
    
    job_service = JobService(db_service)
    jobs = await job_service.list_user_jobs(callback.from_user.id, limit=10)
    
    text = "📜 <b>История генераций</b>\n\n"
    
    if not jobs:
        text += "<i>У вас пока нет генераций</i>\n\n"
        text += "💡 Попробуйте создать что-то в разделе ⚡ Быстрые действия!"
    else:
        # Count by status
        succeeded = sum(1 for j in jobs if j.get("status") == "succeeded")
        failed = sum(1 for j in jobs if j.get("status") == "failed")
        running = sum(1 for j in jobs if j.get("status") in ("running", "queued"))
        
        text += f"✅ Успешно: {succeeded} | ❌ Ошибки: {failed} | 🔄 В работе: {running}\n\n"
        
        # Show recent jobs with clickable details
        text += "<b>Последние генерации:</b>\n"
        for idx, job in enumerate(jobs[:5], 1):
            model_id = job.get("model_id", "unknown")
            status = job.get("status", "unknown")
            price = job.get("price_rub", 0)
            created = job.get("created_at")
            
            # Status emoji
            status_emoji = {
                "succeeded": "✅",
                "failed": "❌",
                "running": "🔄",
                "queued": "⏱️",
            }.get(status, "•")
            
            # Format date
            date_str = created.strftime("%d.%m %H:%M") if created else "—"
            
            # Short model name
            model_name = model_id.split('/')[-1] if '/' in model_id else model_id
            
            text += f"\n{idx}. {status_emoji} {model_name} ({format_price_rub(price)}) - {date_str}"
    
    # Build keyboard with gallery option
    keyboard_rows = []
    
    if jobs and any(j.get("status") == "succeeded" for j in jobs):
        keyboard_rows.append([
            InlineKeyboardButton(text="🖼️ Просмотр галереи", callback_data="history:gallery")
        ])
    
    keyboard_rows.append([
        InlineKeyboardButton(text="📊 История транзакций", callback_data="history:transactions")
    ])
    keyboard_rows.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="balance:main")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "history:gallery")
async def cb_history_gallery(callback: CallbackQuery, state: FSMContext):
    """Show visual gallery of successful generations."""
    await callback.answer()
    
    db_service = _get_db_service()
    if not db_service:
        await callback.answer("⚠️ База данных недоступна", show_alert=True)
        return
    
    from app.database.services import JobService
    
    job_service = JobService(db_service)
    jobs = await job_service.list_user_jobs(callback.from_user.id, limit=20)
    
    # Filter only succeeded jobs
    succeeded_jobs = [j for j in jobs if j.get("status") == "succeeded"]
    
    if not succeeded_jobs:
        await callback.message.edit_text(
            "🖼️ <b>Галерея генераций</b>\n\n"
            "<i>У вас пока нет завершённых генераций</i>\n\n"
            "💡 Создайте что-то крутое через ⚡ Быстрые действия!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="history:main")]
            ])
        )
        return
    
    # Build gallery text
    text = "🖼️ <b>Галерея ваших генераций</b>\n\n"
    text += f"Всего успешных работ: {len(succeeded_jobs)}\n\n"
    
    # Show up to 5 recent succeeded jobs with details
    for idx, job in enumerate(succeeded_jobs[:5], 1):
        job_id = job.get("id")
        model_id = job.get("model_id", "unknown")
        price = job.get("price_rub", 0)
        created = job.get("created_at")
        
        model_name = model_id.split('/')[-1] if '/' in model_id else model_id
        date_str = created.strftime("%d.%m.%Y %H:%M") if created else "—"
        
        text += (
            f"{idx}. <b>{model_name}</b>\n"
            f"   💰 {format_price_rub(price)} | 📅 {date_str}\n\n"
        )
    
    if len(succeeded_jobs) > 5:
        text += f"<i>...и ещё {len(succeeded_jobs) - 5} работ</i>\n"
    
    # Buttons to navigate
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Создать ещё", callback_data="quick:menu")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="history:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "history:transactions")
async def cb_history_transactions(callback: CallbackQuery, state: FSMContext):
    """Show transaction history."""
    db_service = _get_db_service()
    if not db_service:
        await callback.answer("⚠️ База данных недоступна", show_alert=True)
        return
    
    from app.database.services import WalletService
    from decimal import Decimal
    
    wallet_service = WalletService(db_service)
    history = await wallet_service.get_history(callback.from_user.id, limit=20)
    
    text = "📊 <b>История транзакций</b>\n\n"
    
    if not history:
        text += "<i>У вас пока нет транзакций</i>"
    else:
        for entry in history:
            kind = entry.get("kind", "")
            amount = entry.get("amount_rub", Decimal("0.00"))
            created = entry.get("created_at")
            ref = entry.get("ref", "")
            
            # Format kind
            kind_emoji = {
                "topup": "💵",
                "charge": "💸",
                "refund": "↩️",
                "hold": "🔒",
                "release": "🔓"
            }.get(kind, "•")
            
            kind_text = {
                "topup": "Пополнение",
                "charge": "Списание",
                "refund": "Возврат",
                "hold": "Резерв",
                "release": "Освобождение"
            }.get(kind, kind)
            
            # Format date
            date_str = created.strftime("%d.%m %H:%M") if created else "—"
            
            text += (
                f"\n{kind_emoji} {kind_text}: {format_price_rub(amount)}\n"
                f"  Дата: {date_str}\n"
            )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к генерациям", callback_data="history:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# Export router
__all__ = ["router", "set_database_service"]
