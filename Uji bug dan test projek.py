import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
import time

# =========================================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# =========================================================
st.set_page_config(
    page_title="PSM Toko - Mobile Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"  # Sidebar tersembunyi agar fokus ke layar HP
)

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
    """Menyimpan perubahan master data ke Google Sheets."""
    try:
        conn.update(worksheet=sheet_name, data=df_data)
        st.toast(f"Master {sheet_name} berhasil diperbarui di Google Sheets!", icon="✅")
        return True
    except Exception as e:
        st.error(f"Gagal update master {sheet_name}: {e}")
        return False

if "data_loaded" not in st.session_state:
    p_df, i_df, pers_df, si_df, sp_df = load_database()
    st.session_state.periods_df = p_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.data_loaded = True

# Dynamic state navigasi
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Home"

# =========================================================
# 3. WAKTU REALTIME GMT+7 (WIB)
# =========================================================
waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%A, %d %B %Y %H:%M WIB")

# =========================================================
# 4. FUNGSI AUTENTIKASI DINAMIS
# =========================================================
def check_login(input_username, input_password):
    input_user_clean = str(input_username).strip().lower()
    input_pass_clean = str(input_password).strip()

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

    df_users = st.session_state.get("person_df", pd.DataFrame())
    if df_users.empty:
        try:
            df_users = conn.read(worksheet="MASTER_PERSONIL", ttl=0)
            st.session_state.person_df = df_users.copy()
        except Exception:
            df_users = pd.DataFrame()

    if df_users.empty or "username" not in df_users.columns or "password" not in df_users.columns:
        return False

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
# 5. CUSTOM CSS (NEON DARK + MOBILE GRID HOME SCREEN)
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #0b0f19; color: #f8fafc; font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; }

/* Custom Styling Komponen UI */
label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label, label p {
    color: #38bdf8 !important; font-weight: 600 !important; font-size: 14px !important;
}
div[data-baseweb="input"] input, div[data-baseweb="select"] input, div[data-baseweb="select"] span {
    color: #ffffff !important; background-color: transparent !important; font-weight: bold !important;
}
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background-color: #0d1117 !important; border: 1.5px solid #00f0ff !important; border-radius: 8px !important;
}

/* Metric Card */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #38bdf8; padding: 14px; border-radius: 12px; box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
}
div[data-testid="stMetric"] label { color: #94a3b8 !important; font-weight: 700; font-size: 12px; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #38bdf8 !important; text-shadow: 0 0 10px rgba(56, 189, 248, 0.5); font-weight: 800; font-size: 22px;
}

/* Styling Home Screen App Card ala HP */
.app-card {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border: 1.5px solid #00f0ff;
    border-radius: 18px;
    padding: 16px 10px;
    text-align: center;
    box-shadow: 0 6px 16px rgba(0, 240, 255, 0.15);
    margin-bottom: 8px;
}
.app-icon { font-size: 38px; margin-bottom: 4px; display: block; }
.app-title { color: #ffffff; font-size: 15px; font-weight: 700; margin: 0; }
.app-desc { color: #94a3b8; font-size: 11px; margin-top: 2px; }

/* Custom Button */
div.stButton > button {
    background-color: #080c14 !important; color: #ffffff !important; border: 1.5px solid #00f0ff !important;
    border-radius: 10px !important; font-weight: bold !important; box-shadow: 0 0 10px rgba(0, 240, 255, 0.2) !important;
}
</style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# =========================================================
# 6. HALAMAN LOGIN
# =========================================================
def show_login_page():
    LOGO_URL = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/kgs_group_belgium_logo.jpg"
    
    st.markdown("""
    <style>
    .login-card { 
        background-color: #1e293b; padding: 25px 20px; border-radius: 16px; 
        box-shadow: 0 10px 25px 5px rgba(0, 0, 0, 0.4); text-align: center; margin-bottom: 20px; 
    }
    .login-logo { 
        width: 90px; height: 90px; object-fit: contain; border-radius: 12px; 
        background-color: #ffffff; padding: 6px; margin-bottom: 12px; display: block; margin-left: auto; margin-right: auto; 
    }
    .login-title { color: #ffffff; font-size: 20px; font-weight: 700; margin-bottom: 4px; }
    .login-subtitle { color: #38bdf8; font-size: 13px; margin-bottom: 0px; }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown(f"""
        <div class='login-card'>
            <img src='{LOGO_URL}' class='login-logo' alt='KGS Group Logo'>
            <div class='login-title'>TOKO C383</div>
            <p class='login-subtitle'>Sistem Monitoring PSM Toko</p>
        </div>
        """, unsafe_allow_html=True)
        
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
                st.toast(f"🎉 Selamat Datang, {st.session_state.get('person_name', u_clean)}!")
                st.rerun()
            else:
                st.error("❌ Username atau Password salah!")

if not st.session_state["logged_in"]:
    show_login_page()
    st.stop()

# =========================================================
# 7. HEADER UTAMA DASHBOARD
# =========================================================
periods_df = st.session_state.get("periods_df", pd.DataFrame())
if not periods_df.empty and "period_name" in periods_df.columns and "period_id" in periods_df.columns:
    periods_dict = {str(row["period_name"]): str(row["period_id"]) for _, row in periods_df.iterrows()}
else:
    periods_dict = {"Periode Utama": "P01"}

# Top Navigation Bar & Info User
h_col1, h_col2 = st.columns([2.5, 1])
with h_col1:
    st.markdown(f"""
    <div style='display: flex; align-items: center; gap: 10px;'>
        <div style='background: #00f0ff; width: 10px; height: 35px; border-radius: 4px;'></div>
        <div>
            <h3 style='margin:0; color:#ffffff; font-size: 18px;'>TOKO C383 MOBILE</h3>
            <p style='margin:0; color:#38bdf8; font-size: 11px;'>👤 {st.session_state.get("person_name", "User")} ({st.session_state.get("role", "Staff")})</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with h_col2:
    if st.button("🚪 Logout", key="btn_logout_top", use_container_width=True):
        st.session_state.clear()
        st.session_state["logged_in"] = False
        st.rerun()

st.markdown("<hr style='margin: 12px 0; border-color: #1e293b;'>", unsafe_allow_html=True)

# =========================================================
# 8. TAMPILAN HOME SCREEN (GRID MENU ALA HP)
# =========================================================
def show_home_screen():
    st.markdown("""
    <div style='text-align: center; margin-bottom: 20px;'>
        <p style='color: #94a3b8; font-size: 12px; font-weight: bold; margin-bottom: 2px;'>WAKTU SISTEM REALTIME</p>
        <p style='color: #00f0ff; font-size: 13px; font-weight: bold; margin-top: 0;'>""" + current_time_str + """</p>
    </div>
    """, unsafe_allow_html=True)

    # BARIS 1 (GRID 2 KOLOM)
    g1_col1, g1_col2 = st.columns(2)

    with g1_col1:
        st.markdown("""
        <div class='app-card'>
            <span class='app-icon'>📊</span>
            <div class='app-title'>Dashboard</div>
            <div class='app-desc'>Sales & Item Store</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Buka Dashboard", key="btn_app_dash", use_container_width=True):
            st.session_state.active_tab = "01 Dashboard Toko"
            st.rerun()

    with g1_col2:
        st.markdown("""
        <div class='app-card'>
            <span class='app-icon'>👥</span>
            <div class='app-title'>Raport Personil</div>
            <div class='app-desc'>Ranking & Pencapaian</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Buka Raport", key="btn_app_pers", use_container_width=True):
            st.session_state.active_tab = "02 Raport Personil Toko"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # BARIS 2 (GRID 2 KOLOM)
    g2_col1, g2_col2 = st.columns(2)

    with g2_col1:
        st.markdown("""
        <div class='app-card'>
            <span class='app-icon'>🎯</span>
            <div class='app-title'>IKT & PPS</div>
            <div class='app-desc'>Net Sales & Target</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Buka IKT & PPS", key="btn_app_ikt", use_container_width=True):
            st.session_state.active_tab = "03 Report IKT & PPS"
            st.rerun()

    with g2_col2:
        st.markdown("""
        <div class='app-card'>
            <span class='app-icon'>⚙️</span>
            <div class='app-title'>Pengaturan</div>
            <div class='app-desc'>Master & Filter Data</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Buka Pengaturan", key="btn_app_set", use_container_width=True):
            st.session_state.active_tab = "04 Pengaturan & Download"
            st.rerun()

# =========================================================
# 9. NAVIGASI BAR ATAS (MUNCUL SAAT DI DALAM MENU)
# =========================================================
selected_tab = st.session_state.active_tab

if selected_tab != "Home":
    nav_col1, nav_col2 = st.columns([1.2, 2.8])
    with nav_col1:
        if st.button("🏠 Home Screen", key="btn_nav_home", use_container_width=True):
            st.session_state.active_tab = "Home"
            st.rerun()
    with nav_col2:
        st.markdown(f"<h4 style='color:#00f0ff; margin: 6px 0 0 0;'>📌 {selected_tab}</h4>", unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 10px 0 15px 0; border-color: #334155;'>", unsafe_allow_html=True)

# =========================================================
# 10. MODUL HALAMAN APLIKASI
# =========================================================

# --- HOME SCREEN ---
if selected_tab == "Home":
    show_home_screen()

# --- TAB 01: DASHBOARD TOKO ---
elif selected_tab == "01 Dashboard Toko":
    sub_tab01 = st.radio(
        "Pilih Sub-Menu:",
        ["📊 Overview Penjualan", "📦 Detail Item & Performa Toko"],
        horizontal=True, key="sub_tab01_mobile"
    )
    st.markdown("<br>", unsafe_allow_html=True)

    si_df = st.session_state.sales_item_df.copy()
    sp_df = st.session_state.sales_person_df.copy()
    periods_df = st.session_state.periods_df.copy()

    if sub_tab01 == "📊 Overview Penjualan":
        selected_p_overview = st.selectbox("🗓️ Filter Periode:", ["Semua Periode (Overall)"] + list(periods_dict.keys()), key="ov_period_select")

        if selected_p_overview != "Semua Periode (Overall)":
            p_id = periods_dict[selected_p_overview]
            sub_periods = periods_df[periods_df["period_id"] == p_id]
            sub_si = si_df[si_df["period_id"] == p_id]
            sub_sp = sp_df[sp_df["period_id"] == p_id]
        else:
            sub_periods = periods_df
            sub_si = si_df
            sub_sp = sp_df

        if not sub_periods.empty and "start_date" in sub_periods.columns:
            start_date = pd.to_datetime(sub_periods["start_date"].min()).date()
            end_date = pd.to_datetime(sub_periods["end_date"].max()).date()
        else:
            start_date = waktu_wib.date().replace(day=1)
            end_date = waktu_wib.date()

        total_days = max((end_date - start_date).days + 1, 1)
        today_date = waktu_wib.date()
        passed_days = total_days if today_date > end_date else (0 if today_date < start_date else max((today_date - start_date).days + 1, 1))

        time_factor = (passed_days / total_days) * 100 if total_days > 0 else 0
        tot_target = pd.to_numeric(sub_si.get("target_qty", 0), errors="coerce").fillna(0).sum()
        tot_actual = pd.to_numeric(sub_sp.get("actual_qty", 0), errors="coerce").fillna(0).sum()
        tot_gap = tot_target - tot_actual
        tot_ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0
        weighted_score = (tot_ach / 100) * 20

        m1, m2, m3 = st.columns(3)
        m1.metric("🎯 Target", f"{tot_target:,.0f} Pcs")
        m2.metric("📦 Actual", f"{tot_actual:,.0f} Pcs")
        m3.metric("📉 Sisa Gap", f"{max(tot_gap, 0):,.0f} Pcs")

        st.markdown("<br>", unsafe_allow_html=True)
        m4, m5, m6 = st.columns(3)
        m4.metric("⚡ % Ach Toko", f"{tot_ach:.1f}%")
        m5.metric("⏳ Time Factor", f"{time_factor:.1f}%")
        m6.metric("🏆 Indeks Bobot", f"{weighted_score:.1f} Pt")

    elif sub_tab01 == "📦 Detail Item & Performa Toko":
        search_query = st.text_input("🔍 Cari Produk:", placeholder="Ketik nama item...", key="search_item_mob")
        selected_p_detail = st.selectbox("Filter Periode", ["Semua Periode"] + list(periods_dict.keys()), key="period_detail_mob")
        
        si_det = si_df[si_df["period_id"] == periods_dict[selected_p_detail]].copy() if selected_p_detail != "Semua Periode" else si_df.copy()
        si_det["target_qty"] = pd.to_numeric(si_det.get("target_qty", 0), errors="coerce").fillna(0)
        si_det["actual_qty"] = pd.to_numeric(si_det.get("actual_qty", 0), errors="coerce").fillna(0)

        item_grouped = si_det.groupby("item_name").agg({"target_qty": "sum", "actual_qty": "sum"}).reset_index()
        item_grouped["gap"] = item_grouped["target_qty"] - item_grouped["actual_qty"]
        item_grouped["ach"] = item_grouped.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)

        if search_query:
            item_grouped = item_grouped[item_grouped["item_name"].str.contains(search_query, case=False, na=False)]

        st.dataframe(item_grouped, use_container_width=True)

# --- TAB 02: RAPORT PERSONIL TOKO ---
elif selected_tab == "02 Raport Personil Toko":
    st.markdown("### 🏆 Ranking & Summary Personil")
    sp_df = st.session_state.sales_person_df.copy()
    sp_df["actual_qty"] = pd.to_numeric(sp_df.get("actual_qty", 0), errors="coerce").fillna(0)

    if not sp_df.empty:
        summary_person = sp_df.groupby("person_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        tot_actual_personil = summary_person["actual_qty"].sum()

        m1, m2 = st.columns(2)
        m1.metric("TOTAL SALES", f"{tot_actual_personil:,.0f} Pcs")
        m2.metric("👑 TOP PERSONIL", summary_person.iloc[0]["person_name"] if not summary_person.empty else "-")

        st.markdown("<br>", unsafe_allow_html=True)
        fig_person = go.Figure(go.Bar(
            x=summary_person["person_name"], y=summary_person["actual_qty"],
            text=summary_person["actual_qty"].apply(lambda x: f"{x:,.0f}"), textposition="outside",
            marker=dict(color=summary_person["actual_qty"], colorscale="Viridis")
        ))
        fig_person.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ffffff"))
        st.plotly_chart(fig_person, use_container_width=True)
    else:
        st.info("💡 Belum ada data transaksi personil.")

# --- TAB 03: REPORT IKT & PPS ---
elif selected_tab == "03 Report IKT & PPS":
    if "current_view" not in st.session_state:
        st.session_state.current_view = "summary"

    if st.session_state.current_view == "summary":
        st.markdown("### 🎯 Summary Performance")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Net Sales", "Rp 0", "0%")
            if st.button("Detail Net Sales", key="goto_sales_mob", use_container_width=True):
                st.session_state.current_view = "detail_sales"
                st.rerun()

        with col2:
            st.metric("PPS", "0", "0%")
            if st.button("Detail PPS", key="goto_pps_mob", use_container_width=True):
                st.session_state.current_view = "detail_pps"
                st.rerun()

    elif st.session_state.current_view == "detail_sales":
        if st.button("⬅️ Kembali", key="back_ik_s"):
            st.session_state.current_view = "summary"
            st.rerun()
        st.markdown("### 💰 Detail Net Sales")
        st.metric("Total Sales", "Rp 0")

    elif st.session_state.current_view == "detail_pps":
        if st.button("⬅️ Kembali", key="back_ik_p"):
            st.session_state.current_view = "summary"
            st.rerun()
        st.markdown("### 📦 Detail Report PPS")
        st.info("Data PPS Siap Ditampilkan.")

# --- TAB 04: PENGATURAN & DOWNLOAD ---
elif selected_tab == "04 Pengaturan & Download":
    st.markdown("### ⚙️ Pengaturan & Data Master")
    st.success("Aplikasi terhubung dengan Google Sheets!")
    if st.button("🔄 Reload Data Realtime", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
