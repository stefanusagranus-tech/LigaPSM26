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
        # PSM & PPS
        ("_BACKUP_SALES_ITEM", "sales_item_df"),
        ("_BACKUP_SALES_PERSON", "sales_person_df"),
        ("_BACKUP_SALES_PPS", "sales_pps_df"),
        ("_BACKUP_PERIODE", "periods_df"),
        ("_BACKUP_PERIODE_PPS", "periods_pps_df"),
        ("_BACKUP_MASTER_ITEM", "items_df"),
        ("_BACKUP_MASTER_PERSONIL", "person_df"),
        # Daily Performance (BARU!)
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

                    # Bersihkan NaN/inf dulu
                    _df_clean = _df.copy()

                    # Ganti NaN jadi string kosong
                    _df_clean = _df_clean.fillna("")

                    # Untuk kolom numerik, ganti inf/-inf jadi 0 atau ""
                    for _col in _df_clean.columns:
                        try:
                            # Coba konversi ke numeric
                            _numeric = pd.to_numeric(_df_clean[_col], errors="coerce")
                            # Cari nilai inf
                            _inf_mask = _numeric.apply(lambda x: x != x or x in [float('inf'), float('-inf')] if isinstance(x, (int, float)) else False)
                            # Ganti inf dengan string kosong
                            _df_clean.loc[_inf_mask, _col] = ""
                        except Exception:
                            pass

                    # Konversi semua ke string dan bersihkan
                    _df_clean = _df_clean.astype(str).replace({
                        "nan": "",
                        "NaN": "",
                        "inf": "",
                        "-inf": "",
                        "Infinity": "",
                        "-Infinity": "",
                        "None": "",
                    })
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

        st.markdown("---")
        st.markdown("### 💓 Test Heartbeat")

        if st.button("💓 Test Write Heartbeat", key="btn_debug_hb_write", use_container_width=True):
            from datetime import datetime
            from zoneinfo import ZoneInfo
            _now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
            _ok, _msg = write_heartbeat_to_sheet("DEBUG_HEARTBEAT", "debug-session", "system", "ONLINE")
            if _ok:
                st.sidebar.success(_msg)
            else:
                st.sidebar.error(_msg)

        if st.button("📖 Lihat Semua Heartbeat", key="btn_debug_hb_read", use_container_width=True):
            ws = get_ws_audit("ACTIVITY_HEARTBEAT")
            if ws is None:
                st.sidebar.error("Gagal akses sheet")
            else:
                all_values = ws.get_all_values()
                if len(all_values) <= 1:
                    st.sidebar.info("📭 Heartbeat kosong")
                else:
                    st.sidebar.success(f"✅ {len(all_values) - 1} user aktif")
                    with st.sidebar.expander("Preview"):
                        for row in all_values[:5]:
                            st.write(row)

        if st.button("🧹 Clear All Heartbeat", key="btn_debug_hb_clear", use_container_width=True):
            _ok, _msg = clear_all_heartbeat()
            if _ok:
                st.sidebar.success(_msg)
            else:
                st.sidebar.error(_msg)
        
        st.markdown("---")
        st.markdown("### 🚨 Force Trigger")

        if st.button("🚨 Force Check Stale NOW", key="btn_force_stale", 
                    use_container_width=True, type="primary"):
            # Reset flag biar check langsung jalan
            st.session_state["last_stale_check"] = 0
            st.sidebar.info("✅ Flag direset! Refresh halaman (F5) sekarang.")
            
            # Trigger manual (khusus test)
            try:
                from zoneinfo import ZoneInfo
                from datetime import datetime as _dt
                _now = _dt.now(ZoneInfo("Asia/Jakarta"))
                
                # Ambil stale
                _stale = get_stale_heartbeats(threshold_minutes=0.5)
                
                st.sidebar.write(f"📊 Ditemukan **{len(_stale)}** user stale:")
                for _u in _stale:
                    st.sidebar.write(f"• {_u['username']} — idle {_u['selisih_menit']} menit")
                
                # Catat AUTO_LOGOUT untuk tiap user
                if _stale:
                    if "pending_activity_logs" not in st.session_state:
                        st.session_state["pending_activity_logs"] = []
                    
                    for _user in _stale:
                        _waktu = _dt.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
                        _log = {
                            "timestamp": _waktu,
                            "username": str(_user["username"]),
                            "role": str(_user["role"]),
                            "action": "AUTO_LOGOUT",
                            "detail": f"[FORCE] Auto-logout setelah {_user['selisih_menit']} menit idle",
                            "session_id": str(_user["session_id"]),
                        }
                        st.session_state["pending_activity_logs"].insert(0, _log)
                        
                        # Hapus dari heartbeat
                        _ok_d, _msg_d = remove_heartbeat_from_sheet(_user["username"])
                        st.sidebar.write(f"  🗑️ {_msg_d}")
                    
                    # Flush log
                    _c, _m = append_logs_to_sheet(st.session_state["pending_activity_logs"])
                    st.session_state["pending_activity_logs"] = []
                    
                    st.sidebar.success(f"✅ {_c} AUTO_LOGOUT dicatat & di-flush!")
                    st.sidebar.info("👉 Cek `ACTIVITY_LOG` & `ACTIVITY_HEARTBEAT`")
                else:
                    st.sidebar.warning("⚠️ Tidak ada user stale")
            
            except Exception as e:
                st.sidebar.error(f"❌ Error: {str(e)[:100]}")

        st.markdown("---")
        st.markdown("### 💾 Test Backup")

        if st.button("💾 Test Backup 1 Sheet", key="btn_debug_backup_one", use_container_width=True):
            try:
                def _getter(key):
                    return st.session_state.get(key, pd.DataFrame())
                
                _result = backup_to_audit_sheet(_getter)
                
                if _result["success"]:
                    st.sidebar.success(f"✅ Backup OK: {len(_result['success'])} sheet")
                    with st.sidebar.expander("Detail"):
                        st.write(f"Total baris: {_result['total']:,}")
                        st.write("**Sukses:**")
                        for _s in _result["success"]:
                            st.write(f"  ✅ {_s}")
                        if _result["failed"]:
                            st.write("**Gagal:**")
                            for _f in _result["failed"]:
                                st.write(f"  {_f}")
                else:
                    st.sidebar.error("❌ Semua sheet gagal di-backup")
                    with st.sidebar.expander("Detail"):
                        for _f in _result["failed"]:
                            st.write(f"  {_f}")
            except Exception as e:
                st.sidebar.error(f"❌ Error: {str(e)[:100]}")

        st.markdown("---")
        st.markdown("### 📊 Test Laporan")

        if st.button("📊 Test Generate Laporan (Bulan Ini)", key="btn_debug_lap", use_container_width=True):
            from datetime import datetime
            from zoneinfo import ZoneInfo
            
            _now = datetime.now(ZoneInfo("Asia/Jakarta"))
            _bulan_int = _now.month
            _tahun_int = _now.year
            _bulan_str = _now.strftime("%B").upper()
            
            _ok, _msg, _n = generate_laporan_bulanan_psm(_bulan_int, _tahun_int, _bulan_str)
            
            if _ok:
                st.sidebar.success(_msg)
                st.sidebar.info(f"👥 Personil: {_n}")
                st.sidebar.write(f"👉 Cek LIGAPSM-LAPORAN → {_bulan_str} {_tahun_int}")
            else:
                st.sidebar.error(_msg)        


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