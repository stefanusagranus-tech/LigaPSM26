import os
import shutil
import sqlite3
import zipfile
import pandas as pd
import streamlit as st

# ============================================================
# KONFIGURASI
# ============================================================
st.set_page_config(
    page_title="Dashboard Penjualan POS", page_icon="📊", layout="wide"
)

st.title("📊 Dashboard Penjualan & Kinerja Kasir POS")
st.markdown("Dashboard ini terhubung langsung dengan database SQLite POS toko Anda.")

# ============================================================
# KONFIGURASI KOLOM (SESUAI DATABASE ASLI)
# ============================================================
KOLOM = {
    # tabel tx_tsale
    "total": "total_faktur",
    "faktur": "faktur",
    "tanggal": "date_tx",
    "jam": "time_tx",
    "kasir": "user_id",
    "cash": "cash",
    "card": "card",
    "card_type": "card_type",
    "diskon": "discount",
    "promo_disc": "promo_disc",
    "member": "member",
    "store_id": "store_id",
    "voucher": "voucher",
    "change_pay": "change_pay",
    "total_item": "total_item",
    "total_value": "total_value",
    "cust_id": "cust_id",
}

TABEL_TRANSAKSI = "tx_tsale"
TABEL_DETAIL = "tx_trans"
TABEL_KASIR = "log_sales_cashier"


# ============================================================
# FUNGSI BACA DATABASE
# ============================================================
def get_table_names(conn):
    q = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    return pd.read_sql(q, conn)["name"].tolist()


def load_data(db_path):
    conn = sqlite3.connect(db_path)
    tables = get_table_names(conn)

    df_sale = pd.DataFrame()
    df_detail = pd.DataFrame()
    df_kasir = pd.DataFrame()

    # --- Transaksi utama: tx_tsale ---
    if TABEL_TRANSAKSI in tables:
        try:
            df_sale = pd.read_sql(f"SELECT * FROM `{TABEL_TRANSAKSI}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_TRANSAKSI}`: {e}")

    # --- Detail item: tx_trans ---
    if TABEL_DETAIL in tables:
        try:
            df_detail = pd.read_sql(f"SELECT * FROM `{TABEL_DETAIL}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_DETAIL}`: {e}")

    # --- Log kasir: log_sales_cashier ---
    if TABEL_KASIR in tables:
        try:
            df_kasir = pd.read_sql(f"SELECT * FROM `{TABEL_KASIR}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_KASIR}`: {e}")

    conn.close()
    return df_sale, df_detail, df_kasir, tables


# ============================================================
# UPLOAD
# ============================================================
st.sidebar.header("📁 Sumber Data")
upload_mode = st.sidebar.radio("Sumber database:", ["Upload ZIP", "Path Lokal"])

db_file = None
extract_path = "temp_dashboard_db"

if upload_mode == "Upload ZIP":
    uploaded = st.sidebar.file_uploader("Upload ZIP database", type=["zip"])
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
    db_file = st.sidebar.text_input("Path database:", value="pos_database.db")


# ============================================================
# LOAD & TAMPILKAN
# ============================================================
if db_file and os.path.exists(db_file):
    try:
        df_sale, df_detail, df_kasir, all_tables = load_data(db_file)

        with st.sidebar.expander("🔍 Daftar Tabel"):
            st.write(all_tables)

        if df_sale.empty:
            st.error("Tabel `tx_tsale` kosong atau tidak ditemukan.")
            st.stop()

        # Konversi tipe
        if KOLOM["total"] in df_sale.columns:
            df_sale[KOLOM["total"]] = pd.to_numeric(
                df_sale[KOLOM["total"]], errors="coerce"
            ).fillna(0)
        if KOLOM["cash"] in df_sale.columns:
            df_sale[KOLOM["cash"]] = pd.to_numeric(
                df_sale[KOLOM["cash"]], errors="coerce"
            ).fillna(0)
        if KOLOM["tanggal"] in df_sale.columns:
            df_sale[KOLOM["tanggal"]] = pd.to_datetime(
                df_sale[KOLOM["tanggal"]], errors="coerce"
            )

        st.caption(
            f"Tabel: **`{TABEL_TRANSAKSI}`** — {len(df_sale):,} baris, "
            f"{len(df_sale.columns)} kolom"
        )

        # ============================================================
        # FILTER TANGGAL
        # ============================================================
        st.sidebar.header("📅 Filter")
        if KOLOM["tanggal"] in df_sale.columns and df_sale[KOLOM["tanggal"]].notna().any():
            min_d = df_sale[KOLOM["tanggal"]].min().date()
            max_d = df_sale[KOLOM["tanggal"]].max().date()
            tgl_range = st.sidebar.date_input(
                "Rentang Tanggal",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
            )
            if len(tgl_range) == 2:
                mask = (
                    df_sale[KOLOM["tanggal"]].dt.date >= tgl_range[0]
                ) & (df_sale[KOLOM["tanggal"]].dt.date <= tgl_range[1])
                df_filtered = df_sale[mask]
            else:
                df_filtered = df_sale
        else:
            df_filtered = df_sale

        # ============================================================
        # KPI
        # ============================================================
        st.subheader("Ringkasan Performa")

        total_omzet = df_filtered[KOLOM["total"]].sum()
        total_struk = df_filtered[KOLOM["faktur"]].nunique()
        rata = total_omzet / total_struk if total_struk > 0 else 0
        total_cash = df_filtered[KOLOM["cash"]].sum() if KOLOM["cash"] in df_filtered.columns else 0
        total_card = df_filtered[KOLOM["card"]].sum() if "card" in df_filtered.columns else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Total Omzet", f"Rp {total_omzet:,.0f}")
        c2.metric("🧾 Jumlah Struk", f"{total_struk:,}")
        c3.metric("📊 Rata-rata / Struk", f"Rp {rata:,.0f}")
        c4.metric("💵 Total Tunai", f"Rp {total_cash:,.0f}")

        st.markdown("---")

        # ============================================================
        # GRAFIK
        # ============================================================
        cl, cr = st.columns(2)

        with cl:
            st.subheader("📈 Tren Penjualan Harian")
            if KOLOM["tanggal"] in df_filtered.columns:
                trend = (
                    df_filtered.dropna(subset=[KOLOM["tanggal"]])
                    .groupby(df_filtered[KOLOM["tanggal"]].dt.date)[KOLOM["total"]]
                    .sum()
                    .reset_index()
                )
                trend.columns = ["Tanggal", "Omzet"]
                if not trend.empty:
                    st.line_chart(trend.set_index("Tanggal"))
                else:
                    st.info("Tidak ada data tanggal valid.")
            else:
                st.info("Kolom tanggal tidak ditemukan.")

        with cr:
            st.subheader("💳 Metode Pembayaran")
            # Bandingkan cash vs card
            metode_data = pd.DataFrame({
                "Metode": ["Tunai (Cash)", "Kartu (Card)"],
                "Total": [
                    df_filtered[KOLOM["cash"]].sum() if KOLOM["cash"] in df_filtered.columns else 0,
                    df_filtered["card"].sum() if "card" in df_filtered.columns else 0,
                ],
            })
            st.bar_chart(metode_data.set_index("Metode"))

        st.markdown("---")

        # ============================================================
        # REKAP KASIR
        # ============================================================
        st.subheader("👤 Rekapitulasi Penjualan per Kasir")

        if KOLOM["kasir"] in df_filtered.columns:
            rekap_kasir = (
                df_filtered.groupby(KOLOM["kasir"])
                .agg(
                    Jumlah_Struk=(KOLOM["faktur"], "nunique"),
                    Total_Omzet=(KOLOM["total"], "sum"),
                    Total_Tunai=(KOLOM["cash"], "sum"),
                    Total_Kartu=("card", "sum"),
                )
                .reset_index()
                .sort_values("Total_Omzet", ascending=False)
            )
            st.dataframe(rekap_kasir, use_container_width=True)
        else:
            st.warning("Kolom kasir (`user_id`) tidak ditemukan.")

        st.markdown("---")

        # ============================================================
        # TRANSAKSI TERBARU
        # ============================================================
        st.subheader("🧾 Transaksi Terbaru")
        cols_show = [
            c for c in [
                KOLOM["faktur"], KOLOM["tanggal"], KOLOM["jam"],
                KOLOM["kasir"], KOLOM["total"], KOLOM["cash"],
                "card", KOLOM["diskon"], KOLOM["total_item"],
            ] if c in df_filtered.columns
        ]
        st.dataframe(
            df_filtered[cols_show].sort_values(
                KOLOM["tanggal"], ascending=False
            ).head(20),
            use_container_width=True,
        )

        # ============================================================
        # DEBUG
        # ============================================================
        with st.expander("🔍 Debug: Info Kolom & Data"):
            st.write("**Semua kolom `tx_tsale`:**")
            st.code("\n".join(df_sale.columns.tolist()))
            st.write("**3 baris contoh `tx_tsale`:**")
            st.dataframe(df_sale.head(3), use_container_width=True)
            if not df_detail.empty:
                st.write("**3 baris contoh `tx_trans`:**")
                st.dataframe(df_detail.head(3), use_container_width=True)
            if not df_kasir.empty:
                st.write("**3 baris contoh `log_sales_cashier`:**")
                st.dataframe(df_kasir.head(3), use_container_width=True)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
        st.exception(e)

elif db_file:
    st.warning(f"Database `{db_file}` tidak ditemukan. Upload ZIP dulu.")

if upload_mode == "Upload ZIP" and os.path.exists(extract_path):
    pass
