import sqlite3
import pandas as pd
from app.config import settings

def get_db_connection(db_path: str = settings.db_path) -> sqlite3.Connection:
    """Returns a SQLite connection for the specified database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query: str, params: tuple = (), db_path: str = settings.db_path) -> list[dict]:
    """Executes a query and returns the results as a list of dictionaries."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def execute_query_df(query: str, params: tuple = (), db_path: str = settings.db_path) -> pd.DataFrame:
    """Executes a query and returns the results as a pandas DataFrame."""
    with get_db_connection(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)

def execute_write(query: str, params: tuple = (), db_path: str = settings.db_path):
    """Executes a write query (INSERT, UPDATE, DELETE)."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
