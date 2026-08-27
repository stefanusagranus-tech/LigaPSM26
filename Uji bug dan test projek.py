import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection

# =========================================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# =========================================================
st.set_page_config(
    page_title="PSM Toko - Mobile Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

SPREADSHEET_ID = "1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk"

# =========================================================
# 2. INISIALISASI DATABASE & GSHEETS
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)

def load_database():
    try:
        periods_df = conn.read(worksheet="PERIODE", ttl=0)
        items_df = conn.read(worksheet="MASTER_ITEM", ttl=0)
        person_df = conn.read(worksheet="MASTER_PERSONIL", ttl=0)
        sales_item_df = conn.read(worksheet="SALES_ITEM", ttl=0)
        sales_person_df = conn.read(worksheet="SALES_PERSONIL", ttl=0)
        
        for df in [periods_df, items_df, person_df, sales_item_df, sales_person_df]:
            if not df.empty:
                df.columns = df.columns.astype(str).str.strip().str.lower()
                
        for df in [periods_df, sales_item_df, sales_person_df]:
            if not df.empty and "period_id" in df.columns:
                df["period_id"] = df["period_id"].astype(str).str.strip()
                
        for df in [items_df, sales_item_df, sales_person_df]:
            if not df.empty and "item_id" in df.columns:
                df["item_id"] = df["item_id"].astype(str).str.strip()

        for df in [person_df, sales_person_df]:
            if not df.empty and "person_name" in df.columns:
                df["person_name"] = df["person_name"].astype(str).str.strip().str.upper()
                df["person_name"] = df["person_name"].str.replace(r"\s+", " ", regex=True)

        return periods_df, items_df, person_df, sales_item_df, sales_person_df
    except Exception as e:
        st.error(f"Gagal membaca Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

if "data_loaded" not in st.session_state:
    p_df, i_df, pers_df, si_df, sp_df = load_database()
    st.session_state.periods_df = p_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.data_loaded = True

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Home"

waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%A, %d %B %Y %H:%M WIB")

# Auth Sederhana
def check_login(input_username, input_password):
    u = str(input_username).strip().lower()
    p = str(input_password).strip()
    if (u == "admin" and p == "lavitality") or (u == "visitor" and p == "visitor"):
        st.session_state["logged_in"] = True
        st.session_state["person_name"] = "Administrator" if u == "admin" else "Pengunjung"
        st.session_state["role"] = "Admin" if u == "admin" else "Visitor"
        return True
    
    df_users = st.session_state.get("person_df", pd.DataFrame())
    if not df_users.empty and "username" in df_users.columns and "password" in df_users.columns:
        df_users["u_clean"] = df_users["username"].astype(str).str.strip().str.lower()
        df_users["p_clean"] = df_users["password"].astype(str).str.strip()
        match = df_users[(df_users["u_clean"] == u) & (df_users["p_clean"] == p)]
        if not match.empty:
            st.session_state["logged_in"] = True
            st.session_state["person_name"] = str(match.iloc[0].get("person_name", u))
            st.session_state["role"] = str(match.iloc[0].get("role", "Staff"))
            return True
    return False

# =========================================================
# 3. CUSTOM CSS STYLING (MOBILE LOOK & GRID)
# =========================================================
st.markdown("""
<style>
header[data-testid="stHeader"] { display: none !important; }
.stApp { background-color: #0b0f19; color: #f8fafc; font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #38bdf8; 
    padding: 12px; 
    border-radius: 12px; 
}
div[data-testid="stMetric"] label { color: #94a3b8 !important; font-size: 11px; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #38bdf8 !important; font-size: 18px; font-weight: 800; }

.app-card {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border: 1.5px solid #00f0ff;
    border-radius: 16px;
    padding: 14px 8px;
    text-align: center;
    box-shadow: 0 4px 14px rgba(0, 240, 255, 0.12);
    margin-bottom: 6px;
}
.app-icon { font-size: 30px; margin-bottom: 2px; display: block; }
.app-title { color: #ffffff; font-size: 13px; font-weight: 700; margin: 0; }
.app-desc { color: #94a3b8; font-size: 10px; margin-top: 2px; }

div.stButton > button {
    background-color: #080c14 !important; 
    color: #ffffff !important; 
    border: 1.5px solid #00f0ff !important;
    border-radius: 10px !important; 
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# =========================================================
# 4. LOGIN PAGE
# =========================================================
if not st.session_state["logged_in"]:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h2 style='text-align:center; color:#00f0ff;'>TOKO C383</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            u_in = st.text_input("Username")
            p_in = st.text_input("Password", type="password")
            if st.form_submit_button("Masuk", use_container_width=True):
                if check_login(u_in, p_in):
                    st.rerun()
                else:
                    st.error("Login Gagal")
    st.stop()

# =========================================================
# 5. HEADER ATAS (MOBILE FRIENDLY)
# =========================================================
h_col1, h_col2 = st.columns([2.5, 1])
with h_col1:
    st.markdown(f"""
    <div style='display: flex; align-items: center; gap: 8px;'>
        <div style='background: #00f0ff; width: 5px; height: 28px; border-radius: 3px;'></div>
        <div>
            <h4 style='margin:0; color:#ffffff; font-size: 15px;'>TOKO C383 MOBILE</h4>
            <p style='margin:0; color:#38bdf8; font-size: 10px;'>👤 {st.session_state.get("person_name", "User")}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with h_col2:
    if st.button("🚪 Keluar", key="btn_logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.markdown("<hr style='margin: 8px 0; border-color: #1e293b;'>", unsafe_allow_html=True)

# =========================================================
# 6. NAVIGASI UTAMA (HOME GRID 2x2 & TABS)
# =========================================================
selected_tab = st.session_state.active_tab

if selected_tab != "Home":
    nav_col1, nav_col2 = st.columns([1.2, 2.8])
    with nav_col1:
        if st.button("🏠 Home", key="btn_nav_home", use_container_width=True):
            st.session_state.active_tab = "Home"
            st.rerun()
    with nav_col2:
        st.markdown(f"<h4 style='color:#00f0ff; margin: 4px 0 0 0; font-size:14px;'>📌 {selected_tab}</h4>", unsafe_allow_html=True)
    st.markdown("<hr style='margin: 6px 0 10px 0; border-color: #334155;'>", unsafe_allow_html=True)

# --- DISPLAY HOME SCREEN (GRID 2x2) ---
if selected_tab == "Home":
    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 12px;'>
        <p style='color: #94a3b8; font-size: 10px; margin-bottom: 2px;'>WAKTU SISTEM REALTIME</p>
        <p style='color: #00f0ff; font-size: 11px; font-weight: bold; margin-top: 0;'>{current_time_str}</p>
    </div>
    """, unsafe_allow_html=True)

    # Baris 1 Grid 2x2
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("<div class='app-card'><span class='app-icon'>📊</span><div class='app-title'>01 Dashboard</div><div class='app-desc'>PSM, Sales, PPS, STD</div></div>", unsafe_allow_html=True)
        if st.button("Buka Dashboard", key="btn_a1", use_container_width=True):
            st.session_state.active_tab = "01 Dashboard"
            st.rerun()
    with g2:
        st.markdown("<div class='app-card'><span class='app-icon'>🏆</span><div class='app-title'>02 Raport Personil</div><div class='app-desc'>Penjualan, Rank PSM & PPS</div></div>", unsafe_allow_html=True)
        if st.button("Buka Raport", key="btn_a2", use_container_width=True):
            st.session_state.active_tab = "02 Raport Personil"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Baris 2 Grid 2x2
    g3, g4 = st.columns(2)
    with g3:
        st.markdown("<div class='app-card'><span class='app-icon'>📥</span><div class='app-title'>03 Input Laporan</div><div class='app-desc'>Input Data Harian</div></div>", unsafe_allow_html=True)
        if st.button("Buka Input", key="btn_a3", use_container_width=True):
            st.session_state.active_tab = "03 Input Laporan"
            st.rerun()
    with g4:
        st.markdown("<div class='app-card'><span class='app-icon'>⚙️</span><div class='app-title'>04 Pengaturan</div><div class='app-desc'>Reload & Info Sistem</div></div>", unsafe_allow_html=True)
        if st.button("Buka Pengaturan", key="btn_a4", use_container_width=True):
            st.session_state.active_tab = "04 Pengaturan"
            st.rerun()

# =========================================================
# TAB 01: DASHBOARD (DENGAN 4 SUB-MENU UTAMA)
# =========================================================
elif selected_tab == "01 Dashboard":
    if "dash_sub" not in st.session_state:
        st.session_state.dash_sub = "Report PSM"

    # Pilihan Kapsul untuk 4 Menu Dashboard
    dash_options = ["Report PSM", "Report Sales Toko", "Report PPS Toko", "Report STD & Member"]
    if hasattr(st, "pills"):
        st.session_state.dash_sub = st.pills("Pilih Menu Dashboard", dash_options, default=st.session_state.dash_sub, key="pills_dash")
    else:
        st.session_state.dash_sub = st.selectbox("Pilih Menu Dashboard:", dash_options, key="select_dash")

    st.markdown("---")
    sub_menu = st.session_state.dash_sub

    # 1. Report PSM
    if sub_menu == "Report PSM":
        st.markdown("### 📊 Report Pencapaian PSM")
        st.info("Menampilkan rangkuman target, actual, gap, dan persentase achievement PSM toko.")
        # (Logika dashboard PSM awal kamu ditaruh di sini)

    # 2. Report Sales Toko
    elif sub_menu == "Report Sales Toko":
        st.markdown("### 💰 Report Sales Toko")
        
        tab_s1, tab_s2 = st.tabs(["📌 Net Sales & GM", "🧾 NSB Toko"])
        with tab_s1:
            st.markdown("##### Menu Net Sales & GM")
            net_sales = st.number_input("Input Net Sales (Rp):", value=0, step=100000)
            gm_persen = st.number_input("Input GM (%):", value=0.0, step=0.1)
            gm_rupiah = net_sales * (gm_persen / 100)
            budget_so = st.number_input("Input Budget SO (Rp):", value=0, step=10000)
            
            st.markdown(f"**GM Rupiah (Net Sales x GM%):** Rp {gm_rupiah:,.2f}")
            st.success(f"**Budget SO Terhitung:** Rp {budget_so:,.2f}")

        with tab_s2:
            st.markdown("##### Menu NSB Toko")
            sales_toko = st.number_input("Sales Toko (Rp):", value=0, step=100000)
            budget_nbh = sales_toko * 0.0015  # Sales x 0.15%
            adjust_so = st.number_input("Adjust SO (Rp):", value=0, step=10000)
            total_nbh = budget_nbh - adjust_so
            
            st.metric("Budget NBH (0.15%)", f"Rp {budget_nbh:,.2f}")
            st.metric("Total NBH (Budget - Adjust)", f"Rp {total_nbh:,.2f}")

    # 3. Report PPS Toko
    elif sub_menu == "Report PPS Toko":
        st.markdown("### 🎯 Report PPS Toko")
        pps_sub_tab = st.selectbox("Pilih Sub-Kategori PPS:", ["Report PPS Utama", "Report Sueger & Cemilan Ceban", "Simulasi PPS Toko"])
        
        if pps_sub_tab == "Report PPS Utama":
            st.markdown("##### Rangkuman PPS Utama")
            c1, c2 = st.columns(2)
            c1.metric("Apc Toko", "0")
            c1.metric("Psm Toko", "0")
            c2.metric("Pwp Toko", "0")
            c2.metric("Serba Gratis Toko", "0")
        elif pps_sub_tab == "Report Sueger & Cemilan Ceban":
            st.markdown("##### 🥤 Report Sueger & Cemilan Ceban")
            st.write("Data dan pencapaian produk Sueger serta Cemilan Ceban.")
        else:
            st.markdown("##### 🧮 Simulasi PPS Toko")
            sim_val = st.slider("Simulasi Target Index PPS", 0, 100, 50)
            st.write(f"Estimasi Poin Bonus / Bobot Berdasarkan Simulasi: **{sim_val * 0.2:.2f} Poin**")

    # 4. Report STD & Member
    elif sub_menu == "Report STD & Member":
        st.markdown("### 👥 Report STD & Kontribusi Member Toko")
        st.info("Analisis data transaksi harian (STD) dan persentase kontribusi member terhadap total member belanja toko.")

# =========================================================
# TAB 02: RAPORT PERSONIL TOKO (3 MENU UTAMA)
# =========================================================
selected_tab = st.session_state.active_tab
if selected_tab == "02 Raport Personil":
    st.markdown("### 🏆 Raport Personil Toko")
    
    r_options = ["Penjualan Personil Toko", "Rangking PSM Toko", "Rangking PPS Toko"]
    if hasattr(st, "pills"):
        r_choice = st.pills("Menu Raport", r_options, default=r_options[0], key="pills_raport")
    else:
        r_choice = st.selectbox("Pilih Menu Raport:", r_options, key="select_raport")
        
    st.markdown("---")
    
    if r_choice == "Penjualan Personil Toko":
        st.markdown("##### 📊 Menu Penjualan Personil Toko")
        st.write("Daftar rinci pencapaian aktual penjualan masing-masing kasir/personil.")
    elif r_choice == "Rangking PSM Toko":
        st.markdown("##### 🥇 Menu Rangking PSM Toko")
        st.write("Papan peringkat (Leaderboard) personil berdasarkan target dan actual PSM.")
    else:
        st.markdown("##### 🎯 Menu Rangking PPS Toko")
        st.write("Papan peringkat personil berdasarkan performa indikator PPS.")

# =========================================================
# TAB 03: INPUT LAPORAN (SEMENTARA)
# =========================================================
elif selected_tab == "03 Input Laporan":
    st.markdown("### 📥 Menu Input Laporan")
    st.info("Menu input laporan harian akan segera dikembangkan di tahap berikutnya.")

# =========================================================
# TAB 04: PENGATURAN
# =========================================================
elif selected_tab == "04 Pengaturan":
    st.markdown("### ⚙️ Pengaturan & Informasi Sistem")
    st.success("Aplikasi terhubung dengan Google Sheets!")
    
    st.markdown("##### 🔄 Manajemen Data")
    if st.button("Reload Data Realtime dari GSheets", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### ℹ️ Tentang Aplikasi")
    st.text("Versi: 2.0 (Mobile Optimized)\nArea: Toko C383\nFramework: Streamlit & Python")


