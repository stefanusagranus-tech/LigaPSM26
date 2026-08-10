import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt

# Konfigurasi Halaman Dashboard (Lebar penuh)
st.set_page_config(page_title="PSM Toko - Sales Dashboard", layout="wide")

EXCEL_FILE = "Database_Penjualan_PSM_Toko_Clean_GoogleSheets.xlsx"

# --- CUSTOM CSS UNTUK TAMPILAN NEON / DARK MODE FUTURISTIK ---
st.markdown("""
    <style>
    /* Mengubah latar belakang utama menjadi gelap */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Styling untuk kartu metrik / kotak border */
    div.metric-card, div[data-testid="stMetric"], .css-1r6slb0 {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    
    /* Warna teks header */
    h1, h2, h3 {
        color: #f0f6fc !important;
    }
    
    /* Styling Sidebar */
    [data-testid="stSidebar"] {
        background-color: #111418;
        border-right: 1px solid #30363d;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNGSI LOAD & SAVE DATA EXCEL ---
def load_database():
    if not os.path.exists(EXCEL_FILE):
        st.error(f"File database '{EXCEL_FILE}' tidak ditemukan di folder yang sama!")
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

# Inisialisasi Session State
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

# --- SIDEBAR & NAVIGASI ---
st.sidebar.image("https://tse3.mm.bing.net/th/id/OIP.mVrKCdnlL5Yc-3wRmzFXOAAAAA?r=0&rs=1&pid=ImgDetMain&o=7&rm=3", width=60)
st.sidebar.title("PSM TOKO")
st.sidebar.markdown("<small>Sales Dashboard & Input System</small>", unsafe_allow_html=True)
st.sidebar.markdown("---")

menu_options = [
    "01 · Overview", 
    "02 · Detail Item", 
    "03 · Penjualan Personil", 
    "04 · Pencapaian Pernik", 
    "05 · Analisis Tren"
]

if st.session_state.logged_in:
    menu_options.append("06 · Input & Reset Data")

selected_tab = st.sidebar.selectbox("📌 Navigasi Menu", menu_options)

st.sidebar.markdown("---")
periods_dict = {row["period_name"]: row["period_id"] for _, row in st.session_state.periods_df.iterrows()}
selected_period_name = st.selectbox("🌟 Pilih Periode Laporan", ["Semua Periode (Overall)"] + list(periods_dict.keys()))
selected_period_id = None if selected_period_name == "Semua Periode (Overall)" else periods_dict[selected_period_name]

# Area Login Admin dengan ikon kunci di bawah
st.sidebar.markdown("---")
with st.sidebar.expander("🔑 Login Admin / Editor"):
    if not st.session_state.logged_in:
        u_input = st.text_input("Username", key="u_login")
        p_input = st.text_input("Password", type="password", key="p_login")
        if st.button("Masuk"):
            if u_input == "admin" and p_input == "admin123":
                st.session_state.logged_in = True
                st.success("Login berhasil!")
                st.rerun()
            else:
                st.error("Username/Password salah!")
    else:
        st.success("Status: Login sebagai Editor")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

# --- TAB 01: OVERVIEW (DENGAN CHART & KARTU NEON) ---
if selected_tab == "01 · Overview":
    st.title("📊 Overview Penjualan Toko")
    st.markdown(f"<p style='color: #8b949e;'>Laporan performa toko harian • {pd.Timestamp.today().strftime('%d %b %Y')}</p>", unsafe_allow_html=True)
    
    si_df = st.session_state.sales_item_df.copy()
    if selected_period_id:
        si_df = si_df[si_df["period_id"] == selected_period_id]
        
    si_df["target_qty"] = pd.to_numeric(si_df["target_qty"], errors="coerce").fillna(0)
    si_df["actual_qty"] = pd.to_numeric(si_df["actual_qty"], errors="coerce").fillna(0)
    
    tot_target = si_df["target_qty"].sum()
    tot_actual = si_df["actual_qty"].sum()
    ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0
    gap = tot_actual - tot_target

    # Baris 1: Kotak Metrik Utama (Gaya Kartu Gelap)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🎯 TARGET", f"{tot_target:,.0f}")
    with c2:
        st.metric("📦 ACTUAL", f"{tot_actual:,.0f}")
    with c3:
        st.metric("⚡ ACHIEVEMENT", f"{ach:.1f}%")
    with c4:
        st.metric("📉 GAP", f"{gap:,.0f}")

    st.markdown("---")
    
    # Baris 2: Visualisasi Grafik (Bar Chart & Donut Chart)
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.subheader("📈 Target vs Achievement per Periode")
        # Membuat Bar Chart menggunakan Streamlit/Altair atau Matplotlib
        chart_data = st.session_state.sales_item_df.groupby("period_id")[["target_qty", "actual_qty"]].sum().reset_index()
        st.bar_chart(chart_data.set_index("period_id"), color=["#1f77b4", "#00d4ff"])

    with col_chart2:
        st.subheader("🍩 Donut Kontribusi Item")
        if not si_df.empty:
            top_items = si_df.groupby("item_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False).head(5)
            # Tampilkan sebagai progress bar interaktif atau ringkasan kontribusi
            for _, row in top_items.iterrows():
                pct = (row["actual_qty"] / tot_actual * 100) if tot_actual > 0 else 0
                st.text(f"{row['item_name']} — {pct:.1f}%")
                st.progress(min(int(pct), 100))
        else:
            st.info("Belum ada data.")

    st.markdown("---")
    st.subheader("📅 Ringkasan Periode Penjualan Toko")
    summary_data = []
    for _, p in st.session_state.periods_df.iterrows():
        p_id = p["period_id"]
        p_name = p["period_name"]
        p_target_total = p["target_total"]
        
        sub_si = st.session_state.sales_item_df[st.session_state.sales_item_df["period_id"] == p_id]
        p_actual = pd.to_numeric(sub_si["actual_qty"], errors="coerce").fillna(0).sum()
        p_target = pd.to_numeric(sub_si["target_qty"], errors="coerce").fillna(0).sum()
        if pd.isna(p_target_total):
            p_target_total = p_target
            
        p_ach = (p_actual / p_target_total * 100) if p_target_total > 0 else 0
        summary_data.append({
            "ID Periode": p_id,
            "Nama Periode": p_name,
            "Rentang Tanggal": f"{str(p['start_date'])[:10]} s/d {str(p['end_date'])[:10]}",
            "Target Total": f"{p_target_total:,.0f} Pcs",
            "Actual Total": f"{p_actual:,.0f} Pcs",
            "% Ach Toko": f"{p_ach:.1f}%"
        })
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

# --- TAB 02: DETAIL ITEM ---
elif selected_tab == "02 · Detail Item":
    st.title("📦 Detail Item & Performa")
    si_df = st.session_state.sales_item_df.copy()
    if selected_period_id:
        si_df = si_df[si_df["period_id"] == selected_period_id]
        
    si_df["target_qty"] = pd.to_numeric(si_df["target_qty"], errors="coerce").fillna(0)
    si_df["actual_qty"] = pd.to_numeric(si_df["actual_qty"], errors="coerce").fillna(0)
    si_df["ach"] = si_df.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)
    
    search_query = st.text_input("🔍 Cari Nama Item")
    if search_query:
        si_df = si_df[si_df["item_name"].str.contains(search_query, case=False, na=False)]
        
    st.dataframe(si_df[["item_id", "item_name", "target_qty", "actual_qty", "ach", "updated_at"]], use_container_width=True)

# --- TAB 03: PENJUALAN PERSONIL ---
elif selected_tab == "03 · Penjualan Personil":
    st.title("👥 Penjualan Personil / Staf")
    sp_df = st.session_state.sales_person_df.copy()
    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
    sp_df["actual_qty"] = pd.to_numeric(sp_df["actual_qty"], errors="coerce").fillna(0)
    
    if not sp_df.empty:
        summary_person = sp_df.groupby("person_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        st.dataframe(summary_person, use_container_width=True)
    else:
        st.info("Belum ada data penjualan personil.")

# --- TAB 04: PENCAPAIAN PERNIK ---
elif selected_tab == "04 · Pencapaian Pernik":
    st.title("🏆 Pencapaian Pernik Per Personil")
    person_list = st.session_state.person_df["person_name"].tolist()
    selected_person = st.selectbox("Pilih Staf Toko", person_list)
    
    sp_df = st.session_state.sales_person_df[st.session_state.sales_person_df["person_name"] == selected_person]
    if selected_period_id:
        sp_df = sp_df[sp_df["period_id"] == selected_period_id]
    st.dataframe(sp_df, use_container_width=True)

# --- TAB 05: ANALISIS TREN ---
elif selected_tab == "05 · Analisis Tren":
    st.title("📈 Analisis Tren Harian & Estimasi")
    st.write("Analisis ritme dan performa penjualan toko secara keseluruhan.")

# --- TAB 06: INPUT & RESET DATA (HANYA UNTUK ADMIN) ---
elif selected_tab == "06 · Input & Reset Data" and st.session_state.logged_in:
    st.title("✏️ Form Input & Penghapusan Data Sales")
    
    tab_in1, tab_in2 = st.tabs(["Input/Hapus Sales Personil", "Update/Hapus Sales Item Toko"])
    
    with tab_in1:
        st.subheader("Kelola Data Sales Personil")
        f_period_name = st.selectbox("Periode", list(periods_dict.keys()), key="in_p_per")
        f_date = st.date_input("Tanggal Update/Input", key="in_p_date")
        f_person = st.selectbox("Nama Staf", st.session_state.person_df["person_name"].tolist(), key="in_p_pers")
        
        p_id_val = periods_dict[f_period_name]
        filtered_si = st.session_state.sales_item_df[st.session_state.sales_item_df["period_id"] == p_id_val]
        item_dict = {row["item_name"]: row["item_id"] for _, row in filtered_si.iterrows()}
        
        if item_dict:
            f_item_name = st.selectbox("Pilih Item (Periode Promosi)", list(item_dict.keys()), key="in_p_item")
            f_qty = st.number_input("Actual Qty (Pcs)", min_value=0, step=1, key="in_p_qty")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("💾 Simpan Sales Personil", use_container_width=True):
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
                    st.success("Data berhasil disimpan!")
            with col_b2:
                if st.button("🗑️ Hapus Data Personil", use_container_width=True):
                    st.session_state.sales_person_df = st.session_state.sales_person_df[
                        ~((st.session_state.sales_person_df["period_id"] == p_id_val) & 
                          (st.session_state.sales_person_df["person_name"] == f_person) & 
                          (st.session_state.sales_person_df["item_id"] == item_dict[f_item_name]))
                    ]
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.warning("Data berhasil dihapus!")
        else:
            st.warning("Tidak ada item tersedia pada periode ini.")

    with tab_in2:
        st.subheader("Kelola / Update Target & Aktual Item Toko")
        f_period_name_t = st.selectbox("Periode Toko", list(periods_dict.keys()), key="in_t_per")
        f_date_t = st.date_input("Tanggal Update", key="in_t_date")
        
        p_id_val_t = periods_dict[f_period_name_t]
        filtered_si_t = st.session_state.sales_item_df[st.session_state.sales_item_df["period_id"] == p_id_val_t]
        item_dict_t = {row["item_name"]: row["item_id"] for _, row in filtered_si_t.iterrows()}
        
        if item_dict_t:
            f_item_name_t = st.selectbox("Pilih Item Toko", list(item_dict_t.keys()), key="in_t_item")
            f_actual_t = st.number_input("Actual Qty Toko (Pcs)", min_value=0, step=1, key="in_t_act")
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                if st.button("📦 Update Actual Toko", use_container_width=True):
                    idx = st.session_state.sales_item_df[
                        (st.session_state.sales_item_df["period_id"] == p_id_val_t) & 
                        (st.session_state.sales_item_df["item_name"] == f_item_name_t)
                    ].index
                    
                    if not idx.empty:
                        st.session_state.sales_item_df.loc[idx, "actual_qty"] = f_actual_t
                        st.session_state.sales_item_df.loc[idx, "updated_at"] = str(f_date_t)
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.success("Aktual item toko berhasil diperbarui!")
            with col_t2:
                if st.button("🗑️ Hapus Record Item Toko", use_container_width=True):
                    st.session_state.sales_item_df = st.session_state.sales_item_df[
                        ~((st.session_state.sales_item_df["period_id"] == p_id_val_t) & 
                          (st.session_state.sales_item_df["item_name"] == f_item_name_t))
                    ]
                    save_database(st.session_state.sales_item_df, st.session_state.sales_person_df)
                    st.warning("Record item toko berhasil dihapus!")
        else:
            st.warning("Tidak ada item tersedia pada periode ini.")
