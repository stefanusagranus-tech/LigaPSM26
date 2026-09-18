import time
import random
from datetime import date, datetime, timedelta
import re
import math
import os
import io
import base64
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import streamlit as st
import streamlit.components.v1 as components
import textwrap
import streamlit as st
st.write("Streamlit version:", st.__version__)


# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="PSM Toko - Sales Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

SPREADSHEET_ID = "1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk"

# =========================================================
# 2. INISIALISASI KONEKSI GOOGLE SHEETS & FUNGSI DATABASE
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)


# Menggunakan cache dengan TTL 300 detik (5 menit) untuk mencegah Quota Limit
@st.cache_data(ttl=300)
def load_database():
    """Membaca data sheet secara bertahap sesuai modul PSM, PPS, dan Store Performance."""
    try:
        # 1. Modul PSM & Master Data Umum
        periods_df = conn.read(worksheet="PERIODE")
        items_df = conn.read(worksheet="MASTER_ITEM")
        person_df = conn.read(worksheet="MASTER_PERSONIL")
        sales_item_df = conn.read(worksheet="SALES_ITEM")
        sales_person_df = conn.read(worksheet="SALES_PERSONIL")

        # 2. Modul PPS
        periods_pps_df = conn.read(worksheet="PERIODE_PPS")
        sales_pps_df = conn.read(worksheet="SALES_PPS")

        # 3. Modul Store Performance
        periods_store_df = conn.read(worksheet="PERIODE_STOREPERFORMANCE")
        sales_store_df = conn.read(worksheet="SALES_STOREPERFORMANCE")

        # Pembersihan nama kolom menjadi string bersih dan huruf kecil
        all_dfs = [
            periods_df,
            items_df,
            person_df,
            sales_item_df,
            sales_person_df,
            periods_pps_df,
            sales_pps_df,
            periods_store_df,
            sales_store_df,
        ]
        for df in all_dfs:
            if not df.empty:
                df.columns = df.columns.astype(str).str.strip().str.lower()

        # Normalisasi tipe data period_id
        for df in all_dfs:
            if not df.empty and "period_id" in df.columns:
                df["period_id"] = df["period_id"].astype(str).str.strip()

        # Normalisasi tipe data item_id
        for df in [items_df, sales_item_df, sales_person_df]:
            if not df.empty and "item_id" in df.columns:
                df["item_id"] = df["item_id"].astype(str).str.strip()

        # Normalisasi nama personil
        for df in [person_df, sales_person_df, sales_pps_df, sales_store_df]:
            for col in ["person_name", "staff_name", "kasir_name"]:
                if not df.empty and col in df.columns:
                    df[col] = df[col].astype(str).str.strip().str.upper()
                    df[col] = df[col].str.replace(r"\s+", " ", regex=True)

        return (
            periods_df,
            periods_pps_df,
            periods_store_df,
            items_df,
            person_df,
            sales_item_df,
            sales_person_df,
            sales_pps_df,
            sales_store_df,
        )
    except Exception as e:
        st.error(f"Gagal membaca Google Sheets: {e}")
        return tuple([pd.DataFrame() for _ in range(9)])


def sync_periode_pps_from_sales():
    """Mengakumulasi data transaksi harian dari SALES_PPS ke PERIODE_PPS secara otomatis

    berdasarkan rentang tanggal promo (start_date s/d end_date).
    """
    if (
        "sales_pps_df" not in st.session_state
        or "periods_pps_df" not in st.session_state
    ):
        return

    sales_pps = st.session_state.sales_pps_df.copy()
    periode_pps = st.session_state.periods_pps_df.copy()

    if sales_pps.empty or periode_pps.empty:
        return

    # Pastikan format tanggal transaksi valid
    sales_pps["updated_at"] = pd.to_datetime(
        sales_pps["updated_at"], errors="coerce"
    ).dt.date

    # Pastikan kolom penampung syarat & redeem tersedia di PERIODE_PPS
    for col in ["syarat_total", "redeem_total"]:
        if col not in periode_pps.columns:
            periode_pps[col] = 0

    # Normalisasi kolom numerik di SALES_PPS
    numeric_cols = [
        "syarat_pwp",
        "redeem_pwp",
        "qty_pwp",
        "qty_sg",
        "syarat_sueger",
        "redeem_sueger",
        "cemilan_ceban",
    ]
    for col in numeric_cols:
        if col in sales_pps.columns:
            sales_pps[col] = pd.to_numeric(
                sales_pps[col], errors="coerce"
            ).fillna(0)

    # Iterasi akumulasi untuk tiap baris program di PERIODE_PPS
    for idx, row in periode_pps.iterrows():
        p_id = str(row.get("period_id", "")).strip().upper()
        p_name = str(row.get("period_name", "")).strip().upper()

        p_start = pd.to_datetime(row["start_date"], errors="coerce").date()
        p_end = pd.to_datetime(row["end_date"], errors="coerce").date()

        if pd.isna(p_start) or pd.isna(p_end):
            continue

        # Filter transaksi harian yang masuk dalam batas tanggal promo
        mask = (sales_pps["updated_at"] >= p_start) & (
            sales_pps["updated_at"] <= p_end
        )
        filtered_sales = sales_pps[mask]

        # 1. Program Suegeer (SGR001)
        if "SGR" in p_id or "SUEGEER" in p_name:
            syarat = filtered_sales["syarat_sueger"].sum()
            redeem = filtered_sales["redeem_sueger"].sum()
            periode_pps.loc[idx, "syarat_total"] = int(syarat)
            periode_pps.loc[idx, "redeem_total"] = int(redeem)
            periode_pps.loc[idx, "actual_qty"] = int(
                redeem
            )  # Actual Suegeer berbasis Qty Redeem

        # 2. Program PWP (PWP01)
        elif "PWP" in p_id or "PWP" in p_name:
            syarat = filtered_sales["syarat_pwp"].sum()
            redeem = filtered_sales["redeem_pwp"].sum()
            qty_pwp = filtered_sales["qty_pwp"].sum()
            periode_pps.loc[idx, "syarat_total"] = int(syarat)
            periode_pps.loc[idx, "redeem_total"] = int(redeem)
            periode_pps.loc[idx, "actual_qty"] = int(
                qty_pwp
            )  # Actual PWP berbasis Qty PWP

        # 3. Program Serba Gratis (SGS01)
        elif "SGS" in p_id or "SERBA GRATIS" in p_name:
            qty_sg = filtered_sales["qty_sg"].sum()
            periode_pps.loc[idx, "syarat_total"] = 0
            periode_pps.loc[idx, "redeem_total"] = 0
            periode_pps.loc[idx, "actual_qty"] = int(qty_sg)

        # 4. Program Cemilan Ceban (CBN01)
        elif "CBN" in p_id or "CEBAN" in p_name:
            cemilan = filtered_sales["cemilan_ceban"].sum()
            periode_pps.loc[idx, "syarat_total"] = 0
            periode_pps.loc[idx, "redeem_total"] = 0
            periode_pps.loc[idx, "actual_qty"] = int(cemilan)

    # Simpan kembali ke Session State
    st.session_state.periods_pps_df = periode_pps


def save_database(
    sales_item_df, sales_person_df, sales_pps_df, sales_store_df
):
    """Menyimpan data transaksi & hasil akumulasi PPS ke Google Sheets."""
    try:
        # PENGAMANAN: Blokir penyimpanan jika data transaksi utama mendadak kosong
        if sales_item_df.empty or sales_person_df.empty:
            st.warning(
                "⚠️ Proses simpan dibatalkan: Data transaksi terdeteksi kosong"
                " untuk mencegah kehilangan data."
            )
            return False

        # 1. Pastikan sinkronisasi akumulasi PPS ter-update sebelum disimpan
        sync_periode_pps_from_sales()

        # 2. Proses update bertahap ke Google Sheets
        conn.update(worksheet="SALES_ITEM", data=sales_item_df)
        time.sleep(0.4)
        conn.update(worksheet="SALES_PERSONIL", data=sales_person_df)
        time.sleep(0.4)
        conn.update(worksheet="SALES_PPS", data=sales_pps_df)
        time.sleep(0.4)

        # Update pula PERIODE_PPS untuk menyimpan akumulasi aktual
        if (
            "periods_pps_df" in st.session_state
            and not st.session_state.periods_pps_df.empty
        ):
            conn.update(
                worksheet="PERIODE_PPS", data=st.session_state.periods_pps_df
            )
            time.sleep(0.4)

        conn.update(worksheet="SALES_STOREPERFORMANCE", data=sales_store_df)

        # Hapus cache agar Streamlit membaca data paling baru setelah disimpan
        st.cache_data.clear()

        st.toast(
            "Perubahan transaksi tersimpan permanen di Google Sheets!", icon="✅"
        )
        return True
    except Exception as e:
        st.error(
            f"❌ Gagal menyimpan transaksi ke Google Sheets (Kemungkinan"
            f" terkena limit/timeout): {e}"
        )
        return False


def save_master_table(sheet_name, df_data):
    """Menyimpan tabel master dengan pengaman validasi data kosong dan urutan kolom."""
    try:
        if df_data.empty:
            st.warning(
                f"⚠️ Master {sheet_name} batal disimpan karena data kosong."
            )
            return False

        # Penyelarasan urutan kolom khusus untuk MASTER_ITEM agar tidak bergeser
        if sheet_name == "MASTER_ITEM":
            expected_cols = [
                "period_id",
                "item_id",
                "item_name",
                "active",
                "category",
            ]
            for col in expected_cols:
                if col not in df_data.columns:
                    df_data[col] = ""
            df_data = df_data[expected_cols]

        conn.update(worksheet=sheet_name, data=df_data)
        time.sleep(0.3)

        # Hapus cache agar perubahan master data langsung terefleksi
        st.cache_data.clear()

        st.toast(
            f"Master {sheet_name} berhasil diperbarui di Google Sheets!",
            icon="✅",
        )
        return True
    except Exception as e:
        st.error(
            f"❌ Gagal update master {sheet_name} (Terkena limit API): {e}"
        )
        return False


def sync_store_sales_from_personnel():
    if (
        "sales_person_df" in st.session_state
        and "sales_item_df" in st.session_state
    ):
        sp_df = st.session_state.sales_person_df.copy()
        si_df = st.session_state.sales_item_df.copy()

        req_cols_sp = ["period_id", "item_id", "actual_qty"]
        req_cols_si = ["period_id", "item_id"]

        if sp_df.empty or not all(col in sp_df.columns for col in req_cols_sp):
            return
        if si_df.empty or not all(col in si_df.columns for col in req_cols_si):
            return

        sp_df["period_id"] = sp_df["period_id"].astype(str)
        sp_df["item_id"] = sp_df["item_id"].astype(str)
        si_df["period_id"] = si_df["period_id"].astype(str)
        si_df["item_id"] = si_df["item_id"].astype(str)

        sp_df["actual_qty"] = pd.to_numeric(
            sp_df["actual_qty"], errors="coerce"
        ).fillna(0)
        tot_per_item = (
            sp_df.groupby(["period_id", "item_id"])["actual_qty"]
            .sum()
            .reset_index()
        )
        tot_per_item.rename(
            columns={"actual_qty": "calc_actual_qty"}, inplace=True
        )

        if "calc_actual_qty" in si_df.columns:
            si_df.drop(columns=["calc_actual_qty"], inplace=True)

        merged = pd.merge(
            si_df, tot_per_item, on=["period_id", "item_id"], how="left"
        )
        merged["calc_actual_qty"] = merged["calc_actual_qty"].fillna(0)
        merged["actual_qty"] = merged["calc_actual_qty"]
        merged.drop(columns=["calc_actual_qty"], inplace=True)
        st.session_state.sales_item_df = merged


# Inisialisasi Session State Data
if "data_loaded" not in st.session_state:
    (
        p_df,
        p_pps_df,
        p_store_df,
        i_df,
        pers_df,
        si_df,
        sp_df,
        s_pps_df,
        s_store_df,
    ) = load_database()
    st.session_state.periods_df = p_df
    st.session_state.periods_pps_df = p_pps_df
    st.session_state.periods_store_df = p_store_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.sales_pps_df = s_pps_df
    st.session_state.sales_store_df = s_store_df
    st.session_state.data_loaded = True

    # Sinkronisasi awal agar PERIODE_PPS langsung terhitung saat aplikasi pertama kali dibuka
    sync_periode_pps_from_sales()


# --- FUNGSI PEMBANTU BATAS TANGGAL PERIODE ---
def get_period_date_bounds(p_id):
    periods_df = st.session_state.get("periods_df", pd.DataFrame())
    if not periods_df.empty and "period_id" in periods_df.columns:
        p_match = periods_df[
            periods_df["period_id"].astype(str).str.strip() == str(p_id).strip()
        ]
        if (
            not p_match.empty
            and "start_date" in p_match.columns
            and "end_date" in p_match.columns
        ):
            try:
                p_start = pd.to_datetime(
                    p_match.iloc[0]["start_date"], errors="coerce"
                ).date()
                p_end = pd.to_datetime(
                    p_match.iloc[0]["end_date"], errors="coerce"
                ).date()
                if not pd.isna(p_start) and not pd.isna(p_end):
                    if p_start > p_end:
                        p_start, p_end = p_end, p_start
                    return p_start, p_end
            except Exception:
                pass
    today = pd.Timestamp.now().date()
    return today.replace(day=1), today


# --- INISIALISASI GLOBAL PERIODS_DICT ---
periods_dict = {}
active_periods_df = st.session_state.get("periods_df", pd.DataFrame())

if not active_periods_df.empty and all(
    col in active_periods_df.columns
    for col in ["period_id", "period_name", "start_date", "end_date"]
):
    for _, row in active_periods_df.iterrows():
        periods_dict[str(row["period_name"])] = str(row["period_id"])

if not periods_dict and not active_periods_df.empty:
    periods_dict = {
        str(row["period_name"]): str(row["period_id"])
        for _, row in active_periods_df.iterrows()
    }

def backup_to_gsheets():
    """Menyimpan salinan cadangan otomatis ke tab _BACKUP di Google Sheets."""
    try:
        # 1. Backup Data PPS
        if (
            "sales_pps_df" in st.session_state
            and not st.session_state.sales_pps_df.empty
        ):
            conn.update(
                worksheet="SALES_PPS_BACKUP", data=st.session_state.sales_pps_df
            )

        if (
            "periods_pps_df" in st.session_state
            and not st.session_state.periods_pps_df.empty
        ):
            conn.update(
                worksheet="PERIODE_PPS_BACKUP",
                data=st.session_state.periods_pps_df,
            )

        # 2. Backup Data Utama / PSM
        if (
            "sales_item_df" in st.session_state
            and not st.session_state.sales_item_df.empty
        ):
            conn.update(
                worksheet="SALES_ITEM_BACKUP",
                data=st.session_state.sales_item_df,
            )

        if (
            "sales_person_df" in st.session_state
            and not st.session_state.sales_person_df.empty
        ):
            conn.update(
                worksheet="SALES_PERSON_BACKUP",
                data=st.session_state.sales_person_df,
            )

        return True
    except Exception as e:
        # Jika tab _BACKUP belum dibuat di Google Sheets, sistem tidak akan menghentikan aplikasi
        return False

# ==========================================
# 3. WAKTU REALTIME GMT+7 (WIB)
# ==========================================
waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%A, %d %B %Y | %H:%M WIB")

# ==========================================
# 4. DATABASE AKUN PENGGUNA (LOGIN)
# ==========================================
USER_DATABASE = {
    "admin": {"password": "lavitality", "nama": "admin"},
    "23044862": {"password": "c383kgs", "nama": "ARIS APRILIANTO"},
    "24091737": {"password": "c383kgs", "nama": "TIKA"},
    "24096619": {"password": "c383kgs", "nama": "RIZKI GUNAWAN"},
    "25037119": {"password": "c383kgs", "nama": "ADELIA PRATIWI"},
    "26065884": {"password": "c383kgs", "nama": "ILHAM PRIANDIKA"},
    "13127006": {"password": "c383kgs", "nama": "REZA PURNAMA AGUSTIN"},
    "16016359": {"password": "c383kgs", "nama": "SUBEKTI PANDU YULIANTO"},
    "19061965": {"password": "c383kgs", "nama": "KUSDEWI TIA NINGRUM"},
    "21046101": {"password": "c383kgs", "nama": "AHMAD ZAKI SYABANI ZEN"},
    "visitor": {"password": "visitor", "nama": "Pengunjung"},
}


def check_login(input_username, input_password):
  if "person_df" in st.session_state and not st.session_state.person_df.empty:
    df_users = st.session_state.person_df
  else:
    df_users = conn.read(worksheet="MASTER_PERSONIL", ttl=0)

  user_match = df_users[
      (
          df_users["username"].astype(str).str.strip().str.lower()
          == str(input_username).strip().lower()
      )
      & (
          df_users["password"].astype(str).str.strip()
          == str(input_password).strip()
      )
  ]

  if not user_match.empty:
    matched_user = user_match.iloc[0]
    st.session_state["username"] = matched_user["username"]
    st.session_state["user_role"] = matched_user.get("role", "Staff Toko")
    st.session_state["role"] = matched_user.get("role", "Staff Toko")
    return True
  return False


# =============================================================================
# CUSTOM CSS UNIVERSAL (ROYAL GUILD / RPG FANTASY THEME)
# =============================================================================
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Quicksand:wght@600;700&family=Cinzel:wght@600;700;800&display=swap');

    /* -------------------------------------------------------------------------
       1. BASE APP & BACKGROUND KERAJAAN
       ------------------------------------------------------------------------- */
    .stApp {
        background: radial-gradient(circle at top, #162447 0%, #0b0f19 70%, #05070c 100%) !important;
        color: #f1e5c7 !important;
        font-family: 'Quicksand', sans-serif !important;
    }
    
    /* SCROLLBAR KERAJAAN */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #0b0f19;
    }
    ::-webkit-scrollbar-thumb {
        background: #9a7b38;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #d4af37;
    }

    /* -------------------------------------------------------------------------
       2. LABEL & WIDGET TEKS
       ------------------------------------------------------------------------- */
    label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label, label p {
        color: #f7e7b4 !important;
        font-family: 'Cinzel', serif !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        letter-spacing: 0.5px !important;
        text-shadow: 0 0 5px rgba(212, 175, 55, 0.3) !important;
    }
    
    /* -------------------------------------------------------------------------
       3. INPUT BOX & DROPDOWN (FIELD TEKS/SELECT/DATE)
       ------------------------------------------------------------------------- */
    div[data-baseweb="input"] input, 
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] span {
        color: #f1e5c7 !important;
        background-color: transparent !important;
        font-weight: bold !important;
    }
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div {
        background-color: rgba(10, 17, 34, 0.85) !important;
        border: 1.5px solid #9a7b38 !important;
        border-radius: 8px !important;
        box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.8) !important;
    }
    div[data-baseweb="input"] svg, div[data-baseweb="select"] svg {
        fill: #d4af37 !important;
    }

    /* -------------------------------------------------------------------------
       4. METRICS / KARTU STATISTIK (BINGKAI KERAJAAN)
       ------------------------------------------------------------------------- */
    div[data-testid="stMetric"] {
        background: radial-gradient(circle, #1a2636 0%, #0e1726 100%) !important;
        border: 2px solid #d4af37 !important;
        padding: 16px !important;
        border-radius: 12px !important;
        box-shadow: 0 0 15px rgba(212, 175, 55, 0.25), inset 0 0 15px rgba(0, 0, 0, 0.7) !important;
        position: relative !important;
    }
    div[data-testid="stMetric"] label {
        color: #cbd5e1 !important;
        font-family: 'Quicksand', sans-serif !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f7e7b4 !important;
        text-shadow: 0 0 10px rgba(212, 175, 55, 0.6), 1px 1px 3px #000 !important;
        font-family: 'MedievalSharp', serif !important;
        font-weight: 800 !important;
        font-size: 28px !important;
    }

    /* -------------------------------------------------------------------------
       5. ST.EXPANDER (GULUNGAN MISTIS / EXPANDER KERAJAAN)
       ------------------------------------------------------------------------- */
    div[data-testid="stExpander"] {
        background: rgba(12, 20, 39, 0.85) !important;
        border: 1.5px solid #9a7b38 !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.6) !important;
        overflow: hidden !important;
        margin-bottom: 12px !important;
    }
    div[data-testid="stExpander"] summary {
        background: linear-gradient(90deg, #162447 0%, #0d172e 100%) !important;
        color: #f7e7b4 !important;
        font-family: 'Cinzel', serif !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        border-bottom: 1px solid #9a7b38 !important;
        padding: 10px 16px !important;
        transition: all 0.25s ease !important;
    }
    div[data-testid="stExpander"] summary:hover {
        background: linear-gradient(90deg, #1f315c 0%, #121e3a 100%) !important;
        color: #ffffff !important;
        text-shadow: 0 0 8px rgba(212, 175, 55, 0.6) !important;
    }
    div[data-testid="stExpander"] summary svg {
        fill: #d4af37 !important;
    }
    div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        padding: 16px !important;
        background: rgba(8, 13, 25, 0.6) !important;
    }

    /* -------------------------------------------------------------------------
       6. ST.DATAFRAME / ST.TABLE (GULUNGAN DATA & KATALOG GUILD)
       ------------------------------------------------------------------------- */
    div[data-testid="stDataFrame"], div[data-testid="stTable"] {
        background-color: rgba(10, 17, 34, 0.9) !important;
        border: 1.5px solid #d4af37 !important;
        border-radius: 10px !important;
        box-shadow: 0 0 15px rgba(212, 175, 55, 0.2), inset 0 0 15px rgba(0, 0, 0, 0.8) !important;
        padding: 4px !important;
    }
    /* Dynamic table header / glide data grid override */
    div[data-testid="stDataFrame"] iframe {
        border-radius: 8px !important;
    }

    /* -------------------------------------------------------------------------
       7. SIDEBAR KERAJAAN
       ------------------------------------------------------------------------- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0c1427 0%, #05070c 100%) !important;
        border-right: 2px solid #9a7b38 !important;
        box-shadow: 5px 0 15px rgba(0, 0, 0, 0.5) !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #f1e5c7 !important;
        font-weight: 600 !important;
    }

    /* -------------------------------------------------------------------------
   8. FIX ULTIMATE: SIDEBAR PRESISI SAMA & FLOATING PILL ICON-ONLY NAVBAR
   ------------------------------------------------------------------------- */

    /* Sembunyikan Radio Dot Asli Streamlit */
    div[data-testid="stRadio"] input[type="radio"] {
        position: absolute !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        pointer-events: none !important;
    }
    
    div[data-testid="stRadio"] [data-testid="stRadioButtonCustomIcon"],
    div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    
    /* =========================================================================
       A. SIDEBAR: LOCK PRESISI 100% SAMA BESAR DENGAN TOMBOL TUTUP SIDEBAR
       ========================================================================= */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] {
        display: flex !important;
        flex-direction: column !important;
        gap: 10px !important;
        width: 100% !important;
        align-items: stretch !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label,
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] [data-baseweb="radio"] {
        width: 100% !important;              /* Paksa 100% Lebar Sidebar */
        max-width: 100% !important;
        min-width: 100% !important;
        height: 44px !important;             /* Tinggi Presisi Sama Rata */
        background: linear-gradient(180deg, #162447 0%, #0c1427 100%) !important;
        border: 1.5px solid #9a7b38 !important;
        border-radius: 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        margin: 0 !important;
        padding: 0 10px !important;
        box-sizing: border-box !important;
        cursor: pointer !important;
        box-shadow: inset 0 0 6px rgba(0, 0, 0, 0.5), 0 2px 4px rgba(0, 0, 0, 0.4) !important;
    }
    
    /* Teks Sidebar Tetap Rapi Di Tengah */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label * {
        color: #f1e5c7 !important;
        font-family: 'Cinzel', serif !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        white-space: nowrap !important;
    }
    
    /* Active State Sidebar */
    section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #b8860b 0%, #785805 100%) !important;
        border-color: #f7e7b4 !important;
        box-shadow: 0 0 12px rgba(212, 175, 55, 0.6) !important;
    }
    
    /* =========================================================================
   B. FLOATING PILL NAVBAR - FIX PRESISI TENGAH LAYAR
   ========================================================================= */
    /* Wrapper Bawaan Streamlit Dipaksa Center */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        margin: 0 auto !important;
    }
    
    /* Kapsul Utama */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: center !important;
        align-items: center !important;
        gap: 6px !important;
        
        background: #09101f !important;
        border: 1.5px solid #2d3f66 !important;
        border-radius: 50px !important;
        padding: 6px 10px !important;
        
        /* Lock Center Mutlak */
        margin: 10px auto !important;
        width: fit-content !important;
        max-width: 90% !important;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5) !important;
    }
    
    /* ITEM TOMBOL (Aktiv & Non-Aktif) */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] [data-baseweb="radio"] {
        background: transparent !important;
        border: none !important;
        border-radius: 30px !important;
        height: 42px !important;
        min-width: 44px !important;
        padding: 0 12px !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        transition: all 0.3s ease-in-out !important;
        flex: 0 0 auto !important;
    }
    
    /* Sembunyikan Teks pada Opsi Tidak Aktif */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label p,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label span {
        font-size: 0px !important;
        color: transparent !important;
    }
    
    /* IKON / LOGO PADA MENU NON-AKTIF */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label p::first-letter,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label span::first-letter {
        font-size: 20px !important;
        color: #a0aec0 !important;
    }
    
    /* Hover State */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label:hover p::first-letter,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label:hover span::first-letter {
        color: #d4af37 !important;
    }
    
    /* =========================================================================
       C. ACTIVE STATE (KAPSUL EMAS TERPILIH)
       ========================================================================= */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked),
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] [aria-checked="true"] {
        background: linear-gradient(135deg, #d4af37 0%, #aa7c11 100%) !important;
        padding: 0 16px !important;
        box-shadow: 0 4px 12px rgba(212, 175, 55, 0.4) !important;
    }
    
    /* TEKS & IKON PADA TOMBOL AKTIF */
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) span,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] [aria-checked="true"] p,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] [aria-checked="true"] span {
        font-size: 11px !important;
        font-family: 'Cinzel', serif !important;
        font-weight: 800 !important;
        color: #0d1527 !important;
        white-space: nowrap !important;
    }
    
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p::first-letter,
    div[data-testid="stMainBlockContainer"] div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) span::first-letter {
        font-size: 16px !important;
        color: #0d1527 !important;
    }


    /* -------------------------------------------------------------------------
       9. TOMBOL ST.BUTTON (TOMBOL EKSEKUSI GUILD)
       ------------------------------------------------------------------------- */
    div.stButton > button, div.stFormSubmitButton > button {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
        color: #f7e7b4 !important;
        border: 1.5px solid #d4af37 !important;
        border-radius: 8px !important;
        font-family: 'Cinzel', serif !important;
        font-weight: bold !important;
        box-shadow: 0 0 10px rgba(212, 175, 55, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background: linear-gradient(180deg, #d4af37 0%, #9a7b38 100%) !important;
        color: #0b0f19 !important;
        box-shadow: 0 0 18px rgba(212, 175, 55, 0.7) !important;
    }

    /* -------------------------------------------------------------------------
       10. TAB CONTROL KERAJAAN
       ------------------------------------------------------------------------- */
    div[data-baseweb="tab-list"] button {
        background-color: transparent !important;
    }
    div[data-baseweb="tab-list"] button div[data-testid="stMarkdownContainer"] p {
        color: #94a3b8 !important;
        font-family: 'Cinzel', serif !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="tab-list"] button[aria-selected="true"] div[data-testid="stMarkdownContainer"] p {
        color: #f7e7b4 !important;
        font-weight: 800 !important;
        text-shadow: 0 0 8px rgba(212, 175, 55, 0.6) !important;
    }
    div[data-baseweb="tab-highlight"] {
        background-color: #d4af37 !important;
        box-shadow: 0 0 8px rgba(212, 175, 55, 0.8) !important;
    }

    /* -------------------------------------------------------------------------
       11. HEADER KERAJAAN (ROYAL FRAME STYLES)
       ------------------------------------------------------------------------- */
    .royal-outer-frame {
        position: relative;
        background: radial-gradient(circle, #162447 0%, #0c1427 100%);
        border: 3px double #d4af37;
        border-radius: 14px;
        box-shadow: 0 0 15px rgba(212, 175, 55, 0.35), inset 0 0 20px rgba(0, 0, 0, 0.8);
        padding: 10px 14px;
        color: #f1e5c7;
        font-family: 'Quicksand', sans-serif;
    }
    .corner-ornament { position: absolute; color: #d4af37; font-size: 10px; line-height: 1; opacity: 0.85; pointer-events: none; }
    .top-left { top: 3px; left: 5px; }
    .top-right { top: 3px; right: 5px; }
    .bottom-left { bottom: 3px; left: 5px; }
    .bottom-right { bottom: 3px; right: 5px; }
    .guild-title-box { text-align: center; margin-bottom: 8px; }
    .guild-title {
        font-family: 'MedievalSharp', serif;
        font-size: 16px;
        color: #f7e7b4;
        text-shadow: 0 0 8px rgba(212, 175, 55, 0.8), 2px 2px 4px #000;
        margin: 0;
        letter-spacing: 0.8px;
    }
    .guild-subtitle { font-size: 9px; color: #38bdf8; margin-top: 1px; letter-spacing: 0.3px; }
    .bottom-row { display: flex; align-items: stretch; justify-content: space-between; gap: 10px; width: 100%; }
    .royal-side-box {
        flex: 1;
        background: rgba(10, 17, 34, 0.75);
        border: 1px solid #9a7b38;
        border-radius: 8px;
        padding: 6px 10px;
        min-width: 0;
        box-shadow: inset 0 0 8px rgba(0, 0, 0, 0.6);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .box-title { font-size: 8px; color: #e5c158; font-weight: bold; letter-spacing: 0.6px; margin-bottom: 3px; text-transform: uppercase; }
    .marquee-container { overflow: hidden; white-space: nowrap; width: 100%; border-radius: 5px; padding: 2px 0; margin-top: 2px; }
    .marquee-text { display: inline-block; padding-left: 100%; animation: marquee 10s linear infinite; font-size: 10px; font-weight: bold; }

    @keyframes marquee {
        0%   { transform: translate(0, 0); }
        100% { transform: translate(-100%, 0); }
    }

    .time-box-wrapper { display: flex; align-items: center; justify-content: space-between; width: 100%; }
    .hourglass-container { display: flex; align-items: center; justify-content: center; padding-right: 8px; }
    .hourglass-spin {
        font-size: 20px;
        display: inline-block;
        filter: drop-shadow(0 0 6px rgba(212, 175, 55, 0.8));
        animation: spinHourglass 2.5s infinite ease-in-out;
    }

    @keyframes spinHourglass {
        0% { transform: rotate(0deg); }
        50% { transform: rotate(180deg); }
        100% { transform: rotate(180deg); }
    }

    .right-clock-content { text-align: right; flex: 1; }
    .greeting-text { font-size: 9px; color: #fcd34d; font-weight: bold; margin-bottom: 1px; }
    .digital-clock { font-family: monospace; font-size: 13px; font-weight: bold; color: #38bdf8; text-shadow: 0 0 6px rgba(56, 189, 248, 0.5); line-height: 1.1; }
    .digital-date { font-size: 9px; color: #cbd5e1; margin-top: 1px; font-weight: bold; }

    @media (min-width: 650px) {
        .guild-title { font-size: 18px; }
        .guild-subtitle { font-size: 11px; }
        .greeting-text { font-size: 10px; }
        .digital-clock { font-size: 14px; }
        .digital-date { font-size: 10px; }
        .box-title { font-size: 9px; }
        .marquee-text { font-size: 11px; }
        .hourglass-spin { font-size: 24px; }
    }
</style>
""",
    unsafe_allow_html=True,
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
    

# ==========================================
# 6. HALAMAN LOGIN
# ==========================================
def show_login_page():
  LOGO_URL = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/kgs_group_belgium_logo.jpg"

  st.markdown(
      f"""
        <style>
            .login-card {{
                background-color: #1e293b;
                padding: 35px 30px;
                border-radius: 16px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
                text-align: center;
                margin-bottom: 20px;
            }}
            .login-logo {{
                width: 100px;
                height: 100px;
                object-fit: contain;
                border-radius: 12px;
                background-color: #ffffff;
                padding: 8px;
                margin-bottom: 15px;
                display: block;
                margin-left: auto;
                margin-right: auto;
            }}
            .login-subtitle {{
                color: #38bdf8;
                font-size: 13px;
                margin-bottom: 0px;
            }}
        </style>
        <div class='login-card'>
            <img src='{LOGO_URL}' class='login-logo' alt='KGS Group Logo'>
            <p class='login-subtitle'>Sistem Monitoring PSM Toko</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  _, col2, _ = st.columns([1, 1.4, 1])

  with col2:
    with st.form("login_form", clear_on_submit=False):
      username_input = st.text_input(
          "Username", placeholder="Masukkan username"
      ).strip()
      password_input = st.text_input(
          "Password", type="password", placeholder="Masukkan password"
      )
      submit_btn = st.form_submit_button(
          "Masuk ke Aplikasi", use_container_width=True
      )

      if submit_btn:
        if not username_input or not password_input:
          st.warning("Username dan Password wajib diisi!")
        elif (
            username_input in USER_DATABASE
            and USER_DATABASE[username_input]["password"] == password_input
        ):
          user_info = USER_DATABASE[username_input]
          st.session_state.logged_in = True
          st.session_state.username = user_info["nama"]
          st.toast(f"Selamat Datang, {user_info['nama']}!", icon="✅")
          st.rerun()
        else:
          st.error("Username atau Password salah!")
# =========================================================================
# 🛡️ SUNTIKAN MEMORI UTAMA (WAJIB ADA AGAR VARIABEL LOGGED_IN TERDAFTAR)
# =========================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "campaign_sub_page" not in st.session_state:
    st.session_state["campaign_sub_page"] = "resepsionis_utama"

if not st.session_state.logged_in:
  show_login_page()
  st.stop()

# ==========================================================
# 7. SIDEBAR DASHBOARD - GAYA CODINGLAB (BAGIAN 1)
# ==========================================================

# Inisialisasi status buka/tutup sidebar di session_state
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False

# Fungsi untuk memicu perubahan ukuran sidebar saat tombol diklik
def toggle_sidebar_size():
    st.session_state.sidebar_collapsed = not st.session_state.sidebar_collapsed

# Tentukan lebar sidebar berdasarkan statusnya
sidebar_width = "80px" if st.session_state.sidebar_collapsed else "260px"

st.sidebar.markdown(
    f"""
    <style>
        /* Mengatur transisi animasi perubahan lebar sidebar */
        [data-testid="stSidebar"] {{
            width: {sidebar_width} !important;
            min-width: {sidebar_width} !important;
            max-width: {sidebar_width} !important;
            transition: width 0.3s ease-in-out !important;
            background-color: #1c1c1e;
            overflow-x: hidden !important;
        }}
        
        /* Menyesuaikan pergeseran konten utama saat sidebar mengecil */
        [data-testid="stAppViewContainer"] {{
            padding-left: 0px !important;
        }}

        /* Header Profil */
        .sidebar-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
            padding: 5px 10px;
            white-space: nowrap;
        }}
        .profile-container {{
            display: flex;
            align-items: center;
            gap: 14px;
            /* Menyembunyikan nama user jika sidebar mengecil */
            display: {"none" if st.session_state.sidebar_collapsed else "flex"};
        }}
        .sidebar-logo {{
            width: 45px;
            height: 45px;
            border-radius: 12px;
            object-fit: cover;
            border: 2px solid #6366f1;
        }}

        /* Teks Judul Toko (Disembunyikan jika mengecil) */
        .store-info-box {{
            display: {"none" if st.session_state.sidebar_collapsed else "block"};
            padding: 0 10px;
        }}
        .store-title {{
            color: #ffffff;
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 2px;
            letter-spacing: 0.5px;
        }}
        .store-subtitle {{
            color: #a1a1aa;
            font-size: 12px;
            font-weight: 500;
            margin-bottom: 20px;
        }}
    </style>
""",
    unsafe_allow_html=True,
)
# ==========================================================
# 7. SIDEBAR DASHBOARD - GAYA CODINGLAB (BAGIAN 2)
# ==========================================================
st.sidebar.markdown(
    """
    <style>
        /* Mengubah struktur menu navigasi radio Streamlit */
        div[data-testid="stRadio"] > div {
            gap: 8px;
        }
        div[data-testid="stRadio"] label {
            background-color: transparent;
            color: #e4e4e7 !important;
            padding: 12px !important;
            border-radius: 8px;
            transition: all 0.2s ease;
            width: 100%;
            cursor: pointer;
            display: flex !important;
            align-items: center;
            justify-content: center;
        }
        
        /* Efek saat menu aktif (Ungu Balok) */
        div[data-testid="stRadio"] [data-checked="true"] label {
            background-color: #6366f1 !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }
        div[data-testid="stRadio"] [data-testid="stMarkdownVisibility"] {
            display: none;
        }
    </style>
""",
    unsafe_allow_html=True,
)

LOCAL_LOGO_PATH = "kgs_group_belgium_logo.jpg"
import os, base64
if os.path.exists(LOCAL_LOGO_PATH):
    with open(LOCAL_LOGO_PATH, "rb") as f:
        data = f.read()
    logo_src = f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"
else:
    logo_src = "https://flaticon.com"

username = st.session_state.get("username", "Admin")

if not st.session_state.sidebar_collapsed:
    # 👐 Tampilan saat Sidebar TERBUKA LEBAR (Nama Profil + Tombol ◀ Berdampingan)
    st.sidebar.markdown(
        f"""
        <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; padding: 5px 10px;'>
            <div class='profile-container' style='display: flex; align-items: center; gap: 14px;'>
                <img src='{logo_src}' class='sidebar-logo'>
                <div style='display: flex; flex-direction: column;'>
                    <span style='color: #a1a1aa; font-size: 11px;'>Selamat Datang,</span>
                    <span style='color: #ffffff; font-size: 14px; font-weight: 600;'>{username}</span>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True
    )
    # Tombol Panah ditaruh di bawah profil agar posisinya pas dan stabil
    st.sidebar.button("◀ Tutup Sidebar", on_click=toggle_sidebar_size, key="toggle_size_btn_open", use_container_width=True)
else:
    # 📭 Tampilan saat Sidebar MENGECIL / CIUT (Logo + Tombol ▶ Tersusun ke Bawah)
    st.sidebar.markdown(
        f"""
        <div style='display: flex; justify-content: center; align-items: center; margin-bottom: 10px; width: 100%;'>
            <img src='{logo_src}' class='sidebar-logo' style='width: 45px; height: 45px; border-radius: 12px;'>
        </div>
    """, unsafe_allow_html=True
    )
    st.sidebar.button("▶", on_click=toggle_sidebar_size, key="toggle_size_btn_close", use_container_width=True)
# Render Informasi Toko
st.sidebar.markdown(
    f"""
    <div class='store-info-box'>
        <div class='store-title'>TOKO C383</div>
        <div class='store-subtitle'>Report PSM dan Target PSM</div>
    </div>
""", unsafe_allow_html=True
)

# Navigasi Menu Utama (Jika mengecil, otomatis hanya menampilkan karakter ikon pertamanya saja)
if st.session_state.sidebar_collapsed:
    menu_options = ["🏠", "📝", "➕", "⚙️"]
    st.sidebar.markdown("<center><p style='color:#a1a1aa; font-size:12px;'>📌</p></center>", unsafe_allow_html=True)
else:
    menu_options = ["🏠 Menu Utama", "📝 Input Data", "➕ Edit Data (Admin)", "⚙️ Pengaturan & Master"]
    st.sidebar.markdown("<p style='color:#a1a1aa; font-size:11px; font-weight:700; padding: 0 10px;'>📌 NAVIGASI MENU</p>", unsafe_allow_html=True)

# 🚀 TAMBAHKAN SAKLAR PENGUNCI PERKEMAHAN INI TEPAT DI ATAS ST.SIDEBAR.RADIO ANDA:
if st.session_state.get("current_camp_menu") == "quiz_campaign":
    # Paksa agar navigasi utama mengalah dan mengunci sistem tetap di halaman Quiz Campaign
    selected_tab = None 
elif "redirect_to_input" in st.session_state and st.session_state.redirect_to_input:
    st.session_state["selected_tab"] = "📝 Input Data"
    del st.session_state.redirect_to_input

# 🚀 SISIPKAN KODE INI TEPAT SATU BARIS DI ATAS ST.SIDEBAR.RADIO ANDA:
if "redirect_to_input" in st.session_state and st.session_state.redirect_to_input:
    st.session_state["selected_tab"] = "📝 Input Data"
    del st.session_state.redirect_to_input # Matikan saklar setelah berhasil digunakan

# 🚀 SISIPKAN KODE INI TEPAT SATU BARIS DI ATAS ST.SIDEBAR.RADIO ANDA:
if "redirect_to_input" in st.session_state and st.session_state.redirect_to_input:
    st.session_state["selected_tab"] = "📝 Input Data"
    del st.session_state.redirect_to_input # Matikan saklar setelah berhasil digunakan

# Ini adalah baris kode st.sidebar.radio Anda (Jangan dihapus, pastikan posisinya berada di bawah kode if di atas):
selected_tab = st.sidebar.radio("", menu_options, key="selected_tab", label_visibility="collapsed")

# Tombol Keluar / Logout
st.sidebar.markdown("<hr style='margin: 15px 0; border-color: #27272a;'>", unsafe_allow_html=True)
logout_text = "🚪" if st.session_state.sidebar_collapsed else "🚪 Keluar / Logout"
if st.sidebar.button(logout_text, use_container_width=True, key="logout_sidebar"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()


# ==========================================
# 9. MODUL TAB / SUB MENU
# ==========================================

if "portal_guild_ready" in st.session_state and st.session_state.portal_guild_ready:
    st.markdown(
        """
        <style>
            /* 📱 KUNCI LAYOUT RAMPING & PRESISI UNTUK WEB, ANDROID, & IOS */
            .main .block-container {
                background-color: #0c1020 !important;
                min-height: 100vh !important;
                max-width: 750px !important;    /* 🎯 Membatasi lebar maksimal agar selalu ramping */
                margin: 0 auto !important;       /* 🎯 Memaksa wadah ramping berada tepat di tengah monitor */
                padding-top: 12% !important;     /* Jarak proporsional dari atas layar */
                padding-left: 20px !important;   /* Ruang aman sisi kiri di HP */
                padding-right: 20px !important;  /* Ruang aman sisi kanan di HP */
            }
            
            /* Menghilangkan elemen bawaan Streamlit */
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="stHeader"] { display: none !important; }

            /* Menata ulang gaya tombol Streamlit agar berbentuk Kartu Pilihan Game */
            div[data-testid="stColumn"] div.stButton > button,
            div[data-testid="stColumn"] a[data-testid="stLinkButton"] {
                min-height: 150px !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                align-items: center !important;
                border-radius: 16px !important;
                font-family: monospace !important;
                font-size: 15px !important;
                font-weight: 800 !important;
                letter-spacing: 0.5px !important;
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
                box-sizing: border-box !important;
                text-decoration: none !important;
            }

            /* Tombol Kiri: LAUNCH TELEPORTATION (Cyan Neon) */
            div[data-testid="stColumn"]:nth-child(1) a[data-testid="stLinkButton"] {
                background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(8, 145, 178, 0.3) 100%) !important;
                color: #00f0ff !important;
                border: 2px solid #06b6d4 !important;
                box-shadow: 0 0 15px rgba(6, 182, 212, 0.15) !important;
            }
            div[data-testid="stColumn"]:nth-child(1) a[data-testid="stLinkButton"]:hover {
                transform: translateY(-5px) scale(1.02) !important;
                background: #06b6d4 !important;
                color: #0f172a !important;
                box-shadow: 0 0 30px rgba(6, 182, 212, 0.6) !important;
            }

            /* Tombol Kanan: CANCEL AND RETURN (Merah Crimson) */
            div[data-testid="stColumn"]:nth-child(2) div.stButton > button {
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(185, 28, 28, 0.2) 100%) !important;
                color: #ef4444 !important;
                border: 2px solid #ef4444 !important;
                box-shadow: 0 0 15px rgba(239, 68, 68, 0.1) !important;
            }
            div[data-testid="stColumn"]:nth-child(2) div.stButton > button:hover {
                transform: translateY(-5px) scale(1.02) !important;
                background: #ef4444 !important;
                color: #ffffff !important;
                box-shadow: 0 0 30px rgba(239, 68, 68, 0.6) !important;
            }
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    st.markdown("<h1 style='color: #00ff88; font-family: monospace; font-size: 32px; text-shadow: 0 0 20px rgba(0,255,136,0.6); text-align: center;'>⚡ PORTAL READY! ⚡</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8; font-family: monospace; text-align: center; font-size: 13px; margin-bottom: 40px;'>Mekanisme sihir teleportasi aliansi telah dikonfigurasi sempurna. Silakan pilih langkah Anda:</p>", unsafe_allow_html=True)
    
    # 📱 Menggunakan pembagian kolom responsif
    col_portal1, col_portal2 = st.columns(2)
    
    with col_portal1:
        st.link_button("⚡ LAUNCH TELEPORTATION", url="https://guildutamac383.streamlit.app", use_container_width=True)
        
    with col_portal2:
        if st.button("❌ CANCEL & RETURN", use_container_width=True, key="btn_cancel_portal_main"):
            st.session_state.portal_guild_ready = False
            st.rerun()
            
    # Mengunci aplikasi secara mutlak agar kode di bawah tidak ikut dibaca
    st.stop()

# =========================================================================
# 🚀 LANGKAH 1: NAVIGASI PREPARATION CAMP (MURNI & AMAN DARI LOGIKA BENTROK)
# =========================================================================
if "portal_prep_ready" in st.session_state and st.session_state.portal_prep_ready:
    
    # Inisialisasi awal: jika baru masuk, pastikan wajib membuka menu utama perkemahan
    if "current_camp_menu" not in st.session_state:
        st.session_state["current_camp_menu"] = "main"

    # =========================================================================
    # 📜 SUB-MENU 1: KARTU ANGGOTA GUILD (EDISI FULLSCREEN MURNI)
    # =========================================================================
    if st.session_state.get("current_camp_menu") == "status":
    
        # =========================================================================
        # 🧪 1. DETEKSI AKUN HERO & SEASON BULANAN RIIL (ANTI-CRASH)
        # =========================================================================
        # Mengambil username login aktif (Nama Asli Kasir)
        current_hero_name = st.session_state.get("username", "VISITOR").strip().upper()
        
        # Deteksi Waktu Sekarang & Kunci Nama Season Bulanan (Contoh: "SEPTEMBER 2026")
        current_month_num = waktu_wib.month
        current_year_num = waktu_wib.year
        season_name_string = waktu_wib.strftime("%B %Y").upper()

        # Ambil salinan database ter-update dari session_state
        db_sales_person = st.session_state.get("sales_person_df", pd.DataFrame()).copy()
        db_sales_pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()
        db_periods_pps = st.session_state.get("periods_pps_df", pd.DataFrame()).copy()
        db_sales_item = st.session_state.get("sales_item_df", pd.DataFrame()).copy()

        # -------------------------------------------------------------------------
        # 👑 A. HITUNG PANGKAT (RANK) & LEVEL BERDASARKAN TOTAL DATA SEPANJANG MASA
        # -------------------------------------------------------------------------
        total_qty_psm_all_time = 0
        if not db_sales_person.empty and "person_name" in db_sales_person.columns and "actual_qty" in db_sales_person.columns:
            # Saring data khusus pahlawan yang sedang login
            hero_all_time_df = db_sales_person[db_sales_person["person_name"].astype(str).str.strip().str.upper() == current_hero_name]
            if not hero_all_time_df.empty:
                total_qty_psm_all_time = pd.to_numeric(hero_all_time_df["actual_qty"], errors="coerce").fillna(0).sum()

        # Formula Penentuan Pangkat / Title Berdasarkan Total Pencapaian PSM Semua Bulan
        if total_qty_psm_all_time < 100:
            hero_rank_title = "NOVICE"
        elif total_qty_psm_all_time < 300:
            hero_rank_title = "ELITE"
        elif total_qty_psm_all_time < 600:
            hero_rank_title = "MASTER"
        else:
            hero_rank_title = "LEGEND"

        # Formula Level Dinamis: Setiap kelipatan 15 pcs menaikkan level
        hero_calculated_level = int(math.floor(total_qty_psm_all_time / 15)) + 1
        if hero_calculated_level < 1:
            hero_calculated_level = 1

        # -------------------------------------------------------------------------
        # 📦 B. HITUNG BAR EXP (MURNI QUANTITY JUAL PSM BULAN BERJALAN / SEPTEMBER)
        # -------------------------------------------------------------------------
        qty_psm_current_season = 0
        if not db_sales_person.empty and "updated_at" in db_sales_person.columns and "actual_qty" in db_sales_person.columns:
            try:
                # Konversi kolom tanggal menjadi tipe datetime agar bisa dibaca bulannya
                db_sales_person["datetime_parsed"] = pd.to_datetime(db_sales_person["updated_at"], errors="coerce")
                
                # Saring data murni: Berdasarkan NAMA HERO + BULAN SEKARANG + TAHUN SEKARANG
                season_hero_df = db_sales_person[
                    (db_sales_person["person_name"].astype(str).str.strip().str.upper() == current_hero_name) &
                    (db_sales_person["datetime_parsed"].dt.month == current_month_num) &
                    (db_sales_person["datetime_parsed"].dt.year == current_year_num)
                ]
                
                if not season_hero_df.empty:
                    # Ambil total akumulasi Qty penjualan produk PSM bulan ini
                    qty_psm_current_season = int(pd.to_numeric(season_hero_df["actual_qty"], errors="coerce").fillna(0).sum())
            except Exception:
                qty_psm_current_season = 0

        # Hitung Persentase Isi Bar EXP (Target Bulanan Naik Level = 150 Pcs)
        target_exp_limit = 150
        if qty_psm_current_season > 0:
            percent_exp_calc = min(int((qty_psm_current_season / target_exp_limit) * 100), 100)
        else:
            percent_exp_calc = 2 # Berikan 2% minimum agar bar warna ungunya kelihatan sedikit di awal
            
        test_percent_exp = f"{percent_exp_calc}%"

        # -------------------------------------------------------------------------
        # ⚡ C. HITUNG TARGET MAKSIMAL PPS PER KASIR (PENGUNCI BATAS 100% ATK & DEF)
        # -------------------------------------------------------------------------
        target_pps_per_kasir = 20  # Angka cadangan default jika database kosong
        if not db_periods_pps.empty and "target_total" in db_periods_pps.columns and "start_date" in db_periods_pps.columns:
            db_periods_pps["start_dt"] = pd.to_datetime(db_periods_pps["start_date"], errors="coerce")
            active_pps_period = db_periods_pps[db_periods_pps["start_dt"].dt.month == current_month_num]
            if not active_pps_period.empty:
                try:
                    global_target_toko = pd.to_numeric(active_pps_period.iloc[0]["target_total"], errors="coerce")
                    if pd.isna(global_target_toko) or global_target_toko <= 0:
                        global_target_toko = 180
                    target_pps_per_kasir = int(math.ceil(global_target_toko / 9))
                except Exception:
                    target_pps_per_kasir = 20

        if target_pps_per_kasir <= 0:
            target_pps_per_kasir = 20

        # -------------------------------------------------------------------------
        # 🔥 D. HITUNG BAR ATK (SERBA GRATIS) & 🛡️ BAR DEF (PWP) KHUSUS BULAN SEKARANG
        # -------------------------------------------------------------------------
        qty_sg_season = 0
        qty_pwp_season = 0
        qty_sueger_season = 0
        qty_ceban_season = 0
        total_syarat_sueger_season = 0
        total_redeem_sueger_season = 0

        if not db_sales_pps.empty and "kasir_name" in db_sales_pps.columns and "updated_at" in db_sales_pps.columns:
            db_sales_pps["datetime_parsed"] = pd.to_datetime(db_sales_pps["updated_at"], errors="coerce")
            # ATURAN 1: Filter murni menggunakan KASIR_NAME
            pps_hero_season_df = db_sales_pps[
                (db_sales_pps["kasir_name"].astype(str).str.strip().str.upper() == current_hero_name) &
                (db_sales_pps["datetime_parsed"].dt.month == current_month_num) &
                (db_sales_pps["datetime_parsed"].dt.year == current_year_num)
            ]
            
            if not pps_hero_season_df.empty:
                qty_sg_season = int(pd.to_numeric(pps_hero_season_df["qty_sg"], errors="coerce").fillna(0).sum())
                qty_pwp_season = int(pd.to_numeric(pps_hero_season_df["qty_pwp"], errors="coerce").fillna(0).sum())
                qty_sueger_season = int(pd.to_numeric(pps_hero_season_df.get("qty_sueger", pps_hero_season_df["redeem_sueger"]), errors="coerce").fillna(0).sum())
                qty_ceban_season = int(pd.to_numeric(pps_hero_season_df["cemilan_ceban"], errors="coerce").fillna(0).sum())
                
                total_syarat_sueger_season = pd.to_numeric(pps_hero_season_df["syarat_sueger"], errors="coerce").fillna(0).sum()
                total_redeem_sueger_season = pd.to_numeric(pps_hero_season_df["redeem_sueger"], errors="coerce").fillna(0).sum()

        # Hitung Persentase Isian Warna Bar ATK & DEF (Dibagi Target PPS Per Kasir)
        percent_atk_calc = min(int((qty_sg_season / target_pps_per_kasir) * 100), 100)
        percent_def_calc = min(int((qty_pwp_season / target_pps_per_kasir) * 100), 100)
        
        test_percent_psm = f"{percent_atk_calc}%"   # Mengisi Bar ATK (Serba Gratis)
        test_percent_pps = f"{percent_def_calc}%"   # Mengisi Bar DEF (PWP)

        # -------------------------------------------------------------------------
        # 🍃 E. HITUNG BAR AGI (SUEGER + CEBAN) BERDASARKAN SKALA TERTINGGI TOKO
        # -------------------------------------------------------------------------
        total_agi_hero = qty_sueger_season + qty_ceban_season
        max_agi_leaderboard = 50  # Standar aman jika staf lain masih 0
        
        if not db_sales_pps.empty and "updated_at" in db_sales_pps.columns:
            # Cari tahu siapa kasir dengan kombinasi sueger+ceban tertinggi bulan ini di Toko C383
            db_sales_pps["total_agi_calc"] = pd.to_numeric(db_sales_pps.get("qty_sueger", db_sales_pps["redeem_sueger"]), errors="coerce").fillna(0) + \
                                             pd.to_numeric(db_sales_pps["cemilan_ceban"], errors="coerce").fillna(0)
            
            # Kelompokkan data khusus bulan berjalan saat ini
            db_sales_pps["datetime_parsed"] = pd.to_datetime(db_sales_pps["updated_at"], errors="coerce")
            filtered_monthly_pps = db_sales_pps[
                (db_sales_pps["datetime_parsed"].dt.month == current_month_num) & 
                (db_sales_pps["datetime_parsed"].dt.year == current_year_num)
            ]
            
            if not filtered_monthly_pps.empty and "kasir_name" in filtered_monthly_pps.columns:
                grouped_staf_agi = filtered_monthly_pps.groupby("kasir_name")["total_agi_calc"].sum()
                if not grouped_staf_agi.empty:
                    max_agi_leaderboard = int(grouped_staf_agi.max())

        if max_agi_leaderboard <= 0:
            max_agi_leaderboard = 50

        percent_agi_calc = min(int((total_agi_hero / max_agi_leaderboard) * 100), 100)
        test_percent_sueger = f"{percent_agi_calc}%"  # Mengisi Bar AGI

        # -------------------------------------------------------------------------
        # 🔮 F. HITUNG STRUKTUR DATA UTAMA UNTUK 2 LENCANA KRISTAL BAWAH KARTU
        # -------------------------------------------------------------------------
        # LENCANA KIRI: Rata-rata Achievement Persentase Penjualan Sueger
        sueger_achievement_percentage = 0.0
        if total_syarat_sueger_season > 0:
            sueger_achievement_percentage = round((total_redeem_sueger_season / total_syarat_sueger_season) * 100, 1)
        
        # Tentukan Warna Cahaya Lampu Neon Kristal Kiri secara Otomatis (Std 50% target)
        neon_color_left_badge = "#00ffff" if sueger_achievement_percentage >= 50.0 else "#ff0055"
        text_badge_sueger_display = f"{sueger_achievement_percentage}%"

        # LENCANA KANAN: Jumlah Jenis Item PSM yang Penjualannya Mencapai Target Toko Bulan Ini
        count_item_success_season = 0
        if not db_sales_person.empty and not db_sales_item.empty and "season_hero_df" in locals():
            if not season_hero_df.empty and "item_id" in season_hero_df.columns and "actual_qty" in season_hero_df.columns:
                # Saring Qty jualan item per produk milik kasir aktif bulan ini
                hero_items_grouped = season_hero_df.groupby("item_id")["actual_qty"].sum().reset_index()
                
                for _, i_row in hero_items_grouped.iterrows():
                    i_id = str(i_row["item_id"]).strip()
                    i_qty = pd.to_numeric(i_row["actual_qty"], errors="coerce")
                    
                    # Cocokkan dengan target kelompok kasir di sales_item_df
                    match_item_target = db_sales_item[db_sales_item["item_id"].astype(str).str.strip() == i_id]
                    if not match_item_target.empty:
                        target_k_minimum = pd.to_numeric(match_item_target.iloc[0].get("target_kasir", 0), errors="coerce")
                        if i_qty >= target_k_minimum and target_k_minimum > 0:
                            count_item_success_season += 1

        # Alihkan variabel nama lama agar otomatis terhubung ke komponen HTML utama Anda
        test_level = hero_calculated_level
        test_qty_psm = qty_sg_season             # Mengisi angka teks 🔥 ATTACK (Serba Gratis)
        test_qty_pps = qty_pwp_season            # Mengisi angka teks 🛡️ DEFENSE (PWP)
        test_qty_sueger = total_agi_hero          # Mengisi angka teks 🍃 AGILITY (Sueger + Ceban)

        # 🎲 ATURAN RANDOM AVATAR KONSISTEN (ANTI-ACAK LIAR SAAT REFRESH)
        # Daftar emoji pahlawan medieval RPG premium
        list_avatar_rpg = ["🧙‍♂️", "🧝‍♂️", "⚔️", "🎯", "🛡️", "🦁", "🦅", "🐺", "👑", "💎", "🔮", "🔥"]
        
        # Gunakan rumus sisa bagi berdasarkan jumlah huruf nama kasir untuk mengunci 1 emoji unik
        index_avatar = len(current_hero_name) % len(list_avatar_rpg)
        random_hero_avatar = list_avatar_rpg[index_avatar]
        
        # 👑 2. STRUKTUR UTAMA HTML KARTU (FIXED: HTML KEMBALI NORMAL & WARNA BAR MUNCUL)
        html_master_packet = """
        <div class="rpg-card-fullscreen-container">
            <h2 class="rpg-header-title">📜 GUILD MEMBER LICENSE 📜</h2>
            <p class="rpg-header-sub">Sentuh gulungan kartu di bawah ini untuk melihat status pahlawan Anda.</p>
            <input type="checkbox" id="card-trigger" style="display: none !important;">
            <label class="flip-card-wrapper" for="card-trigger">
                <div class="flip-card-inner">
                    <!-- 🎴 SISI BELAKANG KARTU -->
                    <div class="card-face card-back-design">
                        <div class="magic-seal-back">🔮</div>
                        <h3 style="color: #b45309; font-size: 16px; font-weight: 800; margin: 0; letter-spacing: 2px; font-family: monospace;">UNVEIL STATUS</h3>
                        <p style="color: #475569; font-size: 11px; margin: 8px 0 0 0; font-family: monospace;">Tap to break the seal</p>
                    </div>
                    <!-- 👑 SISI DEPAN BINGKAI EMAS UTUH -->
                    <div class="card-face card-front-design">    
                        <!-- 🎯 AVATAR ATAS: Diisi otomatis dengan emoji RPG acak yang konsisten -->
                        <div class="char-avatar-box">""" + str(random_hero_avatar) + """</div>
                        <!-- 🎯 FIX FONT NAMA RESPONSIF: Mengecilkan font nama panjang agar tidak merusak bingkai emas -->
                        <div class="char-hero-name" style="font-size: 16px !important; letter-spacing: 1px !important; margin: 5px 0 !important; white-space: normal !important; max-width: 280px; line-height: 1.2;">""" + str(current_hero_name) + """</div>
                        <div class="char-hero-level-badge">RANK: """ + str(hero_rank_title) + """ • LEVEL """ + str(test_level) + """</div>
                        <div class="rpg-exp-container">
                            <div class="rpg-exp-header">
                            <div class="rpg-stat-header"><span>✨EXP (PSM BULAN INI)</span><span>""" + str(qty_psm_current_season) + """ Qty</span></div>
                            <div class="rpg-bar-bg">
                            <div class="rpg-exp-fill" style="width: """ + str(test_percent_exp) + """; height: 100%; display: block; background: linear-gradient(90deg, #a855f7, #d8b4fe) !important; box-shadow: 0 0 8px rgba(168, 85, 247, 0.6) !important;"></div>
                            </div>
                        </div>
                        <!-- BAR SG-->
                        <div class="rpg-stat-container">
                            <div class="rpg-stat-header"><span>🔥 ATTACK (PENJUALAN SG)</span><span>""" + str(test_qty_psm) + """ Qty</span></div>
                            <div class="rpg-bar-bg">
                            <div class="rpg_bar_fill_psm" style="width: """ + str(test_percent_psm) + """; height: 100%; border-radius: 4px; display: block;"></div>
                            </div>
                        </div>
                        <!-- BAR PWP -->
                        <div class="rpg-stat-container">
                            <div class="rpg-stat-header"><span>🛡️ DEFENSE (PENJUALAN PWP)</span><span>""" + str(test_qty_pps) + """ Poin</span></div>
                            <div class="rpg-bar-bg">
                            <div class="rpg_bar_fill_pps" style="width: """ + str(test_percent_pps) + """; height: 100%; border-radius: 4px; display: block;"></div>
                            </div>
                        </div>
                        <!-- BAR sueger -->
                        <div class="rpg-stat-container">
                            <div class="rpg-stat-header"><span>🍃 AGILITY (PENJUALAN SUEGER)</span><span>""" + str(test_qty_sueger) + """ Qty</span></div>
                            <div class="rpg-bar-bg">
                            <div class="rpg_bar_fill_sueger" style="width: """ + str(test_percent_sueger) + """; height: 100%; border-radius: 4px; display: block;"></div>
                            </div>
                        <div class="rpg-dual-badge-row">
                            <!-- LENCANA KIRI: Persentase Penjualan Sueger (Bulat) -->
                            <div class="rpg-badge-item">
                                <div class="rpg-emblem-wrapper emblem-left">
                                    <span class="rpg-emblem-text">""" + str(test_percent_sueger) + """</span>
                                </div>
                                <div class="rpg-emblem-label">SUEGER</div>
                            </div>
                            <!-- LENCANA KANAN: Total Item Mencapai Target (Segi Enam) -->
                            <!-- 🎯 FIX MUTLAK: Ditambahkan style transform untuk menggeser seluruh komponen (bingkai + teks) ke kanan sebanyak 12px -->
                            <div class="rpg-badge-item" style="transform: translateX(12px) !important;">
                                <div class="rpg-emblem-wrapper emblem-right">
                                    <span class="rpg-emblem-text">""" + str(count_item_success_season) + """</span>
                                </div>
                                <div class="rpg-emblem-label">TERCAPAI</div>
                            </div>
                        </div>
                        <div class="avatar-holder-bottom">👤</div>
                    </div>
                </div>
            </label>
        </div>
        """
        st.markdown(html_master_packet, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 🎨 3. SUNTIKKAN GAYA CSS GLOBAL & ENGINE KARTU FLIP (DIGABUNG PENUH & STERIL)
        st.markdown(
            """
            <style>
                /* ========================================================================= */
                /* 👑 KING OF FULLSCREEN: BERSINARKAN SATU LAYAR PENUH MURNI GAMBAR 1 */
                /* ========================================================================= */
                
                /* 1. Paksa lipat dan hancurkan visual sidebar kiri beserta tombol burger tiga garis */
                [data-testid="stSidebar"], 
                [data-testid="stSidebarCollapsedControl"],
                .stSidebar,
                div[data-testid="stSidebarUserContent"],
                button[title="Expand sidebar"] { 
                    display: none !important; 
                    width: 0px !important;
                    visibility: hidden !important;
                }
                
                /* 2. Tembak mati kotak header biru monitoring atas beserta jam sistem real-time */
                [data-testid="stHeader"],
                header,
                .stAppHeader,
                div[data-testid="stElementContainer"]:has(h1),
                div.stBlock:first-child,
                div[data-testid="stVerticalBlock"] > div:first-child,
                .element-container:has(.stMarkdown h1) {
                    display: none !important;
                    height: 0px !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    visibility: hidden !important;
                }

                /* 3. Ratakan lembar kerja utama agar melar penuh 100% memenuhi monitor PC / HP */
                .main .block-container { 
                    background-color: #090d16 !important; 
                    min-height: 100vh !important; 
                    max-width: 600px !important; 
                    margin: 0 auto !important; 
                    padding-top: 2% !important; 
                    box-sizing: border-box !important;
                }
                
                /* 4. Bersihkan margin hantu Streamlit agar posisi judul Guild License naik seimbang */
                div[data-testid="stVerticalBlock"] {
                    gap: 0rem !important;
                }

                /* ========================================================================= */
                /* 🎴 ENGINE UTAMA STYLE KARTU 3D MEDIEVAL */
                /* ========================================================================= */
                .rpg-card-fullscreen-container { text-align: center; font-family: monospace; width: 100%; margin: 0 auto; }
                .rpg-header-title { color: #fbbf24 !important; font-size: 23px !important; text-shadow: 0 0 10px rgba(251,191,36,0.3) !important; margin: 0 0 5px 0 !important; font-weight: 900 !important; }
                .rpg-header-sub { color: #475569 !important; font-size: 11px !important; margin: 0 0 15px 0 !important; }
                
                .flip-card-wrapper { background-color: transparent !important; width: 330px; height: 520px; perspective: 1000px; margin: 15px auto; cursor: pointer; display: block; }
                .flip-card-inner { position: relative; width: 100%; height: 100%; text-align: center; transition: transform 0.8s cubic-bezier(0.4, 0, 0.2, 1); transform-style: preserve-3d; }
                
                #card-trigger:checked ~ .flip-card-wrapper .flip-card-inner { transform: rotateY(180deg) !important; }
                
                .card-face { position: absolute; width: 100%; height: 100%; background: linear-gradient(145deg, #111827 0%, #0b0f19 100%) !important; -webkit-backface-visibility: hidden; backface-visibility: hidden; border-radius: 20px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 24px; }
                
                .card-back-design { border: 3px dashed #b45309 !important; box-shadow: 0 8px 25px rgba(0,0,0,0.5), inset 0 0 30px rgba(180, 83, 9, 0.2) !important; color: #b45309 !important; }
                .magic-seal-back { width: 110px; height: 110px; border: 2px dashed #b45309; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 45px; margin-bottom: 20px; }
                
                .card-front-design { border: 4px double #d97706 !important; box-shadow: 0 12px 35px rgba(217, 119, 6, 0.3), inset 0 0 25px rgba(217, 119, 6, 0.05) !important; color: white !important; transform: rotateY(180deg); justify-content: flex-start !important; padding-top: 35px !important; }
                .card-front-design::before { content: "⚜️"; position: absolute; top: 12px; font-size: 18px; color: #d97706; filter: drop-shadow(0 0 5px #d97706); }
                
                .char-avatar-box { width: 65px; height: 65px; border-radius: 50%; border: 2px solid #d97706; background: #151d30; display: flex; justify-content: center; align-items: center; font-size: 30px; margin-bottom: 12px; box-shadow: 0 0 12px rgba(217, 119, 6, 0.4); }
                .char-name-plate { background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); border: 1px solid #d97706; border-radius: 6px; padding: 4px 25px; box-shadow: 0 0 10px rgba(217, 119, 6, 0.2); margin-bottom: 4px; }
                .char-hero-name { color: #ffffff !important; font-size: 24px !important; font-weight: 900 !important; margin: 0 !important; letter-spacing: 2px !important; text-shadow: 0 0 8px rgba(255,255,255,0.2) !important; }
                .char-hero-level-badge { background: linear-gradient(90deg, rgba(180, 83, 9, 0.3), rgba(217, 119, 6, 0.15)); color: #fbbf24; font-size: 11px; font-weight: 800; padding: 4px 16px; border-radius: 4px; border: 1px solid #d97706; margin-bottom: 25px; letter-spacing: 0.8px; box-shadow: inset 0 0 5px rgba(0,0,0,0.5); }
                
                .rpg-stat-container { width: 100%; margin-bottom: 14px; text-align: left; }
                .rpg-stat-header { display: flex; justify-content: space-between; color: #94a3b8; font-size: 11px; font-weight: bold; margin-bottom: 5px; font-family: monospace; letter-spacing: 0.5px; }
                
                .rpg-bar-bg { background-color: #05070a !important; height: 14px; border-radius: 4px; overflow: hidden; border: 1px solid rgba(217, 119, 6, 0.25); box-shadow: inset 0 3px 6px rgba(0,0,0,0.8); }
                .rpg_bar_fill_psm { background: linear-gradient(90deg, #ef4444, #ff8080) !important; }
                .rpg_bar_fill_pps { background: linear-gradient(90deg, #3b82f6, #60a5fa) !important; }
                .rpg_bar_fill_sueger { background: linear-gradient(90deg, #10b981, #34d399) !important; }
                .rpg-exp-fill {background: linear-gradient(90deg, #a855f7, #d8b4fe) !important; }
                .avatar-holder-bottom { width: 65px; height: 65px; border-radius: 50%; border: 3px solid #d97706; background-color: #0b0f19; position: absolute; bottom: -32px; left: 50%; transform: translateX(-50%); display: flex; justify-content: center; align-items: center; font-size: 28px; box-shadow: 0 8px 20px rgba(217, 119, 6, 0.5), inset 0 0 10px rgba(217, 119, 6, 0.2); z-index: 100; }

                .rpg-exp-fill {
                    /* 🎯 FIX WARNA BAR EXP: Dipaksa keluar menggunakan warna Ungu Neon Magic */
                    background: linear-gradient(90deg, #a855f7, #d8b4fe) !important; 
                    height: 100% !important;
                    border-radius: 4px !important;
                    display: block !important;
                    box-shadow: 0 0 10px rgba(168, 85, 247, 0.6) !important;
                }
                
                /* ========================================================================= */
                /* 🏆 CSS LENCANA SEPARASI (2 GAMBAR TERPISAH - FIXED SEJAJAR SIMETRIS)      */
                /* ========================================================================= */
                .rpg-dual-badge-row {
                    display: flex !important;
                    justify-content: space-around !important;
                    align-items: center !important;
                    width: 100% !important;
                    margin: 20px auto 10px auto !important;
                    box-sizing: border-box !important;
                }
                
                .rpg-badge-item {
                    display: flex !important;
                    flex-direction: column !important;
                    align-items: center !important;
                    width: 45% !important;
                }
                
                /* 🎯 FIX GESER KANAN: Khusus mendorong kontainer kanan agar lebih melebar ke kanan seimbang */
                .rpg-dual-badge-row .rpg-badge-item:nth-child(2) {
                    margin-left: 10px !important;
                }
                
                .rpg-emblem-wrapper {
                    background-repeat: no-repeat !important;
                    background-size: contain !important; /* Otomatis pas tanpa terpotong */
                    background-position: center !important; /* Terkunci di tengah wadah */
                    width: 110px !important;
                    height: 75px !important; 
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    position: relative !important;
                    mix-blend-mode: screen !important; 
                }
                
                /* Memanggil link 2 gambar terpisah Anda dari GitHub */
                .emblem-left {
                    background-image: url("https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/kiri.png") !important; 
                }
                
                .emblem-right {
                    background-image: url("https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/kanan.png") !important; 
                }
                
                /* Pengaturan teks neon otomatis seragam */
                .rpg-emblem-text {
                    color: #00ffff !important; 
                    font-size: 14px !important;
                    font-weight: 900 !important;
                    font-family: 'Courier New', monospace !important;
                    display: inline-block !important;
                    margin-top: 4px !important; /* Menurunkan angka pas di tengah lingkaran */
                    
                    text-shadow: 0 0 5px #00ffff, 
                                 0 0 10px #00ffff, 
                                 0 0 20px #00ffff, 
                                 0 0 4px #000000 !important;
                }
                
                /* Jika tinggi pusat teks di gambar kanan (segi enam) dirasa berbeda, dikunci di sini */
                .emblem-right .rpg-emblem-text {
                    margin-top: 4px !important;
                }
                
                .rpg-emblem-label {
                    color: #475569 !important;
                    font-size: 9px !important;
                    font-weight: bold !important;
                    letter-spacing: 0.8px !important;
                    margin-top: 5px !important;
                    font-family: monospace !important;
                    text-align: center !important;
                }

                /* ========================================================================= */
                /* 👑 TOMBOL NATIVE KEMBALI (EDISI RE-DESIGN PREMIUM MEDIEVAL & SIMETRIS)    */
                /* ========================================================================= */
                .rpg-back-btn-box {
                    max-width: 330px !important;
                    margin: 55px auto 30px auto !important; /* FIXED: Dinaikkan ke 55px agar tidak menabrak avatar bawah kartu */
                    padding: 0 5px !important;
                    box-sizing: border-box !important;
                }

                
                .rpg-back-btn-box div.stButton > button { 
                    background: linear-gradient(135deg, rgba(180, 83, 9, 0.15) 0%, rgba(180, 83, 9, 0.3) 100%) !important; 
                    color: #fbbf24 !important; 
                    border: 2px solid #b45309 !important; 
                    border-radius: 12px !important; 
                    font-family: monospace !important; 
                    font-size: 13px !important; 
                    font-weight: bold !important; 
                    padding: 12px 0px !important; 
                    letter-spacing: 1px !important;
                    box-shadow: 0 4px 15px rgba(180, 83, 9, 0.15) !important;
                    transition: all 0.25s ease-in-out !important;
                    width: 100% !important;
                    display: block !important;
                }
                
                .rpg-back-btn-box div.stButton > button:hover { 
                    background: #b45309 !important; 
                    color: #090d16 !important; 
                    box-shadow: 0 0 25px rgba(180, 83, 9, 0.6) !important;
                    transform: translateY(-2px) !important;
                }
            </style>
            """, 
            unsafe_allow_html=True
        )
        
        # Cetak kontainer dan tombol resmi Streamlit Anda
        st.markdown("<div class='rpg-back-btn-box'>", unsafe_allow_html=True)
        if st.button("⬅️ KEMBALI KE KEMAH PERSIAPAN", use_container_width=True, key="btn_close_status"):
            st.session_state["current_camp_menu"] = "main"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Pemotongan aliran halaman utama secara resmi
        st.stop()
        
        # 🎨 PERBAIKAN MUTLAK: Memaksa lebar bar melar 100% dan memunculkan warnanya
        st.markdown(
            """
            <style>
                /* 1. Paksa kontainer statistik agar melebar penuh memenuhi kartu */
                .rpg-stat-container {
                    width: 100% !important;
                    display: block !important;
                }

                /* 2. Berikan tinggi pada bar pengisi agar tidak mengkerut */
                .rpg-bar-fill-psm, .rpg-bar-fill-pps, .rpg-bar-fill-sueger {
                    height: 100% !important;
                    border-radius: 4px !important;
                    display: block !important;
                }

                /* 3. Suntikkan warna gradasi asli pahlawan Anda */
                .rpg-bar-fill-psm { background: linear-gradient(90deg, #ef4444, #ff8080) !important; }
                .rpg-bar-fill-pps { background: linear-gradient(90deg, #3b82f6, #60a5fa) !important; }
                .rpg-bar-fill-sueger { background: linear-gradient(90deg, #10b981, #34d399) !important; }
            </style>
            """,
            unsafe_allow_html=True
        )

    # 🛡️ JALUR B: HALAMAN UTAMA STATISTIK UTAMA (VIEW STATS)
    elif st.session_state["current_camp_menu"] == "view_stats":
        st.markdown(
            """
            <style>
                .main .block-container { background-color: #090d16 !important; min-height: 100vh !important; max-width: 650px !important; margin: 0 auto !important; padding-top: 5% !important; }
                [data-testid="stSidebar"] { display: none !important; }
                [data-testid="stHeader"] { display: none !important; }
            </style>
            """, 
            unsafe_allow_html=True
        )
        st.markdown("<h2 style='color: #d97706; font-family: monospace; text-align: center; text-shadow: 0 0 10px rgba(217,119,6,0.4);'>🛡️ HERO STATUS MENU 🛡️</h2>", unsafe_allow_html=True)
        st.info("Halaman view statistik utama berhasil dikunci! Desain isian atribut bar dan ornamen emas menyusul sesuai pesanan Anda berikutnya.")
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("⬅️ KEMBALI KE GULUNGAN KARTU", use_container_width=True, key="btn_back_to_card"):
            st.session_state["current_camp_menu"] = "status"
            st.rerun()
        st.stop()


    # =========================================================================
    # 🎯 JALUR D: MENU INTERAKTIF QUIZ CAMPAIGN (STRUKTUR SINKRON & BERSIH)
    # =========================================================================
    elif st.session_state.get("current_camp_menu") == "quiz_campaign":
        
        # 👑 KUNCI INITIAL STATE: Jika memori kosong, paksa ke lobby resepsionis
        if "campaign_sub_page" not in st.session_state:
            st.session_state["campaign_sub_page"] = "resepsionis_utama"
        # State untuk Hall of Fame PSM
        if "hof_psm_selected" not in st.session_state:
            st.session_state["hof_psm_selected"] = 0
        if "hof_psm_data" not in st.session_state:
            st.session_state["hof_psm_data"] = None

        # =========================================================================
        # 🎨 1. SUNTIKKAN SISI CSS FULLSCREEN SEJAJAR (BERSIH DARI NEON BIRU)
        # =========================================================================
        st.markdown(
            """
            <style>
                /* Kunci Fullscreen Web, Android, & iOS */
                [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], .stSidebar, button[title="Expand sidebar"] { 
                    display: none !important; width: 0px !important;
                }
                
                /* Hapus header bawaan Streamlit */
                [data-testid="stHeader"], header, .stAppHeader {
                    display: none !important; height: 0px !important; margin: 0 !important;
                }
                
                .main .block-container { 
                    background-color: #090d16 !important; min-height: 100vh !important; max-width: 650px !important; margin: 0 auto !important; padding-top: 5% !important; box-sizing: border-box !important;
                }
                div[data-testid="stVerticalBlock"] { gap: 0rem !important; }

                /* Tema Lobby Resepsionis */
                .guild-lobby-title { text-align: center; color: #fbbf24 !important; font-family: monospace; font-size: 24px !important; font-weight: 900 !important; text-shadow: 0 0 12px rgba(251,191,36,0.4) !important; margin: 0 0 5px 0 !important; }
                .guild-lobby-sub { text-align: center; color: #475569 !important; font-size: 11px !important; margin: 0 0 25px 0 !important; font-family: monospace; }
                
                /* ========================================================================= */
                /* 🪵 PAKSA SEMUA TOMBOL MENJADI PAPAN KAYU ANTIK (BASMI TOTAL NEON BIRU)     */
                /* ========================================================================= */
                .stButton button, 
                div[data-testid="stColumn"] button {
                    background: linear-gradient(135deg, #4a3319 0%, #2c1d0c 100%) !important;
                    color: #e2d9c5 !important;
                    border: 2px solid #5c4033 !important;
                    border-top: 2px solid #735137 !important;
                    border-bottom: 2px solid #1a1107 !important;
                    border-radius: 6px !important;
                    box-shadow: 0 6px 15px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.1) !important;
                    font-family: 'Courier New', monospace !important;
                    font-weight: bold !important;
                    text-shadow: 0 1px 2px rgba(0,0,0,0.8) !important;
                    transition: all 0.2s ease !important;
                }
                
                /* Efek saat tombol kayu ditekan */
                .stButton button:active, 
                div[data-testid="stColumn"] button:active {
                    background: linear-gradient(135deg, #2c1d0c 0%, #1a1107 100%) !important;
                    transform: translateY(2px) !important;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.8), inset 0 2px 4px rgba(0,0,0,0.5) !important;
                    border-color: #3d2b1f !important;
                    color: #b5a995 !important;
                }

                /* Hapus sisa efek hover biru neon pada tombol */
                .stButton button:hover, 
                div[data-testid="stColumn"] button:hover {
                    border-color: #735137 !important;
                    color: #ffffff !important;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.7) !important;
                }

                /* ========================================================================= */
                /* 📖 ANIMASI & STRUKTUR BUKU TERBUKA (PERKAMEN KUNO DENGAN EFEK 3D FLIP)    */
                /* ========================================================================= */
                @keyframes flipPageLeft {
                    0% { transform: rotateY(-90deg); opacity: 0; }
                    100% { transform: rotateY(0deg); opacity: 1; }
                }

                @keyframes flipPageRight {
                    0% { transform: rotateY(90deg); opacity: 0; }
                    100% { transform: rotateY(0deg); opacity: 1; }
                }

                .kitab-misi-page-wrapper .guild-lobby-title {
                    text-align: center;
                    font-family: 'Courier New', monospace;
                    font-weight: 900;
                    color: #b45309;
                    margin-bottom: 2px;
                    text-shadow: 0 1px 2px rgba(0,0,0,0.2);
                }
                .kitab-misi-page-wrapper .guild-lobby-sub {
                    text-align: center;
                    font-family: 'Courier New', monospace;
                    font-size: 11px;
                    color: #78716c;
                    margin-bottom: 20px;
                    font-style: italic;
                }

                .kitab-misi-page-wrapper .rpg-open-book-container { 
                    background: #f4eae1 !important; 
                    border: 4px solid #5c4033 !important; 
                    border-radius: 12px !important; 
                    box-shadow: 0 15px 35px rgba(0,0,0,0.6) !important; 
                    display: flex !important; 
                    min-height: 380px !important; 
                    max-height: 420px !important;
                    position: relative !important; 
                    overflow: hidden !important; 
                    width: 100% !important; 
                    max-width: 700px !important; 
                    margin: 0 auto !important; 
                    perspective: 1200px !important; 
                }
                
                .kitab-misi-page-wrapper .rpg-open-book-container::before { 
                    content: "" !important; 
                    position: absolute !important; 
                    top: 0 !important; 
                    left: 50% !important; 
                    width: 4px !important; 
                    height: 100% !important; 
                    background: linear-gradient(90deg, rgba(0,0,0,0.2), rgba(0,0,0,0.4), rgba(0,0,0,0.2)) !important; 
                    box-shadow: 0 0 10px rgba(0,0,0,0.4) !important; 
                    z-index: 5 !important; 
                }
                
                .kitab-misi-page-wrapper .rpg-book-page { 
                    width: 50% !important; 
                    padding: 24px 18px !important; 
                    box-sizing: border-box !important; 
                    display: flex !important; 
                    flex-direction: column !important; 
                    justify-content: flex-start !important; 
                    color: #2b1d0c !important; 
                    font-family: 'Courier New', monospace !important; 
                    overflow-y: auto;
                }

                .kitab-misi-page-wrapper .open-page-title { 
                    text-align: center !important; 
                    font-size: 13px !important; 
                    font-weight: 900 !important; 
                    margin: 0 0 2px 0 !important; 
                    color: #854d0e !important; 
                    text-transform: uppercase;
                }
                .kitab-misi-page-wrapper .open-page-sub { 
                    text-align: center !important; 
                    font-size: 9.5px !important; 
                    color: #78716c !important; 
                    margin: 0 0 10px 0 !important; 
                    font-style: italic !important; 
                }
                .kitab-misi-page-wrapper .open-book-divider { 
                    border-bottom: 2px double #854d0e !important; 
                    margin-bottom: 15px !important; 
                    width: 100% !important; 
                }
                .kitab-misi-page-wrapper .open-stat-row { 
                    display: flex !important; 
                    justify-content: space-between !important; 
                    align-items: center !important;
                    font-size: 10px !important; 
                    font-weight: bold !important; 
                    margin-bottom: 10px !important; 
                    border-bottom: 1px dashed rgba(133,77,14,0.15) !important; 
                    padding-bottom: 4px !important; 
                }
                
                /* 🏅 KELAS KHUSUS PODIUM & MEDAL TEMA MEDIEVAL */
                .rank-1 { background: rgba(234, 179, 8, 0.2); border-left: 4px solid #eab308; padding-left: 6px; border-radius: 4px; }
                .rank-2 { background: rgba(148, 163, 184, 0.2); border-left: 4px solid #94a3b8; padding-left: 6px; border-radius: 4px; }
                .rank-3 { background: rgba(217, 119, 6, 0.2); border-left: 4px solid #d97706; padding-left: 6px; border-radius: 4px; }

                .kitab-misi-page-wrapper .open-page-footer { 
                    margin-top: auto !important; 
                    font-size: 9px !important; 
                    color: #78716c !important; 
                    text-align: center !important; 
                    font-weight: bold !important; 
                }

                /* ✨ GAYA TOMBOL RPG KULIT */
                .kitab-misi-page-wrapper div.stButton > button {
                    background: linear-gradient(135deg, #3d2b1f 0%, #2b1d0c 100%);
                    color: #fdf8f2;
                    border: 2px solid #b45309;
                    border-radius: 8px;
                    font-family: 'Courier New', monospace;
                    font-weight: bold;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.4);
                    transition: all 0.2s ease-in-out;
                }
                .kitab-misi-page-wrapper div.stButton > button:hover {
                    background: linear-gradient(135deg, #5c4033 0%, #3d2b1f 100%);
                    border-color: #d97706;
                    color: #ffffff;
                    box-shadow: 0 6px 10px rgba(0,0,0,0.6);
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # =========================================================================
        # 👑 NAVIGATION STRUKTUR INTERNAL: JALUR NAVIGASI UTAMA BERURUTAN (FIXED)
        # =========================================================================
                         
        # =========================================================================
        # 🚪 MEJA RESEPSIONIS UTAMA — VERSI FINAL (RAPAT)
        # =========================================================================
        
        if st.session_state.get("campaign_sub_page", "resepsionis_utama") == "resepsionis_utama":
        
            url_gambar_latar = "https://i.imgur.com/9HTvsmJ.jpeg"
        
            st.markdown(
                f"""
                <style>
                    /* 🌌 BACKGROUND */
                    .stApp {{
                        background-image: linear-gradient(rgba(15, 23, 42, 0.82), rgba(15, 23, 42, 0.82)), url("{url_gambar_latar}") !important;
                        background-size: cover !important;
                        background-position: center !important;
                        background-repeat: no-repeat !important;
                        background-attachment: fixed !important;
                    }}
        
                    /* 🏗️ KARTU */
                    .rpg-card-box {{
                        background: linear-gradient(135deg, #0f172a 0%, #1e1b18 100%) !important;
                        border: 2px solid #b45309 !important;
                        border-top: 6px solid #d97706 !important;
                        border-radius: 12px !important;
                        padding: 25px 20px 20px 20px !important;
                        margin-bottom: 0 !important;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.6), inset 0 0 15px rgba(251, 191, 36, 0.02) !important;
                        text-align: center;
                        max-width: 480px;
                        margin-left: auto;
                        margin-right: auto;
                    }}
        
                    /* 🎨 WARNA KARTU */
                    .rpg-card-blue {{
                        border: 2px solid #1d4ed8 !important;
                        border-top: 6px solid #3b82f6 !important;
                    }}
                    .rpg-card-purple {{
                        border: 2px solid #7c3aed !important;
                        border-top: 6px solid #a855f7 !important;
                    }}
                    .rpg-card-gold {{
                        border: 2px solid #b45309 !important;
                        border-top: 6px solid #d97706 !important;
                    }}
        
                    /* ✨ EMOJI */
                    .rpg-card-emoji {{
                        font-size: 38px;
                        line-height: 1;
                        margin-bottom: 12px;
                        display: inline-block;
                        animation: floatScrollBtn 2.5s infinite ease-in-out;
                    }}
        
                    /* 📘 JUDUL */
                    .rpg-card-title {{
                        font-family: monospace;
                        font-size: 15px;
                        font-weight: bold;
                        color: #fbbf24;
                        margin-bottom: 10px;
                        letter-spacing: 0.5px;
                    }}
        
                    /* 📝 DESKRIPSI */
                    .rpg-card-desc {{
                        font-family: monospace;
                        font-size: 12px;
                        line-height: 1.6;
                        color: #cbd5e1;
                        margin-bottom: 0;
                    }}
        
                    /* 🎯 WRAPPER TOMBOL — jarak diperkecil jadi 3px */
                    div[data-testid="stButton"] {{
                        max-width: 480px !important;
                        margin: 14px auto 30px auto !important;   /* ← 3px, lebih rapat */
                        padding: 0 !important;
                    }}
        
                    /* 🔘 TOMBOL */
                    div[data-testid="stButton"] > button {{
                        background: rgba(180, 83, 9, 0.15) !important;
                        border: 2px solid #b45309 !important;
                        border-radius: 12px !important;
                        color: #fde047 !important;
                        font-family: monospace !important;
                        font-size: 13px !important;
                        font-weight: bold !important;
                        padding: 12px 20px !important;
                        transition: all 0.3s ease !important;
                        width: 100% !important;
                        display: block !important;
                    }}
        
                    /* 🔵 TOMBOL 1 — BIRU */
                    .st-key-btn_go_to_jurnal_buruan_camp_style button {{
                        background: rgba(29, 78, 216, 0.18) !important;
                        border: 2px solid #1d4ed8 !important;
                        color: #93c5fd !important;
                    }}
                    .st-key-btn_go_to_jurnal_buruan_camp_style button:hover {{
                        background: #1d4ed8 !important;
                        color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
                    }}
        
                    /* 🟣 TOMBOL 2 — UNGU */
                    .st-key-btn_go_to_kitab_misi_camp_style button {{
                        background: rgba(124, 58, 237, 0.18) !important;
                        border: 2px solid #7c3aed !important;
                        color: #d8b4fe !important;
                    }}
                    .st-key-btn_go_to_kitab_misi_camp_style button:hover {{
                        background: #7c3aed !important;
                        color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(168, 85, 247, 0.4) !important;
                    }}
        
                    /* 🟡 TOMBOL 3 — EMAS */
                    .st-key-btn_go_to_hall_of_fame button {{
                        background: rgba(180, 83, 9, 0.18) !important;
                        border: 2px solid #b45309 !important;
                        color: #fde047 !important;
                    }}
                    .st-key-btn_go_to_hall_of_fame button:hover {{
                        background: #b45309 !important;
                        color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(251, 191, 36, 0.4) !important;
                    }}
        
                    /* ↩️ TOMBOL KEMBALI */
                    .st-key-btn_exit_reception_lobby_camp_style button {{
                        background: rgba(100, 116, 139, 0.15) !important;
                        border: 2px solid #475569 !important;
                        border-radius: 12px !important;
                        color: #cbd5e1 !important;
                        padding: 12px 20px !important;
                        font-family: monospace !important;
                        font-size: 13px !important;
                        font-weight: bold !important;
                        transition: all 0.3s ease !important;
                    }}
                    .st-key-btn_exit_reception_lobby_camp_style button:hover {{
                        background: #475569 !important;
                        color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(100, 116, 139, 0.4) !important;
                    }}
        
                    /* 🎬 ANIMASI */
                    @keyframes floatScrollBtn {{
                        0%, 100% {{ transform: translateY(0); filter: drop-shadow(0 0 4px rgba(251,191,36,0.3)); }}
                        50%      {{ transform: translateY(-4px); filter: drop-shadow(0 0 10px rgba(251,191,36,0.6)); }}
                    }}
                </style>
                """,
                unsafe_allow_html=True
            )
        
            # 🏷️ JUDUL
            st.markdown(
                "<h2 style='text-shadow: 0 0 15px rgba(251,191,36,0.5); color: #fef08a; "
                "text-align: center; font-family: monospace; margin-bottom: 5px;'>"
                "🛎️ GUILD RECEPTION DESK 🛎️</h2>",
                unsafe_allow_html=True
            )
            st.markdown(
                "<p style='color: #cbd5e1; text-align: center; font-family: monospace; "
                "margin-bottom: 30px; font-size: 13px;'>"
                "Pilih gulungan maklumat di bawah ini untuk memeriksa catatan log petualangan Anda.</p>",
                unsafe_allow_html=True
            )
        
            # 🔵 KARTU 1
            st.markdown("""
                <div class='rpg-card-box rpg-card-blue'>
                    <div class='rpg-card-emoji'>📘</div>
                    <div class='rpg-card-title'>JURNAL BURUAN INDIVIDU</div>
                    <div class='rpg-card-desc'>Akses lembar arsip report pribadi Anda untuk meninjau akumulasi poin hasil buruan, tingkat level pahlawan, dan rekap performa penjualan harian Anda.</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Buka Catatan ➔", key="btn_go_to_jurnal_buruan_camp_style", use_container_width=True):
                st.session_state["campaign_sub_page"] = "view_buku_pencapaian"
                st.rerun()
        
            # 🟣 KARTU 2
            st.markdown("""
                <div class='rpg-card-box rpg-card-purple'>
                    <div class='rpg-card-emoji'>🔮 ⚔️</div>
                    <div class='rpg-card-title'>KITAB MISI & QUIZ GUILD</div>
                    <div class='rpg-card-desc'>Cek papan pengumuman maklumat aliansi untuk memantau target pencapaian toko harian, daftar quest mingguan PSM, serta tantangan kuis berkala.</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Periksa Kitab ➔", key="btn_go_to_kitab_misi_camp_style", use_container_width=True):
                st.session_state["campaign_sub_page"] = "view_buku_tugas"
                st.rerun()
        
            # 🟡 KARTU 3
            st.markdown("""
                <div class='rpg-card-box rpg-card-gold'>
                    <div class='rpg-card-emoji'>🏆 ✨</div>
                    <div class='rpg-card-title'>HALL OF FAME ALIANSI</div>
                    <div class='rpg-card-desc'>Lihat papan prasasti pahlawan tertinggi untuk memeriksa daftar peringkat petualang legendaris yang memiliki akumulasi buruan paling perkasa musim ini.</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("Lihat Papan Peringkat ➔", key="btn_go_to_hall_of_fame", use_container_width=True):
                # 🎬 ANIMASI MASUK ALTAR HALL OF FAME
                placeholder_altar = st.empty()
                with placeholder_altar.container():
                    # 1️⃣ STYLE BLOCK — TERPISAH, TIDAK NESTED DI DALAM DIV
                    st.markdown(
                        """
                        <style>
                            @keyframes altarBlink { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
                            @keyframes altarSpinCW { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                            @keyframes altarSpinCCW { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
                            @keyframes altarPulse {
                                0%, 100% { transform: scale(1); filter: drop-shadow(0 0 15px #d97706); }
                                50% { transform: scale(1.12); filter: drop-shadow(0 0 30px #fbbf24); }
                            }
                            @keyframes altarSparkFloat {
                                0% { transform: translateY(0) scale(0.6); opacity: 0; }
                                50% { opacity: 1; }
                                100% { transform: translateY(-60px) scale(1.2); opacity: 0; }
                            }
                            @keyframes altarShimmer {
                                0% { background-position: 0% 50%; }
                                100% { background-position: 300% 50%; }
                            }
                            @keyframes altarGrowFill {
                                0% { width: 0%; }
                                100% { width: 100%; }
                            }

                            .altar-overlay {
                                background-color: #0a0d1a;
                                position: fixed; top: 0; left: 0;
                                width: 100vw; height: 100vh;
                                z-index: 999999;
                                display: flex; flex-direction: column;
                                justify-content: center; align-items: center;
                                color: white; overflow: hidden;
                            }
                            .altar-portal-container {
                                position: relative; width: 220px; height: 220px;
                                display: flex; justify-content: center; align-items: center;
                            }
                            .altar-outer-ring {
                                transform-origin: 110px 110px;
                                animation: altarSpinCW 10s infinite linear;
                                filter: drop-shadow(0 0 12px #d97706);
                            }
                            .altar-mid-ring {
                                transform-origin: 110px 110px;
                                animation: altarSpinCCW 6s infinite linear;
                                filter: drop-shadow(0 0 10px #fbbf24);
                            }
                            .altar-inner-ring {
                                transform-origin: 110px 110px;
                                animation: altarSpinCW 4s infinite linear;
                                filter: drop-shadow(0 0 8px #fef08a);
                            }
                            .altar-triangle {
                                transform-origin: 110px 110px;
                                animation: altarSpinCCW 12s infinite linear;
                                filter: drop-shadow(0 0 10px #d97706);
                            }
                            .altar-core-icon {
                                position: absolute; font-size: 65px; z-index: 10;
                                animation: altarPulse 2s infinite ease-in-out;
                            }
                            .altar-spark {
                                position: absolute; color: #fbbf24; font-size: 16px; font-weight: bold;
                                filter: drop-shadow(0 0 8px #fef08a);
                            }
                            .altar-spark-1 { top: 20px; left: 50px; animation: altarSparkFloat 2.5s infinite ease-out; }
                            .altar-spark-2 { top: 30px; right: 55px; animation: altarSparkFloat 3s infinite ease-out 0.5s; }
                            .altar-spark-3 { bottom: 40px; left: 80px; animation: altarSparkFloat 2.8s infinite ease-out 1s; }
                            .altar-title {
                                color: #fbbf24; font-family: monospace;
                                animation: altarBlink 1.5s infinite;
                                font-size: 22px; margin-top: 40px;
                                letter-spacing: 2px;
                                text-shadow: 0 0 20px rgba(251,191,36,0.6);
                                text-align: center; padding: 0 20px;
                            }
                            .altar-sub {
                                color: #64748b; font-size: 13px; margin-top: 8px;
                                font-family: monospace; text-align: center; padding: 0 20px;
                            }
                            .altar-progress-wrapper { margin-top: 30px; width: 280px; }
                            .altar-progress-bg {
                                width: 100%; height: 14px;
                                background: rgba(15, 23, 42, 0.9);
                                border: 2px solid #b45309; border-radius: 8px;
                                overflow: hidden;
                                box-shadow: inset 0 0 10px rgba(0,0,0,0.8), 0 0 15px rgba(180, 83, 9, 0.3);
                            }
                            .altar-progress-fill {
                                height: 100%; width: 0%; border-radius: 6px;
                                background: linear-gradient(90deg, #78350f, #d97706, #fbbf24, #fef08a, #fbbf24, #d97706, #78350f);
                                background-size: 300% 100%;
                                animation: altarShimmer 1.5s infinite linear, altarGrowFill 2.2s forwards ease-out;
                                box-shadow: 0 0 15px rgba(251, 191, 36, 0.8);
                            }
                            .altar-progress-pct {
                                color: #fbbf24; font-family: monospace;
                                font-size: 12px; font-weight: bold;
                                text-align: center; margin-top: 8px;
                            }
                        </style>
                        """,
                        unsafe_allow_html=True
                    )

                    # 2️⃣ HTML DIV — TERPISAH, LEBIH SEDERHANA
                    st.markdown(
                        """
                        <div class="altar-overlay">
                            <div class="altar-portal-container">
                                <svg width="220" height="220" viewBox="0 0 220 220" style="position: absolute;">
                                    <circle cx="110" cy="110" r="100" class="altar-outer-ring" stroke="#d97706" stroke-width="3" stroke-dasharray="15, 10" fill="none" />
                                    <circle cx="110" cy="110" r="75" class="altar-mid-ring" stroke="#fbbf24" stroke-width="2" stroke-dasharray="5, 8" fill="none" />
                                    <circle cx="110" cy="110" r="50" class="altar-inner-ring" stroke="#fef08a" stroke-width="2" fill="none" />
                                    <polygon points="110,30 180,150 40,150" class="altar-triangle" stroke="#d97706" stroke-width="1.5" fill="none" />
                                </svg>
                                <div class="altar-core-icon">🏛️</div>
                                <div class="altar-spark altar-spark-1">✦</div>
                                <div class="altar-spark altar-spark-2">✦</div>
                                <div class="altar-spark altar-spark-3">✦</div>
                            </div>
                            <h1 class="altar-title">🚪 MEMBUKA PINTU ALTAR... 🚪</h1>
                            <p class="altar-sub">Menyatukan cahaya prasasti kuno dan mengaktifkan ruang Hall of Fame...</p>
                            <div class="altar-progress-wrapper">
                                <div class="altar-progress-bg">
                                    <div class="altar-progress-fill"></div>
                                </div>
                                <div class="altar-progress-pct">ACTIVATING: 100%</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    # ⏱️ Tunggu animasi selesai (2.2 detik)
                    time.sleep(2.4)

                placeholder_altar.empty()

                st.session_state["campaign_sub_page"] = "view_hall_of_fame"
                st.session_state["hof_sub_page"] = None
                st.rerun()
                
            # ↩️ KEMBALI
            st.markdown("<br><hr style='border-color: rgba(251, 191, 36, 0.3); margin: 15px 0;'><br>", unsafe_allow_html=True)
            if st.button("⬅️ KEMBALI KE BERANDA KOTA", use_container_width=True, key="btn_exit_reception_lobby_camp_style"):
                st.session_state.current_camp_menu = "main"
                st.rerun()
        
            st.stop()

        # =========================================================================
        # 📘 JURNAL BURUAN INDIVIDU (PEMISAHAN RANKING: TINGKAT LEVEL = RANKING PPS, RANKING PENJUALAN = RANKING PSM)
        # =========================================================================
        elif st.session_state.get("campaign_sub_page") == "view_buku_pencapaian":
            
            # 🛡️ PROTEKSI HALAMAN: Set halaman awal ke 1 jika baru masuk atau belum terdefinisi
            if "book_page_number" not in st.session_state:
                st.session_state["book_page_number"] = 1
                
            current_page = st.session_state.get("book_page_number", 1)
            username_hero = str(st.session_state.get("username", "RIZKI GUNAWAN")).strip().upper()


            # --- 📥 AMBIL DATAFRAME DARI SESSION STATE ---
            df_sales_item = st.session_state.get("sales_item_df", pd.DataFrame())
            sales_personil = st.session_state.get("sales_person_df", pd.DataFrame())
            periods_df = st.session_state.get("periods_df", pd.DataFrame())
            sales_pps_df = st.session_state.get("sales_pps_df", pd.DataFrame())

            # Normalisasi nama kolom ke lowercase
            for df_obj in [df_sales_item, sales_personil, periods_df, sales_pps_df]:
                if not df_obj.empty:
                    df_obj.columns = df_obj.columns.astype(str).str.strip().str.lower()

            # --- 🗓️ AMBIL SELURUH PERIODE DALAM BULAN BERJALAN ---
            today_date = datetime.now().date()
            current_month = today_date.month
            current_year = today_date.year
            
            list_periode_bulan_ini = []
            nama_periode_aktif = today_date.strftime("%B %Y")

            if not periods_df.empty and all(col in periods_df.columns for col in ['period_id', 'start_date']):
                for _, row in periods_df.iterrows():
                    try:
                        p_start = pd.to_datetime(row['start_date'], errors='coerce').date()
                        if pd.notna(p_start) and p_start.month == current_month and p_start.year == current_year:
                            p_id = str(row['period_id']).strip()
                            if p_id not in list_periode_bulan_ini:
                                list_periode_bulan_ini.append(p_id)
                    except Exception:
                        continue
            
            if not list_periode_bulan_ini:
                list_periode_bulan_ini = ["S01"]

            # --- 🔍 1. TARIK DATA DARI SALES_PPS BERDASARKAN KASIR_NAME ---
            total_pwp_val = 0
            total_sg_val = 0
            total_sueger_val = 0
            total_cemilan_val = 0
            total_syarat_sueger = 0
            total_redeem_sueger = 0
            
            log_sueger_collection = []

            if not sales_pps_df.empty and 'kasir_name' in sales_pps_df.columns:
                df_pps_user = sales_pps_df[sales_pps_df['kasir_name'].astype(str).str.strip().str.upper() == username_hero].copy()
                
                if not df_pps_user.empty:
                    for col_num in ['qty_pwp', 'qty_sg', 'syarat_sueger', 'redeem_sueger', 'cemilan_ceban']:
                        if col_num in df_pps_user.columns:
                            df_pps_user[col_num] = pd.to_numeric(df_pps_user[col_num], errors='coerce').fillna(0)

                    total_pwp_val = int(df_pps_user['qty_pwp'].sum()) if 'qty_pwp' in df_pps_user.columns else 0
                    total_sg_val = int(df_pps_user['qty_sg'].sum()) if 'qty_sg' in df_pps_user.columns else 0
                    total_sueger_val = int(df_pps_user['redeem_sueger'].sum()) if 'redeem_sueger' in df_pps_user.columns else 0
                    total_cemilan_val = int(df_pps_user['cemilan_ceban'].sum()) if 'cemilan_ceban' in df_pps_user.columns else 0
                    
                    total_syarat_sueger = df_pps_user['syarat_sueger'].sum() if 'syarat_sueger' in df_pps_user.columns else 0
                    total_redeem_sueger = df_pps_user['redeem_sueger'].sum() if 'redeem_sueger' in df_pps_user.columns else 0

                    # Ekstraksi Baris per Baris (Tanggal, Shift Asli, Syarat, Redeem, & Achievement %)
                    for _, row in df_pps_user.iterrows():
                        tgl_raw = str(row.get('updated_at', '')) or str(row.get('date', ''))
                        
                        shift_raw = "SHIFT 1"
                        for s_col in ['shift_person', 'shift', 'nama_shift']:
                            if s_col in row and pd.notna(row[s_col]) and str(row[s_col]).strip() != "":
                                shift_raw = str(row[s_col]).strip().upper()
                                break
                        
                        syarat_row = int(row.get('syarat_sueger', 0))
                        redeem_row = int(row.get('redeem_sueger', 0))
                        
                        ach_row = (redeem_row / syarat_row * 100) if syarat_row > 0 else 0.0
                        
                        try:
                            parsed_dt = pd.to_datetime(tgl_raw, errors='coerce')
                            if pd.notna(parsed_dt):
                                tgl_str = f"Tgl {parsed_dt.strftime('%d/%m')}"
                            else:
                                tgl_str = "Tgl Khusus"
                        except Exception:
                            tgl_str = "Tgl Khusus"

                        if syarat_row > 0 or redeem_row > 0:
                            log_sueger_collection.append(
                                f'<div class="open-stat-row">'
                                f'<span>{tgl_str} <span style="font-size:7.5px; color:#b45309; background:#fef08a; padding:1px 3px; border-radius:3px;">{shift_raw}</span></span>'
                                f'<span style="color:#0d9488; font-weight:900;">Syarat: {syarat_row} | Redeem: {redeem_row} (<span style="color:#ca8a04;">{ach_row:.0f}%</span>)</span>'
                                f'</div>'
                            )

            if not log_sueger_collection:
                log_sueger_collection.append('<div class="open-stat-row"><span>BELUM ADA ARSIP SUEGER</span><span style="color:#71717a;">-</span></div>')

            # Hitung Achievement % Total Sueger
            achievement_pct = 0.0
            if total_syarat_sueger > 0:
                achievement_pct = (total_redeem_sueger / total_syarat_sueger) * 100
            achievement_str = f"{achievement_pct:.1f}%"

            # --- 🔍 2. HITUNG RANKING PPS (TINGKAT LEVEL) & RANKING PSM (RANKING PENJUALAN) ---
            ranking_pps_val = "#RANK -"
            ranking_psm_val = "#RANK -"

            # A. Hitung Ranking PPS (Total (qty_pwp + qty_sg) dari sales_pps_df)
            if not sales_pps_df.empty and 'kasir_name' in sales_pps_df.columns:
                df_pps_all = sales_pps_df.copy()
                for col_num in ['qty_pwp', 'qty_sg', 'syarat_sueger', 'redeem_sueger']:
                    if col_num in df_pps_all.columns:
                        df_pps_all[col_num] = pd.to_numeric(df_pps_all[col_num], errors='coerce').fillna(0)
                
                df_pps_all['kasir_clean'] = df_pps_all['kasir_name'].astype(str).str.strip().str.upper()
                df_pps_all['total_pwp_sg'] = df_pps_all.get('qty_pwp', 0) + df_pps_all.get('qty_sg', 0)
                
                df_ranked_pps = df_pps_all.groupby('kasir_clean')['total_pwp_sg'].sum().reset_index()
                df_ranked_pps = df_ranked_pps.sort_values(by='total_pwp_sg', ascending=False).reset_index(drop=True)
                df_ranked_pps['rank'] = df_ranked_pps.index + 1
                
                user_pps_row = df_ranked_pps[df_ranked_pps['kasir_clean'] == username_hero]
                if not user_pps_row.empty:
                    ranking_pps_val = f"#RANK {int(user_pps_row['rank'].values[0])}"

            # B. Hitung Qty Penjualan PSM & Ranking PSM (dari sales_personil)
            qty_penjualan_psm_val = 0
            if not sales_personil.empty and 'period_id' in sales_personil.columns and 'person_name' in sales_personil.columns:
                df_sp_all = sales_personil.copy()
                df_sp_all['person_clean'] = df_sp_all['person_name'].astype(str).str.strip().str.upper()
                df_sp_all['actual_qty'] = pd.to_numeric(df_sp_all['actual_qty'], errors='coerce').fillna(0)

                df_sp_bulan_ini = df_sp_all[df_sp_all['period_id'].astype(str).str.strip().isin(list_periode_bulan_ini)]

                df_user_sales = df_sp_bulan_ini[df_sp_bulan_ini['person_clean'] == username_hero]
                if not df_user_sales.empty:
                    qty_penjualan_psm_val = int(df_user_sales['actual_qty'].sum())

                df_ranked_sales = df_sp_bulan_ini.groupby('person_clean')['actual_qty'].sum().reset_index()
                df_ranked_sales = df_ranked_sales.sort_values(by='actual_qty', ascending=False).reset_index(drop=True)
                df_ranked_sales['rank'] = df_ranked_sales.index + 1

                user_sales_rank = df_ranked_sales[df_ranked_sales['person_clean'] == username_hero]
                if not user_sales_rank.empty:
                    ranking_psm_val = f"#RANK {int(user_sales_rank['rank'].values[0])}"

            # C. Ranking Sueger Achievement
            ranking_sueger_val = "#RANK -"
            if not sales_pps_df.empty and 'kasir_name' in sales_pps_df.columns:
                df_ranked_sueger = df_pps_all.groupby('kasir_clean')[['syarat_sueger', 'redeem_sueger']].sum().reset_index()
                df_ranked_sueger['ach_sueger'] = df_ranked_sueger.apply(
                    lambda r: (r['redeem_sueger'] / r['syarat_sueger'] * 100) if r['syarat_sueger'] > 0 else 0.0, axis=1
                )
                df_ranked_sueger = df_ranked_sueger.sort_values(by='ach_sueger', ascending=False).reset_index(drop=True)
                df_ranked_sueger['rank'] = df_ranked_sueger.index + 1

                user_sueger_row = df_ranked_sueger[df_ranked_sueger['kasir_clean'] == username_hero]
                if not user_sueger_row.empty:
                    ranking_sueger_val = f"#RANK {int(user_sueger_row['rank'].values[0])}"

            data_stats = {
                "level": ranking_pps_val,          # Menggunakan Ranking PPS untuk Tingkat Level
                "pwp": f"{total_pwp_val:,} Pts", 
                "sg": f"{total_sg_val:,} Pts", 
                "sueger": f"{total_sueger_val:,} Pts", 
                "cemilan": f"{total_cemilan_val:,} Pts", 
                "achievement": achievement_str,
                "rank_sueger": ranking_sueger_val
            }

            # --- 🔍 3. TARIK TARGET & QTY AKTUAL ITEM TERCAPAI ---
            dict_target_item = {}
            if not df_sales_item.empty and 'period_id' in df_sales_item.columns:
                df_f_item = df_sales_item[df_sales_item['period_id'].astype(str).str.strip().isin(list_periode_bulan_ini)]
                if 'item_name' in df_f_item.columns and 'target_kasir' in df_f_item.columns:
                    df_f_item['target_kasir'] = pd.to_numeric(df_f_item['target_kasir'], errors='coerce').fillna(0)
                    for _, row in df_f_item.iterrows():
                        it_name = str(row['item_name']).strip().upper()
                        tgt_val = pd.to_numeric(row['target_kasir'], errors='coerce') or 0
                        dict_target_item[it_name] = dict_target_item.get(it_name, 0) + int(tgt_val)

            list_item_tercapai_collection = []
            
            if not sales_personil.empty and 'period_id' in sales_personil.columns and 'person_name' in sales_personil.columns:
                df_user_sales_items = sales_personil[
                    (sales_personil['period_id'].astype(str).str.strip().isin(list_periode_bulan_ini)) & 
                    (sales_personil['person_name'].astype(str).str.strip().str.upper() == username_hero)
                ].copy()
                
                if not df_user_sales_items.empty:
                    df_user_sales_items['actual_qty'] = pd.to_numeric(df_user_sales_items['actual_qty'], errors='coerce').fillna(0)

                    if 'item_name' in df_user_sales_items.columns:
                        df_grouped_item = df_user_sales_items.groupby(df_user_sales_items['item_name'].astype(str).str.strip().str.upper())['actual_qty'].sum().reset_index()
                        df_grouped_item.columns = ['item_name', 'actual_qty']
                        
                        for _, row in df_grouped_item.iterrows():
                            nama_item = row['item_name']
                            qty_aktual = int(row['actual_qty'])
                            target_item_ini = dict_target_item.get(nama_item, 0)
                            
                            is_achieved = False
                            if target_item_ini > 0 and qty_aktual >= target_item_ini:
                                is_achieved = True
                            elif target_item_ini == 0 and qty_aktual > 0:
                                is_achieved = True

                            if is_achieved:
                                emoji_status = "🏆 MASTERED"
                                warna_status = "#16a34a"
                                row_html = f'<div class="open-stat-row"><span>📦 {nama_item}</span><span style="color:{warna_status}; font-weight:900;">{qty_aktual} Qty ({emoji_status})</span></div>'
                                list_item_tercapai_collection.append(row_html)

            jumlah_jenis_item_tercapai = len(list_item_tercapai_collection)
            if jumlah_jenis_item_tercapai == 0:
                list_item_tercapai_collection.append('<div class="open-stat-row"><span>📦 BELUM ADA ITEM TERCAPAI</span><span style="color:#71717a;">0 Qty</span></div>')

            # --- 📜 KATA-KATA MOTIVASI ALIANSI ---
            daftar_motivasi = [
                "\"Fokus, bidik target dengan tepat, dan buktikan kemampuan terbaikmu di arena penjualan!\"",
                "\"Tetap semangat ksatria! Konsistensi hari ini adalah kunci kemenangan di akhir bulan.\"",
                "\"Setiap item yang terjual mendekatkanmu pada singgasana juara! Terus berjuang!\"",
                "\"Jangan menyerah pada rintangan kecil, pahlawan sejati selalu bangkit dan melampaui target!\"",
                "\"Langkah kecil setiap hari menghasilkan pencapaian luar biasa. Ayo taklukkan quest hari ini!\""
            ]
            motivasi_terpilih = random.choice(daftar_motivasi)

            # --- ⚙️ SISTEM PAGINASI BUKU ---
            ITEMS_PER_PAGE = 5
            chunked_items = [list_item_tercapai_collection[i:i + ITEMS_PER_PAGE] for i in range(0, len(list_item_tercapai_collection), ITEMS_PER_PAGE)]
            
            book_spreads = []
            
            # Spread 1: Status & Rekap Utama
            book_spreads.append({
                "type": "main_menu",
                "left_title": "⚜️ STATUS PAHLAWAN ⚜️",
                "left_sub": "Catatan Karakter Ksatria",
                "right_title": "⚔️ REKAP REPORT ⚔️",
                "right_sub": "Akumulasi Poin Buruan (1 Bulan)"
            })
            
            # Spread Item Detail
            item_page_pairs = [chunked_items[i:i+2] for i in range(0, len(chunked_items), 2)]
            for idx, pair in enumerate(item_page_pairs):
                left_items_html = "".join(pair[0])
                right_items_html = "".join(pair[1]) if len(pair) > 1 else '<div class="open-stat-row"><span>✨ BAGIAN INI TELAH SELESAI</span><span style="color:#71717a;">-</span></div>'
                
                book_spreads.append({
                    "type": "item_detail",
                    "page_num_left": f"Halaman {(idx*2)+3}",
                    "page_num_right": f"Halaman {(idx*2)+4}",
                    "left_content": left_items_html,
                    "right_content": right_items_html,
                    "sub_title": f"Rincian Quest Bulan {nama_periode_aktif}"
                })
            
            # Spread Terakhir: Log Harian Sueger & Catatan Aliansi
            book_spreads.append({
                "type": "closing_scroll",
                "sueger_html": "".join(log_sueger_collection),
                "motivasi_text": motivasi_terpilih
            })

            max_spread_index = len(book_spreads)
            if current_page > max_spread_index:
                current_page = 1
                st.session_state["book_page_number"] = 1

            current_spread = book_spreads[current_page - 1]

            # --- 🎨 STYLING RPG BUKU ---
            st.markdown(
                """
                <style>
                    div[data-testid="stColumn"] button[key^="btn_desk_nav_"],
                    div[data-testid="stVerticalBlockBorderWrapper"] button[key^="btn_desk_nav_"],
                    .stButton button[key^="btn_desk_nav_"] {
                        width: 100% !important; max-width: 620px !important; margin: 0 auto !important;
                        min-height: 44px !important; height: 44px !important;
                        background: linear-gradient(135deg, #5c4033 0%, #3d2b1f 100%) !important;
                        color: #fef08a !important; border: 2px solid #b45309 !important; border-radius: 8px !important;
                        font-family: monospace !important; font-weight: 900 !important; font-size: 13px !important;
                        letter-spacing: 1px !important; box-shadow: 0 8px 20px rgba(0,0,0,0.6) !important;
                        text-shadow: 0 1px 2px rgba(0,0,0,0.8);
                    }
                    .rpg-open-book-container {
                        background: #fdf8f2 !important; border: 5px solid #3d2b1f !important; border-radius: 12px !important; 
                        box-shadow: 0 20px 40px rgba(0,0,0,0.8), inset 0 0 40px rgba(181, 101, 29, 0.15) !important; 
                        display: flex !important; min-height: 380px !important; max-height: 380px !important; 
                        position: relative !important; overflow: hidden !important; width: 100% !important; max-width: 620px !important; margin: 15px auto !important;
                    }
                    .rpg-open-book-container::before { 
                        content: "" !important; position: absolute !important; top: 0 !important; left: 50% !important; 
                        width: 4px !important; height: 100% !important; background: linear-gradient(90deg, rgba(61,43,31,0.4), rgba(30,20,10,0.7), rgba(61,43,31,0.4)) !important; z-index: 5 !important; 
                    }
                    .rpg-book-page { 
                        width: 50% !important; padding: 18px 12px !important; box-sizing: border-box !important; 
                        display: flex !important; flex-direction: column !important; justify-content: flex-start !important; 
                        color: #2b1d0c !important; font-family: 'Courier New', monospace !important; overflow-y: auto !important;
                    }
                    .open-page-title { text-align: center !important; font-size: 12px !important; font-weight: 900 !important; margin: 0 0 2px 0 !important; color: #854d0e !important; letter-spacing: 0.5px; text-transform: uppercase; }
                    .open-page-sub { text-align: center !important; font-size: 9px !important; color: #78716c !important; margin: 0 0 8px 0 !important; font-style: italic !important; }
                    .open-book-divider { border-bottom: 2px double #b45309 !important; margin-bottom: 8px !important; width: 100% !important; opacity: 0.7; }
                    .open-stat-row { 
                        display: flex !important; justify-content: space-between !important; align-items: center !important; font-size: 9px !important; 
                        font-weight: bold !important; margin-bottom: 7px !important; border-bottom: 1px dashed rgba(133,77,14,0.2) !important; padding-bottom: 3px !important; 
                    }
                    .open-page-footer { margin-top: auto !important; font-size: 9px !important; color: #78716c !important; text-align: center !important; font-weight: bold !important; padding-top: 4px; }
                    .sueger-daily-scroll-box { max-height: 230px !important; overflow-y: auto !important; padding-right: 4px !important; width: 100% !important; }
                    .rpg-open-book-animated { animation: bookOpenFold 0.5s cubic-bezier(0.25, 1, 0.5, 1) forwards; transform-origin: center center; }
                    @keyframes bookOpenFold {
                        0% { transform: scaleX(0.8) scale(0.98); opacity: 0.4; filter: brightness(0.7); }
                        100% { transform: scaleX(1) scale(1); opacity: 1; filter: brightness(1); }
                    }
                </style>
                """,
                unsafe_allow_html=True
            )

            # --- 🏛️ TOMBOL NAVIGASI ATAS ---
            if current_page == 1:
                if st.button("📖 TUTUP JURNAL & KEMBALI KE MEJA DESK", use_container_width=True, key="btn_desk_nav_exit"):
                    st.session_state["campaign_sub_page"] = "resepsionis_utama"
                    st.session_state["book_page_number"] = 1
                    st.rerun()
            else:
                if st.button("⬅️ LEMBAR SEBELUMNYA (PREV PAGE)", use_container_width=True, key="btn_desk_nav_prev"):
                    st.session_state["book_page_number"] -= 1
                    st.rerun()
                    
            # --- 🏛️ RENDER HALAMAN BUKU BERDASARKAN SPREAD AKTIF ---
            html_content_pages = ""

            if current_spread["type"] == "main_menu":
                html_content_pages = (
                    '<div class="rpg-open-book-container rpg-open-book-animated">'
                    '<div class="rpg-book-page">'
                    f'<div class="open-page-title">{current_spread["left_title"]}</div>'
                    f'<div class="open-page-sub">{current_spread["left_sub"]}</div>'
                    '<div class="open-book-divider"></div>'
                    f'<div class="open-stat-row"><span>NAMA PAHLAWAN</span><span style="color:#b45309;">{username_hero}</span></div>'
                    f'<div class="open-stat-row"><span>TINGKAT LEVEL</span><span style="color:#16a34a; font-weight:900;">{data_stats["level"]}</span></div>'
                    f'<div class="open-stat-row"><span>TOTAL PWP</span><span style="color:#2563eb;">{data_stats["pwp"]}</span></div>'
                    f'<div class="open-stat-row"><span>PENJUALAN SG</span><span style="color:#7c3aed;">{data_stats["sg"]}</span></div>'
                    f'<div class="open-stat-row"><span>PENJUALAN SUEGER</span><span style="color:#0d9488;">{data_stats["sueger"]}</span></div>'
                    f'<div class="open-stat-row"><span>CEMILAN CEBAN</span><span style="color:#db2777;">{data_stats["cemilan"]}</span></div>'
                    f'<div class="open-stat-row"><span>ACHIEVEMENT %</span><span style="color:#ca8a04; font-weight:900;">{data_stats["achievement"]}</span></div>'
                    f'<div class="open-stat-row"><span>RANK SUEGER</span><span style="color:#0d9488; font-weight:900;">{data_stats["rank_sueger"]}</span></div>'
                    '<div class="open-page-footer">- Halaman 1 -</div>'
                    '</div>'
                    '<div class="rpg-book-page">'
                    f'<div class="open-page-title">{current_spread["right_title"]}</div>'
                    f'<div class="open-page-sub">{current_spread["right_sub"]}</div>'
                    '<div class="open-book-divider"></div>'
                    f'<div class="open-stat-row" style="margin-top:10px;"><span>QTY PENJUALAN PSM</span><span style="color:#b45309; font-weight:900;">{qty_penjualan_psm_val} Pts 📦</span></div>'
                    f'<div class="open-stat-row"><span>ITEM TERCAPAI</span><span style="color:#16a34a; font-weight:900;">{jumlah_jenis_item_tercapai} Jenis 🏆</span></div>'
                    f'<div class="open-stat-row"><span>RANKING PENJUALAN</span><span style="color:#ca8a04; font-weight:900;">{ranking_psm_val} 👑</span></div>'
                    '<div class="open-page-footer" style="margin-top:auto;">- Halaman 2 -</div>'
                    '</div>'
                    '</div>'
                )

            elif current_spread["type"] == "item_detail":
                html_content_pages = (
                    '<div class="rpg-open-book-container rpg-open-book-animated">'
                    '<div class="rpg-book-page">'
                    '<div class="open-page-title">💎 DETAIL ITEM TERCAPAI 💎</div>'
                    f'<div class="open-page-sub">{current_spread["sub_title"]}</div>'
                    '<div class="open-book-divider"></div>'
                    f'{current_spread["left_content"]}' 
                    f'<div class="open-page-footer">- {current_spread["page_num_left"]} -</div>'
                    '</div>'
                    '<div class="rpg-book-page">'
                    '<div class="open-page-title">💎 DETAIL ITEM TERCAPAI 💎</div>'
                    f'<div class="open-page-sub">{current_spread["sub_title"]} (Lanjutan)</div>'
                    '<div class="open-book-divider"></div>'
                    f'{current_spread["right_content"]}' 
                    f'<div class="open-page-footer">- {current_spread["page_num_right"]} -</div>'
                    '</div>'
                    '</div>'
                )

            elif current_spread["type"] == "closing_scroll":
                html_content_pages = (
                    '<div class="rpg-open-book-container rpg-open-book-animated">'
                    '<div class="rpg-book-page">'
                    '<div class="open-page-title">🍹 LOG HARIAN SUEGER 🍹</div>'
                    '<div class="open-page-sub">Arsip Tanggal, Shift, Syarat & Redeem</div>'
                    '<div class="open-book-divider"></div>'
                    '<div class="sueger-daily-scroll-box">'
                    f'{current_spread["sueger_html"]}'
                    '</div>'
                    '<div class="open-page-footer" style="margin-top:10px;">- Arsip Harian -</div>'
                    '</div>'
                    '<div class="rpg-book-page">'
                    '<div class="open-page-title">📜 CATATAN ALIANSI 📜</div>'
                    '<div class="open-page-sub">Maklumat & Motivasi Petualang</div>'
                    '<div class="open-book-divider"></div>'
                    f'<div style="background: rgba(180, 83, 9, 0.08); border-left: 3px solid #b45309; padding: 12px; border-radius: 6px; margin-top: 15px;">'
                    f'<p style="font-size:10px; color:#5c4033; line-height:1.6; text-align:center; font-style:italic; margin: 0;">'
                    f'{current_spread["motivasi_text"]}'
                    f'</p>'
                    f'</div>'
                    '<div class="open-page-footer" style="margin-top:auto;">- Halaman Terakhir -</div>'
                    '</div>'
                    '</div>'
                )

            st.markdown(html_content_pages, unsafe_allow_html=True)

            # --- 🏛️ TOMBOL NAVIGASI BAWAH ---
            # 🛡️ Proteksi Awal: Jika karena suatu hal variabel belum terinisialisasi, set ke halaman 1
            if "book_page_number" not in st.session_state:
                st.session_state["book_page_number"] = 1
            
            # Ambil nilai halaman saat ini dengan aman untuk pencocokan kondisi
            current_page = st.session_state["book_page_number"]
            
            if current_page == max_spread_index:
                if st.button("↺ KEMBALI KE HALAMAN UTAMA (AWAL BUKU)", use_container_width=True, key="btn_desk_nav_reset"):
                    st.session_state["book_page_number"] = 1
                    st.rerun()
            else:
                if st.button("LEMBAR BERIKUTNYA (BUKA HALAMAN SELANJUTNYA) ➔", use_container_width=True, key="btn_desk_nav_next"):
                    # Menggunakan .get() agar lebih aman dari KeyError saat proses penambahan
                    st.session_state["book_page_number"] = st.session_state.get("book_page_number", 1) + 1
                    st.rerun()

            
            # Memotong eksekusi halaman agar skrip di bawahnya tidak ikut terpanggil
            st.stop()

        # =========================================================================
        # 🏆 HALAMAN 3: HALL OF FAME ALIANSI — MENU 3 PILAR
        # =========================================================================
        elif st.session_state.get("campaign_sub_page") == "view_hall_of_fame" and not st.session_state.get("hof_sub_page"):

            url_gambar_latar = "https://i.imgur.com/kMo29aW.jpeg"

            st.markdown(
                f"""
                <style>
                    .stApp {{
                        background-image: linear-gradient(rgba(10, 13, 26, 0.78), rgba(10, 13, 26, 0.88)), url("{url_gambar_latar}") !important;
                        background-size: cover !important;
                        background-position: center !important;
                        background-repeat: no-repeat !important;
                        background-attachment: fixed !important;
                    }}
                    .main .block-container {{
                        background-color: transparent !important;
                        max-width: 700px !important;
                        padding-top: 3% !important;
                    }}
                    div[data-testid="stVerticalBlock"] {{ gap: 0rem !important; }}

                    /* ✨ ANIMASI MASUK HALAMAN */
                    .hof-page-wrapper {{
                        animation: hofEnterFade 0.9s cubic-bezier(0.25, 1, 0.5, 1) forwards;
                        transform-origin: center center;
                    }}
                    @keyframes hofEnterFade {{
                        0% {{ opacity: 0; transform: scale(0.94) translateY(20px); filter: blur(6px); }}
                        100% {{ opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }}
                    }}

                    .fame-header-title {{
                        text-align: center; color: #fef08a !important; font-family: monospace;
                        font-size: 24px !important; font-weight: 900 !important;
                        text-shadow: 0 0 15px rgba(251, 191, 36, 0.6) !important;
                        margin: 0 0 5px 0 !important;
                        animation: hofTitleGlow 3s infinite ease-in-out;
                    }}
                    @keyframes hofTitleGlow {{
                        0%, 100% {{ text-shadow: 0 0 15px rgba(251, 191, 36, 0.5); }}
                        50% {{ text-shadow: 0 0 25px rgba(251, 191, 36, 0.9), 0 0 40px rgba(251, 191, 36, 0.5); }}
                    }}
                    .fame-header-sub {{
                        text-align: center; color: #cbd5e1 !important; font-family: monospace;
                        font-size: 12px !important; margin-bottom: 30px !important;
                    }}

                    .fame-pillar-card {{
                        background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 27, 24, 0.95) 100%) !important;
                        border-radius: 12px !important;
                        padding: 25px 20px 20px 20px !important;
                        text-align: center;
                        max-width: 480px;
                        margin: 0 auto;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.6) !important;
                        min-height: 190px;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                    }}
                    .fame-pillar-psm {{
                        border: 2px solid #1d4ed8 !important;
                        border-top: 6px solid #3b82f6 !important;
                    }}
                    .fame-pillar-pps {{
                        border: 2px solid #7c3aed !important;
                        border-top: 6px solid #a855f7 !important;
                    }}
                    .fame-pillar-sueger {{
                        border: 2px solid #059669 !important;
                        border-top: 6px solid #10b981 !important;
                    }}

                    .fame-pillar-emoji {{
                        font-size: 45px; line-height: 1; margin-bottom: 12px;
                        display: inline-block;
                        animation: floatFameEmoji 2.5s infinite ease-in-out;
                    }}
                    .fame-pillar-title {{
                        font-family: monospace; font-size: 15px; font-weight: bold;
                        color: #fbbf24; margin-bottom: 8px; letter-spacing: 0.5px;
                    }}
                    .fame-pillar-desc {{
                        font-family: monospace; font-size: 11.5px;
                        line-height: 1.6; color: #cbd5e1; margin-bottom: 0;
                    }}

                    div[data-testid="stButton"] {{
                        max-width: 480px !important;
                        margin: 6px auto 25px auto !important;
                        padding: 0 !important;
                    }}
                    div[data-testid="stButton"] > button {{
                        border-radius: 12px !important;
                        font-family: monospace !important;
                        font-size: 13px !important;
                        font-weight: bold !important;
                        padding: 12px 20px !important;
                        transition: all 0.3s ease !important;
                        width: 100% !important;
                        display: block !important;
                    }}

                    .st-key-btn_hof_psm button {{
                        background: rgba(29, 78, 216, 0.18) !important;
                        border: 2px solid #1d4ed8 !important;
                        color: #93c5fd !important;
                    }}
                    .st-key-btn_hof_psm button:hover {{
                        background: #1d4ed8 !important; color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4) !important;
                    }}

                    .st-key-btn_hof_pps button {{
                        background: rgba(124, 58, 237, 0.18) !important;
                        border: 2px solid #7c3aed !important;
                        color: #d8b4fe !important;
                    }}
                    .st-key-btn_hof_pps button:hover {{
                        background: #7c3aed !important; color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(168, 85, 247, 0.4) !important;
                    }}

                    .st-key-btn_hof_sueger button {{
                        background: rgba(5, 150, 105, 0.18) !important;
                        border: 2px solid #059669 !important;
                        color: #6ee7b7 !important;
                    }}
                    .st-key-btn_hof_sueger button:hover {{
                        background: #059669 !important; color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4) !important;
                    }}

                    .st-key-btn_hof_back button {{
                        background: rgba(100, 116, 139, 0.15) !important;
                        border: 2px solid #475569 !important;
                        color: #cbd5e1 !important;
                    }}
                    .st-key-btn_hof_back button:hover {{
                        background: #475569 !important; color: #ffffff !important;
                        box-shadow: 0 4px 15px rgba(100, 116, 139, 0.4) !important;
                    }}

                    @keyframes floatFameEmoji {{
                        0%, 100% {{ transform: translateY(0); filter: drop-shadow(0 0 6px rgba(251,191,36,0.4)); }}
                        50%      {{ transform: translateY(-5px); filter: drop-shadow(0 0 12px rgba(251,191,36,0.7)); }}
                    }}
                </style>
                """,
                unsafe_allow_html=True
            )

            st.markdown("<div class='hof-page-wrapper'>", unsafe_allow_html=True)

            st.markdown("<h2 class='fame-header-title'>🏛️ HALL OF FAME ALIANSI 🏛️</h2>", unsafe_allow_html=True)
            st.markdown("<p class='fame-header-sub'>Pilih papan prasasti pahlawan yang ingin dilihat</p>", unsafe_allow_html=True)

            # 👑 PILAR 1: PSM
            st.markdown("""
                <div class='fame-pillar-card fame-pillar-psm'>
                    <div class='fame-pillar-emoji'>👑</div>
                    <div class='fame-pillar-title'>HALL OF FAME PSM</div>
                    <div class='fame-pillar-desc'>Papan peringkat pahlawan dengan akumulasi penjualan item terbanyak per periode promosi.</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("👑 BUKA PAPAN PSM ➔", key="btn_hof_psm", use_container_width=True):
                st.session_state["hof_sub_page"] = "hof_psm"
                st.rerun()

            # ⚔️ PILAR 2: PWP & SG
            st.markdown("""
                <div class='fame-pillar-card fame-pillar-pps'>
                    <div class='fame-pillar-emoji'>⚔️</div>
                    <div class='fame-pillar-title'>HALL OF FAME PWP & SG</div>
                    <div class='fame-pillar-desc'>Papan kehormatan untuk pahlawan dengan total penjualan program PWP dan Serba Gratis terbanyak.</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("⚔️ BUKA PAPAN PWP & SG ➔", key="btn_hof_pps", use_container_width=True):
                st.session_state["hof_sub_page"] = "hof_pps"
                st.rerun()

            # 🍃 PILAR 3: SUEGER
            st.markdown("""
                <div class='fame-pillar-card fame-pillar-sueger'>
                    <div class='fame-pillar-emoji'>🍃</div>
                    <div class='fame-pillar-title'>HALL OF FAME SUEGER</div>
                    <div class='fame-pillar-desc'>Papan pencapaian untuk kasir dengan persentase achievement program Sueger tertinggi.</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("🍃 BUKA PAPAN SUEGER ➔", key="btn_hof_sueger", use_container_width=True):
                st.session_state["hof_sub_page"] = "hof_sueger"
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<br><hr style='border-color: rgba(251, 191, 36, 0.3); margin: 15px 0;'><br>", unsafe_allow_html=True)
            
            if st.button("⬅️ KEMBALI KE RESEPSIONIS", key="btn_hof_back", use_container_width=True):
                st.session_state["campaign_sub_page"] = "resepsionis_utama"
                st.session_state["hof_sub_page"] = None
                st.rerun()

            st.stop()
    
        # =========================================================================
        # 👑 HALAMAN 3A: HALL OF FAME PSM (DATA REAL + DINAMIS + MISTERI H+1)
        # =========================================================================
        elif (
            st.session_state.get("campaign_sub_page") == "view_hall_of_fame"
            and st.session_state.get("hof_sub_page") == "hof_psm"
        ):

            url_gambar_latar = "https://i.imgur.com/kMo29aW.jpeg"
            import hashlib

            # ==== FUNGSI AVATAR AUTO-HASH ====
            def get_avatar(name):
                list_avatar_rpg = [
                    "🧙‍♂️", "🧝‍♂️", "🧝‍♀️", "⚔️", "🎯", "🛡️", "🦁", "🦅",
                    "🐺", "👑", "💎", "🔮", "🔥", "🏹", "🪄", "🗡️",
                    "⚗️", "🧛‍♂️", "🧟‍♂️", "🐉", "🦉", "🐻", "🦊", "🦌"
                ]
                h = int(hashlib.md5(str(name).upper().encode()).hexdigest(), 16)
                return list_avatar_rpg[h % len(list_avatar_rpg)]

            # ==== AMBIL DATA ====
            df_periode = st.session_state.get("periods_df", pd.DataFrame()).copy()
            df_sales = st.session_state.get("sales_person_df", pd.DataFrame()).copy()

            for df in [df_periode, df_sales]:
                if not df.empty:
                    df.columns = df.columns.astype(str).str.strip().str.lower()

            today = datetime.now().date()

            # ==== BANGUN DAFTAR KARTU DINAMIS ====
            kartu_periode = []   # periode individual
            kartu_bulan = []     # grup bulan
            kartu_alltime = None # all time

            if not df_periode.empty and all(
                c in df_periode.columns for c in ["period_id", "period_name", "start_date", "end_date"]
            ):
                df_periode["start_dt"] = pd.to_datetime(df_periode["start_date"], errors="coerce")
                df_periode["end_dt"] = pd.to_datetime(df_periode["end_date"], errors="coerce")
                df_periode = df_periode.dropna(subset=["start_dt", "end_dt"])

                # Skip PPS / Sueger
                df_periode = df_periode[
                    ~df_periode["period_id"].astype(str).str.upper().str.contains(
                        "PWP|SGR|SGS|CBN|PPS", na=False
                    )
                ]

                # Urutkan ASCENDING (terlama dulu) untuk periode
                df_periode_asc = df_periode.sort_values("start_dt", ascending=True).reset_index(drop=True)

                # === BANGUN KARTU PERIODE (ASCENDING) ===
                for _, row_p in df_periode_asc.iterrows():
                    p_id = str(row_p["period_id"]).strip()
                    p_name = str(row_p["period_name"]).strip()
                    p_start = row_p["start_dt"].date()
                    p_end = row_p["end_dt"].date()
                    is_selesai = p_end < today

                    if p_start.month == p_end.month:
                        label_tgl = f"{p_start.day}-{p_end.day} {p_start.strftime('%b').upper()}"
                    else:
                        label_tgl = f"{p_start.day} {p_start.strftime('%b').upper()} - {p_end.day} {p_end.strftime('%b').upper()}"

                    kartu_periode.append({
                        "key": f"periode_{p_id}",
                        "label": f"📅 {label_tgl}",
                        "tipe": "periode",
                        "period_ids": [p_id],
                        "is_active": not is_selesai,
                        "period_name": p_name,
                        "start_dt": p_start,
                    })

                # === BANGUN KARTU ALL TIME (hanya periode selesai) ===
                df_selesai = df_periode[df_periode["end_dt"].dt.date < today]
                if not df_selesai.empty:
                    kartu_alltime = {
                        "key": "alltime",
                        "label": "🏆 ALL TIME",
                        "tipe": "alltime",
                        "period_ids": df_selesai["period_id"].astype(str).str.strip().tolist(),
                        "is_active": False,
                    }

                # === BANGUN KARTU BULAN (ASCENDING) ===
                if not df_selesai.empty:
                    df_bulan = df_selesai.copy()
                    df_bulan["bulan_key"] = df_bulan["start_dt"].dt.strftime("%Y-%m")
                    df_bulan["bulan_label"] = df_bulan["start_dt"].dt.strftime("%B %Y").str.upper()

                    bulan_unik = df_bulan[["bulan_key", "bulan_label"]].drop_duplicates().sort_values("bulan_key", ascending=True)

                    for _, row_bulan in bulan_unik.iterrows():
                        b_key = row_bulan["bulan_key"]
                        b_label = row_bulan["bulan_label"]
                        period_ids_bulan = df_bulan[
                            df_bulan["bulan_key"] == b_key
                        ]["period_id"].astype(str).str.strip().tolist()

                        kartu_bulan.append({
                            "key": f"bulan_{b_key}",
                            "label": f"📆 {b_label}",
                            "tipe": "bulan",
                            "period_ids": period_ids_bulan,
                            "is_active": False,
                        })

            # ==== GABUNG URUTAN: Periode → Bulan → All Time ====
            kartu_list = kartu_periode + kartu_bulan
            if kartu_alltime:
                kartu_list.append(kartu_alltime)

            # ==== HITUNG JUARA ====
            def get_juara_per_kartu(kartu):
                if df_sales.empty or "person_name" not in df_sales.columns or "actual_qty" not in df_sales.columns:
                    return None
                if "period_id" not in df_sales.columns:
                    return None

                df_filter = df_sales[
                    df_sales["period_id"].astype(str).str.strip().isin(kartu["period_ids"])
                ].copy()

                if df_filter.empty:
                    return None

                df_filter["person_name"] = df_filter["person_name"].astype(str).str.strip()
                df_filter["actual_qty"] = pd.to_numeric(df_filter["actual_qty"], errors="coerce").fillna(0)

                grouped = df_filter.groupby("person_name")["actual_qty"].sum().reset_index()
                grouped = grouped[grouped["actual_qty"] > 0]
                if grouped.empty:
                    return None

                grouped = grouped.sort_values("actual_qty", ascending=False).reset_index(drop=True)
                top1 = grouped.iloc[0]

                return {
                    "nama": str(top1["person_name"]),
                    "qty": int(top1["actual_qty"]),
                }

            for k in kartu_list:
                k["juara"] = get_juara_per_kartu(k)

            total_kartu = len(kartu_list)

            # ==== CSS ====
            st.markdown("""
                <style>
                @keyframes hofTitleGlow {
                    0%, 100% { text-shadow: 0 0 15px rgba(251, 191, 36, 0.5); }
                    50% { text-shadow: 0 0 25px rgba(251, 191, 36, 0.9), 0 0 40px rgba(251, 191, 36, 0.5); }
                }
                @keyframes crownFloat {
                    0%, 100% { transform: translateY(0) rotate(0deg); filter: drop-shadow(0 0 15px rgba(251, 191, 36, 0.7)); }
                    50% { transform: translateY(-6px) rotate(-3deg); filter: drop-shadow(0 0 25px rgba(251, 191, 36, 1)); }
                }
                @keyframes sparkleFloat1 {
                    0%, 100% { transform: translateY(0) scale(0.8); opacity: 0.5; }
                    50% { transform: translateY(-10px) scale(1.2); opacity: 1; }
                }
                @keyframes sparkleFloat2 {
                    0%, 100% { transform: translateY(-5px) scale(1); opacity: 0.7; }
                    50% { transform: translateY(5px) scale(0.8); opacity: 0.3; }
                }
                @keyframes avatarBob {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-3px); }
                }
                @keyframes cardEnter {
                    0% { opacity: 0; transform: translateY(30px) scale(0.95); }
                    100% { opacity: 1; transform: translateY(0) scale(1); }
                }
                @keyframes cardGlow {
                    0%, 100% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(212, 175, 55, 0.3); }
                    50% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 35px rgba(212, 175, 55, 0.6); }
                }
                @keyframes mysteryPulse {
                    0%, 100% { filter: drop-shadow(0 0 15px rgba(168, 85, 247, 0.6)); transform: scale(1); }
                    50% { filter: drop-shadow(0 0 30px rgba(168, 85, 247, 1)); transform: scale(1.08); }
                }
                @keyframes lockShake {
                    0%, 100% { transform: rotate(0deg); }
                    25% { transform: rotate(-5deg); }
                    75% { transform: rotate(5deg); }
                }

                .hof-page-title {
                    text-align: center; color: #fef08a; font-family: monospace;
                    font-size: 22px; font-weight: 900; margin: 0 0 5px 0;
                    animation: hofTitleGlow 3s infinite ease-in-out;
                }
                .hof-page-sub {
                    text-align: center; color: #cbd5e1; font-family: monospace;
                    font-size: 11.5px; margin-bottom: 25px;
                }

                /* ============================================
                🎠 CAROUSEL — FIX SCROLL BEBAS
                ============================================ */
                .hof-carousel-wrapper {
                    display: flex;
                    flex-direction: row;
                    flex-wrap: nowrap;
                    gap: 14px;
                    padding: 15px 20px 25px 20px;
                    justify-content: flex-start;
                    overflow-x: auto;
                    overflow-y: visible;
                    scroll-snap-type: x proximity;
                    -webkit-overflow-scrolling: touch;
                    scrollbar-width: thin;
                    width: 100%;
                    box-sizing: border-box;
                }
                .hof-carousel-wrapper::-webkit-scrollbar {
                    height: 8px;
                }
                .hof-carousel-wrapper::-webkit-scrollbar-track {
                    background: rgba(15, 23, 42, 0.5);
                    border-radius: 4px;
                }
                .hof-carousel-wrapper::-webkit-scrollbar-thumb {
                    background: linear-gradient(90deg, #b45309, #fbbf24, #b45309);
                    border-radius: 4px;
                }

                .hof-card {
                    flex: 0 0 auto;
                    width: 280px;
                    min-width: 280px;
                    max-width: 280px;
                    min-height: 420px;
                    scroll-snap-align: center;
                    position: relative;
                    background: linear-gradient(160deg, #0f172a 0%, #1a1410 50%, #0f172a 100%);
                    border-radius: 18px;
                    padding: 3px;
                    animation: cardEnter 0.7s cubic-bezier(0.25, 1, 0.5, 1) forwards,
                            cardGlow 4s infinite ease-in-out 1s;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(212, 175, 55, 0.3);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }
                .hof-card-inner {
                    background: linear-gradient(160deg, #0a0d1a 0%, #15110a 100%);
                    border: 2px solid #d4af37;
                    border-radius: 16px;
                    padding: 25px 20px 20px 20px;
                    position: relative;
                    min-height: 414px;
                    box-shadow: inset 0 0 20px rgba(212, 175, 55, 0.08);
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                }
                .hof-ornament {
                    position: absolute; color: #d4af37; font-size: 16px; line-height: 1;
                    filter: drop-shadow(0 0 4px rgba(212, 175, 55, 0.8)); z-index: 5;
                }
                .hof-orn-tl { top: 8px; left: 10px; }
                .hof-orn-tr { top: 8px; right: 10px; }
                .hof-orn-bl { bottom: 8px; left: 10px; }
                .hof-orn-br { bottom: 8px; right: 10px; }
                .hof-period-badge {
                    text-align: center;
                    background: linear-gradient(90deg, rgba(180, 83, 9, 0.4), rgba(251, 191, 36, 0.3), rgba(180, 83, 9, 0.4));
                    border: 1px solid #d4af37; border-radius: 8px;
                    padding: 7px 12px; font-family: monospace;
                    font-size: 11px; font-weight: 900; color: #fef08a;
                    letter-spacing: 1px; margin-bottom: 20px;
                    text-shadow: 0 0 6px rgba(254, 240, 138, 0.5);
                    width: 100%;
                    box-sizing: border-box;
                }
                .hof-crown-box { text-align: center; position: relative; height: 70px; margin-bottom: 8px; width: 100%; }
                .hof-crown { font-size: 48px; display: inline-block; animation: crownFloat 2.5s infinite ease-in-out; }
                .hof-sparkle { position: absolute; color: #fef08a; font-size: 14px; filter: drop-shadow(0 0 6px #fbbf24); }
                .hof-sparkle-1 { top: 5px; left: 30%; animation: sparkleFloat1 2s infinite ease-in-out; }
                .hof-sparkle-2 { top: 20px; right: 30%; animation: sparkleFloat2 2.3s infinite ease-in-out 0.3s; }
                .hof-sparkle-3 { bottom: 0px; left: 50%; transform: translateX(-50%); animation: sparkleFloat1 2.6s infinite ease-in-out 0.7s; }
                .hof-avatar-wrapper { text-align: center; margin: 10px 0 15px 0; }
                .hof-avatar-circle {
                    display: inline-flex; justify-content: center; align-items: center;
                    width: 80px; height: 80px; border-radius: 50%;
                    background: radial-gradient(circle, #1e293b 0%, #0f172a 100%);
                    border: 3px solid #d4af37; font-size: 40px;
                    box-shadow: 0 0 20px rgba(212, 175, 55, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.6);
                    animation: avatarBob 2.5s infinite ease-in-out;
                }
                .hof-champion-name {
                    text-align: center; font-family: monospace; font-size: 16px; font-weight: 900;
                    color: #ffffff; letter-spacing: 0.5px; margin-bottom: 12px;
                    text-shadow: 0 0 10px rgba(255, 255, 255, 0.4);
                    line-height: 1.3; word-break: break-word;
                }
                .hof-champion-qty {
                    text-align: center; font-family: monospace; font-size: 22px; font-weight: 900;
                    color: #fbbf24;
                    text-shadow: 0 0 15px rgba(251, 191, 36, 0.8);
                }
                .hof-card-alltime .hof-period-badge {
                    background: linear-gradient(90deg, rgba(212, 175, 55, 0.5), rgba(254, 240, 138, 0.4), rgba(212, 175, 55, 0.5));
                    color: #0f172a; text-shadow: none;
                }
                .hof-card-alltime .hof-crown {
                    filter: drop-shadow(0 0 25px rgba(251, 191, 36, 1)) drop-shadow(0 0 40px rgba(251, 191, 36, 0.6));
                }
                .hof-card-selected .hof-card-inner {
                    box-shadow: inset 0 0 30px rgba(251, 191, 36, 0.2), 0 0 40px rgba(251, 191, 36, 0.5);
                    border: 3px solid #fbbf24;
                }

                /* KARTU MISTERI */
                .hof-card-mystery .hof-card-inner {
                    background: linear-gradient(160deg, #0f0a1e 0%, #1a0d2e 50%, #0f0a1e 100%);
                    border: 2px dashed #7c3aed;
                    box-shadow: inset 0 0 30px rgba(124, 58, 237, 0.15);
                }
                .hof-mystery-icon {
                    font-size: 70px;
                    animation: mysteryPulse 2s infinite ease-in-out;
                    margin-bottom: 15px;
                }
                .hof-mystery-lock {
                    font-size: 35px;
                    display: inline-block;
                    animation: lockShake 2.5s infinite ease-in-out;
                    margin-bottom: 10px;
                }
                .hof-mystery-title {
                    text-align: center;
                    color: #d8b4fe;
                    font-family: monospace;
                    font-size: 14px;
                    font-weight: 900;
                    letter-spacing: 1.5px;
                    text-shadow: 0 0 12px rgba(168, 85, 247, 0.8);
                    margin-bottom: 15px;
                    line-height: 1.4;
                }
                .hof-mystery-sub {
                    text-align: center;
                    color: #94a3b8;
                    font-family: monospace;
                    font-size: 10.5px;
                    line-height: 1.6;
                    padding: 0 10px;
                }
                .hof-card-mystery .hof-period-badge {
                    background: linear-gradient(90deg, rgba(124, 58, 237, 0.4), rgba(168, 85, 247, 0.3), rgba(124, 58, 237, 0.4));
                    border-color: #a855f7;
                    color: #d8b4fe;
                }

                /* KARTU EMPTY */
                .hof-card-empty .hof-card-inner {
                    background: linear-gradient(160deg, #0f172a 0%, #13110a 100%);
                    border: 2px dashed #475569;
                }
                .hof-empty-icon {
                    font-size: 60px;
                    opacity: 0.5;
                    margin-bottom: 15px;
                }
                .hof-empty-title {
                    text-align: center;
                    color: #94a3b8;
                    font-family: monospace;
                    font-size: 12px;
                    font-weight: 900;
                    letter-spacing: 1px;
                    margin-bottom: 10px;
                }
                .hof-empty-sub {
                    text-align: center;
                    color: #64748b;
                    font-family: monospace;
                    font-size: 10.5px;
                    line-height: 1.6;
                    padding: 0 10px;
                }

                /* TOMBOL */
                div[data-testid="stButton"] {
                    max-width: 480px !important;
                    margin: 8px auto 10px auto !important;
                    padding: 0 !important;
                }
                div[data-testid="stButton"] > button {
                    border-radius: 12px !important;
                    font-family: monospace !important;
                    font-size: 13px !important;
                    font-weight: bold !important;
                    padding: 13px 20px !important;
                    width: 100% !important;
                    display: block !important;
                    transition: all 0.3s ease !important;
                }
                .st-key-btn_hof_psm_back button {
                    background: rgba(100, 116, 139, 0.15) !important;
                    border: 2px solid #475569 !important;
                    color: #cbd5e1 !important;
                }
                .st-key-btn_hof_psm_back button:hover {
                    background: #475569 !important; color: #ffffff !important;
                }

                @media (max-width: 600px) {
                    .hof-card { width: 260px; min-width: 260px; max-width: 260px; }
                    .hof-carousel-wrapper { padding: 15px 15px 25px 15px; }
                }
                @media (max-width: 380px) {
                    .hof-card { width: 240px; min-width: 240px; max-width: 240px; }
                }
                </style>
                """, unsafe_allow_html=True)

            # ==== BACKGROUND ====
            st.markdown(
                f"""
                <style>
                .stApp {{
                    background-image: linear-gradient(rgba(10, 13, 26, 0.85), rgba(10, 13, 26, 0.92)), url("{url_gambar_latar}") !important;
                    background-size: cover !important;
                    background-position: center !important;
                    background-repeat: no-repeat !important;
                    background-attachment: fixed !important;
                }}
                .main .block-container {{
                    background-color: transparent !important;
                    max-width: 100% !important;
                    padding-top: 3% !important;
                    padding-left: 0 !important;
                    padding-right: 0 !important;
                }}
                div[data-testid="stVerticalBlock"] {{ gap: 0rem !important; }}
                </style>
                """,
                unsafe_allow_html=True
            )

            # ==== HEADER ====
            st.markdown("<h2 class='hof-page-title'>👑 HALL OF FAME PSM 👑</h2>", unsafe_allow_html=True)
            st.markdown("<p class='hof-page-sub'>Peringkat penjualan item terbaik per periode</p>", unsafe_allow_html=True)

            # ==== JIKA BELUM ADA PERIODE ====
            if total_kartu == 0:
                st.markdown(
                    "<div style='background: rgba(15,23,42,0.85); border: 2px dashed #475569; "
                    "border-radius: 12px; padding: 40px 20px; margin: 30px auto; max-width: 500px; "
                    "text-align: center;'>"
                    "<div style='font-size: 60px; opacity: 0.5; margin-bottom: 15px;'>📜</div>"
                    "<div style='color: #94a3b8; font-family: monospace; font-size: 14px; font-weight: 900; "
                    "letter-spacing: 1px; margin-bottom: 8px;'>BELUM ADA PERIODE TERCATAT</div>"
                    "<div style='color: #64748b; font-family: monospace; font-size: 11px; line-height: 1.6;'>"
                    "Data periode akan muncul setelah admin mendaftarkan periode di sheet PERIODE."
                    "</div></div>",
                    unsafe_allow_html=True
                )
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("⬅️ KEMBALI KE HALL OF FAME", key="btn_hof_psm_back", use_container_width=True):
                    st.session_state["hof_sub_page"] = None
                    st.rerun()
                st.stop()

            # ==== CAROUSEL KARTU ====
            kartu_parts = ["<div class='hof-carousel-wrapper'>"]

            for idx, k in enumerate(kartu_list):
                alltime_class = "hof-card-alltime" if k["tipe"] == "alltime" else ""

                if k.get("is_active") and k["tipe"] == "periode":
                    # KARTU MISTERI
                    konten = (
                        "<div class='hof-mystery-icon'>❓</div>"
                        "<div class='hof-mystery-lock'>🔒</div>"
                        "<div class='hof-mystery-title'>AWAITING FINAL RESULTS</div>"
                        "<div class='hof-mystery-sub'>Prasasti juara akan dibuka setelah periode selesai (H+1).<br><br>"
                        "Selesaikan pertempuran periode ini dulu!</div>"
                    )
                    card_cls = "hof-card hof-card-mystery"
                elif k.get("juara"):
                    juara = k["juara"]
                    av = get_avatar(juara["nama"])
                    konten = (
                        "<div class='hof-crown-box'>"
                        "<span class='hof-sparkle hof-sparkle-1'>✦</span>"
                        "<span class='hof-crown'>👑</span>"
                        "<span class='hof-sparkle hof-sparkle-2'>✦</span>"
                        "<span class='hof-sparkle hof-sparkle-3'>✦</span>"
                        "</div>"
                        "<div class='hof-avatar-wrapper'>"
                        "<div class='hof-avatar-circle'>" + av + "</div>"
                        "</div>"
                        "<div class='hof-champion-name'>" + juara["nama"] + "</div>"
                        "<div class='hof-champion-qty'>" + str(juara["qty"]) + " Pcs</div>"
                    )
                    card_cls = "hof-card " + alltime_class
                else:
                    konten = (
                        "<div class='hof-empty-icon'>📭</div>"
                        "<div class='hof-empty-title'>BELUM ADA PENJUALAN</div>"
                        "<div class='hof-empty-sub'>Tidak ada data penjualan untuk periode ini.</div>"
                    )
                    card_cls = "hof-card hof-card-empty " + alltime_class

                kartu_parts.append(
                    "<div class='" + card_cls + "'>"
                    "<div class='hof-card-inner'>"
                    "<div class='hof-ornament hof-orn-tl'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-tr'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-bl'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-br'>⚜️</div>"
                    "<div class='hof-period-badge'>" + k["label"] + "</div>"
                    + konten +
                    "</div>"
                    "</div>"
                )

            kartu_parts.append("</div>")
            kartu_html = "".join(kartu_parts).strip()
            st.markdown(kartu_html, unsafe_allow_html=True)

            # ==== TOMBOL KEMBALI ====
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⬅️ KEMBALI KE HALL OF FAME", key="btn_hof_psm_back", use_container_width=True):
                st.session_state["hof_sub_page"] = None
                st.rerun()

            st.stop()

        # =========================================================================
        # 📊 HALAMAN 3A-2: TABEL LENGKAP PERINGKAT PSM (EMAS)
        # =========================================================================
        elif (
            st.session_state.get("campaign_sub_page") == "view_hall_of_fame"
            and st.session_state.get("hof_sub_page") == "hof_table_psm"
        ):

            url_gambar_latar = "https://i.imgur.com/kMo29aW.jpeg"

            # ==== AMBIL DATA ====
            data_dummy = st.session_state.get("hof_dummy_data", {})
            selected_key = st.session_state.get("hof_selected_period", "periode_1")
            d = data_dummy.get(selected_key, {})
            ranking = d.get("data", [])
            label = d.get("label", "-")
            short = d.get("short", "-")

            # ==== FUNGSI AVATAR ====
            import hashlib
            def get_avatar_table(name):
                list_avatar_rpg = [
                    "🧙‍♂️", "🧝‍♂️", "🧝‍♀️", "⚔️", "🎯", "🛡️", "🦁", "🦅",
                    "🐺", "👑", "💎", "🔮", "🔥", "🏹", "🪄", "🗡️",
                    "⚗️", "🧛‍♂️", "🧟‍♂️", "🐉", "🦉", "🐻", "🦊", "🦌"
                ]
                h = int(hashlib.md5(name.upper().encode()).hexdigest(), 16)
                return list_avatar_rpg[h % len(list_avatar_rpg)]

            # ==== CSS ====
            st.markdown("""
                <style>
                @keyframes tblEnter {
                    0% { opacity: 0; transform: translateY(20px); }
                    100% { opacity: 1; transform: translateY(0); }
                }
                .tbl-page-title {
                    text-align: center; color: #fef08a; font-family: monospace;
                    font-size: 22px; font-weight: 900; margin: 0 0 5px 0;
                    text-shadow: 0 0 15px rgba(251, 191, 36, 0.6);
                }
                .tbl-page-sub {
                    text-align: center; color: #cbd5e1; font-family: monospace;
                    font-size: 11.5px; margin-bottom: 20px;
                }
                .tbl-wrapper {
                    max-width: 620px;
                    margin: 0 auto;
                    background: linear-gradient(160deg, #0a0d1a 0%, #15110a 100%);
                    border: 2px solid #d4af37;
                    border-radius: 16px;
                    padding: 20px 15px;
                    box-shadow: 0 8px 30px rgba(0,0,0,0.7), inset 0 0 25px rgba(212, 175, 55, 0.08);
                    animation: tblEnter 0.7s cubic-bezier(0.25, 1, 0.5, 1) forwards;
                    position: relative;
                }
                .tbl-ornament {
                    position: absolute; color: #d4af37; font-size: 16px; line-height: 1;
                    filter: drop-shadow(0 0 6px rgba(212, 175, 55, 0.9));
                }
                .tbl-orn-tl { top: 8px; left: 10px; }
                .tbl-orn-tr { top: 8px; right: 10px; }
                .tbl-orn-bl { bottom: 8px; left: 10px; }
                .tbl-orn-br { bottom: 8px; right: 10px; }
                .tbl-header-row {
                    display: grid;
                    grid-template-columns: 50px 50px 1fr 90px;
                    gap: 8px;
                    padding: 10px 12px;
                    background: linear-gradient(90deg, rgba(180, 83, 9, 0.5), rgba(251, 191, 36, 0.3), rgba(180, 83, 9, 0.5));
                    border: 1.5px solid #d4af37;
                    border-radius: 8px;
                    margin-bottom: 12px;
                    font-family: monospace;
                    font-size: 11px;
                    font-weight: 900;
                    color: #fef08a;
                    letter-spacing: 1px;
                    text-transform: uppercase;
                }
                .tbl-row {
                    display: grid;
                    grid-template-columns: 50px 50px 1fr 90px;
                    gap: 8px;
                    padding: 10px 12px;
                    background: rgba(15, 23, 42, 0.6);
                    border: 1.5px solid rgba(180, 83, 9, 0.4);
                    border-radius: 8px;
                    margin-bottom: 6px;
                    align-items: center;
                    font-family: monospace;
                    font-size: 13px;
                    color: #e2e8f0;
                    transition: all 0.2s ease;
                }
                .tbl-row:hover {
                    background: rgba(180, 83, 9, 0.15);
                    border-color: #d4af37;
                }
                .tbl-row.row-1 {
                    background: linear-gradient(90deg, rgba(254, 240, 138, 0.15), rgba(217, 119, 6, 0.25)) !important;
                    border-color: #fbbf24 !important;
                }
                .tbl-row.row-2 {
                    background: linear-gradient(90deg, rgba(203, 213, 225, 0.1), rgba(100, 116, 139, 0.2)) !important;
                    border-color: #94a3b8 !important;
                }
                .tbl-row.row-3 {
                    background: linear-gradient(90deg, rgba(255, 237, 213, 0.1), rgba(194, 65, 12, 0.2)) !important;
                    border-color: #ea580c !important;
                }
                .tbl-rank {
                    font-weight: 900;
                    color: #fbbf24;
                    text-align: center;
                    font-size: 14px;
                }
                .tbl-avatar {
                    font-size: 22px;
                    text-align: center;
                }
                .tbl-name {
                    font-weight: bold;
                    color: #ffffff;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .tbl-score {
                    font-weight: 900;
                    color: #fbbf24;
                    text-align: right;
                    font-size: 14px;
                }
                .tbl-footer {
                    text-align: center;
                    color: #94a3b8;
                    font-family: monospace;
                    font-size: 10px;
                    margin-top: 15px;
                    padding-top: 12px;
                    border-top: 1px solid rgba(212, 175, 55, 0.3);
                    letter-spacing: 1px;
                }
                @media (max-width: 500px) {
                    .tbl-header-row, .tbl-row {
                        grid-template-columns: 40px 40px 1fr 70px;
                        font-size: 11px;
                    }
                    .tbl-avatar { font-size: 18px; }
                    .tbl-rank, .tbl-score { font-size: 12px; }
                }
                div[data-testid="stButton"] {
                    max-width: 480px !important;
                    margin: 8px auto 10px auto !important;
                    padding: 0 !important;
                }
                div[data-testid="stButton"] > button {
                    border-radius: 12px !important;
                    font-family: monospace !important;
                    font-size: 13px !important;
                    font-weight: bold !important;
                    padding: 13px 20px !important;
                    width: 100% !important;
                    display: block !important;
                }
                .st-key-btn_table_back button {
                    background: rgba(100, 116, 139, 0.15) !important;
                    border: 2px solid #475569 !important;
                    color: #cbd5e1 !important;
                }
                .st-key-btn_table_back button:hover {
                    background: #475569 !important; color: #ffffff !important;
                }
                </style>
                """, unsafe_allow_html=True)

            st.markdown(
                f"""
                <style>
                .stApp {{
                    background-image: linear-gradient(rgba(10, 13, 26, 0.88), rgba(10, 13, 26, 0.95)), url("{url_gambar_latar}") !important;
                    background-size: cover !important;
                    background-position: center !important;
                    background-repeat: no-repeat !important;
                    background-attachment: fixed !important;
                }}
                .main .block-container {{
                    background-color: transparent !important;
                    max-width: 900px !important;
                    padding-top: 3% !important;
                    padding-left: 8px !important;
                    padding-right: 8px !important;
                }}
                div[data-testid="stVerticalBlock"] {{ gap: 0rem !important; }}
                </style>
                """,
                unsafe_allow_html=True
            )

            # ==== HEADER ====
            st.markdown("<h2 class='tbl-page-title'>📊 TABEL LENGKAP PERINGKAT 📊</h2>", unsafe_allow_html=True)
            st.markdown("<p class='tbl-page-sub'>" + label + "</p>", unsafe_allow_html=True)

            # ==== TABEL ====
            if ranking:
                baris_html = (
                    "<div class='tbl-wrapper'>"
                    "<div class='tbl-ornament tbl-orn-tl'>⚜️</div>"
                    "<div class='tbl-ornament tbl-orn-tr'>⚜️</div>"
                    "<div class='tbl-ornament tbl-orn-bl'>⚜️</div>"
                    "<div class='tbl-ornament tbl-orn-br'>⚜️</div>"
                    "<div class='tbl-header-row'>"
                    "<div style='text-align:center;'>#</div>"
                    "<div style='text-align:center;'>👤</div>"
                    "<div>NAMA PAHLAWAN</div>"
                    "<div style='text-align:right;'>QTY</div>"
                    "</div>"
                )

                for idx, (name, qty) in enumerate(ranking):
                    rank_num = idx + 1
                    rank_cls = ""
                    if rank_num == 1:
                        rank_cls = "row-1"
                        rank_label = "🥇"
                    elif rank_num == 2:
                        rank_cls = "row-2"
                        rank_label = "🥈"
                    elif rank_num == 3:
                        rank_cls = "row-3"
                        rank_label = "🥉"
                    else:
                        rank_label = str(rank_num)

                    av = get_avatar_table(name)

                    baris_html += (
                        "<div class='tbl-row " + rank_cls + "'>"
                        "<div class='tbl-rank'>" + rank_label + "</div>"
                        "<div class='tbl-avatar'>" + av + "</div>"
                        "<div class='tbl-name'>" + name + "</div>"
                        "<div class='tbl-score'>" + str(qty) + " Pcs</div>"
                        "</div>"
                    )

                baris_html += (
                    "<div class='tbl-footer'>"
                    "Halaman Peringkat Lengkap • " + short +
                    "</div>"
                    "</div>"
                )
                st.markdown(baris_html, unsafe_allow_html=True)
            else:
                st.info("Belum ada data peringkat untuk periode ini.")

            # ==== TOMBOL KEMBALI ====
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⬅️ KEMBALI KE HALL OF FAME PSM", key="btn_table_back", use_container_width=True):
                st.session_state["hof_sub_page"] = "hof_psm"
                st.rerun()

            st.stop()

                # =========================================================================
        # ⚔️ HALAMAN 3B: HALL OF FAME PWP & SG (2 TAB, CAROUSEL ALA PSM)
        # =========================================================================
        elif (
            st.session_state.get("campaign_sub_page") == "view_hall_of_fame"
            and st.session_state.get("hof_sub_page") == "hof_pps"
        ):

            url_gambar_latar = "https://i.imgur.com/kMo29aW.jpeg"
            import hashlib

            # ==== FUNGSI AVATAR ====
            def get_avatar(name):
                list_avatar_rpg = [
                    "🧙‍♂️", "🧝‍♂️", "🧝‍♀️", "⚔️", "🎯", "🛡️", "🦁", "🦅",
                    "🐺", "👑", "💎", "🔮", "🔥", "🏹", "🪄", "🗡️",
                    "⚗️", "🧛‍♂️", "🧟‍♂️", "🐉", "🦉", "🐻", "🦊", "🦌"
                ]
                h = int(hashlib.md5(str(name).upper().encode()).hexdigest(), 16)
                return list_avatar_rpg[h % len(list_avatar_rpg)]

            # ==== STATE: TAB YANG DIPILIH ====
            if "hof_pps_tab" not in st.session_state:
                st.session_state["hof_pps_tab"] = "pwp"

            # ==== CSS ====
            st.markdown("""
                <style>
                @keyframes crownFloat {
                    0%, 100% { transform: translateY(0) rotate(0deg); }
                    50% { transform: translateY(-6px) rotate(-3deg); }
                }
                @keyframes sparkleFloat1 {
                    0%, 100% { transform: translateY(0) scale(0.8); opacity: 0.5; }
                    50% { transform: translateY(-10px) scale(1.2); opacity: 1; }
                }
                @keyframes sparkleFloat2 {
                    0%, 100% { transform: translateY(-5px) scale(1); opacity: 0.7; }
                    50% { transform: translateY(5px) scale(0.8); opacity: 0.3; }
                }
                @keyframes avatarBob {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-3px); }
                }
                @keyframes cardEnter {
                    0% { opacity: 0; transform: translateY(30px) scale(0.95); }
                    100% { opacity: 1; transform: translateY(0) scale(1); }
                }
                @keyframes cardGlow {
                    0%, 100% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(168, 85, 247, 0.3); }
                    50% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 35px rgba(168, 85, 247, 0.6); }
                }
                @keyframes mysteryPulse {
                    0%, 100% { filter: drop-shadow(0 0 15px rgba(168, 85, 247, 0.6)); transform: scale(1); }
                    50% { filter: drop-shadow(0 0 30px rgba(168, 85, 247, 1)); transform: scale(1.08); }
                }
                @keyframes lockShake {
                    0%, 100% { transform: rotate(0deg); }
                    25% { transform: rotate(-5deg); }
                    75% { transform: rotate(5deg); }
                }

                .hof-pps-page-title {
                    text-align: center; color: #d8b4fe; font-family: monospace;
                    font-size: 22px; font-weight: 900; margin: 0 0 5px 0;
                    text-shadow: 0 0 15px rgba(168, 85, 247, 0.6);
                }
                .hof-pps-page-sub {
                    text-align: center; color: #cbd5e1; font-family: monospace;
                    font-size: 11.5px; margin-bottom: 20px;
                }

                /* TAB PWP/SG */
                .st-key-hof_pps_tab_radio {
                    display: flex !important;
                    justify-content: center !important;
                    margin: 5px 0 15px 0 !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] {
                    display: flex !important;
                    flex-direction: row !important;
                    justify-content: center !important;
                    align-items: center !important;
                    gap: 12px !important;
                    background: rgba(15, 23, 42, 0.6) !important;
                    border: 1.5px solid rgba(168, 85, 247, 0.4) !important;
                    border-radius: 14px !important;
                    padding: 8px !important;
                    width: fit-content !important;
                    margin: 0 auto !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] input[type="radio"] {
                    display: none !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] > label > div:first-child {
                    display: none !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] > label {
                    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
                    border: 2px solid #475569 !important;
                    border-radius: 10px !important;
                    padding: 10px 20px !important;
                    cursor: pointer !important;
                    transition: all 0.3s ease !important;
                    margin: 0 !important;
                    min-width: 140px !important;
                    text-align: center !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] > label p {
                    color: #94a3b8 !important;
                    font-family: monospace !important;
                    font-size: 12px !important;
                    font-weight: 900 !important;
                    letter-spacing: 1px !important;
                    margin: 0 !important;
                    white-space: nowrap !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] > label:hover {
                    border-color: #a855f7 !important;
                    transform: translateY(-2px) !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] > label:hover p {
                    color: #d8b4fe !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] > label:has(input:checked) {
                    background: linear-gradient(135deg, #7c3aed 0%, #4c1d95 100%) !important;
                    border-color: #d8b4fe !important;
                    box-shadow: 0 0 20px rgba(168, 85, 247, 0.7) !important;
                }
                .st-key-hof_pps_tab_radio div[role="radiogroup"] > label:has(input:checked) p {
                    color: #ffffff !important;
                    text-shadow: 0 0 8px rgba(216, 180, 254, 0.8) !important;
                }

                /* CAROUSEL */
                .hof-carousel-wrapper {
                    display: flex;
                    flex-direction: row;
                    flex-wrap: nowrap;
                    gap: 14px;
                    padding: 15px 20px 25px 20px;
                    justify-content: flex-start;
                    overflow-x: auto;
                    overflow-y: visible;
                    scroll-snap-type: x proximity;
                    -webkit-overflow-scrolling: touch;
                    scrollbar-width: thin;
                    width: 100%;
                    box-sizing: border-box;
                }
                .hof-carousel-wrapper::-webkit-scrollbar { height: 8px; }
                .hof-carousel-wrapper::-webkit-scrollbar-track {
                    background: rgba(15, 23, 42, 0.5);
                    border-radius: 4px;
                }
                .hof-carousel-wrapper::-webkit-scrollbar-thumb {
                    border-radius: 4px;
                }
                .hof-carousel-wrapper.warna-pwp::-webkit-scrollbar-thumb {
                    background: linear-gradient(90deg, #4c1d95, #a855f7, #4c1d95);
                }
                .hof-carousel-wrapper.warna-sg::-webkit-scrollbar-thumb {
                    background: linear-gradient(90deg, #9a3412, #fb923c, #9a3412);
                }

                .hof-card {
                    flex: 0 0 auto;
                    width: 280px;
                    min-width: 280px;
                    max-width: 280px;
                    min-height: 420px;
                    scroll-snap-align: center;
                    position: relative;
                    border-radius: 18px;
                    padding: 3px;
                    animation: cardEnter 0.7s cubic-bezier(0.25, 1, 0.5, 1) forwards,
                            cardGlow 4s infinite ease-in-out 1s;
                    transition: transform 0.3s ease;
                }
                /* Warna PWP */
                .hof-card.warna-pwp {
                    background: linear-gradient(160deg, #0f172a 0%, #1a1030 50%, #0f172a 100%);
                    box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(168, 85, 247, 0.3);
                }
                .hof-card.warna-pwp .hof-card-inner {
                    background: linear-gradient(160deg, #0a0d1a 0%, #151030 100%);
                    border: 2px solid #a855f7;
                    box-shadow: inset 0 0 20px rgba(168, 85, 247, 0.08);
                }
                /* Warna SG */
                .hof-card.warna-sg {
                    background: linear-gradient(160deg, #0f172a 0%, #221408 50%, #0f172a 100%);
                    box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(251, 146, 60, 0.3);
                }
                .hof-card.warna-sg .hof-card-inner {
                    background: linear-gradient(160deg, #0a0d1a 0%, #1a0f08 100%);
                    border: 2px solid #fb923c;
                    box-shadow: inset 0 0 20px rgba(251, 146, 60, 0.08);
                }

                .hof-card-inner {
                    border-radius: 16px;
                    padding: 25px 20px 20px 20px;
                    position: relative;
                    min-height: 414px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                }
                .hof-ornament {
                    position: absolute; font-size: 16px; line-height: 1; z-index: 5;
                }
                .warna-pwp .hof-ornament { color: #a855f7; filter: drop-shadow(0 0 4px rgba(168, 85, 247, 0.8)); }
                .warna-sg .hof-ornament { color: #fb923c; filter: drop-shadow(0 0 4px rgba(251, 146, 60, 0.8)); }
                .hof-orn-tl { top: 8px; left: 10px; }
                .hof-orn-tr { top: 8px; right: 10px; }
                .hof-orn-bl { bottom: 8px; left: 10px; }
                .hof-orn-br { bottom: 8px; right: 10px; }
                .hof-period-badge {
                    text-align: center;
                    border-radius: 8px;
                    padding: 7px 12px; font-family: monospace;
                    font-size: 11px; font-weight: 900;
                    letter-spacing: 1px; margin-bottom: 20px;
                    width: 100%;
                    box-sizing: border-box;
                }
                .warna-pwp .hof-period-badge {
                    background: linear-gradient(90deg, rgba(76, 29, 149, 0.4), rgba(168, 85, 247, 0.3), rgba(76, 29, 149, 0.4));
                    border: 1px solid #a855f7;
                    color: #d8b4fe;
                    text-shadow: 0 0 6px rgba(216, 180, 254, 0.5);
                }
                .warna-sg .hof-period-badge {
                    background: linear-gradient(90deg, rgba(154, 52, 18, 0.4), rgba(251, 146, 60, 0.3), rgba(154, 52, 18, 0.4));
                    border: 1px solid #fb923c;
                    color: #fdba74;
                    text-shadow: 0 0 6px rgba(253, 186, 116, 0.5);
                }

                .hof-crown-box { text-align: center; position: relative; height: 70px; margin-bottom: 8px; width: 100%; }
                .hof-crown { font-size: 48px; display: inline-block; animation: crownFloat 2.5s infinite ease-in-out; }
                .hof-sparkle { position: absolute; font-size: 14px; }
                .warna-pwp .hof-sparkle { color: #d8b4fe; filter: drop-shadow(0 0 6px #a855f7); }
                .warna-sg .hof-sparkle { color: #fdba74; filter: drop-shadow(0 0 6px #fb923c); }
                .hof-sparkle-1 { top: 5px; left: 30%; animation: sparkleFloat1 2s infinite ease-in-out; }
                .hof-sparkle-2 { top: 20px; right: 30%; animation: sparkleFloat2 2.3s infinite ease-in-out 0.3s; }
                .hof-sparkle-3 { bottom: 0px; left: 50%; transform: translateX(-50%); animation: sparkleFloat1 2.6s infinite ease-in-out 0.7s; }

                .hof-avatar-wrapper { text-align: center; margin: 10px 0 15px 0; }
                .hof-avatar-circle {
                    display: inline-flex; justify-content: center; align-items: center;
                    width: 80px; height: 80px; border-radius: 50%;
                    background: radial-gradient(circle, #1e293b 0%, #0f172a 100%);
                    font-size: 40px;
                    animation: avatarBob 2.5s infinite ease-in-out;
                }
                .warna-pwp .hof-avatar-circle {
                    border: 3px solid #a855f7;
                    box-shadow: 0 0 20px rgba(168, 85, 247, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.6);
                }
                .warna-sg .hof-avatar-circle {
                    border: 3px solid #fb923c;
                    box-shadow: 0 0 20px rgba(251, 146, 60, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.6);
                }

                .hof-champion-name {
                    text-align: center; font-family: monospace; font-size: 16px; font-weight: 900;
                    color: #ffffff; letter-spacing: 0.5px; margin-bottom: 12px;
                    line-height: 1.3; word-break: break-word;
                }
                .hof-champion-qty {
                    text-align: center; font-family: monospace; font-size: 22px; font-weight: 900;
                }
                .warna-pwp .hof-champion-qty {
                    color: #a855f7;
                    text-shadow: 0 0 15px rgba(168, 85, 247, 0.8);
                }
                .warna-sg .hof-champion-qty {
                    color: #fb923c;
                    text-shadow: 0 0 15px rgba(251, 146, 60, 0.8);
                }

                /* KARTU MISTERI */
                .hof-card-mystery .hof-card-inner {
                    background: linear-gradient(160deg, #0f0a1e 0%, #1a0d2e 50%, #0f0a1e 100%);
                    border: 2px dashed #7c3aed;
                    box-shadow: inset 0 0 30px rgba(124, 58, 237, 0.15);
                }
                .hof-mystery-icon {
                    font-size: 70px;
                    animation: mysteryPulse 2s infinite ease-in-out;
                    margin-bottom: 15px;
                }
                .hof-mystery-lock {
                    font-size: 35px;
                    display: inline-block;
                    animation: lockShake 2.5s infinite ease-in-out;
                    margin-bottom: 10px;
                }
                .hof-mystery-title {
                    text-align: center;
                    color: #d8b4fe;
                    font-family: monospace;
                    font-size: 14px;
                    font-weight: 900;
                    letter-spacing: 1.5px;
                    text-shadow: 0 0 12px rgba(168, 85, 247, 0.8);
                    margin-bottom: 15px;
                    line-height: 1.4;
                }
                .hof-mystery-sub {
                    text-align: center;
                    color: #94a3b8;
                    font-family: monospace;
                    font-size: 10.5px;
                    line-height: 1.6;
                    padding: 0 10px;
                }
                .hof-card-mystery .hof-period-badge {
                    background: linear-gradient(90deg, rgba(124, 58, 237, 0.4), rgba(168, 85, 247, 0.3), rgba(124, 58, 237, 0.4));
                    border: 1px solid #a855f7;
                    color: #d8b4fe;
                }

                /* KARTU EMPTY */
                .hof-card-empty .hof-card-inner {
                    background: linear-gradient(160deg, #0f172a 0%, #13110a 100%);
                    border: 2px dashed #475569;
                }
                .hof-empty-icon { font-size: 60px; opacity: 0.5; margin-bottom: 15px; }
                .hof-empty-title {
                    text-align: center; color: #94a3b8; font-family: monospace;
                    font-size: 12px; font-weight: 900; letter-spacing: 1px; margin-bottom: 10px;
                }
                .hof-empty-sub {
                    text-align: center; color: #64748b; font-family: monospace;
                    font-size: 10.5px; line-height: 1.6; padding: 0 10px;
                }

                /* TOMBOL */
                div[data-testid="stButton"] {
                    max-width: 480px !important;
                    margin: 8px auto 10px auto !important;
                    padding: 0 !important;
                }
                div[data-testid="stButton"] > button {
                    border-radius: 12px !important;
                    font-family: monospace !important;
                    font-size: 13px !important;
                    font-weight: bold !important;
                    padding: 13px 20px !important;
                    width: 100% !important;
                    display: block !important;
                    transition: all 0.3s ease !important;
                }
                .st-key-btn_hof_pps_back button {
                    background: rgba(100, 116, 139, 0.15) !important;
                    border: 2px solid #475569 !important;
                    color: #cbd5e1 !important;
                }
                .st-key-btn_hof_pps_back button:hover {
                    background: #475569 !important; color: #ffffff !important;
                }

                @media (max-width: 600px) {
                    .hof-card { width: 260px; min-width: 260px; max-width: 260px; }
                    .hof-carousel-wrapper { padding: 15px 15px 25px 15px; }
                    .st-key-hof_pps_tab_radio div[role="radiogroup"] > label { min-width: 110px !important; padding: 8px 12px !important; }
                    .st-key-hof_pps_tab_radio div[role="radiogroup"] > label p { font-size: 11px !important; }
                }
                @media (max-width: 380px) {
                    .hof-card { width: 240px; min-width: 240px; max-width: 240px; }
                }
                </style>
                """, unsafe_allow_html=True)

            # ==== BACKGROUND ====
            st.markdown(
                f"""
                <style>
                .stApp {{
                    background-image: linear-gradient(rgba(10, 13, 26, 0.85), rgba(10, 13, 26, 0.92)), url("{url_gambar_latar}") !important;
                    background-size: cover !important;
                    background-position: center !important;
                    background-repeat: no-repeat !important;
                    background-attachment: fixed !important;
                }}
                .main .block-container {{
                    background-color: transparent !important;
                    max-width: 100% !important;
                    padding-top: 3% !important;
                    padding-left: 0 !important;
                    padding-right: 0 !important;
                }}
                div[data-testid="stVerticalBlock"] {{ gap: 0rem !important; }}
                </style>
                """,
                unsafe_allow_html=True
            )

            # ==== HEADER ====
            st.markdown("<h2 class='hof-pps-page-title'>⚔️ HALL OF FAME PWP & SG ⚔️</h2>", unsafe_allow_html=True)
            st.markdown("<p class='hof-pps-page-sub'>Papan kehormatan program PWP & Serba Gratis</p>", unsafe_allow_html=True)

            # ==== TAB PWP & SG ====
            pilihan_tab = st.radio(
                "Pilih Papan",
                options=["⚔️ PAPAN PWP", "🎁 PAPAN SG"],
                index=0 if st.session_state.get("hof_pps_tab", "pwp") == "pwp" else 1,
                key="hof_pps_tab_radio",
                label_visibility="collapsed",
                horizontal=True,
            )

            tab_aktif = "pwp" if "PWP" in pilihan_tab else "sg"
            if tab_aktif != st.session_state.get("hof_pps_tab"):
                st.session_state["hof_pps_tab"] = tab_aktif

            kolom_qty = "qty_pwp" if tab_aktif == "pwp" else "qty_sg"
            kolom_label = "PWP" if tab_aktif == "pwp" else "SG"
            warna_class = "warna-pwp" if tab_aktif == "pwp" else "warna-sg"
            ikon_juara = "⚔️" if tab_aktif == "pwp" else "🎁"

            # ==== AMBIL DATA ====
            df_pps_periode = st.session_state.get("periods_pps_df", pd.DataFrame()).copy()
            df_sales_pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()

            for df in [df_pps_periode, df_sales_pps]:
                if not df.empty:
                    df.columns = df.columns.astype(str).str.strip().str.lower()

            today = datetime.now().date()

            # ==== BANGUN KARTU DINAMIS BERDASARKAN PERIODE_PPS ====
            kartu_periode = []
            kartu_bulan = []
            kartu_alltime = None

            if not df_pps_periode.empty and all(
                c in df_pps_periode.columns for c in ["period_id", "start_date", "end_date"]
            ):
                df_pps_periode["start_dt"] = pd.to_datetime(df_pps_periode["start_date"], errors="coerce")
                df_pps_periode["end_dt"] = pd.to_datetime(df_pps_periode["end_date"], errors="coerce")
                df_pps_periode = df_pps_periode.dropna(subset=["start_dt", "end_dt"])

                # Filter sesuai tab: PWP atau SG
                if tab_aktif == "pwp":
                    # PWP — exact prefix
                    df_filter = df_pps_periode[
                        df_pps_periode["period_id"].astype(str).str.upper().str.strip().str.startswith("PWP", na=False)
                    ]
                else:
                    # SG — exact prefix SGS (bukan SGR!)
                    df_filter = df_pps_periode[
                        df_pps_periode["period_id"].astype(str).str.upper().str.strip().str.startswith("SGS", na=False)
                    ]

                # Urut ascending (terlama dulu)
                df_filter = df_filter.sort_values("start_dt", ascending=True).reset_index(drop=True)

                # === KARTU PERIODE ===
                for _, row_p in df_filter.iterrows():
                    p_id = str(row_p["period_id"]).strip()
                    p_name = str(row_p.get("period_name", p_id)).strip()
                    p_start = row_p["start_dt"].date()
                    p_end = row_p["end_dt"].date()
                    is_selesai = p_end < today

                    if p_start.month == p_end.month:
                        label_tgl = f"{p_start.day}-{p_end.day} {p_start.strftime('%b').upper()}"
                    else:
                        label_tgl = f"{p_start.day} {p_start.strftime('%b').upper()} - {p_end.day} {p_end.strftime('%b').upper()}"

                    kartu_periode.append({
                        "key": f"periode_{p_id}",
                        "label": f"📅 {label_tgl}",
                        "tipe": "periode",
                        "period_id": p_id,
                        "start_date": p_start,
                        "end_date": p_end,
                        "is_active": not is_selesai,
                    })

                # === KARTU ALL TIME (yang sudah selesai) ===
                df_selesai = df_filter[df_filter["end_dt"].dt.date < today]
                if not df_selesai.empty:
                    kartu_alltime = {
                        "key": "alltime",
                        "label": "🏆 ALL TIME",
                        "tipe": "alltime",
                        "periode_list": [
                            {
                                "period_id": str(r["period_id"]).strip(),
                                "start_date": r["start_dt"].date(),
                                "end_date": r["end_dt"].date(),
                            }
                            for _, r in df_selesai.iterrows()
                        ],
                        "is_active": False,
                    }

                # === KARTU BULAN ===
                if not df_selesai.empty:
                    df_bulan = df_selesai.copy()
                    df_bulan["bulan_key"] = df_bulan["start_dt"].dt.strftime("%Y-%m")
                    df_bulan["bulan_label"] = df_bulan["start_dt"].dt.strftime("%B %Y").str.upper()

                    bulan_unik = df_bulan[["bulan_key", "bulan_label"]].drop_duplicates().sort_values("bulan_key", ascending=True)

                    for _, row_bulan in bulan_unik.iterrows():
                        b_key = row_bulan["bulan_key"]
                        b_label = row_bulan["bulan_label"]
                        periode_bulan = df_bulan[
                            df_bulan["bulan_key"] == b_key
                        ]

                        kartu_bulan.append({
                            "key": f"bulan_{b_key}",
                            "label": f"📆 {b_label}",
                            "tipe": "bulan",
                            "periode_list": [
                                {
                                    "period_id": str(r["period_id"]).strip(),
                                    "start_date": r["start_dt"].date(),
                                    "end_date": r["end_dt"].date(),
                                }
                                for _, r in periode_bulan.iterrows()
                            ],
                            "is_active": False,
                        })

            # Gabung urutan
            kartu_list = kartu_periode + kartu_bulan
            if kartu_alltime:
                kartu_list.append(kartu_alltime)

            # ==== HITUNG JUARA ====
            def get_juara(kartu):
                """Ambil juara 1 untuk kartu tertentu dari sales_pps_df."""
                if df_sales_pps.empty:
                    return None
                if "kasir_name" not in df_sales_pps.columns:
                    return None
                if kolom_qty not in df_sales_pps.columns:
                    return None
                if "start_date" not in df_sales_pps.columns:
                    return None

                df_temp = df_sales_pps.copy()

                # Cari kolom tanggal yang tersedia (prioritas: updated_at)
                _date_col = None
                for _c in ["updated_at", "start_date", "tanggal", "date"]:
                    if _c in df_temp.columns:
                        _date_col = _c
                        break

                if _date_col is None:
                    return None

                df_temp["_start"] = pd.to_datetime(df_temp[_date_col], errors="coerce")
                df_temp = df_temp.dropna(subset=["_start"])

                # Tentukan daftar periode untuk kartu ini
                if kartu["tipe"] == "periode":
                    periode_list = [{
                        "start_date": kartu["start_date"],
                        "end_date": kartu["end_date"],
                    }]
                else:
                    periode_list = kartu.get("periode_list", [])

                if not periode_list:
                    return None

                # Filter
                mask = pd.Series([False] * len(df_temp), index=df_temp.index)
                for p in periode_list:
                    mask = mask | (
                        (df_temp["_start"].dt.date >= p["start_date"]) &
                        (df_temp["_start"].dt.date <= p["end_date"])
                    )
                df_temp = df_temp[mask]

                if df_temp.empty:
                    return None

                df_temp["kasir_clean"] = df_temp["kasir_name"].astype(str).str.strip()
                df_temp[kolom_qty] = pd.to_numeric(df_temp[kolom_qty], errors="coerce").fillna(0)

                grouped = df_temp.groupby("kasir_clean")[kolom_qty].sum().reset_index()
                grouped = grouped[grouped[kolom_qty] > 0]
                if grouped.empty:
                    return None

                grouped = grouped.sort_values(kolom_qty, ascending=False).reset_index(drop=True)
                top1 = grouped.iloc[0]

                return {
                    "nama": str(top1["kasir_clean"]),
                    "qty": int(top1[kolom_qty]),
                }

            for k in kartu_list:
                k["juara"] = get_juara(k)

            total_kartu = len(kartu_list)

            # ==== JIKA BELUM ADA KARTU ====
            if total_kartu == 0:
                st.markdown(
                    "<div style='background: rgba(15,23,42,0.85); border: 2px dashed #7c3aed; "
                    "border-radius: 12px; padding: 40px 20px; margin: 30px auto; max-width: 500px; "
                    "text-align: center;'>"
                    "<div style='font-size: 60px; opacity: 0.5; margin-bottom: 15px;'>📜</div>"
                    "<div style='color: #a855f7; font-family: monospace; font-size: 14px; font-weight: 900; "
                    "letter-spacing: 1px; margin-bottom: 8px;'>BELUM ADA PERIODE " + kolom_label + "</div>"
                    "<div style='color: #64748b; font-family: monospace; font-size: 11px; line-height: 1.6;'>"
                    "Data periode akan muncul setelah admin mendaftarkan periode di sheet PERIODE_PPS."
                    "</div></div>",
                    unsafe_allow_html=True
                )
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("⬅️ KEMBALI KE HALL OF FAME", key="btn_hof_pps_back", use_container_width=True):
                    st.session_state["hof_sub_page"] = None
                    st.rerun()
                st.stop()

            # ==== CAROUSEL KARTU ====
            kartu_parts = ["<div class='hof-carousel-wrapper " + warna_class + "'>"]

            for idx, k in enumerate(kartu_list):
                alltime_class = "hof-card-alltime" if k["tipe"] == "alltime" else ""

                if k.get("is_active") and k["tipe"] == "periode":
                    konten = (
                        "<div class='hof-mystery-icon'>❓</div>"
                        "<div class='hof-mystery-lock'>🔒</div>"
                        "<div class='hof-mystery-title'>AWAITING FINAL RESULTS</div>"
                        "<div class='hof-mystery-sub'>Prasasti juara akan dibuka setelah periode selesai (H+1).<br><br>"
                        "Selesaikan pertempuran periode ini dulu!</div>"
                    )
                    card_cls = "hof-card hof-card-mystery " + warna_class
                elif k.get("juara"):
                    juara = k["juara"]
                    av = get_avatar(juara["nama"])
                    konten = (
                        "<div class='hof-crown-box'>"
                        "<span class='hof-sparkle hof-sparkle-1'>✦</span>"
                        "<span class='hof-crown'>" + ikon_juara + "</span>"
                        "<span class='hof-sparkle hof-sparkle-2'>✦</span>"
                        "<span class='hof-sparkle hof-sparkle-3'>✦</span>"
                        "</div>"
                        "<div class='hof-avatar-wrapper'>"
                        "<div class='hof-avatar-circle'>" + av + "</div>"
                        "</div>"
                        "<div class='hof-champion-name'>" + juara["nama"] + "</div>"
                        "<div class='hof-champion-qty'>" + str(juara["qty"]) + " Pcs</div>"
                    )
                    card_cls = "hof-card " + warna_class + " " + alltime_class
                else:
                    konten = (
                        "<div class='hof-empty-icon'>📭</div>"
                        "<div class='hof-empty-title'>BELUM ADA PENJUALAN</div>"
                        "<div class='hof-empty-sub'>Tidak ada data penjualan " + kolom_label + " untuk periode ini.</div>"
                    )
                    card_cls = "hof-card hof-card-empty " + warna_class + " " + alltime_class

                kartu_parts.append(
                    "<div class='" + card_cls + "'>"
                    "<div class='hof-card-inner'>"
                    "<div class='hof-ornament hof-orn-tl'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-tr'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-bl'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-br'>⚜️</div>"
                    "<div class='hof-period-badge'>" + k["label"] + "</div>"
                    + konten +
                    "</div>"
                    "</div>"
                )

            kartu_parts.append("</div>")
            kartu_html = "".join(kartu_parts).strip()
            st.markdown(kartu_html, unsafe_allow_html=True)

            # ==== TOMBOL KEMBALI ====
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⬅️ KEMBALI KE HALL OF FAME", key="btn_hof_pps_back", use_container_width=True):
                st.session_state["hof_sub_page"] = None
                st.rerun()

            st.stop()

        # =========================================================================
        # 🍃 HALAMAN 3C: HALL OF FAME SUEGER (DUAL: QTY + %)
        # =========================================================================
        elif (
            st.session_state.get("campaign_sub_page") == "view_hall_of_fame"
            and st.session_state.get("hof_sub_page") == "hof_sueger"
        ):

            url_gambar_latar = "https://i.imgur.com/kMo29aW.jpeg"
            import hashlib

            # ==== FUNGSI AVATAR ====
            def get_avatar(name):
                list_avatar_rpg = [
                    "🧙‍♂️", "🧝‍♂️", "🧝‍♀️", "⚔️", "🎯", "🛡️", "🦁", "🦅",
                    "🐺", "👑", "💎", "🔮", "🔥", "🏹", "🪄", "🗡️",
                    "⚗️", "🧛‍♂️", "🧟‍♂️", "🐉", "🦉", "🐻", "🦊", "🦌"
                ]
                h = int(hashlib.md5(str(name).upper().encode()).hexdigest(), 16)
                return list_avatar_rpg[h % len(list_avatar_rpg)]

            # ==== CSS ====
            st.markdown("""
                <style>
                @keyframes crownFloat {
                    0%, 100% { transform: translateY(0) rotate(0deg); }
                    50% { transform: translateY(-6px) rotate(-3deg); }
                }
                @keyframes sparkleFloat1 {
                    0%, 100% { transform: translateY(0) scale(0.8); opacity: 0.5; }
                    50% { transform: translateY(-10px) scale(1.2); opacity: 1; }
                }
                @keyframes sparkleFloat2 {
                    0%, 100% { transform: translateY(-5px) scale(1); opacity: 0.7; }
                    50% { transform: translateY(5px) scale(0.8); opacity: 0.3; }
                }
                @keyframes avatarBob {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-3px); }
                }
                @keyframes cardEnter {
                    0% { opacity: 0; transform: translateY(30px) scale(0.95); }
                    100% { opacity: 1; transform: translateY(0) scale(1); }
                }
                @keyframes cardGlowQty {
                    0%, 100% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(16, 185, 129, 0.3); }
                    50% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 35px rgba(16, 185, 129, 0.6); }
                }
                @keyframes cardGlowPct {
                    0%, 100% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(110, 231, 183, 0.3); }
                    50% { box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 35px rgba(110, 231, 183, 0.6); }
                }
                @keyframes mysteryPulse {
                    0%, 100% { filter: drop-shadow(0 0 15px rgba(16, 185, 129, 0.6)); transform: scale(1); }
                    50% { filter: drop-shadow(0 0 30px rgba(16, 185, 129, 1)); transform: scale(1.08); }
                }
                @keyframes lockShake {
                    0%, 100% { transform: rotate(0deg); }
                    25% { transform: rotate(-5deg); }
                    75% { transform: rotate(5deg); }
                }

                .hof-sgr-page-title {
                    text-align: center; color: #6ee7b7; font-family: monospace;
                    font-size: 22px; font-weight: 900; margin: 0 0 5px 0;
                    text-shadow: 0 0 15px rgba(16, 185, 129, 0.6);
                }
                .hof-sgr-page-sub {
                    text-align: center; color: #cbd5e1; font-family: monospace;
                    font-size: 11.5px; margin-bottom: 20px;
                }

                .hof-carousel-wrapper {
                    display: flex;
                    flex-direction: row;
                    flex-wrap: nowrap;
                    gap: 14px;
                    padding: 15px 20px 25px 20px;
                    justify-content: flex-start;
                    overflow-x: auto;
                    overflow-y: visible;
                    scroll-snap-type: x proximity;
                    -webkit-overflow-scrolling: touch;
                    scrollbar-width: thin;
                    width: 100%;
                    box-sizing: border-box;
                }
                .hof-carousel-wrapper::-webkit-scrollbar { height: 8px; }
                .hof-carousel-wrapper::-webkit-scrollbar-track {
                    background: rgba(15, 23, 42, 0.5);
                    border-radius: 4px;
                }
                .hof-carousel-wrapper::-webkit-scrollbar-thumb {
                    background: linear-gradient(90deg, #064e3b, #10b981, #064e3b);
                    border-radius: 4px;
                }

                .hof-card {
                    flex: 0 0 auto;
                    width: 280px;
                    min-width: 280px;
                    max-width: 280px;
                    min-height: 420px;
                    scroll-snap-align: center;
                    position: relative;
                    border-radius: 18px;
                    padding: 3px;
                    animation: cardEnter 0.7s cubic-bezier(0.25, 1, 0.5, 1) forwards;
                    transition: transform 0.3s ease;
                }
                /* QTY — hijau tua */
                .hof-card.mode-qty {
                    background: linear-gradient(160deg, #0f172a 0%, #0a1f16 50%, #0f172a 100%);
                    animation: cardEnter 0.7s cubic-bezier(0.25, 1, 0.5, 1) forwards,
                            cardGlowQty 4s infinite ease-in-out 1s;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(16, 185, 129, 0.3);
                }
                .hof-card.mode-qty .hof-card-inner {
                    background: linear-gradient(160deg, #0a0d1a 0%, #0a1f16 100%);
                    border: 2px solid #10b981;
                    box-shadow: inset 0 0 20px rgba(16, 185, 129, 0.08);
                }
                /* % — hijau muda */
                .hof-card.mode-pct {
                    background: linear-gradient(160deg, #0f172a 0%, #0e2a20 50%, #0f172a 100%);
                    animation: cardEnter 0.7s cubic-bezier(0.25, 1, 0.5, 1) forwards,
                            cardGlowPct 4s infinite ease-in-out 1s;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.6), 0 0 15px rgba(110, 231, 183, 0.3);
                }
                .hof-card.mode-pct .hof-card-inner {
                    background: linear-gradient(160deg, #0a0d1a 0%, #0e2a20 100%);
                    border: 2px solid #6ee7b7;
                    box-shadow: inset 0 0 20px rgba(110, 231, 183, 0.08);
                }

                .hof-card-inner {
                    border-radius: 16px;
                    padding: 25px 20px 20px 20px;
                    position: relative;
                    min-height: 414px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                }
                .hof-ornament {
                    position: absolute; font-size: 16px; line-height: 1; z-index: 5;
                }
                .mode-qty .hof-ornament { color: #10b981; filter: drop-shadow(0 0 4px rgba(16, 185, 129, 0.8)); }
                .mode-pct .hof-ornament { color: #6ee7b7; filter: drop-shadow(0 0 4px rgba(110, 231, 183, 0.8)); }
                .hof-orn-tl { top: 8px; left: 10px; }
                .hof-orn-tr { top: 8px; right: 10px; }
                .hof-orn-bl { bottom: 8px; left: 10px; }
                .hof-orn-br { bottom: 8px; right: 10px; }

                .hof-period-badge {
                    text-align: center;
                    border-radius: 8px;
                    padding: 7px 12px; font-family: monospace;
                    font-size: 10.5px; font-weight: 900;
                    letter-spacing: 1px; margin-bottom: 20px;
                    width: 100%;
                    box-sizing: border-box;
                }
                .mode-qty .hof-period-badge {
                    background: linear-gradient(90deg, rgba(6, 78, 59, 0.5), rgba(16, 185, 129, 0.3), rgba(6, 78, 59, 0.5));
                    border: 1px solid #10b981;
                    color: #6ee7b7;
                    text-shadow: 0 0 6px rgba(110, 231, 183, 0.5);
                }
                .mode-pct .hof-period-badge {
                    background: linear-gradient(90deg, rgba(16, 185, 129, 0.5), rgba(110, 231, 183, 0.3), rgba(16, 185, 129, 0.5));
                    border: 1px solid #6ee7b7;
                    color: #ffffff;
                    text-shadow: 0 0 6px rgba(255, 255, 255, 0.5);
                }

                .hof-crown-box { text-align: center; position: relative; height: 70px; margin-bottom: 8px; width: 100%; }
                .hof-crown { font-size: 48px; display: inline-block; animation: crownFloat 2.5s infinite ease-in-out; }
                .hof-sparkle { position: absolute; font-size: 14px; }
                .mode-qty .hof-sparkle { color: #6ee7b7; filter: drop-shadow(0 0 6px #10b981); }
                .mode-pct .hof-sparkle { color: #ffffff; filter: drop-shadow(0 0 6px #6ee7b7); }
                .hof-sparkle-1 { top: 5px; left: 30%; animation: sparkleFloat1 2s infinite ease-in-out; }
                .hof-sparkle-2 { top: 20px; right: 30%; animation: sparkleFloat2 2.3s infinite ease-in-out 0.3s; }
                .hof-sparkle-3 { bottom: 0px; left: 50%; transform: translateX(-50%); animation: sparkleFloat1 2.6s infinite ease-in-out 0.7s; }

                .hof-avatar-wrapper { text-align: center; margin: 10px 0 15px 0; }
                .hof-avatar-circle {
                    display: inline-flex; justify-content: center; align-items: center;
                    width: 80px; height: 80px; border-radius: 50%;
                    background: radial-gradient(circle, #1e293b 0%, #0f172a 100%);
                    font-size: 40px;
                    animation: avatarBob 2.5s infinite ease-in-out;
                }
                .mode-qty .hof-avatar-circle {
                    border: 3px solid #10b981;
                    box-shadow: 0 0 20px rgba(16, 185, 129, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.6);
                }
                .mode-pct .hof-avatar-circle {
                    border: 3px solid #6ee7b7;
                    box-shadow: 0 0 20px rgba(110, 231, 183, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.6);
                }

                .hof-champion-name {
                    text-align: center; font-family: monospace; font-size: 16px; font-weight: 900;
                    color: #ffffff; letter-spacing: 0.5px; margin-bottom: 12px;
                    line-height: 1.3; word-break: break-word;
                }
                .hof-champion-qty {
                    text-align: center; font-family: monospace; font-size: 22px; font-weight: 900;
                    margin-bottom: 5px;
                }
                .mode-qty .hof-champion-qty {
                    color: #10b981;
                    text-shadow: 0 0 15px rgba(16, 185, 129, 0.8);
                }
                .mode-pct .hof-champion-qty {
                    color: #6ee7b7;
                    text-shadow: 0 0 15px rgba(110, 231, 183, 0.8);
                }
                .hof-champion-detail {
                    text-align: center; font-family: monospace; font-size: 9.5px;
                    color: #94a3b8; letter-spacing: 0.3px; line-height: 1.5;
                }

                /* KARTU MISTERI */
                .hof-card-mystery .hof-card-inner {
                    background: linear-gradient(160deg, #0f0a1e 0%, #1a0d2e 50%, #0f0a1e 100%);
                    border: 2px dashed #7c3aed;
                    box-shadow: inset 0 0 30px rgba(124, 58, 237, 0.15);
                }
                .hof-mystery-icon {
                    font-size: 70px;
                    animation: mysteryPulse 2s infinite ease-in-out;
                    margin-bottom: 15px;
                }
                .hof-mystery-lock {
                    font-size: 35px;
                    display: inline-block;
                    animation: lockShake 2.5s infinite ease-in-out;
                    margin-bottom: 10px;
                }
                .hof-mystery-title {
                    text-align: center;
                    color: #d8b4fe;
                    font-family: monospace;
                    font-size: 14px;
                    font-weight: 900;
                    letter-spacing: 1.5px;
                    text-shadow: 0 0 12px rgba(168, 85, 247, 0.8);
                    margin-bottom: 15px;
                    line-height: 1.4;
                }
                .hof-mystery-sub {
                    text-align: center;
                    color: #94a3b8;
                    font-family: monospace;
                    font-size: 10.5px;
                    line-height: 1.6;
                    padding: 0 10px;
                }
                .hof-card-mystery .hof-period-badge {
                    background: linear-gradient(90deg, rgba(124, 58, 237, 0.4), rgba(168, 85, 247, 0.3), rgba(124, 58, 237, 0.4));
                    border: 1px solid #a855f7;
                    color: #d8b4fe;
                }

                /* KARTU EMPTY */
                .hof-card-empty .hof-card-inner {
                    background: linear-gradient(160deg, #0f172a 0%, #13110a 100%);
                    border: 2px dashed #475569;
                }
                .hof-empty-icon { font-size: 60px; opacity: 0.5; margin-bottom: 15px; }
                .hof-empty-title {
                    text-align: center; color: #94a3b8; font-family: monospace;
                    font-size: 12px; font-weight: 900; letter-spacing: 1px; margin-bottom: 10px;
                }
                .hof-empty-sub {
                    text-align: center; color: #64748b; font-family: monospace;
                    font-size: 10.5px; line-height: 1.6; padding: 0 10px;
                }

                div[data-testid="stButton"] {
                    max-width: 480px !important;
                    margin: 8px auto 10px auto !important;
                    padding: 0 !important;
                }
                div[data-testid="stButton"] > button {
                    border-radius: 12px !important;
                    font-family: monospace !important;
                    font-size: 13px !important;
                    font-weight: bold !important;
                    padding: 13px 20px !important;
                    width: 100% !important;
                    display: block !important;
                    transition: all 0.3s ease !important;
                }
                .st-key-btn_hof_sueger_back button {
                    background: rgba(100, 116, 139, 0.15) !important;
                    border: 2px solid #475569 !important;
                    color: #cbd5e1 !important;
                }
                .st-key-btn_hof_sueger_back button:hover {
                    background: #475569 !important; color: #ffffff !important;
                }

                @media (max-width: 600px) {
                    .hof-card { width: 260px; min-width: 260px; max-width: 260px; }
                    .hof-carousel-wrapper { padding: 15px 15px 25px 15px; }
                }
                @media (max-width: 380px) {
                    .hof-card { width: 240px; min-width: 240px; max-width: 240px; }
                }
                </style>
                """, unsafe_allow_html=True)

            # ==== BACKGROUND ====
            st.markdown(
                f"""
                <style>
                .stApp {{
                    background-image: linear-gradient(rgba(10, 13, 26, 0.85), rgba(10, 13, 26, 0.92)), url("{url_gambar_latar}") !important;
                    background-size: cover !important;
                    background-position: center !important;
                    background-repeat: no-repeat !important;
                    background-attachment: fixed !important;
                }}
                .main .block-container {{
                    background-color: transparent !important;
                    max-width: 100% !important;
                    padding-top: 3% !important;
                    padding-left: 0 !important;
                    padding-right: 0 !important;
                }}
                div[data-testid="stVerticalBlock"] {{ gap: 0rem !important; }}
                </style>
                """,
                unsafe_allow_html=True
            )

            # ==== HEADER ====
            st.markdown("<h2 class='hof-sgr-page-title'>🍃 HALL OF FAME SUEGER 🍃</h2>", unsafe_allow_html=True)
            st.markdown("<p class='hof-sgr-page-sub'>Papan kehormatan program Sueger — Qty & Achievement %</p>", unsafe_allow_html=True)

            # ==== AMBIL DATA ====
            df_pps_periode = st.session_state.get("periods_pps_df", pd.DataFrame()).copy()
            df_sales_pps = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()

            for df in [df_pps_periode, df_sales_pps]:
                if not df.empty:
                    df.columns = df.columns.astype(str).str.strip().str.lower()

            today = datetime.now().date()

            # ==== BANGUN KARTU (Base) ====
            kartu_base = []

            if not df_pps_periode.empty and all(
                c in df_pps_periode.columns for c in ["period_id", "start_date", "end_date"]
            ):
                df_pps_periode["start_dt"] = pd.to_datetime(df_pps_periode["start_date"], errors="coerce")
                df_pps_periode["end_dt"] = pd.to_datetime(df_pps_periode["end_date"], errors="coerce")
                df_pps_periode = df_pps_periode.dropna(subset=["start_dt", "end_dt"])

                df_filter = df_pps_periode[
                    df_pps_periode["period_id"].astype(str).str.upper().str.strip().str.startswith("SGR", na=False)
                ]

                df_filter = df_filter.sort_values("start_dt", ascending=True).reset_index(drop=True)

                # KARTU PERIODE
                for _, row_p in df_filter.iterrows():
                    p_id = str(row_p["period_id"]).strip()
                    p_start = row_p["start_dt"].date()
                    p_end = row_p["end_dt"].date()
                    is_selesai = p_end < today

                    if p_start.month == p_end.month:
                        label_tgl = f"{p_start.day}-{p_end.day} {p_start.strftime('%b').upper()}"
                    else:
                        label_tgl = f"{p_start.day} {p_start.strftime('%b').upper()} - {p_end.day} {p_end.strftime('%b').upper()}"

                    kartu_base.append({
                        "key": f"periode_{p_id}",
                        "label_tgl": label_tgl,
                        "tipe": "periode",
                        "start_date": p_start,
                        "end_date": p_end,
                        "is_active": not is_selesai,
                    })

                # ALL TIME
                df_selesai = df_filter[df_filter["end_dt"].dt.date < today]
                if not df_selesai.empty:
                    kartu_base.append({
                        "key": "alltime",
                        "label_tgl": "ALL TIME",
                        "tipe": "alltime",
                        "periode_list": [
                            {"start_date": r["start_dt"].date(), "end_date": r["end_dt"].date()}
                            for _, r in df_selesai.iterrows()
                        ],
                        "is_active": False,
                    })

                # BULAN
                if not df_selesai.empty:
                    df_bulan = df_selesai.copy()
                    df_bulan["bulan_key"] = df_bulan["start_dt"].dt.strftime("%Y-%m")
                    df_bulan["bulan_label"] = df_bulan["start_dt"].dt.strftime("%B %Y").str.upper()

                    bulan_unik = df_bulan[["bulan_key", "bulan_label"]].drop_duplicates().sort_values("bulan_key", ascending=True)

                    for _, row_bulan in bulan_unik.iterrows():
                        b_key = row_bulan["bulan_key"]
                        b_label = row_bulan["bulan_label"]
                        periode_bulan = df_bulan[df_bulan["bulan_key"] == b_key]

                        kartu_base.append({
                            "key": f"bulan_{b_key}",
                            "label_tgl": b_label,
                            "tipe": "bulan",
                            "periode_list": [
                                {"start_date": r["start_dt"].date(), "end_date": r["end_dt"].date()}
                                for _, r in periode_bulan.iterrows()
                            ],
                            "is_active": False,
                        })

            # ==== HITUNG JUARA QTY ====
            def get_juara_qty(kartu):
                if df_sales_pps.empty or "kasir_name" not in df_sales_pps.columns:
                    return None

                _kolom = None
                for _c in ["qty_sueger", "redeem_sueger", "qty_suegeer", "redeem_suegeer"]:
                    if _c in df_sales_pps.columns:
                        _kolom = _c
                        break
                if _kolom is None:
                    return None

                _date_col = None
                for _c in ["updated_at", "start_date", "tanggal", "date"]:
                    if _c in df_sales_pps.columns:
                        _date_col = _c
                        break
                if _date_col is None:
                    return None

                df_temp = df_sales_pps.copy()
                df_temp["_start"] = pd.to_datetime(df_temp[_date_col], errors="coerce")
                df_temp = df_temp.dropna(subset=["_start"])

                if kartu["tipe"] == "periode":
                    periode_list = [{"start_date": kartu["start_date"], "end_date": kartu["end_date"]}]
                else:
                    periode_list = kartu.get("periode_list", [])

                if not periode_list:
                    return None

                mask = pd.Series([False] * len(df_temp), index=df_temp.index)
                for p in periode_list:
                    mask = mask | (
                        (df_temp["_start"].dt.date >= p["start_date"]) &
                        (df_temp["_start"].dt.date <= p["end_date"])
                    )
                df_temp = df_temp[mask]

                if df_temp.empty:
                    return None

                df_temp["kasir_clean"] = df_temp["kasir_name"].astype(str).str.strip()
                df_temp[_kolom] = pd.to_numeric(df_temp[_kolom], errors="coerce").fillna(0)

                grouped = df_temp.groupby("kasir_clean")[_kolom].sum().reset_index()
                grouped = grouped[grouped[_kolom] > 0]
                if grouped.empty:
                    return None

                grouped = grouped.sort_values(_kolom, ascending=False).reset_index(drop=True)
                top1 = grouped.iloc[0]

                return {"nama": str(top1["kasir_clean"]), "qty": int(top1[_kolom])}

            # ==== HITUNG JUARA % ====
            def get_juara_pct(kartu, min_syarat=10):
                if df_sales_pps.empty or "kasir_name" not in df_sales_pps.columns:
                    return None
                if "syarat_sueger" not in df_sales_pps.columns or "redeem_sueger" not in df_sales_pps.columns:
                    return None

                _date_col = None
                for _c in ["updated_at", "start_date", "tanggal", "date"]:
                    if _c in df_sales_pps.columns:
                        _date_col = _c
                        break
                if _date_col is None:
                    return None

                df_temp = df_sales_pps.copy()
                df_temp["_start"] = pd.to_datetime(df_temp[_date_col], errors="coerce")
                df_temp = df_temp.dropna(subset=["_start"])

                if kartu["tipe"] == "periode":
                    periode_list = [{"start_date": kartu["start_date"], "end_date": kartu["end_date"]}]
                else:
                    periode_list = kartu.get("periode_list", [])

                if not periode_list:
                    return None

                mask = pd.Series([False] * len(df_temp), index=df_temp.index)
                for p in periode_list:
                    mask = mask | (
                        (df_temp["_start"].dt.date >= p["start_date"]) &
                        (df_temp["_start"].dt.date <= p["end_date"])
                    )
                df_temp = df_temp[mask]

                if df_temp.empty:
                    return None

                df_temp["kasir_clean"] = df_temp["kasir_name"].astype(str).str.strip()
                df_temp["syarat_sueger"] = pd.to_numeric(df_temp["syarat_sueger"], errors="coerce").fillna(0)
                df_temp["redeem_sueger"] = pd.to_numeric(df_temp["redeem_sueger"], errors="coerce").fillna(0)

                grouped = df_temp.groupby("kasir_clean").agg(
                    total_syarat=("syarat_sueger", "sum"),
                    total_redeem=("redeem_sueger", "sum"),
                ).reset_index()

                # Skip syarat=0
                grouped = grouped[grouped["total_syarat"] > 0]
                if grouped.empty:
                    return None

                # Minimal syarat
                grouped = grouped[grouped["total_syarat"] >= min_syarat]
                if grouped.empty:
                    return None

                grouped["pct"] = (grouped["total_redeem"] / grouped["total_syarat"]) * 100
                grouped = grouped.sort_values("pct", ascending=False).reset_index(drop=True)
                top1 = grouped.iloc[0]

                return {
                    "nama": str(top1["kasir_clean"]),
                    "pct": float(top1["pct"]),
                    "syarat": int(top1["total_syarat"]),
                    "redeem": int(top1["total_redeem"]),
                }

            # Precompute
            for k in kartu_base:
                k["juara_qty"] = get_juara_qty(k)
                k["juara_pct"] = get_juara_pct(k)

            # Bangun kartu_list: per periode → Qty dulu, lalu %
            kartu_list = []
            for k in kartu_base:
                # Kartu QTY
                kartu_list.append({**k, "mode": "qty"})
                # Kartu % (hanya kalau bukan periode aktif — misteri cukup 1x saja)
                if not (k.get("is_active") and k["tipe"] == "periode"):
                    kartu_list.append({**k, "mode": "pct"})

            total_kartu = len(kartu_list)

            # ==== JIKA BELUM ADA KARTU ====
            if total_kartu == 0:
                st.markdown(
                    "<div style='background: rgba(15,23,42,0.85); border: 2px dashed #10b981; "
                    "border-radius: 12px; padding: 40px 20px; margin: 30px auto; max-width: 500px; "
                    "text-align: center;'>"
                    "<div style='font-size: 60px; opacity: 0.5; margin-bottom: 15px;'>📜</div>"
                    "<div style='color: #10b981; font-family: monospace; font-size: 14px; font-weight: 900; "
                    "letter-spacing: 1px; margin-bottom: 8px;'>BELUM ADA PERIODE SUEGER</div>"
                    "<div style='color: #64748b; font-family: monospace; font-size: 11px; line-height: 1.6;'>"
                    "Data periode akan muncul setelah admin mendaftarkan periode Sueger di sheet PERIODE_PPS."
                    "</div></div>",
                    unsafe_allow_html=True
                )
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("⬅️ KEMBALI KE HALL OF FAME", key="btn_hof_sueger_back", use_container_width=True):
                    st.session_state["hof_sub_page"] = None
                    st.rerun()
                st.stop()

            # ==== CAROUSEL ====
            kartu_parts = ["<div class='hof-carousel-wrapper'>"]

            for k in kartu_list:
                mode = k["mode"]

                # MISTERI (khusus periode aktif — cukup 1x, di mode qty)
                if k.get("is_active") and k["tipe"] == "periode":
                    konten = (
                        "<div class='hof-mystery-icon'>❓</div>"
                        "<div class='hof-mystery-lock'>🔒</div>"
                        "<div class='hof-mystery-title'>AWAITING FINAL RESULTS</div>"
                        "<div class='hof-mystery-sub'>Prasasti juara akan dibuka setelah periode selesai (H+1).<br><br>"
                        "Selesaikan pertempuran periode ini dulu!</div>"
                    )
                    card_cls = "hof-card hof-card-mystery"
                    badge = "📅 " + k["label_tgl"]
                elif mode == "qty" and k.get("juara_qty"):
                    juara = k["juara_qty"]
                    av = get_avatar(juara["nama"])
                    konten = (
                        "<div class='hof-crown-box'>"
                        "<span class='hof-sparkle hof-sparkle-1'>✦</span>"
                        "<span class='hof-crown'>🍃</span>"
                        "<span class='hof-sparkle hof-sparkle-2'>✦</span>"
                        "<span class='hof-sparkle hof-sparkle-3'>✦</span>"
                        "</div>"
                        "<div class='hof-avatar-wrapper'>"
                        "<div class='hof-avatar-circle'>" + av + "</div>"
                        "</div>"
                        "<div class='hof-champion-name'>" + juara["nama"] + "</div>"
                        "<div class='hof-champion-qty'>" + str(juara["qty"]) + " Pcs</div>"
                    )
                    card_cls = "hof-card mode-qty"
                    badge = "📊 QTY · " + k["label_tgl"]
                elif mode == "pct" and k.get("juara_pct"):
                    juara = k["juara_pct"]
                    av = get_avatar(juara["nama"])
                    konten = (
                        "<div class='hof-crown-box'>"
                        "<span class='hof-sparkle hof-sparkle-1'>✦</span>"
                        "<span class='hof-crown'>💯</span>"
                        "<span class='hof-sparkle hof-sparkle-2'>✦</span>"
                        "<span class='hof-sparkle hof-sparkle-3'>✦</span>"
                        "</div>"
                        "<div class='hof-avatar-wrapper'>"
                        "<div class='hof-avatar-circle'>" + av + "</div>"
                        "</div>"
                        "<div class='hof-champion-name'>" + juara["nama"] + "</div>"
                        "<div class='hof-champion-qty'>" + f"{juara['pct']:.1f}%" + "</div>"
                        "<div class='hof-champion-detail'>Syarat: " + str(juara["syarat"]) + " | Redeem: " + str(juara["redeem"]) + "</div>"
                    )
                    card_cls = "hof-card mode-pct"
                    badge = "🎯 % · " + k["label_tgl"]
                else:
                    # Empty
                    mode_label = "Qty" if mode == "qty" else "Achievement %"
                    konten = (
                        "<div class='hof-empty-icon'>📭</div>"
                        "<div class='hof-empty-title'>BELUM ADA DATA</div>"
                        "<div class='hof-empty-sub'>Tidak ada data Sueger (" + mode_label + ") untuk periode ini.</div>"
                    )
                    card_cls = "hof-card hof-card-empty mode-" + mode
                    badge = ("📊 QTY · " if mode == "qty" else "🎯 % · ") + k["label_tgl"]

                kartu_parts.append(
                    "<div class='" + card_cls + "'>"
                    "<div class='hof-card-inner'>"
                    "<div class='hof-ornament hof-orn-tl'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-tr'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-bl'>⚜️</div>"
                    "<div class='hof-ornament hof-orn-br'>⚜️</div>"
                    "<div class='hof-period-badge'>" + badge + "</div>"
                    + konten +
                    "</div>"
                    "</div>"
                )

            kartu_parts.append("</div>")
            kartu_html = "".join(kartu_parts).strip()
            st.markdown(kartu_html, unsafe_allow_html=True)

            # ==== TOMBOL KEMBALI ====
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⬅️ KEMBALI KE HALL OF FAME", key="btn_hof_sueger_back", use_container_width=True):
                st.session_state["hof_sub_page"] = None
                st.rerun()

            st.stop()
        
        
        # ==============================================================================
        # 🚪 KONDISI 3: BUKU TERBUKA - KITAB MISI GUILD (DENGAN ISOLASI CSS WRAPPER)
        # ==============================================================================
        import streamlit as st
        import textwrap

        # ==========================================
        # 📅 1. LOGIKA PERIODE DINAMIS BERDASARKAN TANGGAL
        # ==========================================
        today = datetime.now().date()
        # Simulasi jika ingin tes tanggal tertentu (misal: 10 September 2026)
        # today = datetime(2026, 9, 10).date()

        def get_active_period(current_date):
            if datetime(2026, 9, 1).date() <= current_date <= datetime(2026, 9, 7).date():
                return "Periode 1 Sep - 7 Sep"
            elif datetime(2026, 9, 8).date() <= current_date <= datetime(2026, 9, 15).date():
                return "Periode 8 Sep - 15 Sep"
            elif datetime(2026, 9, 16).date() <= current_date <= datetime(2026, 9, 22).date():
                return "Periode 16 Sep - 22 Sep"
            else:
                return "Periode 23 Sep - 30 Sep"

        active_period = get_active_period(today)
        current_month_name = today.strftime("%B")

        # ==========================================
        # 📅 4.1. TENTUKAN PERIODE AKTIF GLOBAL
        # ==========================================
        periods_df = st.session_state.get("periods_df", pd.DataFrame())
        target_period_id = ""
        if not periods_df.empty:
            for _, r in periods_df.iterrows():
                try:
                    s_date = pd.to_datetime(r.get("start_date")).date()
                    e_date = pd.to_datetime(r.get("end_date")).date()
                    if s_date <= today <= e_date:
                        target_period_id = str(r.get("period_id", "")).strip()
                        break
                except Exception:
                    pass
            if not target_period_id:
                for _, r in periods_df.iterrows():
                    p_name = str(r.get("period_name", "")).lower()
                    if "8" in p_name and "15" in p_name and ("sep" in p_name or "september" in p_name):
                        target_period_id = str(r.get("period_id", "")).strip()
                        break

        # ==========================================
        # 🎨 3. SUNTIKAN CSS (TERMASUK Kartu Item RPG Interaktif)
        # ==========================================
        st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&display=swap');

            .stApp {
                background-color: #1a1a1a !important;
                background-image: 
                    linear-gradient(rgba(0, 0, 0, 0.35), rgba(0, 0, 0, 0.35)),
                    url("https://static0.thegamerimages.com/wordpress/wp-content/uploads/2025/01/copy-of-untitled-2025-01-31t105330-637.jpg?q=49&fit=crop&w=825&dpr=2") !important;
                background-size: cover !important;
                background-position: center !important;
                background-repeat: no-repeat !important;
                background-attachment: fixed !important;
            }

            .kitab-misi-page-wrapper {
                position: relative;
                width: 100%;
                max-width: 950px;
                margin: 0 auto;
                box-sizing: border-box;
            }

            .guild-lobby-title {
                font-family: 'MedievalSharp', cursive, serif !important;
                font-size: 38px !important;
                letter-spacing: 2px;
                color: #f59e0b !important;
                text-shadow: 2px 2px 6px rgba(0, 0, 0, 0.9);
                text-align: center;
            }

            .rpg-open-book-container {
                display: flex !important;
                flex-direction: row !important;
                justify-content: space-between !important;
                gap: 16px !important;
                width: 100% !important;
                background: #fef3c7;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 12px 30px rgba(0,0,0,0.8), inset 0 0 30px rgba(120, 53, 15, 0.2);
                border: 2px solid #b45309;
                box-sizing: border-box !important;
            }

            .rpg-book-page {
                flex: 1 1 50% !important;
                width: 50% !important;
                min-height: 450px !important;
                max-height: 450px !important;
                background-color: #fffbeb;
                padding: 16px;
                border-radius: 6px;
                border: 1px solid #d97706;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                box-sizing: border-box !important;
                display: flex;
                flex-direction: column;
                overflow-y: auto;
                position: relative;
            }

            .rpg-book-page-left, .rpg-book-page-right {
                background-image: url("https://img.pikbest.com/png-images/20250303/fierce-dragon-silhouette--e2-80-93-stylized-black-and-white-mythical-beast-illustration_11570728.png!bw800");
                background-position: center 65%;
                background-size: 75% auto; 
                background-repeat: no-repeat;
            }

            .rpg-book-page::before {
                content: "";
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                background-color: rgba(255, 251, 235, 0.90); 
                z-index: 1;
                pointer-events: none;
                border-radius: 6px;
            }

            @media (max-width: 768px) {
                .rpg-open-book-container {
                    flex-direction: column !important;
                    padding: 12px;
                }
                .rpg-book-page {
                    width: 100% !important;
                    min-height: 380px !important;
                    max-height: 380px !important;
                }
            }

            .open-page-title, .open-page-sub, .open-book-divider, .open-stat-row, .open-page-footer, .rpg-item-card {
                position: relative;
                z-index: 2;
            }

            .open-page-title {
                font-family: 'MedievalSharp', cursive, serif !important;
                font-weight: bold;
                color: #451a03 !important;
                font-size: 20px;
                margin-bottom: 2px;
                text-align: center !important;
            }

            .open-page-sub {
                font-size: 12px;
                color: #78350f !important;
                margin-bottom: 12px;
                font-weight: 600;
                font-family: monospace;
                text-align: center !important;
            }

            .open-book-divider {
                height: 2px;
                background: #d97706;
                margin-bottom: 12px;
            }

            .open-stat-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 10px;
                margin-bottom: 6px;
                background: #ffffff !important;
                border: 1px solid #fcd34d;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                color: #451a03 !important;
            }

            rpg_badge_style = 
            .rpg-badge-1 {
                background: linear-gradient(135deg, #fef08a 0%, #eab308 100%);
                border: 2px solid #713f12;
                box-shadow: 0 0 10px rgba(234, 179, 8, 0.6);
                color: #422006 !important;
                font-weight: bold;
            }
            .rpg-badge-2 {
                background: linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%);
                border: 2px solid #475569;
                box-shadow: 0 0 8px rgba(148, 163, 184, 0.5);
                color: #0f172a !important;
                font-weight: bold;
            }
            .rpg-badge-3 {
                background: linear-gradient(135deg, #fed7aa 0%, #c2410c 100%);
                border: 2px solid #7c2d12;
                box-shadow: 0 0 8px rgba(249, 115, 22, 0.5);
                color: #431407 !important;
                font-weight: bold;
            }

            /* RPG Item Card Styling untuk Target Item Interaktif */
            .rpg-item-card {
                background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
                border: 1px solid #d97706;
                border-radius: 6px;
                padding: 8px 10px;
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .rpg-item-card.completed {
                background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%) !important;
                border-color: #059669 !important;
            }
            .item-title { color: #451a03; font-weight: bold; font-size: 12px; font-family: 'MedievalSharp', cursive; }
            .item-stats { font-size: 11px; color: #78350f; font-family: monospace; }
            .badge-success { background-color: #059669; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 9px; font-weight: bold; }
            .badge-warning { background-color: #d97706; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 9px; font-weight: bold; }

            .open-page-footer {
                margin-top: auto;
                text-align: right;
                font-size: 10px;
                color: #78350f !important;
                font-family: monospace;
                padding-top: 10px;
                font-weight: bold;
            }
        </style>
        """, unsafe_allow_html=True)

        # ==========================================
        # 🚪 4. STATE & NAVIGASI BUKU
        # ==========================================
        if "kitab_misi_page" not in st.session_state:
            st.session_state["kitab_misi_page"] = 1

        if "page_direction" not in st.session_state:
            st.session_state["page_direction"] = "right"

        TOTAL_SHEETS = 5

        st.markdown("<h2 class='guild-lobby-title'>📜 KITAB MISI GUILD</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center; color:#fef3c7; font-size:13px; font-family:monospace;'>Misi Aktif: <b>{active_period}</b> | Bulan: <b>{current_month_name} 2026</b></p>", unsafe_allow_html=True)

        page_num = st.session_state["kitab_misi_page"]

        # Navigasi Atas Buku
        col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])

        with col_nav1:
            if page_num > 1:
                if st.button("⬅️ Sebelumnya", key="prev_sheet", use_container_width=True):
                    st.session_state["page_direction"] = "left"
                    st.session_state["kitab_misi_page"] -= 1
                    st.rerun()
            else:
                if st.button("🚪 TUTUP KITAB", key="btn_close_top", use_container_width=True):
                    st.session_state["campaign_sub_page"] = "resepsionis_utama"
                    st.rerun()

        with col_nav2:
            st.markdown(f"<p style='text-align:center; color:#fef3c7; font-family:monospace; font-weight:bold; font-size:11px; margin-top:8px;'>LEMBAR BUKA KE-{page_num} DARI {TOTAL_SHEETS}</p>", unsafe_allow_html=True)

        with col_nav3:
            if page_num < TOTAL_SHEETS:
                if st.button("Berikutnya ➡️", key="next_sheet", use_container_width=True):
                    st.session_state["page_direction"] = "right"
                    st.session_state["kitab_misi_page"] += 1
                    st.rerun()
            else:
                if st.button("🔄 KEMBALI KE AWAL", key="btn_back_to_first", use_container_width=True):
                    st.session_state["page_direction"] = "left"
                    st.session_state["kitab_misi_page"] = 1
                    st.rerun()

        # ==========================================
        # 🛠️ HELPER FORMATTING RANKING
        # ==========================================
        def format_row_top3(rank, name, score):
            badge_class = ""
            icon = ""
            if rank == 1:
                badge_class = "rpg-badge-1"
                icon = "👑 "
            elif rank == 2:
                badge_class = "rpg-badge-2"
                icon = "🥈 "
            elif rank == 3:
                badge_class = "rpg-badge-3"
                icon = "🥉 "
                
            return f"""
            <div class="{badge_class}" style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; margin-bottom: 8px; border-radius: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span>{icon}<strong>#{rank}</strong></span>
                    <span>{name}</span>
                </div>
                <div>{score}</div>
            </div>
            """

        # Dummy data dinamis personil untuk fallback jika sheet kosong
        dummy_9_personil = [
            ("Ksatria Arthur", "98 Pcs"), ("Lancelot", "92 Pcs"), ("Galahad", "85 Pcs"),
            ("Parsifal", "78 Pcs"), ("Gawain", "70 Pcs"), ("Tristan", "65 Pcs"),
            ("Bors", "60 Pcs"), ("Kay", "55 Pcs"), ("Bedivere", "50 Pcs")
        ]

        # ==========================================
        # 📄 5. KONTEN PER HALAMAN BUKU (Halaman 1)
        # ==========================================
        if page_num == 1:
            periods_df = st.session_state.get("periods_df", pd.DataFrame())
            target_period_id = ""
            if not periods_df.empty:
                for _, r in periods_df.iterrows():
                    try:
                        s_date = pd.to_datetime(r.get("start_date")).date()
                        e_date = pd.to_datetime(r.get("end_date")).date()
                        if s_date <= today <= e_date:
                            target_period_id = str(r.get("period_id", "")).strip()
                            break
                    except Exception:
                        pass
                if not target_period_id:
                    for _, r in periods_df.iterrows():
                        p_name = str(r.get("period_name", "")).lower()
                        if "8" in p_name and "15" in p_name and ("sep" in p_name or "september" in p_name):
                            target_period_id = str(r.get("period_id", "")).strip()
                            break

            sales_item_df = st.session_state.get("sales_item_df", pd.DataFrame())
            df_filtered_items = pd.DataFrame()
            if not sales_item_df.empty and target_period_id:
                df_filtered_items = sales_item_df[sales_item_df["period_id"].astype(str).str.strip() == target_period_id]
            elif not sales_item_df.empty:
                df_filtered_items = sales_item_df

            # Deteksi Role & User Aktif sesuai session
            current_user = str(st.session_state.get("username", st.session_state.get("user", "admin"))).strip().lower()
            user_role = str(st.session_state.get("role", "user")).strip().lower()
            is_admin = (user_role == "admin" or current_user == "admin")

            sales_person_df = st.session_state.get("sales_person_df", pd.DataFrame())
            actual_dict = {}
            if not sales_person_df.empty:
                sp_filtered = sales_person_df[sales_person_df["period_id"].astype(str).str.strip() == target_period_id] if target_period_id else sales_person_df
                
                # Jika bukan admin, filter berdasarkan nama kasir yang sedang login
                if not is_admin:
                    if not sp_filtered.empty and "person_name" in sp_filtered.columns:
                        sp_filtered = sp_filtered[sp_filtered["person_name"].astype(str).str.strip().str.lower() == current_user]
                
                if not sp_filtered.empty and "item_id" in sp_filtered.columns and "actual_qty" in sp_filtered.columns:
                    sp_filtered["actual_qty"] = pd.to_numeric(sp_filtered["actual_qty"], errors="coerce").fillna(0)
                    actual_dict = sp_filtered.groupby("item_id")["actual_qty"].sum().to_dict()

            items_html_left = ""
            items_html_right = ""
            render_items = []
            if not df_filtered_items.empty:
                for _, r in df_filtered_items.iterrows():
                    item_id = str(r.get("item_id", "")).strip()
                    name = str(r.get("item_name", r.get("item_nam", "Item Misi")))
                    
                    # Logika Target: target_qty (Admin) vs target_kasir (Kasir)
                    if is_admin:
                        target = int(pd.to_numeric(r.get("target_qty", 0), errors="coerce"))
                    else:
                        target = int(pd.to_numeric(r.get("target_kasir", r.get("get_kasir", 0)), errors="coerce"))
                    
                    aktual = int(actual_dict.get(item_id, 0))
                    render_items.append((name, target, aktual))

            if not render_items:
                render_items = [("Belum ada target item untuk periode ini", 0, 0)]

            for idx, (iname, itarget, iaktual) in enumerate(render_items):
                gap = itarget - iaktual if itarget > 0 else 0
                achiv = (iaktual / itarget) * 100 if itarget > 0 else 0
                is_done = iaktual >= itarget if itarget > 0 else False
                card_cls = "rpg-item-card completed" if is_done else "rpg-item-card"
                badge = '<span class="badge-success">✨ SELESAI</span>' if is_done else '<span class="badge-warning">GAP: {}</span>'.format(gap)
                achiv_color = '#065f46' if is_done else '#92400e'
                card_markup = '<div class="{}"><div><div class="item-title">⚔️ {} {}</div><div class="item-stats">Target: {} | Aktual: <b>{}</b></div></div><div style="text-align: right;"><div style="font-size: 14px; font-weight: bold; color: {};">{:.1f}%</div></div></div>'.format(card_cls, iname, badge, itarget, iaktual, achiv_color, achiv)
                if idx % 2 == 0:
                    items_html_left += card_markup
                else:
                    items_html_right += card_markup

            if not items_html_right:
                items_html_right = "<div style='color:#78350f; font-size:12px; text-align:center; margin-top:20px;'><i>Tidak ada item tambahan pada periode ini.</i></div>"

            # Layout Buku
            html_open_tugas = """
            <div class="rpg-open-book-container">
                <div class="rpg-book-page rpg-book-page-left">
                    <h3 class="open-page-title">🎯 TARGET ITEM (1)</h3>
                    <p class="open-page-sub">Maklumat Target & Achiv ({active_period})</p>
                    <div class="open-book-divider"></div>
                    {items_html_left}
                    <div class="open-page-footer">Halaman Kiri • Item Bagian 1</div>
                </div>
                <div class="rpg-book-page rpg-book-page-right">
                    <h3 class="open-page-title">📍 POSISI PAHLAWAN</h3>
                    <p class="open-page-sub">Kelanjutan Maklumat Target Item</p>
                    <div class="open-book-divider"></div>
                    {items_html_right}
                    <div class="open-page-footer">Halaman Kanan • Item Bagian 2</div>
                </div>
            </div>
            """.format(active_period=active_period, items_html_left=items_html_left, items_html_right=items_html_right)
        #batas========================================================================================================#
        elif page_num == 2:
            # 1. AMBIL DATA DARI SESSION STATE
            periods_df = st.session_state.get("periods_df", pd.DataFrame())
            periods_pps_df = st.session_state.get("periods_pps_df", pd.DataFrame())
            sales_pps_df = st.session_state.get("sales_pps_df", pd.DataFrame())
            sales_item_df = st.session_state.get("sales_item_df", pd.DataFrame())
            sales_person_df = st.session_state.get("sales_person_df", pd.DataFrame())
            
            current_user = str(st.session_state.get("username", st.session_state.get("user", "admin"))).strip().lower()
            user_role = str(st.session_state.get("role", "user")).strip().lower()
            is_admin = (user_role == "admin" or current_user == "admin")

            # 2. TENTUKAN BULAN & MODE REKAP H+1 (Tanggal 1 Cek Hasil Bulan Lalu)
            t_today = pd.Timestamp.now().date()
            
            if t_today.day == 1:
                eval_month = t_today.month - 1 if t_today.month > 1 else 12
                eval_year = t_today.year if t_today.month > 1 else t_today.year - 1
                is_recap_mode = True
                recap_title_note = " (REKAP FINAL BULAN LALU)"
            else:
                eval_month = t_today.month
                eval_year = t_today.year
                is_recap_mode = False
                recap_title_note = ""

            # Random Icon Musuh (Bisa menggunakan seed berdasarkan bulan/tahun agar stabil sepanjang bulan tersebut)
            import random
            enemy_pool = ["👹", "💀", "🕷️", "🐉", "🦇", "🧟", "🧙‍♂️", "🧛‍♂️"]
            # Gunakan gabungan tahun & bulan sebagai seed agar icon musuh tidak berubah-ubah setiap refresh di bulan yang sama
            random.seed(eval_year * 100 + eval_month)
            current_enemy_icon = random.choice(enemy_pool)
            blue_guild_icon = "🐉" # Logo guild biru konsisten Naga

            # 3. CARI PERIODE AKTIF UTAMA & DATES (HALAMAN KIRI)
            active_pps_rows = []
            active_period_pps_name = "Program PPS"
            time_factor = 50.0
            
            if not periods_pps_df.empty:
                p_df_pps = periods_pps_df.copy()
                p_df_pps["start_date"] = pd.to_datetime(p_df_pps["start_date"], errors="coerce").dt.date
                p_df_pps["end_date"] = pd.to_datetime(p_df_pps["end_date"], errors="coerce").dt.date
                
                current_pps = p_df_pps[
                    (p_df_pps["start_date"] <= t_today) & 
                    (p_df_pps["end_date"] >= t_today) &
                    (p_df_pps["status"].astype(str).str.strip().str.lower() == "aktif")
                ]
                
                if current_pps.empty:
                    current_pps = p_df_pps[p_df_pps["status"].astype(str).str.strip().str.lower() == "aktif"]
                    
                if not current_pps.empty:
                    active_pps_rows = [row for _, row in current_pps.iterrows()]
                else:
                    active_pps_rows = [periods_pps_df.iloc[0]]
                    
                if active_pps_rows:
                    r_act = active_pps_rows[0]
                    active_period_pps_name = str(r_act.get("period_name", "Program PPS"))
                    try:
                        s_date = r_act.get("start_date")
                        e_date = r_act.get("end_date")
                        total_days = (e_date - s_date).days + 1
                        passed_days = (t_today - s_date).days + 1
                        passed_days = max(1, min(passed_days, total_days))
                        time_factor = (passed_days / total_days) * 100.0
                    except Exception:
                        time_factor = 50.0

            # 4. OLAH DATA HALAMAN KIRI (TARGET PPS HARIAN)
            items_kiri_list = []
            icon_list = ["🛡️", "⚡", "🗡️", "🏹", "📜"]
            
            for idx, r in enumerate(active_pps_rows):
                p_name = str(r.get("period_name", "Program PPS"))
                p_lower = p_name.lower()
                icon = icon_list[idx % len(icon_list)]
                
                col_syarat_sgr = "syarat_sueger" if "syarat_sueger" in r else "syarat_suegeer"
                col_redeem_sgr = "redeem_sueger" if "redeem_sueger" in r else "redeem_suegeer"

                syarat_val = float(pd.to_numeric(r.get("syarat_total", r.get("syarat_pwp", r.get(col_syarat_sgr, 0))), errors="coerce"))
                redeem_val = float(pd.to_numeric(r.get("redeem_total", r.get("redeem_pwp", r.get(col_redeem_sgr, 0))), errors="coerce"))
                
                f_sales = sales_pps_df
                if not is_admin and not sales_pps_df.empty and "kasir_name" in sales_pps_df.columns:
                    f_sales = sales_pps_df[sales_pps_df["kasir_name"].astype(str).str.strip().str.lower() == current_user]

                if "suegeer" in p_lower or "sueger" in p_lower:
                    if not is_admin and not f_sales.empty:
                        s_col = "syarat_sueger" if "syarat_sueger" in f_sales.columns else "syarat_suegeer"
                        r_col = "redeem_sueger" if "redeem_sueger" in f_sales.columns else "redeem_suegeer"
                        
                        syarat_val = float(pd.to_numeric(f_sales[s_col], errors="coerce").sum()) if s_col in f_sales.columns else 0.0
                        redeem_val = float(pd.to_numeric(f_sales[r_col], errors="coerce").sum()) if r_col in f_sales.columns else 0.0
                        actual_val = float(pd.to_numeric(f_sales["qty_suegeer"], errors="coerce").sum()) if "qty_suegeer" in f_sales.columns else 0.0
                    else:
                        actual_val = float(pd.to_numeric(r.get("actual_qty", 0), errors="coerce"))

                    achiv = (redeem_val / syarat_val * 100) if syarat_val > 0 else 0
                    info_syarat = f"Syarat: {int(syarat_val)} | Redeem: {int(redeem_val)} | Aktual: <b>{int(actual_val)}</b>"
                    badge_txt = "AKTIF"
                    is_above_tf = True
                else:
                    target_total = float(pd.to_numeric(r.get("target_total", 0), errors="coerce"))
                    target_val = target_total if is_admin else (target_total / 9.0 if target_total > 0 else 0)
                    
                    q_col = "actual_qty"
                    if "pwp" in p_lower and "qty_pwp" in f_sales.columns: q_col = "qty_pwp"
                    elif ("serba" in p_lower or "sg" in p_lower) and "qty_sg" in f_sales.columns: q_col = "qty_sg"
                    elif "cemilan" in p_lower and "cemilan_ceban" in f_sales.columns: q_col = "cemilan_ceban"
                    
                    actual_val = float(pd.to_numeric(f_sales[q_col], errors="coerce").sum()) if not f_sales.empty and q_col in f_sales.columns else 0.0
                    achiv = (actual_val / target_val * 100) if target_val > 0 else 0
                    gap = max(0, target_val - actual_val)
                    info_syarat = f"Target: {int(target_val)} Pcs | Aktual: <b>{int(actual_val)}</b>"
                    is_above_tf = achiv >= time_factor
                    badge_txt = "ON TRACK" if is_above_tf else f"GAP: {int(gap)}"

                badge_cls = "badge-success" if is_above_tf else "badge-warning"
                achiv_color = "#065f46" if is_above_tf else "#b91c1c"

                items_kiri_list.append({
                    "icon": icon, "p_name": p_name, "badge_cls": badge_cls,
                    "badge_txt": badge_txt, "info_syarat": info_syarat,
                    "achiv_color": achiv_color, "achiv": achiv
                })

            # 5. OLAH DATA HALAMAN KANAN (GUILD WAR SYSTEM)
            sept_period_ids = []
            if not periods_df.empty:
                p_df = periods_df.copy()
                if "start_date" in p_df.columns:
                    p_df["start_date"] = pd.to_datetime(p_df["start_date"], errors="coerce")
                    sept_periods = p_df[
                        (p_df["start_date"].dt.month == eval_month) | 
                        (p_df["period_id"].astype(str).str.strip().str.upper().str.startswith("S"))
                    ]
                    if not sept_periods.empty and "period_id" in sept_periods.columns:
                        sept_period_ids = sept_periods["period_id"].astype(str).str.strip().tolist()

            sept_pps_ids = []
            if not periods_pps_df.empty and "start_date" in periods_pps_df.columns:
                pps_temp = periods_pps_df.copy()
                pps_temp["start_date"] = pd.to_datetime(pps_temp["start_date"], errors="coerce")
                sept_pps = pps_temp[pps_temp["start_date"].dt.month == eval_month]
                if not sept_pps.empty and "period_id" in sept_pps.columns:
                    sept_pps_ids = sept_pps["period_id"].astype(str).str.strip().tolist()

            psm_target, psm_actual, psm_mvp = 0.0, 0.0, "-"
            if not sales_item_df.empty and "target_qty" in sales_item_df.columns:
                f_item_sept = sales_item_df[sales_item_df["period_id"].astype(str).str.strip().isin(sept_period_ids)] if sept_period_ids and "period_id" in sales_item_df.columns else sales_item_df
                psm_target = float(pd.to_numeric(f_item_sept["target_qty"], errors="coerce").sum())

            if not sales_person_df.empty and "actual_qty" in sales_person_df.columns:
                f_person_sept = sales_person_df[sales_person_df["period_id"].astype(str).str.strip().isin(sept_period_ids)] if sept_period_ids and "period_id" in sales_person_df.columns else sales_person_df
                psm_actual = float(pd.to_numeric(f_person_sept["actual_qty"], errors="coerce").sum())
                p_col = "person_name" if "person_name" in f_person_sept.columns else ("staff_name" if "staff_name" in f_person_sept.columns else "")
                if p_col:
                    grp_psm = f_person_sept.groupby(p_col)["actual_qty"].sum()
                    if not grp_psm.empty and grp_psm.max() > 0:
                        psm_mvp = str(grp_psm.idxmax()).title()

            programs = [
                {"name": "PSM Assault", "key": "psm", "weight": 20, "target": psm_target, "actual": psm_actual, "mvp": psm_mvp},
                {"name": "PWP Siege", "key": "pwp", "weight": 25, "col_act": "qty_pwp"},
                {"name": "Serba Gratis (SG)", "key": "serba", "weight": 30, "col_act": "qty_sg"},
                {"name": "Suegeer Strike", "key": "suegeer", "weight": 0, "col_act": "qty_suegeer"}
            ]

            items_kanan_list = []
            total_blue_points = 0.0

            for p in programs:
                p_key = p["key"]
                weight = p["weight"]
                
                if p_key == "psm":
                    p_target = p["target"]
                    p_actual = p["actual"]
                    mvp_name = p["mvp"]
                elif p_key == "suegeer":
                    s_col = "syarat_sueger" if "syarat_sueger" in sales_pps_df.columns else "syarat_suegeer"
                    r_col = "redeem_sueger" if "redeem_sueger" in sales_pps_df.columns else "redeem_suegeer"
                    
                    p_syarat = float(pd.to_numeric(sales_pps_df[s_col], errors="coerce").sum()) if not sales_pps_df.empty and s_col in sales_pps_df.columns else 0.0
                    p_redeem = float(pd.to_numeric(sales_pps_df[r_col], errors="coerce").sum()) if not sales_pps_df.empty and r_col in sales_pps_df.columns else 0.0
                    
                    p_target = p_syarat
                    p_actual = p_redeem
                    mvp_name = "-"
                    if not sales_pps_df.empty and "kasir_name" in sales_pps_df.columns and s_col in sales_pps_df.columns and r_col in sales_pps_df.columns:
                        grp = sales_pps_df.groupby("kasir_name")[[s_col, r_col]].sum()
                        grp = grp[grp[s_col] > 0]
                        if not grp.empty:
                            grp["ach"] = (grp[r_col] / grp[s_col]) * 100
                            if not grp.empty and grp["ach"].max() > 0:
                                mvp_name = str(grp["ach"].idxmax()).title()
                else:
                    t_rows = pd.DataFrame()
                    if not periods_pps_df.empty and "period_name" in periods_pps_df.columns:
                        mask = periods_pps_df["period_name"].astype(str).str.lower().str.contains(p_key)
                        if p_key == "serba":
                            mask = mask | periods_pps_df["period_name"].astype(str).str.lower().str.contains("sg")
                        t_rows = periods_pps_df[mask]
                        
                        if sept_pps_ids and "period_id" in t_rows.columns:
                            t_rows = t_rows[t_rows["period_id"].astype(str).str.strip().isin(sept_pps_ids)]
                    
                    p_target = float(pd.to_numeric(t_rows["target_total"], errors="coerce").sum()) if not t_rows.empty and "target_total" in t_rows.columns else 0.0
                    col_name = p["col_act"]
                    p_actual = float(pd.to_numeric(sales_pps_df[col_name], errors="coerce").sum()) if not sales_pps_df.empty and col_name in sales_pps_df.columns else 0.0
                    
                    mvp_name = "-"
                    if not sales_pps_df.empty and "kasir_name" in sales_pps_df.columns and col_name in sales_pps_df.columns:
                        grp = sales_pps_df.groupby("kasir_name")[col_name].sum()
                        if not grp.empty and grp.max() > 0:
                            mvp_name = str(grp.idxmax()).title()

                p_achiv = (p_actual / p_target * 100) if p_target > 0 else 0
                achiv_ratio = (p_actual / p_target) if p_target > 0 else 0
                
                if weight > 0:
                    total_blue_points += (achiv_ratio * weight)

                blue_flex = min(100.0, p_achiv)
                red_flex = max(0.0, 100.0 - blue_flex)
                
                items_kanan_list.append({
                    "name": p["name"], "mvp": mvp_name, "p_achiv": p_achiv,
                    "p_actual": int(p_actual), "p_target": int(p_target),
                    "blue_flex": blue_flex, "red_flex": red_flex,
                    "is_suegeer": (p_key == "suegeer")
                })

            # Poin Maksimal 75 (Aturan: Jika Biru Naik, Merah Berkurang)
            total_blue_points = min(75.0, total_blue_points)
            total_blue_pts_int = int(round(total_blue_points))
            total_red_pts_int = max(0, 75 - total_blue_pts_int)
            
            header_blue_pct = (total_blue_points / 75.0) * 100
            header_red_pct = 100 - header_blue_pct
            
            # Penentuan Status Victory / Defeat
            if total_blue_points > total_red_pts_int:
                match_status = "VICTORY 🏆"
                status_color = "#16a34a"
            elif total_red_pts_int > total_blue_points:
                match_status = "DEFEAT 💀"
                status_color = "#dc2626"
            else:
                match_status = "DRAW ⚔️"
                status_color = "#eab308"

            # 6. RENDER HTML DUA HALAMAN
            html_kiri_str = "".join([
                f'<div class="rpg-item-card">'
                f'<div><div class="item-title">{x["icon"]} {x["p_name"]} <span class="{x["badge_cls"]}">{x["badge_txt"]}</span></div>'
                f'<div class="item-stats">{x["info_syarat"]}</div></div>'
                f'<div style="text-align: right;"><div style="font-size: 14px; font-weight: bold; color: {x["achiv_color"]};">{x["achiv"]:.1f}%</div></div>'
                f'</div>'
                for x in items_kiri_list
            ]) if items_kiri_list else '<div style="color:#78350f; font-size:12px; text-align:center; margin-top:20px;"><i>Belum ada data Target PPS aktif.</i></div>'

            html_kanan_items = ""
            for item in items_kanan_list:
                label_stat = f"Redeem: {item['p_actual']} / Syarat: {item['p_target']}" if item["is_suegeer"] else f"Hit: {item['p_actual']} / Target: {item['p_target']}"
                html_kanan_items += (
                    f'<div class="gw-card">'
                    f'<div class="gw-card-header">'
                    f'<span class="gw-card-title">⚔️ {item["name"]}</span>'
                    f'<span class="gw-mvp">👑 MVP: {item["mvp"]}</span>'
                    f'</div>'
                    f'<div class="gw-bar-container">'
                    f'<div class="gw-bar-blue" style="width: {item["blue_flex"]}%;"></div>'
                    f'<div class="gw-bar-red" style="width: {item["red_flex"]}%;"></div>'
                    f'<div class="gw-bar-text">{item["p_achiv"]:.1f}%</div>'
                    f'</div>'
                    f'<div class="gw-card-footer">{label_stat}</div>'
                    f'</div>'
                )

            html_header_box = (
                f'<div class="gw-header-box">'
                f'<div style="font-size: 10px; font-weight: bold; color: #b45309; margin-bottom: 2px;">'
                f'ARENA GUILD WAR{recap_title_note}'
                f'</div>'
                f'<div class="gw-match-title">'
                f'<span class="gw-team-blue">{blue_guild_icon} ACHIV: {total_blue_pts_int} PTS</span>'
                f'<span class="gw-vs">VS</span>'
                f'<span class="gw-team-red">{current_enemy_icon} TARGET: {total_red_pts_int} PTS</span>'
                f'</div>'
                f'<div class="gw-status-text" style="color: {status_color} !important;">{match_status}</div>'
                f'<div class="gw-main-bar">'
                f'<div class="gw-main-blue" style="width: {header_blue_pct}%;"></div>'
                f'<div class="gw-main-red" style="width: {header_red_pct}%;"></div>'
                f'<div class="gw-main-bar-text">{total_blue_pts_int} / {total_red_pts_int} PTS</div>'
                f'</div>'
                f'</div>'
            )

            css_gw = """
            <style>
                .rpg-book-page-right {
                    position: relative !important;
                    z-index: 1 !important;
                }
                .rpg-book-page-right * {
                    position: relative !important;
                    z-index: 5 !important;
                    opacity: 1 !important;
                }
                .gw-header-box {
                    background-color: #fffbeb !important;
                    border: 2px solid #b45309 !important;
                    border-radius: 8px !important;
                    padding: 8px 12px !important;
                    margin-bottom: 12px !important;
                    text-align: center !important;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
                }
                .gw-match-title {
                    display: flex !important;
                    justify-content: space-between !important;
                    align-items: center !important;
                    font-weight: 800 !important;
                }
                .gw-team-blue { color: #0284c7 !important; font-size: 13px !important; font-weight: 900 !important; }
                .gw-team-red { color: #dc2626 !important; font-size: 13px !important; font-weight: 900 !important; }
                .gw-vs { font-size: 12px !important; color: #78350f !important; margin: 0 6px !important; }
                .gw-status-text {
                    font-size: 11px !important;
                    font-weight: 900 !important;
                    letter-spacing: 2px !important;
                    margin: 3px 0 !important;
                }
                .gw-main-bar {
                    height: 18px !important;
                    background-color: #cbd5e1 !important;
                    border-radius: 4px !important;
                    border: 1px solid #94a3b8 !important;
                    display: flex !important;
                    overflow: hidden !important;
                    margin-top: 4px !important;
                }
                .gw-main-blue { background: linear-gradient(90deg, #0284c7, #38bdf8) !important; height: 100% !important; }
                .gw-main-red { background: linear-gradient(90deg, #dc2626, #f87171) !important; height: 100% !important; }
                .gw-main-bar-text {
                    position: absolute !important; width: 100% !important; text-align: center !important; line-height: 18px !important;
                    font-size: 10px !important; font-weight: bold !important; color: #ffffff !important; text-shadow: 1px 1px 2px #000 !important;
                    left: 0; top: 0;
                }
                .gw-card {
                    background-color: #fffdf5 !important;
                    border: 1.5px solid #fde68a !important;
                    border-radius: 6px !important;
                    padding: 8px 10px !important;
                    margin-bottom: 8px !important;
                    box-shadow: 0 2px 4px rgba(180, 83, 9, 0.1) !important;
                }
                .gw-card-header { 
                    display: flex !important; 
                    justify-content: space-between !important; 
                    align-items: center !important; 
                    margin-bottom: 4px !important; 
                }
                .gw-card-title { font-size: 12px !important; font-weight: bold !important; color: #451a03 !important; }
                .gw-mvp { 
                    font-size: 9px !important; background-color: #fef3c7 !important; color: #b45309 !important; 
                    border: 1px solid #fde68a !important; padding: 2px 6px !important; border-radius: 4px !important; font-weight: bold !important; 
                }
                .gw-bar-container {
                    height: 14px !important; background-color: #cbd5e1 !important; border-radius: 3px !important; 
                    border: 1px solid #94a3b8 !important; display: flex !important; overflow: hidden !important; 
                }
                .gw-bar-blue { background: linear-gradient(90deg, #2563eb, #60a5fa) !important; height: 100% !important; }
                .gw-bar-red { background: linear-gradient(90deg, #dc2626, #f87171) !important; height: 100% !important; }
                .gw-bar-text {
                    position: absolute !important; width: 100% !important; text-align: center !important; line-height: 14px !important;
                    font-size: 9px !important; font-weight: bold !important; color: #ffffff !important; text-shadow: 1px 1px 2px #000 !important;
                    left: 0; top: 0;
                }
                .gw-card-footer { font-size: 10px !important; color: #78350f !important; margin-top: 4px !important; font-weight: 700 !important; }
            </style>
            """

            html_open_tugas = (
                f'{css_gw}'
                f'<div class="rpg-open-book-container">'
                f'<div class="rpg-book-page rpg-book-page-left">'
                f'<h3 class="open-page-title">🛡️ TARGET PPS</h3>'
                f'<p class="open-page-sub">Rincian Target Harian ({active_period_pps_name})</p>'
                f'<div class="open-book-divider"></div>'
                f'{html_kiri_str}'
                f'<div class="open-page-footer">Halaman Kiri • Target PPS</div>'
                f'</div>'
                f'<div class="rpg-book-page rpg-book-page-right">'
                f'<h3 class="open-page-title">⚔️ GUILD WAR ARENA</h3>'
                f'<p class="open-page-sub">Pertempuran Performa Bulanan</p>'
                f'<div class="open-book-divider"></div>'
                f'{html_header_box}'
                f'{html_kanan_items}'
                f'<div class="open-page-footer">Halaman Kanan • Guild War</div>'
                f'</div>'
                f'</div>'
            )

        #============================================================= batas =======================================#
        elif page_num == 3:
            # 1. Ambil Username Aktif
            current_user_name = st.session_state.get("user_name", st.session_state.get("username", ""))

            # 2. STYLING CSS MEDIEVAL PODIUM, ZONA MERAH, & MOBILE FIX
            rpg_badge_style = """
            <style>
            .rpg-open-book-container {
                display: flex;
                flex-direction: row;
                gap: 20px;
                width: 100%;
                box-sizing: border-box;
            }

            @media (max-width: 768px) {
                .rpg-open-book-container {
                    flex-direction: column !important;
                    gap: 15px;
                }
            }

            .rpg-book-page {
                flex: 1;
                background: #fdf6e2;
                border: 3px solid #d4af37;
                border-radius: 8px;
                padding: 16px;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                min-height: 480px;
                position: relative;
                overflow: hidden;
            }

            /* Watermark Naga Pudar */
            .rpg-book-page::before {
                content: "";
                position: absolute;
                top: 0; left: 0; width: 100%; height: 100%;
                background-image: url("https://img.pikbest.com/png-images/20250303/fierce-dragon-silhouette--e2-80-93-stylized-black-and-white-mythical-beast-illustration_11570728.png!bw800");
                background-repeat: no-repeat;
                background-position: center;
                background-size: 85% auto;
                opacity: 0.08 !important;
                pointer-events: none;
                z-index: 0;
            }

            /* --- PODIUM MEDIEVAL TOP 3 --- */
            .podium-wrapper {
                display: flex;
                align-items: flex-end;
                justify-content: center;
                gap: 8px;
                margin-top: auto;
                margin-bottom: 10px;
                position: relative;
                z-index: 2;
                width: 100%;
            }

            .podium-slot {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                min-width: 0;
            }

            .podium-card {
                width: 100%;
                border-radius: 6px 6px 0 0;
                padding: 8px 4px;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                box-shadow: 0 -3px 10px rgba(0,0,0,0.25), inset 0 1px 2px rgba(255,255,255,0.4);
                position: relative;
            }

            /* Balok Podium Medieval Berbingkai */
            .podium-1 {
                height: 175px;
                background: linear-gradient(180deg, #fef08a 0%, #d97706 100%);
                border: 2.5px solid #78350f;
                border-bottom: none;
            }
            .podium-2 {
                height: 140px;
                background: linear-gradient(180deg, #f8fafc 0%, #64748b 100%);
                border: 2.5px solid #334155;
                border-bottom: none;
            }
            .podium-3 {
                height: 115px;
                background: linear-gradient(180deg, #ffedd5 0%, #c2410c 100%);
                border: 2.5px solid #7c2d12;
                border-bottom: none;
            }

            .podium-rank-tag {
                font-size: 15px;
                font-weight: 900;
                color: #1e1b4b;
                text-shadow: 0px 1px 0px rgba(255,255,255,0.8);
            }

            .podium-name {
                font-size: 11px;
                font-weight: 800;
                color: #0f172a;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 95%;
                margin-top: 3px;
                background: rgba(255, 255, 255, 0.45);
                padding: 2px 5px;
                border-radius: 4px;
                border: 1px solid rgba(0,0,0,0.1);
            }

            .podium-score {
                font-size: 12px;
                font-weight: 900;
                color: #1e1103;
                margin-top: 4px;
                text-shadow: 0px 1px 0px rgba(255,255,255,0.6);
            }

            .podium-achiv {
                font-size: 10px;
                color: #064e3b;
                font-weight: 800;
                margin-top: 2px;
                background: rgba(255,255,255,0.65);
                padding: 1px 5px;
                border-radius: 10px;
            }

            /* --- LIST KANAN & ZONA MERAH --- */
            .rpg-list-container {
                display: flex;
                flex-direction: column;
                gap: 6px;
                position: relative;
                z-index: 2;
                overflow-y: auto;
                max-height: 360px;
                padding-right: 2px;
            }

            .rpg-normal-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 10px;
                border: 1.5px solid #cbd5e1;
                background: #ffffff;
                border-radius: 6px;
                color: #020617 !important;
                font-size: 12px;
                font-weight: 600;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
                flex-shrink: 0;
            }

            /* ZONA MERAH (EXACT 3 TERBAWAH) */
            .danger-zone-row {
                background: #fff5f5 !important;
                border: 1.5px solid #fca5a5 !important;
                color: #991b1b !important;
            }
            .danger-zone-badge {
                background: #fee2e2;
                color: #dc2626;
                font-size: 9px;
                padding: 2px 5px;
                border-radius: 4px;
                font-weight: 800;
                border: 1px solid #f87171;
            }

            /* HIGHLIGHT USER AKTIF */
            .rpg-user-me {
                outline: 2.5px solid #2563eb !important;
                outline-offset: -1px;
            }

            .open-page-title { color: #3b1104 !important; text-align: center; font-weight: bold; margin-bottom: 2px; position: relative; z-index: 2; font-size: 16px; }
            .open-page-sub { color: #5c2406 !important; text-align: center; font-size: 11px; margin-bottom: 8px; position: relative; z-index: 2; font-weight: 600; }
            .open-book-divider { border-bottom: 2px solid #d4af37; margin-bottom: 10px; position: relative; z-index: 2; }
            .open-page-footer { margin-top: auto; text-align: right; font-size: 10px; color: #5c2406 !important; font-family: monospace; padding-top: 6px; font-weight: bold; position: relative; z-index: 2; }
            </style>
            """
            st.markdown(rpg_badge_style, unsafe_allow_html=True)

            if 'active_period' not in locals() and 'active_period' not in globals():
                active_period = st.session_state.get("active_period", "Periode Aktif")

            # 3. OLAH DATA PERINGKAT (QTY PERIODE vs ACHIV REALTME BULANAN DARI SHEET PERIODE)
            sales_person_df = st.session_state.get("sales_person_df", pd.DataFrame())
            sales_item_df = st.session_state.get("sales_item_df", pd.DataFrame())
            periods_df = st.session_state.get("periods_df", pd.DataFrame())
            
            target_pid_clean = str(target_period_id).strip() if ('target_period_id' in locals() and target_period_id) else ""

            # --- AMBIL PILTER PERIOD_ID UNTUK BULAN YANG SAMA DARI SHEET PERIODE ---
            valid_month_pids = set()
            if not periods_df.empty and target_pid_clean and "period_id" in periods_df.columns:
                periods_copy = periods_df.copy()
                periods_copy["clean_pid"] = periods_copy["period_id"].astype(str).str.strip()
                
                # Ambil tanggal dari start_date periode aktif
                curr_row = periods_copy[periods_copy["clean_pid"] == target_pid_clean]
                if not curr_row.empty and "start_date" in curr_row.columns:
                    try:
                        ref_date = pd.to_datetime(curr_row["start_date"].iloc[0])
                        periods_copy["start_dt"] = pd.to_datetime(periods_copy["start_date"], errors="coerce")
                        
                        # Filter period_id mana saja yang bulan & tahunnya sama dengan periode aktif
                        same_month_df = periods_copy[
                            (periods_copy["start_dt"].dt.month == ref_date.month) & 
                            (periods_copy["start_dt"].dt.year == ref_date.year)
                        ]
                        valid_month_pids = set(same_month_df["clean_pid"].unique())
                    except Exception:
                        valid_month_pids = {target_pid_clean}
                else:
                    valid_month_pids = {target_pid_clean}
            else:
                if target_pid_clean:
                    valid_month_pids = {target_pid_clean}

            master_personil = []
            if "master_personil_df" in st.session_state and not st.session_state["master_personil_df"].empty:
                master_personil = st.session_state["master_personil_df"]["person_name"].dropna().astype(str).str.strip().unique().tolist()
            elif not sales_person_df.empty and "person_name" in sales_person_df.columns:
                master_personil = sales_person_df["person_name"].dropna().astype(str).str.strip().unique().tolist()

            # --- A. TOTAL QTY PCS (HANYA PERIODE AKTIF SPESIFIK) ---
            qty_dict = {}
            if not sales_person_df.empty and "person_name" in sales_person_df.columns:
                sp_period = sales_person_df.copy()
                if target_pid_clean and "period_id" in sp_period.columns:
                    sp_period = sp_period[sp_period["period_id"].astype(str).str.strip() == target_pid_clean]
                
                if not sp_period.empty:
                    sp_period["person_name"] = sp_period["person_name"].astype(str).str.strip()
                    sp_period["actual_qty"] = pd.to_numeric(sp_period.get("actual_qty", 0), errors="coerce").fillna(0)
                    grouped_qty = sp_period.groupby("person_name")["actual_qty"].sum().reset_index()
                    for _, r in grouped_qty.iterrows():
                        qty_dict[r["person_name"]] = int(r["actual_qty"])

            # --- B. ACHIEVEMENT (AKUMULASI HANYA BULAN AKTIF DARI SHEET PERIODE) ---
            achiv_dict = {}
            if not sales_person_df.empty and "person_name" in sales_person_df.columns:
                sp_month = sales_person_df.copy()
                sp_month["clean_pid"] = sp_month["period_id"].astype(str).str.strip() if "period_id" in sp_month.columns else ""

                # 1. CARI SEMUA PERIOD_ID YANG SE-BULAN DENGAN TARGET_PERIOD_ID
                valid_month_pids = set()
                
                if not periods_df.empty and target_pid_clean:
                    p_df = periods_df.copy()
                    p_df["clean_pid"] = p_df["period_id"].astype(str).str.strip()
                    
                    # Cari baris periode yang sedang dipilih/aktif
                    active_row = p_df[p_df["clean_pid"] == target_pid_clean]
                    
                    if not active_row.empty and "start_date" in active_row.columns:
                        # Ambil Bulan & Tahun dari Periode Aktif
                        active_date = pd.to_datetime(active_row["start_date"].iloc[0], errors="coerce")
                        
                        if pd.notna(active_date):
                            p_df["start_dt"] = pd.to_datetime(p_df["start_date"], errors="coerce")
                            # Filter: Ambil period_id yang Bulan & Tahunnya SAMA SAJA
                            same_month_mask = (p_df["start_dt"].dt.month == active_date.month) & (p_df["start_dt"].dt.year == active_date.year)
                            valid_month_pids = set(p_df[same_month_mask]["clean_pid"].unique())
                
                # Fallback jika sheet PERIODE tidak terbaca: Filter berdasarkan Karakter Pertama Kode (Misal: 'S' untuk September, 'P' untuk Agustus)
                if not valid_month_pids and target_pid_clean:
                    prefix = target_pid_clean[0] # Mengambil huruf depan 'S' atau 'P'
                    valid_month_pids = {pid for pid in sp_month["clean_pid"].unique() if str(pid).startswith(prefix)}

                # 2. FILTER TRANSAKSI HANYA UNTUK BULAN TERSEBUT
                if valid_month_pids:
                    sp_month = sp_month[sp_month["clean_pid"].isin(valid_month_pids)]

                # 3. PROSES HITUNG ACHIEVEMENT SEPERTI BIASA
                if not sp_month.empty:
                    sp_month["person_name"] = sp_month["person_name"].astype(str).str.strip()
                    sp_month["actual_qty"] = pd.to_numeric(sp_month.get("actual_qty", 0), errors="coerce").fillna(0)
                    
                    item_col_sp = next((c for c in ["item_id", "item_code", "kode_item"] if c in sp_month.columns), "item_name")
                    sp_month["clean_item"] = sp_month[item_col_sp].astype(str).str.strip()

                    target_map = {}
                    if not sales_item_df.empty:
                        item_df = sales_item_df.copy()
                        t_col = next((c for c in item_df.columns if "target_kasir" in c.lower() or "get_kasir" in c.lower() or ("target" in c.lower() and "kasir" in c.lower())), None)
                        item_col_si = next((c for c in ["item_id", "item_code", "kode_item"] if c in item_df.columns), "item_name")

                        if t_col:
                            for _, r in item_df.iterrows():
                                pid = str(r.get("period_id", "")).strip()
                                ival = str(r.get(item_col_si, "")).strip()
                                tval = pd.to_numeric(r.get(t_col, 0), errors="coerce")
                                if pd.notna(tval) and tval > 0:
                                    target_map[(pid, ival)] = tval

                    aggregated_sales = sp_month.groupby(["person_name", "clean_pid", "clean_item"])["actual_qty"].sum().reset_index()

                    for _, row in aggregated_sales.iterrows():
                        p_name = row["person_name"]
                        pid = row["clean_pid"]
                        ival = row["clean_item"]
                        total_act = row["actual_qty"]
                        
                        target_val = target_map.get((pid, ival), 0)
                        if target_val == 0:
                            target_val = next((v for (p, i), v in target_map.items() if i == ival), 0)

                        if target_val > 0 and total_act >= target_val:
                            achiv_dict[p_name] = achiv_dict.get(p_name, 0) + 1

            # --- C. GABUNG DAN URUTKAN RANKING ---
            ranking_list = []
            all_names = set(master_personil) | set(qty_dict.keys()) | set(achiv_dict.keys())
            for name in all_names:
                if not name: continue
                ranking_list.append((name, qty_dict.get(name, 0), achiv_dict.get(name, 0)))

            ranking_list = sorted(ranking_list, key=lambda x: x[1], reverse=True)

            if not ranking_list:
                ranking_list = [("Ksatriya Arthur", 98, 3), ("Lancelot", 92, 2), ("Galahad", 85, 1), ("Parsifal", 78, 0), ("Gawain", 70, 0), ("Tristan", 65, 0), ("Bors", 60, 0), ("Kay", 55, 0), ("Bedivere", 50, 0)]

            # 4. FUNGSI PEMBUAT ELEMENT PODIUM
            def make_podium_item(rank_idx, class_name, crown_icon, r_list):
                if len(r_list) > rank_idx:
                    n, q, a = r_list[rank_idx]
                    is_me = (n.lower() == str(current_user_name).lower())
                    me_cls = "rpg-user-me" if is_me else ""
                    you_badge = '<span style="background:#2563eb; color:white; font-size:8px; padding:1px 4px; border-radius:4px; margin-top:2px;">KAMU</span>' if is_me else ""
                    
                    html = f'<div class="podium-slot">'
                    html += f'<div style="font-size:22px; margin-bottom:2px; z-index:3;">{crown_icon}</div>'
                    html += f'<div class="podium-card {class_name} {me_cls}">'
                    html += f'<div class="podium-rank-tag">#{rank_idx+1}</div>'
                    html += f'<div class="podium-name" title="{n}">{n}</div>'
                    html += f'{you_badge}'
                    html += f'<div class="podium-score">{q} Pcs</div>'
                    html += f'<div class="podium-achiv">✨ {a} Achiv</div>'
                    html += f'</div></div>'
                    return html
                return ""

            # Generate HTML Podium Kiri (1-3)
            podium_html = '<div class="podium-wrapper">'
            podium_html += make_podium_item(1, "podium-2", "🥈", ranking_list)
            podium_html += make_podium_item(0, "podium-1", "👑", ranking_list)
            podium_html += make_podium_item(2, "podium-3", "🥉", ranking_list)
            podium_html += '</div>'

            # 5. GENERATE LIST KANAN (4-9) + EXACT 3 TERBAWAH ZONA MERAH
            rest_html = '<div class="rpg-list-container">'
            total_personil = len(ranking_list)
            danger_cutoff_rank = max(4, total_personil - 2)

            for i, (n, q, a) in enumerate(ranking_list[3:9]):
                rank = i + 4
                is_me = (n.lower() == str(current_user_name).lower())
                me_class = "rpg-user-me" if is_me else ""
                you_badge = '<span style="background: #2563eb; color: white; font-size: 8px; padding: 1px 4px; border-radius: 4px; margin-left: 4px;">KAMU</span>' if is_me else ""
                
                is_danger = rank >= danger_cutoff_rank
                row_style = "danger-zone-row" if is_danger else ""
                danger_tag = '<span class="danger-zone-badge">⚠️ ZONA MERAH</span>' if is_danger else ""
                rank_icon = "🔻" if is_danger else "🛡️"
                score_label = f"{q} Pcs <span style='font-size:10px; color:#065f46; font-weight:bold;'>(✨ {a} Achiv)</span>"

                rest_html += f'<div class="rpg-normal-row {row_style} {me_class}">'
                rest_html += f'<div style="display: flex; align-items: center; gap: 4px; overflow: hidden; white-space: nowrap;">'
                rest_html += f'<span>{rank_icon}</span>'
                rest_html += f'<span style="font-weight:bold;">#{rank}</span>'
                rest_html += f'<span style="overflow: hidden; text-overflow: ellipsis;" title="{n}">{n}</span>'
                rest_html += f'{you_badge}{danger_tag}'
                rest_html += f'</div>'
                rest_html += f'<div style="flex-shrink: 0; margin-left: 6px;">{score_label}</div>'
                rest_html += f'</div>'
            
            rest_html += '</div>'

            # 6. RENDER KEDUA HALAMAN BUKU
            html_open_tugas = (
                f'<div class="rpg-open-book-container">'
                f'<div class="rpg-book-page">'
                f'<h3 class="open-page-title">⚔️ PSM TOP (1-3)</h3>'
                f'<p class="open-page-sub">Periode: {active_period}</p>'
                f'<div class="open-book-divider"></div>'
                f'{podium_html}'
                f'<div class="open-page-footer">Halaman Kiri • PSM 1-3</div>'
                f'</div>'
                f'<div class="rpg-book-page">'
                f'<h3 class="open-page-title">⚔️ PSM (4-9)</h3>'
                f'<p class="open-page-sub">Kelanjutan Peringkat Periode</p>'
                f'<div class="open-book-divider"></div>'
                f'{rest_html}'
                f'<div class="open-page-footer">Halaman Kanan • PSM 4-9</div>'
                f'</div>'
                f'</div>'
            )

            
        #=============================================batas biar gak psimh===================================================#
        elif page_num == 4:
            # 1. Ambil Username Aktif
            current_user_name = st.session_state.get("user_name", st.session_state.get("username", ""))

            # 2. STYLING CSS MEDIEVAL PODIUM & LIST ITEM
            rpg_badge_style = """
            <style>
            .rpg-open-book-container {
                display: flex;
                flex-direction: row;
                gap: 20px;
                width: 100%;
                box-sizing: border-box;
            }

            @media (max-width: 768px) {
                .rpg-open-book-container {
                    flex-direction: column !important;
                    gap: 15px;
                }
            }

            .rpg-book-page {
                flex: 1;
                background: #fdf6e2;
                border: 3px solid #d4af37;
                border-radius: 8px;
                padding: 16px;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                min-height: 500px;
                position: relative;
                overflow: hidden;
            }

            .rpg-book-page::before {
                content: "";
                position: absolute;
                top: 0; left: 0; width: 100%; height: 100%;
                background-image: url("https://img.pikbest.com/png-images/20250303/fierce-dragon-silhouette--e2-80-93-stylized-black-and-white-mythical-beast-illustration_11570728.png!bw800");
                background-repeat: no-repeat;
                background-position: center;
                background-size: 85% auto;
                opacity: 0.08 !important;
                pointer-events: none;
                z-index: 0;
            }

            /* --- PODIUM MEDIEVAL PPS --- */
            .podium-wrapper {
                display: flex;
                align-items: flex-end;
                justify-content: center;
                gap: 8px;
                margin-top: auto;
                margin-bottom: 10px;
                position: relative;
                z-index: 2;
                width: 100%;
            }

            .podium-slot {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                min-width: 0;
            }

            .podium-card {
                width: 100%;
                border-radius: 6px 6px 0 0;
                padding: 8px 4px;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                box-shadow: 0 -3px 10px rgba(0,0,0,0.25), inset 0 1px 2px rgba(255,255,255,0.4);
                position: relative;
            }

            .podium-1 {
                height: 195px;
                background: linear-gradient(180deg, #fef08a 0%, #d97706 100%);
                border: 2.5px solid #78350f;
                border-bottom: none;
            }
            .podium-2 {
                height: 160px;
                background: linear-gradient(180deg, #f8fafc 0%, #64748b 100%);
                border: 2.5px solid #334155;
                border-bottom: none;
            }
            .podium-3 {
                height: 135px;
                background: linear-gradient(180deg, #ffedd5 0%, #c2410c 100%);
                border: 2.5px solid #7c2d12;
                border-bottom: none;
            }

            .podium-rank-tag {
                font-size: 15px;
                font-weight: 900;
                color: #1e1b4b;
                text-shadow: 0px 1px 0px rgba(255,255,255,0.8);
            }

            .podium-name {
                font-size: 11px;
                font-weight: 800;
                color: #0f172a;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 95%;
                margin-top: 3px;
                background: rgba(255, 255, 255, 0.5);
                padding: 2px 4px;
                border-radius: 4px;
            }

            .podium-sub-detail {
                font-size: 9px;
                font-weight: 700;
                color: #334155;
                margin-top: 4px;
                background: rgba(255, 255, 255, 0.7);
                padding: 2px 5px;
                border-radius: 4px;
                width: 90%;
                line-height: 1.2;
            }

            .podium-score {
                font-size: 13px;
                font-weight: 900;
                color: #1e1103;
                margin-top: 4px;
                text-shadow: 0px 1px 0px rgba(255,255,255,0.6);
            }

            /* --- LIST KANAN --- */
            .rpg-list-container {
                display: flex;
                flex-direction: column;
                gap: 6px;
                position: relative;
                z-index: 2;
                overflow-y: auto;
                max-height: 380px;
                padding-right: 2px;
            }

            .rpg-normal-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 10px;
                border: 1.5px solid #cbd5e1;
                background: #ffffff;
                border-radius: 6px;
                color: #020617 !important;
                font-size: 12px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
                flex-shrink: 0;
            }

            .danger-zone-row {
                background: #fff5f5 !important;
                border: 1.5px solid #fca5a5 !important;
                color: #991b1b !important;
            }
            .danger-zone-badge {
                background: #fee2e2;
                color: #dc2626;
                font-size: 9px;
                padding: 2px 5px;
                border-radius: 4px;
                font-weight: 800;
                border: 1px solid #f87171;
            }

            .rpg-user-me {
                outline: 2.5px solid #2563eb !important;
                outline-offset: -1px;
            }

            .open-page-title { color: #3b1104 !important; text-align: center; font-weight: bold; margin-bottom: 2px; position: relative; z-index: 2; font-size: 16px; }
            .open-page-sub { color: #5c2406 !important; text-align: center; font-size: 11px; margin-bottom: 8px; position: relative; z-index: 2; font-weight: 600; }
            .open-book-divider { border-bottom: 2px solid #d4af37; margin-bottom: 10px; position: relative; z-index: 2; }
            .open-page-footer { margin-top: auto; text-align: right; font-size: 10px; color: #5c2406 !important; font-family: monospace; padding-top: 6px; font-weight: bold; position: relative; z-index: 2; }
            </style>
            """
            st.markdown(rpg_badge_style, unsafe_allow_html=True)

            active_period = st.session_state.get("active_period", "Periode PPS Aktif")

            # 3. OLAH DATA KASIR: MASTER_PERSONIL SEBAGAI ACUAN UTAMA
            sales_pps_df = st.session_state.get("sales_pps_df", st.session_state.get("SALES_PPS", pd.DataFrame()))
            periode_pps_df = st.session_state.get("periode_pps_df", st.session_state.get("PERIODE_PPS", pd.DataFrame()))
            master_personil_df = st.session_state.get("master_personil_df", st.session_state.get("MASTER_PERSONIL", pd.DataFrame()))

            # A. Filter Bulan Aktif dari PERIODE_PPS
            valid_month_dates = None
            if not periode_pps_df.empty and "start_date" in periode_pps_df.columns:
                try:
                    p_pps = periode_pps_df.copy()
                    p_pps["start_dt"] = pd.to_datetime(p_pps["start_date"], errors="coerce")
                    active_dates = p_pps[p_pps["status"].astype(str).str.lower() == "aktif"]["start_dt"].dropna()
                    if not active_dates.empty:
                        ref_month = active_dates.iloc[0].month
                        ref_year = active_dates.iloc[0].year
                        valid_month_dates = (ref_month, ref_year)
                except Exception:
                    valid_month_dates = None

            kasir_summary = {}

            # B. MASUKKAN SEMUA PERSONIL AKTIF DARI MASTER_PERSONIL DULU (Default 0 Pcs)
            if not master_personil_df.empty:
                mp_df = master_personil_df.copy()
                if "active" in mp_df.columns:
                    mp_df = mp_df[pd.to_numeric(mp_df["active"], errors="coerce") == 1]
                    
                if "person_name" in mp_df.columns:
                    for p_name in mp_df["person_name"].dropna().astype(str).str.strip().unique():
                        if p_name and p_name.lower() != "nan":
                            kasir_summary[p_name] = {"pwp": 0, "sg": 0, "total": 0}

            # C. UPDATE ATAU TIMPA DENGAN TRANSAKSI PENJUALAN PPS DARI SALES_PPS
            if not sales_pps_df.empty:
                sp_df = sales_pps_df.copy()
                kasir_col = next((c for c in ["kasir_name", "staff_name", "person_name"] if c in sp_df.columns), None)
                
                if kasir_col:
                    sp_df["clean_kasir"] = sp_df[kasir_col].astype(str).str.strip()
                    sp_df["qty_pwp"] = pd.to_numeric(sp_df.get("qty_pwp", 0), errors="coerce").fillna(0)
                    sp_df["qty_sg"] = pd.to_numeric(sp_df.get("qty_sg", 0), errors="coerce").fillna(0)

                    # Filter Berdasarkan Bulan Aktif
                    date_col = next((c for c in ["updated_at", "start_date", "tanggal"] if c in sp_df.columns), None)
                    if date_col and valid_month_dates:
                        sp_df["dt_check"] = pd.to_datetime(sp_df[date_col], errors="coerce")
                        sp_df = sp_df[(sp_df["dt_check"].dt.month == valid_month_dates[0]) & (sp_df["dt_check"].dt.year == valid_month_dates[1])]

                    grouped = sp_df.groupby("clean_kasir")[["qty_pwp", "qty_sg"]].sum().reset_index()

                    for _, r in grouped.iterrows():
                        k_name = r["clean_kasir"]
                        if not k_name or k_name.lower() == "nan":
                            continue
                        pwp_val = int(r["qty_pwp"])
                        sg_val = int(r["qty_sg"])
                        tot_val = pwp_val + sg_val
                        
                        # Masukkan ke dictionary (otomatis menimpa default 0 jika sudah ada di master, atau menambah baru jika belum ada)
                        kasir_summary[k_name] = {"pwp": pwp_val, "sg": sg_val, "total": tot_val}

            # D. SUSUN PERINGKAT BERDASARKAN TOTAL TERBANYAK
            ranking_list = []
            for k_name, val in kasir_summary.items():
                ranking_list.append((k_name, val["pwp"], val["sg"], val["total"]))

            ranking_list = sorted(ranking_list, key=lambda x: x[3], reverse=True)

            # 4. FUNGSI ELEMENT PODIUM
            def make_podium_item(rank_idx, class_name, crown_icon, r_list):
                if len(r_list) > rank_idx:
                    n, pwp, sg, tot = r_list[rank_idx]
                    is_me = (n.lower() == str(current_user_name).lower())
                    me_cls = "rpg-user-me" if is_me else ""
                    you_badge = '<span style="background:#2563eb; color:white; font-size:8px; padding:1px 4px; border-radius:4px; margin-top:2px;">KAMU</span>' if is_me else ""
                    
                    html = f'<div class="podium-slot">'
                    html += f'<div style="font-size:22px; margin-bottom:2px; z-index:3;">{crown_icon}</div>'
                    html += f'<div class="podium-card {class_name} {me_cls}">'
                    html += f'<div class="podium-rank-tag">#{rank_idx+1}</div>'
                    html += f'<div class="podium-name" title="{n}">{n}</div>'
                    html += f'{you_badge}'
                    html += f'<div class="podium-sub-detail">PWP: <b>{pwp}</b> | SG: <b>{sg}</b></div>'
                    html += f'<div class="podium-score">{tot} Pcs</div>'
                    html += f'</div></div>'
                    return html
                return ""

            podium_html = '<div class="podium-wrapper">'
            podium_html += make_podium_item(1, "podium-2", "🥈", ranking_list)
            podium_html += make_podium_item(0, "podium-1", "👑", ranking_list)
            podium_html += make_podium_item(2, "podium-3", "🥉", ranking_list)
            podium_html += '</div>'

            # 5. GENERATE LIST KANAN (PERINGKAT 4 SAMPAI SELESAI / TERMASUK #9 DST)
            rest_html = '<div class="rpg-list-container">'
            total_personil = len(ranking_list)
            danger_cutoff_rank = max(4, total_personil - 1)  # 2 orang terbawah masuk zona merah

            for i, (n, pwp, sg, tot) in enumerate(ranking_list[3:]):
                rank = i + 4
                is_me = (n.lower() == str(current_user_name).lower())
                me_class = "rpg-user-me" if is_me else ""
                you_badge = '<span style="background: #2563eb; color: white; font-size: 8px; padding: 1px 4px; border-radius: 4px; margin-left: 4px;">KAMU</span>' if is_me else ""
                
                is_danger = rank >= danger_cutoff_rank
                row_style = "danger-zone-row" if is_danger else ""
                danger_tag = '<span class="danger-zone-badge">⚠️ ZONA MERAH</span>' if is_danger else ""
                rank_icon = "🔻" if is_danger else "🛡️"

                rest_html += f'<div class="rpg-normal-row {row_style} {me_class}">'
                rest_html += f'<div style="display: flex; flex-direction: column; gap: 2px; overflow: hidden;">'
                rest_html += f'<div style="display: flex; align-items: center; gap: 4px;">'
                rest_html += f'<span>{rank_icon}</span>'
                rest_html += f'<span style="font-weight:bold;">#{rank}</span>'
                rest_html += f'<span style="font-weight:bold; overflow: hidden; text-overflow: ellipsis;" title="{n}">{n}</span>'
                rest_html += f'{you_badge}{danger_tag}'
                rest_html += f'</div>'
                rest_html += f'<div style="font-size: 10px; color: #475569; padding-left: 20px;">PWP: <b>{pwp}</b> Pcs | SG: <b>{sg}</b> Pcs</div>'
                rest_html += f'</div>'
                rest_html += f'<div style="flex-shrink: 0; margin-left: 6px; font-weight: 900; font-size: 13px; color: #0f172a;">{tot} Pcs</div>'
                rest_html += f'</div>'
            
            rest_html += '</div>'

            # 6. RENDER DUA HALAMAN BUKU
            html_open_tugas = (
                f'<div class="rpg-open-book-container">'
                f'<div class="rpg-book-page">'
                f'<h3 class="open-page-title">⚔️ PPS TOP (1-3)</h3>'
                f'<p class="open-page-sub">Periode: {active_period}</p>'
                f'<div class="open-book-divider"></div>'
                f'{podium_html}'
                f'<div class="open-page-footer">Halaman Kiri • PPS 1-3</div>'
                f'</div>'
                f'<div class="rpg-book-page">'
                f'<h3 class="open-page-title">⚔️ PPS (4+)</h3>'
                f'<p class="open-page-sub">Kelanjutan Peringkat Kasir PPS</p>'
                f'<div class="open-book-divider"></div>'
                f'{rest_html}'
                f'<div class="open-page-footer">Halaman Kanan • PPS 4+</div>'
                f'</div>'
                f'</div>'
            )

        #================================================batas=====================================================#

        elif page_num == 5:
            # 1. Ambil Username Aktif
            current_user_name = st.session_state.get("user_name", st.session_state.get("username", ""))

            # 2. STYLING CSS SUEGER PODIUM & LIST ITEM
            rpg_badge_style = """
            <style>
            .rpg-open-book-container {
                display: flex;
                flex-direction: row;
                gap: 20px;
                width: 100%;
                box-sizing: border-box;
            }

            @media (max-width: 768px) {
                .rpg-open-book-container {
                    flex-direction: column !important;
                    gap: 15px;
                }
            }

            .rpg-book-page {
                flex: 1;
                background: #fdf6e2;
                border: 3px solid #d4af37;
                border-radius: 8px;
                padding: 16px;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                min-height: 500px;
                position: relative;
                overflow: hidden;
            }

            .rpg-book-page::before {
                content: "";
                position: absolute;
                top: 0; left: 0; width: 100%; height: 100%;
                background-image: url("https://img.pikbest.com/png-images/20250303/fierce-dragon-silhouette--e2-80-93-stylized-black-and-white-mythical-beast-illustration_11570728.png!bw800");
                background-repeat: no-repeat;
                background-position: center;
                background-size: 85% auto;
                opacity: 0.08 !important;
                pointer-events: none;
                z-index: 0;
            }

            /* --- PODIUM SUEGER --- */
            .podium-wrapper {
                display: flex;
                align-items: flex-end;
                justify-content: center;
                gap: 8px;
                margin-top: auto;
                margin-bottom: 10px;
                position: relative;
                z-index: 2;
                width: 100%;
            }

            .podium-slot {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                min-width: 0;
            }

            .podium-card {
                width: 100%;
                border-radius: 6px 6px 0 0;
                padding: 8px 4px;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                box-shadow: 0 -3px 10px rgba(0,0,0,0.25), inset 0 1px 2px rgba(255,255,255,0.4);
                position: relative;
            }

            .podium-1 {
                height: 205px;
                background: linear-gradient(180deg, #fef08a 0%, #d97706 100%);
                border: 2.5px solid #78350f;
                border-bottom: none;
            }
            .podium-2 {
                height: 170px;
                background: linear-gradient(180deg, #f8fafc 0%, #64748b 100%);
                border: 2.5px solid #334155;
                border-bottom: none;
            }
            .podium-3 {
                height: 145px;
                background: linear-gradient(180deg, #ffedd5 0%, #c2410c 100%);
                border: 2.5px solid #7c2d12;
                border-bottom: none;
            }

            .podium-rank-tag {
                font-size: 14px;
                font-weight: 900;
                color: #1e1b4b;
                text-shadow: 0px 1px 0px rgba(255,255,255,0.8);
            }

            .podium-name {
                font-size: 11px;
                font-weight: 800;
                color: #0f172a;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 95%;
                margin-top: 3px;
                background: rgba(255, 255, 255, 0.5);
                padding: 2px 4px;
                border-radius: 4px;
            }

            .podium-sub-detail {
                font-size: 9px;
                font-weight: 700;
                color: #334155;
                margin-top: 4px;
                background: rgba(255, 255, 255, 0.7);
                padding: 2px 4px;
                border-radius: 4px;
                width: 92%;
                line-height: 1.2;
            }

            .podium-score {
                font-size: 13px;
                font-weight: 900;
                color: #1e1103;
                margin-top: 4px;
                text-shadow: 0px 1px 0px rgba(255,255,255,0.6);
            }

            /* --- LIST KANAN --- */
            .rpg-list-container {
                display: flex;
                flex-direction: column;
                gap: 6px;
                position: relative;
                z-index: 2;
                overflow-y: auto;
                max-height: 380px;
                padding-right: 2px;
            }

            .rpg-normal-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 10px;
                border: 1.5px solid #cbd5e1;
                background: #ffffff;
                border-radius: 6px;
                color: #020617 !important;
                font-size: 12px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
                flex-shrink: 0;
            }

            .danger-zone-row {
                background: #fff5f5 !important;
                border: 1.5px solid #fca5a5 !important;
                color: #991b1b !important;
            }
            .danger-zone-badge {
                background: #fee2e2;
                color: #dc2626;
                font-size: 9px;
                padding: 2px 5px;
                border-radius: 4px;
                font-weight: 800;
                border: 1px solid #f87171;
            }

            .rpg-user-me {
                outline: 2.5px solid #2563eb !important;
                outline-offset: -1px;
            }

            .open-page-title { color: #3b1104 !important; text-align: center; font-weight: bold; margin-bottom: 2px; position: relative; z-index: 2; font-size: 16px; }
            .open-page-sub { color: #5c2406 !important; text-align: center; font-size: 11px; margin-bottom: 8px; position: relative; z-index: 2; font-weight: 600; }
            .open-book-divider { border-bottom: 2px solid #d4af37; margin-bottom: 10px; position: relative; z-index: 2; }
            .open-page-footer { margin-top: auto; text-align: right; font-size: 10px; color: #5c2406 !important; font-family: monospace; padding-top: 6px; font-weight: bold; position: relative; z-index: 2; }
            </style>
            """
            st.markdown(rpg_badge_style, unsafe_allow_html=True)

            active_period = st.session_state.get("active_period", "Periode Sueger Aktif")

            # 3. OLAH DATA KASIR: MASTER_PERSONIL SEBAGAI ACUAN UTAMA
            sales_pps_df = st.session_state.get("sales_pps_df", st.session_state.get("SALES_PPS", pd.DataFrame()))
            periode_pps_df = st.session_state.get("periode_pps_df", st.session_state.get("PERIODE_PPS", pd.DataFrame()))
            master_personil_df = st.session_state.get("master_personil_df", st.session_state.get("MASTER_PERSONIL", pd.DataFrame()))

            # Filter Bulan Aktif dari PERIODE_PPS
            valid_month_dates = None
            if not periode_pps_df.empty and "start_date" in periode_pps_df.columns:
                try:
                    p_pps = periode_pps_df.copy()
                    p_pps["start_dt"] = pd.to_datetime(p_pps["start_date"], errors="coerce")
                    active_dates = p_pps[p_pps["status"].astype(str).str.lower() == "aktif"]["start_dt"].dropna()
                    if not active_dates.empty:
                        ref_month = active_dates.iloc[0].month
                        ref_year = active_dates.iloc[0].year
                        valid_month_dates = (ref_month, ref_year)
                except Exception:
                    valid_month_dates = None

            kasir_summary = {}

            # A. Masukkan semua personil aktif dari MASTER_PERSONIL (Default 0)
            if not master_personil_df.empty:
                mp_df = master_personil_df.copy()
                if "active" in mp_df.columns:
                    mp_df = mp_df[pd.to_numeric(mp_df["active"], errors="coerce") == 1]
                    
                if "person_name" in mp_df.columns:
                    for p_name in mp_df["person_name"].dropna().astype(str).str.strip().unique():
                        if p_name and p_name.lower() != "nan":
                            kasir_summary[p_name] = {"syarat": 0, "redeem": 0, "achiv": 0.0}

            # B. Ambil dan akumulasikan data Sueger dari SALES_PPS (syarat_sueger & redeem_sueger)
            if not sales_pps_df.empty:
                sp_df = sales_pps_df.copy()
                kasir_col = next((c for c in ["kasir_name", "staff_name", "person_name"] if c in sp_df.columns), None)
                
                if kasir_col and "syarat_sueger" in sp_df.columns and "redeem_sueger" in sp_df.columns:
                    sp_df["clean_kasir"] = sp_df[kasir_col].astype(str).str.strip()
                    sp_df["syarat_sueger"] = pd.to_numeric(sp_df["syarat_sueger"], errors="coerce").fillna(0)
                    sp_df["redeem_sueger"] = pd.to_numeric(sp_df["redeem_sueger"], errors="coerce").fillna(0)

                    # Filter Berdasarkan Bulan Aktif
                    date_col = next((c for c in ["updated_at", "start_date", "tanggal"] if c in sp_df.columns), None)
                    if date_col and valid_month_dates:
                        sp_df["dt_check"] = pd.to_datetime(sp_df[date_col], errors="coerce")
                        sp_df = sp_df[(sp_df["dt_check"].dt.month == valid_month_dates[0]) & (sp_df["dt_check"].dt.year == valid_month_dates[1])]

                    grouped = sp_df.groupby("clean_kasir")[["syarat_sueger", "redeem_sueger"]].sum().reset_index()

                    for _, r in grouped.iterrows():
                        k_name = r["clean_kasir"]
                        if not k_name or k_name.lower() == "nan":
                            continue
                        syarat_val = int(r["syarat_sueger"])
                        redeem_val = int(r["redeem_sueger"])
                        
                        # Hitung Persentase Achievement (%): (redeem / syarat) * 100
                        achiv_val = (redeem_val / syarat_val * 100) if syarat_val > 0 else 0.0
                        
                        kasir_summary[k_name] = {
                            "syarat": syarat_val, 
                            "redeem": redeem_val, 
                            "achiv": round(achiv_val, 1)
                        }

            # C. Susun Peringkat Berdasarkan % Achievement Tertinggi
            ranking_list = []
            for k_name, val in kasir_summary.items():
                ranking_list.append((k_name, val["syarat"], val["redeem"], val["achiv"]))

            ranking_list = sorted(ranking_list, key=lambda x: x[3], reverse=True)

            # 4. FUNGSI ELEMENT PODIUM
            def make_podium_item(rank_idx, class_name, crown_icon, r_list):
                if len(r_list) > rank_idx:
                    n, syarat, redeem, achiv = r_list[rank_idx]
                    is_me = (n.lower() == str(current_user_name).lower())
                    me_cls = "rpg-user-me" if is_me else ""
                    you_badge = '<span style="background:#2563eb; color:white; font-size:8px; padding:1px 4px; border-radius:4px; margin-top:2px;">KAMU</span>' if is_me else ""
                    
                    html = f'<div class="podium-slot">'
                    html += f'<div style="font-size:22px; margin-bottom:2px; z-index:3;">{crown_icon}</div>'
                    html += f'<div class="podium-card {class_name} {me_cls}">'
                    html += f'<div class="podium-rank-tag">#{rank_idx+1}</div>'
                    html += f'<div class="podium-name" title="{n}">{n}</div>'
                    html += f'{you_badge}'
                    html += f'<div class="podium-sub-detail">Syarat: {syarat}<br>Redeem: {redeem}</div>'
                    html += f'<div class="podium-score">{achiv}%</div>'
                    html += f'</div></div>'
                    return html
                return ""

            podium_html = '<div class="podium-wrapper">'
            podium_html += make_podium_item(1, "podium-2", "🥈", ranking_list)
            podium_html += make_podium_item(0, "podium-1", "👑", ranking_list)
            podium_html += make_podium_item(2, "podium-3", "🥉", ranking_list)
            podium_html += '</div>'

            # 5. GENERATE LIST KANAN (PERINGKAT 4 SAMPAI SELESAI)
            rest_html = '<div class="rpg-list-container">'
            total_personil = len(ranking_list)
            danger_cutoff_rank = max(4, total_personil - 1)

            for i, (n, syarat, redeem, achiv) in enumerate(ranking_list[3:]):
                rank = i + 4
                is_me = (n.lower() == str(current_user_name).lower())
                me_class = "rpg-user-me" if is_me else ""
                you_badge = '<span style="background: #2563eb; color: white; font-size: 8px; padding: 1px 4px; border-radius: 4px; margin-left: 4px;">KAMU</span>' if is_me else ""
                
                is_danger = rank >= danger_cutoff_rank
                row_style = "danger-zone-row" if is_danger else ""
                danger_tag = '<span class="danger-zone-badge">⚠️ ZONA MERAH</span>' if is_danger else ""
                rank_icon = "🔻" if is_danger else "🛡️"

                rest_html += f'<div class="rpg-normal-row {row_style} {me_class}">'
                rest_html += f'<div style="display: flex; flex-direction: column; gap: 2px; overflow: hidden;">'
                rest_html += f'<div style="display: flex; align-items: center; gap: 4px;">'
                rest_html += f'<span>{rank_icon}</span>'
                rest_html += f'<span style="font-weight:bold;">#{rank}</span>'
                rest_html += f'<span style="font-weight:bold; overflow: hidden; text-overflow: ellipsis;" title="{n}">{n}</span>'
                rest_html += f'{you_badge}{danger_tag}'
                rest_html += f'</div>'
                rest_html += f'<div style="font-size: 10px; color: #475569; padding-left: 20px;">Syarat: <b>{syarat}</b> | Redeem: <b>{redeem}</b></div>'
                rest_html += f'</div>'
                rest_html += f'<div style="flex-shrink: 0; margin-left: 6px; font-weight: 900; font-size: 13px; color: #0f172a;">{achiv}%</div>'
                rest_html += f'</div>'
            
            rest_html += '</div>'

            # 6. RENDER HALAMAN BUKU SUEGER
            html_open_tugas = (
                f'<div class="rpg-open-book-container">'
                f'<div class="rpg-book-page">'
                f'<h3 class="open-page-title">🥤 SUEGER TOP (1-3)</h3>'
                f'<p class="open-page-sub">Periode: {active_period}</p>'
                f'<div class="open-book-divider"></div>'
                f'{podium_html}'
                f'<div class="open-page-footer">Halaman Kiri • Sueger 1-3</div>'
                f'</div>'
                f'<div class="rpg-book-page">'
                f'<h3 class="open-page-title">🥤 SUEGER (4+)</h3>'
                f'<p class="open-page-sub">Kelanjutan Peringkat Kasir Sueger</p>'
                f'<div class="open-book-divider"></div>'
                f'{rest_html}'
                f'<div class="open-page-footer">Halaman Kanan • Sueger 4+</div>'
                f'</div>'
                f'</div>'
            )
        st.markdown(html_open_tugas, unsafe_allow_html=True)
        st.stop()

       
    #===============================================================================#
     # ⛺ JALUR C: BERANDA UTAMA 3 KARTU CAMP (YANG HARUSNYA MUNCUL DI AWAL)
    #==============================================================================#
    elif st.session_state["current_camp_menu"] == "main":
        st.markdown(
            """
            <style>
                .main .block-container { background-color: #0b0f19 !important; min-height: 100vh !important; max-width: 800px !important; margin: 0 auto !important; padding-top: 5% !important; padding-left: 20px !important; padding-right: 20px !important; box-sizing: border-box !important; }
                [data-testid="stSidebar"] { display: none !important; }
                [data-testid="stHeader"] { display: none !important; }
                div[data-testid="stColumn"] { display: flex !important; flex-direction: column !important; justify-content: flex-start !important; align-items: stretch !important; }
                .camp-card { background: linear-gradient(135deg, #131926 0%, #1e2638 100%); border: 2px solid #b45309; border-bottom: none; border-radius: 12px 12px 0 0; padding: 24px; text-align: center; position: relative; box-shadow: 0 4px 15px rgba(180, 83, 9, 0.15); flex-grow: 1; }
                .camp-card-full { background: linear-gradient(135deg, #131926 0%, #1e2638 100%); border: 2px solid #b45309; border-bottom: none; border-radius: 12px 12px 0 0; padding: 24px; text-align: center; position: relative; box-shadow: 0 4px 15px rgba(180, 83, 9, 0.15); width: 100%; box-sizing: border-box; margin-top: 20px; }
                .camp-icon { font-size: 45px; margin-bottom: 12px; filter: drop-shadow(0 0 8px rgba(251, 191, 36, 0.4)); }
                .camp-title { color: #fef08a; font-family: monospace; font-size: 16px; font-weight: 800; margin-bottom: 8px; letter-spacing: 1px; }
                .camp-desc { color: #94a3b8; font-family: monospace; font-size: 12px; line-height: 1.5; margin-bottom: 5px; }
                div.stButton { margin: 0 !important; padding: 0 !important; display: block !important; width: 100% !important; }
                div.stButton > button { background: rgba(180, 83, 9, 0.15) !important; color: #fef08a !important; border: 2px solid #b45309 !important; border-top: 1px solid rgba(180, 83, 9, 0.3) !important; border-radius: 0 0 12px 12px !important; font-family: monospace !important; font-size: 13px !important; font-weight: 700 !important; padding: 12px 0px !important; width: 100% !important; box-sizing: border-box !important; margin: 0 !important; }
                div.stButton > button:hover { background: #b45309 !important; color: #0b0f19 !important; box-shadow: 0 4px 12px rgba(180, 83, 9, 0.4) !important; }
                .leave-camp-box div.stButton { margin-top: 40px !important; }
                .leave-camp-box div.stButton > button { border-radius: 10px !important; background: rgba(239, 68, 68, 0.1) !important; color: #ef4444 !important; border: 1px solid rgba(239, 68, 68, 0.4) !important; }
                .leave-camp-box div.stButton > button:hover { background: #ef4444 !important; color: white !important; box-shadow: 0 0 15px rgba(239, 68, 68, 0.5) !important; }
                @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
                .spark { position: absolute; border-radius: 50%; border: 2px solid #ef4444; box-sizing: border-box; }
                .circle1 { width: 120px; height: 120px; animation: explode 1.6s infinite linear; filter: drop-shadow(0 0 10px #f97316); }
                .circle2 { width: 140px; height: 140px; animation: explode 1.6s infinite linear; animation-delay: 0.8s; filter: drop-shadow(0 0 10px #ef4444); }
                @keyframes strike { 0%, 100% { transform: scale(1) translateY(0); } 50% { transform: scale(0.9) translateY(8px); filter: drop-shadow(0 0 25px #fbbf24); } }
                @keyframes explode { 0% { transform: scale(0.3); opacity: 1; border-style: solid; } 50% { border-style: dashed; } 100% { transform: scale(1.1); opacity: 0; border-style: dotted; } }
            </style>
            """, 
            unsafe_allow_html=True
        )

        st.markdown("<h1 style='color: #f59e0b; font-family: monospace; font-size: 32px; text-shadow: 0 0 15px rgba(245,158,11,0.4); text-align: center; margin-bottom: 5px;'>⛺ PREPARATION CAMP ⛺</h1>", unsafe_allow_html=True)
        col_camp1, col_camp2, col_camp3 = st.columns(3)
    
        #================
        #Kartu nama anjay#
        #================
        with col_camp1:
            st.markdown("<div class='camp-card'><div class='camp-icon'>📜</div><div class='camp-title'>ANGGOTA GUILD</div><div class='camp-desc'>Buka gulungan piagam untuk memeriksa status level, poin atribut, dan rapor performa penjualan individu Anda.</div></div>", unsafe_allow_html=True)
            if st.button("Lihat Status ➔", use_container_width=True, key="btn_camp_status"):
                placeholder = st.empty()
                with placeholder.container():
                    # --- LAYAR LOADING FULLSCREEN: RITUAL PENCATATAN NAMA HERO (ANTI-STUCK) ---
                    st.markdown(
                        """
                        <div style='background-color: #0c1020; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;'>
                            <div class="magic-portal-container" style="position: relative; width: 150px; height: 150px; display: flex; justify-content: center; align-items: center;">
                                <!-- Efek Ring Sihir Emas Berpusing Pelan -->
                                <svg width="160" height="160" viewBox="0 0 160 160" style="position: absolute;">
                                    <circle cx="80" cy="80" r="70" stroke="#d97706" stroke-width="2" stroke-dasharray="8, 6" fill="none" style="transform-origin: 80px 80px; animation: spin-clockwise 10s infinite linear;" />
                                    <circle cx="80" cy="80" r="50" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="3, 4" fill="none" style="transform-origin: 80px 80px; animation: spin-counter 6s infinite linear;" />
                                </svg>
                                <div style="font-size: 50px; filter: drop-shadow(0 0 12px #d97706); animation: pulse-core 2s infinite ease-in-out;">📜</div>
                            </div>
                            <h1 style='color: #fbbf24; font-family: monospace; animation: blink 1.5s infinite; font-size: 22px; margin-top: 40px; letter-spacing: 2px; text-shadow: 0 0 15px rgba(251,191,36,0.4);'>RECORDING HERO NAME...</h1>
                            <p style='color: #475569; font-size: 13px; margin-top: 5px; font-family: monospace;'>Reading spreadsheet registry and stabilizing guild roster...</p>
                            <style>
                                @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
                                [data-testid="stSidebar"] { display: none !important; }
                                [data-testid="stHeader"] { display: none !important; }
                                @keyframes spin-clockwise { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                                @keyframes spin-counter { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
                                @keyframes pulse-core { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }
                            </style>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    # Menjalankan bar simulasi pemuatan selama ~3 detik
                    progress_bar = st.progress(0)
                    for percent_complete in range(100):
                        time.sleep(0.03) 
                        progress_bar.progress(percent_complete + 1)
                
                placeholder.empty()
                # Nyalakan status sub-menu dan segarkan halaman untuk menampilkan Back Card
                st.session_state.current_camp_menu = "status"
                st.rerun()
                
        with col_camp2:
            st.markdown("<div class='camp-card'><div class='camp-icon'>🎯</div><div class='camp-title'>QUIZ CAMPAIGN</div><div class='camp-desc'>Cek papan pengumuman untuk melihat quest musiman, tugas mingguan PSM, serta daily target buruan Anda.</div></div>", unsafe_allow_html=True)
            if st.button("Ambil Quest ➔", use_container_width=True, key="btn_camp_quest"):
                placeholder_loading = st.empty()
                with placeholder_loading.container():
                    # 🧙‍♂️ RITUAL LOADING FULLSCREEN: LINGKARAN SIHIR + PENCATATAN BUKU GAIB
                    st.markdown(
                        """
                        <div style='background-color: #0c1020; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;'>
                            <!-- LINGKARAN SIHIR VEKTOR BERPENDAR NEON -->
                            <div class="magic-circle-container" style="position: relative; width: 200px; height: 100px; display: flex; justify-content: center; align-items: center;">
                                <svg width="200" height="200" viewBox="0 0 200 200" style="position: absolute; top: -50px;">
                                    <circle cx="100" cy="100" r="90" class="vector-glow" stroke="#00f0ff" stroke-width="3" stroke-dasharray="15, 10" fill="none" />
                                    <circle cx="100" cy="100" r="65" class="vector-glow-inner" stroke="#a855f7" stroke-width="2" stroke-dasharray="4, 6" fill="none" />
                                    <polygon points="100,25 165,140 35,140" stroke="#fbbf24" stroke-width="1.5" fill="none" class="vector-glow" style="transform-origin: 100px 100px; animation: spin-clockwise 12s infinite linear;" />
                                </svg>
                                <!-- EMOJI BUKU BERPUTAR DI TENGAH SEGITIGA SIHIR -->
                                <div class="magic-core-book" style="position: absolute; font-size: 55px; filter: drop-shadow(0 0 15px #00f0ff); animation: pulse-book 1.5s infinite ease-in-out; z-index: 10;">📖</div>
                            </div>
                            <!-- TEKS ANIMASI PENCATATAN DATA -->
                            <h1 id="txt-magic-title" style='color: #00f0ff; font-family: monospace; animation: blink-text 1.2s infinite; font-size: 22px; margin-top: 70px; letter-spacing: 2px; text-shadow: 0 0 15px rgba(0,240,255,0.5); text-align: center;'>LOGGING ADVENTURE DATA...</h1>
                            <p id="txt-magic-sub" style='color: #64748b; font-size: 13px; margin-top: 5px; font-family: monospace; text-align: center; max-width: 320px; padding: 0 15px;'>Opening the heavy leather journal and engraving your guild performance...</p>
                            <!-- GAUNG GAYA ANIMASI CSS -->
                            <style>
                                @keyframes spin-clockwise { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                                .vector-glow { transform-origin: 100px 100px; animation: spin-clockwise 10s infinite linear; filter: drop-shadow(0 0 12px #00f0ff); }
                                .vector-glow-inner { transform-origin: 100px 100px; animation: spin-clockwise 6s infinite linear; reverse; filter: drop-shadow(0 0 10px #a855f7); }
                                @keyframes pulse-book { 0%, 100% { transform: scale(1) rotateY(0deg); } 50% { transform: scale(1.15) rotateY(180deg); } }
                                @keyframes blink-text { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
                            </style>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    # Jeda khidmat simulasi prapencatatan mantra (3 detik)
                    progress_bar = st.progress(0)
                    for percent_complete in range(100):
                        time.sleep(0.02)
                        progress_bar.progress(percent_complete + 1)
                        if percent_complete == 40:
                            st.markdown("<script>window.parent.document.getElementById('txt-magic-title').innerHTML = 'SYNCHRONIZING REWARD LOGS...'; window.parent.document.getElementById('txt-magic-sub').innerHTML = 'Inking down total item counts and verifying sueger elixirs...';</script>", unsafe_allow_html=True)
                        elif percent_complete == 80:
                            st.markdown("<script>window.parent.document.getElementById('txt-magic-title').innerHTML = 'STABILIZING MANA CONNECTIONS...'; window.parent.document.getElementById('txt-magic-sub').innerHTML = 'Polishing crystal emblems and locking privacy gates...';</script>", unsafe_allow_html=True)
                    
                    # 🔔 LAYAR KEDUA: PENGUMUMAN SELAMAT DATANG DI RESEPSIONIS GUILD
                    st.markdown(
                        """
                        <div style='background-color: #0c1020; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1000000; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;'>
                            <div style='font-size: 70px; filter: drop-shadow(0 0 20px #fbbf24); animation: welcome-bounce 1s infinite alternate;'>🛎️</div>
                            <h1 style='color: #fbbf24; font-family: monospace; font-size: 26px; margin-top: 30px; letter-spacing: 2px; text-shadow: 0 0 20px rgba(251,191,36,0.6); text-align: center; padding: 0 10px;'>SELAMAT DATANG DI RESEPSIONIS GUILD</h1>
                            <p style='color: #ffffff; font-size: 14px; margin-top: 10px; font-family: monospace; text-align: center; font-style: italic;'>Silakan pilih buku panduan di meja resepsionis untuk melanjutkan tugas.</p>
                            <style>
                                @keyframes welcome-bounce { from { transform: translateY(0); } to { transform: translateY(-12px); } }
                            </style>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    time.sleep(1.8) # Jeda waktu agar pengguna bisa membaca tulisan selamat datang
                
                placeholder_loading.empty()
                
                # Mengaktifkan gerbang alihan menuju halaman 2 Buku Resepsionis
                st.session_state.current_camp_menu = "quiz_campaign"
                st.session_state["campaign_sub_page"] = "resepsionis_utama"
                st.rerun()

                
        # =========================================================================
        # ⚔️ KARTU 3: UPGRADE SKILL (EDISI RITUAL PENEMPAAN SENJATA 1-100)
        # =========================================================================
        with col_camp3:
            st.markdown("<div class='camp-card'><div class='camp-icon'>⚔️</div><div class='camp-title'>UPGRADE SKILL</div><div class='camp-desc'>Masuki ruang latihan untuk mengasah keahlian bertarung Anda (Shortcut penginputan data transaksi penjualan).</div></div>", unsafe_allow_html=True)
            if st.button("Latih Skill ➔", use_container_width=True, key="btn_camp_skill"):
                placeholder = st.empty()
                with placeholder.container():
                    # --- LAYAR LOADING FULLSCREEN: BLACKSMITH FORGING (MURNI TANPA TAG STYLE YANG RAWAN BOCOR) ---
                    st.markdown(
                        """
                        <div style='background-color: #0c1020; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;'>
                            <div class="forge-container" style="position: relative; width: 150px; height: 150px; display: flex; justify-content: center; align-items: center;">
                                <div class="anvil" style="font-size: 70px; z-index: 10; animation: strike 0.8s infinite ease-in-out;">⚒️</div>
                                <div class="spark circle1"></div>
                                <div class="spark circle2"></div>
                            </div>
                            <h1 style='color: #f97316; font-family: monospace; animation: blink 1.2s infinite; font-size: 26px; margin-top: 40px; letter-spacing: 2px; text-shadow: 0 0 15px rgba(249,115,22,0.5);'>FORGING YOUR SALES SKILL...</h1>
                            <p id="forge-status" style='color: #64748b; font-size: 13px; margin-top: 5px; font-family: monospace;'>Heating the metal and sharpening performance attributes...</p>
                            <p id="progress-text" style='color: #fbbf24; font-family: monospace; font-size: 18px; font-weight: bold; margin-top: 25px;'>FORGING PROGRESS: 0%</p>
                        </div>
                        """, unsafe_allow_html=True
                    )
                    
                    # Progress bar simulasi tempa berjalan mundur lambat khidmat
                    progress_bar = st.progress(0)
                    for percent_complete in range(100):
                        time.sleep(0.04) 
                        current_percent = percent_complete + 1
                        progress_bar.progress(current_percent)
                        st.markdown(f"<script>window.parent.document.getElementById('progress-text').innerHTML = 'FORGING PROGRESS: {current_percent}%'; if ({current_percent} > 40 && {current_percent} < 80) {{ window.parent.document.getElementById('forge-status').innerHTML = 'Tempering blade core and structuring transaction logs...'; }} else if ({current_percent} >= 80) {{ window.parent.document.getElementById('forge-status').innerHTML = 'Quenching weapon in holy water! Stabilization complete!'; }}</script>", unsafe_allow_html=True)
                    
                    # Sukses Screen Pendek
                    st.markdown("<div style='background-color: #0c1020; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1000000; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;'><h1 style='color: #fbbf24; font-family: monospace; font-size: 32px; text-shadow: 0 0 20px rgba(251,191,36,0.6);'>⚔️ WEAPON UPGRADED!</h1><p style='color: #ffffff; font-size: 15px; margin-top: 10px; font-family: monospace;'>Entering training ground with your sharpest sword...</p></div>", unsafe_allow_html=True)
                    time.sleep(1.2)
                
                # 🚀 KUNCI PERBAIKAN EMERGENSI: MENGGUNAKAN GERBANG ALIHAN AMAN (ANTI-TABRAKAN WIDGET)
                placeholder.empty()
                st.session_state.portal_prep_ready = False  # Menutup layar perkemahan
                
                # Alih-alih menembak widget langsung, kita nyalakan saklar bantuan sementara
                st.session_state.redirect_to_input = True
                
                st.rerun()
                
        st.markdown("<div class='leave-camp-box'>", unsafe_allow_html=True)
        if st.button("🚪 KEMBALI KE BERANDA KOTA", use_container_width=True, key="btn_leave_camp"):
            st.session_state.portal_prep_ready = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

# =========================================================================
# MENU UTAMA: GAYA RPG RESPONSIVE (PORTAL GUILD ONLY)
# =========================================================================
if selected_tab == "🏠 Menu Utama":

    # -------------------------------------------------------------------------
    # 1. RENDER HEADER UTAMA MEDIEVAL ROYAL GUILD (HANYA DI TAB MENU UTAMA)
    # -------------------------------------------------------------------------
    is_di_dalam_camp = (
        "portal_prep_ready" in st.session_state
        and st.session_state.portal_prep_ready
    ) or (
        "current_camp_menu" in st.session_state
        and st.session_state["current_camp_menu"] == "status"
    )

    if not is_di_dalam_camp:
        unfilled_info = "✅ Semua shift aman"
        badge_bg = "rgba(16, 185, 129, 0.15)"
        badge_border = "#10b981"
        badge_text_color = "#34d399"

        try:
            if (
                "sales_pps_df" in st.session_state
                and not st.session_state.sales_pps_df.empty
            ):
                df_pps = st.session_state.sales_pps_df.copy()

                col_date_name = "updated_at"
                col_shift_name = "shift_personil"

                if (
                    col_date_name in df_pps.columns
                    and col_shift_name in df_pps.columns
                ):
                    df_pps["clean_date"] = pd.to_datetime(
                        df_pps[col_date_name], errors="coerce"
                    ).dt.date
                    today_date = pd.Timestamp.now(tz="Asia/Jakarta").date()

                    df_today = df_pps[df_pps["clean_date"] == today_date]
                    shifts_found = (
                        df_today[col_shift_name].dropna().astype(str).unique()
                    )

                    missing_shifts = []
                    for s in ["Shift 1", "Shift 2", "Shift 3"]:
                        num = s.split()[-1]
                        if not any(
                            s.lower() in found.lower() or num == found.strip()
                            for found in shifts_found
                        ):
                            missing_shifts.append(s)

                    if len(df_today) == 0:
                        unfilled_info = "⚠️ Belum ada input hari ini"
                        badge_bg = "rgba(245, 158, 11, 0.15)"
                        badge_border = "#f59e0b"
                        badge_text_color = "#fbbf24"
                    elif missing_shifts:
                        unfilled_info = f"⚠️ Belum: {', '.join(missing_shifts)}"
                        badge_bg = "rgba(239, 68, 68, 0.15)"
                        badge_border = "#ef4444"
                        badge_text_color = "#fca5a5"
                else:
                    unfilled_info = "ℹ️ Kolom data tidak ditemukan"
            else:
                unfilled_info = "⚠️ Memuat Data Sales..."
                badge_bg = "rgba(245, 158, 11, 0.15)"
                badge_border = "#f59e0b"
                badge_text_color = "#fbbf24"
        except Exception as e:
            unfilled_info = "⚠️ Cek data gagal"

        rpg_header_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Quicksand:wght@600;700&display=swap');

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                background-color: transparent;
                font-family: 'Quicksand', sans-serif;
                overflow: hidden;
            }}

            /* BINGKAI UTAMA ROYAL KERAJAAN */
            .royal-outer-frame {{
                position: relative;
                background: radial-gradient(circle, #162447 0%, #0c1427 100%);
                border: 3px double #d4af37;
                border-radius: 14px;
                box-shadow: 0 0 15px rgba(212, 175, 55, 0.35), inset 0 0 20px rgba(0, 0, 0, 0.8);
                padding: 10px 14px;
                color: #f1e5c7;
                margin-bottom: 5px;
            }}

            /* UKIRAN SUDUT EMAS */
            .corner-ornament {{
                position: absolute;
                color: #d4af37;
                font-size: 10px;
                line-height: 1;
                opacity: 0.85;
                pointer-events: none;
            }}
            .top-left {{ top: 3px; left: 5px; }}
            .top-right {{ top: 3px; right: 5px; }}
            .bottom-left {{ bottom: 3px; left: 5px; }}
            .bottom-right {{ bottom: 3px; right: 5px; }}

            /* BARIS ATAS: JUDUL DASHBOARD */
            .guild-title-box {{
                text-align: center;
                margin-bottom: 8px;
            }}

            .guild-title {{
                font-family: 'MedievalSharp', serif;
                font-size: 16px;
                color: #f7e7b4;
                text-shadow: 0 0 8px rgba(212, 175, 55, 0.8), 2px 2px 4px #000;
                margin: 0;
                letter-spacing: 0.8px;
            }}

            .guild-subtitle {{
                font-size: 9px;
                color: #38bdf8;
                margin-top: 1px;
                letter-spacing: 0.3px;
            }}

            /* BARIS BAWAH: DUA KOTAK SIMETRIS */
            .bottom-row {{
                display: flex;
                align-items: stretch;
                justify-content: space-between;
                gap: 10px;
                width: 100%;
            }}

            .royal-side-box {{
                flex: 1;
                background: rgba(10, 17, 34, 0.75);
                border: 1px solid #9a7b38;
                border-radius: 8px;
                padding: 6px 10px;
                min-width: 0;
                box-shadow: inset 0 0 8px rgba(0, 0, 0, 0.6);
                display: flex;
                flex-direction: column;
                justify-content: center;
            }}

            .box-title {{
                font-size: 8px;
                color: #e5c158;
                font-weight: bold;
                letter-spacing: 0.6px;
                margin-bottom: 3px;
                text-transform: uppercase;
            }}

            /* RUNNING TEXT (KIRI) */
            .marquee-container {{
                overflow: hidden;
                white-space: nowrap;
                width: 100%;
                background: {badge_bg};
                border: 1px solid {badge_border};
                border-radius: 5px;
                padding: 2px 0;
                margin-top: 2px;
            }}

            .marquee-text {{
                display: inline-block;
                padding-left: 100%;
                animation: marquee 10s linear infinite;
                color: {badge_text_color};
                font-size: 10px;
                font-weight: bold;
            }}

            @keyframes marquee {{
                0%   {{ transform: translate(0, 0); }}
                100% {{ transform: translate(-100%, 0); }}
            }}

            /* KANAN: FLEX LAYOUT UNTUK MENGISI SISI KIRI & KANAN KOTAK */
            .time-box-wrapper {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                width: 100%;
            }}

            .hourglass-container {{
                display: flex;
                align-items: center;
                justify-content: center;
                padding-right: 8px;
            }}

            .hourglass-spin {{
                font-size: 20px;
                display: inline-block;
                filter: drop-shadow(0 0 6px rgba(212, 175, 55, 0.8));
                animation: spinHourglass 2.5s infinite ease-in-out;
            }}

            @keyframes spinHourglass {{
                0% {{ transform: rotate(0deg); }}
                50% {{ transform: rotate(180deg); }}
                100% {{ transform: rotate(180deg); }}
            }}

            .right-clock-content {{
                text-align: right;
                flex: 1;
            }}

            .greeting-text {{
                font-size: 9px;
                color: #fcd34d;
                font-weight: bold;
                margin-bottom: 1px;
            }}

            .digital-clock {{
                font-family: monospace;
                font-size: 13px;
                font-weight: bold;
                color: #38bdf8;
                text-shadow: 0 0 6px rgba(56, 189, 248, 0.5);
                line-height: 1.1;
            }}

            .digital-date {{
                font-size: 9px;
                color: #cbd5e1;
                margin-top: 1px;
                font-weight: bold;
            }}

            @media (min-width: 650px) {{
                .guild-title {{ font-size: 18px; }}
                .guild-subtitle {{ font-size: 11px; }}
                .greeting-text {{ font-size: 10px; }}
                .digital-clock {{ font-size: 14px; }}
                .digital-date {{ font-size: 10px; }}
                .box-title {{ font-size: 9px; }}
                .marquee-text {{ font-size: 11px; }}
                .hourglass-spin {{ font-size: 24px; }}
            }}
        </style>
        </head>
        <body>

        <div class="royal-outer-frame">
            <div class="corner-ornament top-left">⚜</div>
            <div class="corner-ornament top-right">⚜</div>
            <div class="corner-ornament bottom-left">⚜</div>
            <div class="corner-ornament bottom-right">⚜</div>

            <div class="guild-title-box">
                <h1 class="guild-title">⚔️ Dashboard Toko Karang Satria ⚔️</h1>
                <div class="guild-subtitle">Sistem Analisis & Optimasi Pencapaian Target Toko</div>
            </div>

            <div class="bottom-row">
                <div class="royal-side-box">
                    <div class="box-title">📜 STATUS INPUT SHIFT</div>
                    <div class="marquee-container">
                        <span class="marquee-text">{unfilled_info}</span>
                    </div>
                </div>

                <div class="royal-side-box">
                    <div class="time-box-wrapper">
                        <div class="hourglass-container">
                            <span class="hourglass-spin">⏳</span>
                        </div>
                        <div class="right-clock-content">
                            <div class="greeting-text" id="timeGreeting">🌙 Selamat Malam</div>
                            <div class="digital-clock" id="liveClock">00:00:00 WIB</div>
                            <div class="digital-date" id="liveDate">Senin, 01/01/2026</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function updateClock() {{
                const now = new Date();
                const hoursNum = now.getHours();
                
                let greeting = "🌙 Selamat Malam";
                if (hoursNum >= 4 && hoursNum < 11) {{
                    greeting = "🌅 Selamat Pagi";
                }} else if (hoursNum >= 11 && hoursNum < 15) {{
                    greeting = "☀️ Selamat Siang";
                }} else if (hoursNum >= 15 && hoursNum < 18) {{
                    greeting = "🌇 Selamat Sore";
                }}
                document.getElementById('timeGreeting').textContent = greeting;

                const hours = String(hoursNum).padStart(2, '0');
                const minutes = String(now.getMinutes()).padStart(2, '0');
                const seconds = String(now.getSeconds()).padStart(2, '0');
                document.getElementById('liveClock').textContent = `${{hours}}:${{minutes}}:${{seconds}} WIB`;

                const daysArr = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
                const dayName = daysArr[now.getDay()];
                
                const day = String(now.getDate()).padStart(2, '0');
                const month = String(now.getMonth() + 1).padStart(2, '0');
                const year = now.getFullYear();
                
                document.getElementById('liveDate').textContent = `${{dayName}}, ${{day}}/${{month}}/${{year}}`;
            }}

            setInterval(updateClock, 1000);
            updateClock();
        </script>

        </body>
        </html>
        """

        components.html(rpg_header_html, height=175)

    # -------------------------------------------------------------------------
    # 2. STYLING UNTUK KARTU RPG UTAMA
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <style>
            .rpg-grid-container {
                width: 100%;
                margin-top: 10px;
            }
            .rpg-card-center-fixed {
                background: linear-gradient(135deg, rgba(15, 23, 42, 0.75) 0%, rgba(30, 41, 59, 0.95) 100%);
                border: 2px solid #38bdf8;
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 15px;
                min-height: 290px;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                align-items: center;
                text-align: center;
                position: relative;
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
                box-shadow: 0 0 15px rgba(56, 189, 248, 0.1);
            }
            .rpg-card-center-fixed:hover {
                transform: translateY(-5px);
                border-color: #00f0ff;
                box-shadow: 0 0 25px rgba(0, 240, 255, 0.35);
            }
            .rpg-icon-center-fixed {
                font-size: 55px;
                margin-top: 15px;
                margin-bottom: 10px;
                filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.5));
                animation: pulse-game 2s infinite ease-in-out;
                display: block;
                width: 100%;
            }
            .rpg-badge-fixed {
                position: absolute;
                top: 14px;
                right: 14px;
                font-size: 9px;
                font-weight: 800;
                padding: 3px 8px;
                border-radius: 20px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }
            .badge-dungeon {
                background-color: rgba(239, 68, 68, 0.15);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.4);
            }
            .badge-prep {
                background-color: rgba(234, 179, 8, 0.15);
                color: #eab308;
                border: 1px solid rgba(234, 179, 8, 0.4);
            }
            .rpg-title-fixed {
                color: #ffffff;
                font-size: 20px;
                font-weight: 800;
                margin-bottom: 8px;
                letter-spacing: 1px;
            }
            .rpg-desc-fixed {
                color: #94a3b8;
                font-size: 13px;
                line-height: 1.5;
                margin-bottom: 15px;
            }
            div[data-testid="stColumn"] div.stButton > button {
                background: rgba(56, 189, 248, 0.08) !important;
                color: #38bdf8 !important;
                border: 1px solid #38bdf8 !important;
                border-radius: 10px !important;
                padding: 10px 0px !important;
                font-weight: 700 !important;
                transition: all 0.2s ease !important;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2) !important;
            }
            div[data-testid="stColumn"] div.stButton > button:hover {
                background: #38bdf8 !important;
                color: #0f172a !important;
                box-shadow: 0 0 15px rgba(56, 189, 248, 0.5) !important;
            }
            @keyframes pulse-game {
                0% { transform: scale(1); }
                50% { transform: scale(1.06); }
                100% { transform: scale(1); }
            }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='rpg-grid-container'>", unsafe_allow_html=True)

    col_game1, col_game2 = st.columns(2)

    # 🏰 KARTU 1: ENTER GUILD
    with col_game1:
        st.markdown(
            """
            <div class='rpg-card-center-fixed'>
                <div class='rpg-badge-fixed badge-dungeon'>🛡️ Alliance Mode</div>
                <div class='rpg-icon-center-fixed'>🏰</div>
                <div class='rpg-title-fixed'>ENTER GUILD</div>
                <div class='rpg-desc-fixed'>Masuk ke Markas Besar Guild untuk memantau papan pengumuman performa total, grafik target kelompok, dan analisis pencapaian bersama.</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        if "portal_guild_ready" not in st.session_state:
            st.session_state.portal_guild_ready = False

        if st.button("Masuk Markas Guild ➔", use_container_width=True, key="btn_enter_dungeon_fixed"):
            placeholder = st.empty()
            with placeholder.container():
                st.markdown(
                    """
                    <style>
                        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
                        [data-testid="stSidebar"] { display: none !important; }
                        [data-testid="stHeader"] { display: none !important; }
                        .magic-portal-container { position: relative; width: 180px; height: 180px; display: flex; justify-content: center; align-items: center; }
                        .portal-core-icon { position: absolute; font-size: 32px; z-index: 10; animation: pulse-core 2s infinite ease-in-out; }
                        .outer-vector { transform-origin: 90px 90px; animation: spin-clockwise 8s infinite linear; filter: drop-shadow(0 0 12px rgba(0, 240, 255, 0.5)); }
                        .middle-vector { transform-origin: 90px 90px; animation: spin-counter 5s infinite linear; filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.5)); }
                        .inner-vector { transform-origin: 90px 90px; filter: drop-shadow(0 0 15px rgba(0, 255, 136, 0.6)); }
                        @keyframes spin-clockwise { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                        @keyframes spin-counter { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
                        @keyframes pulse-core { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1); } }
                    </style>
                    
                    <div style='background-color: #0c1020; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;'>
                        <div class="magic-portal-container">
                            <svg width="180" height="180" viewBox="0 0 180 180" style="position: absolute;">
                                <circle cx="90" cy="90" r="80" class="outer-vector" stroke="#00f0ff" stroke-width="3" stroke-dasharray="12, 8" fill="none" />
                                <circle cx="90" cy="90" r="55" class="middle-vector" stroke="#6366f1" stroke-width="2" stroke-dasharray="3, 6" fill="none" />
                                <circle cx="90" cy="90" r="32" class="inner-vector" stroke="#00ff88" stroke-width="2" fill="#0f172a" />
                            </svg>
                            <div class="portal-core-icon">🏰</div>
                        </div>
                        <h1 style='color: #00f0ff; font-family: monospace; animation: blink 1.5s infinite; font-size: 24px; margin-top: 50px; letter-spacing: 2px;'>CONJURING PORTAL...</h1>
                        <p style='color: #64748b; font-size: 13px; margin-top: 5px; font-family: monospace;'>Channeling mana resources and stabilizing guild gate...</p>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

                progress_bar = st.progress(0)
                for percent_complete in range(100):
                    time.sleep(0.04) 
                    progress_bar.progress(percent_complete + 1)

            placeholder.empty()
            st.session_state.portal_guild_ready = True
            st.rerun()

    # 🎒 KARTU 2: PREPARATION CAMP
    with col_game2:
        st.markdown(
            """
            <div class='rpg-card-center-fixed'>
                <div class='rpg-badge-fixed badge-prep'>🛡️ Solo Prep</div>
                <div class='rpg-icon-center-fixed'>🎒</div>
                <div class='rpg-title-fixed'>PREPARATION CAMP</div>
                <div class='rpg-desc-fixed'>Lihat tas penyimpanan (Inventory) rapor pribadi Anda. Cek pencapaian individu, target harian staf, dan statistik performa Anda sendiri.</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        if "portal_prep_ready" not in st.session_state:
            st.session_state.portal_prep_ready = False

        if st.button("Buka Rapor Personil Toko ➔", use_container_width=True, key="btn_enter_prep_fixed"):
            placeholder = st.empty()
            with placeholder.container():
                st.markdown(
                    """
                    <div style='background-color: #0c1020; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;'>
                        <div class="magic-portal-container">
                            <svg width="180" height="180" viewBox="0 0 180 180" style="position: absolute;">
                                <circle cx="90" cy="90" r="80" class="outer-vector" stroke="#eab308" stroke-width="3" stroke-dasharray="12, 8" fill="none" />
                                <circle cx="90" cy="90" r="55" class="middle-vector" stroke="#b45309" stroke-width="2" stroke-dasharray="3, 6" fill="none" />
                                <circle cx="90" cy="90" r="32" class="inner-vector" stroke="#f59e0b" stroke-width="2" fill="#0f172a" />
                            </svg>
                            <div class="portal-core-icon">🎒</div>
                        </div>
                        <h1 style='color: #eab308; font-family: monospace; animation: blink 1.5s infinite; font-size: 24px; margin-top: 50px; letter-spacing: 2px;'>OPENING INVENTORY...</h1>
                        <p style='color: #64748b; font-size: 13px; margin-top: 5px; font-family: monospace;'>Equipping gear and sorting personal records...</p>
                        <style>
                            @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
                            [data-testid="stSidebar"] { display: none !important; }
                            [data-testid="stHeader"] { display: none !important; }
                            .magic-portal-container { position: relative; width: 180px; height: 180px; display: flex; justify-content: center; align-items: center; }
                            .portal-core-icon { position: absolute; font-size: 32px; z-index: 10; animation: pulse-core 2s infinite ease-in-out; }
                            .outer-vector { transform-origin: 90px 90px; animation: spin-clockwise 8s infinite linear; filter: drop-shadow(0 0 12px rgba(234, 179, 8, 0.4)); }
                            .middle-vector { transform-origin: 90px 90px; animation: spin-counter 5s infinite linear; filter: drop-shadow(0 0 8px rgba(180, 83, 9, 0.4)); }
                            .inner-vector { transform-origin: 90px 90px; filter: drop-shadow(0 0 15px rgba(245, 158, 11, 0.5)); }
                            @keyframes spin-clockwise { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                            @keyframes spin-counter { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }
                            @keyframes pulse-core { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1); } }
                        </style>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                progress_bar = st.progress(0)
                for percent_complete in range(100):
                    time.sleep(0.04) 
                    progress_bar.progress(percent_complete + 1)

            placeholder.empty()

            st.session_state.current_camp_menu = "main"
            st.session_state.portal_prep_ready = True

            st.rerun()

    
# =============================================================================
# --- INPUT & RESET DATA ---
# =============================================================================
elif selected_tab == "📝 Input Data":
    st.markdown(
        "<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>✏️"
        " Kelola & Input Data Penjualan</h2>",
        unsafe_allow_html=True,
    )
    
    # --- Context & User Role ---
    current_user = st.session_state.get("username", "visitor")
    user_lower = str(current_user).lower()
    is_admin = any(
        x in user_lower for x in ["admin", "chief", "cos", "lavitality"]
    )
    is_visitor = "visitor" in user_lower

    # --- DataFrames Normalization ---
    periods_df = st.session_state.get("periods_df", pd.DataFrame()).copy()
    periode_pps_df = st.session_state.get("periode_pps_df", pd.DataFrame()).copy()
    si_df = st.session_state.get("sales_item_df", pd.DataFrame()).copy()
    sp_df = st.session_state.get("sales_person_df", pd.DataFrame()).copy()
    pps_df_report = st.session_state.get("sales_pps_df", pd.DataFrame()).copy()
    person_df = st.session_state.get("person_df", pd.DataFrame()).copy()

    if (
        not periods_df.empty
        and "period_name" in periods_df.columns
        and "period_id" in periods_df.columns
    ):
        periods_dict = {
            row["period_name"]: row["period_id"] for _, row in periods_df.iterrows()
        }
    else:
        periods_dict = {"Periode Utama": "P01"}

    # =========================================================================
    # FIX BINGKAI EMAS UNTUK SEMUA TOMBOL (DEFAULT & ACTIVE STATE)
    # =========================================================================
    st.markdown(
            """
        <style>
            /* 1. Atur container radio group */
            div[data-testid="stRadio"] > div[role="radiogroup"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: wrap !important;
                gap: 12px !important;
                justify-content: center !important;
                align-items: center !important;
                width: 100% !important;
            }
        
            /* 2. Sembunyikan bulat/bullet radio bawaan Streamlit secara mutlak */
            div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child,
            div[data-testid="stRadio"] [data-baseweb="radio"] > div:first-child,
            div[data-testid="stRadio"] input[type="radio"] {
                display: none !important;
                width: 0 !important;
                height: 0 !important;
            }
        
            /* 3. BINGKAI EMAS DASAR (Berlaku untuk SEMUA tombol, baik diklik maupun TIDAK) */
            div[data-testid="stRadio"] div[role="radiogroup"] > label,
            div[data-testid="stRadio"] [data-baseweb="radio"] {
                background: linear-gradient(180deg, #2a1a0c 0%, #170d05 100%) !important;
                border: 2px solid #b8860b !important; /* Border emas standar */
                box-shadow: 0 0 4px rgba(184, 134, 11, 0.3), inset 0 0 4px rgba(0, 0, 0, 0.8) !important;
                border-radius: 8px !important;
                padding: 10px 16px !important;
                margin: 4px !important;
                min-width: 130px !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                text-align: center !important;
                cursor: pointer !important;
                transition: all 0.25s ease-in-out !important;
            }
        
            /* 4. Format Teks Default */
            div[data-testid="stRadio"] label *,
            div[data-testid="stRadio"] [data-baseweb="radio"] * {
                color: #d4af37 !important; /* Warna teks emas redup */
                font-family: 'Georgia', serif !important;
                font-weight: bold !important;
                font-size: 11px !important;
                letter-spacing: 0.5px !important;
                text-transform: uppercase !important;
                background: transparent !important;
            }
        
            /* 5. EFEK HOVER (Saat Disentuh/Kursor Di Atas Tombol) */
            div[data-testid="stRadio"] label:hover,
            div[data-testid="stRadio"] [data-baseweb="radio"]:hover {
                border-color: #ffe57f !important;
                background: linear-gradient(180deg, #422913 0%, #291607 100%) !important;
                box-shadow: 0 0 10px rgba(255, 229, 127, 0.5) !important;
                transform: translateY(-2px) !important;
            }
        
            /* 6. EFEK TOMBOL YANG SEDANG DIKLIK / TERPILIH (NYALA BERCAHAYA) */
            div[data-testid="stRadio"] label:has(input:checked),
            div[data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked),
            div[data-testid="stRadio"] [aria-checked="true"] {
                background: linear-gradient(180deg, #6e4218 0%, #3d230b 100%) !important;
                border: 2px solid #fff3b0 !important; /* Border emas terang */
                box-shadow: 0 0 15px rgba(212, 175, 55, 0.9), inset 0 0 8px rgba(255, 243, 176, 0.5) !important;
            }
        
            div[data-testid="stRadio"] label:has(input:checked) *,
            div[data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked) *,
            div[data-testid="stRadio"] [aria-checked="true"] * {
                color: #ffffff !important; /* Teks putih terang saat aktif */
                text-shadow: 0 0 6px rgba(255, 243, 176, 0.9) !important;
            }
        </style>
        """,
            unsafe_allow_html=True,
    )

    active_sub_tab = st.radio(
        "",
        ["⚡ Multi Input Sales", "🎯 Input Sales PPS", "📱 Salin Format WA"],
        horizontal=True,
        label_visibility="collapsed",
        key="custom_sub_tabs",
    )
    
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)


    # --- Helper Functions & Dialogs ---
    def get_period_date_bounds(p_id):
        if not periods_df.empty and "period_id" in periods_df.columns:
            p_match = periods_df[periods_df["period_id"] == p_id]
            if (
                not p_match.empty
                and "start_date" in p_match.columns
                and "end_date" in p_match.columns
            ):
                try:
                    p_start = pd.to_datetime(p_match.iloc[0]["start_date"]).date()
                    p_end = pd.to_datetime(p_match.iloc[0]["end_date"]).date()
                    if p_start > p_end:
                        p_start, p_end = p_end, p_start
                    return p_start, p_end
                except Exception:
                    pass
        today = datetime.now().date()
        return today.replace(day=1), today


    @st.dialog("🎉 Input Data Berhasil!")
    def show_success_popup(inserted_count, person_name, date_str):
        st.success(
            f"**{inserted_count} Item Penjualan** berhasil disimpan secara permanen"
            " ke database!"
        )
        st.markdown(f"""
            * **Personil:** `{person_name}`
            * **Tanggal:** `{date_str}`
            * **Status:** Synchronized to Google Sheets ✅
            """)
        if st.button("👍 Mantap, Tutup", use_container_width=True):
            st.rerun()

    # =========================================================================
    # SUB TAB 1: MULTI INPUT SALES PERSONIL
    # =========================================================================
    if active_sub_tab == "⚡ Multi Input Sales":
        st.markdown(
            "<h4 style='color: #00ff88; margin-top: 15px;'>⚡ Multi Input Sales"
            " Personil</h4>",
            unsafe_allow_html=True,
        )

        if is_visitor:
            st.error(
                "🔒 **Akses Ditolak!** Akun **Visitor** hanya memiliki akses membaca"
                " data (read-only)."
            )
        else:
            today_date = waktu_wib.date()

            # -----------------------------------------------------------------
            # 1. TAMPILKAN SELEKSI BULAN PERIODE
            # -----------------------------------------------------------------
            nama_bulan_dict = {
                1: "Januari",
                2: "Februari",
                3: "Maret",
                4: "April",
                5: "Mei",
                6: "Juni",
                7: "Juli",
                8: "Agustus",
                9: "September",
                10: "Oktober",
                11: "November",
                12: "Desember",
            }

            default_month_num = today_date.month
            month_options = list(nama_bulan_dict.values())
            default_month_idx = default_month_num - 1

            selected_bulan_name = st.selectbox(
                "🗓️ Pilih Bulan Periode",
                options=month_options,
                index=default_month_idx,
                key="multi_select_month",
            )

            selected_month_num = [
                k for k, v in nama_bulan_dict.items() if v == selected_bulan_name
            ][0]

            # -----------------------------------------------------------------
            # 2. AMBIL PERIODE MURNI DARI TABEL PERIODE (periods_df)
            # -----------------------------------------------------------------
            tab1_periods_dict = {}
            default_period_key = None

            if not periods_df.empty and all(
                col in periods_df.columns
                for col in ["period_id", "period_name", "start_date", "end_date"]
            ):
                for _, row in periods_df.iterrows():
                    p_id = (
                        str(row["period_id"])
                        .replace(".0", "")
                        .strip()
                    )
                    p_name = str(row["period_name"])

                    try:
                        p_start = pd.to_datetime(
                            row["start_date"], errors="coerce"
                        ).date()
                        p_end = pd.to_datetime(
                            row["end_date"], errors="coerce"
                        ).date()

                        if pd.isna(p_start) or pd.isna(p_end):
                            continue

                        if p_start > p_end:
                            p_start, p_end = p_end, p_start

                        # Filter periode yang start_date-nya berada di bulan terpilih
                        if p_start.month == selected_month_num:
                            tab1_periods_dict[p_name] = p_id

                            # Set default pilihan jika hari ini masuk dalam rentang periode ini
                            if (
                                p_start <= today_date <= p_end
                                and default_period_key is None
                            ):
                                default_period_key = p_name
                    except Exception:
                        continue

            # Render Dropdown Periode
            if not tab1_periods_dict:
                st.warning(
                    f"⚠️ Tidak ada periode transaksi yang terdaftar pada tabel"
                    f" **PERIODE** di bulan **{selected_bulan_name}**."
                )
                m_period_name = None
                m_p_id = None
            else:
                period_keys = list(tab1_periods_dict.keys())
                default_index = 0
                if default_period_key and default_period_key in period_keys:
                    default_index = period_keys.index(default_period_key)

                m_period_name = st.selectbox(
                    f"📌 Pilih Periode Transaksi ({selected_bulan_name})",
                    period_keys,
                    index=default_index,
                    key="multi_period",
                )
                m_p_id = tab1_periods_dict[m_period_name]

            # -----------------------------------------------------------------
            # 3. BATAS TANGGAL TRANSAKSI SESUAI RENTANG PERIODE
            # -----------------------------------------------------------------
            if m_p_id:
                try:
                    p_start, p_end = get_period_date_bounds(m_p_id)
                    if isinstance(p_start, (pd.Timestamp, datetime)):
                        p_start = p_start.date()
                    if isinstance(p_end, (pd.Timestamp, datetime)):
                        p_end = p_end.date()
                except Exception:
                    p_start = today_date - timedelta(days=30)
                    p_end = today_date + timedelta(days=30)

                default_val_m = (
                    p_start
                    if today_date < p_start
                    else (p_end if today_date > p_end else today_date)
                )

                m_date = st.date_input(
                    f"📅 Tanggal Transaksi (Batas Periode:"
                    f" {p_start.strftime('%d/%m/%Y')} s/d"
                    f" {p_end.strftime('%d/%m/%Y')})",
                    value=default_val_m,
                    min_value=p_start,
                    max_value=p_end,
                    key="multi_date",
                )

                # -------------------------------------------------------------
                # 4. PILIH PERSONIL / USER (ROLE-BASED)
                # -------------------------------------------------------------
                all_personnel = (
                    sorted(person_df["person_name"].dropna().unique().tolist())
                    if not person_df.empty and "person_name" in person_df.columns
                    else [current_user]
                )

                if is_admin:
                    m_person = st.selectbox(
                        "👤 Pilih Nama Personil / Staf",
                        options=all_personnel,
                        key="multi_person",
                    )
                else:
                    if current_user in all_personnel:
                        user_idx = all_personnel.index(current_user)
                    else:
                        all_personnel.append(current_user)
                        user_idx = len(all_personnel) - 1

                    m_person = st.selectbox(
                        "👤 Nama Personil / Staf (Penginputan Dikunci)",
                        options=all_personnel,
                        index=user_idx,
                        disabled=True,
                        key="multi_person_disabled",
                    )

                # -------------------------------------------------------------
                # 5. AMBIL DAFTAR ITEM MURNI DARI TABEL SALES_ITEM (sales_item_df)
                # -------------------------------------------------------------
                sales_item_ref = st.session_state.get(
                    "sales_item_df", pd.DataFrame()
                )

                cleaned_sales_period = (
                    sales_item_ref["period_id"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                    if not sales_item_ref.empty
                    and "period_id" in sales_item_ref.columns
                    else pd.Series()
                )
                cleaned_target_p_id = re.sub(r"\.0$", "", str(m_p_id)).strip()

                filtered_sales_item_df = (
                    sales_item_ref[cleaned_sales_period == cleaned_target_p_id]
                    if not sales_item_ref.empty
                    else pd.DataFrame()
                )

                items_list = []
                if (
                    not filtered_sales_item_df.empty
                    and "item_id" in filtered_sales_item_df.columns
                    and "item_name" in filtered_sales_item_df.columns
                ):
                    items_list = (
                        filtered_sales_item_df[["item_id", "item_name"]]
                        .drop_duplicates()
                        .to_dict("records")
                    )

                # -------------------------------------------------------------
                # 6. FORM INPUT QTY PENJUALAN PRODUK
                # -------------------------------------------------------------
                if not items_list:
                    st.warning(
                        f"⚠️ Tidak ada daftar item produk pada **SALES_ITEM** yang"
                        f" terdaftar untuk periode **{m_period_name}** (ID:"
                        f" {m_p_id})."
                    )
                else:
                    st.markdown("---")
                    with st.form(key=f"form_multi_input_{m_p_id}"):
                        st.markdown(
                            "##### 📦 Masukkan Jumlah Qty Penjualan Masing-Masing"
                            " Produk:"
                        )
                        multi_input_values = {}
                        col_m1, col_m2 = st.columns(2)

                        for idx, item in enumerate(items_list):
                            target_col = col_m1 if (idx % 2 == 0) else col_m2
                            item_id_str = str(item["item_id"])
                            item_name_str = str(item["item_name"])

                            with target_col:
                                qty_val = st.number_input(
                                    f"📌 {item_name_str}",
                                    min_value=0,
                                    step=1,
                                    value=0,
                                    key=f"multi_qty_{m_p_id}_{item_id_str}",
                                )
                                multi_input_values[item_id_str] = {
                                    "item_name": item_name_str,
                                    "qty": qty_val,
                                }

                        st.markdown("---")
                        btn_save = st.form_submit_button(
                            "💾 Simpan Semua Data Penjualan Multi-Input",
                            use_container_width=True,
                        )

                    # ---------------------------------------------------------
                    # 7. SIMPAN DATA TRANSAKSI
                    # ---------------------------------------------------------
                    if btn_save:
                        p_match = (
                            person_df[person_df["person_name"] == m_person]
                            if not person_df.empty
                            else pd.DataFrame()
                        )
                        person_id_val = (
                            str(p_match.iloc[0]["person_id"])
                            if not p_match.empty and "person_id" in p_match.columns
                            else "P999"
                        )

                        existing_person_df = st.session_state.get(
                            "sales_person_df", pd.DataFrame()
                        )
                        current_max_id = 0
                        if (
                            not existing_person_df.empty
                            and "record_id" in existing_person_df.columns
                        ):
                            numeric_ids = (
                                existing_person_df["record_id"]
                                .astype(str)
                                .str.extract(r"(\d+)")[0]
                                .dropna()
                            )
                            if not numeric_ids.empty:
                                current_max_id = numeric_ids.astype(int).max()

                        new_rows, inserted_count = [], 0
                        for item_id, item_data in multi_input_values.items():
                            input_qty = int(item_data["qty"])
                            if input_qty > 0:
                                current_max_id += 1
                                new_rows.append(
                                    {
                                        "record_id": f"SP{current_max_id:05d}",
                                        "period_id": str(m_p_id),
                                        "item_id": str(item_id),
                                        "item_name": str(item_data["item_name"]),
                                        "person_id": str(person_id_val),
                                        "person_name": str(m_person),
                                        "actual_qty": input_qty,
                                        "updated_at": str(m_date),
                                    }
                                )
                                inserted_count += 1

                                # Akumulasi ke sales_item_df
                                if "sales_item_df" in st.session_state:
                                    s_item_df = st.session_state.sales_item_df
                                    cond = (
                                        s_item_df["period_id"]
                                        .astype(str)
                                        .str.replace(r"\.0$", "", regex=True)
                                        .str.strip()
                                        == str(m_p_id).strip()
                                    ) & (
                                        s_item_df["item_id"]
                                        .astype(str)
                                        .str.replace(r"\.0$", "", regex=True)
                                        .str.strip()
                                        == str(item_id).strip()
                                    )

                                    if cond.any():
                                        s_item_df.loc[cond, "actual_qty"] = (
                                            pd.to_numeric(
                                                s_item_df.loc[cond, "actual_qty"],
                                                errors="coerce",
                                            ).fillna(0)
                                            + input_qty
                                        )
                                        if "updated_at" in s_item_df.columns:
                                            s_item_df.loc[
                                                cond, "updated_at"
                                            ] = str(m_date)
                                    else:
                                        new_item_row = {
                                            "period_id": str(m_p_id),
                                            "item_id": str(item_id),
                                            "item_name": str(
                                                item_data["item_name"]
                                            ),
                                            "actual_qty": input_qty,
                                            "updated_at": str(m_date),
                                        }
                                        st.session_state.sales_item_df = pd.concat(
                                            [
                                                s_item_df,
                                                pd.DataFrame([new_item_row]),
                                            ],
                                            ignore_index=True,
                                        )

                        if inserted_count > 0:
                            try:
                                with st.spinner(
                                    "⏳ Menyimpan & Menjumlahkan Data Sales..."
                                ):
                                    new_person_df = pd.DataFrame(new_rows)
                                    if "sales_person_df" not in st.session_state:
                                        st.session_state.sales_person_df = (
                                            pd.DataFrame()
                                        )

                                    st.session_state.sales_person_df = pd.concat(
                                        [
                                            st.session_state.sales_person_df,
                                            new_person_df,
                                        ],
                                        ignore_index=True,
                                    )

                                    if (
                                        "sync_store_sales_from_personnel"
                                        in globals()
                                    ):
                                        sync_store_sales_from_personnel()

                                    save_database(
                                        st.session_state.sales_item_df,
                                        st.session_state.sales_person_df,
                                        st.session_state.sales_pps_df,
                                        st.session_state.sales_store_df,
                                    )

                                    # --- BACKUP OTOMATIS BERJALAN DI SINI ---
                                    backup_to_gsheets()

                                show_success_popup(
                                    inserted_count,
                                    m_person,
                                    m_date.strftime("%d/%m/%Y"),
                                )
                            except Exception as e:
                                st.error(
                                    f"❌ Terjadi kesalahan penyimpanan: {str(e)}"
                                )
                        else:
                            st.warning(
                                "⚠️ Tidak ada Qty produk yang diisi (semua bernilai"
                                " 0)."
                            )
            
    # =========================================================================
    # SUB TAB 2: INPUT SALES PPS (LOGIKA TANGGAL FIX)
    # =========================================================================
    elif active_sub_tab == "🎯 Input Sales PPS":
        st.markdown(
            "<h4 style='color: #00ff88; margin-top: 15px;'>🎯 Form Input Penjualan &"
            " Kinerja PPS</h4>",
            unsafe_allow_html=True,
        )

        if is_visitor:
            st.error(
                "🔒 **Akses Ditolak!** Akun **Visitor** hanya memiliki akses membaca"
                " data (read-only)."
            )
        else:

            @st.dialog("🎉 Data PPS Berhasil Disimpan!")
            def show_success_pps_dialog(
                staff_val, kasir_val, date_str, syarat_pwp_val, redeem_pwp_val
            ):
                st.success(
                    "✅ **Data Sales PPS** berhasil disimpan dan diakumulasikan ke"
                    " tabel **PERIODE_PPS**!"
                )
                st.markdown(f"""
                    * **Staf / Personil:** `{staff_val}`
                    * **Kasir:** `{kasir_val}`
                    * **Tanggal:** `{date_str}`
                    * **Syarat PWP:** `{syarat_pwp_val}` | **Redeem PWP:** `{redeem_pwp_val}`
                    * **Status:** Synchronized to SALES_PPS & PERIODE_PPS ✅
                    """)
                if st.button(
                    "👍 Oke, Lanjutkan / Tutup",
                    use_container_width=True,
                    key="btn_close_pps_dialog",
                ):
                    st.rerun()

            # Ambil daftar personil
            all_personnel = (
                sorted(person_df["person_name"].dropna().unique().tolist())
                if not person_df.empty and "person_name" in person_df.columns
                else [current_user]
            )

            today_date = waktu_wib.date()

            # --- FIX: AMBIL BATAS TANGGAL DARI PERIODE_PPS ---
            pps_master_df = st.session_state.get("periods_pps_df", pd.DataFrame())

            min_promo_date = today_date - timedelta(days=30)
            max_promo_date = today_date + timedelta(days=30)

            if not pps_master_df.empty and all(
                col in pps_master_df.columns for col in ["start_date", "end_date"]
            ):
                valid_starts = pd.to_datetime(
                    pps_master_df["start_date"], errors="coerce"
                ).dropna()
                valid_ends = pd.to_datetime(
                    pps_master_df["end_date"], errors="coerce"
                ).dropna()

                if not valid_starts.empty and not valid_ends.empty:
                    min_promo_date = valid_starts.min().date()
                    max_promo_date = valid_ends.max().date()

            # Form Input Transaksi Harian
            with st.form(key="form_input_pps_dynamic"):
                st.markdown(
                    "##### 📋 Masukkan Detail Transaksi & Kinerja Program PPS:"
                )
                col_p1, col_p2 = st.columns(2)

                with col_p1:
                    shift_personil = st.selectbox(
                        "Shift Personil",
                        ["Shift 1", "Shift 2", "Shift 3", "Full Shift"],
                        key="pps_shift_dyn",
                    )

                    # Diubah agar semua user bisa memilih/mengubah nama staf
                    user_idx = (
                        all_personnel.index(current_user)
                        if current_user in all_personnel
                        else 0
                    )
                    staff_name = st.selectbox(
                        "Nama Staf / Personil",
                        all_personnel,
                        index=user_idx,
                        key="pps_staff_dyn",
                    )

                with col_p2:
                    kasir_name = st.selectbox(
                        "Nama Kasir", all_personnel, key="pps_kasir_dyn"
                    )

                    # Pastikan default_date tidak melebih batas min/max
                    default_date_pps = (
                        min_promo_date
                        if today_date < min_promo_date
                        else (
                            max_promo_date
                            if today_date > max_promo_date
                            else today_date
                        )
                    )

                    tanggal_pps = st.date_input(
                        f"📅 Tanggal Input PPS (Rentang Promo:"
                        f" {min_promo_date.strftime('%d/%m')} -"
                        f" {max_promo_date.strftime('%d/%m/%Y')})",
                        value=default_date_pps,
                        min_value=min_promo_date,
                        max_value=max_promo_date,
                        key="pps_date_dyn",
                    )

                st.markdown("---")
                st.markdown("##### 🛒 Detail Indikator Penjualan PPS:")

                col_q1, col_q2, col_q3 = st.columns(3)
                with col_q1:
                    syarat_pwp = st.number_input(
                        "Syarat PWP",
                        min_value=0,
                        step=1,
                        value=0,
                        key="pps_syarat_pwp_dyn",
                    )
                    redeem_pwp = st.number_input(
                        "Redeem PWP",
                        min_value=0,
                        step=1,
                        value=0,
                        key="pps_redeem_pwp_dyn",
                    )
                with col_q2:
                    qty_pwp = st.number_input(
                        "Qty PWP",
                        min_value=0,
                        step=1,
                        value=0,
                        key="pps_qty_pwp_dyn",
                    )
                    qty_sg = st.number_input(
                        "Qty SG (Serba Gratis)",
                        min_value=0,
                        step=1,
                        value=0,
                        key="pps_qty_sg_dyn",
                    )
                with col_q3:
                    syarat_sueger = st.number_input(
                        "Syarat Sueger",
                        min_value=0,
                        step=1,
                        value=0,
                        key="pps_syarat_sueger_dyn",
                    )
                    redeem_sueger = st.number_input(
                        "Redeem Sueger",
                        min_value=0,
                        step=1,
                        value=0,
                        key="pps_redeem_sueger_dyn",
                    )

                cemilan_ceban = st.number_input(
                    "Cemilan Ceban",
                    min_value=0,
                    step=1,
                    value=0,
                    key="pps_cemilan_ceban_dyn",
                )

                st.markdown("---")
                btn_save_pps = st.form_submit_button(
                    "💾 Simpan & Sinkronkan Data PPS", use_container_width=True
                )

            # Eksekusi Penyimpanan
            if btn_save_pps:
                existing_pps_df = st.session_state.get(
                    "sales_pps_df", pd.DataFrame()
                )
                current_max_pps_id = 0
                if (
                    not existing_pps_df.empty
                    and "record_id" in existing_pps_df.columns
                ):
                    numeric_ids = (
                        existing_pps_df["record_id"]
                        .astype(str)
                        .str.extract(r"(\d+)")[0]
                        .dropna()
                    )
                    if not numeric_ids.empty:
                        current_max_pps_id = numeric_ids.astype(int).max()

                current_max_pps_id += 1

                p_match = (
                    person_df[person_df["person_name"] == staff_name]
                    if not person_df.empty
                    else pd.DataFrame()
                )
                person_id_val = (
                    str(p_match.iloc[0]["person_id"])
                    if not p_match.empty and "person_id" in p_match.columns
                    else "PRS999"
                )

                new_pps_record = {
                    "record_id": f"PPS{current_max_pps_id:05d}",
                    "period_id": "PPS_MULTI",
                    "shift_personil": str(shift_personil),
                    "staff_name": str(staff_name),
                    "person_id": str(person_id_val),
                    "kasir_name": str(kasir_name),
                    "syarat_pwp": int(syarat_pwp),
                    "redeem_pwp": int(redeem_pwp),
                    "qty_pwp": int(qty_pwp),
                    "qty_sg": int(qty_sg),
                    "syarat_sueger": int(syarat_sueger),
                    "redeem_sueger": int(redeem_sueger),
                    "cemilan_ceban": int(cemilan_ceban),
                    "updated_at": str(tanggal_pps),
                }

                try:
                    with st.spinner("⏳ Memproses & Menyingkronkan Data..."):
                        new_pps_df = pd.DataFrame([new_pps_record])
                        if "sales_pps_df" not in st.session_state:
                            st.session_state.sales_pps_df = pd.DataFrame()

                        st.session_state.sales_pps_df = pd.concat(
                            [st.session_state.sales_pps_df, new_pps_df],
                            ignore_index=True,
                        )

                        # Jalankan sinkronisasi
                        sync_periode_pps_from_sales()

                        # Simpan ke Google Sheets
                        save_database(
                            st.session_state.sales_item_df,
                            st.session_state.sales_person_df,
                            st.session_state.sales_pps_df,
                            st.session_state.sales_store_df,
                        )

                        # --- BACKUP OTOMATIS BERJALAN DI SINI ---
                        backup_to_gsheets()

                    show_success_pps_dialog(
                        staff_name,
                        kasir_name,
                        tanggal_pps.strftime("%d/%m/%Y"),
                        syarat_pwp,
                        redeem_pwp,
                    )
                except Exception as e:
                    st.error(f"❌ Gagal menyimpan data SALES_PPS: {str(e)}")

    # =========================================================================
    # SUB TAB 3: SALIN FORMAT WHATSAPP
    # =========================================================================
    elif active_sub_tab == "📱 Salin Format WA":
        st.markdown(
            "<h4 style='color: #00ff88; margin-top: 15px;'>📱 Generator Format"
            " Laporan WhatsApp</h4>",
            unsafe_allow_html=True,
        )

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            wa_format_type = st.radio(
                "Pilih Format Laporan:",
                ["📋 Format Laporan PPS", "🥤 Format Laporan Sueger"],
                key="wa_format_selector",
            )
        with col_f2:
            selected_wa_date = st.date_input(
                "Pilih Tanggal Laporan",
                value=waktu_wib.date(),
                key="wa_report_date",
            )

        date_str_formatted = selected_wa_date.strftime("%d-%m-%Y")

        if "sueger_generated" not in st.session_state:
            st.session_state["sueger_generated"] = False

        def reset_sueger_state():
            st.session_state["sueger_generated"] = False

        available_kasir = (
            pps_df_report["kasir_name"].dropna().unique().tolist()
            if not pps_df_report.empty and "kasir_name" in pps_df_report.columns
            else (
                person_df["person_name"].dropna().unique().tolist()
                if not person_df.empty
                else ["TIKA"]
            )
        )

        if wa_format_type == "🥤 Format Laporan Sueger":
            selected_kasir = st.selectbox(
                "👤 Filter Berdasarkan Nama Kasir:",
                available_kasir,
                key="wa_filter_kasir_sueger",
                on_change=reset_sueger_state,
            )
        else:
            selected_kasir = None

        pps_filtered_harian = (
            pps_df_report[
                pd.to_datetime(
                    pps_df_report["updated_at"], errors="coerce"
                ).dt.date
                == selected_wa_date
            ]
            if not pps_df_report.empty and "updated_at" in pps_df_report.columns
            else pd.DataFrame()
        )

        if wa_format_type == "📋 Format Laporan PPS":
            st.markdown(
                "<h5 style='color: #38bdf8;'>✨ Preview Format Laporan PPS (Harian"
                " per Shift)</h5>",
                unsafe_allow_html=True,
            )

            # 🚀 TOMBOL PEMICU UTAMA: Dirombak total agar menyinkronkan KEDUA tabel (PSM & PPS) sekaligus
            if st.button("🔮 GENERATE LAPORAN HARIAN PPS", use_container_width=True, key="btn_generate_pps_final", type="primary"):
                
                with st.spinner("🧙‍♂️ Ritual pembersihan cache massal... Menarik data segar dari Google Sheets"):
                    # 1. Hancurkan benteng pertahanan cache ttl=60 Google Sheets Streamlit
                    st.cache_data.clear()
                    
                    # 2. Ambil paket data paling murni dan paling baru langsung dari awan Google Sheets
                    (p_df, p_pps_df, p_store_df, i_df, pers_df, si_df, sp_df, s_pps_df, s_store_df) = load_database()
                    
                    # 3. KUNCI UTAMA: Suntikkan paksa data segar ke memori session_state global
                    # Agar variabel pps_filtered_harian di bawah ikut berubah kosong secara detik itu juga!
                    st.session_state.sales_person_df = sp_df
                    st.session_state.sales_pps_df = s_pps_df
                    st.session_state.sales_item_df = si_df
                    st.session_state.sales_store_df = s_store_df
                    
                    # 4. Paksa variabel filter harian PPS Anda membaca ulang baris data yang baru ditarik
                    # (Kita tiru persis rumus filter tanggal harian PPS Anda yang ada di baris atas script Anda)
                    if not s_pps_df.empty and "updated_at" in s_pps_df.columns:
                        s_pps_df["clean_date"] = pd.to_datetime(s_pps_df["updated_at"], errors="coerce").dt.date
                        # Overwrite variabel filter harian agar langsung sinkron dengan database riil
                        pps_filtered_harian = s_pps_df[s_pps_df["clean_date"] == selected_wa_date]
                    else:
                        pps_filtered_harian = pd.DataFrame()
                        
                st.toast("Semua tabel (PSM & PPS) sukses disinkronkan secara live!", icon="⚡")
                st.rerun() # Memicu render ulang agar teks st.code langsung berubah bersih saat itu juga

            # --- SISA KODE PROSES PEMBACAAN DATA DI BAWAHNYA TETAP SAMA ---
            periode_bulan = selected_wa_date.strftime("%B %Y")
            sp_report_df = st.session_state.get(
                "sales_person_df", pd.DataFrame()
            ).copy()

            if not sp_report_df.empty and "updated_at" in sp_report_df.columns:
                sp_report_df["clean_date"] = pd.to_datetime(
                    sp_report_df["updated_at"], errors="coerce"
                ).dt.date
                psm_filtered = sp_report_df[
                    sp_report_df["clean_date"] == selected_wa_date
                ]
            else:
                psm_filtered = pd.DataFrame()

            if not psm_filtered.empty and "item_name" in psm_filtered.columns:
                psm_filtered["actual_qty"] = pd.to_numeric(
                    psm_filtered["actual_qty"], errors="coerce"
                ).fillna(0)
                psm_grouped = (
                    psm_filtered.groupby("item_name")["actual_qty"].sum().reset_index()
                )
                psm_grouped = psm_grouped[psm_grouped["actual_qty"] > 0]

                if not psm_grouped.empty:
                    total_qty_psm = int(psm_grouped["actual_qty"].sum())
                    list_psm_text = "".join([
                        f"\t• {r['item_name']} = {int(r['actual_qty'])}\n"
                        for _, r in psm_grouped.iterrows()
                    ])
                else:
                    list_psm_text = "\t• (Tidak ada penjualan PSM pada tanggal ini)\n"
                    total_qty_psm = 0
            else:
                list_psm_text = "\t• (Tidak ada penjualan PSM pada tanggal ini)\n"
                total_qty_psm = 0

            wa_pps_text = (
                "🌟 *REKAP LAPORAN HARIAN PPS* 🌟\n"
                f"📅 Tanggal: {date_str_formatted}\n"
                f"📦 *Periode*: {periode_bulan}\n\n"
                "📦 *Report PSM*\n"
                "   📌 *List item terjual dan qty jual*\n"
                f"{list_psm_text}"
                "   =============================================\n"
                f"\tTOTAL PENJUALAN : {total_qty_psm}\n\n"
                "🎯 *Detail Kinerja Program (PWP, SG, Ceban)*:\n"
            )

            if not pps_filtered_harian.empty:
                for shift_name, group_df in pps_filtered_harian.groupby(
                    "shift_personil"
                ):
                    kasir_str = " & ".join(
                        group_df["kasir_name"].dropna().unique().tolist()
                    )
                    staff_str = ", ".join(
                        group_df["staff_name"].dropna().unique().tolist()
                    )

                    tot_syarat_pwp = int(group_df["syarat_pwp"].sum())
                    tot_redeem_pwp = int(group_df["redeem_pwp"].sum())
                    tot_qty_pwp = int(group_df["qty_pwp"].sum())
                    tot_qty_sg = int(group_df["qty_sg"].sum())

                    tot_syarat_sueger = int(group_df["syarat_sueger"].sum())
                    tot_redeem_sueger = int(group_df["redeem_sueger"].sum())
                    tot_qty_sueger = int(
                        group_df.get("qty_sueger", group_df["redeem_sueger"]).sum()
                    )

                    sueger_ach_shift = (
                        f"{round((tot_redeem_sueger / tot_syarat_sueger) * 100, 1)}%"
                        if tot_syarat_sueger > 0
                        else ""
                    )
                    tot_ceban = int(group_df["cemilan_ceban"].sum())

                    wa_pps_text += (
                        f"   📌 *{shift_name}* (Staf: {staff_str} | Kasir: {kasir_str})\n"
                        f"      • PWP ➔ Syarat: {tot_syarat_pwp} | Redeem:"
                        f" {tot_redeem_pwp} | Qty: {tot_qty_pwp}\n"
                        f"      • Serba Gratis (SG) ➔ Qty: {tot_qty_sg}\n"
                        f"      • Sueger ➔ Qty: {tot_qty_sueger} | Syarat:"
                        f" {tot_syarat_sueger} | Redeem: {tot_redeem_sueger} | Ach%:"
                        f" {sueger_ach_shift}\n"
                        f"      • Cemilan Ceban ➔ Qty: {tot_ceban}\n\n"
                    )

                sum_syarat_pwp = int(pps_filtered_harian["syarat_pwp"].sum())
                sum_redeem_pwp = int(pps_filtered_harian["redeem_pwp"].sum())
                sum_qty_pwp = int(pps_filtered_harian["qty_pwp"].sum())
                sum_qty_sg = int(pps_filtered_harian["qty_sg"].sum())

                sum_syarat_sueger = int(pps_filtered_harian["syarat_sueger"].sum())
                sum_redeem_sueger = int(pps_filtered_harian["redeem_sueger"].sum())
                sum_qty_sueger = int(
                    pps_filtered_harian.get(
                        "qty_sueger", pps_filtered_harian["redeem_sueger"]
                    ).sum()
                )
                sum_sueger_ach = (
                    f"{round((sum_redeem_sueger / sum_syarat_sueger) * 100, 1)}%"
                    if sum_syarat_sueger > 0
                    else ""
                )
                sum_ceban = int(pps_filtered_harian["cemilan_ceban"].sum())

                wa_pps_text += (
                    "🎯 *SUMMARY PENJUALAN (PWP, SG, Ceban)*\n"
                    f"   📌 *TOTAL PENJUALAN TANGGAL {date_str_formatted}*\n"
                    f"      • PWP ➔ Syarat: {sum_syarat_pwp} | Redeem:"
                    f" {sum_redeem_pwp} | Qty: {sum_qty_pwp}\n"
                    f"      • Serba Gratis (SG) ➔ Qty: {sum_qty_sg}\n"
                    f"      • Sueger ➔ Qty: {sum_qty_sueger} | Syarat:"
                    f" {sum_syarat_sueger} | Redeem: {sum_redeem_sueger} | Ach%:"
                    f" {sum_sueger_ach}\n"
                    f"      • Cemilan Ceban ➔ Qty: {sum_ceban}\n\n"
                )
            else:
                wa_pps_text += (
                    f"   _Belum ada data input PPS untuk tanggal {date_str_formatted}._\n\n"
                )

            wa_pps_text += "✅ *Status: Program PPS Berjalan Lancar & Termonitor*"
            st.code(wa_pps_text, language="markdown")

        elif wa_format_type == "🥤 Format Laporan Sueger":
            st.markdown(
                "<h5 style='color: #38bdf8;'>✨ Generator Laporan Sueger"
                " Perorangan</h5>",
                unsafe_allow_html=True,
            )

            if st.button(
                "🚀 Generate Laporan Sueger",
                on_click=lambda: st.session_state.update({"sueger_generated": True}),
            ):
                st.session_state["sueger_generated"] = True

            if st.session_state.get("sueger_generated") and selected_kasir:
                kode_toko, nama_toko = "C383", "Karang Satria"

                pps_sueger_today_kasir = (
                    pps_df_report[
                        (
                            pd.to_datetime(
                                pps_df_report["updated_at"], errors="coerce"
                            ).dt.date
                            == selected_wa_date
                        )
                        & (
                            pps_df_report["kasir_name"].astype(str).str.lower()
                            == str(selected_kasir).lower()
                        )
                    ]
                    if not pps_df_report.empty and "updated_at" in pps_df_report.columns
                    else pd.DataFrame()
                )

                if not pps_sueger_today_kasir.empty:
                    syarat_hari_ini = int(pps_sueger_today_kasir["syarat_sueger"].sum())
                    redeem_hari_ini = int(pps_sueger_today_kasir["redeem_sueger"].sum())
                    ach_hari_ini = (
                        round((redeem_hari_ini / syarat_hari_ini) * 100, 1)
                        if syarat_hari_ini > 0
                        else 0.0
                    )
                else:
                    syarat_hari_ini, redeem_hari_ini, ach_hari_ini = 0, 0, 0.0

                wa_sueger_text = (
                    f"KODE TOKO: {kode_toko}\n"
                    f"NAMA TOKO: {nama_toko}\n"
                    f"TANGGAL UPDATE: {date_str_formatted}\n"
                    f"NAMA KASIR: *{selected_kasir.upper()}*\n\n"
                    "🥤 *LAPORAN PENJUALAN SUEGER HARI INI* 🥤\n"
                    f"    *Tanggal {date_str_formatted}* (Kasir: {selected_kasir})\n"
                    f"      • Syarat Varian  : {syarat_hari_ini}\n"
                    f"      • Total Redeem   : {redeem_hari_ini}\n"
                    f"      • Pencapaian %   : {ach_hari_ini}%\n\n"
                )

                pps_sueger_monthly_kasir = (
                    pps_df_report[
                        (
                            pd.to_datetime(
                                pps_df_report["updated_at"], errors="coerce"
                            ).dt.month
                            == selected_wa_date.month
                        )
                        & (
                            pd.to_datetime(
                                pps_df_report["updated_at"], errors="coerce"
                            ).dt.year
                            == selected_wa_date.year
                        )
                        & (
                            pd.to_datetime(
                                pps_df_report["updated_at"], errors="coerce"
                            ).dt.date
                            <= selected_wa_date
                        )
                        & (
                            pps_df_report["kasir_name"].astype(str).str.lower()
                            == str(selected_kasir).lower()
                        )
                    ]
                    if not pps_df_report.empty and "updated_at" in pps_df_report.columns
                    else pd.DataFrame()
                )

                wa_sueger_text += (
                    f"🥤 *SUMMARY LAPORAN PENJUALAN SUEGER (KASIR:"
                    f" {selected_kasir.upper()})* 🥤\n"
                    "🔹 TANGGAL / SYARAT / REDEEM / ACHIEVEMENT / KETERANGAN\n"
                )

                if not pps_sueger_monthly_kasir.empty:
                    pps_sueger_monthly_kasir["tgl_dt"] = pd.to_datetime(
                        pps_sueger_monthly_kasir["updated_at"]
                    ).dt.date

                    grouped_daily = (
                        pps_sueger_monthly_kasir.groupby("tgl_dt")
                        .agg({"syarat_sueger": "sum", "redeem_sueger": "sum"})
                        .reset_index()
                        .sort_values("tgl_dt")
                    )

                    for idx, row in enumerate(grouped_daily.itertuples(), start=1):
                        tgl_fmt = row.tgl_dt.strftime("%d/%m/%y")
                        syarat, redeem = int(row.syarat_sueger), int(row.redeem_sueger)
                        ach = round((redeem / syarat) * 100, 1) if syarat > 0 else 0.0
                        status_icon = "🟢 LULUS" if ach >= 50.0 else "🔴 TIDAK LULUS"
                        wa_sueger_text += f"{idx}. {tgl_fmt} : {syarat} / {redeem} / {ach}% / {status_icon}\n"

                    tot_syarat = int(grouped_daily["syarat_sueger"].sum())
                    tot_redeem = int(grouped_daily["redeem_sueger"].sum())
                    tot_ach = (
                        round((tot_redeem / tot_syarat) * 100, 1)
                        if tot_syarat > 0
                        else 0.0
                    )
                    tot_status = "🟢 LULUS" if tot_ach >= 50.0 else "🔴 TIDAK LULUS"

                    wa_sueger_text += (
                        "==================\n"
                        "📊 *SUMMARY TOTAL KESELURUHAN*:\n"
                        f"   {tot_syarat} / {tot_redeem} / {tot_ach}% / {tot_status}\n"
                    )
                else:
                    wa_sueger_text += f"_Belum ada catatan transaksi Sueger untuk Kasir {selected_kasir} bulan ini._\n"

                st.code(wa_sueger_text, language="markdown")

# --- EDIT DATA ---
elif selected_tab == "➕ Edit Data (Admin)":
    st.markdown(
        "<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>⚙️"
        " Edit Data Jika Terjadi Kesalahan Input </h2>",
        unsafe_allow_html=True,
    )

    current_user = st.session_state.get("username", "visitor")
    user_lower = str(current_user).lower()
    is_admin = any(
        x in user_lower for x in ["admin", "chief", "cos", "lavitality"]
    )

    if not is_admin:
        st.error(
            "🔒 **Akses Ditolak!** Fitur Master Data & Pengaturan hanya dapat"
            " diakses oleh **Admin / COS**."
        )
        st.stop()

    # --- AMBIL PERIODE & DATA SALES DARI SESSION STATE ---
    periods_df = (
        st.session_state.get("periods_df", pd.DataFrame())
        if not st.session_state.get("periods_df", pd.DataFrame()).empty
        else (
            periode_df
            if "periode_df" in locals() and not periode_df.empty
            else pd.DataFrame()
        )
    )

    sp_df = st.session_state.get("sales_person_df", pd.DataFrame())

    edit_periods_dict = {}
    if not periods_df.empty and all(
        col in periods_df.columns
        for col in ["period_id", "period_name", "start_date", "end_date"]
    ):
        for _, row in periods_df.iterrows():
            edit_periods_dict[str(row["period_name"])] = str(row["period_id"])

    if not edit_periods_dict and not periods_df.empty:
        edit_periods_dict = {
            str(row["period_name"]): str(row["period_id"])
            for _, row in periods_df.iterrows()
        }

    # =========================================================================
    # RENDER CUSTOM RADIO MENU UNTUK SUB-TAB EDIT DATA
    # =========================================================================
    st.markdown("""
    <style>
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] {
            display: flex;
            gap: 10px;
            flex-direction: row;
            align-stretch: stretch;
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label {
            background-color: #1e293b !important;
            border: 1px solid #334155 !important;
            padding: 10px 12px !important;
            border-radius: 10px !important;
            color: #b0c4de !important;
            font-weight: 600 !important;
            font-size: 12px !important;
            white-space: nowrap !important; /* 🔥 Memaksa teks mutlak satu baris */
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            cursor: pointer;
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            min-height: 50px;
            transition: all 0.25s ease-in-out;
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] input[type="radio"] {
            display: none !important;
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
            border-color: #38bdf8 !important;
            background-color: #334155 !important;
            color: #ffffff !important;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
            border: 1px solid #00f0ff !important;
            color: #ffffff !important;
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.5) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    selected_sub_tab = st.radio(
        "Pilih Menu Edit",
        ["✏️ EDIT SALES PERSONIL", "🗑️ HAPUS & RESET"],
        label_visibility="collapsed",
        key="sub_tab_edit_radio"
    )
    
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # SUB TAB 1: EDIT SALES PERSONIL
    if selected_sub_tab == "✏️ EDIT SALES PERSONIL":
        st.markdown(
            "<h4 style='color: #38bdf8;'>✏️ Edit Transaksi Sales (Koreksi"
            " Input)</h4>",
            unsafe_allow_html=True,
        )
        if not edit_periods_dict:
            st.warning("⚠️ Tidak ada data periode yang tersedia di sheet PERIODE.")
        else:
            e_period_name = st.selectbox(
                "Pilih Periode", list(edit_periods_dict.keys()), key="edit_period"
            )
            e_p_id = edit_periods_dict[e_period_name]
            p_start, p_end = get_period_date_bounds(e_p_id)

            sp_sub = (
                sp_df[sp_df["period_id"].astype(str) == str(e_p_id)].copy()
                if not sp_df.empty and "period_id" in sp_df.columns
                else pd.DataFrame()
            )

            if sp_sub.empty:
                st.info("Belum ada data transaksi di periode ini untuk diedit.")
            else:
                e_person = st.selectbox(
                    "Pilih Personil", sp_sub["person_name"].unique(), key="edit_person"
                )
                sp_person_sub = sp_sub[sp_sub["person_name"] == e_person]

                if sp_person_sub.empty:
                    st.info("Tidak ada transaksi untuk personil ini.")
                else:
                    sp_person_sub["label_trx"] = sp_person_sub.apply(
                        lambda r: (
                            f"[{r.get('updated_at', '-')}] {r['item_name']} -"
                            f" {r['actual_qty']} Pcs"
                        ),
                        axis=1,
                    )
                    selected_label = st.selectbox(
                        "Pilih Transaksi yang Akan Diedit",
                        sp_person_sub["label_trx"].tolist(),
                        key="edit_trx_select",
                    )
                    selected_row = sp_person_sub[
                        sp_person_sub["label_trx"] == selected_label
                    ].iloc[0]

                    st.markdown("---")
                    col_e1, col_e2 = st.columns(2)
                    try:
                        raw_date = pd.to_datetime(selected_row.get("updated_at")).date()
                    except Exception:
                        raw_date = p_start

                    safe_e_date = (
                        p_start
                        if raw_date < p_start
                        else (p_end if raw_date > p_end else raw_date)
                    )

                    with col_e1:
                        new_e_date = st.date_input(
                            "Ubah Tanggal Transaksi",
                            value=safe_e_date,
                            min_value=p_start,
                            max_value=p_end,
                            key="edit_date_val",
                        )
                    with col_e2:
                        new_e_qty = st.number_input(
                            "Ubah Jumlah Qty (Pcs)",
                            min_value=0,
                            step=1,
                            value=int(selected_row["actual_qty"]),
                            key="edit_qty_val",
                        )

                    if st.button(
                        "💾 Simpan Perubahan Edit",
                        use_container_width=True,
                        key="btn_save_edit",
                    ):
                        idx = selected_row.name
                        st.session_state.sales_person_df.loc[idx, "actual_qty"] = new_e_qty
                        st.session_state.sales_person_df.loc[idx, "updated_at"] = str(
                            new_e_date
                        )

                        sync_store_sales_from_personnel()
                        save_database(
                            st.session_state.sales_item_df,
                            st.session_state.sales_person_df,
                            st.session_state.sales_pps_df,
                            st.session_state.sales_store_df,
                        )

                        st.toast("🎉 Perubahan data sukses disimpan!", icon="✅")
                        st.success("✅ Perubahan transaksi berhasil disimpan permanen!")
                        time.sleep(1.5)
                        st.rerun()

    # SUB TAB 2: HAPUS & RESET
    elif selected_sub_tab == "🗑️ HAPUS & RESET":
        st.markdown(
            "<h4 style='color: #38bdf8;'>🗑️ Hapus Transaksi / Reset Sales"
            " Personil</h4>",
            unsafe_allow_html=True,
        )
        if not edit_periods_dict:
            st.warning("⚠️ Tidak ada data periode yang tersedia di sheet PERIODE.")
        else:
            d_period_name = st.selectbox(
                "Pilih Periode", list(edit_periods_dict.keys()), key="del_period"
            )
            d_p_id = edit_periods_dict[d_period_name]

            sp_del_sub = (
                sp_df[sp_df["period_id"].astype(str) == str(d_p_id)].copy()
                if not sp_df.empty and "period_id" in sp_df.columns
                else pd.DataFrame()
            )

            if sp_del_sub.empty:
                st.info("Tidak ada transaksi untuk dihapus pada periode ini.")
            else:
                d_person = st.selectbox(
                    "Pilih Personil",
                    sp_del_sub["person_name"].unique(),
                    key="del_person",
                )
                sp_del_person = sp_del_sub[sp_del_sub["person_name"] == d_person]

                mode_hapus = st.radio(
                    "Pilih Opsi Penghapusan:",
                    [
                        "Hapus Item Tertentu Saja",
                        "Reset Seluruh Penjualan Personil Ini",
                    ],
                    key="del_mode",
                )

                if mode_hapus == "Hapus Item Tertentu Saja":
                    d_item_name = st.selectbox(
                        "Pilih Produk yang Ingin Dihapus",
                        sp_del_person["item_name"].unique(),
                        key="del_item_select",
                    )

                    if st.button(
                        f"🗑️ Hapus Transaksi Produk '{d_item_name}'",
                        use_container_width=True,
                        key="btn_del_single",
                    ):
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~(
                                (
                                    st.session_state.sales_person_df["period_id"].astype(
                                        str
                                    )
                                    == str(d_p_id)
                                )
                                & (
                                    st.session_state.sales_person_df["person_name"]
                                    == d_person
                                )
                                & (
                                    st.session_state.sales_person_df["item_name"]
                                    == d_item_name
                                )
                            )
                        ]
                        sync_store_sales_from_personnel()
                        save_database(
                            st.session_state.sales_item_df,
                            st.session_state.sales_person_df,
                            st.session_state.sales_pps_df,
                            st.session_state.sales_store_df,
                        )
                        st.toast("🗑️ Transaksi sukses dihapus!", icon="⚠️")
                        st.warning(
                            f"⚠️ Transaksi '{d_item_name}' untuk {d_person} berhasil dihapus"
                            " permanen!"
                        )
                        time.sleep(1.5)
                        st.rerun()

                else:
                    st.error(
                        f"⚠️ Perhatian: Aksi me-reset akan menghapus SELURUH catatan"
                        f" penjualan {d_person} pada periode ini."
                    )
                    if st.button(
                        f"🚨 Reset Total Sales {d_person} di Periode Ini",
                        use_container_width=True,
                        key="btn_reset_all",
                    ):
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~(
                                (
                                    st.session_state.sales_person_df["period_id"].astype(
                                        str
                                    )
                                    == str(d_p_id)
                                )
                                & (
                                    st.session_state.sales_person_df["person_name"]
                                    == d_person
                                )
                            )
                        ]
                        sync_store_sales_from_personnel()
                        save_database(
                            st.session_state.sales_item_df,
                            st.session_state.sales_person_df,
                            st.session_state.sales_pps_df,
                            st.session_state.sales_store_df,
                        )
                        st.toast("🚨 Seluruh data transaksi di-reset!", icon="⚠️")
                        st.warning(
                            f"⚠️ Seluruh transaksi {d_person} pada periode ini berhasil"
                            " di-reset!"
                        )
                        time.sleep(1.5)
                        st.rerun()
              
# --- TAB MASTER DATA & PENGATURAN ---
elif selected_tab == "⚙️ Pengaturan & Master":
    st.markdown(
        "<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>⚙️ "
        "Master Data & Pengaturan Sistem</h2>",
        unsafe_allow_html=True,
    )

    # --- FUNGSI HELPER SWEETALERT (POP-UP TENGAH LAYAR) ---
    def show_swal(title, text, icon="success"):
        swal_code = f"""
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <script>
            Swal.fire({{
                title: '{title}',
                text: '{text}',
                icon: '{icon}',
                confirmButtonText: 'OK',
                confirmButtonColor: '#0084ff',
                background: '#1e293b',
                color: '#ffffff'
            }});
        </script>
        """
        st.markdown(swal_code, unsafe_allow_html=True)

    current_user = st.session_state.get("username", "visitor")
    user_lower = str(current_user).lower()
    is_admin = any(
        x in user_lower for x in ["admin", "chief", "cos", "lavitality"]
    )

    if not is_admin:
        st.error(
            "🔒 **Akses Ditolak!** Fitur Master Data & Pengaturan hanya dapat"
            " diakses oleh **Admin / COS**."
        )
        st.stop()

    # =========================================================================
    # RENDER CUSTOM RADIO MENU UTAMA (4 PILAR PENGATURAN & MASTER)
    # =========================================================================
    st.markdown("""
    <style>
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] {
            display: flex;
            gap: 8px;
            flex-direction: row;
            align-stretch: stretch;
            flex-wrap: nowrap;
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label {
            background-color: #1e293b !important;
            border: 1px solid #334155 !important;
            padding: 8px 10px !important;
            border-radius: 10px !important;
            color: #b0c4de !important;
            font-weight: 600 !important;
            font-size: 11px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            cursor: pointer;
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            min-height: 48px;
            transition: all 0.25s ease-in-out;
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] input[type="radio"] {
            display: none !important;
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
            border-color: #38bdf8 !important;
            background-color: #334155 !important;
            color: #ffffff !important;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
        }
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
        div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
            border: 1px solid #00f0ff !important;
            color: #ffffff !important;
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.5) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    selected_master_sub = st.radio(
        "Pilih Menu Master Data",
        [
            "🎛️ Pengaturan PSM",
            "👥 Pengaturan Sales",
            "📦 PPS & Sueger",
            "📈 Status & Summary"
        ],
        label_visibility="collapsed",
        key="master_sub_tab_radio"
    )

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # =========================================================================
    # PILAR 1: PENGATURAN PSM
    # =========================================================================
    if selected_master_sub == "🎛️ Pengaturan PSM":
        
        selected_psm_sub = st.radio(
            [
                "➕ Tambah Item & Target",
                "⚙️ Pengaturan & Edit Item",
                "📅 Pengaturan Periode Promosi"
            ],
            key="psm_inner_menu_select"
        )
        
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

        # SUB-TAB 1.1: TAMBAH ITEM
        if selected_psm_sub == "➕ Tambah Item & Target":
            st.markdown(
                "<h4 style='color: #00ff88;'>➕ Tambah Produk & Target Per Periode</h4>",
                unsafe_allow_html=True,
            )
            with st.form("form_add_new_item"):
                col_add1, col_add2 = st.columns(2)
                with col_add1:
                    add_period_name = st.selectbox(
                        "Pilih Periode Alokasi Target",
                        list(periods_dict.keys()),
                        key="add_item_period",
                    )
                    add_period_id = periods_dict[add_period_name]
                    
                    new_item_id = (
                        st.text_input(
                            "ID Item (PLU / Barcode)", placeholder="Contoh: 100234"
                        )
                        .strip()
                        .upper()
                    )
                    new_item_name = st.text_input(
                        "Nama Produk / Item", placeholder="Contoh: MINYAK GORENG 2L"
                    ).strip()
                    
                    new_category = st.text_input("Kategori Produk", placeholder="Contoh: FOOD / NON-FOOD").strip()

                with col_add2:
                    new_target_toko = st.number_input(
                        "Target Toko (Total Pcs)", min_value=0, step=1, value=90
                    )

                    new_target_otomatis = int(math.ceil(new_target_toko / 3)) if new_target_toko > 0 else 0
                    st.markdown(f"📦 **Target Otomatis (Target Toko / 3):** `{new_target_otomatis} Pcs`")
                    new_target_kasir = new_target_otomatis

                btn_submit_add_item = st.form_submit_button(
                    "💾 Simpan Produk & Target Baru", use_container_width=True
                )

                if btn_submit_add_item:
                    if not new_item_id or not new_item_name:
                        st.error("⚠️ ID Item dan Nama Produk wajib diisi!")
                    else:
                        try:
                            if "items_df" not in st.session_state or st.session_state.items_df is None:
                                st.session_state.items_df = pd.DataFrame(columns=["period_id", "item_id", "item_name", "active", "category"])
                            
                            m_items = st.session_state.items_df.copy()
                            
                            for col in ["period_id", "item_id", "item_name", "active", "category"]:
                                if col not in m_items.columns:
                                    m_items[col] = ""

                            mask_master = (m_items["period_id"].astype(str) == str(add_period_id)) & (m_items["item_id"].astype(str) == str(new_item_id))
                            
                            if not mask_master.any():
                                new_m_row = pd.DataFrame([{
                                    "period_id": str(add_period_id),
                                    "item_id": str(new_item_id),
                                    "item_name": str(new_item_name),
                                    "active": "TRUE",
                                    "category": str(new_category)
                                }])
                                st.session_state.items_df = pd.concat([m_items, new_m_row], ignore_index=True)
                                save_master_table("MASTER_ITEM", st.session_state.items_df)

                            if "sales_item_df" not in st.session_state or st.session_state.sales_item_df is None:
                                st.session_state.sales_item_df = pd.DataFrame(columns=[
                                    "period_id", "item_id", "item_name", "target_qty", "target_kasir", "actual_qty"
                                ])

                            s_items = st.session_state.sales_item_df.copy()
                            mask_sales = (
                                (s_items["period_id"].astype(str) == str(add_period_id)) & 
                                (s_items["item_id"].astype(str) == str(new_item_id))
                            )

                            if mask_sales.any():
                                s_items.loc[mask_sales, "item_name"] = str(new_item_name)
                                s_items.loc[mask_sales, "target_qty"] = int(new_target_toko)
                                s_items.loc[mask_sales, "target_kasir"] = int(new_target_kasir)
                            else:
                                new_si_row = pd.DataFrame([{
                                    "period_id": str(add_period_id),
                                    "item_id": str(new_item_id),
                                    "item_name": str(new_item_name),
                                    "target_qty": int(new_target_toko),
                                    "target_kasir": int(new_target_kasir),
                                    "actual_qty": 0,
                                }])
                                s_items = pd.concat([s_items, new_si_row], ignore_index=True)

                            st.session_state.sales_item_df = s_items
                            
                            save_database(
                                st.session_state.sales_item_df,
                                st.session_state.sales_person_df,
                                st.session_state.sales_pps_df,
                                st.session_state.sales_store_df,
                            )

                            show_swal("Berhasil!", f"Produk {new_item_name} berhasil disimpan!", "success")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal menambahkan produk: {e}")

        # SUB-TAB 1.2: PENGATURAN ITEM
        elif selected_psm_sub == "⚙️ Pengaturan & Edit Item":
            st.markdown(
                "<h4 style='color: #38bdf8;'>⚙️ Pengaturan, Edit & Hapus Item</h4>",
                unsafe_allow_html=True,
            )
            si_df = st.session_state.sales_item_df.copy()
            if si_df.empty:
                st.info("Belum ada data item terdaftar.")
            else:
                m_p_name = st.selectbox(
                    "Pilih Periode Item",
                    list(periods_dict.keys()),
                    key="setting_item_period",
                )
                m_p_id = periods_dict[m_p_name]
                si_sub = si_df[si_df["period_id"] == m_p_id]

                if si_sub.empty:
                    st.warning("Tidak ada item di periode ini.")
                else:
                    selected_item_name = st.selectbox(
                        "Pilih Item yang Ingin Diatur",
                        si_sub["item_name"].unique(),
                        key="setting_item_select",
                    )
                    curr_row = si_sub[si_sub["item_name"] == selected_item_name].iloc[0]

                    with st.form("form_edit_item"):
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            edit_item_name = st.text_input(
                                "Nama Item / Produk", value=str(curr_row["item_name"])
                            )
                            target_toko_val = int(curr_row.get("target_qty", 0))
                            edit_target_toko = st.number_input(
                                "Target Toko", min_value=0, step=1, value=target_toko_val
                            )
                        with col_e2:
                            target_kasir_val = int(curr_row.get("target_kasir", 0))
                            edit_target_kasir = st.number_input(
                                "Target Kasir / Staf",
                                min_value=0,
                                step=1,
                                value=target_kasir_val,
                            )
                            edit_period_dest = st.selectbox(
                                "Pindah ke Periode",
                                list(periods_dict.keys()),
                                index=list(periods_dict.keys()).index(m_p_name),
                            )

                        btn_save_item_setting = st.form_submit_button(
                            "💾 Simpan Perubahan Item", use_container_width=True
                        )

                        if btn_save_item_setting:
                            try:
                                target_p_id = periods_dict[edit_period_dest]
                                idx_list = st.session_state.sales_item_df[
                                    (st.session_state.sales_item_df["period_id"] == m_p_id)
                                    & (
                                        st.session_state.sales_item_df["item_id"]
                                        == str(curr_row["item_id"])
                                    )
                                ].index

                                st.session_state.sales_item_df.loc[
                                    idx_list, "item_name"
                                ] = edit_item_name
                                st.session_state.sales_item_df.loc[
                                    idx_list, "target_qty"
                                ] = edit_target_toko
                                st.session_state.sales_item_df.loc[
                                    idx_list, "target_kasir"
                                ] = edit_target_kasir
                                st.session_state.sales_item_df.loc[
                                    idx_list, "period_id"
                                ] = target_p_id

                                sp_idx = st.session_state.sales_person_df[
                                    st.session_state.sales_person_df["item_id"]
                                    == str(curr_row["item_id"])
                                ].index
                                st.session_state.sales_person_df.loc[
                                    sp_idx, "item_name"
                                ] = edit_item_name

                                save_database(
                                    st.session_state.sales_item_df,
                                    st.session_state.sales_person_df,
                                    st.session_state.sales_pps_df,
                                    st.session_state.sales_store_df,
                                )
                                show_swal("Tersimpan!", "Perubahan item berhasil disimpan!", "success")
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Gagal memperbarui item: {e}")

                    st.markdown("---")
                    if st.button(
                        f"🗑️ Hapus Item '{selected_item_name}' dari Periode Ini",
                        use_container_width=True,
                    ):
                        st.session_state.sales_item_df = st.session_state.sales_item_df[
                            ~(
                                (st.session_state.sales_item_df["period_id"] == m_p_id)
                                & (
                                    st.session_state.sales_item_df["item_id"]
                                    == str(curr_row["item_id"])
                                )
                            )
                        ]
                        save_database(
                            st.session_state.sales_item_df, 
                            st.session_state.sales_person_df,
                            st.session_state.sales_pps_df,
                            st.session_state.sales_store_df,
                        )
                        show_swal("Terhapus!", "Item berhasil dihapus dari periode.", "warning")
                        time.sleep(1.5)
                        st.rerun()

        # SUB-TAB 1.3: PENGATURAN PERIODE PSM
        elif selected_psm_sub == "📅 Pengaturan Periode Promosi":
            st.markdown(
                "<h4 style='color: #f59e0b;'>📅 Pengaturan Periode Promosi</h4>",
                unsafe_allow_html=True,
            )
            p_df = st.session_state.periods_df.copy()
            col_p1, col_p2 = st.columns([1, 1.2])

            with col_p1:
                st.markdown("##### ➕ Tambah Periode Baru")
                with st.form("form_add_period"):
                    new_p_id = (
                        st.text_input("ID Periode", placeholder="Contoh: P03")
                        .strip()
                        .upper()
                    )
                    new_p_name = st.text_input(
                        "Nama Periode", placeholder="Contoh: Periode Maret 2026"
                    ).strip()
                    new_p_start = st.date_input(
                        "Tanggal Mulai", value=waktu_wib.date(), key="add_p_start"
                    )
                    new_p_end = st.date_input(
                        "Tanggal Selesai", value=waktu_wib.date(), key="add_p_end"
                    )

                    btn_add_p = st.form_submit_button(
                        "💾 Tambah Periode Baru", use_container_width=True
                    )

                    if btn_add_p:
                        if not new_p_id or not new_p_name:
                            st.error("⚠️ ID dan Nama Periode wajib diisi!")
                        elif new_p_start > new_p_end:
                            st.error("⚠️ Tanggal Mulai tidak boleh melebihi Tanggal Selesai!")
                        else:
                            new_p_row = pd.DataFrame([{
                                "period_id": new_p_id,
                                "period_name": new_p_name,
                                "start_date": str(new_p_start),
                                "end_date": str(new_p_end),
                            }])
                            st.session_state.periods_df = pd.concat(
                                [p_df, new_p_row], ignore_index=True
                            )
                            save_master_table("PERIODE", st.session_state.periods_df)
                            show_swal("Sukses!", f"Periode {new_p_name} berhasil ditambahkan!", "success")
                            time.sleep(1.5)
                            st.rerun()

            with col_p2:
                st.markdown("##### ✏️ Edit & Hapus Periode")
                if not p_df.empty:
                    sel_p_edit = st.selectbox(
                        "Pilih Periode yang Ingin Diubah",
                        p_df["period_name"].tolist(),
                        key="select_p_edit",
                    )
                    p_row_match = p_df[p_df["period_name"] == sel_p_edit].iloc[0]

                    with st.form("form_edit_period"):
                        edit_p_name = st.text_input(
                            "Nama Periode", value=str(p_row_match["period_name"])
                        )
                        try:
                            curr_start_d = pd.to_datetime(p_row_match["start_date"]).date()
                            curr_end_d = pd.to_datetime(p_row_match["end_date"]).date()
                        except Exception:
                            curr_start_d, curr_end_d = (
                                waktu_wib.date(),
                                waktu_wib.date(),
                            )

                        edit_p_start = st.date_input(
                            "Tanggal Mulai", value=curr_start_d, key="edit_p_start"
                        )
                        edit_p_end = st.date_input(
                            "Tanggal Selesai", value=curr_end_d, key="edit_p_end"
                        )

                        btn_save_p_edit = st.form_submit_button(
                            "💾 Update Tanggal & Nama Periode", use_container_width=True
                        )

                        if btn_save_p_edit:
                            idx_p = st.session_state.periods_df[
                                st.session_state.periods_df["period_id"]
                                == str(p_row_match["period_id"])
                            ].index
                            st.session_state.periods_df.loc[idx_p, "period_name"] = edit_p_name
                            st.session_state.periods_df.loc[idx_p, "start_date"] = str(
                                edit_p_start
                            )
                            st.session_state.periods_df.loc[idx_p, "end_date"] = str(edit_p_end)

                            save_master_table("PERIODE", st.session_state.periods_df)
                            show_swal("Diperbarui!", "Periode berhasil diperbarui!", "success")
                            time.sleep(1.5)
                            st.rerun()

    # =========================================================================
    # PILAR 2: PENGATURAN SALES
    # =========================================================================
    elif selected_master_sub == "👥 Pengaturan Sales":
        st.markdown(
            "<h4 style='color: #38bdf8;'>👥 Pengaturan & Manajemen Sales</h4>",
            unsafe_allow_html=True,
        )
        
        sales_sub_menu = st.radio(
            "Sub Menu Sales",
            ["📅 Pengaturan Periode Sales", "📊 Monitoring Sales"],
            horizontal=True,
            key="sales_sub_menu_radio"
        )
        
        if sales_sub_menu == "📅 Pengaturan Periode Sales":
            st.info("ℹ️ Atur target dan jadwal periode khusus untuk tim sales di sini.")
            with st.form("form_setting_sales_period"):
                sales_period_name = st.text_input("Nama Periode Sales", placeholder="Contoh: Sales Q1")
                sales_target_val = st.number_input("Target Keseluruhan Sales", min_value=0, value=500)
                btn_save_sales_p = st.form_submit_button("💾 Simpan Pengaturan Sales", use_container_width=True)
                
                if btn_save_sales_p:
                    show_swal("Berhasil!", "Pengaturan periode sales berhasil disimpan!", "success")
                    time.sleep(1.2)
                    st.rerun()
                    
        elif sales_sub_menu == "📊 Monitoring Sales":
            st.markdown("##### 📈 Monitoring Pencapaian Sales")
            st.write("Tabel atau metrik monitoring pencapaian sales akan ditampilkan di sini.")

   # SUB TAB 4: INPUT & PENGATURAN PERIODE PPS & SUEGER
    elif selected_master_sub == "📦 PPS & Sueger":
        st.markdown(
            "<h4 style='color: #c084fc;'>🎯 Input & Pengaturan Periode PPS &"
            " Sueger</h4>",
            unsafe_allow_html=True,
        )

        if "periode_pps_df" not in st.session_state:
            st.session_state.periode_pps_df = pd.DataFrame(columns=[
                "period_id", "start_date", "end_date", "period_name", "target_total", "status", "actual_qty"
            ])

        # =========================================================================
        # CUSTOM RADIO MENU UNTUK SUB-TAB PPS & SUEGER (UNGU NEON & TEKS CYAN)
        # =========================================================================
        st.markdown("""
        <style>
            div.block-container div[data-testid="stRadio"] div[role="radiogroup"] {
                display: flex;
                gap: 8px;
                flex-direction: row;
                align-stretch: stretch;
                flex-wrap: nowrap;
            }
            div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label {
                background-color: #1e1b4b !important;
                border: 1px solid #4c1d95 !important;
                padding: 8px 10px !important;
                border-radius: 10px !important;
                color: #00f0ff !important;
                font-weight: 600 !important;
                font-size: 11px !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
                cursor: pointer;
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                min-height: 48px;
                transition: all 0.25s ease-in-out;
            }
            div.block-container div[data-testid="stRadio"] div[role="radiogroup"] input[type="radio"] {
                display: none !important;
            }
            div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
                border-color: #00f0ff !important;
                background-color: #312e81 !important;
                box-shadow: 0 0 10px rgba(0, 240, 255, 0.4);
            }
            div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
            div.block-container div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
                background: linear-gradient(135deg, #7e22ce 0%, #581c87 100%) !important;
                border: 1px solid #00f0ff !important;
                color: #00f0ff !important;
                box-shadow: 0 0 15px rgba(126, 34, 206, 0.7), 0 0 5px rgba(0, 240, 255, 0.5) !important;
            }
        </style>
        """, unsafe_allow_html=True)

        selected_pps_sub = st.radio(
            "Pilih Sub Menu PPS & Sueger",
            [
                "➕ Tambah Sueger",
                "➕ Tambah Periode PPS",
                "✏️ Edit & Hapus Program",
                "📊 Monitoring Periode"
            ],
            label_visibility="collapsed",
            key="pps_sueger_sub_tab_radio"
        )

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        if selected_pps_sub == "➕ Tambah Sueger":
            st.markdown("##### 📌 Form Input Program Sueger (Persentase)")
            with st.form("form_add_sueger_pure_only"):
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    sgr_id = st.text_input("ID Periode Sueger", placeholder="Contoh: SGR01").strip().upper()
                    sgr_name = st.text_input("Nama Program Sueger", placeholder="Contoh: SUEGER MARET").strip()
                with col_s2:
                    sgr_start = st.date_input("Tanggal Mulai", value=waktu_wib.date(), key="sgr_start_only")
                    sgr_end = st.date_input("Tanggal Akhir", value=waktu_wib.date(), key="sgr_end_only")

                st.info("ℹ️ Program **Sueger** menggunakan persentase (target_total = 0) dan hanya disimpan ke sheet `PERIODE_PPS`.")

                btn_submit_sgr = st.form_submit_button("💾 Simpan Program Sueger", use_container_width=True)

                if btn_submit_sgr:
                    if not sgr_id or not sgr_name:
                        st.error("⚠️ ID Periode dan Nama Program wajib diisi!")
                    elif sgr_start > sgr_end:
                        st.error("⚠️ Tanggal mulai tidak boleh melebihi tanggal akhir!")
                    else:
                        try:
                            new_sgr_row = pd.DataFrame([{
                                "period_id": sgr_id,
                                "start_date": str(sgr_start),
                                "end_date": str(sgr_end),
                                "period_name": sgr_name,
                                "target_total": 0,
                                "status": "Aktif",
                                "actual_qty": 0
                            }])

                            st.session_state.periode_pps_df = pd.concat(
                                [st.session_state.periode_pps_df, new_sgr_row], ignore_index=True
                            )
                            
                            save_master_table("PERIODE_PPS", st.session_state.periode_pps_df)

                            st.toast("✅ Program Sueger berhasil disimpan ke PERIODE_PPS!", icon="🎉")
                            time.sleep(1.2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal menyimpan program Sueger: {e}")

        elif selected_pps_sub == "➕ Tambah Periode PPS":
            st.markdown(
                "##### 📌 Form Input Periode PPS (Target Fisik & Pembulatan Otomatis)"
            )

            # Menghitung jumlah personil aktif secara dinamis untuk pembagi target
            total_active_personnel = 9
            if "person_df" in st.session_state and not st.session_state.person_df.empty:
                if "person_name" in st.session_state.person_df.columns:
                    count_p = (
                        st.session_state.person_df["person_name"].dropna().nunique()
                    )
                    if count_p > 0:
                        total_active_personnel = count_p

            with st.form("form_add_pps_pure_only"):
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    pps_id = (
                        st.text_input("ID Periode PPS", placeholder="Contoh: PPS01")
                        .strip()
                        .upper()
                    )
                    pps_name = st.text_input(
                        "Nama Periode PPS", placeholder="Contoh: PPS MARET"
                    ).strip()
                    pps_target = st.number_input(
                        "Target Total (Pcs)", min_value=0, step=1, value=180
                    )
                with col_p2:
                    pps_start = st.date_input(
                        "Tanggal Mulai", value=waktu_wib.date(), key="pps_start_only"
                    )
                    pps_end = st.date_input(
                        "Tanggal Akhir", value=waktu_wib.date(), key="pps_end_only"
                    )

                    # Hitung target per personil dengan pembulatan ke atas
                    pps_target_kasir_auto = (
                        int(math.ceil(pps_target / total_active_personnel))
                        if pps_target > 0
                        else 0
                    )
                    st.markdown(
                        f"👤 **Target Otomatis Per Personil (Target Total /"
                        f" {total_active_personnel}):** `{pps_target_kasir_auto} Pcs`"
                    )
                    st.caption(
                        "*(Nilai desimal dibulatkan ke atas secara otomatis dan"
                        " disimpan ke PERIODE_PPS)*"
                    )

                btn_submit_pps_exc = st.form_submit_button(
                    "💾 Simpan Periode PPS", use_container_width=True
                )

                if btn_submit_pps_exc:
                    if not pps_id or not pps_name:
                        st.error("⚠️ ID Periode dan Nama Periode wajib diisi!")
                    elif pps_start > pps_end:
                        st.error("⚠️ Tanggal mulai tidak boleh melebihi tanggal akhir!")
                    else:
                        try:
                            # Menambahkan 'target_personil' ke dalam baris data baru
                            new_pps_row = pd.DataFrame([
                                {
                                    "period_id": pps_id,
                                    "start_date": str(pps_start),
                                    "end_date": str(pps_end),
                                    "period_name": pps_name,
                                    "target_total": int(pps_target),
                                    "target_personil": int(
                                        pps_target_kasir_auto
                                    ),  # <-- DIKIRIM KE SHEET
                                    "status": "Aktif",
                                    "actual_qty": 0,
                                    "syarat_total": 0,
                                    "redeem_total": 0,
                                }
                            ])

                            if "periods_pps_df" not in st.session_state:
                                st.session_state.periods_pps_df = pd.DataFrame()

                            st.session_state.periods_pps_df = pd.concat(
                                [st.session_state.periods_pps_df, new_pps_row],
                                ignore_index=True,
                            )

                            save_master_table(
                                "PERIODE_PPS", st.session_state.periods_pps_df
                            )

                            st.toast(
                                "✅ Periode PPS berhasil disimpan ke PERIODE_PPS!",
                                icon="🎉",
                            )
                            time.sleep(1.2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal menyimpan Periode PPS: {e}")

        elif selected_pps_sub == "✏️ Edit & Hapus Program":
            st.markdown("##### ✏️ Kelola / Edit & Hapus Program PERIODE_PPS")
            edit_df = st.session_state.periode_pps_df.copy()
            
            if edit_df.empty or "period_id" not in edit_df.columns or edit_df["period_id"].dropna().empty:
                st.info("Belum ada data di tabel PERIODE_PPS yang tersimpan untuk diedit.")
            else:
                edit_df["period_id"] = edit_df["period_id"].astype(str).str.strip()
                edit_df["period_name"] = edit_df["period_name"].astype(str).str.strip()
                valid_edit_df = edit_df[edit_df["period_id"] != ""]
                
                if valid_edit_df.empty:
                    st.info("Tidak ada ID Program valid.")
                else:
                    list_options = (valid_edit_df["period_id"] + " - " + valid_edit_df["period_name"]).tolist()
                    
                    if len(list_options) > 0:
                        selected_opt = st.selectbox("Pilih Program untuk Diedit/Dihapus", list_options, key="pure_edit_selectbox_only")
                        selected_id = str(selected_opt).split(" - ")[0].strip() if selected_opt else None

                        if selected_id and selected_id in valid_edit_df["period_id"].values:
                            matched = valid_edit_df[valid_edit_df["period_id"] == selected_id]
                            
                            if not matched.empty:
                                rmatch = matched.iloc[0]

                                with st.form("form_edit_pure_only_prog"):
                                    col_e1, col_e2 = st.columns(2)
                                    with col_e1:
                                        edit_name = st.text_input("Nama Program", value=str(rmatch.get("period_name", "")))
                                        try:
                                            cs = pd.to_datetime(rmatch["start_date"]).date()
                                            ce = pd.to_datetime(rmatch["end_date"]).date()
                                        except Exception:
                                            cs, ce = waktu_wib.date(), waktu_wib.date()

                                        edit_s = st.date_input("Tanggal Mulai", value=cs)
                                    with col_e2:
                                        edit_e = st.date_input("Tanggal Akhir", value=ce)
                                        edit_t = st.number_input("Target Total (Pcs)", min_value=0, step=1, value=int(rmatch.get("target_total", 0)))
                                        
                                        c_status = str(rmatch.get("status", "Aktif"))
                                        idx_s = ["Aktif", "Non-Aktif", "Selesai"].index(c_status) if c_status in ["Aktif", "Non-Aktif", "Selesai"] else 0
                                        edit_st = st.selectbox("Status", ["Aktif", "Non-Aktif", "Selesai"], index=idx_s)

                                    btn_upd = st.form_submit_button("💾 Simpan Perubahan ke PERIODE_PPS", use_container_width=True)

                                    if btn_upd:
                                        try:
                                            idx_t = st.session_state.periode_pps_df[
                                                st.session_state.periode_pps_df["period_id"].astype(str) == str(selected_id)
                                            ].index
                                            
                                            st.session_state.periode_pps_df.loc[idx_t, "period_name"] = edit_name
                                            st.session_state.periode_pps_df.loc[idx_t, "start_date"] = str(edit_s)
                                            st.session_state.periode_pps_df.loc[idx_t, "end_date"] = str(edit_e)
                                            st.session_state.periode_pps_df.loc[idx_t, "target_total"] = int(edit_t)
                                            st.session_state.periode_pps_df.loc[idx_t, "status"] = edit_st

                                            save_master_table("PERIODE_PPS", st.session_state.periode_pps_df)
                                            
                                            st.toast("✅ Perubahan berhasil disimpan ke PERIODE_PPS!", icon="💾")
                                            time.sleep(1.2)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Gagal memperbarui: {e}")

                                st.markdown("---")
                                if st.button(f"🗑️ Hapus Program ID: {selected_id}", use_container_width=True, key="pure_btn_del_only"):
                                    st.session_state.periode_pps_df = st.session_state.periode_pps_df[
                                        st.session_state.periode_pps_df["period_id"].astype(str) != str(selected_id)
                                    ]
                                    save_master_table("PERIODE_PPS", st.session_state.periode_pps_df)
                                    
                                    st.toast("⚠️ Program berhasil dihapus dari PERIODE_PPS.", icon="🗑️")
                                    time.sleep(1.2)
                                    st.rerun()

        elif selected_pps_sub == "📊 Monitoring Periode":
            st.markdown("##### 📊 Monitoring Data PERIODE_PPS")
            if not st.session_state.periode_pps_df.empty:
                st.dataframe(st.session_state.periode_pps_df, use_container_width=True)
            else:
                st.info("Belum ada data periode yang tercatat di tabel `PERIODE_PPS`.")

    # --- SUB TAB 5: GENERATOR REPORT SUMMARY WHATSAPP (PERBAIKAN LOGIKA AKURAT) ---
    elif selected_master_sub == "📈 Status & Summary":
        st.markdown(
            "<h4 style='color: #00ff88;'>📊 Status Database & Generator Report WhatsApp</h4>",
            unsafe_allow_html=True,
        )

        # 1. Metrik Utama Sistem
        c_s1, c_s2, c_s3 = st.columns(3)
        with c_s1:
            st.metric("🔗 Koneksi Database", "Terhubung (GSheets)")
        with c_s2:
            st.metric(
                "📦 Total Master Item",
                f"{len(st.session_state.get('items_df', []))} Item",
            )
        with c_s3:
            st.metric(
                "👥 Total Personil",
                f"{len(st.session_state.get('person_df', []))} Staf",
            )

        st.markdown("---")

        # 2. Status Detail & Backup
        st.subheader("📦 Center Backup Database")
        col_bk1, col_bk2 = st.columns(2)
        with col_bk1:
            st.markdown("##### ☁️ Backup Otomatis Google Sheets")
            if st.button(
                "⚡ Jalankan Backup Otomatis Sekarang", use_container_width=True
            ):
                st.success("✅ Backup ke tab `_BACKUP` berhasil!")

        with col_bk2:
            st.markdown("##### 📥 Backup Manual File (.xlsx)")
            try:
                output_backup = io.BytesIO()
                with pd.ExcelWriter(
                    output_backup, engine="xlsxwriter"
                ) as backup_writer:
                    dict_backup_tables = {
                        "PERIODE_PSM": "periods_df",
                        "MASTER_ITEM": "items_df",
                        "MASTER_PERSONIL": "person_df",
                        "SALES_ITEM": "sales_item_df",
                        "SALES_PERSONIL": "sales_person_df",
                        "PERIODE_PPS": "periods_pps_df",
                        "SALES_PPS": "sales_pps_df",
                    }
                    for sheet_name, state_key in dict_backup_tables.items():
                        df_b = st.session_state.get(state_key, pd.DataFrame())
                        if not df_b.empty:
                            df_b.to_excel(
                                backup_writer, sheet_name=sheet_name, index=False
                            )

                excel_backup_bytes = output_backup.getvalue()
                filename_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="💾 Download Full Backup (.xlsx)",
                    data=excel_backup_bytes,
                    file_name=f"Backup_Database_LigaPSM_{filename_time}.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ),
                    use_container_width=True,
                )
            except Exception as e_dl:
                st.error(f"⚠️ Gagal menyiapkan file download: {e_dl}")

        st.markdown("---")

        # =========================================================================
        # 3. GENERATOR REPORT SUMMARY WHATSAPP
        # =========================================================================
        st.subheader("📲 Generator Report Summary WhatsApp")
        st.caption(
            "Pilih filter bulan & periode untuk menghasilkan rangkuman performa PSM & PPS."
        )

        col_rep1, col_rep2 = st.columns(2)
        with col_rep1:
            bulan_list = [
                "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                "Juli", "Agustus", "September", "Oktober", "November", "Desember"
            ]
            curr_month_idx = waktu_wib.month - 1
            selected_month_name = st.selectbox(
                "📅 Pilih Bulan Report", bulan_list, index=curr_month_idx
            )
            selected_month_num = bulan_list.index(selected_month_name) + 1

        psm_periods_df = st.session_state.get("periods_df", pd.DataFrame())
        psm_opt = ["Seluruh Penjualan 1 Bulan"]

        if not psm_periods_df.empty and "period_name" in psm_periods_df.columns:
            psm_opt.extend(psm_periods_df["period_name"].dropna().unique().tolist())

        with col_rep2:
            selected_psm_period_opt = st.selectbox("🎯 Filter Periode PSM", psm_opt)

        btn_gen_summary = st.button(
            "🚀 Generate Summary WhatsApp",
            use_container_width=True,
            type="primary",
        )

        if btn_gen_summary:
            # ---------------------------------------------------------------------
            # A. LOGIKA HITUNG AKURAT UNTUK PSM
            # ---------------------------------------------------------------------
            target_psm_tot = 0
            actual_psm_tot = 0

            sales_item_df = st.session_state.get("sales_item_df", pd.DataFrame())
            valid_period_ids = []

            if not psm_periods_df.empty:
                p_filtered = psm_periods_df.copy()
                
                if "start_date" in p_filtered.columns:
                    p_filtered["start_date"] = pd.to_datetime(p_filtered["start_date"], errors="coerce")
                    p_date_filtered = p_filtered[
                        (p_filtered["start_date"].dt.month == selected_month_num) & 
                        (p_filtered["start_date"].dt.year == waktu_wib.year)
                    ]
                    if not p_date_filtered.empty:
                        p_filtered = p_date_filtered

                if selected_psm_period_opt != "Seluruh Penjualan 1 Bulan" and "period_name" in p_filtered.columns:
                    p_filtered = p_filtered[p_filtered["period_name"] == selected_psm_period_opt]

                if "period_id" in p_filtered.columns:
                    valid_period_ids = p_filtered["period_id"].dropna().unique().tolist()

            if not sales_item_df.empty:
                s_item = sales_item_df.copy()
                
                if valid_period_ids and "period_id" in s_item.columns:
                    s_item_filtered = s_item[s_item["period_id"].isin(valid_period_ids)]
                    if not s_item_filtered.empty:
                        s_item = s_item_filtered
                elif selected_psm_period_opt != "Seluruh Penjualan 1 Bulan":
                    s_item = s_item.iloc[0:0]

                if "target_qty" in s_item.columns:
                    target_psm_tot = pd.to_numeric(s_item["target_qty"], errors="coerce").sum()
                
                if "actual_qty" in s_item.columns:
                    actual_psm_tot = pd.to_numeric(s_item["actual_qty"], errors="coerce").sum()

            ach_psm = (actual_psm_tot / target_psm_tot * 100) if target_psm_tot > 0 else 0

            # ---------------------------------------------------------------------
            # B. LOGIKA PPS (Mengambil langsung berdasarkan period_id yang akurat)
            # ---------------------------------------------------------------------
            periods_pps_df = st.session_state.get("periods_pps_df", pd.DataFrame())
            pps_filtered = periods_pps_df.copy()

            def get_pps_by_id(df, p_id, col_name):
                """Mengambil nilai berdasarkan period_id yang spesifik"""
                if df.empty or "period_id" not in df.columns or col_name not in df.columns:
                    return 0
                sub_df = df[df["period_id"].astype(str).str.strip() == p_id]
                if sub_df.empty:
                    return 0
                return pd.to_numeric(sub_df[col_name], errors="coerce").sum()

            # Kolom redeem di sheet tertulis 'deem_total' (atau 'redeem_total')
            redeem_col_name = "deem_total" if "deem_total" in pps_filtered.columns else "redeem_total"

            # 1. PWP (period_id: PWP01)
            s_pwp  = get_pps_by_id(pps_filtered, "PWP01", "syarat_total")
            r_pwp  = get_pps_by_id(pps_filtered, "PWP01", redeem_col_name)
            tq_pwp = get_pps_by_id(pps_filtered, "PWP01", "target_total")
            q_pwp  = get_pps_by_id(pps_filtered, "PWP01", "actual_qty")

            ach_pwp_redeem = (r_pwp / s_pwp * 100) if s_pwp > 0 else 0
            ach_pwp_qty    = (q_pwp / tq_pwp * 100) if tq_pwp > 0 else 0

            # 2. SUEGER (period_id: SGR001)
            s_sueger_val = get_pps_by_id(pps_filtered, "SGR001", "syarat_total")
            r_sueger_val = get_pps_by_id(pps_filtered, "SGR001", redeem_col_name)
            if r_sueger_val == 0:
                r_sueger_val = get_pps_by_id(pps_filtered, "SGR001", "actual_qty")
            ach_sueger = (r_sueger_val / s_sueger_val * 100) if s_sueger_val > 0 else 0

            # 3. SERBA GRATIS (period_id: SGS01)
            t_sg = get_pps_by_id(pps_filtered, "SGS01", "target_total")
            q_sg = get_pps_by_id(pps_filtered, "SGS01", "actual_qty")
            ach_sg = (q_sg / t_sg * 100) if t_sg > 0 else 0

            # 4. CEMILAN CEBAN (period_id: CBN01)
            t_ceban = get_pps_by_id(pps_filtered, "CBN01", "target_total")
            q_ceban = get_pps_by_id(pps_filtered, "CBN01", "actual_qty")
            ach_ceban = (q_ceban / t_ceban * 100) if t_ceban > 0 else 0

            # ---------------------------------------------------------------------
            # D. PERHITUNGAN BOBOT POIN PROGRAM
            # ---------------------------------------------------------------------
            poin_psm = 20 * (ach_psm / 100)
            poin_pwp = 25 * (ach_pwp_qty / 100)
            poin_sg = 30 * (ach_sg / 100)
            
            total_poin_didapat = poin_psm + poin_pwp + poin_sg

            # ---------------------------------------------------------------------
            # E. FORMAT TEKS SUMMARY WHATSAPP
            # ---------------------------------------------------------------------
            wa_text = f"""*📊 REPORT SUMMARY PENJUALAN {selected_month_name.upper()} {waktu_wib.year}*
        ----------------------------------------
        *1. PROGRAM PSM ({selected_psm_period_opt.upper()})*
        • Target PSM     : {int(target_psm_tot):,} Pcs
        • Actual Qty     : {int(actual_psm_tot):,} Pcs
        • Achievement    : *{ach_psm:.1f}%*
        • Poin PSM       : *{poin_psm:.2f}* (Bobot Max: 20)

        *2. PROGRAM PENJUALAN & KINERJA (PPS)*
        • *PWP (Purchase with Purchase)*
        - Syarat Redeem: {int(s_pwp):,}
        - Total Redeem : {int(r_pwp):,}
        - Target Qty   : {int(tq_pwp):,} Pcs
        - Total Qty    : {int(q_pwp):,} Pcs
        - Ach. Redeem  : *{ach_pwp_redeem:.1f}%*
        - Ach. Qty     : *{ach_pwp_qty:.1f}%*
        - Poin PWP     : *{poin_pwp:.2f}* (Bobot Max: 25)

        • *SUEGER*
        - Syarat Redeem: {int(s_sueger_val):,}
        - Qty Redeem   : {int(r_sueger_val):,}
        - Achievement  : *{ach_sueger:.1f}%*

        • *SERBA GRATIS*
        - Target Qty   : {int(t_sg):,} Pcs
        - Actual Qty   : {int(q_sg):,} Pcs
        - Achievement  : *{ach_sg:.1f}%*
        - Poin SG      : *{poin_sg:.2f}* (Bobot Max: 30)

        ----------------------------------------
        *🏆 TOTAL POIN DIDAPAT: {total_poin_didapat:.2f}*
        ----------------------------------------
        _Generated automatically via LigaPSM System_
        """.replace(",", ".")

            st.markdown("##### 📝 Hasil Text Report (Siap Copas ke WA):")
            st.text_area(
                "Salin teks di bawah sini:",
                wa_text,
                height=400,
                key="wa_summary_text_area",
            )
            st.code(wa_text, language="text")
