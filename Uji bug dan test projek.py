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
# 6. HALAMAN LOGIN
# =========================================================
def show_login_page():
    LOGO_URL = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/kgs_group_belgium_logo.jpg"
    st.markdown("""
    <style>
    .login-card { background-color: #1e293b; padding: 35px 30px; border-radius: 16px; box-shadow: 0 10px 25px 5px rgba(0, 0, 0, 0.4); text-align: center; margin-bottom: 20px; }
    .login-logo { width: 100px; height: 100px; object-fit: contain; border-radius: 12px; background-color: #ffffff; padding: 8px; margin-bottom: 15px; display: block; margin-left: auto; margin-right: auto; }
    .login-subtitle { color: #38bdf8; font-size: 13px; margin-bottom: 0px; }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown(f"""
        <div class='login-card'>
            <img src='{LOGO_URL}' class='login-logo' alt='KGS Group Logo'>
            <p class='login-subtitle'>Sistem Monitoring PSM Toko</p>
        </div>
        """, unsafe_allow_html=True)
        
    with st.form("login_form", clear_on_submit=False):
        username_input = st.text_input("Username", placeholder="Masukkan username")
        password_input = st.text_input("Password", type="password", placeholder="Masukkan password")
        submit_btn = st.form_submit_button("Masuk ke Aplikasi", use_container_width=True)

    if submit_btn:
        # Membersihkan spasi pada input
        u_clean = username_input.strip()
        p_clean = password_input.strip()

    if not u_clean or not p_clean:
        st.warning("⚠️ Username dan Password wajib diisi!")
    elif check_login(u_clean, p_clean):
        # 1. TANDAI USER SUDAH LOGIN (PENTING!)
        st.session_state["logged_in"] = True
        
        # 2. BACA ROLE USER
        user_role = st.session_state.get("role", st.session_state.get("user_role", ""))
        st.session_state["is_admin"] = (str(user_role).strip().lower() == "admin")

        st.toast(f"🎉 Selamat Datang, {st.session_state.get('person_name', u_clean)}!")
        st.rerun()
    else:
        st.error("❌ Username atau Password salah!")

    if not st.session_state.logged_in:
        show_login_page()
        st.stop()

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
    "03 Raport Personil Toko",
    "05 Analisis Tren",
    "06 Input & Reset Data",
    "07 Master Data & Pengaturan"
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
elif selected_tab == "03 Raport Personil Toko":
    st.markdown("<h3 style='color: #00ff88;'>📊 Raport & Evaluasi Personil Toko</h3>", unsafe_allow_html=True)

    # 1. Ambil data dari Session State
    sales_df = st.session_state.get("sales_df", pd.DataFrame())
    sp_df = st.session_state.get("sales_person_df", pd.DataFrame())
    person_df = st.session_state.get("person_df", pd.DataFrame())
    items_df = st.session_state.get("items_df", pd.DataFrame())
    periods_df = st.session_state.get("periods_df", pd.DataFrame())

    if periods_df.empty:
        st.warning("⚠️ Data Master Periode belum tersedia. Silakan atur periode di Master Data.")
    else:
        # Pilih Periode
        periods_dict = dict(zip(periods_df["period_name"], periods_df["period_id"]))
        sel_period_name = st.selectbox("Pilih Periode Evaluasi:", list(periods_dict.keys()), key="rap_period_sel")
        target_p_id = str(periods_dict[sel_period_name])

        # Sub-menu Analisis (Lengkap 4 Mode)
        rap_mode = st.radio(
            "Pilih Mode Analisis:",
            [
                "🏆 Ranking & Summary Tim", 
                "📅 Evaluasi Harian & Tren", 
                "🎯 Detail Pernik Per-Personil", 
                "⌛ Dynamic Target & Run Rate"
            ],
            horizontal=True,
            key="rap_mode_radio"
        )

        # Filter Data Target Personil untuk Periode Ini
        sp_period = sp_df[sp_df["period_id"].astype(str) == target_p_id].copy() if not sp_df.empty else pd.DataFrame()
        sales_period = sales_df[sales_df["period_id"].astype(str) == target_p_id].copy() if not sales_df.empty else pd.DataFrame()

        # Filter Personil Kasir/Staff
        kasir_list = person_df[
            person_df["role"].astype(str).str.lower().isin(["kasir toko", "staff toko", "kasir", "staff"])
        ] if not person_df.empty else pd.DataFrame()

        if kasir_list.empty:
            st.warning("⚠️ Belum ada data Personil Kasir/Staff yang terdaftar di Master Personil.")
        else:
            # -------------------------------------------------------------
            # MODE 1: RANKING & SUMMARY TIM
            # -------------------------------------------------------------
            if rap_mode == "🏆 Ranking & Summary Tim":
                st.markdown(f"#### 📊 Ringkasan Pencapaian Kasir — Periode: **{sel_period_name}**")

                summary_data = []
                for _, k_row in kasir_list.iterrows():
                    k_id = str(k_row["person_id"])
                    k_name = str(k_row["person_name"])

                    k_target = 0
                    if not sp_period.empty:
                        k_target_df = sp_period[sp_period["person_id"].astype(str) == k_id]
                        if not k_target_df.empty:
                            k_target = pd.to_numeric(k_target_df["target_qty"], errors="coerce").fillna(0).sum()

                    k_actual = 0
                    if not sales_period.empty and "person_id" in sales_period.columns:
                        k_sales_df = sales_period[sales_period["person_id"].astype(str) == k_id]
                        if not k_sales_df.empty:
                            k_actual = pd.to_numeric(k_sales_df["qty"], errors="coerce").fillna(0).sum()
                    elif not sp_period.empty:
                        k_target_df = sp_period[sp_period["person_id"].astype(str) == k_id]
                        if not k_target_df.empty:
                            k_actual = pd.to_numeric(k_target_df["actual_qty"], errors="coerce").fillna(0).sum()

                    achieve_pct = (k_actual / k_target * 100) if k_target > 0 else 0.0

                    summary_data.append({
                        "ID Personil": k_id,
                        "Nama Kasir": k_name,
                        "Target (Pcs)": int(k_target),
                        "Aktual (Pcs)": int(k_actual),
                        "Pencapaian (%)": round(achieve_pct, 1),
                        "Status": "✅ Tuntas" if k_actual >= k_target and k_target > 0 else "⏳ Proses"
                    })

                res_df = pd.DataFrame(summary_data).sort_values(by="Pencapaian (%)", ascending=False)
                st.dataframe(
                    res_df,
                    use_container_width=True,
                    column_config={
                        "Pencapaian (%)": st.column_config.ProgressColumn(
                            "Pencapaian (%)", format="%.1f%%", min_value=0, max_value=100
                        )
                    }
                )

            # -------------------------------------------------------------
            # MODE 2: EVALUASI HARIAN & TREN
            # -------------------------------------------------------------
            elif rap_mode == "📅 Evaluasi Harian & Tren":
                st.markdown(f"#### 📅 Tren Penjualan Harian — Periode: **{sel_period_name}**")
                if not sales_period.empty and "date" in sales_period.columns:
                    trend_df = sales_period.groupby(["date", "person_name"])["qty"].sum().reset_index()
                    st.line_chart(trend_df.pivot(index="date", columns="person_name", values="qty").fillna(0))
                else:
                    st.info("ℹ️ Belum ada riwayat transaksi harian per-personil pada periode ini.")

            # -------------------------------------------------------------
            # MODE 3: DETAIL PERNIK PER-PERSONIL
            # -------------------------------------------------------------
            elif rap_mode == "🎯 Detail Pernik Per-Personil":
                sel_kasir = st.selectbox("Pilih Personil / Kasir:", kasir_list["person_name"].tolist(), key="rap_kasir_sel")
                sel_kasir_row = kasir_list[kasir_list["person_name"] == sel_kasir].iloc[0]
                sel_k_id = str(sel_kasir_row["person_id"])

                st.markdown(f"#### 📦 Detail Target & Pencapaian Item: **{sel_kasir}**")
                kasir_items_sp = sp_period[sp_period["person_id"].astype(str) == sel_k_id] if not sp_period.empty else pd.DataFrame()

                if kasir_items_sp.empty:
                    st.info(f"ℹ️ Belum ada target item yang di-set untuk **{sel_kasir}** pada periode ini.")
                else:
                    item_details = []
                    for _, sp_item in kasir_items_sp.iterrows():
                        itm_id = str(sp_item["item_id"])
                        itm_name = str(sp_item["item_name"])
                        t_qty = int(pd.to_numeric(sp_item.get("target_qty", 0), errors="coerce"))

                        a_qty = 0
                        if not sales_period.empty and "person_id" in sales_period.columns:
                            m_sales = sales_period[
                                (sales_period["person_id"].astype(str) == sel_k_id) &
                                (sales_period["item_id"].astype(str) == itm_id)
                            ]
                            if not m_sales.empty:
                                a_qty = int(pd.to_numeric(m_sales["qty"], errors="coerce").fillna(0).sum())
                        else:
                            a_qty = int(pd.to_numeric(sp_item.get("actual_qty", 0), errors="coerce"))

                        pct = (a_qty / t_qty * 100) if t_qty > 0 else 0.0

                        item_details.append({
                            "ID Item": itm_id,
                            "Nama Item": itm_name,
                            "Target (Pcs)": t_qty,
                            "Aktual (Pcs)": a_qty,
                            "Pencapaian (%)": round(pct, 1)
                        })

                    st.dataframe(pd.DataFrame(item_details), use_container_width=True)

            # -------------------------------------------------------------
            # MODE 4: DYNAMIC TARGET & RUN RATE
            # -------------------------------------------------------------
            elif rap_mode == "⌛ Dynamic Target & Run Rate":
                st.markdown(f"#### ⌛ Kalkulator Dynamic Target & Run Rate Harian — Periode: **{sel_period_name}**")
                st.caption("Menghitung perkiraan sisa target harian yang harus dicapai kasir berdasarkan sisa hari promosi.")

                c1, c2 = st.columns(2)
                with c1:
                    days_passed = st.number_input("Jumlah Hari Yang Sudah Berjalan:", min_value=1, value=5, step=1)
                with c2:
                    days_remaining = st.number_input("Sisa Hari Periode Promosi:", min_value=1, value=3, step=1)

                dyn_data = []
                for _, k_row in kasir_list.iterrows():
                    k_id = str(k_row["person_id"])
                    k_name = str(k_row["person_name"])

                    k_target = 0
                    if not sp_period.empty:
                        k_target_df = sp_period[sp_period["person_id"].astype(str) == k_id]
                        if not k_target_df.empty:
                            k_target = pd.to_numeric(k_target_df["target_qty"], errors="coerce").fillna(0).sum()

                    k_actual = 0
                    if not sales_period.empty and "person_id" in sales_period.columns:
                        k_sales_df = sales_period[sales_period["person_id"].astype(str) == k_id]
                        if not k_sales_df.empty:
                            k_actual = pd.to_numeric(k_sales_df["qty"], errors="coerce").fillna(0).sum()
                    elif not sp_period.empty:
                        k_target_df = sp_period[sp_period["person_id"].astype(str) == k_id]
                        if not k_target_df.empty:
                            k_actual = pd.to_numeric(k_target_df["actual_qty"], errors="coerce").fillna(0).sum()

                    remaining_target = max(0, k_target - k_actual)
                    run_rate_daily = remaining_target / days_remaining if days_remaining > 0 else remaining_target
                    current_daily_avg = k_actual / days_passed if days_passed > 0 else 0

                    dyn_data.append({
                        "Nama Kasir": k_name,
                        "Total Target": int(k_target),
                        "Pencapaian Saat Ini": int(k_actual),
                        "Sisa Target": int(remaining_target),
                        "Rata2/Hari (Lalu)": round(current_daily_avg, 1),
                        "Wajib Target/Hari (Sisa)": round(run_rate_daily, 1),
                        "Proyeksi Status": "🔥 On Track" if current_daily_avg >= run_rate_daily else "⚠️ Need Push"
                    })

                st.dataframe(pd.DataFrame(dyn_data), use_container_width=True)




# --- TAB 05: ANALISIS TREN HARIAN ---
elif selected_tab == "05 Analisis Tren":
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

    st.markdown("### 🗓️ Navigasi Filter Rentang Tanggal")
    c_d1, c_d2 = st.columns(2)
    with c_d1:
        start_date = st.date_input("Tanggal Awal", value=default_start, key="t5_start_date")
    with c_d2:
        end_date = st.date_input("Tanggal Akhir", value=default_end, key="t5_end_date")

    if start_date > end_date:
        st.error("⚠️ Tanggal Awal tidak boleh lebih besar dari Tanggal Akhir!")
        st.stop()

    if "updated_at" in sub_sp.columns and not sub_sp.empty:
        sub_sp["updated_at_dt"] = pd.to_datetime(sub_sp["updated_at"]).dt.date
        filtered_sp = sub_sp[(sub_sp["updated_at_dt"] >= start_date) & (sub_sp["updated_at_dt"] <= end_date)].copy()
    else:
        filtered_sp = sub_sp.copy()

    sub_si["target_qty"] = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0)
    filtered_sp["actual_qty"] = pd.to_numeric(filtered_sp["actual_qty"], errors="coerce").fillna(0)

    tot_target = sub_si["target_qty"].sum()
    tot_actual = filtered_sp["actual_qty"].sum()

    total_range_days = max((end_date - start_date).days + 1, 1)
    today_date = waktu_wib.date()

    if today_date < start_date: passed_days = 0
    elif today_date > end_date: passed_days = total_range_days
    else: passed_days = max((today_date - start_date).days + 1, 1)

    # Perbaikan bug: remaining_days bernilai 0 jika hari sudah melewati end_date
    remaining_days = max(total_range_days - passed_days, 0)
    daily_target_ideal = max(0, int((tot_target - tot_actual) / remaining_days)) if remaining_days > 0 else 0
    avg_daily_sales = tot_actual / passed_days if passed_days > 0 else 0
    best_est = int(tot_actual + (avg_daily_sales * remaining_days))

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("🎯 Target Periode", f"{tot_target:,.0f} Pcs")
    with k2: st.metric("🎯 Target Harian Ideal", f"{daily_target_ideal:,.0f} Pcs/Hari")
    with k3: st.metric("📦 Actual (Filter Tanggal)", f"{tot_actual:,.0f} Pcs")
    with k4: st.metric("🔮 Best Estimasi Akhir", f"{best_est:,.0f} Pcs")

    st.markdown("---")
    st.subheader("📈 Grafik Fluktuasi Penjualan Harian")

    if "updated_at_dt" in filtered_sp.columns and not filtered_sp.empty:
        daily_trend = filtered_sp.groupby("updated_at_dt")["actual_qty"].sum().reset_index().sort_values(by="updated_at_dt")
        daily_trend["updated_at_str"] = daily_trend["updated_at_dt"].astype(str)
    else:
        daily_trend = pd.DataFrame({"updated_at_str": [f"Hari {i+1}" for i in range(total_range_days)], "actual_qty": [0] * total_range_days})

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=daily_trend["updated_at_str"], y=daily_trend["actual_qty"], mode='lines+markers', name="Penjualan Harian", line=dict(color="#00f2fe", width=3)))
    fig_trend.add_trace(go.Scatter(x=daily_trend["updated_at_str"], y=[daily_target_ideal] * len(daily_trend), mode='lines', name="Target Harian Ideal", line=dict(color="#ff2a6d", dash='dash', width=2)))
    fig_trend.update_layout(height=340, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#ffffff"), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Analisis Detil Growth & Disgrowth Produk")

    item_sales = filtered_sp.groupby(["item_id", "item_name"])["actual_qty"].sum().reset_index() if not filtered_sp.empty else pd.DataFrame(columns=["item_id", "item_name", "actual_qty"])
    si_grouped = sub_si.groupby(["item_id", "item_name"])["target_qty"].sum().reset_index() if not sub_si.empty else pd.DataFrame(columns=["item_id", "item_name", "target_qty"])

    # Cast item_id ke string
    si_grouped["item_id"] = si_grouped["item_id"].astype(str)
    item_sales["item_id"] = item_sales["item_id"].astype(str)

    merged_item_analysis = pd.merge(si_grouped, item_sales[["item_id", "actual_qty"]], on="item_id", how="left")
    merged_item_analysis["actual_qty"] = merged_item_analysis["actual_qty"].fillna(0)
    merged_item_analysis["gap"] = merged_item_analysis["target_qty"] - merged_item_analysis["actual_qty"]
    merged_item_analysis["ach"] = merged_item_analysis.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)

    col_g, col_d = st.columns(2)
    top_growth = merged_item_analysis.sort_values(by="actual_qty", ascending=False).head(3)
    top_disgrowth = merged_item_analysis.sort_values(by="gap", ascending=False).head(3)

    with col_g:
        st.markdown('<div style="background: #080c14; border: 1.5px solid #00ff9d; border-left: 6px solid #00ff9d; border-radius: 10px; padding: 16px; margin-bottom: 12px;"><h4 style="color: #00ff9d; margin: 0;">🚀 TOP 3 ITEM GROWTH</h4></div>', unsafe_allow_html=True)
        for _, r in top_growth.iterrows():
            st.success(f"**{r['item_name']}** - Terjual: **{r['actual_qty']:,.0f} Pcs** (Ach: **{r['ach']:.1f}%**)")

    with col_d:
        st.markdown('<div style="background: #080c14; border: 1.5px solid #ff2a6d; border-left: 6px solid #ff2a6d; border-radius: 10px; padding: 16px; margin-bottom: 12px;"><h4 style="color: #ff2a6d; margin: 0;">⚠️ TOP 3 ITEM DISGROWTH</h4></div>', unsafe_allow_html=True)
        for _, r in top_disgrowth.iterrows():
            st.error(f"**{r['item_name']}** - Sisa Gap: **{max(0, r['gap']):,.0f} Pcs** (Ach: **{r['ach']:.1f}%**)")

# --- TAB 06: INPUT & RESET DATA ---
elif selected_tab == "06 Input & Reset Data":
    st.markdown("<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>🛠️ Kelola & Input Data Penjualan</h2>", unsafe_allow_html=True)

    current_user = st.session_state.get("username", "visitor")
    user_role_str = str(st.session_state.get("user_role", "visitor")).lower()

    is_admin = "admin" in user_role_str
    is_visitor = "visitor" in user_role_str

    periods_df = st.session_state.get("periods_df", pd.DataFrame())
    si_df = st.session_state.get("sales_item_df", pd.DataFrame())
    sp_df = st.session_state.get("sales_person_df", pd.DataFrame())
    person_df = st.session_state.get("person_df", pd.DataFrame())

    tab_in1, tab_in2, tab_in3 = st.tabs(["✍️ Multi Input Sales Personil", "✏️ Edit Sales Personil", "🗑️ Hapus & Reset Sales"])

    def get_period_date_bounds(p_id):
        if not periods_df.empty and "period_id" in periods_df.columns:
            p_match = periods_df[periods_df["period_id"].astype(str) == str(p_id)]
            if not p_match.empty and "start_date" in p_match.columns and "end_date" in p_match.columns:
                try:
                    p_start = pd.to_datetime(p_match.iloc[0]["start_date"]).date()
                    p_end = pd.to_datetime(p_match.iloc[0]["end_date"]).date()
                    if p_start > p_end: p_start, p_end = p_end, p_start
                    return p_start, p_end
                except Exception: pass
        today = waktu_wib.date()
        return today.replace(day=1), today

    # SUBTAB 1: MULTI INPUT
    with tab_in1:
        st.markdown("<h4 style='color: #00ff88;'>✍️ Multi Input Sales Personil</h4>", unsafe_allow_html=True)
        if is_visitor:
            st.error("🔒 **Akses Ditolak!** Akun **Visitor** hanya memiliki akses membaca data (read-only).")
        else:
            m_period_name = st.selectbox("Pilih Periode Transaksi", list(periods_dict.keys()), key="multi_period")
            m_p_id = periods_dict[m_period_name]
            p_start, p_end = get_period_date_bounds(m_p_id)
            today_val = waktu_wib.date()

            if today_val < p_start: default_val_m = p_start
            elif today_val > p_end: default_val_m = p_end
            else: default_val_m = today_val

            str_start = p_start.strftime("%d/%m/%Y")
            str_end = p_end.strftime("%d/%m/%Y")
            label_tgl = f"Tanggal Transaksi (Batas Periode: {str_start} s/d {str_end})"
            m_date = st.date_input(label_tgl, value=default_val_m, min_value=p_start, max_value=p_end, key="multi_date")

            if not person_df.empty and "person_name" in person_df.columns:
                all_personnel = person_df["person_name"].dropna().unique().tolist()
            else:
                all_personnel = [current_user]

            if is_admin:
                m_person = st.selectbox("Pilih Nama Personil / Staf", all_personnel, key="multi_person")
            else:
                m_person = st.session_state.get("person_name", current_user)
                st.info(f"👤 Penginputan dikunci untuk akun pengguna aktif: **{m_person}**")

            filtered_si_m = si_df[si_df["period_id"].astype(str) == str(m_p_id)] if not si_df.empty and "period_id" in si_df.columns else pd.DataFrame()
            items_list = filtered_si_m[["item_id", "item_name"]].drop_duplicates().to_dict('records') if not filtered_si_m.empty and "item_name" in filtered_si_m.columns else []

            if not items_list:
                st.warning(f"⚠️ Tidak ada daftar item produk yang terdaftar pada periode **{m_period_name}**.")
            else:
                st.markdown("---")
                st.markdown("##### 📦 Masukkan Jumlah Qty Penjualan Masing-Masing Produk:")
                multi_input_values = {}
                col_m1, col_m2 = st.columns(2)
                for idx, item in enumerate(items_list):
                    target_col = col_m1 if idx % 2 == 0 else col_m2
                    item_id_str = str(item['item_id'])
                    item_name_str = str(item['item_name'])
                    with target_col:
                        qty_val = st.number_input(f"🛒 {item_name_str}", min_value=0, step=1, value=0, key=f"multi_qty_{m_p_id}_{item_id_str}")
                        multi_input_values[item_id_str] = {"item_name": item_name_str, "qty": qty_val}

                st.markdown("---")
                if st.button("💾 Simpan Semua Data Penjualan Multi-Input", use_container_width=True, key="btn_save_multi"):
                    p_match = person_df[person_df["person_name"] == m_person] if not person_df.empty and "person_name" in person_df.columns else pd.DataFrame()
                    person_id_val = p_match.iloc[0]["person_id"] if not p_match.empty and "person_id" in p_match.columns else "P999"

                    new_rows = []
                    inserted_count = 0
                    for item_id, item_data in multi_input_values.items():
                        if item_data["qty"] > 0:
                            new_id = f"SP{len(st.session_state.sales_person_df) + len(new_rows) + 1:05d}"
                            new_rows.append({
                                "record_id": new_id,
                                "period_id": str(m_p_id),
                                "item_id": str(item_id),
                                "item_name": item_data["item_name"],
                                "person_id": str(person_id_val),
                                "person_name": m_person,
                                "actual_qty": item_data["qty"],
                                "updated_at": str(m_date)
                            })
                            inserted_count += 1

                    if inserted_count > 0:
                        st.session_state.sales_person_df = pd.concat([st.session_state.sales_person_df, pd.DataFrame(new_rows)], ignore_index=True)
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.success(f"✅ Berhasil menyimpan {inserted_count} item penjualan untuk {m_person} secara permanen!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.warning("⚠️ Tidak ada Qty produk yang diisi (semua bernilai 0).")

    # SUBTAB 2: EDIT SALES
    with tab_in2:
        st.markdown("<h4 style='color: #38bdf8;'>✏️ Edit Transaksi Sales (Koreksi Input)</h4>", unsafe_allow_html=True)
        if not is_admin:
            st.error("🔒 Akses Ditolak! Fitur edit transaksi ini hanya dapat diakses oleh akun Admin.")
        else:
            e_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="edit_period")
            e_p_id = periods_dict[e_period_name]
            p_start, p_end = get_period_date_bounds(e_p_id)

            sp_sub = sp_df[sp_df["period_id"].astype(str) == str(e_p_id)].copy() if not sp_df.empty and "period_id" in sp_df.columns else pd.DataFrame()

            if sp_sub.empty:
                st.info("Belum ada data transaksi di periode ini untuk diedit.")
            else:
                e_person = st.selectbox("Pilih Personil", sp_sub["person_name"].unique(), key="edit_person")
                sp_person_sub = sp_sub[sp_sub["person_name"] == e_person].copy()

                if sp_person_sub.empty:
                    st.info("Tidak ada transaksi untuk personil ini.")
                else:
                    sp_person_sub["label_trx"] = sp_person_sub.apply(lambda r: f"[{r.get('updated_at', '-')}] {r['item_name']} - {r['actual_qty']} Pcs", axis=1)
                    selected_label = st.selectbox("Pilih Transaksi yang Akan Diedit", sp_person_sub["label_trx"].tolist(), key="edit_trx_select")
                    selected_row = sp_person_sub[sp_person_sub["label_trx"] == selected_label].iloc[0]

                    st.markdown("---")
                    col_e1, col_e2 = st.columns(2)

                    try: raw_date = pd.to_datetime(selected_row.get("updated_at")).date()
                    except Exception: raw_date = p_start

                    safe_e_date = min(max(raw_date, p_start), p_end)

                    with col_e1:
                        new_e_date = st.date_input("Ubah Tanggal Transaksi", value=safe_e_date, min_value=p_start, max_value=p_end, key="edit_date_val")
                    with col_e2:
                        new_e_qty = st.number_input("Ubah Jumlah Qty (Pcs)", min_value=0, step=1, value=int(selected_row["actual_qty"]), key="edit_qty_val")

                    if st.button("💾 Simpan Perubahan Edit", use_container_width=True, key="btn_save_edit"):
                        idx = selected_row.name
                        st.session_state.sales_person_df.loc[idx, "actual_qty"] = new_e_qty
                        st.session_state.sales_person_df.loc[idx, "updated_at"] = str(new_e_date)
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.success("✅ Perubahan transaksi berhasil disimpan permanen!")
                        time.sleep(1.5)
                        st.rerun()

    # SUBTAB 3: RESET SALES
    with tab_in3:
        st.markdown("<h4 style='color: #38bdf8;'>🗑️ Hapus Transaksi / Reset Sales Personil</h4>", unsafe_allow_html=True)
        if not is_admin:
            st.error("🔒 Akses Ditolak! Fitur hapus/reset transaksi hanya dapat dilakukan oleh akun Admin.")
        else:
            d_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="del_period")
            d_p_id = periods_dict[d_period_name]

            sp_del_sub = sp_df[sp_df["period_id"].astype(str) == str(d_p_id)].copy() if not sp_df.empty and "period_id" in sp_df.columns else pd.DataFrame()

            if sp_del_sub.empty:
                st.info("Tidak ada transaksi untuk dihapus pada periode ini.")
            else:
                d_person = st.selectbox("Pilih Personil", sp_del_sub["person_name"].unique(), key="del_person")
                sp_del_person = sp_del_sub[sp_del_sub["person_name"] == d_person]

                mode_hapus = st.radio("Pilih Opsi Penghapusan:", ["Hapus Item Tertentu Saja", "Reset Seluruh Penjualan Personil Ini"], key="del_mode")

                if mode_hapus == "Hapus Item Tertentu Saja":
                    d_item_name = st.selectbox("Pilih Produk yang Ingin Dihapus", sp_del_person["item_name"].unique(), key="del_item_select")
                    if st.button(f"🗑️ Hapus Transaksi Produk '{d_item_name}'", use_container_width=True, key="btn_del_single"):
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~((st.session_state.sales_person_df["period_id"].astype(str) == str(d_p_id)) &
                              (st.session_state.sales_person_df["person_name"] == d_person) &
                              (st.session_state.sales_person_df["item_name"] == d_item_name))
                        ]
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.warning(f"🗑️ Transaksi '{d_item_name}' untuk {d_person} berhasil dihapus permanen!")
                        time.sleep(1.5)
                        st.rerun()
                else:
                    st.error(f"⚠️ Perhatian: Aksi ini akan menghapus SELURUH catatan penjualan {d_person} pada periode ini.")
                    if st.button(f"🚨 Reset Total Sales {d_person} di Periode Ini", use_container_width=True, key="btn_reset_all"):
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~((st.session_state.sales_person_df["period_id"].astype(str) == str(d_p_id)) &
                              (st.session_state.sales_person_df["person_name"] == d_person))
                        ]
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.warning(f"🚨 Seluruh transaksi {d_person} pada periode ini berhasil di-reset!")
                        time.sleep(1.5)
                        st.rerun()

# ==========================================
# TAB 07: MASTER DATA & PENGATURAN SYSTEM
# ==========================================
elif selected_tab == "07 Master Data & Pengaturan":
    st.markdown("<h3 style='color: #00ff88;'>⚙️ Master Data & Pengaturan System</h3>", unsafe_allow_html=True)

    # 1. Cek Status Admin
    is_admin = st.session_state.get("is_admin", False) or (str(st.session_state.get("user_role", "")).strip().lower() == "admin")

    # 2. Ambil data database dari session state (Mencegah Error items_df)
    items_df = st.session_state.get("items_df", pd.DataFrame())
    periods_df = st.session_state.get("periods_df", pd.DataFrame())
    si_df = st.session_state.get("sales_item_df", pd.DataFrame())
    person_df = st.session_state.get("person_df", pd.DataFrame())

    # 3. Buat dictionary periode
    periods_dict = {}
    if not periods_df.empty and "period_name" in periods_df.columns and "period_id" in periods_df.columns:
        periods_dict = dict(zip(periods_df["period_name"], periods_df["period_id"]))

    # 4. Pengecekan Akses
    if not is_admin:
        st.warning("🔒 Akses terbatas! Halaman ini hanya dapat diakses oleh Admin.")
    else:
        m_tab1, m_tab2, m_tab3, m_tab4 = st.tabs([
            "👥 Master Personil", 
            "📦 Master Item & Target", 
            "🗓️ Master Periode", 
            "⚙️ Pengaturan System"
        ])

        # ------------------------------------------------------------------
        # SUBTAB 1: MASTER PERSONIL (FIX BUG USERNAME)
        # ------------------------------------------------------------------
        with m_tab1:
            st.markdown("<h4 style='color: #00ff88;'>👥 Kelola Master Personil & User Login</h4>", unsafe_allow_html=True)
            
            if "personil_success_msg" in st.session_state and st.session_state.person_personil_msg:
                st.success(st.session_state.personil_success_msg)
                del st.session_state["personil_success_msg"]

            col_p1, col_p2 = st.columns([1.2, 1])
            with col_p1:
                st.markdown("##### 📋 Daftar User Terdaftar")
                if not st.session_state.person_df.empty:
                    st.dataframe(st.session_state.person_df[["person_id", "nik", "person_name", "username", "role"]], use_container_width=True, hide_index=True)
            
            with col_p2:
                st.markdown("##### ➕ Tambah User Baru")
                with st.form("form_add_personil"):
                    new_nik = st.text_input("NIK Kasir / Staff")
                    new_nama = st.text_input("Nama Lengkap")
                    new_user = st.text_input("Username Login")
                    new_pass = st.text_input("Password", type="password")
                    new_role = st.selectbox("Role Akun", ["Admin", "Staff Toko", "Kasir Toko"], index=1)

                    btn_add_p = st.form_submit_button("➕ Tambah User", use_container_width=True)

                    if btn_add_p:
                        # Fix Bug Username: Paksa Lowercase & Strip Whitespace
                        clean_user = str(new_user).strip().lower()
                        if not clean_user or not new_pass or not new_nama:
                            st.warning("⚠️ Nama, Username, dan Password wajib diisi!")
                        else:
                            existing_users = st.session_state.person_df["username"].astype(str).str.strip().str.lower().tolist() if not st.session_state.person_df.empty else []
                            if clean_user in existing_users:
                                st.error(f"❌ Username '{clean_user}' sudah terdaftar!")
                            else:
                                new_person_id = f"P{len(st.session_state.person_df) + 1:03d}"
                                new_row = pd.DataFrame([{
                                    "person_id": new_person_id,
                                    "nik": str(new_nik).strip(),
                                    "person_name": str(new_nama).strip().upper(),
                                    "username": clean_user,  # Username tersimpan bersih
                                    "password": str(new_pass).strip(),
                                    "role": str(new_role)
                                }])
                                st.session_state.person_df = pd.concat([st.session_state.person_df, new_row], ignore_index=True)
                                save_master_table("MASTER_PERSONIL", st.session_state.person_df)
                                st.cache_data.clear()
                                st.session_state["personil_success_msg"] = f"🎉 User '{clean_user}' berhasil ditambahkan!"
                                st.rerun()

        # ------------------------------------------------------------------
        # SUBTAB 2: MASTER ITEM & TARGET (TAMBAH, EDIT, SET, HAPUS)
        # ------------------------------------------------------------------
        with m_tab2:
            st.markdown("<h4 style='color: #00ff88;'>📦 Kelola Master Item & Target Penjualan</h4>", unsafe_allow_html=True)
            
            sub_itm1, sub_itm2, sub_itm3 = st.tabs([
                "➕ Tambah Item", 
                "🎯 Set Target Toko & Kasir",  
                "🗑️ Hapus Item"
            ])

                      # 1. TAMBAH ITEM BARU (+ PERIODE PRODUK)
            with sub_itm1:
                st.caption("Gunakan formulir ini untuk mendaftarkan barang/produk baru ke dalam database system.")

                with st.form("form_add_new_item"):
                    col_id, col_period = st.columns(2)

                    with col_id:
                        # Auto-generate ID Item
                        next_id_num = len(items_df) + 1 if not items_df.empty else 1
                        new_item_id = st.text_input("ID Item", value=f"ITM{next_id_num:03d}", key="add_itm_id")

                    with col_period:
                        # Pilih Periode Produk
                        p_options = list(periods_dict.keys()) if periods_dict else ["Belum Ada Periode"]
                        sel_item_period = st.selectbox("Pilih Periode Produk", options=p_options, key="add_itm_period")

                    col_name, col_price = st.columns(2)
                    with col_name:
                        new_item_name = st.text_input("Nama Produk / Item", placeholder="Contoh: PAKET HAPPY", key="add_itm_name")

                    btn_save_item = st.form_submit_button("💾 Simpan Item Baru", use_container_width=True)

                    if btn_save_item:
                        if not new_item_name.strip():
                            st.error("❌ Nama produk tidak boleh kosong!")
                        elif not periods_dict:
                            st.error("❌ Silakan buat periode terlebih dahulu di menu Master Periode!")
                        else:
                            selected_p_id = str(periods_dict[sel_item_period])

                            # 1. Simpan ke MASTER_ITEM
                            new_item_data = {
                                "item_id": new_item_id,
                                "item_name": new_item_name.strip(),
                                "price": new_item_price,
                                "period_id": selected_p_id
                            }

                            st.session_state.items_df = pd.concat([
                                st.session_state.items_df, 
                                pd.DataFrame([new_item_data])
                            ], ignore_index=True)

                            save_master_table("MASTER_ITEM", st.session_state.items_df)

                            # 2. Inisialisasi otomatis ke SALES_ITEM agar langsung terhubung ke periode terpilih
                            new_si_row = {
                                "period_id": selected_p_id,
                                "item_id": new_item_id,
                                "item_name": new_item_name.strip(),
                                "target_qty": 0,
                                "actual_qty": 0
                            }

                            st.session_state.sales_item_df = pd.concat([
                                st.session_state.sales_item_df, 
                                pd.DataFrame([new_si_row])
                            ], ignore_index=True)

                            save_master_table("SALES_ITEM", st.session_state.sales_item_df)

                            st.success(f"✅ Produk '{new_item_name}' berhasil ditambahkan ke periode **{sel_item_period}**!")
                            st.rerun()



            # 2. SET TARGET TOKO & KASIR PER PERIODE (LAYOUT SESUAI REFERENSI)
            with sub_itm2:
                if periods_df.empty:
                    st.info("ℹ️ Belum ada periode promosi. Silakan buat periode terlebih dahulu pada tab Master Periode.")
                else:
                    st.caption("Pilih periode dan produk untuk memperbarui target. Jika belum ada target, abaikan bagian ini.")

                    # 1. Select Periode
                    sel_p_target = st.selectbox("Pilih Periode Target", list(periods_dict.keys()), key="sb_target_period_ref")
                    target_p_id = str(periods_dict[sel_p_target])

                    # Ambil data SALES_ITEM khusus periode terpilih
                    si_p_sub = st.session_state.sales_item_df[
                        st.session_state.sales_item_df["period_id"].astype(str) == target_p_id
                    ] if not st.session_state.sales_item_df.empty else pd.DataFrame()

                    # Filter item yang terdaftar di periode ini (jika belum ada, tampilkan semua master item)
                    available_items_in_p = si_p_sub["item_name"].tolist() if not si_p_sub.empty else items_df["item_name"].tolist()
                    
                    if not available_items_in_p:
                        st.warning("⚠️ Belum ada item terdaftar di Master Item.")
                    else:
                        # 2. Select Produk Item
                        sel_item_name = st.selectbox("Pilih Produk Item", available_items_in_p, key="sb_target_item_ref")
                        
                        # Ambil ID Item
                        selected_item_row = items_df[items_df["item_name"] == sel_item_name]
                        if not selected_item_row.empty:
                            target_item_id = str(selected_item_row.iloc[0]["item_id"])
                        else:
                            target_item_id = ""

                        # Ambil nilai target eksisting Toko & Kasir
                        exist_toko_target = 0
                        exist_kasir_target = 0

                        if not si_p_sub.empty and target_item_id:
                            match_si = si_p_sub[si_p_sub["item_id"].astype(str) == target_item_id]
                            if not match_si.empty:
                                exist_toko_target = int(pd.to_numeric(match_si.iloc[0].get("target_qty", 0), errors="coerce"))

                        # Ambil target kasir jika ada di SALES_PERSON
                        if not st.session_state.sales_person_df.empty and target_item_id:
                            sp_sub = st.session_state.sales_person_df[
                                (st.session_state.sales_person_df["period_id"].astype(str) == target_p_id) &
                                (st.session_state.sales_person_df["item_id"].astype(str) == target_item_id)
                            ]
                            if not sp_sub.empty:
                                exist_kasir_target = int(pd.to_numeric(sp_sub.iloc[0].get("target_qty", 0), errors="coerce"))

                        # 3. Form Input 2 Kolom (Toko & Kasir)
                        with st.form("form_set_target_ref"):
                            col_toko, col_kasir = st.columns(2)
                            
                            with col_toko:
                                input_target_toko = st.number_input(
                                    "Target Penjualan Toko (Qty Pcs)", 
                                    min_value=0, 
                                    value=exist_toko_target,
                                    key="in_t_toko"
                                )

                            with col_kasir:
                                input_target_kasir = st.number_input(
                                    "Target Penjualan Kasir (Qty Pcs)", 
                                    min_value=0, 
                                    value=exist_kasir_target,
                                    key="in_t_kasir"
                                )

                            btn_save_target_ref = st.form_submit_button("💾 Simpan / Update Target Ke Google Sheets", use_container_width=False)

                            if btn_save_target_ref:
                                # Update Database Target Toko (SALES_ITEM)
                                other_si = st.session_state.sales_item_df[
                                    ~((st.session_state.sales_item_df["period_id"].astype(str) == target_p_id) & 
                                      (st.session_state.sales_item_df["item_id"].astype(str) == target_item_id))
                                ].copy() if not st.session_state.sales_item_df.empty else pd.DataFrame()

                                curr_act_toko = 0
                                if not si_p_sub.empty:
                                    m_act = si_p_sub[si_p_sub["item_id"].astype(str) == target_item_id]
                                    if not m_act.empty:
                                        curr_act_toko = int(pd.to_numeric(m_act.iloc[0].get("actual_qty", 0), errors="coerce"))

                                new_si_data = pd.DataFrame([{
                                    "period_id": target_p_id,
                                    "item_id": target_item_id,
                                    "item_name": sel_item_name,
                                    "target_qty": input_target_toko,
                                    "actual_qty": curr_act_toko
                                }])

                                st.session_state.sales_item_df = pd.concat([other_si, new_si_data], ignore_index=True)
                                save_master_table("SALES_ITEM", st.session_state.sales_item_df)

                                # Update Database Target Kasir (SALES_PERSON - Set rata ke seluruh kasir/default)
                                if not st.session_state.person_df.empty:
                                    kasir_list = st.session_state.person_df[
                                        st.session_state.person_df["role"].astype(str).str.lower().isin(["kasir toko", "staff toko", "kasir", "staff"])
                                    ]
                                    
                                    other_sp = st.session_state.sales_person_df[
                                        ~((st.session_state.sales_person_df["period_id"].astype(str) == target_p_id) & 
                                          (st.session_state.sales_person_df["item_id"].astype(str) == target_item_id))
                                    ].copy() if not st.session_state.sales_person_df.empty else pd.DataFrame()

                                    new_sp_rows = []
                                    for _, k_row in kasir_list.iterrows():
                                        k_id = str(k_row["person_id"])
                                        k_name = str(k_row["person_name"])
                                        
                                        curr_k_act = 0
                                        if not st.session_state.sales_person_df.empty:
                                            m_k = st.session_state.sales_person_df[
                                                (st.session_state.sales_person_df["period_id"].astype(str) == target_p_id) &
                                                (st.session_state.sales_person_df["item_id"].astype(str) == target_item_id) &
                                                (st.session_state.sales_person_df["person_id"].astype(str) == k_id)
                                            ]
                                            if not m_k.empty:
                                                curr_k_act = int(pd.to_numeric(m_k.iloc[0].get("actual_qty", 0), errors="coerce"))

                                        new_sp_rows.append({
                                            "period_id": target_p_id,
                                            "person_id": k_id,
                                            "person_name": k_name,
                                            "item_id": target_item_id,
                                            "item_name": sel_item_name,
                                            "target_qty": input_target_kasir,
                                            "actual_qty": curr_k_act
                                        })

                                    st.session_state.sales_person_df = pd.concat([other_sp, pd.DataFrame(new_sp_rows)], ignore_index=True)
                                    save_master_table("SALES_PERSON", st.session_state.sales_person_df)

                                st.success(f"✅ Target item '{sel_item_name}' untuk Toko & Kasir berhasil tersimpan ke Google Sheets!")
                                st.rerun()

            # 3. HAPUS ITEM (INTEGRASI LANGSUNG SPREADSHEET)
            with sub_itm3:
                if items_df.empty:
                    st.info("ℹ️ Tidak ada item untuk dihapus.")
                else:
                    item_to_del = st.selectbox("Pilih Item yang Akan Dihapus", items_df["item_name"].tolist(), key="sb_del_item")
                    target_del_row = items_df[items_df["item_name"] == item_to_del].iloc[0]
                    del_item_id = str(target_del_row["item_id"])

                    st.warning(f"⚠️ Menghapus item **{item_to_del}** juga akan menghapus data target item ini pada seluruh periode.")
                    if st.button("🗑️ Hapus Item Ini Permanen", use_container_width=True):
                        # Hapus dari MASTER_ITEM
                        st.session_state.items_df = st.session_state.items_df[st.session_state.items_df["item_id"].astype(str) != del_item_id].reset_index(drop=True)
                        save_master_table("MASTER_ITEM", st.session_state.items_df)

                        # Hapus dari SALES_ITEM
                        if not st.session_state.sales_item_df.empty:
                            st.session_state.sales_item_df = st.session_state.sales_item_df[st.session_state.sales_item_df["item_id"].astype(str) != del_item_id].reset_index(drop=True)
                            save_master_table("SALES_ITEM", st.session_state.sales_item_df)

                        st.success(f"🗑️ Item '{item_to_del}' dan seluruh target terkait berhasil dihapus!")
                        st.rerun()

        # ------------------------------------------------------------------
        # SUBTAB 3: MASTER PERIODE (TAMBAH & HAPUS BERSIH)
        # ------------------------------------------------------------------
        with m_tab3:
            st.markdown("<h4 style='color: #00ff88;'>🗓️ Kelola Master Periode Promosi</h4>", unsafe_allow_html=True)
            
            p_tab1, p_tab2 = st.tabs(["➕ Tambah Periode", "🗑️ Hapus Periode Selesai"])

            # 1. TAMBAH PERIODE
            with p_tab1:
                with st.form("form_add_period"):
                    col_per1, col_per2, col_per3 = st.columns(3)
                    with col_per1:
                        new_pid = st.text_input("ID Periode", value=f"P{len(periods_df)+1:02d}")
                        new_pname = st.text_input("Nama Periode (Contoh: PSM FEBRUARI W1)")
                    with col_per2:
                        new_pstart = st.date_input("Tanggal Mulai", value=waktu_wib.date())
                    with col_per3:
                        new_pend = st.date_input("Tanggal Selesai", value=waktu_wib.date())

                    btn_add_period = st.form_submit_button("💾 Simpan Periode Baru", use_container_width=True)

                    if btn_add_period:
                        if not new_pname.strip():
                            st.warning("⚠️ Nama periode wajib diisi!")
                        elif new_pstart > new_pend:
                            st.error("❌ Tanggal mulai tidak boleh melebihi tanggal selesai!")
                        else:
                            new_period_row = pd.DataFrame([{
                                "period_id": str(new_pid).strip(),
                                "period_name": str(new_pname).strip().upper(),
                                "start_date": str(new_pstart),
                                "end_date": str(new_pend)
                            }])
                            st.session_state.periods_df = pd.concat([st.session_state.periods_df, new_period_row], ignore_index=True)
                            save_master_table("PERIODE", st.session_state.periods_df)
                            st.success(f"✅ Periode '{new_pname}' berhasil ditambahkan!")
                            st.rerun()

                st.markdown("---")
                st.markdown("##### 📋 Daftar Periode Aktif")
                if not periods_df.empty:
                    st.dataframe(periods_df, use_container_width=True, hide_index=True)

            # 2. HAPUS PERIODE & CLEANUP TOTAL
            with p_tab2:
                if periods_df.empty:
                    st.info("ℹ️ Tidak ada periode terdaftar.")
                else:
                    p_to_del_name = st.selectbox("Pilih Periode yang Akan Dihapus", list(periods_dict.keys()), key="sb_del_period")
                    p_to_del_id = periods_dict[p_to_del_name]

                    st.error("🚨 **PERHATIAN (Pembersihan Dokumen)**:")
                    st.write(f"Menghapus periode **{p_to_del_name}** akan menghapus secara permanen:")
                    st.write("1. Data Periode dari Master")
                    st.write("2. Semua Target & Penjualan Item Toko pada periode ini (`SALES_ITEM`)")
                    st.write("3. Semua Transaksi & Penjualan Kasir pada periode ini (`SALES_PERSON`)")

                    if st.button("🔥 Hapus Periode & Seluruh Riwayat Terkait", use_container_width=True):
                        # Hapus dari MASTER_PERIODE
                        st.session_state.periods_df = st.session_state.periods_df[st.session_state.periods_df["period_id"].astype(str) != str(p_to_del_id)].reset_index(drop=True)
                        save_master_table("PERIODE", st.session_state.periods_df)

                        # Hapus dari SALES_ITEM
                        if not st.session_state.sales_item_df.empty:
                            st.session_state.sales_item_df = st.session_state.sales_item_df[st.session_state.sales_item_df["period_id"].astype(str) != str(p_to_del_id)].reset_index(drop=True)
                            save_master_table("SALES_ITEM", st.session_state.sales_item_df)

                        # Hapus dari SALES_PERSON
                        if not st.session_state.sales_person_df.empty:
                            st.session_state.sales_person_df = st.session_state.sales_person_df[st.session_state.sales_person_df["period_id"].astype(str) != str(p_to_del_id)].reset_index(drop=True)
                            save_master_table("SALES_PERSON", st.session_state.sales_person_df)

                        st.cache_data.clear()
                        st.success(f"🧹 Periode '{p_to_del_name}' beserta seluruh riwayat penjualan berhasil dibersihkan dari Spreadsheet!")
                        st.rerun()

        # ------------------------------------------------------------------
        # SUBTAB 4: PENGATURAN SYSTEM (TANPA EXPORT BACKUP)
        # ------------------------------------------------------------------
        with m_tab4:
            st.markdown("<h4 style='color: #00f0ff;'>⚙️ Pemeliharaan System & Sinkronisasi Realtime</h4>", unsafe_allow_html=True)
            st.info("Gunakan menu ini untuk menyinkronkan ulang cache Streamlit dengan data Spreadsheet.")

            col_sys1, col_sys2 = st.columns(2)
            with col_sys1:
                if st.button("🔄 Paksa Muat Ulang Data (Reload Database)", use_container_width=True):
                    st.cache_data.clear()
                    p_df, i_df, pers_df, si_df_new, sp_df_new = load_database()
                    st.session_state.periods_df = p_df
                    st.session_state.items_df = i_df
                    st.session_state.person_df = pers_df
                    st.session_state.sales_item_df = si_df_new
                    st.session_state.sales_person_df = sp_df_new
                    st.toast("Database berhasil dimuat ulang secara realtime!", icon="🔄")
                    time.sleep(1)
                    st.rerun()

            with col_sys2:
                if st.button("⚡ Rekap Ulang Total Penjualan Toko", use_container_width=True):
                    sync_store_sales_from_personnel()
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.toast("Total penjualan toko berhasil dikalkulasi ulang dari data personil!", icon="✅")
                    time.sleep(1)
                    st.rerun()

