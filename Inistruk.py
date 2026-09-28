import os
import shutil
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Cetak Struk & Data Penjualan", page_icon="🧾", layout="wide"
)

st.title("🧾 Aplikasi Cek Struk & Penjualan dari Database")
st.write(
    "Upload file `.zip` database Anda, lalu pilih atau cari nomor bill untuk"
    " melihat detail penjualan dan struk."
)

uploaded_file = st.file_uploader(
    "Upload File ZIP Database", type=["zip"], key="zip_uploader"
)
extract_path = "temp_db_folder"

if uploaded_file is not None:
  if os.path.exists(extract_path):
    shutil.rmtree(extract_path)
  os.makedirs(extract_path, exist_ok=True)

  import zipfile

  with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
    zip_ref.extractall(extract_path)

  db_file_path = None
  for root, dirs, files in os.walk(extract_path):
    for file in files:
      if file.endswith((".db", ".sqlite", ".sqlite3")):
        db_file_path = os.path.join(root, file)
        break

  if db_file_path:
    st.success(f"Database ditemukan!")

    try:
      conn = sqlite3.connect(db_file_path)

      # Ambil daftar nama tabel yang ada di database
      cursor = conn.cursor()
      cursor.execute(
          "SELECT name FROM sqlite_master WHERE type='table';"
      )
      tables = [row[0] for row in cursor.fetchall()]

      st.markdown("---")
      st.subheader("Pilih Berdasarkan Bill Number")

      # Cek apakah tabel 'tx_trans' ada untuk mengambil daftar bill_no
      if "tx_trans" in tables:
        # Ambil daftar bill_no unik dari ts_trans agar user bisa melihatnya
        df_bills = pd.read_sql(
            "SELECT DISTINCT bill_no FROM tx_trans ORDER BY bill_no DESC", conn
        )
        list_bills = df_bills["bill_no"].tolist()

        # Widget Selectbox / Pilihan Bill No
        selected_bill = st.selectbox(
            "Pilih atau Cari Nomor Bill (`bill_no`):", options=list_bills
        )
      else:
        selected_bill = st.text_input(
            "Masukkan Nomor Bill (`bill_no`):", placeholder="Contoh: 149"
        )

      if selected_bill:
        # Konversi ke string atau integer sesuai format database
        # Query aman untuk tx_trans dan log_recipt_print
        query_trans = (
            f"SELECT * FROM ts_trans WHERE bill_no = '{selected_bill}'"
        )
        query_receipt = (
            f"SELECT * FROM log_recipt_print WHERE bill_no = '{selected_bill}'"
        )

        df_trans = pd.read_sql(query_trans, conn)
        df_receipt = pd.read_sql(query_receipt, conn)

        # Cek struktur kolom pada tx_tsale terlebih dahulu agar tidak error
        df_tsale_sample = pd.read_sql(
            "SELECT * FROM tx_tsale LIMIT 1", conn
        )
        col_names = df_tsale_sample.columns.tolist()

        # Cari kolom yang mirip dengan bill_no di tabel tx_tsale
        match_col = None
        for col in col_names:
          if "bill" in col.lower():
            match_col = col
            break

        if match_col:
          query_sale = (
              f"SELECT * FROM tx_tsale WHERE {match_col} = '{selected_bill}'"
          )
          df_sale = pd.read_sql(query_sale, conn)
        else:
          df_sale = pd.DataFrame()

        # Tampilkan Hasil Tab
        tab1, tab2, tab3 = st.tabs(
            ["🛒 Data ts_trans", "📊 Data tx_tsale", "🧾 Struk (log_recipt_print)"]
        )

        with tab1:
          st.write(
              f"### Tabel ts_trans (Detail Item untuk Bill:"
              f" {selected_bill})"
          )
          if not df_trans.empty:
            st.dataframe(df_trans, use_container_width=True)
          else:
            st.warning(f"Tidak ada data di `ts_trans` untuk bill {selected_bill}")

        with tab2:
          st.write(f"### Tabel tx_tsale")
          if match_col:
            st.info(f"Menggunakan kolom pencocokan: `{match_col}`")
          if not df_sale.empty:
            st.dataframe(df_sale, use_container_width=True)
          else:
            st.warning(f"Tidak ada data di `tx_tsale` untuk bill {selected_bill}")

        with tab3:
          st.write(f"### Preview Struk (`log_recipt_print`)")
          if not df_receipt.empty:
            for idx, row in df_receipt.iterrows():
              st.code(row.to_string(), language="text")
          else:
            st.warning(
                f"Tidak ada data `log_recipt_print` untuk bill {selected_bill}"
            )

      conn.close()

    except Exception as e:
      st.error(f"Terjadi kesalahan saat membaca database: {e}")

  else:
    st.error(
        "File database dengan format `.db` atau `.sqlite` tidak ditemukan di"
        " dalam folder ZIP."
    )

if os.path.exists(extract_path) and uploaded_file is None:
  shutil.rmtree(extract_path, ignore_errors=True)
    
