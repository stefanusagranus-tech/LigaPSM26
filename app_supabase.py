import streamlit as st
from supabase_connector import test_connection, load_periode_store_supabase, load_daily_performance_supabase

st.title("🧪 Test v2 — Supabase Connector")

# Test 1: Connection
result = test_connection()
st.json(result)

# Test 2: Periode Store
st.markdown("### 📊 Periode Store")
df_periode = load_periode_store_supabase()
st.dataframe(df_periode)

# Test 3: Daily Performance
st.markdown("### 📊 Daily Performance")
df_daily = load_daily_performance_supabase()
st.dataframe(df_daily)
