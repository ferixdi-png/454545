"""Generation callback handler - resolves short keys and starts wizard."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.ui.callback_registry import resolve_key
from app.ui.catalog import get_model

logger = logging.getLogger(__name__)
router = Router(name="gen_handler")


@router.callback_query(F.data.startswith("gen:"))
async def gen_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Handle gen: callbacks (short key format).
    
    Resolves short key → model_id, then starts wizard.
    """
    await callback.answer()
    
    short_key = callback.data
    model_id = resolve_key(short_key)
    
    if not model_id:
        logger.error(f"Failed to resolve gen key: {short_key}")
        await callback.message.edit_text("❌ Модель не найдена", parse_mode="HTML")
        return
    
    # Load model
    model = get_model(model_id)
    if not model:
        logger.error(f"Model not found: {model_id}")
        await callback.message.edit_text("❌ Модель не найдена", parse_mode="HTML")
        return
    
    # Start wizard flow
    from bot.flows.wizard import start_wizard
    await start_wizard(callback, state, model)
