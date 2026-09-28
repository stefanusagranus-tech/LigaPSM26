"""
Generator Laporan WhatsApp PPS v2
==================================
Format: Per-shift dengan 5 program
Target dinamis (best estimate)

Version: 2.0
"""

import pandas as pd
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# HELPER: FORMAT ANGKA
# =========================================================
def _fmt_pct(actual, target):
    """Format achievement 1 desimal."""
    if target <= 0:
        return "0.0%"
    return f"{(actual / target * 100):.1f}%"


def _fmt_int(v):
    """Format integer."""
    try:
        return f"{int(v):,}"
    except Exception:
        return "0"


# =========================================================
# HELPER: AMBIL PERIODE
# =========================================================
def _get_periode_by_kode(periods_df, kode_prefix, tanggal):
    """
    Cari periode yang aktif berdasarkan kode prefix & tanggal.
    
    Args:
        periods_df: DataFrame periode
        kode_prefix: 'P' untuk PSM, 'PWPS' untuk PWP, 'SGS' untuk SG, 'SGR' untuk Sueger
        tanggal: date
    
    Returns:
        dict atau None: {period_id, start_date, end_date, jhk, label}
    """
    try:
        if periods_df is None or periods_df.empty:
            return None
        
        df = periods_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        # Filter by prefix kode
        df = df[df["period_id"].astype(str).str.upper().str.startswith(kode_prefix.upper(), na=False)]
        
        if df.empty:
            return None
        
        # Parse tanggal
        df["start_dt"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
        df["end_dt"] = pd.to_datetime(df["end_date"], errors="coerce").dt.date
        
        # Filter yang aktif di tanggal
        df = df[(df["start_dt"] <= tanggal) & (df["end_dt"] >= tanggal)]
        
        if df.empty:
            return None
        
        row = df.iloc[0]
        start = row["start_dt"]
        end = row["end_dt"]
        jhk = (end - start).days + 1
        
        return {
            "period_id": str(row["period_id"]),
            "start_date": start,
            "end_date": end,
            "jhk": jhk,
            "label": str(row.get("period_name", row["period_id"])),
        }
    except Exception as e:
        print(f"[_get_periode_by_kode ERROR] {e}")
        return None


# =========================================================
# HELPER: TARGET PSM
# =========================================================
def _hitung_target_psm_harian(sales_item_df, period_id, jhk):
    """
    Target PSM harian = SUM(target_qty) / JHK
    """
    try:
        if sales_item_df is None or sales_item_df.empty:
            return 0, 0
        
        df = sales_item_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        # Filter periode
        df = df[df["period_id"].astype(str).str.strip() == str(period_id).strip()]
        
        if df.empty:
            return 0, 0
        
        # Sum target_qty
        if "target_qty" not in df.columns:
            return 0, 0
        
        df["target_qty"] = pd.to_numeric(df["target_qty"], errors="coerce").fillna(0)
        total_target = int(df["target_qty"].sum())
        
        # Target harian
        target_harian = int(total_target / jhk) if jhk > 0 else 0
        
        return total_target, target_harian
    except Exception as e:
        print(f"[_hitung_target_psm_harian ERROR] {e}")
        return 0, 0


# =========================================================
# HELPER: TARGET PPS (PWP / SG)
# =========================================================
def _hitung_target_pps_harian(periods_pps_df, kode_prefix, tanggal):
    """
    Target PPS harian = target_total / JHK
    """
    try:
        if periods_pps_df is None or periods_pps_df.empty:
            return 0, 0, None
        
        df = periods_pps_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        # Filter by prefix
        df = df[df["period_id"].astype(str).str.upper().str.startswith(kode_prefix.upper(), na=False)]
        
        if df.empty:
            return 0, 0, None
        
        # Parse tanggal
        df["start_dt"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
        df["end_dt"] = pd.to_datetime(df["end_date"], errors="coerce").dt.date
        
        # Filter yang aktif
        df = df[(df["start_dt"] <= tanggal) & (df["end_dt"] >= tanggal)]
        
        if df.empty:
            return 0, 0, None
        
        row = df.iloc[0]
        start = row["start_dt"]
        end = row["end_dt"]
        jhk = (end - start).days + 1
        
        target_total = int(pd.to_numeric(row.get("target_total", 0), errors="coerce") or 0)
        target_harian = int(target_total / jhk) if jhk > 0 else 0
        
        return target_total, target_harian, {
            "period_id": str(row["period_id"]),
            "jhk": jhk,
            "start_date": start,
            "end_date": end,
            "label": str(row.get("period_name", row["period_id"])),
        }
    except Exception as e:
        print(f"[_hitung_target_pps_harian ERROR] {e}")
        return 0, 0, None
