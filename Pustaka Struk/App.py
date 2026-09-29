import streamlit as st

st.set_page_config(
    page_title="Dashboard POS",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Dashboard POS")
st.markdown("Pilih menu di **sidebar kiri** untuk membuka halaman.")

st.markdown("---")

st.markdown("### 📌 Halaman Tersedia")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📦 PSM per PLU")
    st.markdown(
        "Laporan **PSM (Promo Serba Murah)** berdasarkan daftar PLU. "
        "Menampilkan qty, sales item, dan nomor bon per PLU."
    )

with col2:
    st.markdown("#### 🎁 SG per Paket")
    st.markdown(
        "Laporan **SG (Serba Gratis)** per paket. "
        "Hanya menampilkan paket yang sudah memenuhi syarat penjualan."
    )

st.markdown("---")

st.info(
    "💡 Buka sidebar kiri → pilih **1 PSM per PLU** atau **2 SG per Paket**."
)
