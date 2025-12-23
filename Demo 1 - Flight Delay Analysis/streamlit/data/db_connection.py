import streamlit as st
from airflow.providers.postgres.hooks.postgres import PostgresHook

@st.cache_resource
def get_engine():
    hook = PostgresHook(postgres_conn_id="demo_db")
    return hook.get_sqlalchemy_engine()

def get_db():
    engine = get_engine()
    return engine.connect()
