"""Bot handlers package."""
from .flow import router as flow_router
from .zero_silence import router as zero_silence_router
from .diag import router as diag_router
from .error_handler import router as error_handler_router
from .marketing import router as marketing_router
from .balance import router as balance_router
from .history import router as history_router
from .admin import router as admin_router
from .gallery import router as gallery_router
from .quick_actions import router as quick_actions_router
from .callback_fallback import router as callback_fallback_router
from .navigation import router as navigation_router
from .gen_handler import router as gen_handler_router

__all__ = [
    "flow_router",
    "zero_silence_router", 
    "diag_router",
    "error_handler_router",
    "marketing_router",
    "balance_router",
    "history_router",
    "admin_router",
    "gallery_router",
    "quick_actions_router",
    "callback_fallback_router",
    "navigation_router",
    "gen_handler_router",
]
