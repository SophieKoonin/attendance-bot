from urllib.parse import urlparse
import psycopg2
import os

def connect_to_db():
    url = urlparse(os.environ.get("DATABASE_URL"))

    return psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )

def commit_or_rollback(db):
    try:
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        pass

def execute_with_cursor(db, query, *args):
    try:
        cur = db.cursor()
        cur.execute(query, *args)
        return cur
    except psycopg2.Error as e:
        return None

def executemany_with_cursor(db, query, *args):
    try:
        cur = db.cursor()
        cur.executemany(query, *args)
        return cur
    except psycopg2.Error as e:
        return None

def execute_fetchone(db, query, *args):
    res = execute_with_cursor(db, query, *args)
    if res is None:
        return res
    return res.fetchone()

def execute_fetchall(db, query, *args):
    res = execute_with_cursor(db, query, *args)
    if res is None:
        return res
    return res.fetchall()

def execute_and_commit(db, query, *args):
    execute_with_cursor(db, query, *args)
    commit_or_rollback(db)

def executemany_and_commit(db, query, *args):
    executemany_with_cursor(db, query, *args)
    commit_or_rollback(db)