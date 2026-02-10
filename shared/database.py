"""
Shared database utilities for all microservices
"""
import os
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

class DatabasePool:
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        self._pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            host=os.getenv('DB_HOST', 'postgres'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'voting_db'),
            user=os.getenv('DB_USER', 'voting_user'),
            password=os.getenv('DB_PASSWORD', 'voting_pass')
        )
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, commit=True):
        """Context manager for database cursors"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

# Singleton instance
db_pool = DatabasePool()
