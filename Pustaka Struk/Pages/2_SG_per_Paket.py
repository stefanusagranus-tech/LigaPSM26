import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from utils.common import (
    setup_upload, load_tables,
    render_struk_html, generate_pdf, render_print_button,
    get_struk_text, build_plu_name_dict,
)

st.set_page_config(
    page_title="SG per Paket",
    page_icon="🎁",
    layout="wide",
)

st.title("🎁 Laporan Serba Gratis (SG) per Paket")
st.markdown("Menampilkan paket Serba Gratis yang sudah memenuhi syarat penjualan.")

# ============================================================
# DEFINISI GRUP SG  (silakan rapihin / tambah sesuai juklak)
# ============================================================
SG_GROUPS = {
    "wow_spageti": {
        "plu": [444755, 444756, 448657, 461599],
        "nama": "WOW SPAGETI ALL VAR",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "moms_recipe": {
        "plu": [441179, 110859],
        "nama": "MOM'S RECIPE SP TARO / MANGGA",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "ovale_ellips": {
        "plu": [213741],
        "nama": "OVALE FAC LOT + ELLIPS",
        "syarat_qty": 2,
        "beli_qty": 1,
    },
    "ramen_yes": {
        "plu": [453045, 453044],
        "nama": "RAMEN YES ALL VAR",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "koolfever": {
        "plu": [428690],
        "nama": "KOOLFEVER DEWASA",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "rapika": {
        "plu": [197589, 415156, 454096],
        "nama": "RAPIKA ALL VAR",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "koko_milo": {
        "plu": [125431, 125432],
        "nama": "KOKO KRUNCH / MILO CEREAL",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "nutrive": {
        "plu": [113852, 200213, 408055, 113850],
        "nama": "NUTRIVE BENECOL ALL VAR",
        "syarat_qty": 4,
        "beli_qty": 3,
    },
    "alfa_vit_air": {
        "plu": [460878, 426512],
        "nama": "ALFA AIR / VIT AIR",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "pepsodent": {
        "plu": [459336, 460329, 453125, 453252, 453126],
        "nama": "PEPSODENT ALL VAR",
        "syarat_qty": 2,
        "beli_qty": 1,
    },
    "creamytreats": {
        "plu": [452313],
        "nama": "ALFAMART CREAMY TREATS TUNA",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "cat_choize": {
        "plu": [439558, 439557, 444036],
        "nama": "ALFA CAT CHOIZE",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "tissue_onepiece": {
        "plu": [451060],
        "nama": "ALFA FAC TISSUE ONE PIECE",
        "syarat_qty": 2,
        "beli_qty": 1,
    },
    "tissue_albi": {
        "plu": [421455, 442078],
        "nama": "ALFAMART FAC TISSUE ALBI",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "promina": {
        "plu": [414495, 437950, 437951],
        "nama": "PROMINA BABY CRUNCH",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
    "pristine": {
        "plu": [990150],
        "nama": "PRISTINE 8.6+ WTR",
        "syarat_qty": 3,
        "beli_qty": 2,
    },
}

# Bangun mapping PLU -> grup
PLU_TO_GROUP = {}
for grp_key, grp_data in SG_GROUPS.items():
    for plu in grp_data["plu"]:
        PLU_TO_GROUP[plu] = grp_key

ALL_PLU_SG = set(PLU_TO_GROUP.keys())


# ============================================================
# UPLOAD
# ============================================================
db_file = setup_upload()


# ============================================================
# MAIN
# ============================================================
if db_file and os.path.exists(db_file):
    try:
        dfs = load_tables(db_file, ["tx_tsale", "tx_trans", "log_receipt_prn"])
        df_sale = dfs["tx_tsale"]
        df_detail = dfs["tx_trans"]
        df_receipt = dfs["log_receipt_prn"]

        if df_detail.empty:
            st.error("Tabel tx_trans kosong.")
            st.stop()

        # ---- Konversi numerik ----
        df_detail["plu_num"] = pd.to_numeric(df_detail["plu"], errors="coerce")
        for c in ["qty", "price"]:
            if c in df_detail.columns:
                df_detail[c] = pd.to_numeric(
                    df_detail[c], errors="coerce"
                ).fillna(0)

        # ---- Filter item SG ----
        df_sg_all = df_detail[df_detail["plu_num"].isin(ALL_PLU_SG)].copy()

        st.info("Ditemukan " + str(len(df_sg_all)) + " baris item dengan PLU SG.")

        if df_sg_all.empty:
            st.warning("Tidak ada item dengan PLU SG di database.")
            st.stop()

        # ---- Tambah kolom grup ----
        df_sg_all["grup"] = df_sg_all["plu_num"].map(PLU_TO_GROUP)
        df_sg_all["bill_str"] = df_sg_all["bill_no"].astype(str).str.strip()

        # ---- Bangun kamus PLU -> nama ----
        with st.spinner("Membangun kamus nama item dari struk..."):
            plu_name_dict = build_plu_name_dict(df_receipt, df_detail)

        st.success("Berhasil mapping " + str(len(plu_name_dict)) + " PLU ke nama.")

        # ============================================================
        # HITUNG PAKET SG PER STRUK PER GRUP
        # ============================================================
        paket_rows = []

        for (bill, grup_key), grp in df_sg_all.groupby(["bill_str", "grup"]):
            grp_info = SG_GROUPS.get(grup_key)
            if grp_info is None:
                continue

            syarat_qty = grp_info["syarat_qty"]
            beli_qty = grp_info["beli_qty"]
            nama_grup = grp_info["nama"]

            total_qty = grp["qty"].sum()
            total_sales = (grp["price"] * grp["qty"]).sum()

            # Hitung jumlah paket
            jumlah_paket = int(total_qty // syarat_qty)
            if jumlah_paket == 0:
                continue  # belum memenuhi syarat

            # Rasio yang dibayar = beli_qty / syarat_qty
            rasio_bayar = beli_qty / syarat_qty

            sales_per_paket = total_sales / jumlah_paket
            sales_bayar_per_paket = sales_per_paket * rasio_bayar
            qty_per_paket = int(total_qty // jumlah_paket)

            # Ambil daftar PLU yang ada di grup ini
            list_plu_di_struk = sorted(grp["plu_num"].unique().astype(int).tolist())

            # Ambil nama produk (dari mapping) — gabung beberapa nama
            nama_items = []
            for plu in list_plu_di_struk:
                nm = plu_name_dict.get(plu, "-")
                if nm != "-":
                    nama_items.append(nm)
            nama_items_str = " + ".join(nama_items[:3])
            if len(nama_items) > 3:
                nama_items_str += " + ..."

            # Buat 1 baris per paket
            for p in range(1, jumlah_paket + 1):
                paket_rows.append({
                    "Faktur": bill,
                    "Grup": grup_key,
                    "Nama_Grup": nama_grup,
                    "PLU": list_plu_di_struk,
                    "Nama_Item": nama_items_str,
                    "Qty_Total_Struk": int(total_qty),
                    "Syarat_Qty": syarat_qty,
                    "Jumlah_Paket": jumlah_paket,
                    "Paket_Ke": p,
                    "Qty_Paket": qty_per_paket,
                    "Sales_Paket": sales_bayar_per_paket,
                })

        df_paket = pd.DataFrame(paket_rows)

        if df_paket.empty:
            st.warning("Tidak ada paket SG yang memenuhi syarat.")
            st.stop()

        # Tambah tanggal dari tx_tsale (via faktur -> bill_no)
        # Kita pakai kolom tanggal di log_receipt_prn kalau ada
        if not df_receipt.empty and "bill_no" in df_receipt.columns:
            df_receipt["_bill_z"] = (
                df_receipt["bill_no"].astype(str).str.strip().str.zfill(4)
            )
            # Buat mapping bill -> date
            if "date_tx" in df_receipt.columns:
                bill_to_date = {}
                for _, r in df_receipt.iterrows():
                    b = str(r["bill_no"]).strip().zfill(4)
                    bill_to_date[b] = r.get("date_tx", "")
                df_paket["Tanggal"] = df_paket["Faktur"].apply(
                    lambda x: bill_to_date.get(str(x).zfill(4), "")
                )
            else:
                df_paket["Tanggal"] = ""
        else:
            df_paket["Tanggal"] = ""

        df_paket = df_paket.sort_values(
            ["Tanggal", "Faktur", "Grup", "Paket_Ke"]
        ).reset_index(drop=True)

        # ============================================================
        # RINGKASAN
        # ============================================================
        st.markdown("### Tabel Paket Serba Gratis")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Paket SG", format(len(df_paket), ","))
        c2.metric("Total Struk SG", format(df_paket["Faktur"].nunique(), ","))
        c3.metric("Total Qty", format(int(df_paket["Qty_Paket"].sum()), ","))
        c4.metric(
            "Total Sales Item",
            "Rp " + format(df_paket["Sales_Paket"].sum(), ",.0f")
        )

        st.markdown("---")

        # ============================================================
        # FILTER & URUTKAN
        # ============================================================
        with st.expander("Filter & Urutkan", expanded=False):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                sort_by = st.selectbox(
                    "Urutkan berdasarkan:",
                    ["Tanggal", "Sales_Paket", "Qty_Paket", "Faktur"],
                    index=0,
                )
            with col_b:
                sort_order = st.radio(
                    "Urutan:", ["Descending", "Ascending"], horizontal=True
                )
            with col_c:
                filter_grup = st.multiselect(
                    "Filter Grup:",
                    options=sorted(df_paket["Grup"].unique().tolist()),
                    default=sorted(df_paket["Grup"].unique().tolist()),
                )

            ascending = (sort_order == "Ascending")
            df_paket = df_paket[df_paket["Grup"].isin(filter_grup)]
            df_paket = df_paket.sort_values(sort_by, ascending=ascending).reset_index(drop=True)

        # ============================================================
        # TAMPILKAN TABEL (1 BARIS = 1 PAKET)
        # ============================================================
        for idx, row in df_paket.iterrows():
            faktur = row["Faktur"]
            grup_key = row["Grup"]
            nama_grup = row["Nama_Grup"]
            list_plu = row["PLU"]
            nama_item = row["Nama_Item"]
            qty_paket = row["Qty_Paket"]
            sales_paket = row["Sales_Paket"]
            paket_ke = row["Paket_Ke"]
            jml_paket = row["Jumlah_Paket"]
            qty_total_struk = row["Qty_Total_Struk"]
            tanggal = row["Tanggal"]

            plu_str = ", ".join(str(p) for p in list_plu)

            judul = (
                "🧾 " + str(tanggal) + " | Bon " + str(faktur)
                + " | " + nama_grup
                + " | Paket " + str(paket_ke) + "/" + str(jml_paket)
                + " | Qty: " + str(qty_paket)
                + " | Rp " + format(sales_paket, ",.0f")
            )

            with st.expander(judul):
                st.write("**Faktur:** " + str(faktur))
                st.write("**Grup:** " + str(nama_grup))
                st.write("**PLU:** " + plu_str)
                st.write("**Nama Item:** " + str(nama_item))
                st.write(
                    "**Qty Total di Struk:** " + str(qty_total_struk)
                    + "  →  **" + str(jml_paket) + " paket** "
                    + "(paket " + str(paket_ke) + ")"
                )
                st.write("**Qty per Paket:** " + str(qty_paket))
                st.write("**Sales Item (dibayar):** Rp " + format(sales_paket, ",.0f"))

                # Tombol lihat struk
                btn_key = "sg_btn_" + str(faktur) + "_" + str(grup_key) + "_" + str(paket_ke)
                if st.button("🧾 Lihat Struk", key=btn_key):
                    st.session_state["sg_selected_faktur"] = faktur

                # Tampilkan struk kalau dipilih
                if st.session_state.get("sg_selected_faktur") == faktur:
                    st.markdown("---")
                    st.markdown("### 🧾 Struk Bon " + str(faktur))

                    # Cari bill_no dari faktur
                    bill_no = None
                    if not df_receipt.empty and "bill_no" in df_receipt.columns:
                        # Cari di log_receipt_prn yang body1-nya mengandung faktur
                        for _, r in df_receipt.iterrows():
                            body = str(r.get("body1", "")) + str(r.get("header", ""))
                            if faktur in body:
                                bill_no = str(r["bill_no"]).strip()
                                break

                    if bill_no is None:
                        # Coba pakai faktur langsung (kalau bill_no = faktur)
                        bill_no = faktur

                    struk_result = get_struk_text(df_receipt, bill_no)

                    if struk_result and struk_result[0]:
                        full_receipt_text, raw_text = struk_result

                        receipt_html = render_struk_html(full_receipt_text)
                        components.html(receipt_html, height=650, scrolling=True)

                        st.write("")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.download_button(
                                label="📥 TXT",
                                data=full_receipt_text,
                                file_name="struk_" + str(faktur) + ".txt",
                                mime="text/plain",
                                use_container_width=True,
                                key="sg_txt_" + str(faktur),
                            )

                        with col2:
                            try:
                                pdf_bytes = generate_pdf(full_receipt_text)
                                st.download_button(
                                    label="📄 PDF",
                                    data=pdf_bytes,
                                    file_name="struk_" + str(faktur) + ".pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key="sg_pdf_" + str(faktur),
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

                        with st.expander("🔍 Lihat Teks Mentah (Debug)"):
                            st.code(raw_text, language=None)
                            st.write("**Setelah diformat:**")
                            st.code(full_receipt_text, language=None)

                    else:
                        st.warning(
                            "Struk untuk faktur " + str(faktur) + " tidak ditemukan di log_receipt_prn."
                        )

        st.markdown("---")

        # ============================================================
        # DOWNLOAD CSV
        # ============================================================
        df_export = df_paket.copy()
        df_export["PLU"] = df_export["PLU"].apply(
            lambda x: ", ".join(str(p) for p in x) if isinstance(x, list) else x
        )
        st.download_button(
            "📥 Download Tabel SG per Paket (CSV)",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name="sg_per_paket.csv",
            mime="text/csv",
        )

        # ============================================================
        # DEBUG
        # ============================================================
        with st.expander("🔍 Debug"):
            st.write("Total grup SG: " + str(len(SG_GROUPS)))
            st.write("Total PLU SG: " + str(len(ALL_PLU_SG)))
            st.write("PLU SG yang ditemukan di database: " + str(df_sg_all["plu_num"].nunique()))
            st.write("Total baris item SG: " + str(len(df_sg_all)))
            st.write("Total paket SG: " + str(len(df_paket)))

            plu_di_db = set(df_detail["plu_num"].dropna().astype(int).unique())
            plu_match = ALL_PLU_SG & plu_di_db
            plu_tidak = ALL_PLU_SG - plu_di_db
            st.write("PLU SG yang match: " + str(len(plu_match)))
            st.write("PLU SG tidak ada di database: " + str(len(plu_tidak)))

            if plu_tidak:
                st.write("Contoh PLU tidak ada:", sorted(list(plu_tidak))[:20])

            st.write("**Distribusi paket per grup:**")
            if not df_paket.empty:
                dist = df_paket.groupby("Nama_Grup").agg(
                    Jumlah_Paket=("Paket_Ke", "count"),
                    Total_Sales=("Sales_Paket", "sum"),
                ).sort_values("Jumlah_Paket", ascending=False)
                st.dataframe(dist, use_container_width=True)

    except Exception as e:
        st.error("Error: " + str(e))
        st.exception(e)

elif db_file:
    st.warning("Database " + db_file + " tidak ditemukan.")
