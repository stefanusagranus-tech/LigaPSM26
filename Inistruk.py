import os
import shutil
import sqlite3
import zipfile
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import html
import re
from collections import defaultdict

st.set_page_config(
    page_title="PSM per PLU",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Laporan PSM per PLU")
st.markdown("Menampilkan PLU yang memicu promo PSM (SPRM) beserta qty, sales, dan nomor bon.")

# ============================================================
# KONFIGURASI
# ============================================================
TABEL_TRANSAKSI = "tx_tsale"
TABEL_DETAIL = "tx_trans"
TABEL_PROMO_HEAD = "log_promo_result_head"
TABEL_RECEIPT = "log_receipt_prn"
TABEL_SYNC = "log_trans_sync"

KODE_PSM = "SPRM"
STRUK_WIDTH = 42


# ============================================================
# FUNGSI BACA DATABASE
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
        "promo_head": TABEL_PROMO_HEAD,
        "receipt": TABEL_RECEIPT,
        "sync": TABEL_SYNC,
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
# PARSE TEKS STRUK -> DAPAT NAMA ITEM
# ============================================================
def parse_struk_items(body1):
    """
    Parse body1 dari log_receipt_prn untuk dapat daftar item.
    Format: NAMA_ITEM  QTY  HARGA  TOTAL
    """
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
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if any(kw in line for kw in skip_keywords):
            continue

        m = re.match(
            r"^(.+?)\s+(\d+(?:\.\d+)?)\s+([\d,]+)\s+([\d,]+)\s*$",
            line,
        )
        if m:
            nama = m.group(1).strip()
            try:
                qty = float(m.group(2))
                harga = float(m.group(3).replace(",", ""))
                total = float(m.group(4).replace(",", ""))
                if harga > 0 and len(nama) >= 3:
                    items.append({
                        "nama": nama,
                        "qty": qty,
                        "harga": harga,
                        "total": total,
                    })
            except ValueError:
                continue

    return items


def build_plu_name_dict(df_receipt, df_detail, df_sync):
    """
    Bangun kamus PLU -> Nama Item dengan cara parse struk dari log_receipt_prn,
    lalu cocokkan (qty, harga) dengan tx_trans.
    """
    plu_names = defaultdict(lambda: defaultdict(int))

    if df_receipt.empty or df_detail.empty:
        return {}

    # Mapping faktur -> bill_no via log_trans_sync
    faktur_to_bill = {}
    if (not df_sync.empty
            and "faktur" in df_sync.columns
            and "bill_no" in df_sync.columns):
        for _, r in df_sync.iterrows():
            faktur = str(r["faktur"]).strip()
            bill = str(r["bill_no"]).strip()
            faktur_to_bill[faktur] = bill

    # Mapping bill_no (4 digit) -> faktur dari body1 log_receipt_prn
    bill_to_faktur = {}
    for _, r in df_receipt.iterrows():
        bill = str(r["bill_no"]).zfill(4)
        body = str(r.get("body1", "")) + str(r.get("header", ""))
        m = re.search(r"C383-(\d+-\d+[A-Z0-9]+)", body)
        if m:
            part = m.group(1)
            if "-" in part:
                faktur = "119-" + part.split("-", 1)[1]
            else:
                faktur = part
            bill_to_faktur[bill] = faktur

    # Mapping bill_no -> list (plu, qty, price) dari tx_trans
    faktur_to_items = {}
    if "bill_no" in df_detail.columns:
        df_detail["_bill_zfill"] = df_detail["bill_no"].astype(str).str.zfill(4)
        for bill4, grp in df_detail.groupby("_bill_zfill"):
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
            faktur_to_items[bill4] = items

    # Proses tiap receipt
    for bill4, faktur in bill_to_faktur.items():
        row = df_receipt[df_receipt["bill_no"].astype(str).str.zfill(4) == bill4]
        if row.empty:
            continue
        body1 = str(row.iloc[0].get("body1", ""))
        struk_items = parse_struk_items(body1)
        tx_items = faktur_to_items.get(bill4, [])

        for s in struk_items:
            for t in tx_items:
                if (abs(t["qty"] - s["qty"]) < 0.01
                        and abs(t["price"] - s["harga"]) < 1):
                    plu_names[t["plu"]][s["nama"]] += 1

    result = {}
    for plu, names in plu_names.items():
        best_name = max(names.items(), key=lambda x: x[1])[0]
        result[plu] = best_name

    return result


# ============================================================
# FORMAT & RENDER STRUK
# ============================================================
def format_struk(raw_text, width=STRUK_WIDTH):
    if not raw_text:
        return ""
    text = str(raw_text).replace("|", "\n")
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
            result.append(line[:width])
            rest = line[width:]
            while len(rest) > width:
                result.append(rest[:width])
                rest = rest[width:]
            if rest:
                result.append(rest)
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

    return "\n".join(cleaned)


def render_struk_html(text):
    escaped = html.escape(text)
    container_width_px = int(STRUK_WIDTH * 7.8) + 40

    style = (
        "<style>"
        "body { margin:0; padding:0; background:transparent; font-family:'Courier New', monospace; }"
        ".struk-outer { display:flex; justify-content:center; padding:8px 0; }"
        ".struk-container { background:#fff; color:#000; padding:18px 22px; "
        "border-radius:6px; border:1px solid #ddd; "
        "box-shadow:0 4px 12px rgba(0,0,0,0.15); "
        "width:" + str(container_width_px) + "px; max-width:100%; overflow-x:auto; }"
        ".struk-container pre { margin:0; font-family:'Courier New', monospace; "
        "font-size:13px; line-height:1.15; white-space:pre; }"
        "</style>"
    )

    return (
        "<!DOCTYPE html><html><head>" + style + "</head><body>"
        "<div class='struk-outer'><div class='struk-container'>"
        "<pre>" + escaped + "</pre>"
        "</div></div></body></html>"
    )


def get_struk_text(df_receipt, bill_no):
    if df_receipt.empty or "bill_no" not in df_receipt.columns:
        return ""
    cols = ["header", "body1", "body2", "body3",
            "addtl1", "addtl2", "addtl3", "footer"]
    bill4 = str(bill_no).zfill(4)
    row = df_receipt[df_receipt["bill_no"].astype(str).str.zfill(4) == bill4]
    if row.empty:
        return ""
    r = row.iloc[0]
    parts = []
    for c in cols:
        if c in r and pd.notna(r[c]) and str(r[c]).strip():
            parts.append(str(r[c]))
    return format_struk("\n".join(parts))


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
        df_promo_head = dfs["promo_head"]
        df_receipt = dfs["receipt"]
        df_sync = dfs["sync"]

        with st.sidebar.expander("Daftar Tabel"):
            st.write(all_tables)

        if df_sale.empty:
            st.error("Tabel tx_tsale kosong.")
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

        # ---- Ambil faktur PSM ----
        if df_promo_head.empty or "no_juklak" not in df_promo_head.columns:
            st.error("Tabel log_promo_result_head tidak ditemukan.")
            st.stop()

        mask_psm = df_promo_head["no_juklak"].astype(str).str.contains(
            KODE_PSM, case=False, na=False, regex=False
        )
        faktur_psm_set = set(
            df_promo_head.loc[mask_psm, "faktur"].astype(str).unique()
        )

        st.info("Ditemukan " + str(len(faktur_psm_set)) + " struk dengan promo PSM.")

        # ---- Bangun kamus PLU -> nama ----
        with st.spinner("Membangun kamus PLU dari struk..."):
            plu_name_dict = build_plu_name_dict(df_receipt, df_detail, df_sync)

        st.success("Berhasil mapping " + str(len(plu_name_dict)) + " PLU ke nama item.")

        # ---- Mapping faktur -> bill_no via log_trans_sync ----
        faktur_to_bill = {}
        if (not df_sync.empty
                and "faktur" in df_sync.columns
                and "bill_no" in df_sync.columns):
            for _, r in df_sync.iterrows():
                faktur_to_bill[str(r["faktur"]).strip()] = str(r["bill_no"]).strip()

        # ---- Filter detail item PSM ----
        if df_detail.empty or "bill_no" not in df_detail.columns:
            st.error("Tabel tx_trans tidak ditemukan atau tidak ada kolom bill_no.")
            st.stop()

        billno_psm = set()
        for faktur in faktur_psm_set:
            if faktur in faktur_to_bill:
                billno_psm.add(str(faktur_to_bill[faktur]).zfill(4))

        df_detail["_bill_zfill"] = df_detail["bill_no"].astype(str).str.zfill(4)
        df_detail_psm = df_detail[df_detail["_bill_zfill"].isin(billno_psm)].copy()

        # Filter tanggal
        df_psm_sale = df_sale[
            df_sale["faktur"].astype(str).isin(faktur_psm_set)
        ].copy()
        if len(tgl_range) == 2:
            df_psm_sale = df_psm_sale[
                (df_psm_sale["date_tx"].dt.date >= tgl_range[0])
                & (df_psm_sale["date_tx"].dt.date <= tgl_range[1])
            ]
            faktur_in_range = set(df_psm_sale["faktur"].astype(str))
            billno_in_range = set()
            for f in faktur_in_range:
                if f in faktur_to_bill:
                    billno_in_range.add(str(faktur_to_bill[f]).zfill(4))
            df_detail_psm = df_detail_psm[
                df_detail_psm["_bill_zfill"].isin(billno_in_range)
            ]

        if df_detail_psm.empty:
            st.warning("Tidak ada detail item PSM untuk rentang tanggal ini.")
            st.stop()

        # Numerik
        for c in ["plu", "qty", "price", "disc", "promo_disc"]:
            if c in df_detail_psm.columns:
                df_detail_psm[c] = pd.to_numeric(
                    df_detail_psm[c], errors="coerce"
                ).fillna(0)

        # ---- Agregasi per PLU ----
        agg_rows = []
        for plu, grp in df_detail_psm.groupby("plu"):
            qty = grp["qty"].sum()
            sales = (grp["price"] * grp["qty"]).sum()
            list_bon = sorted(set(grp["_bill_zfill"].astype(str)))
            nama = plu_name_dict.get(plu, plu_name_dict.get(int(plu), "-"))
            agg_rows.append({
                "PLU": int(plu),
                "Nama_Item": nama,
                "Qty": int(qty),
                "Sales_Item": sales,
                "List_Bon": list_bon,
            })

        df_agg = pd.DataFrame(agg_rows).sort_values(
            "Sales_Item", ascending=False
        )

        # ---- Tampilkan ----
        st.markdown("### Tabel PSM per PLU")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total PLU", format(df_agg["PLU"].nunique(), ","))
        c2.metric("Total Qty", format(int(df_agg["Qty"].sum()), ","))
        c3.metric("Total Sales Item", "Rp " + format(df_agg["Sales_Item"].sum(), ",.0f"))

        st.markdown("---")

        for _, row in df_agg.iterrows():
            plu = row["PLU"]
            nama = row["Nama_Item"]
            qty = row["Qty"]
            sales = row["Sales_Item"]
            list_bon = row["List_Bon"]

            judul = (
                "PLU " + str(plu)
                + " - " + str(nama)
                + " - Qty: " + str(qty)
                + " - Sales: Rp " + format(sales, ",.0f")
                + " - " + str(len(list_bon)) + " bon"
            )

            with st.expander(judul):
                st.write("Nama Item: " + str(nama))
                st.write("Total Qty: " + str(qty))
                st.write("Total Sales Item: Rp " + format(sales, ",.0f"))
                st.write("Jumlah Bon: " + str(len(list_bon)))
                st.write("Daftar Nomor Bon (klik untuk lihat struk):")

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

                sel = st.session_state.get("selected_bon_psm")
                if (sel
                        and sel["plu"] == int(plu)
                        and sel["bon"] in list_bon):
                    st.markdown("#### Struk Bon " + str(sel["bon"]))
                    struk_text = get_struk_text(df_receipt, sel["bon"])
                    if struk_text:
                        components.html(
                            render_struk_html(struk_text),
                            height=600,
                            scrolling=True,
                        )
                        st.download_button(
                            "Download Struk (TXT)",
                            data=struk_text,
                            file_name="struk_bon_" + str(sel["bon"]) + ".txt",
                            mime="text/plain",
                            key="dl_" + str(plu) + "_" + str(sel["bon"]),
                        )
                    else:
                        st.warning(
                            "Struk bon " + str(sel["bon"]) + " tidak ditemukan."
                        )

        st.markdown("---")

        # ---- Download CSV ----
        df_export = df_agg.copy()
        df_export["List_Bon"] = df_export["List_Bon"].apply(
            lambda x: ", ".join(x)
        )
        st.download_button(
            "Download Tabel PSM per PLU (CSV)",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name="psm_per_plu.csv",
            mime="text/csv",
        )

        # ---- Debug ----
        with st.expander("Debug"):
            st.write("Faktur PSM: " + str(len(faktur_psm_set)))
            st.write("Faktur -> Bill mapping: " + str(len(faktur_to_bill)))
            st.write("Bill No PSM: " + str(len(billno_psm)))
            st.write("Detail item PSM: " + str(len(df_detail_psm)) + " baris")
            st.write("PLU berhasil di-mapping: " + str(len(plu_name_dict)))

            bill_trans = set(
                df_detail["bill_no"].astype(str).str.zfill(4).unique()
            )
            bill_receipt = set()
            if not df_receipt.empty and "bill_no" in df_receipt.columns:
                bill_receipt = set(
                    df_receipt["bill_no"].astype(str).str.zfill(4).unique()
                )
            irisan = bill_trans & bill_receipt
            st.write("Bill no di tx_trans: " + str(len(bill_trans)))
            st.write("Bill no di log_receipt_prn: " + str(len(bill_receipt)))
            st.write("Irisan (match): " + str(len(irisan)))
            st.write("Sample tx_trans:", sorted(list(bill_trans))[:10])
            st.write("Sample log_receipt_prn:", sorted(list(bill_receipt))[:10])

            st.write("Contoh mapping PLU -> Nama:")
            sample = dict(list(plu_name_dict.items())[:20])
            st.json(sample)

    except Exception as e:
        st.error("Error: " + str(e))
        st.exception(e)

elif db_file:
    st.warning("Database " + db_file + " tidak ditemukan.")
