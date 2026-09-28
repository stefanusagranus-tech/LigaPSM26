import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="LigaPSM Supabase Test", layout="wide")

st.title("🔌 Test Supabase Connector")
result = test_connection()

if result["client_ok"]:
    st.success("✅ Client OK")
    st.json(result["tables"])
else:
    st.error("❌ Client gagal")
    st.json(result["errors"])
