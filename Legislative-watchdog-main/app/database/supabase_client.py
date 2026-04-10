# from supabase import create_client
# import os

# # Try to import Airflow's Variable helper. If Airflow isn't installed (common
# # when running locally), fall back to environment variables. This allows the
# # Streamlit app to run without installing the full Airflow stack.
# try:
#     from airflow.models import Variable  # type: ignore
#     _HAS_AIRFLOW = True
# except Exception:
#     Variable = None
#     _HAS_AIRFLOW = False


# def _get_var(name: str) -> str | None:
#     """Return variable value from Airflow Variables when available,
#     otherwise read from environment variables. Accepts both the raw name
#     (e.g. SUPABASE_URL) and the AIRFLOW_VAR_ prefixed env var.
#     """
#     if _HAS_AIRFLOW and Variable is not None:
#         try:
#             return Variable.get(name)
#         except Exception:
#             return os.environ.get(f"AIRFLOW_VAR_{name}") or os.environ.get(name)

#     return os.environ.get(f"AIRFLOW_VAR_{name}") or os.environ.get(name)


# def get_supabase():
#     url = _get_var("SUPABASE_URL")
#     key = _get_var("SUPABASE_SERVICE_ROLE_KEY")
#     return create_client(url, key)