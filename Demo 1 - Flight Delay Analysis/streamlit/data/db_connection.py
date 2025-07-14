import streamlit as st
from dataflow.dataflow import Dataflow

@st.cache_resource
def get_engine():
    dataflow = Dataflow()
    return dataflow.connection("demo_db", mode="engine")

def get_db():
    engine = get_engine()
    return engine.connect()
