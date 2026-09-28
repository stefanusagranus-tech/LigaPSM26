import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="LigaPSM Supabase Test", layout="wide")

st.title("🧪 Supabase Connection Test")
st.caption(f"Test time: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

# === TEST 1: Init Client ===
try:
    sb = create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )
    st.success("✅ TEST 1: Supabase client initialized")
except Exception as e:
    st.error(f"❌ TEST 1 FAILED: {e}")
    st.stop()

# === TEST 2: Read from table ===
try:
    result = sb.table("master_personil").select("*").limit(5).execute()
    if result.data is not None:
        st.success(f"✅ TEST 2: Read successful — {len(result.data)} rows")
        if result.data:
            st.dataframe(pd.DataFrame(result.data))
        else:
            st.info("ℹ️ Table kosong (belum ada data) — ini normal")
    else:
        st.warning("⚠️ TEST 2: No data returned")
except Exception as e:
    st.error(f"❌ TEST 2 FAILED: {e}")

# === TEST 3: Insert dummy data ===
st.markdown("---")
st.markdown("### 🧪 TEST 3: Insert Dummy Data")

if st.button("🚀 Jalankan Test Insert"):
    try:
        # Insert 1 dummy row
        test_data = {
            "person_id": f"TEST_{datetime.now().strftime('%H%M%S')}",
            "person_name": "TEST USER",
            "username": f"test_{datetime.now().strftime('%H%M%S')}",
            "password": "test123",
            "role": "Staff",
            "active": True,
        }
        
        result = sb.table("master_personil").insert(test_data).execute()
        
        if result.data:
            st.success(f"✅ TEST 3: Insert successful!")
            st.json(result.data)
            
            # Cleanup: hapus data test
            test_id = result.data[0]["person_id"]
            sb.table("master_personil").delete().eq("person_id", test_id).execute()
            st.info(f"🧹 Cleanup: Test data {test_id} dihapus")
        else:
            st.error("❌ Insert returned no data")
    
    except Exception as e:
        st.error(f"❌ TEST 3 FAILED: {e}")
        st.exception(e)

# === TEST 4: Count rows ===
st.markdown("---")
st.markdown("### 📊 TEST 4: Table Count")

tables = [
    "master_personil", "master_item", "periode_psm", "periode_pps",
    "sales_item", "sales_personil", "sales_pps",
    "periode_store", "sales_store", "activity_log"
]

if st.button("🔢 Cek Jumlah Baris Semua Tabel"):
    st.markdown("| Tabel | Jumlah Baris |")
    st.markdown("|-------|--------------|")
    for t in tables:
        try:
            r = sb.table(t).select("*", count="exact").limit(1).execute()
            count = r.count if r.count is not None else len(r.data)
            st.markdown(f"| `{t}` | {count} |")
        except Exception as e:
            st.markdown(f"| `{t}` | ❌ Error |")
