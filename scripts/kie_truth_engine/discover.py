#!/usr/bin/env python3
"""
Model Discovery - находит все модели на сайте kie.ai

Стратегия:
1. Парсим главную страницу https://kie.ai/models или https://kie.ai/api-market
2. Находим все ссылки на страницы моделей
3. Кэшируем результаты для повторного использования
"""
import httpx
import logging
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import re

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/kie_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting
RATE_LIMIT_DELAY = 0.5  # 2 RPS max
_last_request_time = 0.0


def _rate_limit():
    """Enforce rate limiting."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()


def _cache_path(url: str) -> Path:
    """Generate cache file path for URL."""
    # Create safe filename from URL
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', url)
    return CACHE_DIR / f"{safe_name}.html"


def _fetch_url(url: str, use_cache: bool = True) -> Optional[str]:
    """
    Fetch URL with caching and rate limiting.
    
    Args:
        url: URL to fetch
        use_cache: Use cached version if available
    
    Returns:
        HTML content or None on error
    """
    cache_file = _cache_path(url)
    
    # Check cache
    if use_cache and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < 24:  # Cache for 24 hours
            logger.info(f"Using cached version of {url} (age: {age_hours:.1f}h)")
            return cache_file.read_text(encoding='utf-8')
    
    # Fetch fresh
    logger.info(f"Fetching {url}...")
    _rate_limit()
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; KieTruthEngine/1.0)'
            }
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            
            content = resp.text
            
            # Save to cache
            cache_file.write_text(content, encoding='utf-8')
            logger.info(f"Cached {url} ({len(content)} bytes)")
            
            return content
    
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def discover_models_from_index() -> List[Dict[str, str]]:
    """
    Discover all models from kie.ai main pages.
    
    Returns:
        List of {model_id, url, name} dicts
    """
    models = []
    
    # Try multiple entry points
    entry_urls = [
        "https://kie.ai/models",
        "https://kie.ai/api-market",
        "https://kie.ai/",
    ]
    
    for entry_url in entry_urls:
        logger.info(f"\n{'='*60}")
        logger.info(f"Trying entry point: {entry_url}")
        logger.info(f"{'='*60}\n")
        
        html = _fetch_url(entry_url)
        if not html:
            continue
        
        # Find model links
        # Pattern 1: /z-image, /flux-2-pro, etc.
        pattern1 = r'href="(/[a-z0-9-]+)"'
        matches1 = re.findall(pattern1, html)
        
        # Pattern 2: /ai/model-name or similar
        pattern2 = r'href="(/ai/[a-z0-9-]+)"'
        matches2 = re.findall(pattern2, html)
        
        all_paths = set(matches1 + matches2)
        
        logger.info(f"Found {len(all_paths)} potential model paths")
        
        for path in all_paths:
            # Skip non-model paths
            if any(skip in path for skip in [
                '/about', '/docs', '/pricing', '/login', '/signup',
                '/terms', '/privacy', '/blog', '/api', '/models',
                '/contact', '/support', '/faq'
            ]):
                continue
            
            # Skip if too short or just numbers
            if len(path) < 3 or path.replace('-', '').replace('/', '').isdigit():
                continue
            
            full_url = urljoin("https://kie.ai", path)
            model_id = path.strip('/')
            
            # Simple heuristic: if path contains known model keywords
            if any(word in model_id.lower() for word in [
                'image', 'video', 'audio', 'text', 'speech', 
                'flux', 'wan', 'kling', 'veo', 'grok', 'midjourney',
                'suno', 'eleven', 'recraft', 'topaz', 'openai',
                'ideogram', 'hailuo', 'seedream', 'nano'
            ]):
                models.append({
                    'model_id': model_id,
                    'url': full_url,
                    'name': model_id.replace('-', ' ').title(),
                    'source': 'discovered'
                })
                logger.info(f"  ✓ {model_id}")
    
    # Deduplicate by model_id
    seen = set()
    unique_models = []
    for m in models:
        if m['model_id'] not in seen:
            seen.add(m['model_id'])
            unique_models.append(m)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Total unique models discovered: {len(unique_models)}")
    logger.info(f"{'='*60}\n")
    
    return unique_models


def discover_models_from_known_list() -> List[Dict[str, str]]:
    """
    Build list from known models (backup strategy).
    
    Returns:
        List of known model entries
    """
    # Известные модели из pricing таблицы
    known_models = [
        # Images
        "z-image",
        "grok-imagine",
        "flux-2-pro",
        "flux-2-flex",
        "flux-1-kontext",
        "midjourney",
        "imagen4",
        "ideogram-v3",
        "ideogram-v3-remix",
        "ideogram-v3-edit",
        "seedream-4-0",
        "seedream-4-5",
        "recraft",
        "openai-4o-image",
        
        # Videos
        "wan-2-6",
        "wan-2-5",
        "wan-2-2",
        "veo-3-1",
        "kling-2-6",
        "kling-2-1",
        "hailuo-2-3",
        "hailuo-02",
        "runway-aleph",
        
        # Audio
        "suno",
        "elevenlabs",
        
        # Upscale
        "topaz",
        "nano-banana",
    ]
    
    models = []
    for model_id in known_models:
        models.append({
            'model_id': model_id,
            'url': f"https://kie.ai/{model_id}",
            'name': model_id.replace('-', ' ').title(),
            'source': 'known_list'
        })
    
    logger.info(f"Built {len(models)} models from known list")
    return models


def discover_all_models(use_scraping: bool = True) -> List[Dict[str, str]]:
    """
    Discover all models using all available strategies.
    
    Args:
        use_scraping: Whether to scrape website (vs just use known list)
    
    Returns:
        Combined list of all discovered models
    """
    all_models = []
    
    # Strategy 1: Known list (always included)
    known = discover_models_from_known_list()
    all_models.extend(known)
    
    # Strategy 2: Scrape website
    if use_scraping:
        try:
            discovered = discover_models_from_index()
            all_models.extend(discovered)
        except Exception as e:
            logger.error(f"Scraping failed: {e}", exc_info=True)
    
    # Deduplicate
    seen = set()
    unique = []
    for m in all_models:
        if m['model_id'] not in seen:
            seen.add(m['model_id'])
            unique.append(m)
    
    # Save index
    index_file = CACHE_DIR / "models_index.json"
    with index_file.open('w', encoding='utf-8') as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"TOTAL MODELS DISCOVERED: {len(unique)}")
    logger.info(f"Saved to: {index_file}")
    logger.info(f"{'='*60}\n")
    
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    models = discover_all_models(use_scraping=False)  # Start with known list only
    
    print("\nDiscovered models:")
    for i, m in enumerate(models, 1):
        print(f"{i:3d}. {m['model_id']:30s} ({m['source']})")
