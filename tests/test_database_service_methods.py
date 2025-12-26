"""Tests for DatabaseService wrapper methods."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from contextlib import asynccontextmanager
from app.database.services import DatabaseService


class MockConnection:
    """Mock asyncpg connection."""
    def __init__(self):
        self.execute = AsyncMock(return_value="EXECUTED")
        self.fetchrow = AsyncMock(return_value={"id": 1, "value": "test"})
        self.fetchval = AsyncMock(return_value=42)
        self.fetch = AsyncMock(return_value=[{"id": 1}, {"id": 2}])


class MockPool:
    """Mock asyncpg pool with proper context manager."""
    def __init__(self):
        self.conn = MockConnection()
        self.acquired_count = 0
        self.released_count = 0
    
    async def acquire(self):
        """Async acquire method (returns connection)."""
        self.acquired_count += 1
        return self.conn
    
    async def release(self, conn):
        """Async release method."""
        self.released_count += 1


class MockPoolWithContextManager:
    """Mock asyncpg pool with context manager for execute/fetch methods."""
    def __init__(self):
        self.conn = MockConnection()
        self.acquired_count = 0
        self.released_count = 0
    
    @asynccontextmanager
    async def acquire(self):
        """Async context manager for acquiring connection."""
        self.acquired_count += 1
        try:
            yield self.conn
        finally:
            self.released_count += 1


@pytest.fixture
def mock_db():
    """Create DatabaseService with mocked pool (context manager for execute/fetch)."""
    db = DatabaseService("postgresql://test")
    db._pool = MockPoolWithContextManager()
    return db


@pytest.fixture
def mock_db_for_get_connection():
    """Create DatabaseService with mocked pool (acquire/release for get_connection)."""
    db = DatabaseService("postgresql://test")
    db._pool = MockPool()
    return db


@pytest.mark.asyncio
async def test_execute_method_exists(mock_db):
    """Test that execute method exists and works."""
    result = await mock_db.execute("INSERT INTO test VALUES ($1)", 123)
    
    assert result == "EXECUTED"
    mock_db._pool.conn.execute.assert_called_once_with("INSERT INTO test VALUES ($1)", 123)


@pytest.mark.asyncio
async def test_fetchrow_method_exists(mock_db):
    """Test that fetchrow method exists and works."""
    result = await mock_db.fetchrow("SELECT * FROM test WHERE id = $1", 1)
    
    assert result == {"id": 1, "value": "test"}
    mock_db._pool.conn.fetchrow.assert_called_once_with("SELECT * FROM test WHERE id = $1", 1)


@pytest.mark.asyncio
async def test_fetchval_method_exists(mock_db):
    """Test that fetchval method exists and works."""
    result = await mock_db.fetchval("SELECT COUNT(*) FROM test")
    
    assert result == 42
    mock_db._pool.conn.fetchval.assert_called_once_with("SELECT COUNT(*) FROM test")


@pytest.mark.asyncio
async def test_fetch_method_exists(mock_db):
    """Test that fetch method exists and works."""
    result = await mock_db.fetch("SELECT * FROM test")
    
    assert result == [{"id": 1}, {"id": 2}]
    mock_db._pool.conn.fetch.assert_called_once_with("SELECT * FROM test")


@pytest.mark.asyncio
async def test_get_connection_context_manager(mock_db_for_get_connection):
    """Test that get_connection works as context manager."""
    async with mock_db_for_get_connection.get_connection() as conn:
        assert isinstance(conn, MockConnection)
    
    assert mock_db_for_get_connection._pool.acquired_count == 1
    assert mock_db_for_get_connection._pool.released_count == 1


def test_database_service_has_all_methods():
    """Test that DatabaseService has all required methods."""
    db = DatabaseService("postgresql://test")
    
    assert hasattr(db, "execute")
    assert hasattr(db, "fetchrow")
    assert hasattr(db, "fetchval")
    assert hasattr(db, "fetch")
    assert hasattr(db, "get_connection")
    
    assert callable(db.execute)
    assert callable(db.fetchrow)
    assert callable(db.fetchval)
    assert callable(db.fetch)
    assert callable(db.get_connection)

