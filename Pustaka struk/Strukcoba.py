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
    "Upload file `.zip` yang berisi database Anda (misal: SQLite `.db` atau file data), lalu masukkan nomor bill (`bill_no`) untuk melihat detail penjualan dan struk."
)

# 1. Widget Upload ZIP
uploaded_file = st.file_uploader(
    "Upload File ZIP Database", type=["zip"], key="zip_uploader"
)

extract_path = "temp_db_folder"

if uploaded_file is not None:
  # Bersihkan folder temp lama jika ada
  if os.path.exists(extract_path):
    shutil.rmtree(extract_path)
  os.makedirs(extract_path, exist_ok=True)

  # Ekstrak ZIP
  import zipfile

  with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
    zip_ref.extractall(extract_path)

  st.success("File ZIP berhasil di-upload dan diekstrak!")

  # Cari file database (.db / .sqlite) di dalam folder hasil ekstraksi
  db_file_path = None
  for root, dirs, files in os.walk(extract_path):
    for file in files:
      if file.endswith((".db", ".sqlite", ".sqlite3")):
        db_file_path = os.path.join(root, file)
        break

  if db_file_path:
    st.info(f"Database ditemukan: `{os.path.basename(db_file_path)}`")

    try:
      # Koneksi ke database SQLite
      conn = sqlite3.connect(db_file_path)

      # 2. Input Bill Number dari User
      st.markdown("---")
      st.subheader("Cari Berdasarkan Bill Number")
      bill_no_input = st.text_input(
          "Masukkan Nomor Bill (`bill_no`):", placeholder="Contoh: BILL-001"
      )

      if bill_no_input:
        # Query untuk mengambil data dari tx_tsale dan ts_trans
        # (Sesuaikan nama kolom jika berbeda di database Anda)
        query_sale = f"SELECT * FROM tx_tsale WHERE bill_no = '{bill_no_input}'"
        query_trans = (
            f"SELECT * FROM ts_trans WHERE bill_no = '{bill_no_input}'"
        )
        query_receipt = f"SELECT * FROM log_recipt_print WHERE bill_no = '{bill_no_input}'"

        df_sale = pd.read_sql(query_sale, conn)
        df_trans = pd.read_sql(query_trans, conn)
        df_receipt = pd.read_sql(query_receipt, conn)

        # Tampilkan Hasil Data Penjualan
        tab1, tab2, tab3 = st.tabs(
            ["📊 Data tx_tsale", "🛒 Data ts_trans", "🧾 Struk (log_recipt_print)"]
        )

        with tab1:
          st.write("### Tabel tx_tsale")
          if not df_sale.empty:
            st.dataframe(df_sale, use_container_width=True)
          else:
            st.warning(f"Tidak ada data `tx_tsale` untuk bill: {bill_no_input}")

        with tab2:
          st.write("### Tabel ts_trans (Detail Item)")
          if not df_trans.empty:
            st.dataframe(df_trans, use_container_width=True)
          else:
            st.warning(f"Tidak ada data `ts_trans` untuk bill: {bill_no_input}")

        with tab3:
          st.write("### Preview Struk (`log_recipt_print`)")
          if not df_receipt.empty:
            # Asumsi log_recipt_print menyimpan teks mentah atau format ESC/POS/Text
            for idx, row in df_receipt.iterrows():
              # Jika kolom teks struk bernama 'receipt_text' atau 'content' (ubah sesuai database Anda)
              # Di sini kita ambil kolom teks pertama yang ditemukan atau tampilkan seluruh baris
              st.code(row.to_string(), language="text")
          else:
            st.warning(
                f"Tidak ada data `log_recipt_print` untuk bill: {bill_no_input}"
            )

      conn.close()

    except Exception as e:
      st.error(f"Terjadi kesalahan saat membaca database: {e}")

  else:
    st.error(
        "File database dengan format `.db` atau `.sqlite` tidak ditemukan di"
        " dalam folder ZIP yang di-upload."
    )

# Bersihkan direktori temporary saat aplikasi ditutup/di-refresh (opsional)
if os.path.exists(extract_path) and uploaded_file is None:
  shutil.rmtree(extract_path, ignore_errors=True)
