"""
Supabase Connector untuk LigaPSM
=================================
Fungsi baca/tulis ke Supabase, dengan fallback & error handling.

Author: LigaPSM Team
Version: 1.0
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from zoneinfo import ZoneInfo
import time

# =========================================================
# INIT CLIENT
# =========================================================
@st.cache_resource
def init_supabase():
    """Inisialisasi Supabase client (cache_resource biar hemat)."""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Gagal init Supabase: {e}")
        return None


@st.cache_resource
def init_supabase_admin():
    """Inisialisasi Supabase dengan service_role (untuk migrasi)."""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["service_role_key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Gagal init Supabase admin: {e}")
        return None


# =========================================================
# HELPER
# =========================================================
def _df_from_data(data: list) -> pd.DataFrame:
    """Convert list of dict dari Supabase ke DataFrame dengan normalisasi."""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Konversi kolom timestamp
    for col in df.columns:
        if "at" in col.lower() or "tanggal" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                pass
    
    return df


def _handle_error(e, context: str = ""):
    """Handle error konsisten."""
    err_msg = str(e)
    if "row-level security" in err_msg.lower():
        return f"🔒 RLS blocked ({context}). Cek policy Supabase."
    elif "duplicate" in err_msg.lower():
        return f"⚠️ Duplicate entry ({context})"
    elif "connection" in err_msg.lower() or "timeout" in err_msg.lower():
        return f"🌐 Connection error ({context}). Coba lagi."
    else:
        return f"❌ {context}: {err_msg[:150]}"


# =========================================================
# READ FUNCTIONS
# =========================================================
def sb_read(table: str, filters: dict = None, limit: int = 10000, order_by: str = None) -> pd.DataFrame:
    """
    Baca data dari tabel Supabase.
    
    Args:
        table (str): Nama tabel
        filters (dict): Filter {'column': value} atau {'column': {'op': 'gt', 'value': 5}}
        limit (int): Max baris (default 10000)
        order_by (str): Kolom untuk sort (default None)
    
    Returns:
        pd.DataFrame
    """
    try:
        sb = init_supabase()
        if sb is None:
            return pd.DataFrame()
        
        query = sb.table(table).select("*")
        
        # Apply filters
        if filters:
            for col, val in filters.items():
                if isinstance(val, dict) and "op" in val:
                    op = val["op"]
                    v = val["value"]
                    if op == "gt":
                        query = query.gt(col, v)
                    elif op == "gte":
                        query = query.gte(col, v)
                    elif op == "lt":
                        query = query.lt(col, v)
                    elif op == "lte":
                        query = query.lte(col, v)
                    elif op == "in":
                        query = query.in_(col, v)
                    elif op == "like":
                        query = query.like(col, v)
                    elif op == "eq":
                        query = query.eq(col, v)
                else:
                    query = query.eq(col, val)
        
        # Order
        if order_by:
            query = query.order(order_by, desc=True)
        
        # Limit
        query = query.limit(limit)
        
        result = query.execute()
        return _df_from_data(result.data)
    
    except Exception as e:
        print(f"[SB_READ] {_handle_error(e, table)}")
        return pd.DataFrame()


def sb_read_by_period(table: str, period_ids: list, limit: int = 10000) -> pd.DataFrame:
    """Baca data by period_id list."""
    return sb_read(table, filters={"period_id": {"op": "in", "value": period_ids}}, limit=limit)


def sb_count(table: str, filters: dict = None) -> int:
    """Hitung jumlah baris di tabel."""
    try:
        sb = init_supabase()
        if sb is None:
            return 0
        
        query = sb.table(table).select("*", count="exact")
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        
        result = query.limit(1).execute()
        return result.count if result.count is not None else 0
    except Exception as e:
        print(f"[SB_COUNT] {_handle_error(e, table)}")
        return 0


# =========================================================
# WRITE FUNCTIONS
# =========================================================
def sb_insert(table: str, records: list) -> tuple:
    """
    Insert batch records ke Supabase.
    
    Args:
        table (str): Nama tabel
        records (list): List of dict
    
    Returns:
        tuple: (success: bool, message: str, count: int)
    """
    try:
        if not records:
            return False, "Empty records", 0
        
        sb = init_supabase()
        if sb is None:
            return False, "Supabase not initialized", 0
        
        result = sb.table(table).insert(records).execute()
        count = len(result.data) if result.data else 0
        
        if count > 0:
            return True, f"✅ {count} records inserted", count
        return False, "No data returned", 0
    
    except Exception as e:
        return False, _handle_error(e, f"insert to {table}"), 0


def sb_upsert(table: str, records: list, on_conflict: str = "record_id") -> tuple:
    """
    Upsert (insert or update) ke Supabase.
    
    Args:
        table (str): Nama tabel
        records (list): List of dict
        on_conflict (str): Kolom untuk conflict detection
    
    Returns:
        tuple: (success: bool, message: str, count: int)
    """
    try:
        if not records:
            return False, "Empty records", 0
        
        sb = init_supabase()
        if sb is None:
            return False, "Supabase not initialized", 0
        
        result = sb.table(table).upsert(records, on_conflict=on_conflict).execute()
        count = len(result.data) if result.data else 0
        
        if count > 0:
            return True, f"✅ {count} records upserted", count
        return False, "No data returned", 0
    
    except Exception as e:
        return False, _handle_error(e, f"upsert to {table}"), 0


def sb_update(table: str, filters: dict, updates: dict) -> tuple:
    """Update rows yang match filter."""
    try:
        sb = init_supabase()
        if sb is None:
            return False, "Supabase not initialized", 0
        
        query = sb.table(table).update(updates)
        for col, val in filters.items():
            query = query.eq(col, val)
        
        result = query.execute()
        count = len(result.data) if result.data else 0
        return True, f"✅ {count} records updated", count
    
    except Exception as e:
        return False, _handle_error(e, f"update {table}"), 0


def sb_delete(table: str, filters: dict) -> tuple:
    """Delete rows yang match filter."""
    try:
        sb = init_supabase()
        if sb is None:
            return False, "Supabase not initialized", 0
        
        query = sb.table(table).delete()
        for col, val in filters.items():
            query = query.eq(col, val)
        
        result = query.execute()
        count = len(result.data) if result.data else 0
        return True, f"✅ {count} records deleted", count
    
    except Exception as e:
        return False, _handle_error(e, f"delete from {table}"), 0


# =========================================================
# LOAD DATABASE (pengganti load_database dari Sheets)
# =========================================================
def load_database_supabase(_cache_buster=0):
    """
    Load semua data dari Supabase (pengganti load_database lama).
    
    Returns:
        tuple: (periods, periods_pps, periods_store, items, person, 
                sales_item, sales_person, sales_pps, sales_store)
    """
    try:
        # Master & Periode (statis)
        periods = sb_read("periode_psm", order_by="start_date")
        periods_pps = sb_read("periode_pps", order_by="start_date")
        periods_store = sb_read("periode_store", order_by="start_date")
        items = sb_read("master_item", limit=5000)
        person = sb_read("master_personil", limit=1000)
        
        # Sales (dinamis)
        sales_item = sb_read("sales_item", limit=50000, order_by="updated_at")
        sales_person = sb_read("sales_personil", limit=50000, order_by="updated_at")
        sales_pps = sb_read("sales_pps", limit=50000, order_by="updated_at")
        sales_store = sb_read("sales_store", limit=5000, order_by="tanggal")
        
        return (
            periods, periods_pps, periods_store,
            items, person,
            sales_item, sales_person, sales_pps, sales_store
        )
    
    except Exception as e:
        st.error(f"❌ Gagal load database Supabase: {e}")
        return tuple([pd.DataFrame() for _ in range(9)])


# =========================================================
# SYNC / UTILITY
# =========================================================
def test_connection() -> dict:
    """Test koneksi Supabase & return status."""
    result = {
        "client_ok": False,
        "tables": {},
        "errors": [],
    }
    
    try:
        sb = init_supabase()
        if sb is None:
            result["errors"].append("Client gagal init")
            return result
        
        result["client_ok"] = True
        
        tables = [
            "master_personil", "master_item", "periode_psm", "periode_pps",
            "sales_item", "sales_personil", "sales_pps",
            "periode_store", "sales_store", "activity_log"
        ]
        
        for t in tables:
            try:
                count = sb_count(t)
                result["tables"][t] = count
            except Exception as e:
                result["tables"][t] = f"❌ {str(e)[:50]}"
        
        return result
    
    except Exception as e:
        result["errors"].append(str(e))
        return result


def get_supabase_info() -> dict:
    """Get info tentang Supabase project."""
    try:
        url = st.secrets["supabase"]["url"]
        project_ref = url.replace("https://", "").split(".")[0]
        return {
            "url": url,
            "project_ref": project_ref,
            "region": "Singapore (asumsi)",
        }
    except Exception:
        return {}
