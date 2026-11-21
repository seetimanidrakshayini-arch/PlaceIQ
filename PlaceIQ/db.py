"""Small PyMySQL helper layer: one connection per request."""
import pymysql
from flask import g
from config import Config


def connect(database=True):
    return pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        database=Config.DB_NAME if database else None,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=None):
    """Return list of dict rows."""
    with get_db().cursor() as cur:
        cur.execute(sql, args or ())
        return cur.fetchall()


def one(sql, args=None):
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=None):
    """Run INSERT/UPDATE/DELETE; return lastrowid."""
    with get_db().cursor() as cur:
        cur.execute(sql, args or ())
        return cur.lastrowid


def transaction():
    """Context manager for multi-statement atomic work."""
    return _Tx(get_db())


class _Tx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.autocommit(False)
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.conn.autocommit(True)
        return False
