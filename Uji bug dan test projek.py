import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
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

# Waktu Realtime
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
# 3. CUSTOM CSS FIX HEADER & MOBILE SCREEN
# =========================================================
st.markdown("""
<style>
/* Sembunyikan Header Bawaan Streamlit Supaya Tidak Kepotong */
header[data-testid="stHeader"] {
    display: none !important;
}

/* Background & Padding Layar HP */
.stApp { 
    background-color: #0b0f19; 
    color: #f8fafc; 
    font-family: 'Inter', sans-serif; 
}
.block-container { 
    padding-top: 1.8rem !important; 
    padding-bottom: 2rem !important; 
}

/* Custom Card & Metric */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #38bdf8; 
    padding: 12px; 
    border-radius: 12px; 
}
div[data-testid="stMetric"] label { color: #94a3b8 !important; font-size: 11px; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #38bdf8 !important; font-size: 20px; font-weight: 800; }

.app-card {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border: 1.5px solid #00f0ff;
    border-radius: 18px;
    padding: 16px 10px;
    text-align: center;
    box-shadow: 0 6px 16px rgba(0, 240, 255, 0.15);
    margin-bottom: 8px;
}
.app-icon { font-size: 36px; margin-bottom: 4px; display: block; }
.app-title { color: #ffffff; font-size: 14px; font-weight: 700; margin: 0; }
.app-desc { color: #94a3b8; font-size: 11px; margin-top: 2px; }

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
# 5. HEADER ATAS (AMAN UNTUK HP)
# =========================================================
h_col1, h_col2 = st.columns([2.5, 1])
with h_col1:
    st.markdown(f"""
    <div style='display: flex; align-items: center; gap: 8px;'>
        <div style='background: #00f0ff; width: 6px; height: 32px; border-radius: 3px;'></div>
        <div>
            <h4 style='margin:0; color:#ffffff; font-size: 16px;'>TOKO C383 MOBILE</h4>
            <p style='margin:0; color:#38bdf8; font-size: 11px;'>👤 {st.session_state.get("person_name", "User")}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with h_col2:
    if st.button("🚪 Keluar", key="btn_logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.markdown("<hr style='margin: 10px 0; border-color: #1e293b;'>", unsafe_allow_html=True)

# =========================================================
# 6. NAVIGASI HOME SCREEN & TABS
# =========================================================
selected_tab = st.session_state.active_tab

if selected_tab != "Home":
    nav_col1, nav_col2 = st.columns([1.2, 2.8])
    with nav_col1:
        if st.button("🏠 Home", key="btn_nav_home", use_container_width=True):
            st.session_state.active_tab = "Home"
            st.rerun()
    with nav_col2:
        st.markdown(f"<h4 style='color:#00f0ff; margin: 4px 0 0 0;'>📌 {selected_tab}</h4>", unsafe_allow_html=True)
    st.markdown("<hr style='margin: 8px 0 12px 0; border-color: #334155;'>", unsafe_allow_html=True)

# --- DISPLAY HOME SCREEN ---
if selected_tab == "Home":
    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 16px;'>
        <p style='color: #94a3b8; font-size: 11px; margin-bottom: 2px;'>WAKTU SISTEM REALTIME</p>
        <p style='color: #00f0ff; font-size: 12px; font-weight: bold; margin-top: 0;'>{current_time_str}</p>
    </div>
    """, unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("<div class='app-card'><span class='app-icon'>📊</span><div class='app-title'>Dashboard</div><div class='app-desc'>Sales & Item Toko</div></div>", unsafe_allow_html=True)
        if st.button("Buka Dashboard", key="btn_a1", use_container_width=True):
            st.session_state.active_tab = "01 Dashboard Toko"
            st.rerun()
    with g2:
        st.markdown("<div class='app-card'><span class='app-icon'>👥</span><div class='app-title'>Raport Personil</div><div class='app-desc'>Ranking Sales Staff</div></div>", unsafe_allow_html=True)
        if st.button("Buka Raport", key="btn_a2", use_container_width=True):
            st.session_state.active_tab = "02 Raport Personil Toko"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    g3, g4 = st.columns(2)
    with g3:
        st.markdown("<div class='app-card'><span class='app-icon'>🎯</span><div class='app-title'>IKT & PPS</div><div class='app-desc'>Net Sales & Target</div></div>", unsafe_allow_html=True)
        if st.button("Buka IKT & PPS", key="btn_a3", use_container_width=True):
            st.session_state.active_tab = "03 Report IKT & PPS"
            st.rerun()
    with g4:
        st.markdown("<div class='app-card'><span class='app-icon'>⚙️</span><div class='app-title'>Pengaturan</div><div class='app-desc'>Reload & Data</div></div>", unsafe_allow_html=True)
        if st.button("Buka Pengaturan", key="btn_a4", use_container_width=True):
            st.session_state.active_tab = "04 Pengaturan & Download"
            st.rerun()

# =========================================================
# TAB 01: DASHBOARD TOKO
# =========================================================
elif selected_tab == "01 Dashboard Toko":
    sub_tab01 = st.radio(
        "Pilih Sub-Menu:",
        ["📊 Overview Penjualan", "📦 Detail Item & Performa Toko"],
        horizontal=True, key="sub_tab01_mobile"
    )
    st.markdown("<br>", unsafe_allow_html=True)

    periods_df = st.session_state.get("periods_df", pd.DataFrame())
    si_df = st.session_state.get("sales_item_df", pd.DataFrame()).copy()
    sp_df = st.session_state.get("sales_person_df", pd.DataFrame()).copy()

    # PERBAIKAN: Pastikan today_date terdefinisi di sini
    today_date = datetime.now(ZoneInfo("Asia/Jakarta")).date()

    period_options = list(periods_df["period_name"].dropna().unique()) if not periods_df.empty and "period_name" in periods_df.columns else []

    # OTOMATIS DETEKSI PERIODE BERJALAN BERDASARKAN TANGGAL HARI INI
    default_index = 0
    if not periods_df.empty and "start_date" in periods_df.columns and "end_date" in periods_df.columns:
        periods_df["start_dt"] = pd.to_datetime(periods_df["start_date"], errors="coerce").dt.date
        periods_df["end_dt"] = pd.to_datetime(periods_df["end_date"], errors="coerce").dt.date
        
        # Sekarang today_date sudah aman digunakan tanpa error
        current_period_match = periods_df[(periods_df["start_dt"] <= today_date) & (periods_df["end_dt"] >= today_date)]
        if not current_period_match.empty:
            curr_name = current_period_match.iloc[0]["period_name"]
            if curr_name in period_options:
                default_index = period_options.index(curr_name) + 1  # +1 karena index 0 adalah "Semua Periode”

            # --- SUBTAB 1: OVERVIEW PENJUALAN ---
    if sub_tab01 == "📊 Overview Penjualan":
        view_mode = st.radio(
            "Mode Tampilan Overview:",
            ["📅 1 Periode Full", "☀️ Harian (Daily Target)", "🗓️ Bulanan"],
            horizontal=True, key="ov_view_mode"
        )

        # =========================================================
        # FILTER PERIODE BULANAN VS REGULER
        # =========================================================
        if view_mode == "🗓️ Bulanan":
            if not periods_df.empty and "start_date" in periods_df.columns:
                periods_df["start_dt_temp"] = pd.to_datetime(periods_df["start_date"], errors="coerce")
                periods_df["month_year"] = periods_df["start_dt_temp"].dt.strftime("%B %Y")
                
                monthly_options_dict = {}
                for my, group in periods_df.groupby("month_year", sort=False):
                    min_d = group["start_dt_temp"].min().strftime("%d")
                    max_d = group["start_dt_temp"].max().strftime("%d %B %Y")
                    label = f"{my} ({min_d} - {max_d})"
                    monthly_options_dict[label] = my
                
                monthly_labels = list(monthly_options_dict.keys())
                selected_m_label = st.selectbox("🗓️ Pilih Bulan Penjualan:", monthly_labels, key="ov_month_select")
                selected_month_year = monthly_options_dict[selected_m_label]

                month_periods = periods_df[periods_df["month_year"] == selected_month_year]
                same_month_p_ids = month_periods["period_id"].tolist()

                sub_periods = month_periods
                sub_si = si_df[si_df["period_id"].isin(same_month_p_ids)]
                sub_sp = sp_df[sp_df["period_id"].isin(same_month_p_ids)]
            else:
                sub_periods, sub_si, sub_sp = periods_df, si_df, sp_df
        else:
            selected_p_overview = st.selectbox(
                "🗓️ Filter Periode:", 
                ["Semua Periode (Overall)"] + period_options, 
                index=default_index, 
                key="ov_period_select"
            )

            if selected_p_overview != "Semua Periode (Overall)":
                matched_period = periods_df[periods_df["period_name"] == selected_p_overview]
                p_id = matched_period.iloc[0]["period_id"] if not matched_period.empty else None
                sub_periods = periods_df[periods_df["period_id"] == p_id] if p_id else pd.DataFrame()
                sub_si = si_df[si_df["period_id"] == p_id] if p_id else pd.DataFrame()
                sub_sp = sp_df[sp_df["period_id"] == p_id] if p_id else pd.DataFrame()
            else:
                sub_periods, sub_si, sub_sp = periods_df, si_df, sp_sp

        # FIX TANGGAL: Normalisasi kolom tanggal pada sub_sp ke format datetime.date
        if not sub_sp.empty:
            date_col = "date" if "date" in sub_sp.columns else ("tanggal" if "tanggal" in sub_sp.columns else None)
            if date_col:
                sub_sp["dt_clean"] = pd.to_datetime(sub_sp[date_col], errors="coerce").dt.date
            else:
                sub_sp["dt_clean"] = None
        else:
            sub_sp["dt_clean"] = None

        # Hitung rentang tanggal
        if not sub_periods.empty and "start_date" in sub_periods.columns:
            start_date = pd.to_datetime(sub_periods["start_date"].min()).date()
            end_date = pd.to_datetime(sub_periods["end_date"].max()).date()
        else:
            start_date = today_date.replace(day=1)
            end_date = today_date

        total_days = max((end_date - start_date).days + 1, 1)
        passed_days = total_days if today_date > end_date else (0 if today_date < start_date else max((today_date - start_date).days + 1, 1))
        remaining_days = max(total_days - passed_days, 1)

        # =========================================================
        # 1. MODE: 1 PERIODE FULL
        # =========================================================
        if view_mode == "📅 1 Periode Full":
            tot_target = pd.to_numeric(sub_si.get("target_qty", 0), errors="coerce").fillna(0).sum()
            tot_actual = pd.to_numeric(sub_sp.get("actual_qty", 0), errors="coerce").fillna(0).sum()
            tot_gap = tot_target - tot_actual
            tot_ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0
            
            sisa_target = max(tot_gap, 0)
            target_per_day_remaining = sisa_target / remaining_days if sisa_target > 0 else 0

            c1, c2, c3 = st.columns(3)
            c1.metric("🎯 Target Periode", f"{tot_target:,.0f} Pcs")
            c2.metric("📦 Actual Sales", f"{tot_actual:,.0f} Pcs")
            c3.metric("⚡ % Ach", f"{tot_ach:.1f}%")

            st.markdown("<br>", unsafe_allow_html=True)
            c4, c5 = st.columns(2)
            c4.metric("📉 Sisa Gap Target", f"{sisa_target:,.0f} Pcs")
            c5.metric("🎯 Target/Hari (Sisa)", f"{target_per_day_remaining:,.0f} Pcs/hr")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📈 Tren Penjualan Harian Per Minggu")

            # FIX GRAFIK TREN PENJUALAN
            date_range = pd.date_range(start=start_date, end=end_date).date
            if not sub_sp.empty and "dt_clean" in sub_sp.columns:
                sub_sp["actual_qty"] = pd.to_numeric(sub_sp["actual_qty"], errors="coerce").fillna(0)
                daily_agg = sub_sp.groupby("dt_clean")["actual_qty"].sum()
                trend_values = [daily_agg.get(d, 0) for d in date_range]
            else:
                trend_values = [0] * len(date_range)

            daily_trend = pd.DataFrame({"Tanggal": date_range, "Actual": trend_values})

            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=daily_trend["Tanggal"], 
                y=daily_trend["Actual"],
                mode='lines+markers',
                line=dict(color='#00f0ff', width=3),
                marker=dict(size=6, color='#ffffff'),
                name='Actual Pcs'
            ))
            fig_trend.update_layout(
                height=260,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#ffffff"),
                xaxis=dict(showgrid=False, tickformat="%d %b"),
                yaxis=dict(showgrid=True, gridcolor="#1e293b")
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # =========================================================
        # 2. MODE: HARIAN (DAILY TARGET)
        # =========================================================
        elif view_mode == "☀️ Harian (Daily Target)":
            date_options = [start_date + pd.Timedelta(days=i) for i in range((end_date - start_date).days + 1)]
            default_daily_idx = date_options.index(today_date) if today_date in date_options else 0
            selected_daily_date = st.selectbox("📅 Pilih Tanggal Harian:", date_options, index=default_daily_idx, key="daily_date_picker")

            # FIX FILTER HARIAN
            if not sub_sp.empty and "dt_clean" in sub_sp.columns:
                sub_sp["actual_qty"] = pd.to_numeric(sub_sp.get("actual_qty", 0), errors="coerce").fillna(0)
                day_sp = sub_sp[sub_sp["dt_clean"] == selected_daily_date]
            else:
                day_sp = pd.DataFrame()

            # TOP CONTRIBUTOR
            top_person = "-"
            if not day_sp.empty:
                person_col = "person_name" if "person_name" in day_sp.columns else ("sales_person" if "sales_person" in day_sp.columns else None)
                if person_col:
                    top_p_df = day_sp.groupby(person_col)["actual_qty"].sum().reset_index()
                    if not top_p_df.empty and top_p_df["actual_qty"].max() > 0:
                        top_person = top_p_df.sort_values(by="actual_qty", ascending=False).iloc[0][person_col]

            # TOP ITEM
            top_item = "-"
            if not sub_si.empty and "item_name" in sub_si.columns:
                sub_si["actual_qty"] = pd.to_numeric(sub_si.get("actual_qty", 0), errors="coerce").fillna(0)
                top_i_df = sub_si.groupby("item_name")["actual_qty"].sum().reset_index()
                if not top_i_df.empty and top_i_df["actual_qty"].max() > 0:
                    top_item = top_i_df.sort_values(by="actual_qty", ascending=False).iloc[0]["item_name"]

            tc1, tc2 = st.columns(2)
            tc1.markdown(f"""
            <div class='app-card' style='padding: 10px;'>
                <span style='color:#94a3b8; font-size:10px;'>🥇 TOP CONTRIBUTOR</span>
                <p style='color:#00f0ff; font-size:14px; font-weight:bold; margin:2px 0 0 0;'>{top_person}</p>
            </div>
            """, unsafe_allow_html=True)
            
            tc2.markdown(f"""
            <div class='app-card' style='padding: 10px;'>
                <span style='color:#94a3b8; font-size:10px;'>📦 TOP ITEM</span>
                <p style='color:#38bdf8; font-size:14px; font-weight:bold; margin:2px 0 0 0;'>{top_item}</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            tot_target_full = pd.to_numeric(sub_si.get("target_qty", 0), errors="coerce").fillna(0).sum()
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

        # =========================================================
        # 3. MODE: BULANAN
        # =========================================================
        elif view_mode == "🗓️ Bulanan":
            tot_target = pd.to_numeric(sub_si.get("target_qty", 0), errors="coerce").fillna(0).sum()
            tot_actual = pd.to_numeric(sub_sp.get("actual_qty", 0), errors="coerce").fillna(0).sum()
            tot_gap = tot_target - tot_actual
            tot_ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0
            
            bobot_pps = (tot_ach / 100) * 20

            bm1, bm2, bm3 = st.columns(3)
            bm1.metric("🎯 Target Bulan Ini", f"{tot_target:,.0f} Pcs")
            bm2.metric("📦 Actual Sales", f"{tot_actual:,.0f} Pcs")
            bm3.metric("📉 Sisa Gap", f"{max(tot_gap, 0):,.0f} Pcs")

            st.markdown("<br>", unsafe_allow_html=True)
            bm4, bm5 = st.columns(2)
            bm4.metric("⚡ % Ach Bulanan", f"{tot_ach:.1f}%")
            bm5.metric("🏆 Indeks Bobot PPS", f"{bobot_pps:.2f} Pt")



            
    # --- SUBTAB 2: DETAIL ITEM & PERFORMA TOKO ---
    elif sub_tab01 == "📦 Detail Item & Performa Toko":
        search_query = st.text_input("🔍 Cari Produk:", placeholder="Ketik nama item...", key="search_item_mob")
        selected_p_detail = st.selectbox(
            "Filter Periode", 
            ["Semua Periode"] + period_options, 
            index=default_index, 
            key="period_detail_mob"
        )
        
        if selected_p_detail != "Semua Periode":
            matched_p = periods_df[periods_df["period_name"] == selected_p_detail]
            p_id = matched_p.iloc[0]["period_id"] if not matched_p.empty else None
            si_det = si_df[si_df["period_id"] == p_id].copy() if p_id else pd.DataFrame()
        else:
            si_det = si_df.copy()
        
        if not si_det.empty:
            si_det["target_qty"] = pd.to_numeric(si_det.get("target_qty", 0), errors="coerce").fillna(0)
            si_det["actual_qty"] = pd.to_numeric(si_det.get("actual_qty", 0), errors="coerce").fillna(0)

            item_grouped = si_det.groupby("item_name").agg({"target_qty": "sum", "actual_qty": "sum"}).reset_index()
            item_grouped["gap"] = item_grouped["target_qty"] - item_grouped["actual_qty"]
            item_grouped["ach"] = item_grouped.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)

            if search_query:
                item_grouped = item_grouped[item_grouped["item_name"].str.contains(search_query, case=False, na=False)]

            # GENERATE TABEL NEON CUSTOM HTML (TANPA INDEX BARIS 0,1,2...)
            table_rows = ""
            for idx, row in item_grouped.iterrows():
                ach_val = row['ach']
                ach_color_class = "text-green" if ach_val >= 100 else ("text-cyan" if ach_val >= 50 else "text-red")
                
                table_rows += f"""
                <tr>
                    <td style='font-weight:600;'>{row['item_name']}</td>
                    <td style='text-align:right;'>{row['target_qty']:,.0f}</td>
                    <td style='text-align:right;'>{row['actual_qty']:,.0f}</td>
                    <td style='text-align:right;'>{row['gap']:,.0f}</td>
                    <td style='text-align:right;' class='{ach_color_class}'>{ach_val:.1f}%</td>
                </tr>
                """

            neon_table_html = f"""
            <div class="neon-table-container">
                <table class="neon-table">
                    <thead>
                        <tr>
                            <th>Item Name</th>
                            <th style='text-align:right;'>Target</th>
                            <th style='text-align:right;'>Actual</th>
                            <th style='text-align:right;'>Gap</th>
                            <th style='text-align:right;'>% Ach</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
            """
            st.markdown(neon_table_html, unsafe_allow_html=True)
        else:
            st.info("Tidak ada data item untuk periode ini.")




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
