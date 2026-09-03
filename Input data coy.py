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
    page_title="Leafora - Sales & Plant Dashboard",
    page_icon="🌿",
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

    for df in all_dfs:
      if not df.empty and "period_id" in df.columns:
        df["period_id"] = df["period_id"].astype(str).str.strip()

    for df in [items_df, sales_item_df, sales_person_df]:
      if not df.empty and "item_id" in df.columns:
        df["item_id"] = df["item_id"].astype(str).str.strip()

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
    if sales_item_df.empty or sales_person_df.empty:
      st.warning(
          "⚠️ Proses simpan dibatalkan: Data transaksi terdeteksi kosong untuk"
          " mencegah kehilangan data."
      )
      return False

    conn.update(worksheet="SALES_ITEM", data=sales_item_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_PERSONIL", data=sales_person_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_PPS", data=sales_pps_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_STOREPERFORMANCE", data=sales_store_df)

    st.toast(
        "Perubahan transaksi tersimpan permanen di Google Sheets!", icon="🌿"
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

    if sheet_name == "MASTER_ITEM":
      expected_cols = ["period_id", "item_id", "item_name", "active", "category"]
      for col in expected_cols:
        if col not in df_data.columns:
          df_data[col] = ""
      df_data = df_data[expected_cols]

    conn.update(worksheet=sheet_name, data=df_data)
    time.sleep(0.3)
    st.toast(
        f"Master {sheet_name} berhasil diperbarui di Google Sheets!", icon="🌿"
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
# 5. CUSTOM CSS (LEAFORA FOREST THEME)
# ==========================================
st.markdown(
    """
<style>
    /* Background and Primary Font */
    .stApp {
        background-color: #0d1912;
        color: #e2e8f0;
        font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
    }
    
    /* Labels and Headings */
    label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label, label p {
        color: #a7f3d0 !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }
    
    /* Input Fields & Selectboxes */
    div[data-baseweb="input"] input, 
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] span {
        color: #ffffff !important;
        background-color: transparent !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div {
        background-color: #132219 !important;
        border: 1.5px solid #2e4d38 !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="input"] > div:focus-within, 
    div[data-baseweb="select"] > div:focus-within {
        border-color: #4ade80 !important;
        box-shadow: 0 0 10px rgba(74, 222, 128, 0.25) !important;
    }
    div[data-baseweb="input"] svg {
        fill: #4ade80 !important;
    }
    
    /* Metrics Styling */
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #1a2e22 0%, #132219 100%);
        border: 1px solid #2e4d38;
        padding: 18px;
        border-radius: 14px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-weight: 600;
        font-size: 13px;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #4ade80 !important;
        font-weight: 800;
        font-size: 26px;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #111f17;
        border-right: 1px solid #1e3527;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #e2e8f0 !important;
        font-weight: 500;
    }
    
    /* Sidebar Navigation Radio Buttons */
    div[data-testid="stRadio"] input[type="radio"],
    div[data-testid="stRadio"] div[role="radiogroup"] div:has(> input[type="radio"]) {
        display: none !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label {
        background-color: #172a1f;
        border: 1px solid #244230;
        padding: 12px 18px;
        border-radius: 12px;
        margin-bottom: 8px;
        color: #e2e8f0 !important;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.25s ease-in-out;
        display: block;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        border-color: #4ade80;
        background-color: #1e3829;
        transform: translateY(-1px);
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
    div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, #166534 0%, #14532d 100%) !important;
        border: 1px solid #4ade80 !important;
        box-shadow: 0 0 15px rgba(74, 222, 128, 0.3) !important;
        color: #ffffff !important;
    }
    
    /* General Buttons */
    div.stButton > button, div.stFormSubmitButton > button {
        background: linear-gradient(135deg, #166534 0%, #15803d 100%) !important;
        color: #ffffff !important;
        border: 1px solid #4ade80 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        padding: 8px 16px !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
        box-shadow: 0 0 15px rgba(74, 222, 128, 0.4) !important;
        color: #ffffff !important;
    }
    
    /* Logout Button in Sidebar */
    [data-testid="stSidebar"] div[data-testid="stButton"] > button {
        background: transparent !important;
        color: #f87171 !important;
        border: 1px solid #991b1b !important;
    }
    [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background-color: #991b1b !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.4) !important;
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
  st.markdown(
      """
        <style>
            .login-card {
                background-color: #132219;
                padding: 40px 30px;
                border-radius: 20px;
                border: 1px solid #244230;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                text-align: center;
                margin-bottom: 20px;
            }
            .login-brand {
                color: #4ade80;
                font-size: 32px;
                font-weight: 800;
                letter-spacing: -0.5px;
                margin-bottom: 2px;
            }
            .login-subtitle {
                color: #94a3b8;
                font-size: 14px;
                margin-bottom: 0px;
            }
        </style>
        <div class='login-card'>
            <div style="font-size: 40px; margin-bottom: 10px;">🌿</div>
            <div class='login-brand'>Leafora</div>
            <p class='login-subtitle'>Curated Greenery & Sales Management</p>
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
          "Masuk ke Leafora Portal", use_container_width=True
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
          st.toast(f"Selamat Datang di Leafora, {user_info['nama']}!", icon="🌿")
          st.rerun()
        else:
          st.error("Username atau Password salah!")


if not st.session_state.logged_in:
  show_login_page()
  st.stop()

# ==========================================================
# 7. SIDEBAR DASHBOARD
# ==========================================================
username = st.session_state.get("username", "Admin")

st.sidebar.markdown(
    f"""
    <div style='display: flex; align-items: center; gap: 12px; margin-bottom: 20px;'>
        <div style='background-color: #166534; border: 1.5px solid #4ade80; border-radius: 50%; width: 45px; height: 45px; display: flex; align-items: center; justify-content: center; font-size: 22px;'>
            🌿
        </div>
        <div style='display: flex; flex-direction: column;'>
            <span style='color: #94a3b8; font-size: 11px; font-weight: 500;'>Selamat Datang,</span>
            <span style='color: #4ade80; font-size: 14px; font-weight: 700;'>👤 {username}</span>
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    "<hr style='margin: 10px 0; border-color: #1e3527;'>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    "<div style='text-align: center; color: #ffffff; font-size: 22px; font-weight: 800; letter-spacing: 1px;'>LEAFORA</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    "<div style='text-align: center; color: #4ade80; font-size: 12px; font-weight: 600; margin-bottom: 15px;'>Curated Greenery for Modern Homes</div>",
    unsafe_allow_html=True,
)

if st.sidebar.button("🔄 Refresh Data Cache", use_container_width=True):
  st.cache_data.clear()
  for key in list(st.session_state.keys()):
    del st.session_state[key]
  st.rerun()

st.sidebar.markdown("---")

st.sidebar.markdown(
    "<p style='color:#a7f3d0; font-weight:bold; letter-spacing:1px;"
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
    "<p style='color:#a7f3d0; font-weight:bold; letter-spacing:1px;"
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
    "<hr style='margin: 15px 0; border-color: #1e3527;'>",
    unsafe_allow_html=True,
)
if st.sidebar.button("🚪 Keluar / Logout", use_container_width=True):
  st.session_state.logged_in = False
  st.session_state.username = ""
  st.rerun()

# ==========================================
# 8. HEADER UTAMA LEAFORA
# ==========================================
st.markdown(
    f"""
    <div style='background: linear-gradient(135deg, #132219 0%, #1a2e22 100%); padding: 20px 26px; border-radius: 16px; border: 1px solid #244230; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 20px rgba(0,0,0,0.3);'>
        <div>
            <h2 style='margin:0; color:#ffffff; font-size: 24px; font-weight: 800;'>🌱 LEAFORA SALES & PERFORMANCE DASHBOARD</h2>
            <p style='margin:0; color:#4ade80; font-size: 13px;'>Monitored Greenery Sales & Staff Performance Optimization</p>
        </div>
        <div style='text-align: right;'>
            <p style='margin:0; color:#94a3b8; font-size: 11px; font-weight:bold;'>WAKTU REALTIME SISTEM</p>
            <p style='margin:0; color:#a7f3d0; font-size: 14px; font-weight:bold;'>⏰ {current_time_str}</p>
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
    status_color = "#4ade80"
    status_bg = "rgba(74, 222, 128, 0.1)"
    status_icon = "🌿"
    status_title = "PACE PENJUALAN ON TRACK"
    status_desc = (
        f"Pencapaian penjualan (**{tot_ach:.1f}%**) melampaui laju waktu"
        f" berjalan (**{time_factor:.1f}%**). Pertahankan performa toko!"
    )
  else:
    status_color = "#f87171"
    status_bg = "rgba(248, 113, 113, 0.1)"
    status_icon = "⚠️"
    status_title = "PACE PENJUALAN BEHIND TARGET"
    status_desc = (
        f"Pencapaian penjualan (**{tot_ach:.1f}%**) masih di bawah laju waktu"
        f" berjalan (**{time_factor:.1f}%**). Tertinggal sebesar"
        f" **{abs(pace_gap):.1f}%**."
    )

  st.markdown(
      f"""
        <div style="background: {status_bg}; border: 1.5px solid {status_color}; border-left: 6px solid {status_color}; border-radius: 12px; padding: 16px; margin-bottom: 20px;">
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
    gap_color = "#4ade80" if row["gap"] <= 0 else "#f87171"
    ach_color = "#4ade80" if row["ach"] >= time_factor else "#fbbf24"
    table_rows_html += f"""
        <tr style="border-bottom: 1px solid #1e3527;">
            <td style="padding: 12px; color: #ffffff; font-weight: bold; font-size: 13px;">{row['item_name']}</td>
            <td style="padding: 12px; color: #94a3b8; font-size: 13px;">{row['target_qty']:,.0f} Pcs</td>
            <td style="padding: 12px; color: #4ade80; font-weight: bold; font-size: 13px;">{row['actual_qty']:,.0f} Pcs</td>
            <td style="padding: 12px; color: {gap_color}; font-size: 13px;">{row['gap']:,.0f} Pcs</td>
            <td style="padding: 12px; color: {ach_color}; font-weight: bold; font-size: 13px;">{row['ach']:.1f}%</td>
        </tr>
        """

  st.markdown(
      f"""
        <div style="background: #132219; border: 1.5px solid #244230; border-radius: 14px; padding: 12px; max-height: 400px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                <thead>
                    <tr style="border-bottom: 2px solid #2e4d38;">
                        <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">NAMA PRODUK</th>
                        <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">TARGET TOKO</th>
                        <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">ACTUAL PENJUALAN</th>
                        <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">SISA GAP</th>
                        <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">% ACHIEVEMENT</th>
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
      "<p style='color:#a7f3d0; font-weight:bold; font-size:13px;'>🔍 FILTER &"
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
                <div style="background: #132219; border: 1.5px solid #2e4d38; border-radius: 12px; padding: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                    <div style="color: #fbbf24; font-size: 11px; font-weight: bold;">🔥 ITEM TERLARIS</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{top_item['item_name']}</div>
                    <div style="color: #4ade80; font-size: 20px; font-weight: 800;">{top_item['actual_qty']:,.0f} Pcs</div>
                </div>
            """,
          unsafe_allow_html=True,
      )
    with r_col2:
      st.markdown(
          f"""
                <div style="background: #132219; border: 1.5px solid #2e4d38; border-radius: 12px; padding: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                    <div style="color: #f87171; font-size: 11px; font-weight: bold;">📉 ITEM TERENDAH</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{low_item['item_name']}</div>
                    <div style="color: #4ade80; font-size: 20px; font-weight: 800;">{low_item['actual_qty']:,.0f} Pcs</div>
                </div>
            """,
          unsafe_allow_html=True,
      )
    with r_col3:
      st.markdown(
          f"""
                <div style="background: #132219; border: 1.5px solid #2e4d38; border-radius: 12px; padding: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                    <div style="color: #38bdf8; font-size: 11px; font-weight: bold;">📦 VARIASI ITEM</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{len(item_grouped)} Jenis</div>
                    <div style="color: #4ade80; font-size: 20px; font-weight: 800;">{item_grouped['actual_qty'].sum():,.0f} Pcs Total</div>
                </div>
            """,
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)
    table_rows_html = ""
    for _, row in item_grouped.iterrows():
      gap_color = "#4ade80" if row["gap"] >= 0 else "#f87171"
      table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e3527;">
                <td style="padding: 12px; color: #ffffff; font-weight: bold;">{row['item_name']}</td>
                <td style="padding: 12px; color: #94a3b8;">{row['target_qty']:,.0f}</td>
                <td style="padding: 12px; color: #4ade80; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 12px; color: #4ade80; font-weight: bold;">{row['ach']:.1f}%</td>
                <td style="padding: 12px; color: {gap_color}; font-weight: bold;">{row['gap']:,.0f}</td>
            </tr>
            """

    st.markdown(
        f"""
            <div style="background: #132219; border: 1.5px solid #244230; border-radius: 14px; padding: 12px; max-height: 520px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #2e4d38;">
                            <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">NAMA PRODUK</th>
                            <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">TARGET (PCS)</th>
                            <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">ACTUAL SALES</th>
                            <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">% ACH</th>
                            <th style="padding: 10px; color: #a7f3d0; font-size: 11px;">GAP / SELISIH</th>
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
          '<div style="background:#132219; border:1.5px solid #2e4d38;'
          ' border-radius:12px; padding:16px;"><div style="color:#ffffff;'
          ' font-size:11px; font-weight:bold;">TOTAL ACTUAL PERSONIL</div><div'
          ' style="color:#4ade80; font-size:28px;'
          f' font-weight:800;">{tot_actual_personil:,.0f} Pcs</div></div>',
          unsafe_allow_html=True,
      )
    with m2:
      st.markdown(
          '<div style="background:#132219; border:1.5px solid #2e4d38;'
          ' border-radius:12px; padding:16px;"><div style="color:#ffffff;'
          ' font-size:11px; font-weight:bold;">RATA-RATA'
          ' PENJUALAN/STAF</div><div style="color:#4ade80; font-size:28px;'
          f' font-weight:800;">{avg_sales_personil:,.0f} Pcs</div></div>',
          unsafe_allow_html=True,
      )
    with m3:
      st.markdown(
          '<div style="background:#132219; border:1.5px solid #2e4d38;'
          ' border-radius:12px; padding:16px;"><div style="color:#ffffff;'
          ' font-size:11px; font-weight:bold;">TOP PERFORMER</div><div'
          ' style="color:#4ade80; font-size:26px;'
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
                <div style="display: flex; gap: 14px; justify-content: center; align-items: flex-end; margin-bottom: 20px;">
                    <div style="flex: 1; background: #132219; border: 1.5px solid #2e4d38; border-radius: 12px; padding: 12px; text-align: center;">
                        <span style="font-size: 20px;">🥈</span>
                        <div style="color: #94a3b8; font-size: 10px; font-weight: bold;">JUARA 2</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold;">{p2_name}</div>
                        <div style="color: #4ade80; font-size: 16px; font-weight: 800;">{p2_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #1a2e22; border: 2px solid #4ade80; border-radius: 14px; padding: 14px; text-align: center; transform: scale(1.03); box-shadow: 0 0 20px rgba(74, 222, 128, 0.2);">
                        <span style="font-size: 24px;">🥇</span>
                        <div style="color: #fbbf24; font-size: 10px; font-weight: bold;">JUARA 1</div>
                        <div style="color: #ffffff; font-size: 14px; font-weight: bold;">{p1_name}</div>
                        <div style="color: #4ade80; font-size: 18px; font-weight: 800;">{p1_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #132219; border: 1.5px solid #2e4d38; border-radius: 12px; padding: 12px; text-align: center;">
                        <span style="font-size: 20px;">🥉</span>
                        <div style="color: #d97706; font-size: 10px; font-weight: bold;">JUARA 3</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold;">{p3_name}</div>
                        <div style="color: #4ade80; font-size: 16px; font-weight: 800;">{p3_qty:,.0f} Pcs</div>
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
                <tr style="border-bottom: 1px solid #1e3527;">
                    <td style="padding: 12px; color: #ffffff; font-weight: bold;">{row['person_name']}</td>
                    <td style="padding: 12px; color: #4ade80; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                    <td style="padding: 12px; color: #4ade80; font-weight: bold;">{row['pct_contrib']:.1f}%</td>
                </tr>
                """
      st.markdown(
          f"""
                <div style="background: #132219; border: 1.5px solid #244230; border-radius: 12px; padding: 10px; height: {COMPONENT_HEIGHT}px; overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                        <thead>
                            <tr style="border-bottom: 2px solid #2e4d38;">
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
              marker_color="#4ade80",
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
      gap_color = "#4ade80" if row["gap"] <= 0 else "#f87171"
      ach_color = "#4ade80" if row["ach"] >= 100 else "#fbbf24"
      table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e3527;">
                <td style="padding: 10px; color: #ffffff; font-weight: bold;">{row['item_name']}</td>
                <td style="padding: 10px; color: #94a3b8;">{row['target_val']:,.0f}</td>
                <td style="padding: 10px; color: #4ade80; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 10px; color: {gap_color};">{row['gap']:,.0f}</td>
                <td style="padding: 10px; color: {ach_color}; font-weight: bold;">{row['ach']:.1f}%</td>
            </tr>
            """
    st.markdown(
        f"""
            <div style="background: #132219; border: 1.5px solid #244230; border-radius: 12px; padding: 10px; max-height: 380px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #2e4d38;">
                            <th style="padding: 8px; color: #a7f3d0; font-size: 11px;">NAMA ITEM</th>
                            <th style="padding: 8px; color: #a7f3d0; font-size: 11px;">TARGET KASIR</th>
                            <th style="padding: 8px; color: #a7f3d0; font-size: 11px;">ACTUAL</th>
                            <th style="padding: 8px; color: #a7f3d0; font-size: 11px;">GAP</th>
                            <th style="padding: 8px; color: #a7f3d0; font-size: 11px;">% ACH</th>
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
            marker_color="#4ade80",
        )
    )
    fig_p4.add_trace(
        go.Bar(
            y=merged_item_df["item_name"],
            x=merged_item_df["target_val"],
            name="Target Kasir",
            orientation="h",
            marker_color="#334155",
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
          line=dict(color="#4ade80", width=3),
      )
  )
  fig_trend.add_trace(
      go.Scatter(
          x=daily_trend["updated_at_str"],
          y=[daily_target_ideal] * len(daily_trend),
          mode="lines",
          name="Target Harian Ideal",
          line=dict(color="#f87171", dash="dash", width=2),
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
        '<div style="background: #132219; border: 1.5px solid #4ade80;'
        ' border-left: 6px solid #4ade80; border-radius: 12px; padding: 16px;'
        ' margin-bottom: 12px;"><h4 style="color: #4ade80; margin: 0;">🔥 TOP 3'
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
        '<div style="background: #132219; border: 1.5px solid #f87171;'
        ' border-left: 6px solid #f87171; border-radius: 12px; padding: 16px;'
        ' margin-bottom: 12px;"><h4 style="color: #f87171; margin: 0;">⚠️ TOP 3'
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
      "<h2 style='color: #4ade80;'>✏️ Kelola & Input Data Penjualan</h2>",
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
      "✏️ Edit Sales Personil",
      "🗑️ Hapus & Reset Sales",
      "📱 Salin Format WA",
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
        * **Status:** Synchronized to Google Sheets 🌿
        """)
    if st.button("👍 Mantap, Tutup", use_container_width=True):
      st.rerun()

  # SUB TAB 1: MULTI INPUT SALES
  with tab_in1:
    st.subheader("📝 Form Multi Input Sales Personil")
    col_i1, col_i2 = st.columns(2)
    with col_i1:
      input_period_id = st.selectbox(
          "Pilih Periode",
          options=list(periods_dict.values()),
          format_func=lambda x: [
              k for k, v in periods_dict.items() if v == x
          ][0],
      )
    with col_i2:
      person_options = person_df["person_name"].unique().tolist()
      input_person_name = st.selectbox("Pilih Personil", options=person_options)

    p_start, p_end = get_period_date_bounds(input_period_id)
    input_date = st.date_input(
        "Tanggal Transaksi",
        value=min(max(datetime.now().date(), p_start), p_end),
        min_value=p_start,
        max_value=p_end,
    )

    items_in_period = si_df[si_df["period_id"] == input_period_id]

    with st.form("multi_input_form"):
      st.write("Isi jumlah penjualan untuk masing-masing produk:")
      input_qtys = {}
      for _, row in items_in_period.iterrows():
        input_qtys[row["item_id"]] = st.number_input(
            f"{row['item_name']} (ID: {row['item_id']})",
            min_value=0,
            step=1,
            value=0,
        )

      btn_save_multi = st.form_submit_button("💾 Simpan Transaksi Penjualan")

      if btn_save_multi:
        inserted_count = 0
        new_rows = []
        for item_id, qty in input_qtys.items():
          if qty > 0:
            item_name = items_in_period[
                items_in_period["item_id"] == item_id
            ]["item_name"].values[0]
            new_rows.append({
                "period_id": input_period_id,
                "item_id": item_id,
                "item_name": item_name,
                "person_name": input_person_name,
                "actual_qty": qty,
                "updated_at": str(input_date),
            })
            inserted_count += 1

        if inserted_count > 0:
          new_sp_df = pd.concat(
              [st.session_state.sales_person_df, pd.DataFrame(new_rows)],
              ignore_index=True,
          )
          st.session_state.sales_person_df = new_sp_df
          sync_store_sales_from_personnel()
          save_database(
              st.session_state.sales_item_df,
              st.session_state.sales_person_df,
              st.session_state.sales_pps_df,
              st.session_state.sales_store_df,
          )
          show_success_popup(inserted_count, input_person_name, str(input_date))
        else:
          st.warning("Tidak ada kuantitas produk yang diisi (> 0).")

  # SUB TAB 2: EDIT SALES PERSONIL
  with tab_in2:
    st.subheader("✏️ Edit Data Transaksi Sales")
    st.info("Fitur edit memungkinkan Anda mengubah entri data penjualan yang telah diinput.")

  # SUB TAB 3: HAPUS & RESET
  with tab_in3:
    st.subheader("🗑️ Hapus & Reset Data Transaksi")
    st.warning("Hati-hati! Tindakan reset tidak dapat dibatalkan.")

  # SUB TAB 4: SALIN FORMAT WA
  with tab_in4:
    st.subheader("📱 Generator Format WhatsApp")
    st.write("Salin ringkasan pencapaian toko untuk dibagikan ke grup WhatsApp.")

# --- TAB 07: MASTER DATA & PENGATURAN ---
elif selected_tab == "⚙️ Master Data & Pengaturan":
  st.title("⚙️ Master Data & Pengaturan Toko")
  st.write("Kelola Master Item, Master Personil, dan Periode Promosi Toko Leafora.")
