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

# --- FUNGSI PEMBANTU BATAS TANGGAL PERIODE ---
def get_period_date_bounds(p_id):
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
  today = waktu_wib.date()
  return today.replace(day=1), today

# --- INISIALISASI GLOBAL PERIODS_DICT ---
periods_dict = {}
active_periods_df = (
    st.session_state.get("periods_df", pd.DataFrame())
    if not st.session_state.get("periods_df", pd.DataFrame()).empty
    else (
        periode_df
        if "periode_df" in locals() and not periode_df.empty
        else pd.DataFrame()
    )
)

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
# 5. CUSTOM CSS (NEON DARK THEME + TAB FIX)
# ==========================================
st.markdown(
    """
<style>
    .stApp {
        background-color: #0b0f19;
        color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    /* Label Widget Biasa (Kecuali yang di dalam tab) */
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

    /* ========================================================================= */
    /* JURUS PAMUNGKAS: FORCE COLOR TAB STREAMLIT                                */
    /* ========================================================================= */
    
    /* Targetkan seluruh elemen di dalam container tab */
    div[data-baseweb="tab-list"] button {
        background-color: transparent !important;
    }
    
    /* Memaksa warna teks SEMUA tab menjadi terang (#b0c4de) */
    div[data-baseweb="tab-list"] button div[data-testid="stMarkdownContainer"] p {
        color: #b0c4de !important;
        font-weight: 500 !important;
    }

    /* Memaksa warna teks tab yang sedang AKTIF menjadi hijau neon (#00ff88) */
    div[data-baseweb="tab-list"] button[aria-selected="true"] div[data-testid="stMarkdownContainer"] p {
        color: #00ff88 !important;
        font-weight: 700 !important;
    }

    /* Garis bawah/indikator tab aktif */
    div[data-baseweb="tab-highlight"] {
        background-color: #00ff88 !important;
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
    "Menu Utama",
    "📝 Input Data",
    "➕Edit Data (admin only)",
    "⚙️ Master Data & Pengaturan",
]
selected_tab = st.sidebar.radio(
    "", menu_options, label_visibility="collapsed"
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


# =============================================================================
# --- INPUT & RESET DATA ---
# =============================================================================
if selected_tab == "📝 Input Data":
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
    # RENDER CUSTOM RADIO MENU (TERPISAH ANTARA SIDEBAR & KONTEN UTAMA)
    # =========================================================================
    st.markdown("""
    <style>
        /* CSS khusus untuk Sub-Tab (Menu Navigasi Horizontal di Konten Utama) */
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
            font-size: 12px !important; /* Ukuran font disesuaikan agar muat berdampingan */
            white-space: nowrap !important; /* 🚀 Memaksa teks mutlak satu baris */
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

        /* CSS khusus untuk Sidebar agar tetap vertikal rapi dan tidak berantakan */
        section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] {
            flex-direction: column !important;
            gap: 8px !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] > label {
            flex-direction: row !important;
            justify-content: flex-start !important;
            text-align: left !important;
            min-height: auto !important;
            padding: 8px 12px !important;
            white-space: normal !important; /* Kembalikan normal khusus sidebar */
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] input[type="radio"] {
            display: inline-block !important;
        }
    </style>
    """, unsafe_allow_html=True)

    active_sub_tab = st.radio(
        "Pilih Menu Navigasi",
        ["⚡ Multi Input Sales", "🎯 Input Sales PPS", "📱 Salin Format WA"],
        horizontal=True,
        label_visibility="collapsed",
        key="custom_sub_tabs"
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
            tab1_periods_dict = {}

            if not periods_df.empty and all(
                col in periods_df.columns
                for col in ["period_id", "period_name", "start_date", "end_date"]
            ):
                for _, row in periods_df.iterrows():
                    p_id = str(row["period_id"])
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

                        max_allowed_date = p_end + timedelta(days=2)

                        if is_admin:
                            tab1_periods_dict[p_name] = p_id
                        else:
                            if p_start <= today_date <= max_allowed_date:
                                tab1_periods_dict[p_name] = p_id
                    except Exception:
                        continue

            if not tab1_periods_dict and is_admin and not periods_df.empty:
                tab1_periods_dict = {
                    str(row["period_name"]): str(row["period_id"])
                    for _, row in periods_df.iterrows()
                }

            if not tab1_periods_dict:
                st.warning(
                    "⚠️ Tidak ada periode aktif yang sesuai dengan tanggal hari ini ("
                    + today_date.strftime("%d %B %Y")
                    + ") untuk melakukan input penjualan."
                )
            else:
                m_period_name = st.selectbox(
                    "Pilih Periode Transaksi",
                    list(tab1_periods_dict.keys()),
                    key="multi_period",
                )
                m_p_id = tab1_periods_dict[m_period_name]
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
                        f"👤 Penginputan dikunci untuk akun pengguna aktif:"
                        f" **{current_user}**"
                    )

                current_items_df = (
                    items_df
                    if "items_df" in locals() and not items_df.empty
                    else st.session_state.get("items_df", pd.DataFrame())
                )

                if (
                    not current_items_df.empty
                    and "period_id" in current_items_df.columns
                ):
                    cleaned_df_period = (
                        current_items_df["period_id"]
                        .astype(str)
                        .str.replace(r"\.0$", "", regex=True)
                        .str.strip()
                    )
                    cleaned_target_id = re.sub(r"\.0$", "", str(m_p_id)).strip()
                    filtered_items_df = current_items_df[
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
                        col in filtered_items_df.columns
                        for col in ["item_id", "item_name"]
                    )
                    else []
                )

                if not items_list:
                    st.warning(
                        f"⚠️ Tidak ada daftar item produk dari **MASTER_ITEM** yang"
                        f" terdaftar pada periode **{m_period_name}** (ID: {m_p_id})."
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

                        existing_df = st.session_state.get(
                            "sales_person_df", pd.DataFrame()
                        )
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

    # =========================================================================
    # SUB TAB 2: INPUT SALES PPS
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
                staff_val,
                kasir_val,
                date_str,
                matched_pps_id,
                syarat_pwp_val,
                redeem_pwp_val,
            ):
                st.success(
                    "✅ **Data Sales PPS** berhasil disimpan secara permanen ke"
                    " database (SALES_PPS)!"
                )
                st.markdown(f"""
                    * **ID Periode PPS:** `{matched_pps_id}`
                    * **Staf / Personil:** `{staff_val}`
                    * **Kasir:** `{kasir_val}`
                    * **Tanggal:** `{date_str}`
                    * **Syarat PWP:** `{syarat_pwp_val}` | **Redeem PWP:** `{redeem_pwp_val}`
                    * **Status:** Synchronized to SALES_PPS ✅
                    """)
                if st.button(
                    "👍 Oke, Lanjutkan / Tutup",
                    use_container_width=True,
                    key="btn_close_pps_dialog",
                ):
                    st.rerun()

            all_personnel = (
                person_df["person_name"].dropna().unique().tolist()
                if not person_df.empty and "person_name" in person_df.columns
                else [current_user]
            )

            default_staff_idx = (
                all_personnel.index(current_user)
                if current_user in all_personnel
                else 0
            )

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
                    staff_name = st.selectbox(
                        "Nama Staf",
                        all_personnel,
                        index=default_staff_idx,
                        key="pps_staff_dyn",
                    )

                with col_p2:
                    kasir_name = st.selectbox(
                        "Nama Kasir", all_personnel, key="pps_kasir_dyn"
                    )
                    tanggal_pps = st.date_input(
                        "Tanggal Input PPS", value=waktu_wib.date(), key="pps_date_dyn"
                    )

                active_pps_id = "PPS_DEFAULT"
                if not periode_pps_df.empty and all(
                    col in periode_pps_df.columns
                    for col in ["period_id", "start_date", "end_date"]
                ):
                    matched_row = periode_pps_df[
                        (
                            pd.to_datetime(periode_pps_df["start_date"]).dt.date
                            <= tanggal_pps
                        )
                        & (
                            pd.to_datetime(periode_pps_df["end_date"]).dt.date
                            >= tanggal_pps
                        )
                    ]
                    if not matched_row.empty:
                        active_pps_id = str(matched_row.iloc[0]["period_id"])
                        st.info(
                            f"📅 Tanggal `{tanggal_pps.strftime('%d/%m/%Y')}` mendeteksi ID"
                            f" Periode PPS: **{active_pps_id}**"
                        )
                    else:
                        st.warning(
                            f"⚠️ Tanggal tidak ada di `PERIODE_PPS`. Default:"
                            f" `{active_pps_id}`"
                        )

                st.markdown("---")
                st.markdown("##### 🛒 Detail Kolom Kinerja PPS:")

                col_q1, col_q2, col_q3 = st.columns(3)
                with col_q1:
                    syarat_pwp = st.number_input(
                        "Syarat PWP", min_value=0, step=1, value=0, key="pps_syarat_pwp_dyn"
                    )
                    redeem_pwp = st.number_input(
                        "Redeem PWP", min_value=0, step=1, value=0, key="pps_redeem_pwp_dyn"
                    )
                with col_q2:
                    qty_pwp = st.number_input(
                        "Qty PWP", min_value=0, step=1, value=0, key="pps_qty_pwp_dyn"
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
                    "💾 Simpan Data ke SALES_PPS", use_container_width=True
                )

            if btn_save_pps:
                existing_pps_df = st.session_state.get("sales_pps_df", pd.DataFrame())
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
                    "period_id": str(active_pps_id),
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
                    with st.spinner("⏳ Menyimpan data ke sheet SALES_PPS..."):
                        new_pps_df = pd.DataFrame([new_pps_record])
                        if "sales_pps_df" not in st.session_state:
                            st.session_state.sales_pps_df = pd.DataFrame()

                        st.session_state.sales_pps_df = pd.concat(
                            [st.session_state.sales_pps_df, new_pps_df], ignore_index=True
                        )

                        save_master_table("SALES_PPS", st.session_state.sales_pps_df)
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
                        active_pps_id,
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
elif selected_tab == "➕Edit Data (admin only)":
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

# SUB TAB 4: INPUT & PENGATURAN PERIODE PPS & SUEGER (Fokus Hanya ke PERIODE_PPS)
  with tab_m4:
    st.markdown(
        "<h4 style='color: #c084fc;'>🎯 Input & Pengaturan Periode PPS &"
        " Sueger</h4>",
        unsafe_allow_html=True,
    )

    # Inisialisasi State khusus untuk PERIODE_PPS
    if "periode_pps_df" not in st.session_state:
      st.session_state.periode_pps_df = pd.DataFrame(columns=[
          "period_id", "start_date", "end_date", "period_name", "target_total", "status", "actual_qty"
      ])

    sub_sue, sub_pps, sub_edit, sub_mon = st.tabs([
        "➕ Tambah Sueger",
        "➕ Tambah Periode PPS",
        "✏️ Edit & Hapus Program",
        "📊 Monitoring Periode",
    ])

    # ----------------------------------------------------
    # SUB TAB 1: TAMBAH SUEGER (Masuk Khusus ke PERIODE_PPS)
    # ----------------------------------------------------
    with sub_sue:
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
              
              # HANYA DISIMPAN KE PERIODE_PPS (Tidak menyentuh SALES_PPS)
              save_master_table("PERIODE_PPS", st.session_state.periode_pps_df)

              st.toast("✅ Program Sueger berhasil disimpan ke PERIODE_PPS!", icon="🎉")
              time.sleep(1.2)
              st.rerun()
            except Exception as e:
              st.error(f"❌ Gagal menyimpan program Sueger: {e}")

    # ----------------------------------------------------
    # SUB TAB 2: TAMBAH PERIODE PPS (Target & Kasir / 9 Ceil, Masuk PERIODE_PPS)
    # ----------------------------------------------------
    with sub_pps:
      st.markdown("##### 📌 Form Input Periode PPS (Target Fisik & Pembulatan Otomatis)")
      with st.form("form_add_pps_pure_only"):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
          pps_id = st.text_input("ID Periode PPS", placeholder="Contoh: PPS01").strip().upper()
          pps_name = st.text_input("Nama Periode PPS", placeholder="Contoh: PPS MARET").strip()
          pps_target = st.number_input("Target Total (Pcs)", min_value=0, step=1, value=180)
        with col_p2:
          pps_start = st.date_input("Tanggal Mulai", value=waktu_wib.date(), key="pps_start_only")
          pps_end = st.date_input("Tanggal Akhir", value=waktu_wib.date(), key="pps_end_only")

          pps_target_kasir_auto = int(math.ceil(pps_target / 9)) if pps_target > 0 else 0
          st.markdown(f"👤 **Target Otomatis Per Personil (Target Total / 9):** `{pps_target_kasir_auto} Pcs`")
          st.caption("*(Nilai desimal dibulatkan ke atas secara otomatis dan disimpan ke PERIODE_PPS)*")

        btn_submit_pps_exc = st.form_submit_button("💾 Simpan Periode PPS", use_container_width=True)

        if btn_submit_pps_exc:
          if not pps_id or not pps_name:
            st.error("⚠️ ID Periode dan Nama Periode wajib diisi!")
          elif pps_start > pps_end:
            st.error("⚠️ Tanggal mulai tidak boleh melebihi tanggal akhir!")
          else:
            try:
              new_pps_row = pd.DataFrame([{
                  "period_id": pps_id,
                  "start_date": str(pps_start),
                  "end_date": str(pps_end),
                  "period_name": pps_name,
                  "target_total": int(pps_target),
                  "status": "Aktif",
                  "actual_qty": 0
              }])

              st.session_state.periode_pps_df = pd.concat(
                  [st.session_state.periode_pps_df, new_pps_row], ignore_index=True
              )
              
              # HANYA DISIMPAN KE PERIODE_PPS
              save_master_table("PERIODE_PPS", st.session_state.periode_pps_df)

              st.toast("✅ Periode PPS berhasil disimpan ke PERIODE_PPS!", icon="🎉")
              time.sleep(1.2)
              st.rerun()
            except Exception as e:
              st.error(f"❌ Gagal menyimpan Periode PPS: {e}")

    # ----------------------------------------------------
    # SUB TAB 3: EDIT & HAPUS PROGRAM (Khusus PERIODE_PPS)
    # ----------------------------------------------------
    with sub_edit:
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

    # ----------------------------------------------------
    # SUB TAB 4: MONITORING PERIODE (100% Berdasarkan PERIODE_PPS)
    # ----------------------------------------------------
    with sub_mon:
      st.markdown("##### 📊 Monitoring Data PERIODE_PPS")
      
      if not st.session_state.periode_pps_df.empty:
        st.dataframe(st.session_state.periode_pps_df, use_container_width=True)
      else:
        st.info("Belum ada data periode yang tercatat di tabel `PERIODE_PPS`.")

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
