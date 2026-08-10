import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Konfigurasi Halaman
st.set_page_config(page_title="PSM Toko - Sales Dashboard", layout="wide")

EXCEL_FILE = "Database_Penjualan_PSM_Toko_Clean_GoogleSheets (1).xlsx"

# --- FUNGSI DATABASE EXCEL ---
def load_data_from_excel():
    if not os.path.exists(EXCEL_FILE):
        # Buat file Excel dummy otomatis jika belum ada agar aplikasi tidak error saat pertama kali jalan
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
            pd.DataFrame([
                {"period_id": "P01", "period_name": "Periode 1 (Januari)", "start_date": "2026-01-01", "end_date": "2026-01-15"},
                {"period_id": "P02", "period_name": "Periode 2 (Februari)", "start_date": "2026-02-01", "end_date": "2026-02-15"}
            ]).to_excel(writer, sheet_name="Periods", index=False)
            
            pd.DataFrame([
                {"period_id": "P01", "item_id": "I01", "item_name": "Baby Happy", "target_qty": 500, "target_kasir": 100},
                {"period_id": "P01", "item_id": "I02", "item_name": "Goodtime", "target_qty": 300, "target_kasir": 60},
                {"period_id": "P02", "item_id": "I03", "item_name": "Aqua Galon", "target_qty": 400, "target_kasir": 80}
            ]).to_excel(writer, sheet_name="MasterItems", index=False)
            
            pd.DataFrame(columns=["period_id", "date", "person_name", "item_id", "actual_qty"]).to_excel(writer, sheet_name="PersonilSales", index=False)
            pd.DataFrame(columns=["period_id", "date", "item_id", "actual_qty"]).to_excel(writer, sheet_name="StoreSales", index=False)

    periods_df = pd.read_excel(EXCEL_FILE, sheet_name="Periods")
    items_df = pd.read_excel(EXCEL_FILE, sheet_name="MasterItems")
    
    try:
        personil_df = pd.read_excel(EXCEL_FILE, sheet_name="PersonilSales")
    except:
        personil_df = pd.DataFrame(columns=["period_id", "date", "person_name", "item_id", "actual_qty"])
        
    try:
        store_df = pd.read_excel(EXCEL_FILE, sheet_name="StoreSales")
    except:
        store_df = pd.DataFrame(columns=["period_id", "date", "item_id", "actual_qty"])
        
    return periods_df.to_dict("records"), items_df.to_dict("records"), personil_df.to_dict("records"), store_df.to_dict("records")

def save_data_to_excel():
    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="w") as writer:
        pd.DataFrame(st.session_state.periods).to_excel(writer, sheet_name="Periods", index=False)
        pd.DataFrame(st.session_state.master_items).to_excel(writer, sheet_name="MasterItems", index=False)
        pd.DataFrame(st.session_state.personil_sales).to_excel(writer, sheet_name="PersonilSales", index=False)
        pd.DataFrame(st.session_state.store_items_sales).to_excel(writer, sheet_name="StoreSales", index=False)

# Inisialisasi Data ke Session State
if "data_loaded" not in st.session_state:
    periods, master_items, personil_sales, store_items_sales = load_data_from_excel()
    st.session_state.periods = periods
    st.session_state.master_items = master_items
    st.session_state.personil_sales = personil_sales
    st.session_state.store_items_sales = store_items_sales
    st.session_state.data_loaded = True

st.session_state.master_persons = ["Tika", "Aris", "Rizki"]

# --- SIDEBAR & OTENTIKASI LOGIN ---
# Menu Navigasi Sidebar
menu_options = ["01 · Overview", "02 · Detail Item", "03 · Penjualan Personil", "04 · Pencapaian Pernik", "05 · Analisis Tren"]
if st.session_state.logged_in:
    menu_options.append("06 · Input & Reset Data")

selected_tab = st.sidebar.selectbox("Pilih Menu", menu_options)

# Filter Global Periode
all_periods_dict = {p["period_name"]: p["period_id"] for p in st.session_state.periods}
selected_period_name = st.selectbox("🌟 Pilih Periode Laporan", ["Semua Periode (Overall)"] + list(all_periods_dict.keys()))
selected_period_id = None if selected_period_name == "Semua Periode (Overall)" else all_periods_dict[selected_period_name]

st.markdown("---")

# Helper untuk kalkulasi item berdasarkan filter periode
def get_current_items():
    items = st.session_state.master_items
    if selected_period_id:
        items = [i for i in items if i["period_id"] == selected_period_id]
    return items

# --- TAB 01: OVERVIEW ---
if selected_tab == "01 · Overview":
    st.title("📊 Overview Penjualan Toko")
    
    current_items = get_current_items()
    tot_target = sum([i["target_qty"] for i in current_items])
    
    store_sales = st.session_state.store_items_sales
    if selected_period_id:
        store_sales = [s for s in store_sales if s["period_id"] == selected_period_id]
    tot_actual = sum([s["actual_qty"] for s in store_sales])
    
    ach = (tot_actual / tot_target * 100) if tot_target > 0 else 0
    gap = tot_actual - tot_target

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Target Toko", f"{tot_target:,} Pcs")
    c2.metric("Actual Sales", f"{tot_actual:,} Pcs", delta=f"{gap:,} Pcs")
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
    
    items_list = get_current_items()
    if items_list:
        df_items = pd.DataFrame(items_list)
        df_store = pd.DataFrame(st.session_state.store_items_sales)
        
        if not df_store.empty:
            agg_store = df_store.groupby("item_id")["actual_qty"].sum().reset_index()
            merged = pd.merge(df_items, agg_store, on="item_id", how="left").fillna(0)
        else:
            merged = df_items.copy()
            merged["actual_qty"] = 0
            
        merged["ach"] = merged.apply(lambda r: (r["actual_qty"] / r["target_qty"] * 100) if r["target_qty"] > 0 else 0, axis=1)
        
        # Kartu Top & Bad Performance
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
    p_sales = st.session_state.personil_sales
    if selected_period_id:
        p_sales = [x for x in p_sales if x["period_id"] == selected_period_id]
        
    if p_sales:
        df_p = pd.DataFrame(p_sales)
        summary_person = df_p.groupby("person_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        st.dataframe(summary_person, use_container_width=True)
    else:
        st.info("Belum ada data penjualan personil.")

# --- TAB 04: PENCAPAIAN PERNIK ---
elif selected_tab == "04 · Pencapaian Pernik":
    st.title("🏆 Pencapaian Pernik Per Personil")
    selected_person = st.selectbox("Pilih Staf Toko", st.session_state.master_persons)
    
    current_items = get_current_items()
    st.write(f"Rincian target kasir untuk staf: **{selected_person}**")
    if current_items:
        st.dataframe(pd.DataFrame(current_items), use_container_width=True)
    else:
        st.info("Tidak ada item.")

# --- TAB 05: ANALISIS TREN ---
elif selected_tab == "05 · Analisis Tren":
    st.title("📈 Analisis Tren Harian & Estimasi")
    st.write("Analisis ritme penjualan harian toko berdasarkan data aktual.")

# --- TAB 06: INPUT & RESET DATA (KHUSUS EDITOR) ---
elif selected_tab == "06 · Input & Reset Data":
    st.title("✏️ Form Input & Penghapusan Data Sales")
    
    tab_in1, tab_in2 = st.tabs(["Input/Hapus Sales Personil", "Update/Hapus Total Toko"])
    
    with tab_in1:
        st.subheader("Kelola Data Sales Personil")
        f_period = st.selectbox("Periode", list(all_periods_dict.keys()), key="in_p_per")
        f_date = st.date_input("Tanggal Penjualan", key="in_p_date")
        f_person = st.selectbox("Nama Staf", st.session_state.master_persons, key="in_p_pers")
        
        # Filter item hanya yang masuk periode promosi tersebut
        p_id_val = all_periods_dict[f_period]
        filtered_items = [i for i in st.session_state.master_items if i["period_id"] == p_id_val]
        item_names = {i["item_name"]: i["item_id"] for i in filtered_items}
        
        if item_names:
            f_item_name = st.selectbox("Pilih Item (Periode Promosi)", list(item_names.keys()), key="in_p_item")
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
                    save_data_to_excel()
                    st.success("Data penjualan staf berhasil disimpan ke Excel!")
            with col_btn2:
                if st.button("🗑️ Hapus Data (Berdasarkan Tanggal & Staf)", use_container_width=True):
                    st.session_state.personil_sales = [
                        x for x in st.session_state.personil_sales 
                        if not (x["period_id"] == p_id_val and x["date"] == str(f_date) and x["item_id"] == item_names[f_item_name] and x["person_name"] == f_person)
                    ]
                    save_data_to_excel()
                    st.warning("Data berhasil dihapus dari database Excel!")
        else:
            st.warning("Tidak ada item tersedia pada periode promosi ini.")

    with tab_in2:
        st.subheader("Kelola Total Penjualan Toko")
        f_period_t = st.selectbox("Periode Toko", list(all_periods_dict.keys()), key="in_t_per")
        f_date_t = st.date_input("Tanggal Toko", key="in_t_date")
        
        p_id_val_t = all_periods_dict[f_period_t]
        filtered_items_t = [i for i in st.session_state.master_items if i["period_id"] == p_id_val_t]
        item_names_t = {i["item_name"]: i["item_id"] for i in filtered_items_t}
        
        if item_names_t:
            f_item_name_t = st.selectbox("Pilih Item Toko (Periode Promosi)", list(item_names_t.keys()), key="in_t_item")
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
                    save_data_to_excel()
                    st.success("Total item toko berhasil diperbarui ke Excel!")
            with col_bt2:
                if st.button("🗑️ Hapus Data Toko (Sesuai Tanggal & Item)", use_container_width=True):
                    st.session_state.store_items_sales = [
                        x for x in st.session_state.store_items_sales
                        if not (x["period_id"] == p_id_val_t and x["date"] == str(f_date_t) and x["item_id"] == item_names_t[f_item_name_t])
                    ]
                    save_data_to_excel()
                    st.warning("Data toko berhasil dihapus dari Excel!")
        else:
            st.warning("Tidak ada item tersedia pada periode promosi ini.")
