import streamlit as st
import pandas as pd
import numpy as np
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# Konfigurasi Halaman Dashboard
st.set_page_config(page_title="PSM Toko - Sales Dashboard", layout="wide")

EXCEL_FILE = "Database_Penjualan_PSM_Toko_Clean_GoogleSheets.xlsx"

# --- CUSTOM CSS: SIDEBAR CERAH, TEKS KONTRASTING, NEON CARD & NO WHITE DOTS ---
st.markdown("""
    <style>
    /* Latar Belakang Utama Aplikasi */
    .stApp {
        background-color: #0b0f19;
        color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    /* Styling Kartu Metrik Utama (Glow Card) */
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
    
    /* Judul dan Header Teks Terang */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 700;
    }
    
    /* Sidebar Layout & Kontras Terang */
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: 600;
    }
    
    /* Sembunyikan Lingkaran Putih Bawaan Radio Button */
    div[data-testid="stRadio"] input[type="radio"],
    div[data-testid="stRadio"] div[role="radiogroup"] div:has(> input[type="radio"]) {
        display: none !important;
    }
    
    /* Ubah Radio Button Menjadi Box / Card Navigasi Neon */
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
    
    /* Hover Effect pada Menu Box Navigasi */
    div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        border-color: #38bdf8;
        background-color: #334155;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
        transform: translateY(-1px);
    }
    
    /* Effect Menu Aktif / Terpilih */
    div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"],
    div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: 1px solid #38bdf8 !important;
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.6) !important;
        color: #ffffff !important;
    }

    /* Podium Custom Styling */
    .podium-box {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        border: 1px solid #334155;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .podium-1 {
        border: 2px solid #f59e0b;
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.4);
    }
    .podium-2 {
        border: 2px solid #94a3b8;
        box-shadow: 0 0 15px rgba(148, 163, 184, 0.3);
    }
    .podium-3 {
        border: 2px solid #b45309;
        box-shadow: 0 0 15px rgba(180, 83, 9, 0.3);
    }

    /* Expander Login Admin */
    div[data-testid="stExpander"] {
        background: #1e293b !important;
        border: 1px solid #38bdf8 !important;
        border-radius: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNGSI LOAD & SAVE DATABASE EXCEL ---
def load_database():
    if not os.path.exists(EXCEL_FILE):
        st.error(f"File database '{EXCEL_FILE}' tidak ditemukan!")
        st.stop()
    
    periods_df = pd.read_excel(EXCEL_FILE, sheet_name="PERIODE")
    items_df = pd.read_excel(EXCEL_FILE, sheet_name="MASTER_ITEM")
    person_df = pd.read_excel(EXCEL_FILE, sheet_name="MASTER_PERSONIL")
    sales_item_df = pd.read_excel(EXCEL_FILE, sheet_name="SALES_ITEM")
    sales_person_df = pd.read_excel(EXCEL_FILE, sheet_name="SALES_PERSONIL")
    
    return periods_df, items_df, person_df, sales_item_df, sales_person_df

def save_database(sales_item_df, sales_person_df):
    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        sales_item_df.to_excel(writer, sheet_name="SALES_ITEM", index=False)
        sales_person_df.to_excel(writer, sheet_name="SALES_PERSONIL", index=False)

# Inisialisasi Data
if "data_loaded" not in st.session_state:
    p_df, i_df, pers_df, si_df, sp_df = load_database()
    st.session_state.periods_df = p_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.data_loaded = True

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- SIDEBAR NAVIGASI ---
st.sidebar.image("https://tse3.mm.bing.net/th/id/OIP.mVrKCdnlL5Yc-3wRmzFXOAAAAA?r=0&rs=1&pid=ImgDetMain&o=7&rm=3", width=65)
st.sidebar.markdown("<h2 style='color:#ffffff; margin-bottom:0px;'>PSM TOKO</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='color:#38bdf8; font-size:12px; font-weight:bold; margin-top:-5px;'>Sales Dashboard & Input System</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>📌 NAVIGASI MENU</p>", unsafe_allow_html=True)

menu_options = [
    "01 · Overview", 
    "02 · Detail Item", 
    "03 · Penjualan Personil", 
    "04 · Pencapaian Pernik", 
    "05 · Analisis Tren"
]

if st.session_state.logged_in:
    menu_options.append("06 · Input & Reset Data")

selected_tab = st.sidebar.radio("", menu_options, label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>🌟 FILTER PERIODE</p>", unsafe_allow_html=True)
periods_dict = {row["period_name"]: row["period_id"] for _, row in st.session_state.periods_df.iterrows()}
selected_period_name = st.sidebar.selectbox("", ["Semua Periode (Overall)"] + list(periods_dict.keys()), label_visibility="collapsed")
selected_period_id = None if selected_period_name == "Semua Periode (Overall)" else periods_dict[selected_period_name]

# Area Login Admin (Expander)
st.sidebar.markdown("---")
with st.sidebar.expander("🔑 Login Admin / Editor"):
    if not st.session_state.logged_in:
        u_input = st.text_input("Username", key="u_login")
        p_input = st.text_input("Password", type="password", key="p_login")
        if st.button("Masuk Editor"):
            if u_input == "admin" and p_input == "admin123":
                st.session_state.logged_in = True
                st.success("Login Berhasil!")
                st.rerun()
            else:
                st.error("Username/Password Salah!")
    else:
        st.success("Status: Login Editor Active")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- HEADER UTAMA: REALTIME TIME & DATE ---
now = datetime.now()
current_time_str = now.strftime("%A, %d %B %Y | %H:%M WIB")

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


# --- TAB 01: OVERVIEW ---
if selected_tab == "01 · Overview":
    st.title("📊 Overview Penjualan Toko")
    
    si_df = st.session_state.sales_item_df.copy()
    if selected_period_id:
        si_df = si_df[si_df["period_id"] == selected_period_id]
        
    si_df["target_qty"] = pd.to_numeric(si_df["target_qty"], errors="coerce").fillna(0)
    si_df["actual_qty"] = pd.to_numeric(si_df["actual_qty"], errors="coerce").fillna(0)
    
    tot_target = si_df["target_qty"].sum()
    tot_actual = si_df["actual_qty"].sum()
    ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0
    gap = tot_actual - tot_target

    # Kalkulasi Best Estimasi Penjualan (Pacing Realtime)
    # Menghitung durasi hari berdasarkan periode yang dipilih
    if selected_period_id:
        p_info = st.session_state.periods_df[st.session_state.periods_df["period_id"] == selected_period_id].iloc[0]
        s_date = pd.to_datetime(p_info["start_date"])
        e_date = pd.to_datetime(p_info["end_date"])
        total_days = max((e_date - s_date).days + 1, 1)
        # Hari yang berjalan (asumsi simulasi tanggal aktif saat ini di rentang promosi)
        today_date = pd.to_datetime(now.strftime("%Y-%m-%d"))
        if today_date < s_date:
            elapsed_days = 1
        elif today_date > e_date:
            elapsed_days = total_days
        else:
            elapsed_days = max((today_date - s_date).days + 1, 1)
    else:
        total_days = 31
        elapsed_days = max(now.day, 1)

    daily_pace = tot_actual / elapsed_days
    best_estimate_sales = int(daily_pace * total_days)
    est_achievement = (best_estimate_sales / tot_target * 100) if tot_target > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("🎯 TARGET TOKO", f"{tot_target:,.0f} Pcs")
    with c2:
        st.metric("📦 ACTUAL SALES", f"{tot_actual:,.0f} Pcs")
    with c3:
        st.metric("⚡ ACHIEVEMENT", f"{ach:.1f}%")
    with c4:
        st.metric("📉 GAP TARGET", f"{gap:,.0f} Pcs")
    with c5:
        st.metric("🔮 BEST ESTIMASI", f"{best_estimate_sales:,.0f} Pcs", delta=f"{est_achievement:.1f}% Projected")

    st.markdown("---")
    
    # Visualisasi Grafik Batang (Bar Chart)
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.subheader("📈 Target vs Actual Sales per Periode Promosi")
        chart_df = st.session_state.sales_item_df.groupby("period_id")[["target_qty", "actual_qty"]].sum().reset_index()
        chart_df = pd.merge(chart_df, st.session_state.periods_df[["period_id", "period_name"]], on="period_id", how="left")
        
        # Plotly Bar Chart dengan warna lembut/harmonis
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=chart_df["period_name"], 
            y=chart_df["target_qty"], 
            name="Target (Pcs)", 
            marker_color="#38bdf8"
        ))
        fig.add_trace(go.Bar(
            x=chart_df["period_name"], 
            y=chart_df["actual_qty"], 
            name="Actual (Pcs)", 
            marker_color="#0284c7"
        ))
        fig.update_layout(
            barmode='group',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#ffffff"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_chart2:
        st.subheader("🍩 Top 5 Kontribusi Produk")
        if not si_df.empty:
            top_items = si_df.groupby("item_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False).head(5)
            for _, row in top_items.iterrows():
                pct = (row["actual_qty"] / tot_actual * 100) if tot_actual > 0 else 0
                st.markdown(f"**{row['item_name']}** — {row['actual_qty']:,.0f} Pcs ({pct:.1f}%)")
                st.progress(min(int(pct), 100))
        else:
            st.info("Belum ada data.")

    st.markdown("---")
    st.subheader("📅 Ringkasan Performa Seluruh Periode Promosi")
    summary_data = []
    for _, p in st.session_state.periods_df.iterrows():
        p_id = p["period_id"]
        p_name = p["period_name"]
        p_target_total = p["target_total"]
        
        sub_si = st.session_state.sales_item_df[st.session_state.sales_item_df["period_id"] == p_id]
        p_actual = pd.to_numeric(sub_si["actual_qty"], errors="coerce").fillna(0).sum()
        p_target = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0).sum()
        if pd.isna(p_target_total) or p_target_total == 0:
            p_target_total = p_target
            
        p_ach = (p_actual / p_target_total * 100) if p_target_total > 0 else 0
        summary_data.append({
            "Nama Periode Promosi": p_name,
            "Rentang Tanggal": f"{str(p['start_date'])[:10]} s/d {str(p['end_date'])[:10]}",
            "Target (Pcs)": f"{p_target_total:,.0f}",
            "Actual (Pcs)": f"{p_actual:,.0f}",
            "% Achievement": f"{p_ach:.1f}%",
            "Status Periode": p["status"]
        })
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)


# --- TAB 02: DETAIL ITEM ---
elif selected_tab == "02 · Detail Item":
    st.title("📦 Detail Item & Performa Produk")
    
    si_df = st.session_state.sales_item_df.copy()
    if selected_period_id:
        si_df = si_df[si_df["period_id"] == selected_period_id]
        
    si_df["target_qty"] = pd.to_numeric(si_df["target_qty"], errors="coerce").fillna(0)
    si_df["actual_qty"] = pd.to_numeric(si_df["actual_qty"], errors="coerce").fillna(0)
    si_df["ach"] = si_df.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)
    
    search_query = st.text_input("🔍 Cari Nama Produk / Item")
    if search_query:
        si_df = si_df[si_df["item_name"].str.contains(search_query, case=False, na=False)]
        
    # Bersihkan tabel: Buang item_id, record_id, updated_at
    display_items = si_df[["item_name", "target_qty", "actual_qty", "ach"]].copy()
    display_items.columns = ["Nama Produk / Item", "Target (Pcs)", "Actual Penjualan (Pcs)", "% Achievement"]
    display_items["% Achievement"] = display_items["% Achievement"].apply(lambda x: f"{x:.1f}%")
    
    st.dataframe(display_items, use_container_width=True, hide_index=True)


# --- TAB 03: PENJUALAN PERSONIL ---
elif selected_tab == "03 · Penjualan Personil":
    st.title("👥 Total Penjualan Personil Toko")
    
    sp_df = st.session_state.sales_person_df.copy()
    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
        
    sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)
    
    if not sp_df.empty:
        summary_person = sp_df.groupby("person_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        total_all_person = summary_person["actual_qty"].sum()
        summary_person["pct_contrib"] = (summary_person["actual_qty"] / total_all_person * 100) if total_all_person > 0 else 0
        
        # Format Tampilan Tabel Tanpa ID & Tanpa Tanggal Update
        summary_person.columns = ["Nama Staf / Personil", "Total Penjualan (Pcs)", "% Kontribusi Total"]
        summary_person["% Kontribusi Total"] = summary_person["% Kontribusi Total"].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(summary_person, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data transaksi penjualan personil.")


# --- TAB 04: PENCAPAIAN PERNIK ---
elif selected_tab == "04 · Pencapaian Pernik":
    st.title("🏆 Leaderboard & Pencapaian Pernik Personil")
    
    sp_df = st.session_state.sales_person_df.copy()
    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
        
    sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)
    
    if not sp_df.empty:
        person_ranks = sp_df.groupby("person_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        total_overall_sales = person_ranks["actual_qty"].sum()
        person_ranks["pct_contribution"] = (person_ranks["actual_qty"] / total_overall_sales * 100) if total_overall_sales > 0 else 0
        
        # --- PODIUM JUARA TOP 3 STAF ---
        st.subheader("🥇 PODIUM JUARA PERNIK PERIODE INI")
        col_p2, col_p1, col_p3 = st.columns(3)
        
        # Juara 1
        if len(person_ranks) >= 1:
            r1 = person_ranks.iloc[0]
            with col_p1:
                st.markdown(f"""
                    <div class='podium-box podium-1'>
                        <h1 style='margin:0; font-size:40px;'>🥇</h1>
                        <h3 style='color:#f59e0b; margin:4px 0;'>JUARA 1</h3>
                        <h2 style='color:#ffffff; margin:0;'>{r1['person_name']}</h2>
                        <h3 style='color:#38bdf8; margin:8px 0;'>{r1['actual_qty']:,.0f} Pcs</h3>
                        <p style='color:#94a3b8; margin:0; font-weight:bold;'>Kontribusi: {r1['pct_contribution']:.1f}%</p>
                    </div>
                """, unsafe_allow_html=True)
                
        # Juara 2
        if len(person_ranks) >= 2:
            r2 = person_ranks.iloc[1]
            with col_p2:
                st.markdown(f"""
                    <div class='podium-box podium-2' style='margin-top: 25px;'>
                        <h1 style='margin:0; font-size:36px;'>🥈</h1>
                        <h3 style='color:#94a3b8; margin:4px 0;'>JUARA 2</h3>
                        <h2 style='color:#ffffff; margin:0;'>{r2['person_name']}</h2>
                        <h3 style='color:#38bdf8; margin:8px 0;'>{r2['actual_qty']:,.0f} Pcs</h3>
                        <p style='color:#94a3b8; margin:0; font-weight:bold;'>Kontribusi: {r2['pct_contribution']:.1f}%</p>
                    </div>
                """, unsafe_allow_html=True)
                
        # Juara 3
        if len(person_ranks) >= 3:
            r3 = person_ranks.iloc[2]
            with col_p3:
                st.markdown(f"""
                    <div class='podium-box podium-3' style='margin-top: 40px;'>
                        <h1 style='margin:0; font-size:32px;'>🥉</h1>
                        <h3 style='color:#b45309; margin:4px 0;'>JUARA 3</h3>
                        <h2 style='color:#ffffff; margin:0;'>{r3['person_name']}</h2>
                        <h3 style='color:#38bdf8; margin:8px 0;'>{r3['actual_qty']:,.0f} Pcs</h3>
                        <p style='color:#94a3b8; margin:0; font-weight:bold;'>Kontribusi: {r3['pct_contribution']:.1f}%</p>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("📋 Tabel Kontribusi Penjualan Pernik Seluruh Personil")
        
        # Format Tampilan Tabel Lengkap (Tanpa Kolom ID / Update)
        table_ranks = person_ranks.copy()
        table_ranks.columns = ["Nama Staf / Personil Toko", "Total Penjualan Pernik (Pcs)", "% Kontribusi"]
        table_ranks["% Kontribusi"] = table_ranks["% Kontribusi"].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(table_ranks, use_container_width=True, hide_index=True)
        
        st.info(f"💡 **Total Penjualan Pernik Gabungan Seluruh
