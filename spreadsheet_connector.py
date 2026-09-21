"""
spreadsheet_connector.py
========================
Konektor multi-spreadsheet untuk LigaPSM + Debug Panel.

- Spreadsheet 1 (Data):     akses via st.connection (existing)
- Spreadsheet 2 (Audit):    akses via gspread (append-only)
- Spreadsheet 3 (Laporan):  akses via gspread (read/write manual)

Fungsi utama:
    get_ws_audit(sheet_name)          → worksheet Spreadsheet Audit
    get_ws_laporan(sheet_name)        → worksheet Spreadsheet Laporan
    append_logs_to_sheet(logs_list)   → tulis log ke ACTIVITY_LOG
    read_activity_log(cache_buster)   → baca log dengan cache
    backup_to_audit_sheet()           → backup 7 sheet ke Spreadsheet Audit
    write_laporan_bulanan(...)        → tulis laporan ke Spreadsheet Laporan

Debug:
    render_debug_panel()              → tampilkan panel test di UI
"""
import gspread
import streamlit as st
import pandas as pd
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials


# =========================================================================
# 🔒 LOCK GLOBAL — ANTI RACE CONDITION
# =========================================================================
_AUDIT_LOCK = threading.Lock()
_LAPORAN_LOCK = threading.Lock()


# =========================================================================
# 🔌 KONEKSI DASAR
# =========================================================================
@st.cache_resource(show_spinner=False)
def _get_client():
    """Bikin koneksi gspread sekali seumur app (hemat quota)."""
    try:
        _creds_dict = dict(st.secrets["gcp_service_account"])
        _creds = Credentials.from_service_account_info(
            _creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        return gspread.authorize(_creds)
    except Exception as e:
        print(f"[GET_CLIENT ERROR] {e}")
        return None


@st.cache_resource(show_spinner=False)
def get_ws_audit(sheet_name):
    """
    Buka worksheet di Spreadsheet Audit (Log & Backup).
    Auto-create kalau sheet belum ada.
    """
    try:
        client = _get_client()
        if client is None:
            return None
        sh = client.open_by_key(st.secrets["spreadsheet_id_audit"])
        try:
            return sh.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=10)
            return ws
    except Exception as e:
        print(f"[GET_WS_AUDIT ERROR] {sheet_name}: {e}")
        return None


@st.cache_resource(show_spinner=False)
def get_ws_laporan(sheet_name):
    """Buka worksheet di Spreadsheet Laporan. Auto-create kalau belum ada."""
    try:
        client = _get_client()
        if client is None:
            return None
        sh = client.open_by_key(st.secrets["spreadsheet_id_laporan"])
        try:
            return sh.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=40)
            return ws
    except Exception as e:
        print(f"[GET_WS_LAPORAN ERROR] {sheet_name}: {e}")
        return None


# =========================================================================
# 📝 LOG ACTIVITY — APPEND-ONLY
# =========================================================================
_HEADER_ACTIVITY = ["timestamp", "username", "role", "action", "detail", "session_id"]


def append_logs_to_sheet(logs_list):
    """
    Append list of dict log ke sheet ACTIVITY_LOG (Spreadsheet Audit).
    - TANPA READ → hemat quota
    - Lock global → anti race condition
    - Return: (success_count, message)
    """
    if not logs_list:
        return 0, "Queue kosong"

    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_LOG")
            if ws is None:
                return 0, "❌ Gagal akses sheet ACTIVITY_LOG"

            # Pastikan header ada
            try:
                _first = ws.row_values(1)
                if not _first or _first[0].lower() != "timestamp":
                    ws.insert_row(_HEADER_ACTIVITY, index=1)
            except Exception:
                pass

            # Bangun rows
            _rows = []
            for log in logs_list:
                _rows.append([
                    str(log.get("timestamp", "")),
                    str(log.get("username", "-")),
                    str(log.get("role", "-")),
                    str(log.get("action", "")),
                    str(log.get("detail", ""))[:200],
                    str(log.get("session_id", "")),
                ])

            ws.append_rows(_rows, value_input_option="USER_ENTERED")

        return len(_rows), f"✅ {len(_rows)} log tersimpan"

    except gspread.exceptions.APIError as e:
        _err = str(e)
        if "429" in _err or "RESOURCE_EXHAUSTED" in _err:
            return 0, "⚠️ Quota Google Sheets habis, coba 1 menit lagi"
        return 0, f"❌ API Error: {_err[:100]}"
    except Exception as e:
        return 0, f"❌ Gagal: {str(e)[:150]}"


@st.cache_data(ttl=300, show_spinner=False)
def read_activity_log(_cache_buster=0):
    """Baca ACTIVITY_LOG dengan cache 5 menit."""
    try:
        ws = get_ws_audit("ACTIVITY_LOG")
        if ws is None:
            return pd.DataFrame(columns=_HEADER_ACTIVITY)

        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return pd.DataFrame(columns=_HEADER_ACTIVITY)

        header = all_values[0]
        rows = all_values[1:]
        return pd.DataFrame(rows, columns=header)
    except Exception as e:
        print(f"[READ_ACTIVITY ERROR] {e}")
        return pd.DataFrame(columns=_HEADER_ACTIVITY)


# =========================================================================
# 💾 BACKUP KE SPREADSHEET AUDIT
# =========================================================================
def backup_to_audit_sheet(state_getter):
    """
    Backup 7 sheet ke Spreadsheet Audit (tab _BACKUP_*).
    
    Args:
        state_getter: fungsi lambda untuk ambil DataFrame dari session_state
                      contoh: lambda k: st.session_state.get(k, pd.DataFrame())
    
    Returns:
        dict {"success": [...], "failed": [...], "total": int}
    """
    _result = {"success": [], "failed": [], "total": 0}

    _backup_map = [
        ("_BACKUP_SALES_PPS", "sales_pps_df"),
        ("_BACKUP_PERIODE_PPS", "periods_pps_df"),
        ("_BACKUP_SALES_ITEM", "sales_item_df"),
        ("_BACKUP_SALES_PERSON", "sales_person_df"),
        ("_BACKUP_PERIODE", "periods_df"),
        ("_BACKUP_MASTER_ITEM", "items_df"),
        ("_BACKUP_MASTER_PERSONIL", "person_df"),
    ]

    try:
        with _AUDIT_LOCK:
            for _sheet_name, _state_key in _backup_map:
                try:
                    _df = state_getter(_state_key)
                    if _df is None or _df.empty:
                        _result["failed"].append(f"⚠️ {_sheet_name}: data kosong")
                        continue

                    _df_clean = _df.copy().fillna("")
                    _df_clean.columns = _df_clean.columns.astype(str)
                    _df_clean = _df_clean.reset_index(drop=True)

                    ws = get_ws_audit(_sheet_name)
                    if ws is None:
                        _result["failed"].append(f"❌ {_sheet_name}: worksheet gagal")
                        continue

                    ws.clear()
                    header = [str(c) for c in _df_clean.columns.tolist()]
                    ws.append_row(header)
                    data_rows = _df_clean.astype(str).values.tolist()
                    if data_rows:
                        ws.append_rows(data_rows, value_input_option="USER_ENTERED")

                    _result["success"].append(_sheet_name)
                    _result["total"] += len(_df_clean)
                    time.sleep(0.5)  # Delay antar sheet

                except Exception as e:
                    _err = str(e)
                    if "429" in _err:
                        _result["failed"].append(f"❌ {_sheet_name}: Kuota habis")
                    else:
                        _result["failed"].append(f"❌ {_sheet_name}: {_err[:50]}")
                    continue
    except Exception as e:
        _result["failed"].append(f"❌ Lock error: {str(e)[:80]}")

    return _result


# =========================================================================
# 📊 TULIS LAPORAN BULANAN
# =========================================================================
def write_laporan_bulanan(sheet_name, rows_matrix):
    """
    Tulis matrix laporan ke Spreadsheet Laporan.
    
    Args:
        sheet_name (str): nama sheet, contoh "SEPTEMBER 2026"
        rows_matrix (list[list]): matrix data
    
    Returns:
        (success: bool, message: str)
    """
    try:
        with _LAPORAN_LOCK:
            ws = get_ws_laporan(sheet_name)
            if ws is None:
                return False, f"❌ Gagal akses sheet {sheet_name}"

            ws.clear()
            ws.update(rows_matrix, "A1")

        return True, f"✅ Laporan {sheet_name} tersimpan ({len(rows_matrix)} baris)"
    except Exception as e:
        return False, f"❌ Gagal: {str(e)[:150]}"


# =========================================================================
# 🧪 DEBUG PANEL — TEST SEMUA FUNGSI DARI UI
# =========================================================================
def render_debug_panel():
    """
    Tampilkan panel debug di sidebar.
    Panel ini test 3 spreadsheet + fungsi connector.
    
    Cara pakai (di script utama):
        from spreadsheet_connector import render_debug_panel
        render_debug_panel()
    """
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🧪 Debug Panel")
        st.caption("Test koneksi & fungsi connector")

        if st.button("🔌 TEST SEMUA", key="btn_debug_test_all", use_container_width=True):
            _test_all()

        st.markdown("---")
        st.markdown("### ✍️ Test Write")

        if st.button("📝 Test Append Log", key="btn_debug_test_append", use_container_width=True):
            _test_append_log()

        if st.button("💾 Test Backup 1 Sheet", key="btn_debug_test_backup", use_container_width=True):
            _test_backup_one()

        if st.button("📊 Test Write Laporan", key="btn_debug_test_laporan", use_container_width=True):
            _test_laporan()

        st.markdown("---")
        st.markdown("### 📥 Test Read")

        if st.button("📜 Baca Activity Log", key="btn_debug_read_log", use_container_width=True):
            _test_read_log()


# ---------- Fungsi test individual ----------

def _test_all():
    """Test koneksi 3 spreadsheet."""
    try:
        from google.oauth2.service_account import Credentials
        _creds_dict = dict(st.secrets["gcp_service_account"])
        _creds = Credentials.from_service_account_info(
            _creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        _client = gspread.authorize(_creds)

        st.sidebar.success("✅ Credentials OK")
        st.sidebar.caption(f"👤 `{_creds_dict.get('client_email', '?')[:30]}...`")

        # Test 1: Data
        try:
            _id = st.secrets.get("spreadsheet_id", "")
            _sh = _client.open_by_key(_id)
            st.sidebar.success(f"✅ Data: `{_sh.title[:25]}`")
            with st.sidebar.expander(f"📋 {len(_sh.worksheets())} sheet"):
                for ws in _sh.worksheets():
                    st.write(f"• {ws.title}")
        except Exception as e:
            st.sidebar.error(f"❌ Data: {str(e)[:60]}")

        # Test 2: Audit
        try:
            _id = st.secrets.get("spreadsheet_id_audit", "")
            if not _id:
                st.sidebar.warning("⚠️ `spreadsheet_id_audit` belum di-set")
            else:
                _sh = _client.open_by_key(_id)
                st.sidebar.success(f"✅ Audit: `{_sh.title[:25]}`")
                _names = [ws.title for ws in _sh.worksheets()]
                with st.sidebar.expander(f"📋 {len(_names)} sheet"):
                    for s in _names:
                        st.write(f"• {s}")
                _wajib = ["ACTIVITY_LOG", "ACTIVITY_HEARTBEAT"]
                _missing = [s for s in _wajib if s not in _names]
                if _missing:
                    st.sidebar.warning(f"⚠️ Kurang: {_missing}")
                else:
                    st.sidebar.info("✅ ACTIVITY_LOG & ACTIVITY_HEARTBEAT ada")
        except Exception as e:
            st.sidebar.error(f"❌ Audit: {str(e)[:60]}")

        # Test 3: Laporan
        try:
            _id = st.secrets.get("spreadsheet_id_laporan", "")
            if not _id:
                st.sidebar.warning("⚠️ `spreadsheet_id_laporan` belum di-set")
            else:
                _sh = _client.open_by_key(_id)
                st.sidebar.success(f"✅ Laporan: `{_sh.title[:25]}`")
                _names = [ws.title for ws in _sh.worksheets()]
                with st.sidebar.expander(f"📋 {len(_names)} sheet"):
                    for s in _names:
                        st.write(f"• {s}")
        except Exception as e:
            st.sidebar.error(f"❌ Laporan: {str(e)[:60]}")

        st.sidebar.balloons()
        st.sidebar.success("🎉 TEST SELESAI")

    except Exception as e:
        st.sidebar.error(f"❌ Error: {str(e)[:80]}")


def _test_append_log():
    """Test tulis 1 baris ke ACTIVITY_LOG."""
    try:
        _now_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
        _test_log = [{
            "timestamp": _now_str,
            "username": "DEBUG_TEST",
            "role": "system",
            "action": "TEST",
            "detail": "Test append dari Debug Panel",
            "session_id": "debug-001",
        }]
        count, msg = append_logs_to_sheet(_test_log)
        if count > 0:
            st.sidebar.success(f"✅ {msg}")
            st.sidebar.info("👉 Cek LIGAPSM_AUDIT → ACTIVITY_LOG")
        else:
            st.sidebar.error(msg)
    except Exception as e:
        st.sidebar.error(f"❌ {str(e)[:80]}")


def _test_backup_one():
    """Test backup 1 sheet saja (SALES_PERSONIL)."""
    try:
        def _getter(key):
            return st.session_state.get(key, pd.DataFrame())

        _result = backup_to_audit_sheet(_getter)
        if _result["success"]:
            st.sidebar.success(f"✅ Backup OK: {len(_result['success'])} sheet")
            with st.sidebar.expander("Detail"):
                st.write(f"Total baris: {_result['total']}")
                st.write(f"Success: {_result['success']}")
                if _result["failed"]:
                    st.write(f"Failed: {_result['failed']}")
        else:
            st.sidebar.warning("⚠️ Tidak ada yang berhasil di-backup")
            with st.sidebar.expander("Detail"):
                st.write(_result["failed"])
    except Exception as e:
        st.sidebar.error(f"❌ {str(e)[:80]}")


def _test_laporan():
    """Test tulis laporan dummy."""
    try:
        _rows = [
            ["", "Toko", "C383/KARANG SATRIA"] + [str(i) for i in range(1, 32)],
            ["No", "NIK", "Nama Personil", "ACTUAL"] + [""] * 30,
            [1, "13127006", "REZA PURNAMA"] + [0] * 31,
            [2, "16016359", "SUBEKTI PANDU"] + [0] * 31,
            ["Total", "", ""] + [0] * 31,
        ]
        _sheet = f"TEST {datetime.now().strftime('%H%M%S')}"
        ok, msg = write_laporan_bulanan(_sheet, _rows)
        if ok:
            st.sidebar.success(f"✅ {msg}")
            st.sidebar.info("👉 Cek LIGAPSM-LAPORAN")
        else:
            st.sidebar.error(msg)
    except Exception as e:
        st.sidebar.error(f"❌ {str(e)[:80]}")


def _test_read_log():
    """Test baca ACTIVITY_LOG."""
    try:
        df = read_activity_log()
        if df.empty:
            st.sidebar.warning("📭 Log kosong atau belum ada")
        else:
            st.sidebar.success(f"✅ {len(df)} baris log")
            with st.sidebar.expander("Preview 5 baris"):
                st.dataframe(df.head(5), use_container_width=True)
    except Exception as e:
        st.sidebar.error(f"❌ {str(e)[:80]}")
