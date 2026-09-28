"""
Supabase Connector untuk LigaPSM v2
====================================
Fungsi baca/tulis ke Supabase + backup ke Sheets Audit.

Version: 2.0
- Fungsi dasar (sb_read, sb_insert, sb_upsert, dll)
- Fungsi Daily Performance
- Fungsi Log Activity
- Fungsi Backup ke Audit
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# INIT CLIENT
# =========================================================
@st.cache_resource
def init_supabase():
    """Inisialisasi Supabase client (anon key)."""
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
    """Inisialisasi Supabase dengan service_role (untuk admin)."""
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["service_role_key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Gagal init Supabase admin: {e}")
        return None


# =========================================================
# HELPER: CLEAN DATA
# =========================================================
def _clean_for_supabase(obj):
    """Convert numpy/pandas types ke Python native, NaN → None."""
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, np.floating):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(obj, str):
        s = obj.strip()
        if s.lower() in ["nan", "none", "null", "nat", ""]:
            return None
        return s
    return obj


def _df_to_records(df):
    """Convert DataFrame ke list of dict yang aman untuk Supabase."""
    records = []
    for _, row in df.iterrows():
        row_dict = {}
        for col in df.columns:
            row_dict[col] = _clean_for_supabase(row[col])
        records.append(row_dict)
    return records


def _handle_error(e, context=""):
    """Format error message."""
    err = str(e)
    if "row-level security" in err.lower():
        return f"🔒 RLS blocked ({context})"
    elif "duplicate" in err.lower():
        return f"⚠️ Duplicate entry ({context})"
    elif "connection" in err.lower() or "timeout" in err.lower():
        return f"🌐 Connection error ({context})"
    else:
        return f"❌ {context}: {err[:150]}"


# =========================================================
# READ FUNCTIONS
# =========================================================
def sb_read(table, filters=None, limit=10000, order_by=None, order_desc=True):
    """Baca data dari tabel Supabase."""
    try:
        sb = init_supabase()
        if sb is None:
            return pd.DataFrame()

        query = sb.table(table).select("*")

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

        if order_by:
            query = query.order(order_by, desc=order_desc)

        query = query.limit(limit)
        result = query.execute()

        if not result.data:
            return pd.DataFrame()

        df = pd.DataFrame(result.data)

        # Konversi kolom timestamp
        for col in df.columns:
            if col in ["created_at", "updated_at"]:
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass

        return df

    except Exception as e:
        print(f"[SB_READ] {_handle_error(e, table)}")
        return pd.DataFrame()


def sb_count(table, filters=None):
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
def sb_insert(table, records):
    """Insert batch records ke Supabase."""
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


def sb_upsert(table, records, on_conflict="record_id"):
    """Upsert (insert or update) ke Supabase."""
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


def sb_update(table, filters, updates):
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


def sb_delete(table, filters):
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
# DAILY PERFORMANCE — FUNGSI KHUSUS
# =========================================================
def load_periode_store_supabase():
    """
    Baca periode store dari Supabase.
    Return DataFrame dengan kolom standar.
    """
    try:
        df = sb_read("periode_store", order_by="start_date", order_desc=True)

        if df.empty:
            return pd.DataFrame(columns=[
                "period_id", "period_name", "start_date", "end_date",
                "target_net_sales", "target_std", "target_apc",
                "target_gm_pct", "nsb_percentage", "status"
            ])

        # Konversi kolom numeric
        for col in ["target_net_sales", "target_std", "target_apc"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        for col in ["target_gm_pct", "nsb_percentage"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Konversi tanggal
        for col in ["start_date", "end_date"]:
            if col in df.columns:
                df[col + "_dt"] = pd.to_datetime(df[col], errors="coerce")

        return df

    except Exception as e:
        print(f"[LOAD_PERIODE_STORE] {e}")
        return pd.DataFrame()


def get_active_period_store_supabase(force_refresh=False):
    """
    Ambil periode store aktif + auto-hitung JHK, target SPD, NSB target.
    CACHE 5 menit di session_state.
    """
    cache_key = "_cached_active_period_sb"
    cache_time_key = "_cached_active_period_sb_time"
    now = time.time()
    last_fetch = st.session_state.get(cache_time_key, 0)

    if not force_refresh and (cache_key in st.session_state) and (now - last_fetch < 300):
        return st.session_state.get(cache_key)

    try:
        df = load_periode_store_supabase()

        if df.empty:
            st.session_state[cache_key] = None
            st.session_state[cache_time_key] = now
            return None

        today = pd.Timestamp.now().date()

        # Filter aktif
        aktif = df[
            (df["start_date_dt"].dt.date <= today) &
            (df["end_date_dt"].dt.date >= today) &
            (df["status"].astype(str).str.lower().str.strip() == "aktif")
        ]

        if aktif.empty:
            st.session_state[cache_key] = None
            st.session_state[cache_time_key] = now
            return None

        row = aktif.iloc[0]

        period_id = str(row["period_id"])
        period_name = str(row["period_name"])
        start = row["start_date_dt"].date()
        end = row["end_date_dt"].date()
        target_ns = int(row["target_net_sales"])
        target_std = int(row["target_std"])
        target_apc = int(row["target_apc"]) if "target_apc" in row.index else 0
        nsb_pct = float(row["nsb_percentage"]) if "nsb_percentage" in row.index else 0.15
        target_gm_pct = float(row["target_gm_pct"]) if "target_gm_pct" in row.index else 0

        jhk = (end - start).days + 1
        target_spd = int(target_ns / jhk) if jhk > 0 else 0
        nsb_target_bulanan = int(target_ns * (nsb_pct / 100))
        nsb_target_harian = int(target_spd * (nsb_pct / 100))

        target_warning = (target_ns <= 0 or target_std <= 0 or target_apc <= 0)

        result = {
            "period_id": period_id,
            "period_name": period_name,
            "start_date": start,
            "end_date": end,
            "jhk": jhk,
            "target_net_sales": target_ns,
            "target_std": target_std,
            "target_apc": target_apc,
            "nsb_percentage": nsb_pct,
            "target_spd": target_spd,
            "nsb_target_bulanan": nsb_target_bulanan,
            "nsb_target_harian": nsb_target_harian,
            "target_warning": target_warning,
            "target_gm_pct": target_gm_pct,
        }

        st.session_state[cache_key] = result
        st.session_state[cache_time_key] = now
        return result

    except Exception as e:
        print(f"[GET_ACTIVE_PERIOD_STORE] {e}")
        return st.session_state.get(cache_key, None)


def load_daily_performance_supabase(force_refresh=False):
    """
    Baca data harian dari Supabase (cache 10 menit).
    """
    cache_key = "_cached_daily_perf_sb"
    cache_time_key = "_cached_daily_perf_sb_time"
    now = time.time()
    last_fetch = st.session_state.get(cache_time_key, 0)

    if not force_refresh and (cache_key in st.session_state) and (now - last_fetch < 600):
        return st.session_state.get(cache_key, pd.DataFrame())

    try:
        df = sb_read("sales_store", order_by="tanggal", order_desc=False)

        if df.empty:
            st.session_state[cache_key] = df
            st.session_state[cache_time_key] = now
            return df

        # Konversi kolom numeric
        for col in ["spd", "std", "apc", "nsb_target", "nsb_actual"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Konversi tanggal
        if "tanggal" in df.columns:
            df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")

        st.session_state[cache_key] = df
        st.session_state[cache_time_key] = now
        return df

    except Exception as e:
        print(f"[LOAD_DAILY_PERFORMANCE] {e}")
        return st.session_state.get(cache_key, pd.DataFrame())


def save_daily_performance_supabase(record_dict):
    """
    Simpan/update 1 record data harian ke Supabase.
    Return: (success, message)
    """
    try:
        # Validasi record
        if not record_dict:
            return False, "❌ Record kosong"

        if "tanggal" not in record_dict or "record_id" not in record_dict:
            return False, "❌ Kolom 'tanggal' dan 'record_id' wajib ada"

        # Clean data
        cleaned = {}
        for k, v in record_dict.items():
            cleaned[k] = _clean_for_supabase(v)

        # Upsert by record_id
        ok, msg, count = sb_upsert("sales_store", [cleaned], on_conflict="record_id")

        if ok:
            # Invalidate cache
            if "_cached_daily_perf_sb" in st.session_state:
                del st.session_state["_cached_daily_perf_sb"]
            if "_cached_daily_perf_sb_time" in st.session_state:
                del st.session_state["_cached_daily_perf_sb_time"]

        return ok, msg

    except Exception as e:
        return False, f"❌ {str(e)[:150]}"


def generate_daily_record_id_supabase():
    """Generate record_id berikutnya untuk sales_store."""
    try:
        sb = init_supabase()
        if sb is None:
            return f"SP{int(time.time()) % 100000:05d}"

        # Ambil record_id terakhir
        result = sb.table("sales_store").select("record_id").order("record_id", desc=True).limit(1).execute()

        if result.data and len(result.data) > 0:
            last_id = str(result.data[0]["record_id"])
            # Extract number
            import re
            match = re.search(r"(\d+)", last_id)
            if match:
                next_num = int(match.group(1)) + 1
                return f"SP{next_num:05d}"

        return "SP00001"

    except Exception as e:
        print(f"[GEN_RECORD_ID] {e}")
        return f"SP{int(time.time()) % 100000:05d}"


# =========================================================
# LOG ACTIVITY (Supabase)
# =========================================================
def log_activity_supabase(action, detail="", username=None, role=None, session_id=None):
    """
    Log aktivitas user ke Supabase.
    """
    try:
        action_upper = str(action).upper()

        if username is None:
            username = st.session_state.get("username", "")
        if role is None:
            role = st.session_state.get("role", "")
        if session_id is None:
            session_id = st.session_state.get("session_id", "")

        if not username and action != "LOGIN":
            return False, "No username"

        now = datetime.now(ZoneInfo("Asia/Jakarta"))

        record = {
            "timestamp": now.strftime("%d/%m/%Y %H:%M:%S"),
            "username": str(username) if username else "-",
            "role": str(role) if role else "-",
            "action": str(action_upper),
            "detail": str(detail)[:200],
            "session_id": str(session_id) if session_id else "-",
        }

        # Insert ke activity_log
        sb = init_supabase()
        if sb is None:
            return False, "Supabase not initialized"

        result = sb.table("activity_log").insert(record).execute()

        if result.data:
            return True, "✅ Log saved"

        return False, "No data returned"

    except Exception as e:
        print(f"[LOG_ACTIVITY] {e}")
        return False, str(e)[:150]


# =========================================================
# BACKUP KE SHEETS AUDIT
# =========================================================
def backup_daily_to_audit(spreadsheet_id):
    """
    Backup data dari Supabase ke Sheets Audit.
    Dipakai saat ganti hari (otomatis).
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Init Google Sheets
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        # Cek apakah pakai service account atau OAuth
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=scopes,
            )
            gc = gspread.authorize(creds)
        else:
            st.warning("⚠️ Service account not found in secrets")
            return {"success": 0, "failed": 1, "error": "No credentials"}

        # Buka spreadsheet
        sh = gc.open_by_key(spreadsheet_id)

        # Mapping: nama tabel Supabase → nama sheet di Audit
        tables_to_backup = {
            "sales_store": "_BACKUP_SALES_STORE",
            "sales_item": "_BACKUP_SALES_ITEM",
            "sales_personil": "_BACKUP_SALES_PERSONIL",
            "sales_pps": "_BACKUP_SALES_PPS",
            "periode_psm": "_BACKUP_PERIODE_PSM",
            "periode_pps": "_BACKUP_PERIODE_PPS",
            "periode_store": "_BACKUP_PERIODE_STORE",
            "master_item": "_BACKUP_MASTER_ITEM",
            "master_personil": "_BACKUP_MASTER_PERSONIL",
        }

        success_count = 0
        failed_count = 0
        total_rows = 0

        for table_name, sheet_name in tables_to_backup.items():
            try:
                # Baca dari Supabase
                df = sb_read(table_name, limit=100000)

                if df.empty:
                    continue

                # Convert ke list of list
                headers = list(df.columns)
                rows = df.values.tolist()

                # Convert values
                clean_rows = []
                for row in rows:
                    clean_row = [_clean_for_supabase(v) for v in row]
                    clean_rows.append(clean_row)

                                # Tulis ke sheet
                try:
                    worksheet = sh.worksheet(sheet_name)
                    worksheet.clear()
                except gspread.WorksheetNotFound:
                    worksheet = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)

                worksheet.update([headers] + clean_rows)

                success_count += 1
                total_rows += len(clean_rows)
                time.sleep(0.5)

            except Exception as e:
                print(f"[BACKUP {table_name}] {e}")
                failed_count += 1

        return {
            "success": success_count,
            "failed": failed_count,
            "total": total_rows,
        }

    except Exception as e:
        print(f"[BACKUP ERROR] {e}")
        return {"success": 0, "failed": 1, "error": str(e)[:150]}


# =========================================================
# BACKUP VIA GSHEETS CONNECTION (Alternatif — pakai st.connection)
# =========================================================
def backup_via_gsheets_connection(tables_to_backup=None):
    """
    Backup dari Supabase → Sheets Audit.
    Pakai `st.connection("gsheets")` yang udah ada.
    
    Args:
        tables_to_backup (dict): Mapping {tabel_supabase: sheet_name_audit}
                                 Kalau None → pakai default
    
    Returns:
        dict: {success, failed, total, details}
    """
    try:
        # Default mapping
        if tables_to_backup is None:
            tables_to_backup = {
                "sales_store": "_BACKUP_SALES_STORE",
                "sales_item": "_BACKUP_SALES_ITEM",
                "sales_personil": "_BACKUP_SALES_PERSONIL",
                "sales_pps": "_BACKUP_SALES_PPS",
                "periode_psm": "_BACKUP_PERIODE_PSM",
                "periode_pps": "_BACKUP_PERIODE_PPS",
                "periode_store": "_BACKUP_PERIODE_STORE",
                "master_item": "_BACKUP_MASTER_ITEM",
                "master_personil": "_BACKUP_MASTER_PERSONIL",
            }

        # Pakai koneksi gsheets yang udah ada
        conn = st.connection("gsheets_audit", type=GSheetsConnection)

        success_list = []
        failed_list = []
        total_rows = 0

        for table_name, sheet_name in tables_to_backup.items():
            try:
                # 1. Baca dari Supabase
                df = sb_read(table_name, limit=100000)

                if df.empty:
                    print(f"[BACKUP SKIP] {table_name} kosong")
                    continue

                # 2. Clean data
                clean_df = df.copy()
                for col in clean_df.columns:
                    clean_df[col] = clean_df[col].apply(_clean_for_supabase)

                # 3. Tulis ke Sheets Audit (update)
                conn.update(worksheet=sheet_name, data=clean_df)
                time.sleep(0.5)

                success_list.append(sheet_name)
                total_rows += len(clean_df)
                print(f"[BACKUP OK] {table_name} → {sheet_name} ({len(clean_df)} baris)")

            except Exception as e:
                print(f"[BACKUP FAIL] {table_name}: {e}")
                failed_list.append(f"{table_name}: {str(e)[:100]}")

        return {
            "success": success_list,
            "failed": failed_list,
            "total": total_rows,
        }

    except Exception as e:
        print(f"[BACKUP ERROR] {e}")
        return {
            "success": [],
            "failed": [f"Global error: {str(e)[:150]}"],
            "total": 0,
        }


# =========================================================
# CHECK & AUTO BACKUP (Ganti Hari)
# =========================================================
def check_and_auto_backup():
    """
    Cek apakah sudah ganti hari.
    Kalau iya → auto backup Supabase → Sheets Audit.
    """
    try:
        today = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d")
        last_backup_date = st.session_state.get("last_backup_date", None)

        if last_backup_date is None:
            st.session_state["last_backup_date"] = today
            return

        if last_backup_date != today:
            print(f"[AUTO BACKUP] Ganti hari: {last_backup_date} → {today}")

            # Jalankan backup
            result = backup_via_gsheets_connection()

            if result["success"]:
                print(f"[AUTO BACKUP OK] {len(result['success'])} sheet")
                print(f"[AUTO BACKUP OK] Total: {result['total']:,} baris")
                st.session_state["last_backup_time"] = datetime.now(
                    ZoneInfo("Asia/Jakarta")
                ).strftime("%d/%m/%Y %H:%M:%S")

            if result["failed"]:
                print(f"[AUTO BACKUP FAIL] {len(result['failed'])} sheet")
                for f in result["failed"]:
                    print(f"  - {f}")

            # Update tanggal
            st.session_state["last_backup_date"] = today

    except Exception as e:
        print(f"[CHECK_AUTO_BACKUP ERROR] {e}")


# =========================================================
# LOGIN HELPER
# =========================================================
def login_check_supabase(username, password):
    """
    Cek login dari Supabase (master_personil).
    Return: (success, user_data)
    """
    try:
        if not username or not password:
            return False, None

        # Baca dari Supabase
        df = sb_read("master_personil", limit=100)

        if df.empty:
            return False, None

        # Normalisasi kolom
        df.columns = df.columns.astype(str).str.strip().str.lower()

        # Cari user
        username_clean = str(username).strip().lower()
        password_clean = str(password).strip()

        match = df[
            (df["username"].astype(str).str.strip().str.lower() == username_clean) &
            (df["password"].astype(str).str.strip() == password_clean)
        ]

        if match.empty:
            return False, None

        row = match.iloc[0]

        # Cek active
        if "active" in df.columns:
            is_active = row.get("active", True)
            if isinstance(is_active, str):
                is_active = is_active.lower() in ["true", "1", "yes", "aktif"]
            if not is_active:
                return False, None

        user_data = {
            "username": str(row.get("username", username)),
            "person_name": str(row.get("person_name", username)),
            "role": str(row.get("role", "Staff Toko")),
            "person_id": str(row.get("person_id", "")),
            "active": True,
        }

        return True, user_data

    except Exception as e:
        print(f"[LOGIN_CHECK] {e}")
        return False, None


# =========================================================
# GET USER INFO
# =========================================================
def get_user_info(username):
    """Ambil info user dari Supabase."""
    try:
        df = sb_read("master_personil", limit=100)

        if df.empty:
            return None

        df.columns = df.columns.astype(str).str.strip().str.lower()

        username_clean = str(username).strip().lower()
        match = df[df["username"].astype(str).str.strip().str.lower() == username_clean]

        if match.empty:
            return None

        row = match.iloc[0]
        return {
            "username": str(row.get("username", "")),
            "person_name": str(row.get("person_name", "")),
            "role": str(row.get("role", "")),
            "person_id": str(row.get("person_id", "")),
        }

    except Exception as e:
        print(f"[GET_USER_INFO] {e}")
        return None
