"""Projects and history management with graceful DB fallback.

FEATURES:
- Save generations to projects
- View history
- DB-first, in-memory fallback
- No crashes if DB unavailable
"""
import logging
from typing import List, Optional, Dict
from datetime import datetime
import asyncio

log = logging.getLogger(__name__)

# In-memory fallback storage
_memory_projects: Dict[int, List[Dict]] = {}  # user_id -> list of projects
_memory_history: Dict[int, List[Dict]] = {}  # user_id -> list of generations


class Project:
    """Project container for generations."""
    
    def __init__(
        self,
        user_id: int,
        name: str,
        project_id: Optional[int] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.project_id = project_id or hash(f"{user_id}_{name}_{datetime.utcnow()}")
        self.user_id = user_id
        self.name = name
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.generations: List[Dict] = []
    
    def to_dict(self) -> Dict:
        return {
            "project_id": self.project_id,
            "user_id": self.user_id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
            "generations": self.generations,
        }


async def save_to_project(
    user_id: int,
    project_name: str,
    generation_data: Dict,
    pool=None,
) -> bool:
    """Save generation to project (DB-first, fallback to memory).
    
    Args:
        user_id: User ID
        project_name: Project name (creates if doesn't exist)
        generation_data: Dict with model_id, format, prompt, result_url, created_at
        pool: Database pool (optional)
    
    Returns:
        True if saved successfully
    """
    try:
        if pool:
            # Try DB
            async with pool.acquire() as conn:
                # Get or create project
                project_id = await conn.fetchval(
                    """
                    INSERT INTO projects (user_id, name, created_at, updated_at)
                    VALUES ($1, $2, NOW(), NOW())
                    ON CONFLICT (user_id, name) 
                    DO UPDATE SET updated_at = NOW()
                    RETURNING project_id
                    """,
                    user_id,
                    project_name,
                )
                
                # Save generation
                await conn.execute(
                    """
                    INSERT INTO project_generations 
                    (project_id, model_id, format, prompt, result_url, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    project_id,
                    generation_data.get("model_id"),
                    generation_data.get("format"),
                    generation_data.get("prompt"),
                    generation_data.get("result_url"),
                    generation_data.get("created_at", datetime.utcnow()),
                )
                
                log.info(f"Saved generation to project {project_name} (DB)")
                return True
                
    except Exception as e:
        log.warning(f"DB save failed, using memory fallback: {e}")
    
    # Fallback to memory
    if user_id not in _memory_projects:
        _memory_projects[user_id] = []
    
    # Find or create project
    project = None
    for p in _memory_projects[user_id]:
        if p["name"] == project_name:
            project = p
            break
    
    if not project:
        project = {
            "project_id": hash(f"{user_id}_{project_name}_{datetime.utcnow()}"),
            "name": project_name,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "generations": [],
        }
        _memory_projects[user_id].append(project)
    
    # Add generation
    project["generations"].append({
        **generation_data,
        "created_at": generation_data.get("created_at", datetime.utcnow()).isoformat()
            if isinstance(generation_data.get("created_at"), datetime)
            else generation_data.get("created_at", datetime.utcnow().isoformat()),
    })
    project["updated_at"] = datetime.utcnow().isoformat()
    
    # Keep only last 50 generations per project
    project["generations"] = project["generations"][-50:]
    
    log.info(f"Saved generation to project {project_name} (memory)")
    return True


async def get_user_projects(
    user_id: int,
    limit: int = 10,
    pool=None,
) -> List[Dict]:
    """Get user's projects with last generations.
    
    Args:
        user_id: User ID
        limit: Max projects to return
        pool: Database pool (optional)
    
    Returns:
        List of project dicts with generations
    """
    try:
        if pool:
            # Try DB
            async with pool.acquire() as conn:
                projects = await conn.fetch(
                    """
                    SELECT 
                        p.project_id,
                        p.name,
                        p.created_at,
                        p.updated_at,
                        COUNT(g.id) as generation_count
                    FROM projects p
                    LEFT JOIN project_generations g ON p.project_id = g.project_id
                    WHERE p.user_id = $1
                    GROUP BY p.project_id, p.name, p.created_at, p.updated_at
                    ORDER BY p.updated_at DESC
                    LIMIT $2
                    """,
                    user_id,
                    limit,
                )
                
                result = []
                for project in projects:
                    # Get last 5 generations
                    gens = await conn.fetch(
                        """
                        SELECT model_id, format, prompt, result_url, created_at
                        FROM project_generations
                        WHERE project_id = $1
                        ORDER BY created_at DESC
                        LIMIT 5
                        """,
                        project["project_id"],
                    )
                    
                    result.append({
                        "project_id": project["project_id"],
                        "name": project["name"],
                        "created_at": project["created_at"].isoformat() if hasattr(project["created_at"], "isoformat") else project["created_at"],
                        "updated_at": project["updated_at"].isoformat() if hasattr(project["updated_at"], "isoformat") else project["updated_at"],
                        "generation_count": project["generation_count"],
                        "last_generations": [dict(g) for g in gens],
                    })
                
                log.info(f"Loaded {len(result)} projects from DB")
                return result
                
    except Exception as e:
        log.warning(f"DB read failed, using memory fallback: {e}")
    
    # Fallback to memory
    projects = _memory_projects.get(user_id, [])
    
    result = []
    for p in sorted(projects, key=lambda x: x["updated_at"], reverse=True)[:limit]:
        result.append({
            **p,
            "generation_count": len(p["generations"]),
            "last_generations": p["generations"][-5:],
        })
    
    log.info(f"Loaded {len(result)} projects from memory")
    return result


async def get_user_history(
    user_id: int,
    limit: int = 10,
    pool=None,
) -> List[Dict]:
    """Get user's recent generation history across all projects.
    
    Args:
        user_id: User ID
        limit: Max items to return
        pool: Database pool (optional)
    
    Returns:
        List of generation dicts
    """
    try:
        if pool:
            # Try DB
            async with pool.acquire() as conn:
                history = await conn.fetch(
                    """
                    SELECT 
                        g.model_id,
                        g.format,
                        g.prompt,
                        g.result_url,
                        g.created_at,
                        p.name as project_name
                    FROM project_generations g
                    LEFT JOIN projects p ON g.project_id = p.project_id
                    WHERE p.user_id = $1
                    ORDER BY g.created_at DESC
                    LIMIT $2
                    """,
                    user_id,
                    limit,
                )
                
                log.info(f"Loaded {len(history)} history items from DB")
                return [dict(h) for h in history]
                
    except Exception as e:
        log.warning(f"DB history read failed, using memory fallback: {e}")
    
    # Fallback to memory
    if user_id not in _memory_history:
        _memory_history[user_id] = []
    
    history = sorted(
        _memory_history[user_id],
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )[:limit]
    
    log.info(f"Loaded {len(history)} history items from memory")
    return history


async def add_to_history(
    user_id: int,
    generation_data: Dict,
    pool=None,
) -> bool:
    """Add generation to history (quick access, no project).
    
    Args:
        user_id: User ID
        generation_data: Generation data dict
        pool: Database pool (optional)
    
    Returns:
        True if saved
    """
    # History is automatically tracked via projects in DB
    # For memory fallback, track separately
    
    if user_id not in _memory_history:
        _memory_history[user_id] = []
    
    _memory_history[user_id].append({
        **generation_data,
        "created_at": generation_data.get("created_at", datetime.utcnow()).isoformat()
            if isinstance(generation_data.get("created_at"), datetime)
            else generation_data.get("created_at", datetime.utcnow().isoformat()),
    })
    
    # Keep only last 100
    _memory_history[user_id] = _memory_history[user_id][-100:]
    
    return True


async def delete_project(
    user_id: int,
    project_id: int,
    pool=None,
) -> bool:
    """Soft delete project.
    
    Args:
        user_id: User ID
        project_id: Project ID
        pool: Database pool (optional)
    
    Returns:
        True if deleted
    """
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE projects SET deleted_at = NOW() WHERE project_id = $1 AND user_id = $2",
                    project_id,
                    user_id,
                )
                log.info(f"Soft deleted project {project_id} from DB")
                return True
    except Exception as e:
        log.warning(f"DB delete failed, using memory fallback: {e}")
    
    # Memory fallback
    if user_id in _memory_projects:
        _memory_projects[user_id] = [
            p for p in _memory_projects[user_id]
            if p["project_id"] != project_id
        ]
        log.info(f"Deleted project {project_id} from memory")
    
    return True


def is_db_available(pool) -> bool:
    """Check if DB is available.
    
    Args:
        pool: Database pool
    
    Returns:
        True if DB can be used
    """
    return pool is not None
