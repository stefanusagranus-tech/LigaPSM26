"""
LigaPSM v2 — Main App (FASE 1: Daily Performance)
==================================================
Base data: Supabase
Backup: LIGAPSM_AUDIT (Sheets)
Laporan: LIGAPSM-LAPORAN (Sheets)

Version: 2.0.0
Fase: 1 (Daily Performance)
"""

import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Import Supabase connector
from supabase_connector import (
    test_connection,
    login_check_supabase,
    get_user_info,
    sb_read,
    sb_insert,
    sb_upsert,
    sb_update,
    sb_delete,
    sb_count,
    load_periode_store_supabase,
    get_active_period_store_supabase,
    load_daily_performance_supabase,
    save_daily_performance_supabase,
    generate_daily_record_id_supabase,
    invalidate_daily_perf_cache,
    invalidate_periode_cache,
    log_activity_supabase,
    backup_via_gsheets_connection,
    check_and_auto_backup,
)

# =========================================================================
# KONFIGURASI HALAMAN
# =========================================================================
st.set_page_config(
    page_title="LigaPSM v2 — Daily Performance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================================
# WAKTU WIB
# =========================================================================
waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%A, %d %B %Y | %H:%M WIB")


# =========================================================================
# 🎬 SPLASH SCREEN
# =========================================================================
def show_splash_screen(title="MEMUAT DATA", subtitle="Menyiapkan...", icon="🔮", duration_ms=1500):
    """Splash screen animasi."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f"""
            <div style="
                position: fixed; top: 0; left: 0;
                width: 100vw; height: 100vh;
                z-index: 999999;
                background: radial-gradient(circle at top, #162447 0%, #0c1427 60%, #05070c 100%);
                display: flex; flex-direction: column;
                justify-content: center; align-items: center;
                color: white;
            ">
                <div style="font-size: 70px; animation: pulse 1.5s infinite ease-in-out;">{icon}</div>
                <h1 style="color: #fbbf24; font-family: monospace; margin-top: 30px; font-size: 24px; letter-spacing: 2px;">{title}</h1>
                <p style="color: #64748b; font-size: 13px; margin-top: 8px; font-family: monospace;">{subtitle}</p>
                <style>
                    @keyframes pulse {{
                        0%, 100% {{ transform: scale(1); filter: drop-shadow(0 0 15px #fbbf24); }}
                        50% {{ transform: scale(1.15); filter: drop-shadow(0 0 30px #fbbf24); }}
                    }}
                </style>
            </div>
            """,
            unsafe_allow_html=True
        )
        time.sleep(duration_ms / 1000)
    placeholder.empty()


# =========================================================================
# 🎨 CSS GLOBAL
# =========================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Quicksand:wght@600;700&family=MedievalSharp&display=swap');

    /* BACKGROUND */
    .stApp {
        background: radial-gradient(ellipse at top, #2d4f7c 0%, #1e3a5f 30%, #0f172a 70%, #0a0f1a 100%) !important;
        color: #f1e5c7 !important;
        font-family: 'Quicksand', sans-serif !important;
    }

    /* HIDE SIDEBAR DEFAULT */
    [data-testid="stHeader"], [data-testid="stToolbar"] {
        display: none !important;
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0c1427 0%, #05070c 100%) !important;
        border-right: 2px solid #9a7b38 !important;
    }

    /* SCROLLBAR */
    ::-webkit-scrollbar { width: 12px; height: 12px; }
    ::-webkit-scrollbar-track { background: #0b0f19; }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #d4af37, #9a7b38);
        border-radius: 6px;
        border: 2px solid #0b0f19;
    }

    /* TOMBOL */
    div.stButton > button, div.stFormSubmitButton > button {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
        color: #f7e7b4 !important;
        border: 1.5px solid #d4af37 !important;
        border-radius: 8px !important;
        font-family: 'Cinzel', serif !important;
        font-weight: bold !important;
        font-size: 13px !important;
        min-height: 44px !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background: linear-gradient(180deg, #d4af37 0%, #9a7b38 100%) !important;
        color: #0b0f19 !important;
        box-shadow: 0 0 12px rgba(212, 175, 55, 0.5) !important;
    }

    /* INPUT */
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div {
        background-color: rgba(15, 23, 42, 0.95) !important;
        border: 1.5px solid #b45309 !important;
        border-radius: 8px !important;
        min-height: 44px !important;
    }
    div[data-baseweb="input"] input,
    div[data-baseweb="select"] span {
        color: #f1e5c7 !important;
        font-weight: bold !important;
    }

    /* LABEL */
    label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label {
        color: #fef3c7 !important;
        font-family: 'Cinzel', serif !important;
        font-weight: 700 !important;
        font-size: 13px !important;
    }

    /* METRIC */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
        border: 1.5px solid #b45309 !important;
        padding: 16px !important;
        border-radius: 12px !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f7e7b4 !important;
        font-family: 'MedievalSharp', serif !important;
        font-size: 28px !important;
    }

    /* DATAFRAME */
    div[data-testid="stDataFrame"] {
        border: 1.5px solid #d4af37 !important;
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================================
# INISIALISASI SESSION STATE
# =========================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "welcome_shown" not in st.session_state:
    st.session_state.welcome_shown = False
if "selected_tab" not in st.session_state:
    st.session_state.selected_tab = "📊 Daily Performance"


# =========================================================================
# 🚀 AUTO BACKUP (GANTI HARI)
# =========================================================================
if st.session_state.get("logged_in", False):
    try:
        check_and_auto_backup()
    except Exception as e:
        print(f"[AUTO BACKUP ERROR] {e}")
    # =========================================================================
# 🔐 HALAMAN LOGIN
# =========================================================================
def show_login_page():
    """Halaman login baca dari Supabase."""

    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }

        .login-container {
            max-width: 450px;
            margin: 80px auto;
            padding: 40px 32px;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.92));
            border: 2px solid rgba(212, 175, 55, 0.5);
            border-radius: 24px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.7);
            text-align: center;
        }

        .login-title {
            font-family: 'MedievalSharp', serif;
            font-size: 28px;
            font-weight: 900;
            color: #fbbf24;
            margin-bottom: 8px;
            text-shadow: 0 0 20px rgba(251, 191, 36, 0.6);
        }

        .login-subtitle {
            font-family: 'Quicksand', sans-serif;
            font-size: 12px;
            color: #94a3b8;
            letter-spacing: 2px;
            margin-bottom: 30px;
            text-transform: uppercase;
        }

        .login-icon {
            font-size: 60px;
            margin-bottom: 20px;
            display: block;
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
        <div style='text-align: center; margin-top: 40px;'>
            <div class='login-icon'>⚜️</div>
            <h1 class='login-title'>LIGA PSM v2</h1>
            <p class='login-subtitle'>Daily Performance Dashboard</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form_v2"):
            username_input = st.text_input(
                "👤 Username",
                placeholder="Masukkan username",
                key="login_user_v2"
            ).strip()
            password_input = st.text_input(
                "🔒 Password",
                type="password",
                placeholder="Masukkan password",
                key="login_pass_v2"
            )
            submit = st.form_submit_button("⚔️ MASUK APLIKASI ⚔️", use_container_width=True)

        if submit:
            if not username_input or not password_input:
                st.warning("⚠️ Username dan Password wajib diisi!")
            else:
                with st.spinner("🔐 Verifikasi login..."):
                    ok, user_data = login_check_supabase(username_input, password_input)

                if ok and user_data:
                    st.session_state.logged_in = True
                    st.session_state.username = user_data.get("person_name", username_input)
                    st.session_state.role = user_data.get("role", "Staff")
                    st.session_state.person_id = user_data.get("person_id", "")
                    st.session_state.welcome_shown = False
                    st.session_state.session_id = f"{int(time.time())}"

                    # Log activity
                    try:
                        log_activity_supabase(
                            "LOGIN",
                            f"Login v2 sebagai {user_data.get('person_name', username_input)}",
                            username=user_data.get("person_name", username_input),
                            role=user_data.get("role", "Staff"),
                            session_id=st.session_state.session_id,
                        )
                    except Exception as e:
                        print(f"[LOG LOGIN] {e}")

                    st.success("✅ Login berhasil!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    # Log failed
                    try:
                        log_activity_supabase(
                            "LOGIN_FAILED",
                            f"Gagal login: {username_input}",
                            username=username_input,
                            role="-",
                        )
                    except Exception:
                        pass

                    st.error("❌ Username atau Password salah!")


# =========================================================================
# 🎬 WELCOME SCREEN
# =========================================================================
def show_welcome_screen():
    """Welcome screen setelah login."""
    import hashlib

    username = st.session_state.get("username", "User")

    # Sapaan waktu
    hour = waktu_wib.hour
    if 4 <= hour < 11:
        sapaan = "Selamat Pagi"
    elif 11 <= hour < 15:
        sapaan = "Selamat Siang"
    elif 15 <= hour < 18:
        sapaan = "Selamat Sore"
    else:
        sapaan = "Selamat Malam"

    # Avatar
    avatar_list = ["🧙‍♂️", "🧝‍♂️", "🧝‍♀️", "⚔️", "🎯", "🛡️", "🦁", "🦅",
                   "🐺", "👑", "💎", "🔮", "🔥", "🏹", "🪄", "🗡️"]
    h = int(hashlib.md5(username.upper().encode()).hexdigest(), 16)
    avatar = avatar_list[h % len(avatar_list)]

    st.markdown(f"""
    <style>
        [data-testid="stSidebar"] {{ display: none !important; }}
        [data-testid="stHeader"] {{ display: none !important; }}

        .welcome-container {{
            position: fixed; top: 0; left: 0;
            width: 100vw; height: 100vh;
            z-index: 1;
            background: radial-gradient(ellipse at top, #1e3a5f 0%, #0f172a 50%, #05070c 100%);
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
        }}

        .welcome-avatar {{
            width: 140px; height: 140px;
            border-radius: 50%;
            background: radial-gradient(circle, #1e293b 0%, #0f172a 100%);
            border: 4px solid #d4af37;
            display: flex; justify-content: center; align-items: center;
            font-size: 70px;
            margin-bottom: 32px;
            box-shadow: 0 0 40px rgba(212, 175, 55, 0.6);
            animation: pulse 2.5s infinite ease-in-out;
        }}

        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.08); }}
        }}

        .welcome-greeting {{
            font-family: 'Quicksand', sans-serif;
            font-size: 16px;
            color: #d4af37;
            font-weight: 700;
            letter-spacing: 6px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}

        .welcome-name {{
            font-family: 'MedievalSharp', serif;
            font-size: 44px;
            font-weight: 900;
            letter-spacing: 3px;
            margin: 0 0 20px 0;
            background: linear-gradient(90deg, #f7e7b4 0%, #d4af37 50%, #f7e7b4 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-align: center;
        }}

        div[data-testid="stButton"]:last-of-type {{
            position: fixed !important;
            bottom: 80px !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            z-index: 999999 !important;
            max-width: 340px !important;
            min-width: 280px !important;
        }}

        div[data-testid="stButton"]:last-of-type > button {{
            background: linear-gradient(135deg, #b45309 0%, #d97706 100%) !important;
            color: #ffffff !important;
            border: 2px solid #fbbf24 !important;
            border-radius: 50px !important;
            font-size: 15px !important;
            font-weight: 900 !important;
            min-height: 64px !important;
            letter-spacing: 2px !important;
        }}
    </style>

    <div class="welcome-container">
        <div class="welcome-avatar">{avatar}</div>
        <p class="welcome-greeting">{sapaan}</p>
        <h1 class="welcome-name">{username}</h1>
    </div>
    """, unsafe_allow_html=True)

    if st.button("⚔️ MASUK KE APLIKASI", use_container_width=True, key="btn_enter_v2"):
        st.session_state.welcome_shown = True
        st.rerun()

    st.stop()
  # =========================================================================
# 🧭 SIDEBAR
# =========================================================================
def render_sidebar():
    """Sidebar dengan menu navigasi."""
    with st.sidebar:
        # Logo & User
        st.markdown(f"""
        <div style='text-align: center; padding: 15px 10px; border-bottom: 1px solid #334155; margin-bottom: 15px;'>
            <div style='font-size: 40px; margin-bottom: 8px;'>⚜️</div>
            <div style='font-family: Cinzel, serif; font-size: 16px; font-weight: 900; color: #fbbf24;'>
                LIGAPSM v2
            </div>
            <div style='font-family: monospace; font-size: 9px; color: #64748b; letter-spacing: 1px; margin-top: 2px;'>
                FASE 1 — DAILY PERFORMANCE
            </div>
        </div>
        """, unsafe_allow_html=True)

        # User info
        st.markdown(f"""
        <div style='padding: 10px 12px; background: rgba(15, 23, 42, 0.6); border-radius: 8px; margin-bottom: 20px;'>
            <div style='font-family: monospace; font-size: 9px; color: #64748b;'>LOGGED IN AS</div>
            <div style='font-family: Quicksand, sans-serif; font-size: 13px; color: #f1e5c7; font-weight: 700; margin-top: 2px;'>
                {st.session_state.get("username", "User")}
            </div>
            <div style='font-family: monospace; font-size: 10px; color: #94a3b8; margin-top: 2px;'>
                🎭 {st.session_state.get("role", "Staff")}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Menu
        st.markdown("<div style='font-family: monospace; font-size: 10px; color: #64748b; letter-spacing: 1px; padding: 0 12px; margin-bottom: 8px;'>📌 NAVIGASI</div>", unsafe_allow_html=True)

        menu_options = [
            "📊 Daily Performance",
            "📝 PSM (Coming Soon)",
            "⚙️ PPS (Coming Soon)",
            "⚙️ Master Data (Coming Soon)",
        ]

        selected = st.radio(
            "Menu",
            menu_options,
            index=menu_options.index(st.session_state.get("selected_tab", menu_options[0])) if st.session_state.get("selected_tab") in menu_options else 0,
            key="sidebar_menu_v2",
            label_visibility="collapsed",
        )
        st.session_state.selected_tab = selected

        st.markdown("<br>", unsafe_allow_html=True)

        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True, key="btn_refresh_v2"):
            st.cache_data.clear()
            invalidate_daily_perf_cache()
            invalidate_periode_cache()
            st.toast("✅ Cache di-refresh!", icon="⚡")
            time.sleep(0.5)
            st.rerun()

        # Logout
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True, key="btn_logout_v2"):
            try:
                log_activity_supabase("LOGOUT", "Logout dari v2")
            except Exception:
                pass

            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.session_state.welcome_shown = False
            st.rerun()


# =========================================================================
# 🏛️ HEADER UTAMA
# =========================================================================
def render_header():
    """Header dengan judul & info."""
    st.markdown(f"""
    <div style='
        background: radial-gradient(circle, #1e3a5f 0%, #0f172a 100%);
        border: 2px solid #b45309;
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 20px;
        text-align: center;
        position: relative;
        box-shadow: 0 0 25px rgba(180, 83, 9, 0.35);
    '>
        <div style='
            position: absolute; top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, transparent, #d4af37, #fbbf24, #d4af37, transparent);
        '></div>

        <h1 style='
            font-family: Cinzel, serif;
            font-size: 22px;
            font-weight: 900;
            color: #fbbf24;
            letter-spacing: 2px;
            margin: 0 0 6px 0;
            text-shadow: 0 0 15px rgba(251, 191, 36, 0.6);
        '>📊 DAILY PERFORMANCE</h1>

        <p style='
            font-family: Quicksand, sans-serif;
            font-size: 11px;
            color: #94a3b8;
            letter-spacing: 1.5px;
            margin: 0;
        '>Toko C383 — Karang Satria • {current_time_str}</p>

        <div style='
            display: inline-block;
            margin-top: 10px;
            padding: 4px 12px;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid #10b981;
            border-radius: 12px;
            font-family: monospace;
            font-size: 10px;
            color: #34d399;
            font-weight: 900;
        '>🟢 SUPABASE CONNECTED</div>
    </div>
    """, unsafe_allow_html=True)
  # =========================================================================
# 📊 DAILY PERFORMANCE — FORM INPUT
# =========================================================================
def render_daily_performance():
    """Halaman Daily Performance."""

    # Cek periode aktif
    active_period = get_active_period_store_supabase()

    if active_period is None:
        render_no_period_page()
        return

    # Info periode
    render_period_info(active_period)

    # Warning target
    if active_period.get("target_warning", False):
        st.warning("⚠️ Target belum di-set lengkap. Hubungi admin.")

    # Form input
    render_daily_input_form(active_period)

    # Preview data
    render_daily_preview()


# =========================================================================
# 🚨 NO PERIOD PAGE
# =========================================================================
def render_no_period_page():
    """Halaman kalau belum ada periode aktif."""
    st.markdown("""
    <div style='
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(220, 38, 38, 0.15));
        border: 2px solid #ef4444;
        border-radius: 14px;
        padding: 30px 24px;
        text-align: center;
        margin: 30px 0;
    '>
        <div style='font-size: 60px; margin-bottom: 15px;'>📅</div>
        <h2 style='color: #fca5a5; font-family: Cinzel, serif; margin: 0 0 10px 0; font-size: 20px;'>
            BELUM ADA PERIODE AKTIF
        </h2>
        <p style='color: #94a3b8; font-family: monospace; font-size: 12px; margin: 0;'>
            Buat periode baru terlebih dahulu di bawah ini
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("➕ Buat Periode Baru", expanded=True):
        with st.form("form_add_periode_v2"):
            col1, col2 = st.columns(2)

            with col1:
                pid = st.text_input("🆔 ID Periode", placeholder="Contoh: SP01").strip().upper()
                pname = st.text_input("📝 Nama Periode", placeholder="Contoh: Sales Sep 2026").strip()
                start = st.date_input("📅 Tanggal Mulai", value=waktu_wib.date(), key="periode_start_v2")
                end = st.date_input("📅 Tanggal Selesai", value=waktu_wib.date(), key="periode_end_v2")

            with col2:
                target_ns = st.number_input("💰 Target Net Sales (Rp)", min_value=0, step=100000, value=0, key="periode_ns_v2")
                target_std = st.number_input("📄 Target STD (struk)", min_value=0, step=1, value=0, key="periode_std_v2")
                nsb_pct = st.number_input("📊 NSB% (persen)", min_value=0.0, max_value=100.0, step=0.01, value=0.15, key="periode_nsb_v2")
                target_gm = st.number_input("💹 Target GM%", min_value=0.0, max_value=100.0, step=0.1, value=0.0, key="periode_gm_v2")

            submit = st.form_submit_button("💾 SIMPAN PERIODE", use_container_width=True, type="primary")

        if submit:
            if not pid or not pname:
                st.error("❌ ID & Nama Periode wajib diisi!")
            elif start > end:
                st.error("❌ Tanggal mulai > tanggal selesai!")
            elif target_ns <= 0 or target_std <= 0:
                st.error("❌ Target Net Sales & STD harus > 0!")
            else:
                # Hitung auto value
                jhk = (end - start).days + 1
                target_spd = int(target_ns / jhk) if jhk > 0 else 0
                target_apc = int(target_spd / target_std) if target_std > 0 else 0

                record = {
                    "period_id": pid,
                    "period_name": pname,
                    "start_date": str(start),
                    "end_date": str(end),
                    "target_net_sales": int(target_ns),
                    "target_std": int(target_std),
                    "target_apc": int(target_apc),
                    "target_gm_pct": float(target_gm),
                    "nsb_percentage": float(nsb_pct),
                    "status": "Aktif",
                }

                with st.spinner("💾 Menyimpan periode..."):
                    ok, msg, count = sb_upsert("periode_store", [record], on_conflict="period_id")

                if ok:
                    st.success(f"✅ Periode {pname} berhasil disimpan!")
                    invalidate_periode_cache()
                    try:
                        log_activity_supabase("SAVE_MASTER", f"Tambah periode: {pid}")
                    except Exception:
                        pass
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Gagal simpan: {msg}")


# =========================================================================
# 📊 PERIOD INFO CARD
# =========================================================================
def render_period_info(period):
    """Tampilkan info periode aktif."""
    st.markdown(f"""
    <div style='
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.85));
        border: 1.5px solid #9a7b38;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 20px;
    '>
        <div style='
            font-family: Cinzel, serif;
            font-size: 13px;
            color: #fbbf24;
            font-weight: 800;
            letter-spacing: 1px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1.5px dashed rgba(180, 83, 9, 0.4);
        '>📅 PERIODE AKTIF</div>

        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px;'>
            <div style='background: rgba(30, 41, 59, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; text-align: center;'>
                <div style='font-family: monospace; font-size: 9px; color: #94a3b8; margin-bottom: 4px;'>NAMA</div>
                <div style='font-family: Cinzel, serif; font-size: 12px; color: #fbbf24; font-weight: 900;'>{period['period_name']}</div>
            </div>
            <div style='background: rgba(30, 41, 59, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; text-align: center;'>
                <div style='font-family: monospace; font-size: 9px; color: #94a3b8; margin-bottom: 4px;'>JHK</div>
                <div style='font-family: Cinzel, serif; font-size: 12px; color: #fbbf24; font-weight: 900;'>{period['jhk']} hari</div>
            </div>
            <div style='background: rgba(30, 41, 59, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; text-align: center;'>
                <div style='font-family: monospace; font-size: 9px; color: #94a3b8; margin-bottom: 4px;'>TARGET SPD</div>
                <div style='font-family: Cinzel, serif; font-size: 12px; color: #fbbf24; font-weight: 900;'>Rp {period['target_spd']:,}</div>
            </div>
            <div style='background: rgba(30, 41, 59, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; text-align: center;'>
                <div style='font-family: monospace; font-size: 9px; color: #94a3b8; margin-bottom: 4px;'>TARGET STD</div>
                <div style='font-family: Cinzel, serif; font-size: 12px; color: #fbbf24; font-weight: 900;'>{period['target_std']} struk</div>
            </div>
            <div style='background: rgba(30, 41, 59, 0.8); border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; text-align: center;'>
                <div style='font-family: monospace; font-size: 9px; color: #94a3b8; margin-bottom: 4px;'>TARGET APC</div>
                <div style='font-family: Cinzel, serif; font-size: 12px; color: #fbbf24; font-weight: 900;'>Rp {period['target_apc']:,}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# 📝 INPUT FORM
# =========================================================================
def render_daily_input_form(period):
    """Form input data harian."""
    st.markdown("---")
    st.markdown("##### 📝 Form Input Data Harian")

    today = waktu_wib.date()

    with st.form("form_daily_v2", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            input_tanggal = st.date_input("📅 Tanggal", value=today, key="daily_date_v2")

        with col2:
            input_keterangan = st.text_input("📝 Keterangan (opsional)", placeholder="Contoh: event promo", key="daily_ket_v2")

        st.markdown("**💰 Data Sales & Struk**")
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            input_spd = st.number_input("💰 SPD (Sales Per Day) — Rp", min_value=0, step=100000, value=0, key="daily_spd_v2")

        with col_s2:
            input_std = st.number_input("📄 STD (Struk Per Day) — struk", min_value=0, step=1, value=0, key="daily_std_v2")

        # Preview auto-calc
        if input_spd > 0 and input_std > 0:
            preview_apc = int(input_spd / input_std)
            preview_nsb_target = int(input_spd * (period['nsb_percentage'] / 100))

            st.markdown(f"""
            <div style='
                background: linear-gradient(135deg, rgba(56, 189, 248, 0.1), rgba(14, 165, 233, 0.15));
                border: 1.5px solid #38bdf8;
                border-radius: 10px;
                padding: 12px 16px;
                margin: 12px 0;
            '>
                <div style='font-family: monospace; font-size: 10px; color: #38bdf8; font-weight: 900; letter-spacing: 1.5px; margin-bottom: 8px; text-align: center;'>
                    📊 AUTO-CALCULATED
                </div>
                <div style='display: flex; justify-content: space-between; font-family: monospace; font-size: 11px; padding: 3px 0;'>
                    <span style='color: #94a3b8;'>👥 APC (SPD ÷ STD)</span>
                    <span style='color: #38bdf8; font-weight: 900;'>Rp {preview_apc:,}</span>
                </div>
                <div style='display: flex; justify-content: space-between; font-family: monospace; font-size: 11px; padding: 3px 0;'>
                    <span style='color: #94a3b8;'>⚠️ NSB Target</span>
                    <span style='color: #38bdf8; font-weight: 900;'>Rp {preview_nsb_target:,}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("**⚠️ NSB (Nota Selisih Barang)**")
        input_nsb_actual = st.number_input(
            "NSB Actual — Rp (boleh minus)",
            min_value=-999_999_999_999,
            max_value=999_999_999_999,
            step=1000,
            value=0,
            key="daily_nsb_v2",
            help="Isi minus (-) kalau ada selisih negatif"
        )

        submit = st.form_submit_button("💾 SIMPAN DATA HARIAN", use_container_width=True, type="primary")

    # Proses simpan
    if submit:
        errors = []
        if input_spd <= 0:
            errors.append("SPD harus > 0")
        if input_std <= 0:
            errors.append("STD harus > 0")

        if errors:
            for e in errors:
                st.error(f"❌ {e}")
        else:
            apc = int(input_spd / input_std)
            nsb_target = int(input_spd * (period['nsb_percentage'] / 100))

            # Cek existing (update atau insert)
            existing_df = load_daily_performance_supabase()
            is_update = False
            record_id = None

            if not existing_df.empty and "tanggal" in existing_df.columns:
                existing_df["_tgl"] = pd.to_datetime(existing_df["tanggal"], errors="coerce").dt.date
                match = existing_df[existing_df["_tgl"] == input_tanggal]
                if not match.empty:
                    is_update = True
                    record_id = str(match.iloc[0]["record_id"])

            if not record_id:
                record_id = generate_daily_record_id_supabase()

            record = {
                "record_id": record_id,
                "tanggal": str(input_tanggal),
                "spd": int(input_spd),
                "std": int(input_std),
                "apc": int(apc),
                "nsb_target": int(nsb_target),
                "nsb_actual": int(input_nsb_actual),
                "keterangan": str(input_keterangan),
                "input_by": st.session_state.get("username", "unknown"),
            }

            with st.spinner("💾 Menyimpan data harian..."):
                ok, msg = save_daily_performance_supabase(record)

            if ok:
                action_text = "diperbarui" if is_update else "disimpan"
                st.success(f"✅ Data harian {input_tanggal.strftime('%d/%m/%Y')} berhasil {action_text}!")

                try:
                    log_activity_supabase(
                        "INPUT",
                        f"Daily Performance: {input_tanggal.strftime('%d/%m/%Y')} - SPD: {input_spd:,}"
                    )
                except Exception:
                    pass

                time.sleep(1.5)
                st.rerun()
            else:
                st.error(f"❌ Gagal simpan: {msg}")


# =========================================================================
# 📋 PREVIEW DATA
# =========================================================================
def render_daily_preview():
    """Preview 10 data terakhir."""
    df = load_daily_performance_supabase()

    if df.empty:
        st.info("📭 Belum ada data harian.")
        return

    st.markdown("---")
    st.markdown("##### 📋 Data 10 Hari Terakhir")

    preview = df.copy()
    if "tanggal" in preview.columns:
        preview["_tgl"] = pd.to_datetime(preview["tanggal"], errors="coerce")
        preview = preview.sort_values("_tgl", ascending=False).head(10)

        display_cols = []
        for c in ["tanggal", "spd", "std", "apc", "nsb_target", "nsb_actual", "input_by"]:
            if c in preview.columns:
                display_cols.append(c)

        if display_cols:
            show_df = preview[display_cols].copy()
            show_df.columns = [c.replace("_", " ").title() for c in display_cols]
            st.dataframe(show_df, use_container_width=True, hide_index=True)


# =========================================================================
# 🚧 COMING SOON PAGE
# =========================================================================
def render_coming_soon(feature_name):
    """Halaman placeholder untuk fitur yang belum jadi."""
    st.markdown(f"""
    <div style='
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9));
        border: 2px dashed #64748b;
        border-radius: 14px;
        padding: 60px 24px;
        text-align: center;
        margin: 40px 0;
    '>
        <div style='font-size: 80px; margin-bottom: 20px;'>🚧</div>
        <h2 style='color: #cbd5e1; font-family: Cinzel, serif; margin: 0 0 10px 0; font-size: 22px;'>
            {feature_name}
        </h2>
        <p style='color: #64748b; font-family: monospace; font-size: 12px; margin: 0;'>
            Fitur ini akan diimplementasi di fase berikutnya
        </p>
        <div style='
            display: inline-block;
            margin-top: 20px;
            padding: 6px 16px;
            background: rgba(251, 191, 36, 0.15);
            border: 1px solid #fbbf24;
            border-radius: 20px;
            font-family: monospace;
            font-size: 11px;
            color: #fbbf24;
            font-weight: 900;
        '>📅 COMING SOON — FASE 2/3</div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# 🎯 MAIN APP ROUTER
# =========================================================================
def main():
    # Login page
    if not st.session_state.logged_in:
        show_login_page()
        st.stop()

    # Welcome screen
    if not st.session_state.get("welcome_shown", False):
        show_welcome_screen()
        st.stop()

    # Sidebar
    render_sidebar()

    # Header
    render_header()

    # Content based on selected tab
    selected = st.session_state.get("selected_tab", "📊 Daily Performance")

    if selected == "📊 Daily Performance":
        render_daily_performance()
    elif selected == "📝 PSM (Coming Soon)":
        render_coming_soon("PSM — Input Sales Personil")
    elif selected == "⚙️ PPS (Coming Soon)":
        render_coming_soon("PPS — Input Sales PPS")
    elif selected == "⚙️ Master Data (Coming Soon)":
        render_coming_soon("Master Data & Pengaturan")


# =========================================================================
# RUN
# =========================================================================
if __name__ == "__main__":
    main()
