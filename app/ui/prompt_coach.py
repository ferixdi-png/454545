"""Prompt coach: inline tips during text input (no external AI calls).

RULES:
- Detect weak prompts locally
- Generate 1-2 short tips max
- Never blocks user flow
- Tips are helpful, not annoying
"""
import re
from typing import List, Optional, Dict


def analyze_prompt(text: str, format_type: str = "text-to-image") -> Dict[str, any]:
    """Analyze prompt quality and detect missing elements.
    
    Args:
        text: User's prompt text
        format_type: Format type (for context-aware tips)
    
    Returns:
        Dict with: is_weak, missing_elements, tips, score (0-100)
    """
    text_lower = text.lower()
    word_count = len(text.split())
    
    # Detection patterns
    has_audience = any(word in text_lower for word in [
        "для", "аудитория", "клиент", "покупател", "подростк", "мам", "бизнес"
    ])
    
    has_style = any(word in text_lower for word in [
        "стиль", "минимал", "премиум", "яр", "дерз", "элегант", "современ", "винтаж"
    ])
    
    has_goal = any(word in text_lower for word in [
        "реклам", "обложк", "баннер", "пост", "stories", "reels", "карточк товар"
    ])
    
    has_specifics = any(word in text_lower for word in [
        "цвет", "фон", "композиц", "крупн план", "детал", "текстур", "освещен"
    ])
    
    # For marketing content
    has_offer = any(word in text_lower for word in [
        "скид", "бонус", "подарок", "акци", "доставк", "-", "%", "беспла"
    ])
    
    has_cta = any(word in text_lower for word in [
        "купи", "закаж", "получи", "подпис", "перейд", "жми", "кликай", "свяж"
    ])
    
    # Scoring
    score = 0
    if word_count >= 5:
        score += 20
    if word_count >= 10:
        score += 10
    if has_audience:
        score += 15
    if has_style:
        score += 15
    if has_goal:
        score += 10
    if has_specifics:
        score += 15
    if has_offer:
        score += 10
    if has_cta:
        score += 5
    
    # Detect missing elements
    missing = []
    if not has_audience and format_type in ["text-to-image", "text-to-video"]:
        missing.append("audience")
    if not has_style:
        missing.append("style")
    if not has_offer and "ad" in format_type.lower():
        missing.append("offer")
    if not has_cta and "ad" in format_type.lower():
        missing.append("cta")
    
    is_weak = score < 50 or word_count < 5
    
    return {
        "is_weak": is_weak,
        "score": score,
        "missing_elements": missing,
        "word_count": word_count,
    }


def generate_tips(analysis: Dict[str, any], format_type: str = "text-to-image") -> List[str]:
    """Generate 1-2 actionable tips based on analysis.
    
    Args:
        analysis: Result from analyze_prompt()
        format_type: Format type
    
    Returns:
        List of tip strings (max 2)
    """
    tips = []
    missing = analysis["missing_elements"]
    
    # Priority tips
    if "audience" in missing:
        tips.append("💡 Добавь аудиторию: для кого это? (мамы 25-35, бизнесмены, подростки)")
    
    if "style" in missing and len(tips) < 2:
        tips.append("💡 Добавь стиль: минимализм / премиум / дерзко / винтаж")
    
    if "offer" in missing and len(tips) < 2:
        tips.append("💡 Добавь оффер: скидка / бонус / бесплатная доставка")
    
    if "cta" in missing and len(tips) < 2:
        tips.append("💡 Добавь призыв: купить / заказать / подписаться")
    
    # Generic tips if nothing specific
    if not tips:
        if analysis["word_count"] < 10:
            tips.append("💡 Добавь деталей: цвет, композицию, настроение")
    
    return tips[:2]  # Max 2 tips


def build_improvement_form_fields(missing_elements: List[str]) -> List[Dict[str, str]]:
    """Build form fields for improvement wizard.
    
    Args:
        missing_elements: List of missing element types
    
    Returns:
        List of field definitions with name, prompt, placeholder
    """
    field_templates = {
        "audience": {
            "name": "audience",
            "prompt": "Для кого это?",
            "placeholder": "Пример: мамы 25-35 лет, владельцы бизнеса",
        },
        "style": {
            "name": "style",
            "prompt": "Какой стиль?",
            "placeholder": "Пример: минимализм, премиум, яркий",
        },
        "offer": {
            "name": "offer",
            "prompt": "Что предлагаешь?",
            "placeholder": "Пример: скидка 20%, бесплатная доставка",
        },
        "cta": {
            "name": "cta",
            "prompt": "Призыв к действию?",
            "placeholder": "Пример: купить сейчас, заказать со скидкой",
        },
    }
    
    fields = []
    for element in missing_elements:
        if element in field_templates:
            fields.append(field_templates[element])
    
    return fields


def merge_improvements(
    original_prompt: str,
    improvements: Dict[str, str],
) -> str:
    """Merge improvements into original prompt (template-based, no AI).
    
    Args:
        original_prompt: Original user prompt
        improvements: Dict of field_name -> value
    
    Returns:
        Enhanced prompt
    """
    parts = [original_prompt.strip()]
    
    # Add improvements in natural order
    if "audience" in improvements and improvements["audience"]:
        parts.append(f"для {improvements['audience']}")
    
    if "style" in improvements and improvements["style"]:
        parts.append(f"в стиле: {improvements['style']}")
    
    if "offer" in improvements and improvements["offer"]:
        parts.append(f"оффер: {improvements['offer']}")
    
    if "cta" in improvements and improvements["cta"]:
        parts.append(f"призыв: {improvements['cta']}")
    
    return ", ".join(parts)


def get_prompt_example(format_type: str) -> str:
    """Get example prompt for format.
    
    Args:
        format_type: Format type
    
    Returns:
        Example prompt text
    """
    examples = {
        "text-to-image": "Современная обложка для онлайн-курса по маркетингу, минимализм, синие тона, для предпринимателей 30-40 лет",
        "text-to-video": "Короткий рилс (15 сек): распаковка iPhone в стиле UGC, крупный план рук, динамичная музыка, для молодёжи 18-25",
        "text-to-audio": "Голосовая озвучка для рекламного ролика: премиум-тон, мужской голос, уверенный и спокойный",
    }
    
    return examples.get(format_type, "Добавь больше деталей: стиль, аудиторию, цель")


def should_show_coach(prompt: str, user_level: str = "newbie") -> bool:
    """Decide whether to show coach tips.
    
    Args:
        prompt: User's prompt
        user_level: User experience level ("newbie", "intermediate", "advanced")
    
    Returns:
        True if should show tips
    """
    # Always show for newbies with weak prompts
    if user_level == "newbie":
        analysis = analyze_prompt(prompt)
        return analysis["is_weak"]
    
    # Show for intermediate if very weak
    if user_level == "intermediate":
        analysis = analyze_prompt(prompt)
        return analysis["score"] < 30
    
    # Never annoy advanced users
    return False
