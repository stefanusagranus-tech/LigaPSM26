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
    "Upload file `.zip` database Anda, lalu pilih nomor bill untuk melihat"
    " detail transaksi dan cetak struk."
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
    st.success("Database berhasil dibaca!")

    try:
      conn = sqlite3.connect(db_file_path)

      # 1. Ambil daftar bill_no dari tabel tx_trans secara dinamis
      df_bills = pd.read_sql(
          "SELECT DISTINCT bill_no FROM tx_trans ORDER BY bill_no DESC", conn
      )
      list_bills = df_bills["bill_no"].tolist()

      st.markdown("---")
      st.subheader("Pilih Berdasarkan Bill Number")

      if list_bills:
        selected_bill = st.selectbox(
            "Pilih Nomor Bill (`bill_no`):", options=list_bills
        )
      else:
        selected_bill = st.text_input("Masukkan Nomor Bill (`bill_no`):")

      if selected_bill:
        # Query data dari tx_trans
        query_trans = (
            f"SELECT * FROM tx_trans WHERE bill_no = '{selected_bill}'"
        )
        df_trans = pd.read_sql(query_trans, conn)

        # Query data dari log_receipt_prn (sesuai nama tabel di database Anda)
        query_receipt = (
            f"SELECT * FROM log_receipt_prn WHERE bill_no = '{selected_bill}'"
        )
        df_receipt = pd.read_sql(query_receipt, conn)

        # Tampilkan Tab Menu
        tab1, tab2 = st.tabs(["🧾 Preview Struk", "🛒 Detail tx_trans"])

        with tab1:
          st.write(f"### Cetak Struk untuk Bill: {selected_bill}")
          if not df_receipt.empty:
            # Ambil baris pertama dari hasil query receipt
            row = df_receipt.iloc[0]

            # Kumpulkan bagian-bagian teks struk dari kolom database Anda
            # (header, body1, body2, body3, addtl1, addtl3, footer, dll)
            parts_to_print = [
                row.get("header", ""),
                row.get("body1", ""),
                row.get("body2", ""),
                row.get("body3", ""),
                row.get("addtl1", ""),
                row.get("addtl3", ""),
                row.get("footer", ""),
            ]

            # Gabungkan teks yang tidak kosong
            full_receipt_text = "\n".join(
                [str(p) for p in parts_to_print if pd.notna(p) and str(p) != ""]
            )

            # Tampilkan dalam wadah berlatar belakang mirip kertas struk
            st.code(full_receipt_text, language="text")

            # Tombol Simulasi Cetak / Unduh (Opsional)
            st.download_button(
                label="📥 Download Struk (TXT)",
                data=full_receipt_text,
                file_name=f"struk_bill_{selected_bill}.txt",
                mime="text/plain",
            )
          else:
            st.warning(
                f"Tidak ditemukan data struk di `log_receipt_prn` untuk bill"
                f" {selected_bill}"
            )

        with tab2:
          st.write(f"### Tabel tx_trans (Detail Item)")
          if not df_trans.empty:
            st.dataframe(df_trans, use_container_width=True)
          else:
            st.warning(f"Tidak ada data di `tx_trans` untuk bill {selected_bill}")

      conn.close()

    except Exception as e:
      st.error(f"Terjadi kesalahan saat membaca database: {e}")

  else:
    st.error("File database (.db/.sqlite) tidak ditemukan di dalam ZIP.")

if os.path.exists(extract_path) and uploaded_file is None:
  shutil.rmtree(extract_path, ignore_errors=True)
