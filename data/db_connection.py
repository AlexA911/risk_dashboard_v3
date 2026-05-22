import pyodbc
import warnings
import sys
import os
from contextlib import contextmanager
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASES

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable"
)

@contextmanager
def get_connection(db_name: str = "ff_risk"):
    """
    Context manager that opens and properly closes a pyodbc connection.
    Usage: with get_connection() as conn:
    """
    cfg = DATABASES[db_name]
    conn_str = (
        f"DRIVER={{{cfg['driver']}}};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        "Trusted_Connection=yes;"
    )
    conn = pyodbc.connect(conn_str, readonly=True)
    try:
        yield conn
    finally:
        conn.close()