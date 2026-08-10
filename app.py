import streamlit as st
import pandas as pd
import numpy as np
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta

# Ambil waktu UTC lalu konversi secara presisi ke WIB (GMT+7)
now_utc = datetime.utcnow()
now_wib = now_utc + timedelta(hours=7)
current_time_str = now_wib.strftime("%A, %d %B %Y | %H:%M WIB")

# Konfigurasi Halaman Dashboard
st.set_page_config(page_title="PSM Toko - Sales Dashboard", layout="wide")

EXCEL_FILE = "Database_Penjualan_PSM_Toko_Clean_GoogleSheets.xlsx"

# --- DATABASE PENGGUNA (LOGIN) ---
USER_CREDENTIALS = {
    "admin": "admin123",
    "user1": "password123",
    "kasir": "kasir123"
}

# --- CUSTOM CSS ---
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

    /* Container Card Login */
    .login-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 30px;
        border-radius: 16px;
        border: 1px solid #38bdf8;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.3);
        margin-top: 50px;
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

# Inisialisasi Session State Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""


# --- HALAMAN LOGIN ---
def show_login_page():
    # URL Direct Image / File Gambar Resmi Logo KGS Group Belgium (.png)
    LOGO_URL = "https://github.com/stefanusagranus-tech/LigaPSM26/blob/main/kgs_group_belgium_logo.jpg?raw=true"

    st.markdown("""
        <style>
            /* Container utama login card */
            .login-card {
                background-color: #1e293b;
                padding: 35px 30px;
                border-radius: 16px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
                border: none !important;
                text-align: center;
                margin-bottom: 20px;
            }
            
            /* Logo Perusahaan */
            .login-logo {
                width: 100px;
                height: 100px;
                object-fit: contain;
                border-radius: 12px;
                background-color: #ffffff;
                padding: 8px;
                margin-bottom: 15px;
                border: none !important;
                display: block;
                margin-left: auto;
                margin-right: auto;
            }
            .login-header {
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
                margin-bottom: 6px;
            }
            .login-subtitle {
                color: #38bdf8;
                font-size: 13px;
                margin-bottom: 0px;
            }

            /* MENGHAPUS PESAN/TOOLTIP "Please enter and submit form" */
            div[data-testid="stForm"] [data-baseweb="popover"],
            div[data-testid="stForm"] div[role="tooltip"],
            .stFormHelp, 
            div[data-testid="stForm"] iframe {
                display: none !important;
            }

            /* MENGUBAH TULISAN LABEL "USERNAME" & "PASSWORD" MENJADI BIRU NEON */
            div[data-testid="stWidgetLabel"] *, 
            label[data-testid="stWidgetLabel"],
            .stTextInput > label {
                color: #38bdf8 !important;
                font-weight: 600 !important;
                font-size: 14px !important;
            }

            /* Styling Kotak Isian (Input) */
            div[data-baseweb="input"] {
                border: none !important;
                background-color: #0f172a !important;
                border-radius: 8px !important;
            }
            div[data-baseweb="input"] input {
                color: #ffffff !important;
            }

            /* TOMBOL MASUK KE APLIKASI (HITAM NEON) */
            div[data-testid="stFormSubmitButton"] > button {
                background-color: #090d16 !important;
                color: #38bdf8 !important;
                font-weight: 700 !important;
                border: 1.5px solid #38bdf8 !important;
                border-radius: 8px !important;
                box-shadow: 0 0 12px rgba(56, 189, 248, 0.4) !important;
                transition: all 0.3s ease-in-out !important;
            }
            
            /* Hover Tombol Submit */
            div[data-testid="stFormSubmitButton"] > button:hover {
                background-color: #38bdf8 !important;
                color: #090d16 !important;
                box-shadow: 0 0 20px rgba(56, 189, 248, 0.8) !important;
                border-color: #38bdf8 !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Layout tengah
    _, col2, _ = st.columns([1, 1.4, 1])
    
    with col2:
        # Header Box
        st.markdown(f"""
            <div class='login-card'>
                <img src='{LOGO_URL}' class='login-logo' alt='KGS Group Logo'>
                <p class='login-subtitle'>Sistem Monitoring PSM Toko</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Form Login
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username", placeholder="Masukkan username").strip()
            password_input = st.text_input("Password", type="password", placeholder="Masukkan password")
            
            submit_btn = st.form_submit_button("Masuk ke Aplikasi", use_container_width=True)
            
            if submit_btn:
                if not username_input or not password_input:
                    st.warning("Username dan Password wajib diisi!")
                elif username_input in USER_CREDENTIALS and USER_CREDENTIALS[username_input] == password_input:
                    st.session_state.logged_in = True
                    st.session_state.username = username_input
                    st.toast("Login Berhasil!", icon="✅")
                    st.rerun()
                else:
                    st.error("Username atau Password salah!")

# Cek Status Autentikasi
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    show_login_page()
    st.stop()
    
# --- INISIALISASI DATA DASHBOARD ---
if "data_loaded" not in st.session_state:
    p_df, i_df, pers_df, si_df, sp_df = load_database()
    st.session_state.periods_df = p_df
    st.session_state.items_df = i_df
    st.session_state.person_df = pers_df
    st.session_state.sales_item_df = si_df
    st.session_state.sales_person_df = sp_df
    st.session_state.data_loaded = True

# --- SIDEBAR NAVIGASI ---
st.sidebar.image("https://tse3.mm.bing.net/th/id/OIP.mVrKCdnlL5Yc-3wRmzFXOAAAAA?r=0&rs=1&pid=ImgDetMain&o=7&rm=3", width=65)
st.sidebar.markdown("<h2 style='color:#ffffff; margin-bottom:0px;'>TOKO C383</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='color:#38bdf8; font-size:12px; font-weight:bold; margin-top:-5px;'>Report PSM dan Target PSM</p>", unsafe_allow_html=True)

st.sidebar.markdown("<p style='color:#38bdf8; font-size:12px; font-weight:bold; margin-top:-5px;'>Selamat Datang Kembali</p>", unsafe_allow_html=True)
st.sidebar.markdown(f"<p style='color:#00ff88; font-size:12px; font-weight:bold;'>👤 User: {st.session_state.username}</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>📌 NAVIGASI MENU</p>", unsafe_allow_html=True)

menu_options = [
    "01 · Overview", 
    "02 · Detail Item", 
    "03 · Penjualan Personil", 
    "04 · Pencapaian Pernik", 
    "05 · Analisis Tren",
    "06 · Input & Reset Data"
]

selected_tab = st.sidebar.radio("", menu_options, label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.markdown("<p style='color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:6px;'>🌟 FILTER PERIODE</p>", unsafe_allow_html=True)
periods_dict = {row["period_name"]: row["period_id"] for _, row in st.session_state.periods_df.iterrows()}
selected_period_name = st.sidebar.selectbox("", ["Semua Periode (Overall)"] + list(periods_dict.keys()), label_visibility="collapsed")
selected_period_id = None if selected_period_name == "Semua Periode (Overall)" else periods_dict[selected_period_name]

# Tombol Logout di Sidebar
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Keluar / Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# --- HEADER UTAMA ---
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

    if selected_period_id:
        p_info = st.session_state.periods_df[st.session_state.periods_df["period_id"] == selected_period_id].iloc[0]
        s_date = pd.to_datetime(p_info["start_date"])
        e_date = pd.to_datetime(p_info["end_date"])
        total_days = max((e_date - s_date).days + 1, 1)
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
    
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.subheader("📈 Target vs Actual Sales per Periode Promosi")
        chart_df = st.session_state.sales_item_df.groupby("period_id")[["target_qty", "actual_qty"]].sum().reset_index()
        chart_df = pd.merge(chart_df, st.session_state.periods_df[["period_id", "period_name"]], on="period_id", how="left")
        
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
    
    st.markdown("<p style='color:#38bdf8; font-weight:bold; font-size:13px;'>🔍 FILTER & PENGURUTAN DATA PRODUK</p>", unsafe_allow_html=True)
    f_col1, f_col2, f_col3 = st.columns([1.5, 1, 1.2])
    
    with f_col1:
        search_query = st.text_input("Cari Nama Produk / Item", placeholder="Ketik nama item...", key="search_item_tab2")
        
    with f_col2:
        period_options_tab2 = ["Semua Periode Promosi"] + list(periods_dict.keys())
        selected_p_tab2 = st.selectbox("Periode Promosi", period_options_tab2, key="period_tab2")
        
    with f_col3:
        sort_option = st.selectbox(
            "Urutkan Berdasarkan", 
            [
                "Penjualan Terbanyak (Terlaris)", 
                "Penjualan Tersedikit", 
                "Achievement Tertinggi (% Ach)", 
                "Nama Produk (A - Z)"
            ],
            key="sort_tab2"
        )

    if selected_p_tab2 != "Semua Periode Promosi":
        p_id_filter = periods_dict[selected_p_tab2]
        si_df = si_df[si_df["period_id"] == p_id_filter]

    si_df["target_qty"] = pd.to_numeric(si_df["target_qty"], errors="coerce").fillna(0)
    si_df["actual_qty"] = pd.to_numeric(si_df["actual_qty"], errors="coerce").fillna(0)
    
    item_grouped = si_df.groupby("item_name").agg({
        "target_qty": "sum",
        "actual_qty": "sum"
    }).reset_index()
    
    item_grouped["ach"] = item_grouped.apply(
        lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1
    )
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
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; text-align: left; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #f59e0b; font-size: 11px; font-weight: bold; letter-spacing: 0.8px;">🔥 ITEM TERLARIS (TOP SELLER)</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{top_item['item_name']}</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{top_item['actual_qty']:,.0f} Pcs</div>
                </div>
            """, unsafe_allow_html=True)
            
        with r_col2:
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; text-align: left; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #ef4444; font-size: 11px; font-weight: bold; letter-spacing: 0.8px;">📉 ITEM PENJUALAN TERENDAH</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{low_item['item_name']}</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{low_item['actual_qty']:,.0f} Pcs</div>
                </div>
            """, unsafe_allow_html=True)
            
        with r_col3:
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 14px; text-align: left; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #38bdf8; font-size: 11px; font-weight: bold; letter-spacing: 0.8px;">📦 TOTAL VARIASI ITEM DIPANTAU</div>
                    <div style="color: #ffffff; font-size: 16px; font-weight: 800; margin-top: 4px;">{len(item_grouped)} Jenis Produk</div>
                    <div style="color: #00ff88; font-size: 20px; font-weight: 800;">{item_grouped['actual_qty'].sum():,.0f} Pcs Total</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<p style='color:#ffffff; font-size:15px; font-weight:bold; margin-bottom:8px;'>📋 Tabel Performa Penjualan Produk</p>", unsafe_allow_html=True)
        
        table_rows_html = ""
        for _, row in item_grouped.iterrows():
            gap_color = "#00ff88" if row['gap'] >= 0 else "#ef4444"
            table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 12px 14px; color: #ffffff; font-weight: bold; font-size: 13px;">{row['item_name']}</td>
                <td style="padding: 12px 14px; color: #94a3b8; font-weight: bold; font-size: 14px;">{row['target_qty']:,.0f}</td>
                <td style="padding: 12px 14px; color: #00ff88; font-weight: bold; font-size: 14px;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 12px 14px; color: #00ff88; font-weight: bold; font-size: 14px;">{row['ach']:.1f}%</td>
                <td style="padding: 12px 14px; color: {gap_color}; font-weight: bold; font-size: 14px;">{row['gap']:,.0f}</td>
            </tr>
            """
            
        st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 12px; box-shadow: 0 0 14px rgba(0, 240, 255, 0.35); max-height: 520px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #334155;">
                            <th style="padding: 10px 14px; color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">NAMA PRODUK / ITEM</th>
                            <th style="padding: 10px 14px; color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">TARGET (PCS)</th>
                            <th style="padding: 10px 14px; color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">ACTUAL SALES (PCS)</th>
                            <th style="padding: 10px 14px; color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">% ACHIEVEMENT</th>
                            <th style="padding: 10px 14px; color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">GAP / SELISIH</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)

    else:
        st.warning("Tidak ada produk yang cocok dengan kriteria pencarian.")

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
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 16px; text-align: left; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #ffffff; font-size: 11px; font-weight: bold; letter-spacing: 0.8px;">TOTAL ACTUAL PERSONIL</div>
                    <div style="color: #00ff88; font-size: 28px; font-weight: 800; margin-top: 4px;">{tot_actual_personil:,.0f} Pcs</div>
                </div>
            """, unsafe_allow_html=True)
            
        with m2:
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 16px; text-align: left; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #ffffff; font-size: 11px; font-weight: bold; letter-spacing: 0.8px;">RATA-RATA PENJUALAN/STAF</div>
                    <div style="color: #00ff88; font-size: 28px; font-weight: 800; margin-top: 4px;">{avg_sales_personil:,.0f} Pcs</div>
                </div>
            """, unsafe_allow_html=True)
            
        with m3:
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 16px; text-align: left; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35);">
                    <div style="color: #ffffff; font-size: 11px; font-weight: bold; letter-spacing: 0.8px;">TOP PERFORMER</div>
                    <div style="color: #00ff88; font-size: 26px; font-weight: 800; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{top_performer_name}</div>
                </div>
            """, unsafe_allow_html=True)

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
                    <div style="flex: 1; background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; text-align: center; box-shadow: 0 0 10px rgba(0,240,255,0.25);">
                        <span style="font-size: 18px;">🥈</span>
                        <div style="color: #94a3b8; font-size: 10px; font-weight: bold;">JUARA 2</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{p2_name}</div>
                        <div style="color: #00ff88; font-size: 15px; font-weight: 800;">{p2_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #080c14; border: 2px solid #00f0ff; border-radius: 10px; padding: 12px; text-align: center; box-shadow: 0 0 16px rgba(0,240,255,0.5); transform: scale(1.02);">
                        <span style="font-size: 22px;">🥇</span>
                        <div style="color: #f59e0b; font-size: 10px; font-weight: bold;">JUARA 1</div>
                        <div style="color: #ffffff; font-size: 13px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{p1_name}</div>
                        <div style="color: #00ff88; font-size: 17px; font-weight: 800;">{p1_qty:,.0f} Pcs</div>
                    </div>
                    <div style="flex: 1; background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; text-align: center; box-shadow: 0 0 10px rgba(0,240,255,0.25);">
                        <span style="font-size: 18px;">🥉</span>
                        <div style="color: #b45309; font-size: 10px; font-weight: bold;">JUARA 3</div>
                        <div style="color: #ffffff; font-size: 12px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{p3_name}</div>
                        <div style="color: #00ff88; font-size: 15px; font-weight: 800;">{p3_qty:,.0f} Pcs</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        col_table, col_chart = st.columns([1, 1])
        COMPONENT_HEIGHT = 310

        with col_table:
            st.markdown("<p style='color:#ffffff; font-size:15px; font-weight:bold; margin-bottom:8px;'>📋 Penjualan Personil</p>", unsafe_allow_html=True)
            
            table_rows_html = ""
            for _, row in summary_person.iterrows():
                table_rows_html += f"""
                <tr style="border-bottom: 1px solid #1e293b;">
                    <td style="padding: 12px 10px; color: #ffffff; font-weight: bold; font-size: 13px;">{row['person_name']}</td>
                    <td style="padding: 12px 10px; color: #00ff88; font-weight: bold; font-size: 14px;">{row['actual_qty']:,.0f}</td>
                    <td style="padding: 12px 10px; color: #00ff88; font-weight: bold; font-size: 14px;">{row['pct_contrib']:.1f}%</td>
                </tr>
                """
            
            st.markdown(f"""
                <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; height: {COMPONENT_HEIGHT}px; box-shadow: 0 0 12px rgba(0, 240, 255, 0.35); overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                        <thead>
                            <tr style="border-bottom: 2px solid #334155;">
                                <th style="padding: 8px 10px; color: #94a3b8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">PERSONIL</th>
                                <th style="padding: 8px 10px; color: #94a3b8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">TOTAL SALES (PCS)</th>
                                <th style="padding: 8px 10px; color: #94a3b8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">KONTRIBUSI</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>
                </div>
            """, unsafe_allow_html=True)

        with col_chart:
            st.markdown("<p style='color:#ffffff; font-size:15px; font-weight:bold; margin-bottom:8px;'>📊 Grafik Perbandingan Performa Tim</p>", unsafe_allow_html=True)
            
            fig_person = go.Figure()
            fig_person.add_trace(go.Bar(
                x=summary_person["person_name"],
                y=summary_person["actual_qty"],
                name="Total Penjualan Pcs",
                marker_color="#00ff88",
                text=summary_person["actual_qty"].apply(lambda x: f"{x:,.0f}"),
                textposition="outside",
                textfont=dict(color="#00ff88", size=11)
            ))
            
            fig_person.update_layout(
                height=COMPONENT_HEIGHT,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#ffffff"),
                xaxis=dict(showgrid=False, tickfont=dict(color="#ffffff", size=10)),
                yaxis=dict(showgrid=True, gridcolor="#1e293b", tickfont=dict(color="#ffffff", size=10)),
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False
            )
            
            st.plotly_chart(fig_person, use_container_width=True)

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
        
        st.subheader("🥇 PODIUM JUARA PERNIK PERIODE INI")
        col_p2, col_p1, col_p3 = st.columns(3)
        
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
        
        table_ranks = person_ranks.copy()
        table_ranks.columns = ["Nama Staf / Personil Toko", "Total Penjualan Pernik (Pcs)", "% Kontribusi"]
        table_ranks["% Kontribusi"] = table_ranks["% Kontribusi"].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(table_ranks, use_container_width=True, hide_index=True)
        st.info(f"💡 **Total Penjualan Pernik Gabungan Seluruh Personil**: **{total_overall_sales:,.0f} Pcs**")
    else:
        st.info("Belum ada data penjualan pernik personil.")

# --- TAB 05: ANALISIS TREN ---
elif selected_tab == "05 · Analisis Tren":
    st.title("📈 Analisis Tren Penjualan & Estimasi Target")
    st.write("Analisis kecepatan transaksi harian (*Sales Pace*) dan proyeksi penutupan periode.")
    
    si_df = st.session_state.sales_item_df.copy()
    si_df["actual_qty"] = pd.to_numeric(si_df["actual_qty"], errors="coerce").fillna(0)
    
    trend_df = si_df.groupby("period_id")["actual_qty"].sum().reset_index()
    trend_df = pd.merge(trend_df, st.session_state.periods_df[["period_id", "period_name", "target_total"]], on="period_id")
    
    fig_trend = px.line(
        trend_df, 
        x="period_name", 
        y="actual_qty", 
        markers=True, 
        title="Tren Penjualan Toko Per Periode Promosi",
        color_discrete_sequence=["#38bdf8"]
    )
    fig_trend.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#ffffff")
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# --- TAB 06: INPUT & RESET DATA ---
elif selected_tab == "06 · Input & Reset Data":
    st.title("✏️ Form Input & Kelola Data Sales (Editor)")
    
    tab_in1, tab_in2 = st.tabs(["Input/Hapus Sales Personil", "Update/Hapus Sales Item Toko"])
    
    with tab_in1:
        st.subheader("Kelola Sales Personil")
        f_period_name = st.selectbox("Periode", list(periods_dict.keys()), key="in_p_per")
        f_date = st.date_input("Tanggal Transaksi", key="in_p_date")
        f_person = st.selectbox("Nama Staf", st.session_state.person_df["person_name"].tolist(), key="in_p_pers")
        
        p_id_val = periods_dict[f_period_name]
        filtered_si = st.session_state.sales_item_df[st.session_state.sales_item_df["period_id"] == p_id_val]
        item_dict = {row["item_name"]: row["item_id"] for _, row in filtered_si.iterrows()}
        
        if item_dict:
            f_item_name = st.selectbox("Pilih Produk", list(item_dict.keys()), key="in_p_item")
            f_qty = st.number_input("Jumlah Qty (Pcs)", min_value=0, step=1, key="in_p_qty")
            
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("💾 Simpan Data Personil", use_container_width=True):
                    new_id = f"SP{len(st.session_state.sales_person_df)+1:05d}"
                    person_row = st.session_state.person_df[st.session_state.person_df["person_name"] == f_person].iloc[0]
                    
                    new_row = {
                        "record_id": new_id,
                        "period_id": p_id_val,
                        "item_id": item_dict[f_item_name],
                        "item_name": f_item_name,
                        "person_id": person_row["person_id"],
                        "person_name": f_person,
                        "actual_qty": f_qty,
                        "updated_at": str(f_date)
                    }
                    st.session_state.sales_person_df = pd.concat([st.session_state.sales_person_df, pd.DataFrame([new_row])], ignore_index=True)
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.success("Data berhasil disimpan ke Excel!")
            with cb2:
                if st.button("🗑️ Hapus Transaksi Staf", use_container_width=True):
                    st.session_state.sales_person_df = st.session_state.sales_person_df[
                        ~((st.session_state.sales_person_df["period_id"] == p_id_val) & 
                          (st.session_state.sales_person_df["person_name"] == f_person) & 
                          (st.session_state.sales_person_df["item_id"] == item_dict[f_item_name]))
                    ]
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.warning("Data berhasil dihapus dari Excel!")
        else:
            st.warning("Tidak ada item tersedia di periode ini.")

    with tab_in2:
        st.subheader("Kelola Total Actual Item Toko")
        f_period_name_t = st.selectbox("Periode Toko", list(periods_dict.keys()), key="in_t_per")
        f_date_t = st.date_input("Tanggal Update", key="in_t_date")
        
        p_id_val_t = periods_dict[f_period_name_t]
        filtered_si_t = st.session_state.sales_item_df[st.session_state.sales_item_df["period_id"] == p_id_val_t]
        item_dict_t = {row["item_name"]: row["item_id"] for _, row in filtered_si_t.iterrows()}
        
        if item_dict_t:
            f_item_name_t = st.selectbox("Pilih Produk Toko", list(item_dict_t.keys()), key="in_t_item")
            f_actual_t = st.number_input("Actual Qty Toko (Pcs)", min_value=0, step=1, key="in_t_act")
            
            ct1, ct2 = st.columns(2)
            with ct1:
                if st.button("📦 Update Total Toko", use_container_width=True):
                    idx = st.session_state.sales_item_df[
                        (st.session_state.sales_item_df["period_id"] == p_id_val_t) & 
                        (st.session_state.sales_item_df["item_name"] == f_item_name_t)
                    ].index
                    
                    if not idx.empty:
                        st.session_state.sales_item_df.loc[idx, "actual_qty"] = f_actual_t
                        st.session_state.sales_item_df.loc[idx, "updated_at"] = str(f_date_t)
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.success("Aktual produk toko berhasil diperbarui di Excel!")
            with ct2:
                if st.button("🗑️ Hapus Record Produk Toko", use_container_width=True):
                    st.session_state.sales_item_df = st.session_state.sales_item_df[
                        ~((st.session_state.sales_item_df["period_id"] == p_id_val_t) & 
                          (st.session_state.sales_item_df["item_name"] == f_item_name_t))
                    ]
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.warning("Record produk toko berhasil dihapus!")
        else:
            st.warning("Tidak ada item tersedia di periode ini.")
            
