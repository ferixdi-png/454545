"""
Payment charges with safety invariants:
- Charge only on generation success
- Auto-refund on fail/timeout/cancel
- Idempotent protection against double charges
- PRODUCTION: Integrated with PostgreSQL WalletService
"""
import logging
from typing import Dict, Any, Optional, Set
from datetime import datetime
from decimal import Decimal
import asyncio

logger = logging.getLogger(__name__)


class ChargeManager:
    """Manages payment charges with idempotency and safety guarantees."""
    
    def __init__(self, storage=None, db_service=None):
        """
        Initialize charge manager.
        
        Args:
            storage: Storage backend for tracking charges (legacy)
            db_service: DatabaseService for PostgreSQL integration (PRODUCTION)
        """
        self.storage = storage
        self.db_service = db_service
        
        # In-memory tracking for pending charges only (temporary state before commit)
        self._pending_charges: Dict[str, Dict[str, Any]] = {}  # task_id -> charge_info
        self._committed_charges: Set[str] = set()  # task_id set for idempotency
        self._released_charges: Set[str] = set()  # task_id set for released charges
        self._committed_info: Dict[str, Dict[str, Any]] = {}
        self._generation_history: Dict[int, list] = {}  # user_id -> [generation_record]
        
        # DEPRECATED: in-memory balances (only for fallback when DB unavailable)
        self._balances: Dict[int, float] = {}
        self._welcomed_users: Set[int] = set()
        
        # Cached WalletService (when DB is configured)
        self.wallet_service = self._get_wallet_service()
    
    def _get_wallet_service(self):
        """Get WalletService if DB is available."""
        if self.db_service:
            from app.database.services import WalletService
            return WalletService(self.db_service)
        return None

    async def get_user_balance(self, user_id: int) -> float:
        """Get user balance - from PostgreSQL if available, else in-memory fallback."""
        wallet_service = self.wallet_service
        if wallet_service:
            try:
                balance_data = await wallet_service.get_balance(user_id)
                balance_rub = balance_data.get("balance_rub", Decimal("0.00"))
                return float(balance_rub)
            except Exception as e:
                logger.warning(f"Failed to get balance from DB for user {user_id}: {e}, using in-memory fallback")
        
        # Fallback to in-memory
        return self._balances.get(user_id, 0.0)

    async def adjust_balance(self, user_id: int, delta: float) -> None:
        """Adjust balance - in PostgreSQL if available, else in-memory."""
        wallet_service = self.wallet_service
        if wallet_service:
            try:
                if delta > 0:
                    # Topup
                    ref = f"adjust_{user_id}_{datetime.now().isoformat()}"
                    await wallet_service.topup(user_id, Decimal(str(delta)), ref=ref, meta={"source": "adjust"})
                    logger.info(f"✅ DB topup: user={user_id}, delta={delta}₽")
                else:
                    # Charge (from hold - but we need to ensure funds are held first)
                    logger.warning(f"Negative adjustment ({delta}₽) for user {user_id} - not supported via adjust_balance")
                return
            except Exception as e:
                logger.error(f"Failed to adjust balance in DB for user {user_id}: {e}, using in-memory fallback")
        
        # Fallback to in-memory (supports negative adjustments with safety)
        current = self._balances.get(user_id, 0.0)
        new_balance = current + delta
        if new_balance < -1e-9:
            raise ValueError(f"Insufficient funds: user={user_id} balance={current} delta={delta}")
        self._balances[user_id] = new_balance

    async def ensure_welcome_credit(self, user_id: int, amount: float) -> bool:
        """Ensure welcome credit - in PostgreSQL if available."""
        wallet_service = self.wallet_service
        if wallet_service:
            try:
                from app.database.services import UserService
                user_service = UserService(self.db_service)
                
                # Check if user already exists
                user = await user_service.get_or_create(user_id, username=None, full_name=None)
                if user.get("created_just_now"):
                    # New user - give welcome credit
                    logger.info(f"User registered: user_id={user_id}, welcome_credit={amount}₽")
                    if amount > 0:
                        ref = f"welcome_{user_id}"
                        await wallet_service.topup(user_id, Decimal(str(amount)), ref=ref, meta={"source": "welcome"})
                        logger.info(f"✅ DB welcome credit: user={user_id}, amount={amount}₽")
                    return True
                else:
                    # Existing user
                    return False
            except Exception as e:
                logger.error(f"Failed to ensure welcome credit in DB for user {user_id}: {e}, using in-memory fallback")
        
        # Fallback to in-memory
        if user_id in self._welcomed_users:
            return False
        self._welcomed_users.add(user_id)
        logger.info(f"User registered: user_id={user_id}, welcome_credit={amount}₽")
        if amount > 0:
            self._balances[user_id] = self._balances.get(user_id, 0.0) + amount
        return True
    
    async def create_pending_charge(
        self,
        task_id: str,
        user_id: int,
        amount: float,
        model_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        reserve_balance: bool = False
    ) -> Dict[str, Any]:
        """
        Create pending charge (reserve funds, don't charge yet).
        
        Args:
            task_id: Task identifier
            user_id: User identifier
            amount: Charge amount
            model_id: Model identifier
            metadata: Optional metadata
            
        Returns:
            Charge info dict
        """
        # Check if already committed (idempotency)
        if task_id in self._committed_charges:
            logger.warning(f"Charge for task {task_id} already committed, skipping")
            return {
                'status': 'already_committed',
                'task_id': task_id,
                'message': 'Оплата уже подтверждена'
            }
        
        # Check if already released
        if task_id in self._released_charges:
            logger.warning(f"Charge for task {task_id} already released, skipping")
            return {
                'status': 'already_released',
                'task_id': task_id,
                'message': 'Оплата уже отменена'
            }
        
        if reserve_balance and amount > 0:
            # Reserve funds (hold) using WalletService if available
            ref = f"hold_{task_id}"
            wallet_service = self.wallet_service
            if wallet_service:
                try:
                    # Use hold operation to reserve funds
                    ref = f"hold_{task_id}"
                    success = await wallet_service.hold(
                        user_id, 
                        Decimal(str(amount)), 
                        ref=ref, 
                        meta={"model_id": model_id, "task_id": task_id, "hold_ref": ref}
                    )
                    if not success:
                        return {
                            'status': 'insufficient_balance',
                            'task_id': task_id,
                            'amount': amount,
                            'message': 'Недостаточно средств'
                        }
                    logger.info(f"✅ DB hold: user={user_id}, amount={amount}₽, task={task_id}")
                except Exception as e:
                    # If DB wallet is enabled, do NOT silently fall back to in-memory.
                    # Otherwise we will desync balance/holds and break future charges/refunds.
                    logger.exception(
                        "Failed to hold funds in DB (no in-memory fallback when DB is enabled): "
                        f"user={user_id} task={task_id} amount={amount} model={model_id}"
                    )
                    return {
                        'status': 'hold_failed',
                        'task_id': task_id,
                        'amount': amount,
                        'message': 'Ошибка резервирования средств. Попробуйте ещё раз.'
                    }
            else:
                # In-memory fallback
                balance = await self.get_user_balance(user_id)
                if balance < amount:
                    return {
                        'status': 'insufficient_balance',
                        'task_id': task_id,
                        'amount': amount,
                        'message': 'Недостаточно средств'
                    }
                await self.adjust_balance(user_id, -amount)

        charge_info = {
            'task_id': task_id,
            'user_id': user_id,
            'amount': amount,
            'model_id': model_id,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'metadata': metadata or {},
            'reserved': reserve_balance,
            'hold_ref': (f"hold_{task_id}" if reserve_balance and amount > 0 else None)
        }
        
        self._pending_charges[task_id] = charge_info
        
        # Store in persistent storage if available
        if self.storage:
            try:
                await self.storage.save_pending_charge(charge_info)
            except Exception as e:
                logger.error(f"Failed to save pending charge: {e}")
        
        logger.info(f"Created pending charge for task {task_id}, amount: {amount}")
        return {
            'status': 'pending',
            'task_id': task_id,
            'amount': amount,
            'message': 'Ожидание оплаты'
        }
    
    async def commit_charge(self, task_id: str) -> Dict[str, Any]:
        """
        Commit charge (actually charge user) - ONLY on generation success.
        Idempotent: repeated calls are no-op.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Commit result dict
        """
        # Idempotency check
        if task_id in self._committed_charges:
            logger.info(f"Charge for task {task_id} already committed (idempotent)")
            return {
                'status': 'already_committed',
                'task_id': task_id,
                'message': 'Оплата уже подтверждена',
                'idempotent': True
            }
        
        # Check if charge exists
        if task_id not in self._pending_charges:
            logger.warning(f"No pending charge found for task {task_id}")
            return {
                'status': 'not_found',
                'task_id': task_id,
                'message': 'Оплата не найдена'
            }
        
        charge_info = self._pending_charges[task_id]
        
        # Check if already released
        if task_id in self._released_charges:
            logger.warning(f"Charge for task {task_id} was released, cannot commit")
            return {
                'status': 'already_released',
                'task_id': task_id,
                'message': 'Оплата была отменена'
            }
        
        # Actually charge user (call payment API)
        try:
            # TODO: Replace with actual payment API call
            charge_result = await self._execute_charge(charge_info)
            
            if charge_result.get('success'):
                # Mark as committed
                self._committed_charges.add(task_id)
                charge_info['status'] = 'committed'
                charge_info['committed_at'] = datetime.now().isoformat()
                self._committed_info[task_id] = charge_info
                
                # Remove from pending
                if task_id in self._pending_charges:
                    del self._pending_charges[task_id]
                
                # Store in persistent storage
                if self.storage:
                    try:
                        await self.storage.save_committed_charge(charge_info)
                    except Exception as e:
                        logger.error(f"Failed to save committed charge: {e}")
                
                logger.info(f"Committed charge for task {task_id}, amount: {charge_info['amount']}")
                return {
                    'status': 'committed',
                    'task_id': task_id,
                    'amount': charge_info['amount'],
                    'message': 'Оплачено',
                    'idempotent': False
                }
            else:
                logger.error(f"Failed to execute charge for task {task_id}: {charge_result.get('error')}")
                return {
                    'status': 'failed',
                    'task_id': task_id,
                    'message': 'Ошибка при списании средств',
                    'error': charge_result.get('error')
                }
        except Exception as e:
            logger.error(f"Exception during charge commit for task {task_id}: {e}", exc_info=True)
            return {
                'status': 'error',
                'task_id': task_id,
                'message': 'Произошла ошибка при списании',
                'error': str(e)
            }
    
    async def release_charge(self, task_id: str, reason: str = "generation_failed") -> Dict[str, Any]:
        """
        Release charge (refund/auto-refund) on fail/timeout/cancel.
        Idempotent: repeated calls are no-op.
        
        Args:
            task_id: Task identifier
            reason: Release reason (generation_failed, timeout, cancelled, etc.)
            
        Returns:
            Release result dict
        """
        # Idempotency check
        if task_id in self._released_charges:
            logger.info(f"Charge for task {task_id} already released (idempotent)")
            return {
                'status': 'already_released',
                'task_id': task_id,
                'message': 'Оплата уже отменена',
                'idempotent': True
            }
        
        # Check if already committed
        if task_id in self._committed_charges:
            # Need to refund
            logger.info(f"Refunding committed charge for task {task_id}")
            try:
                refund_result = await self._execute_refund(task_id, reason)
                if refund_result.get('success'):
                    self._released_charges.add(task_id)
                    # Wallet refund is handled inside _execute_refund (DB-backed & idempotent).
                    return {
                        'status': 'refunded',
                        'task_id': task_id,
                        'message': 'Деньги возвращены',
                        'idempotent': False
                    }
                else:
                    return {
                        'status': 'refund_failed',
                        'task_id': task_id,
                        'message': 'Ошибка при возврате средств',
                        'error': refund_result.get('error')
                    }
            except Exception as e:
                logger.error(f"Exception during refund for task {task_id}: {e}", exc_info=True)
                return {
                    'status': 'refund_error',
                    'task_id': task_id,
                    'message': 'Произошла ошибка при возврате',
                    'error': str(e)
                }
        
        # Release pending charge (no actual charge happened, just cleanup)
        if task_id in self._pending_charges:
            charge_info = self._pending_charges[task_id]
            charge_info['status'] = 'released'
            charge_info['released_at'] = datetime.now().isoformat()
            charge_info['release_reason'] = reason
            if charge_info.get('reserved') and charge_info.get('amount', 0) > 0:
                # Release held funds back to balance (DB-backed & idempotent)
                await self._execute_refund(task_id, reason)
            
            self._released_charges.add(task_id)
            
            # Remove from pending
            del self._pending_charges[task_id]
            
            # Store in persistent storage
            if self.storage:
                try:
                    await self.storage.save_released_charge(charge_info)
                except Exception as e:
                    logger.error(f"Failed to save released charge: {e}")
            
            logger.info(f"Released pending charge for task {task_id}, reason: {reason}")
            return {
                'status': 'released',
                'task_id': task_id,
                'message': 'Деньги не списаны',
                'idempotent': False
            }
        
        # No charge found
        logger.warning(f"No charge found for task {task_id} to release")
        return {
            'status': 'not_found',
            'task_id': task_id,
            'message': 'Оплата не найдена'
        }
    
    async def get_charge_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current charge status for user visibility.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Status dict with user-friendly message
        """
        if task_id in self._committed_charges:
            return {
                'status': 'committed',
                'message': 'Оплачено'
            }
        
        if task_id in self._released_charges:
            return {
                'status': 'released',
                'message': 'Деньги не списаны'
            }
        
        if task_id in self._pending_charges:
            return {
                'status': 'pending',
                'message': 'Ожидание оплаты'
            }
        
        return {
            'status': 'not_found',
            'message': 'Оплата не найдена'
        }
    
    async def _execute_charge(self, charge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize a reserved hold by converting it into a charge.

        Important: this MUST be idempotent.
        - When DB wallet is enabled, we call WalletService.charge(...).
        - When DB wallet is disabled, funds were already debited in-memory during reserve.
        """
        task_id = str(charge_info.get('task_id'))
        user_id = int(charge_info.get('user_id'))
        amount = float(charge_info.get('amount', 0) or 0)
        model_id = str(charge_info.get('model_id', ''))

        if amount <= 0:
            return {'success': True, 'transaction_id': f"free_{task_id}"}

        if not self.wallet_service:
            # In-memory mode: reserve already decreased balance. Nothing to do.
            return {'success': True, 'transaction_id': f"mem_{task_id}"}

        amount_decimal = Decimal(str(amount))
        hold_ref = charge_info.get('hold_ref') or f"hold_{task_id}"
        charge_ref = f"charge_{task_id}"
        meta = {
            'task_id': task_id,
            'model_id': model_id,
            'amount_rub': str(amount_decimal),
            'source': 'charge_manager',
        }

        ok = await self.wallet_service.charge(user_id, amount_decimal, charge_ref, meta=meta, hold_ref=hold_ref)
        if ok:
            logger.info(f"✅ Wallet charge committed: user={user_id} task={task_id} amount={amount_decimal}RUB")
            return {'success': True, 'transaction_id': charge_ref}

        logger.error(f"❌ Wallet charge failed: user={user_id} task={task_id} amount={amount_decimal}RUB")
        return {'success': False, 'error_code': 'charge_failed', 'transaction_id': None}
    
    async def _execute_refund(self, task_id: str, reason: str) -> Dict[str, Any]:
        """Refund for a task.

        Behaviour:
        - If the task was only held (not charged), this releases the hold.
        - If the task was already charged, this credits balance back (without touching other holds).
        """
        task_id = str(task_id)
        info = self._committed_info.get(task_id) or self._pending_charges.get(task_id)
        if not info:
            return {'success': False, 'error_code': 'unknown_task', 'refund_id': None}

        user_id = int(info.get('user_id'))
        amount = float(info.get('amount', 0) or 0)
        model_id = str(info.get('model_id', ''))

        if amount <= 0:
            return {'success': True, 'refund_id': f"free_refund_{task_id}"}

        if not self.wallet_service:
            # In-memory mode: just credit back.
            await self.adjust_balance(user_id, amount)
            return {'success': True, 'refund_id': f"mem_refund_{task_id}"}

        amount_decimal = Decimal(str(amount))
        hold_ref = info.get('hold_ref') or f"hold_{task_id}"
        refund_ref = f"refund_{task_id}"
        meta = {
            'task_id': task_id,
            'model_id': model_id,
            'reason': reason,
            'amount_rub': str(amount_decimal),
            'source': 'charge_manager',
        }

        ok = await self.wallet_service.refund(user_id, amount_decimal, refund_ref, meta=meta, hold_ref=hold_ref)
        if ok:
            logger.info(f"✅ Wallet refund applied: user={user_id} task={task_id} amount={amount_decimal}RUB reason={reason}")
            return {'success': True, 'refund_id': refund_ref}

        logger.error(f"❌ Wallet refund failed: user={user_id} task={task_id} amount={amount_decimal}RUB reason={reason}")
        return {'success': False, 'error_code': 'refund_failed', 'refund_id': None}

    def add_to_history(self, user_id: int, model_id: str, inputs: Dict[str, Any], result: str, success: bool) -> None:
        """Add generation to user history."""
        if user_id not in self._generation_history:
            self._generation_history[user_id] = []
        
        record = {
            'timestamp': datetime.now().isoformat(),
            'model_id': model_id,
            'inputs': inputs,
            'result': result,
            'success': success,
        }
        self._generation_history[user_id].insert(0, record)  # Most recent first
        # Keep only last 20
        self._generation_history[user_id] = self._generation_history[user_id][:20]

    def get_user_history(self, user_id: int, limit: int = 10) -> list:
        """Get user generation history."""
        history = self._generation_history.get(user_id, [])
        return history[:limit]


# Global instance
_charge_manager: Optional[ChargeManager] = None


def get_charge_manager(storage=None) -> ChargeManager:
    """Get or create global charge manager instance."""
    global _charge_manager
    if _charge_manager is None:
        _charge_manager = ChargeManager(storage)
    return _charge_manager
