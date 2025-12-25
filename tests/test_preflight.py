import pytest
from unittest.mock import AsyncMock

from main_render import preflight_webhook


@pytest.mark.asyncio
async def test_preflight_deletes_webhook():
    bot = AsyncMock()
    bot.delete_webhook = AsyncMock(return_value=True)

    await preflight_webhook(bot)

    bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=False)
