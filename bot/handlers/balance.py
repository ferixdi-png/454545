"""
Balance and wallet handlers - полная интеграция с DatabaseService.
"""
import decimal
import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.payments.pricing import format_price_rub

logger = logging.getLogger(__name__)

router = Router(name="balance")

# Global database service
_db_service = None


def set_database_service(db_service):
    """Set database service for handlers."""
    global _db_service
    _db_service = db_service


def _get_db_service():
    """Get database service or None."""
    return _db_service


class TopupStates(StatesGroup):
    """FSM states for topup."""
    enter_amount = State()
    confirm_payment = State()


@router.callback_query(F.data == "balance:main")
async def cb_balance_main(callback: CallbackQuery, state: FSMContext):
    """Show balance and history."""
    await state.clear()
    
    db_service = _get_db_service()
    if not db_service:
        await callback.answer("⚠️ База данных недоступна", show_alert=True)
        return
    
    from app.database.services import UserService, WalletService
    
    user_service = UserService(db_service)
    wallet_service = WalletService(db_service)
    
    # Ensure user exists
    await user_service.get_or_create(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    # Get balance
    balance_data = await wallet_service.get_balance(callback.from_user.id)
    balance = balance_data.get("balance_rub", Decimal("0.00"))
    hold = balance_data.get("hold_rub", Decimal("0.00"))
    
    # Get recent history
    history = await wallet_service.get_history(callback.from_user.id, limit=5)
    
    text = (
        f"💳 <b>Ваш баланс</b>\n\n"
        f"💰 Доступно: {format_price_rub(balance)}\n"
        f"🔒 В резерве: {format_price_rub(hold)}\n"
    )
    
    if history:
        text += "\n<b>Последние операции:</b>\n"
        for entry in history:
            kind = entry.get("kind", "")
            amount = entry.get("amount_rub", Decimal("0.00"))
            
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
            
            text += f"\n{kind_emoji} {kind_text}: {format_price_rub(amount)}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Пополнить", callback_data="balance:topup")],
        [InlineKeyboardButton(text="📜 Вся история", callback_data="history:main")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="marketing:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "balance:topup")
async def cb_balance_topup(callback: CallbackQuery, state: FSMContext):
    """Start topup flow."""
    text = (
        f"💵 <b>Пополнение баланса</b>\n\n"
        f"Введите сумму пополнения в рублях:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100₽", callback_data="topup:amount:100"),
            InlineKeyboardButton(text="500₽", callback_data="topup:amount:500")
        ],
        [
            InlineKeyboardButton(text="1000₽", callback_data="topup:amount:1000"),
            InlineKeyboardButton(text="5000₽", callback_data="topup:amount:5000")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="balance:main")]
    ])
    
    await state.set_state(TopupStates.enter_amount)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("topup:amount:"))
async def cb_topup_preset(callback: CallbackQuery, state: FSMContext):
    """Quick topup with preset amount."""
    amount = int(callback.data.split(":", 2)[2])
    await _show_payment_instructions(callback, state, Decimal(amount))


@router.message(TopupStates.enter_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    """Process custom topup amount."""
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля")
            return
        if amount > 100000:
            await message.answer("❌ Максимальная сумма: 100 000₽")
            return
    except (ValueError, decimal.InvalidOperation) as e:
        # MASTER PROMPT: No bare except - specific exception types for Decimal parsing
        logger.error(f"Failed to parse amount from '{message.text}': {e}")
        await message.answer("❌ Введите корректную сумму (например: 500)")
        return
    
    await _show_payment_instructions_message(message, state, amount)


async def _show_payment_instructions(callback: CallbackQuery, state: FSMContext, amount: Decimal):
    """Show payment instructions (callback version)."""
    import os
    
    # Payment credentials from ENV
    bank = os.getenv("PAYMENT_BANK", "Сбербанк")
    card = os.getenv("PAYMENT_CARD", "2202 2000 0000 0000")
    holder = os.getenv("PAYMENT_CARD_HOLDER", "IVAN IVANOV")
    phone = os.getenv("PAYMENT_PHONE", "+7 900 000 00 00")
    
    text = (
        f"💳 <b>Пополнение на {format_price_rub(amount)}</b>\n\n"
        f"<b>Реквизиты для оплаты:</b>\n"
        f"🏦 Банк: {bank}\n"
        f"💳 Карта: <code>{card}</code>\n"
        f"👤 Получатель: {holder}\n"
        f"📱 Телефон: <code>{phone}</code>\n\n"
        f"<b>Важно:</b>\n"
        f"• Переводите точную сумму: {format_price_rub(amount)}\n"
        f"• После оплаты нажмите кнопку ниже\n"
        f"• Пришлите скриншот чека для проверки\n\n"
        f"<i>Обработка занимает до 5 минут</i>"
    )
    
    await state.update_data(topup_amount=float(amount))
    await state.set_state(TopupStates.confirm_payment)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="topup:paid")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="balance:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def _show_payment_instructions_message(message: Message, state: FSMContext, amount: Decimal):
    """Show payment instructions (message version)."""
    import os
    
    bank = os.getenv("PAYMENT_BANK", "Сбербанк")
    card = os.getenv("PAYMENT_CARD", "2202 2000 0000 0000")
    holder = os.getenv("PAYMENT_CARD_HOLDER", "IVAN IVANOV")
    phone = os.getenv("PAYMENT_PHONE", "+7 900 000 00 00")
    
    text = (
        f"💳 <b>Пополнение на {format_price_rub(amount)}</b>\n\n"
        f"<b>Реквизиты для оплаты:</b>\n"
        f"🏦 Банк: {bank}\n"
        f"💳 Карта: <code>{card}</code>\n"
        f"👤 Получатель: {holder}\n"
        f"📱 Телефон: <code>{phone}</code>\n\n"
        f"<b>Важно:</b>\n"
        f"• Переводите точную сумму: {format_price_rub(amount)}\n"
        f"• После оплаты нажмите кнопку ниже\n"
        f"• Пришлите скриншот чека для проверки\n\n"
        f"<i>Обработка занимает до 5 минут</i>"
    )
    
    await state.update_data(topup_amount=float(amount))
    await state.set_state(TopupStates.confirm_payment)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="topup:paid")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="balance:main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "topup:paid")
async def cb_topup_paid(callback: CallbackQuery, state: FSMContext):
    """User claims they paid - ask for receipt."""
    text = (
        f"📸 <b>Подтверждение платежа</b>\n\n"
        f"Пришлите скриншот чека или квитанции.\n\n"
        f"<i>После проверки средства будут зачислены автоматически</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="balance:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(TopupStates.confirm_payment, F.photo)
async def process_receipt(message: Message, state: FSMContext):
    """Process receipt photo."""
    data = await state.get_data()
    amount = Decimal(str(data.get("topup_amount", 0)))
    
    await state.clear()
    
    db_service = _get_db_service()
    if db_service:
        from app.database.services import WalletService
        import uuid
        
        wallet_service = WalletService(db_service)
        
        # Generate unique ref for this topup
        ref = f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}"
        
        # Add to balance (idempotent)
        success = await wallet_service.topup(
            message.from_user.id,
            amount,
            ref,
            meta={"photo_id": message.photo[-1].file_id, "status": "manual_review"}
        )
        
        if success:
            text = (
                f"✅ <b>Заявка принята!</b>\n\n"
                f"Сумма: {format_price_rub(amount)}\n"
                f"Номер заявки: <code>{ref}</code>\n\n"
                f"Средства будут зачислены после проверки (обычно до 5 минут)"
            )
        else:
            text = (
                f"⚠️ <b>Заявка уже обработана</b>\n\n"
                f"Эта заявка уже была принята ранее."
            )
    else:
        text = (
            f"⚠️ <b>База данных недоступна</b>\n\n"
            f"Попробуйте позже"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Мой баланс", callback_data="balance:main")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="marketing:main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


# Export router
__all__ = ["router", "set_database_service"]
