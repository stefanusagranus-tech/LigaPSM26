import time
import re
import math
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_gsheets import GSheetsConnection

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


@st.cache_data(ttl=60)
def load_database():
  """Membaca data sheet secara bertahap sesuai modul PSM, PPS, dan Store Performance."""
  try:
    # 1. Modul PSM & Master Data Umum
    periods_df = conn.read(worksheet="PERIODE", ttl=0)
    time.sleep(0.3)
    items_df = conn.read(worksheet="MASTER_ITEM", ttl=0)
    time.sleep(0.3)
    person_df = conn.read(worksheet="MASTER_PERSONIL", ttl=0)
    time.sleep(0.3)
    sales_item_df = conn.read(worksheet="SALES_ITEM", ttl=0)
    time.sleep(0.3)
    sales_person_df = conn.read(worksheet="SALES_PERSONIL", ttl=0)
    time.sleep(0.3)

    # 2. Modul PPS
    periods_pps_df = conn.read(worksheet="PERIODE_PPS", ttl=0)
    time.sleep(0.3)
    sales_pps_df = conn.read(worksheet="SALES_PPS", ttl=0)
    time.sleep(0.3)

    # 3. Modul Store Performance
    periods_store_df = conn.read(worksheet="PERIODE_STOREPERFORMANCE", ttl=0)
    time.sleep(0.3)
    sales_store_df = conn.read(worksheet="SALES_STOREPERFORMANCE", ttl=0)

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


def save_database(
    sales_item_df, sales_person_df, sales_pps_df, sales_store_df
):
  """Menyimpan data transaksi ke Google Sheets dengan pengaman validasi data kosong."""
  try:
    # PENGAMANAN: Blokir penyimpanan jika data transaksi utama mendadak kosong melompong
    if sales_item_df.empty or sales_person_df.empty:
      st.warning(
          "⚠️ Proses simpan dibatalkan: Data transaksi terdeteksi kosong untuk"
          " mencegah kehilangan data."
      )
      return False

    # Proses update bertahap dengan jeda waktu untuk menghindari rate limit API
    conn.update(worksheet="SALES_ITEM", data=sales_item_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_PERSONIL", data=sales_person_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_PPS", data=sales_pps_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_STOREPERFORMANCE", data=sales_store_df)

    st.toast(
        "Perubahan transaksi tersimpan permanen di Google Sheets!", icon="✅"
    )
    return True
  except Exception as e:
    st.error(
        f"❌ Gagal menyimpan transaksi ke Google Sheets (Kemungkinan terkena"
        f" limit/timeout): {e}"
    )
    return False


def save_master_table(sheet_name, df_data):
  """Menyimpan tabel master dengan pengaman validasi data kosong dan urutan kolom."""
  try:
    if df_data.empty:
      st.warning(f"⚠️ Master {sheet_name} batal disimpan karena data kosong.")
      return False

    # Penyelarasan urutan kolom khusus untuk MASTER_ITEM agar tidak bergeser
    if sheet_name == "MASTER_ITEM":
      expected_cols = ["period_id", "item_id", "item_name", "active", "category"]
      # Pastikan kolom yang belum ada ditambahkan sebagai string kosong
      for col in expected_cols:
        if col not in df_data.columns:
          df_data[col] = ""
      # Urutkan DataFrame persis seperti struktur Google Sheets
      df_data = df_data[expected_cols]

    conn.update(worksheet=sheet_name, data=df_data)
    time.sleep(0.3)
    st.toast(
        f"Master {sheet_name} berhasil diperbarui di Google Sheets!", icon="✅"
    )
    return True
  except Exception as e:
    st.error(f"❌ Gagal update master {sheet_name} (Terkena limit API): {e}")
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
    tot_per_item.rename(columns={"actual_qty": "calc_actual_qty"}, inplace=True)

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


# ==========================================
# 5. CUSTOM CSS (NEON DARK THEME)
# ==========================================
st.markdown(
    """
<style>
    .stApp {
        background-color: #0b0f19;
        color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label, label p {
        color: #38bdf8 !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }
    div[data-baseweb="input"] input, 
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] span {
        color: #ffffff !important;
        background-color: transparent !important;
        font-weight: bold !important;
    }
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div {
        background-color: #0d1117 !important;
        border: 1.5px solid #00f0ff !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="input"] svg {
        fill: #00f0ff !important;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #38bdf8;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        text-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
        font-weight: 800;
        font-size: 26px;
    }
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: 600;
    }
    div[data-testid="stRadio"] input[type="radio"],
    div[data-testid="stRadio"] div[role="radiogroup"] div:has(> input[type="radio"]) {
        display: none !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label {
        background-color: #1e293b;
        border: 1px solid #334155;
        padding: 12px 18px;
        border-radius: 10px;
        margin-bottom: 8px;
        color: #ffffff !important;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.25s ease-in-out;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        display: block;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        border-color: #38bdf8;
        background-color: #334155;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
        transform: translateY(-1px);
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
    div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: 1px solid #38bdf8 !important;
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.6) !important;
        color: #ffffff !important;
    }
    div.stButton > button, div.stFormSubmitButton > button {
        background-color: #080c14 !important;
        color: #ffffff !important;
        border: 2px solid #00f0ff !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        box-shadow: 0 0 10px rgba(0, 240, 255, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background-color: #00f0ff !important;
        color: #080c14 !important;
        box-shadow: 0 0 20px rgba(0, 240, 255, 0.8) !important;
    }
    [data-testid="stSidebar"] div[data-testid="stButton"] > button {
        background-color: #0f172a !important;
        color: #ef4444 !important;
        border: 1px solid #ef4444 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background-color: #ef4444 !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.5) !important;
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


if not st.session_state.logged_in:
  show_login_page()
  st.stop()

# ==========================================================
# 7. SIDEBAR DASHBOARD
# ==========================================================
st.sidebar.markdown(
    """
    <style>
        .sidebar-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
        }
        .sidebar-logo {
            width: 55px;
            height: 55px;
            border-radius: 50%;
            object-fit: cover;
            border: 1.5px solid #38bdf8;
        }
        .store-title {
            text-align: center;
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 2px;
            letter-spacing: 1px;
        }
        .store-subtitle {
            text-align: center;
            color: #38bdf8;
            font-size: 12px;
            font-weight: 600;
            margin-top: 0px;
            margin-bottom: 10px;
        }
    </style>
""",
    unsafe_allow_html=True,
)

LOGO_URL = "https://tse3.mm.bing.net/th/id/OIP.mVrKCdnlL5Yc-3wRmzFXOAAAAA?r=0&rs=1&pid=ImgDetMain&o=7&rm=3"
username = st.session_state.get("username", "Admin")

st.sidebar.markdown(
    f"""
    <div class='sidebar-header'>
        <img src='{LOGO_URL}' class='sidebar-logo'>
        <div style='display: flex; flex-direction: column;'>
            <span style='color: #94a3b8; font-size: 11px; font-weight: 500;'>Selamat Datang Kembali,</span>
            <span style='color: #00ff88; font-size: 13px; font-weight: 700;'>👤 {username}</span>
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    "<hr style='margin: 10px 0; border-color: #334155;'>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    "<div class='store-title'>TOKO C383</div>", unsafe_allow_html=True
)
st.sidebar.markdown(
    "<div class='store-subtitle'>Report PSM dan Target PSM</div>",
    unsafe_allow_html=True,
)

# ➔ Tombol Refresh Cache ditaruh di sini agar mudah dijangkau
if st.sidebar.button("🔄 Refresh Data Cache", use_container_width=True):
  st.cache_data.clear()
  for key in list(st.session_state.keys()):
    del st.session_state[key]
  st.rerun()

st.sidebar.markdown("---")

st.sidebar.markdown(
    "<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px;"
    " margin-bottom:6px;'>📌 NAVIGASI MENU</p>",
    unsafe_allow_html=True,
)
menu_options = [
    "01 · Overview",
    "02 · Detail Item",
    "03 · Penjualan Personil",
    "04 · Pencapaian Pernik",
    "05 · Analisis Tren",
    "06 · Input & Reset Data",
    "⚙️ Master Data & Pengaturan",
]
selected_tab = st.sidebar.radio(
    "", menu_options, label_visibility="collapsed"
)
st.sidebar.markdown("---")

st.sidebar.markdown(
    "<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px;"
    " margin-bottom:6px;'>🌟 FILTER PERIODE</p>",
    unsafe_allow_html=True,
)

periods_df = st.session_state.periods_df
if not periods_df.empty:
  periods_dict = {
      row["period_name"]: row["period_id"]
      for _, row in periods_df.iterrows()
  }
else:
  periods_dict = {"Periode Utama": "P01"}

selected_period_name = st.sidebar.selectbox(
    "",
    ["Semua Periode (Overall)"] + list(periods_dict.keys()),
    label_visibility="collapsed",
)
selected_period_id = (
    None
    if selected_period_name == "Semua Periode (Overall)"
    else periods_dict[selected_period_name]
)

st.sidebar.markdown(
    "<hr style='margin: 15px 0; border-color: #334155;'>",
    unsafe_allow_html=True,
)
if st.sidebar.button("🚪 Keluar / Logout", use_container_width=True):
  st.session_state.logged_in = False
  st.session_state.username = ""
  st.rerun()
    
# ==========================================
# 8. HEADER UTAMA
# ==========================================
st.markdown(
    f"""
    <div style='background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 16px 24px; border-radius: 12px; border: 1px solid #38bdf8; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;'>
        <div>
            <h2 style='margin:0; color:#ffffff; font-size: 24px;'>📊 PSM TOKO SALES MONITORING</h2>
            <p style='margin:0; color:#38bdf8; font-size: 13px;'>Sistem Analisis & Optimasi Pencapaian Target Toko</p>
        </div>
        <div style='text-align: right;'>
            <p style='margin:0; color:#94a3b8; font-size: 11px; font-weight:bold;'>WAKTU REALTIME SISTEM</p>
            <p style='margin:0; color:#38bdf8; font-size: 14px; font-weight:bold;'>⏰ {current_time_str}</p>
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 9. MODUL TAB / SUB MENU
# ==========================================

# --- TAB 01: OVERVIEW PENJUALAN ---
if selected_tab == "01 · Overview":
  st.title("📊 Overview Penjualan Toko")
  si_df = st.session_state.sales_item_df.copy()
  sp_df = st.session_state.sales_person_df.copy()
  periods_df = st.session_state.periods_df.copy()

  if selected_period_id:
    sub_periods = periods_df[periods_df["period_id"] == selected_period_id]
    sub_si = si_df[si_df["period_id"] == selected_period_id]
    sub_sp = sp_df[sp_df["period_id"] == selected_period_id]
  else:
    sub_periods = periods_df
    sub_si = si_df
    sub_sp = sp_df

  if not sub_periods.empty and "start_date" in sub_periods.columns:
    default_start = pd.to_datetime(sub_periods.iloc[0]["start_date"]).date()
    default_end = pd.to_datetime(sub_periods.iloc[0]["end_date"]).date()
  else:
    default_start = waktu_wib.date().replace(day=1)
    default_end = waktu_wib.date()

  st.markdown("### 📅 Filter Rentang Tanggal Overview")
  col_date1, col_date2 = st.columns(2)
  with col_date1:
    start_date = st.date_input(
        "Tanggal Awal Overview", value=default_start, key="t1_start_date"
    )
  with col_date2:
    end_date = st.date_input(
        "Tanggal Akhir Overview", value=default_end, key="t1_end_date"
    )

  if start_date > end_date:
    st.error("⚠️ Tanggal Awal tidak boleh melebihi Tanggal Akhir!")
    st.stop()

  if "updated_at" in sub_sp.columns and not sub_sp.empty:
    sub_sp["updated_at_dt"] = pd.to_datetime(sub_sp["updated_at"]).dt.date
    filtered_sp = sub_sp[
        (sub_sp["updated_at_dt"] >= start_date)
        & (sub_sp["updated_at_dt"] <= end_date)
    ].copy()
  else:
    filtered_sp = sub_sp.copy()

  total_days = max((end_date - start_date).days + 1, 1)
  today_date = waktu_wib.date()
  if today_date < start_date:
    passed_days = 0
  elif today_date > end_date:
    passed_days = total_days
  else:
    passed_days = max((today_date - start_date).days + 1, 1)

  time_factor = (passed_days / total_days) * 100 if total_days > 0 else 0

  if "target_qty" not in sub_si.columns:
    sub_si["target_qty"] = 0

  sub_si["target_qty"] = pd.to_numeric(
      sub_si["target_qty"], errors="coerce"
  ).fillna(0)

  if "actual_qty" in filtered_sp.columns:
    filtered_sp["actual_qty"] = pd.to_numeric(
        filtered_sp["actual_qty"], errors="coerce"
    ).fillna(0)
  else:
    filtered_sp["actual_qty"] = 0

  tot_target = sub_si["target_qty"].sum()
  tot_actual = filtered_sp["actual_qty"].sum()
  tot_gap = tot_target - tot_actual
  tot_ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0

  m1, m2, m3, m4, m5 = st.columns(5)
  with m1:
    st.metric("🎯 Total Target", f"{tot_target:,.0f} Pcs")
  with m2:
    st.metric("📦 Actual Penjualan", f"{tot_actual:,.0f} Pcs")
  with m3:
    st.metric("📉 Sisa Gap Target", f"{tot_gap:,.0f} Pcs")
  with m4:
    st.metric("⚡ % Achievement", f"{tot_ach:.1f}%")
  with m5:
    st.metric(
        "⏳ Time Factor (Waktu)",
        f"{time_factor:.1f}%",
        help=f"Hari berjalan: {passed_days}/{total_days} hari",
    )

  st.markdown("---")
  pace_gap = tot_ach - time_factor
  if pace_gap >= 0:
    status_color = "#00ff9d"
    status_bg = "rgba(0, 255, 157, 0.1)"
    status_icon = "🚀"
    status_title = "PACE PENJUALAN ON TRACK"
    status_desc = (
        f"Pencapaian penjualan (**{tot_ach:.1f}%**) melampaui laju waktu"
        f" berjalan (**{time_factor:.1f}%**). Pertahankan performa toko!"
    )
  else:
    status_color = "#ff2a6d"
    status_bg = "rgba(255, 42, 109, 0.1)"
    status_icon = "⚠️"
    status_title = "PACE PENJUALAN BEHIND TARGET"
    status_desc = (
        f"Pencapaian penjualan (**{tot_ach:.1f}%**) masih di bawah laju waktu"
        f" berjalan (**{time_factor:.1f}%**). Tertinggal sebesar"
        f" **{abs(pace_gap):.1f}%**."
    )

  st.markdown(
      f"""
        <div style="background: {status_bg}; border: 1.5px solid {status_color}; border-left: 6px solid {status_color}; border-radius: 10px; padding: 16px; margin-bottom: 20px;">
            <h4 style="color: {status_color}; margin: 0 0 6px 0;">{status_icon} {status_title}</h4>
            <p style="color: #f1f5f9; margin: 0; font-size: 14px;">{status_desc}</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.subheader("📋 Ringkasan Penjualan Per Item Produk")
  item_sp = (
      filtered_sp.groupby(["item_id", "item_name"])["actual_qty"]
      .sum()
      .reset_index()
      if not filtered_sp.empty
      else pd.DataFrame(columns=["item_id", "item_name", "actual_qty"])
  )
  overview_table = pd.merge(
      sub_si[["item_id", "item_name", "target_qty"]],
      item_sp[["item_id", "actual_qty"]],
      on="item_id",
      how="left",
  )
  overview_table["actual_qty"] = overview_table["actual_qty"].fillna(0)
  overview_table["gap"] = (
      overview_table["target_qty"] - overview_table["actual_qty"]
  )
  overview_table["ach"] = overview_table.apply(
      lambda r: (r["actual_qty"] / r["target_qty"] * 100)
      if r["target_qty"] > 0
      else 0,
      axis=1,
  )

  table_rows_html = ""
  for _, row in overview_table.iterrows():
    gap_color = "#00ff88" if row["gap"] <= 0 else "#ef4444"
    ach_color = "#00ff88" if row["ach"] >= time_factor else "#ffb703"
    table_rows_html += f"""
        <tr style="border-bottom: 1px solid #1e293b;">
            <td style="padding: 10px; color: #ffffff; font-weight: bold; font-size: 13px;">{row['item_name']}</td>
            <td style="padding: 10px; color: #94a3b8; font-size: 13px;">{row['target_qty']:,.0f} Pcs</td>
            <td style="padding: 10px; color: #00ff88; font-weight: bold; font-size: 13px;">{row['actual_qty']:,.0f} Pcs</td>
            <td style="padding: 10px; color: {gap_color}; font-size: 13px;">{row['gap']:,.0f} Pcs</td>
            <td style="padding: 10px; color: {ach_color}; font-weight: bold; font-size: 13px;">{row['ach']:.1f}%</td>
        </tr>
        """

  st.markdown(
      f"""
        <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; max-height: 400px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                <thead>
                    <tr style="border-bottom: 2px solid #334155;">
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">NAMA PRODUK</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">TARGET TOKO</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">ACTUAL PENJUALAN</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">SISA GAP</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">% ACHIEVEMENT</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>
        </div>
    """,
      unsafe_allow_html=True,
  )

# --- TAB 02: DETAIL ITEM ---
elif selected_tab == "02 · Detail Item":
  st.title("📦 Detail Item & Performa Produk")
  si_df = st.session_state.sales_item_df.copy()

  st.markdown(
      "<p style='color:#38bdf8; font-weight:bold; font-size:13px;'>🔍 FILTER &"
      " PENGURUTAN DATA PRODUK</p>",
      unsafe_allow_html=True,
  )
  f_col1, f_col2, f_col3 = st.columns([1.5, 1, 1.2])

  with f_col1:
    search_query = st.text_input(
        "Cari Nama Produk / Item",
        placeholder="Ketik nama item...",
        key="search_item_tab2",
    )
  with f_col2:
    selected_p_tab2 = st.selectbox(
        "Periode Promosi",
        ["Semua Periode Promosi"] + list(periods_dict.keys()),
        key="period_tab2",
    )
  with f_col3:
    sort_option = st.selectbox(
        "Urutkan Berdasarkan",
        [
            "Penjualan Terbanyak (Terlaris)",
            "Penjualan Tersedikit",
            "Achievement Tertinggi (% Ach)",
            "Nama Produk (A - Z)",
        ],
        key="sort_tab2",
    )

  if selected_p_tab2 != "Semua Periode Promosi":
    p_id_filter = periods_dict[selected_p_tab2]
    si_df = si_df[si_df["period_id"] == p_id_filter]

  si_df["target_qty"] = pd.to_numeric(
      si_df["target_qty"], errors="coerce"
  ).fillna(0)
  si_df["actual_qty"] = pd.to_numeric(
      si_df["actual_qty"], errors="coerce"
  ).fillna(0)

  item_grouped = (
      si_df.groupby("item_name")
      .agg({"target_qty": "sum", "actual_qty": "sum"})
      .reset_index()
  )
  item_grouped["ach"] = item_grouped.apply(
      lambda r: (r["actual_qty"] / r["target_qty"] * 100)
      if r["target_qty"] > 0
      else 0,
      axis=1,
  )
  item_grouped["gap"] = item_grouped["actual_qty"] - item_grouped["target_qty"]

  if search_query:
    item_grouped = item_grouped[
        item_grouped["item_name"].str.contains(
            search_query, case=False, na=False
        )
    ]

  if not item_grouped.empty:
    top_item = item_grouped.sort_values(
        by="actual_qty", ascending=False
    ).iloc[0]
    low_item = item_grouped.sort_values(by="actual_qty", ascending=True).iloc[0]

    if sort_option == "Penjualan Terbanyak (Terlaris)":
      item_grouped = item_grouped.sort_values(by="actual_qty", ascending=False)
    elif sort_option == "Penjualan Tersedikit":
      item_grouped = item_grouped.sort_values(by="actual_qty", ascending=True)
    elif sort_option == "Achievement Tertinggi (% Ach)":
      item_grouped = item_grouped.sort_values(by="ach", ascending=False)
    elif sort_option == "Nama Produk (A - Z)":
      item_grouped = item_grouped.sort_values(by="item_name", ascending=True)

    st.markdown("<br>", unsafe_allow_html=True)
    r_col1, r_col2, r_col3 = st.columns(3)
    with r_col1:
      st.markdown(
          f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #f59e0b; font-size: 11px; font-weight: bold;">🔥 ITEM TERLARIS</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{top_item['item_name']}</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{top_item['actual_qty']:,.0f} Pcs</div>
                </div>
            """,
          unsafe_allow_html=True,
      )
    with r_col2:
      st.markdown(
          f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #ef4444; font-size: 11px; font-weight: bold;">📉 ITEM TERENDAH</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{low_item['item_name']}</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{low_item['actual_qty']:,.0f} Pcs</div>
                </div>
            """,
          unsafe_allow_html=True,
      )
    with r_col3:
      st.markdown(
          f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #38bdf8; font-size: 11px; font-weight: bold;">📦 VARIASI ITEM</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{len(item_grouped)} Jenis</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{item_grouped['actual_qty'].sum():,.0f} Pcs Total</div>
                </div>
            """,
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)
    table_rows_html = ""
    for _, row in item_grouped.iterrows():
      gap_color = "#00ff88" if row["gap"] >= 0 else "#ef4444"
      table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 12px; color: #ffffff; font-weight: bold;">{row['item_name']}</td>
                <td style="padding: 12px; color: #94a3b8;">{row['target_qty']:,.0f}</td>
                <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['ach']:.1f}%</td>
                <td style="padding: 12px; color: {gap_color}; font-weight: bold;">{row['gap']:,.0f}</td>
            </tr>
            """

    st.markdown(
        f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 12px; max-height: 520px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #334155;">
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">NAMA PRODUK</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">TARGET (PCS)</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">ACTUAL SALES</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">% ACH</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">GAP / SELISIH</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
        """,
        unsafe_allow_html=True,
    )

# --- TAB 03: PENJUALAN PERSONIL ---
elif selected_tab == "03 · Penjualan Personil":
  st.title("👥 Penjualan Personil Toko")
  sp_df = st.session_state.sales_person_df.copy()
  if selected_period_id:
    sp_df = sp_df[sp_df["period_id"] == selected_period_id]

  sp_df["actual_qty"] = pd.to_numeric(
      sp_df["actual_qty"], errors="coerce"
  ).fillna(0)

  if not sp_df.empty:
    summary_person = (
        sp_df.groupby("person_name")["actual_qty"]
        .sum()
        .reset_index()
        .sort_values(by="actual_qty", ascending=False)
    )
    tot_actual_personil = summary_person["actual_qty"].sum()
    avg_sales_personil = (
        summary_person["actual_qty"].mean() if len(summary_person) > 0 else 0
    )
    top_performer_name = (
        summary_person.iloc[0]["person_name"]
        if len(summary_person) > 0
        else "-"
    )
    summary_person["pct_contrib"] = (
        (summary_person["actual_qty"] / tot_actual_personil * 100)
        if tot_actual_personil > 0
        else 0
    )

    m1, m2, m3 = st.columns(3)
    with m1:
      st.markdown(
          '<div style="background:#080c14; border:1.5px solid #00f0ff;'
          ' border-radius:10px; padding:16px;"><div style="color:#ffffff;'
          ' font-size:11px; font-weight:bold;">TOTAL ACTUAL PERSONIL</div><div'
          ' style="color:#00ff88; font-size:28px;'
          f' font-weight:800;">{tot_actual_personil:,.0f} Pcs</div></div>',
          unsafe_allow_html=True,
      )
    with m2:
      st.markdown(
          '<div style="background:#080c14; border:1.5px solid #00f0ff;'
          ' border-radius:10px; padding:16px;"><div style="color:#ffffff;'
          ' font-size:11px; font-weight:bold;">RATA-RATA'
          ' PENJUALAN/STAF</div><div style="color:#00ff88; font-size:28px;'
          f' font-weight:800;">{avg_sales_personil:,.0f} Pcs</div></div>',
          unsafe_allow_html=True,
      )
    with m3:
      st.markdown(
          '<div style="background:#080c14; border:1.5px solid #00f0ff;'
          ' border-radius:10px; padding:16px;"><div style="color:#ffffff;'
          ' font-size:11px; font-weight:bold;">TOP PERFORMER</div><div'
          ' style="color:#00ff88; font-size:26px;'
          f' font-weight:800;">{top_performer_name}</div></div>',
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)
    if len(summary_person) >= 1:
      p1_name = summary_person.iloc[0]["person_name"]
      p1_qty = summary_person.iloc[0]["actual_qty"]
      p2_name = (
          summary_person.iloc[1]["person_name"]
          if len(summary_person) >= 2
          else "-"
      )
      p2_qty = (
          summary_person.iloc[1]["actual_qty"]
          if len(summary_person) >= 2
          else 0
      )
      p3_name = (
          summary_person.iloc[2]["person_name"]
          if len(summary_person) >= 3
          else "-"
      )
      p3_qty = (
          summary_person.iloc[2]["actual_qty"]
          if len(summary_person) >= 3
          else 0
      )

      st.markdown(
          f"""
                <div style="display: flex; gap: 12px; justify-content: center; align-items: flex-end; margin-bottom: 20px;">
                    <div style="flex: 1; background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; text-align: center;">
                        <span style="font-size: 18px;">🥈</span>
                        <div style="color: #94a3b8; font-size: 10px; font-weight: bold;">JUARA 2</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold;">{p2_name}</div>
                        <div style="color: #00ff88; font-size: 15px; font-weight: 800;">{p2_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #080c14; border: 2px solid #00f0ff; border-radius: 10px; padding: 12px; text-align: center; transform: scale(1.02);">
                        <span style="font-size: 22px;">🥇</span>
                        <div style="color: #f59e0b; font-size: 10px; font-weight: bold;">JUARA 1</div>
                        <div style="color: #ffffff; font-size: 13px; font-weight: bold;">{p1_name}</div>
                        <div style="color: #00ff88; font-size: 17px; font-weight: 800;">{p1_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; text-align: center;">
                        <span style="font-size: 18px;">🥉</span>
                        <div style="color: #b45309; font-size: 10px; font-weight: bold;">JUARA 3</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold;">{p3_name}</div>
                        <div style="color: #00ff88; font-size: 15px; font-weight: 800;">{p3_qty:,.0f} Pcs</div>
                    </div>
                </div>
            """,
          unsafe_allow_html=True,
      )

    st.markdown("---")
    col_table, col_chart = st.columns([1, 1])
    COMPONENT_HEIGHT = 310

    with col_table:
      st.markdown(
          "<p style='color:#ffffff; font-size:15px; font-weight:bold;'>📋 Tabel"
          " Ranking Personil</p>",
          unsafe_allow_html=True,
      )
      table_rows_html = ""
      for _, row in summary_person.iterrows():
        table_rows_html += f"""
                <tr style="border-bottom: 1px solid #1e293b;">
                    <td style="padding: 12px; color: #ffffff; font-weight: bold;">{row['person_name']}</td>
                    <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                    <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['pct_contrib']:.1f}%</td>
                </tr>
                """
      st.markdown(
          f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; height: {COMPONENT_HEIGHT}px; overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                        <thead>
                            <tr style="border-bottom: 2px solid #334155;">
                                <th style="padding: 8px; color: #94a3b8; font-size: 11px;">PERSONIL</th>
                                <th style="padding: 8px; color: #94a3b8; font-size: 11px;">TOTAL SALES</th>
                                <th style="padding: 8px; color: #94a3b8; font-size: 11px;">KONTRIBUSI</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>
                </div>
            """,
          unsafe_allow_html=True,
      )

    with col_chart:
      st.markdown(
          "<p style='color:#ffffff; font-size:15px; font-weight:bold;'>📊 Grafik"
          " Perbandingan Personil</p>",
          unsafe_allow_html=True,
      )
      fig_person = go.Figure()
      fig_person.add_trace(
          go.Bar(
              x=summary_person["person_name"],
              y=summary_person["actual_qty"],
              marker_color="#00ff88",
              text=summary_person["actual_qty"].apply(lambda x: f"{x:,.0f}"),
              textposition="outside",
          )
      )
      fig_person.update_layout(
          height=COMPONENT_HEIGHT,
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          font=dict(color="#ffffff"),
          margin=dict(l=10, r=10, t=10, b=10),
      )
      st.plotly_chart(fig_person, use_container_width=True)

# --- TAB 04: PENCAPAIAN PERNIK PER PERSONIL ---
elif selected_tab == "04 · Pencapaian Pernik":
  st.title("🏆 Pencapaian Pernik Per Personil")

  person_list = (
      st.session_state.person_df["person_name"].dropna().unique().tolist()
  )
  if not person_list:
    person_list = (
        st.session_state.sales_person_df["person_name"]
        .dropna()
        .unique()
        .tolist()
    )

  c_p1, _ = st.columns([1.5, 1])
  with c_p1:
    selected_person = st.selectbox(
        "👤 PILIH PERSONIL TOKO", person_list, key="tab4_person_select"
    )

  sp_df = st.session_state.sales_person_df.copy()
  si_df = st.session_state.sales_item_df.copy()

  if selected_period_id:
    sp_df = sp_df[sp_df["period_id"] == selected_period_id]
    si_df = si_df[si_df["period_id"] == selected_period_id]

  sp_df = sp_df[sp_df["person_name"] == selected_person]
  sp_df["actual_qty"] = pd.to_numeric(
      sp_df["actual_qty"], errors="coerce"
  ).fillna(0)

  target_col = "target_kasir" if "target_kasir" in si_df.columns else "target_qty"
  si_df[target_col] = pd.to_numeric(
      si_df[target_col], errors="coerce"
  ).fillna(0)

  sp_grouped = (
      sp_df.groupby(["item_id", "item_name"])["actual_qty"].sum().reset_index()
  )
  si_grouped = (
      si_df.groupby(["item_id", "item_name"])[target_col].sum().reset_index()
  )

  merged_item_df = pd.merge(
      si_grouped,
      sp_grouped[["item_id", "actual_qty"]],
      on="item_id",
      how="left",
  )
  merged_item_df["actual_qty"] = merged_item_df["actual_qty"].fillna(0)
  merged_item_df.rename(columns={target_col: "target_val"}, inplace=True)

  merged_item_df["gap"] = (
      merged_item_df["target_val"] - merged_item_df["actual_qty"]
  )
  merged_item_df["ach"] = merged_item_df.apply(
      lambda r: (r["actual_qty"] / r["target_val"] * 100)
      if r["target_val"] > 0
      else 0,
      axis=1,
  )

  tot_target = merged_item_df["target_val"].sum()
  tot_actual = merged_item_df["actual_qty"].sum()
  tot_gap = tot_target - tot_actual
  tot_ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0

  m1, m2, m3, m4 = st.columns(4)
  with m1:
    st.metric("🎯 Target Kasir Item", f"{tot_target:,.0f} Pcs")
  with m2:
    st.metric("📦 Actual Penjualan", f"{tot_actual:,.0f} Pcs")
  with m3:
    st.metric("📉 Sisa Gap Target", f"{tot_gap:,.0f} Pcs")
  with m4:
    st.metric("⚡ % Achievement", f"{tot_ach:.1f}%")

  st.markdown("---")
  col_t4_left, col_t4_right = st.columns([1.2, 1])

  with col_t4_left:
    st.subheader("📋 Rincian Target Item Pernik")
    table_rows_html = ""
    for _, row in merged_item_df.iterrows():
      gap_color = "#00ff88" if row["gap"] <= 0 else "#ef4444"
      ach_color = "#00ff88" if row["ach"] >= 100 else "#ffb703"
      table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 10px; color: #ffffff; font-weight: bold;">{row['item_name']}</td>
                <td style="padding: 10px; color: #94a3b8;">{row['target_val']:,.0f}</td>
                <td style="padding: 10px; color: #00ff88; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 10px; color: {gap_color};">{row['gap']:,.0f}</td>
                <td style="padding: 10px; color: {ach_color}; font-weight: bold;">{row['ach']:.1f}%</td>
            </tr>
            """
    st.markdown(
        f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; max-height: 380px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #334155;">
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">NAMA ITEM</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">TARGET KASIR</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">ACTUAL</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">GAP</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">% ACH</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
        """,
        unsafe_allow_html=True,
    )

  with col_t4_right:
    st.subheader("📊 Visual Breakdown Item")
    fig_p4 = go.Figure()
    fig_p4.add_trace(
        go.Bar(
            y=merged_item_df["item_name"],
            x=merged_item_df["actual_qty"],
            name="Actual",
            orientation="h",
            marker_color="#00f2fe",
        )
    )
    fig_p4.add_trace(
        go.Bar(
            y=merged_item_df["item_name"],
            x=merged_item_df["target_val"],
            name="Target Kasir",
            orientation="h",
            marker_color="#64748b",
        )
    )
    fig_p4.update_layout(
        barmode="group",
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#ffffff"),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_p4, use_container_width=True)

# --- TAB 05: ANALISIS TREN HARIAN ---
elif selected_tab == "05 · Analisis Tren":
  st.title("📈 Analisis Tren Harian, Growth & Disgrowth")
  si_df = st.session_state.sales_item_df.copy()
  sp_df = st.session_state.sales_person_df.copy()
  periods_df = st.session_state.periods_df.copy()

  if selected_period_id:
    sub_periods = periods_df[periods_df["period_id"] == selected_period_id]
    sub_si = si_df[si_df["period_id"] == selected_period_id]
    sub_sp = sp_df[sp_df["period_id"] == selected_period_id]
  else:
    sub_periods = periods_df
    sub_si = si_df
    sub_sp = sp_df

  if not sub_periods.empty and "start_date" in sub_periods.columns:
    default_start = pd.to_datetime(sub_periods.iloc[0]["start_date"]).date()
    default_end = pd.to_datetime(sub_periods.iloc[0]["end_date"]).date()
  else:
    default_start = waktu_wib.date().replace(day=1)
    default_end = waktu_wib.date()

  st.markdown("### 📅 Navigasi Filter Rentang Tanggal")
  c_d1, c_d2 = st.columns(2)
  with c_d1:
    start_date = st.date_input(
        "Tanggal Awal", value=default_start, key="t5_start_date"
    )
  with c_d2:
    end_date = st.date_input(
        "Tanggal Akhir", value=default_end, key="t5_end_date"
    )

  if start_date > end_date:
    st.error("⚠️ Tanggal Awal tidak boleh lebih besar dari Tanggal Akhir!")
    st.stop()

  if "updated_at" in sub_sp.columns and not sub_sp.empty:
    sub_sp["updated_at_dt"] = pd.to_datetime(sub_sp["updated_at"]).dt.date
    filtered_sp = sub_sp[
        (sub_sp["updated_at_dt"] >= start_date)
        & (sub_sp["updated_at_dt"] <= end_date)
    ].copy()
  else:
    filtered_sp = sub_sp.copy()

  sub_si["target_qty"] = pd.to_numeric(
      sub_si["target_qty"], errors="coerce"
  ).fillna(0)
  filtered_sp["actual_qty"] = pd.to_numeric(
      filtered_sp["actual_qty"], errors="coerce"
  ).fillna(0)

  tot_target = sub_si["target_qty"].sum()
  tot_actual = filtered_sp["actual_qty"].sum()

  total_range_days = max((end_date - start_date).days + 1, 1)
  today_date = waktu_wib.date()

  if today_date < start_date:
    passed_days = 1
  elif today_date > end_date:
    passed_days = total_range_days
  else:
    passed_days = max((today_date - start_date).days + 1, 1)

  remaining_days = max(total_range_days - passed_days, 1)
  daily_target_ideal = (
      max(0, int((tot_target - tot_actual) / remaining_days))
      if remaining_days > 0
      else 0
  )
  avg_daily_sales = tot_actual / passed_days if passed_days > 0 else 0
  best_est = int(tot_actual + (avg_daily_sales * remaining_days))

  k1, k2, k3, k4 = st.columns(4)
  with k1:
    st.metric("🎯 Target Periode", f"{tot_target:,.0f} Pcs")
  with k2:
    st.metric("⚡ Target Harian Ideal", f"{daily_target_ideal:,.0f} Pcs/Hari")
  with k3:
    st.metric("📦 Actual (Filter Tanggal)", f"{tot_actual:,.0f} Pcs")
  with k4:
    st.metric("🔮 Best Estimasi Akhir", f"{best_est:,.0f} Pcs")

  st.markdown("---")
  st.subheader("📈 Grafik Fluktuasi Penjualan Harian")

  if "updated_at_dt" in filtered_sp.columns and not filtered_sp.empty:
    daily_trend = (
        filtered_sp.groupby("updated_at_dt")["actual_qty"]
        .sum()
        .reset_index()
        .sort_values(by="updated_at_dt")
    )
    daily_trend["updated_at_str"] = daily_trend["updated_at_dt"].astype(str)
  else:
    daily_trend = pd.DataFrame({
        "updated_at_str": [f"Hari {i+1}" for i in range(total_range_days)],
        "actual_qty": [0] * total_range_days,
    })

  fig_trend = go.Figure()
  fig_trend.add_trace(
      go.Scatter(
          x=daily_trend["updated_at_str"],
          y=daily_trend["actual_qty"],
          mode="lines+markers",
          name="Penjualan Harian",
          line=dict(color="#00f2fe", width=3),
      )
  )
  fig_trend.add_trace(
      go.Scatter(
          x=daily_trend["updated_at_str"],
          y=[daily_target_ideal] * len(daily_trend),
          mode="lines",
          name="Target Harian Ideal",
          line=dict(color="#ff2a6d", dash="dash", width=2),
      )
  )
  fig_trend.update_layout(
      height=340,
      paper_bgcolor="rgba(0,0,0,0)",
      plot_bgcolor="rgba(0,0,0,0)",
      font=dict(color="#ffffff"),
      margin=dict(l=10, r=10, t=10, b=10),
  )
  st.plotly_chart(fig_trend, use_container_width=True)

  st.markdown("---")
  st.subheader("📊 Analisis Detil Growth & Disgrowth Produk")

  item_sales = (
      filtered_sp.groupby(["item_id", "item_name"])["actual_qty"]
      .sum()
      .reset_index()
      if not filtered_sp.empty
      else pd.DataFrame(columns=["item_id", "item_name", "actual_qty"])
  )
  merged_item_analysis = pd.merge(
      sub_si[["item_id", "item_name", "target_qty"]],
      item_sales[["item_id", "actual_qty"]],
      on="item_id",
      how="left",
  )
  merged_item_analysis["actual_qty"] = merged_item_analysis[
      "actual_qty"
  ].fillna(0)
  merged_item_analysis["gap"] = (
      merged_item_analysis["target_qty"] - merged_item_analysis["actual_qty"]
  )
  merged_item_analysis["ach"] = merged_item_analysis.apply(
      lambda r: (r["actual_qty"] / r["target_qty"] * 100)
      if r["target_qty"] > 0
      else 0,
      axis=1,
  )

  col_g, col_d = st.columns(2)
  top_growth = merged_item_analysis.sort_values(
      by="actual_qty", ascending=False
  ).head(3)
  top_disgrowth = merged_item_analysis.sort_values(
      by="gap", ascending=False
  ).head(3)

  with col_g:
    st.markdown(
        '<div style="background: #080c14; border: 1.5px solid #00ff9d;'
        ' border-left: 6px solid #00ff9d; border-radius: 10px; padding: 16px;'
        ' margin-bottom: 12px;"><h4 style="color: #00ff9d; margin: 0;">🔥 TOP 3'
        " ITEM GROWTH</h4></div>",
        unsafe_allow_html=True,
    )
    for _, r in top_growth.iterrows():
      st.success(
          f"**{r['item_name']}** — Terjual: **{r['actual_qty']:,.0f} Pcs** (Ach:"
          f" **{r['ach']:.1f}%**)"
      )

  with col_d:
    st.markdown(
        '<div style="background: #080c14; border: 1.5px solid #ff2a6d;'
        ' border-left: 6px solid #ff2a6d; border-radius: 10px; padding: 16px;'
        ' margin-bottom: 12px;"><h4 style="color: #ff2a6d; margin: 0;">⚠️ TOP 3'
        " ITEM DISGROWTH</h4></div>",
        unsafe_allow_html=True,
    )
    for _, r in top_disgrowth.iterrows():
      st.error(
          f"**{r['item_name']}** — Sisa Gap: **{max(0, r['gap']):,.0f} Pcs**"
          f" (Ach: **{r['ach']:.1f}%**)"
      )

# --- TAB 06: INPUT & RESET DATA ---
elif selected_tab == "06 · Input & Reset Data":
  st.markdown(
      "<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>✏️"
      " Kelola & Input Data Penjualan</h2>",
      unsafe_allow_html=True,
  )

  current_user = st.session_state.get("username", "visitor")
  user_lower = str(current_user).lower()

  is_admin = any(
      x in user_lower for x in ["admin", "chief", "cos", "lavitality"]
  )
  is_visitor = "visitor" in user_lower

  periods_df = (
      st.session_state.periods_df.copy()
      if "periods_df" in st.session_state
      else pd.DataFrame()
  )
  si_df = (
      st.session_state.sales_item_df.copy()
      if "sales_item_df" in st.session_state
      else pd.DataFrame()
  )
  sp_df = (
      st.session_state.sales_person_df.copy()
      if "sales_person_df" in st.session_state
      else pd.DataFrame()
  )
  person_df = (
      st.session_state.person_df.copy()
      if "person_df" in st.session_state
      else pd.DataFrame()
  )

  tab_in1, tab_in2, tab_in3, tab_in4 = st.tabs([
      "⚡ Multi Input Sales Personil",
      "🎯 Input Sales PPS",
      "✏️ Edit Sales Personil",
      "🗑️ Hapus & Reset Sales",
  ])

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

  # SUB TAB 1: MULTI INPUT SALES
  with tab_in1:
    st.markdown(
        "<h4 style='color: #00ff88;'>⚡ Multi Input Sales Personil</h4>",
        unsafe_allow_html=True,
    )
    if is_visitor:
      st.error(
          "🔒 **Akses Ditolak!** Akun **Visitor** hanya memiliki akses membaca"
          " data (read-only)."
      )
    else:
      m_period_name = st.selectbox(
          "Pilih Periode Transaksi", list(periods_dict.keys()), key="multi_period"
      )
      m_p_id = periods_dict[m_period_name]
      p_start, p_end = get_period_date_bounds(m_p_id)

      today_val = waktu_wib.date()
      default_val_m = (
          p_start
          if today_val < p_start
          else (p_end if today_val > p_end else today_val)
      )

      m_date = st.date_input(
          f"Tanggal Transaksi (Batas Periode: {p_start.strftime('%d/%m/%Y')} s/d"
          f" {p_end.strftime('%d/%m/%Y')})",
          value=default_val_m,
          min_value=p_start,
          max_value=p_end,
          key="multi_date",
      )

      all_personnel = (
          person_df["person_name"].dropna().unique().tolist()
          if not person_df.empty and "person_name" in person_df.columns
          else [current_user]
      )

      if is_admin:
        m_person = st.selectbox(
            "Pilih Nama Personil / Staf", all_personnel, key="multi_person"
        )
      else:
        m_person = current_user
        st.info(
            f"👤 Penginputan dikunci untuk akun pengguna aktif: **{current_user}**"
        )

      if "items_df" in st.session_state and not st.session_state.items_df.empty:
        local_items_df = st.session_state.items_df.copy()
      else:
        local_items_df = (
            items_df.copy()
            if "items_df" in locals() and not items_df.empty
            else pd.DataFrame()
        )

      if not local_items_df.empty and "period_id" in local_items_df.columns:
        cleaned_df_period = (
            local_items_df["period_id"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )
        cleaned_target_id = re.sub(r"\.0$", "", str(m_p_id)).strip()
        filtered_items_df = local_items_df[
            cleaned_df_period == cleaned_target_id
        ]
      else:
        filtered_items_df = pd.DataFrame()

      items_list = (
          filtered_items_df[["item_id", "item_name"]]
          .drop_duplicates()
          .to_dict("records")
          if not filtered_items_df.empty
          and all(
              col in filtered_items_df.columns for col in ["item_id", "item_name"]
          )
          else []
      )

      if not items_list:
        st.warning(
            f"⚠️ Tidak ada daftar item produk yang terdaftar pada periode"
            f" **{m_period_name}** (ID: {m_p_id}). Pastikan sheet"
            f" `MASTER_ITEM` sudah diisi kolom `period_id` dengan nilai yang"
            f" sesuai."
        )
      else:
        st.markdown("---")
        with st.form(key=f"form_multi_input_{m_p_id}"):
          st.markdown(
              "##### 📦 Masukkan Jumlah Qty Penjualan Masing-Masing Produk:"
          )
          multi_input_values = {}
          col_m1, col_m2 = st.columns(2)

          for idx, item in enumerate(items_list):
            target_col = col_m1 if (idx % 2 == 0) else col_m2
            item_id_str, item_name_str = str(item["item_id"]), str(
                item["item_name"]
            )
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

          existing_df = st.session_state.sales_person_df
          current_max_id = 0
          if not existing_df.empty and "record_id" in existing_df.columns:
            numeric_ids = (
                existing_df["record_id"]
                .astype(str)
                .str.extract(r"(\d+)")[0]
                .dropna()
            )
            if not numeric_ids.empty:
              current_max_id = numeric_ids.astype(int).max()

          new_rows, inserted_count = [], 0
          for item_id, item_data in multi_input_values.items():
            if item_data["qty"] > 0:
              current_max_id += 1
              new_rows.append({
                  "record_id": f"SP{current_max_id:05d}",
                  "period_id": str(m_p_id),
                  "item_id": str(item_id),
                  "item_name": str(item_data["item_name"]),
                  "person_id": str(person_id_val),
                  "person_name": str(m_person),
                  "actual_qty": int(item_data["qty"]),
                  "updated_at": str(m_date),
              })
              inserted_count += 1

          if inserted_count > 0:
            try:
              with st.spinner("⏳ Menyimpan data ke Spreadsheet..."):
                new_df = pd.DataFrame(new_rows)
                st.session_state.sales_person_df = pd.concat(
                    [st.session_state.sales_person_df, new_df],
                    ignore_index=True,
                )
                sync_store_sales_from_personnel()
                save_database(
                    st.session_state.sales_item_df,
                    st.session_state.sales_person_df,
                    st.session_state.sales_pps_df,
                    st.session_state.sales_store_df,
                )
              show_success_popup(
                  inserted_count, m_person, m_date.strftime("%d/%m/%Y")
              )
            except Exception as e:
              st.error(f"❌ Terjadi kesalahan penyimpanan: {str(e)}")
          else:
            st.warning("⚠️ Tidak ada Qty produk yang diisi (semua bernilai 0).")

  # SUB TAB 2: INPUT SALES PPS (Mode Uji Coba Tanpa Periode)
  with tab_in2:
    st.markdown(
        "<h4 style='color: #00ff88;'>🎯 Form Input Penjualan & Kinerja"
        " PPS</h4>",
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
            "✅ **Data Sales PPS** berhasil disimpan secara permanen ke"
            " database!"
        )
        st.markdown(f"""
            * **Staf / Personil:** `{staff_val}`
            * **Kasir:** `{kasir_val}`
            * **Tanggal:** `{date_str}`
            * **Syarat PWP:** `{syarat_pwp_val}` | **Redeem PWP:** `{redeem_pwp_val}`
            * **Status:** Synchronized to Google Sheets ✅
            """)
        if st.button(
            "👍 Oke, Lanjutkan / Tutup",
            use_container_width=True,
            key="btn_close_pps_dialog",
        ):
          st.rerun()

      pps_p_id = "UJI_COBA_PPS"

      all_personnel = (
          person_df["person_name"].dropna().unique().tolist()
          if not person_df.empty and "person_name" in person_df.columns
          else [current_user]
      )

      with st.form(key="form_input_pps_trial"):
        st.markdown(
            "##### 📋 Masukkan Detail Transaksi & Kinerja Program PPS:"
        )
        col_p1, col_p2 = st.columns(2)

        with col_p1:
          shift_personil = st.selectbox(
              "Shift Personil",
              ["Shift 1", "Shift 2", "Shift 3", "Full Shift"],
              key="pps_shift",
          )
          if is_admin:
            staff_name = st.selectbox(
                "Nama Staf", all_personnel, key="pps_staff"
            )
          else:
            staff_name = current_user
            st.info(f"👤 Staf Input: **{current_user}**")

        with col_p2:
          kasir_name = st.selectbox(
              "Nama Kasir", all_personnel, key="pps_kasir"
          )
          tanggal_pps = st.date_input(
              "Tanggal Input PPS", value=waktu_wib.date(), key="pps_date"
          )

        st.markdown("---")
        st.markdown("##### 🛒 Detail 7 Kolom Kinerja PPS:")

        col_q1, col_q2, col_q3 = st.columns(3)

        with col_q1:
          syarat_pwp = st.number_input(
              "Syarat PWP", min_value=0, step=1, value=0, key="pps_syarat_pwp"
          )
          redeem_pwp = st.number_input(
              "Redeem PWP", min_value=0, step=1, value=0, key="pps_redeem_pwp"
          )

        with col_q2:
          qty_pwp = st.number_input(
              "Qty PWP", min_value=0, step=1, value=0, key="pps_qty_pwp"
          )
          qty_sg = st.number_input(
              "Qty SG (Serba Gratis)",
              min_value=0,
              step=1,
              value=0,
              key="pps_qty_sg",
          )

        with col_q3:
          syarat_sueger = st.number_input(
              "Syarat Sueger",
              min_value=0,
              step=1,
              value=0,
              key="pps_syarat_sueger",
          )
          redeem_sueger = st.number_input(
              "Redeem Sueger",
              min_value=0,
              step=1,
              value=0,
              key="pps_redeem_sueger",
          )

        st.markdown("")
        cemilan_ceban = st.number_input(
            "Cemilan Ceban", min_value=0, step=1, value=0, key="pps_cemilan_ceban"
        )

        st.markdown("---")
        btn_save_pps = st.form_submit_button(
            "💾 Simpan Data Sales PPS (Uji Coba)", use_container_width=True
        )

      if btn_save_pps:
        existing_pps_df = st.session_state.get(
            "sales_pps_df", pd.DataFrame()
        )
        current_max_pps_id = 0
        if not existing_pps_df.empty and "record_id" in existing_pps_df.columns:
          numeric_ids = (
              existing_pps_df["record_id"]
              .astype(str)
              .str.extract(r"(\d+)")[0]
              .dropna()
          )
          if not numeric_ids.empty:
            current_max_pps_id = numeric_ids.astype(int).max()

        current_max_pps_id += 1

        new_pps_record = {
            "record_id": f"PPS{current_max_pps_id:05d}",
            "period_id": str(pps_p_id),
            "shift_personil": str(shift_personil),
            "staff_name": str(staff_name),
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
          with st.spinner("⏳ Menyimpan data PPS ke Spreadsheet..."):
            new_pps_df = pd.DataFrame([new_pps_record])
            if "sales_pps_df" not in st.session_state:
              st.session_state.sales_pps_df = pd.DataFrame()

            st.session_state.sales_pps_df = pd.concat(
                [st.session_state.sales_pps_df, new_pps_df], ignore_index=True
            )

            save_database(
                st.session_state.sales_item_df,
                st.session_state.sales_person_df,
                st.session_state.sales_pps_df,
                st.session_state.sales_store_df,
            )

          show_success_pps_dialog(
              staff_name,
              kasir_name,
              tanggal_pps.strftime("%d/%m/%Y"),
              syarat_pwp,
              redeem_pwp,
          )
        except Exception as e:
          st.error(f"❌ Gagal menyimpan data PPS: {str(e)}")

  # SUB TAB 3: EDIT SALES PERSONIL
  with tab_in3:
    st.markdown(
        "<h4 style='color: #38bdf8;'>✏️ Edit Transaksi Sales (Koreksi"
        " Input)</h4>",
        unsafe_allow_html=True,
    )
    if not is_admin:
      st.error(
          "🔒 Akses Ditolak! Fitur edit transaksi ini hanya dapat diakses oleh"
          " akun Admin / COS."
      )
    else:
      e_period_name = st.selectbox(
          "Pilih Periode", list(periods_dict.keys()), key="edit_period"
      )
      e_p_id = periods_dict[e_period_name]
      p_start, p_end = get_period_date_bounds(e_p_id)

      sp_sub = (
          sp_df[sp_df["period_id"] == e_p_id].copy()
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

  # SUB TAB 4: HAPUS & RESET
  with tab_in4:
    st.markdown(
        "<h4 style='color: #38bdf8;'>🗑️ Hapus Transaksi / Reset Sales"
        " Personil</h4>",
        unsafe_allow_html=True,
    )
    if not is_admin:
      st.error(
          "🔒 Akses Ditolak! Fitur hapus/reset transaksi hanya dapat dilakukan"
          " oleh akun Admin / COS."
      )
    else:
      d_period_name = st.selectbox(
          "Pilih Periode", list(periods_dict.keys()), key="del_period"
      )
      d_p_id = periods_dict[d_period_name]

      sp_del_sub = (
          sp_df[sp_df["period_id"] == d_p_id].copy()
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
                        st.session_state.sales_person_df["period_id"]
                        == d_p_id
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
                        st.session_state.sales_person_df["period_id"]
                        == d_p_id
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
elif selected_tab == "⚙️ Master Data & Pengaturan":
  st.markdown(
      "<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>⚙️"
      " Master Data & Pengaturan Sistem</h2>",
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

  tab_m1, tab_m2, tab_m3, tab_m4, tab_m5 = st.tabs([
      "➕ Penambahan Item & Target",
      "⚙️ Pengaturan Item",
      "📅 Pengaturan Periode",
      "🎯 Input & Master PPS/Sueger",
      "📊 Master Status & Summary",
  ])

  # SUB TAB 1: PENAMBAHAN ITEM & TARGET PER PERIODE
  with tab_m1:
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
        
        # Kolom tambahan sesuai struktur baru Google Sheets
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
            # 1. Update MASTER_ITEM dengan kolom lengkap
            if "items_df" not in st.session_state or st.session_state.items_df is None:
              st.session_state.items_df = pd.DataFrame(columns=["period_id", "item_id", "item_name", "active", "category"])
            
            m_items = st.session_state.items_df.copy()
            
            # Pastikan semua kolom tersedia
            for col in ["period_id", "item_id", "item_name", "active", "category"]:
              if col not in m_items.columns:
                m_items[col] = ""

            # Cek duplikasi berdasarkan period_id dan item_id
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

            # 2. Update SALES_ITEM_DF
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

            st.toast(f"✅ Produk {new_item_name} berhasil disimpan!", icon="🎉")
            time.sleep(1.5)
            st.rerun()
          except Exception as e:
            st.error(f"❌ Gagal menambahkan produk: {e}")

  # SUB TAB 2: PENGATURAN ITEM (PSM)
  with tab_m2:
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
            st.toast("✅ Perubahan item berhasil disimpan!", icon="💾")
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
          st.toast("⚠️ Item berhasil dihapus dari periode.", icon="🗑️")
          time.sleep(1.5)
          st.rerun()

  # SUB TAB 3: PENGATURAN PERIODE (PSM)
  with tab_m3:
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
            st.toast(f"✅ Periode {new_p_name} berhasil ditambahkan!", icon="🎉")
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
          st.toast("✅ Periode berhasil diperbarui!", icon="💾")
          time.sleep(1.5)
          st.rerun()

  # SUB TAB 4: INPUT & MASTER PPS & SUEGER
  with tab_m4:
    st.markdown(
        "<h4 style='color: #c084fc;'>🎯 Input & Pengaturan Periode PPS &"
        " Sueger</h4>",
        unsafe_allow_html=True,
    )

    if "sales_pps_df" not in st.session_state:
      st.session_state.sales_pps_df = pd.DataFrame(columns=[
          "jenis_program",
          "period_id",
          "start_date",
          "end_date",
          "promo_name",
          "target_promo",
          "target_kasir",
      ])

    sub_pps1, sub_pps2, sub_pps3 = st.tabs([
        "➕ Tambah Program",
        "✏️ Edit & Hapus Program",
        "📊 Monitoring PPS & Sueger",
    ])

    with sub_pps1:
      with st.form("form_add_pps_sueger"):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
          jenis_program = st.selectbox(
              "Pilih Jenis Program", ["PPS", "Sueger"], key="pps_jenis"
          )
          pps_id = (
              st.text_input(
                  "ID Periode / Program", placeholder="Contoh: PPS01 atau SGR01"
              )
              .strip()
              .upper()
          )
          pps_nama_promo = st.text_input(
              "Nama Promo", placeholder="Contoh: PROMO HEMAT PPS MARET"
          ).strip()
        with col_p2:
          pps_start_date = st.date_input(
              "Tanggal Mulai Periode", value=waktu_wib.date(), key="pps_start"
          )
          pps_end_date = st.date_input(
              "Tanggal Akhir Periode", value=waktu_wib.date(), key="pps_end"
          )
          pps_target_promo = st.number_input(
              "Target Promo / Toko (Total Pcs)", min_value=0, step=1, value=180
          )

          pps_target_kasir_auto = int(math.ceil(pps_target_promo / 9)) if pps_target_promo > 0 else 0
          st.markdown(f"👤 **Target Per Personil Kasir (Otomatis / 9):** `{pps_target_kasir_auto} Pcs`")

        btn_submit_pps = st.form_submit_button(
            "💾 Simpan ke SALES_PPS", use_container_width=True
        )

        if btn_submit_pps:
          if not pps_id or not pps_nama_promo:
            st.error("⚠️ ID Periode dan Nama Promo wajib diisi!")
          elif pps_start_date > pps_end_date:
            st.error("⚠️ Tanggal mulai tidak boleh melebihi tanggal akhir!")
          else:
            try:
              new_pps_row = pd.DataFrame([{
                  "jenis_program": jenis_program,
                  "period_id": pps_id,
                  "start_date": str(pps_start_date),
                  "end_date": str(pps_end_date),
                  "promo_name": pps_nama_promo,
                  "target_promo": int(pps_target_promo),
                  "target_kasir": int(pps_target_kasir_auto),
              }])
              st.session_state.sales_pps_df = pd.concat(
                  [st.session_state.sales_pps_df, new_pps_row],
                  ignore_index=True,
              )
              save_master_table(
                  "SALES_PPS", st.session_state.sales_pps_df
              )

              st.toast(
                  f"✅ Berhasil menyimpan {jenis_program} - {pps_nama_promo}!",
                  icon="🎉",
              )
              time.sleep(1.2)
              st.rerun()
            except Exception as e:
              st.error(f"❌ Gagal menyimpan data: {e}")

    with sub_pps2:
      pps_df = st.session_state.sales_pps_df.copy()
      
      required_pps_cols = ["jenis_program", "period_id", "promo_name", "start_date", "end_date", "target_promo", "target_kasir"]
      missing_pps_cols = [col for col in required_pps_cols if col not in pps_df.columns]
      
      if pps_df.empty or len(missing_pps_cols) > 0:
        st.info("Belum ada data program PPS/Sueger yang tersimpan atau struktur kolom belum lengkap.")
      else:
        list_promo_options = (
            pps_df["period_id"].astype(str) + " - " + pps_df["promo_name"].astype(str)
        ).tolist()
        selected_edit_opt = st.selectbox(
            "Pilih Program yang Ingin Diubah/Dihapus", list_promo_options
        )

        selected_id = selected_edit_opt.split(" - ")[0]
        row_match = pps_df[pps_df["period_id"].astype(str) == str(selected_id)].iloc[0]

        with st.form("form_edit_pps"):
          col_e1, col_e2 = st.columns(2)
          with col_e1:
            curr_jenis = str(row_match.get("jenis_program", "PPS"))
            idx_jenis = ["PPS", "Sueger"].index(curr_jenis) if curr_jenis in ["PPS", "Sueger"] else 0
            
            edit_jenis = st.selectbox(
                "Jenis Program",
                ["PPS", "Sueger"],
                index=idx_jenis,
            )
            edit_promo_name = st.text_input(
                "Nama Promo", value=str(row_match.get("promo_name", ""))
            )
            try:
              curr_s = pd.to_datetime(row_match["start_date"]).date()
              curr_e = pd.to_datetime(row_match["end_date"]).date()
            except Exception:
              curr_s, curr_e = waktu_wib.date(), waktu_wib.date()

            edit_start = st.date_input("Tanggal Mulai", value=curr_s)
          with col_e2:
            edit_end = st.date_input("Tanggal Akhir", value=curr_e)
            edit_t_promo = st.number_input(
                "Target Promo",
                min_value=0,
                step=1,
                value=int(row_match.get("target_promo", 0)),
            )
            
            edit_t_kasir_auto = int(math.ceil(edit_t_promo / 9)) if edit_t_promo > 0 else 0
            st.markdown(f"👤 **Target Per Personil (Otomatis / 9):** `{edit_t_kasir_auto} Pcs`")

          btn_update_pps = st.form_submit_button(
              "💾 Simpan Perubahan Program", use_container_width=True
          )

          if btn_update_pps:
            try:
              idx_target = st.session_state.sales_pps_df[
                  st.session_state.sales_pps_df["period_id"].astype(str) == str(selected_id)
              ].index
              
              st.session_state.sales_pps_df.loc[
                  idx_target, "jenis_program"
              ] = edit_jenis
              st.session_state.sales_pps_df.loc[
                  idx_target, "promo_name"
              ] = edit_promo_name
              st.session_state.sales_pps_df.loc[
                  idx_target, "start_date"
              ] = str(edit_start)
              st.session_state.sales_pps_df.loc[
                  idx_target, "end_date"
              ] = str(edit_end)
              st.session_state.sales_pps_df.loc[
                  idx_target, "target_promo"
              ] = int(edit_t_promo)
              st.session_state.sales_pps_df.loc[
                  idx_target, "target_kasir"
              ] = int(edit_t_kasir_auto)

              save_master_table(
                  "SALES_PPS", st.session_state.sales_pps_df
              )
              st.toast("✅ Perubahan program berhasil disimpan!", icon="💾")
              time.sleep(1.2)
              st.rerun()
            except Exception as e:
              st.error(f"❌ Gagal memperbarui data: {e}")

        st.markdown("---")
        if st.button(
            f"🗑️ Hapus Program ID: {selected_id}", use_container_width=True
        ):
          st.session_state.sales_pps_df = st.session_state.sales_pps_df[
              st.session_state.sales_pps_df["period_id"].astype(str) != str(selected_id)
          ]
          save_master_table("SALES_PPS", st.session_state.sales_pps_df)
          st.toast("⚠️ Program berhasil dihapus dari sistem.", icon="🗑️")
          time.sleep(1.2)
          st.rerun()

    with sub_pps3:
      if not st.session_state.sales_pps_df.empty:
        st.dataframe(
            st.session_state.sales_pps_df, use_container_width=True
        )
      else:
        st.info("Belum ada data tersimpan di tabel SALES_PPS.")

  # SUB TAB 5: MASTER STATUS & SUMMARY (PSM)
  with tab_m5:
    st.markdown(
        "<h4 style='color: #00ff88;'>📊 Status Sistem & Summary Laporan</h4>",
        unsafe_allow_html=True,
    )

    c_s1, c_s2, c_s3 = st.columns(3)
    with c_s1:
      st.metric("🔗 Koneksi Database", "Terhubung (GSheets)")
    with c_s2:
      st.metric(
          "📦 Total Master Item", f"{len(st.session_state.items_df)} Item"
      )
    with c_s3:
      st.metric(
          "👥 Total Personil", f"{len(st.session_state.person_df)} Staf"
      )

    st.markdown("---")
    st.subheader("📋 Summary Laporan Penjualan")

    mode_summary = st.radio(
        "Pilih Jenis Laporan Summary:",
        ["Harian (Hari Ini)", "Per Periode (Aktif)", "Bulanan (Bulan Ini)"],
        horizontal=True,
    )

    sp_data = st.session_state.sales_person_df.copy()
    if not sp_data.empty and "actual_qty" in sp_data.columns:
      sp_data["actual_qty"] = pd.to_numeric(
          sp_data["actual_qty"], errors="coerce"
      ).fillna(0)
    else:
      sp_data["actual_qty"] = 0

    today_str = waktu_wib.strftime("%Y-%m-%d")
    current_month_str = waktu_wib.strftime("%Y-%m")

    if mode_summary == "Harian (Hari Ini)":
      if "updated_at" in sp_data.columns:
        filtered_sum = sp_data[
            sp_data["updated_at"].astype(str) == today_str
        ]
      else:
        filtered_sum = pd.DataFrame()
      title_sum = f"Laporan Harian ({waktu_wib.strftime('%d %B %Y')})"
    elif mode_summary == "Per Periode (Aktif)":
      if selected_period_id:
        filtered_sum = sp_data[sp_data["period_id"] == selected_period_id]
        title_sum = f"Laporan Periode ({selected_period_name})"
      else:
        filtered_sum = sp_data.copy()
        title_sum = "Laporan Semua Periode"
    else:
      if "updated_at" in sp_data.columns:
        filtered_sum = sp_data[
            sp_data["updated_at"].astype(str).str.startswith(current_month_str)
        ]
      else:
        filtered_sum = pd.DataFrame()
      title_sum = f"Laporan Bulanan ({waktu_wib.strftime('%B %Y')})"

    tot_actual_sum = filtered_sum["actual_qty"].sum()
    st.markdown(
        f"##### 📌 {title_sum} — Total Sales: **{tot_actual_sum:,.0f} Pcs**"
    )

    sum_item = (
        filtered_sum.groupby("item_name")["actual_qty"]
        .sum()
        .reset_index()
        .sort_values(by="actual_qty", ascending=False)
    )
    st.dataframe(sum_item, use_container_width=True)

    st.markdown("---")
    st.subheader("📲 Salin Laporan Format WhatsApp")
    wa_report_text = f"*📊 REPORT PSM TOKO C383*\n"
    wa_report_text += f"*Jenis Laporan:* {title_sum}\n"
    wa_report_text += f"*Waktu Update:* {current_time_str}\n"
    wa_report_text += (
        f"--------------------------------------------------\n"
    )

    for idx, r in sum_item.iterrows():
      wa_report_text += (
          f"• *{r['item_name']}*: {int(r['actual_qty']):,} Pcs\n"
      )

    wa_report_text += (
        f"--------------------------------------------------\n"
    )
    wa_report_text += f"*TOTAL SALES:* *{int(tot_actual_sum):,} Pcs*\n\n"
    wa_report_text += f"_Laporan dihasilkan otomatis oleh System Sales PSM_"

    st.code(wa_report_text, language="markdown")
    st.caption(
        "💡 Klik tombol salin/copy di pojok kanan atas kotak kode di atas"
        " untuk menempelkannya langsung ke WhatsApp!"
    )

    st.markdown("---")
    st.subheader("📥 Export & Download Laporan")
    csv_data = sum_item.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📄 Download Laporan Data (CSV)",
        data=csv_data,
        file_name=f"Report_PSM_{mode_summary.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
