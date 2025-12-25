"""
Environment configuration manager with validation and multi-tenant support.

REQUIRED ENV:
- TELEGRAM_BOT_TOKEN
- KIE_API_KEY

OPTIONAL ENV:
- ADMIN_ID (single int or CSV: "123,456,789")
- INSTANCE_NAME (for logs/healthcheck)
- PRICING_MARKUP (default: 2.0)
- CURRENCY (default: RUB)
- BOT_MODE (polling or webhook, default: polling)
- DATABASE_URL (for postgres storage)
- STORAGE_MODE (auto, postgres, json)
"""
import os
import sys
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Config:
    """Application configuration with validation."""
    
    def __init__(self):
        """Load and validate configuration from ENV."""
        # REQUIRED
        self.telegram_bot_token = self._get_required("TELEGRAM_BOT_TOKEN")
        self.kie_api_key = self._get_required("KIE_API_KEY")
        
        # OPTIONAL - Instance identification
        self.instance_name = os.getenv("INSTANCE_NAME", "bot-instance")
        
        # OPTIONAL - Admin configuration
        admin_id_str = os.getenv("ADMIN_ID", "0")
        self.admin_ids = self._parse_admin_ids(admin_id_str)
        
        # OPTIONAL - Pricing
        self.pricing_markup = float(os.getenv("PRICING_MARKUP", "2.0"))
        self.currency = os.getenv("CURRENCY", "RUB")
        self.welcome_balance = float(os.getenv("WELCOME_BALANCE_RUB", "200"))
        
        # OPTIONAL - Bot mode
        self.bot_mode = os.getenv("BOT_MODE", "polling").lower()
        if self.bot_mode not in ["polling", "webhook"]:
            raise ValueError(f"BOT_MODE must be 'polling' or 'webhook', got: {self.bot_mode}")
        
        # OPTIONAL - Storage
        self.storage_mode = os.getenv("STORAGE_MODE", "auto").lower()
        self.database_url = os.getenv("DATABASE_URL")
        
        # OPTIONAL - Kie.ai
        self.kie_base_url = os.getenv("KIE_BASE_URL", "https://api.kie.ai").rstrip("/")
        
        # OPTIONAL - Support
        self.support_telegram = os.getenv("SUPPORT_TELEGRAM")
        self.support_text = os.getenv("SUPPORT_TEXT", "Свяжитесь с поддержкой")
        
        # OPTIONAL - Testing
        self.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        self.test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        
        # Validate compatibility
        self._validate()
    
    def _get_required(self, key: str) -> str:
        """Get required ENV variable or fail."""
        value = os.getenv(key)
        if not value:
            logger.error(f"❌ Missing required ENV variable: {key}")
            raise ValueError(f"Required ENV variable {key} not set")
        return value
    
    def _parse_admin_ids(self, admin_str: str) -> List[int]:
        """Parse ADMIN_ID from single int or CSV."""
        admin_str = admin_str.strip()
        if not admin_str or admin_str == "0":
            return []
        
        try:
            # Try single int
            if "," not in admin_str:
                return [int(admin_str)]
            
            # Parse CSV
            return [int(x.strip()) for x in admin_str.split(",") if x.strip()]
        except ValueError as e:
            logger.error(f"❌ Invalid ADMIN_ID format: {admin_str}")
            raise ValueError(f"ADMIN_ID must be int or CSV of ints, got: {admin_str}") from e
    
    def _validate(self):
        """Validate configuration consistency."""
        # If storage_mode is postgres but no DATABASE_URL
        if self.storage_mode == "postgres" and not self.database_url:
            raise ValueError("STORAGE_MODE=postgres requires DATABASE_URL")
        
        # Pricing markup must be >= 1.0
        if self.pricing_markup < 1.0:
            raise ValueError(f"PRICING_MARKUP must be >= 1.0, got: {self.pricing_markup}")
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user_id is admin."""
        if not self.admin_ids:
            return False
        return user_id in self.admin_ids
    
    def mask_secret(self, value: str, show_chars: int = 4) -> str:
        """Mask secret for logging."""
        if not value or len(value) <= show_chars:
            return "****"
        return f"{value[:show_chars]}{'*' * (len(value) - show_chars)}"
    
    def print_summary(self):
        """Print configuration summary (without secrets)."""
        print("=" * 60)
        print("CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"Instance Name: {self.instance_name}")
        print(f"Bot Mode: {self.bot_mode}")
        print(f"Storage Mode: {self.storage_mode}")
        print(f"Admin IDs: {len(self.admin_ids)} configured")
        print(f"Pricing Markup: {self.pricing_markup}x")
        print(f"Currency: {self.currency}")
        print(f"Welcome Balance: {self.welcome_balance} {self.currency}")
        print()
        print("Secrets (masked):")
        print(f"  TELEGRAM_BOT_TOKEN: {self.mask_secret(self.telegram_bot_token)}")
        print(f"  KIE_API_KEY: {self.mask_secret(self.kie_api_key)}")
        if self.database_url:
            print(f"  DATABASE_URL: {self.mask_secret(self.database_url, 10)}")
        print()
        print("Kie.ai:")
        print(f"  Base URL: {self.kie_base_url}")
        print()
        if self.dry_run or self.test_mode:
            print("⚠️  Testing flags:")
            if self.dry_run:
                print("  DRY_RUN=true")
            if self.test_mode:
                print("  TEST_MODE=true")
            print()
        print("=" * 60)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance (singleton)."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def validate_env() -> bool:
    """Validate environment configuration."""
    try:
        config = get_config()
        config.print_summary()
        return True
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        return False


if __name__ == "__main__":
    # Can be run standalone to check ENV
    logging.basicConfig(level=logging.INFO)
    
    if validate_env():
        print("✅ Configuration valid!")
        sys.exit(0)
    else:
        print("❌ Configuration invalid!")
        sys.exit(1)
