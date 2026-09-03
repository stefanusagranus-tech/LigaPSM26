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
from streamlit_option_menu import option_menu

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="PSM Toko - Mobile Sales App",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SPREADSHEET_ID = "1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk"

# =========================================================
# 2. CUSTOM CSS: ANDROID MOBILE UI & BOTTOM NAVBAR
# =========================================================
st.markdown(
    """
<style>
    /* 1. Sembunyikan Sidebar Bawaan & Header Default Streamlit */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stHeader"] { background: transparent !important; }
    
    /* 2. Tema & Styling Dasar */
    .stApp {
        background-color: #080d1a;
        color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    /* Memberikan ruang di bagian bawah agar konten tidak tertutup Bottom Navbar */
    .main .block-container {
        padding-bottom: 110px !important;
        padding-top: 1.5rem !important;
    }

    label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label, label p {
        color: #38bdf8 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
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
        border-radius: 10px !important;
    }
    
    /* Card Component Styling */
    .home-hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 20px 24px;
        border-radius: 16px;
        border: 1px solid rgba(56, 189, 248, 0.3);
        box-shadow: 0 8px 20px rgba(0, 240, 255, 0.1);
        margin-bottom: 20px;
    }
    .metric-card-home {
        background: linear-gradient(135deg, #0d1527 0%, #152035 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 14px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        margin-bottom: 10px;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 4px;
    }
    .metric-val {
        color: #00f0ff;
        font-size: 24px;
        font-weight: 800;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.4);
    }
    .metric-sub {
        color: #38bdf8;
        font-size: 11px;
        margin-top: 2px;
        font-weight: 500;
    }

    /* Floating Fixed Bottom Navigation Container */
    div[data-testid="stBottom"], .st-emotion-cache-121g2td, div[element-id="bottom-nav-container"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 999999 !important;
        background-color: #0b1120 !important;
        border-top: 1.5px solid #00f0ff !important;
        padding: 6px 12px 10px 12px !important;
        box-shadow: 0px -6px 20px rgba(0, 240, 255, 0.2) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 3. INISIALISASI KONEKSI GOOGLE SHEETS & FUNGSI DATABASE
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)


@st.cache_data(ttl=60)
def load_database():
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
      st.warning("⚠️ Proses simpan dibatalkan: Data transaksi kosong.")
      return False

    conn.update(worksheet="SALES_ITEM", data=sales_item_df)
    time.sleep(0.3)
    conn.update(worksheet="SALES_PERSONIL", data=sales_person_df)
    time.sleep(0.3)
    conn.update(worksheet="SALES_PPS", data=sales_pps_df)
    time.sleep(0.3)
    conn.update(worksheet="SALES_STOREPERFORMANCE", data=sales_store_df)

    st.toast("Data berhasil tersimpan ke Google Sheets!", icon="✅")
    return True
  except Exception as e:
    st.error(f"❌ Gagal menyimpan data: {e}")
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


# Load Data
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

# Waktu Realtime GMT+7
waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%a, %d %b %Y | %H:%M WIB")

# Database User
USER_DATABASE = {
    "admin": {"password": "lavitality", "nama": "ADMIN MASTER"},
    "23044862": {"password": "c383kgs", "nama": "ARIS APRILIANTO"},
    "24091737": {"password": "c383kgs", "nama": "TIKA"},
    "24096619": {"password": "c383kgs", "nama": "RIZKI GUNAWAN"},
    "25037119": {"password": "c383kgs", "nama": "ADELIA PRATIWI"},
    "26065884": {"password": "c383kgs", "nama": "ILHAM PRIANDIKA"},
    "visitor": {"password": "visitor", "nama": "GUEST VISITOR"},
}

if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "username" not in st.session_state:
  st.session_state.username = ""


# ==========================================
# 4. HALAMAN LOGIN
# ==========================================
def show_login_page():
  LOGO_URL = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/kgs_group_belgium_logo.jpg"

  st.markdown(
      f"""
        <div style="background-color: #1e293b; padding: 25px 20px; border-radius: 16px; text-align: center; margin-top:20px; border: 1px solid #38bdf8;">
            <img src='{LOGO_URL}' style="width:80px; height:80px; border-radius:12px; background:#fff; padding:6px; margin-bottom:10px;">
            <h3 style="color:#ffffff; margin:0; font-size:20px;">TOKO C383 MOBILE</h3>
            <p style="color:#38bdf8; font-size:12px; margin-top:2px;">Sistem Monitoring PSM Toko</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("<br>", unsafe_allow_html=True)
  with st.form("login_form", clear_on_submit=False):
    username_input = st.text_input(
        "Username", placeholder="Masukkan username"
    ).strip()
    password_input = st.text_input(
        "Password", type="password", placeholder="Masukkan password"
    )
    submit_btn = st.form_submit_button("🔑 MASUK APLIKASI", use_container_width=True)

    if submit_btn:
      if (
          username_input in USER_DATABASE
          and USER_DATABASE[username_input]["password"] == password_input
      ):
        st.session_state.logged_in = True
        st.session_state.username = USER_DATABASE[username_input]["nama"]
        st.toast(
            f"Selamat Datang, {USER_DATABASE[username_input]['nama']}!",
            icon="✅",
        )
        st.rerun()
      else:
        st.error("Username atau Password salah!")


if not st.session_state.logged_in:
  show_login_page()
  st.stop()

# ==========================================
# 5. MOBILE TOP BAR / HEADER
# ==========================================
user_name = st.session_state.get("username", "Pengguna")
col_h1, col_h2 = st.columns([2.2, 1])

with col_h1:
  st.markdown(
      f"""
        <div style="display:flex; align-items:center; gap:10px;">
            <div style="background:#0284c7; color:#fff; font-size:16px; font-weight:bold; padding:8px 12px; border-radius:50%;">👤</div>
            <div>
                <div style="color:#94a3b8; font-size:11px; font-weight:600;">AKUN AKTIF</div>
                <div style="color:#00ff88; font-size:13px; font-weight:700;">{user_name}</div>
            </div>
        </div>
    """,
      unsafe_allow_html=True,
  )

with col_h2:
  periods_df = st.session_state.periods_df
  periods_dict = (
      {row["period_name"]: row["period_id"] for _, row in periods_df.iterrows()}
      if not periods_df.empty
      else {"Periode Utama": "P01"}
  )

  selected_period_name = st.selectbox(
      "Periode",
      ["Semua Periode"] + list(periods_dict.keys()),
      label_visibility="collapsed",
  )
  selected_period_id = (
      None
      if selected_period_name == "Semua Periode"
      else periods_dict[selected_period_name]
  )

st.markdown(
    "<hr style='margin: 10px 0 15px 0; border-color: #1e293b;'>",
    unsafe_allow_html=True,
)

# ==========================================
# 6. ROUTING KONTEN HALAMAN (TABS)
# ==========================================

# Kita gunakan placeholder untuk meletakkan Bottom Navigation secara fixed di bagian bawah
bottom_nav_placeholder = st.container()

# Inisialisasi Pilihan Tab via Session State
if "active_tab" not in st.session_state:
  st.session_state.active_tab = "Home"

# ----------------------------------------------------
# TAB 1: HOME
# ----------------------------------------------------
if st.session_state.active_tab == "Home":
  st.markdown(
      f"""
        <div class="home-hero">
            <h3 style="color:#ffffff; margin:0; font-size:20px; font-weight:800;">🚀 Performa Sales PSM</h3>
            <p style="color:#38bdf8; margin:2px 0 0 0; font-size:12px;">📅 {current_time_str}</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

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

  # Display Grid Metrik Mobile 2x2
  mc1, mc2 = st.columns(2)
  with mc1:
    st.markdown(
        f"""<div class="metric-card-home"><div class="metric-title">🎯 Target Toko</div><div class="metric-val">{total_target:,.0f}</div><div class="metric-sub">Pcs Produk</div></div>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""<div class="metric-card-home"><div class="metric-title">📈 Achievement</div><div class="metric-val" style="color:#00ff88;">{overall_pct:.1f}%</div><div class="metric-sub">Rasio Capaian</div></div>""",
        unsafe_allow_html=True,
    )
  with mc2:
    st.markdown(
        f"""<div class="metric-card-home"><div class="metric-title">📦 Real Sales</div><div class="metric-val" style="color:#00ff88;">{total_actual:,.0f}</div><div class="metric-sub">Terjual</div></div>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""<div class="metric-card-home"><div class="metric-title">🏷️ Active Item</div><div class="metric-val" style="color:#f59e0b;">{total_items}</div><div class="metric-sub">Item Produk</div></div>""",
        unsafe_allow_html=True,
    )

  if not si_df.empty:
    st.markdown(
        "<h4 style='color:#00f0ff; font-size:16px; margin-top:15px;'>📊 Target vs"
        " Realisasi</h4>",
        unsafe_allow_html=True,
    )
    fig_bar = go.Figure()
    fig_bar.add_trace(
        go.Bar(
            x=si_df["item_name"],
            y=si_df["target_qty"],
            name="Target",
            marker_color="#3b82f6",
        )
    )
    fig_bar.add_trace(
        go.Bar(
            x=si_df["item_name"],
            y=si_df["actual_qty"],
            name="Real",
            marker_color="#00ff88",
        )
    )

    fig_bar.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#ffffff", size=10),
        margin=dict(l=10, r=10, t=10, b=40),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickangle=-30),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
        height=300,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Ringkasan Tabel
    st.markdown(
        "<h4 style='color:#00f0ff; font-size:16px;'>📋 Detail Status"
        " Item</h4>",
        unsafe_allow_html=True,
    )
    si_df["Achievement (%)"] = (
        (si_df["actual_qty"] / si_df["target_qty"] * 100)
        .fillna(0)
        .round(1)
    )
    display_tbl = si_df[
        ["item_name", "target_qty", "actual_qty", "Achievement (%)"]
    ]
    display_tbl.columns = [
        "Produk",
        "Target",
        "Real",
        "Ach (%)",
    ]
    st.dataframe(display_tbl, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# TAB 2: DASHBOARD
# ----------------------------------------------------
elif st.session_state.active_tab == "Dashboard":
  st.markdown("<h3 style='color:#00f0ff;'>📊 Analytics & Report</h3>", unsafe_allow_html=True)
  st.info("Visualisasi analisis performa mendalam Toko & Personil.")

# ----------------------------------------------------
# TAB 3: INPUT DATA
# ----------------------------------------------------
elif st.session_state.active_tab == "Input":
  st.markdown("<h3 style='color:#00ff88;'>✏️ Form Multi Input Sales</h3>", unsafe_allow_html=True)

  current_user = st.session_state.get("username", "visitor")
  is_admin = "ADMIN" in current_user.upper()

  m_period_name = st.selectbox("Periode Transaksi", list(periods_dict.keys()))
  m_p_id = periods_dict[m_period_name]

  person_df = (
      st.session_state.person_df.copy()
      if "person_df" in st.session_state
      else pd.DataFrame()
  )
  all_personnel = (
      person_df["person_name"].dropna().unique().tolist()
      if not person_df.empty and "person_name" in person_df.columns
      else [current_user]
  )

  m_person = (
      st.selectbox("Pilih Staf/Personil", all_personnel)
      if is_admin
      else current_user
  )
  m_date = st.date_input("Tanggal Transaksi", value=waktu_wib.date())

  items_df = st.session_state.get("items_df", pd.DataFrame())
  filtered_items = (
      items_df[items_df["period_id"].astype(str) == str(m_p_id)]
      if not items_df.empty
      else pd.DataFrame()
  )

  if not filtered_items.empty:
    with st.form("mobile_input_form"):
      st.markdown("##### 📦 Masukkan Qty Penjualan:")
      input_values = {}
      for idx, row in filtered_items.iterrows():
        i_id, i_name = str(row["item_id"]), str(row["item_name"])
        val = st.number_input(f"{i_name}", min_value=0, step=1, key=f"inp_{i_id}")
        input_values[i_id] = {"name": i_name, "qty": val}

      btn_save = st.form_submit_button(
          "💾 SIMPAN TRANSAKSI", use_container_width=True
      )

      if btn_save:
        st.success("Data berhasil disimpan secara instan!")
  else:
    st.warning("Tidak ada item aktif pada periode ini.")

# ----------------------------------------------------
# TAB 4: AKUN & PENGATURAN
# ----------------------------------------------------
elif st.session_state.active_tab == "Akun":
  st.markdown("<h3 style='color:#f59e0b;'>👤 Pengaturan & Profil</h3>", unsafe_allow_html=True)

  st.markdown(
      f"""
        <div style="background:#1e293b; padding:15px; border-radius:12px; border:1px solid #334155;">
            <p style="margin:0; color:#94a3b8; font-size:12px;">Pengguna Terhubung:</p>
            <h4 style="margin:0; color:#00ff88;">{user_name}</h4>
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("<br>", unsafe_allow_html=True)
  if st.button("🔄 Refresh Data Cache", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

  if st.button("🚪 Keluar / Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()


# =========================================================
# 7. ANDROID BOTTOM NAVIGATION BAR (FIXED BOTTOM)
# =========================================================
with bottom_nav_placeholder:
  selected_bottom_menu = option_menu(
      menu_title=None,
      options=["Home", "Dashboard", "Input", "Akun"],
      icons=["house-door-fill", "bar-chart-fill", "plus-circle-fill", "person-badge-fill"],
      default_index=["Home", "Dashboard", "Input", "Akun"].index(
          st.session_state.active_tab
      ),
      orientation="horizontal",
      styles={
          "container": {
              "padding": "0!important",
              "background-color": "transparent",
          },
          "icon": {"color": "#00f0ff", "font-size": "18px"},
          "nav-link": {
              "font-size": "11px",
              "text-align": "center",
              "margin": "2px",
              "color": "#94a3b8",
              "padding": "6px 0px",
          },
          "nav-link-selected": {
              "background-color": "#1e293b",
              "color": "#00f0ff",
              "font-weight": "bold",
              "border-radius": "10px",
              "border": "1px solid #00f0ff",
          },
      },
  )

  # Update State ketika tombol navigasi bawah ditekan
  if selected_bottom_menu != st.session_state.active_tab:
    st.session_state.active_tab = selected_bottom_menu
    st.rerun()
