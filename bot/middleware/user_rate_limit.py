"""
Per-user rate limiting middleware to prevent abuse.

MASTER PROMPT compliance:
- Protect against single-user DoS
- Fair resource distribution
- Graceful degradation under load
"""

import time
from typing import Dict, Tuple, Optional
from collections import defaultdict
import asyncio

from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
import logging

logger = logging.getLogger(__name__)


class UserRateLimiter:
    """
    Per-user rate limiter using token bucket algorithm.
    
    Each user gets a bucket with tokens that refill over time.
    Actions consume tokens. When bucket is empty, user is rate limited.
    """
    
    def __init__(
        self,
        rate: int = 10,  # tokens per period
        period: int = 60,  # period in seconds
        burst: int = 15,  # max tokens (burst capacity)
    ):
        """
        Initialize rate limiter.
        
        Args:
            rate: Number of tokens to add per period
            period: Time period in seconds
            burst: Maximum tokens (burst capacity)
        """
        self.rate = rate
        self.period = period
        self.burst = burst
        
        # user_id -> (tokens, last_update_time)
        self._buckets: Dict[int, Tuple[float, float]] = {}
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, user_id: int, cost: float = 1.0) -> Tuple[bool, Optional[float]]:
        """
        Check if user can perform action.
        
        Args:
            user_id: User ID
            cost: Token cost of action (default 1.0)
            
        Returns:
            (allowed, retry_after_seconds)
        """
        async with self._lock:
            now = time.time()
            
            # Get or create bucket
            if user_id not in self._buckets:
                self._buckets[user_id] = (self.burst, now)
            
            tokens, last_update = self._buckets[user_id]
            
            # Calculate tokens to add based on time passed
            time_passed = now - last_update
            tokens_to_add = (time_passed / self.period) * self.rate
            
            # Update tokens (capped at burst)
            tokens = min(self.burst, tokens + tokens_to_add)
            
            # Check if user can afford action
            if tokens >= cost:
                # Consume tokens
                tokens -= cost
                self._buckets[user_id] = (tokens, now)
                return True, None
            else:
                # Calculate retry after
                tokens_needed = cost - tokens
                retry_after = (tokens_needed / self.rate) * self.period
                
                # Update last_update time but don't change tokens
                self._buckets[user_id] = (tokens, now)
                
                return False, retry_after
    
    async def reset_user(self, user_id: int):
        """Reset rate limit for specific user (admin action)."""
        async with self._lock:
            if user_id in self._buckets:
                del self._buckets[user_id]
    
    async def get_user_tokens(self, user_id: int) -> float:
        """Get current token count for user."""
        async with self._lock:
            if user_id not in self._buckets:
                return self.burst
            
            tokens, last_update = self._buckets[user_id]
            now = time.time()
            
            # Calculate current tokens
            time_passed = now - last_update
            tokens_to_add = (time_passed / self.period) * self.rate
            current_tokens = min(self.burst, tokens + tokens_to_add)
            
            return current_tokens


class UserRateLimitMiddleware(BaseMiddleware):
    """
    Middleware to enforce per-user rate limits.
    
    Different costs for different actions:
    - Simple queries: 0.5 tokens
    - Button clicks: 1.0 token
    - Generations: 2.0 tokens
    - File uploads: 3.0 tokens
    """
    
    def __init__(
        self,
        rate: int = 20,  # 20 actions per minute
        period: int = 60,
        burst: int = 30,  # Allow bursts of 30
        exempt_users: Optional[set] = None,
    ):
        """
        Initialize middleware.
        
        Args:
            rate: Actions per period
            period: Period in seconds
            burst: Burst capacity
            exempt_users: Set of user IDs exempt from rate limiting (admins)
        """
        self.limiter = UserRateLimiter(rate=rate, period=period, burst=burst)
        self.exempt_users = exempt_users or set()
        super().__init__()
    
    def _get_action_cost(self, update: Update) -> float:
        """Determine token cost based on action type."""
        # Callback queries (button clicks) - cheaper
        if update.callback_query:
            callback_data = update.callback_query.data
            
            # Generations are more expensive
            if callback_data and callback_data.startswith("gen:"):
                return 2.0
            
            return 1.0
        
        # Messages
        if update.message:
            # File uploads - most expensive
            if update.message.photo or update.message.document or update.message.video or update.message.audio:
                return 3.0
            
            # Text messages
            return 1.0
        
        # Default cost
        return 1.0
    
    async def __call__(self, handler, event, data):
        """Process update through rate limiter."""
        # Get user ID
        user_id = None
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id
        
        # Skip if no user ID or user is exempt
        if user_id is None or user_id in self.exempt_users:
            return await handler(event, data)
        
        # Determine action cost
        update = data.get("event_update")
        cost = self._get_action_cost(update) if update else 1.0
        
        # Check rate limit
        allowed, retry_after = await self.limiter.check_rate_limit(user_id, cost)
        
        if not allowed:
            # Rate limited
            logger.warning(f"User {user_id} rate limited. Retry after {retry_after:.1f}s")
            
            # Send friendly message
            if isinstance(event, Message):
                await event.answer(
                    "⏱ Пожалуйста, подождите немного. Вы отправляете слишком много запросов.\n\n"
                    f"Попробуйте снова через {int(retry_after) + 1} секунд."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"⏱ Подождите {int(retry_after) + 1}с перед следующим действием",
                    show_alert=True
                )
            
            # Don't process the event
            return
        
        # User has tokens, proceed
        return await handler(event, data)


# Global rate limiter instance for programmatic access
_global_limiter: Optional[UserRateLimiter] = None


def get_rate_limiter() -> UserRateLimiter:
    """Get global rate limiter instance."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = UserRateLimiter()
    return _global_limiter


async def check_user_rate_limit(user_id: int, cost: float = 1.0) -> bool:
    """
    Programmatically check if user can perform action.
    
    Returns True if allowed, False if rate limited.
    """
    limiter = get_rate_limiter()
    allowed, _ = await limiter.check_rate_limit(user_id, cost)
    return allowed
