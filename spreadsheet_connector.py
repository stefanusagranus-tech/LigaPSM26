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
def _safe_stringify(value):
    """
    Konversi value apapun jadi string aman untuk Google Sheets.
    Handle: NaN, NaT, None, inf, -inf, string 'nan', dll.
    """
    try:
        # Cek None / NaN / NaT
        if value is None:
            return ""
        
        # Cek NaN (pakai try karena NaN != NaN)
        try:
            if pd.isna(value):
                return ""
        except (ValueError, TypeError):
            # pd.isna() bisa error untuk array/list
            pass
        
        # Cek inf / -inf
        if isinstance(value, float):
            if value == float('inf') or value == float('-inf'):
                return ""
            if value != value:  # NaN check
                return ""
        
        # Konversi ke string
        _str = str(value).strip()
        
        # Cek string aneh
        if _str.lower() in ["nan", "nat", "none", "inf", "-inf", "infinity", "-infinity", "<na>"]:
            return ""
        
        return _str
    
    except Exception:
        return ""


def backup_to_audit_sheet(state_getter):
    """
    Backup 9 sheet ke Spreadsheet Audit (tab _BACKUP_*).
    Versi FIX KUAT — handle semua NaN/NaT/inf.
    """
    _result = {"success": [], "failed": [], "total": 0}

    _backup_map = [
        # PSM & PPS
        ("_BACKUP_SALES_ITEM", "sales_item_df"),
        ("_BACKUP_SALES_PERSON", "sales_person_df"),
        ("_BACKUP_SALES_PPS", "sales_pps_df"),
        ("_BACKUP_PERIODE", "periods_df"),
        ("_BACKUP_PERIODE_PPS", "periods_pps_df"),
        ("_BACKUP_MASTER_ITEM", "items_df"),
        ("_BACKUP_MASTER_PERSONIL", "person_df"),
        # Daily Performance
        ("_BACKUP_PERIODE_STOREPERFORMANCE", "periods_store_df"),
        ("_BACKUP_SALES_STOREPERFORMANCE", "sales_store_df"),
    ]

    try:
        with _AUDIT_LOCK:
            for _sheet_name, _state_key in _backup_map:
                try:
                    _df = state_getter(_state_key)
                    if _df is None or _df.empty:
                        _result["failed"].append(f"⚠️ {_sheet_name}: data kosong")
                        continue

                    # === CLEANING 100% KUAT ===
                    # 1. Copy
                    _df_clean = _df.copy()
                    
                    # 2. Header jadi string
                    _df_clean.columns = _df_clean.columns.astype(str)
                    
                    # 3. Apply _safe_stringify ke SETIAP CELL
                    # Ini paling lambat tapi PALING AMAN
                    _df_clean = _df_clean.map(_safe_stringify)
                    
                    # 4. Reset index
                    _df_clean = _df_clean.reset_index(drop=True)

                    # === TULIS KE SHEET ===
                    ws = get_ws_audit(_sheet_name)
                    if ws is None:
                        _result["failed"].append(f"❌ {_sheet_name}: worksheet gagal")
                        continue

                    ws.clear()
                    
                    # Header
                    header = _df_clean.columns.tolist()
                    ws.append_row(header, value_input_option="USER_ENTERED")
                    
                    # Data
                    data_rows = _df_clean.values.tolist()
                    if data_rows:
                        ws.append_rows(data_rows, value_input_option="USER_ENTERED")

                    _result["success"].append(_sheet_name)
                    _result["total"] += len(_df_clean)
                    time.sleep(0.5)

                except Exception as e:
                    _err = str(e)
                    if "429" in _err:
                        _result["failed"].append(f"❌ {_sheet_name}: Kuota habis")
                    else:
                        _result["failed"].append(f"❌ {_sheet_name}: {_err[:60]}")
                    continue
    except Exception as e:
        _result["failed"].append(f"❌ Lock error: {str(e)[:80]}")

    return _result

# =========================================================================
# 📊 GENERATOR LAPORAN BULANAN PSM
# =========================================================================
def generate_laporan_bulanan_psm(bulan_int, tahun_int, nama_bulan_str):
    """
    Generate laporan bulanan PSM ke Spreadsheet Laporan.
    Format: Toko, NIK, Nama Personil, kolom tanggal 1-31.
    
    Args:
        bulan_int (int): 1-12
        tahun_int (int): contoh 2026
        nama_bulan_str (str): contoh "SEPTEMBER"
    
    Returns: (success: bool, message: str, total_personil: int)
    """
    try:
        import pandas as pd
        
        # === 1. Ambil data dari session state ===
        _sp = st.session_state.get("sales_person_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _sp.empty or _pers.empty:
            return False, "❌ Data sales_person atau person_df kosong", 0
        
        # Normalisasi kolom
        _sp.columns = _sp.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        # === 2. Filter bulan ===
        if "updated_at" not in _sp.columns:
            return False, "❌ Kolom 'updated_at' tidak ada di sales_person", 0
        
        _sp["_dt"] = pd.to_datetime(_sp["updated_at"], errors="coerce")
        _sp = _sp.dropna(subset=["_dt"])
        _sp = _sp[(_sp["_dt"].dt.month == bulan_int) & (_sp["_dt"].dt.year == tahun_int)]
        
        if _sp.empty:
            return False, f"❌ Tidak ada data PSM untuk {nama_bulan_str} {tahun_int}", 0
        
        # === 3. Pivot (personil × tanggal) ===
        _sp["_tgl"] = _sp["_dt"].dt.day
        _sp["qty"] = pd.to_numeric(_sp.get("actual_qty", 0), errors="coerce").fillna(0)
        _sp["person_clean"] = _sp["person_name"].astype(str).str.strip().str.upper()
        
        _pivot = _sp.pivot_table(
            index="person_clean",
            columns="_tgl",
            values="qty",
            aggfunc="sum",
            fill_value=0
        )
        
        # === 4. Ambil personil aktif ===
        _pers_active = _pers.copy()
        if "active" in _pers_active.columns:
            _pers_active = _pers_active[pd.to_numeric(_pers_active["active"], errors="coerce") == 1]
        
        _pers_active["person_clean"] = _pers_active["person_name"].astype(str).str.strip().str.upper()
        _pers_active = _pers_active.sort_values("person_clean").drop_duplicates(subset=["person_clean"])
        
        if _pers_active.empty:
            return False, "❌ Tidak ada personil aktif", 0
        
        # === 5. Bangun matrix ===
        _rows_output = []
        
        # Baris 1: Toko + tanggal 1-31
        _row1 = ["", "Toko", "C383/KARANG SATRIA"] + [str(d) for d in range(1, 32)]
        _rows_output.append(_row1)
        
        # Baris 2: Header kolom
        _row2 = ["No", "NIK", "Nama Personil", "ACTUAL"] + [""] * 30
        _rows_output.append(_row2)
        
        # === 6. Data personil ===
        _total_per_tgl = {d: 0 for d in range(1, 32)}
        
        for _idx, (_, _p_row) in enumerate(_pers_active.iterrows(), start=1):
            _nama = str(_p_row.get("person_name", "")).strip().upper()
            
            # NIK / person_id
            _nik = str(_p_row.get("person_id", _p_row.get("nik", ""))).replace(".0", "").strip()
            if not _nik or _nik == "nan":
                _nik = "-"
            
            _row_data = [_idx, _nik, _nama]
            
            if _nama in _pivot.index:
                for _d in range(1, 32):
                    _val = int(_pivot.loc[_nama, _d]) if _d in _pivot.columns else 0
                    _row_data.append(_val)
                    _total_per_tgl[_d] += _val
            else:
                _row_data.extend([0] * 31)
            
            _rows_output.append(_row_data)
        
        # Baris Total
        _total_row = ["Total", "", ""] + [str(_total_per_tgl[_d]) for _d in range(1, 32)]
        _rows_output.append(_total_row)
        
        # === 7. Tulis ke Spreadsheet Laporan ===
        _sheet_name = f"{nama_bulan_str.upper()} {tahun_int}"
        _ok, _msg = write_laporan_bulanan(_sheet_name, _rows_output)
        
        if not _ok:
            return False, _msg, 0
        
        return True, f"✅ Laporan {_sheet_name} tersimpan ({len(_rows_output)} baris)", len(_pers_active)
    
    except Exception as e:
        return False, f"❌ Gagal: {str(e)[:150]}", 0

# =========================================================================
# 📊 TULIS LAPORAN BULANAN KE SPREADSHEET LAPORAN
# =========================================================================
def write_laporan_bulanan(sheet_name, rows_matrix):
    """
    Tulis matrix laporan ke Spreadsheet Laporan.
    Handle nama sheet dengan spasi (fix bug range).
    
    Args:
        sheet_name (str): nama sheet, contoh "SEPTEMBER 2026"
        rows_matrix (list[list]): matrix data (baris × kolom)
    
    Returns:
        (success: bool, message: str)
    """
    try:
        with _LAPORAN_LOCK:
            ws = get_ws_laporan(sheet_name)
            if ws is None:
                return False, f"❌ Gagal akses sheet {sheet_name}"
            
            # Bersihkan sheet dulu
            ws.clear()
            
            # Tulis matrix
            if rows_matrix:
                # Cara 1: Pakai update dengan value_input_option
                ws.update(
                    values=rows_matrix,
                    range_name="A1",
                    value_input_option="USER_ENTERED"
                )
            
            return True, f"✅ Laporan {sheet_name} tersimpan ({len(rows_matrix)} baris)"
    
    except Exception as e:
        _err = str(e)
        # Kalau error "Unable to parse range", coba cara alternatif
        if "Unable to parse range" in _err:
            try:
                # Cara 2: Tulis baris per baris (fallback)
                ws.clear()
                for _row_idx, _row in enumerate(rows_matrix, start=1):
                    ws.insert_row(_row, index=_row_idx, value_input_option="USER_ENTERED")
                return True, f"✅ Laporan {sheet_name} tersimpan ({len(rows_matrix)} baris) [fallback]"
            except Exception as e2:
                return False, f"❌ Gagal (fallback): {str(e2)[:150]}"
        
        return False, f"❌ Gagal: {_err[:150]}"


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
        st.markdown("### 📊 Cek Quota API")

        if st.button("📊 Hitung API Call Hari Ini", key="btn_cek_quota", use_container_width=True):
            try:
                # Hitung log activity hari ini
                ws = get_ws_audit("ACTIVITY_LOG")
                if ws is None:
                    st.sidebar.error("Gagal akses ACTIVITY_LOG")
                else:
                    all_values = ws.get_all_values()
                    
                    from datetime import datetime
                    from zoneinfo import ZoneInfo
                    
                    _today_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
                    _today_count = sum(1 for row in all_values[1:] if len(row) > 0 and row[0].startswith(_today_str))
                    
                    # Hitung heartbeat aktif
                    ws_hb = get_ws_audit("ACTIVITY_HEARTBEAT")
                    _hb_count = 0
                    if ws_hb is not None:
                        _hb_values = ws_hb.get_all_values()
                        _hb_count = max(0, len(_hb_values) - 1)
                    
                    st.sidebar.success(f"📊 Log hari ini: **{_today_count}** baris")
                    st.sidebar.info(f"👥 User aktif: **{_hb_count}**")
                    st.sidebar.caption(f"📅 Tanggal: {_today_str}")
                    
                    # Estimasi quota
                    _est_read = _today_count * 2 + _hb_count * 20  # kasar
                    _est_write = _today_count + _hb_count * 20
                    
                    st.sidebar.markdown("---")
                    st.sidebar.markdown("**📈 Estimasi API Call:**")
                    st.sidebar.write(f"• Read: ~**{_est_read}**")
                    st.sidebar.write(f"• Write: ~**{_est_write}**")
                    
                    # Quota Google Sheets per day = 300 per minute × 60 × 24 = 432,000
                    # Tapi praktiknya 100-300 request/menit per user
                    st.sidebar.caption("💡 Limit: 300 read + 300 write per menit (per project)")
            
            except Exception as e:
                st.sidebar.error(f"❌ Error: {str(e)[:100]}")

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

# =========================================================================
# 💓 HEARTBEAT — TRACKING USER AKTIF
# =========================================================================
_HEARTBEAT_HEADER = ["username", "session_id", "role", "last_heartbeat", "status"]


def write_heartbeat_to_sheet(username, session_id, role, status="ONLINE"):
    """
    Update/tambah baris heartbeat user di sheet ACTIVITY_HEARTBEAT.
    Kalau username sudah ada → update. Kalau belum → tambah.
    
    Args:
        username (str): nama user
        session_id (str): ID sesi user
        role (str): role user
        status (str): "ONLINE" | "IDLE" | "AWAY"
    
    Returns: (success, message)
    """
    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_HEARTBEAT")
            if ws is None:
                return False, "❌ Gagal akses ACTIVITY_HEARTBEAT"
            
            # Pastikan header ada
            try:
                first_row = ws.row_values(1)
                if not first_row or first_row[0].lower() != "username":
                    ws.insert_row(_HEARTBEAT_HEADER, index=1)
            except Exception:
                pass
            
            # Waktu sekarang
            now_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
            
            # Baca semua data untuk cari user
            all_values = ws.get_all_values()
            if len(all_values) < 1:
                # Sheet kosong, langsung append
                ws.append_row([username, session_id, role, now_str, status],
                              value_input_option="USER_ENTERED")
                return True, f"✅ Heartbeat ditambahkan: {username}"
            
            # Cari username di kolom B (index 1)
            header = all_values[0]
            col_username = 0
            for idx, h in enumerate(header):
                if h.lower().strip() == "username":
                    col_username = idx
                    break
            
            row_to_update = None
            for row_idx, row in enumerate(all_values[1:], start=2):
                if len(row) > col_username and row[col_username].strip().lower() == username.strip().lower():
                    row_to_update = row_idx
                    break
            
            if row_to_update:
                # Update baris
                ws.update(f"A{row_to_update}:E{row_to_update}",
                          [[username, session_id, role, now_str, status]],
                          value_input_option="USER_ENTERED")
                return True, f"✅ Heartbeat diupdate: {username}"
            else:
                # Tambah baris baru
                ws.append_row([username, session_id, role, now_str, status],
                              value_input_option="USER_ENTERED")
                return True, f"✅ Heartbeat ditambahkan: {username}"
    
    except Exception as e:
        print(f"[WRITE_HEARTBEAT ERROR] {e}")
        return False, f"❌ Gagal: {str(e)[:150]}"


def remove_heartbeat_from_sheet(username):
    """
    Hapus baris heartbeat user (dipakai saat logout manual).
    """
    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_HEARTBEAT")
            if ws is None:
                return False, "❌ Gagal akses ACTIVITY_HEARTBEAT"
            
            all_values = ws.get_all_values()
            if len(all_values) < 2:
                return True, "Sheet kosong"
            
            header = all_values[0]
            col_username = 0
            for idx, h in enumerate(header):
                if h.lower().strip() == "username":
                    col_username = idx
                    break
            
            # Cari baris user
            for row_idx, row in enumerate(all_values[1:], start=2):
                if len(row) > col_username and row[col_username].strip().lower() == username.strip().lower():
                    ws.delete_rows(row_idx)
                    return True, f"✅ Heartbeat dihapus: {username}"
            
            return True, f"ℹ️ User {username} tidak ada di heartbeat"
    
    except Exception as e:
        print(f"[REMOVE_HEARTBEAT ERROR] {e}")
        return False, f"❌ Gagal: {str(e)[:150]}"


def get_stale_heartbeats(threshold_minutes=5):
    """
    Ambil daftar user yang heartbeat terakhirnya > threshold_minutes.
    
    SAFETY:
    - Guard threshold (minimal 2 menit)
    - Skip kalau format tanggal salah
    - Skip kalau user tidak valid
    """
    try:
        # 🛡️ GUARD: Jangan izinkan threshold < 2 menit
        if threshold_minutes is None or threshold_minutes < 0.1:
            threshold_minutes = 0.5
            print(f"[WARN] Threshold dipaksa jadi 0.5 menit")
        
        ws = get_ws_audit("ACTIVITY_HEARTBEAT")
        if ws is None:
            return []
        
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return []
        
        header = all_values[0]
        col_idx = {}
        for idx, h in enumerate(header):
            col_idx[h.lower().strip()] = idx
        
        # Cek header lengkap
        for _req in ["username", "session_id", "last_heartbeat"]:
            if _req not in col_idx:
                print(f"[ERROR] Header '{_req}' tidak ditemukan. Header: {header}")
                return []
        
        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        stale_users = []
        
        for row in all_values[1:]:
            if len(row) < 4:
                continue
            
            try:
                _username = row[col_idx["username"]].strip()
                _session = row[col_idx["session_id"]].strip()
                _role = row[col_idx.get("role", 2)].strip() if "role" in col_idx else "-"
                _last_hb_str = row[col_idx["last_heartbeat"]].strip()
                
                # 🛡️ Skip kalau data kosong
                if not _username or not _last_hb_str:
                    continue
                
                # 🛡️ Skip baris DEBUG
                if _username.upper() in ["DEBUG_TEST", "DEBUG_HEARTBEAT"]:
                    continue
                
                # Parse tanggal
                _last_hb = datetime.strptime(_last_hb_str, "%d/%m/%Y %H:%M:%S").replace(
                    tzinfo=ZoneInfo("Asia/Jakarta")
                )
                _selisih_menit = (now - _last_hb).total_seconds() / 60
                
                if _selisih_menit > threshold_minutes:
                    stale_users.append({
                        "username": _username,
                        "session_id": _session,
                        "role": _role,
                        "last_heartbeat": _last_hb_str,
                        "selisih_menit": int(_selisih_menit),
                    })
            except Exception as e_row:
                print(f"[SKIP ROW] {e_row} - row: {row}")
                continue
        
        return stale_users
    
    except Exception as e:
        print(f"[GET_STALE_HEARTBEAT ERROR] {e}")
        return []


def clear_all_heartbeat():
    """Hapus semua baris heartbeat (kecuali header). Dipakai emergency."""
    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_HEARTBEAT")
            if ws is None:
                return False, "❌ Gagal akses sheet"
            
            all_values = ws.get_all_values()
            if len(all_values) <= 1:
                return True, "Sheet sudah kosong"
            
            # Hapus baris 2 sampai akhir
            ws.delete_rows(2, len(all_values))
            return True, f"✅ {len(all_values) - 1} baris heartbeat dihapus"
    
    except Exception as e:
        return False, f"❌ Gagal: {str(e)[:150]}"



# =========================================================================
# 📊 GENERATOR LAPORAN BULANAN — MULTI PROGRAM (PSM, PWP, SG, SUEGER)
# =========================================================================
# Fungsi-fungsi ini generate laporan bulanan dengan format sesuai Excel user.
# Setiap program punya sheet terpisah di Spreadsheet Laporan.
# =========================================================================

from datetime import timedelta as _td


def _get_weeks_from_periode(periode_df, bulan_int, tahun_int, filter_prefix=None):
    """
    Ambil daftar periode untuk bulan tertentu.
    Return list of dict {period_id, start, end, jhk, label, target}.
    
    Args:
        periode_df: DataFrame dari session_state (periods_df atau periods_pps_df)
        bulan_int: 1-12
        tahun_int: 2026 dst
        filter_prefix: "PWP", "SGS", "SGR" (opsional)
    """
    _list = []
    if periode_df is None or periode_df.empty:
        return _list
    
    _df = periode_df.copy()
    _df.columns = _df.columns.astype(str).str.strip().str.lower()
    
    if "start_date" not in _df.columns or "end_date" not in _df.columns:
        return _list
    
    _df["_start"] = pd.to_datetime(_df["start_date"], errors="coerce")
    _df["_end"] = pd.to_datetime(_df["end_date"], errors="coerce")
    _df = _df.dropna(subset=["_start", "_end"])
    
    # Filter bulan & tahun
    _df = _df[(_df["_start"].dt.month == bulan_int) & (_df["_start"].dt.year == tahun_int)]
    
    # Filter prefix kalau ada
    if filter_prefix:
        _df = _df[_df["period_id"].astype(str).str.upper().str.startswith(filter_prefix, na=False)]
    
    _df = _df.sort_values("_start")
    
    for _, _row in _df.iterrows():
        _pid = str(_row.get("period_id", "")).strip()
        _start = _row["_start"].date()
        _end = _row["_end"].date()
        _jhk = (_end - _start).days + 1
        
        # Ambil target dari berbagai kolom
        _target = 0
        for _col in ["target_total", "target", "target_personil"]:
            if _col in _row.index:
                try:
                    _val = pd.to_numeric(_row[_col], errors="coerce")
                    if pd.notna(_val) and _val > 0:
                        _target = int(_val)
                        break
                except Exception:
                    pass
        
        _list.append({
            "period_id": _pid,
            "start": _start,
            "end": _end,
            "jhk": _jhk,
            "target": _target,
            "label": f"{_start.strftime('%d/%m')}-{_end.strftime('%d/%m')}",
        })
    
    return _list


def _hitung_target(toko, jhk):
    """Hitung target pertoko & pershift. Return (pertoko, pershift)."""
    if toko <= 0 or jhk <= 0:
        return 0, 0
    _pertoko = toko / jhk
    _pershift = _pertoko / 2
    return _pertoko, _pershift


def _format_angka(val, desimal=2):
    """Format angka: kalau 0 atau kosong → '-', kalau ada desimal → sesuai."""
    if val is None:
        return "-"
    if isinstance(val, (int, float)):
        if val == 0:
            return "-"
        if desimal == 0:
            return str(int(val))
        return f"{val:.{desimal}f}"
    return str(val)


def _bangun_sheet_psm(sales_person_df, periode_df, sales_item_df, person_df, bulan_int, tahun_int):
    """
    Bangun matrix laporan PSM (per hari, breakdown WEEK).
    Return: (sheet_name, rows_matrix)
    """
    import calendar
    _bulan_nama = calendar.month_name[bulan_int].upper()
    _sheet_name = f"{_bulan_nama} {tahun_int}"
    
    if sales_person_df is None or sales_person_df.empty:
        return _sheet_name, None
    
    _sp = sales_person_df.copy()
    _sp.columns = _sp.columns.astype(str).str.strip().str.lower()
    
    if "updated_at" not in _sp.columns:
        return _sheet_name, None
    
    _sp["_dt"] = pd.to_datetime(_sp["updated_at"], errors="coerce")
    _sp = _sp.dropna(subset=["_dt"])
    _sp = _sp[(_sp["_dt"].dt.month == bulan_int) & (_sp["_dt"].dt.year == tahun_int)]
    
    if _sp.empty:
        return _sheet_name, None
    
    # Ambil periode PSM bulan ini
    _weeks = _get_weeks_from_periode(periode_df, bulan_int, tahun_int)
    
    if not _weeks:
        return _sheet_name, None
    
    # Ambil target toko per periode dari SALES_ITEM
    _target_map = {}
    if sales_item_df is not None and not sales_item_df.empty:
        _si = sales_item_df.copy()
        _si.columns = _si.columns.astype(str).str.strip().str.lower()
        if "target_qty" in _si.columns and "period_id" in _si.columns:
            _si["target_qty"] = pd.to_numeric(_si["target_qty"], errors="coerce").fillna(0)
            _grp = _si.groupby(_si["period_id"].astype(str).str.strip())["target_qty"].sum()
            _target_map = _grp.to_dict()
    
    # Assign target ke weeks
    for _w in _weeks:
        _w["target"] = int(_target_map.get(_w["period_id"], 0))
    
    # Ambil daftar personil aktif
    _pers = person_df.copy() if person_df is not None else pd.DataFrame()
    if not _pers.empty:
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        if "active" in _pers.columns:
            _pers = _pers[pd.to_numeric(_pers["active"], errors="coerce") == 1]
        _pers["person_clean"] = _pers["person_name"].astype(str).str.strip().str.upper()
        _pers = _pers.sort_values("person_clean").drop_duplicates(subset=["person_clean"])
    
    if _pers.empty:
        _names = _sp["person_name"].dropna().astype(str).str.upper().unique()
        _pers = pd.DataFrame({"person_clean": _names, "nik": "-", "person_name": _names})
    
    if "nik" not in _pers.columns:
        for _c in ["person_id", "nik_personil"]:
            if _c in _pers.columns:
                _pers["nik"] = _pers[_c]
                break
        else:
            _pers["nik"] = "-"
    
    # Bangun matrix
    # Row 1: Toko + WEEK labels
    _row1 = ["", "Toko", "C383/KARANG SATRIA"]
    for _idx, _w in enumerate(_weeks):
        _row1.append(f"PSM WEEK {_idx+1}")
        _cols_week = 3 + _w["jhk"] + 3  # 3 target + N hari + 3 footer
        _row1.extend([""] * (_cols_week - 1))
    _row1.extend(["FULL MONTH", "", "", ""])
    
    # Row 2: Header kolom
    _row2 = ["No", "NIK", "Nama Personil"]
    for _w in _weeks:
        _row2.extend(["TGT TOKO", "TGT/hari", "TGT/shift"])
        for _d in range(_w["jhk"]):
            _row2.append(_w["start"].strftime("%d/%m") if _d == 0 else "")
        _row2.extend(["TOTAL", "GAP", "ACV%"])
    _row2.extend(["TOTAL", "GAP", "ACV%"])
    
    _rows = [_row1, _row2]
    
    for _idx, (_, _p) in enumerate(_pers.iterrows(), start=1):
        _nama = str(_p.get("person_clean", "")).strip().upper()
        _nik = str(_p.get("nik", "-")).replace(".0", "").strip()
        if not _nik or _nik == "nan":
            _nik = "-"
        
        _row = [_idx, _nik, _nama]
        _grand_total = 0
        _grand_target = 0
        
        for _w in _weeks:
            _target_toko = _w["target"]
            _target_pertoko, _target_pershift = _hitung_target(_target_toko, _w["jhk"])
            
            _row.extend([
                _format_angka(_target_toko, 0),
                _format_angka(_target_pertoko),
                _format_angka(_target_pershift),
            ])
            
            # N hari actual
            _week_total = 0
            for _d_offset in range(_w["jhk"]):
                _tgl = _w["start"] + _td(days=_d_offset)
                _mask = (_sp["person_name"].astype(str).str.upper() == _nama) & (_sp["_dt"].dt.date == _tgl)
                if _mask.any():
                    _qty = int(pd.to_numeric(_sp.loc[_mask, "actual_qty"], errors="coerce").fillna(0).sum())
                else:
                    _qty = 0
                _row.append(_qty if _qty > 0 else "-")
                _week_total += _qty
            
            # TOTAL, GAP, ACV% per week
            _gap = _target_pertoko - _week_total
            _acv = (_week_total / _target_pertoko * 100) if _target_pertoko > 0 else 0
            
            _row.append(_week_total if _week_total > 0 else "-")
            _row.append(_format_angka(-_gap))
            _row.append(f"{_acv:.1f}%" if _target_pertoko > 0 else "-")
            
            _grand_total += _week_total
            _grand_target += _target_pertoko
        
        # Grand total
        _row.append(_grand_total if _grand_total > 0 else "-")
        _row.append(_format_angka(-(_grand_target - _grand_total)))
        _row.append(f"{(_grand_total / _grand_target * 100):.1f}%" if _grand_target > 0 else "-")
        
        _rows.append(_row)
    
    # Row Total
    _total_row = ["Total", "", ""]
    _grand_total_all = 0
    _grand_target_all = 0
    for _w in _weeks:
        _t_pertoko, _t_pershift = _hitung_target(_w["target"], _w["jhk"])
        _total_row.extend([
            _format_angka(_w["target"], 0),
            _format_angka(_t_pertoko),
            _format_angka(_t_pershift),
        ])
        _total_row.extend([""] * _w["jhk"])
        _total_row.extend(["", "", ""])
        _grand_target_all += _t_pertoko
    _total_row.extend(["", "", ""])
    _rows.append(_total_row)
    
    return _sheet_name, _rows


def _bangun_sheet_pps(sales_pps_df, periode_pps_df, person_df, bulan_int, tahun_int,
                     prefix, sheet_suffix, kolom_a, kolom_b, label_a, label_b):
    """
    Bangun matrix laporan PPS (PWP, SG, Sueger).
    
    Args:
        prefix: "PWP" | "SGS" | "SGR"
        sheet_suffix: "PWP" | "SG" | "SUEGER"
        kolom_a: nama kolom untuk nilai A (syarat / qty_sg)
        kolom_b: nama kolom untuk nilai B (qty_pwp / redeem_sueger)
        label_a, label_b: label kolom
    """
    import calendar
    _bulan_nama = calendar.month_name[bulan_int].upper()
    _sheet_name = f"{_bulan_nama} {tahun_int}_{sheet_suffix}"
    
    if sales_pps_df is None or sales_pps_df.empty:
        return _sheet_name, None
    
    _pps = sales_pps_df.copy()
    _pps.columns = _pps.columns.astype(str).str.strip().str.lower()
    
    if "updated_at" not in _pps.columns:
        return _sheet_name, None
    
    _pps["_dt"] = pd.to_datetime(_pps["updated_at"], errors="coerce")
    _pps = _pps.dropna(subset=["_dt"])
    _pps = _pps[(_pps["_dt"].dt.month == bulan_int) & (_pps["_dt"].dt.year == tahun_int)]
    
    if _pps.empty:
        return _sheet_name, None
    
    # Ambil periode PPS
    _weeks = _get_weeks_from_periode(periode_pps_df, bulan_int, tahun_int, filter_prefix=prefix)
    
    if not _weeks:
        return _sheet_name, None
    
    # Ambil personil aktif
    _pers = person_df.copy() if person_df is not None else pd.DataFrame()
    if not _pers.empty:
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        if "active" in _pers.columns:
            _pers = _pers[pd.to_numeric(_pers["active"], errors="coerce") == 1]
        _pers["person_clean"] = _pers["person_name"].astype(str).str.strip().str.upper()
        _pers = _pers.sort_values("person_clean").drop_duplicates(subset=["person_clean"])
    
    if _pers.empty:
        if "kasir_name" in _pps.columns:
            _names = _pps["kasir_name"].dropna().astype(str).str.upper().unique()
            _pers = pd.DataFrame({"person_clean": _names, "nik": "-", "person_name": _names})
        else:
            return _sheet_name, None
    
    if "nik" not in _pers.columns:
        for _c in ["person_id", "nik_personil"]:
            if _c in _pers.columns:
                _pers["nik"] = _pers[_c]
                break
        else:
            _pers["nik"] = "-"
    
    # Bangun matrix
    _row1 = ["", "Toko", "C383/KARANG SATRIA"]
    for _idx, _w in enumerate(_weeks):
        _row1.append(f"{sheet_suffix} WEEK {_idx+1}")
        _cols_week = 3 + _w["jhk"] + 3
        _row1.extend([""] * (_cols_week - 1))
    _row1.extend(["FULL MONTH", "", "", ""])
    
    _row2 = ["No", "NIK", "Nama Personil"]
    for _w in _weeks:
        _row2.extend(["TGT TOKO", "TGT/hari", "TGT/shift"])
        for _d in range(_w["jhk"]):
            _row2.append(_w["start"].strftime("%d/%m") if _d == 0 else "")
        _row2.extend(["TOTAL", "GAP", "ACV%"])
    _row2.extend(["TOTAL", "GAP", "ACV%"])
    
    _rows = [_row1, _row2]
    
    for _idx, (_, _p) in enumerate(_pers.iterrows(), start=1):
        _nama = str(_p.get("person_clean", "")).strip().upper()
        _nik = str(_p.get("nik", "-")).replace(".0", "").strip()
        if not _nik or _nik == "nan":
            _nik = "-"
        
        _row = [_idx, _nik, _nama]
        _grand_total = 0
        _grand_target = 0
        
        for _w in _weeks:
            _target_toko = _w["target"]
            _target_pertoko, _target_pershift = _hitung_target(_target_toko, _w["jhk"])
            
            _row.extend([
                _format_angka(_target_toko, 0),
                _format_angka(_target_pertoko),
                _format_angka(_target_pershift),
            ])
            
            _week_total = 0
            for _d_offset in range(_w["jhk"]):
                _tgl = _w["start"] + _td(days=_d_offset)
                
                # Cari kolom kasir (bisa "kasir_name")
                if "kasir_name" in _pps.columns:
                    _mask = (_pps["kasir_name"].astype(str).str.upper() == _nama) & (_pps["_dt"].dt.date == _tgl)
                else:
                    _mask = pd.Series([False] * len(_pps), index=_pps.index)
                
                if _mask.any():
                    _val_a = 0
                    _val_b = 0
                    if kolom_a in _pps.columns:
                        _val_a = int(pd.to_numeric(_pps.loc[_mask, kolom_a], errors="coerce").fillna(0).sum())
                    if kolom_b in _pps.columns:
                        _val_b = int(pd.to_numeric(_pps.loc[_mask, kolom_b], errors="coerce").fillna(0).sum())
                    
                    if _val_a > 0 or _val_b > 0:
                        _row.append(f"{_val_a}/{_val_b}" if _val_a > 0 else f"-/{_val_b}")
                    else:
                        _row.append("-")
                    
                    _week_total += _val_b
                else:
                    _row.append("-")
            
            _gap = _target_pertoko - _week_total
            _acv = (_week_total / _target_pertoko * 100) if _target_pertoko > 0 else 0
            
            _row.append(_week_total if _week_total > 0 else "-")
            _row.append(_format_angka(-_gap))
            _row.append(f"{_acv:.1f}%" if _target_pertoko > 0 else "-")
            
            _grand_total += _week_total
            _grand_target += _target_pertoko
        
        _row.append(_grand_total if _grand_total > 0 else "-")
        _row.append(_format_angka(-(_grand_target - _grand_total)))
        _row.append(f"{(_grand_total / _grand_target * 100):.1f}%" if _grand_target > 0 else "-")
        
        _rows.append(_row)
    
    # Row Total
    _total_row = ["Total", "", ""]
    for _w in _weeks:
        _t_pertoko, _t_pershift = _hitung_target(_w["target"], _w["jhk"])
        _total_row.extend([
            _format_angka(_w["target"], 0),
            _format_angka(_t_pertoko),
            _format_angka(_t_pershift),
        ])
        _total_row.extend([""] * _w["jhk"])
        _total_row.extend(["", "", ""])
    _total_row.extend(["", "", ""])
    _rows.append(_total_row)
    
    return _sheet_name, _rows


# ==== PUBLIC FUNCTIONS ====

def generate_laporan_psm(bulan_int, tahun_int):
    """Generate laporan PSM bulanan (sheet: [BULAN] [TAHUN])."""
    try:
        _sp = st.session_state.get("sales_person_df", pd.DataFrame())
        _per = st.session_state.get("periods_df", pd.DataFrame())
        _si = st.session_state.get("sales_item_df", pd.DataFrame())
        _pers = st.session_state.get("person_df", pd.DataFrame())
        
        _sheet_name, _rows = _bangun_sheet_psm(_sp, _per, _si, _pers, bulan_int, tahun_int)
        
        if _rows is None:
            return False, f"❌ Tidak ada data PSM untuk bulan tersebut", 0
        
        _ok, _msg = write_laporan_bulanan(_sheet_name, _rows)
        if not _ok:
            return False, _msg, 0
        
        return True, f"✅ Laporan PSM {_sheet_name} tersimpan ({len(_rows)} baris)", len(_rows) - 2
    except Exception as e:
        import traceback
        print(f"[GEN_PSM ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0


def generate_laporan_pwp(bulan_int, tahun_int):
    """Generate laporan PWP bulanan (sheet: [BULAN] [TAHUN]_PWP)."""
    try:
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame())
        _per_pps = st.session_state.get("periods_pps_df", pd.DataFrame())
        _pers = st.session_state.get("person_df", pd.DataFrame())
        
        _sheet_name, _rows = _bangun_sheet_pps(
            _pps, _per_pps, _pers, bulan_int, tahun_int,
            prefix="PWP", sheet_suffix="PWP",
            kolom_a="syarat_pwp", kolom_b="qty_pwp",
            label_a="Syarat", label_b="Qty"
        )
        
        if _rows is None:
            return False, "❌ Tidak ada data PWP untuk bulan tersebut", 0
        
        _ok, _msg = write_laporan_bulanan(_sheet_name, _rows)
        if not _ok:
            return False, _msg, 0
        
        return True, f"✅ Laporan PWP {_sheet_name} tersimpan ({len(_rows)} baris)", len(_rows) - 2
    except Exception as e:
        import traceback
        print(f"[GEN_PWP ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0


def generate_laporan_sg(bulan_int, tahun_int):
    """Generate laporan Serba Gratis (sheet: [BULAN] [TAHUN]_SG)."""
    try:
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame())
        _per_pps = st.session_state.get("periods_pps_df", pd.DataFrame())
        _pers = st.session_state.get("person_df", pd.DataFrame())
        
        _sheet_name, _rows = _bangun_sheet_pps(
            _pps, _per_pps, _pers, bulan_int, tahun_int,
            prefix="SGS", sheet_suffix="SG",
            kolom_a="qty_sg", kolom_b="qty_sg",
            label_a="Qty", label_b="Qty"
        )
        
        if _rows is None:
            return False, "❌ Tidak ada data SG untuk bulan tersebut", 0
        
        _ok, _msg = write_laporan_bulanan(_sheet_name, _rows)
        if not _ok:
            return False, _msg, 0
        
        return True, f"✅ Laporan SG {_sheet_name} tersimpan ({len(_rows)} baris)", len(_rows) - 2
    except Exception as e:
        import traceback
        print(f"[GEN_SG ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0


def generate_laporan_sueger(bulan_int, tahun_int):
    """Generate laporan Sueger (sheet: [BULAN] [TAHUN]_SUEGER)."""
    try:
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame())
        _per_pps = st.session_state.get("periods_pps_df", pd.DataFrame())
        _pers = st.session_state.get("person_df", pd.DataFrame())
        
        _sheet_name, _rows = _bangun_sheet_pps(
            _pps, _per_pps, _pers, bulan_int, tahun_int,
            prefix="SGR", sheet_suffix="SUEGER",
            kolom_a="syarat_sueger", kolom_b="redeem_sueger",
            label_a="Syarat", label_b="Redeem"
        )
        
        if _rows is None:
            return False, "❌ Tidak ada data Sueger untuk bulan tersebut", 0
        
        _ok, _msg = write_laporan_bulanan(_sheet_name, _rows)
        if not _ok:
            return False, _msg, 0
        
        return True, f"✅ Laporan Sueger {_sheet_name} tersimpan ({len(_rows)} baris)", len(_rows) - 2
    except Exception as e:
        import traceback
        print(f"[GEN_SUEGER ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0


def generate_semua_laporan(bulan_int, tahun_int):
    """
    Generate 4 laporan sekaligus: PSM, PWP, SG, Sueger.
    
    Return:
        dict {
            "success": [list of dict {nama, pesan, baris}],
            "failed": [list of dict {nama, error}],
            "total_sheet": int,
            "total_baris": int,
        }
    """
    _result = {
        "success": [],
        "failed": [],
        "total_sheet": 0,
        "total_baris": 0,
    }
    
    _laporan_list = [
        ("PSM", generate_laporan_psm),
        ("PWP", generate_laporan_pwp),
        ("SG", generate_laporan_sg),
        ("SUEGER", generate_laporan_sueger),
    ]
    
    for _nama, _fungsi in _laporan_list:
        try:
            _ok, _msg, _n = _fungsi(bulan_int, tahun_int)
            
            if _ok:
                _result["success"].append({
                    "nama": _nama,
                    "pesan": _msg,
                    "baris": _n,
                })
                _result["total_sheet"] += 1
                _result["total_baris"] += _n
            else:
                _result["failed"].append({
                    "nama": _nama,
                    "error": _msg,
                })
        except Exception as e:
            _result["failed"].append({
                "nama": _nama,
                "error": f"❌ Error: {str(e)[:100]}",
            })
            continue
    
    return _result

# =========================================================================
# 📝 ISI LAPORAN PSM — HANYA TARGET & ACTUAL (Rumus Excel Dibiarkan)
# =========================================================================
# =========================================================================
# 📝 ISI LAPORAN PSM — HANYA TARGET & ACTUAL + FORMAT (Rumus Excel Dibiarkan)
# =========================================================================
def isi_laporan_psm(bulan_int, tahun_int, sheet_name):
    """
    Isi kolom TARGET TOKO & ACTUAL di sheet PSM yang sudah ada format + rumus.
    Urutkan personil berdasarkan NIK (person_id) ascending.
    Set alignment center untuk cell yang diisi.
    
    Return: (success, message, jumlah_update)
    """
    try:
        # === 1. Ambil data ===
        _sp = st.session_state.get("sales_person_df", pd.DataFrame()).copy()
        _si = st.session_state.get("sales_item_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _sp.empty or _pers.empty:
            return False, "❌ Data sales_person atau person_df kosong", 0
        
        # Normalisasi kolom
        _sp.columns = _sp.columns.astype(str).str.strip().str.lower()
        _si.columns = _si.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        # === 2. Ambil target per periode dari SALES_ITEM ===
        _target_map = {}
        if not _si.empty and "target_qty" in _si.columns and "period_id" in _si.columns:
            _si["target_qty"] = pd.to_numeric(_si["target_qty"], errors="coerce").fillna(0)
            _grp = _si.groupby(_si["period_id"].astype(str).str.strip())["target_qty"].sum()
            _target_map = _grp.to_dict()
        
        # === 3. Ambil daftar personil aktif — URUT BERDASARKAN NIK ASCENDING ===
        if "active" in _pers.columns:
            _pers = _pers[pd.to_numeric(_pers["active"], errors="coerce") == 1]
        
        # Cek kolom NIK
        _nik_col = None
        for _c in ["nik", "person_id"]:
            if _c in _pers.columns:
                _nik_col = _c
                break
        
        if _nik_col:
            # Konversi ke numeric untuk sorting
            _pers["_nik_sort"] = pd.to_numeric(_pers[_nik_col], errors="coerce").fillna(99999999)
            _pers = _pers.sort_values("_nik_sort", ascending=True)
        else:
            # Fallback: urut berdasarkan person_id string
            if "person_id" in _pers.columns:
                _pers = _pers.sort_values("person_id", ascending=True)
        
        _pers["person_clean"] = _pers["person_name"].astype(str).str.strip().str.upper()
        _pers = _pers.drop_duplicates(subset=["person_clean"])
        _pers_list = _pers["person_clean"].tolist()
        
        if not _pers_list:
            return False, "❌ Tidak ada personil aktif", 0
        
        # === 4. Parse tanggal di sales_person ===
        if "updated_at" not in _sp.columns:
            return False, "❌ Kolom updated_at tidak ada", 0
        _sp["_dt"] = pd.to_datetime(_sp["updated_at"], errors="coerce")
        _sp = _sp.dropna(subset=["_dt"])
        
        # === 5. Buka worksheet ===
        ws = get_ws_laporan(sheet_name)
        if ws is None:
            return False, f"❌ Sheet {sheet_name} tidak ditemukan", 0
        
        # === 6. Konfigurasi kolom per WEEK ===
        _week_config = [
            {
                "name": "W1",
                "period_id": "S01",
                "tanggal": list(range(1, 8)),           # 1-7
                "col_target": "D",
                "col_actual_start": "G",
                "col_actual_end": "M",
            },
            {
                "name": "W2",
                "period_id": "S02",
                "tanggal": list(range(8, 16)),          # 8-15
                "col_target": "Q",
                "col_actual_start": "T",
                "col_actual_end": "AA",
            },
            {
                "name": "W3",
                "period_id": "S03",
                "tanggal": list(range(16, 24)),         # 16-23
                "col_target": "AE",
                "col_actual_start": "AH",
                "col_actual_end": "AO",
            },
            {
                "name": "W4",
                "period_id": "S04",
                "tanggal": list(range(24, 31)),         # 24-30
                "col_target": "AS",
                "col_actual_start": "AV",
                "col_actual_end": "BC",
            },
        ]
        
        # === 7. Bangun batch update untuk VALUE ===
        _updates = []
        
        # TARGET: 1 nilai sama untuk semua personil
        _target_ranges = []
        for _w in _week_config:
            _target_val = int(_target_map.get(_w["period_id"], 0))
            if _target_val > 0:
                _target_values = [[_target_val] for _ in range(len(_pers_list))]
                _range = f"{_w['col_target']}3:{_w['col_target']}{2 + len(_pers_list)}"
                _updates.append({
                    "range": _range,
                    "values": _target_values,
                })
                _target_ranges.append(_range)
        
        # ACTUAL: per personil per tanggal
        _actual_ranges = []
        for _row_offset, _person in enumerate(_pers_list):
            _row_idx = 3 + _row_offset
            
            for _w in _week_config:
                _actual_values = []
                
                for _tgl in _w["tanggal"]:
                    _mask = (
                        (_sp["person_name"].astype(str).str.upper() == _person) &
                        (_sp["_dt"].dt.day == _tgl) &
                        (_sp["_dt"].dt.month == bulan_int) &
                        (_sp["_dt"].dt.year == tahun_int)
                    )
                    
                    if _mask.any():
                        _qty = int(pd.to_numeric(_sp.loc[_mask, "actual_qty"], errors="coerce").fillna(0).sum())
                    else:
                        _qty = 0
                    
                    _actual_values.append(_qty if _qty > 0 else "")
                
                _actual_range = f"{_w['col_actual_start']}{_row_idx}:{_w['col_actual_end']}{_row_idx}"
                _updates.append({
                    "range": _actual_range,
                    "values": [_actual_values],
                })
                _actual_ranges.append(_actual_range)
        
        # === 8. Batch update untuk VALUE ===
        if _updates:
            ws.batch_update(_updates, value_input_option="USER_ENTERED")
        
        # === 9. Set FORMAT: Center Alignment ===
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, HorizontalAlignment,
                format_cell_range,
            )
            
            # Format default untuk semua range yang di-update
            _fmt = CellFormat(
                horizontalAlignment=HorizontalAlignment.CENTER,
                verticalAlignment="MIDDLE",
                textFormat=TextFormat(
                    fontFamily="Calibri",
                    fontSize=10,
                    bold=True,
                ),
            )
            
            for _range in _target_ranges + _actual_ranges:
                try:
                    format_cell_range(ws, _range, _fmt)
                except Exception as _e_fmt:
                    print(f"[FORMAT WARN] {_range}: {_e_fmt}")
                    continue
        
        except ImportError:
            print("[FORMAT WARN] gspread_formatting tidak terinstall, skip format")
        except Exception as _e_fmt_all:
            print(f"[FORMAT WARN] Gagal set format: {_e_fmt_all}")
        
        return True, f"✅ {len(_updates)} range di-update + format center ({len(_pers_list)} personil)", len(_updates)
    
    except Exception as e:
        import traceback
        print(f"[ISI_LAPORAN_PSM ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0

# =========================================================================
# 📝 ISI LAPORAN PWP — HANYA SYARAT & REDEEM (Rumus Excel Dibiarkan)
# =========================================================================
def isi_laporan_pwp(bulan_int, tahun_int, sheet_name):
    """
    Isi kolom Struk Syarat & Struk Redemp di sheet PWP.
    
    Struktur:
    - W1 (tgl 1-15): Kolom D, G, J, M, ... (syarat) & E, H, K, N, ... (redemp)
    - W2 (tgl 16-30): Kolom AX, BA, BD, ... (syarat) & AY, BB, BE, ... (redemp)
    
    Rumus % Redempt dibiarkan.
    Urutkan personil berdasarkan NIK ascending.
    """
    try:
        # === 1. Ambil data ===
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _pps.empty or _pers.empty:
            return False, "❌ Data PPS atau person_df kosong", 0
        
        # Normalisasi kolom
        _pps.columns = _pps.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        # === 2. Parse tanggal di sales_pps ===
        if "updated_at" not in _pps.columns:
            return False, "❌ Kolom updated_at tidak ada", 0
        _pps["_dt"] = pd.to_datetime(_pps["updated_at"], errors="coerce")
        _pps = _pps.dropna(subset=["_dt"])
        
        # === 3. Ambil daftar personil aktif — URUT NIK ASCENDING ===
        if "active" in _pers.columns:
            _pers = _pers[pd.to_numeric(_pers["active"], errors="coerce") == 1]
        
        _nik_col = None
        for _c in ["nik", "person_id"]:
            if _c in _pers.columns:
                _nik_col = _c
                break
        
        if _nik_col:
            _pers["_nik_sort"] = pd.to_numeric(_pers[_nik_col], errors="coerce").fillna(99999999)
            _pers = _pers.sort_values("_nik_sort", ascending=True)
        
        _pers["person_clean"] = _pers["person_name"].astype(str).str.strip().str.upper()
        _pers = _pers.drop_duplicates(subset=["person_clean"])
        _pers_list = _pers["person_clean"].tolist()
        
        if not _pers_list:
            return False, "❌ Tidak ada personil aktif", 0
        
        # === 4. Buka worksheet ===
        ws = get_ws_laporan(sheet_name)
        if ws is None:
            return False, f"❌ Sheet {sheet_name} tidak ditemukan", 0
        
        # === 5. Konfigurasi kolom per tanggal ===
        # Struktur: tiap tanggal = 3 kolom (syarat, redemp, %rumus)
        # Kita cuma isi kolom 1 (syarat) & 2 (redemp)
        
        # Generate mapping kolom untuk W1 (tgl 1-15)
        # Start dari kolom D (index 3) dengan step 3
        def _col_from_index(idx):
            """Konversi index 0-based ke huruf Excel."""
            result = ""
            idx_1 = idx + 1  # 1-based
            while idx_1 > 0:
                idx_1, rem = divmod(idx_1 - 1, 26)
                result = chr(65 + rem) + result
            return result
        
        def _index_from_col(col):
            """Konversi huruf kolom ke index 0-based."""
            result = 0
            for c in col:
                result = result * 26 + (ord(c.upper()) - 64)
            return result - 1
        
        # W1: mulai dari kolom D (index 3), tgl 1-15 (15 hari)
        # Syarat tgl 1 = D, Redemp tgl 1 = E, % tgl 1 = F
        # Syarat tgl 2 = G, Redemp tgl 2 = H, % tgl 2 = I
        # Step: +3
        _w1_start_idx = _index_from_col("D")  # index 3
        _w1_tanggal = list(range(1, 15))       # 1-15
        
        # W2: mulai dari kolom AZ (index 51), tgl 16-30
        _w2_start_idx = _index_from_col("AZ")  # index 51
        _w2_tanggal = list(range(16, 31))      # 16-30
        
        # Bangun list mapping: [(tgl, col_syarat, col_redemp)]
        _col_map = []
        
        for i, tgl in enumerate(_w1_tanggal):
            _syr_idx = _w1_start_idx + i * 3
            _red_idx = _syr_idx + 1
            _col_map.append({
                "tanggal": tgl,
                "syarat": _col_from_index(_syr_idx),
                "redemp": _col_from_index(_red_idx),
            })
        
        for i, tgl in enumerate(_w2_tanggal):
            _syr_idx = _w2_start_idx + i * 3
            _red_idx = _syr_idx + 1
            _col_map.append({
                "tanggal": tgl,
                "syarat": _col_from_index(_syr_idx),
                "redemp": _col_from_index(_red_idx),
            })
        
        # === 6. Bangun batch update ===
        _updates = []
        _formatted_ranges = []
        
        for _row_offset, _person in enumerate(_pers_list):
            _row_idx = 3 + _row_offset
            
            for _cm in _col_map:
                _tgl = _cm["tanggal"]
                
                # Filter data
                _mask = (
                    (_pps["kasir_name"].astype(str).str.upper() == _person) &
                    (_pps["_dt"].dt.day == _tgl) &
                    (_pps["_dt"].dt.month == bulan_int) &
                    (_pps["_dt"].dt.year == tahun_int)
                )
                
                # Nilai syarat
                if _mask.any() and "syarat_pwp" in _pps.columns:
                    _syarat = int(pd.to_numeric(_pps.loc[_mask, "syarat_pwp"], errors="coerce").fillna(0).sum())
                else:
                    _syarat = 0
                
                # Nilai redemp (qty_pwp)
                if _mask.any() and "qty_pwp" in _pps.columns:
                    _redemp = int(pd.to_numeric(_pps.loc[_mask, "qty_pwp"], errors="coerce").fillna(0).sum())
                else:
                    _redemp = 0
                
                # Update syarat
                _updates.append({
                    "range": f"{_cm['syarat']}{_row_idx}",
                    "values": [[_syarat if _syarat > 0 else ""]],
                })
                _formatted_ranges.append(f"{_cm['syarat']}{_row_idx}")
                
                # Update redemp
                _updates.append({
                    "range": f"{_cm['redemp']}{_row_idx}",
                    "values": [[_redemp if _redemp > 0 else ""]],
                })
                _formatted_ranges.append(f"{_cm['redemp']}{_row_idx}")
        
        # === 7. Batch update value ===
        if _updates:
            ws.batch_update(_updates, value_input_option="USER_ENTERED")
        
        # === 8. Set format center ===
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, HorizontalAlignment,
                format_cell_range,
            )
            _fmt = CellFormat(
                horizontalAlignment=HorizontalAlignment.CENTER,
                verticalAlignment="MIDDLE",
                textFormat=TextFormat(
                    fontFamily="Calibri",
                    fontSize=10,
                    bold=True,
                ),
            )
            # Format per cell (banyak), pakai batch
            # Optimasi: format range besar per baris
            _ranges_to_format = []
            for _row_idx in range(3, 3 + len(_pers_list)):
                # Format range W1 (kolom D sampai AU) per baris
                _ranges_to_format.append(f"D{_row_idx}:AU{_row_idx}")
                # Format range W2 (kolom AZ sampai CO) per baris
                _ranges_to_format.append(f"AZ{_row_idx}:CO{_row_idx}")
            
            for _r in _ranges_to_format:
                try:
                    format_cell_range(ws, _r, _fmt)
                except Exception:
                    continue
        
        except ImportError:
            print("[FORMAT WARN] gspread_formatting tidak terinstall")
        except Exception as _e:
            print(f"[FORMAT WARN] {_e}")
        
        return True, f"✅ {len(_updates)} cell di-update + format ({len(_pers_list)} personil)", len(_updates)
    
    except Exception as e:
        import traceback
        print(f"[ISI_LAPORAN_PWP ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0

# =========================================================================
# 📝 ISI LAPORAN SG — SERBA GRATIS (2 WEEK: 1-15 & 16-31)
# Target dari PERIODE_PPS (SGS01 & SGS02), Actual dari SALES_PPS.qty_sg
# =========================================================================
def isi_laporan_sg(bulan_int, tahun_int, sheet_name):
    """
    Isi kolom TARGET TOKO & ACTUAL di sheet SG.
    
    Struktur (2 WEEK):
    - W1 (tgl 1-15): Target D, Actual G-U (15 hari)
    - W2 (tgl 16-31): Target Y, Actual AB-AQ (16 hari)
    
    Target dari PERIODE_PPS: SGS01 (W1), SGS02 (W2)
    Actual dari SALES_PPS.qty_sg (per kasir per tanggal)
    """
    try:
        # === 1. Ambil data ===
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()
        _per_pps = st.session_state.get("periods_pps_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _pps.empty or _pers.empty:
            return False, "❌ Data PPS atau person_df kosong", 0
        
        # Normalisasi
        _pps.columns = _pps.columns.astype(str).str.strip().str.lower()
        _per_pps.columns = _per_pps.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        # === 2. Ambil target dari PERIODE_PPS (SGS01 & SGS02) ===
        _target_sgs01 = 0
        _target_sgs02 = 0
        
        if not _per_pps.empty and "period_id" in _per_pps.columns:
            _per_pps["_pid_clean"] = _per_pps["period_id"].astype(str).str.upper().str.strip()
            
            # SGS01 (W1)
            _sgs01 = _per_pps[_per_pps["_pid_clean"].str.startswith("SGS01", na=False)]
            if not _sgs01.empty and "target_total" in _sgs01.columns:
                _target_sgs01 = int(pd.to_numeric(_sgs01.iloc[0]["target_total"], errors="coerce") or 0)
            
            # SGS02 (W2)
            _sgs02 = _per_pps[_per_pps["_pid_clean"].str.startswith("SGS02", na=False)]
            if not _sgs02.empty and "target_total" in _sgs02.columns:
                _target_sgs02 = int(pd.to_numeric(_sgs02.iloc[0]["target_total"], errors="coerce") or 0)
        
        # === 3. Ambil personil by NIK ascending ===
        if "active" in _pers.columns:
            _pers = _pers[pd.to_numeric(_pers["active"], errors="coerce") == 1]
        
        _nik_col = None
        for _c in ["nik", "person_id"]:
            if _c in _pers.columns:
                _nik_col = _c
                break
        
        if _nik_col:
            _pers["_nik_sort"] = pd.to_numeric(_pers[_nik_col], errors="coerce").fillna(99999999)
            _pers = _pers.sort_values("_nik_sort", ascending=True)
        
        _pers["person_clean"] = _pers["person_name"].astype(str).str.strip().str.upper()
        _pers = _pers.drop_duplicates(subset=["person_clean"])
        _pers_list = _pers["person_clean"].tolist()
        
        if not _pers_list:
            return False, "❌ Tidak ada personil aktif", 0
        
        # === 4. Parse tanggal sales_pps ===
        if "updated_at" not in _pps.columns:
            return False, "❌ Kolom updated_at tidak ada", 0
        _pps["_dt"] = pd.to_datetime(_pps["updated_at"], errors="coerce")
        _pps = _pps.dropna(subset=["_dt"])
        
        # === 5. Buka worksheet ===
        ws = get_ws_laporan(sheet_name)
        if ws is None:
            return False, f"❌ Sheet {sheet_name} tidak ditemukan", 0
        
        # === 6. Config WEEK ===
        _week_config = [
            {
                "name": "W1",
                "target": _target_sgs01,
                "tanggal": list(range(1, 16)),   # 1-15
                "col_target": "D",
                "col_actual_start": "G",
                "col_actual_end": "U",
            },
            {
                "name": "W2",
                "target": _target_sgs02,
                "tanggal": list(range(16, 32)),  # 16-31
                "col_target": "Y",
                "col_actual_start": "AB",
                "col_actual_end": "AQ",
            },
        ]
        
        # === 7. Bangun batch update ===
        _updates = []
        _target_ranges = []
        _actual_ranges = []
        
        # Target Toko (W1 & W2)
        for _w in _week_config:
            _target_val = _w["target"]
            if _target_val > 0:
                _target_values = [[_target_val] for _ in range(len(_pers_list))]
                _range = f"{_w['col_target']}3:{_w['col_target']}{2 + len(_pers_list)}"
                _updates.append({
                    "range": _range,
                    "values": _target_values,
                })
                _target_ranges.append(_range)
        
        # Actual per personil per tanggal
        for _row_offset, _person in enumerate(_pers_list):
            _row_idx = 3 + _row_offset
            
            for _w in _week_config:
                _actual_values = []
                
                for _tgl in _w["tanggal"]:
                    _mask = (
                        (_pps["kasir_name"].astype(str).str.strip().str.upper() == _person) &
                        (_pps["_dt"].dt.day == _tgl) &
                        (_pps["_dt"].dt.month == bulan_int) &
                        (_pps["_dt"].dt.year == tahun_int)
                    )
                    
                    if _mask.any() and "qty_sg" in _pps.columns:
                        _qty = int(pd.to_numeric(_pps.loc[_mask, "qty_sg"], errors="coerce").fillna(0).sum())
                    else:
                        _qty = 0
                    
                    _actual_values.append(_qty if _qty > 0 else "")
                
                _actual_range = f"{_w['col_actual_start']}{_row_idx}:{_w['col_actual_end']}{_row_idx}"
                _updates.append({
                    "range": _actual_range,
                    "values": [_actual_values],
                })
                _actual_ranges.append(_actual_range)
        
        # === 8. Batch update ===
        if _updates:
            ws.batch_update(_updates, value_input_option="USER_ENTERED")
        
        # === 9. Format center ===
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, HorizontalAlignment,
                format_cell_range,
            )
            _fmt = CellFormat(
                horizontalAlignment=HorizontalAlignment.CENTER,
                verticalAlignment="MIDDLE",
                textFormat=TextFormat(
                    fontFamily="Calibri",
                    fontSize=10,
                    bold=True,
                ),
            )
            for _range in _target_ranges + _actual_ranges:
                try:
                    format_cell_range(ws, _range, _fmt)
                except Exception:
                    continue
        except ImportError:
            print("[FORMAT WARN] gspread_formatting tidak terinstall")
        except Exception as _e:
            print(f"[FORMAT WARN] {_e}")
        
        _info = f"Target W1={_target_sgs01}, W2={_target_sgs02}"
        return True, f"✅ {len(_updates)} range di-update ({len(_pers_list)} personil). {_info}", len(_updates)
    
    except Exception as e:
        import traceback
        print(f"[ISI_LAPORAN_SG ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0

# =========================================================================
# 📝 ISI LAPORAN SUEGER — SYARAT & REDEEM (Selang-Seling per Tanggal)
# W1 (1-15): mulai kolom D, W2 (16-30): mulai kolom AZ
# =========================================================================
def isi_laporan_sueger(bulan_int, tahun_int, sheet_name):
    """
    Isi kolom Struk Syarat & Struk Redemp di sheet Sueger.
    
    Struktur (sama seperti PWP):
    - W1 (tgl 1-15): Kolom D, G, J, M, ... (syarat) & E, H, K, N, ... (redemp)
    - W2 (tgl 16-30): Kolom AZ, BC, BF, ... (syarat) & BA, BD, BG, ... (redemp)
    
    Data source: SALES_PPS (syarat_sueger & redeem_sueger)
    Rumus % Redempt dibiarkan.
    """
    try:
        # === 1. Ambil data ===
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _pps.empty or _pers.empty:
            return False, "❌ Data PPS atau person_df kosong", 0
        
        # Normalisasi
        _pps.columns = _pps.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        # === 2. Parse tanggal ===
        if "updated_at" not in _pps.columns:
            return False, "❌ Kolom updated_at tidak ada", 0
        _pps["_dt"] = pd.to_datetime(_pps["updated_at"], errors="coerce")
        _pps = _pps.dropna(subset=["_dt"])
        
        # === 3. Ambil personil by NIK ascending ===
        if "active" in _pers.columns:
            _pers = _pers[pd.to_numeric(_pers["active"], errors="coerce") == 1]
        
        _nik_col = None
        for _c in ["nik", "person_id"]:
            if _c in _pers.columns:
                _nik_col = _c
                break
        
        if _nik_col:
            _pers["_nik_sort"] = pd.to_numeric(_pers[_nik_col], errors="coerce").fillna(99999999)
            _pers = _pers.sort_values("_nik_sort", ascending=True)
        
        _pers["person_clean"] = _pers["person_name"].astype(str).str.strip().str.upper()
        _pers = _pers.drop_duplicates(subset=["person_clean"])
        _pers_list = _pers["person_clean"].tolist()
        
        if not _pers_list:
            return False, "❌ Tidak ada personil aktif", 0
        
        # === 4. Buka worksheet ===
        ws = get_ws_laporan(sheet_name)
        if ws is None:
            return False, f"❌ Sheet {sheet_name} tidak ditemukan", 0
        
        # === 5. Helper kolom ===
        def _col_from_index(idx):
            """Konversi index 0-based ke huruf Excel."""
            result = ""
            idx_1 = idx + 1
            while idx_1 > 0:
                idx_1, rem = divmod(idx_1 - 1, 26)
                result = chr(65 + rem) + result
            return result
        
        def _index_from_col(col):
            """Konversi huruf kolom ke index 0-based."""
            result = 0
            for c in col:
                result = result * 26 + (ord(c.upper()) - 64)
            return result - 1
        
        # === 6. Config kolom per tanggal ===
        # W1: mulai kolom D, tgl 1-15
        _w1_start_idx = _index_from_col("D")  # = 3
        _w1_tanggal = list(range(1, 16))       # 1-15
        
        # W2: mulai kolom AZ, tgl 16-30
        _w2_start_idx = _index_from_col("AZ")  # = 51
        _w2_tanggal = list(range(16, 31))      # 16-30
        
        # Mapping: [(tgl, col_syarat, col_redemp)]
        _col_map = []
        
        for i, tgl in enumerate(_w1_tanggal):
            _syr_idx = _w1_start_idx + i * 3
            _red_idx = _syr_idx + 1
            _col_map.append({
                "tanggal": tgl,
                "syarat": _col_from_index(_syr_idx),
                "redemp": _col_from_index(_red_idx),
            })
        
        for i, tgl in enumerate(_w2_tanggal):
            _syr_idx = _w2_start_idx + i * 3
            _red_idx = _syr_idx + 1
            _col_map.append({
                "tanggal": tgl,
                "syarat": _col_from_index(_syr_idx),
                "redemp": _col_from_index(_red_idx),
            })
        
        # === 7. Bangun batch update ===
        _updates = []
        _formatted_ranges = []
        
        for _row_offset, _person in enumerate(_pers_list):
            _row_idx = 3 + _row_offset
            
            for _cm in _col_map:
                _tgl = _cm["tanggal"]
                
                # Filter data
                _mask = (
                    (_pps["kasir_name"].astype(str).str.strip().str.upper() == _person) &
                    (_pps["_dt"].dt.day == _tgl) &
                    (_pps["_dt"].dt.month == bulan_int) &
                    (_pps["_dt"].dt.year == tahun_int)
                )
                
                # Nilai syarat
                if _mask.any() and "syarat_sueger" in _pps.columns:
                    _syarat = int(pd.to_numeric(_pps.loc[_mask, "syarat_sueger"], errors="coerce").fillna(0).sum())
                else:
                    _syarat = 0
                
                # Nilai redemp
                if _mask.any() and "redeem_sueger" in _pps.columns:
                    _redemp = int(pd.to_numeric(_pps.loc[_mask, "redeem_sueger"], errors="coerce").fillna(0).sum())
                else:
                    _redemp = 0
                
                # Update syarat
                _updates.append({
                    "range": f"{_cm['syarat']}{_row_idx}",
                    "values": [[_syarat if _syarat > 0 else ""]],
                })
                _formatted_ranges.append(f"{_cm['syarat']}{_row_idx}")
                
                # Update redemp
                _updates.append({
                    "range": f"{_cm['redemp']}{_row_idx}",
                    "values": [[_redemp if _redemp > 0 else ""]],
                })
                _formatted_ranges.append(f"{_cm['redemp']}{_row_idx}")
        
        # === 8. Batch update value ===
        if _updates:
            ws.batch_update(_updates, value_input_option="USER_ENTERED")
        
        # === 9. Set format center ===
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, HorizontalAlignment,
                format_cell_range,
            )
            _fmt = CellFormat(
                horizontalAlignment=HorizontalAlignment.CENTER,
                verticalAlignment="MIDDLE",
                textFormat=TextFormat(
                    fontFamily="Calibri",
                    fontSize=10,
                    bold=True,
                ),
            )
            
            # Format range besar per baris
            _ranges_to_format = []
            for _row_idx in range(3, 3 + len(_pers_list)):
                # W1: kolom D sampai AV
                _ranges_to_format.append(f"D{_row_idx}:AV{_row_idx}")
                # W2: kolom AZ sampai CR (atau lebih, tergantung panjang)
                _ranges_to_format.append(f"AZ{_row_idx}:CR{_row_idx}")
            
            for _r in _ranges_to_format:
                try:
                    format_cell_range(ws, _r, _fmt)
                except Exception:
                    continue
        
        except ImportError:
            print("[FORMAT WARN] gspread_formatting tidak terinstall")
        except Exception as _e:
            print(f"[FORMAT WARN] {_e}")
        
        return True, f"✅ {len(_updates)} cell di-update ({len(_pers_list)} personil)", len(_updates)
    
    except Exception as e:
        import traceback
        print(f"[ISI_LAPORAN_SUEGER ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0