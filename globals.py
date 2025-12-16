import psycopg2
import os
from loguru import logger

conn = psycopg2.connect(os.environ['DB_PATH'])
cur = conn.cursor()

cur.execute("SELECT version();")

logger.info(cur.fetchone())
cur.close()

def get_conn():
    global conn
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
    except (psycopg2.InterfaceError, psycopg2.OperationalError):
        logger.warning('Connection to DB has been closed by server. Reconnecting...')
        if conn:
            try:
                conn.close()
            except:
                pass
        conn = psycopg2.connect(os.environ['DB_PATH'])
        logger.success('Connected to DB!')
    return conn

sessions = {}