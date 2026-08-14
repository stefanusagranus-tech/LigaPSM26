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
            username_input = st.text_input("Username", placeholder="Masukkan username").strip()
            password_input = st.text_input("Password", type="password", placeholder="Masukkan password")
            submit_btn = st.form_submit_button("Masuk ke Aplikasi", use_container_width=True)
            
            if submit_btn:
                if not username_input or not password_input:
                    st.warning("⚠️ Username dan Password wajib diisi!")
                elif check_login(username_input, password_input):
                    st.toast(f"🎉 Selamat Datang, {st.session_state.get('person_name', username_input)}!", icon="✅")
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
    "01 Overview",
    "02 Detail Item",
    "03 Penjualan Personil",
    "04 Pencapaian Pernik",
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
    st.session_state.logged_in = False
    st.session_state.username = ""
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

# --- TAB 01: OVERVIEW PENJUALAN ---
if selected_tab == "01 Overview":
    st.title("Overview Penjualan Toko")
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

    st.markdown("### 🗓️ Filter Rentang Tanggal Overview")
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.date_input("Tanggal Awal Overview", value=default_start, key="t1_start_date")
    with col_date2:
        end_date = st.date_input("Tanggal Akhir Overview", value=default_end, key="t1_end_date")

    if start_date > end_date:
        st.error("⚠️ Tanggal Awal tidak boleh melebihi Tanggal Akhir!")
        st.stop()

    if "updated_at" in sub_sp.columns and not sub_sp.empty:
        sub_sp["updated_at_dt"] = pd.to_datetime(sub_sp["updated_at"]).dt.date
        filtered_sp = sub_sp[(sub_sp["updated_at_dt"] >= start_date) & (sub_sp["updated_at_dt"] <= end_date)].copy()
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

    if "target_qty" not in sub_si.columns: sub_si["target_qty"] = 0
    sub_si["target_qty"] = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0)
    
    if "actual_qty" in filtered_sp.columns:
        filtered_sp["actual_qty"] = pd.to_numeric(filtered_sp["actual_qty"], errors="coerce").fillna(0)
    else:
        filtered_sp["actual_qty"] = 0

    tot_target = sub_si["target_qty"].sum()
    tot_actual = filtered_sp["actual_qty"].sum()
    tot_gap = tot_target - tot_actual
    tot_ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.metric("🎯 Total Target", f"{tot_target:,.0f} Pcs")
    with m2: st.metric("📦 Actual Penjualan", f"{tot_actual:,.0f} Pcs")
    with m3: st.metric("📉 Sisa Gap Target", f"{tot_gap:,.0f} Pcs")
    with m4: st.metric("⚡ % Achievement", f"{tot_ach:.1f}%")
    with m5: st.metric("⏳ Time Factor (Waktu)", f"{time_factor:.1f}%", help=f"Hari berjalan: {passed_days}/{total_days} hari")

    st.markdown("---")

    pace_gap = tot_ach - time_factor
    if pace_gap >= 0:
        status_color = "#00ff9d"
        status_bg = "rgba(0, 255, 157, 0.1)"
        status_icon = "🚀"
        status_title = "PACE PENJUALAN ON TRACK"
        status_desc = f"Pencapaian penjualan (**{tot_ach:.1f}%**) melampaui laju waktu berjalan (**{time_factor:.1f}%**). Pertahankan performa toko!"
    else:
        status_color = "#ff2a6d"
        status_bg = "rgba(255, 42, 109, 0.1)"
        status_icon = "⚠️"
        status_title = "PACE PENJUALAN BEHIND TARGET"
        status_desc = f"Pencapaian penjualan (**{tot_ach:.1f}%**) masih di bawah laju waktu berjalan (**{time_factor:.1f}%**). Tertinggal sebesar **{abs(pace_gap):.1f}%**."

    st.markdown(f"""
    <div style="background: {status_bg}; border: 1.5px solid {status_color}; border-left: 6px solid {status_color}; border-radius: 10px; padding: 16px; margin-bottom: 20px;">
        <h4 style="color: {status_color}; margin: 0 0 6px 0;">{status_icon} {status_title}</h4>
        <p style="color: #f1f5f9; margin: 0; font-size: 14px;">{status_desc}</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("📊 Ringkasan Penjualan Per Item Produk")
    
    # Aggregasi sub_si agar item_id tidak terduplikasi jika "Semua Periode" dipilih
    si_grouped = sub_si.groupby(["item_id", "item_name"])["target_qty"].sum().reset_index() if not sub_si.empty else pd.DataFrame(columns=["item_id", "item_name", "target_qty"])
    item_sp = filtered_sp.groupby(["item_id", "item_name"])["actual_qty"].sum().reset_index() if not filtered_sp.empty else pd.DataFrame(columns=["item_id", "item_name", "actual_qty"])

    overview_table = pd.merge(si_grouped, item_sp[["item_id", "actual_qty"]], on="item_id", how="left")
    overview_table["actual_qty"] = overview_table["actual_qty"].fillna(0)
    overview_table["gap"] = overview_table["target_qty"] - overview_table["actual_qty"]
    overview_table["ach"] = overview_table.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)

    table_rows_html = ""
    for _, row in overview_table.iterrows():
        gap_color = "#00ff88" if row['gap'] <= 0 else "#ef4444"
        ach_color = "#00ff88" if row['ach'] >= time_factor else "#ffb703"
        table_rows_html += f"""
        <tr style="border-bottom: 1px solid #1e293b;">
            <td style="padding: 10px; color: #ffffff; font-weight: bold; font-size: 13px;">{row['item_name']}</td>
            <td style="padding: 10px; color: #94a3b8; font-size: 13px;">{row['target_qty']:,.0f} Pcs</td>
            <td style="padding: 10px; color: #00ff88; font-weight: bold; font-size: 13px;">{row['actual_qty']:,.0f} Pcs</td>
            <td style="padding: 10px; color: {gap_color}; font-size: 13px;">{row['gap']:,.0f} Pcs</td>
            <td style="padding: 10px; color: {ach_color}; font-weight: bold; font-size: 13px;">{row['ach']:.1f}%</td>
        </tr>
        """

    st.markdown(f"""
        <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; max-height: 400px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                <thead>
                    <tr style="border-bottom: 2px solid #334155;">
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">NAMA PRODUK</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">TARGET TOKO</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">ACTUAL PENJUALAN</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">SISA GAP</th>
                        <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">% ACHIEVEMENT</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
        </div>
    """, unsafe_allow_html=True)
    
# --- TAB 02: DETAIL ITEM ---
elif selected_tab == "02 Detail Item":
    st.title("📦 Detail Item & Performa Produk")
    si_df = st.session_state.sales_item_df.copy()
    
    st.markdown("<p style='color:#38bdf8; font-weight:bold; font-size:13px;'>🔍 FILTER & PENGURUTAN DATA PRODUK</p>", unsafe_allow_html=True)
    f_col1, f_col2, f_col3 = st.columns([1.5, 1, 1.2])
    with f_col1:
        search_query = st.text_input("Cari Nama Produk / Item", placeholder="Ketik nama item...", key="search_item_tab2")
    with f_col2:
        selected_p_tab2 = st.selectbox("Periode Promosi", ["Semua Periode Promosi"] + list(periods_dict.keys()), key="period_tab2")
    with f_col3:
        sort_option = st.selectbox("Urutkan Berdasarkan", ["Penjualan Terbanyak (Terlaris)", "Penjualan Tersedikit", "Achievement Tertinggi (% Ach)", "Nama Produk (A - Z)"], key="sort_tab2")

    if selected_p_tab2 != "Semua Periode Promosi":
        p_id_filter = periods_dict[selected_p_tab2]
        si_df = si_df[si_df["period_id"] == p_id_filter]

    si_df["target_qty"] = pd.to_numeric(si_df["target_qty"], errors="coerce").fillna(0)
    si_df["actual_qty"] = pd.to_numeric(si_df["actual_qty"], errors="coerce").fillna(0)

    item_grouped = si_df.groupby("item_name").agg({"target_qty": "sum", "actual_qty": "sum"}).reset_index()
    item_grouped["ach"] = item_grouped.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)
    item_grouped["gap"] = item_grouped["actual_qty"] - item_grouped["target_qty"]

    if search_query:
        item_grouped = item_grouped[item_grouped["item_name"].str.contains(search_query, case=False, na=False)]

    if not item_grouped.empty:
        top_item = item_grouped.sort_values(by="actual_qty", ascending=False).iloc[0]
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
            st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                <div style="color: #f59e0b; font-size: 11px; font-weight: bold;">🔥 ITEM TERLARIS</div>
                <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{top_item['item_name']}</div>
                <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{top_item['actual_qty']:,.0f} Pcs</div>
            </div>""", unsafe_allow_html=True)
        with r_col2:
            st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                <div style="color: #ef4444; font-size: 11px; font-weight: bold;">📉 ITEM TERENDAH</div>
                <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{low_item['item_name']}</div>
                <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{low_item['actual_qty']:,.0f} Pcs</div>
            </div>""", unsafe_allow_html=True)
        with r_col3:
            st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                <div style="color: #38bdf8; font-size: 11px; font-weight: bold;">📦 VARIASI ITEM</div>
                <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{len(item_grouped)} Jenis</div>
                <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{item_grouped['actual_qty'].sum():,.0f} Pcs Total</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        table_rows_html = ""
        for _, row in item_grouped.iterrows():
            gap_color = "#00ff88" if row['gap'] >= 0 else "#ef4444"
            table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 12px; color: #ffffff; font-weight: bold;">{row['item_name']}</td>
                <td style="padding: 12px; color: #94a3b8;">{row['target_qty']:,.0f}</td>
                <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['ach']:.1f}%</td>
                <td style="padding: 12px; color: {gap_color}; font-weight: bold;">{row['gap']:,.0f}</td>
            </tr>
            """

    st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 12px; max-height: 520px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #334155;">
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">NAMA PRODUK</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">TARGET (PCS)</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">ACTUAL SALES</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">% ACH</th>
                            <th style="padding: 10px; color: #38bdf8; font-size: 11px;">GAP / SELISIH</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
            </div>
        """, unsafe_allow_html=True)

# --- TAB 03: PENJUALAN PERSONIL ---
elif selected_tab == "03 Penjualan Personil":
    st.title("👥 Penjualan Personil Toko")
    sp_df = st.session_state.sales_person_df.copy()
    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
        
    sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)

    if not sp_df.empty:
        summary_person = sp_df.groupby("person_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        tot_actual_personil = summary_person["actual_qty"].sum()
        avg_sales_personil = summary_person["actual_qty"].mean() if len(summary_person) > 0 else 0
        top_performer_name = summary_person.iloc[0]["person_name"] if len(summary_person) > 0 else "-"
        summary_person["pct_contrib"] = (summary_person["actual_qty"] / tot_actual_personil * 100) if tot_actual_personil > 0 else 0

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f'<div style="background:#080c14; border:1.5px solid #00f0ff; border-radius:10px; padding:16px;"><div style="color:#ffffff; font-size:11px; font-weight:bold;">TOTAL ACTUAL PERSONIL</div><div style="color:#00ff88; font-size:28px; font-weight:800;">{tot_actual_personil:,.0f} Pcs</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div style="background:#080c14; border:1.5px solid #00f0ff; border-radius:10px; padding:16px;"><div style="color:#ffffff; font-size:11px; font-weight:bold;">RATA-RATA PENJUALAN/STAF</div><div style="color:#00ff88; font-size:28px; font-weight:800;">{avg_sales_personil:,.0f} Pcs</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div style="background:#080c14; border:1.5px solid #00f0ff; border-radius:10px; padding:16px;"><div style="color:#ffffff; font-size:11px; font-weight:bold;">TOP PERFORMER</div><div style="color:#00ff88; font-size:26px; font-weight:800;">{top_performer_name}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if len(summary_person) >= 1:
            p1_name = summary_person.iloc[0]["person_name"]
            p1_qty = summary_person.iloc[0]["actual_qty"]
            p2_name = summary_person.iloc[1]["person_name"] if len(summary_person) >= 2 else "-"
            p2_qty = summary_person.iloc[1]["actual_qty"] if len(summary_person) >= 2 else 0
            p3_name = summary_person.iloc[2]["person_name"] if len(summary_person) >= 3 else "-"
            p3_qty = summary_person.iloc[2]["actual_qty"] if len(summary_person) >= 3 else 0

            st.markdown(f"""
                <div style="display: flex; gap: 12px; justify-content: center; align-items: flex-end; margin-bottom: 20px;">
                    <div style="flex: 1; background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; text-align: center;">
                        <span style="font-size: 18px;">🥈</span>
                        <div style="color: #94a3b8; font-size: 10px; font-weight: bold;">JUARA 2</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold;">{p2_name}</div>
                        <div style="color: #00ff88; font-size: 15px; font-weight: 800;">{p2_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #080c14; border: 2px solid #00f0ff; border-radius: 10px; padding: 12px; text-align: center; transform: scale(1.02);">
                        <span style="font-size: 22px;">🥇</span>
                        <div style="color: #f59e0b; font-size: 10px; font-weight: bold;">JUARA 1</div>
                        <div style="color: #ffffff; font-size: 13px; font-weight: bold;">{p1_name}</div>
                        <div style="color: #00ff88; font-size: 17px; font-weight: 800;">{p1_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; text-align: center;">
                        <span style="font-size: 18px;">🥉</span>
                        <div style="color: #b45309; font-size: 10px; font-weight: bold;">JUARA 3</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold;">{p3_name}</div>
                        <div style="color: #00ff88; font-size: 15px; font-weight: 800;">{p3_qty:,.0f} Pcs</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        col_table, col_chart = st.columns([1, 1])
        COMPONENT_HEIGHT = 310

        with col_table:
            st.markdown("<p style='color:#ffffff; font-size:15px; font-weight:bold;'>📋 Tabel Ranking Personil</p>", unsafe_allow_html=True)
            table_rows_html = ""
            for _, row in summary_person.iterrows():
                table_rows_html += f"""
                <tr style="border-bottom: 1px solid #1e293b;">
                    <td style="padding: 12px; color: #ffffff; font-weight: bold;">{row['person_name']}</td>
                    <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                    <td style="padding: 12px; color: #00ff88; font-weight: bold;">{row['pct_contrib']:.1f}%</td>
                </tr>
                """
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; height: {COMPONENT_HEIGHT}px; overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                        <thead>
                            <tr style="border-bottom: 2px solid #334155;">
                                <th style="padding: 8px; color: #94a3b8; font-size: 11px;">PERSONIL</th>
                                <th style="padding: 8px; color: #94a3b8; font-size: 11px;">TOTAL SALES</th>
                                <th style="padding: 8px; color: #94a3b8; font-size: 11px;">KONTRIBUSI</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                </div>
            """, unsafe_allow_html=True)

        with col_chart:
            st.markdown("<p style='color:#ffffff; font-size:15px; font-weight:bold;'>📊 Grafik Perbandingan Personil</p>", unsafe_allow_html=True)
            fig_person = go.Figure()
            fig_person.add_trace(go.Bar(
                x=summary_person["person_name"],
                y=summary_person["actual_qty"],
                marker_color="#00ff88",
                text=summary_person["actual_qty"].apply(lambda x: f"{x:,.0f}"),
                textposition="outside"
            ))
            fig_person.update_layout(
                height=COMPONENT_HEIGHT, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#ffffff"), margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_person, use_container_width=True)
            
# --- TAB 04: PENCAPAIAN PERNIK PER PERSONIL ---
elif selected_tab == "04 Pencapaian Pernik":
    st.title("🏆 Pencapaian Pernik Per Personil")

    person_list = (
        st.session_state.person_df["person_name"].dropna().unique().tolist()
        if "person_df" in st.session_state
        and not st.session_state.person_df.empty
        else []
    )
    if not person_list and "sales_person_df" in st.session_state:
        person_list = (
            st.session_state.sales_person_df["person_name"]
            .dropna()
            .unique()
            .tolist()
        )

    c_p1, _ = st.columns([1.5, 1])
    with c_p1:
        selected_person = st.selectbox(
            "👤 PILIH PERSONIL TOKO",
            person_list if person_list else ["Belum Ada Data"],
            key="tab4_person_select",
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

    target_col = (
        "target_kasir" if "target_kasir" in si_df.columns else "target_qty"
    )
    si_df[target_col] = pd.to_numeric(si_df[target_col], errors="coerce").fillna(
        0
    )

    sp_grouped = (
        sp_df.groupby(["item_id", "item_name"])["actual_qty"].sum().reset_index()
        if not sp_df.empty
        else pd.DataFrame(columns=["item_id", "item_name", "actual_qty"])
    )
    si_grouped = (
        si_df.groupby(["item_id", "item_name"])[target_col].sum().reset_index()
        if not si_df.empty
        else pd.DataFrame(columns=["item_id", "item_name", target_col])
    )

    # Konversi ID ke string agar merging konsisten
    si_grouped["item_id"] = si_grouped["item_id"].astype(str)
    sp_grouped["item_id"] = sp_grouped["item_id"].astype(str)

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

    # === KOLOM KIRI: TABEL ===
    with col_t4_left:
        st.subheader("📋 Rincian Target Item Pernik")
        table_rows_html = ""
        for _, row in merged_item_df.iterrows():
            gap_color = "#00ff88" if row["gap"] <= 0 else "#ef4444"
            ach_color = "#00ff88" if row["ach"] >= 100 else "#ffb703"
            table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 10px; color: #ffffff; font-weight: bold;">{row['item_name']}</td>
                <td style="padding: 10px; color: #94a3b8;">{row['target_val']:,.0f}</td>
                <td style="padding: 10px; color: #00ff88; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 10px; color: {gap_color};">{row['gap']:,.0f}</td>
                <td style="padding: 10px; color: {ach_color}; font-weight: bold;">{row['ach']:.1f}%</td>
            </tr>
            """

        # PERBAIKAN: st.markdown() dimasukkan ke dalam with col_t4_left
        # dan ditambahkan tag penutup </tbody></table>
        table_full_html = textwrap.dedent(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; max-height: 380px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #334155;">
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">NAMA ITEM</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">TARGET KASIR</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">ACTUAL</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">GAP</th>
                            <th style="padding: 8px; color: #38bdf8; font-size: 11px;">% ACH</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
            </div>
        """)
        st.markdown(table_full_html, unsafe_allow_html=True)

    # === KOLOM KANAN: GRAFIK ===
    with col_t4_right:
        st.subheader("📊 Visual Breakdown Item")
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
                marker_color="#64748b",
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

# --- TAB 07: MASTER DATA & PENGATURAN ---
elif selected_tab == "07 Master Data & Pengaturan":
    current_user = st.session_state.get("username", "visitor")
    raw_role = st.session_state.get("user_role", st.session_state.get("role", "visitor"))

    user_role = str(raw_role).lower()
    user_lower = str(current_user).lower()

    is_admin = "admin" in user_role or "admin" in user_lower
    is_visitor = (not is_admin) and ("visitor" in user_role or "visitor" in user_lower)

    if is_visitor:
        st.error("🔒 **Akses Ditolak!** Pengguna dengan status **Visitor** tidak diizinkan masuk ke menu Master Data & Pengaturan.")
        st.stop()

    st.markdown("<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>⚙️ Panel Master Data & Pengaturan Sistem</h2>", unsafe_allow_html=True)

    person_df = st.session_state.get("person_df", pd.DataFrame())
    items_df = st.session_state.get("items_df", pd.DataFrame())
    periods_df = st.session_state.get("periods_df", pd.DataFrame())
    si_df = st.session_state.get("sales_item_df", pd.DataFrame())

    if is_admin:
        m_tab1, m_tab2, m_tab3, m_tab4 = st.tabs([
            "👥 Master Personil & Role",
            "📦 Master Item & Target",
            "🗓️ Master Periode",
            "⚙️ Pengaturan & Pemeliharaan System"
        ])
    else:
        st.info(f"👤 Anda login sebagai **{current_user}** ({user_role.title()}). Anda hanya diizinkan mengelola profil & password akun milik Anda sendiri.")
        m_tab1, = st.tabs(["👤 Profil & Password Saya"])

    # SUBTAB 1: MASTER PERSONIL
    with m_tab1:
        st.markdown("<h4 style='color: #00ff88;'>👥 Kelola Profil, Username, & Password</h4>", unsafe_allow_html=True)

        if "personil_success_msg" in st.session_state and st.session_state.personil_success_msg:
            st.success(st.session_state.personil_success_msg)
            st.toast(st.session_state.personil_success_msg, icon="✅")
            del st.session_state["personil_success_msg"]

        if is_admin:
            aksi_personil = st.radio("Pilih Tindakan:", ["✏️ Edit User Terdaftar", "➕ Buat Username Baru"], horizontal=True, key="p_action")
        else:
            aksi_personil = "✏️ Edit User Terdaftar"

        if aksi_personil == "✏️ Edit User Terdaftar":
            if not person_df.empty and "username" in person_df.columns:
                user_list = person_df["username"].dropna().unique().tolist()

                if is_admin:
                    selected_user = st.selectbox("Pilih Akun User yang Ingin Diubah", user_list, key="sel_user_edit")
                else:
                    selected_user = current_user
                    st.info(f"👤 Pengeditan dikunci untuk akun Anda: **{current_user}**")

                if selected_user in user_list:
                    user_row = person_df[person_df["username"] == selected_user].iloc[0]
                    with st.form("form_edit_personil"):
                        col_p1, col_p2 = st.columns(2)
                        with col_p1:
                            edit_nik = st.text_input("NIK", value=str(user_row.get("nik", "")))
                            edit_nama = st.text_input("Nama Lengkap", value=str(user_row.get("person_name", selected_user)))
                            edit_username = st.text_input("Username", value=str(user_row.get("username", selected_user)), disabled=not is_admin)
                        with col_p2:
                            edit_password = st.text_input("Password Baru", value=str(user_row.get("password", "")))
                            roles_options = ["Admin", "Staff Toko", "Kasir Toko"]
                            curr_role = str(user_row.get("role", "Staff Toko"))
                            role_idx = roles_options.index(curr_role) if curr_role in roles_options else 1
                            edit_role = st.selectbox("Role Akun", roles_options, index=role_idx, disabled=not is_admin)

                        btn_simpan_p = st.form_submit_button("💾 Simpan Perubahan Profil & Password", use_container_width=True)

                        if btn_simpan_p:
                            st.session_state.person_df = st.session_state.person_df.astype(str)
                            mask = st.session_state.person_df["username"] == selected_user

                            st.session_state.person_df.loc[mask, "nik"] = str(edit_nik)
                            st.session_state.person_df.loc[mask, "person_name"] = str(edit_nama)
                            st.session_state.person_df.loc[mask, "username"] = str(edit_username).strip()
                            st.session_state.person_df.loc[mask, "password"] = str(edit_password).strip()
                            st.session_state.person_df.loc[mask, "role"] = str(edit_role)

                            save_master_table("MASTER_PERSONIL", st.session_state.person_df)
                            st.cache_data.clear()
                            st.session_state["personil_success_msg"] = f"✅ Perubahan akun '{edit_username.strip()}' berhasil disimpan permanen!"
                            st.rerun()

        elif aksi_personil == "➕ Buat Username Baru" and is_admin:
            with st.form("form_add_personil"):
                col_n1, col_n2 = st.columns(2)
                with col_n1:
                    new_nik = st.text_input("NIK")
                    new_nama = st.text_input("Nama Lengkap")
                    new_user = st.text_input("Username Baru (Tanpa Spasi)")
                with col_n2:
                    new_pass = st.text_input("Password")
                    new_role = st.selectbox("Role Akun", ["Admin", "Staff Toko", "Kasir Toko"])

                btn_create_p = st.form_submit_button("➕ Tambahkan User Baru", use_container_width=True)

                if btn_create_p:
                    clean_username = new_user.strip()
                    clean_password = new_pass.strip()

                    if not clean_username or not clean_password:
                        st.error("⚠️ Username dan Password wajib diisi!")
                    else:
                        existing_users = person_df["username"].dropna().astype(str).str.lower().tolist() if not person_df.empty else []
                        if clean_username.lower() in existing_users:
                            st.error(f"⚠️ Username **'{clean_username}'** sudah terdaftar! Gunakan username lain.")
                        else:
                            new_p_id = f"P{len(st.session_state.person_df) + 1:03d}"
                            new_person_row = {
                                "person_id": new_p_id,
                                "person_name": new_nama if new_nama else clean_username,
                                "username": clean_username,
                                "password": clean_password,
                                "nik": new_nik,
                                "role": new_role,
                                "last_login": "-",
                                "last_logout": "-"
                            }
                            st.session_state.person_df = pd.concat([st.session_state.person_df, pd.DataFrame([new_person_row])], ignore_index=True)
                            save_master_table("MASTER_PERSONIL", st.session_state.person_df)
                            st.cache_data.clear()
                            st.session_state["personil_success_msg"] = f"🎉 Username baru '{clean_username}' berhasil dibuat dan siap digunakan!"
                            st.rerun()

    # SUBTAB 2: MASTER ITEM & TARGET
    if is_admin:
        with m_tab2:
            st.markdown("<h4 style='color: #00ff88;'>📦 Kelola Master Produk & Target Sales</h4>", unsafe_allow_html=True)
            sub_m2 = st.radio("Pilih Fitur Item:", ["➕ Tambah / Edit Produk", "🎯 Set Target Toko & Kasir Per Periode"], horizontal=True)

            if sub_m2 == "➕ Tambah / Edit Produk":
                if not items_df.empty:
                    st.dataframe(items_df, use_container_width=True)

                with st.form("form_item_master"):
                    col_i1, col_i2 = st.columns(2)
                    with col_i1:
                        item_id_in = st.text_input("ID Produk (Contoh: ITM001)")
                        item_name_in = st.text_input("Nama Produk")
                    with col_i2:
                        item_cat_in = st.text_input("Kategori Produk")

                    btn_save_item = st.form_submit_button("💾 Simpan Produk ke Master")

                    if btn_save_item:
                        new_item = {"item_id": str(item_id_in), "item_name": item_name_in, "category": item_cat_in}
                        st.session_state.items_df = pd.concat([st.session_state.items_df, pd.DataFrame([new_item])], ignore_index=True)
                        save_master_table("MASTER_ITEM", st.session_state.items_df)
                        st.success("✅ Produk baru berhasil ditambahkan!")
                        time.sleep(1.5)
                        st.rerun()

            elif sub_m2 == "🎯 Set Target Toko & Kasir Per Periode":
                st.info("ℹ️ Target yang dibuat akan langsung ditambahkan ke Google Sheets tanpa merubah rekap target periode terdahulu.")
                if not periods_df.empty and "period_name" in periods_df.columns:
                    p_opt = {row["period_name"]: str(row["period_id"]) for _, row in periods_df.iterrows()}
                    selected_p_name = st.selectbox("Pilih Periode Target", list(p_opt.keys()), key="target_p_sel")
                    target_p_id = str(p_opt[selected_p_name])

                    if not items_df.empty and "item_name" in items_df.columns:
                        selected_item_target = st.selectbox("Pilih Produk", items_df["item_name"].unique(), key="target_i_sel")
                        item_id_target = str(items_df[items_df["item_name"] == selected_item_target].iloc[0]["item_id"])

                        with st.form("form_target_period"):
                            col_t1, col_t2 = st.columns(2)
                            with col_t1: target_toko_val = st.number_input("Target Penjualan Toko (Qty Pcs)", min_value=0, step=1)
                            with col_t2: target_kasir_val = st.number_input("Target Penjualan Kasir (Qty Pcs)", min_value=0, step=1)

                            btn_save_target = st.form_submit_button("💾 Simpan / Update Target Ke Google Sheets")

                            if btn_save_target:
                                mask = (st.session_state.sales_item_df["period_id"].astype(str) == target_p_id) & (st.session_state.sales_item_df["item_id"].astype(str) == item_id_target)

                                if mask.any():
                                    st.session_state.sales_item_df.loc[mask, "target_qty"] = target_toko_val
                                    st.session_state.sales_item_df.loc[mask, "target_kasir"] = target_kasir_val
                                else:
                                    new_target_row = {
                                        "period_id": target_p_id,
                                        "item_id": item_id_target,
                                        "item_name": selected_item_target,
                                        "target_qty": target_toko_val,
                                        "target_kasir": target_kasir_val,
                                        "actual_qty": 0
                                    }
                                    st.session_state.sales_item_df = pd.concat([st.session_state.sales_item_df, pd.DataFrame([new_target_row])], ignore_index=True)

                                save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                                st.toast("Target berhasil disimpan permanen!", icon="✅")
                                time.sleep(1.5)
                                st.rerun()

        # SUBTAB 3: MASTER PERIODE
        with m_tab3:
            st.markdown("<h4 style='color: #00ff88;'>🗓️ Kelola Periode Transaksi & Tutup Buku</h4>", unsafe_allow_html=True)
            if not periods_df.empty:
                st.dataframe(periods_df, use_container_width=True)

            with st.form("form_add_period"):
                st.markdown("##### ➕ Tambah / Update Periode Baru")
                col_per1, col_per2 = st.columns(2)
                with col_per1:
                    p_id_new = st.text_input("ID Periode (Contoh: P01, P02)")
                    p_name_new = st.text_input("Nama Periode (Contoh: Periode Maret 2026)")
                with col_per2:
                    p_start_new = st.date_input("Tanggal Mulai")
                    p_end_new = st.date_input("Tanggal Selesai")
                    p_status_new = st.selectbox("Status Periode", ["Aktif", "Tutup Buku"])

                btn_save_period = st.form_submit_button("💾 Simpan Periode")

                if btn_save_period:
                    mask_p = st.session_state.periods_df["period_id"].astype(str) == str(p_id_new)
                    if mask_p.any():
                        st.session_state.periods_df.loc[mask_p, "period_name"] = p_name_new
                        st.session_state.periods_df.loc[mask_p, "start_date"] = str(p_start_new)
                        st.session_state.periods_df.loc[mask_p, "end_date"] = str(p_end_new)
                        st.session_state.periods_df.loc[mask_p, "status"] = p_status_new
                    else:
                        new_p_data = {
                            "period_id": str(p_id_new),
                            "period_name": p_name_new,
                            "start_date": str(p_start_new),
                            "end_date": str(p_end_new),
                            "status": p_status_new
                        }
                        st.session_state.periods_df = pd.concat([st.session_state.periods_df, pd.DataFrame([new_p_data])], ignore_index=True)

                    save_master_table("PERIODE", st.session_state.periods_df)
                    st.toast("Master Periode berhasil diperbarui!", icon="🗓️")
                    time.sleep(1.5)
                    st.rerun()

        # SUBTAB 4: PEMELIHARAAN SYSTEM
        with m_tab4:
            st.markdown("<h4 style='color: #00ff88;'>⚙️ Pemeliharaan System & Status Akses</h4>", unsafe_allow_html=True)
            col_sys1, col_sys2 = st.columns(2)
            with col_sys1:
                st.markdown("##### Refresh Cache App")
                if st.button("🔄 Force Refresh Cache Streamlit", use_container_width=True):
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.toast("Cache aplikasi berhasil dibersihkan!", icon="⚡")
                    time.sleep(1)
                    st.rerun()

            with col_sys2:
                st.markdown("##### Status Koneksi Google Sheets")
                try:
                    test_read = conn.read(worksheet="PERIODE", ttl=0)
                    st.success("🟢 Terhubung Lancar dengan Google Sheets Cloud")
                except Exception as ex:
                    st.error(f"🔴 Koneksi Terputus / Error: {ex}")

            st.markdown("---")
            st.markdown("##### Export Backup Data System")
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                if not si_df.empty:
                    st.download_button("📥 Download Backup Sales Item (CSV)", si_df.to_csv(index=False), file_name="backup_sales_item.csv", mime="text/csv", use_container_width=True)
            with col_exp2:
                if not st.session_state.sales_person_df.empty:
                    st.download_button("📥 Download Backup Sales Personil (CSV)", st.session_state.sales_person_df.to_csv(index=False), file_name="backup_sales_personil.csv", mime="text/csv", use_container_width=True)

            st.markdown("---")
            st.markdown("##### Live Activity Log (History Login & Logout User)")
            st.caption("Menampilkan timestamp aktivitas login & logout terbaru dari masing-masing akun terdaftar.")
            if not person_df.empty:
                disp_cols = [c for c in ["username", "person_name", "role", "last_login", "last_logout"] if c in person_df.columns]
                st.dataframe(person_df[disp_cols], use_container_width=True)


