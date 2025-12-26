"""
Pricing Contract - Single Source of Truth for all pricing operations.

INVARIANTS:
- models/pricing_source_truth.txt is THE canonical price list (USD, no markup)
- Formula: BASE_RUB = USD × FX_RATE (no markup)
- Formula: USER_RUB = BASE_RUB × PRICING_MARKUP (applied in pricing.py)
- DEFAULT: MARKUP=2.0, FX_RATE=95
- In registry: rub_per_use/rub_per_gen = BASE RUB (no markup)
- FREE tier = TOP-5 cheapest by BASE RUB price

USAGE:
    from app.payments.pricing_contract import PricingContract
    
    pc = PricingContract()
    pc.load_truth()  # Load from pricing_source_truth.txt
    pc.normalize_registry()  # Sync SOURCE_OF_TRUTH.json
    
    base_rub = pc.get_price_rub("z-image")  # Get BASE RUB price
    free_tier = pc.derive_free_tier()  # Get TOP-5 cheapest
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
import json

logger = logging.getLogger(__name__)


class PricingContract:
    """Pricing contract enforcer - ensures consistency across system."""
    
    def __init__(
        self,
        markup: float = None,
        fx_rate: float = None,
        truth_file: Path = None,
        registry_file: Path = None
    ):
        """
        Initialize pricing contract.
        
        Args:
            markup: Price markup multiplier (default: 2.0 or PRICING_MARKUP env)
            fx_rate: USD to RUB exchange rate (default: 95 or USD_RUB_RATE env)
            truth_file: Path to pricing_source_truth.txt
            registry_file: Path to KIE_SOURCE_OF_TRUTH.json
        """
        self.markup = markup or float(os.getenv("PRICING_MARKUP", "2.0"))
        self.fx_rate = fx_rate or float(os.getenv("USD_RUB_RATE", "95.0"))
        
        root = Path(__file__).resolve().parents[2]
        self.truth_file = truth_file or root / "models" / "pricing_source_truth.txt"
        self.registry_file = registry_file or root / "models" / "KIE_SOURCE_OF_TRUTH.json"
        
        # Pricing map: model_id -> (usd, rub)
        self._pricing_map: Dict[str, Tuple[Decimal, Decimal]] = {}
    
    def compute_rub_price(self, usd: float) -> Decimal:
        """
        Compute BASE RUB price from USD using FX rate (WITHOUT markup).
        
        Markup is applied separately by pricing.py when showing user prices.
        
        Args:
            usd: Price in USD
            
        Returns:
            BASE price in RUB (rounded: 2 decimals if <10, else to integer)
        """
        rub = Decimal(str(usd)) * Decimal(str(self.fx_rate))
        
        # Rounding logic: preserve cents for cheap models, round to whole for expensive
        if rub < 10:
            return round(rub, 2)
        else:
            return round(rub, 0)
    
    def load_truth(self) -> Dict[str, Tuple[Decimal, Decimal]]:
        """
        Load pricing truth from pricing_source_truth.txt.
        
        Returns:
            Dict[model_id, (usd, rub)]
        """
        if not self.truth_file.exists():
            logger.error(f"Pricing truth file not found: {self.truth_file}")
            return {}
        
        self._pricing_map = {}
        
        with open(self.truth_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                try:
                    # Format: "model_id: 0.0200 USD"
                    parts = line.split(':')
                    if len(parts) != 2:
                        continue
                    
                    model_id = parts[0].strip()
                    usd_str = parts[1].strip().replace('USD', '').strip()
                    
                    usd = Decimal(usd_str)
                    rub = self.compute_rub_price(float(usd))
                    
                    self._pricing_map[model_id] = (usd, rub)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse pricing line '{line}': {e}")
                    continue
        
        logger.info(f"Loaded pricing for {len(self._pricing_map)} models from truth file")
        return self._pricing_map
    
    def get_price_rub(self, model_id: str) -> Optional[Decimal]:
        """Get RUB price for model."""
        if not self._pricing_map:
            self.load_truth()
        
        if model_id in self._pricing_map:
            return self._pricing_map[model_id][1]
        return None
    
    def get_price_usd(self, model_id: str) -> Optional[Decimal]:
        """Get USD price for model."""
        if not self._pricing_map:
            self.load_truth()
        
        if model_id in self._pricing_map:
            return self._pricing_map[model_id][0]
        return None
    
    def derive_free_tier(self, count: int = 5) -> List[str]:
        """
        Derive FREE tier = TOP-N cheapest models by BASE RUB price (no markup).
        
        Tie-breaking: If multiple models have same price, sort alphabetically.
        
        Args:
            count: Number of free models (default: 5)
            
        Returns:
            List of model_ids sorted by price (cheapest first), then alphabetically
        """
        if not self._pricing_map:
            self.load_truth()
        
        # Sort by BASE RUB price, then alphabetically (deterministic tie-breaking)
        sorted_models = sorted(
            self._pricing_map.items(),
            key=lambda x: (x[1][1], x[0])  # (base_rub_price, model_id)
        )
        
        return [model_id for model_id, _ in sorted_models[:count]]
    
    def normalize_registry(self) -> int:
        """
        Normalize pricing in SOURCE_OF_TRUTH.json to match pricing truth.
        
        ENSURES: rub_per_use == rub_per_gen == BASE_RUB (no markup)
                 usd_per_use == usd_per_gen == truth_usd
        
        Markup is applied separately when showing user prices.
        
        Returns:
            Number of models updated
        """
        if not self._pricing_map:
            self.load_truth()
        
        if not self.registry_file.exists():
            logger.error(f"Registry file not found: {self.registry_file}")
            return 0
        
        with open(self.registry_file, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        models = registry.get('models', {})
        updated_count = 0
        
        for model_id, model_data in models.items():
            if model_id not in self._pricing_map:
                logger.warning(f"Model {model_id} not in pricing truth - skipping")
                continue
            
            usd, base_rub = self._pricing_map[model_id]
            
            # Ensure pricing object exists
            if 'pricing' not in model_data:
                model_data['pricing'] = {}
            
            pricing = model_data['pricing']
            
            # Normalize all pricing fields to BASE prices (no markup)
            old_rub_use = pricing.get('rub_per_use')
            old_rub_gen = pricing.get('rub_per_gen')
            
            pricing['usd_per_use'] = float(usd)
            pricing['usd_per_gen'] = float(usd)
            pricing['rub_per_use'] = float(base_rub)
            pricing['rub_per_gen'] = float(base_rub)
            
            # Credits (legacy compatibility)
            pricing['credits_per_use'] = float(usd) * 100
            pricing['credits_per_gen'] = float(usd) * 100
            
            # Check if changed
            if old_rub_use != float(base_rub) or old_rub_gen != float(base_rub):
                logger.info(
                    f"Normalized {model_id}: "
                    f"rub_per_use={old_rub_use}→{float(base_rub)} (base, no markup), "
                    f"rub_per_gen={old_rub_gen}→{float(base_rub)} (base, no markup)"
                )
                updated_count += 1
        
        # Save back
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Normalized {updated_count} models in registry (BASE prices, no markup)")
        return updated_count
    
    def validate_coverage(self, expected_count: int = 42) -> Tuple[bool, List[str]]:
        """
        Validate pricing coverage.
        
        Args:
            expected_count: Expected number of models
            
        Returns:
            (is_valid, issues_list)
        """
        if not self._pricing_map:
            self.load_truth()
        
        issues = []
        
        # Check count
        actual_count = len(self._pricing_map)
        if actual_count != expected_count:
            issues.append(
                f"Expected {expected_count} models, got {actual_count}"
            )
        
        # Check for zero prices
        zero_price = [
            mid for mid, (usd, rub) in self._pricing_map.items()
            if usd == 0 or rub == 0
        ]
        if zero_price:
            issues.append(f"Models with zero price: {zero_price}")
        
        # Load registry and check coverage
        if self.registry_file.exists():
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                registry = json.load(f)
            
            registry_models = set(registry.get('models', {}).keys())
            truth_models = set(self._pricing_map.keys())
            
            missing_in_truth = registry_models - truth_models
            if missing_in_truth:
                issues.append(f"Models in registry but not in truth: {missing_in_truth}")
            
            extra_in_truth = truth_models - registry_models
            if extra_in_truth:
                issues.append(f"Models in truth but not in registry: {extra_in_truth}")
        
        return len(issues) == 0, issues


# Singleton instance
_contract = None

def get_pricing_contract() -> PricingContract:
    """Get singleton pricing contract instance."""
    global _contract
    if _contract is None:
        _contract = PricingContract()
        _contract.load_truth()
    return _contract
