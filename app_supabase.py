import streamlit as st
from supabase_connector import test_connection, test_daily_performance

st.title("🧪 Test v2 — Supabase Connector")

# Test 1: Connection
st.markdown("### 1️⃣ Test Connection")
result = test_connection()
st.json(result)

# Test 2: Daily Performance
st.markdown("### 2️⃣ Test Daily Performance")
result_dp = test_daily_performance()
st.json(result_dp)
