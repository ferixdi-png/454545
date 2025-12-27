"""Global style guide for AI Studio - premium UX consistency."""
from typing import Optional


class StyleGuide:
    """Centralized style rules for consistent premium UX."""
    
    # Headers
    @staticmethod
    def header(section: str) -> str:
        """Format main header: ✨ AI Studio — Section"""
        return f"✨ <b>AI Studio</b> — {section}"
    
    @staticmethod
    def subheader_marketer() -> str:
        """Value proposition for marketers."""
        return "Создавай контент за минуты: видео, креативы, озвучка"
    
    # Badges
    @staticmethod
    def badge_free() -> str:
        return "🎁 FREE"
    
    @staticmethod
    def badge_popular() -> str:
        return "🔥 POPULAR"
    
    @staticmethod
    def badge_new() -> str:
        return "✨ NEW"
    
    @staticmethod
    def badge_pro() -> str:
        return "⭐ PRO"
    
    # Pricing
    @staticmethod
    def format_price(price_rub: float, is_free: bool = False) -> str:
        """Format price consistently."""
        if is_free or price_rub == 0:
            return "Цена: FREE"
        return f"Цена: {price_rub:.1f} ₽ / запуск"
    
    @staticmethod
    def format_time_hint(seconds: Optional[int] = None) -> str:
        """Format time estimate."""
        if not seconds:
            return ""
        if seconds < 20:
            return "⏱ Обычно: 5–15 сек"
        elif seconds < 60:
            return "⏱ Обычно: 10–30 сек"
        elif seconds < 180:
            return f"⏱ Обычно: ~{seconds // 60} мин"
        else:
            return "⏱ Обычно: несколько минут"
    
    # Messages
    @staticmethod
    def error(reason: str, action: str) -> str:
        """Format error message."""
        return f"⚠️ <b>Не получилось</b>\n\nПричина: {reason}\n\nЧто делать: {action}"
    
    @staticmethod
    def success(what_returned: str) -> str:
        """Format success message."""
        return f"✅ <b>Готово!</b>\n\n{what_returned}"
    
    # Buttons
    @staticmethod
    def btn_start() -> str:
        return "🚀 Запустить"
    
    @staticmethod
    def btn_example() -> str:
        return "✨ Пример"
    
    @staticmethod
    def btn_back() -> str:
        return "◀️ Назад"
    
    @staticmethod
    def btn_home() -> str:
        return "🏠 Меню"
    
    @staticmethod
    def btn_retry() -> str:
        return "🔁 Повторить"
    
    # Tips
    @staticmethod
    def tip_recommended() -> str:
        """Helper tip for recommended models."""
        return "<i>Совет: начни с Recommended — там меньше ошибок и быстрее результат.</i>"
    
    @staticmethod
    def tip_prompt_quality() -> str:
        """Tip for better prompts."""
        return "<i>Совет: добавь стиль / свет / ракурс / бренд-цвет для лучшего результата.</i>"
    
    # Formatting helpers
    @staticmethod
    def bullet_list(items: list, max_items: int = 4) -> str:
        """Format bullet list (max 4 items)."""
        limited = items[:max_items]
        return "\n".join(f"• {item}" for item in limited)
    
    @staticmethod
    def compact_text(lines: list) -> str:
        """Join lines compactly (1-2 paragraphs max)."""
        return "\n\n".join(lines[:2])
