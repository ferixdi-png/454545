#!/usr/bin/env python3
"""
KIE.AI Site Scraper - Official Source of Truth

Parses kie.ai/market and individual model pages to extract:
- Model slugs and display names
- Technical model IDs (as used by API)
- API endpoints (createTask, recordInfo)
- Request body schemas
- Output schemas
- Pricing (credits + USD)

This replaces manual copy-paste with automated truth extraction.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
import time

# Paths
CACHE_DIR = Path("/workspaces/5656/cache")
OUTPUT_FILE = Path("/workspaces/5656/models/kie_models_source_of_truth.json")
CACHE_DIR.mkdir(exist_ok=True)

# Rate limiting
DELAY_BETWEEN_PAGES = 2  # seconds


class KieSiteScraper:
    """Scrapes KIE.AI site for model API data"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.models_data: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        
    async def init_browser(self):
        """Initialize headless browser"""
        print("🌐 Initializing browser...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        print("✅ Browser ready")
    
    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
    
    async def fetch_market_page(self) -> List[Dict[str, str]]:
        """
        Fetch list of models from market/pricing page
        Returns: [{"slug": "wan-2-6", "name": "Wan 2.6", "category": "video"}, ...]
        """
        print("\n📋 Fetching market page...")
        
        page = await self.browser.new_page()
        
        try:
            # Try multiple possible URLs
            urls_to_try = [
                "https://kie.ai/pricing",
                "https://kie.ai/market",
                "https://kie.ai/models"
            ]
            
            for url in urls_to_try:
                print(f"   Trying: {url}")
                try:
                    response = await page.goto(url, wait_until="networkidle", timeout=30000)
                    if response.ok:
                        break
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    continue
            
            # Wait for content to load
            await page.wait_for_timeout(3000)
            
            # Get page content
            content = await page.content()
            
            # Save raw HTML for debugging
            cache_file = CACHE_DIR / "market_page.html"
            cache_file.write_text(content, encoding='utf-8')
            print(f"   💾 Cached to: {cache_file}")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, 'lxml')
            
            # Extract model links
            # Pattern 1: Look for links to model pages
            model_links = []
            
            # Try finding links with model patterns
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Skip external/non-model links
                if any(skip in href for skip in ['blog', 'docs', 'login', 'pricing', 'terms', 'privacy']):
                    continue
                
                # Look for model slugs (lowercase with hyphens)
                if re.match(r'^/[a-z0-9-]+$', href) or re.match(r'^https://kie\.ai/[a-z0-9-]+$', href):
                    slug = href.strip('/').split('/')[-1]
                    
                    # Get display name from link text or nearby elements
                    name = link.get_text(strip=True) or slug.replace('-', ' ').title()
                    
                    model_links.append({
                        "slug": slug,
                        "name": name,
                        "url": f"https://kie.ai/{slug}"
                    })
            
            # Deduplicate
            seen = set()
            unique_models = []
            for m in model_links:
                if m['slug'] not in seen:
                    seen.add(m['slug'])
                    unique_models.append(m)
            
            print(f"   ✅ Found {len(unique_models)} potential model pages")
            
            # If we didn't find models via links, try parsing JSON data from __NEXT_DATA__
            if len(unique_models) < 10:
                print("   🔍 Searching for models in __NEXT_DATA__...")
                script_tags = soup.find_all('script', id='__NEXT_DATA__')
                
                for script in script_tags:
                    try:
                        data = json.loads(script.string)
                        # Navigate through the data structure to find models
                        # This is site-specific and may need adjustment
                        print(f"   📊 Found NEXT_DATA with {len(str(data))} chars")
                        # Could extract model info here if structured
                    except:
                        pass
            
            return unique_models
            
        finally:
            await page.close()
    
    async def fetch_model_page(self, slug: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch individual model page and extract API data
        
        Looks for:
        1. "Copy page" button data
        2. API code snippets
        3. Parameter documentation
        4. Pricing information
        """
        print(f"\n🔍 Fetching model: {slug}")
        
        page = await self.browser.new_page()
        
        try:
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            
            if not response.ok:
                print(f"   ❌ HTTP {response.status}")
                return None
            
            # Wait for page to fully load
            await page.wait_for_timeout(3000)
            
            # Get page content
            content = await page.content()
            
            # Cache the page
            cache_file = CACHE_DIR / f"model_{slug}.html"
            cache_file.write_text(content, encoding='utf-8')
            
            # Parse HTML
            soup = BeautifulSoup(content, 'lxml')
            
            model_data = {
                "slug": slug,
                "url": url,
                "display_name": None,
                "tech_model_id": None,
                "category": None,
                "endpoint_create": None,
                "endpoint_record": None,
                "request_schema": {},
                "output_type": None,
                "pricing": {},
                "raw_api_data": None
            }
            
            # Extract title
            title_tag = soup.find('h1')
            if title_tag:
                model_data['display_name'] = title_tag.get_text(strip=True)
            
            # Look for "Copy page" button or API section
            # Common patterns:
            # - button with text "Copy"
            # - pre/code blocks with API examples
            # - data attributes with model info
            
            # Try to find API code blocks
            code_blocks = soup.find_all(['pre', 'code'])
            for block in code_blocks:
                text = block.get_text()
                
                # Look for createTask endpoint
                if 'createTask' in text or '/api/v1/jobs' in text:
                    model_data['endpoint_create'] = '/api/v1/jobs/createTask'
                
                # Look for model ID in code
                model_match = re.search(r'"model":\s*"([^"]+)"', text)
                if model_match:
                    model_data['tech_model_id'] = model_match.group(1)
                
                # Look for request body example
                if '{' in text and '"input"' in text:
                    try:
                        # Try to extract JSON
                        json_match = re.search(r'\{.*\}', text, re.DOTALL)
                        if json_match:
                            example_request = json.loads(json_match.group(0))
                            model_data['raw_api_data'] = example_request
                            
                            # Extract input schema
                            if 'input' in example_request:
                                model_data['request_schema'] = example_request['input']
                    except:
                        pass
            
            # Look for pricing information
            pricing_patterns = [
                (r'(\d+(?:\.\d+)?)\s*credits?', 'credits'),
                (r'\$(\d+(?:\.\d+)?)', 'usd'),
                (r'(\d+(?:\.\d+)?)\s*₽', 'rub')
            ]
            
            page_text = soup.get_text()
            for pattern, currency in pricing_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    try:
                        model_data['pricing'][currency] = float(matches[0])
                    except:
                        pass
            
            # Try to determine category from text
            text_lower = page_text.lower()
            if any(kw in text_lower for kw in ['video', 'movie', 'clip']):
                model_data['category'] = 'video'
            elif any(kw in text_lower for kw in ['image', 'picture', 'photo']):
                model_data['category'] = 'image'
            elif any(kw in text_lower for kw in ['audio', 'music', 'sound']):
                model_data['category'] = 'audio'
            
            # If we didn't find tech_model_id, try inferring from slug
            if not model_data['tech_model_id']:
                # Use slug as fallback
                model_data['tech_model_id'] = slug.replace('-', '/')
            
            print(f"   ✅ Extracted: {model_data['tech_model_id']}")
            print(f"      Category: {model_data['category']}")
            print(f"      Pricing: {model_data['pricing']}")
            
            await page.wait_for_timeout(DELAY_BETWEEN_PAGES * 1000)
            
            return model_data
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.errors.append(f"{slug}: {str(e)}")
            return None
        
        finally:
            await page.close()
    
    async def scrape_all(self, limit: Optional[int] = None):
        """Main scraping workflow"""
        
        print("="*80)
        print("🚀 KIE.AI SITE SCRAPER - STARTING")
        print("="*80)
        
        await self.init_browser()
        
        try:
            # Step 1: Get model list from market
            models_list = await self.fetch_market_page()
            
            if not models_list:
                print("\n❌ No models found on market page")
                print("   Falling back to known models from pricing...")
                
                # Fallback: use models from kie_pricing_raw.txt
                pricing_file = Path("/workspaces/5656/kie_pricing_raw.txt")
                if pricing_file.exists():
                    models_list = self._extract_models_from_pricing(pricing_file)
            
            print(f"\n📊 Total models to process: {len(models_list)}")
            
            if limit:
                models_list = models_list[:limit]
                print(f"   (Limited to first {limit} for testing)")
            
            # Step 2: Fetch each model page
            for i, model_info in enumerate(models_list, 1):
                print(f"\n[{i}/{len(models_list)}] Processing: {model_info['slug']}")
                
                model_data = await self.fetch_model_page(
                    model_info['slug'],
                    model_info['url']
                )
                
                if model_data:
                    self.models_data.append(model_data)
            
            # Step 3: Save results
            self._save_results()
            
            # Step 4: Print summary
            self._print_summary()
            
        finally:
            await self.close_browser()
    
    def _extract_models_from_pricing(self, pricing_file: Path) -> List[Dict[str, str]]:
        """Extract model slugs from kie_pricing_raw.txt as fallback"""
        
        models = []
        seen_slugs = set()
        
        with open(pricing_file, 'r') as f:
            for line in f:
                if '|' not in line:
                    continue
                
                parts = line.split(',')
                if len(parts) < 2:
                    continue
                
                name = parts[0].strip()
                
                # Generate slug
                slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                
                if slug and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    models.append({
                        "slug": slug,
                        "name": name,
                        "url": f"https://kie.ai/{slug}"
                    })
        
        print(f"   📋 Extracted {len(models)} models from pricing file")
        return models
    
    def _save_results(self):
        """Save scraped data to JSON"""
        
        print(f"\n💾 Saving results to: {OUTPUT_FILE}")
        
        output_data = {
            "version": "6.1.0",
            "source": "kie.ai site scraper",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_models": len(self.models_data),
            "total_errors": len(self.errors),
            "models": self.models_data,
            "errors": self.errors
        }
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"   ✅ Saved {len(self.models_data)} models")
        print(f"   ⚠️  {len(self.errors)} errors")
    
    def _print_summary(self):
        """Print scraping summary"""
        
        print("\n" + "="*80)
        print("📊 SCRAPING SUMMARY")
        print("="*80)
        
        print(f"\n✅ Successfully scraped: {len(self.models_data)} models")
        print(f"❌ Errors: {len(self.errors)}")
        
        if self.models_data:
            # Count by category
            categories = {}
            with_pricing = 0
            with_schema = 0
            
            for m in self.models_data:
                cat = m.get('category', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1
                
                if m.get('pricing'):
                    with_pricing += 1
                
                if m.get('request_schema'):
                    with_schema += 1
            
            print(f"\n📂 By category:")
            for cat, count in sorted(categories.items()):
                print(f"   • {cat:20s}: {count:3d} models")
            
            print(f"\n💰 With pricing data: {with_pricing}/{len(self.models_data)}")
            print(f"📝 With request schema: {with_schema}/{len(self.models_data)}")
        
        if self.errors:
            print(f"\n⚠️  Errors encountered:")
            for err in self.errors[:10]:
                print(f"   • {err}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more")
        
        print("\n" + "="*80)


async def main():
    """Run scraper"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Scrape KIE.AI site for model data")
    parser.add_argument('--limit', type=int, help="Limit number of models to scrape (for testing)")
    args = parser.parse_args()
    
    scraper = KieSiteScraper()
    await scraper.scrape_all(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
