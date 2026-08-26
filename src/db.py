import os
import psycopg2
import psycopg2.extras

DB_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://postgres:{os.environ['SUPABASE_DB_PASSWORD']}@"
    f"{os.environ.get('SUPABASE_DB_HOST', 'db.grkqkfaetnmwtloiouoa.supabase.co')}:"
    f"{os.environ.get('SUPABASE_DB_PORT', '5432')}/"
    f"{os.environ.get('SUPABASE_DB_NAME', 'postgres')}?sslmode=require"
)


def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def fetch_all(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def fetch_one(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def execute(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.fetchall()
    finally:
        conn.close()


def execute_many(sql, params_list):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, params_list)
            conn.commit()
    finally:
        conn.close()
