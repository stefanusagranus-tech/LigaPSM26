import importlib
from importlib import metadata
import math
import re
import time
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
    page_icon="📊",
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
    periods_df = conn.read(worksheet="PERIODE", ttl=0)
    time.sleep(0.2)
    items_df = conn.read(worksheet="MASTER_ITEM", ttl=0)
    time.sleep(0.2)
    person_df = conn.read(worksheet="MASTER_PERSONIL", ttl=0)
    time.sleep(0.2)
    sales_item_df = conn.read(worksheet="SALES_ITEM", ttl=0)
    time.sleep(0.2)
    sales_person_df = conn.read(worksheet="SALES_PERSONIL", ttl=0)
    time.sleep(0.2)

    periods_pps_df = conn.read(worksheet="PERIODE_PPS", ttl=0)
    time.sleep(0.2)
    sales_pps_df = conn.read(worksheet="SALES_PPS", ttl=0)
    time.sleep(0.2)

    periods_store_df = conn.read(worksheet="PERIODE_STOREPERFORMANCE", ttl=0)
    time.sleep(0.2)
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
  try:
    if sales_item_df.empty or sales_person_df.empty:
      st.warning(
          "⚠️ Proses simpan dibatalkan: Data transaksi terdeteksi kosong untuk"
          " mencegah kehilangan data."
      )
      return False

    conn.update(worksheet="SALES_ITEM", data=sales_item_df)
    time.sleep(0.3)
    conn.update(worksheet="SALES_PERSONIL", data=sales_person_df)
    time.sleep(0.3)
    conn.update(worksheet="SALES_PPS", data=sales_pps_df)
    time.sleep(0.3)
    conn.update(worksheet="SALES_STOREPERFORMANCE", data=sales_store_df)

    st.toast("Perubahan transaksi tersimpan di Google Sheets!", icon="✅")
    return True
  except Exception as e:
    st.error(f"❌ Gagal menyimpan data ke Google Sheets: {e}")
    return False


def save_master_table(sheet_name, df_data):
  try:
    if df_data.empty:
      st.warning(f"⚠️ Master {sheet_name} batal disimpan karena data kosong.")
      return False

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
    st.toast(
        f"Master {sheet_name} berhasil diperbarui di Google Sheets!", icon="✅"
    )
    return True
  except Exception as e:
    st.error(f"❌ Gagal update master {sheet_name}: {e}")
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

# ==========================================
# 5. CUSTOM CSS (NEON DARK THEME)
# ==========================================
st.markdown(
    """
<style>
    .stApp {
        background-color: #080d1a;
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
        background-color: #0d1424 !important;
        border: 1.5px solid #00f0ff !important;
        border-radius: 8px !important;
    }
    
    /* Modern Dashboard Hero & Metric Card Styling */
    .home-hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 24px 30px;
        border-radius: 16px;
        border: 1px solid rgba(56, 189, 248, 0.3);
        box-shadow: 0 10px 25px -5px rgba(0, 240, 255, 0.15);
        margin-bottom: 25px;
    }
    .metric-card-home {
        background: linear-gradient(135deg, #0d1527 0%, #152035 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card-home:hover {
        transform: translateY(-2px);
        border-color: #00f0ff;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 6px;
    }
    .metric-val {
        color: #00f0ff;
        font-size: 28px;
        font-weight: 800;
        text-shadow: 0 0 12px rgba(0, 240, 255, 0.4);
    }
    .metric-sub {
        color: #38bdf8;
        font-size: 12px;
        margin-top: 4px;
        font-weight: 500;
    }

    [data-testid="stSidebar"] {
        background-color: #0b1120;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: 600;
    }
    div[data-testid="stRadio"] input[type="radio"] {
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
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
    div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: 1px solid #38bdf8 !important;
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.6) !important;
        color: #ffffff !important;
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
    "HOME",
    "DASHBOARD UTAMA",
    "Input & Reset Data",
    "⚙️ Master Data & Pengaturan",
]
selected_tab = st.sidebar.radio("", menu_options, label_visibility="collapsed")
st.sidebar.markdown("---")

st.sidebar.markdown(
    "<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px;"
    " margin-bottom:6px;'>🌟 FILTER PERIODE</p>",
    unsafe_allow_html=True,
)

periods_df = st.session_state.periods_df
if not periods_df.empty:
  periods_dict = {
      row["period_name"]: row["period_id"] for _, row in periods_df.iterrows()
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

# --- TAB 01: HOME (HALAMAN UTAMA INTERAKTIF & MODERN) ---
if selected_tab == "HOME":
  # Hero Section Halaman Utama
  st.markdown(
      f"""
        <div class="home-hero">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                <div>
                    <h2 style="color:#ffffff; margin:0; font-size:26px; font-weight:800;">🚀 Ringkasan Performa Penjualan PSM Toko</h2>
                    <p style="color:#38bdf8; margin:4px 0 0 0; font-size:14px;">Pemantauan Real-time Pencapaian Target Toko & Individual Personil</p>
                </div>
                <div style="background:rgba(0, 240, 255, 0.1); border:1px solid #00f0ff; padding:8px 16px; border-radius:20px;">
                    <span style="color:#00f0ff; font-weight:700; font-size:13px;">📌 Filter Aktif: {selected_period_name}</span>
                </div>
            </div>
        </div>
    """,
      unsafe_allow_html=True,
  )

  # Menyiapkan Data Penjualan Item
  si_df = (
      st.session_state.sales_item_df.copy()
      if "sales_item_df" in st.session_state
      else pd.DataFrame()
  )

  if selected_period_id and not si_df.empty and "period_id" in si_df.columns:
    si_df = si_df[si_df["period_id"] == selected_period_id]

  if not si_df.empty:
    si_df["target_qty"] = pd.to_numeric(
        si_df.get("target_qty", 0), errors="coerce"
    ).fillna(0)
    si_df["actual_qty"] = pd.to_numeric(
        si_df.get("actual_qty", 0), errors="coerce"
    ).fillna(0)
    total_target = si_df["target_qty"].sum()
    total_actual = si_df["actual_qty"].sum()
    overall_pct = (
        (total_actual / total_target * 100) if total_target > 0 else 0.0
    )
    total_items = len(si_df)
  else:
    total_target, total_actual, overall_pct, total_items = 0, 0, 0.0, 0

  # 1. Empat Kartu Metrik Utama (Metric Cards)
  c1, c2, c3, c4 = st.columns(4)

  with c1:
    st.markdown(
        f"""
            <div class="metric-card-home">
                <div class="metric-title">🎯 Total Target Toko</div>
                <div class="metric-val">{total_target:,.0f} <span style="font-size:16px;">Pcs</span></div>
                <div class="metric-sub">Alokasi seluruh produk</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

  with c2:
    st.markdown(
        f"""
            <div class="metric-card-home">
                <div class="metric-title">📦 Real Penjualan</div>
                <div class="metric-val" style="color:#00ff88;">{total_actual:,.0f} <span style="font-size:16px;">Pcs</span></div>
                <div class="metric-sub">Terjual secara akumulatif</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

  with c3:
    color_pct = "#00ff88" if overall_pct >= 100 else "#38bdf8"
    st.markdown(
        f"""
            <div class="metric-card-home">
                <div class="metric-title">📈 Achievement Overall</div>
                <div class="metric-val" style="color:{color_pct};">{overall_pct:.1f}%</div>
                <div class="metric-sub">Rasio Real vs Target</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

  with c4:
    st.markdown(
        f"""
            <div class="metric-card-home">
                <div class="metric-title">🏷️ Kategori Produk</div>
                <div class="metric-val" style="color:#f59e0b;">{total_items} <span style="font-size:16px;">Item</span></div>
                <div class="metric-sub">Produk PSM aktif</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

  st.markdown("<br>", unsafe_allow_html=True)

  # 2. Grafik Interaktif Visualisasi Performa
  if not si_df.empty:
    col_g1, col_g2 = st.columns([1.6, 1])

    with col_g1:
      st.markdown(
          "<h4 style='color:#00f0ff;'>📊 Perbandingan Target vs Realisasi Sales"
          " Per Produk</h4>",
          unsafe_allow_html=True,
      )

      fig_bar = go.Figure()
      fig_bar.add_trace(
          go.Bar(
              x=si_df["item_name"],
              y=si_df["target_qty"],
              name="Target Toko",
              marker_color="#3b82f6",
              opacity=0.85,
          )
      )
      fig_bar.add_trace(
          go.Bar(
              x=si_df["item_name"],
              y=si_df["actual_qty"],
              name="Real Sales",
              marker_color="#00ff88",
          )
      )

      fig_bar.update_layout(
          barmode="group",
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          font=dict(color="#ffffff"),
          margin=dict(l=20, r=20, t=30, b=50),
          legend=dict(
              orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
          ),
          xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickangle=-25),
          yaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
          height=360,
      )
      st.plotly_chart(fig_bar, use_container_width=True)

    with col_g2:
      st.markdown(
          "<h4 style='color:#00f0ff;'>🍩 Distribusi Penjualan Produk</h4>",
          unsafe_allow_html=True,
      )

      if total_actual > 0:
        fig_donut = px.pie(
            si_df,
            values="actual_qty",
            names="item_name",
            hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ffffff"),
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=False,
            height=360,
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_donut, use_container_width=True)
      else:
        st.info("Belum ada data realisasi penjualan untuk ditampilkan.")

    st.markdown("---")

    # 3. Tabel Detail & Status Pencapaian Penjualan
    st.markdown(
        "<h4 style='color:#00f0ff;'>📋 Detail & Status Pencapaian Target Item"
        " PSM</h4>",
        unsafe_allow_html=True,
    )

    si_df["Pencapaian (%)"] = (
        (si_df["actual_qty"] / si_df["target_qty"] * 100)
        .fillna(0)
        .round(1)
    )

    def status_badge(pct):
      if pct >= 100:
        return "Tercapai ✅"
      elif pct >= 50:
        return "Mendekati Target ⚠️"
      else:
        return "Belum Terjangkau ❌"

    si_df["Status Target"] = si_df["Pencapaian (%)"].apply(status_badge)

    display_table = si_df[[
        "item_name",
        "target_qty",
        "actual_qty",
        "Pencapaian (%)",
        "Status Target",
    ]].copy()
    display_table.columns = [
        "Nama Produk",
        "Target (Pcs)",
        "Real Sales (Pcs)",
        "Pencapaian (%)",
        "Status",
    ]

    st.dataframe(
        display_table,
        use_container_width=True,
        column_config={
            "Pencapaian (%)": st.column_config.ProgressColumn(
                "Progress (%)",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
        },
        hide_index=True,
    )

    # 4. Unduh Data Excel/CSV Instan
    csv_data = display_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Rekapitulasi Data (CSV)",
        data=csv_data,
        file_name=f'rekap_psm_{waktu_wib.strftime("%Y%m%d")}.csv',
        mime="text/csv",
    )
  else:
    st.warning("⚠️ Belum ada data item yang terdaftar pada periode ini.")

# --- TAB 02: DASHBOARD UTAMA ---
elif selected_tab == "DASHBOARD UTAMA":
  st.markdown("## 📊 Dashboard Utam Penjualan PSM Toko")
  st.info(
      "Modul rincian grafik performa serta analisis mendalam per personil."
  )

# --- TAB 06: INPUT & RESET DATA ---
elif selected_tab == "Input & Reset Data":
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
  periode_pps_df = (
      st.session_state.periode_pps_df.copy()
      if "periode_pps_df" in st.session_state
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
  pps_df_report = (
      st.session_state.sales_pps_df.copy()
      if "sales_pps_df" in st.session_state
      else pd.DataFrame()
  )
  person_df = (
      st.session_state.person_df.copy()
      if "person_df" in st.session_state
      else pd.DataFrame()
  )

  tab_in1, tab_in2, tab_in3, tab_in4, tab_in5 = st.tabs([
      "⚡ Multi Input Sales Personil",
      "🎯 Input Sales PPS",
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
        * **Status:** Synchronized to Google Sheets ✅
        """)
    if st.button("👍 Mantap, Tutup", use_container_width=True):
      st.rerun()

  with tab_in1:
    st.markdown(
        "<h4 style='color: #00ff88;'>⚡ Multi Input Sales Personil</h4>",
        unsafe_allow_html=True,
    )
    if is_visitor:
      st.error("🔒 Akses Ditolak! Akun Visitor hanya membaca data.")
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
        st.info(f"👤 Penginputan dikunci untuk akun pengguna: {current_user}")

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
            f"⚠️ Tidak ada daftar item produk pada periode **{m_period_name}**."
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
              st.error(f"❌ Terjadi kesalahan: {str(e)}")
          else:
            st.warning("⚠️ Tidak ada Qty produk yang diisi.")

# --- TAB MASTER DATA & PENGATURAN ---
elif selected_tab == "⚙️ Master Data & Pengaturan":
  st.markdown("## ⚙️ Master Data & Pengaturan Sistem")
  st.info("Fitur pengelolaan master item, periode, serta konfigurasi database.")
