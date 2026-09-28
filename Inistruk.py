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
    page_title="PSM per PLU", page_icon="📦", layout="wide"
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
    for key, tbl in {
        "sale": TABEL_TRANSAKSI,
        "detail": TABEL_DETAIL,
        "promo_head": TABEL_PROMO_HEAD,
        "receipt": TABEL_RECEIPT,
        "sync": TABEL_SYNC,
    }.items():
        if tbl in tables:
            try:
                dfs[key] = pd.read_sql(f"SELECT * FROM `{tbl}`", conn)
            except Exception as e:
                st.warning(f"Gagal baca `{tbl}`: {e}")
        else:
            dfs[key] = pd.DataFrame()

    conn.close()
    return dfs, tables


# ============================================================
# PARSE TEKS STRUK → DAPAT NAMA ITEM
# ============================================================
def parse_struk_items(body1: str) -> list:
    """
    Parse body1 dari log_receipt_prn untuk dapat daftar item.
    Format: NAMA_ITEM  QTY  HARGA  TOTAL
    Contoh: "RINSO RYL GL500      1  15,200    15,200"
    Return: list of dict {nama, qty, harga, total}
    """
    if not body1 or not isinstance(body1, str):
        return []

    items = []
    # Ganti | jadi newline
    text = body1.replace("|", "\n")
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip baris header/total
        skip_keywords = ["Bon", "Kasir", "===", "---", "Total", "Disc",
                         "Tunai", "Kembalian", "PPN", "Tgl", "MEMBER",
                         "STAR", "Potensi", "A-POIN", "Voucher", "EXTRA",
                         "STRUK", "ALFAGIFT", "QRIS", "Card", "Jenis"]
        if any(kw in line for kw in skip_keywords):
            continue

        # Regex: nama (bisa ada spasi) + qty + harga + total
        # Format: NAMA...  <spasi>  QTY  HARGA  TOTAL
        m = re.match(
            r"^(.+?)\s+(\d+(?:\.\d+)?)\s+([\d,]+)\s+([\d,]+)\s*$",
            line
        )
        if m:
            nama = m.group(1).strip()
            try:
                qty = float(m.group(2))
                harga = float(m.group(3).replace(",", ""))
                total = float(m.group(4).replace(",", ""))
                # Skip kalau harga 0 atau nama terlalu pendek
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


def build_plu_name_dict(df_receipt: pd.DataFrame,
                        df_detail: pd.DataFrame,
                        df_sync: pd.DataFrame) -> dict:
    """
    Bangun kamus PLU → Nama Item dengan cara:
    1. Untuk setiap baris log_receipt_prn, parse body1 → list item
    2. Cari bill_no di tx_trans yang match (via log_trans_sync atau langsung)
    3. Cocokkan item berdasarkan (qty, harga) → dapat PLU
    Return: {plu: nama_item}
    """
    plu_names = defaultdict(lambda: defaultdict(int))

    if df_receipt.empty or df_detail.empty:
        return {}

    # Mapping faktur → bill_no via log_trans_sync
    # log_trans_sync: faktur (119-27090149), bill_no (149)
    # log_receipt_prn: bill_no (0149), body1 (berisi faktur)
    faktur_to_bill = {}
    if not df_sync.empty and "faktur" in df_sync.columns and "bill_no" in df_sync.columns:
        for _, r in df_sync.iterrows():
            faktur = str(r["faktur"]).strip()
            bill = str(r["bill_no"]).strip()
            faktur_to_bill[faktur] = bill

    # Mapping bill_no (4 digit) → faktur, dari body1 log_receipt_prn
    bill_to_faktur = {}
    for _, r in df_receipt.iterrows():
        bill = str(r["bill_no"]).zfill(4)
        body = str(r.get("body1", "")) + str(r.get("header", ""))
        # Cari faktur pattern: C383-119-27095X76
        m = re.search(r"C383-(\d+-\d+[A-Z0-9]+)", body)
        if m:
            faktur = f"119-{m.group(1).split('-', 1)[1]}" if '-' in m.group(1) else m.group(1)
            bill_to_faktur[bill] = faktur

    # Bangun mapping bill_no → list (plu, qty, price) dari tx_trans
    # tx_trans.bill_no = 149 (angka), log_receipt_prn.bill_no = 0149
    # Kita cocokkan via faktur
    faktur_to_items = {}
    if "bill_no" in df_detail.columns:
        df_detail["_bill_zfill"] = df_detail["bill_no"].astype(str).str.zfill(4)
        for bill4, grp in df_detail.groupby("_bill_zfill"):
            items = []
            for _, r in grp.iterrows():
                items.append({
                    "plu": r["plu"],
                    "qty": float(r["qty"]) if pd.notna(r["qty"]) else 0,
                    "price": float(r["price"]) if pd.notna(r["price"]) else 0,
                })
            faktur_to_items[bill4] = items

    # Sekarang proses setiap receipt
    for bill4, faktur in bill_to_faktur.items():
        # Ambil body1
        row = df_receipt[df_receipt["bill_no"].astype(str).str.zfill(4) == bill4]
        if row.empty:
            continue
        body1 = str(row.iloc[0].get("body1", ""))

        # Parse item dari struk
        struk_items = parse_struk_items(body1)

        # Ambil item dari tx_trans
        tx_items = faktur_to_items.get(bill4, [])

        # Cocokkan berdasarkan (qty, harga)
        for s in struk_items:
            for t in tx_items:
                if abs(t["qty"] - s["qty"]) < 0.01 and abs(t["price"] - s["harga"]) < 1:
                    plu_names[t["plu"]][s["nama"]] += 1

    # Pilih nama yang paling sering muncul untuk setiap PLU
    result = {}
    for plu, names in plu_names.items():
        best_name = max(names.items(), key=lambda x: x[1])[0]
        result[plu] = best_name

    return result


# ============================================================
# FORMAT & RENDER STRUK
# ============================================================
def format_struk(raw_text: str, width: int = STRUK_WIDTH) -> str:
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
            result.append("=" * width if "=" in stripped else "-" * width)
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


def render_struk_html(text: str) -> str:
    escaped = html.escape(text)
    container_width_px = int(STRUK_WIDTH * 7.8) + 40
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; background: transparent;
                font-family: 'Courier New', monospace; }}
        .struk-outer {{ display: flex; justify-content: center; padding: 8px 0; }}
        .struk-container {{
            background: #fff; color: #000;
            padding: 18px 22px; border-radius: 6px;
            border: 1px solid #ddd;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            width: {container_width_px}px; max-width: 100%;
            overflow-x: auto;
        }}
        .struk-container pre {{
            margin: 0; font-family: 'Courier New', monospace;
            font-size: 13px; line-height: 1.15; white-space: pre;
        }}
    </style>
    </head>
    <body>
        <div class="struk-outer">
            <div class="struk-container"><pre>{escaped}</pre></div>
        </div>
    </body>
    </html>
    """


def get_struk_text(df_receipt: pd.DataFrame, bill_no: str) -> str:
    if df_receipt.empty or "bill_no" not in df_receipt.columns:
        return ""
    cols = ["header", "body1", "body2", "body3", "addtl1", "addtl2", "addtl3", "footer"]
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
# UPLOAD
# ============================================================
st.sidebar.header("📁 Sumber Data")
upload_mode = st.sidebar.radio("Sumber database:", ["Upload ZIP", "Path Lokal"], key="psm_upload")

db_file = None
extract_path = "temp_psm_db"

if upload_mode == "Upload ZIP":
    uploaded = st.sidebar.file_uploader("Upload ZIP database", type=["zip"], key="psm_zip")
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
            st.sidebar.success(f"✅ {os.path.basename(db_file)}")
        else:
            st.sidebar.error("Tidak ada file .db di dalam ZIP.")
else:
    db_file = st.sidebar.text_input("Path database:", value="pos_database.db", key="psm_path")


# ============================================================
# LOAD & TAMPILKAN
# ============================================================
if db_file and os.path.exists(db_file):
    try:
        dfs, all_tables = load_data(db_file)
        df_sale = dfs["sale"]
        df_detail = dfs["detail"]
        df_promo_head = dfs["promo_head"]
        df_receipt = dfs["receipt"]
        df_sync = dfs["sync"]

        with st.sidebar.expander("🔍 Daftar Tabel"):
            st.write(all_tables)

        if df_sale.empty:
            st.error("Tabel `tx_tsale` kosong.")
            st.stop()

        # ============================================================
        # FILTER TANGGAL
        # ============================================================
        st.sidebar.header("📅 Filter")
        df_sale["date_tx"] = pd.to_datetime(df_sale["date_tx"], errors="coerce")

        if df_sale["date_tx"].notna().any():
            min_d = df_sale["date_tx"].min().date()
            max_d = df_sale["date_tx"].max().date()
            tgl_range = st.sidebar.date_input(
                "Rentang Tanggal",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
                key="psm_tgl"
            )
        else:
            tgl_range = ()

        # ============================================================
        # AMBIL FAKTUR PSM
        # ============================================================
        if df_promo_head.empty or "no_juklak" not in df_promo_head.columns:
            st.error("Tabel `log_promo_result_head` tidak ditemukan.")
            st.stop()

        mask_psm = df_promo_head["no_juklak"].astype(str).str.contains(
            KODE_PSM, case=False, na=False, regex=False
        )
        faktur_psm_set = set(df_promo_head.loc[mask_psm, "faktur"].astype(str).unique())

        st.info(f"🎯 Ditemukan **{len(faktur_psm_set)}** struk dengan promo PSM.")

        # ============================================================
        # BANGUN KAMUS PLU → NAMA
        # ============================================================
        with st.spinner("Membangun kamus PLU → nama item dari struk..."):
            plu_name_dict = build_plu_name_dict(df_receipt, df_detail, df_sync)

        st.success(f"✅ Berhasil mapping **{len(plu_name_dict)}** PLU ke nama item.")

        # ============================================================
        # MAPPING faktur PSM → bill_no
        # ============================================================
        # Dari log_trans_sync: faktur → bill_no
        faktur_to_bill = {}
        if not df_sync.empty and "faktur" in df_sync.columns and "bill_no" in df_sync.columns:
            for _, r in df_sync.iterrows():
                faktur_to_bill[str(r["faktur"]).strip()] = str(r["bill_no"]).strip()

        # ============================================================
        # FILTER DETAIL ITEM PSM
        # ============================================================
        if df_detail.empty or "bill_no" not in df_detail.columns:
            st.error("Tabel `tx_trans` tidak ditemukan atau tidak ada kolom `bill_no`.")
            st.stop()

        # Kumpulkan bill_no yang terkait faktur PSM
        billno_psm = set()
        for faktur in faktur_psm_set:
            if faktur in faktur_to_bill:
                billno_psm.add(str(faktur_to_bill[faktur]).zfill(4))

        # Filter tx_trans
        df_detail["_bill_zfill"] = df_detail["bill_no"].astype(str).str.zfill(4)
        df_detail_psm = df_detail[df_detail["_bill_zfill"].isin(billno_psm)].copy()

        # Filter tanggal (dari faktur PSM yang masuk rentang)
        df_psm_sale = df_sale[df_sale["faktur"].astype(str).isin(faktur_psm_set)].copy()
        if len(tgl_range) == 2:
            df_psm_sale = df_psm_sale[
                (df_psm_sale["date_tx"].dt.date >= tgl_range[0]) &
                (df_psm_sale["date_tx"].dt.date <= tgl_range[1])
            ]
            faktur_in_range = set(df_psm_sale["faktur"].astype(str))
            billno_in_range = {str(faktur_to_bill[f]).zfill(4)
                               for f in faktur_in_range if f in faktur_to_bill}
            df_detail_psm = df_detail_psm[df_detail_psm["_bill_zfill"].isin(billno_in_range)]

        if df_detail_psm.empty:
            st.warning("Tidak ada detail item PSM untuk rentang tanggal ini.")
            st.stop()

        # Numerik
        for c in ["plu", "qty", "price", "disc", "promo_disc"]:
            if c in df_detail_psm.columns:
                df_detail_psm[c] = pd.to_numeric(df_detail_psm[c], errors="coerce").fillna(0)

        # ============================================================
        # AGREGASI PER PLU
        # ============================================================
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

        df_agg = pd.DataFrame(agg_rows).sort_values("Sales_Item", ascending=False)

        # ============================================================
        # TAMPILKAN
        # ============================================================
        st.markdown("### 📊 Tabel PSM per PLU")

        c1, c2, c3 = st.columns(3)
        c1.metric("🧾 Total PLU", f"{df_agg['PLU'].nunique():,}")
        c2.metric("📦 Total Qty", f"{int(df_agg['Qty'].sum()):,}")
        c3.metric("💰 Total Sales Item", f"Rp {df_agg['Sales_Item'].sum():,.0f}")

        st.markdown("---")

        # Tampilkan dengan expander per PLU
        for _, row in df_agg.iterrows():
            plu = row["PLU"]
            nama = row["Nama_Item"]
            qty = row["Qty"]
            sales = row["Sales_Item"]
            list_bon = row["List_Bon"]

            with st.expander(
                f"📦 PLU **{plu}** — {nama} — Qty: **{qty}** — "
                f"Sales: **Rp {sales:,.0f}** — {len(list_bon)} bon"
            ):
                st.write(f"**Nama Item:** {nama}")
                st.write(f"**Total Qty:** {qty}")
                st.write(f"**Total Sales Item:** Rp {sales:,.0f}")
                st.write(f"**Jumlah Bon:** {len(list_bon)}")
                st.write("**Daftar Nomor Bon (klik untuk lihat struk):**")

                cols_per_row = 4
                for i in range(0, len(list_bon), cols_per_row):
                    chunk = list_bon[i:i+cols_per_row]
                    cols = st.columns(len(chunk))
                    for col, bon in zip(cols, chunk):
                        btn_key = f"btn_{plu}_{bon}"
                        if col.button(f"🧾 {bon}", key=btn_key, use_container_width=True):
                            st.session_state["selected_bon_psm"] = {
                                "plu": int(plu),
                                "bon": bon,
                            }

                # Tampilkan struk kalau dipilih
                sel = st.session_state.get("selected_bon_psm")
                if sel and sel["plu"] == int(plu) and sel["bon"] in list_bon:
                    st.markdown(f"#### 🧾 Struk Bon `{sel['bon']}`")
                    struk_text = get_struk_text(df_receipt, sel["bon"])
                    if struk_text:
                        components.html(render_struk_html(struk_text), height=600, scrolling=True)
                        st.download_button(
                            "📥 Download Struk (TXT)",
                            data=struk_text,
                            file_name=f"struk_bon_{sel['bon']}.txt",
                            mime="text/plain",
                            key=f"dl_{plu}_{sel['bon']}",
                        )
                    else:
                        st.warning(f"Struk bon `{sel['bon']}` tidak ditemukan.")

        st.markdown("---")

        # ============================================================
        # DOWNLOAD CSV
        # ============================================================
        df_export = df_agg.copy()
        df_export["List_Bon"] = df_export["List_Bon"].apply(lambda x: ", ".join(x))
        st.download_button(
            "📥 Download Tabel PSM per PLU (CSV)",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name="psm_per_plu.csv",
            mime="text/csv",
        )

        # ============================================================
        # DEBUG
        # ============================================================
        with st.expander("🔍 Debug"):
            st.write(f"**Faktur PSM:** {len(faktur_psm_set)}")
            st.write(f"
