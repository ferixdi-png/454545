"""
Integration of payments with generation flow.
Ensures charges are only committed on success.
Handles FREE tier models (no charge).
"""
import logging
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from app.payments.charges import ChargeManager, get_charge_manager
from app.kie.generator import KieGenerator
from app.utils.metrics import track_generation
from app.pricing.free_models import is_free_model

logger = logging.getLogger(__name__)


async def generate_with_payment(
    model_id: str,
    user_inputs: Dict[str, Any],
    user_id: int,
    amount: float,
    progress_callback: Optional[Any] = None,
    timeout: int = 300,
    task_id: Optional[str] = None,
    reserve_balance: bool = False,
    charge_manager: Optional[ChargeManager] = None
) -> Dict[str, Any]:
    """
    Generate with payment safety guarantees:
    - FREE models: no charge
    - Paid models: charge only on success, auto-refund on fail/timeout
    
    Args:
        model_id: Model identifier
        user_inputs: User inputs
        user_id: User identifier
        amount: Charge amount (ignored for FREE models)
        progress_callback: Progress callback
        timeout: Generation timeout
        
    Returns:
        Result dict with generation and payment info
    """
    # Check if model is FREE (TOP-5 cheapest)
    if is_free_model(model_id):
        logger.info(f"🆓 Model {model_id} is FREE - skipping payment")
        generator = KieGenerator()
        gen_result = await generator.generate(model_id, user_inputs, progress_callback, timeout)
        return {
            **gen_result,
            'charge_task_id': None,
            'payment_status': 'free_tier',
            'payment_message': '🆓 FREE модель - генерация бесплатна'
        }
    
    # Paid model - proceed with charging
    charge_manager = charge_manager or get_charge_manager()
    generator = KieGenerator()
    charge_task_id = task_id or f"charge_{user_id}_{model_id}_{uuid4().hex[:8]}"
    
    # Create pending charge
    charge_result = await charge_manager.create_pending_charge(
        task_id=charge_task_id,
        user_id=user_id,
        amount=amount,
        model_id=model_id,
        reserve_balance=reserve_balance
    )
    
    if charge_result['status'] == 'already_committed':
        # Already paid, just generate
        gen_result = await generator.generate(model_id, user_inputs, progress_callback, timeout)
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': 'already_committed',
            'payment_message': 'Оплата уже подтверждена'
        }
    if charge_result['status'] == 'insufficient_balance':
        return {
            'success': False,
            'message': '❌ Недостаточно средств. Пополните баланс и попробуйте снова.',
            'result_urls': [],
            'result_object': None,
            'error_code': 'INSUFFICIENT_BALANCE',
            'error_message': 'Insufficient balance',
            'task_id': None,
            'charge_task_id': charge_task_id,
            'payment_status': charge_result['status'],
            'payment_message': charge_result['message']
        }
    
    # Generate
    start_time = time.time()
    gen_result = await generator.generate(model_id, user_inputs, progress_callback, timeout)
    duration = time.time() - start_time
    
    # Track metrics
    success = gen_result.get('success', False)
    await track_generation(
        model_id=model_id,
        success=success,
        duration=duration,
        price_rub=amount if success else 0.0
    )
    
    # Determine task_id from generation (if available)
    # Commit or release charge based on generation result
    if gen_result.get('success'):
        # SUCCESS: Commit charge
        commit_result = await charge_manager.commit_charge(charge_task_id)
        # Add to history
        result_urls = gen_result.get('result_urls', [])
        result_text = '\n'.join(result_urls) if result_urls else 'Success'
        charge_manager.add_to_history(user_id, model_id, user_inputs, result_text, True)
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': commit_result['status'],
            'payment_message': commit_result['message']
        }
    else:
        # FAIL/TIMEOUT: Release charge (auto-refund)
        release_result = await charge_manager.release_charge(
            charge_task_id,
            reason=gen_result.get('error_code', 'generation_failed')
        )
        # Add to history
        error_msg = gen_result.get('message', 'Failed')
        charge_manager.add_to_history(user_id, model_id, user_inputs, error_msg, False)
        return {
            **gen_result,
            'charge_task_id': charge_task_id,
            'payment_status': release_result['status'],
            'payment_message': release_result['message']
        }
