import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="PSM Toko - Sales Dashboard", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# ID SPREADSHEET GOOGLE SHEETS ANDA
# ==========================================
SPREADSHEET_ID = "1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk"

def load_database():
    """
    Membaca data realtime secara langsung dari Google Sheets via GViz CSV Endpoint.
    Bebas error 400 Bad Request & tidak membutuhkan Service Account untuk membaca data.
    """
    try:
        def read_sheet(sheet_name):
            # Endpoint publik CSV resmi dari Google
            url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
            df = pd.read_csv(url)
            if not df.empty:
                # Otomatis rapikan nama kolom (huruf kecil & hapus spasi)
                df.columns = df.columns.astype(str).str.strip().str.lower()
            return df

        periods_df = read_sheet("PERIODE")
        items_df = read_sheet("MASTER_ITEM")
        person_df = read_sheet("MASTER_PERSONIL")
        sales_item_df = read_sheet("SALES_ITEM")
        sales_person_df = read_sheet("SALES_PERSONIL")

        return periods_df, items_df, person_df, sales_item_df, sales_person_df
    except Exception as e:
        st.error(f"⚠️ Gagal membaca Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def save_database(sales_item_df, sales_person_df):
    """Menyimpan data transaksi harian ke Google Sheets secara permanen."""
    try:
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="SALES_ITEM", data=sales_item_df)
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="SALES_PERSONIL", data=sales_person_df)
        st.toast("✅ Perubahan transaksi tersimpan permanen di Google Sheets!", icon="💾")
    except Exception as e:
        st.error(f"❌ Gagal menyimpan transaksi ke Google Sheets: {e}")

def save_master_table(sheet_name, df_data):
    """Menyimpan perubahan master data (Personil/Item/Periode) ke Google Sheets."""
    try:
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=sheet_name, data=df_data)
        st.toast(f"✅ Master {sheet_name} berhasil diperbarui di Google Sheets!", icon="💾")
    except Exception as e:
        st.error(f"❌ Gagal update master {sheet_name}: {e}")

def sync_store_sales_from_personnel():
    """
    Merekap total penjualan seluruh personil toko dan memperbarui 
    actual_qty pada Penjualan Toko (sales_item_df).
    """
    if "sales_person_df" in st.session_state and "sales_item_df" in st.session_state:
        sp_df = st.session_state.sales_person_df.copy()
        si_df = st.session_state.sales_item_df.copy()
        
        req_cols_sp = ["period_id", "item_id", "actual_qty"]
        req_cols_si = ["period_id", "item_id"]
        
        if sp_df.empty or not all(col in sp_df.columns for col in req_cols_sp):
            return
        if si_df.empty or not all(col in si_df.columns for col in req_cols_si):
            return
            
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
    "visitor": {"password": "visitor", "nama": "Pengunjung"}
}

# ==========================================
# 5. CUSTOM CSS (NEON DARK THEME)
# ==========================================
st.markdown("""
<style>
    /* Latar Belakang Utama Aplikasi */
    .stApp {
        background-color: #0b0f19;
        color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    /* Styling Teks Input & Label */
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
        background-color: #0d1117 !important;
        border: 1.5px solid #00f0ff !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="input"] svg {
        fill: #00f0ff !important;
    }

    /* Metric Cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #38bdf8;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        text-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
        font-weight: 800;
        font-size: 26px;
    }
    
    /* Sidebar Layout */
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: 600;
    }
    div[data-testid="stRadio"] input[type="radio"],
    div[data-testid="stRadio"] div[role="radiogroup"] div:has(> input[type="radio"]) {
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
        transform: translateY(-1px);
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
    div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: 1px solid #38bdf8 !important;
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.6) !important;
        color: #ffffff !important;
    }

    /* Tombol Utama */
    div.stButton > button, div.stFormSubmitButton > button {
        background-color: #080c14 !important;
        color: #ffffff !important;
        border: 2px solid #00f0ff !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        box-shadow: 0 0 10px rgba(0, 240, 255, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background-color: #00f0ff !important;
        color: #080c14 !important;
        box-shadow: 0 0 20px rgba(0, 240, 255, 0.8) !important;
    }

    /* Tombol Logout Sidebar */
    [data-testid="stSidebar"] div[data-testid="stButton"] > button {
        background-color: #0f172a !important;
        color: #ef4444 !important;
        border: 1px solid #ef4444 !important;
    }
    [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background-color: #ef4444 !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)

# Inisialisasi Session State Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# ==========================================
# 6. HALAMAN LOGIN
# ==========================================
def show_login_page():
    LOGO_URL = "https://github.com/stefanusagranus-tech/LigaPSM26/blob/main/kgs_group_belgium_logo.jpg?raw=true"
    
    st.markdown("""
        <style>
            .login-card {
                background-color: #1e293b;
                padding: 35px 30px;
                border-radius: 16px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
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
                margin-bottom: 15px;
                display: block;
                margin-left: auto;
                margin-right: auto;
            }
            .login-subtitle {
                color: #38bdf8;
                font-size: 13px;
                margin-bottom: 0px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    _, col2, _ = st.columns([1, 1.4, 1])
    
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
                    st.warning("Username dan Password wajib diisi!")
                elif username_input in USER_DATABASE and USER_DATABASE[username_input]["password"] == password_input:
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

# ==========================================
# 7. LOAD DATA DARI GOOGLE SHEETS LIVE
# ==========================================
if "data_loaded" not in st.session_state:
    p_df, i_df, pers_df, si_df, sp_df = load_database()
    st.session_state.periods_df = p_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.data_loaded = True

# ==========================================
# 8. SIDEBAR DASHBOARD
# ==========================================
st.sidebar.markdown("""
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

st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>📌 NAVIGASI MENU</p>", unsafe_allow_html=True)
menu_options = [
    "01 · Overview", 
    "02 · Detail Item", 
    "03 · Penjualan Personil", 
    "04 · Pencapaian Pernik", 
    "05 · Analisis Tren",
    "06 · Input & Reset Data",
    "⚙️ Master Data & Pengaturan"
]
selected_tab = st.sidebar.radio("", menu_options, label_visibility="collapsed")
st.sidebar.markdown("---")

st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>🌟 FILTER PERIODE</p>", unsafe_allow_html=True)
periods_dict = {row["period_name"]: row["period_id"] for _, row in st.session_state.periods_df.iterrows()}
selected_period_name = st.sidebar.selectbox("", ["Semua Periode (Overall)"] + list(periods_dict.keys()), label_visibility="collapsed")
selected_period_id = None if selected_period_name == "Semua Periode (Overall)" else periods_dict[selected_period_name]

st.sidebar.markdown("<hr style='margin: 15px 0; border-color: #334155;'>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Keluar / Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# ==========================================
# 9. HEADER UTAMA
# ==========================================
st.markdown(f"""
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
""", unsafe_allow_html=True)

# ==========================================
# 10. MODUL TAB / SUB MENU
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

        # --- Kode perhitungan hari (biarkan tetap seperti ini) ---
    total_days = max((end_date - start_date).days + 1, 1)
    today_date = waktu_wib.date()
    if today_date < start_date:
        passed_days = 0
    elif today_date > end_date:
        passed_days = total_days
    else:
        passed_days = max((today_date - start_date).days + 1, 1)

    # Menghitung Persentase Time Factor
    time_factor = (passed_days / total_days) * 100 if total_days > 0 else 0

    # 🛠️ KODE PENGAMAN TAMBAHAN (Disisipkan di sini):
    if "target_qty" not in sub_si.columns:
        sub_si["target_qty"] = 0

    sub_si["target_qty"] = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0)
    
    if "actual_qty" in filtered_sp.columns:
        filtered_sp["actual_qty"] = pd.to_numeric(filtered_sp["actual_qty"], errors="coerce").fillna(0)
    else:
        filtered_sp["actual_qty"] = 0

    time_factor = (passed_days / total_days) * 100 if total_days > 0 else 0
    sub_si["target_qty"] = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0)
    filtered_sp["actual_qty"] = pd.to_numeric(filtered_sp["actual_qty"], errors="coerce").fillna(0)

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
        st.metric("⏳ Time Factor (Waktu)", f"{time_factor:.1f}%", help=f"Hari berjalan: {passed_days}/{total_days} hari")

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

    st.subheader("📋 Ringkasan Penjualan Per Item Produk")
    item_sp = filtered_sp.groupby(["item_id", "item_name"])["actual_qty"].sum().reset_index() if not filtered_sp.empty else pd.DataFrame(columns=["item_id", "item_name", "actual_qty"])
    overview_table = pd.merge(sub_si[["item_id", "item_name", "target_qty"]], item_sp[["item_id", "actual_qty"]], on="item_id", how="left")
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
                </tbody>
            </table>
        </div>
    """, unsafe_allow_html=True)

# --- TAB 02: DETAIL ITEM ---
elif selected_tab == "02 · Detail Item":
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
                </div>
            """, unsafe_allow_html=True)
        with r_col2:
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #ef4444; font-size: 11px; font-weight: bold;">📉 ITEM TERENDAH</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{low_item['item_name']}</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{low_item['actual_qty']:,.0f} Pcs</div>
                </div>
            """, unsafe_allow_html=True)
        with r_col3:
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #38bdf8; font-size: 11px; font-weight: bold;">📦 VARIASI ITEM</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800;">{len(item_grouped)} Jenis</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{item_grouped['actual_qty'].sum():,.0f} Pcs Total</div>
                </div>
            """, unsafe_allow_html=True)

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
elif selected_tab == "03 · Penjualan Personil":
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
elif selected_tab == "04 · Pencapaian Pernik":
    st.title("🏆 Pencapaian Pernik Per Personil")
    
    person_list = st.session_state.person_df["person_name"].dropna().unique().tolist()
    if not person_list:
        person_list = st.session_state.sales_person_df["person_name"].dropna().unique().tolist()

    c_p1, _ = st.columns([1.5, 1])
    with c_p1:
        selected_person = st.selectbox("👤 PILIH PERSONIL TOKO", person_list, key="tab4_person_select")

    sp_df = st.session_state.sales_person_df.copy()
    si_df = st.session_state.sales_item_df.copy()

    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
        si_df = si_df[si_df["period_id"] == selected_period_id]

    sp_df = sp_df[sp_df["person_name"] == selected_person]
    sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)

    target_col = "target_kasir" if "target_kasir" in si_df.columns else "target_qty"
    si_df[target_col] = pd.to_numeric(si_df[target_col], errors="coerce").fillna(0)

    sp_grouped = sp_df.groupby(["item_id", "item_name"])["actual_qty"].sum().reset_index()
    si_grouped = si_df.groupby(["item_id", "item_name"])[target_col].sum().reset_index()

    merged_item_df = pd.merge(si_grouped, sp_grouped[["item_id", "actual_qty"]], on="item_id", how="left")
    merged_item_df["actual_qty"] = merged_item_df["actual_qty"].fillna(0)
    merged_item_df.rename(columns={target_col: "target_val"}, inplace=True)

    merged_item_df["gap"] = merged_item_df["target_val"] - merged_item_df["actual_qty"]
    merged_item_df["ach"] = merged_item_df.apply(lambda r: (r["actual_qty"] / r["target_val"] * 100) if r["target_val"] > 0 else 0, axis=1)

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
            gap_color = "#00ff88" if row['gap'] <= 0 else "#ef4444"
            ach_color = "#00ff88" if row['ach'] >= 100 else "#ffb703"
            table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 10px; color: #ffffff; font-weight: bold;">{row['item_name']}</td>
                <td style="padding: 10px; color: #94a3b8;">{row['target_val']:,.0f}</td>
                <td style="padding: 10px; color: #00ff88; font-weight: bold;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 10px; color: {gap_color};">{row['gap']:,.0f}</td>
                <td style="padding: 10px; color: {ach_color}; font-weight: bold;">{row['ach']:.1f}%</td>
            </tr>
            """
        st.markdown(f"""
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
        """, unsafe_allow_html=True)

    with col_t4_right:
        st.subheader("📊 Visual Breakdown Item")
        fig_p4 = go.Figure()
        fig_p4.add_trace(go.Bar(y=merged_item_df["item_name"], x=merged_item_df["actual_qty"], name="Actual", orientation='h', marker_color="#00f2fe"))
        fig_p4.add_trace(go.Bar(y=merged_item_df["item_name"], x=merged_item_df["target_val"], name="Target Kasir", orientation='h', marker_color="#64748b"))
        fig_p4.update_layout(barmode='group', height=380, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#ffffff"), margin=dict(l=10, r=10, t=10, b=10))
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

    if today_date < start_date:
        passed_days = 1
    elif today_date > end_date:
        passed_days = total_range_days
    else:
        passed_days = max((today_date - start_date).days + 1, 1)

    remaining_days = max(total_range_days - passed_days, 1)
    daily_target_ideal = max(0, int((tot_target - tot_actual) / remaining_days)) if remaining_days > 0 else 0
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
    merged_item_analysis = pd.merge(sub_si[["item_id", "item_name", "target_qty"]], item_sales[["item_id", "actual_qty"]], on="item_id", how="left")
    merged_item_analysis["actual_qty"] = merged_item_analysis["actual_qty"].fillna(0)
    merged_item_analysis["gap"] = merged_item_analysis["target_qty"] - merged_item_analysis["actual_qty"]
    merged_item_analysis["ach"] = merged_item_analysis.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)

    col_g, col_d = st.columns(2)
    top_growth = merged_item_analysis.sort_values(by="actual_qty", ascending=False).head(3)
    top_disgrowth = merged_item_analysis.sort_values(by="gap", ascending=False).head(3)

    with col_g:
        st.markdown('<div style="background: #080c14; border: 1.5px solid #00ff9d; border-left: 6px solid #00ff9d; border-radius: 10px; padding: 16px; margin-bottom: 12px;"><h4 style="color: #00ff9d; margin: 0;">🔥 TOP 3 ITEM GROWTH</h4></div>', unsafe_allow_html=True)
        for _, r in top_growth.iterrows():
            st.success(f"**{r['item_name']}** — Terjual: **{r['actual_qty']:,.0f} Pcs** (Ach: **{r['ach']:.1f}%**)")

    with col_d:
        st.markdown('<div style="background: #080c14; border: 1.5px solid #ff2a6d; border-left: 6px solid #ff2a6d; border-radius: 10px; padding: 16px; margin-bottom: 12px;"><h4 style="color: #ff2a6d; margin: 0;">⚠️ TOP 3 ITEM DISGROWTH</h4></div>', unsafe_allow_html=True)
        for _, r in top_disgrowth.iterrows():
            st.error(f"**{r['item_name']}** — Sisa Gap: **{max(0, r['gap']):,.0f} Pcs** (Ach: **{r['ach']:.1f}%**)")

# --- TAB 06: INPUT & RESET DATA ---
elif selected_tab == "06 · Input & Reset Data":
    st.title("✏️ Kelola & Input Data Penjualan")
    
    current_user = st.session_state.get("username", "")
    is_admin = (str(current_user).lower() == "admin")
    
    periods_df = st.session_state.periods_df.copy()
    si_df = st.session_state.sales_item_df.copy()
    sp_df = st.session_state.sales_person_df.copy()
    person_df = st.session_state.person_df.copy()

    # ---------------------------------------------------------
    # PEMBAGIAN 4 SUB MENU BARU
    # ---------------------------------------------------------
    tab_in1, tab_in2, tab_in3, tab_in4 = st.tabs([
        "➕ Input Sales Personil",
        "✏️ Edit Sales Personil",
        "🗑️ Hapus & Reset Sales",
        "⚡ Multi Input Sales"
    ])

    # Helper function untuk mendapatkan batasan tanggal periode
    def get_period_date_bounds(p_id):
        p_match = periods_df[periods_df["period_id"] == p_id]
        if not p_match.empty and "start_date" in p_match.columns and "end_date" in p_match.columns:
            try:
                p_start = pd.to_datetime(p_match.iloc[0]["start_date"]).date()
                p_end = pd.to_datetime(p_match.iloc[0]["end_date"]).date()
                return p_start, p_end
            except:
                pass
        return waktu_wib.date().replace(day=1), waktu_wib.date()

    # =========================================================
    # SUB MENU 1: INPUT SALES PERSONIL (SINGLE ITEM)
    # =========================================================
    with tab_in1:
        st.subheader("➕ Input Penjualan Personil (Satuan)")
        
        f_period_name = st.selectbox("Pilih Periode Transaksi", list(periods_dict.keys()), key="in1_period")
        p_id_val = periods_dict[f_period_name]
        
        # Req 1: Tanggal terkunci sesuai rentang periode
        p_start, p_end = get_period_date_bounds(p_id_val)
        default_val = min(max(waktu_wib.date(), p_start), p_end)
        
        f_date = st.date_input(
            f"Tanggal Transaksi (Batas Periode: {p_start.strftime('%d/%m/%Y')} s/d {p_end.strftime('%d/%m/%Y')})",
            value=default_val,
            min_value=p_start,
            max_value=p_end,
            key="in1_date"
        )

        # Req 8: Admin bebas pilih staf, user toko terkunci ke username-nya
        all_personnel = person_df["person_name"].dropna().unique().tolist() if not person_df.empty else []
        if is_admin:
            f_person = st.selectbox("Nama Staf / Personil", all_personnel, key="in1_person")
        else:
            f_person = current_user
            st.info(f"👤 Penginputan dikunci untuk akun: **{current_user}**")

        filtered_si = si_df[si_df["period_id"] == p_id_val]
        item_dict = {row["item_name"]: row["item_id"] for _, row in filtered_si.iterrows()} if not filtered_si.empty else {}

        if item_dict:
            f_item_name = st.selectbox("Pilih Produk", list(item_dict.keys()), key="in1_item")
            f_qty = st.number_input("Jumlah Penjualan Qty (Pcs)", min_value=0, step=1, value=0, key="in1_qty")

            if st.button("💾 Simpan Data Personil", use_container_width=True, key="btn_save_in1"):
                if f_qty <= 0:
                    st.warning("⚠️ Qty penjualan harus lebih dari 0!")
                else:
                    new_id = f"SP{len(st.session_state.sales_person_df) + 1:05d}"
                    p_match = person_df[person_df["person_name"] == f_person]
                    person_id_val = p_match.iloc[0]["person_id"] if not p_match.empty and "person_id" in p_match.columns else "P999"

                    new_row = {
                        "record_id": new_id,
                        "period_id": p_id_val,
                        "item_id": item_dict[f_item_name],
                        "item_name": f_item_name,
                        "person_id": person_id_val,
                        "person_name": f_person,
                        "actual_qty": f_qty,
                        "updated_at": str(f_date)
                    }

                    # Req 5: Langsung tambahkan, sinkronkan ke total toko, dan simpan permanen ke Google Sheets
                    st.session_state.sales_person_df = pd.concat([st.session_state.sales_person_df, pd.DataFrame([new_row])], ignore_index=True)
                    sync_store_sales_from_personnel()
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.success(f"✅ Penjualan {f_item_name} ({f_qty} Pcs) tersimpan & tersinkron permanen!")
                    st.rerun()
        else:
            st.warning("Tidak ada item produk tersedia di periode ini.")

    # =========================================================
    # SUB MENU 2: EDIT SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in2:
        st.subheader("✏️ Edit Transaksi Sales (Koreksi Input)")
        
        # Req 4 & 8: Khusus Admin
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur edit transaksi ini hanya dapat diakses oleh Admin.")
        else:
            e_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="edit_period")
            e_p_id = periods_dict[e_period_name]
            p_start, p_end = get_period_date_bounds(e_p_id)

            # Filter data transaksi yang ada
            sp_sub = sp_df[sp_df["period_id"] == e_p_id].copy()
            
            if sp_sub.empty:
                st.info("Belum ada data transaksi di periode ini untuk diedit.")
            else:
                e_person = st.selectbox("Pilih Personil", sp_sub["person_name"].unique(), key="edit_person")
                sp_person_sub = sp_sub[sp_sub["person_name"] == e_person]

                if sp_person_sub.empty:
                    st.info("Tidak ada transaksi untuk personil ini.")
                else:
                    # Pilih baris transaksi yang ingin diedit
                    sp_person_sub["label_trx"] = sp_person_sub.apply(
                        lambda r: f"[{r.get('updated_at', '-')}] {r['item_name']} - {r['actual_qty']} Pcs", axis=1
                    )
                    selected_label = st.selectbox("Pilih Transaksi yang Akan Diedit", sp_person_sub["label_trx"].tolist(), key="edit_trx_select")
                    
                    selected_row = sp_person_sub[sp_person_sub["label_trx"] == selected_label].iloc[0]
                    
                    st.markdown("---")
                    st.markdown("##### Form Perubahan Data")
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        new_e_date = st.date_input(
                            "Ubah Tanggal Transaksi",
                            value=pd.to_datetime(selected_row.get("updated_at", p_start)).date(),
                            min_value=p_start,
                            max_value=p_end,
                            key="edit_date_val"
                        )
                    with col_e2:
                        new_e_qty = st.number_input(
                            "Ubah Jumlah Qty (Pcs)",
                            min_value=0,
                            step=1,
                            value=int(selected_row["actual_qty"]),
                            key="edit_qty_val"
                        )

                    if st.button("💾 Simpan Perubahan Edit", use_container_width=True, key="btn_save_edit"):
                        idx = selected_row.name
                        st.session_state.sales_person_df.loc[idx, "actual_qty"] = new_e_qty
                        st.session_state.sales_person_df.loc[idx, "updated_at"] = str(new_e_date)
                        
                        # Sync total & simpan ke GS
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.success("✅ Perubahan transaksi berhasil disimpan permanen!")
                        st.rerun()

    # =========================================================
    # SUB MENU 3: HAPUS & RESET SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in3:
        st.subheader("🗑️ Hapus Transaksi / Reset Sales Personil")
        
        # Req 2 & 8: Khusus Admin
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur hapus/reset transaksi hanya dapat dilakukan oleh Admin.")
        else:
            d_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="del_period")
            d_p_id = periods_dict[d_period_name]
            
            sp_del_sub = sp_df[sp_df["period_id"] == d_p_id].copy()

            if sp_del_sub.empty:
                st.info("Tidak ada transaksi untuk dihapus pada periode ini.")
            else:
                d_person = st.selectbox("Pilih Personil", sp_del_sub["person_name"].unique(), key="del_person")
                sp_del_person = sp_del_sub[sp_del_sub["person_name"] == d_person]

                # Req 2: Pilih Hapus Item Tertentu ATAU Reset Seluruh Transaksi Staf
                mode_hapus = st.radio("Pilih Opsi Penghapusan:", ["Hapus Item Tertentu Saja", "Reset Seluruh Penjualan Personil Ini"], key="del_mode")

                if mode_hapus == "Hapus Item Tertentu Saja":
                    d_item_name = st.selectbox("Pilih Produk yang Ingin Dihapus", sp_del_person["item_name"].unique(), key="del_item_select")
                    
                    if st.button(f"🗑️ Hapus Transaksi Produk '{d_item_name}'", use_container_width=True, key="btn_del_single"):
                        # Req 2 & 3: Hanya hapus item spesifik pada personil & periode tersebut
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~((st.session_state.sales_person_df["period_id"] == d_p_id) & 
                              (st.session_state.sales_person_df["person_name"] == d_person) & 
                              (st.session_state.sales_person_df["item_name"] == d_item_name))
                        ]
                        
                        # Req 3: Langsung sinkron ke Google Sheets agar permanen
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.warning(f"⚠️ Transaksi '{d_item_name}' untuk {d_person} berhasil dihapus permanen!")
                        st.rerun()

                else:
                    st.error(f"⚠️ Perhatian: Aksi ini akan menghapus SELURUH catatan penjualan {d_person} pada periode ini.")
                    if st.button(f"🚨 Reset Total Sales {d_person} di Periode Ini", use_container_width=True, key="btn_reset_all"):
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~((st.session_state.sales_person_df["period_id"] == d_p_id) & 
                              (st.session_state.sales_person_df["person_name"] == d_person))
                        ]
                        
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
# --- TAB 06: INPUT & RESET DATA ---
elif selected_tab == "06 · Input & Reset Data":
    st.title("✏️ Kelola & Input Data Penjualan")
    
    current_user = st.session_state.get("username", "")
    is_admin = (str(current_user).lower() == "admin")
    
    periods_df = st.session_state.periods_df.copy()
    si_df = st.session_state.sales_item_df.copy()
    sp_df = st.session_state.sales_person_df.copy()
    person_df = st.session_state.person_df.copy()

    # ---------------------------------------------------------
    # PEMBAGIAN 4 SUB MENU
    # ---------------------------------------------------------
    tab_in1, tab_in2, tab_in3, tab_in4 = st.tabs([
        "➕ Input Sales Personil",
        "✏️ Edit Sales Personil",
        "🗑️ Hapus & Reset Sales",
        "⚡ Multi Input Sales"
    ])

    # 🛠️ Helper function aman untuk mengambil rentang tanggal periode
    def get_period_date_bounds(p_id):
        p_match = periods_df[periods_df["period_id"] == p_id]
        if not p_match.empty and "start_date" in p_match.columns and "end_date" in p_match.columns:
            try:
                p_start = pd.to_datetime(p_match.iloc[0]["start_date"]).date()
                p_end = pd.to_datetime(p_match.iloc[0]["end_date"]).date()
                if p_start > p_end:
                    p_start, p_end = p_end, p_start
                return p_start, p_end
            except Exception:
                pass
        today = waktu_wib.date()
        return today.replace(day=1), today

    # =========================================================
    # SUB MENU 1: INPUT SALES PERSONIL (SINGLE ITEM)
    # =========================================================
    with tab_in1:
        st.subheader("➕ Input Penjualan Personil (Satuan)")
        
        f_period_name = st.selectbox("Pilih Periode Transaksi", list(periods_dict.keys()), key="in1_period")
        p_id_val = periods_dict[f_period_name]
        
        # Tanggal terkunci sesuai rentang periode
        p_start, p_end = get_period_date_bounds(p_id_val)
        default_val = min(max(waktu_wib.date(), p_start), p_end)
        
        f_date = st.date_input(
            f"Tanggal Transaksi (Batas Periode: {p_start.strftime('%d/%m/%Y')} s/d {p_end.strftime('%d/%m/%Y')})",
            value=default_val,
            min_value=p_start,
            max_value=p_end,
            key="in1_date"
        )

        all_personnel = person_df["person_name"].dropna().unique().tolist() if not person_df.empty else []
        if is_admin:
            f_person = st.selectbox("Nama Staf / Personil", all_personnel, key="in1_person")
        else:
            f_person = current_user
            st.info(f"👤 Penginputan dikunci untuk akun: **{current_user}**")

        filtered_si = si_df[si_df["period_id"] == p_id_val]
        item_dict = {row["item_name"]: row["item_id"] for _, row in filtered_si.iterrows()} if not filtered_si.empty else {}

        if item_dict:
            f_item_name = st.selectbox("Pilih Produk", list(item_dict.keys()), key="in1_item")
            f_qty = st.number_input("Jumlah Penjualan Qty (Pcs)", min_value=0, step=1, value=0, key="in1_qty")

            if st.button("💾 Simpan Data Personil", use_container_width=True, key="btn_save_in1"):
                if f_qty <= 0:
                    st.warning("⚠️ Qty penjualan harus lebih dari 0!")
                else:
                    new_id = f"SP{len(st.session_state.sales_person_df) + 1:05d}"
                    p_match = person_df[person_df["person_name"] == f_person]
                    person_id_val = p_match.iloc[0]["person_id"] if not p_match.empty and "person_id" in p_match.columns else "P999"

                    new_row = {
                        "record_id": new_id,
                        "period_id": p_id_val,
                        "item_id": item_dict[f_item_name],
                        "item_name": f_item_name,
                        "person_id": person_id_val,
                        "person_name": f_person,
                        "actual_qty": f_qty,
                        "updated_at": str(f_date)
                    }

                    st.session_state.sales_person_df = pd.concat([st.session_state.sales_person_df, pd.DataFrame([new_row])], ignore_index=True)
                    sync_store_sales_from_personnel()
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.success(f"✅ Penjualan {f_item_name} ({f_qty} Pcs) tersimpan & tersinkron permanen!")
                    st.rerun()
        else:
            st.warning("Tidak ada item produk tersedia di periode ini.")

    # =========================================================
    # SUB MENU 2: EDIT SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in2:
        st.subheader("✏️ Edit Transaksi Sales (Koreksi Input)")
        
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur edit transaksi ini hanya dapat diakses oleh Admin.")
        else:
            e_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="edit_period")
            e_p_id = periods_dict[e_period_name]
            p_start, p_end = get_period_date_bounds(e_p_id)

            sp_sub = sp_df[sp_df["period_id"] == e_p_id].copy()
            
            if sp_sub.empty:
                st.info("Belum ada data transaksi di periode ini untuk diedit.")
            else:
                e_person = st.selectbox("Pilih Personil", sp_sub["person_name"].unique(), key="edit_person")
                sp_person_sub = sp_sub[sp_sub["person_name"] == e_person]

                if sp_person_sub.empty:
                    st.info("Tidak ada transaksi untuk personil ini.")
                else:
                    sp_person_sub["label_trx"] = sp_person_sub.apply(
                        lambda r: f"[{r.get('updated_at', '-')}] {r['item_name']} - {r['actual_qty']} Pcs", axis=1
                    )
                    selected_label = st.selectbox("Pilih Transaksi yang Akan Diedit", sp_person_sub["label_trx"].tolist(), key="edit_trx_select")
                    
                    selected_row = sp_person_sub[sp_person_sub["label_trx"] == selected_label].iloc[0]
                    
                    st.markdown("---")
                    st.markdown("##### Form Perubahan Data")
                    col_e1, col_e2 = st.columns(2)
                    
                    # 🛠️ PERBAIKAN UTAMA: Validasi & Clamping Tanggal Lama agar Bebas Crash
                    try:
                        raw_date = pd.to_datetime(selected_row.get("updated_at")).date()
                    except Exception:
                        raw_date = p_start

                    # Memastikan nilai tanggal aman di antara p_start dan p_end
                    safe_e_date = min(max(raw_date, p_start), p_end)

                    with col_e1:
                        new_e_date = st.date_input(
                            "Ubah Tanggal Transaksi",
                            value=safe_e_date,
                            min_value=p_start,
                            max_value=p_end,
                            key="edit_date_val"
                        )
                    with col_e2:
                        new_e_qty = st.number_input(
                            "Ubah Jumlah Qty (Pcs)",
                            min_value=0,
                            step=1,
                            value=int(selected_row["actual_qty"]),
                            key="edit_qty_val"
                        )

                    if st.button("💾 Simpan Perubahan Edit", use_container_width=True, key="btn_save_edit"):
                        idx = selected_row.name
                        st.session_state.sales_person_df.loc[idx, "actual_qty"] = new_e_qty
                        st.session_state.sales_person_df.loc[idx, "updated_at"] = str(new_e_date)
                        
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.success("✅ Perubahan transaksi berhasil disimpan permanen!")
                        st.rerun()

    # =========================================================
    # SUB MENU 3: HAPUS & RESET SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in3:
        st.subheader("🗑️ Hapus Transaksi / Reset Sales Personil")
        
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur hapus/reset transaksi hanya dapat dilakukan oleh Admin.")
        else:
            d_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="del_period")
            d_p_id = periods_dict[d_period_name]
            
            sp_del_sub = sp_df[sp_df["period_id"] == d_p_id].copy()

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
                            ~((st.session_state.sales_person_df["period_id"] == d_p_id) & 
                              (st.session_state.sales_person_df["person_name"] == d_person) & 
                              (st.session_state.sales_person_df["item_name"] == d_item_name))
                        ]
                        
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.warning(f"⚠️ Transaksi '{d_item_name}' untuk {d_person} berhasil dihapus permanen!")
                        st.rerun()

                else:
                    st.error(f"⚠️ Perhatian: Aksi ini akan menghapus SELURUH catatan penjualan {d_person} pada periode ini.")
                    if st.button(f"🚨 Reset Total Sales {d_person} di Periode Ini", use_container_width=True, key="btn_reset_all"):
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~((st.session_state.sales_person_df["period_id"] == d_p_id) & 
                              (st.session_state.sales_person_df["person_name"] == d_person))
                        ]
                        
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.warning(f"⚠️ Seluruh transaksi {d_person} pada periode ini berhasil di-reset!")
                        st.rerun()

    # =========================================================
    # SUB MENU 4: MULTI INPUT SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in4:
        st.subheader("⚡ Multi Input Sales Personil (Penginputan Cepat)")
        
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur Multi Input Penginputan Cepat hanya dapat diakses oleh Admin.")
        else:
            m_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="multi_period")
            m_p_id = periods_dict[m_period_name]
            
            p_start, p_end = get_period_date_bounds(m_p_id)
            default_val_m = min(max(waktu_wib.date(), p_start), p_end)
            
            m_date = st.date_input(
                f"Tanggal Transaksi (Batas Periode: {p_start.strftime('%d/%m/%Y')} s/d {p_end.strftime('%d/%m/%Y')})",
                value=default_val_m,
                min_value=p_start,
                max_value=p_end,
                key="multi_date"
            )

            all_personnel = person_df["person_name"].dropna().unique().tolist() if not person_df.empty else []
            m_person = st.selectbox("Pilih Nama Personil Staf", all_personnel, key="multi_person")

            filtered_si_m = si_df[si_df["period_id"] == m_p_id]
            
            if filtered_si_m.empty:
                st.warning("Tidak ada item produk tersedia di periode ini.")
            else:
                st.markdown("---")
                st.markdown("##### 📦 Masukkan Jumlah Qty Penjualan Masing-Masing Produk:")
                
                multi_input_values = {}
                col_m1, col_m2 = st.columns(2)
                
                items_list = filtered_si_m[["item_id", "item_name"]].drop_duplicates().to_dict('records')
                
                for idx, item in enumerate(items_list):
                    target_col = col_m1 if idx % 2 == 0 else col_m2
                    with target_col:
                        qty_val = st.number_input(
                            f"📌 {item['item_name']}",
                            min_value=0,
# --- TAB 06: INPUT & RESET DATA ---
elif selected_tab == "06 · Input & Reset Data":
    st.title("✏️ Kelola & Input Data Penjualan")
    
    current_user = st.session_state.get("username", "")
    is_admin = (str(current_user).lower() == "admin")
    
    periods_df = st.session_state.periods_df.copy()
    si_df = st.session_state.sales_item_df.copy()
    sp_df = st.session_state.sales_person_df.copy()
    person_df = st.session_state.person_df.copy()

    # ---------------------------------------------------------
    # PEMBAGIAN 4 SUB MENU
    # ---------------------------------------------------------
    tab_in1, tab_in2, tab_in3, tab_in4 = st.tabs([
        "➕ Input Sales Personil",
        "✏️ Edit Sales Personil",
        "🗑️ Hapus & Reset Sales",
        "⚡ Multi Input Sales"
    ])

    # 🛠️ Helper function aman untuk mengambil rentang tanggal periode
    def get_period_date_bounds(p_id):
        p_match = periods_df[periods_df["period_id"] == p_id]
        if not p_match.empty and "start_date" in p_match.columns and "end_date" in p_match.columns:
            try:
                p_start = pd.to_datetime(p_match.iloc[0]["start_date"]).date()
                p_end = pd.to_datetime(p_match.iloc[0]["end_date"]).date()
                if p_start > p_end:
                    p_start, p_end = p_end, p_start
                return p_start, p_end
            except Exception:
                pass
        today = waktu_wib.date()
        return today.replace(day=1), today

    # =========================================================
    # SUB MENU 1: INPUT SALES PERSONIL (SINGLE ITEM)
    # =========================================================
    with tab_in1:
        st.subheader("➕ Input Penjualan Personil (Satuan)")
        
        f_period_name = st.selectbox("Pilih Periode Transaksi", list(periods_dict.keys()), key="in1_period")
        p_id_val = periods_dict[f_period_name]
        
        # Tanggal terkunci sesuai rentang periode
        p_start, p_end = get_period_date_bounds(p_id_val)
        default_val = min(max(waktu_wib.date(), p_start), p_end)
        
        f_date = st.date_input(
            f"Tanggal Transaksi (Batas Periode: {p_start.strftime('%d/%m/%Y')} s/d {p_end.strftime('%d/%m/%Y')})",
            value=default_val,
            min_value=p_start,
            max_value=p_end,
            key="in1_date"
        )

        all_personnel = person_df["person_name"].dropna().unique().tolist() if not person_df.empty else []
        if is_admin:
            f_person = st.selectbox("Nama Staf / Personil", all_personnel, key="in1_person")
        else:
            f_person = current_user
            st.info(f"👤 Penginputan dikunci untuk akun: **{current_user}**")

        filtered_si = si_df[si_df["period_id"] == p_id_val]
        item_dict = {row["item_name"]: row["item_id"] for _, row in filtered_si.iterrows()} if not filtered_si.empty else {}

        if item_dict:
            f_item_name = st.selectbox("Pilih Produk", list(item_dict.keys()), key="in1_item")
            f_qty = st.number_input("Jumlah Penjualan Qty (Pcs)", min_value=0, step=1, value=0, key="in1_qty")

            if st.button("💾 Simpan Data Personil", use_container_width=True, key="btn_save_in1"):
                if f_qty <= 0:
                    st.warning("⚠️ Qty penjualan harus lebih dari 0!")
                else:
                    new_id = f"SP{len(st.session_state.sales_person_df) + 1:05d}"
                    p_match = person_df[person_df["person_name"] == f_person]
                    person_id_val = p_match.iloc[0]["person_id"] if not p_match.empty and "person_id" in p_match.columns else "P999"

                    new_row = {
                        "record_id": new_id,
                        "period_id": p_id_val,
                        "item_id": item_dict[f_item_name],
                        "item_name": f_item_name,
                        "person_id": person_id_val,
                        "person_name": f_person,
                        "actual_qty": f_qty,
                        "updated_at": str(f_date)
                    }

                    st.session_state.sales_person_df = pd.concat([st.session_state.sales_person_df, pd.DataFrame([new_row])], ignore_index=True)
                    sync_store_sales_from_personnel()
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.success(f"✅ Penjualan {f_item_name} ({f_qty} Pcs) tersimpan & tersinkron permanen!")
                    st.rerun()
        else:
            st.warning("Tidak ada item produk tersedia di periode ini.")

    # =========================================================
    # SUB MENU 2: EDIT SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in2:
        st.subheader("✏️ Edit Transaksi Sales (Koreksi Input)")
        
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur edit transaksi ini hanya dapat diakses oleh Admin.")
        else:
            e_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="edit_period")
            e_p_id = periods_dict[e_period_name]
            p_start, p_end = get_period_date_bounds(e_p_id)

            sp_sub = sp_df[sp_df["period_id"] == e_p_id].copy()
            
            if sp_sub.empty:
                st.info("Belum ada data transaksi di periode ini untuk diedit.")
            else:
                e_person = st.selectbox("Pilih Personil", sp_sub["person_name"].unique(), key="edit_person")
                sp_person_sub = sp_sub[sp_sub["person_name"] == e_person]

                if sp_person_sub.empty:
                    st.info("Tidak ada transaksi untuk personil ini.")
                else:
                    sp_person_sub["label_trx"] = sp_person_sub.apply(
                        lambda r: f"[{r.get('updated_at', '-')}] {r['item_name']} - {r['actual_qty']} Pcs", axis=1
                    )
                    selected_label = st.selectbox("Pilih Transaksi yang Akan Diedit", sp_person_sub["label_trx"].tolist(), key="edit_trx_select")
                    
                    selected_row = sp_person_sub[sp_person_sub["label_trx"] == selected_label].iloc[0]
                    
                    st.markdown("---")
                    st.markdown("##### Form Perubahan Data")
                    col_e1, col_e2 = st.columns(2)
                    
                    # 🛠️ PERBAIKAN UTAMA: Validasi & Clamping Tanggal Lama agar Bebas Crash
                    try:
                        raw_date = pd.to_datetime(selected_row.get("updated_at")).date()
                    except Exception:
                        raw_date = p_start

                    # Memastikan nilai tanggal aman di antara p_start dan p_end
                    safe_e_date = min(max(raw_date, p_start), p_end)

                    with col_e1:
                        new_e_date = st.date_input(
                            "Ubah Tanggal Transaksi",
                            value=safe_e_date,
                            min_value=p_start,
                            max_value=p_end,
                            key="edit_date_val"
                        )
                    with col_e2:
                        new_e_qty = st.number_input(
                            "Ubah Jumlah Qty (Pcs)",
                            min_value=0,
                            step=1,
                            value=int(selected_row["actual_qty"]),
                            key="edit_qty_val"
                        )

                    if st.button("💾 Simpan Perubahan Edit", use_container_width=True, key="btn_save_edit"):
                        idx = selected_row.name
                        st.session_state.sales_person_df.loc[idx, "actual_qty"] = new_e_qty
                        st.session_state.sales_person_df.loc[idx, "updated_at"] = str(new_e_date)
                        
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.success("✅ Perubahan transaksi berhasil disimpan permanen!")
                        st.rerun()

    # =========================================================
    # SUB MENU 3: HAPUS & RESET SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in3:
        st.subheader("🗑️ Hapus Transaksi / Reset Sales Personil")
        
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur hapus/reset transaksi hanya dapat dilakukan oleh Admin.")
        else:
            d_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="del_period")
            d_p_id = periods_dict[d_period_name]
            
            sp_del_sub = sp_df[sp_df["period_id"] == d_p_id].copy()

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
                            ~((st.session_state.sales_person_df["period_id"] == d_p_id) & 
                              (st.session_state.sales_person_df["person_name"] == d_person) & 
                              (st.session_state.sales_person_df["item_name"] == d_item_name))
                        ]
                        
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.warning(f"⚠️ Transaksi '{d_item_name}' untuk {d_person} berhasil dihapus permanen!")
                        st.rerun()

                else:
                    st.error(f"⚠️ Perhatian: Aksi ini akan menghapus SELURUH catatan penjualan {d_person} pada periode ini.")
                    if st.button(f"🚨 Reset Total Sales {d_person} di Periode Ini", use_container_width=True, key="btn_reset_all"):
                        st.session_state.sales_person_df = st.session_state.sales_person_df[
                            ~((st.session_state.sales_person_df["period_id"] == d_p_id) & 
                              (st.session_state.sales_person_df["person_name"] == d_person))
                        ]
                        
                        sync_store_sales_from_personnel()
                        save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                        st.warning(f"⚠️ Seluruh transaksi {d_person} pada periode ini berhasil di-reset!")
                        st.rerun()

    # =========================================================
    # SUB MENU 4: MULTI INPUT SALES PERSONIL (KHUSUS ADMIN)
    # =========================================================
    with tab_in4:
        st.subheader("⚡ Multi Input Sales Personil (Penginputan Cepat)")
        
        if not is_admin:
            st.error("🔒 **Akses Ditolak!** Fitur Multi Input Penginputan Cepat hanya dapat diakses oleh Admin.")
        else:
            m_period_name = st.selectbox("Pilih Periode", list(periods_dict.keys()), key="multi_period")
            m_p_id = periods_dict[m_period_name]
            
            p_start, p_end = get_period_date_bounds(m_p_id)
            default_val_m = min(max(waktu_wib.date(), p_start), p_end)
            
            m_date = st.date_input(
                f"Tanggal Transaksi (Batas Periode: {p_start.strftime('%d/%m/%Y')} s/d {p_end.strftime('%d/%m/%Y')})",
                value=default_val_m,
                min_value=p_start,
                max_value=p_end,
                key="multi_date"
            )

            all_personnel = person_df["person_name"].dropna().unique().tolist() if not person_df.empty else []
            m_person = st.selectbox("Pilih Nama Personil Staf", all_personnel, key="multi_person")

            filtered_si_m = si_df[si_df["period_id"] == m_p_id]
            
            if filtered_si_m.empty:
                st.warning("Tidak ada item produk tersedia di periode ini.")
            else:
                st.markdown("---")
                st.markdown("##### 📦 Masukkan Jumlah Qty Penjualan Masing-Masing Produk:")
                
                multi_input_values = {}
                col_m1, col_m2 = st.columns(2)
                
                items_list = filtered_si_m[["item_id", "item_name"]].drop_duplicates().to_dict('records')
                
                for idx, item in enumerate(items_list):
                    target_col = col_m1 if idx % 2 == 0 else col_m2
                    with target_col:
                        qty_val = st.number_input(
                            f"📌 {item['item_name']}",
                            min_value=0,
                            step=1,
                            value=0,
                            key=f"multi_qty_{item['item_id']}"
                        )
                        multi_input_values[item['item_id']] = {
                            "item_name": item['item_name'],
                            "qty": qty_val
                        }

                st.markdown("---")
                if st.button("💾 Simpan Semua Data Penjualan Multi-Input", use_container_width=True, key="btn_save_multi"):
                    p_match = person_df[person_df["person_name"] == m_person]
                    person_id_val = p_match.iloc[0]["person_id"] if not p_match.empty and "person_id" in p_match.columns else "P999"

                    new_rows = []
                    inserted_count = 0
                    
                    for item_id, item_data in multi_input_values.items():
                        if item_data["qty"] > 0:
                            new_id = f"SP{len(st.session_state.sales_person_df) + len(new_rows) + 1:05d}"
                            new_rows.append({
                                "record_id": new_id,
                                "period_id": m_p_id,
                                "item_id": item_id,
                                "item_name": item_data["item_name"],
                                "person_id": person_id_val,
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
                        st.rerun()
                    else:
                        st.warning("⚠️ Tidak ada Qty produk yang diisi (semua bernilai 0).")

# --- TAB 07: MASTER DATA & PENGATURAN ---
elif selected_tab == "⚙️ Master Data & Pengaturan":
    ALLOWED_USERNAMES = ["admin", "Staff Toko"]
    current_user = st.session_state.get("username", "").lower()
    
    if current_user not in ALLOWED_USERNAMES:
        st.error("🔒 **Akses Ditolak!** Menu ini hanya dapat diakses oleh akun Admin / Pengelola Toko.")
        st.stop()
        
    st.title("⚙️ Pengaturan Master Data & Akun Toko")
    p_df = st.session_state.periods_df.copy()
    i_df = st.session_state.items_df.copy()
    pers_df = st.session_state.person_df.copy()
    si_df = st.session_state.sales_item_df.copy()
    sp_df = st.session_state.sales_person_df.copy()

    if "users_df" not in st.session_state:
        st.session_state.users_df = pd.DataFrame([
            {"username": "admin", "password": "123", "role": "Admin / COS", "name": "Chief Of Store"},
            {"username": "kasir1", "password": "123", "role": "Kasir / Staf Toko", "name": "Kasir Utama"}
        ])
    users_df = st.session_state.users_df.copy()

    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
        "👥 Personil & Resign", 
        "🔑 Kelola Akun & Password",
        "📦 Master Item Produk", 
        "📅 Kelola Periode"
    ])

    with sub_tab1:
        st.subheader("👥 Kelola Personil Toko")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            new_person_name = st.text_input("Nama Personil Baru", key="new_p_name")
            new_person_role = st.selectbox("Jabatan / Role", ["Kasir", "Pramuniaga", "Chief Of Store", "Assistant COS"], key="new_p_role")
            if st.button("💾 Simpan Personil Baru", use_container_width=True):
                if new_person_name.strip() != "":
                    new_p_id = f"P{len(pers_df)+1:03d}"
                    new_p_row = pd.DataFrame([{"person_id": new_p_id, "person_name": new_person_name.strip(), "role": new_person_role}])
                    pers_df = pd.concat([pers_df, new_p_row], ignore_index=True)
                    st.session_state.person_df = pers_df
                    save_master_table("MASTER_PERSONIL", pers_df)
                    st.success(f"✅ Personil '{new_person_name}' berhasil ditambahkan ke Google Sheets!")
                    st.rerun()

        with col_p2:
            if not pers_df.empty and "person_name" in pers_df.columns:
                person_to_delete = st.selectbox("Pilih Personil Resign", pers_df["person_name"].unique(), key="del_p_name")
                if st.button("🗑️ Hapus Personil Ini", use_container_width=True):
                    pers_df = pers_df[pers_df["person_name"] != person_to_delete]
                    st.session_state.person_df = pers_df
                    save_master_table("MASTER_PERSONIL", pers_df)
                    st.success(f"🗑️ Personil '{person_to_delete}' telah dihapus!")
                    st.rerun()

        st.markdown("---")
        st.dataframe(pers_df, use_container_width=True, hide_index=True)

    with sub_tab2:
        st.subheader("🔑 Kelola Username & Password Akses Web")
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            new_user = st.text_input("Username Baru", key="new_user_input")
            new_pass = st.text_input("Password Baru", type="password", key="new_pass_input")
            user_fullname = st.text_input("Nama Lengkap Karyawan", key="fullname_input")
            user_role = st.selectbox("Akses Role", ["Kasir / Staf Toko", "Admin / COS"], key="role_input")
            
            if st.button("💾 Buat Akun Baru", use_container_width=True):
                if new_user.strip() != "" and new_pass.strip() != "":
                    if new_user.strip() in users_df["username"].values:
                        st.error("⚠️ Username sudah digunakan!")
                    else:
                        new_u_row = pd.DataFrame([{
                            "username": new_user.strip(), "password": new_pass.strip(),
                            "role": user_role, "name": user_fullname.strip() if user_fullname.strip() != "" else new_user.strip()
                        }])
                        users_df = pd.concat([users_df, new_u_row], ignore_index=True)
                        st.session_state.users_df = users_df
                        st.success(f"✅ Akun '{new_user}' berhasil dibuat!")
                        st.rerun()

        with col_u2:
            if not users_df.empty:
                selected_u = st.selectbox("Pilih Username", users_df["username"].unique(), key="edit_u_select")
                updated_pass = st.text_input("Password Baru", type="password", key="edit_pass_input")
                
                if st.button("💾 Simpan Password Baru", use_container_width=True):
                    if updated_pass.strip() != "":
                        users_df.loc[users_df["username"] == selected_u, "password"] = updated_pass.strip()
                        st.session_state.users_df = users_df
                        st.success(f"✅ Password untuk '{selected_u}' berhasil diperbarui!")
                        st.rerun()

        st.markdown("---")
        st.dataframe(users_df[["username", "name", "role"]], use_container_width=True, hide_index=True)

    with sub_tab3:
        st.subheader("📦 Kelola Master Item & Target")
        c_i1, c_i2 = st.columns(2)
        with c_i1:
            select_p_id = st.selectbox("Pilih Periode Target", p_df["period_id"].unique() if not p_df.empty else ["P01"], key="item_p_id")
            new_item_name = st.text_input("Nama Item Produk Baru", key="new_i_name")
            new_item_target = st.number_input("Target Qty Toko (Pcs)", min_value=0, value=100, step=10, key="new_i_target")
            new_item_target_kasir = st.number_input("Target Qty Kasir (Pcs)", min_value=0, value=20, step=5, key="new_i_target_kasir")
            
            if st.button("💾 Simpan Item Ke Periode Ini", use_container_width=True):
                if new_item_name.strip() != "":
                    new_i_id = f"ITM{len(i_df)+1:03d}"
                    new_item_row = pd.DataFrame([{"item_id": new_i_id, "item_name": new_item_name.strip()}])
                    i_df = pd.concat([i_df, new_item_row], ignore_index=True)
                    st.session_state.items_df = i_df
                    save_master_table("MASTER_ITEM", i_df)
                    
                    new_si_row = pd.DataFrame([{
                        "period_id": select_p_id,
                        "item_id": new_i_id,
                        "item_name": new_item_name.strip(),
                        "target_qty": new_item_target,
                        "target_qty_kasir": new_item_target_kasir,
                        "actual_qty": 0
                    }])
                    si_df = pd.concat([si_df, new_si_row], ignore_index=True)
                    st.session_state.sales_item_df = si_df
                    save_database(si_df, sp_df)
                    st.success(f"✅ Item '{new_item_name}' disimpan ke Google Sheets!")
                    st.rerun()

        with c_i2:
            if not si_df.empty:
                item_to_delete = st.selectbox("Pilih Item yang Dihapus", si_df["item_name"].unique(), key="del_i_name")
                if st.button("🗑️ Hapus Item Ini", use_container_width=True):
                    si_df = si_df[si_df["item_name"] != item_to_delete]
                    st.session_state.sales_item_df = si_df
                    sp_df = sp_df[sp_df["item_name"] != item_to_delete]
                    st.session_state.sales_person_df = sp_df
                    sync_store_sales_from_personnel()
                    save_database(si_df, sp_df)
                    st.success(f"🗑️ Item '{item_to_delete}' berhasil dihapus!")
                    st.rerun()

    with sub_tab4:
        st.subheader("📅 Ubah Nama & Label Periode")
        if not p_df.empty:
            p_to_edit = st.selectbox("Pilih ID Periode", p_df["period_id"].unique(), key="edit_p_id")
            current_name = p_df.loc[p_df["period_id"] == p_to_edit, "period_name"].values[0] if "period_name" in p_df.columns else f"Periode {p_to_edit}"
            new_period_label = st.text_input("Label Periode Baru", value=current_name)
            
            if st.button("💾 Update Nama Periode", use_container_width=True):
                p_df.loc[p_df["period_id"] == p_to_edit, "period_name"] = new_period_label
                st.session_state.periods_df = p_df
                save_master_table("PERIODE", p_df)
                st.success(f"✅ Nama Periode diperbarui!")
                st.rerun()
