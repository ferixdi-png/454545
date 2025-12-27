"""Build version info for deployment tracking."""
import os
import subprocess
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_git_commit() -> str:
    """Get current git commit hash."""
    try:
        # Try Render env var first (set by Render automatically)
        render_commit = os.getenv("RENDER_GIT_COMMIT")
        if render_commit:
            return render_commit[:8]  # Short hash
        
        # Try git command
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.debug(f"Could not get git commit: {e}")
    
    return "unknown"


def get_build_date() -> str:
    """Get build/deploy date."""
    # Try Render deploy timestamp
    render_deploy = os.getenv("RENDER_SERVICE_DEPLOY_TIMESTAMP")
    if render_deploy:
        try:
            ts = int(render_deploy) / 1000  # milliseconds to seconds
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass
    
    # Fallback: current time
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def get_version_string() -> str:
    """Get full version string for logging."""
    commit = get_git_commit()
    build_date = get_build_date()
    
    # Include Render service name if available
    service = os.getenv("RENDER_SERVICE_NAME", "local")
    
    return f"{service}@{commit} ({build_date})"


def log_version_info():
    """Log version info at startup."""
    version = get_version_string()
    commit = get_git_commit()
    
    logger.info("=" * 60)
    logger.info(f"🚀 BUILD VERSION: {version}")
    logger.info(f"📦 Commit: {commit}")
    logger.info(f"🌍 Service: {os.getenv('RENDER_SERVICE_NAME', 'local')}")
    logger.info(f"🔗 Region: {os.getenv('RENDER_REGION', 'unknown')}")
    logger.info("=" * 60)


def get_admin_version_info() -> str:
    """Get version info for admin /start message."""
    commit = get_git_commit()
    build_date = get_build_date()
    service = os.getenv("RENDER_SERVICE_NAME", "local")
    
    return f"<code>{service}@{commit}</code> • {build_date}"
