import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
import math

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

# Contoh saat me-load data di bagian atas aplikasi Streamlit:
df_periode = pd.read_excel("Database_Penjualan_PSM_Toko_Clean_GoogleSheets (2).xlsx", sheet_name="PERIODE")
df_sales_item = pd.read_excel("Database_Penjualan_PSM_Toko_Clean_GoogleSheets (2).xlsx", sheet_name="SALES_ITEM")

# Simpan ke session_state agar aman diakses di mana saja
st.session_state['df_periode'] = df_periode
st.session_state['df_sales_item'] = df_sales_item

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

# Ekstraksi dataframe dari session state agar aman
df_periods = st.session_state.get("periods_df", pd.DataFrame())
df_items = st.session_state.get("items_df", pd.DataFrame())
df_person = st.session_state.get("person_df", pd.DataFrame())
df_sales_item = st.session_state.get("sales_item_df", pd.DataFrame())
df_sales_person = st.session_state.get("sales_person_df", pd.DataFrame())

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
# TAB 01: DASHBOARD
# =========================================================
elif selected_tab == "01 Dashboard":
    
    if "dash_page" not in st.session_state:
        st.session_state.dash_page = "Main"

    if st.session_state.dash_page != "Main":
        if st.button("⬅️ Kembali ke Menu Utama Dashboard", key="btn_back_dash", use_container_width=True):
            st.session_state.dash_page = "Main"
            st.session_state.active_detail_view = None
            st.rerun()
        st.markdown("<hr style='margin: 8px 0; border-color: #334155;'>", unsafe_allow_html=True)

    # --- MENU UTAMA DASHBOARD ---
    if st.session_state.dash_page == "Main":
        st.markdown("<h4 style='text-align: center; color: #00f0ff; margin-bottom: 16px;'>📊 MENU DASHBOARD UTAMA</h4>", unsafe_allow_html=True)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown("<div class='app-card'><span class='app-icon'>📈</span><div class='app-title'>Report PSM</div><div class='app-desc'>Pencapaian PSM Toko</div></div>", unsafe_allow_html=True)
            if st.button("Buka PSM", key="btn_dash_psm", use_container_width=True):
                st.session_state.dash_page = "PSM"
                st.rerun()
                
        with col_d2:
            st.markdown("<div class='app-card'><span class='app-icon'>💰</span><div class='app-title'>Report Sales Toko</div><div class='app-desc'>Net Sales, GM & NSB</div></div>", unsafe_allow_html=True)
            if st.button("Buka Sales Toko", key="btn_dash_sales", use_container_width=True):
                st.session_state.dash_page = "SalesToko"
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        col_d3, col_d4 = st.columns(2)
        with col_d3:
            st.markdown("<div class='app-card'><span class='app-icon'>🛒</span><div class='app-title'>Report PPS Toko</div><div class='app-desc'>APC, PWP, Sueger, Simulasi</div></div>", unsafe_allow_html=True)
            if st.button("Buka PPS Toko", key="btn_dash_pps", use_container_width=True):
                st.session_state.dash_page = "PPSToko"
                st.rerun()
                
        with col_d4:
            st.markdown("<div class='app-card'><span class='app-icon'>👥</span><div class='app-title'>Report STD & Member</div><div class='app-desc'>Kontribusi Member & STD</div></div>", unsafe_allow_html=True)
            if st.button("Buka STD & Member", key="btn_dash_std", use_container_width=True):
                st.session_state.dash_page = "StdMember"
                st.rerun()

    # --- HALAMAN 1: REPORT PSM ---
    elif st.session_state.dash_page == "PSM":
        st.markdown("### 📈 Report PSM Toko")
        
        view_mode = st.radio("Pilih Mode Tampilan PSM:", ["☀️ Harian", "⏱️ Periode", "🗓️ Bulanan"], horizontal=True, key="rad_psm_mode")
        st.markdown("---")

        today_date = waktu_wib.date() if 'waktu_wib' in locals() else datetime.now().date()
        active_date = st.session_state.get("calendar_psm_harian", today_date)
            
        # 1. MODE HARIAN
        if view_mode == "☀️ Harian":
            if st.session_state.get("active_detail_view") == "detail_kontributor":
                if st.button("⬅️ Kembali ke Menu Harian", key="btn_back_to_harian", use_container_width=True):
                    st.session_state.active_detail_view = None
                    st.rerun()
            
                st.markdown("### 🏆 Podium & Rincian Kontributor Toko (Hari Ini)")
            
                selected_daily_date = st.session_state.get("calendar_psm_harian", today_date)
                sub_sp = df_sales_person.copy() if not df_sales_person.empty else pd.DataFrame()
                if not sub_sp.empty:
                    date_col_sp = next((c for c in sub_sp.columns if "updated_at" in c or "date" in c or "tanggal" in c), None)
                    sub_sp["dt_clean"] = pd.to_datetime(sub_sp[date_col_sp], errors="coerce").dt.date if date_col_sp else None
                    sub_sp["actual_qty"] = pd.to_numeric(sub_sp.get("actual_qty", 0), errors="coerce").fillna(0)
                    day_sp = sub_sp[sub_sp["dt_clean"] == selected_daily_date] if "dt_clean" in sub_sp.columns else pd.DataFrame()
                else:
                    day_sp = pd.DataFrame()
            
                if not day_sp.empty and "person_name" in day_sp.columns:
                    df_contrib = day_sp.groupby("person_name")["actual_qty"].sum().reset_index()
                    df_contrib.columns = ["Nama Personil", "Total Penjualan (Pcs)"]
                    df_contrib = df_contrib.sort_values(by="Total Penjualan (Pcs)", ascending=False).reset_index(drop=True)
            
                    if len(df_contrib) >= 3:
                        p_cols = st.columns(3)
                        podium_order = [1, 0, 2] 
                        medals = ["🥈 Juara 2", "🥇 Juara 1", "🥉 Juara 3"]
                        colors = ["#94a3b8", "#f59e0b", "#b45309"]
                        heights = ["130px", "160px", "110px"]
            
                        for target_col_idx, orig_rank_idx in enumerate(podium_order):
                            with p_cols[target_col_idx]:
                                if orig_rank_idx < len(df_contrib):
                                    name = df_contrib.iloc[orig_rank_idx]["Nama Personil"]
                                    qty = df_contrib.iloc[orig_rank_idx]["Total Penjualan (Pcs)"]
                                    st.markdown(f"""
                                    <div style='background-color: #1e293b; padding: 15px; border-radius: 10px; border: 2px solid {colors[orig_rank_idx]}; text-align: center; min-height: {heights[target_col_idx]};'>
                                        <h4 style='margin:0; color: {colors[orig_rank_idx]};'>{medals[orig_rank_idx]}</h4>
                                        <p style='font-size: 16px; font-weight: bold; color: #ffffff; margin: 8px 0 4px 0;'>{name}</p>
                                        <p style='font-size: 14px; color: #38bdf8; margin: 0;'>{qty:,.0f} Pcs</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                    else:
                        p_cols = st.columns(len(df_contrib))
                        for idx, col in enumerate(p_cols):
                            with col:
                                name = df_contrib.iloc[idx]["Nama Personil"]
                                qty = df_contrib.iloc[idx]["Total Penjualan (Pcs)"]
                                st.markdown(f"""
                                <div style='background-color: #1e293b; padding: 15px; border-radius: 10px; border: 2px solid #f59e0b; text-align: center;'>
                                    <h4 style='margin:0; color: #f59e0b;'>Juara {idx+1}</h4>
                                    <p style='font-size: 16px; font-weight: bold; color: #ffffff; margin: 8px 0 4px 0;'>{name}</p>
                                    <p style='font-size: 14px; color: #38bdf8; margin: 0;'>{qty:,.0f} Pcs</p>
                                </div>
                                """, unsafe_allow_html=True)
            
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("##### 📋 Tabel Peringkat Lengkap Kontributor")
                    df_contrib.insert(0, "Peringkat", range(1, len(df_contrib) + 1))
                    st.dataframe(df_contrib, use_container_width=True, hide_index=True)
                else:
                    st.info("Tidak ada data kontributor pada tanggal yang dipilih.")

            else:
                selected_daily_date = st.date_input("📅 Pilih Tanggal Laporan:", value=today_date, key="calendar_psm_harian")
            
                sub_sp = df_sales_person.copy() if not df_sales_person.empty else pd.DataFrame()
                sub_si = df_sales_item.copy() if not df_sales_item.empty else pd.DataFrame()
            
                if not sub_sp.empty:
                    date_col_sp = next((c for c in sub_sp.columns if "updated_at" in c or "date" in c or "tanggal" in c), None)
                    sub_sp["dt_clean"] = pd.to_datetime(sub_sp[date_col_sp], errors="coerce").dt.date if date_col_sp else None
                    sub_sp["actual_qty"] = pd.to_numeric(sub_sp.get("actual_qty", 0), errors="coerce").fillna(0)
                    day_sp = sub_sp[sub_sp["dt_clean"] == selected_daily_date] if "dt_clean" in sub_sp.columns else pd.DataFrame()
                else:
                    day_sp = pd.DataFrame()
            
                top_person = "-"
                person_col = "person_name" if "person_name" in day_sp.columns else ("sales_person" if "sales_person" in day_sp.columns else None)
                if person_col and not day_sp.empty:
                    top_p_df = day_sp.groupby(person_col)["actual_qty"].sum().reset_index()
                    if not top_p_df.empty and top_p_df["actual_qty"].max() > 0:
                        top_person = top_p_df.sort_values(by="actual_qty", ascending=False).iloc[0][person_col]
            
                top_item = "-"
                if not day_sp.empty and "item_name" in day_sp.columns:
                    top_i_df = day_sp.groupby("item_name")["actual_qty"].sum().reset_index()
                    if not top_i_df.empty and top_i_df["actual_qty"].max() > 0:
                        top_item = top_i_df.sort_values(by="actual_qty", ascending=False).iloc[0]["item_name"]
            
                tc1, tc2 = st.columns(2)
                with tc1:
                    st.markdown(f"""
                    <div class='app-card' style='padding: 10px; margin-bottom: 5px;'>
                        <span style='color:#94a3b8; font-size:10px;'>🥇 TOP CONTRIBUTOR</span>
                        <p style='color:#00f0ff; font-size:14px; font-weight:bold; margin:2px 0 0 0;'>{top_person}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("🔍 Klik Detail Kontributor", key="btn_to_contrib_detail", use_container_width=True):
                        st.session_state.active_detail_view = "detail_kontributor"
                        st.rerun()
                        
                with tc2:
                    st.markdown(f"""
                    <div class='app-card' style='padding: 10px; margin-bottom: 5px;'>
                        <span style='color:#94a3b8; font-size:10px;'>📦 TOP ITEM</span>
                        <p style='color:#38bdf8; font-size:14px; font-weight:bold; margin:2px 0 0 0;'>{top_item}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("<div style='height: 38px;'></div>", unsafe_allow_html=True)
            
                st.markdown("<br>", unsafe_allow_html=True)
            
                daily_target = 0.0
                try:
                    if not df_periods.empty:
                        for _, row_p in df_periods.iterrows():
                            p_s = pd.to_datetime(row_p.get("start_date"), errors="coerce").date()
                            p_e = pd.to_datetime(row_p.get("end_date"), errors="coerce").date()
                            
                            if p_s and p_e and (p_s <= selected_daily_date <= p_e):
                                period_id = row_p.get("period_id")
                                tot_p_target = pd.to_numeric(row_p.get("target_total", 0), errors="coerce")
                                tot_p_target = float(tot_p_target) if pd.notna(tot_p_target) else 0.0
                                
                                sub_p_sales = sub_si[sub_si["period_id"] == period_id] if not sub_si.empty and "period_id" in sub_si.columns else pd.DataFrame()
                                tot_p_actual = float(pd.to_numeric(sub_p_sales["actual_qty"], errors="coerce").fillna(0).sum()) if not sub_p_sales.empty else 0.0
                                
                                sisa_target_periode = max(tot_p_target - tot_p_actual, 0.0)
                                sisa_hari = int((p_e - selected_daily_date).days + 1)
                                if sisa_hari <= 0:
                                    sisa_hari = 1
                                
                                daily_target = float(math.ceil(sisa_target_periode / sisa_hari))
                                break
                except Exception:
                    daily_target = 0.0
            
                if pd.isna(daily_target) or daily_target <= 0:
                    if not sub_si.empty and "target_qty" in sub_si.columns:
                        tot_target_full = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0).sum()
                        tot_target_full = float(tot_target_full) if pd.notna(tot_target_full) else 0.0
                        daily_target = tot_target_full / 30.0 if tot_target_full > 0 else 0.0
                    else:
                        daily_target = 0.0
            
                daily_target = float(math.ceil(daily_target)) if pd.notna(daily_target) else 0.0
                daily_actual = float(day_sp["actual_qty"].sum()) if not day_sp.empty else 0.0
                daily_gap = daily_target - daily_actual
                daily_ach = (daily_actual / daily_target * 100.0) if daily_target > 0 else 0.0
            
                g_col1, g_col2 = st.columns(2)
                g_col1.metric("🎯 Target Hari Ini", f"{daily_target:,.0f} Pcs")
                g_col2.metric("📦 Actual Sales", f"{daily_actual:,.0f} Pcs")
            
                st.markdown("<br>", unsafe_allow_html=True)
                g_col3, g_col4 = st.columns(2)
                g_col3.metric("📉 Sisa Gap Harian", f"{max(daily_gap, 0):,.0f} Pcs")
                g_col4.metric("⚡ % Ach Harian", f"{daily_ach:.1f}%")
            
                st.markdown("<br>", unsafe_allow_html=True)
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    default_start = waktu_wib.date().replace(day=1) if 'waktu_wib' in locals() else datetime.now().date().replace(day=1)
                    start_periode_custom = st.date_input("📅 Tanggal Awal:", value=default_start, key="custom_start_date")
                with col_d2:
                    default_end = waktu_wib.date() if 'waktu_wib' in locals() else datetime.now().date()
                    end_periode_custom = st.date_input("📅 Tanggal Akhir:", value=default_end, key="custom_end_date")
                
                is_processed = st.button("🚀 Proses Grafik Penjualan", key="btn_process_grafik", use_container_width=True)
                
                if is_processed:
                    st.markdown(f"##### 📈 GRAFIK GARIS PENJUALAN HARIAN ({start_periode_custom.strftime('%d %b %Y')} s.d. {end_periode_custom.strftime('%d %b %Y')})")
                
                    df_target_source = pd.DataFrame()
                    if not df_sales_person.empty:
                        df_target_source = df_sales_person.copy()
                    elif not df_sales_item.empty:
                        df_target_source = df_sales_item.copy()
                
                    if not df_target_source.empty:
                        date_col = next((c for c in df_target_source.columns if "updated_at" in c or "date" in c or "tanggal" in c), None)
                        actual_qty_col = next((c for c in df_target_source.columns if "actual_qty" in c or "actual" in c), None)
                        
                        if date_col and actual_qty_col:
                            sub_line_df = df_target_source.copy()
                            sub_line_df["dt_clean"] = pd.to_datetime(sub_line_df[date_col], errors="coerce").dt.date
                            sub_line_df["actual_qty"] = pd.to_numeric(sub_line_df[actual_qty_col], errors="coerce").fillna(0)
                            
                            sub_line_df = sub_line_df[(sub_line_df["dt_clean"] >= start_periode_custom) & (sub_line_df["dt_clean"] <= end_periode_custom)]
                            
                            if not sub_line_df.empty:
                                df_daily_trend = sub_line_df.groupby("dt_clean")["actual_qty"].sum().reset_index()
                                df_daily_trend.columns = ["Tanggal", "Total Actual Qty"]
                                df_daily_trend = df_daily_trend.sort_values("Tanggal")
                                
                                df_daily_trend["Tanggal_Str"] = pd.to_datetime(df_daily_trend["Tanggal"]).dt.strftime("%d %b %Y")
                                
                                fig_line = px.line(
                                    df_daily_trend, 
                                    x="Tanggal_Str", 
                                    y="Total Actual Qty", 
                                    markers=True,
                                    text="Total Actual Qty",
                                    labels={"Tanggal_Str": "Tanggal", "Total Actual Qty": "Jumlah Penjualan (Pcs)"}
                                )
                                
                                fig_line.update_traces(
                                    textposition="top center",
                                    textfont=dict(size=11, color="#38bdf8", family="sans-serif"),
                                    line=dict(color="#00f0ff", width=3, shape="spline"),
                                    marker=dict(size=9, color="#00f0ff", line=dict(width=2, color="#0f172a"))
                                )
                                
                                fig_line.update_layout(
                                    margin=dict(t=40, b=20, l=20, r=20), 
                                    height=380,
                                    xaxis_title=None,
                                    yaxis_title="Total Qty",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font=dict(color="#cbd5e1", size=12),
                                    xaxis=dict(showgrid=False, tickfont=dict(color="#94a3b8")),
                                    yaxis=dict(showgrid=True, gridcolor="rgba(255, 255, 255, 0.08)", tickfont=dict(color="#94a3b8"))
                                )
                                st.plotly_chart(fig_line, use_container_width=True)
                            else:
                                st.warning(f"Tidak ada data penjualan pada rentang tanggal tersebut.")
                        else:
                            st.warning("Kolom tanggal atau actual qty tidak ditemukan pada data transaksi.")
                    else:
                        st.info("Belum ada data transaksi yang dimuat untuk menampilkan grafik garis.")
                else:
                    st.info("👆 Silakan tentukan Tanggal Awal & Tanggal Akhir, lalu klik tombol **'Proses Grafik Penjualan'** di atas.")

        # 2. MODE PERIODE
        elif view_mode == "⏱️ Periode":
            st.markdown("##### ⏱️ Pencapaian PSM Berdasarkan Periode")
            
            selected_period_name = None
            selected_period_id = None
            p_start, p_end = None, None
            
            if not df_periods.empty and "period_name" in df_periods.columns:
                period_options = df_periods["period_name"].tolist()
                selected_period_name = st.selectbox("Pilih Periode:", period_options, key="sel_period_psm")
                
                matched_row = df_periods[df_periods["period_name"] == selected_period_name]
                if not matched_row.empty:
                    selected_period_id = matched_row.iloc[0]["period_id"]
                    p_start = pd.to_datetime(matched_row.iloc[0]["start_date"], errors="coerce").date()
                    p_end = pd.to_datetime(matched_row.iloc[0]["end_date"], errors="coerce").date()
            else:
                st.selectbox("Pilih Periode:", ["Periode 1", "Periode 2"], key="sel_period_dummy")
        
            sub_item_periode = pd.DataFrame()
            if not df_sales_item.empty and selected_period_id:
                if "period_id" in df_sales_item.columns:
                    sub_item_periode = df_sales_item[df_sales_item["period_id"] == selected_period_id].copy()
        
            total_target_periode = 0
            total_actual_periode = 0
            top_item_name = "-"
            
            if not sub_item_periode.empty:
                if "target_qty" in sub_item_periode.columns:
                    sub_item_periode["target_qty"] = pd.to_numeric(sub_item_periode["target_qty"], errors="coerce").fillna(0)
                    total_target_periode = sub_item_periode["target_qty"].sum()
                    
                if "actual_qty" in sub_item_periode.columns:
                    sub_item_periode["actual_qty"] = pd.to_numeric(sub_item_periode["actual_qty"], errors="coerce").fillna(0)
                    total_actual_periode = sub_item_periode["actual_qty"].sum()
                    
                if "item_name" in sub_item_periode.columns and not sub_item_periode.empty:
                    df_top = sub_item_periode.groupby("item_name")["actual_qty"].sum().reset_index()
                    if not df_top.empty:
                        df_top = df_top.sort_values(by="actual_qty", ascending=False)
                        top_item_name = f"{df_top.iloc[0]['item_name']} ({df_top.iloc[0]['actual_qty']:,.0f} Pcs)"
        
            ach_periode = (total_actual_periode / total_target_periode * 100) if total_target_periode > 0 else 0
            gap_periode = total_target_periode - total_actual_periode
        
            time_factor_pct = 0.0
            elapsed_days = 0
            total_days = 0
            target_harian_terbaru = 0
            
            if p_start and p_end:
                today_val = datetime.now().date()
                total_days = (p_end - p_start).days + 1
                
                if today_val < p_start:
                    elapsed_days = 0
                elif today_val > p_end:
                    elapsed_days = total_days
                else:
                    elapsed_days = (today_val - p_start).days + 1
                    
                time_factor_pct = (elapsed_days / total_days * 100) if total_days > 0 else 0
                
                remaining_days = (p_end - today_val).days + 1
                remaining_days = max(remaining_days, 1)
                
                sisa_target = max(gap_periode, 0)
                target_harian_terbaru = math.ceil(sisa_target / remaining_days)
        
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Target Periode", f"{total_target_periode:,.0f} Pcs")
            c2.metric("Actual Periode", f"{total_actual_periode:,.0f} Pcs")
            c3.metric("Achievement", f"{ach_periode:.1f}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            c4, c5, c6 = st.columns(3)
            c4.metric("Gap Target", f"{gap_periode:,.0f} Pcs")
            c5.metric("Time Factor", f"{time_factor_pct:.1f}%", help="Persentase durasi hari periode yang sudah berjalan")
            c6.metric("Target Per Hari (Sisa)", f"{target_harian_terbaru:,.1f} Pcs/hari")
        
            st.markdown("<br>", unsafe_allow_html=True)
            if ach_periode >= time_factor_pct:
                status_box_type = "success"
                status_title = "🚀 Status: DI ATAS TIME FACTOR (SUKSES)"
                status_desc = f"Luar biasa! Pencapaian saat ini (**{ach_periode:.1f}%**) berhasil melampaui atau sejalan dengan durasi waktu periode yang sudah berjalan (**{time_factor_pct:.1f}%** pada hari ke-{elapsed_days} dari {total_days} hari). Pertahankan performa positif ini!"
            else:
                status_box_type = "warning"
                status_title = "⚠️ Status: DI BAWAH TIME FACTOR (BELUM MENCAPAI TARGET)"
                status_desc = f"Perhatian! Pencapaian saat ini (**{ach_periode:.1f}%**) masih berada di bawah persentase waktu berjalan (**{time_factor_pct:.1f}%** pada hari ke-{elapsed_days} dari {total_days} hari). Perlu peningkatan strategi penjualan harian agar target dapat tercapai tepat waktu."
        
            if status_box_type == "success":
                st.success(f"**{status_title}**\n\n{status_desc}")
            else:
                st.warning(f"**{status_title}**\n\n{status_desc}")
        
            st.info(f"🏆 **Item Paling Laris Periode Ini:** {top_item_name}")
        
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander(f"📋 Klik untuk Melihat Rincian Penjualan Item ({selected_period_name})", expanded=False):
                if not sub_item_periode.empty:
                    item_col = "item_name" if "item_name" in sub_item_periode.columns else None
                    if item_col:
                        df_summary = sub_item_periode.groupby(item_col).agg({
                            "target_qty": "sum",
                            "actual_qty": "sum"
                        }).reset_index()
                        
                        df_summary.columns = ["Item", "Target Toko", "Jumlah Penjualan"]
                        df_summary["Target Toko"] = pd.to_numeric(df_summary["Target Toko"], errors="coerce").fillna(0)
                        df_summary["Jumlah Penjualan"] = pd.to_numeric(df_summary["Jumlah Penjualan"], errors="coerce").fillna(0)
                        
                        df_summary["Achievement (%)"] = df_summary.apply(
                            lambda r: f"{(r['Jumlah Penjualan'] / r['Target Toko'] * 100):.1f}%" if r["Target Toko"] > 0 else "0.0%", axis=1
                        )
                        df_summary["Gap Penjualan"] = df_summary["Target Toko"] - df_summary["Jumlah Penjualan"]
                        df_summary["Keterangan"] = df_summary.apply(
                            lambda r: "Achieved ✅" if r['Jumlah Penjualan'] >= r['Target Toko'] else "Not Achieved ❌", axis=1
                        )
                        
                        st.dataframe(df_summary, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Kolom 'item_name' tidak ditemukan pada sheet SALES_ITEM.")
                else:
                    st.info(f"Tidak ada data rincian item untuk {selected_period_name}.")

        # 3. MODE BULANAN
        elif view_mode == "🗓️ Bulanan":
            st.markdown("##### 🗓️ Pencapaian PSM Bulanan")
            
            list_bulan = [
                "Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                "Juli", "Agustus", "September", "Oktober", "November", "Desember"
            ]
            
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                selected_bulan_str = st.selectbox("Pilih Bulan:", list_bulan, index=7, key="sel_bulan_psm")
            with col_sel2:
                selected_tahun = st.number_input("Pilih Tahun:", min_value=2020, max_value=2030, value=2026, key="sel_tahun_psm")

            # Angka bulan (1 - 12)
            selected_month_num = list_bulan.index(selected_bulan_str) + 1

            sub_target = df_sales_item.copy() if not df_sales_item.empty else pd.DataFrame()
            
            # Ambil df_periode dari session_state atau lokal
            if 'df_periode' in st.session_state:
                sub_periode = st.session_state.df_periode.copy()
            elif 'df_periode' in locals() and not df_periode.empty:
                sub_periode = df_periode.copy()
            else:
                sub_periode = pd.DataFrame()
        
            monthly_target = 0.0
            monthly_actual = 0.0
        
            if not sub_target.empty:
                # 1. Lakukan MERGE dengan df_periode jika kolom 'start_date' atau 'period_name' belum ada di df_sales_item
                if "period_id" in sub_target.columns and not sub_periode.empty:
                    # Hapus kolom bentrok jika ada
                    cols_to_use = [c for c in sub_periode.columns if c not in sub_target.columns or c == "period_id"]
                    sub_target = sub_target.merge(sub_periode[cols_to_use], on="period_id", how="left")

                # 2. Filter Berdasarkan Bulan dan Tahun
                df_filtered_bulan = pd.DataFrame()
                
                # Opsi A: Filter lewat start_date (datetime)
                if "start_date" in sub_target.columns:
                    sub_target["start_date_dt"] = pd.to_datetime(sub_target["start_date"], errors="coerce")
                    df_filtered_bulan = sub_target[
                        (sub_target["start_date_dt"].dt.month == selected_month_num) & 
                        (sub_target["start_date_dt"].dt.year == selected_tahun)
                    ]
                
                # Opsi B: Filter lewat string period_name (misal: '1 - 7 Agustus 2026')
                if df_filtered_bulan.empty and "period_name" in sub_target.columns:
                    df_filtered_bulan = sub_target[
                        sub_target["period_name"].astype(str).str.contains(selected_bulan_str, case=False, na=False) &
                        sub_target["period_name"].astype(str).str.contains(str(selected_tahun), case=False, na=False)
                    ]

                # 3. Hitung Penjumlahan Target & Actual
                if not df_filtered_bulan.empty:
                    if "target_qty" in df_filtered_bulan.columns:
                        monthly_target = float(pd.to_numeric(df_filtered_bulan["target_qty"], errors="coerce").fillna(0).sum())
                    
                    if "actual_qty" in df_filtered_bulan.columns:
                        monthly_actual = float(pd.to_numeric(df_filtered_bulan["actual_qty"], errors="coerce").fillna(0).sum())
        
            # Perhitungan KPI Bulanan
            monthly_gap = monthly_actual - monthly_target  
            monthly_ach = (monthly_actual / monthly_target * 100.0) if monthly_target > 0 else 0.0
            bobot_pencapaian = (monthly_ach / 100.0) * 20.0
            time_factor_val = 100.0  
            
            # Status Performa
            if monthly_ach >= time_factor_val:
                status_label = "🔥 Achieved (Sangat On Track)"
                status_color = "#10b981" 
            elif monthly_ach >= (time_factor_val * 0.8):
                status_label = "⚠️ Near Target (Kejar Dikit Lagi)"
                status_color = "#f59e0b" 
            else:
                status_label = "❌ Off Track (Perlu Pergerakan Ekstra)"
                status_color = "#ef4444" 
        
            # Baris Metrik Utama
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Target Bulanan", f"{monthly_target:,.0f} Pcs")
            m2.metric("Actual Bulanan", f"{monthly_actual:,.0f} Pcs", delta=f"{monthly_gap:+,.0f} Pcs (GAP)")
            m3.metric("Achievement", f"{monthly_ach:.1f}%")
        
            # Indikator Sekunder
            st.write("")
            b1, b2, b3 = st.columns(3)
            b1.metric("Bobot Pencapaian", f"{bobot_pencapaian:.2f}", help="Rumus: Achievement % x 20")
            b2.metric("Time Factor", f"{time_factor_val:.1f}%")
            
            with b3:
                st.markdown(f"""
                <div style='background-color: #1e293b; padding: 12px 14px; border-radius: 8px; border: 1px solid #334155; text-align: center;'>
                    <span style='font-size: 12px; color: #94a3b8; display: block;'>Status Performa</span>
                    <span style='font-size: 14px; font-weight: bold; color: {status_color}; margin-top: 4px; display: block;'>{status_label}</span>
                </div>
                """, unsafe_allow_html=True)
        
            # Pesan Motivasi
            st.write("")
            if monthly_ach >= 100:
                st.success(f"🌟 Luar biasa! Performa bulan **{selected_bulan_str} {selected_tahun}** ini benar-benar bersinar terang. Pertahankan konsistensi tim yang hebat ini! 💪✨")
            elif monthly_ach >= 80:
                st.info(f"☕ Hebat banget! Bulan **{selected_bulan_str} {selected_tahun}** sudah berjalan di jalur yang positif. Tinggal sedikit dorongan lagi! 🚀🔥")
            else:
                st.warning(f"💡 Semangat terus untuk tim di bulan **{selected_bulan_str} {selected_tahun}**! Setiap angka adalah proses belajar. Pacu strategi baru! 🎯❤️")
    
    
    # --- HALAMAN 2: REPORT SALES TOKO ---
    elif st.session_state.dash_page == "SalesToko":
        st.markdown("### 💰 Report Sales Toko")
        
        tab_st1, tab_st2 = st.tabs(["📌 Net Sales & GM", "🧾 NSB Toko"])
        
        with tab_st1:
            st.markdown("##### Menu Net Sales, GM% & Budget SO")
            net_sales = st.number_input("Net Sales (Rp):", value=0, step=100000, key="ns_input")
            gm_persen = st.number_input("GM (%):", value=0.0, step=0.1, key="gm_input")
            
            gm_rupiah = net_sales * (gm_persen / 100)
            budget_so = st.number_input("Budget SO (Rp):", value=0, step=10000, key="bso_input")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.metric("GM Rupiah (Net Sales x GM%)", f"Rp {gm_rupiah:,.2f}")
            st.success(f"**Budget SO:** Rp {budget_so:,.2f}")

        with tab_st2:
            st.markdown("##### Menu NSB Toko")
            sales_toko = st.number_input("Sales Toko (Rp):", value=0, step=100000, key="st_input")
            
            budget_nbh = sales_toko * 0.0015
            adjust_so = st.number_input("Adjust SO (Rp):", value=0, step=10000, key="adj_input")
            total_nbh = budget_nbh - adjust_so
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.metric("Budget NBH (Sales x 0.15%)", f"Rp {budget_nbh:,.2f}")
            st.metric("Total NBH (Budget NBH - Adjust SO)", f"Rp {total_nbh:,.2f}")

    # --- HALAMAN 3: REPORT PPS TOKO ---
    elif st.session_state.dash_page == "PPSToko":
        st.markdown("### 🛒 Report PPS Toko")
        
        pps_menu_choice = st.selectbox("Pilih Kategori PPS:", [
            "Report PPS (APC, PSM, PWP, Serba Gratis)", 
            "Menu Sueger & Cemilan Ceban", 
            "Simulasi PPS Toko"
        ])
        
        st.markdown("---")
        
        if pps_menu_choice == "Report PPS (APC, PSM, PWP, Serba Gratis)":
            st.markdown("##### Indikator PPS Toko")
            c_p1, c_p2 = st.columns(2)
            c_p1.metric("APC Toko", "0")
            c_p1.metric("PSM Toko", "0")
            c_p2.metric("PWP Toko", "0")
            c_p2.metric("Serba Gratis Toko", "0")
            
        elif pps_menu_choice == "Menu Sueger & Cemilan Ceban":
            st.markdown("##### 🥤 Report Sueger & Cemilan Ceban")
            st.write("Monitoring pencapaian produk Sueger dan Cemilan Ceban.")
            
        else:
            st.markdown("##### 🧮 Simulasi PPS Toko")
            sim_val = st.slider("Atur Target Simulasi PPS", 0, 100, 50, key="sim_pps_slider")
            st.info(f"Proyeksi Hasil Simulasi: **{sim_val * 1.2:.1f} Poin**")

    # --- HALAMAN 4: REPORT STD & MEMBER ---
    elif st.session_state.dash_page == "StdMember":
        st.markdown("### 👥 Report STD & Kontribusi Member Toko")
        st.write("Analisis performa Sales Through Department (STD) serta persentase kontribusi member belanja di toko.")
        
        sm1, sm2 = st.columns(2)
        sm1.metric("Rata-rata STD", "0.00")
        sm2.metric("Kontribusi Member", "0.0%")
        st.info("Data grafik harian akan dimuat dari database Google Sheets.")

# =========================================================
# TAB 02: RAPORT PERSONIL TOKO
# =========================================================
elif selected_tab == "02 Raport Personil":
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
# TAB 03: INPUT LAPORAN
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
