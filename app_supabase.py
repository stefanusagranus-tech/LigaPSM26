import streamlit as st
from supabase_connector import test_connection

st.set_page_config(page_title="LigaPSM Supabase", layout="wide")
st.title("🔌 Test Supabase Connector")
st.caption(f"Test time: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

try:
    result = test_connection()
    
    if result["client_ok"]:
        st.success("✅ Supabase Client OK")
    else:
        st.error("❌ Supabase Client GAGAL init")
        st.json(result["errors"])
        st.stop()
    
    st.markdown("### 📊 Jumlah Baris per Tabel")
    
    # Tampilkan sebagai table
    import pandas as pd
    tables_data = []
    for table_name, count in result["tables"].items():
        tables_data.append({
            "Tabel": table_name,
            "Jumlah Baris": count,
        })
    
    df = pd.DataFrame(tables_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Ringkasan
    st.markdown("---")
    total_errors = sum(1 for v in result["tables"].values() if isinstance(v, str) and v.startswith("❌"))
    if total_errors == 0:
        st.success(f"✅ Semua {len(result['tables'])} tabel bisa diakses!")
    else:
        st.warning(f"⚠️ {total_errors} tabel bermasalah")
    
    if result["errors"]:
        with st.expander("⚠️ Error detail"):
            st.json(result["errors"])

except Exception as e:
    st.error(f"❌ Error: {e}")
    st.exception(e)
