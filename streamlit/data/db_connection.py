import streamlit as st
from dataflow.dataflow import Dataflow

@st.cache_resource
def get_engine():
    dataflow = Dataflow()
    return dataflow.connection("demo_db", mode="engine")

# import streamlit as st
# from sqlalchemy import create_engine

# # Cache the engine as a resource
# @st.cache_resource
# def get_engine():
#     # Replace with your actual connection string
#     uri = "postgresql://postgres.iftsexdljxsigonzeqmf:supabase_password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
#     return create_engine(uri)

# Function to get a fresh DB connection (not cached)
def get_db():
    engine = get_engine()
    return engine.connect()
