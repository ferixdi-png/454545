"""Revamped referral system with gamification."""
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Cache for rewards config
_rewards_config: Optional[Dict] = None


def load_rewards_config() -> Dict:
    """Load referral rewards configuration.
    
    Returns:
        Rewards config dict
    """
    global _rewards_config
    
    if _rewards_config is not None:
        return _rewards_config
    
    config_file = Path(__file__).parent / "content" / "referral_rewards.json"
    
    try:
        _rewards_config = json.loads(config_file.read_text(encoding="utf-8"))
        log.info("Loaded referral rewards config")
        return _rewards_config
    except Exception as e:
        log.error(f"Failed to load referral rewards config: {e}")
        
        # Fallback config
        _rewards_config = {
            "tiers": [
                {"referrals_needed": 1, "reward_amount": 3, "title": "Первый друг"},
                {"referrals_needed": 3, "reward_amount": 10, "title": "Команда"},
                {"referrals_needed": 10, "reward_amount": 50, "title": "VIP статус"},
            ],
            "share_templates": [
                {
                    "id": "story_1",
                    "text": "🎨 Делаю контент за секунды в AI Studio. Попробуй бесплатно 👇"
                }
            ],
            "progress_messages": {
                "0_refs": "Пригласи друзей — получи бесплатные запуски!",
            },
            "referral_bonus_per_user": {
                "inviter_bonus": 2,
                "invitee_bonus": 1,
            }
        }
        
        return _rewards_config


def get_current_tier(referral_count: int) -> Dict:
    """Get current reward tier for user.
    
    Args:
        referral_count: Number of successful referrals
    
    Returns:
        Current tier dict
    """
    config = load_rewards_config()
    tiers = config.get("tiers", [])
    
    # Find highest achieved tier
    current_tier = None
    for tier in sorted(tiers, key=lambda t: t["referrals_needed"]):
        if referral_count >= tier["referrals_needed"]:
            current_tier = tier
        else:
            break
    
    return current_tier or {"referrals_needed": 0, "reward_amount": 0, "title": "Новичок"}


def get_next_tier(referral_count: int) -> Optional[Dict]:
    """Get next reward tier to achieve.
    
    Args:
        referral_count: Number of successful referrals
    
    Returns:
        Next tier dict or None if max tier reached
    """
    config = load_rewards_config()
    tiers = config.get("tiers", [])
    
    for tier in sorted(tiers, key=lambda t: t["referrals_needed"]):
        if referral_count < tier["referrals_needed"]:
            return tier
    
    return None


def get_progress_message(referral_count: int) -> str:
    """Get motivational progress message.
    
    Args:
        referral_count: Number of successful referrals
    
    Returns:
        Progress message
    """
    config = load_rewards_config()
    messages = config.get("progress_messages", {})
    
    # Try exact match first
    exact_key = f"{referral_count}_refs"
    if exact_key in messages:
        return messages[exact_key]
    
    # Find closest match
    keys = sorted([int(k.split("_")[0]) for k in messages.keys()])
    closest = 0
    for k in keys:
        if k <= referral_count:
            closest = k
    
    return messages.get(f"{closest}_refs", "Продолжай приглашать друзей!")


def build_progress_bar(referral_count: int) -> str:
    """Build visual progress bar to next tier.
    
    Args:
        referral_count: Current referral count
    
    Returns:
        Progress bar string
    """
    next_tier = get_next_tier(referral_count)
    
    if not next_tier:
        return "🏆 Максимальный уровень достигнут!"
    
    needed = next_tier["referrals_needed"]
    remaining = needed - referral_count
    
    # Visual bar (10 segments)
    progress_pct = min(100, int((referral_count / needed) * 100))
    filled = int(progress_pct / 10)
    empty = 10 - filled
    
    bar = "█" * filled + "░" * empty
    
    return f"До **{next_tier['title']}**: {bar} ({remaining} приглашений)"


def get_share_template(template_id: str = "story_1") -> str:
    """Get share template text.
    
    Args:
        template_id: Template ID
    
    Returns:
        Share template text
    """
    config = load_rewards_config()
    templates = config.get("share_templates", [])
    
    for template in templates:
        if template.get("id") == template_id:
            return template.get("text", "")
    
    # Fallback
    return "🎨 Попробуй AI Studio — генерация контента за секунды!"


def get_referral_link(user_id: int, bot_username: str) -> str:
    """Generate referral link for user.
    
    Args:
        user_id: User ID
        bot_username: Bot username
    
    Returns:
        Referral link
    """
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


async def track_referral(
    inviter_id: int,
    invitee_id: int,
    pool=None,
) -> Tuple[bool, int, int]:
    """Track referral and award bonuses.
    
    Args:
        inviter_id: User who invited
        invitee_id: New user
        pool: DB pool (optional)
    
    Returns:
        (success, inviter_bonus_credits, invitee_bonus_credits)
    """
    config = load_rewards_config()
    bonus_config = config.get("referral_bonus_per_user", {})
    
    inviter_bonus = bonus_config.get("inviter_bonus", 2)
    invitee_bonus = bonus_config.get("invitee_bonus", 1)
    
    try:
        if pool:
            async with pool.acquire() as conn:
                # Record referral
                await conn.execute(
                    """
                    INSERT INTO referrals (inviter_id, invitee_id, created_at, bonus_awarded)
                    VALUES ($1, $2, NOW(), TRUE)
                    """,
                    inviter_id,
                    invitee_id,
                )
                
                # Award bonuses
                # (This would integrate with credits/free_runs system)
                
                log.info(f"Tracked referral: {inviter_id} -> {invitee_id}")
                return True, inviter_bonus, invitee_bonus
                
    except Exception as e:
        log.error(f"Failed to track referral: {e}")
    
    return False, 0, 0


async def get_referral_count(user_id: int, pool=None) -> int:
    """Get user's successful referral count.
    
    Args:
        user_id: User ID
        pool: DB pool (optional)
    
    Returns:
        Referral count
    """
    try:
        if pool:
            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM referrals WHERE inviter_id = $1",
                    user_id,
                )
                return count or 0
    except Exception as e:
        log.warning(f"Failed to get referral count: {e}")
    
    return 0


async def get_unclaimed_rewards(user_id: int, pool=None) -> List[Dict]:
    """Get list of unclaimed tier rewards.
    
    Args:
        user_id: User ID
        pool: DB pool (optional)
    
    Returns:
        List of unclaimed reward dicts
    """
    referral_count = await get_referral_count(user_id, pool)
    config = load_rewards_config()
    tiers = config.get("tiers", [])
    
    unclaimed = []
    
    try:
        if pool:
            async with pool.acquire() as conn:
                claimed_tiers = await conn.fetch(
                    "SELECT tier_referrals_needed FROM referral_tier_claims WHERE user_id = $1",
                    user_id,
                )
                claimed_set = {row["tier_referrals_needed"] for row in claimed_tiers}
        else:
            claimed_set = set()
    except Exception as e:
        log.warning(f"Failed to check claimed rewards: {e}")
        claimed_set = set()
    
    # Find unclaimed tiers
    for tier in tiers:
        needed = tier["referrals_needed"]
        if referral_count >= needed and needed not in claimed_set:
            unclaimed.append(tier)
    
    return unclaimed


async def claim_tier_reward(
    user_id: int,
    tier_referrals_needed: int,
    pool=None,
) -> bool:
    """Claim tier reward.
    
    Args:
        user_id: User ID
        tier_referrals_needed: Tier to claim
        pool: DB pool (optional)
    
    Returns:
        True if claimed
    """
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO referral_tier_claims (user_id, tier_referrals_needed, claimed_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    user_id,
                    tier_referrals_needed,
                )
                log.info(f"Claimed tier reward: user={user_id}, tier={tier_referrals_needed}")
                return True
    except Exception as e:
        log.error(f"Failed to claim tier reward: {e}")
    
    return False
