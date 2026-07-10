from sqlalchemy import create_engine, text
import pandas as pd

DB_CONN_ID = "euenergy_db"

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        try:
            from airflow.hooks.base import BaseHook
            c = BaseHook.get_connection(DB_CONN_ID)
            url = f"postgresql+psycopg2://{c.login}:{c.password}@{c.host}:{c.port or 5432}/{c.schema}"
        except Exception:
            from dataflow import Dataflow
            c = Dataflow().connection(DB_CONN_ID, mode='dict')
            url = f"postgresql+psycopg2://{c['login']}:{c['password']}@{c['host']}:{c.get('port', 5432)}/{c['schema']}"
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def query(sql: str, **kwargs) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=kwargs)
