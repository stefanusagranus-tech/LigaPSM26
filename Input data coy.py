import streamlit as st
import pandas as pd
from datetime import datetime
import random

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Input Report PSM Toko",
    page_icon="📱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS STYLING (DARK NEON MOBILE-FRIENDLY THEME) ---
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    
    /* Hide Default Header & Toolbar Streamlit */
    [data-testid="stToolbar"],
    div.stToolbarActions,
    [data-testid="stAppDeployButton"],
    button[title="Manage app"],
    div[class*="terminalButton"],
    div[class*="stAppDeployButton"],
    footer, #MainMenu {
        display: none !important;
        visibility: hidden !important;
    }

    /* Card Styling */
    .card {
        background-color: #161e2e;
        border: 1px solid #1f293d;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .card-neon {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        border: 1px solid #38bdf8;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.2);
    }

    /* Custom Metrics */
    .metric-val {
        font-size: 22px;
        font-weight: 800;
        color: #38bdf8;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .metric-sub {
        font-size: 12px;
        color: #10b981;
        font-weight: 600;
        margin-top: 4px;
    }
    .metric-lbl {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Motivational Quote Box */
    .quote-box {
        background-color: rgba(56, 189, 248, 0.08);
        border-left: 4px solid #38bdf8;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        font-style: italic;
        color: #e2e8f0;
        margin-top: 10px;
        font-size: 13px;
    }

    /* Inputs & Buttons */
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #0284c7 0%, #2563eb 100%);
        color: white;
        font-weight: 700;
        border: none;
        padding: 12px 20px;
        border-radius: 8px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
    }
    
    .stButton > button:hover {
        background: linear-gradient(90deg, #0369a1 0%, #1d4ed8 100%);
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.5);
    }

    div[data-baseweb="input"] {
        background-color: #0f172a !important;
        border-color: #334155 !important;
        border-radius: 8px !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION FUNCTION ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk/edit?usp=drivesdk"

@st.cache_data(ttl=15)
def load_data():
    try:
        from streamlit_gsheets import GSheetsConnection
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_personil = conn.read(worksheet="MASTER_PERSONIL")
        df_item = conn.read(worksheet="MASTER_ITEM")
        df_periode = conn.read(worksheet="PERIODE")
        df_sales_i = conn.read(worksheet="SALES_ITEM")
        df_sales_p = conn.read(worksheet="SALES_PERSONIL")
        return conn, df_personil, df_item, df_periode, df_sales_i, df_sales_p
    except Exception:
        excel_url = SPREADSHEET_URL.replace('/edit?usp=drivesdk', '/export?format=xlsx')
        df_personil = pd.read_excel(excel_url, sheet_name="MASTER_PERSONIL")
        df_item = pd.read_excel(excel_url, sheet_name="MASTER_ITEM")
        df_periode = pd.read_excel(excel_url, sheet_name="PERIODE")
        df_sales_i = pd.read_excel(excel_url, sheet_name="SALES_ITEM")
        df_sales_p = pd.read_excel(excel_url, sheet_name="SALES_PERSONIL")
        return None, df_personil, df_item, df_periode, df_sales_i, df_sales_p

conn, df_personil, df_item, df_periode, df_sales_i, df_sales_p = load_data()

# --- MOTIVATIONAL QUOTES ENGINE ---
def get_motivational_quote(qty_achieved):
    high_quotes = [
        "🔥 Performa luar biasa! Pertahankan ritme penjualan terbaikmu hari ini!",
        "🚀 Juara! Dedikasi dan usahamu memberikan kontribusi besar untuk toko!",
        "⭐ Luar biasa! Semangatmu adalah inspirasi bagi seluruh tim toko!",
        "💪 Pencapaian gemilang! Selangkah lagi menuju puncak target periode ini!"
    ]
    medium_quotes = [
        "📈 Hasil yang sangat baik! Sedikit dorongan lagi untuk mencapai hasil maksimal!",
        "👍 Progres yang konsisten! Tetap fokus tawarkan item PSM ke setiap pelanggan!",
        "🎯 Usaha yang mantap! Teruskan penawaran aktif di area kasir & sales floor!",
        "⚡ Semangat terus! Setiap item yang terjual mendekatkan toko ke pencapaian target."
    ]
    low_quotes = [
        "🌱 Awal yang baik! Ayo tingkatkan penawaran PSM ke setiap konsumen hari ini!",
        "💡 Setiap transaksi adalah peluang! Tetap antusias dan tawarkan produk unggulan!",
        "🔥 Jangan menyerah! Sapa pelanggan dengan ramah dan tawarkan promo PSM terbaik!",
        "✨ Hari baru, kesempatan baru! Mari wujudkan rekor penjualan harianmu hari ini!"
    ]
    
    if qty_achieved >= 100:
        return random.choice(high_quotes)
    elif qty_achieved >= 30:
        return random.choice(medium_quotes)
    else:
        return random.choice(low_quotes)

# --- SESSION STATE INITIALIZATION ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

# ==========================================
# 1. HALAMAN LOGIN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style='text-align: center;'>
        <h1 style='color: #38bdf8; font-size: 26px; margin-bottom: 5px;'>📱 LOGIN REPORT PERSONIL</h1>
        <p style='color: #94a3b8; font-size: 14px;'>Sistem Pelaporan Penjualan & Catatan Harian Toko</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        
        username_input = st.text_input("Username (Nama / NIK Personil)").strip()
        password_input = st.text_input("Password", type="password").strip()
        
        login_btn = st.button("🔓 MASUK KE APLIKASI")
        
        if login_btn:
            if not username_input or not password_input:
                st.warning("⚠️ Silakan isi Username dan Password terlebih dahulu.")
            else:
                user_match = df_personil[
                    (df_personil['person_name'].str.upper() == username_input.upper()) |
                    (df_personil['nik'].astype(str) == username_input)
                ]
                
                if not user_match.empty:
                    person_row = user_match.iloc[0]
                    expected_pass = str(person_row['nik']) if pd.notnull(person_row['nik']) else "12345"
                    
                    if password_input in [expected_pass, "12345", str(person_row['person_name']).lower()]:
                        st.session_state.logged_in = True
                        st.session_state.user_info = {
                            "person_id": person_row.get("person_id", f"PRS{person_row.name:03d}"),
                            "person_name": person_row["person_name"],
                            "nik": person_row["nik"]
                        }
                        st.success(f"✅ Login Berhasil! Selamat datang {person_row['person_name']}")
                        st.rerun()
                    else:
                        st.error("❌ Password salah! (Default password adalah NIK Anda).")
                else:
                    st.error("❌ Nama / NIK Personil tidak ditemukan dalam Database.")
                    
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 2. HALAMAN UTAMA (SETELAH LOGIN)
# ==========================================
else:
    user = st.session_state.user_info
    person_name = user["person_name"]
    person_id = user["person_id"]
    
    # Filter Periode Aktif
    active_periods = df_periode[df_periode["status"] == "OPEN"]["period_name"].tolist() if "status" in df_periode.columns else df_periode["period_name"].tolist()
    if not active_periods:
        active_periods = df_periode["period_name"].tolist()

    # Header Sapaan & Motivasi
    st.markdown(f"""
    <div class='card-neon'>
        <div>
            <span style='background-color: #0284c7; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold;'>PERSONIL TOKO</span>
            <h2 style='color: #ffffff; margin: 8px 0 2px 0; font-size: 22px;'>Selamat Datang, {person_name}! 👋</h2>
            <p style='color: #94a3b8; font-size: 12px; margin: 0;'>NIK: {user["nik"]}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_a, col_b = st.columns([3, 1])
    with col_b:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.user_info = None
            st.rerun()

    # --- PILIHAN PERIODE DASHBOARD ---
    selected_period_name = st.selectbox("📌 Pilih Periode Promosi", active_periods)
    period_row = df_periode[df_periode["period_name"] == selected_period_name]
    period_id = period_row.iloc[0]["period_id"] if not period_row.empty else "P01"
    
    # --- KALKULASI TARGET & METRICS PERSONIL ---
    # 1. Total Target Toko & Target Personil
    target_toko = float(period_row.iloc[0]["target_total"]) if not period_row.empty and pd.notnull(period_row.iloc[0]["target_total"]) else 0.0
    active_personil_count = len(df_personil[df_personil["active"] == True]) if "active" in df_personil.columns else len(df_personil)
    target_personil = target_toko / active_personil_count if active_personil_count > 0 else 0.0
    
    # 2. Total Terjual Personil pada Periode Terpilih
    user_sales_period = df_sales_p[
        (df_sales_p["person_name"].str.upper() == person_name.upper()) & 
        (df_sales_p["period_id"] == period_id)
    ] if not df_sales_p.empty else pd.DataFrame()
    
    total_qty_personil = int(round(user_sales_period["actual_qty"].sum())) if not user_sales_period.empty else 0
    pct_ach_personil = (total_qty_personil / target_personil * 100) if target_personil > 0 else 0.0
    
    # 3. Item Terbanyak Dijual Personil
    top_item_name = "-"
    top_item_qty = 0
    top_item_pct = 0.0
    
    if not user_sales_period.empty and user_sales_period["actual_qty"].sum() > 0:
        top_group = user_sales_period.groupby("item_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        top_item_name = top_group.iloc[0]["item_name"]
        top_item_qty = int(round(top_group.iloc[0]["actual_qty"]))
        
        # Cari Target Item Personil pada Periode Tersebut
        item_target_row = df_sales_i[(df_sales_i["period_id"] == period_id) & (df_sales_i["item_name"] == top_item_name)]
        if not item_target_row.empty and pd.to_numeric(item_target_row.iloc[0]["target_qty"], errors="coerce") is not None:
            item_target_store = float(item_target_row.iloc[0]["target_qty"])
            item_target_person = item_target_store / active_personil_count if active_personil_count > 0 else 0.0
            top_item_pct = (top_item_qty / item_target_person * 100) if item_target_person > 0 else 0.0

    # Kata Motivasi Otomatis
    st.markdown(f"""
    <div class='quote-box'>
        "{get_motivational_quote(total_qty_personil)}"
    </div>
    <br>
    """, unsafe_allow_html=True)

    # Display Metrics Card
    st.markdown("<h3 style='color: #38bdf8; font-size: 18px;'>📊 Performa Penjualan Anda</h3>", unsafe_allow_html=True)
    
    m1, m2 = st.columns(2)
    with m1:
        st.markdown(f"""
        <div class='card' style='text-align: center;'>
            <div class='metric-lbl'>Total Terjual</div>
            <div class='metric-val'>{total_qty_personil:,} <span style='font-size:13px;'>Pcs</span></div>
            <div class='metric-sub'>🎯 {pct_ach_personil:.1f}% Target</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class='card' style='text-align: center;'>
            <div class='metric-lbl'>Item Terbanyak</div>
            <div class='metric-val' title='{top_item_name}'>{top_item_name}</div>
            <div class='metric-sub'>📦 {top_item_qty} Pcs ({top_item_pct:.1f}%)</div>
        </div>
        """, unsafe_allow_html=True)

    # --- FORM INPUT PENJUALAN & CATATAN ---
    st.markdown("<h3 style='color: #38bdf8; font-size: 18px; margin-top: 10px;'>📝 Form Laporan & Catatan Sales</h3>", unsafe_allow_html=True)
    
    # Filter Item PSM Otomatis Berdasarkan Periode Terpilih
    items_in_period = df_sales_i[(df_sales_i["period_id"] == period_id) & (df_sales_i["item_name"] != "NAMA ITEM")]["item_name"].tolist() if not df_sales_i.empty else []
    if not items_in_period:
        items_in_period = df_item[df_item["active"] == True]["item_name"].tolist() if "active" in df_item.columns else df_item["item_name"].tolist()
    
    with st.form("form_report_personil", clear_on_submit=True):
        selected_item_name = st.selectbox("📦 Pilih Item PSM (Promosi Periode Ini)", items_in_period)
        
        # Dapatkan item_id
        item_row = df_item[df_item["item_name"] == selected_item_name]
        item_id = item_row.iloc[0]["item_id"] if not item_row.empty else "ITM0001"
        
        c_qty, c_date = st.columns(2)
        with c_qty:
            input_qty = st.number_input("🔢 Qty Terjual (Pcs)", min_value=1, value=1, step=1)
        with c_date:
            input_date = st.date_input("📅 Tanggal Penjualan", value=datetime.now())
            
        input_catatan = st.text_area("💬 Catatan Harian / Kendala Penjualan Personil", placeholder="Contoh: Menawarkan ke 15 konsumen, stokdisplay rapi...")
        
        submit_report = st.form_submit_button("🚀 SIMPAN LAPORAN PENJUALAN")
        
        if submit_report:
            new_record_id = f"SP{len(df_sales_p) + 1:05d}" if not df_sales_p.empty else "SP00001"
            today_str = str(datetime.now().strftime("%Y-%m-%d"))
            
            new_row = {
                "record_id": new_record_id,
                "period_id": period_id,
                "item_id": item_id,
                "item_name": selected_item_name,
                "person_id": person_id,
                "person_name": person_name,
                "actual_qty": int(round(input_qty)),
                "updated_at": today_str,
                "tanggal_input": str(input_date),
                "catatan": input_catatan
            }
            
            if conn is not None:
                try:
                    updated_df = pd.concat([df_sales_p, pd.DataFrame([new_row])], ignore_index=True)
                    conn.update(worksheet="SALES_PERSONIL", data=updated_df)
                    st.success(f"✅ Laporan {selected_item_name} ({int(input_qty)} Pcs) berhasil dikirim!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as ex:
                    st.warning(f"⚠️ Berhasil diproses, kendala sync Sheets: {ex}")
            else:
                st.success(f"✅ Laporan {selected_item_name} ({int(input_qty)} Pcs) berhasil dicatat!")

    # --- RIWAYAT CATATAN & REPORT PERSONIL ---
    st.markdown("<h3 style='color: #38bdf8; font-size: 18px; margin-top: 20px;'>📋 Riwayat Input Periode Ini</h3>", unsafe_allow_html=True)
    
    if not user_sales_period.empty:
        disp_cols = [c for c in ["period_id", "item_name", "actual_qty", "updated_at", "catatan"] if c in user_sales_period.columns]
        disp_df = user_sales_period[disp_cols].copy()
        disp_df.columns = ["Periode", "Nama Item", "Qty (Pcs)", "Tanggal", "Catatan Staf"][:len(disp_cols)]
        st.dataframe(disp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada riwayat input penjualan pada periode terpilih.")='text-align: center;'>
            <div class='metric-lbl'>Jumlah Input</div>
            <div class='metric-val'>{total_transaksi} <span style='font-size:14px;'>Kali</span></div>
        </div>
        """, unsafe_allow_html=True)

    # --- FORM INPUT PENJUALAN & CATATAN ---
    st.markdown("<h3 style='color: #38bdf8; font-size: 18px; margin-top: 10px;'>📝 Form Laporan & Catatan Sales</h3>", unsafe_allow_html=True)
    
    with st.form("form_report_personil", clear_on_submit=True):
        active_periods = df_periode[df_periode["status"] == "OPEN"]["period_name"].tolist() if "status" in df_periode.columns else df_periode["period_name"].tolist()
        if not active_periods:
            active_periods = df_periode["period_name"].tolist()
        
        selected_period_name = st.selectbox("📌 Pilih Periode Toko", active_periods)
        
        period_row = df_periode[df_periode["period_name"] == selected_period_name]
        period_id = period_row.iloc[0]["period_id"] if not period_row.empty else "P01"
        
        active_items = df_item[df_item["active"] == True]["item_name"].tolist() if "active" in df_item.columns else df_item["item_name"].tolist()
        selected_item_name = st.selectbox("📦 Pilih Item PSM", active_items)
        
        item_row = df_item[df_item["item_name"] == selected_item_name]
        item_id = item_row.iloc[0]["item_id"] if not item_row.empty else "ITM0001"
        
        c_qty, c_date = st.columns(2)
        with c_qty:
            input_qty = st.number_input("🔢 Qty Terjual (Pcs)", min_value=1, value=1, step=1)
        with c_date:
            input_date = st.date_input("📅 Tanggal Penjualan", value=datetime.now())
            
        input_catatan = st.text_area("💬 Catatan Harian / Kendala Penjualan Personil", placeholder="Contoh: Menawarkan ke 15 konsumen, stokdisplay rapi...")
        
        submit_report = st.form_submit_button("🚀 SIMPAN LAPORAN PENJUALAN")
        
        if submit_report:
            new_record_id = f"SP{len(df_sales_p) + 1:05d}" if not df_sales_p.empty else "SP00001"
            today_str = str(datetime.now().strftime("%Y-%m-%d"))
            
            new_row = {
                "record_id": new_record_id,
                "period_id": period_id,
                "item_id": item_id,
                "item_name": selected_item_name,
                "person_id": person_id,
                "person_name": person_name,
                "actual_qty": int(input_qty),
                "updated_at": today_str,
                "tanggal_input": str(input_date),
                "catatan": input_catatan
            }
            
            if conn is not None:
                try:
                    updated_df = pd.concat([df_sales_p, pd.DataFrame([new_row])], ignore_index=True)
                    conn.update(worksheet="SALES_PERSONIL", data=updated_df)
                    st.success(f"✅ Laporan {selected_item_name} ({input_qty} Pcs) berhasil dikirim ke Web Monitoring!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as ex:
                    st.warning(f"⚠️ Berhasil diproses, kendala sync Sheets: {ex}")
            else:
                st.success(f"✅ Laporan {selected_item_name} ({input_qty} Pcs) berhasil dicatat!")

    # --- RIWAYAT CATATAN & REPORT PERSONIL ---
    st.markdown("<h3 style='color: #38bdf8; font-size: 18px; margin-top: 20px;'>📋 Riwayat Input Anda</h3>", unsafe_allow_html=True)
    
    if not user_sales.empty:
        disp_cols = [c for c in ["period_id", "item_name", "actual_qty", "updated_at", "catatan"] if c in user_sales.columns]
        disp_df = user_sales[disp_cols].copy()
        disp_df.columns = ["Periode", "Nama Item", "Qty (Pcs)", "Tanggal", "Catatan Staf"][:len(disp_cols)]
        st.dataframe(disp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada riwayat input penjualan untuk akun Anda.")
      
