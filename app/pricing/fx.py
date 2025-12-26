"""
Foreign Exchange (FX) rate management.

Provides USD to RUB exchange rate with caching and fallback.

RULES:
1. Cache rate for 12 hours
2. Primary source: external API (e.g., exchangerate-api.com, cbr.ru)
3. Fallback: ENV variable FX_RUB_PER_USD
4. Default fallback: 78.0 (conservative estimate)
"""
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Cache
_cached_rate: Optional[float] = None
_cache_timestamp: Optional[float] = None
_cache_duration = 12 * 3600  # 12 hours in seconds


def get_usd_to_rub_rate(force_refresh: bool = False) -> float:
    """
    Get USD to RUB exchange rate.
    
    Args:
        force_refresh: Force fetch from API even if cached
    
    Returns:
        Exchange rate (RUB per 1 USD)
    """
    global _cached_rate, _cache_timestamp
    
    # Check cache
    if not force_refresh and _cached_rate and _cache_timestamp:
        age = time.time() - _cache_timestamp
        if age < _cache_duration:
            logger.debug(f"Using cached FX rate: {_cached_rate} (age: {age/3600:.1f}h)")
            return _cached_rate
    
    # Try to fetch fresh rate
    fresh_rate = _fetch_fresh_rate()
    
    if fresh_rate:
        _cached_rate = fresh_rate
        _cache_timestamp = time.time()
        logger.info(f"Updated FX rate: {fresh_rate} RUB/USD")
        return fresh_rate
    
    # Fallback to cached rate if available
    if _cached_rate:
        logger.warning("Could not fetch fresh FX rate, using stale cache")
        return _cached_rate
    
    # Final fallback to ENV or default
    fallback = _get_fallback_rate()
    logger.warning(f"Using fallback FX rate: {fallback} RUB/USD")
    return fallback


def _fetch_fresh_rate() -> Optional[float]:
    """
    Fetch fresh exchange rate from external API.
    
    Tries multiple sources in order:
    1. Central Bank of Russia (free, no key needed)
    2. ENV variable (if API fails)
    
    Returns:
        Exchange rate or None if all sources fail
    """
    # Try CBR (Central Bank of Russia) - no API key needed
    try:
        import httpx
        
        # CBR daily rates (free, official)
        url = "https://www.cbr-xml-daily.ru/latest.js"
        
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # CBR returns rates as "1 CURRENCY = X RUB"
                # For USD, we need to invert: if response shows USD rate,
                # it's actually RUB per USD
                rate = data.get("rates", {}).get("USD")
                
                # If rate is less than 1, it's inverted (RUB/USD instead of USD/RUB)
                if rate and isinstance(rate, (int, float)):
                    if rate < 1:
                        # Invert: 1 / rate gives us USD/RUB
                        rate = 1.0 / rate
                    logger.info(f"Fetched CBR rate: {rate} RUB/USD")
                    return float(rate)
    
    except ImportError:
        logger.warning("httpx not installed, cannot fetch FX rate from API")
    except Exception as e:
        logger.warning(f"Failed to fetch CBR rate: {e}")
    
    # All sources failed
    return None


def _get_fallback_rate() -> float:
    """
    Get fallback rate from ENV or default.
    
    Returns:
        Fallback exchange rate
    """
    env_rate = os.getenv("FX_RUB_PER_USD")
    
    if env_rate:
        try:
            rate = float(env_rate)
            if rate > 0:
                logger.info(f"Using ENV FX rate: {rate}")
                return rate
        except ValueError:
            logger.error(f"Invalid FX_RUB_PER_USD: {env_rate}")
    
    # Hard default (conservative estimate)
    default_rate = 78.0
    logger.warning(f"Using default FX rate: {default_rate}")
    return default_rate


def usd_to_rub(usd_amount: float, markup: float = 2.0) -> float:
    """
    Convert USD to RUB with markup.
    
    Args:
        usd_amount: Amount in USD
        markup: Price markup multiplier (default: 2.0 = 2x)
    
    Returns:
        Amount in RUB
    """
    rate = get_usd_to_rub_rate()
    rub_amount = usd_amount * rate * markup
    return round(rub_amount, 2)


def credits_to_rub(
    credits: float,
    credits_to_usd_rate: float = 0.01,
    markup: float = 2.0
) -> float:
    """
    Convert Kie.ai credits to RUB.
    
    Args:
        credits: Amount in credits
        credits_to_usd_rate: Conversion rate (default: 0.01 = 1 credit = $0.01)
        markup: Price markup multiplier
    
    Returns:
        Amount in RUB
    """
    usd_amount = credits * credits_to_usd_rate
    return usd_to_rub(usd_amount, markup)


# Initialize on import
try:
    _initial_rate = get_usd_to_rub_rate()
    logger.info(f"FX module initialized: {_initial_rate} RUB/USD")
except Exception as e:
    logger.error(f"FX initialization failed: {e}")
