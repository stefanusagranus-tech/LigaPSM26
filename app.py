import streamlit as st
import pandas as pd
import numpy as np
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo

# --- CONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Dashboard PSM & Pernik Toko",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS UNTUK TEMA NEON DARK MODE ---
st.markdown("""
<style>
    .stApp {
        background-color: #030712;
        color: #f3f4f6;
    }
    .main-header {
        background: linear-gradient(90deg, #0f172a 0%, #1e1b4b 100%);
        padding: 15px 20px;
        border-radius: 12px;
        border: 1px solid #312e81;
        margin-bottom: 20px;
    }
    .kpi-card {
        background-color: #0b0f19;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
    }
    .stMetric {
        background-color: #080c14;
        border: 1px solid #1e293b;
        padding: 12px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE PENGGUNA (LOGIN) ---
USER_DATABASE = {
    "admin": {"password": "c383kgs", "nama": "Staff Toko"},
    "20220002": {"password": "c383kgs", "nama": "Aris Aprilianto"},
    "20220007": {"password": "c383kgs", "nama": "Tika"},
    "20220009": {"password": "c383kgs", "nama": "Rizki Gunawan"},
    "20220019": {"password": "c383kgs", "nama": "Adelia Pratiwi"},
    "20220034": {"password": "c383kgs", "nama": "Ilham Priandika"},
    "20220096": {"password": "c383kgs", "nama": "Reza Purnama Agustin"},
    "20220059": {"password": "c383kgs", "nama": "Subekti Pandu Yulianto"},
    "20220055": {"password": "c383kgs", "nama": "Kusdewi Tia Ningrum"}
}

# --- INITIALIZE SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# Sample Mock Master Data (Jika belum ada data dari database/excel)
if "periods_df" not in st.session_state:
    st.session_state.periods_df = pd.DataFrame([
        {"period_id": "P01", "period_name": "Periode Awal Bulan", "start_date": "2026-08-01", "end_date": "2026-08-31"}
    ])

if "person_df" not in st.session_state:
    st.session_state.person_df = pd.DataFrame([
        {"person_name": "Staff Toko"},
        {"person_name": "Aris Aprilianto"},
        {"person_name": "Tika"},
        {"person_name": "Rizki Gunawan"},
        {"person_name": "Adelia Pratiwi"},
        {"person_name": "Ilham Priandika"},
        {"person_name": "Reza Purnama Agustin"},
        {"person_name": "Subekti Pandu Yulianto"},
        {"person_name": "Kusdewi Tia Ningrum"}
    ])

if "sales_item_df" not in st.session_state:
    st.session_state.sales_item_df = pd.DataFrame([
        {"period_id": "P01", "item_id": "ITM01", "item_name": "Pernik A", "target_kasir": 100, "target_qty": 100, "actual_qty": 0},
        {"period_id": "P01", "item_id": "ITM02", "item_name": "Pernik B", "target_kasir": 150, "target_qty": 150, "actual_qty": 0},
        {"period_id": "P01", "item_id": "ITM03", "item_name": "Pernik C", "target_kasir": 80, "target_qty": 80, "actual_qty": 0}
    ])

if "sales_person_df" not in st.session_state:
    st.session_state.sales_person_df = pd.DataFrame([
        {"period_id": "P01", "person_name": "Aris Aprilianto", "item_id": "ITM01", "item_name": "Pernik A", "actual_qty": 20, "updated_at": "2026-08-10"},
        {"period_id": "P01", "person_name": "Aris Aprilianto", "item_id": "ITM02", "item_name": "Pernik B", "actual_qty": 15, "updated_at": "2026-08-10"},
        {"period_id": "P01", "person_name": "Tika", "item_id": "ITM01", "item_name": "Pernik A", "actual_qty": 30, "updated_at": "2026-08-11"}
    ])


# --- FUNGSI SINKRONISASI PENJUALAN PERSONIL KE PENJUALAN TOKO ---
def sync_store_sales_from_personnel():
    """
    Otomatis merekap seluruh total penjualan staf dan memperbarui 
    actual_qty toko secara real-time.
    """
    if "sales_person_df" in st.session_state and "sales_item_df" in st.session_state:
        sp_df = st.session_state.sales_person_df.copy()
        sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)
        
        # Total per item dan periode
        tot_per_item = sp_df.groupby(["period_id", "item_id"])["actual_qty"].sum().reset_index()
        tot_per_item.rename(columns={"actual_qty": "calc_actual_qty"}, inplace=True)
        
        si_df = st.session_state.sales_item_df.copy()
        if "calc_actual_qty" in si_df.columns:
            si_df.drop(columns=["calc_actual_qty"], inplace=True)
            
        merged = pd.merge(si_df, tot_per_item, on=["period_id", "item_id"], how="left")
        merged["calc_actual_qty"] = merged["calc_actual_qty"].fillna(0)
        
        # Override actual_qty di toko
        merged["actual_qty"] = merged["calc_actual_qty"]
        merged.drop(columns=["calc_actual_qty"], inplace=True)
        
        st.session_state.sales_item_df = merged


# --- HALAMAN LOGIN ---
def show_login_page():
    st.markdown("<h2 style='text-align: center; color: #00f0ff;'>🔐 LOGIN SYSTEM TOKO</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username / ID Karyawan", placeholder="Masukkan ID / Username").strip()
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


# --- CEK STATUS LOGIN ---
if not st.session_state.logged_in:
    show_login_page()
    st.stop()


# --- HEADER UTAMA & JAM REAL-TIME GMT+7 ---
waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
tanggal_str = waktu_wib.strftime("%A, %d %B %Y")
jam_str = waktu_wib.strftime("%H:%M:%S WIB")

current_user = st.session_state.get("username", "Pengguna")
is_admin = (current_user == "Staff Toko") or (current_user == "Admin")

st.markdown(f"""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h3 style="margin: 0; color: #00f0ff;">👋 Selamat Datang, {current_user}!</h3>
                <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 13px;">Role: <b>{"ADMINISTRATOR" if is_admin else "STAFF / KASIR"}</b></p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 16px; font-weight: bold; color: #00ff88;">🕒 {jam_str}</div>
                <div style="font-size: 12px; color: #94a3b8;">📅 {tanggal_str}</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)


# --- SIDEBAR & NAVIGASI MENU ---
with st.sidebar:
    st.title("📌 Navigation")
    
    selected_period_id = None
    if not st.session_state.periods_df.empty:
        period_options = st.session_state.periods_df["period_id"].tolist()
        selected_period_id = st.selectbox("📅 Pilih Periode Toko", period_options)
        
    selected_tab = st.radio(
        "Pilih Menu Dashboard:",
        [
            "01 · Overview Penjualan",
            "02 · Update Penjualan Staf",
            "03 · Monitoring PSM",
            "04 · Pencapaian Pernik",
            "05 · Analisis Tren"
        ]
    )
    
    st.markdown("---")
    if st.button("🚪 Logout / Keluar", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()


# --- TAB 02: UPDATE PENJUALAN STAF (AKSES TERBATAS & AUTO-SYNC) ---
if selected_tab == "02 · Update Penjualan Staf":
    st.title("📝 Input & Update Penjualan Personil")
    
    person_list = st.session_state.person_df["person_name"].dropna().unique().tolist()
    
    # 1. LOGIKA PEMBATASAN AKSES USER
    if is_admin:
        selected_person_name = st.selectbox("👤 Pilih Personil Toko (Mode Admin)", options=person_list)
    else:
        selected_person_name = current_user
        st.info(f"🔒 **Mode Staf**: Anda saat ini hanya mengedit data laporan untuk akun: **{current_user}**")
        
    st.markdown("---")
    
    # Form Input Penjualan
    si_df = st.session_state.sales_item_df.copy()
    if selected_period_id:
        si_df = si_df[si_df["period_id"] == selected_period_id]
        
    with st.form("form_update_penjualan"):
        st.subheader(f"Input Penjualan: {selected_person_name}")
        
        input_data = {}
        for _, row in si_df.iterrows():
            item_id = row["item_id"]
            item_name = row["item_name"]
            
            # Cari nilai actual sebelumnya dari sales_person_df
            sp_df = st.session_state.sales_person_df
            existing_val = sp_df[(sp_df["person_name"] == selected_person_name) & 
                                 (sp_df["item_id"] == item_id)]
            
            default_qty = int(existing_val["actual_qty"].values[0]) if not existing_val.empty else 0
            
            input_data[item_id] = st.number_input(
                f"Jumlah Terjual: {item_name}", 
                min_value=0, 
                value=default_qty,
                step=1
            )
            
        submit_save_btn = st.form_submit_button("💾 Simpan & Sinkronkan Penjualan", use_container_width=True)
        
        if submit_save_btn:
            sp_df = st.session_state.sales_person_df.copy()
            today_str = waktu_wib.strftime("%Y-%m-%d")
            
            for item_id, qty in input_data.items():
                item_name = si_df[si_df["item_id"] == item_id]["item_name"].values[0]
                
                # Cek jika baris data sudah ada
                mask = (sp_df["person_name"] == selected_person_name) & \
                       (sp_df["item_id"] == item_id) & \
                       (sp_df["period_id"] == selected_period_id)
                
                if mask.any():
                    sp_df.loc[mask, "actual_qty"] = qty
                    sp_df.loc[mask, "updated_at"] = today_str
                else:
                    new_row = pd.DataFrame([{
                        "period_id": selected_period_id,
                        "person_name": selected_person_name,
                        "item_id": item_id,
                        "item_name": item_name,
                        "actual_qty": qty,
                        "updated_at": today_str
                    }])
                    sp_df = pd.concat([sp_df, new_row], ignore_index=True)
            
            # Simpan data personil
            st.session_state.sales_person_df = sp_df
            
            # 2. PROSES AUTO-SYNC PENJUALAN KE TOKO
            sync_store_sales_from_personnel()
            
            st.success("✅ Data penjualan berhasil disimpan dan otomatis disinkronkan ke Penjualan Toko!")
            st.rerun()


# --- TAB 04: PENCAPAIAN PERNIK PER PERSONIL ---
elif selected_tab == "04 · Pencapaian Pernik":
    st.title("🏆 Pencapaian Pernik Per Personil")
    
    person_list = st.session_state.person_df["person_name"].dropna().unique().tolist()
    if not person_list:
        person_list = st.session_state.sales_person_df["person_name"].dropna().unique().tolist()
        
    c_p1, _ = st.columns([1.5, 1])
    with c_p1:
        selected_person = st.selectbox(
            "👤 PILIH PERSONIL TOKO", 
            person_list, 
            key="tab4_person_select",
            help="Filter laporan item pernik spesifik per staf"
        )
    
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
    merged_item_df["ach"] = merged_item_df.apply(
        lambda r: (r["actual_qty"] / r["target_val"] * 100) if r["target_val"] > 0 else 0, axis=1
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
    
    with col_t4_left:
        st.subheader("📋 Rincian Target Item Pernik")
        table_rows_html = ""
        for _, row in merged_item_df.iterrows():
            gap_color = "#00ff88" if row['gap'] <= 0 else "#ef4444"
            ach_color = "#00ff88" if row['ach'] >= 100 else "#ffb703"
            
            table_rows_html += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 10px; color: #ffffff; font-weight: bold; font-size: 13px;">{row['item_name']}</td>
                <td style="padding: 10px; color: #94a3b8; font-size: 13px;">{row['target_val']:,.0f}</td>
                <td style="padding: 10px; color: #00ff88; font-weight: bold; font-size: 13px;">{row['actual_qty']:,.0f}</td>
                <td style="padding: 10px; color: {gap_color}; font-size: 13px;">{row['gap']:,.0f}</td>
                <td style="padding: 10px; color: {ach_color}; font-weight: bold; font-size: 13px;">{row['ach']:.1f}%</td>
            </tr>
            """
            
        st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00f0ff; border-radius: 10px; padding: 10px; max-height: 380px; overflow-y: auto;">
                <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 2px solid #334155;">
                            <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">NAMA ITEM</th>
                            <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">TARGET KASIR</th>
                            <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">ACTUAL</th>
                            <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">GAP</th>
                            <th style="padding: 8px 10px; color: #38bdf8; font-size: 11px;">% ACH</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows_html}</tbody>
                </table>
            </div>
        """, unsafe_allow_html=True)
        
    with col_t4_right:
        st.subheader("📊 Visual Breakdown Item")
        fig_p4 = go.Figure()
        fig_p4.add_trace(go.Bar(
            y=merged_item_df["item_name"], x=merged_item_df["actual_qty"],
            name="Actual", orientation='h', marker_color="#00f2fe",
            text=merged_item_df["actual_qty"].apply(lambda x: f"{x:,.0f}"), textposition="auto"
        ))
        fig_p4.add_trace(go.Bar(
            y=merged_item_df["item_name"], x=merged_item_df["target_val"],
            name="Target Kasir", orientation='h', marker_color="#64748b",
            text=merged_item_df["target_val"].apply(lambda x: f"{x:,.0f}"), textposition="auto"
        ))
        fig_p4.update_layout(
            barmode='group', height=380, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#ffffff"), xaxis=dict(showgrid=True, gridcolor="#1e293b"),
            yaxis=dict(showgrid=False, autorange="reversed"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_p4, use_container_width=True)


# --- TAB 05: ANALISIS TREN HARIAN ---
elif selected_tab == "05 · Analisis Tren":
    st.title("📈 Analisis Tren Harian & Target")
    
    si_df = st.session_state.sales_item_df.copy()
    periods_df = st.session_state.periods_df.copy()
    
    if selected_period_id:
        sub_periods = periods_df[periods_df["period_id"] == selected_period_id]
        sub_si = si_df[si_df["period_id"] == selected_period_id]
    else:
        sub_periods = periods_df
        sub_si = si_df
        
    sub_si["target_qty"] = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0)
    sub_si["actual_qty"] = pd.to_numeric(sub_si["actual_qty"], errors="coerce").fillna(0)
    
    tot_target = sub_si["target_qty"].sum()
    tot_actual = sub_si["actual_qty"].sum()
    
    if not sub_periods.empty:
        p_row = sub_periods.iloc[0]
        s_date = pd.to_datetime(p_row["start_date"])
        e_date = pd.to_datetime(p_row["end_date"])
        total_days = max((e_date - s_date).days + 1, 1)
        today_date = pd.to_datetime(waktu_wib.strftime("%Y-%m-%d"))
        
        if today_date < s_date:
            passed_days = 1
        elif today_date > e_date:
            passed_days = total_days
        else:
            passed_days = max((today_date - s_date).days + 1, 1)
    else:
        total_days = 31
        passed_days = max(waktu_wib.day, 1)
        
    remaining_days = max(total_days - passed_days, 1)
    daily_target_ideal = max(0, int((tot_target - tot_actual) / remaining_days))
    avg_daily_sales = tot_actual / passed_days
    best_est = int(tot_actual + (avg_daily_sales * remaining_days))
    
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("🎯 Target Periode", f"{tot_target:,.0f} Pcs")
    with k2:
        st.metric("⚡ Target Harian Ideal", f"{daily_target_ideal:,.0f} Pcs/Hari")
    with k3:
        st.metric("📦 Pencapaian Actual", f"{tot_actual:,.0f} Pcs")
    with k4:
        st.metric("🔮 Best Estimasi Akhir", f"{best_est:,.0f} Pcs")
        
    st.markdown("---")
    
    st.subheader("📈 Grafik Fluktuasi Penjualan Harian")
    sp_df = st.session_state.sales_person_df.copy()
    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
        
    sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)
    
    if "updated_at" in sp_df.columns and not sp_df.empty:
        daily_trend = sp_df.groupby("updated_at")["actual_qty"].sum().reset_index().sort_values(by="updated_at")
    else:
        daily_trend = pd.DataFrame({
            "updated_at": [f"Hari {i+1}" for i in range(passed_days)],
            "actual_qty": [tot_actual / passed_days] * passed_days
        })
        
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=daily_trend["updated_at"], y=daily_trend["actual_qty"],
        mode='lines+markers', name="Penjualan Harian",
        line=dict(color="#00f2fe", width=3), marker=dict(size=8)
    ))
    fig_trend.add_trace(go.Scatter(
        x=daily_trend["updated_at"], y=[daily_target_ideal] * len(daily_trend),
        mode='lines', name="Target Harian Ideal",
        line=dict(color="#ff2a6d", dash='dash', width=2)
    ))
    fig_trend.update_layout(
        height=320, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#ffffff"), xaxis=dict(showgrid=True, gridcolor="#1e293b"),
        yaxis=dict(showgrid=True, gridcolor="#1e293b"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    
    st.markdown("---")
    
    col_g, col_d = st.columns(2)
    item_perf = sub_si.groupby("item_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
    top_item_name = item_perf.iloc[0]["item_name"] if not item_perf.empty else "-"
    
    with col_g:
        st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #00ff9d; border-left: 6px solid #00ff9d; border-radius: 10px; padding: 16px;">
                <h4 style="color: #00ff9d; margin: 0 0 8px 0;">🔥 Insight Growth (Penjualan Melonjak)</h4>
                <p style="color: #f1f5f9; margin: 0; font-size: 14px;">
                    Performa terbaik dicapai pada item <b>{top_item_name}</b> dengan kontribusi penjualan tertinggi di periode ini.
                </p>
            </div>
        """, unsafe_allow_html=True)
        
    with col_d:
        gap_rem = max(0, tot_target - tot_actual)
        st.markdown(f"""
            <div style="background: #080c14; border: 1.5px solid #ff2a6d; border-left: 6px solid #ff2a6d; border-radius: 10px; padding: 16px;">
                <h4 style="color: #ff2a6d; margin: 0 0 8px 0;">⚠️ Insight Disgrowth (Penjualan Drop)</h4>
                <p style="color: #f1f5f9; margin: 0; font-size: 14px;">
                    Sisa target sebesar <b>{gap_rem:,.0f} Pcs</b>. Dibutuhkan rata-rata tambahan <b>~{daily_target_ideal:,.0f} Pcs/hari</b> selama sisa <b>{remaining_days} hari</b>.
                </p>
            </div>
        """, unsafe_allow_html=True)


# --- TAB LAINNYA (OVERVIEW & MONITORING PSM) ---
else:
    st.title("📊 Overview Penjualan & Monitoring PSM")
    st.info("Pilih menu **02 · Update Penjualan Staf**, **04 · Pencapaian Pernik**, atau **05 · Analisis Tren** pada sidebar untuk melihat detail data.")
