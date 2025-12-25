"""
Telegram API rate limit handling middleware.
Handles RetryAfter and TooManyRequests exceptions gracefully.
"""
import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для обработки Telegram API rate limits.
    
    Автоматически обрабатывает RetryAfter ошибки и повторяет запрос после задержки.
    """
    
    def __init__(self, max_retries: int = 3):
        """
        Args:
            max_retries: Максимальное количество повторных попыток
        """
        self.max_retries = max_retries
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Handle rate limits with automatic retry.
        
        Args:
            handler: Next handler in chain
            event: Telegram event
            data: Handler data
            
        Returns:
            Handler result
        """
        retries = 0
        
        while retries <= self.max_retries:
            try:
                return await handler(event, data)
                
            except TelegramRetryAfter as e:
                retry_after = e.retry_after
                
                if retries >= self.max_retries:
                    logger.error(
                        f"Rate limit exceeded after {self.max_retries} retries. "
                        f"Giving up. Retry after: {retry_after}s"
                    )
                    raise
                
                retries += 1
                logger.warning(
                    f"Telegram rate limit hit. Retry after {retry_after}s "
                    f"(attempt {retries}/{self.max_retries})"
                )
                
                await asyncio.sleep(retry_after)
                
            except TelegramAPIError as e:
                # Другие Telegram API ошибки - не повторяем
                logger.error(f"Telegram API error: {e}")
                raise
        
        # Не должно сюда дойти, но на всякий случай
        raise RuntimeError("Rate limit retry loop exceeded")


class GlobalRateLimiter:
    """
    Глобальный rate limiter для всего бота.
    Предотвращает слишком частые запросы к Telegram API.
    """
    
    def __init__(self, requests_per_second: float = 20.0):
        """
        Args:
            requests_per_second: Максимум запросов в секунду
                                Telegram limit: 30 req/sec, используем 20 для безопасности
        """
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
    
    async def acquire(self):
        """Подождать перед следующим запросом если необходимо."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = asyncio.get_event_loop().time()


# Глобальный инстанс rate limiter
global_rate_limiter = GlobalRateLimiter(requests_per_second=20.0)
