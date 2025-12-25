"""
Pricing calculator: USER_PRICE_RUB = (PRICE_USD × 79) × 2

ФОРМУЛА ЦЕНООБРАЗОВАНИЯ (ЗАФИКСИРОВАНА НАВСЕГДА):
  1. Kie.ai цены в USD (1 кредит = $0.005)
  2. Курс конвертации: 79 RUB/USD (ФИКСИРОВАННЫЙ, НЕ МЕНЯЕТСЯ)
  3. Цена Kie.ai в RUB: kie_cost_rub = price_usd × 79
  4. Наценка пользователю: user_price_rub = kie_cost_rub × 2
  
  Итого: user_price_rub = price_usd × 79 × 2

ПРИМЕР:
  1 кредит Kie.ai = $0.005 USD
  Цена Kie.ai = 0.005 × 79 = 0.395 RUB
  Цена пользователю = 0.395 × 2 = 0.79 RUB за 1 кредит

ЗАКОН ПРОЕКТА: 
  - Курс 79 RUB/USD ФИКСИРОВАН и НЕ ИЗМЕНЯЕТСЯ
  - Наценка ×2 ФИКСИРОВАНА и НЕ ИЗМЕНЯЕТСЯ
  - Цены в SOURCE_OF_TRUTH хранятся БЕЗ наценки (Kie.ai cost)
  - Наценка применяется только в calculate_user_price()
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ФИКСИРОВАННЫЙ курс (НЕ ИЗМЕНЯТЬ!)
# Используется для всех расчётов, независимо от реального курса ЦБ
USD_TO_RUB = 78.0

# ФИКСИРОВАННЫЙ множитель наценки (НЕ ИЗМЕНЯТЬ!)
# Цена пользователю = Цена Kie.ai × 2
MARKUP_MULTIPLIER = 2.0

# Fallback prices for models without pricing in SOURCE_OF_TRUTH (in USD)
# These are converted to RUB using USD_TO_RUB when needed
FALLBACK_PRICES_USD = {
    "flux/pro": 12.0,
    "flux/dev": 5.0,
    "flux-2/pro-text-to-image": 15.0,
    "flux-2/flex-text-to-image": 8.0,
    "google/veo-3": 20.0,
    "kling/v1-standard": 10.0,
}


def calculate_kie_cost(
    model: Dict[str, Any],
    user_inputs: Dict[str, Any],
    kie_response: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate real Kie.ai cost in RUB.
    
    Priority:
    1. kie_response['cost'] or ['price'] if available (assumed in RUB)
    2. model['pricing']['rub_per_gen'] from SOURCE_OF_TRUTH (direct RUB)
    3. model['price'] from old registry (in USD) → convert to RUB
    4. Default 10.0 USD → convert to RUB
    
    Args:
        model: Model metadata from registry
        user_inputs: User parameters (steps, duration, resolution, etc.)
        kie_response: Optional Kie.ai API response with actual cost (in RUB)
        
    Returns:
        Cost in RUB (float)
    """
    model_id = model.get("model_id", "unknown")
    
    # Priority 1: Use Kie.ai response cost if available (assumed in RUB)
    if kie_response:
        for key in ["cost", "price", "usage_cost", "credits_used"]:
            if key in kie_response:
                cost_rub = float(kie_response[key])
                logger.info(f"Using Kie.ai response cost for {model_id}: {cost_rub} RUB")
                return cost_rub
    
    # Priority 2: SOURCE_OF_TRUTH format (direct RUB price)
    pricing = model.get("pricing", {})
    if isinstance(pricing, dict):
        rub_price = pricing.get("rub_per_gen")
        if rub_price is not None:
            try:
                cost_rub = float(rub_price)
                # Allow 0 for FREE models
                if cost_rub >= 0:
                    if cost_rub == 0:
                        logger.info(f"Using SOURCE_OF_TRUTH price for {model_id}: FREE (0 RUB)")
                    else:
                        logger.info(f"Using SOURCE_OF_TRUTH price for {model_id}: {cost_rub} RUB")
                    return cost_rub
            except (TypeError, ValueError):
                logger.warning(f"Invalid SOURCE_OF_TRUTH price for {model_id}: {rub_price}")
    
    # Priority 3: Old registry format (in USD → convert to RUB)
    registry_price_usd = model.get("price")
    if registry_price_usd is not None:
        try:
            price_usd = float(registry_price_usd)
            if price_usd > 0:
                cost_rub = price_usd * USD_TO_RUB
                logger.info(f"Using old registry price for {model_id}: ${price_usd} → {cost_rub} RUB")
                return cost_rub
        except (TypeError, ValueError):
            logger.warning(f"Invalid registry price for {model_id}: {registry_price_usd}")
            pass
    
    # Priority 4: Fallback table (in USD → convert to RUB)
    if model_id in FALLBACK_PRICES_USD:
        price_usd = FALLBACK_PRICES_USD[model_id]
        cost_rub = price_usd * USD_TO_RUB
        logger.info(f"Using fallback price for {model_id}: ${price_usd} → {cost_rub} RUB")
        return cost_rub
    
    # Priority 5: Default (in USD → convert to RUB)
    default_usd = 10.0
    cost_rub = default_usd * USD_TO_RUB
    logger.warning(f"No price info for {model_id}, using default ${default_usd} → {cost_rub} RUB")
    return cost_rub


def calculate_user_price(kie_cost_rub: float) -> float:
    """
    Calculate user price: USER_PRICE_RUB = KIE_COST_RUB × 2
    
    Args:
        kie_cost_rub: Kie.ai cost in RUB (already converted from USD if needed)
        
    Returns:
        User price in RUB (rounded to 2 decimals)
    """
    user_price = kie_cost_rub * MARKUP_MULTIPLIER
    result = round(user_price, 2)
    
    # ASSERT: verify pricing formula
    assert result == round(kie_cost_rub * 2, 2), \
        f"Pricing formula violated: {result} != {kie_cost_rub} * 2"
    
    return result


def format_price_rub(price: float) -> str:
    """Format price for display: '96.00 ₽' or 'Бесплатно'."""
    if price == 0:
        return "Бесплатно"
    return f"{price:.2f} ₽"


def create_charge_metadata(
    model: Dict[str, Any],
    user_inputs: Dict[str, Any],
    kie_response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create charge metadata with pricing info.
    
    Returns:
        {
            'kie_cost_rub': float,
            'user_price_rub': float,
            'markup': 'x2',
            'model_id': str,
            'timestamp': str
        }
    """
    from datetime import datetime
    
    kie_cost = calculate_kie_cost(model, user_inputs, kie_response)
    user_price = calculate_user_price(kie_cost)
    
    # ASSERT: проверка формулы
    assert user_price == round(kie_cost * 2, 2), f"Pricing formula violated: {user_price} != {kie_cost} * 2"
    
    return {
        'kie_cost_rub': kie_cost,
        'user_price_rub': user_price,
        'markup': 'x2',
        'model_id': model.get('model_id'),
        'timestamp': datetime.now().isoformat()
    }
