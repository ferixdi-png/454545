"""
Integration of payments with generation flow.
Ensures charges are only committed on success.
Handles FREE tier models (no charge).
"""
import logging
from app.utils.trace import TraceContext, get_request_id
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from app.payments.charges import ChargeManager, get_charge_manager
from app.kie.generator import KieGenerator
from app.utils.metrics import track_generation
from app.pricing.free_models import is_free_model
from app.database.services import UserService
from app.utils.config import REFERRAL_MAX_RUB

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
    # Request-scoped trace (correlation id for logs)
    with TraceContext(user_id=user_id, model_id=model_id, request_id=(get_request_id() if get_request_id() != '-' else None)) as _trace:
        logger.info(f"▶️ generate_with_payment start amount={amount} reserve_balance={reserve_balance} timeout={timeout}s")
        
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
        
        # Paid model - proceed with charging (or apply referral-free uses if available)
        charge_manager = charge_manager or get_charge_manager()
        generator = KieGenerator()
        
        # Referral-free: limited бесплатные генерации за приглашения
        referral_used = False
        referral_uses_left: Optional[int] = None
        try:
            db = getattr(charge_manager, "db_service", None)
            if db is not None and amount <= REFERRAL_MAX_RUB:
                user_service = UserService(db)
                meta = await user_service.get_metadata(user_id)
                referral_uses_left = int(meta.get("referral_free_uses", 0) or 0)
                if referral_uses_left > 0:
                    await user_service.increment_metadata_counter(user_id, "referral_free_uses", -1, min_value=0)
                    referral_used = True
                    referral_uses_left -= 1
                    logger.info(
                        f"🎁 Referral-free used: user={user_id} model={model_id} amount={amount:.2f} cap={REFERRAL_MAX_RUB:.2f} left={referral_uses_left}"
                    )
        except Exception as e:
            logger.warning(f"Referral-free precheck failed (continuing with normal charging): {e}")
        
        if referral_used:
            start_time = time.time()
            gen_result = await generator.generate(model_id, user_inputs, progress_callback, timeout)
            duration = time.time() - start_time
        
            success = gen_result.get('success', False)
            await track_generation(
                model_id=model_id,
                success=success,
                duration=duration,
                price_rub=0.0
            )
        
            if success:
                result_urls = gen_result.get('result_urls', [])
                result_text = '\n'.join(result_urls) if result_urls else 'Success'
                charge_manager.add_to_history(user_id, model_id, user_inputs, result_text, True)
                return {
                    **gen_result,
                    'charge_task_id': None,
                    'payment_status': 'referral_free',
                    'payment_message': f'🎁 Бесплатная генерация за приглашения (осталось: {referral_uses_left})'
                }
        
            # FAIL/TIMEOUT: return referral use back
            try:
                db = getattr(charge_manager, "db_service", None)
                if db is not None:
                    await UserService(db).increment_metadata_counter(user_id, "referral_free_uses", +1)
            except Exception as e:
                logger.warning(f"Failed to restore referral-free use after failure: {e}")
        
            error_msg = gen_result.get('message', 'Failed')
            charge_manager.add_to_history(user_id, model_id, user_inputs, error_msg, False)
            return {
                **gen_result,
                'charge_task_id': None,
                'payment_status': 'referral_free_failed',
                'payment_message': '⚠️ Генерация не удалась, бесплатная попытка возвращена'
            }
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
