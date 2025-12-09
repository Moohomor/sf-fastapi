import psycopg2
import os
import utils
from loguru import logger

conn = psycopg2.connect(os.environ['DB_PATH'])
cur = conn.cursor()

cur.execute("SELECT version();")

logger.info(cur.fetchone())
cur.close()


sessions = {}