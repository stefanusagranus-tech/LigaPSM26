import os
import shutil
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import html
import re
import io

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
# KONFIGURASI
# ============================================================
STRUK_WIDTH = 42  # karakter per baris (thermal 80mm)


# ============================================================
# FORMAT STRUK
# ============================================================
def format_struk(raw_text: str, width: int = STRUK_WIDTH) -> str:
    """Ubah teks mentah jadi fixed-width 42 karakter."""
    if not raw_text:
        return ""

    text = raw_text.replace("|", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")
    result = []

    for line in lines:
        line = line.rstrip()
        stripped = line.strip()

        # Garis pemisah
        if re.fullmatch(r"[=\-]{5,}", stripped):
            result.append("=" * width if "=" in stripped else "-" * width)
            continue

        if stripped == "":
            result.append("")
            continue

        # Kalau panjang, potong (hindari wrap)
        if len(line) > width:
            m = re.match(
                r"^(.*?)\s{2,}(\d+)\s+([\d.,]+)\s+([\d.,]+)\s*$", line
            )
            if m:
                nama, qty, harga, total = m.groups()
                kanan = f"{qty:>3} {harga:>8} {total:>9}"
                nama_max = width - len(kanan) - 1
                nama = nama[:nama_max]
                result.append(f"{nama:<{nama_max}} {kanan}")
            else:
                while len(line) > width:
                    result.append(line[:width])
                    line = line[width:]
                if line:
                    result.append(line)
        else:
            result.append(line)

    # Buang baris kosong beruntun, dan hapus baris kosong
    # tepat setelah baris pemisah "===" di awal (header)
    cleaned = []
    prev_empty = False
    for i, line in enumerate(result):
        if line.strip() == "":
            if not prev_empty:
                cleaned.append("")
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False

    # Hapus baris kosong yang berada tepat setelah "===" pertama
    # (biar header rapat dengan Bon seperti struk asli)
    final = []
    skip_next_empty = False
    for i, line in enumerate(cleaned):
        if skip_next_empty and line.strip() == "":
            skip_next_empty = False
            continue
        skip_next_empty = False
        if re.fullmatch(r"=+", line.strip()) and i < 5:
            # Ini garis pemisah header
            final.append(line)
            skip_next_empty = True
            continue
        final.append(line)

    return "\n".join(final)


# ============================================================
# RENDER HTML STRUK
# ============================================================
def render_struk_html(text: str, width: int = STRUK_WIDTH) -> str:
    """Render struk ke HTML fixed-width, mirip printer thermal."""
    escaped = html.escape(text)
    char_width_px = 7.8
    container_width_px = int(width * char_width_px) + 40

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: 'Courier New', Courier, monospace;
        }}
        .struk-outer {{
            display: flex;
            justify-content: center;
            padding: 8px 0;
        }}
        .struk-container {{
            background-color: #ffffff;
            color: #000000;
            padding: 18px 22px;
            border-radius: 6px;
            border: 1px solid #dddddd;
            box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
            width: {container_width_px}px;
            max-width: 100%;
            overflow-x: auto;
        }}
        .struk-container pre {{
            margin: 0;
            font-family: 'Courier New', Courier, monospace;
            font-size: 13px;
            line-height: 1.15;
            white-space: pre;
            color: #000000;
            background: transparent;
        }}
    </style>
    </head>
    <body>
        <div class="struk-outer">
            <div class="struk-container">
                <pre>{escaped}</pre>
            </div>
        </div>
    </body>
    </html>
    """


# ============================================================
# GENERATE PDF (pakai fpdf2)
# ============================================================
def generate_pdf(text: str) -> bytes:
    """Buat PDF dari teks struk pakai fpdf2."""
    from fpdf import FPDF

    pdf = FPDF(unit="mm", format=(80, 297))  # lebar 80mm, tinggi bebas
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=5)

    # Font monospace
    pdf.set_font("Courier", size=9)

    for line in text.split("\n"):
        # FPDF tidak bisa handle karakter non-latin, sanitasi
        safe_line = line.encode("latin-1", "replace").decode("latin-1")
        pdf.cell(0, 3.6, safe_line, ln=1)

    # Output bytes
    return bytes(pdf.output())


# ============================================================
# TOMBOL PRINT (pakai HTML/JS di components.html)
# ============================================================
def render_print_button(receipt_text: str) -> str:
    """Render tombol print yang buka dialog print browser."""
    escaped = html.escape(receipt_text)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; background: transparent; }}
        .print-btn {{
            background-color: #0066cc;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            font-family: sans-serif;
        }}
        .print-btn:hover {{ background-color: #0055aa; }}
        @media print {{
            body * {{ visibility: hidden; }}
            .print-area, .print-area * {{ visibility: visible; }}
            .print-area {{
                position: absolute;
                left: 0;
                top: 0;
                width: 80mm;
            }}
        }}
    </style>
    </head>
    <body>
        <button class="print-btn" onclick="printStruk()">🖨️ Cetak / Print</button>
        <div id="print-area" style="display:none;">
            <pre style="font-family:'Courier New',monospace;font-size:10px;line-height:1.2;white-space:pre;">{escaped}</pre>
        </div>
        <script>
            function printStruk() {{
                var w = window.open('', '', 'width=400,height=600');
                w.document.write('<html><head><title>Cetak Struk</title>');
                w.document.write('<style>body{{font-family:Courier New,monospace;font-size:11px;white-space:pre;}}@page{{size:80mm auto;margin:0;}}</style>');
                w.document.write('</head><body>');
                w.document.write(document.getElementById('print-area').innerHTML);
                w.document.write('</body></html>');
                w.document.close();
                w.focus();
                setTimeout(function(){{ w.print(); }}, 300);
            }}
        </script>
    </body>
    </html>
    """


# ============================================================
# PROSES UPLOAD
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
                        full_receipt_text = format_struk(raw_text, width=STRUK_WIDTH)

                        # ---- PREVIEW ----
                        receipt_html = render_struk_html(full_receipt_text)
                        components.html(receipt_html, height=650, scrolling=True)

                        st.write("")

                        # ---- TOMBOL AKSI ----
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            # Tombol Download TXT
                            st.download_button(
                                label="📥 TXT",
                                data=full_receipt_text,
                                file_name=f"struk_bill_{selected_bill}.txt",
                                mime="text/plain",
                                use_container_width=True,
                            )

                        with col2:
                            # Tombol Download PDF
                            try:
                                pdf_bytes = generate_pdf(full_receipt_text)
                                st.download_button(
                                    label="📄 PDF",
                                    data=pdf_bytes,
                                    file_name=f"struk_bill_{selected_bill}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )
                            except ImportError:
                                st.info("Install `fpdf2` untuk PDF")
                            except Exception as e:
                                st.warning(f"PDF error: {e}")

                        with col3:
                            # Tombol Print (buka tab baru)
                            print_html = render_print_button(full_receipt_text)
                            with st.popover("🖨️ Cetak", use_container_width=True):
                                st.write("Klik tombol di bawah untuk print:")
                                components.html(print_html, height=80)

                        # DEBUG
                        with st.expander("🔍 Lihat Teks Mentah (Debug)"):
                            st.code(raw_text, language=None)
                            st.write("**Setelah diformat:**")
                            st.code(full_receipt_text, language=None)
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
