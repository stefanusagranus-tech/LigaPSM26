import os
import shutil
import sqlite3
import zipfile
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import html
import re

st.set_page_config(
    page_title="PSM per PLU",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Laporan PSM per PLU")
st.markdown("Menampilkan PLU PSM beserta qty, sales, dan nomor bon.")

# ============================================================
# DAFTAR PLU PSM
# ============================================================
PLU_PSM = {
    435191, 429397, 434880, 401632, 401633, 434281, 221623, 4504,
    4557, 118380, 118379, 440439, 461159, 5867, 5868, 401180,
    401181, 120076, 120077, 466031, 433323, 437941, 434243,
    434244, 432389, 444497, 451870, 451873, 451874, 124226,
    400443, 424005, 434414, 465935, 454047, 454048, 407263,
    418146, 413446, 440529, 450856, 425653, 452793, 119887,
    119895, 119898, 119899, 415150, 415376, 122157, 144353,
    428675, 428676, 431566, 428817, 428818, 453458, 453459,
}

TABEL_TRANSAKSI = "tx_tsale"
TABEL_DETAIL = "tx_trans"
TABEL_RECEIPT = "log_receipt_prn"

STRUK_WIDTH = 42


# ============================================================
# BACA DATABASE
# ============================================================
def get_table_names(conn):
    q = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    return pd.read_sql(q, conn)["name"].tolist()


def load_data(db_path):
    conn = sqlite3.connect(db_path)
    tables = get_table_names(conn)
    dfs = {}
    mapping = {
        "sale": TABEL_TRANSAKSI,
        "detail": TABEL_DETAIL,
        "receipt": TABEL_RECEIPT,
    }
    for key, tbl in mapping.items():
        if tbl in tables:
            try:
                dfs[key] = pd.read_sql("SELECT * FROM `" + tbl + "`", conn)
            except Exception as e:
                st.warning("Gagal baca tabel " + tbl + ": " + str(e))
        else:
            dfs[key] = pd.DataFrame()
    conn.close()
    return dfs, tables


# ============================================================
# FORMAT STRUK
# ============================================================
def format_struk(raw_text, width=STRUK_WIDTH):
    if not raw_text:
        return ""
    text = raw_text.replace("|", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    result = []

    for line in lines:
        line = line.rstrip()
        stripped = line.strip()
        if re.fullmatch(r"[=\-]{5,}", stripped):
            if "=" in stripped:
                result.append("=" * width)
            else:
                result.append("-" * width)
            continue
        if stripped == "":
            result.append("")
            continue
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

    cleaned = []
    prev_empty = False
    for line in result:
        if line.strip() == "":
            if not prev_empty:
                cleaned.append("")
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False

    final = []
    skip_next_empty = False
    for i, line in enumerate(cleaned):
        if skip_next_empty and line.strip() == "":
            skip_next_empty = False
            continue
        skip_next_empty = False
        if re.fullmatch(r"=+", line.strip()) and i < 5:
            final.append(line)
            skip_next_empty = True
            continue
        final.append(line)

    return "\n".join(final)


# ============================================================
# RENDER HTML STRUK
# ============================================================
def render_struk_html(text, width=STRUK_WIDTH):
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
            margin: 0; padding: 0; background: transparent;
            font-family: 'Courier New', Courier, monospace;
        }}
        .struk-outer {{
            display: flex; justify-content: center; padding: 8px 0;
        }}
        .struk-container {{
            background-color: #ffffff; color: #000000;
            padding: 18px 22px; border-radius: 6px;
            border: 1px solid #dddddd;
            box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
            width: {container_width_px}px; max-width: 100%;
            overflow-x: auto;
        }}
        .struk-container pre {{
            margin: 0;
            font-family: 'Courier New', Courier, monospace;
            font-size: 13px; line-height: 1.15;
            white-space: pre;
            color: #000000; background: transparent;
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
# GENERATE PDF
# ============================================================
def generate_pdf(text):
    from fpdf import FPDF
    pdf = FPDF(unit="mm", format=(80, 297))
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.set_font("Courier", size=9)
    for line in text.split("\n"):
        safe_line = line.encode("latin-1", "replace").decode("latin-1")
        pdf.cell(0, 3.6, safe_line, ln=1)
    return bytes(pdf.output())


# ============================================================
# TOMBOL PRINT
# ============================================================
def render_print_button(receipt_text):
    escaped = html.escape(receipt_text)
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; background: transparent; }}
        .print-btn {{
            background-color: #0066cc; color: white; border: none;
            padding: 8px 16px; border-radius: 6px;
            font-size: 14px; cursor: pointer; font-family: sans-serif;
        }}
        .print-btn:hover {{ background-color: #0055aa; }}
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
# AMBIL STRUK
# ============================================================
def get_struk_text(df_receipt, bill_no):
    if df_receipt.empty or "bill_no" not in df_receipt.columns:
        return None
    cols = ["header", "body1", "body2", "body3",
            "addtl1", "addtl2", "addtl3", "footer"]
    bill_str = str(bill_no).strip()
    bill_zfill = bill_str.zfill(4)
    candidates = [bill_str, bill_zfill, bill_str.lstrip("0")]
    row = None
    for c in candidates:
        match = df_receipt[df_receipt["bill_no"].astype(str).str.strip() == c]
        if not match.empty:
            row = match.iloc[0]
            break
    if row is None:
        match = df_receipt[
            df_receipt["bill_no"].astype(str).str.strip().str.zfill(4) == bill_zfill
        ]
        if not match.empty:
            row = match.iloc[0]
    if row is None:
        return None
    parts = []
    for c in cols:
        if c in row and pd.notna(row[c]) and str(row[c]).strip():
            parts.append(str(row[c]))
    raw_text = "\n".join(parts)
    return format_struk(raw_text, width=STRUK_WIDTH), raw_text


# ============================================================
# PARSE NAMA ITEM
# ============================================================
def parse_struk_items(body1):
    if not body1 or not isinstance(body1, str):
        return []
    items = []
    text = body1.replace("|", "\n")
    lines = text.split("\n")
    skip_keywords = [
        "Bon", "Kasir", "===", "---", "Total", "Disc",
        "Tunai", "Kembalian", "PPN", "Tgl", "MEMBER",
        "STAR", "Potensi", "A-POIN", "Voucher", "EXTRA",
        "STRUK", "ALFAGIFT", "QRIS", "Card", "Jenis",
        "Nomor", "Alamat", "Penerima", "Pengirim",
    ]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(kw in line for kw in skip_keywords):
            continue
        m = re.match(
            r"^(.+?)\s+(\d+(?:\.\d+)?)\s+([\d,]+)\s+([\d,]+)\s*$", line
        )
        if m:
            nama = m.group(1).strip()
            try:
                qty = float(m.group(2))
                harga = float(m.group(3).replace(",", ""))
                total = float(m.group(4).replace(",", ""))
                if harga > 0 and len(nama) >= 3:
                    items.append({
                        "nama": nama, "qty": qty,
                        "harga": harga, "total": total,
                    })
            except ValueError:
                continue
    return items


def build_plu_name_dict(df_receipt, df_detail):
    if df_receipt.empty or df_detail.empty:
        return {}
    plu_names = {}
    bill_to_body = {}
    for _, r in df_receipt.iterrows():
        bill = str(r["bill_no"]).strip().zfill(4)
        bill_to_body[bill] = str(r.get("body1", ""))
    df_detail = df_detail.copy()
    df_detail["_bill_z"] = df_detail["bill_no"].astype(str).str.strip().str.zfill(4)
    bill_to_items = {}
    for bill, grp in df_detail.groupby("_bill_z"):
        items = []
        for _, r in grp.iterrows():
            try:
                items.append({
                    "plu": r["plu"],
                    "qty": float(r["qty"]) if pd.notna(r["qty"]) else 0,
                    "price": float(r["price"]) if pd.notna(r["price"]) else 0,
                })
            except Exception:
                continue
        bill_to_items[bill] = items
    for bill, body in bill_to_body.items():
        struk_items = parse_struk_items(body)
        tx_items = bill_to_items.get(bill, [])
        for s in struk_items:
            for t in tx_items:
                if (abs(t["qty"] - s["qty"]) < 0.01
                        and abs(t["price"] - s["harga"]) < 1):
                    plu = t["plu"]
                    if plu not in plu_names:
                        plu_names[plu] = {}
                    plu_names[plu][s["nama"]] = plu_names[plu].get(s["nama"], 0) + 1
    result = {}
    for plu, names in plu_names.items():
        best = max(names.items(), key=lambda x: x[1])[0]
        result[plu] = best
    return result
# ============================================================
# SIDEBAR UPLOAD
# ============================================================
st.sidebar.header("Sumber Data")
upload_mode = st.sidebar.radio(
    "Sumber database:",
    ["Upload ZIP", "Path Lokal"],
    key="psm_upload",
)

db_file = None
extract_path = "temp_psm_db"

if upload_mode == "Upload ZIP":
    uploaded = st.sidebar.file_uploader(
        "Upload ZIP database", type=["zip"], key="psm_zip"
    )
    if uploaded is not None:
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(uploaded, "r") as z:
            z.extractall(extract_path)
        for root, _, files in os.walk(extract_path):
            for f in files:
                if f.endswith((".db", ".sqlite", ".sqlite3")):
                    db_file = os.path.join(root, f)
                    break
            if db_file:
                break
        if db_file:
            st.sidebar.success("Database: " + os.path.basename(db_file))
        else:
            st.sidebar.error("Tidak ada file .db di dalam ZIP.")
else:
    db_file = st.sidebar.text_input(
        "Path database:", value="pos_database.db", key="psm_path"
    )


# ============================================================
# MAIN
# ============================================================
if db_file and os.path.exists(db_file):
    try:
        dfs, all_tables = load_data(db_file)
        df_sale = dfs["sale"]
        df_detail = dfs["detail"]
        df_receipt = dfs["receipt"]

        with st.sidebar.expander("Daftar Tabel"):
            st.write(all_tables)

        if df_sale.empty:
            st.error("Tabel tx_tsale kosong.")
            st.stop()

        if df_detail.empty:
            st.error("Tabel tx_trans kosong.")
            st.stop()

        # ---- Filter tanggal ----
        st.sidebar.header("Filter Tanggal")
        df_sale["date_tx"] = pd.to_datetime(df_sale["date_tx"], errors="coerce")

        tgl_range = ()
        if df_sale["date_tx"].notna().any():
            min_d = df_sale["date_tx"].min().date()
            max_d = df_sale["date_tx"].max().date()
            tgl_range = st.sidebar.date_input(
                "Rentang Tanggal",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
                key="psm_tgl",
            )

        # ---- Filter PLU PSM ----
        df_detail["plu_num"] = pd.to_numeric(df_detail["plu"], errors="coerce")
        df_psm_detail = df_detail[df_detail["plu_num"].isin(PLU_PSM)].copy()

        st.info("Ditemukan " + str(len(df_psm_detail)) + " baris item dengan PLU PSM.")

        if df_psm_detail.empty:
            st.warning("Tidak ada item dengan PLU PSM di database.")
            st.stop()

        # ---- Konversi numerik ----
        for c in ["qty", "price", "disc", "promo_disc"]:
            if c in df_psm_detail.columns:
                df_psm_detail[c] = pd.to_numeric(
                    df_psm_detail[c], errors="coerce"
                ).fillna(0)

        df_psm_detail["bill_str"] = df_psm_detail["bill_no"].astype(str).str.strip()

        # ---- Bangun kamus PLU -> nama ----
        with st.spinner("Membangun kamus nama item dari struk..."):
            plu_name_dict = build_plu_name_dict(df_receipt, df_detail)

        st.success("Berhasil mapping " + str(len(plu_name_dict)) + " PLU ke nama.")

        # ---- Agregasi per PLU ----
        agg_rows = []
        for plu, grp in df_psm_detail.groupby("plu_num"):
            plu_int = int(plu)
            qty = grp["qty"].sum()
            sales = (grp["price"] * grp["qty"]).sum()
            list_bon = sorted(
                set(grp["bill_str"].unique()),
                key=lambda x: int(x) if x.isdigit() else 0
            )
            nama = plu_name_dict.get(plu_int, plu_name_dict.get(plu, "-"))
            agg_rows.append({
                "PLU": plu_int,
                "Nama_Item": nama,
                "Qty": int(qty),
                "Sales_Item": sales,
                "List_Bon": list_bon,
                "Jumlah_Bon": len(list_bon),
            })

        df_agg = pd.DataFrame(agg_rows).sort_values(
            "Sales_Item", ascending=False
        ).reset_index(drop=True)

        # ---- Ringkasan ----
        st.markdown("### Tabel PSM per PLU")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total PLU", format(df_agg["PLU"].nunique(), ","))
        c2.metric("Total Qty", format(int(df_agg["Qty"].sum()), ","))
        c3.metric("Total Bon Unik", format(
            len(set(b for bl in df_agg["List_Bon"] for b in bl)), ","
        ))
        c4.metric("Total Sales Item", "Rp " + format(df_agg["Sales_Item"].sum(), ",.0f"))

        st.markdown("---")

        # ---- Filter & Urutkan ----
        with st.expander("Filter & Urutkan", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                sort_by = st.selectbox(
                    "Urutkan berdasarkan:",
                    ["Sales_Item", "Qty", "Jumlah_Bon", "PLU"],
                    index=0,
                )
            with col_b:
                sort_order = st.radio(
                    "Urutan:", ["Descending", "Ascending"], horizontal=True
                )
            ascending = (sort_order == "Ascending")
            df_agg = df_agg.sort_values(sort_by, ascending=ascending).reset_index(drop=True)

        # ---- Tampilkan per PLU ----
        for idx, row in df_agg.iterrows():
            plu = row["PLU"]
            nama = row["Nama_Item"]
            qty = row["Qty"]
            sales = row["Sales_Item"]
            list_bon = row["List_Bon"]
            jml_bon = row["Jumlah_Bon"]

            judul = (
                "PLU " + str(plu)
                + " - " + str(nama)
                + " - Qty: " + str(qty)
                + " - Sales: Rp " + format(sales, ",.0f")
                + " - " + str(jml_bon) + " bon"
            )

            with st.expander(judul):
                st.write("**Nama Item:** " + str(nama))
                st.write("**Total Qty:** " + str(qty))
                st.write("**Total Sales Item:** Rp " + format(sales, ",.0f"))
                st.write("**Jumlah Bon:** " + str(jml_bon))

                st.markdown("**Daftar Nomor Bon** (klik untuk lihat struk):")

                cols_per_row = 4
                for i in range(0, len(list_bon), cols_per_row):
                    chunk = list_bon[i:i + cols_per_row]
                    cols = st.columns(len(chunk))
                    for col, bon in zip(cols, chunk):
                        btn_key = "btn_" + str(plu) + "_" + str(bon)
                        if col.button(
                            "Bon " + str(bon),
                            key=btn_key,
                            use_container_width=True,
                        ):
                            st.session_state["selected_bon_psm"] = {
                                "plu": int(plu),
                                "bon": bon,
                            }

                # ---- Tampilkan struk kalau dipilih ----
                sel = st.session_state.get("selected_bon_psm")
                if (sel
                        and sel["plu"] == int(plu)
                        and sel["bon"] in list_bon):

                    st.markdown("---")
                    st.markdown("### 🧾 Struk Bon " + str(sel["bon"]))

                    struk_result = get_struk_text(df_receipt, sel["bon"])

                    if struk_result and struk_result[0]:
                        full_receipt_text, raw_text = struk_result

                        # ---- PREVIEW STRUK ----
                        receipt_html = render_struk_html(full_receipt_text)
                        components.html(receipt_html, height=650, scrolling=True)

                        st.write("")

                        # ---- TOMBOL AKSI ----
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.download_button(
                                label="📥 TXT",
                                data=full_receipt_text,
                                file_name="struk_bon_" + str(sel["bon"]) + ".txt",
                                mime="text/plain",
                                use_container_width=True,
                                key="txt_" + str(plu) + "_" + str(sel["bon"]),
                            )

                        with col2:
                            try:
                                pdf_bytes = generate_pdf(full_receipt_text)
                                st.download_button(
                                    label="📄 PDF",
                                    data=pdf_bytes,
                                    file_name="struk_bon_" + str(sel["bon"]) + ".pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key="pdf_" + str(plu) + "_" + str(sel["bon"]),
                                )
                            except ImportError:
                                st.info("Install `fpdf2` untuk PDF")
                            except Exception as e:
                                st.warning("PDF error: " + str(e))

                        with col3:
                            print_html = render_print_button(full_receipt_text)
                            with st.popover("🖨️ Cetak", use_container_width=True):
                                st.write("Klik tombol di bawah untuk print:")
                                components.html(print_html, height=80)

                        # ---- DEBUG ----
                        with st.expander("🔍 Lihat Teks Mentah (Debug)"):
                            st.code(raw_text, language=None)
                            st.write("**Setelah diformat:**")
                            st.code(full_receipt_text, language=None)

                    else:
                        st.warning(
                            "Struk bon " + str(sel["bon"]) + " tidak ditemukan di log_receipt_prn."
                        )

        st.markdown("---")

        # ---- Download CSV ----
        df_export = df_agg.copy()
        df_export["List_Bon"] = df_export["List_Bon"].apply(
            lambda x: ", ".join(str(b) for b in x)
        )
        st.download_button(
            "📥 Download Tabel PSM per PLU (CSV)",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name="psm_per_plu.csv",
            mime="text/csv",
        )

        # ---- Debug ----
        with st.expander("🔍 Debug"):
            st.write("Total PLU di daftar PSM: " + str(len(PLU_PSM)))
            st.write("PLU PSM yang ditemukan: " + str(df_psm_detail["plu_num"].nunique()))
            st.write("Total baris detail PSM: " + str(len(df_psm_detail)))
            st.write("PLU berhasil di-mapping nama: " + str(len(plu_name_dict)))

            plu_di_db = set(df_detail["plu_num"].dropna().astype(int).unique())
            plu_tidak_ada = PLU_PSM - plu_di_db
            plu_match = PLU_PSM & plu_di_db
            st.write("PLU PSM yang match: " + str(len(plu_match)))
            st.write("PLU PSM tidak ada: " + str(len(plu_tidak_ada)))

            if not df_receipt.empty and "bill_no" in df_receipt.columns:
                bill_receipt = set(
                    df_receipt["bill_no"].astype(str).str.strip().str.zfill(4)
                )
                bill_psm = set(df_psm_detail["bill_str"].str.zfill(4))
                irisan = bill_psm & bill_receipt
                st.write("Bill PSM: " + str(len(bill_psm)))
                st.write("Bill di log_receipt_prn: " + str(len(bill_receipt)))
                st.write("Irisan (bisa dicetak): " + str(len(irisan)))

    except Exception as e:
        st.error("Error: " + str(e))
        st.exception(e)

elif db_file:
    st.warning("Database " + db_file + " tidak ditemukan.")
