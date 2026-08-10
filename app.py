import streamlit as st
import pandas as pd
from datetime import datetime

# Konfigurasi Halaman Dashboard
st.set_page_config(page_title="PSM Toko - Sales Dashboard", layout="wide")

# --- SIMULASI DATABASE / DATA DUMMY (Bisa diubah/koneksi ke Google Sheets nantinya) ---
if "periods" not in st.session_state:
    st.session_state.periods = [
        {"period_id": "P01", "period_name": "Periode 1 ", "start_date": "2026-08-01", "end_date": "2026-08-07"},
        {"period_id": "P02", "period_name": "Periode 2 ", "start_date": "2026-08-08", "end_date": "2026-08-15"}
    ]

if "master_items" not in st.session_state:
    st.session_state.master_items = [
        {"period_id": "P01", "item_id": "I01", "item_name": "Baby Happy", "target_qty": 500, "target_kasir": 100},
        {"period_id": "P01", "item_id": "I02", "item_name": "Goodtime", "target_qty": 300, "target_kasir": 60},
        {"period_id": "P02", "item_id": "I03", "item_name": "Aqua Galon", "target_qty": 400, "target_kasir": 80}
    ]

if "personil_sales" not in st.session_state:
    st.session_state.personil_sales = []

if "store_items_sales" not in st.session_state:
    st.session_state.store_items_sales = []

if "master_persons" not in st.session_state:
    st.session_state.master_persons = ["Tika", "Aris", "Rizki"]

# --- SIDEBAR & AUTENTIKASI LOGIN ---
st.sidebar.image("https://tse3.mm.bing.net/th/id/OIP.mVrKCdnlL5Yc-3wRmzFXOAAAAA?r=0&rs=1&pid=ImgDetMain&o=7&rm=3", width=60)
st.sidebar.title("PSM TOKO")
st.sidebar.markdown("<small>Sales Dashboard & Input System</small>", unsafe_allow_html=True)
st.sidebar.markdown("---")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.sidebar.subheader("🔒 Login Editor")
    u_input = st.sidebar.text_input("Username")
    p_input = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if u_input == "admin" and p_input == "admin123":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.sidebar.error("Username/Password salah!")
    mode_text = "Viewer (Read-Only)"
else:
    st.sidebar.success("Status: Login sebagai Editor")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    mode_text = "Editor"

st.sidebar.markdown(f"Mode Akses: **{mode_text}**")
st.sidebar.markdown("---")

# Menu Navigasi
menu_options = ["01 · Overview", "02 · Detail Item", "03 · Penjualan Personil", "04 · Pencapaian Pernik", "05 · Analisis Tren"]
if st.session_state.logged_in:
    menu_options.append("06 · Input & Reset Data")

selected_tab = st.sidebar.selectbox("Pilih Menu", menu_options)

# Global Filter Periode
all_periods_dict = {p["period_name"]: p["period_id"] for p in st.session_state.periods}
selected_period_name = st.selectbox("🌟 Pilih Periode Laporan", ["Semua Periode (Overall)"] + list(all_periods_dict.keys()))
selected_period_id = None if selected_period_name == "Semua Periode (Overall)" else all_periods_dict[selected_period_name]

st.markdown("---")

# --- TAB 01: OVERVIEW ---
if selected_tab == "01 · Overview":
    st.title("📊 Overview Penjualan Toko")
    
    # Filter item berdasarkan periode
    items_df = pd.DataFrame(st.session_state.master_items)
    if selected_period_id:
        items_df = items_df[items_df["period_id"] == selected_period_id]
    
    tot_target = items_df["target_qty"].sum() if not items_df.empty else 0
    
    # Hitung actual dari store sales
    actual_df = pd.DataFrame(st.session_state.store_items_sales)
    tot_actual = actual_df["actual_qty"].sum() if not actual_df.empty else 0
    ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0
    gap = tot_actual - tot_target

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Target Toko", f"{tot_target:,} Pcs")
    c2.metric("Actual Sales", f"{tot_actual:,} Pcs")
    c3.metric("Achievement", f"{ach:.1f}%")
    c4.metric("Gap Target", f"{gap:,} Pcs")

    st.subheader("📅 Ringkasan Periode Penjualan Toko")
    period_summary = []
    for p in st.session_state.periods:
        p_id = p["period_id"]
        p_target = sum([x["target_qty"] for x in st.session_state.master_items if x["period_id"] == p_id])
        p_actual = sum([x["actual_qty"] for x in st.session_state.store_items_sales if x["period_id"] == p_id])
        p_ach = (p_actual / p_target * 100) if p_target > 0 else 0
        period_summary.append({
            "ID Periode": p_id,
            "Nama Periode": p["period_name"],
            "Rentang Tanggal": f"{p['start_date']} s/d {p['end_date']}",
            "Target Total": f"{p_target:,} Pcs",
            "Actual Total": f"{p_actual:,} Pcs",
            "% Ach Toko": f"{p_ach:.1f}%"
        })
    st.table(pd.DataFrame(period_summary))

# --- TAB 02: DETAIL ITEM ---
elif selected_tab == "02 · Detail Item":
    st.title("📦 Detail Item & Performa")
    
    items_df = pd.DataFrame(st.session_state.master_items)
    if selected_period_id:
        items_df = items_df[items_df["period_id"] == selected_period_id]
    
    if not items_df.empty:
        # Gabungkan actual sales per item
        actual_agg = pd.DataFrame(st.session_state.store_items_sales)
        if not actual_agg.empty:
            actual_agg = actual_agg.groupby("item_id")["actual_qty"].sum().reset_index()
            merged = pd.merge(items_df, actual_agg, on="item_id", how="left").fillna(0)
        else:
            merged = items_df.copy()
            merged["actual_qty"] = 0
            
        merged["ach"] = merged.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)
        
        # Top & Bad Performance Card
        if not merged.empty:
            top_item = merged.loc[merged["ach"].idxmax()]
            bad_item = merged.loc[merged["ach"].idxmin()]
            
            col_t, col_b = st.columns(2)
            with col_t:
                st.markdown(f"**🔥 Top Performance:** {top_item['item_name']} ({top_item['ach']:.1f}%)")
            with col_b:
                st.markdown(f"**⚠️ Bad Performance:** {bad_item['item_name']} ({bad_item['ach']:.1f}%)")
        
        search_query = st.text_input("🔍 Cari Nama Item")
        if search_query:
            merged = merged[merged["item_name"].str.contains(search_query, case=False, na=False)]
            
        st.dataframe(merged[["item_id", "item_name", "target_qty", "actual_qty", "ach"]], use_container_width=True)
    else:
        st.info("Belum ada data item untuk periode ini.")

# --- TAB 03: PENJUALAN PERSONIL ---
elif selected_tab == "03 · Penjualan Personil":
    st.title("👥 Penjualan Personil / Staf")
    p_sales_df = pd.DataFrame(st.session_state.personil_sales)
    if selected_period_id and not p_sales_df.empty:
        p_sales_df = p_sales_df[p_sales_df["period_id"] == selected_period_id]
        
    if not p_sales_df.empty:
        summary_person = p_sales_df.groupby("person_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        st.dataframe(summary_person, use_container_width=True)
    else:
        st.info("Belum ada data penjualan personil.")

# --- TAB 04: PENCAPAIAN PERNIK ---
elif selected_tab == "04 · Pencapaian Pernik":
    st.title("🏆 Pencapaian Pernik Per Personil")
    selected_person = st.selectbox("Pilih Staf Toko", st.session_state.master_persons)
    
    items_df = pd.DataFrame(st.session_state.master_items)
    if selected_period_id:
        items_df = items_df[items_df["period_id"] == selected_period_id]
        
    st.write(f"Rincian target kasir untuk staf: **{selected_person}**")
    st.dataframe(items_df, use_container_width=True)

# --- TAB 05: ANALISIS TREN ---
elif selected_tab == "05 · Analisis Tren":
    st.title("📈 Analisis Tren Harian & Estimasi")
    st.write("Fitur analisis ritme penjualan harian toko.")

# --- TAB 06: INPUT & RESET DATA (KHUSUS EDITOR) ---
elif selected_tab == "06 · Input & Reset Data":
    st.title("✏️ Form Input & Penghapusan Data Sales")
    
    tab_in1, tab_in2 = st.tabs(["Input/Hapus Sales Personil", "Update/Hapus Total Toko"])
    
    with tab_in1:
        st.subheader("Kelola Data Sales Personil")
        f_period = st.selectbox("Periode", list(all_periods_dict.keys()), key="in_p_per")
        f_date = st.date_input("Tanggal Penjualan", key="in_p_date")
        f_person = st.selectbox("Nama Staf", st.session_state.master_persons, key="in_p_pers")
        
        # Filter item berdasarkan periode yang dipilih
        p_id_val = all_periods_dict[f_period]
        filtered_items = [i for i in st.session_state.master_items if i["period_id"] == p_id_val]
        item_names = {i["item_name"]: i["item_id"] for i in filtered_items}
        
        if item_names:
            f_item_name = st.selectbox("Pilih Item", list(item_names.keys()), key="in_p_item")
            f_qty = st.number_input("Jumlah Qty (Pcs)", min_value=0, step=1, key="in_p_qty")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("💾 Simpan Penjualan Staf", use_container_width=True):
                    st.session_state.personil_sales.append({
                        "period_id": p_id_val,
                        "date": str(f_date),
                        "person_name": f_person,
                        "item_id": item_names[f_item_name],
                        "actual_qty": f_qty
                    })
                    st.success("Data penjualan staf berhasil disimpan!")
            with col_btn2:
                if st.button("🗑️ Hapus Data (Berdasarkan Tanggal & Item)", use_container_width=True):
                    # Hapus data yang cocok dengan tanggal dan item
                    st.session_state.personil_sales = [
                        x for x in st.session_state.personil_sales 
                        if not (x["period_id"] == p_id_val and x["date"] == str(f_date) and x["item_id"] == item_names[f_item_name] and x["person_name"] == f_person)
                    ]
                    st.warning("Data berhasil dihapus dari database!")
        else:
            st.info("Tidak ada item tersedia pada periode promosi ini.")

    with tab_in2:
        st.subheader("Kelola Total Penjualan Toko")
        f_period_t = st.selectbox("Periode Toko", list(all_periods_dict.keys()), key="in_t_per")
        f_date_t = st.date_input("Tanggal Toko", key="in_t_date")
        
        p_id_val_t = all_periods_dict[f_period_t]
        filtered_items_t = [i for i in st.session_state.master_items if i["period_id"] == p_id_val_t]
        item_names_t = {i["item_name"]: i["item_id"] for i in filtered_items_t}
        
        if item_names_t:
            f_item_name_t = st.selectbox("Pilih Item Toko", list(item_names_t.keys()), key="in_t_item")
            f_qty_t = st.number_input("Actual Total Toko (Pcs)", min_value=0, step=1, key="in_t_qty")
            
            col_bt1, col_bt2 = st.columns(2)
            with col_bt1:
                if st.button("📦 Update / Simpan Total Toko", use_container_width=True):
                    st.session_state.store_items_sales.append({
                        "period_id": p_id_val_t,
                        "date": str(f_date_t),
                        "item_id": item_names_t[f_item_name_t],
                        "actual_qty": f_qty_t
                    })
                    st.success("Total item toko berhasil diperbarui!")
            with col_bt2:
                if st.button("🗑️ Hapus Data Toko (Sesuai Tanggal)", use_container_width=True):
                    st.session_state.store_items_sales = [
                        x for x in st.session_state.store_items_sales
                        if not (x["period_id"] == p_id_val_t and x["date"] == str(f_date_t) and x["item_id"] == item_names_t[f_item_name_t])
                    ]
                    st.warning("Data toko berhasil dihapus!")
        else:
            st.info("Tidak ada item tersedia pada periode promosi ini.")
