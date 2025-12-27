#!/usr/bin/env python3
"""
Update input_schema for models from cached Kie.ai docs.

CRITICAL: This updates SOURCE_OF_TRUTH - backup first!
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional

def extract_schema_from_cache(model_id: str) -> Optional[Dict[str, Any]]:
    """
    Extract input_schema from cached Kie.ai page.
    
    Cache locations:
    - cache/kie_model_pages/docs.kie.ai_market_{model_id}.html
    - cache/kie_model_pages/market_{model_id}.html
    """
    cache_dir = Path("cache/kie_model_pages")
    if not cache_dir.exists():
        return None
    
    # Try different file patterns
    patterns = [
        f"docs.kie.ai_market_{model_id.replace('/', '_')}.html",
        f"market_{model_id.replace('/', '_')}.html",
        f"*{model_id.replace('/', '*')}*.html",
    ]
    
    for pattern in patterns:
        files = list(cache_dir.glob(pattern))
        if files:
            return extract_schema_from_html(files[0])
    
    return None

def extract_schema_from_html(html_path: Path) -> Optional[Dict[str, Any]]:
    """Extract JSON schema from __NEXT_DATA__ in HTML."""
    try:
        html = html_path.read_text(encoding='utf-8')
        
        # Find <script id="__NEXT_DATA__">
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL
        )
        
        if not match:
            return None
        
        data = json.loads(match.group(1))
        
        # Navigate to inputSchema
        props = data.get('props', {})
        page_props = props.get('pageProps', {})
        schema = page_props.get('inputSchema', {})
        
        if schema and isinstance(schema, dict):
            return schema
        
    except Exception as e:
        print(f"  ⚠️  Parse error for {html_path.name}: {e}")
    
    return None

def update_source_of_truth(dry_run: bool = True):
    """
    Update SOURCE_OF_TRUTH with schemas from cache.
    
    Args:
        dry_run: If True, only show what would change (no write)
    """
    sot_path = Path("models/KIE_SOURCE_OF_TRUTH.json")
    
    if not sot_path.exists():
        print("❌ SOURCE_OF_TRUTH not found")
        return 1
    
    # Backup
    if not dry_run:
        backup_path = sot_path.with_suffix('.json.backup')
        backup_path.write_text(sot_path.read_text())
        print(f"💾 Backup created: {backup_path}")
    
    # Load current
    data = json.loads(sot_path.read_text())
    models = data.get('models', {})
    
    stats = {'found': 0, 'updated': 0, 'empty': 0, 'missing': 0}
    
    print(f"\n{'='*70}")
    print("🔍 Scanning cache for input_schema updates...")
    print(f"{'='*70}\n")
    
    for model_id, model in models.items():
        current_schema = model.get('input_schema', {})
        
        if current_schema and current_schema.get('properties'):
            stats['found'] += 1
            continue  # Already has schema
        
        stats['empty'] += 1
        
        # Try to find schema in cache
        new_schema = extract_schema_from_cache(model_id)
        
        if new_schema and new_schema.get('properties'):
            stats['updated'] += 1
            print(f"✅ {model_id}")
            print(f"   Properties: {list(new_schema.get('properties', {}).keys())[:5]}")
            
            if not dry_run:
                model['input_schema'] = new_schema
        else:
            stats['missing'] += 1
            print(f"⚠️  {model_id}: no cache found")
    
    # Summary
    print(f"\n{'='*70}")
    print("📊 SUMMARY")
    print(f"{'='*70}")
    print(f"✅ Already have schema: {stats['found']}")
    print(f"🔄 Updated from cache: {stats['updated']}")
    print(f"⚠️  Empty (no cache): {stats['missing']}")
    print(f"📦 Total models: {len(models)}")
    print(f"{'='*70}\n")
    
    if dry_run:
        print("🔍 DRY RUN - no changes made")
        print("💡 Run with --apply to actually update SOURCE_OF_TRUTH")
    else:
        # Write updated data
        data['models'] = models
        sot_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"✅ SOURCE_OF_TRUTH updated: {stats['updated']} schemas added")
    
    return 0

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Update SOURCE_OF_TRUTH schemas from cache"
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually apply changes (default: dry-run)'
    )
    
    args = parser.parse_args()
    
    if not args.apply:
        print("⚠️  DRY RUN MODE (use --apply to make changes)\n")
    
    return update_source_of_truth(dry_run=not args.apply)

if __name__ == "__main__":
    sys.exit(main())
