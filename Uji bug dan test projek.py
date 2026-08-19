import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
import time
import textwrap 

# =========================================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# =========================================================
st.set_page_config(
    page_title="PSM Toko - Sales Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ID SPREADSHEET GOOGLE SHEETS
SPREADSHEET_ID = "1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk"

# =========================================================
# 2. INISIALISASI KONEKSI GOOGLE SHEETS & FUNGSI DATABASE
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)

def load_database():
    """Membaca data realtime secara langsung dari Google Sheets."""
    try:
        periods_df = conn.read(worksheet="PERIODE", ttl=0)
        items_df = conn.read(worksheet="MASTER_ITEM", ttl=0)
        person_df = conn.read(worksheet="MASTER_PERSONIL", ttl=0)
        sales_item_df = conn.read(worksheet="SALES_ITEM", ttl=0)
        sales_person_df = conn.read(worksheet="SALES_PERSONIL", ttl=0)
        
        # Otomatis rapikan nama kolom (huruf kecil & hapus spasi)
        for df in [periods_df, items_df, person_df, sales_item_df, sales_person_df]:
            if not df.empty:
                df.columns = df.columns.astype(str).str.strip().str.lower()
                
        # Normalisasi tipe ID ke string agar merging aman
        for df in [periods_df, sales_item_df, sales_person_df]:
            if not df.empty and "period_id" in df.columns:
                df["period_id"] = df["period_id"].astype(str).str.strip()
                
        for df in [items_df, sales_item_df, sales_person_df]:
            if not df.empty and "item_id" in df.columns:
                df["item_id"] = df["item_id"].astype(str).str.strip()

        # Normalisasi nama personil (Hapus spasi ganda/awal/akhir & Kapitalisasi)
        for df in [person_df, sales_person_df]:
            if not df.empty and "person_name" in df.columns:
                df["person_name"] = df["person_name"].astype(str).str.strip().str.upper()
                df["person_name"] = df["person_name"].str.replace(r"\s+", " ", regex=True)

        return periods_df, items_df, person_df, sales_item_df, sales_person_df
    except Exception as e:
        st.error(f"Gagal membaca Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def save_database(sales_item_df, sales_person_df):
    """Menyimpan data transaksi harian ke Google Sheets secara permanen."""
    try:
        conn.update(worksheet="SALES_ITEM", data=sales_item_df)
        conn.update(worksheet="SALES_PERSONIL", data=sales_person_df)
        st.toast("Perubahan transaksi tersimpan permanen di Google Sheets!", icon="✅")
        return True
    except Exception as e:
        st.error(f"Gagal menyimpan transaksi ke Google Sheets: {e}")
        return False

def save_master_table(sheet_name, df_data):
    """Menyimpan perubahan master data (Personil/Item/Periode) ke Google Sheets."""
    try:
        conn.update(worksheet=sheet_name, data=df_data)
        st.toast(f"Master {sheet_name} berhasil diperbarui di Google Sheets!", icon="✅")
        return True
    except Exception as e:
        st.error(f"Gagal update master {sheet_name}: {e}")
        return False

def sync_store_sales_from_personnel():
    """Merekap total penjualan seluruh personil toko dan memperbarui actual_qty pada Penjualan Toko."""
    if "sales_person_df" in st.session_state and "sales_item_df" in st.session_state:
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

        sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)
        tot_per_item = sp_df.groupby(["period_id", "item_id"])["actual_qty"].sum().reset_index()
        tot_per_item.rename(columns={"actual_qty": "calc_actual_qty"}, inplace=True)
        
        if "calc_actual_qty" in si_df.columns:
            si_df.drop(columns=["calc_actual_qty"], inplace=True)
            
        merged = pd.merge(si_df, tot_per_item, on=["period_id", "item_id"], how="left")
        merged["calc_actual_qty"] = merged["calc_actual_qty"].fillna(0)
        merged["actual_qty"] = merged["calc_actual_qty"]
        merged.drop(columns=["calc_actual_qty"], inplace=True)
        st.session_state.sales_item_df = merged

# Load database awal ke session state jika belum ada
if "data_loaded" not in st.session_state:
    p_df, i_df, pers_df, si_df, sp_df = load_database()
    st.session_state.periods_df = p_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.data_loaded = True



# =========================================================
# 3. WAKTU REALTIME GMT+7 (WIB)
# =========================================================
waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%A, %d %B %Y %H:%M WIB")

# =========================================================
# 4. FUNGSI AUTENTIKASI DINAMIS (GOOGLE SHEETS)
# =========================================================
def check_login(input_username, input_password):
    """Mengecek kredensial login secara terpadu dari Google Sheets."""
    input_user_clean = str(input_username).strip().lower()
    input_pass_clean = str(input_password).strip()

    # Pintu Belakang Darurat Admin / Visitor Hardcoded
    if input_user_clean == "admin" and input_pass_clean == "lavitality":
        st.session_state["logged_in"] = True
        st.session_state["username"] = "admin"
        st.session_state["person_name"] = "Administrator"
        st.session_state["user_role"] = "Admin"
        st.session_state["role"] = "Admin"
        return True
    elif input_user_clean == "visitor" and input_pass_clean == "visitor":
        st.session_state["logged_in"] = True
        st.session_state["username"] = "visitor"
        st.session_state["person_name"] = "Pengunjung"
        st.session_state["user_role"] = "Visitor"
        st.session_state["role"] = "Visitor"
        return True

    # Ambil data personil dari session state
    df_users = st.session_state.get("person_df", pd.DataFrame())
    if df_users.empty:
        try:
            df_users = conn.read(worksheet="MASTER_PERSONIL", ttl=0)
            st.session_state.person_df = df_users.copy()
        except Exception:
            df_users = pd.DataFrame()

    if df_users.empty or "username" not in df_users.columns or "password" not in df_users.columns:
        return False

    # Konversi string & bersihkan spasi
    df_users["username_clean"] = df_users["username"].astype(str).str.strip().str.lower()
    df_users["password_clean"] = df_users["password"].astype(str).str.strip()

    user_match = df_users[
        (df_users["username_clean"] == input_user_clean) &
        (df_users["password_clean"] == input_pass_clean)
    ]

    if not user_match.empty:
        matched_user = user_match.iloc[0]
        st.session_state["logged_in"] = True
        st.session_state["username"] = str(matched_user["username"]).strip()
        st.session_state["person_name"] = str(matched_user.get("person_name", matched_user["username"]))
        
        user_role_val = str(matched_user.get("role", "Staff Toko")).strip()
        st.session_state["user_role"] = user_role_val
        st.session_state["role"] = user_role_val
        return True

    return False

# =========================================================
# 5. CUSTOM CSS (NEON DARK THEME)
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #0b0f19; color: #f8fafc; font-family: 'Inter', sans-serif; }
label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label, label p {
    color: #38bdf8 !important; font-weight: 600 !important; font-size: 14px !important;
}
div[data-baseweb="input"] input, div[data-baseweb="select"] input, div[data-baseweb="select"] span {
    color: #ffffff !important; background-color: transparent !important; font-weight: bold !important;
}
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background-color: #0d1117 !important; border: 1.5px solid #00f0ff !important; border-radius: 8px !important;
}
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #38bdf8; padding: 16px; border-radius: 12px; box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
}
div[data-testid="stMetric"] label { color: #94a3b8 !important; font-weight: 700; font-size: 13px; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #38bdf8 !important; text-shadow: 0 0 10px rgba(56, 189, 248, 0.5); font-weight: 800; font-size: 26px;
}
[data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #1e293b; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label { color: #ffffff !important; font-weight: 600; }
div[data-testid="stRadio"] input[type="radio"], div[data-testid="stRadio"] div[role="radiogroup"] div:has(> input[type="radio"]) { display: none !important; }
div[data-testid="stRadio"] div[role="radiogroup"] > label {
    background-color: #1e293b; border: 1px solid #334155; padding: 12px 18px; border-radius: 10px;
    margin-bottom: 8px; color: #ffffff !important; font-weight: 700; cursor: pointer; display: block;
}
div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"], div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
    border: 1px solid #38bdf8 !important; box-shadow: 0 0 18px rgba(56, 189, 248, 0.6) !important; color: #ffffff !important;
}
div.stButton > button, div.stFormSubmitButton > button {
    background-color: #080c14 !important; color: #ffffff !important; border: 2px solid #00f0ff !important;
    border-radius: 8px !important; font-weight: bold !important; box-shadow: 0 0 10px rgba(0, 240, 255, 0.3) !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background-color: #0f172a !important; color: #ef4444 !important; border: 1px solid #ef4444 !important;
}
</style>
""", unsafe_allow_html=True)

# Inisialisasi Session State Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# =========================================================
# 6. HALAMAN LOGIN & LOGIKA AUTHENTICATION
# =========================================================
def show_login_page():
    LOGO_URL = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/kgs_group_belgium_logo.jpg"
    
    st.markdown("""
    <style>
    .login-card { 
        background-color: #1e293b; 
        padding: 25px 20px; 
        border-radius: 16px; 
        box-shadow: 0 10px 25px 5px rgba(0, 0, 0, 0.4); 
        text-align: center; 
        margin-bottom: 20px; 
    }
    .login-logo { 
        width: 100px; 
        height: 100px; 
        object-fit: contain; 
        border-radius: 12px; 
        background-color: #ffffff; 
        padding: 8px; 
        margin-bottom: 12px; 
        display: block; 
        margin-left: auto; 
        margin-right: auto; 
    }
    .login-title { 
        color: #ffffff; 
        font-size: 20px; 
        font-weight: 700; 
        margin-bottom: 4px; 
    }
    .login-subtitle { 
        color: #38bdf8; 
        font-size: 13px; 
        margin-bottom: 0px; 
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        # 1. HEADER LOGO & JUDUL (TAMPIL PALING ATAS)
        st.markdown(f"""
        <div class='login-card'>
            <img src='{LOGO_URL}' class='login-logo' alt='KGS Group Logo'>
            <div class='login-title'>TOKO C383</div>
            <p class='login-subtitle'>Sistem Monitoring PSM Toko</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 2. FORM INPUT LOGIN (BERADA DI BAWAH JUDUL)
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username", placeholder="Masukkan username")
            password_input = st.text_input("Password", type="password", placeholder="Masukkan password")
            submit_btn = st.form_submit_button("Masuk ke Aplikasi", use_container_width=True)

        if submit_btn:
            u_clean = username_input.strip()
            p_clean = password_input.strip()

            if not u_clean or not p_clean:
                st.warning("⚠️ Username dan Password wajib diisi!")
            elif check_login(u_clean, p_clean):
                st.session_state["logged_in"] = True
                user_role = st.session_state.get("role", st.session_state.get("user_role", ""))
                st.session_state["is_admin"] = (str(user_role).strip().lower() == "admin")

                st.toast(f"🎉 Selamat Datang, {st.session_state.get('person_name', u_clean)}!")
                st.rerun()
            else:
                st.error("❌ Username atau Password salah!")

# ---------------------------------------------------------
# PEMBLOKIR UTAMA (Mencegah Akses Sebelum Login)
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    show_login_page()
    st.stop()  # ⛔ KUNCI UTAMA: Hentikan render sidebar & dashboard jika belum login

# =========================================================
# 7. SIDEBAR DASHBOARD & NAVIGASI
# =========================================================
st.sidebar.markdown("""
<style>
.sidebar-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.sidebar-logo { width: 55px; height: 55px; border-radius: 50%; object-fit: cover; border: 1.5px solid #38bdf8; }
.store-title { text-align: center; color: #ffffff; font-size: 22px; font-weight: 700; margin-bottom: 2px; letter-spacing: 1px; }
.store-subtitle { text-align: center; color: #38bdf8; font-size: 12px; font-weight: 600; margin-top: 0px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

LOGO_URL = "https://tse3.mm.bing.net/th/id/OIP.mVrKCdnlL5Yc-3wRmzFXOAAAAA?r=0&rs=1&pid=ImgDetMain&o=7&rm=3"
username = st.session_state.get("username", "Admin")

st.sidebar.markdown(f"""
<div class='sidebar-header'>
    <img src='{LOGO_URL}' class='sidebar-logo'>
    <div style='display: flex; flex-direction: column;'>
        <span style='color: #94a3b8; font-size: 11px; font-weight: 500;'>Selamat Datang Kembali,</span>
        <span style='color: #00ff88; font-size: 13px; font-weight: 700;'>👤 {username}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<hr style='margin: 10px 0; border-color: #334155;'>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='store-title'>TOKO C383</div>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='store-subtitle'>Report PSM dan Target PSM</div>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# 🧪 TEST ROLE SWITCHER DIBUAT DYNAMIC SIKAP ADMIN/DEVELOPER
with st.sidebar.expander("🧪 Mode Testing Role Switcher", expanded=False):
    selected_manual_role = st.selectbox(
        "Pilih Role (Mode Testing):",
        ["Admin", "Staff Toko", "Kasir Toko", "Visitor"],
        index=0,
        key="manual_role_selector"
    )
    st.session_state["user_role"] = selected_manual_role
    st.session_state["role"] = selected_manual_role
    st.info(f"👤 Active Role: **{selected_manual_role}**")

st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>📌 NAVIGASI MENU</p>", unsafe_allow_html=True)
menu_options = [
    "01 Dashboard Toko",
    "02 Raport Personil Toko",
    "03 Report IKT & PPS",
    "04 Pengaturan & Download"
]
selected_tab = st.sidebar.radio("", menu_options, label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>FILTER PERIODE</p>", unsafe_allow_html=True)

periods_df = st.session_state.get("periods_df", pd.DataFrame())
if not periods_df.empty and "period_name" in periods_df.columns and "period_id" in periods_df.columns:
    periods_dict = {str(row["period_name"]): str(row["period_id"]) for _, row in periods_df.iterrows()}
else:
    periods_dict = {"Periode Utama": "P01"}

selected_period_name = st.sidebar.selectbox("", ["Semua Periode (Overall)"] + list(periods_dict.keys()), label_visibility="collapsed")
selected_period_id = None if selected_period_name == "Semua Periode (Overall)" else periods_dict[selected_period_name]

st.sidebar.markdown("<hr style='margin: 15px 0; border-color: #334155;'>", unsafe_allow_html=True)

# 🚪 TOMBOL LOGOUT FIX
if st.sidebar.button("🚪 Keluar / Logout", use_container_width=True):
    st.session_state.clear()
    st.session_state["logged_in"] = False
    st.rerun()



# =========================================================
# 8. HEADER UTAMA
# =========================================================
st.markdown(f"""
<div style='background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 16px 24px; border-radius: 12px; border: 1px solid #38bdf8; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;'>
    <div>
        <h2 style='margin:0; color:#ffffff; font-size: 24px;'>📊 PSM TOKO SALES MONITORING</h2>
        <p style='margin:0; color:#38bdf8; font-size: 13px;'>Sistem Analisis & Optimasi Pencapaian Target Toko</p>
    </div>
    <div style='text-align: right;'>
        <p style='margin:0; color:#94a3b8; font-size: 11px; font-weight:bold;'>WAKTU REALTIME SISTEM</p>
        <p style='margin:0; color:#38bdf8; font-size: 14px; font-weight:bold;'>{current_time_str}</p>
    </div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# 9. MODUL TAB / SUB MENU
# =========================================================

# =========================================================
# --- TAB 01: OVERVIEW & DETAIL ITEM (SUB-TAB DESIGN) ---
# =========================================================
if selected_tab == "01 Dashboard Toko":
    # SUB-TAB NAVIGATION
    sub_tab01 = st.radio(
        "Pilih Tampilan Sub-Tab:",
        ["📊 Overview Penjualan", "📦 Detail Item & Performa Toko"],
        horizontal=True,
        key="sub_tab01_selector",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Prepare datasets
    si_df = st.session_state.sales_item_df.copy()
    sp_df = st.session_state.sales_person_df.copy()
    periods_df = st.session_state.periods_df.copy()

    # Create mapping dictionary for periods if not available
    if "periods_dict" not in locals():
        if not periods_df.empty and "period_id" in periods_df.columns:
            p_col_name = next(
                (
                    c
                    for c in ["period_name", "nama_periode", "periode"]
                    if c in periods_df.columns
                ),
                "period_id",
            )
            periods_dict = dict(zip(periods_df[p_col_name], periods_df["period_id"]))
        else:
            periods_dict = {}

    # =========================================================
    # 1. SUB-TAB 1: OVERVIEW PENJUALAN
    # =========================================================
    if sub_tab01 == "📊 Overview Penjualan":
        st.markdown(
            "<p style='color:#38bdf8; font-weight:bold; font-size:14px; margin-bottom:5px;'>🗓️ PILIH PERIODE PENJUALAN</p>",
            unsafe_allow_html=True,
        )

        period_options = ["Semua Periode (Overall)"] + list(periods_dict.keys())
        selected_p_overview = st.selectbox(
            "Filter Periode Overview",
            period_options,
            key="ov_period_select",
            label_visibility="collapsed",
        )

        # Filter dataset berdasar dropdown periode
        if selected_p_overview != "Semua Periode (Overall)":
            p_id = periods_dict[selected_p_overview]
            sub_periods = periods_df[periods_df["period_id"] == p_id]
            sub_si = si_df[si_df["period_id"] == p_id]
            sub_sp = sp_df[sp_df["period_id"] == p_id]
        else:
            sub_periods = periods_df
            sub_si = si_df
            sub_sp = sp_df

        # Hitung rentang tanggal & time factor
        if not sub_periods.empty and "start_date" in sub_periods.columns:
            start_date = pd.to_datetime(sub_periods["start_date"].min()).date()
            end_date = pd.to_datetime(sub_periods["end_date"].max()).date()
        else:
            start_date = waktu_wib.date().replace(day=1)
            end_date = waktu_wib.date()

        total_days = max((end_date - start_date).days + 1, 1)
        today_date = waktu_wib.date()

        if today_date < start_date:
            passed_days = 0
        elif today_date > end_date:
            passed_days = total_days
        else:
            passed_days = max((today_date - start_date).days + 1, 1)

        time_factor = (passed_days / total_days) * 100 if total_days > 0 else 0

        # Normalisasi Target & Actual
        if "target_qty" not in sub_si.columns:
            sub_si["target_qty"] = 0
        tot_target = pd.to_numeric(
            sub_si["target_qty"], errors="coerce"
        ).fillna(0).sum()

        if "actual_qty" in sub_sp.columns:
            tot_actual = pd.to_numeric(
                sub_sp["actual_qty"], errors="coerce"
            ).fillna(0).sum()
        else:
            tot_actual = 0

        tot_gap = tot_target - tot_actual
        tot_ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0

        # 🎯 KALKULASI INDEKS BOBOT (LINIER DENGAN BASE 20 POINT)
        weighted_score = (tot_ach / 100) * 20

        # 6 METRIC CARDS (3 DI ATAS, 3 DI BAWAH)
        st.markdown("<br>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("🎯 Total Target", f"{tot_target:,.0f} Pcs")
        with m2:
            st.metric("📦 Actual Penjualan", f"{tot_actual:,.0f} Pcs")
        with m3:
            st.metric("📉 Sisa Gap Target", f"{max(tot_gap, 0):,.0f} Pcs")

        st.markdown("<br>", unsafe_allow_html=True)
        m4, m5, m6 = st.columns(3)
        with m4:
            st.metric("⚡ % Achievement Toko", f"{tot_ach:.1f}%")
        with m5:
            st.metric(
                "⏳ Time Factor (Waktu)",
                f"{time_factor:.1f}%",
                help=f"Hari berjalan: {passed_days}/{total_days} hari",
            )
        with m6:
            st.metric(
                "🏆 Indeks Bobot Toko",
                f"{weighted_score:.1f} Point",
                help="Dihitung linier: (% Achievement Toko × 20 Point Base)",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # PACE PENJUALAN CARD STATUS
        pace_gap = tot_ach - time_factor
        if pace_gap >= 0:
            status_color = "#00ff9d"
            status_bg = "rgba(0, 255, 157, 0.08)"
            status_icon = "🚀"
            status_title = "PACE PENJUALAN ON TRACK"
            status_desc = f"Pencapaian penjualan (**{tot_ach:.1f}%**) melampaui laju waktu berjalan (**{time_factor:.1f}%**). Indeks kontribusi bobot toko saat ini mencapai **{weighted_score:.1f} Point** (Acuan 100% = 20 Point)."
        else:
            status_color = "#ff2a6d"
            status_bg = "rgba(255, 42, 109, 0.08)"
            status_icon = "⚠️"
            status_title = "PACE PENJUALAN BEHIND TARGET"
            status_desc = f"Pencapaian penjualan (**{tot_ach:.1f}%**) masih di bawah laju waktu berjalan (**{time_factor:.1f}%**). Indeks kontribusi bobot toko saat ini baru mencapai **{weighted_score:.1f} Point** dari acuan standar 20 Point."

        st.markdown(
            f"""
        <div style="background: {status_bg}; border: 1.5px solid {status_color}; border-left: 6px solid {status_color}; border-radius: 10px; padding: 18px; margin-top: 10px;">
            <h4 style="color: {status_color}; margin: 0 0 6px 0; font-size: 16px;">{status_icon} {status_title}</h4>
            <p style="color: #f1f5f9; margin: 0; font-size: 13.5px; line-height: 1.5;">{status_desc}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # =========================================================
    # 2. SUB-TAB 2: DETAIL ITEM & PERFORMA TOKO
    # =========================================================
    elif sub_tab01 == "📦 Detail Item & Performa Toko":
        st.markdown(
            "<p style='color:#38bdf8; font-weight:bold; font-size:13px;'>🔍 FILTER & PENGURUTAN DATA PRODUK</p>",
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
            selected_p_detail = st.selectbox(
                "Periode Promosi",
                ["Semua Periode Promosi"] + list(periods_dict.keys()),
                key="period_detail_tab",
            )
        with f_col3:
            sort_option = st.selectbox(
                "Urutkan Berdasarkan",
                [
                    "Penjualan Terbanyak (Terlaris)",
                    "Penjualan Tersedikit",
                    "Achievement Tertinggi (% Ach)",
                    "Target/Hari Terbesar",
                    "Nama Produk (A - Z)",
                ],
                key="sort_detail_tab",
            )

        if selected_p_detail != "Semua Periode Promosi":
            p_id_det = periods_dict[selected_p_detail]
            si_det = si_df[si_df["period_id"] == p_id_det].copy()
            p_info = periods_df[periods_df["period_id"] == p_id_det]
        else:
            si_det = si_df.copy()
            p_info = periods_df.copy()

        if not p_info.empty and "start_date" in p_info.columns:
            s_date = pd.to_datetime(p_info["start_date"].min()).date()
            e_date = pd.to_datetime(p_info["end_date"].max()).date()
        else:
            s_date = waktu_wib.date().replace(day=1)
            e_date = waktu_wib.date()

        tot_days_period = max((e_date - s_date).days + 1, 1)
        today_d = waktu_wib.date()

        if today_d < s_date:
            remaining_days = tot_days_period
        elif today_d > e_date:
            remaining_days = 1
        else:
            remaining_days = max((e_date - today_d).days + 1, 1)

        si_det["target_qty"] = pd.to_numeric(
            si_det["target_qty"], errors="coerce"
        ).fillna(0)
        si_det["actual_qty"] = pd.to_numeric(
            si_det["actual_qty"], errors="coerce"
        ).fillna(0)

        item_grouped = (
            si_det.groupby("item_name")
            .agg({"target_qty": "sum", "actual_qty": "sum"})
            .reset_index()
        )

        item_grouped["gap"] = item_grouped["target_qty"] - item_grouped["actual_qty"]
        item_grouped["ach"] = item_grouped.apply(
            lambda r: (r["actual_qty"] / r["target_qty"] * 100)
            if r["target_qty"] > 0
            else 0,
            axis=1,
        )

        item_grouped["target_per_hari"] = item_grouped["gap"].apply(
            lambda g: int(np.ceil(g / remaining_days)) if g > 0 else 0
        )

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
            low_item = item_grouped.sort_values(
                by="actual_qty", ascending=True
            ).iloc[0]

            if sort_option == "Penjualan Terbanyak (Terlaris)":
                item_grouped = item_grouped.sort_values(
                    by="actual_qty", ascending=False
                )
            elif sort_option == "Penjualan Tersedikit":
                item_grouped = item_grouped.sort_values(
                    by="actual_qty", ascending=True
                )
            elif sort_option == "Achievement Tertinggi (% Ach)":
                item_grouped = item_grouped.sort_values(
                    by="ach", ascending=False
                )
            elif sort_option == "Target/Hari Terbesar":
                item_grouped = item_grouped.sort_values(
                    by="target_per_hari", ascending=False
                )
            elif sort_option == "Nama Produk (A - Z)":
                item_grouped = item_grouped.sort_values(
                    by="item_name", ascending=True
                )

            st.markdown("<br>", unsafe_allow_html=True)
            r_col1, r_col2, r_col3 = st.columns(3)
            with r_col1:
                st.markdown(
                    f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.25);">
                    <div style="color: #f59e0b; font-size: 11px; font-weight: bold;">🔥 ITEM TERLARIS</div>
                    <div style="color: #ffffff; font-size: 15px; font-weight: 800; margin: 3px 0;">{top_item['item_name']}</div>
                    <div style="color: #00ff88; font-size: 18px; font-weight: 800;">{top_item['actual_qty']:,.0f} Pcs</div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with r_col2:
                st.markdown(
                    f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.25);">
                    <div style="color: #ef4444; font-size: 11px; font-weight: bold;">📉 ITEM TERENDAH</div>
                    <div style="color: #ffffff; font-size: 15px; font-weight: 800; margin: 3px 0;">{low_item['item_name']}</div>
                    <div style="color: #00ff88; font-size: 18px; font-weight: 800;">{low_item['actual_qty']:,.0f} Pcs</div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with r_col3:
                st.markdown(
                    f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.25);">
                    <div style="color: #38bdf8; font-size: 11px; font-weight: bold;">📦 TOTAL VARIASI PRODUK</div>
                    <div style="color: #ffffff; font-size: 15px; font-weight: 800; margin: 3px 0;">{len(item_grouped)} Jenis Item</div>
                    <div style="color: #00ff88; font-size: 18px; font-weight: 800;">{item_grouped['actual_qty'].sum():,.0f} Pcs Actual</div>
                </div>""",
                    unsafe_allow_html=True,
                )

            st.markdown("<br>", unsafe_allow_html=True)

            detail_rows_html = ""
            for _, row in item_grouped.iterrows():
                gap_val = row["gap"]
                gap_color = "#00ff88" if gap_val <= 0 else "#ef4444"
                gap_display = (
                    f"+{abs(gap_val):,.0f}" if gap_val <= 0 else f"-{gap_val:,.0f}"
                )

                t_daily_color = (
                    "#f59e0b" if row["target_per_hari"] > 0 else "#00ff88"
                )

                detail_rows_html += f"""
                <tr style="border-bottom: 1px solid #1e293b;">
                    <td style="padding: 10px 12px; color: #ffffff; font-weight: bold; font-size: 13px;">{row['item_name']}</td>
                    <td style="padding: 10px 12px; color: #94a3b8; font-size: 13px;">{row['target_qty']:,.0f} Pcs</td>
                    <td style="padding: 10px 12px; color: #00ff88; font-weight: bold; font-size: 13px;">{row['actual_qty']:,.0f} Pcs</td>
                    <td style="padding: 10px 12px; color: #00f0ff; font-weight: bold; font-size: 13px;">{row['ach']:.1f}%</td>
                    <td style="padding: 10px 12px; color: {gap_color}; font-weight: bold; font-size: 13px;">{gap_display} Pcs</td>
                    <td style="padding: 10px 12px; color: {t_daily_color}; font-weight: bold; font-size: 13px;">⚡ {row['target_per_hari']:,.0f} Pcs/Hari</td>
                </tr>
                """

            st.markdown(
                f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; max-height: 500px; overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                        <thead>
                            <tr style="border-bottom: 2px solid #334155;">
                                <th style="padding: 10px 12px; color: #38bdf8; font-size: 11px;">NAMA PRODUK</th>
                                <th style="padding: 10px 12px; color: #38bdf8; font-size: 11px;">TARGET TOKO</th>
                                <th style="padding: 10px 12px; color: #38bdf8; font-size: 11px;">ACTUAL SALES</th>
                                <th style="padding: 10px 12px; color: #38bdf8; font-size: 11px;">% ACH</th>
                                <th style="padding: 10px 12px; color: #38bdf8; font-size: 11px;">SISA GAP</th>
                                <th style="padding: 10px 12px; color: #f59e0b; font-size: 11px;">TARGET / HARI (DYNAMIC)</th>
                            </tr>
                        </thead>
                        <tbody>{detail_rows_html}
                </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info("💡 Tidak ada item/produk yang sesuai dengan filter pencarian.")

# =========================================================
# --- TAB COMBINED: PERFORMA PERSONIL, PERNIK & DYNAMIC TARGET ---
# =========================================================
elif selected_tab in ["02 Raport Personil Toko"]:
    st.title("👥 Raport Personil Toko")

    # Custom CSS Style
    st.markdown(
        """
    <style>
    .neon-card {
        background: linear-gradient(135deg, #080c14 0%, #0f172a 100%);
        border: 1.5px solid #00f0ff;
        box-shadow: 0 0 10px rgba(0, 240, 255, 0.15);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .neon-title { color: #94a3b8; font-size: 11px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }
    .neon-value { color: #00ff88; font-size: 24px; font-weight: 800; text-shadow: 0 0 8px rgba(0,255,136,0.3); }
    .podium-1 {
        background: linear-gradient(180deg, #1e1b4b 0%, #080c14 100%);
        border: 2px solid #f59e0b;
        box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
        border-radius: 12px; padding: 14px; text-align: center;
    }
    .podium-23 {
        background: #080c14;
        border: 1.5px solid #00f0ff;
        border-radius: 12px; padding: 12px; text-align: center;
    }
    .status-growth { color: #00ff88; font-weight: bold; }
    .status-disgrowth { color: #ef4444; font-weight: bold; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Sub-menu Navigasi 4 Sub-Tab
    sub_view = st.radio(
        "Pilih Modul Analisis:",
        [
            "🏆 Ranking & Summary Tim",
            "📅 Evaluasi Harian & Tren",
            "🎯 Detail Pernik Per-Personil",
            "⏳ Dynamic Target (Sisa Hari)",
        ],
        horizontal=True,
        key="personnel_sub_view_4tab",
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # Load Data
    sp_df = st.session_state.sales_person_df.copy()
    si_df = st.session_state.sales_item_df.copy()
    p_df = st.session_state.get("periods_df", pd.DataFrame()).copy()

    # Clean Person Name
    for df_temp in [sp_df, st.session_state.get("person_df", pd.DataFrame())]:
        if not df_temp.empty and "person_name" in df_temp.columns:
            df_temp["person_name"] = (
                df_temp["person_name"]
                .astype(str)
                .str.replace("\xa0", " ", regex=False)
                .str.strip()
                .str.upper()
            )
            df_temp["person_name"] = df_temp["person_name"].str.replace(
                r"\s+", " ", regex=True
            )

    # Filter Periode
    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
        si_df = si_df[si_df["period_id"] == selected_period_id]
        if not p_df.empty and "period_id" in p_df.columns:
            p_df = p_df[p_df["period_id"] == selected_period_id]

    sp_df["actual_qty"] = pd.to_numeric(
        sp_df["actual_qty"], errors="coerce"
    ).fillna(0)

    # Normalisasi Kolom Tanggal jika ada
    date_col = next(
        (
            c
            for c in ["date", "transaction_date", "tanggal"]
            if c in sp_df.columns
        ),
        None,
    )
    if date_col:
        sp_df[date_col] = pd.to_datetime(sp_df[date_col], errors="coerce")

    # =========================================================
    # SUB-TAB 1: RANKING & SUMMARY TIM (IKUT PERIODE AKTIF)
    # =========================================================
    if sub_view == "🏆 Ranking & Summary Tim":
        if "date_col" not in locals() or not date_col:
            date_col = next(
                (
                    c
                    for c in [
                        "updated_at",
                        "created_at",
                        "tanggal",
                        "tgl",
                        "date",
                        "trans_date",
                    ]
                    if c in sp_df.columns
                ),
                None,
            )

        if date_col and date_col in sp_df.columns:
            sp_df[date_col] = pd.to_datetime(sp_df[date_col], errors="coerce")

        start_date_period = None
        end_date_period = None
        if not p_df.empty and selected_period_id:
            p_curr = p_df[p_df["period_id"] == selected_period_id]
            if not p_curr.empty:
                s_col = next(
                    (
                        c
                        for c in [
                            "start_date",
                            "tgl_mulai",
                            "start",
                            "periode_awal",
                        ]
                        if c in p_curr.columns
                    ),
                    None,
                )
                e_col = next(
                    (
                        c
                        for c in [
                            "end_date",
                            "tgl_selesai",
                            "end",
                            "periode_akhir",
                        ]
                        if c in p_curr.columns
                    ),
                    None,
                )
                if s_col and e_col:
                    start_date_period = pd.to_datetime(
                        p_curr[s_col].values[0]
                    ).date()
                    end_date_period = pd.to_datetime(
                        p_curr[e_col].values[0]
                    ).date()

        if (
            (not start_date_period or not end_date_period)
            and date_col
            and not sp_df.empty
        ):
            valid_dates = sp_df[date_col].dropna()
            if not valid_dates.empty:
                start_date_period = valid_dates.min().date()
                end_date_period = valid_dates.max().date()

        sp_df_filtered = sp_df.copy()
        if start_date_period and end_date_period and date_col:
            col_mode, col_cal = st.columns([1, 1.5])
            with col_mode:
                filter_mode = st.radio(
                    "📅 Tampilan Ranking:",
                    ["Full Periode Ini", "Filter Tanggal Spesifik"],
                    horizontal=True,
                )
            if filter_mode == "Filter Tanggal Spesifik":
                with col_cal:
                    selected_dates = st.date_input(
                        "📆 Pilih Tanggal Dalam Periode:",
                        value=(start_date_period, end_date_period),
                        min_value=start_date_period,
                        max_value=end_date_period,
                        help="Pilih 1 tanggal atau rentang tanggal dalam periode aktif ini",
                    )
                if isinstance(selected_dates, (tuple, list)):
                    if len(selected_dates) == 2:
                        s_d, e_d = selected_dates
                        sp_df_filtered = sp_df[
                            (sp_df[date_col].dt.date >= s_d)
                            & (sp_df[date_col].dt.date <= e_d)
                        ]
                    elif len(selected_dates) == 1:
                        sp_df_filtered = sp_df[
                            sp_df[date_col].dt.date == selected_dates[0]
                        ]
                else:
                    sp_df_filtered = sp_df[
                        sp_df[date_col].dt.date == selected_dates
                    ]
            else:
                sp_df_filtered = sp_df[
                    (sp_df[date_col].dt.date >= start_date_period)
                    & (sp_df[date_col].dt.date <= end_date_period)
                ]

        st.markdown("<br>", unsafe_allow_html=True)

        if not sp_df_filtered.empty:
            summary_person = (
                sp_df_filtered.groupby("person_name")["actual_qty"]
                .sum()
                .reset_index()
                .sort_values(by="actual_qty", ascending=False)
                .reset_index(drop=True)
            )
            tot_actual_personil = summary_person["actual_qty"].sum()
            avg_sales_personil = (
                summary_person["actual_qty"].mean()
                if len(summary_person) > 0
                else 0
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
                    f'<div class="neon-card"><div class="neon-title">TOTAL ACTUAL PERSONIL</div><div class="neon-value">{tot_actual_personil:,.0f} <span style="font-size:14px; color:#38bdf8;">Pcs</span></div></div>',
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    f'<div class="neon-card"><div class="neon-title">RATA-RATA / STAF</div><div class="neon-value">{avg_sales_personil:,.0f} <span style="font-size:14px; color:#38bdf8;">Pcs</span></div></div>',
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown(
                    f'<div class="neon-card" style="border-color:#f59e0b;"><div class="neon-title" style="color:#f59e0b;">👑 TOP PERFORMER</div><div class="neon-value" style="color:#ffffff; font-size:18px;">{top_performer_name}</div></div>',
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
                    f"""<div style="display: flex; gap: 14px; justify-content: center; align-items: flex-end; margin-bottom: 25px;">
<div style="flex: 1;" class="podium-23"><span style="font-size: 24px;">🥈</span><div style="color: #94a3b8; font-size: 11px; font-weight: bold;">JUARA 2</div><div style="color: #ffffff; font-size: 13px; font-weight: bold; margin: 4px 0;">{p2_name}</div><div style="color: #00ff88; font-size: 16px; font-weight: 800;">{p2_qty:,.0f} Pcs</div></div>
<div style="flex: 1.1;" class="podium-1"><span style="font-size: 30px;">🥇</span><div style="color: #f59e0b; font-size: 11px; font-weight: bold;">JUARA 1</div><div style="color: #ffffff; font-size: 15px; font-weight: bold; margin: 4px 0;">{p1_name}</div><div style="color: #00ff88; font-size: 20px; font-weight: 800;">{p1_qty:,.0f} Pcs</div></div>
<div style="flex: 1;" class="podium-23"><span style="font-size: 24px;">🥉</span><div style="color: #b45309; font-size: 11px; font-weight: bold;">JUARA 3</div><div style="color: #ffffff; font-size: 13px; font-weight: bold; margin: 4px 0;">{p3_name}</div><div style="color: #00ff88; font-size: 16px; font-weight: 800;">{p3_qty:,.0f} Pcs</div></div>
</div>""",
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            col_table, col_chart = st.columns([1.1, 1])
            COMPONENT_HEIGHT = 330

            with col_table:
                st.markdown(
                    "<p style='color:#38bdf8; font-size:15px; font-weight:bold;'>📋 Tabel Ranking Akumulasi</p>",
                    unsafe_allow_html=True,
                )
                table_rows_html = ""
                for rank, (_, row) in enumerate(summary_person.iterrows()):
                    badge = (
                        "🥇"
                        if rank == 0
                        else (
                            "🥈"
                            if rank == 1
                            else ("🥉" if rank == 2 else "👤")
                        )
                    )
                    table_rows_html += f'<tr style="border-bottom: 1px solid #1e293b;"><td style="padding: 10px; color: #ffffff; font-weight: bold;">{badge} {row["person_name"]}</td><td style="padding: 10px; color: #00ff88; font-weight: bold; text-align:right;">{row["actual_qty"]:,.0f}</td><td style="padding: 10px; color: #00f0ff; font-weight: bold; text-align:right;">{row["pct_contrib"]:.1f}%</td></tr>'

                table_full_html = f'<div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; height: {COMPONENT_HEIGHT}px; overflow-y: auto;"><table style="width: 100%; border-collapse: collapse; font-family: sans-serif;"><thead><tr style="border-bottom: 2px solid #334155; text-align: left;"><th style="padding: 8px; color: #94a3b8; font-size: 11px;">PERSONIL</th><th style="padding: 8px; color: #94a3b8; font-size: 11px; text-align:right;">TOTAL SALES</th><th style="padding: 8px; color: #94a3b8; font-size: 11px; text-align:right;">KONTRIBUSI</th></tr></thead><tbody>{table_rows_html}</tbody></table></div>'
                st.markdown(table_full_html, unsafe_allow_html=True)

            with col_chart:
                st.markdown(
                    "<p style='color:#38bdf8; font-size:15px; font-weight:bold;'>📊 Grafik Perbandingan Akumulasi</p>",
                    unsafe_allow_html=True,
                )
                fig_person = go.Figure()
                fig_person.add_trace(
                    go.Bar(
                        x=summary_person["person_name"],
                        y=summary_person["actual_qty"],
                        marker=dict(
                            color=summary_person["actual_qty"],
                            colorscale="Viridis",
                        ),
                        text=summary_person["actual_qty"].apply(
                            lambda x: f"{x:,.0f}"
                        ),
                        textposition="outside",
                    )
                )
                fig_person.update_layout(
                    height=COMPONENT_HEIGHT,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#ffffff"),
                    margin=dict(l=10, r=10, t=25, b=10),
                    yaxis=dict(showgrid=False),
                    xaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig_person, use_container_width=True)
        else:
            st.info(
                "💡 Belum ada data penjualan personil untuk rentang tanggal/periode yang dipilih."
            )

    # =========================================================
    # SUB-TAB 2: EVALUASI HARIAN & TREN PENJUALAN
    # =========================================================
    elif sub_view == "📅 Evaluasi Harian & Tren":
        if "date_col" not in locals() or not date_col:
            date_col = next(
                (
                    c
                    for c in [
                        "updated_at",
                        "created_at",
                        "tanggal",
                        "tgl",
                        "date",
                        "trans_date",
                    ]
                    if c in sp_df.columns
                ),
                None,
            )

        if date_col and date_col in sp_df.columns:
            sp_df[date_col] = pd.to_datetime(sp_df[date_col], errors="coerce")

        if (
            date_col
            and not sp_df.empty
            and not sp_df[date_col].isna().all()
        ):
            available_dates = sorted(
                sp_df[date_col].dt.date.dropna().unique(), reverse=True
            )
            if available_dates:
                c_date, _ = st.columns([1.5, 1])
                with c_date:
                    selected_date = st.selectbox(
                        "📆 PILIH TANGGAL EVALUASI", available_dates
                    )

                sp_daily = sp_df[
                    sp_df[date_col].dt.date == selected_date
                ]
                st.markdown(
                    f"### 📊 Evaluasi Penjualan Tanggal: **{selected_date.strftime('%d %B %Y')}**"
                )

                tot_daily_qty = (
                    sp_daily["actual_qty"].sum()
                    if not sp_daily.empty
                    else 0
                )
                active_person = (
                    sp_daily["person_name"].nunique()
                    if not sp_daily.empty
                    else 0
                )
                total_items = (
                    sp_daily["item_id"].nunique()
                    if not sp_daily.empty
                    else 0
                )

                m_h1, m_h2, m_h3 = st.columns(3)
                with m_h1:
                    st.metric(
                        "📦 Total Penjualan Hari Ini",
                        f"{tot_daily_qty:,.0f} Pcs",
                    )
                with m_h2:
                    st.metric(
                        "👥 Personil Aktif Transaksi", f"{active_person} Orang"
                    )
                with m_h3:
                    st.metric(
                        "🏷️ Varian Item Terjual", f"{total_items} Item"
                    )

                st.markdown("---")
                col_t_daily, col_c_daily = st.columns([1.1, 1])
                COMPONENT_HEIGHT = 350

                with col_t_daily:
                    st.markdown(
                        "<p style='color:#38bdf8; font-size:15px; font-weight:bold;'>📋 Rincian Sales Per-Personil (Hari Ini)</p>",
                        unsafe_allow_html=True,
                    )
                    daily_person = (
                        (
                            sp_daily.groupby("person_name")["actual_qty"]
                            .sum()
                            .reset_index()
                            .sort_values(by="actual_qty", ascending=False)
                            .reset_index(drop=True)
                        )
                        if not sp_daily.empty
                        else pd.DataFrame(columns=["person_name", "actual_qty"])
                    )

                    daily_rows = ""
                    for rank, (_, r) in enumerate(daily_person.iterrows()):
                        badge = (
                            "🥇"
                            if rank == 0
                            else (
                                "🥈"
                                if rank == 1
                                else ("🥉" if rank == 2 else "👤")
                            )
                        )
                        daily_rows += f'<tr style="border-bottom: 1px solid #1e293b;"><td style="padding: 10px; color: #ffffff; font-weight: bold;">{badge} {r["person_name"]}</td><td style="padding: 10px; color: #00ff88; font-weight: bold; text-align:right;">{r["actual_qty"]:,.0f} Pcs</td></tr>'

                    daily_full_html = f'<div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; height: {COMPONENT_HEIGHT}px; overflow-y: auto;"><table style="width: 100%; border-collapse: collapse; font-family: sans-serif;"><thead><tr style="border-bottom: 2px solid #334155; text-align: left;"><th style="padding: 8px; color: #94a3b8; font-size: 11px;">PERSONIL</th><th style="padding: 8px; color: #94a3b8; font-size: 11px; text-align:right;">ACTUAL SALES</th></tr></thead><tbody>{daily_rows if daily_rows else "<tr><td colspan=\'2\' style=\'padding:10px; color:#94a3b8; text-align:center;\'>Tidak ada transaksi di tanggal ini</td></tr>"}</tbody></table></div>'
                    st.markdown(daily_full_html, unsafe_allow_html=True)

                with col_c_daily:
                    st.markdown(
                        "<p style='color:#38bdf8; font-size:15px; font-weight:bold;'>📈 Tren Penjualan Harian (Periode Ini)</p>",
                        unsafe_allow_html=True,
                    )
                    trend_df = (
                        sp_df.groupby(sp_df[date_col].dt.date)["actual_qty"]
                        .sum()
                        .reset_index()
                    )
                    trend_df.columns = ["tanggal", "total_qty"]
                    trend_df = trend_df.sort_values(by="tanggal")

                    fig_trend = go.Figure()
                    fig_trend.add_trace(
                        go.Scatter(
                            x=trend_df["tanggal"],
                            y=trend_df["total_qty"],
                            mode="lines+markers+text",
                            line=dict(color="#00f0ff", width=3),
                            marker=dict(size=8, color="#00ff88"),
                            text=trend_df["total_qty"].apply(
                                lambda x: f"{x:,.0f}"
                            ),
                            textposition="top center",
                        )
                    )
                    fig_trend.update_layout(
                        height=COMPONENT_HEIGHT,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#ffffff"),
                        margin=dict(l=10, r=10, t=30, b=10),
                        yaxis=dict(showgrid=False),
                        xaxis=dict(showgrid=False),
                    )
                    st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning(
                "⚠️ Kolom tanggal transaksi tidak ditemukan atau bernilai kosong pada dataset SALES_PERSONIL."
            )

    # =========================================================
    # SUB-TAB 3: DETAIL PERNIK PER-PERSONIL
    # =========================================================
    elif sub_view == "🎯 Detail Pernik Per-Personil":
        person_list = (
            sp_df["person_name"].dropna().unique().tolist()
            if not sp_df.empty
            else []
        )
        c_p1, _ = st.columns([1.5, 1])
        with c_p1:
            selected_person = st.selectbox(
                "👤 PILIH PERSONIL TOKO",
                person_list if person_list else ["Belum Ada Data"],
                key="tab4_person_select_comb4",
            )

        sp_person_df = sp_df[sp_df["person_name"] == selected_person]
        target_col = (
            "target_kasir"
            if "target_kasir" in si_df.columns
            else "target_qty"
        )
        si_df[target_col] = pd.to_numeric(
            si_df[target_col], errors="coerce"
        ).fillna(0)

        sp_grouped = (
            sp_person_df.groupby(["item_id", "item_name"])["actual_qty"]
            .sum()
            .reset_index()
            if not sp_person_df.empty
            else pd.DataFrame(
                columns=["item_id", "item_name", "actual_qty"]
            )
        )
        si_grouped = (
            si_df.groupby(["item_id", "item_name"])[target_col]
            .sum()
            .reset_index()
            if not si_df.empty
            else pd.DataFrame(columns=["item_id", "item_name", target_col])
        )

        si_grouped["item_id"] = si_grouped["item_id"].astype(str)
        sp_grouped["item_id"] = sp_grouped["item_id"].astype(str)

        merged_item_df = pd.merge(
            si_grouped,
            sp_grouped[["item_id", "actual_qty"]],
            on="item_id",
            how="left",
        )
        merged_item_df["actual_qty"] = merged_item_df["actual_qty"].fillna(0)
        merged_item_df.rename(
            columns={target_col: "target_val"}, inplace=True
        )
        merged_item_df["gap"] = (
            merged_item_df["target_val"] - merged_item_df["actual_qty"]
        )
        merged_item_df["ach"] = merged_item_df.apply(
            lambda r: (
                (r["actual_qty"] / r["target_val"] * 100)
                if r["target_val"] > 0
                else 0
            ),
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
            st.markdown(
                "<p style='color:#38bdf8; font-size:15px; font-weight:bold;'>📋 Rincian Target Item Pernik</p>",
                unsafe_allow_html=True,
            )
            table_rows_html = ""
            for _, row in merged_item_df.iterrows():
                gap_color = "#00ff88" if row["gap"] <= 0 else "#ef4444"
                ach_color = "#00ff88" if row["ach"] >= 100 else "#ffb703"
                table_rows_html += f'<tr style="border-bottom: 1px solid #1e293b;"><td style="padding: 10px; color: #ffffff; font-weight: bold;">{row["item_name"]}</td><td style="padding: 10px; color: #94a3b8;">{row["target_val"]:,.0f}</td><td style="padding: 10px; color: #00ff88; font-weight: bold;">{row["actual_qty"]:,.0f}</td><td style="padding: 10px; color: {gap_color};">{row["gap"]:,.0f}</td><td style="padding: 10px; color: {ach_color}; font-weight: bold;">{row["ach"]:.1f}%</td></tr>'

            table_full_html = f'<div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; max-height: 380px; overflow-y: auto;"><table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;"><thead><tr style="border-bottom: 2px solid #334155;"><th style="padding: 8px; color: #38bdf8; font-size: 11px;">NAMA ITEM</th><th style="padding: 8px; color: #38bdf8; font-size: 11px;">TARGET KASIR</th><th style="padding: 8px; color: #38bdf8; font-size: 11px;">ACTUAL</th><th style="padding: 8px; color: #38bdf8; font-size: 11px;">GAP</th><th style="padding: 8px; color: #38bdf8; font-size: 11px;">% ACH</th></tr></thead><tbody>{table_rows_html}</tbody></table></div>'
            st.markdown(table_full_html, unsafe_allow_html=True)

        with col_t4_right:
            st.markdown(
                "<p style='color:#38bdf8; font-size:15px; font-weight:bold;'>📊 Visual Breakdown Item</p>",
                unsafe_allow_html=True,
            )
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
                    marker_color="#475569",
                )
            )
            fig_p4.update_layout(
                barmode="group",
                height=380,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#ffffff"),
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02
                ),
            )
            st.plotly_chart(fig_p4, use_container_width=True)

    # =========================================================
    # SUB-TAB 4: DYNAMIC TARGET (TIMEFACTOR & SISA HARI KERJA PERIODE)
    # =========================================================
    elif sub_view == "⏳ Dynamic Target (Sisa Hari)":
        st.subheader("⏳ Kalkulator Timefactor & Target Harian Terupdate")

        start_date_period = None
        end_date_period = None

        if not p_df.empty and selected_period_id:
            p_curr = p_df[p_df["period_id"] == selected_period_id]
            if not p_curr.empty:
                s_col = next(
                    (
                        c
                        for c in [
                            "start_date",
                            "tgl_mulai",
                            "start",
                            "periode_awal",
                        ]
                        if c in p_curr.columns
                    ),
                    None,
                )
                e_col = next(
                    (
                        c
                        for c in [
                            "end_date",
                            "tgl_selesai",
                            "end",
                            "periode_akhir",
                        ]
                        if c in p_curr.columns
                    ),
                    None,
                )
                if s_col and e_col:
                    start_date_period = pd.to_datetime(
                        p_curr[s_col].values[0]
                    ).date()
                    end_date_period = pd.to_datetime(
                        p_curr[e_col].values[0]
                    ).date()

        if (
            (not start_date_period or not end_date_period)
            and date_col
            and not sp_df.empty
        ):
            valid_dates = sp_df[date_col].dropna()
            if not valid_dates.empty:
                start_date_period = valid_dates.min().date()
                end_date_period = valid_dates.max().date()

        today = datetime.now().date()
        if start_date_period and end_date_period:
            calc_total_days = max(
                (end_date_period - start_date_period).days + 1, 1
            )
            if today < start_date_period:
                calc_passed_days = 0
            elif today > end_date_period:
                calc_passed_days = calc_total_days
            else:
                calc_passed_days = (today - start_date_period).days + 1

            info_periode_str = f"📅 Periode Aktif: **{start_date_period.strftime('%d %b %Y')}** s/d **{end_date_period.strftime('%d %b %Y')}**"
        else:
            calc_total_days = 30
            calc_passed_days = min(today.day, 30)
            info_periode_str = (
                "ℹ️ Menggunakan default estimasi 30 hari kalender."
            )

        st.caption(info_periode_str)

        c_tf1, c_tf2, c_tf3 = st.columns(3)
        with c_tf1:
            total_days = st.number_input(
                "📅 Total Hari Kerja Periode",
                min_value=1,
                max_value=60,
                value=int(calc_total_days),
            )
        with c_tf2:
            passed_days = st.number_input(
                "⏱️ Hari Kerja Berjalan",
                min_value=0,
                max_value=total_days,
                value=min(int(calc_passed_days), total_days),
            )

        remaining_days = max(total_days - passed_days, 0)
        timefactor_pct = (
            (passed_days / total_days * 100) if total_days > 0 else 0
        )

        with c_tf3:
            st.markdown(
                f'<div class="neon-card" style="border-color:#38bdf8;"><div class="neon-title">TIMEFACTOR PERIODE</div><div class="neon-value" style="color:#00f0ff;">{timefactor_pct:.1f}%</div><div style="font-size:11px; color:#94a3b8;">Sisa Hari Kerja: <b style="color:#ffffff;">{remaining_days} Hari</b></div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        person_list_dyn = (
            sp_df["person_name"].dropna().unique().tolist()
            if not sp_df.empty
            else []
        )
        c_p_dyn, _ = st.columns([1.5, 1])
        with c_p_dyn:
            sel_person_dyn = st.selectbox(
                "👤 PILIH PERSONIL UNTUK TARGET HARIAN",
                person_list_dyn if person_list_dyn else ["Belum Ada Data"],
                key="select_person_dynamic",
            )

        sp_person_dyn = sp_df[sp_df["person_name"] == sel_person_dyn]
        target_col = (
            "target_kasir"
            if "target_kasir" in si_df.columns
            else "target_qty"
        )
        si_df[target_col] = pd.to_numeric(
            si_df[target_col], errors="coerce"
        ).fillna(0)

        sp_grouped_dyn = (
            sp_person_dyn.groupby(["item_id", "item_name"])["actual_qty"]
            .sum()
            .reset_index()
            if not sp_person_dyn.empty
            else pd.DataFrame(
                columns=["item_id", "item_name", "actual_qty"]
            )
        )
        si_grouped_dyn = (
            si_df.groupby(["item_id", "item_name"])[target_col]
            .sum()
            .reset_index()
            if not si_df.empty
            else pd.DataFrame(columns=["item_id", "item_name", target_col])
        )

        si_grouped_dyn["item_id"] = si_grouped_dyn["item_id"].astype(str)
        sp_grouped_dyn["item_id"] = sp_grouped_dyn["item_id"].astype(str)

        dyn_df = pd.merge(
            si_grouped_dyn,
            sp_grouped_dyn[["item_id", "actual_qty"]],
            on="item_id",
            how="left",
        ).fillna(0)

        dyn_df.rename(columns={target_col: "target_val"}, inplace=True)
        dyn_df["sisa_gap"] = dyn_df["target_val"] - dyn_df["actual_qty"]
        dyn_df["sisa_gap"] = dyn_df["sisa_gap"].apply(lambda x: max(x, 0))

        dyn_df["req_daily_qty"] = dyn_df["sisa_gap"].apply(
            lambda x: (x / remaining_days) if remaining_days > 0 else x
        )

        tot_target_dyn = dyn_df["target_val"].sum()
        tot_actual_dyn = dyn_df["actual_qty"].sum()
        tot_gap_dyn = max(tot_target_dyn - tot_actual_dyn, 0)
        tot_req_daily = (
            (tot_gap_dyn / remaining_days)
            if remaining_days > 0
            else tot_gap_dyn
        )

        st.markdown(
            f"### 💡 Target Harian Terupdate untuk **{sel_person_dyn}**"
        )

        m_d1, m_d2, m_d3, m_d4 = st.columns(4)
        with m_d1:
            st.metric("🎯 Total Target Periode", f"{tot_target_dyn:,.0f} Pcs")
        with m_d2:
            st.metric("📦 Actual Penjualan", f"{tot_actual_dyn:,.0f} Pcs")
        with m_d3:
            st.metric("📉 Sisa Gap Target", f"{tot_gap_dyn:,.0f} Pcs")
        with m_d4:
            st.metric(
                "⚡ Wajib Target / Hari",
                f"{tot_req_daily:.1f} Pcs/Hari",
                help="Beban target per hari agar target periode ini tercapai 100%",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        dyn_rows = ""
        for _, r in dyn_df.iterrows():
            status_txt = (
                "✅ TERCAPAI"
                if r["sisa_gap"] <= 0
                else f"⚡ {r['req_daily_qty']:.1f} Pcs/Hari"
            )
            status_color = "#00ff88" if r["sisa_gap"] <= 0 else "#ffb703"
            dyn_rows += f'<tr style="border-bottom: 1px solid #1e293b;"><td style="padding: 10px; color: #ffffff; font-weight: bold;">{r["item_name"]}</td><td style="padding: 10px; color: #94a3b8; text-align:right;">{r["target_val"]:,.0f}</td><td style="padding: 10px; color: #00ff88; font-weight: bold; text-align:right;">{r["actual_qty"]:,.0f}</td><td style="padding: 10px; color: #ef4444; text-align:right;">{r["sisa_gap"]:,.0f}</td><td style="padding: 10px; color: {status_color}; font-weight: bold; text-align:right;">{status_txt}</td></tr>'

        dyn_full_html = f'<div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 12px; overflow-x: auto;"><table style="width: 100%; border-collapse: collapse; font-family: sans-serif;"><thead><tr style="border-bottom: 2px solid #334155; text-align: left;"><th style="padding: 10px; color: #38bdf8; font-size: 11px;">ITEM PERNIK</th><th style="padding: 10px; color: #38bdf8; font-size: 11px; text-align:right;">TARGET PERIODE</th><th style="padding: 10px; color: #38bdf8; font-size: 11px; text-align:right;">ACTUAL</th><th style="padding: 10px; color: #38bdf8; font-size: 11px; text-align:right;">SISA GAP</th><th style="padding: 10px; color: #38bdf8; font-size: 11px; text-align:right;">TARGET/HARI SISA HARI</th></tr></thead><tbody>{dyn_rows}</tbody></table></div>'
        st.markdown(dyn_full_html, unsafe_allow_html=True)


