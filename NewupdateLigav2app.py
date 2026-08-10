import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="PSM Toko Dashboard",
    page_icon="📊",
    layout="wide"
)

# ==========================================
# 2. CUSTOM CSS (UI LIGHT MODE ELEGANT)
# ==========================================
st.markdown("""
<style>
    /* Background Utama */
    .stApp {
        background-color: #f4f6f9;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Header Title Sidebar */
    .sidebar-section-title {
        color: #94a3b8;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.8px;
        margin-top: 18px;
        margin-bottom: 8px;
    }

    /* Custom White Cards */
    .white-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
        border: 1px solid #edf2f7;
        margin-bottom: 16px;
    }
    
    /* Badge Status */
    .badge-success {
        background-color: #dcfce7;
        color: #16a34a;
        font-size: 10px;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 20px;
        letter-spacing: 0.5px;
    }
    
    .badge-pill-active {
        background-color: #6366f1;
        color: #ffffff;
        font-weight: bold;
        padding: 6px 16px;
        border-radius: 20px;
        display: inline-block;
        font-size: 12px;
    }
    
    .badge-pill {
        background-color: #ffffff;
        color: #64748b;
        border: 1px solid #e2e8f0;
        font-weight: bold;
        padding: 6px 16px;
        border-radius: 20px;
        display: inline-block;
        font-size: 12px;
    }

    /* Typography inside Cards */
    .card-label {
        color: #64748b;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.6px;
        text-transform: uppercase;
    }
    .card-value {
        color: #0f172a;
        font-size: 26px;
        font-weight: 800;
        margin-top: 4px;
    }
    .card-subtext {
        color: #64748b;
        font-size: 12px;
        margin-top: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. WAKTU REALTIME GMT+7 (WIB)
# ==========================================
wib_tz = timezone(timedelta(hours=7))
now_utc = datetime.now(timezone.utc)
now_wib = now_utc.astimezone(wib_tz)
current_time_str = now_wib.strftime("%H.%M.%S")

# ==========================================
# 4. DATABASE KARYAWAN & SESSION
# ==========================================
USER_DATABASE = {
"admin": {"password": "123", "nama": "Staff Toko"}, 
"23044862": {"password": "123", "nama": "Aris Aprilianto"}, 
"24091737": {"password": "123", "nama": "Tika"}, 
"24096619": {"password": "123", "nama": "Rizki Gunawan"}, 
"25037119": {"password": "123", "nama": "Adelia Pratiwi"}, 
"26065884": {"password": "123", "nama": "Ilham Priandika"}
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_fullname" not in st.session_state:
    st.session_state.user_fullname = ""

# ==========================================
# 5. HALAMAN LOGIN (LIGHT MODE)
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("""
            <div class="white-card" style="text-align: center;">
                <h2 style="color: #0f172a; margin-bottom: 0px;">📊 CIROKEK</h2>
                <p style="color: #64748b; font-size: 13px;">Dashboard COS PSM Monitoring</p>
            </div>
        """, unsafe_allow_html=True)
        
        user_input = st.text_input("Username", key="login_u")
        pass_input = st.text_input("Password", type="password", key="login_p")
        
        if st.button("🔓 LOGIN APLIKASI", use_container_width=True):
            u_clean = user_input.strip().lower()
            if u_clean in USER_DATABASE and USER_DATABASE[u_clean]["password"] == pass_input:
                st.session_state.logged_in = True
                st.session_state.user_fullname = USER_DATABASE[u_clean]["nama"]
                st.rerun()
            else:
                st.error("Username atau Password salah!")

# ==========================================
# 6. DASHBOARD UTAMA
# ==========================================
else:
    # --- SIDEBAR NAVIGASI (Sesuai Gambar) ---
    with st.sidebar:
        st.markdown("<h3 style='color: #0f172a; margin-bottom:0;'>📊 CIROKEK</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: #64748b; font-size: 11px;'>Dashboard COS</p>", unsafe_allow_html=True)
        
        st.markdown('<p class="sidebar-section-title">MENU UTAMA</p>', unsafe_allow_html=True)
        main_menu = st.radio(
            "Navigasi Menu",
            [
                "📊 Dashboard",
                "👥 Laporan Personil",
                "🏆 Leaderboard",
                "📋 Semua Laporan"
            ],
            label_visibility="collapsed"
        )
        
        st.markdown('<p class="sidebar-section-title">ANALITIK & TARGET</p>', unsafe_allow_html=True)
        st.radio("Analitik Menu", ["🎯 Target 30 Hari", "📄 Laporan PDF"], label_visibility="collapsed")
        
        st.markdown('<p class="sidebar-section-title">SISTEM</p>', unsafe_allow_html=True)
        st.markdown(f"👤 Account: **{st.session_state.user_fullname}**")
        if st.button("🚪 Keluar / Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # --- TOP HEADER & STATUS BAR (Sesuai Gambar) ---
    h1, h2 = st.columns([2, 1])
    with h1:
        st.title("Dashboard")
        st.caption("Ringkasan performa toko")
        
    with h2:
        st.markdown(f"""
            <div style="display: flex; gap: 8px; justify-content: flex-end; align-items: center; margin-top: 15px;">
                <span class="badge-success">🟢 Live - Sheet</span>
                <span style="font-size: 11px; color: #64748b; font-weight:bold;">Update: {current_time_str}</span>
            </div>
        """, unsafe_allow_html=True)

    # --- FILTER TABS (SEMUA / BULAN / TANGGAL) ---
    st.markdown("""
        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <span class="badge-pill-active">SEMUA</span>
            <span class="badge-pill">BULAN</span>
            <span class="badge-pill">TANGGAL</span>
        </div>
    """, unsafe_allow_html=True)

    # --- SECTION 1: Review PSM ---
    st.markdown("<p style='color: #0f172a; font-weight: bold; font-size: 15px;'>🔵 Ringkasan Utama</p>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.markdown("""
            <div class="white-card">
                <span style="font-size: 20px;">📋</span>
                <div class="card-label" style="margin-top: 8px;">TOTAL PENJUALAN</div>
                <div class="card-value">SEDANG PENGERJAAN</div>
            </div>
        """, unsafe_allow_html=True)
        
    with m2:
        st.markdown("""
            <div class="white-card">
                <span style="font-size: 20px;">🎯</span>
                <div class="card-label" style="margin-top: 8px;">RATA-RATA ACV TOKO</div>
                <div class="card-value" style="color: #0f172a;">MASIH PENGERJAAN</div>
                <div class="card-subtext">SELURUH PENJUALAN PSM</div>
            </div>
        """, unsafe_allow_html=True)

    with m3:
        st.markdown("""
            <div class="white-card">
                <span style="font-size: 20px;">🏆</span>
                <div class="card-label" style="margin-top: 8px;">KASIR TERBAIK</div>
                <div class="card-value" style="color: #6366f1;">MASIH PENGERJAAN</div>
                <div class="card-subtext">total penjualan : masih pengerjaan </div>
            </div>
        """, unsafe_allow_html=True)

    with m4:
        st.markdown("""
            <div class="white-card">
                <span style="font-size: 20px;">⚠️</span>
                <div class="card-label" style="margin-top: 8px;">GAP TARGET</div>
                <div class="card-value" style="color: #ef4444;">Masih Pengerjaan</div>
                <div class="card-subtext">Time Factor : masih pengerjaan</div>
            </div>
        """, unsafe_allow_html=True)

    # --- SECTION 2: MONITORING IKT ---
    st.markdown("<p style='color: #0f172a; font-weight: bold; font-size: 15px; margin-top: 10px;'>🔵 Detail Per Indikator KPI</p>", unsafe_allow_html=True)
    
    k1, k2, k3 = st.columns(3)
    
    with k1:
        st.markdown("""
            <div class="white-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 18px;">🛒</span> <b>Sales</b>
                        <p style="color: #94a3b8; font-size: 10px; margin:0; font-weight:bold;">UP-SELLING</p>
                    </div>
                    <span class="badge-success">TERCAPAI</span>
                </div>
                <hr style="margin: 12px 0; border: 0.5px solid #f1f5f9;">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div class="card-label">TOTAL ACTUAL</div>
                        <div style="font-size: 20px; font-weight: 800; color: #0f172a;">333</div>
                    </div>
                    <div>
                        <div class="card-label">RATA-RATA ACV</div>
                        <div style="font-size: 20px; font-weight: 800; color: #16a34a;">147%</div>
                    </div>
                </div>
                <div style="margin-top: 12px; font-size: 11px; color: #64748b;">
                    🏆 ACV TERBESAR: <b>mia - 190%</b>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with k2:
        st.markdown("""
            <div class="white-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 18px;">🎁</span> <b>PWP</b>
                        <p style="color: #94a3b8; font-size: 10px; margin:0; font-weight:bold;">BUNDLING</p>
                    </div>
                    <span class="badge-success">TERCAPAI</span>
                </div>
                <hr style="margin: 12px 0; border: 0.5px solid #f1f5f9;">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div class="card-label">TOTAL ACTUAL</div>
                        <div style="font-size: 20px; font-weight: 800; color: #0f172a;">141</div>
                    </div>
                    <div>
                        <div class="card-label">RATA-RATA ACV</div>
                        <div style="font-size: 20px; font-weight: 800; color: #16a34a;">140%</div>
                    </div>
                </div>
                <div style="margin-top: 12px; font-size: 11px; color: #64748b;">
                    🏆 ACV TERBESAR: <b>mia - 182%</b>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with k3:
        st.markdown("""
            <div class="white-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 18px;">🧴</span> <b>SERTIS</b>
                        <p style="color: #94a3b8; font-size: 10px; margin:0; font-weight:bold;">SERBA GRATIS</p>
                    </div>
                    <span class="badge-success">TERCAPAI</span>
                </div>
                <hr style="margin: 12px 0; border: 0.5px solid #f1f5f9;">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div class="card-label">TOTAL ACTUAL</div>
                        <div style="font-size: 20px; font-weight: 800; color: #0f172a;">97</div>
                    </div>
                    <div>
                        <div class="card-label">RATA-RATA ACV</div>
                        <div style="font-size: 20px; font-weight: 800; color: #16a34a;">124%</div>
                    </div>
                </div>
                <div style="margin-top: 12px; font-size: 11px; color: #64748b;">
                    🏆 ACV TERBESAR: <b>Listi - 167%</b>
                </div>
            </div>
        """, unsafe_allow_html=True)
