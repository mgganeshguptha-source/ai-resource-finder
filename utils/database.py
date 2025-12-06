"""
Database connection utilities for PostgreSQL with pgvector
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any, List
from contextlib import contextmanager


class DatabaseManager:
    """
    Manages PostgreSQL database connections with pgvector support
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            connection_string: PostgreSQL connection URL
        """
        self.connection_string = connection_string or os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
        if not self.connection_string:
            raise ValueError("Database connection string not provided")
        
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            print("✅ Connected to PostgreSQL database")
        except Exception as e:
            print(f"❌ Failed to connect to PostgreSQL: {str(e)}")
            raise
    
    def _ensure_connection(self):
        """Ensure database connection is alive"""
        if self.conn is None or self.conn.closed:
            self._connect()
    
    @contextmanager
    def get_cursor(self, cursor_factory=None):
        """
        Context manager for database cursors
        
        Args:
            cursor_factory: Cursor factory (e.g., RealDictCursor)
        """
        self._ensure_connection()
        cursor = self.conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = True) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SELECT query and return results
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch_one: Return single row
            fetch_all: Return all rows
            
        Returns:
            Query results as list of dicts
        """
        with self.get_cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch_one:
                result = cur.fetchone()
                return dict(result) if result else None
            elif fetch_all:
                results = cur.fetchall()
                return [dict(row) for row in results]
            return None
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute batch insert/update
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            Total number of affected rows
        """
        from psycopg2.extras import execute_batch
        
        self._ensure_connection()
        with self.conn.cursor() as cur:
            execute_batch(cur, query, params_list, page_size=100)
            self.conn.commit()
            return len(params_list)
    
    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()
            print("✅ Closed PostgreSQL connection")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Singleton instance (optional, for convenience)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(connection_string: Optional[str] = None) -> DatabaseManager:
    """
    Get or create database manager instance
    
    Args:
        connection_string: Optional connection string
        
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(connection_string)
    return _db_manager


