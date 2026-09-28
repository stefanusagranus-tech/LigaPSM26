"""
Migrasi Google Sheets → Supabase
=================================
Script ini migrasi data per sheet, satu-satu.

Usage:
    1. Pastikan secrets punya [connections.gsheets] dan [supabase]
    2. Jalankan: streamlit run migrasi_sheets_to_supabase.py
    3. Pilih sheet yang mau di-migrasi
    4. Klik "Migrasi"

Author: LigaPSM Team
Version: 1.0
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime

from streamlit_gsheets import GSheetsConnection
from supabase_connector import init_supabase_admin, sb_count


st.set_page_config(page_title="Migrasi Sheets → Supabase", layout="wide")

# =========================================================
# KONFIGURASI MIGRASI
# =========================================================
MIGRATION_MAP = {
    "MASTER_PERSONIL": {
        "table": "master_personil",
        "columns": {
            "person_id": "person_id",
            "person_name": "person_name",
            "username": "username",
            "password": "password",
            "role": "role",
            "active": "active",
        },
        "required": ["person_id", "person_name"],
        "conflict_key": "person_id",
    },
    "PERIODE": {
        "table": "periode_psm",
        "columns": {
            "period_id": "period_id",
            "period_name": "period_name",
            "start_date": "start_date",
            "end_date": "end_date",
        },
        "required": ["period_id", "period_name"],
        "conflict_key": "period_id",
    },
    "MASTER_ITEM": {
        "table": "master_item",
        "columns": {
            "period_id": "period_id",
            "item_id": "item_id",
            "item_name": "item_name",
            "category": "category",
            "active": "active",
        },
        "required": ["period_id", "item_id", "item_name"],
        "conflict_key": "item_id",
    },
    "PERIODE_PPS": {
        "table": "periode_pps",
        "columns": {
            "period_id": "period_id",
            "period_name": "period_name",
            "start_date": "start_date",
            "end_date": "end_date",
            "target_total": "target_total",
            "target_personil": "target_personil",
            "status": "status",
            "syarat_total": "syarat_total",
            "redeem_total": "redeem_total",
            "actual_qty": "actual_qty",
        },
        "required": ["period_id", "period_name"],
        "conflict_key": "period_id",
    },
    "PERIODE_STOREPERFORMANCE": {
        "table": "periode_store",
        "columns": {
            "period_id": "period_id",
            "period_name": "period_name",
            "start_date": "start_date",
            "end_date": "end_date",
            "target_net_sales": "target_net_sales",
            "target_std": "target_std",
            "target_apc": "target_apc",
            "target_gm": "target_gm_pct",       # rename
            "target_gm_pct": "target_gm_pct",
            "nsb_percentage": "nsb_percentage",
            "status": "status",
        },
        "required": ["period_id"],
        "conflict_key": "period_id",
    },
    "SALES_ITEM": {
        "table": "sales_item",
        "columns": {
            "record_id": "record_id",
            "period_id": "period_id",
            "item_id": "item_id",
            "item_name": "item_name",
            "target_qty": "target_qty",
            "target_kasir": "target_kasir",
            "actual_qty": "actual_qty",
            "updated_at": "updated_at",
        },
        "required": ["record_id", "period_id", "item_id"],
        "conflict_key": "record_id",
    },
    "SALES_PERSONIL": {
        "table": "sales_personil",
        "columns": {
            "record_id": "record_id",
            "period_id": "period_id",
            "item_id": "item_id",
            "item_name": "item_name",
            "person_id": "person_id",
            "person_name": "person_name",
            "actual_qty": "actual_qty",
            "shift_personil": "shift_personil",
            "updated_at": "updated_at",
        },
        "required": ["record_id", "period_id", "person_name"],
        "conflict_key": "record_id",
    },
    "SALES_PPS": {
        "table": "sales_pps",
        "columns": {
            "record_id": "record_id",
            "period_id": "period_id",
            "shift_personil": "shift_personil",
            "staff_name": "staff_name",
            "person_id": "person_id",
            "kasir_name": "kasir_name",
            "syarat_pwp": "syarat_pwp",
            "redeem_pwp": "redeem_pwp",
            "qty_pwp": "qty_pwp",
            "qty_sg": "qty_sg",
            "syarat_sueger": "syarat_sueger",
            "redeem_sueger": "redeem_sueger",
            "cemilan_ceban": "cemilan_ceban",
            "updated_at": "updated_at",
        },
        "required": ["record_id", "kasir_name"],
        "conflict_key": "record_id",
    },
    "SALES_STOREPERFORMANCE": {
        "table": "sales_store",
        "columns": {
            "record_id": "record_id",
            "tanggal": "tanggal",
            "spd": "spd",
            "std": "std",
            "apc": "apc",
            "nsb_target": "nsb_target",
            "nsb_actual": "nsb_actual",
            "keterangan": "keterangan",
            "input_by": "input_by",
            "updated_at": "updated_at",
        },
        "required": ["record_id", "tanggal"],
        "conflict_key": "record_id",
    },
}


# =========================================================
# MAIN UI
# =========================================================
st.title("🔄 Migrasi Google Sheets → Supabase")
st.caption(f"Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

st.warning("⚠️ **PENTING:** Backup Google Sheets dulu sebelum migrasi!")

# Cek connection
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    sb = init_supabase_admin()
    if sb is None:
        st.error("❌ Supabase admin gagal init. Cek secrets.")
        st.stop()
    st.success("✅ Koneksi siap (Sheets + Supabase)")
except Exception as e:
    st.error(f"❌ Gagal koneksi: {e}")
    st.stop()

st.markdown("---")

# =========================================================
# PILIH SHEET
# =========================================================
st.markdown("### 📋 Pilih Sheet yang Mau Di-migrasi")

sheet_list = list(MIGRATION_MAP.keys())
selected_sheets = st.multiselect(
    "Pilih 1 atau lebih sheet:",
    sheet_list,
    default=["MASTER_PERSONIL"],  # default: yang paling kecil
    key="migration_select"
)

if not selected_sheets:
    st.info("👆 Pilih minimal 1 sheet untuk migrasi")
    st.stop()

# =========================================================
# PREVIEW
# =========================================================
st.markdown("---")
st.markdown("### 👁️ Preview Data")

preview_data = {}
for sheet_name in selected_sheets:
    config = MIGRATION_MAP[sheet_name]
    
    with st.expander(f"📄 {sheet_name} → `{config['table']}`", expanded=True):
        try:
            df = conn.read(worksheet=sheet_name, ttl=60)
            if df is None or df.empty:
                st.warning(f"⚠️ Sheet `{sheet_name}` kosong")
                preview_data[sheet_name] = pd.DataFrame()
                continue
            
            df.columns = df.columns.astype(str).str.strip().str.lower()
            preview_data[sheet_name] = df
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Baris", len(df))
            with col2:
                st.metric("Kolom", len(df.columns))
            with col3:
                existing_count = sb_count(config["table"])
                st.metric("Baris di Supabase", existing_count)
            
            st.dataframe(df.head(5), use_container_width=True)
            
            # Cek kolom required
            missing = [c for c in config["required"] if c not in df.columns]
            if missing:
                st.error(f"❌ Kolom wajib tidak ada: {missing}")
        except Exception as e:
            st.error(f"❌ Gagal baca sheet: {e}")
            preview_data[sheet_name] = pd.DataFrame()

# =========================================================
# MIGRASI
# =========================================================
st.markdown("---")
st.markdown("### 🚀 Jalankan Migrasi")

mode = st.radio(
    "Mode migrasi:",
    ["Insert (kalau ada duplikat akan error)", "Upsert (update kalau duplikat)"],
    key="migration_mode"
)

mode_key = "insert" if "Insert" in mode else "upsert"

if st.button("🚀 MULAI MIGRASI", type="primary", use_container_width=True):
    overall_result = {}
    
    for sheet_name in selected_sheets:
        config = MIGRATION_MAP[sheet_name]
        df = preview_data.get(sheet_name, pd.DataFrame())
        
        if df.empty:
            overall_result[sheet_name] = {"status": "skipped", "reason": "empty"}
            continue
        
        with st.spinner(f"⏳ Migrasi {sheet_name}..."):
            try:
                # Rename kolom sesuai mapping
                rename_map = {k: v for k, v in config["columns"].items() if k in df.columns}
                df_renamed = df.rename(columns=rename_map)
                
                # Filter kolom yang ada di target table
                target_cols = list(config["columns"].values())
                available_cols = [c for c in target_cols if c in df_renamed.columns]
                df_final = df_renamed[available_cols].copy()
                
                # Convert tipe data
                for col in df_final.columns:
                    if "date" in col.lower() or col == "tanggal":
                        df_final[col] = pd.to_datetime(df_final[col], errors="coerce").dt.strftime("%Y-%m-%d")
                    elif df_final[col].dtype == "object":
                        df_final[col] = df_final[col].astype(str).replace("nan", None).replace("", None)
                    elif df_final[col].dtype == "bool":
                        pass
                
                # Convert ke list of dict
                records = df_final.where(pd.notna(df_final), None).to_dict("records")
                
                # Batch insert
                batch_size = 500
                total_ok = 0
                errors = []
                
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    
                    if mode_key == "insert":
                        result = sb.table(config["table"]).insert(batch).execute()
                    else:
                        result = sb.table(config["table"]).upsert(
                            batch, on_conflict=config["conflict_key"]
                        ).execute()
                    
                    if result.data:
                        total_ok += len(result.data)
                    else:
                        errors.append(f"Batch {i//batch_size + 1}: no data returned")
                    
                    time.sleep(0.3)
                
                overall_result[sheet_name] = {
                    "status": "success",
                    "inserted": total_ok,
                    "total": len(records),
                    "errors": errors,
                }
            
            except Exception as e:
                overall_result[sheet_name] = {
                    "status": "failed",
                    "error": str(e)[:200],
                }
    
    # Tampilkan hasil
    st.markdown("---")
    st.markdown("### 📊 Hasil Migrasi")
    
    for sheet_name, res in overall_result.items():
        if res["status"] == "success":
            st.success(
                f"✅ **{sheet_name}**: {res['inserted']}/{res['total']} baris berhasil"
            )
            if res.get("errors"):
                with st.expander(f"⚠️ {len(res['errors'])} warning"):
                    for e in res["errors"]:
                        st.write(f"  - {e}")
        elif res["status"] == "skipped":
            st.info(f"⏭️ **{sheet_name}**: skip ({res.get('reason', 'kosong')})")
        else:
            st.error(f"❌ **{sheet_name}**: {res.get('error', 'unknown')}")
    
    st.balloons()
    st.caption("Refresh halaman untuk cek migrasi berikutnya")
