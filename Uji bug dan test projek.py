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
# (Harus ditaruh di baris paling awal dari perintah Streamlit!)
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

# Load Data ke Session State saat pertama kali dibuka
if "data_loaded" not in st.session_state:
    p_df, i_df, pers_df, si_df, sp_df = load_database()
    st.session_state.periods_df = p_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.data_loaded = True

# Alias Variabel Lokal agar mudah dipanggil di skrip bawahnya
df_periode = st.session_state.get("periods_df", pd.DataFrame())
df_sales_item = st.session_state.get("sales_item_df", pd.DataFrame())
df_sales_person = st.session_state.get("sales_person_df", pd.DataFrame())

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Home"

waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%A, %d %B %Y %H:%M WIB")

# Fungsi Authentication
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
        
        # Tampilan tombol segmented modern
        view_mode = st.segmented_control(
            "Pilihan Mode Tampilan:",
            options=["☀️ Harian", "⏱️ Periode", "🗓️ Bulanan"],
            default="☀️ Harian",
            key="seg_psm_mode"
        )
        st.markdown("---")

        today_date = waktu_wib.date() if 'waktu_wib' in locals() and hasattr(waktu_wib, 'date') else datetime.now().date()
        
        if view_mode == "☀️ Harian":
            selected_daily_date = st.date_input(
                "📅 Pilih Tanggal Laporan:",
                value=st.session_state.get("calendar_psm_harian", today_date),
                key="calendar_psm_harian"
            )
        else:
            selected_daily_date = st.session_state.get("calendar_psm_harian", today_date)

        # Standardisasi dataframes agar tidak error NameError
        df_periods = st.session_state.get("periods_df", pd.DataFrame())
        df_sales_person = st.session_state.get("sales_person_df", pd.DataFrame())
        df_sales_item = st.session_state.get("sales_item_df", pd.DataFrame())

        # 1. MODE HARIAN
        if view_mode == "☀️ Harian":
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
        
            # Kartu TOP CONTRIBUTOR dan TOP ITEM (Tanpa Tombol Klik Detail)
            tc1, tc2 = st.columns(2)
            with tc1:
                st.markdown(f"""
                <div class='app-card' style='padding: 12px; margin-bottom: 5px; background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;'>
                    <span style='color:#94a3b8; font-size:11px; font-weight: bold;'>🥇 TOP CONTRIBUTOR</span>
                    <p style='color:#00f0ff; font-size:16px; font-weight:bold; margin:4px 0 0 0;'>{top_person}</p>
                </div>
                """, unsafe_allow_html=True)
                    
            with tc2:
                st.markdown(f"""
                <div class='app-card' style='padding: 12px; margin-bottom: 5px; background-color: #1e293b; border-radius: 8px; border: 1px solid #334155;'>
                    <span style='color:#94a3b8; font-size:11px; font-weight: bold;'>📦 TOP ITEM</span>
                    <p style='color:#38bdf8; font-size:16px; font-weight:bold; margin:4px 0 0 0;'>{top_item}</p>
                </div>
                """, unsafe_allow_html=True)
        
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

            selected_month_num = list_bulan.index(selected_bulan_str) + 1

            sub_target = df_sales_item.copy() if not df_sales_item.empty else pd.DataFrame()
            sub_periode = df_periods.copy() if not df_periods.empty else pd.DataFrame()
        
            monthly_target = 0.0
            monthly_actual = 0.0
        
            if not sub_target.empty:
                if "period_id" in sub_target.columns and not sub_periode.empty:
                    cols_to_use = [c for c in sub_periode.columns if c not in sub_target.columns or c == "period_id"]
                    sub_target = sub_target.merge(sub_periode[cols_to_use], on="period_id", how="left")

                df_filtered_bulan = pd.DataFrame()
                
                if "start_date" in sub_target.columns:
                    sub_target["start_date_dt"] = pd.to_datetime(sub_target["start_date"], errors="coerce")
                    df_filtered_bulan = sub_target[
                        (sub_target["start_date_dt"].dt.month == selected_month_num) & 
                        (sub_target["start_date_dt"].dt.year == selected_tahun)
                    ]
                
                if df_filtered_bulan.empty and "period_name" in sub_target.columns:
                    df_filtered_bulan = sub_target[
                        sub_target["period_name"].astype(str).str.contains(selected_bulan_str, case=False, na=False) &
                        sub_target["period_name"].astype(str).str.contains(str(selected_tahun), case=False, na=False)
                    ]

                if not df_filtered_bulan.empty:
                    if "target_qty" in df_filtered_bulan.columns:
                        monthly_target = float(pd.to_numeric(df_filtered_bulan["target_qty"], errors="coerce").fillna(0).sum())
                    
                    if "actual_qty" in df_filtered_bulan.columns:
                        monthly_actual = float(pd.to_numeric(df_filtered_bulan["actual_qty"], errors="coerce").fillna(0).sum())
        
            monthly_gap = monthly_actual - monthly_target  
            monthly_ach = (monthly_actual / monthly_target * 100.0) if monthly_target > 0 else 0.0
            bobot_pencapaian = (monthly_ach / 100.0) * 20.0
            time_factor_val = 100.0  
            
            if monthly_ach >= time_factor_val:
                status_label = "🔥 Achieved (Sangat On Track)"
                status_color = "#10b981" 
            elif monthly_ach >= (time_factor_val * 0.8):
                status_label = "⚠️ Near Target (Kejar Dikit Lagi)"
                status_color = "#f59e0b" 
            else:
                status_label = "❌ Off Track (Perlu Pergerakan Ekstra)"
                status_color = "#ef4444" 
        
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Target Bulanan", f"{monthly_target:,.0f} Pcs")
            m2.metric("Actual Bulanan", f"{monthly_actual:,.0f} Pcs", delta=f"{monthly_gap:+,.0f} Pcs (GAP)")
            m3.metric("Achievement", f"{monthly_ach:.1f}%")
        
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

    # 1. BACA PARAMETER URL UNTUK TOMBOL BACK BROWSER/HP
    query_params = st.query_params
    current_sub_page = query_params.get("sub_page", "MENU_UTAMA")

    # Sync state dengan URL
    st.session_state.sub_page_raport = current_sub_page

    # --- CSS GAYA KARD ANDROID KLIK UTUH & SEGMENTED KAPSUL ---
    st.markdown("""
    <style>
        /* Segmented Control Mode Kapsul */
        div[data-baseweb="segmented-control"] {
            border-radius: 9999px !important;
            padding: 4px !important;
            background-color: #1e293b !important;
        }
        div[data-baseweb="segmented-control"] button {
            border-radius: 9999px !important;
            border: none !important;
            transition: all 0.3s ease !important;
        }
        
        /* Desain Card Utuh yang Bisa Diklik */
        div[data-testid="stVerticalBlockBorderWrapper"] .android-card-box {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 24px 16px;
            text-align: center;
            transition: all 0.25s ease;
            cursor: pointer;
        }
        
        div[data-testid="stVerticalBlockBorderWrapper"]:hover .android-card-box {
            border-color: #00f0ff;
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(0, 240, 255, 0.15);
        }

        /* Merubah Tombol Streamlit Menjadi Kapsul / Menyatu dengan Card */
        .stButton > button {
            border-radius: 9999px !important;
            font-weight: bold !important;
            transition: all 0.2s ease !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # HALAMAN 1: DASHBOARD MENU UTAMA
    # ---------------------------------------------------------
    if st.session_state.sub_page_raport == "MENU_UTAMA":
        st.markdown("### 🏆 Raport Personil Toko")
        st.write("Pilih menu laporan personil di bawah ini:")
        st.markdown("<br>", unsafe_allow_html=True)
    
        col1, col2, col3 = st.columns(3)
    
        # --- CARD 1: PENJUALAN PERSONIL ---
        with col1:
            with st.container(border=True):
                st.markdown("""
                <div style='text-align: center; padding: 10px 0;'>
                    <div style='font-size: 42px; margin-bottom: 8px;'>📊</div>
                    <div style='font-weight: bold; color: #f8fafc; font-size: 16px;'>Penjualan Personil</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Buka Laporan 📊", key="card_btn_penjualan", use_container_width=True):
                    st.query_params["sub_page"] = "PENJUALAN"
                    st.session_state.sub_page_raport = "PENJUALAN"
                    st.rerun()
    
        # --- CARD 2: RANGKING PSM ---
        with col2:
            with st.container(border=True):
                st.markdown("""
                <div style='text-align: center; padding: 10px 0;'>
                    <div style='font-size: 42px; margin-bottom: 8px;'>🥇</div>
                    <div style='font-weight: bold; color: #f8fafc; font-size: 16px;'>Rangking PSM Toko</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Lihat Rangking 🥇", key="card_btn_psm", use_container_width=True):
                    st.query_params["sub_page"] = "RANK_PSM"
                    st.session_state.sub_page_raport = "RANK_PSM"
                    st.rerun()
    
        # --- CARD 3: RANGKING PPS ---
        with col3:
            with st.container(border=True):
                st.markdown("""
                <div style='text-align: center; padding: 10px 0;'>
                    <div style='font-size: 42px; margin-bottom: 8px;'>🎯</div>
                    <div style='font-weight: bold; color: #f8fafc; font-size: 16px;'>Rangking PPS Toko</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Lihat Rangking 🎯", key="card_btn_pps", use_container_width=True):
                    st.query_params["sub_page"] = "RANK_PPS"
                    st.session_state.sub_page_raport = "RANK_PPS"
                    st.rerun()
    
    # ---------------------------------------------------------
    # HALAMAN 2: DETAIL PENJUALAN PERSONIL TOKO (FULL RPG & ISOLATED MONTH)
    # ---------------------------------------------------------
    elif st.session_state.sub_page_raport == "PENJUALAN":
        if st.button("⬅️ Kembali ke Menu Utama", key="btn_back_1"):
            st.query_params["sub_page"] = "MENU_UTAMA"
            st.session_state.sub_page_raport = "MENU_UTAMA"
            st.rerun()
            
        st.markdown("### 📊 Raport Penjualan Personil")
        st.markdown("---")
    
        df_periods = st.session_state.get("periods_df", pd.DataFrame())
        df_sales_person = st.session_state.get("sales_person_df", pd.DataFrame())
        df_sales_item = st.session_state.get("sales_item_df", pd.DataFrame())
    
        # STYLESHEET TEMA RPG & HP BARS
        st.markdown("""
        <style>
            .rpg-card {
                background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%);
                border: 2px solid #38bdf8;
                border-radius: 16px;
                padding: 20px;
                box-shadow: 0 0 15px rgba(56, 189, 248, 0.2);
                margin-bottom: 20px;
            }
            .avatar-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                margin-bottom: 12px;
            }
            .avatar-img {
                width: 90px;
                height: 90px;
                border-radius: 50%;
                border: 3px solid #00f0ff;
                box-shadow: 0 0 12px #00f0ff;
                background-color: #334155;
            }
            .stat-box {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 10px;
                text-align: center;
            }
            .stat-label {
                color: #94a3b8;
                font-size: 11px;
                font-weight: bold;
            }
            .stat-value {
                color: #f8fafc;
                font-size: 17px;
                font-weight: bold;
                margin-top: 2px;
            }
            .hp-bar-bg {
                background-color: #334155;
                border-radius: 10px;
                height: 16px;
                width: 100%;
                overflow: hidden;
                margin-top: 4px;
                position: relative;
                border: 1px solid #475569;
            }
            .hp-bar-fill {
                height: 100%;
                border-radius: 10px;
                transition: width 0.4s ease;
            }
            .item-hp-card {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 14px;
                margin-bottom: 12px;
            }
            .hp-bar-text {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 10px;
                font-weight: bold;
                color: #ffffff;
                text-shadow: 1px 1px 2px #000;
                width: 100%;
                text-align: center;
            }
        </style>
        """, unsafe_allow_html=True)
    
        # 1. FILTER PILIHAN BULAN, PERIODE & PERSONIL
        list_bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            selected_bulan_str = st.selectbox("📅 Pilih Bulan:", list_bulan, index=7, key="rpg_sel_bulan")
            selected_month_num = list_bulan.index(selected_bulan_str) + 1
    
        period_options = ["Semua Periode"]
        target_period_ids = []
    
        if not df_periods.empty and "start_date" in df_periods.columns:
            df_periods_copy = df_periods.copy()
            df_periods_copy["start_dt"] = pd.to_datetime(df_periods_copy["start_date"], errors="coerce")
            filtered_periods = df_periods_copy[df_periods_copy["start_dt"].dt.month == selected_month_num]
            
            if not filtered_periods.empty:
                if "period_name" in filtered_periods.columns:
                    period_options += filtered_periods["period_name"].tolist()
                if "period_id" in filtered_periods.columns:
                    target_period_ids = filtered_periods["period_id"].tolist()
    
        with col_f2:
            selected_period_name = st.selectbox("⏱️ Pilih Periode:", period_options, key="rpg_sel_periode")
    
        selected_period_id = None
        if selected_period_name != "Semua Periode" and not df_periods.empty:
            p_row = df_periods[df_periods["period_name"] == selected_period_name]
            if not p_row.empty and "period_id" in p_row.columns:
                selected_period_id = p_row.iloc[0]["period_id"]
    
        person_list = ["Pilih Personil"]
        if not df_sales_person.empty:
            person_col = next((c for c in df_sales_person.columns if "person_name" in c or "sales_person" in c or "nama" in c), None)
            if person_col:
                person_list += sorted(df_sales_person[person_col].dropna().unique().tolist())
    
        with col_f3:
            selected_person = st.selectbox("👤 Pilih Personil (User):", person_list, key="rpg_sel_person")
    
        st.markdown("<br>", unsafe_allow_html=True)
    
        # 2. PROSES STATISTIK PERSONIL
        if selected_person != "Pilih Personil":
            sub_sp_all = df_sales_person.copy() if not df_sales_person.empty else pd.DataFrame()
            person_col = next((c for c in sub_sp_all.columns if "person_name" in c or "sales_person" in c or "nama" in c), None)
            
            # --- A. LEVELING RPG PERMANEN (SEPANJANG MASA) ---
            total_qty_all_time = 0.0
            if person_col and not sub_sp_all.empty:
                sp_user_all = sub_sp_all[sub_sp_all[person_col] == selected_person]
                if "actual_qty" in sp_user_all.columns:
                    total_qty_all_time = float(pd.to_numeric(sp_user_all["actual_qty"], errors="coerce").fillna(0).sum())
    
            EXP_PER_LEVEL = 100 
            user_level = int(total_qty_all_time // EXP_PER_LEVEL) + 1
            current_level_exp = total_qty_all_time % EXP_PER_LEVEL
            exp_progress_pct = (current_level_exp / EXP_PER_LEVEL) * 100.0
    
            # --- B. FILTER PENJUALAN KHUSUS BULAN / PERIODE TERPILIH ---
            sub_sp = sub_sp_all[sub_sp_all[person_col] == selected_person] if person_col and not sub_sp_all.empty else pd.DataFrame()
            sub_si = df_sales_item.copy() if not df_sales_item.empty else pd.DataFrame()
    
            if selected_period_id is not None:
                if "period_id" in sub_sp.columns:
                    sub_sp = sub_sp[sub_sp["period_id"] == selected_period_id]
                if "period_id" in sub_si.columns:
                    sub_si = sub_si[sub_si["period_id"] == selected_period_id]
            else:
                if target_period_ids:
                    if "period_id" in sub_sp.columns:
                        sub_sp = sub_sp[sub_sp["period_id"].isin(target_period_ids)]
                    if "period_id" in sub_si.columns:
                        sub_si = sub_si[sub_si["period_id"].isin(target_period_ids)]
    
            actual_qty_person_period = 0.0
            if not sub_sp.empty and "actual_qty" in sub_sp.columns:
                actual_qty_person_period = float(pd.to_numeric(sub_sp["actual_qty"], errors="coerce").fillna(0).sum())
    
            # --- C. PROSES DATA TARGET KASIR DARI TABLE SALES_ITEM ---
            total_item_achieved = 0
            df_item_summary = pd.DataFrame()
            total_target_kasir_period = 0.0
    
            if not sub_si.empty and "item_name" in sub_si.columns:
                if "target_kasir" in sub_si.columns:
                    sub_si["target_kasir"] = pd.to_numeric(sub_si["target_kasir"], errors="coerce").fillna(0)
                elif "target_qty" in sub_si.columns:
                    sub_si["target_qty"] = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0)
                    sub_si["target_kasir"] = sub_si["target_qty"].apply(lambda x: math.ceil(x / 3.0))
                else:
                    sub_si["target_kasir"] = 0
    
                df_target_summary = sub_si.groupby("item_name")["target_kasir"].sum().reset_index()
    
                if not sub_sp.empty and "item_name" in sub_sp.columns and "actual_qty" in sub_sp.columns:
                    df_actual_summary = sub_sp.groupby("item_name")["actual_qty"].sum().reset_index()
                    df_item_summary = df_target_summary.merge(df_actual_summary, on="item_name", how="left")
                else:
                    df_item_summary = df_target_summary.copy()
                    df_item_summary["actual_qty"] = 0
    
                df_item_summary["target_kasir"] = pd.to_numeric(df_item_summary["target_kasir"], errors="coerce").fillna(0)
                df_item_summary["actual_qty"] = pd.to_numeric(df_item_summary["actual_qty"], errors="coerce").fillna(0)
    
                total_target_kasir_period = float(df_item_summary["target_kasir"].sum())
    
                for _, row in df_item_summary.iterrows():
                    tk = row["target_kasir"]
                    if tk > 0 and row["actual_qty"] >= tk:
                        total_item_achieved += 1
    
            ach_person_pct = (actual_qty_person_period / total_target_kasir_period * 100.0) if total_target_kasir_period > 0 else 0.0
    
            avatar_url = f"https://api.dicebear.com/7.x/bottts/svg?seed={selected_person}"
    
            # RENDER RPG PROFILE CARD (PERMANENT LEVEL)
            html_card = f"""
            <div class='rpg-card'>
                <div class='avatar-container'>
                    <img src='{avatar_url}' class='avatar-img' alt='Avatar'>
                    <h3 style='color: #00f0ff; margin: 8px 0 2px 0; text-align: center; font-size: 20px;'>{selected_person}</h3>
                    <span style='color: #e2e8f0; background: #0284c7; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;'>
                        LEVEL {user_level} • TOTAL SALES: {total_qty_all_time:,.0f} PCS
                    </span>
                </div>
                <div style='margin-bottom: 14px;'>
                    <div style='display: flex; justify-content: space-between; font-size: 11px; font-weight: bold;'>
                        <span style='color: #94a3b8;'>LEVEL PROGRESS ({current_level_exp:,.0f}/{EXP_PER_LEVEL} PCS)</span>
                        <span style='color: #00f0ff;'>{exp_progress_pct:.1f}%</span>
                    </div>
                    <div class='hp-bar-bg'>
                        <div class='hp-bar-fill' style='width: {exp_progress_pct}%; background: linear-gradient(90deg, #00f0ff 0%, #3b82f6 100%);'></div>
                    </div>
                </div>
                <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;'>
                    <div class='stat-box'>
                        <div class='stat-label'>🎯 TARGET ({selected_bulan_str[:3]})</div>
                        <div class='stat-value' style='color: #cbd5e1;'>{total_target_kasir_period:,.0f}</div>
                    </div>
                    <div class='stat-box'>
                        <div class='stat-label'>📦 ACTUAL ({selected_bulan_str[:3]})</div>
                        <div class='stat-value' style='color: #38bdf8;'>{actual_qty_person_period:,.0f}</div>
                    </div>
                    <div class='stat-box'>
                        <div class='stat-label'>⚡ ACH (%)</div>
                        <div class='stat-value' style='color: #10b981;'>{ach_person_pct:.1f}%</div>
                    </div>
                    <div class='stat-box'>
                        <div class='stat-label'>🏆 TARGET DONE</div>
                        <div class='stat-value' style='color: #f59e0b;'>{total_item_achieved} Item</div>
                    </div>
                </div>
            </div>
            """
            st.markdown(html_card, unsafe_allow_html=True)
    
            # 3. BAR ITEM PENJUALAN BERGAYA HP BAR RPG (QUEST ITEM ACHIEVEMENTS)
            st.markdown(f"##### 🗡️ Quest Item Achievements - {selected_bulan_str} ({selected_period_name})")
    
            if not df_item_summary.empty:
                for _, row in df_item_summary.iterrows():
                    item_name = row["item_name"]
                    actual = int(row["actual_qty"])
                    target_kasir = int(row["target_kasir"])
                    
                    ach_pct = (actual / target_kasir * 100.0) if target_kasir > 0 else 0.0
                    ach_pct_clamped = min(max(ach_pct, 0.0), 100.0)
                    gap_qty = max(target_kasir - actual, 0)
    
                    if target_kasir == 0:
                        bar_label = "TIDAK ADA TARGET"
                        bar_color = "#475569"
                    elif gap_qty == 0:
                        bar_label = "TARGET REACHED! 🎉"
                        bar_color = "linear-gradient(90deg, #10b981 0%, #059669 100%)"
                    else:
                        bar_label = f"Sisa Gap: {gap_qty} Pcs"
                        bar_color = "linear-gradient(90deg, #00f0ff 0%, #3b82f6 100%)"
    
                    item_card_html = f"""
                    <div class='item-hp-card'>
                        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;'>
                            <span style='font-weight: bold; color: #f8fafc; font-size: 14px;'>📦 {item_name}</span>
                            <span style='font-weight: bold; color: #38bdf8; font-size: 13px;'>
                                {actual} / {target_kasir} Pcs <span style='color: {"#10b981" if gap_qty==0 else "#00f0ff"};'>({ach_pct:.1f}%)</span>
                            </span>
                        </div>
                        <div class='hp-bar-bg'>
                            <div class='hp-bar-fill' style='width: {ach_pct_clamped}%; background: {bar_color};'></div>
                            <div class='hp-bar-text'>{bar_label}</div>
                        </div>
                    </div>
                    """
                    st.markdown(item_card_html, unsafe_allow_html=True)
            else:
                st.info(f"Belum ada target item yang ditetapkan untuk bulan **{selected_bulan_str}**.")
        else:
            st.info("👆 Silakan pilih nama **Personil (User)** pada dropdown di atas.")

    
    # ---------------------------------------------------------
    # HALAMAN 3: DETAIL RANGKING PSM TOKO (CYBERPUNK RPG LEADERBOARD)
    # ---------------------------------------------------------
    if st.session_state.get("sub_page_raport") == "RANK_PSM":
        if st.button("⬅️ Kembali ke Menu Utama", key="btn_back_2"):
            st.query_params["sub_page"] = "MENU_UTAMA"
            st.session_state.sub_page_raport = "MENU_UTAMA"
            st.rerun()
            
        st.markdown("### 🥇 Guild Leaderboard - Rangking PSM Toko")
        st.markdown("---")
    
        # 1. LOAD & PREPARE DATA FROM SESSION STATE
        df_periods = st.session_state.get("periods_df", pd.DataFrame())
        df_sales_person = st.session_state.get("sales_person_df", pd.DataFrame())
        df_sales_item = st.session_state.get("sales_item_df", pd.DataFrame())
        df_users = st.session_state.get("users_df", pd.DataFrame())
    
        # CSS STYLING KAPSUL RPG FUTURISTIK & PODIUM
        st.markdown("""
        <style>
            /* Tombol Kapsul Aktif (Glow Neon Cyan) */
            button[kind="primary"] {
                background: linear-gradient(135deg, #00f0ff 0%, #3b82f6 100%) !important;
                color: #0f172a !important;
                font-weight: 800 !important;
                font-size: 13px !important;
                letter-spacing: 0.5px !important;
                border: 1px solid #00f0ff !important;
                border-radius: 30px !important;
                box-shadow: 0 0 15px rgba(0, 240, 255, 0.6) !important;
                transition: all 0.3s ease !important;
            }
            
            /* Tombol Kapsul Non-Aktif (Dark Mode Glass) */
            button[kind="secondary"] {
                background: rgba(30, 41, 59, 0.6) !important;
                color: #94a3b8 !important;
                font-weight: 600 !important;
                font-size: 13px !important;
                border: 1px solid #334155 !important;
                border-radius: 30px !important;
                transition: all 0.3s ease !important;
            }
            
            button[kind="secondary"]:hover {
                color: #00f0ff !important;
                border: 1px solid rgba(0, 240, 255, 0.5) !important;
                background: rgba(30, 41, 59, 0.9) !important;
            }
    
            .podium-card {
                background: #1e293b;
                border-radius: 16px;
                padding: 16px;
                text-align: center;
            }
        </style>
        """, unsafe_allow_html=True)
    
        # 2. MODE SWITCHER KAPSUL FUTURISTIK
        if "psm_filter_mode" not in st.session_state:
            st.session_state.psm_filter_mode = "Bulanan"
    
        st.caption("⚔️ SELECT CAMPAIGN MODE")
        col_k1, col_k2, col_k3 = st.columns(3)
    
        with col_k1:
            type_daily = "primary" if st.session_state.psm_filter_mode == "Harian" else "secondary"
            if st.button("⚡ DAILY QUEST", use_container_width=True, type=type_daily, key="capsule_daily"):
                st.session_state.psm_filter_mode = "Harian"
                st.rerun()
    
        with col_k2:
            type_range = "primary" if st.session_state.psm_filter_mode == "Rentang Periode" else "secondary"
            if st.button("🛰️ CAMPAIGN PERIODE", use_container_width=True, type=type_range, key="capsule_range"):
                st.session_state.psm_filter_mode = "Rentang Periode"
                st.rerun()
    
        with col_k3:
            type_monthly = "primary" if st.session_state.psm_filter_mode == "Bulanan" else "secondary"
            if st.button("🌕 SEASONAL MONTH", use_container_width=True, type=type_monthly, key="capsule_monthly"):
                st.session_state.psm_filter_mode = "Bulanan"
                st.rerun()
    
        filter_mode = st.session_state.psm_filter_mode
        st.markdown("<br>", unsafe_allow_html=True)
    
        # 3. FILTER SELECTION COMPONENT
        start_date, end_date = None, None
        selected_month_num = None
        selected_period_name = None
        list_bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    
        if filter_mode == "Harian":
            single_date = st.date_input("📅 Pilih Tanggal Penjualan:", datetime.today().date(), key="psm_date_single")
            start_date = pd.to_datetime(single_date).normalize()
            end_date = start_date + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    
        elif filter_mode == "Rentang Periode":
            if df_periods is not None and not df_periods.empty and "periode_name" in df_periods.columns:
                list_periode = df_periods["period_name"].dropna().unique().tolist()
                selected_period_name = st.selectbox("📅 Pilih Campaign Periode:", list_periode, key="psm_periode_sel")
            else:
                st.warning("⚠️ Data Sheet PERIODE (kolom 'periode_name') tidak ditemukan.")
    
        elif filter_mode == "Bulanan":
            current_m = datetime.now().month - 1
            selected_bulan_str = st.selectbox("📅 Pilih Bulan Season:", list_bulan, index=current_m, key="psm_month_sel")
            selected_month_num = list_bulan.index(selected_bulan_str) + 1
    
        # 4. FILTER DATA PENJUALAN PERSONIL BERDASARKAN UPDATED_AT
        sub_sp = df_sales_person.copy() if df_sales_person is not None and not df_sales_person.empty else pd.DataFrame()
        
        person_col = next((c for c in sub_sp.columns if "person_name" in c or "sales_person" in c or "nama" in c), None) if not sub_sp.empty else None
        date_col = "updated_at" if "updated_at" in sub_sp.columns else ("trans_date" if "trans_date" in sub_sp.columns else None)
    
        # Master Karyawan Toko (Tetap Muncul Meski Sales = 0)
        all_employees = []
        if df_users is not None and not df_users.empty and "nama" in df_users.columns:
            all_employees = df_users["nama"].dropna().unique().tolist()
        elif person_col and not sub_sp.empty:
            all_employees = sub_sp[person_col].dropna().unique().tolist()
    
        if not sub_sp.empty and date_col:
            sub_sp["dt"] = pd.to_datetime(sub_sp[date_col], errors="coerce")
    
            if filter_mode == "Harian" and start_date is not None and end_date is not None:
                sub_sp = sub_sp[(sub_sp["dt"] >= start_date) & (sub_sp["dt"] <= end_date)]
                
            elif filter_mode == "Rentang Periode" and selected_period_name:
                if "periode_name" in sub_sp.columns:
                    sub_sp = sub_sp[sub_sp["periode_name"] == selected_period_name]
                elif df_periods is not None and not df_periods.empty and "periode_name" in df_periods.columns:
                    row_p = df_periods[df_periods["periode_name"] == selected_period_name]
                    if not row_p.empty and "start_date" in row_p.columns and "end_date" in row_p.columns:
                        p_start = pd.to_datetime(row_p.iloc[0]["start_date"]).normalize()
                        p_end = pd.to_datetime(row_p.iloc[0]["end_date"]).normalize() + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
                        sub_sp = sub_sp[(sub_sp["dt"] >= p_start) & (sub_sp["dt"] <= p_end)]
                        
            elif filter_mode == "Bulanan" and selected_month_num is not None:
                sub_sp = sub_sp[sub_sp["dt"].dt.month == selected_month_num]
    
        # Qty Total Seluruh Toko (Untuk Persentase Kontribusi)
        total_store_qty = 0.0
        if not sub_sp.empty and "actual_qty" in sub_sp.columns:
            sub_sp["actual_qty"] = pd.to_numeric(sub_sp["actual_qty"], errors="coerce").fillna(0)
            total_store_qty = float(sub_sp["actual_qty"].sum())
    
        # 5. HITUNG METRIK PERSONIL & AKUMULASI
        leaderboard_data = []
    
        for emp in all_employees:
            emp_sp = sub_sp[sub_sp[person_col] == emp] if person_col and not sub_sp.empty else pd.DataFrame()
            
            actual_qty = 0.0
            items_100_done = 0
    
            if not emp_sp.empty and "actual_qty" in emp_sp.columns:
                actual_qty = float(emp_sp["actual_qty"].sum())
    
                # Hitung Jumlah Item Yang Target 100% Achieved
                if "item_name" in emp_sp.columns:
                    emp_item_grp = emp_sp.groupby("item_name")["actual_qty"].sum().reset_index()
                    if df_sales_item is not None and not df_sales_item.empty and "item_name" in df_sales_item.columns:
                        target_col = "target_kasir" if "target_kasir" in df_sales_item.columns else "target_qty"
                        target_map = df_sales_item.groupby("item_name")[target_col].sum().to_dict()
                        
                        for _, irow in emp_item_grp.iterrows():
                            iname = irow["item_name"]
                            iqty = irow["actual_qty"]
                            itarget = target_map.get(iname, 0)
                            if itarget > 0 and iqty >= itarget:
                                items_100_done += 1
    
            kontribusi_pct = (actual_qty / total_store_qty * 100.0) if total_store_qty > 0 else 0.0
    
            leaderboard_data.append({
                "Nama Personil": emp,
                "Total Qty": actual_qty,
                "% Kontribusi": kontribusi_pct,
                "Target 100% Done": items_100_done
            })
    
        df_lb = pd.DataFrame(leaderboard_data)
    
        # URUTKAN RANGKING (QTY TERBANYAK & QUEST DONE)
        if not df_lb.empty:
            df_lb = df_lb.sort_values(by=["Total Qty", "Target 100% Done"], ascending=[False, False]).reset_index(drop=True)
            df_lb.index += 1
    
        # 6. PODIUM TOP 3 ADVENTURER (HTML RENDER CLEAN)
        st.markdown("<br>", unsafe_allow_html=True)
        if len(df_lb) >= 3:
            p1, p2, p3 = df_lb.iloc[0], df_lb.iloc[1], df_lb.iloc[2]
            
            podium_html = f"""
            <div style='display: flex; justify-content: center; align-items: flex-end; gap: 15px; margin-bottom: 30px;'>
                <div class='podium-card' style='border: 2px solid #94a3b8; width: 30%; box-shadow: 0 0 12px rgba(148, 163, 184, 0.2);'>
                    <div style='font-size: 32px;'>🥈</div>
                    <div style='font-weight: bold; color: #94a3b8; font-size: 15px;'>{p2["Nama Personil"]}</div>
                    <div style='font-size: 22px; font-weight: bold; color: #f8fafc; margin-top: 4px;'>{p2["Total Qty"]:,.0f} <span style='font-size: 11px;'>Pcs</span></div>
                    <div style='color: #00f0ff; font-size: 12px; font-weight: bold;'>{p2["% Kontribusi"]:.1f}% Kontribusi</div>
                    <div style='background: #334155; border-radius: 6px; padding: 4px; font-size: 11px; margin-top: 8px; color: #f59e0b;'>🏆 {p2["Target 100% Done"]} Item 100%</div>
                </div>
                
                <div class='podium-card' style='border: 3px solid #f59e0b; width: 36%; box-shadow: 0 0 25px rgba(245, 158, 11, 0.4); transform: scale(1.05); background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);'>
                    <div style='font-size: 42px;'>🥇</div>
                    <span style='background: #f59e0b; color: #0f172a; font-size: 10px; font-weight: 800; padding: 2px 10px; border-radius: 10px;'>GUILD MASTER</span>
                    <div style='font-weight: bold; color: #fbbf24; font-size: 18px; margin-top: 6px;'>{p1["Nama Personil"]}</div>
                    <div style='font-size: 26px; font-weight: bold; color: #f8fafc; margin-top: 4px;'>{p1["Total Qty"]:,.0f} <span style='font-size: 12px;'>Pcs</span></div>
                    <div style='color: #00f0ff; font-size: 13px; font-weight: bold;'>{p1["% Kontribusi"]:.1f}% Kontribusi</div>
                    <div style='background: #334155; border-radius: 6px; padding: 4px; font-size: 11px; margin-top: 8px; color: #f59e0b;'>🏆 {p1["Target 100% Done"]} Item 100%</div>
                </div>
    
                <div class='podium-card' style='border: 2px solid #d97706; width: 30%; box-shadow: 0 0 12px rgba(217, 119, 6, 0.2);'>
                    <div style='font-size: 32px;'>🥉</div>
                    <div style='font-weight: bold; color: #d97706; font-size: 15px;'>{p3["Nama Personil"]}</div>
                    <div style='font-size: 22px; font-weight: bold; color: #f8fafc; margin-top: 4px;'>{p3["Total Qty"]:,.0f} <span style='font-size: 11px;'>Pcs</span></div>
                    <div style='color: #00f0ff; font-size: 12px; font-weight: bold;'>{p3["% Kontribusi"]:.1f}% Kontribusi</div>
                    <div style='background: #334155; border-radius: 6px; padding: 4px; font-size: 11px; margin-top: 8px; color: #f59e0b;'>🏆 {p3["Target 100% Done"]} Item 100%</div>
                </div>
            </div>
            """
            st.markdown(podium_html, unsafe_allow_html=True)
    
        # 7. TABEL FULL ADVENTURER LEADERBOARD
        st.markdown("##### 📜 Full Adventurer Leaderboard")
    
        df_display = df_lb.copy()
        df_display["Total Qty"] = df_display["Total Qty"].map("{:,.0f} Pcs".format)
        df_display["% Kontribusi"] = df_display["% Kontribusi"].map("{:.2f} %".format)
        df_display["Target 100% Done"] = df_display["Target 100% Done"].map("{} Item".format)
    
        st.dataframe(
            df_display,
            use_container_width=True,
            column_config={
                "Nama Personil": st.column_config.TextColumn("👤 Nama Personil"),
                "Total Qty": st.column_config.TextColumn("📦 Total Penjualan"),
                "% Kontribusi": st.column_config.TextColumn("📊 Kontribusi Toko"),
                "Target 100% Done": st.column_config.TextColumn("🎯 Target 100% Achieved"),
            }
        )

    
    # ---------------------------------------------------------
    # HALAMAN 4: DETAIL RANGKING PPS TOKO
    # ---------------------------------------------------------
    elif st.session_state.sub_page_raport == "RANK_PPS":
        if st.button("⬅️ Kembali ke Menu Utama", key="btn_back_3"):
            st.query_params["sub_page"] = "MENU_UTAMA"
            st.session_state.sub_page_raport = "MENU_UTAMA"
            st.rerun()
            
        st.markdown("### 🎯 Rangking PPS Toko")
        st.markdown("---")
        st.warning("🛠️ Fitur ini masih dalam tahap pengembangan. Harap bersabar!")

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
