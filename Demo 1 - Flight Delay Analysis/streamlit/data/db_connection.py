import streamlit as st
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.sqlite.hooks.sqlite import SqliteHook


@st.cache_resource
def get_engine():
    try:
        pg_hook = PostgresHook(postgres_conn_id="demo_db")
        engine = pg_hook.get_sqlalchemy_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return engine
    except Exception:
        sqlite_hook = SqliteHook(sqlite_conn_id="demo_db")
        engine = sqlite_hook.get_sqlalchemy_engine()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return engine


def get_db():
    engine = get_engine()
    return engine.connect()