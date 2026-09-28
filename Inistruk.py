import os
import shutil
import sqlite3
import zipfile
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Dashboard Penjualan POS", page_icon="📊", layout="wide"
)

st.title("📊 Dashboard Penjualan & Kinerja Kasir POS")
st.markdown("Dashboard ini terhubung langsung dengan database SQLite sistem POS toko Anda.")

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
    "voucher": "voucher",
    "charity": "charity",
    "cash_out": "cash_out",
    "wallet": "wallet",
    "ol_payment": "ol_payment",
    "total_item": "total_item",
    "total_value": "total_value",
    "ppn": "ppn",
    "ppn_value": "ppn_value",
}

TABEL_TRANSAKSI = "tx_tsale"
TABEL_DETAIL = "tx_trans"
TABEL_KASIR = "log_sales_cashier"
TABEL_RECEIPT = "log_receipt_prn"
TABEL_PROMO_HEAD = "log_promo_result_head"
TABEL_PROMO_PLU = "log_promo_result_plu"
TABEL_SYARAT_PLU = "log_promo_syarat_plu"

# ============================================================
# PARAMETER SYARAT PROMO (NOMINAL)
# ============================================================
SYARAT_SUGER_MIN = 20_000   # struk > Rp 20.000
SYARAT_PWP_MIN = 20_000     # struk >= Rp 20.000

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
    df_promo_head = pd.DataFrame()
    df_promo_plu = pd.DataFrame()
    df_syarat_plu = pd.DataFrame()

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

    if TABEL_PROMO_HEAD in tables:
        try:
            df_promo_head = pd.read_sql(f"SELECT * FROM `{TABEL_PROMO_HEAD}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_PROMO_HEAD}`: {e}")

    if TABEL_PROMO_PLU in tables:
        try:
            df_promo_plu = pd.read_sql(f"SELECT * FROM `{TABEL_PROMO_PLU}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_PROMO_PLU}`: {e}")

    if TABEL_SYARAT_PLU in tables:
        try:
            df_syarat_plu = pd.read_sql(f"SELECT * FROM `{TABEL_SYARAT_PLU}`", conn)
        except Exception as e:
            st.warning(f"Gagal baca `{TABEL_SYARAT_PLU}`: {e}")

    conn.close()
    return df_sale, df_detail, df_kasir, df_promo_head, df_promo_plu, df_syarat_plu, tables


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
# FUNGSI AMBIL FAKTUR BERDASARKAN JUKLAK
# ============================================================
def get_faktur_by_juklak(df_promo_head: pd.DataFrame, keyword: str) -> set:
    """
    Return set of faktur yang punya no_juklak mengandung keyword.
    Contoh keyword: 'SPRM' untuk PSM, 'GNTG' untuk SG.
    """
    if df_promo_head.empty or "no_juklak" not in df_promo_head.columns:
        return set()

    mask = df_promo_head["no_juklak"].astype(str).str.contains(keyword, case=False, na=False)
    if "faktur" in df_promo_head.columns:
        return set(df_promo_head.loc[mask, "faktur"].astype(str).unique())
    return set()


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
        (df_sale, df_detail, df_kasir, df_promo_head,
         df_promo_plu, df_syarat_plu, all_tables) = load_data(db_file)

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
        # HITUNG PSM, SG, DLL DARI log_promo_result_head
        # ============================================================
        faktur_psm_set = get_faktur_by_juklak(df_promo_head, "SPRM")
        faktur_sg_set = get_faktur_by_juklak(df_promo_head, "GNTG")
        faktur_sua_set = get_faktur_by_juklak(df_promo_head, "SUA")
        faktur_h2h_set = get_faktur_by_juklak(df_promo_head, "H2H")

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
        df_filtered["is_sua"] = df_filtered["faktur"].astype(str).isin(faktur_sua_set)
        df_filtered["is_h2h"] = df_filtered["faktur"].astype(str).isin(faktur_h2h_set)

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
        n_struk_sua = df_filtered[df_filtered["is_sua"]]["faktur"].nunique()
        n_struk_h2h = df_filtered[df_filtered["is_h2h"]]["faktur"].nunique()

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

        s6, s7 = st.columns(2)
        s6.metric("🎯 Struk SUA", f"{n_struk_sua:,}")
        s7.metric("🏠 Struk H2H", f"{n_struk_h2h:,}")

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
                "Struk_SUA": ("is_sua", "sum"),
                "Struk_H2H": ("is_h2h", "sum"),
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

            # Cash Clerk per kasir
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
        # DEBUG PROMO
        # ============================================================
        with st.expander("🔍 Debug Promo (Juklak)"):
            st.write("**Tabel `log_promo_result_head`:**")
            if not df_promo_head.empty:
                st.write(f"Total baris: {len(df_promo_head)}")
                if "no_juklak" in df_promo_head.columns:
                    juklak_list = df_promo_head["no_juklak"].astype(str).unique()
                    st.write(f"**Jumlah juklak unik:** {len(juklak_list)}")
                    st.write("**Daftar juklak unik:**")
                    st.code("\n".join(juklak_list))

                    # Ekstrak kategori juklak
                    kategori = set()
                    for j in juklak_list:
                        for k in ["SPRM", "GNTG", "SUA", "H2H", "CRM"]:
                            if k in j.upper():
                                kategori.add(k)
                    st.write(f"**Kategori terdeteksi:** {sorted(kategori)}")
            else:
                st.warning("Tabel `log_promo_result_head` kosong.")

            st.write(f"**Faktur PSM (SPRM):** {len(faktur_psm_set)}")
            st.write(f"**Faktur SG (GNTG):** {len(faktur_sg_set)}")
            st.write(f"**Faktur SUA:** {len(faktur_sua_set)}")
            st.write(f"**Faktur H2H:** {len(faktur_h2h_set)}")

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
