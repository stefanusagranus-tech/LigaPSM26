"""
Migrasi Google Sheets → Supabase
=================================
Script migrasi lengkap dengan konversi tipe data otomatis.

Features:
- Konversi boolean (1.0 → true, 0.0 → false)
- Konversi tanggal (string → DATE)
- Konversi numerik (string "1.0" → int 1)
- Batch processing (500 rows per batch)
- Error handling per-batch
- Mode Insert / Upsert

Usage:
    1. Pastikan secrets punya [connections.gsheets] dan [supabase]
    2. Set main file ke migrasi_sheets_to_supabase.py
    3. Pilih sheet → klik Migrasi

Author: LigaPSM Team
Version: 1.1
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime

from streamlit_gsheets import GSheetsConnection
from supabase_connector import init_supabase_admin, sb_count


# =========================================================
# SETUP
# =========================================================
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
        "bool_cols": ["active"],
        "date_cols": [],
        "int_cols": [],
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
        "bool_cols": [],
        "date_cols": ["start_date", "end_date"],
        "int_cols": [],
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
        "bool_cols": ["active"],
        "date_cols": [],
        "int_cols": [],
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
        "bool_cols": [],
        "date_cols": ["start_date", "end_date"],
        "int_cols": ["target_total", "target_personil", "syarat_total", "redeem_total", "actual_qty"],
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
            "target_gm": "target_gm_pct",
            "target_gm_pct": "target_gm_pct",
            "nsb_percentage": "nsb_percentage",
            "status": "status",
        },
        "required": ["period_id"],
        "conflict_key": "period_id",
        "bool_cols": [],
        "date_cols": ["start_date", "end_date"],
        "int_cols": ["target_net_sales", "target_std", "target_apc"],
        "float_cols": ["target_gm_pct", "nsb_percentage"],
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
        "bool_cols": [],
        "date_cols": ["updated_at"],
        "int_cols": ["target_qty", "target_kasir", "actual_qty"],
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
        "bool_cols": [],
        "date_cols": ["updated_at"],
        "int_cols": ["actual_qty"],
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
        "bool_cols": [],
        "date_cols": ["updated_at"],
        "int_cols": ["syarat_pwp", "redeem_pwp", "qty_pwp", "qty_sg", "syarat_sueger", "redeem_sueger", "cemilan_ceban"],
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
        "bool_cols": [],
        "date_cols": ["tanggal"],
        "int_cols": ["spd", "std", "apc", "nsb_target", "nsb_actual"],
    },
}


# =========================================================
# HELPER: KONVERSI TIPE DATA
# =========================================================
def _to_bool(v) -> bool:
    """Konversi berbagai format ke boolean."""
    if pd.isna(v):
        return True  # default
    s = str(v).strip().lower()
    if s in ["1", "1.0", "true", "t", "yes", "y", "aktif", "active"]:
        return True
    elif s in ["0", "0.0", "false", "f", "no", "n", "non-aktif", "nonaktif", "inactive"]:
        return False
    else:
        return True  # default


def _to_int(v):
    """Konversi ke integer."""
    if pd.isna(v):
        return 0
    try:
        s = str(v).strip()
        if s == "" or s.lower() in ["nan", "none", "null"]:
            return 0
        return int(float(s))  # handle "1.0" → 1
    except (ValueError, TypeError):
        return 0


def _to_float(v):
    """Konversi ke float."""
    if pd.isna(v):
        return 0.0
    try:
        s = str(v).strip()
        if s == "" or s.lower() in ["nan", "none", "null"]:
            return 0.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _to_str(v):
    """Konversi ke string, NaN → None."""
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s.lower() in ["nan", "none", "null", ""]:
        return None
    return s


def _to_date_str(v):
    """Konversi ke format tanggal YYYY-MM-DD."""
    if pd.isna(v):
        return None
    try:
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def clean_dataframe(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Bersihkan DataFrame sesuai config.
    
    - Rename kolom
    - Konversi tipe data
    - Handle NaN
    """
    # 1. Rename kolom sesuai mapping
    rename_map = {k: v for k, v in config["columns"].items() if k in df.columns}
    df_renamed = df.rename(columns=rename_map)
    
    # 2. Ambil kolom yang ada di target
    target_cols = list(config["columns"].values())
    available_cols = [c for c in target_cols if c in df_renamed.columns]
    df_final = df_renamed[available_cols].copy()
    
    # 3. Konversi per tipe
    bool_cols = config.get("bool_cols", [])
    date_cols = config.get("date_cols", [])
    int_cols = config.get("int_cols", [])
    float_cols = config.get("float_cols", [])
    
    for col in df_final.columns:
        # Boolean
        if col in bool_cols:
            df_final[col] = df_final[col].apply(_to_bool)
        
        # Date
        elif col in date_cols:
            df_final[col] = df_final[col].apply(_to_date_str)
        
        # Integer
        elif col in int_cols:
            df_final[col] = df_final[col].apply(_to_int)
        
        # Float
        elif col in float_cols:
            df_final[col] = df_final[col].apply(_to_float)
        
        # Object/string — auto-detect
        elif df_final[col].dtype == "object":
            df_final[col] = df_final[col].apply(_to_str)
        
        # Numeric — handle NaN
        elif df_final[col].dtype in ["int64", "float64"]:
            df_final[col] = df_final[col].where(pd.notna(df_final[col]), None)
    
    return df_final


# =========================================================
# MAIN UI
# =========================================================
st.title("🔄 Migrasi Google Sheets → Supabase")
st.caption(f"Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

st.warning("⚠️ **PENTING:** Backup Google Sheets dulu sebelum migrasi!")

# =========================================================
# CEK KONEKSI
# =========================================================
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
    default=["MASTER_PERSONIL"],
    key="migration_select"
)

if not selected_sheets:
    st.info("👆 Pilih minimal 1 sheet untuk migrasi")
    st.stop()

# =========================================================
# PREVIEW DATA
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
            
            st.markdown("**Preview (5 baris pertama):**")
            st.dataframe(df.head(5), use_container_width=True)
            
            # Cek kolom required
            missing = [c for c in config["required"] if c not in df.columns]
            if missing:
                st.error(f"❌ Kolom wajib tidak ada: {missing}")
            
            # Preview setelah cleaning
            with st.expander("🧹 Preview setelah cleaning"):
                df_clean = clean_dataframe(df, config)
                st.dataframe(df_clean.head(5), use_container_width=True)
                st.caption(f"Kolom final: {list(df_clean.columns)}")
                st.caption(f"Dtypes: {dict(df_clean.dtypes)}")
        
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
    ["Upsert (update kalau duplikat)", "Insert (kalau ada duplikat akan error)"],
    key="migration_mode"
)

mode_key = "upsert" if "Upsert" in mode else "insert"

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
                # 1. Cleaning
                df_final = clean_dataframe(df, config)
                
                # 2. Convert ke list of dict
                records = df_final.where(pd.notna(df_final), None).to_dict("records")
                
                # 3. Batch processing
                batch_size = 500
                total_ok = 0
                errors = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (len(records) + batch_size - 1) // batch_size
                    
                    status_text.text(f"📦 Batch {batch_num}/{total_batches} ({len(batch)} records)")
                    
                    try:
                        if mode_key == "insert":
                            result = sb.table(config["table"]).insert(batch).execute()
                        else:
                            result = sb.table(config["table"]).upsert(
                                batch, on_conflict=config["conflict_key"]
                            ).execute()
                        
                        if result.data:
                            total_ok += len(result.data)
                        else:
                            errors.append(f"Batch {batch_num}: no data returned")
                    
                    except Exception as e_batch:
                        errors.append(f"Batch {batch_num}: {str(e_batch)[:150]}")
                    
                    progress_bar.progress(batch_num / total_batches)
                    time.sleep(0.3)
                
                status_text.text(f"✅ Selesai — {total_ok}/{len(records)} records")
                
                overall_result[sheet_name] = {
                    "status": "success" if total_ok > 0 else "failed",
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
            if res.get("errors"):
                with st.expander("Detail error"):
                    for e in res["errors"]:
                        st.write(f"  - {e}")
    
    st.balloons()
    st.caption("Refresh halaman untuk cek migrasi berikutnya")


# =========================================================
# FOOTER: STATUS TABEL
# =========================================================
st.markdown("---")
st.markdown("### 📊 Status Tabel Supabase")

if st.button("🔄 Refresh Status"):
    st.rerun()

status_data = []
for sheet_name, config in MIGRATION_MAP.items():
    try:
        count = sb_count(config["table"])
        status_data.append({
            "Sheet": sheet_name,
            "Tabel Supabase": config["table"],
            "Baris": count,
        })
    except Exception as e:
        status_data.append({
            "Sheet": sheet_name,
            "Tabel Supabase": config["table"],
            "Baris": f"❌ {str(e)[:30]}",
        })

st.dataframe(pd.DataFrame(status_data), use_container_width=True, hide_index=True)
