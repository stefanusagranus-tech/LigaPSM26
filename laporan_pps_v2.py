"""
Generator Laporan WhatsApp PPS v2.1
====================================
Format: Per-shift dengan 5 program
Target dinamis (best estimate) + fallback flat
Summary bold

Version: 2.1
Changelog:
- Fix: target dinamis fallback ke flat kalau sisa target <= 0
- Fix: summary bold semua angka
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
    """Format integer dengan koma."""
    try:
        return f"{int(v):,}"
    except Exception:
        return "0"


# =========================================================
# HELPER: AMBIL PERIODE BY KODE PREFIX
# =========================================================
def _get_periode_by_kode(periods_df, kode_prefix, tanggal):
    """
    Cari periode aktif berdasarkan kode prefix & tanggal.
    
    Args:
        periods_df: DataFrame periode
        kode_prefix: 'P' PSM, 'PWPS' PWP, 'SGS' SG, 'SGR' Sueger
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
def _hitung_target_psm_bulan(sales_item_df, period_id):
    """Hitung SUM(target_qty) untuk periode PSM."""
    try:
        if sales_item_df is None or sales_item_df.empty:
            return 0
        
        df = sales_item_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        df = df[df["period_id"].astype(str).str.strip() == str(period_id).strip()]
        
        if df.empty or "target_qty" not in df.columns:
            return 0
        
        df["target_qty"] = pd.to_numeric(df["target_qty"], errors="coerce").fillna(0)
        return int(df["target_qty"].sum())
    except Exception as e:
        print(f"[_hitung_target_psm_bulan ERROR] {e}")
        return 0


# =========================================================
# HELPER: TARGET PPS (PWP / SG)
# =========================================================
def _get_target_pps_bulan(periods_pps_df, period_id):
    """Ambil target_total dari periods_pps_df by period_id."""
    try:
        if periods_pps_df is None or periods_pps_df.empty:
            return 0
        
        df = periods_pps_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        df = df[df["period_id"].astype(str).str.strip() == str(period_id).strip()]
        
        if df.empty or "target_total" not in df.columns:
            return 0
        
        return int(pd.to_numeric(df["target_total"].iloc[0], errors="coerce") or 0)
    except Exception as e:
        print(f"[_get_target_pps_bulan ERROR] {e}")
        return 0


# =========================================================
# HELPER: AKTUAL KUMULATIF
# =========================================================
def _get_aktual_kumulatif(df_source, periode, kolom_qty, tanggal, filter_cols=None):
    """
    Hitung aktual kumulatif dari awal periode sampai tanggal.
    
    Args:
        df_source: DataFrame source
        periode: dict {start_date, end_date}
        kolom_qty: nama kolom qty
        tanggal: date (batas akhir)
        filter_cols: dict {kolom: value} untuk filter tambahan
    """
    if df_source is None or df_source.empty or periode is None:
        return 0
    
    try:
        _df = df_source.copy()
        _df.columns = _df.columns.astype(str).str.strip().str.lower()
        _df["_tgl"] = pd.to_datetime(_df["updated_at"], errors="coerce").dt.date
        
        _df = _df[
            (_df["_tgl"] >= periode["start_date"]) &
            (_df["_tgl"] <= tanggal)
        ]
        
        if filter_cols:
            for _col, _val in filter_cols.items():
                if _col in _df.columns:
                    _df = _df[_df[_col].astype(str) == str(_val)]
        
        if kolom_qty in _df.columns:
            return int(pd.to_numeric(_df[kolom_qty], errors="coerce").fillna(0).sum())
    except Exception as e:
        print(f"[_get_aktual_kumulatif ERROR] {e}")
    
    return 0


# =========================================================
# HELPER: TARGET DINAMIS (BEST ESTIMATE + FALLBACK FLAT)
# =========================================================
def _hitung_target_dinamis(total_target, aktual_kumulatif, jhk, hari_ke):
    """
    Target dinamis dengan fallback ke target flat.
    
    Logika:
    - sisa_target > 0  → Target = sisa_target / sisa_hari  (DINAMIS)
    - sisa_target <= 0 → Target = total_target / jhk        (FLAT)
    
    Ini mencegah target minus ketika aktual sudah over/pas.
    """
    sisa_target = total_target - aktual_kumulatif
    sisa_hari = jhk - hari_ke
    
    if sisa_hari <= 0:
        return 0
    
    # Kalau sisa target <= 0 (over/pas) → fallback ke target flat
    if sisa_target <= 0:
        return int(total_target / jhk) if jhk > 0 else 0
    
    # Kalau belum achieved → target dinamis
    return int(sisa_target / sisa_hari)


# =========================================================
# HELPER: TARGET PER SHIFT (40/40/20)
# =========================================================
def _target_per_shift(target_harian):
    """Bagi target harian jadi 3 shift (40/40/20)."""
    return {
        "Shift 1": int(target_harian * 0.40),
        "Shift 2": int(target_harian * 0.40),
        "Shift 3": int(target_harian * 0.20),
    }
# =========================================================
# GENERATOR UTAMA
# =========================================================
def generate_laporan_pps_v2(
    tanggal,
    sales_pps_df,
    sales_personil_df,
    sales_item_df,
    periods_df,
    periods_pps_df,
    person_df=None,
):
    """
    Generate laporan WhatsApp PPS v2.1.
    
    Returns:
        str: Text laporan siap copy
    """
    
    # =========================================================
    # 1. SETUP TANGGAL & PERIODE
    # =========================================================
    tanggal_str = tanggal.strftime("%d-%m-%Y")
    
    # Periode PSM (P01, S01, S04)
    psm_periode = _get_periode_by_kode(periods_df, "P", tanggal)
    if not psm_periode:
        psm_periode = _get_periode_by_kode(periods_df, "S", tanggal)
    
    # Periode PWP (PWPS)
    pwp_periode = _get_periode_by_kode(periods_pps_df, "PWPS", tanggal)
    if not pwp_periode:
        pwp_periode = _get_periode_by_kode(periods_pps_df, "PWP", tanggal)
    
    # Periode SG (SGS)
    sg_periode = _get_periode_by_kode(periods_pps_df, "SGS", tanggal)
    
    # Periode Sueger (SGR)
    sgr_periode = _get_periode_by_kode(periods_pps_df, "SGR", tanggal)
    
    # Label periode (pakai PSM)
    periode_label = psm_periode["label"] if psm_periode else "-"
    jhk = psm_periode["jhk"] if psm_periode else 30
    hari_ke = 1
    if psm_periode:
        hari_ke = (tanggal - psm_periode["start_date"]).days + 1
    sisa_hari = max(0, jhk - hari_ke)
    
    # =========================================================
    # 2. HITUNG TARGET DINAMIS
    # =========================================================
    
    # --- PSM ---
    psm_target_bulan = 0
    psm_target_harian = 0
    if psm_periode:
        psm_target_bulan = _hitung_target_psm_bulan(
            sales_item_df, psm_periode["period_id"]
        )
        psm_hari_ke = (tanggal - psm_periode["start_date"]).days + 1
        aktual_psm_kum = _get_aktual_kumulatif(
            sales_personil_df,
            psm_periode,
            "actual_qty",
            tanggal,
            filter_cols={"period_id": psm_periode["period_id"]},
        )
        psm_target_harian = _hitung_target_dinamis(
            psm_target_bulan, aktual_psm_kum, psm_periode["jhk"], psm_hari_ke
        )
    
    # --- PWP ---
    pwp_target_bulan = 0
    pwp_target_harian = 0
    pwp_jhk = jhk
    if pwp_periode:
        pwp_target_bulan = _get_target_pps_bulan(
            periods_pps_df, pwp_periode["period_id"]
        )
        pwp_jhk = pwp_periode["jhk"]
        pwp_hari_ke = (tanggal - pwp_periode["start_date"]).days + 1
        aktual_pwp_kum = _get_aktual_kumulatif(
            sales_pps_df, pwp_periode, "qty_pwp", tanggal
        )
        pwp_target_harian = _hitung_target_dinamis(
            pwp_target_bulan, aktual_pwp_kum, pwp_jhk, pwp_hari_ke
        )
    
    # --- SG ---
    sg_target_bulan = 0
    sg_target_harian = 0
    if sg_periode:
        sg_target_bulan = _get_target_pps_bulan(
            periods_pps_df, sg_periode["period_id"]
        )
        sg_hari_ke = (tanggal - sg_periode["start_date"]).days + 1
        aktual_sg_kum = _get_aktual_kumulatif(
            sales_pps_df, sg_periode, "qty_sg", tanggal
        )
        sg_target_harian = _hitung_target_dinamis(
            sg_target_bulan, aktual_sg_kum, sg_periode["jhk"], sg_hari_ke
        )
    
    # --- Target per shift (40/40/20) ---
    target_psm_shift = _target_per_shift(psm_target_harian)
    target_pwp_shift = _target_per_shift(pwp_target_harian)
    target_sg_shift = _target_per_shift(sg_target_harian)
    
    # =========================================================
    # 3. FILTER DATA HARI INI
    # =========================================================
    # PPS
    pps_today = pd.DataFrame()
    if sales_pps_df is not None and not sales_pps_df.empty:
        df = sales_pps_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        df["_tgl"] = pd.to_datetime(df["updated_at"], errors="coerce").dt.date
        pps_today = df[df["_tgl"] == tanggal]
    
    # PSM
    psm_today = pd.DataFrame()
    if sales_personil_df is not None and not sales_personil_df.empty:
        df = sales_personil_df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()
        df["_tgl"] = pd.to_datetime(df["updated_at"], errors="coerce").dt.date
        psm_today = df[df["_tgl"] == tanggal]
        if psm_periode:
            psm_today = psm_today[
                psm_today["period_id"].astype(str) == psm_periode["period_id"]
            ]
    
    # =========================================================
    # 4. BUILD HEADER
    # =========================================================
    text = (
        f"🌟 *REKAP LAPORAN HARIAN PPS* 🌟\n"
        f"📅 Tanggal: {tanggal_str}\n"
        f"📦 *Periode*: {periode_label}\n"
        f"⏱️ *Hari ke-{hari_ke} dari {jhk}* | Sisa {sisa_hari} hari\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    # =========================================================
    # 5. REPORT PSM
    # =========================================================
    total_psm_today = 0
    if not psm_today.empty and "actual_qty" in psm_today.columns:
        total_psm_today = int(pd.to_numeric(psm_today["actual_qty"], errors="coerce").fillna(0).sum())
    
    ach_psm = _fmt_pct(total_psm_today, psm_target_harian)
    
    text += (
        f"📦 *REPORT PSM*\n"
        f"   🎯 Target Harian: {psm_target_harian} pcs\n"
        f"   \n"
        f"   📌 *List item terjual:*\n"
    )
    
    if not psm_today.empty and "item_name" in psm_today.columns:
        psm_today["actual_qty"] = pd.to_numeric(psm_today["actual_qty"], errors="coerce").fillna(0)
        item_grouped = (
            psm_today.groupby("item_name")["actual_qty"]
            .sum()
            .sort_values(ascending=False)
        )
        for item, qty in item_grouped.items():
            if qty > 0:
                text += f"      • {item} = {int(qty)}\n"
    else:
        text += "      • (Tidak ada penjualan)\n"
    
    text += (
        f"   \n"
        f"   ═══════════════════════════════\n"
        f"   ✅ *TOTAL PENJUALAN: {total_psm_today} pcs*\n"
        f"   🎯 Achievement: *{ach_psm}*\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    # =========================================================
    # 6. PROGRAM PPS PER SHIFT
    # =========================================================
    text += "⚡ *PROGRAM PPS - PER SHIFT*\n\n"
    
    shift_order = ["Shift 1", "Shift 2", "Shift 3"]
    
    if pps_today.empty:
        text += "   _(Belum ada data input hari ini)_\n"
    else:
        shifts_available = pps_today["shift_personil"].dropna().unique().tolist()
        shifts_sorted = [s for s in shift_order if s in shifts_available]
        
        for idx, shift in enumerate(shifts_sorted):
            shift_df = pps_today[pps_today["shift_personil"] == shift]
            
            if shift_df.empty:
                continue
            
            staff_names = ", ".join(sorted(set(shift_df["staff_name"].dropna().astype(str))))
            kasir_names = " & ".join(sorted(set(shift_df["kasir_name"].dropna().astype(str))))
            
            text += (
                f"   📌 *{shift.upper()}*\n"
                f"   (Staf: {staff_names} | Kasir: {kasir_names})\n"
            )
            
            syarat_pwp = int(shift_df["syarat_pwp"].sum()) if "syarat_pwp" in shift_df.columns else 0
            redeem_pwp = int(shift_df["redeem_pwp"].sum()) if "redeem_pwp" in shift_df.columns else 0
            qty_pwp = int(shift_df["qty_pwp"].sum()) if "qty_pwp" in shift_df.columns else 0
            ach_pwp = _fmt_pct(redeem_pwp, syarat_pwp)
            ach_pwp_qty = _fmt_pct(qty_pwp, target_pwp_shift.get(shift, 0))
            
            qty_sg = int(shift_df["qty_sg"].sum()) if "qty_sg" in shift_df.columns else 0
            ach_sg = _fmt_pct(qty_sg, target_sg_shift.get(shift, 0))
            
            syarat_sgr = int(shift_df["syarat_sueger"].sum()) if "syarat_sueger" in shift_df.columns else 0
            redeem_sgr = int(shift_df["redeem_sueger"].sum()) if "redeem_sueger" in shift_df.columns else 0
            ach_sgr = _fmt_pct(redeem_sgr, syarat_sgr)
            
            qty_ceban = int(shift_df["cemilan_ceban"].sum()) if "cemilan_ceban" in shift_df.columns else 0
            
            text += (
                f"   1️⃣ PWP ➔ Syarat/Redeem: {syarat_pwp}/{redeem_pwp} ({ach_pwp})\n"
                f"   2️⃣ PWP Qty ➔ Target/Qty: 🎯 {target_pwp_shift.get(shift, 0)} / 📦 {qty_pwp} ({ach_pwp_qty})\n"
                f"   3️⃣ SG ➔ Target/Qty: 🎯 {target_sg_shift.get(shift, 0)} / 📦 {qty_sg} ({ach_sg})\n"
                f"   4️⃣ Sueger ➔ Syarat/Redeem: {syarat_sgr}/{redeem_sgr} ({ach_sgr})\n"
                f"   5️⃣ Ceban ➔ Qty: {qty_ceban}\n"
            )
            
            if idx < len(shifts_sorted) - 1:
                text += "   \n   ─────────────────────────────\n   \n"
    
    text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    # =========================================================
    # 7. SUMMARY (BOLD)
    # =========================================================
    text += f"📊 *SUMMARY PENJUALAN TANGGAL {tanggal_str}*\n\n"
    
    # PWP
    total_syarat_pwp = 0
    total_redeem_pwp = 0
    total_qty_pwp = 0
    if not pps_today.empty:
        total_syarat_pwp = int(pps_today["syarat_pwp"].sum()) if "syarat_pwp" in pps_today.columns else 0
        total_redeem_pwp = int(pps_today["redeem_pwp"].sum()) if "redeem_pwp" in pps_today.columns else 0
        total_qty_pwp = int(pps_today["qty_pwp"].sum()) if "qty_pwp" in pps_today.columns else 0
    
    total_ach_pwp = _fmt_pct(total_redeem_pwp, total_syarat_pwp)
    total_ach_pwp_qty = _fmt_pct(total_qty_pwp, pwp_target_harian)
    
    text += (
        f"   ⚡ *PWP*\n"
        f"      • *Syarat/Redeem: {total_syarat_pwp}/{total_redeem_pwp} ({total_ach_pwp})*\n"
        f"      • *PWP Qty: 🎯 {pwp_target_harian} / 📦 {total_qty_pwp} ({total_ach_pwp_qty})*\n"
        f"   \n"
    )
    
    # SG
    total_qty_sg = 0
    if not pps_today.empty and "qty_sg" in pps_today.columns:
        total_qty_sg = int(pps_today["qty_sg"].sum())
    total_ach_sg = _fmt_pct(total_qty_sg, sg_target_harian)
    
    text += (
        f"   🎁 *SG*\n"
        f"      • *SG Qty: 🎯 {sg_target_harian} / 📦 {total_qty_sg} ({total_ach_sg})*\n"
        f"   \n"
    )
    
    # Sueger
    total_syarat_sgr = 0
    total_redeem_sgr = 0
    if not pps_today.empty:
        total_syarat_sgr = int(pps_today["syarat_sueger"].sum()) if "syarat_sueger" in pps_today.columns else 0
        total_redeem_sgr = int(pps_today["redeem_sueger"].sum()) if "redeem_sueger" in pps_today.columns else 0
    total_ach_sgr = _fmt_pct(total_redeem_sgr, total_syarat_sgr)
    
    text += (
        f"   💧 *Sueger*\n"
        f"      • *Syarat/Redeem: {total_syarat_sgr}/{total_redeem_sgr} ({total_ach_sgr})*\n"
        f"   \n"
    )
    
    # Ceban
    total_ceban = 0
    if not pps_today.empty and "cemilan_ceban" in pps_today.columns:
        total_ceban = int(pps_today["cemilan_ceban"].sum())
    
    text += (
        f"   🥤 *Ceban*\n"
        f"      • *Ceban Qty: {total_ceban}*\n"
    )
    
    text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    # =========================================================
    # 8. UPDATE TARGET BESOK (CONDITIONAL)
    # =========================================================
    if not pps_today.empty:
        shift_1_ada = "Shift 1" in pps_today["shift_personil"].unique().tolist()
        shift_2_ada = "Shift 2" in pps_today["shift_personil"].unique().tolist()
        shift_3_ada = "Shift 3" in pps_today["shift_personil"].unique().tolist()
        tiga_shift_lengkap = shift_1_ada and shift_2_ada and shift_3_ada
    else:
        shift_1_ada = shift_2_ada = shift_3_ada = False
        tiga_shift_lengkap = False
    
    if tiga_shift_lengkap:
        # Hitung aktual kumulatif sampai hari ini (udah include data hari ini)
        aktual_psm_kum = _get_aktual_kumulatif(
            sales_personil_df, psm_periode, "actual_qty", tanggal,
            filter_cols={"period_id": psm_periode["period_id"]} if psm_periode else None
        ) if psm_periode else 0
        
        aktual_pwp_kum = _get_aktual_kumulatif(
            sales_pps_df, pwp_periode, "qty_pwp", tanggal
        ) if pwp_periode else 0
        
        aktual_sg_kum = _get_aktual_kumulatif(
            sales_pps_df, sg_periode, "qty_sg", tanggal
        ) if sg_periode else 0
        
        # Target besok (dinamis dengan fallback)
        besok_hari_ke = hari_ke + 1
        target_psm_besok = _hitung_target_dinamis(
            psm_target_bulan, aktual_psm_kum, jhk, besok_hari_ke
        )
        target_pwp_besok = _hitung_target_dinamis(
            pwp_target_bulan, aktual_pwp_kum, pwp_jhk, besok_hari_ke if pwp_periode else hari_ke + 1
        )
        target_sg_besok = _hitung_target_dinamis(
            sg_target_bulan, aktual_sg_kum, sg_periode["jhk"] if sg_periode else jhk, besok_hari_ke
        )
        
        besok = tanggal + timedelta(days=1)
        besok_str = besok.strftime("%d-%m-%Y")
        
        text += (
            f"🎯 *UPDATE TARGET BESOK ({besok_str})*\n"
            f"   \n"
            f"   📦 PSM:  🎯 *{target_psm_besok} pcs*\n"
            f"   ⚡ PWP:  🎯 *{target_pwp_besok} pcs*\n"
            f"   🎁 SG:   🎯 *{target_sg_besok} pcs*\n"
            f"\n"
        )
    else:
        n_shift = sum([shift_1_ada, shift_2_ada, shift_3_ada])
        text += (
            f"🎯 *UPDATE TARGET BESOK*\n"
            f"   ⚠️ _(Akan muncul kalau 3 shift sudah input)_\n"
            f"   📊 Progress: {n_shift}/3 shift\n"
            f"\n"
        )
    
    # =========================================================
    # 9. FOOTER
    # =========================================================
    text += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *Status: Program PPS Berjalan Lancar & Termonitor*"
    )
    
    return text
