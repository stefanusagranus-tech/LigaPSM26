import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

# ==========================================
# 1. KONFIGURASI HALAMAN & STREAMLIT
# ==========================================
st.set_page_config(
    page_title="PSM Toko Sales Monitoring",
    page_icon="📊",
    layout="wide"
)

# ==========================================
# 2. DATABASE USER & CREDENTIALS KARYAWAN
# ==========================================
# Anda bisa menambah/mengubah username, password, dan nama karyawan di sini
USER_DATABASE = {
    "admin": {"password": "123", "nama": "Staff Toko"},
    "23044862": {"password": "123", "nama": "Aris Aprilianto"},
    "24091737": {"password": "123", "nama": "Tika"},
    "24096619": {"password": "123", "nama": "Rizki Gunawan"},
    "25037119": {"password": "123", "nama": "Adelia Pratiwi"},
    "26065884": {"password": "123", "nama": "Ilham Priandika"}
}

# Inisialisasi Session State Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_fullname" not in st.session_state:
    st.session_state.user_fullname = ""
if "username" not in st.session_state:
    st.session_state.username = ""

# ==========================================
# 3. WAKTU REALTIME GMT+7 (WIB)
# ==========================================
wib_tz = timezone(timedelta(hours=7))
now_utc = datetime.now(timezone.utc)
now_wib = now_utc.astimezone(wib_tz)
current_time_str = now_wib.strftime("%A, %d %B %Y | %H:%M WIB")

# ==========================================
# 4. TAMPILAN HALAMAN LOGIN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    
    with c2:
        st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 12px; padding: 24px; text-align: center; box-shadow: 0 0 15px rgba(0, 240, 255, 0.3);">
                <h2 style="color: #ffffff; margin-bottom: 0px;">📊 PSM MONITORING</h2>
                <p style="color: #38bdf8; font-size: 13px;">Silakan login dengan akun karyawan Anda</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        input_username = st.text_input("Username", placeholder="Masukkan Username...", key="login_user")
        input_password = st.text_input("Password", type="password", placeholder="Masukkan Password...", key="login_pass")
        
        if st.button("🔓 LOGIN APLIKASI", use_container_width=True):
            user_clean = input_username.strip().lower()
            if user_clean in USER_DATABASE and USER_DATABASE[user_clean]["password"] == input_password:
                st.session_state.logged_in = True
                st.session_state.username = user_clean
                st.session_state.user_fullname = USER_DATABASE[user_clean]["nama"]
                st.success(f"Selamat datang, {st.session_state.user_fullname}!")
                st.rerun()
            else:
                st.error("Username atau Password salah!")

# ==========================================
# 5. TAMPILAN DASHBOARD SETELAH LOGIN
# ==========================================
else:
    # --- HEADER / BANNER UTAMA (REALTIME GMT+7 + USERNAME) ---
    st.markdown(f"""
        <div style='background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 16px 24px; border-radius: 12px; border: 1px solid #38bdf8; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <h2 style='margin:0; color:#ffffff; font-size: 22px;'>📊 PSM TOKO SALES MONITORING</h2>
                <p style='margin:0; color:#38bdf8; font-size: 13px;'>👤 Login Sebagai: <b>{st.session_state.user_fullname}</b> ({st.session_state.username.upper()})</p>
            </div>
            <div style='text-align: right;'>
                <p style='margin:0; color:#94a3b8; font-size: 11px; font-weight:bold;'>WAKTU REALTIME SISTEM (WIB)</p>
                <p style='margin:0; color:#38bdf8; font-size: 15px; font-weight:bold;'>⏰ {current_time_str}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

      # ==========================================
    # SIDEBAR NAVIGASI UTAMA (TANPA SUB MENU DI SIDEBAR)
    # ==========================================
    st.sidebar.markdown(f"### 👤 Karyawan: **{st.session_state.user_fullname}**")
    if st.sidebar.button("🚪 Logout / Keluar"):
        st.session_state.logged_in = False
        st.rerun()
        
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗂️ MAIN MENU")
    
    # Hanya Menu Utama di Sidebar
    main_menu = st.sidebar.radio(
        "Pilih Modul Utama:",
        [
            "🏠 Halaman Utama (Landing Page)", 
            "1. Monitoring PSM"
        ],
        key="main_menu_nav"
    )

    # ==========================================
    # LOGIKA HALAMAN UTAMA & SUB MENU DI DALAM
    # ==========================================

    # --- 1. HALAMAN UTAMA (LANDING PAGE) ---
    if main_menu == "🏠 Halaman Utama (Landing Page)":
        st.title(f"👋 Selamat Datang, {st.session_state.user_fullname}!")
        st.markdown("#### 📌 Executive Summary & Quick Preview Toko")
        
        # Grid Cards Quick Preview
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            st.metric("Total Actual Sales", "628 Pcs", "+12% vs Kemarin")
        with q2:
            st.metric("Achievement Toko", "44.5%", "Time Factor 50.0%")
        with q3:
            st.metric("🔥 Item Terlaris", "AQUA 600ml", "344 Pcs")
        with q4:
            st.metric("🏆 Top Personil", "Siti Nurhaliza", "Contrib: 32.5%")

    # --- 2. MODUL MONITORING PSM (SUB MENU LANGSUNG DI DALAM) ---
    elif main_menu == "1. Monitoring PSM":
        st.title("📊 Monitoring PSM Toko")
        st.markdown("Pilih sub menu di bawah untuk melihat detail analisis:")
        
        # TAB SUB MENU LANGSUNG DI DALAM HALAMAN UTAMA
        tab_dashboard, tab_detail_item, tab_personil = st.tabs([
            "📈 1. Dashboard PSM",
            "📦 2. Detail Item & Daily Monitoring",
            "👥 3. Performance Personil Toko"
        ])

        # --- SUB MENU 1: DASHBOARD PSM ---
        with tab_dashboard:
            st.subheader("Review & Target Penjualan Toko")
            # [Isi Kodingan Dashboard PSM: Target vs Actual, Time Factor Check, Target Harian, Weekly Bar Chart]
            st.info("Halaman Dashboard PSM siap diisi data.")

        # --- SUB MENU 2: DETAIL ITEM & DAILY MONITORING ---
        with tab_detail_item:
            st.subheader("Detail Item & Daily Monitoring Penjualan")
            # [Isi Kodingan Detail Item: Kalender Harian, Growth H-1, Sidebox Item Laku/Tidak Laku]
            st.info("Halaman Detail Item & Kalender Monitoring Harian siap diisi data.")

        # --- SUB MENU 3: PERFORMANCE PERSONIL TOKO ---
        with tab_personil:
            st.subheader("Performa & Kontribusi Personil Toko")
            # [Isi Kodingan Personil: Podium Top 3, Ranking Staf, Chart Trend, Drill-down Detail Item]
            st.info("Halaman Performa Personil Toko siap diisi data.")

