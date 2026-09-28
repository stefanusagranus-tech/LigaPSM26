import os
import shutil
import sqlite3
import pandas as pd
import streamlit as st
import html
import re

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

# ============================================================
# FUNGSI UNTUK MERAPIKAN STRUK
# ============================================================
def format_struk(raw_text: str, width: int = 42) -> str:
    """
    Mengubah teks mentah dari database menjadi struk rapi
    dengan lebar tetap (default 42 karakter).
    """
    if not raw_text:
        return ""

    # 1. Normalisasi: ganti '|' jadi newline, hapus spasi berlebih
    text = raw_text.replace("|", "\n")

    # 2. Pecah per baris, bersihkan
    lines = [line.rstrip() for line in text.split("\n")]

    # 3. Buang baris kosong beruntun
    cleaned = []
    prev_empty = False
    for line in lines:
        if line.strip() == "":
            if not prev_empty:
                cleaned.append("")
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False

    # 4. Deteksi garis pemisah (=== atau ---)
    result = []
    for line in cleaned:
        stripped = line.strip()

        # Garis pemisah penuh
        if re.fullmatch(r"[=\-]{5,}", stripped):
            result.append("=" * width if "=" in stripped else "-" * width)
            continue

        # Header toko (baris pertama yang mengandung nama toko)
        # Biarkan apa adanya, tapi di-center kalau pendek
        result.append(line)

    return "\n".join(result)


def render_struk_html(text: str, width: int = 42) -> str:
    """Render teks struk ke HTML dengan font monospace & fixed width."""
    escaped = html.escape(text)
    return f"""
    <div style="
        background-color: #ffffff;
        color: #000000;
        padding: 20px;
        border-radius: 6px;
        border: 2px solid #dddddd;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
        overflow-x: auto;
        max-width: 100%;
    ">
        <pre style="
            margin: 0;
            font-family: 'Courier New', Courier, monospace;
            font-size: 13px;
            line-height: 1.25;
            white-space: pre;
            color: #000000;
        ">{escaped}</pre>
    </div>
    """


# ============================================================
# PROSES UPLOAD & BACA DATABASE
# ============================================================
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
                str_bill = str(selected_bill).strip()

                variations = [
                    str_bill,
                    str_bill.zfill(4),
                    str_bill.zfill(len(str_bill) + 1),
                    str(int(str_bill)) if str_bill.isdigit() else str_bill,
                ]
                variations = list(set(variations))

                query_trans = (
                    f"SELECT * FROM tx_trans WHERE bill_no = '{selected_bill}'"
                )
                df_trans = pd.read_sql(query_trans, conn)

                df_receipt = pd.DataFrame()
                for v in variations:
                    query_receipt = f"SELECT * FROM log_receipt_prn WHERE bill_no = '{v}'"
                    df_temp = pd.read_sql(query_receipt, conn)
                    if not df_temp.empty:
                        df_receipt = df_temp
                        break

                tab1, tab2 = st.tabs(["🧾 Preview Struk", "🛒 Detail tx_trans"])

                with tab1:
                    st.write(f"### Cetak Struk untuk Bill: `{selected_bill}`")
                    if not df_receipt.empty:
                        row = df_receipt.iloc[0]

                        columns_to_check = [
                            "header",
                            "body1",
                            "body2",
                            "body3",
                            "addtl1",
                            "addtl2",
                            "addtl3",
                            "footer",
                        ]
                        parts_to_print = []

                        for col in columns_to_check:
                            if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                                parts_to_print.append(str(row[col]))

                        raw_text = "\n".join(parts_to_print)
                        full_receipt_text = format_struk(raw_text, width=42)

                        receipt_html = render_struk_html(full_receipt_text)
                        st.markdown(receipt_html, unsafe_allow_html=True)

                        st.write("")
                        st.download_button(
                            label="📥 Download Struk (TXT)",
                            data=full_receipt_text,
                            file_name=f"struk_bill_{selected_bill}.txt",
                            mime="text/plain",
                        )
                    else:
                        st.warning(
                            f"Tidak ditemukan data struk di `log_receipt_prn` untuk bill"
                            f" `{selected_bill}`."
                        )

                with tab2:
                    st.write("### Tabel tx_trans (Detail Item)")
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
