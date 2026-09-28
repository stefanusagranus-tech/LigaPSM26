import os
import shutil
import sqlite3
import zipfile
import pandas as pd
import streamlit as st

# ============================================================
# KONFIGURASI HALAMAN
# ============================================================
st.set_page_config(
    page_title="Dashboard Penjualan POS", page_icon="📊", layout="wide"
)

st.title("📊 Dashboard Penjualan & Kinerja Kasir POS")
st.markdown(
    "Dashboard ini terhubung langsung dengan database SQLite sistem POS toko Anda."
)


# ============================================================
# FUNGSI BACA DATABASE (FLEKSIBEL)
# ============================================================
def get_table_names(conn):
    """Ambil daftar semua tabel."""
    q = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    return pd.read_sql(q, conn)["name"].tolist()


def get_columns(conn, table):
    """Ambil daftar kolom dari suatu tabel."""
    try:
        q = f"PRAGMA table_info('{table}')"
        return pd.read_sql(q, conn)["name"].tolist()
    except Exception:
        return []


def find_column(columns, candidates):
    """Cari kolom pertama yang cocok dari daftar kandidat."""
    for c in candidates:
        if c in columns:
            return c
    return None


def load_data(db_path):
    """Load data dari database dengan deteksi tabel fleksibel."""
    conn = sqlite3.connect(db_path)

    tables = get_table_names(conn)

    # Cari tabel transaksi penjualan
    # Prioritas: tx_tsale, tx_trans, transaction, sales, penjualan
    sale_table_candidates = [
        "tx_tsale", "tx_trans", "tx_sale", "transaction", "transactions",
        "sales", "penjualan", "tx_penjualan"
    ]
    sale_table = None
    for t in sale_table_candidates:
        if t in tables:
            sale_table = t
            break
    # Kalau tidak ada yang cocok, cari tabel yang namanya mengandung "sale"/"trans"
    if sale_table is None:
        for t in tables:
            if "sale" in t.lower() or "trans" in t.lower():
                sale_table = t
                break

    # Cari tabel kasir
    clerk_table_candidates = [
        "log_clerk", "clerk", "kasir", "cashier", "log_kasir", "users"
    ]
    clerk_table = None
    for t in clerk_table_candidates:
        if t in tables:
            clerk_table = t
            break
    if clerk_table is None:
        for t in tables:
            if "clerk" in t.lower() or "kasir" in t.lower() or "cashier" in t.lower():
                clerk_table = t
                break

    df_sale = pd.DataFrame()
    df_clerk = pd.DataFrame()

    if sale_table:
        try:
            df_sale = pd.read_sql(f"SELECT * FROM `{sale_table}`", conn)
            df_sale.attrs["_table_name"] = sale_table
            df_sale.attrs["_columns"] = get_columns(conn, sale_table)
        except Exception as e:
            st.warning(f"Gagal baca tabel `{sale_table}`: {e}")

    if clerk_table:
        try:
            df_clerk = pd.read_sql(f"SELECT * FROM `{clerk_table}`", conn)
            df_clerk.attrs["_table_name"] = clerk_table
        except Exception as e:
            st.warning(f"Gagal baca tabel `{clerk_table}`: {e}")

    conn.close()
    return df_sale, df_clerk, tables


# ============================================================
# UPLOAD DATABASE
# ============================================================
st.sidebar.header("📁 Sumber Data")
upload_mode = st.sidebar.radio(
    "Pilih sumber database:",
    ["Upload ZIP", "Path Lokal"],
    horizontal=False,
)

db_file = None
extract_path = "temp_dashboard_db"

if upload_mode == "Upload ZIP":
    uploaded = st.sidebar.file_uploader(
        "Upload file ZIP database", type=["zip"], key="dash_zip"
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
            st.sidebar.success(f"Database: `{os.path.basename(db_file)}`")
        else:
            st.sidebar.error("Tidak ada file .db di dalam ZIP.")
else:
    db_file = st.sidebar.text_input(
        "Path database lokal:", value="pos_database.db"
    )


# ============================================================
# LOAD DATA
# ============================================================
if db_file and os.path.exists(db_file):
    try:
        df_sale, df_clerk, all_tables = load_data(db_file)

        with st.sidebar.expander("🔍 Daftar Tabel"):
            st.write(all_tables)

        if df_sale.empty and df_clerk.empty:
            st.error(
                "Database terbaca, tapi tidak ada tabel transaksi/kasir yang "
                "dikenali. Cek daftar tabel di sidebar."
            )
            st.stop()

        sale_cols = df_sale.attrs.get("_columns", [])
        sale_table = df_sale.attrs.get("_table_name", "?")

        st.caption(
            f"Tabel transaksi: **`{sale_table}`** — {len(df_sale):,} baris, "
            f"{len(sale_cols)} kolom"
        )

        # ---- AUTO-DETEKSI KOLOM ----
        col_total = find_column(
            sale_cols, ["total_amount", "grand_total", "total", "total_belanja",
                        "amount", "net_total", "subtotal"]
        )
        col_invoice = find_column(
            sale_cols, ["invoice_no", "bill_no", "receipt_no", "no_struk",
                        "trx_no", "transaction_id", "id"]
        )
        col_date = find_column(
            sale_cols, ["sale_date", "date", "tanggal", "trx_date",
                        "transaction_date", "created_at", "datetime"]
        )
        col_payment = find_column(
            sale_cols, ["payment_method", "payment_type", "metode_bayar",
                        "pay_method", "payment", "jenis_bayar"]
        )
        col_cash = find_column(
            sale_cols, ["cash_amount", "cash", "tunai", "amount_cash",
                        "cash_paid", "bayar_tunai"]
        )
        col_clerk = find_column(
            sale_cols, ["clerk_id", "kasir_id", "cashier_id", "user_id",
                        "clerk", "kasir", "operator"]
        )

        # ============================================================
        # KPI UTAMA
        # ============================================================
        st.subheader("Ringkasan Performa")
        c1, c2, c3 = st.columns(3)

        if col_total:
            total_omzet = pd.to_numeric(df_sale[col_total], errors="coerce").sum()
        else:
            total_omzet = 0
            st.warning("Kolom total penjualan tidak terdeteksi.")

        if col_invoice:
            total_struk = df_sale[col_invoice].nunique()
        else:
            total_struk = len(df_sale)

        rata = total_omzet / total_struk if total_struk > 0 else 0

        c1.metric("Total Omzet Penjualan", f"Rp {total_omzet:,.0f}")
        c2.metric("Jumlah Struk", f"{total_struk:,}")
        c3.metric("Rata-rata / Struk", f"Rp {rata:,.0f}")

        st.markdown("---")

        # ============================================================
        # GRAFIK
        # ============================================================
        cl, cr = st.columns(2)

        with cl:
            st.subheader("📈 Tren Penjualan")
            if col_date and col_total:
                try:
                    df_sale["_tanggal"] = pd.to_datetime(
                        df_sale[col_date], errors="coerce"
                    )
                    trend = (
                        df_sale.dropna(subset=["_tanggal"])
                        .groupby("_tanggal")[col_total]
                        .apply(lambda s: pd.to_numeric(s, errors="coerce").sum())
                        .reset_index()
                    )
                    if not trend.empty:
                        st.line_chart(trend.set_index("_tanggal"))
                    else:
                        st.info("Tidak ada data tanggal valid.")
                except Exception as e:
                    st.warning(f"Gagal buat tren: {e}")
            else:
                st.info(
                    "Grafik tren butuh kolom tanggal "
                    "(`sale_date`/`tanggal`/`date`)."
                )

        with cr:
            st.subheader("💳 Metode Pembayaran")
            if col_payment and col_total:
                try:
                    pay = (
                        df_sale.groupby(col_payment)[col_total]
                        .apply(lambda s: pd.to_numeric(s, errors="coerce").sum())
                        .reset_index()
                        .sort_values(col_total, ascending=False)
                    )
                    st.bar_chart(pay.set_index(col_payment))
                except Exception as e:
                    st.warning(f"Gagal buat chart: {e}")
            else:
                st.info(
                    "Kolom metode pembayaran (`payment_method`) tidak ditemukan."
                )

        st.markdown("---")

        # ============================================================
        # REKAP KASIR / CASH
        # ============================================================
        st.subheader("💵 Rekapitulasi Penjualan Tunai (Cash) per Kasir")

        if col_cash and col_clerk:
            try:
                cash_clerk = (
                    df_sale.groupby(col_clerk)[col_cash]
                    .apply(lambda s: pd.to_numeric(s, errors="coerce").sum())
                    .reset_index()
                    .sort_values(col_cash, ascending=False)
                )
                st.dataframe(cash_clerk, use_container_width=True)
            except Exception as e:
                st.warning(f"Gagal rekap kasir: {e}")
        elif not df_clerk.empty:
            st.markdown(
                f"Menampilkan data dari tabel kasir "
                f"(`{df_clerk.attrs.get('_table_name', '?')}`):"
            )
            st.dataframe(df_clerk, use_container_width=True)
        else:
            st.warning(
                "Kolom kasir / cash belum terdeteksi. "
                "Cek nama kolom di tabel transaksi."
            )

        # ============================================================
        # DEBUG
        # ============================================================
        with st.expander("🔍 Debug: Kolom & Contoh Data"):
            st.write("**Kolom tabel transaksi:**", sale_cols)
            st.write("**Kolom terdeteksi:**")
            st.json({
                "total": col_total,
                "invoice": col_invoice,
                "date": col_date,
                "payment": col_payment,
                "cash": col_cash,
                "clerk": col_clerk,
            })
            st.write("**Contoh 5 baris:**")
            st.dataframe(df_sale.head(), use_container_width=True)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
        st.exception(e)

elif db_file:
    st.warning(
        f"Database `{db_file}` tidak ditemukan. Upload ZIP atau cek path lokal."
    )

# Cleanup
if upload_mode == "Upload ZIP" and os.path.exists(extract_path):
    # Jangan langsung hapus supaya cache tetap jalan; hapus saat tidak dipakai
    pass
