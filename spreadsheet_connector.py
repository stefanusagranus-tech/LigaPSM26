"""
spreadsheet_connector.py (VERSI FINAL v4)
==========================================
Konektor multi-spreadsheet untuk LigaPSM.
"""
import gspread
import streamlit as st
import pandas as pd
import threading
import time
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials


# =========================================================================
# 🔒 LOCK GLOBAL
# =========================================================================
_AUDIT_LOCK = threading.Lock()
_LAPORAN_LOCK = threading.Lock()


# =========================================================================
# 🔌 KONEKSI DASAR
# =========================================================================
@st.cache_resource(show_spinner=False)
def _get_client():
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
    try:
        client = _get_client()
        if client is None:
            return None
        sh = client.open_by_key(st.secrets["spreadsheet_id_audit"])
        try:
            return sh.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            return sh.add_worksheet(title=sheet_name, rows=1000, cols=10)
    except Exception as e:
        print(f"[GET_WS_AUDIT ERROR] {sheet_name}: {e}")
        return None


@st.cache_resource(show_spinner=False)
def get_ws_laporan(sheet_name):
    try:
        client = _get_client()
        if client is None:
            return None
        sh = client.open_by_key(st.secrets["spreadsheet_id_laporan"])
        try:
            return sh.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            return sh.add_worksheet(title=sheet_name, rows=1000, cols=40)
    except Exception as e:
        print(f"[GET_WS_LAPORAN ERROR] {sheet_name}: {e}")
        return None


# =========================================================================
# 📝 LOG ACTIVITY
# =========================================================================
_HEADER_ACTIVITY = ["timestamp", "username", "role", "action", "detail", "session_id"]


def append_logs_to_sheet(logs_list):
    if not logs_list:
        return 0, "Queue kosong"
    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_LOG")
            if ws is None:
                return 0, "❌ Gagal akses sheet ACTIVITY_LOG"
            try:
                _first = ws.row_values(1)
                if not _first or _first[0].lower() != "timestamp":
                    ws.insert_row(_HEADER_ACTIVITY, index=1)
            except Exception:
                pass
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
    try:
        ws = get_ws_audit("ACTIVITY_LOG")
        if ws is None:
            return pd.DataFrame(columns=_HEADER_ACTIVITY)
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return pd.DataFrame(columns=_HEADER_ACTIVITY)
        return pd.DataFrame(all_values[1:], columns=all_values[0])
    except Exception as e:
        print(f"[READ_ACTIVITY ERROR] {e}")
        return pd.DataFrame(columns=_HEADER_ACTIVITY)


# =========================================================================
# 💾 BACKUP
# =========================================================================
def _safe_stringify(value):
    try:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (ValueError, TypeError):
            pass
        if isinstance(value, float):
            if value == float('inf') or value == float('-inf'):
                return ""
            if value != value:
                return ""
        _str = str(value).strip()
        if _str.lower() in ["nan", "nat", "none", "inf", "-inf", "infinity", "-infinity", "<na>"]:
            return ""
        return _str
    except Exception:
        return ""


def backup_to_audit_sheet(state_getter):
    _result = {"success": [], "failed": [], "total": 0}
    _backup_map = [
        ("_BACKUP_SALES_ITEM", "sales_item_df"),
        ("_BACKUP_SALES_PERSON", "sales_person_df"),
        ("_BACKUP_SALES_PPS", "sales_pps_df"),
        ("_BACKUP_PERIODE", "periods_df"),
        ("_BACKUP_PERIODE_PPS", "periods_pps_df"),
        ("_BACKUP_MASTER_ITEM", "items_df"),
        ("_BACKUP_MASTER_PERSONIL", "person_df"),
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
                    _df_clean = _df.copy()
                    _df_clean.columns = _df_clean.columns.astype(str)
                    _df_clean = _df_clean.map(_safe_stringify)
                    _df_clean = _df_clean.reset_index(drop=True)
                    ws = get_ws_audit(_sheet_name)
                    if ws is None:
                        _result["failed"].append(f"❌ {_sheet_name}: worksheet gagal")
                        continue
                    ws.clear()
                    header = _df_clean.columns.tolist()
                    ws.append_row(header, value_input_option="USER_ENTERED")
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
# 📝 ISI LAPORAN PSM — DINAMIS BY BULAN
# =========================================================================
def isi_laporan_psm(bulan_int, tahun_int, sheet_name):
    """
    Isi kolom TARGET TOKO & ACTUAL di sheet PSM.
    Dinamis filter periode PSM by bulan & tahun.
    """
    try:
        _sp = st.session_state.get("sales_person_df", pd.DataFrame()).copy()
        _si = st.session_state.get("sales_item_df", pd.DataFrame()).copy()
        _per = st.session_state.get("periods_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _sp.empty or _pers.empty:
            return False, "❌ Data sales_person atau person_df kosong", 0
        
        _sp.columns = _sp.columns.astype(str).str.strip().str.lower()
        _si.columns = _si.columns.astype(str).str.strip().str.lower()
        _per.columns = _per.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        # Filter periode PSM by bulan
        _psm_bulan_ini = pd.DataFrame()
        if not _per.empty and "period_id" in _per.columns and "start_date" in _per.columns:
            _per["_start_dt"] = pd.to_datetime(_per["start_date"], errors="coerce")
            _per = _per.dropna(subset=["_start_dt"])
            
            _per_psm_only = _per[
                ~_per["period_id"].astype(str).str.upper().str.contains(
                    "PWP|SGR|SGS|CBN|PPS", na=False, regex=True
                )
            ]
            
            _psm_bulan_ini = _per_psm_only[
                (_per_psm_only["_start_dt"].dt.month == bulan_int) &
                (_per_psm_only["_start_dt"].dt.year == tahun_int)
            ].sort_values("_start_dt", ascending=True).reset_index(drop=True)
        
        if _psm_bulan_ini.empty:
            return False, f"❌ Tidak ada periode PSM untuk bulan {bulan_int}/{tahun_int}", 0
        
        # Target map dari SALES_ITEM
        _target_map = {}
        if not _si.empty and "target_qty" in _si.columns and "period_id" in _si.columns:
            _si["target_qty"] = pd.to_numeric(_si["target_qty"], errors="coerce").fillna(0)
            _si["_pid_clean"] = _si["period_id"].astype(str).str.strip()
            _grp = _si.groupby("_pid_clean")["target_qty"].sum()
            _target_map = _grp.to_dict()
        
        # Personil by NIK ascending
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
        
        if "updated_at" not in _sp.columns:
            return False, "❌ Kolom updated_at tidak ada", 0
        _sp["_dt"] = pd.to_datetime(_sp["updated_at"], errors="coerce")
        _sp = _sp.dropna(subset=["_dt"])
        
        ws = get_ws_laporan(sheet_name)
        if ws is None:
            return False, f"❌ Sheet {sheet_name} tidak ditemukan", 0
        
        _week_cols = [
            {"col_target": "D",  "col_act_start": "G",  "col_act_end": "M"},
            {"col_target": "Q",  "col_act_start": "T",  "col_act_end": "AA"},
            {"col_target": "AE", "col_act_start": "AH", "col_act_end": "AO"},
            {"col_target": "AS", "col_act_start": "AV", "col_act_end": "BC"},
        ]
        
        _week_config = []
        for _i, _periode in enumerate(_psm_bulan_ini.iterrows()):
            if _i >= len(_week_cols):
                break
            
            _pid = str(_periode[1].get("period_id", "")).strip()
            _start = _periode[1]["_start_dt"].date()
            _end = pd.to_datetime(_periode[1].get("end_date"), errors="coerce")
            if pd.notna(_end):
                _end = _end.date()
                _jhk = (_end - _start).days + 1
                _tanggal = [_start + timedelta(days=d) for d in range(_jhk)]
            else:
                _tanggal = []
            
            _cols = _week_cols[_i]
            _week_config.append({
                "period_id": _pid,
                "tanggal": _tanggal,
                "col_target": _cols["col_target"],
                "col_actual_start": _cols["col_act_start"],
                "col_actual_end": _cols["col_act_end"],
            })
        
        _updates = []
        _target_ranges = []
        
        for _w in _week_config:
            _target_val = int(_target_map.get(_w["period_id"], 0))
            if _target_val > 0:
                _target_values = [[_target_val] for _ in range(len(_pers_list))]
                _range = f"{_w['col_target']}3:{_w['col_target']}{2 + len(_pers_list)}"
                _updates.append({"range": _range, "values": _target_values})
                _target_ranges.append(_range)
        
        _actual_ranges = []
        for _row_offset, _person in enumerate(_pers_list):
            _row_idx = 3 + _row_offset
            
            for _w in _week_config:
                _actual_values = []
                for _tgl in _w["tanggal"]:
                    _mask = (
                        (_sp["person_name"].astype(str).str.upper() == _person) &
                        (_sp["_dt"].dt.date == _tgl)
                    )
                    if _mask.any():
                        _qty = int(pd.to_numeric(_sp.loc[_mask, "actual_qty"], errors="coerce").fillna(0).sum())
                    else:
                        _qty = 0
                    _actual_values.append(_qty if _qty > 0 else "")
                
                _actual_range = f"{_w['col_actual_start']}{_row_idx}:{_w['col_actual_end']}{_row_idx}"
                _updates.append({"range": _actual_range, "values": [_actual_values]})
                _actual_ranges.append(_actual_range)
        
        if _updates:
            ws.batch_update(_updates, value_input_option="USER_ENTERED")
        
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, HorizontalAlignment,
                format_cell_range,
            )
            _fmt = CellFormat(
                horizontalAlignment=HorizontalAlignment.CENTER,
                verticalAlignment="MIDDLE",
                textFormat=TextFormat(fontFamily="Calibri", fontSize=10, bold=True),
            )
            for _range in _target_ranges + _actual_ranges:
                try:
                    format_cell_range(ws, _range, _fmt)
                except Exception:
                    continue
        except ImportError:
            pass
        
        _info = f"W1-W{len(_week_config)}: {', '.join([w['period_id'] for w in _week_config])}"
        return True, f"✅ {len(_updates)} range di-update + format ({len(_pers_list)} personil). {_info}", len(_updates)
    
    except Exception as e:
        import traceback
        print(f"[ISI_LAPORAN_PSM ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0


# =========================================================================
# 🛠️ HELPER: ISI LAPORAN PPS (PWP / SUEGER) — KOLOM SELANG-SELING 3
# =========================================================================
def _isi_laporan_pps_generic(bulan_int, tahun_int, sheet_name, 
                              prefix, kolom_syarat, kolom_redeem, 
                              label_syarat="Syarat", label_redeem="Redeem"):
    """
    Helper generic untuk isi laporan PWP & Sueger.
    Struktur kolom selang-seling 3 (syarat, redeem, %) per tanggal.
    """
    try:
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _pps.empty or _pers.empty:
            return False, "❌ Data PPS atau person_df kosong", 0
        
        _pps.columns = _pps.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        if "updated_at" not in _pps.columns:
            return False, "❌ Kolom updated_at tidak ada", 0
        _pps["_dt"] = pd.to_datetime(_pps["updated_at"], errors="coerce")
        _pps = _pps.dropna(subset=["_dt"])
        
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
        
        ws = get_ws_laporan(sheet_name)
        if ws is None:
            return False, f"❌ Sheet {sheet_name} tidak ditemukan", 0
        
        def _col_from_index(idx):
            result = ""
            idx_1 = idx + 1
            while idx_1 > 0:
                idx_1, rem = divmod(idx_1 - 1, 26)
                result = chr(65 + rem) + result
            return result
        
        def _index_from_col(col):
            result = 0
            for c in col:
                result = result * 26 + (ord(c.upper()) - 64)
            return result - 1
        
        _w1_start_idx = _index_from_col("D")
        _w1_tanggal = list(range(1, 16))
        _w2_start_idx = _index_from_col("AZ")
        _w2_tanggal = list(range(16, 31))
        
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
        
        _updates = []
        for _row_offset, _person in enumerate(_pers_list):
            _row_idx = 3 + _row_offset
            for _cm in _col_map:
                _tgl = _cm["tanggal"]
                _mask = (
                    (_pps["kasir_name"].astype(str).str.strip().str.upper() == _person) &
                    (_pps["_dt"].dt.day == _tgl) &
                    (_pps["_dt"].dt.month == bulan_int) &
                    (_pps["_dt"].dt.year == tahun_int)
                )
                _syarat = 0
                if _mask.any() and kolom_syarat in _pps.columns:
                    _syarat = int(pd.to_numeric(_pps.loc[_mask, kolom_syarat], errors="coerce").fillna(0).sum())
                _redeem = 0
                if _mask.any() and kolom_redeem in _pps.columns:
                    _redeem = int(pd.to_numeric(_pps.loc[_mask, kolom_redeem], errors="coerce").fillna(0).sum())
                _updates.append({
                    "range": f"{_cm['syarat']}{_row_idx}",
                    "values": [[_syarat if _syarat > 0 else ""]],
                })
                _updates.append({
                    "range": f"{_cm['redemp']}{_row_idx}",
                    "values": [[_redeem if _redeem > 0 else ""]],
                })
        
        if _updates:
            ws.batch_update(_updates, value_input_option="USER_ENTERED")
        
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, HorizontalAlignment,
                format_cell_range,
            )
            _fmt = CellFormat(
                horizontalAlignment=HorizontalAlignment.CENTER,
                verticalAlignment="MIDDLE",
                textFormat=TextFormat(fontFamily="Calibri", fontSize=10, bold=True),
            )
            _ranges_to_format = []
            for _row_idx in range(3, 3 + len(_pers_list)):
                _ranges_to_format.append(f"D{_row_idx}:AU{_row_idx}")
                _ranges_to_format.append(f"AZ{_row_idx}:CO{_row_idx}")
            for _r in _ranges_to_format:
                try:
                    format_cell_range(ws, _r, _fmt)
                except Exception:
                    continue
        except ImportError:
            pass
        
        return True, f"✅ {len(_updates)} cell di-update ({len(_pers_list)} personil)", len(_updates)
    
    except Exception as e:
        import traceback
        print(f"[ISI_LAPORAN_{prefix} ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0
    

# =========================================================================
# 📝 ISI LAPORAN PWP — WRAPPER
# =========================================================================
def isi_laporan_pwp(bulan_int, tahun_int, sheet_name):
    """Isi kolom Syarat & Qty di sheet PWP."""
    return _isi_laporan_pps_generic(
        bulan_int=bulan_int,
        tahun_int=tahun_int,
        sheet_name=sheet_name,
        prefix="PWP",
        kolom_syarat="syarat_pwp",
        kolom_redeem="qty_pwp",
        label_syarat="Syarat",
        label_redeem="Qty",
    )


# =========================================================================
# 📝 ISI LAPORAN SUEGER — WRAPPER
# =========================================================================
def isi_laporan_sueger(bulan_int, tahun_int, sheet_name):
    """Isi kolom Syarat & Redeem di sheet Sueger."""
    return _isi_laporan_pps_generic(
        bulan_int=bulan_int,
        tahun_int=tahun_int,
        sheet_name=sheet_name,
        prefix="SGR",
        kolom_syarat="syarat_sueger",
        kolom_redeem="redeem_sueger",
        label_syarat="Syarat",
        label_redeem="Redeem",
    )


# =========================================================================
# 📝 ISI LAPORAN SG — DINAMIS BY BULAN
# =========================================================================
def isi_laporan_sg(bulan_int, tahun_int, sheet_name):
    """
    Isi kolom TARGET TOKO & ACTUAL di sheet SG.
    Dinamis target by bulan.
    """
    try:
        _pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()
        _per_pps = st.session_state.get("periods_pps_df", pd.DataFrame()).copy()
        _pers = st.session_state.get("person_df", pd.DataFrame()).copy()
        
        if _pps.empty or _pers.empty:
            return False, "❌ Data PPS atau person_df kosong", 0
        
        _pps.columns = _pps.columns.astype(str).str.strip().str.lower()
        _per_pps.columns = _per_pps.columns.astype(str).str.strip().str.lower()
        _pers.columns = _pers.columns.astype(str).str.strip().str.lower()
        
        # Filter periode SGS by bulan
        _sgs_bulan_ini = pd.DataFrame()
        if not _per_pps.empty and "period_id" in _per_pps.columns and "start_date" in _per_pps.columns:
            _per_pps["_start_dt"] = pd.to_datetime(_per_pps["start_date"], errors="coerce")
            _per_pps["_end_dt"] = pd.to_datetime(_per_pps["end_date"], errors="coerce")
            _per_pps = _per_pps.dropna(subset=["_start_dt", "_end_dt"])
            
            _sgs_bulan_ini = _per_pps[
                _per_pps["period_id"].astype(str).str.upper().str.startswith("SGS", na=False) &
                (_per_pps["_start_dt"].dt.month == bulan_int) &
                (_per_pps["_start_dt"].dt.year == tahun_int)
            ].sort_values("_start_dt", ascending=True).reset_index(drop=True)
        
        if _sgs_bulan_ini.empty:
            return False, f"❌ Tidak ada periode SGS untuk bulan {bulan_int}/{tahun_int}", 0
        
        # Target W1 & W2
        _target_sgs_w1 = 0
        _target_sgs_w2 = 0
        
        if len(_sgs_bulan_ini) >= 1:
            _target_sgs_w1 = int(pd.to_numeric(_sgs_bulan_ini.iloc[0].get("target_total", 0), errors="coerce") or 0)
        if len(_sgs_bulan_ini) >= 2:
            _target_sgs_w2 = int(pd.to_numeric(_sgs_bulan_ini.iloc[1].get("target_total", 0), errors="coerce") or 0)
        
        _id_w1 = str(_sgs_bulan_ini.iloc[0]["period_id"]) if len(_sgs_bulan_ini) >= 1 else "-"
        _id_w2 = str(_sgs_bulan_ini.iloc[1]["period_id"]) if len(_sgs_bulan_ini) >= 2 else "-"
        
        # Personil by NIK
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
        
        if "updated_at" not in _pps.columns:
            return False, "❌ Kolom updated_at tidak ada", 0
        _pps["_dt"] = pd.to_datetime(_pps["updated_at"], errors="coerce")
        _pps = _pps.dropna(subset=["_dt"])
        
        ws = get_ws_laporan(sheet_name)
        if ws is None:
            return False, f"❌ Sheet {sheet_name} tidak ditemukan", 0
        
        _week_config = [
            {
                "name": "W1",
                "target": _target_sgs_w1,
                "tanggal": list(range(1, 16)),
                "col_target": "D",
                "col_actual_start": "G",
                "col_actual_end": "U",
            },
            {
                "name": "W2",
                "target": _target_sgs_w2,
                "tanggal": list(range(16, 32)),
                "col_target": "Y",
                "col_actual_start": "AB",
                "col_actual_end": "AQ",
            },
        ]
        
        _updates = []
        _target_ranges = []
        _actual_ranges = []
        
        for _w in _week_config:
            _target_val = _w["target"]
            if _target_val > 0:
                _target_values = [[_target_val] for _ in range(len(_pers_list))]
                _range = f"{_w['col_target']}3:{_w['col_target']}{2 + len(_pers_list)}"
                _updates.append({"range": _range, "values": _target_values})
                _target_ranges.append(_range)
        
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
                _updates.append({"range": _actual_range, "values": [_actual_values]})
                _actual_ranges.append(_actual_range)
        
        if _updates:
            ws.batch_update(_updates, value_input_option="USER_ENTERED")
        
        try:
            from gspread_formatting import (
                CellFormat, TextFormat, HorizontalAlignment,
                format_cell_range,
            )
            _fmt = CellFormat(
                horizontalAlignment=HorizontalAlignment.CENTER,
                verticalAlignment="MIDDLE",
                textFormat=TextFormat(fontFamily="Calibri", fontSize=10, bold=True),
            )
            for _range in _target_ranges + _actual_ranges:
                try:
                    format_cell_range(ws, _range, _fmt)
                except Exception:
                    continue
        except ImportError:
            pass
        
        _info = f"W1 ({_id_w1}) = {_target_sgs_w1} | W2 ({_id_w2}) = {_target_sgs_w2}"
        return True, f"✅ {len(_updates)} range di-update ({len(_pers_list)} personil). {_info}", len(_updates)
    
    except Exception as e:
        import traceback
        print(f"[ISI_LAPORAN_SG ERROR] {traceback.format_exc()}")
        return False, f"❌ Gagal: {str(e)[:150]}", 0
    

# =========================================================================
# 📊 TULIS LAPORAN BULANAN KE SPREADSHEET LAPORAN
# =========================================================================
def write_laporan_bulanan(sheet_name, rows_matrix):
    """Tulis matrix laporan ke Spreadsheet Laporan."""
    try:
        with _LAPORAN_LOCK:
            ws = get_ws_laporan(sheet_name)
            if ws is None:
                return False, f"❌ Gagal akses sheet {sheet_name}"
            
            ws.clear()
            
            if rows_matrix:
                ws.update(
                    values=rows_matrix,
                    range_name="A1",
                    value_input_option="USER_ENTERED"
                )
            
            return True, f"✅ Laporan {sheet_name} tersimpan ({len(rows_matrix)} baris)"
    
    except Exception as e:
        _err = str(e)
        if "Unable to parse range" in _err:
            try:
                ws.clear()
                for _row_idx, _row in enumerate(rows_matrix, start=1):
                    ws.insert_row(_row, index=_row_idx, value_input_option="USER_ENTERED")
                return True, f"✅ Laporan {sheet_name} tersimpan ({len(rows_matrix)} baris) [fallback]"
            except Exception as e2:
                return False, f"❌ Gagal (fallback): {str(e2)[:150]}"
        
        return False, f"❌ Gagal: {_err[:150]}"


# =========================================================================
# 🛠️ HELPER: AMBIL PERIODE & HITUNG TARGET
# =========================================================================
from datetime import timedelta as _td


def _get_weeks_from_periode(periode_df, bulan_int, tahun_int, filter_prefix=None):
    """Ambil daftar periode untuk bulan tertentu."""
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
    
    _df = _df[(_df["_start"].dt.month == bulan_int) & (_df["_start"].dt.year == tahun_int)]
    
    if filter_prefix:
        _df = _df[_df["period_id"].astype(str).str.upper().str.startswith(filter_prefix, na=False)]
    
    _df = _df.sort_values("_start")
    
    for _, _row in _df.iterrows():
        _pid = str(_row.get("period_id", "")).strip()
        _start = _row["_start"].date()
        _end = _row["_end"].date()
        _jhk = (_end - _start).days + 1
        
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
    """Hitung target pertoko & pershift."""
    if toko <= 0 or jhk <= 0:
        return 0, 0
    _pertoko = toko / jhk
    _pershift = _pertoko / 2
    return _pertoko, _pershift


def _format_angka(val, desimal=2):
    """Format angka: 0 → '-', selain itu sesuai."""
    if val is None:
        return "-"
    if isinstance(val, (int, float)):
        if val == 0:
            return "-"
        if desimal == 0:
            return str(int(val))
        return f"{val:.{desimal}f}"
    return str(val)


# =========================================================================
# 🏗️ BANGUN MATRIX: SHEET PSM
# =========================================================================
def _bangun_sheet_psm(sales_person_df, periode_df, sales_item_df, person_df, bulan_int, tahun_int):
    """Bangun matrix laporan PSM (per hari, breakdown WEEK)."""
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
    
    _weeks = _get_weeks_from_periode(periode_df, bulan_int, tahun_int)
    
    if not _weeks:
        return _sheet_name, None
    
    _target_map = {}
    if sales_item_df is not None and not sales_item_df.empty:
        _si = sales_item_df.copy()
        _si.columns = _si.columns.astype(str).str.strip().str.lower()
        if "target_qty" in _si.columns and "period_id" in _si.columns:
            _si["target_qty"] = pd.to_numeric(_si["target_qty"], errors="coerce").fillna(0)
            _grp = _si.groupby(_si["period_id"].astype(str).str.strip())["target_qty"].sum()
            _target_map = _grp.to_dict()
    
    for _w in _weeks:
        _w["target"] = int(_target_map.get(_w["period_id"], 0))
    
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
    
    _row1 = ["", "Toko", "C383/KARANG SATRIA"]
    for _idx, _w in enumerate(_weeks):
        _row1.append(f"PSM WEEK {_idx+1}")
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
                _mask = (_sp["person_name"].astype(str).str.upper() == _nama) & (_sp["_dt"].dt.date == _tgl)
                if _mask.any():
                    _qty = int(pd.to_numeric(_sp.loc[_mask, "actual_qty"], errors="coerce").fillna(0).sum())
                else:
                    _qty = 0
                _row.append(_qty if _qty > 0 else "-")
                _week_total += _qty
            
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


# =========================================================================
# 🏗️ BANGUN MATRIX: SHEET PPS (PWP / SG / SUEGER)
# =========================================================================
def _bangun_sheet_pps(sales_pps_df, periode_pps_df, person_df, bulan_int, tahun_int,
                     prefix, sheet_suffix, kolom_a, kolom_b, label_a, label_b):
    """Bangun matrix laporan PPS (PWP, SG, Sueger)."""
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
    
    _weeks = _get_weeks_from_periode(periode_pps_df, bulan_int, tahun_int, filter_prefix=prefix)
    
    if not _weeks:
        return _sheet_name, None
    
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


# =========================================================================
# 📊 GENERATE LAPORAN PSM (PUBLIC)
# =========================================================================
def generate_laporan_psm(bulan_int, tahun_int):
    """Generate laporan PSM bulanan."""
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
    

# =========================================================================
# 📊 GENERATE LAPORAN PWP (PUBLIC)
# =========================================================================
def generate_laporan_pwp(bulan_int, tahun_int):
    """Generate laporan PWP bulanan."""
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


# =========================================================================
# 📊 GENERATE LAPORAN SG (PUBLIC)
# =========================================================================
def generate_laporan_sg(bulan_int, tahun_int):
    """Generate laporan SG bulanan."""
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


# =========================================================================
# 📊 GENERATE LAPORAN SUEGER (PUBLIC)
# =========================================================================
def generate_laporan_sueger(bulan_int, tahun_int):
    """Generate laporan Sueger bulanan."""
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


# =========================================================================
# 📊 GENERATE SEMUA LAPORAN (PUBLIC)
# =========================================================================
def generate_semua_laporan(bulan_int, tahun_int):
    """Generate 4 laporan sekaligus: PSM, PWP, SG, Sueger."""
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
# 🧪 DEBUG PANEL
# =========================================================================
def render_debug_panel():
    """Tampilkan panel debug di sidebar."""
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
                ws = get_ws_audit("ACTIVITY_LOG")
                if ws is None:
                    st.sidebar.error("Gagal akses ACTIVITY_LOG")
                else:
                    all_values = ws.get_all_values()
                    _today_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
                    _today_count = sum(1 for row in all_values[1:] if len(row) > 0 and row[0].startswith(_today_str))
                    ws_hb = get_ws_audit("ACTIVITY_HEARTBEAT")
                    _hb_count = 0
                    if ws_hb is not None:
                        _hb_values = ws_hb.get_all_values()
                        _hb_count = max(0, len(_hb_values) - 1)
                    st.sidebar.success(f"📊 Log hari ini: **{_today_count}** baris")
                    st.sidebar.info(f"👥 User aktif: **{_hb_count}**")
                    st.sidebar.caption(f"📅 Tanggal: {_today_str}")
                    _est_read = _today_count * 2 + _hb_count * 20
                    _est_write = _today_count + _hb_count * 20
                    st.sidebar.markdown("---")
                    st.sidebar.markdown("**📈 Estimasi API Call:**")
                    st.sidebar.write(f"• Read: ~**{_est_read}**")
                    st.sidebar.write(f"• Write: ~**{_est_write}**")
                    st.sidebar.caption("💡 Limit: 300 read + 300 write per menit")
            except Exception as e:
                st.sidebar.error(f"❌ Error: {str(e)[:100]}")


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
        try:
            _id = st.secrets.get("spreadsheet_id", "")
            _sh = _client.open_by_key(_id)
            st.sidebar.success(f"✅ Data: `{_sh.title[:25]}`")
            with st.sidebar.expander(f"📋 {len(_sh.worksheets())} sheet"):
                for ws in _sh.worksheets():
                    st.write(f"• {ws.title}")
        except Exception as e:
            st.sidebar.error(f"❌ Data: {str(e)[:60]}")
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
    """Test backup 1 sheet saja."""
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
# 💓 HEARTBEAT
# =========================================================================
_HEARTBEAT_HEADER = ["username", "session_id", "role", "last_heartbeat", "status"]


def write_heartbeat_to_sheet(username, session_id, role, status="ONLINE"):
    """Update/tambah baris heartbeat user."""
    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_HEARTBEAT")
            if ws is None:
                return False, "❌ Gagal akses ACTIVITY_HEARTBEAT"

            try:
                first_row = ws.row_values(1)
                if not first_row or first_row[0].lower() != "username":
                    ws.insert_row(_HEARTBEAT_HEADER, index=1)
            except Exception:
                pass

            now_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
            all_values = ws.get_all_values()
            if len(all_values) < 1:
                ws.append_row([username, session_id, role, now_str, status],
                              value_input_option="USER_ENTERED")
                return True, f"✅ Heartbeat ditambahkan: {username}"

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
                ws.update(f"A{row_to_update}:E{row_to_update}",
                          [[username, session_id, role, now_str, status]],
                          value_input_option="USER_ENTERED")
                return True, f"✅ Heartbeat diupdate: {username}"
            else:
                ws.append_row([username, session_id, role, now_str, status],
                              value_input_option="USER_ENTERED")
                return True, f"✅ Heartbeat ditambahkan: {username}"

    except Exception as e:
        print(f"[WRITE_HEARTBEAT ERROR] {e}")
        return False, f"❌ Gagal: {str(e)[:150]}"


def remove_heartbeat_from_sheet(username):
    """Hapus baris heartbeat user."""
    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_HEARTBEAT")
            if ws is None:
                return False, "❌ Gagal akses ACTIVITY_HEARTBEAT"

            all_values = ws.get_all_values()
            if len(all_values) < 2:
                return False, "⚠️ Sheet kosong / user tidak ada"

            header = all_values[0]
            col_username = 0
            for idx, h in enumerate(header):
                if h.lower().strip() == "username":
                    col_username = idx
                    break

            for row_idx, row in enumerate(all_values[1:], start=2):
                if len(row) > col_username and row[col_username].strip().lower() == username.strip().lower():
                    ws.delete_rows(row_idx)
                    return True, f"✅ Heartbeat dihapus: {username}"

            return False, f"ℹ️ User {username} tidak ada di heartbeat"

    except Exception as e:
        print(f"[REMOVE_HEARTBEAT ERROR] {e}")
        return False, f"❌ Gagal: {str(e)[:150]}"


def get_stale_heartbeats(threshold_minutes=15):
    """Ambil daftar user yang heartbeat-nya sudah lama."""
    try:
        if threshold_minutes is None or threshold_minutes < 0.5:
            threshold_minutes = 15
            print(f"[WARN] Threshold tidak valid, dipaksa 15 menit")

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

        for _req in ["username", "session_id", "last_heartbeat"]:
            if _req not in col_idx:
                print(f"[ERROR] Header '{_req}' tidak ada. Header: {header}")
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

                if not _username or not _last_hb_str:
                    continue

                if _username.upper() in ["DEBUG_TEST", "DEBUG_HEARTBEAT", "SYSTEM"]:
                    continue

                _last_hb = datetime.strptime(
                    _last_hb_str, "%d/%m/%Y %H:%M:%S"
                ).replace(tzinfo=ZoneInfo("Asia/Jakarta"))
                _selisih_menit = (now - _last_hb).total_seconds() / 60

                if _selisih_menit > threshold_minutes:
                    stale_users.append({
                        "username": _username,
                        "session_id": _session,
                        "role": _role,
                        "last_heartbeat": _last_hb_str,
                        "selisih_menit": round(_selisih_menit, 1),
                    })
            except Exception as e_row:
                print(f"[SKIP ROW] {e_row}")
                continue

        stale_users.sort(key=lambda x: x["selisih_menit"], reverse=True)
        return stale_users

    except Exception as e:
        print(f"[GET_STALE_HEARTBEAT ERROR] {e}")
        return []


def clear_all_heartbeat():
    """Hapus semua baris heartbeat."""
    try:
        with _AUDIT_LOCK:
            ws = get_ws_audit("ACTIVITY_HEARTBEAT")
            if ws is None:
                return False, "❌ Gagal akses sheet"

            all_values = ws.get_all_values()
            if len(all_values) <= 1:
                return True, "Sheet sudah kosong"

            ws.delete_rows(2, len(all_values))
            return True, f"✅ {len(all_values) - 1} baris heartbeat dihapus"

    except Exception as e:
        return False, f"❌ Gagal: {str(e)[:150]}"