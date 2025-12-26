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

# REFERRALS (optional):
# - REFERRAL_FREE_USES_PER_INVITE (default: 3)
# - REFERRAL_MAX_RUB (default: 50)
"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

def _load_allowed_model_ids_from_repo() -> list[str]:
    """Load the canonical allowlist of model_ids bundled with the repo.

    This project is locked to an allowlist (expected 42 models). If the file is
    missing or unreadable, we fall back to env-provided lists.
    """
    try:
        p = Path(__file__).resolve().parents[2] / "models" / "ALLOWED_MODEL_IDS.txt"
        if p.exists():
            ids: list[str] = []
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                ids.append(s)
            # preserve order, remove dups
            seen=set()
            out=[]
            for mid in ids:
                if mid in seen:
                    continue
                seen.add(mid)
                out.append(mid)
            return out
    except Exception:
        pass
    return []


@dataclass
class Config:
    """Application configuration with validation."""
    
    # REQUIRED fields
    telegram_bot_token: str = field(default="")
    telegram_bot_username: str | None = field(default=None)  # Optional bot username
    kie_api_key: str = field(default="")
    
    # OPTIONAL - Instance
    instance_name: str = field(default="bot-instance")
    admin_ids: List[int] = field(default_factory=list)
    
    # OPTIONAL - Pricing
    pricing_markup: float = field(default=2.0)
    currency: str = field(default="RUB")
    
    # OPTIONAL - Models
    minimal_models_locked: bool = field(default=True)
    minimal_model_ids: List[str] = field(default_factory=list)
    free_tier_model_ids: List[str] = field(default_factory=list)
    start_bonus_rub: float = field(default=0.0)  # Changed from welcome_balance (default was 200, now 0)
    
    # OPTIONAL - Bot mode
    bot_mode: str = field(default="polling")
    
    # OPTIONAL - Storage
    storage_mode: str = field(default="auto")
    database_url: Optional[str] = field(default=None)
    
    # OPTIONAL - Kie.ai
    kie_base_url: str = field(default="https://api.kie.ai")
    
    # OPTIONAL - Support
    support_telegram: Optional[str] = field(default=None)
    support_text: str = field(default="Свяжитесь с поддержкой")
    
    # OPTIONAL - Testing
    dry_run: bool = field(default=False)
    test_mode: bool = field(default=False)
    
    def __post_init__(self):
        """Load and validate configuration from ENV after dataclass init."""
        # REQUIRED
        self.telegram_bot_token = self._get_required("TELEGRAM_BOT_TOKEN")
        self.kie_api_key = self._get_required("KIE_API_KEY")
        
        # OPTIONAL - Bot username
        self.telegram_bot_username = os.getenv("TELEGRAM_BOT_USERNAME") or os.getenv("BOT_USERNAME") or None
        
        # OPTIONAL - Instance identification
        self.instance_name = os.getenv("INSTANCE_NAME", "bot-instance")
        
        # OPTIONAL - Admin configuration
        admin_id_str = os.getenv("ADMIN_ID", "0")
        self.admin_ids = self._parse_admin_ids(admin_id_str)
        
        # OPTIONAL - Pricing
        self.pricing_markup = float(os.getenv("PRICING_MARKUP", "2.0"))
        self.currency = os.getenv("CURRENCY", "RUB")

        # ✅ MINIMAL MODELS LOCK (runtime whitelist)
        # Default: strict allowlist mode ON (exactly 42 models from models/ALLOWED_MODEL_IDS.txt)
        self.minimal_models_locked = os.getenv("MINIMAL_MODELS_LOCKED", "1") not in ("0", "false", "False")
        allowed_from_repo = _load_allowed_model_ids_from_repo()
        default_minimal = ",".join(allowed_from_repo) if allowed_from_repo else "sora-2-text-to-video,sora-2-image-to-video,sora-watermark-remover,grok-imagine/image-to-video,grok-imagine/text-to-video"
        self.minimal_model_ids = self._parse_csv(os.getenv("MINIMAL_MODEL_IDS", default_minimal))

        # 🆓 FREE TIER MODELS (must be subset of minimal_model_ids)
        # TOP-5 cheapest models by base_cost from source_of_truth (auto-derived)
        # Deterministic: sorted by (price, alphabetically)
        # Current: z-image (0.76₽), recraft/remove-background (0.95₽), infinitalk/from-audio (2.85₽), 
        #          google/imagen4 (3.80₽), google/imagen4-fast (3.80₽)
        default_free = "z-image,recraft/remove-background,infinitalk/from-audio,google/imagen4,google/imagen4-fast"
        self.free_tier_model_ids = self._parse_csv(os.getenv("FREE_TIER_MODEL_IDS", default_free))
        
        # START BONUS (onboarding credit, default 0)
        self.start_bonus_rub = float(os.getenv("START_BONUS_RUB", "0"))
        
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
        
        logger.info(f"✅ Config loaded: {self.bot_mode} mode, {len(self.minimal_model_ids)} models")
    
    def _parse_csv(self, value: str) -> List[str]:
        """Parse comma-separated list into normalized list[str]."""
        value = (value or "").strip()
        if not value:
            return []
        return [x.strip() for x in value.split(",") if x.strip()]

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
        print(f"Start Bonus: {self.start_bonus_rub} {self.currency}")
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


# Convenience module-level constants (kept outside Config for easy import)
REFERRAL_FREE_USES_PER_INVITE = int(os.getenv("REFERRAL_FREE_USES_PER_INVITE", "3"))
REFERRAL_MAX_RUB = float(os.getenv("REFERRAL_MAX_RUB", "50"))


def validate_env() -> bool:
    """Validate environment configuration (no side-effect prints)."""
    try:
        _ = get_config()
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