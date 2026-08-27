import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
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
# TAB 01: DASHBOARD - HALAMAN 1: REPORT PSM
# =========================================================
elif selected_tab == "01 Dashboard":
    
    if "dash_page" not in st.session_state:
        st.session_state.dash_page = "Main"

    # Tombol Kembali jika berada di dalam sub-menu
    if st.session_state.dash_page != "Main":
        if st.button("⬅️ Kembali ke Menu Utama Dashboard", key="btn_back_dash", use_container_width=True):
            st.session_state.dash_page = "Main"
            st.session_state.active_detail_view = None
            st.rerun()
        st.markdown("<hr style='margin: 8px 0; border-color: #334155;'>", unsafe_allow_html=True)

    # --- TAMPILAN UTAMA DASHBOARD (MENU GRID 2x2) ---
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

    # =========================================================
    # HALAMAN 1: REPORT PSM
    # =========================================================
    elif st.session_state.dash_page == "PSM":
        
        today_date = waktu_wib.date() if 'waktu_wib' in locals() else datetime.now().date()
        active_date = st.session_state.get("calendar_psm_harian", today_date)

        # Sub-halaman: Detail Kontributor Harian (Donut Chart & Status Input)
        if st.session_state.get("active_detail_view") == "detail_kontributor":
            if st.button("⬅️ Kembali ke Report PSM", key="btn_back_psm_main", use_container_width=True):
                st.session_state.active_detail_view = None
                st.rerun()
            st.markdown("<hr style='margin: 8px 0; border-color: #334155;'>", unsafe_allow_html=True)
            
            st.markdown(f"### 🍩 Detail Kontribusi Personil Harian (Tanggal: {active_date})")
            
            df_sp_detail = st.session_state.get("sales_person_df", pd.DataFrame())
            df_person_master = st.session_state.get("person_df", pd.DataFrame())
            
            if not df_sp_detail.empty:
                date_col_sp = next((c for c in df_sp_detail.columns if "updated_at" in c or "date" in c or "tanggal" in c), None)
                p_col = next((c for c in df_sp_detail.columns if "person_name" in c or "sales_person" in c), None)
                a_col = next((c for c in df_sp_detail.columns if "actual_qty" in c or "actual" in c), None)
                
                if p_col and a_col:
                    sub_sp_dt = df_sp_detail.copy()
                    
                    if date_col_sp:
                        sub_sp_dt["dt_clean"] = pd.to_datetime(sub_sp_dt[date_col_sp], errors="coerce").dt.date
                        sub_sp_dt = sub_sp_dt[sub_sp_dt["dt_clean"] == active_date]
                    
                    sub_sp_dt[a_col] = pd.to_numeric(sub_sp_dt[a_col], errors="coerce").fillna(0)
                    df_contrib = sub_sp_dt.groupby(p_col)[a_col].sum().reset_index()
                    df_contrib.columns = ["Nama Personil", "Total Actual Qty"]
                    
                    if not df_person_master.empty:
                        master_name_col = next((c for c in df_person_master.columns if "person_name" in c or "name" in c), None)
                        if master_name_col:
                            all_persons = df_person_master[master_name_col].dropna().unique()
                            
                            full_person_data = []
                            for p in all_persons:
                                matched_row = df_contrib[df_contrib["Nama Personil"] == p]
                                qty_val = matched_row["Total Actual Qty"].values[0] if not matched_row.empty else 0
                                status = "✅ Sudah Input" if not matched_row.empty and qty_val > 0 else "❌ Belum Input"
                                
                                full_person_data.append({
                                    "Nama Personil": p,
                                    "Total Actual Qty": qty_val,
                                    "Status Input": status
                                })
                            df_contrib = pd.DataFrame(full_person_data)
                    
                    total_all = df_contrib["Total Actual Qty"].sum()
                    df_contrib["Kontribusi (%)"] = df_contrib["Total Actual Qty"].apply(lambda x: f"{(x / total_all * 100):.1f}%" if total_all > 0 else "0.0%")
                    
                    col_dt1, col_dt2 = st.columns([1.3, 1])
                    with col_dt1:
                        st.markdown("##### 📋 Tabel Status & Kontribusi Personil")
                        st.dataframe(df_contrib, use_container_width=True, hide_index=True)
                    with col_dt2:
                        st.markdown("##### 📊 Grafik Donat Kontribusi")
                        df_active_chart = df_contrib[df_contrib["Total Actual Qty"] > 0]
                        if not df_active_chart.empty and total_all > 0:
                            import plotly.express as px
                            fig_donut = px.pie(df_active_chart, names="Nama Personil", values="Total Actual Qty", hole=0.5)
                            fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
                            st.plotly_chart(fig_donut, use_container_width=True)
                        else:
                            st.info("Belum ada data input pada tanggal ini untuk ditampilkan ke grafik.")
                else:
                    st.warning("Struktur kolom pada data sales personil tidak lengkap.")
            else:
                st.warning("Data sales personil kosong.")
                
        else:
            # Tampilan Utama Report PSM
            st.markdown("### 📈 Report Pencapaian PSM")
            
            psm_filter_options = ["☀️ Harian", "⏱️ Periode", "🗓️ Bulanan"]
            if hasattr(st, "pills"):
                view_mode = st.pills("Filter Waktu PSM", psm_filter_options, default="☀️ Harian", key="pills_psm_filter")
            else:
                view_mode = st.selectbox("Filter Waktu PSM:", psm_filter_options, key="select_psm_filter")
                
            st.markdown("<hr style='margin: 8px 0; border-color: #334155;'>", unsafe_allow_html=True)
            
            df_sales_item = st.session_state.get("sales_item_df", pd.DataFrame())
            df_periods = st.session_state.get("periods_df", pd.DataFrame())
            df_sales_person = st.session_state.get("sales_person_df", pd.DataFrame())
            
            # 1. MODE: HARIAN
            if view_mode == "☀️ Harian":
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
                if not sub_si.empty and "item_name" in sub_si.columns:
                    date_col_si_top = next((c for c in sub_si.columns if "updated_at" in c or "date" in c or "tanggal" in c), None)
                    if date_col_si_top:
                        sub_si["dt_clean"] = pd.to_datetime(sub_si[date_col_si_top], errors="coerce").dt.date
                        day_si = sub_si[sub_si["dt_clean"] == selected_daily_date]
                    else:
                        day_si = sub_si.copy()
                        
                    day_si["actual_qty"] = pd.to_numeric(day_si.get("actual_qty", 0), errors="coerce").fillna(0)
                    top_i_df = day_si.groupby("item_name")["actual_qty"].sum().reset_index()
                    if not top_i_df.empty and top_i_df["actual_qty"].max() > 0:
                        top_item = top_i_df.sort_values(by="actual_qty", ascending=False).iloc[0]["item_name"]

                # Kartu Top Contributor & Top Item
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

                tot_target_full = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0).sum() if not sub_si.empty and "target_qty" in sub_si.columns else 0
                total_days = 30
                daily_target = tot_target_full / total_days if total_days > 0 else 0
                daily_actual = day_sp["actual_qty"].sum() if not day_sp.empty else 0
                daily_gap = daily_target - daily_actual
                daily_ach = (daily_actual / daily_target * 100) if daily_target > 0 else 0

                g_col1, g_col2 = st.columns(2)
                g_col1.metric("🎯 Target Hari Ini", f"{daily_target:,.0f} Pcs")
                g_col2.metric("📦 Actual Sales", f"{daily_actual:,.0f} Pcs")

                st.markdown("<br>", unsafe_allow_html=True)
                g_col3, g_col4 = st.columns(2)
                g_col3.metric("📉 Sisa Gap Harian", f"{max(daily_gap, 0):,.0f} Pcs")
                g_col4.metric("⚡ % Ach Harian", f"{daily_ach:.1f}%")

            # 2. MODE: PERIODE
            elif view_mode == "⏱️ Periode":
                st.markdown("##### ⏱️ Pencapaian PSM Berdasarkan Periode")
                if not df_periods.empty and "period_name" in df_periods.columns:
                    st.selectbox("Pilih Periode:", df_periods["period_name"].unique(), key="sel_period_psm")
                else:
                    st.selectbox("Pilih Periode:", ["Periode 1", "Periode 2"], key="sel_period_dummy")
                
                st.markdown("<br>", unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Target Periode", "0 Pcs")
                m2.metric("Actual Periode", "0 Pcs")
                m3.metric("Achievement", "0.0%")

            # 3. MODE: BULANAN
            else:
                st.markdown("##### 🗓️ Pencapaian PSM Bulanan")
                st.selectbox("Pilih Bulan:", ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"], key="sel_bulan_psm")
                
                st.markdown("<br>", unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Target Bulanan", "0 Pcs")
                m2.metric("Actual Bulanan", "0 Pcs")
                m3.metric("Achievement", "0.0%")

            # --- BAGIAN GRAFIK (GRAFIK PENJUALAN HARIAN PER PERIODE) ---
            st.markdown("<br>", unsafe_allow_html=True)
            active_date_val = locals().get('selected_daily_date', today_date)
            
            # 1. Cari rentang tanggal dari df_periode yang mencakup active_date_val
            start_periode = None
            end_periode = None
            label_periode = "Periode Aktif"
            
            if 'df_periode' in locals() and not df_periode.empty:
                col_start = next((c for c in df_periode.columns if "start" in c or "mulai" in c), None)
                col_end = next((c for c in df_periode.columns if "end" in c or "selesai" in c), None)
                col_name = next((c for c in df_periode.columns if "name" in c or "periode" in c), None)
                
                if col_start and col_end:
                    df_periode["dt_start"] = pd.to_datetime(df_periode[col_start], errors="coerce").dt.date
                    df_periode["dt_end"] = pd.to_datetime(df_periode[col_end], errors="coerce").dt.date
                    
                    matched_periode = df_periode[(df_periode["dt_start"] <= active_date_val) & (df_periode["dt_end"] >= active_date_val)]
                    
                    if not matched_periode.empty:
                        start_periode = matched_periode.iloc[0]["dt_start"]
                        end_periode = matched_periode.iloc[0]["dt_end"]
                        p_name = matched_periode.iloc[0][col_name] if col_name else "Periode"
                        label_periode = f"{p_name} ({start_periode.strftime('%d %b')} - {end_periode.strftime('%d %b %Y')})"
            
            # Judul Utama Sesuai Permintaan
            st.markdown(f"##### 📊 GRAFIK PENJUALAN HARIAN PER PERIODE ({label_periode})")
            
            if not df_sales_item.empty:
                date_col_si = next((c for c in df_sales_item.columns if "updated_at" in c or "date" in c or "tanggal" in c), None)
                item_name_col = next((c for c in df_sales_item.columns if "item_name" in c or "name" in c), None)
                actual_qty_col = next((c for c in df_sales_item.columns if "actual_qty" in c or "actual" in c), None)
                
                if item_name_col and actual_qty_col:
                    sub_item_df = df_sales_item.copy()
                    
                    if date_col_si and start_periode and end_periode:
                        sub_item_df["dt_clean"] = pd.to_datetime(sub_item_df[date_col_si], errors="coerce").dt.date
                        sub_item_df = sub_item_df[(sub_item_df["dt_clean"] >= start_periode) & (sub_item_df["dt_clean"] <= end_periode)]
                    
                    if not sub_item_df.empty:
                        sub_item_df["actual_qty"] = pd.to_numeric(sub_item_df[actual_qty_col], errors="coerce").fillna(0)
                        df_grouped = sub_item_df.groupby(item_name_col)["actual_qty"].sum().reset_index()
                        df_grouped.columns = ["Nama Item", "Actual Qty"]
                        
                        sum_actual = df_grouped["Actual Qty"].sum()
                        df_grouped["Kontribusi (%)"] = df_grouped["Actual Qty"].apply(lambda x: f"{(x / sum_actual * 100):.1f}%" if sum_actual > 0 else "0.0%")
                        
                        col_tbl, col_chart = st.columns([1.2, 1])
                        with col_tbl:
                            st.dataframe(df_grouped, use_container_width=True, hide_index=True)
                            
                        with col_chart:
                            import plotly.express as px
                            fig_bar = px.bar(
                                df_grouped, 
                                x="Nama Item", 
                                y="Actual Qty", 
                                title=f"Grafik Penjualan per Item",
                                color="Actual Qty",
                                color_continuous_scale="blues"
                            )
                            fig_bar.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=350)
                            st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.info(f"Tidak ada data item terjual pada rentang periode ini.")
                else:
                    st.warning("Struktur kolom 'item_name' atau 'actual_qty' tidak ditemukan pada sheet SALES_ITEM.")
            else:
                st.info("Belum ada data rincian item PSM yang dimuat.")



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


