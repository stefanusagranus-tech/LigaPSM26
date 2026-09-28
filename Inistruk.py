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
# KONFIGURASI KOLOM
# ============================================================
KOLOM = {
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
    "charity": "charity",
    "cash_out": "cash_out",
    "wallet": "wallet",
    "ol_payment": "ol_payment",
    "ppn": "ppn",
    "ppn_value": "ppn_value",
}

TABEL_TRANSAKSI = "tx_tsale"
TABEL_DETAIL = "tx_trans"
TABEL_KASIR = "log_sales_cashier"

# ============================================================
# PARAMETER SYARAT PROMO (NOMINAL)
# ============================================================
SYARAT_SUGER_MIN = 20_000   # struk > Rp 20.000
SYARAT_PWP_MIN = 20_000     # struk >= Rp 20.000

# ============================================================
# DAFTAR PLU UNTUK PSM (58 PLU)
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

# ============================================================
# DAFTAR PLU UNTUK SG / SERBA GRATIS (40 PLU)
# ============================================================
PLU_SG = {
    444755, 444756, 448657, 461599, 441179, 110859, 213741,
    452835, 453045, 453044, 428690, 197589, 415156, 454096,
    125431, 125432, 113852, 200213, 408055, 113850, 460878,
    426512, 459336, 460329, 453125, 453252, 453126, 452313,
    439558, 439557, 444036, 451060, 421455, 442078, 414495,
    437950, 437951, 990150,
}


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

    if TABEL_TRANSAKSI in tables:
        try:
            df_sale = pd.read_sql(f"SELECT * FROM `{TABEL_TRANSAKSI}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_TRANSAKSI}`: {e}")

    if TABEL_DETAIL in tables:
        try:
            df_detail = pd.read_sql(f"SELECT * FROM `{TABEL_DETAIL}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_DETAIL}`: {e}")

    if TABEL_KASIR in tables:
        try:
            df_kasir = pd.read_sql(f"SELECT * FROM `{TABEL_KASIR}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_KASIR}`: {e}")

    conn.close()
    return df_sale, df_detail, df_kasir, tables


# ============================================================
# FUNGSI HITUNG CASH CLERK
# ============================================================
def hitung_cash_clerk(df: pd.DataFrame) -> float:
    def safe_sum(col):
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
        return 0.0

    return float(
        safe_sum("total_faktur")
        + safe_sum("charity")
        - safe_sum("discount")
        - safe_sum("card")
        - safe_sum("cash_out")
        - safe_sum("wallet")
        - safe_sum("ol_payment")
        - safe_sum("voucher")
    )


# ============================================================
# FUNGSI AMBIL FAKTUR YANG PUNYA PLU TERTENTU
# ============================================================
def get_faktur_by_plu(df_detail: pd.DataFrame, plu_list: set) -> set:
    """
    Return set of bill_no yang punya minimal 1 item dengan PLU
    dalam daftar plu_list.
    """
    if df_detail.empty or "plu" not in df_detail.columns:
        return set()

    plu_series = pd.to_numeric(df_detail["plu"], errors="coerce")
    mask = plu_series.isin(plu_list)

    if "bill_no" in df_detail.columns:
        bill_col = "bill_no"
    elif "faktur" in df_detail.columns:
        bill_col = "faktur"
    else:
        return set()

    return set(df_detail.loc[mask, bill_col].astype(str).unique())


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

        # --- Konversi tipe numerik ---
        for col in ["total_faktur", "cash", "card", "discount", "promo_disc",
                    "charity", "cash_out", "wallet", "ol_payment", "voucher",
                    "ppn", "ppn_value", "total_item", "total_value"]:
            if col in df_sale.columns:
                df_sale[col] = pd.to_numeric(df_sale[col], errors="coerce").fillna(0)

        if "date_tx" in df_sale.columns:
            df_sale["date_tx"] = pd.to_datetime(df_sale["date_tx"], errors="coerce")

        st.caption(
            f"Tabel: **`{TABEL_TRANSAKSI}`** — {len(df_sale):,} baris, "
            f"{len(df_sale.columns)} kolom"
        )

        # ============================================================
        # FILTER TANGGAL
        # ============================================================
        st.sidebar.header("📅 Filter")
        if "date_tx" in df_sale.columns and df_sale["date_tx"].notna().any():
            min_d = df_sale["date_tx"].min().date()
            max_d = df_sale["date_tx"].max().date()
            tgl_range = st.sidebar.date_input(
                "Rentang Tanggal",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
            )
            if len(tgl_range) == 2:
                mask = (
                    df_sale["date_tx"].dt.date >= tgl_range[0]
                ) & (df_sale["date_tx"].dt.date <= tgl_range[1])
                df_filtered = df_sale[mask].copy()
            else:
                df_filtered = df_sale.copy()
        else:
            df_filtered = df_sale.copy()

        # ============================================================
        # HITUNG FAKTUR PSM & SG DARI tx_trans
        # ============================================================
        faktur_psm_set = get_faktur_by_plu(df_detail, PLU_PSM)
        faktur_sg_set = get_faktur_by_plu(df_detail, PLU_SG)

        # ============================================================
        # TAMBAH KOLOM PROMO
        # ============================================================
        total_col = df_filtered["total_faktur"]

        df_filtered["is_member"] = (
            pd.to_numeric(df_filtered["member"], errors="coerce").fillna(0) > 0
            if "member" in df_filtered.columns else False
        )
        df_filtered["is_suger"] = total_col > SYARAT_SUGER_MIN
        df_filtered["is_pwp"] = total_col >= SYARAT_PWP_MIN
        df_filtered["is_psm"] = df_filtered["faktur"].astype(str).isin(faktur_psm_set)
        df_filtered["is_sg"] = df_filtered["faktur"].astype(str).isin(faktur_sg_set)

        # ============================================================
        # KPI UTAMA
        # ============================================================
        st.subheader("Ringkasan Performa")

        total_omzet = df_filtered["total_faktur"].sum()
        total_struk = df_filtered["faktur"].nunique()
        rata = total_omzet / total_struk if total_struk > 0 else 0
        cash_clerk = hitung_cash_clerk(df_filtered)

        n_struk_member = df_filtered[df_filtered["is_member"]]["faktur"].nunique()
        n_struk_suger = df_filtered[df_filtered["is_suger"]]["faktur"].nunique()
        n_struk_pwp = df_filtered[df_filtered["is_pwp"]]["faktur"].nunique()
        n_struk_psm = df_filtered[df_filtered["is_psm"]]["faktur"].nunique()
        n_struk_sg = df_filtered[df_filtered["is_sg"]]["faktur"].nunique()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Total Omzet", f"Rp {total_omzet:,.0f}")
        c2.metric("🧾 Jumlah Struk", f"{total_struk:,}")
        c3.metric("📊 Rata-rata / Struk", f"Rp {rata:,.0f}")
        c4.metric("💵 Cash Clerk", f"Rp {cash_clerk:,.0f}")

        st.markdown("##### 🎯 Struk Berdasarkan Syarat Promo")
        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("👥 Struk Member", f"{n_struk_member:,}")
        s2.metric("🛍️ Struk Suger", f"{n_struk_suger:,}")
        s3.metric("🎁 Struk PWP", f"{n_struk_pwp:,}")
        s4.metric("📦 Struk PSM", f"{n_struk_psm:,}")
        s5.metric("🏷️ Struk SG", f"{n_struk_sg:,}")

        st.markdown("---")

        # ============================================================
        # GRAFIK
        # ============================================================
        cl, cr = st.columns(2)

        with cl:
            st.subheader("📈 Tren Penjualan Harian")
            if "date_tx" in df_filtered.columns:
                trend = (
                    df_filtered.dropna(subset=["date_tx"])
                    .groupby(df_filtered["date_tx"].dt.date)["total_faktur"]
                    .sum()
                    .reset_index()
                )
                trend.columns = ["Tanggal", "Omzet"]
                if not trend.empty:
                    st.line_chart(trend.set_index("Tanggal"))

        with cr:
            st.subheader("💳 Metode Pembayaran")
            metode_data = pd.DataFrame({
                "Metode": ["Tunai (Cash)", "Kartu (Card)", "Wallet", "OL Payment"],
                "Total": [
                    df_filtered["cash"].sum() if "cash" in df_filtered.columns else 0,
                    df_filtered["card"].sum() if "card" in df_filtered.columns else 0,
                    df_filtered["wallet"].sum() if "wallet" in df_filtered.columns else 0,
                    df_filtered["ol_payment"].sum() if "ol_payment" in df_filtered.columns else 0,
                ],
            })
            st.bar_chart(metode_data.set_index("Metode"))

        st.markdown("---")

        # ============================================================
        # REKAP KASIR
        # ============================================================
        st.subheader("👤 Rekapitulasi Penjualan per Kasir")

        if "user_id" in df_filtered.columns:
            agg_dict = {
                "Jumlah_Struk": ("faktur", "nunique"),
                "Total_Omzet": ("total_faktur", "sum"),
                "Struk_Member": ("is_member", "sum"),
                "Struk_Suger": ("is_suger", "sum"),
                "Struk_PWP": ("is_pwp", "sum"),
                "Struk_PSM": ("is_psm", "sum"),
                "Struk_SG": ("is_sg", "sum"),
            }
            for c in ["cash", "card", "voucher", "wallet", "ol_payment",
                      "cash_out", "charity", "discount"]:
                if c in df_filtered.columns:
                    agg_dict[c.capitalize()] = (c, "sum")

            rekap_kasir = (
                df_filtered.groupby("user_id")
                .agg(**agg_dict)
                .reset_index()
                .rename(columns={"user_id": "Kasir"})
                .sort_values("Total_Omzet", ascending=False)
            )

            cash_per_kasir = []
            for kasir in rekap_kasir["Kasir"]:
                df_k = df_filtered[df_filtered["user_id"] == kasir]
                cash_per_kasir.append(hitung_cash_clerk(df_k))
            rekap_kasir["Cash_Clerk"] = cash_per_kasir

            st.dataframe(rekap_kasir, use_container_width=True)

            csv = rekap_kasir.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Rekap Kasir (CSV)",
                data=csv,
                file_name="rekap_kasir.csv",
                mime="text/csv",
            )
        else:
            st.warning("Kolom kasir (`user_id`) tidak ditemukan.")

        st.markdown("---")

        # ============================================================
        # DEBUG PLU
        # ============================================================
        with st.expander("🔍 Debug PLU (PSM & SG)"):
            st.write(f"**Total PLU PSM:** {len(PLU_PSM)}")
            st.write(f"**Total PLU SG:** {len(PLU_SG)}")
            st.write(f"**Faktur dengan PLU PSM:** {len(faktur_psm_set)}")
            st.write(f"**Faktur dengan PLU SG:** {len(faktur_sg_set)}")

            if not df_detail.empty and "plu" in df_detail.columns:
                plu_di_db = set(
                    pd.to_numeric(df_detail["plu"], errors="coerce").dropna().astype(int)
                )
                st.write(f"**PLU di database:** {len(plu_di_db)}")

                psm_match = plu_di_db & PLU_PSM
                sg_match = plu_di_db & PLU_SG
                st.write(f"**PLU PSM yang cocok di DB:** {len(psm_match)}")
                st.write(f"**PLU SG yang cocok di DB:** {len(sg_match)}")

                psm_tidak = PLU_PSM - plu_di_db
                sg_tidak = PLU_SG - plu_di_db
                if psm_tidak:
                    st.write(f"**PLU PSM tidak ada di DB ({len(psm_tidak)}):**", list(psm_tidak)[:10])
                if sg_tidak:
                    st.write(f"**PLU SG tidak ada di DB ({len(sg_tidak)}):**", list(sg_tidak)[:10])

        # ============================================================
        # DEBUG UMUM
        # ============================================================
        with st.expander("🔍 Debug: Info Kolom & Data"):
            st.write("**Semua kolom `tx_tsale`:**")
            st.code("\n".join(df_sale.columns.tolist()))
            st.write("**3 baris contoh `tx_tsale`:**")
            st.dataframe(df_sale.head(3), use_container_width=True)
            if not df_detail.empty:
                st.write("**Kolom `tx_trans`:**")
                st.code("\n".join(df_detail.columns.tolist()))
                st.write("**3 baris contoh `tx_trans`:**")
                st.dataframe(df_detail.head(3), use_container_width=True)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
        st.exception(e)

elif db_file:
    st.warning(f"Database `{db_file}` tidak ditemukan. Upload ZIP dulu.")

if upload_mode == "Upload ZIP" and os.path.exists(extract_path):
    pass
