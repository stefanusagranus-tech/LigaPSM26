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
    "Upload file `.zip` database Anda, lalu pilih tabel dan data yang ingin"
    " ditampilkan."
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
      cursor = conn.cursor()

      # Ambil daftar seluruh tabel yang ada di dalam database SQLite ini
      cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
      tables = [row[0] for row in cursor.fetchall()]

      st.info(f"Tabel yang ditemukan di database: {', '.join(tables)}")

      if tables:
        st.markdown("---")
        st.subheader("Eksplorasi Data Berdasarkan Tabel")

        # Pilih tabel yang ingin dilihat
        selected_table = st.selectbox("Pilih Tabel:", options=tables)

        if selected_table:
          # Ambil sampel data atau seluruh data dari tabel yang dipilih
          df_table = pd.read_sql(f"SELECT * FROM {selected_table}", conn)

          st.write(
              f"Menampilkan isi tabel: **{selected_table}** (Total baris:"
              f" {len(df_table)})"
          )

          # Tampilkan kolom pencarian jika ada kolom yang mirip dengan 'bill'
          columns = df_table.columns.tolist()
          bill_cols = [
              col
              for col in columns
              if "bill" in col.lower() or "id" in col.lower()
          ]

          if bill_cols:
            filter_col = st.selectbox(
                "Filter berdasarkan kolom:", options=bill_cols
            )
            unique_vals = df_table[filter_col].dropna().unique().tolist()
            selected_val = st.selectbox(
                f"Pilih nilai dari {filter_col}:", options=unique_vals
            )

            # Filter dataframe berdasarkan pilihan
            df_filtered = df_table[df_table[filter_col] == selected_val]
            st.dataframe(df_filtered, use_container_width=True)

            # Jika ini adalah tabel log receipt/print, tampilkan struknya
            if "receipt" in selected_table.lower() or "print" in selected_table.lower():
              st.subheader("Preview Struk:")
              for idx, row in df_filtered.iterrows():
                st.code(row.to_string(), language="text")
          else:
            st.dataframe(df_table, use_container_width=True)

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
    
