import streamlit as st
import pandas as pd
from datetime import datetime
import random
import requests
from concurrent.futures import ThreadPoolExecutor

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Input Report PSM Toko",
    page_icon="📱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- URL GOOGLE APPS SCRIPT & SPREADSHEET ID ---
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzPHZQug5zuiTmt3C4YlbHqLj5avf7HYK8YqYw-n2v-TavnlgsdRwuUn9r_qR8i-7lshQ/exec"
SPREADSHEET_ID = "1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk"

# --- CSS STYLING (DARK NEON MOBILE VERSION & UNIFORM MENU BUTTONS) ---
css_code = """
<style>
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
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
    .card-admin {
        background: linear-gradient(135deg, #311021 0%, #4c0519 100%);
        border: 1px solid #f43f5e;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 0 15px rgba(244, 63, 94, 0.3);
    }
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
    
    /* Tombol Utama (Submit / Logout / Back) */
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

    /* Kartu Menu Grid Bersampingan */
    div[data-testid="stHorizontalBlock"] .stButton > button {
        background-color: #161e2e !important;
        background: #161e2e !important;
        border: 1px solid #1f293d !important;
        border-radius: 12px !important;
        padding: 16px 10px !important;
        height: auto !important;
        min-height: 80px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        font-size: 13px !important;
        line-height: 1.4 !important;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.4) !important;
        transform: translateY(-2px);
    }

    div[data-baseweb="input"] {
        background-color: #0f172a !important;
        border-color: #334155 !important;
        border-radius: 8px !important;
        color: white !important;
    }
</style>
"""
st.markdown(css_code, unsafe_allow_html=True)

# --- SESSION STATE MANAGEMENT ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "deleted_records" not in st.session_state:
    st.session_state.deleted_records = set()
if "current_page" not in st.session_state:
    st.session_state.current_page = "main"

# --- BACA DATA REALTIME GOOGLE SHEETS (OPTIMASI PARALEL FAST LOADING) ---
@st.cache_data(ttl=60)
def load_data():
    try:
        sheets = ["MASTER_PERSONIL", "MASTER_ITEM", "PERIODE", "SALES_ITEM", "SALES_PERSONIL"]
        
        def read_sheet(sheet_name):
            url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
            return sheet_name, pd.read_csv(url)

        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(read_sheet, s) for s in sheets]
            for future in futures:
                s_name, df = future.result()
                results[s_name] = df

        df_personil = results["MASTER_PERSONIL"]
        df_item = results["MASTER_ITEM"]
        df_periode = results["PERIODE"]
        df_sales_i = results["SALES_ITEM"]
        df_sales_p = results["SALES_PERSONIL"]
        
        if "actual_qty" in df_sales_p.columns:
            df_sales_p["actual_qty"] = pd.to_numeric(df_sales_p["actual_qty"], errors="coerce").fillna(0).astype(int)
            
        return df_personil, df_item, df_periode, df_sales_i, df_sales_p
    except Exception as e:
        st.error(f"❌ Gagal membaca database Google Sheets: {e}")
        st.stop()

df_personil, df_item, df_periode, df_sales_i, df_sales_p_raw = load_data()

# Filter record yang dihapus secara lokal
if not df_sales_p_raw.empty and "record_id" in df_sales_p_raw.columns:
    df_sales_p = df_sales_p_raw[~df_sales_p_raw["record_id"].astype(str).str.strip().str.upper().isin(st.session_state.deleted_records)].copy()
else:
    df_sales_p = df_sales_p_raw.copy()

# --- MOTIVATIONAL QUOTES ENGINE ---
def get_motivational_quote(qty_achieved):
    high_quotes = [
        "🔥 Performa luar biasa! Pertahankan ritme penjualan terbaikmu hari ini!",
        "🚀 Juara! Dedikasi dan usahamu memberikan kontribusi besar untuk toko!",
        "⭐ Luar biasa! Semangatmu adalah inspirasi bagi seluruh tim toko!"
    ]
    medium_quotes = [
        "📈 Hasil yang sangat baik! Sedikit dorongan lagi untuk mencapai hasil maksimal!",
        "👍 Progres yang konsisten! Tetap fokus tawarkan item PSM ke setiap pelanggan!"
    ]
    low_quotes = [
        "🌱 Awal yang baik! Ayo tingkatkan penawaran PSM ke setiap konsumen hari ini!",
        "💡 Setiap transaksi adalah peluang! Tetap antusias dan tawarkan produk unggulan!"
    ]
    if qty_achieved >= 100:
        return random.choice(high_quotes)
    elif qty_achieved >= 30:
        return random.choice(medium_quotes)
    else:
        return random.choice(low_quotes)

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
            elif username_input.lower() == "admin" and password_input == "lavitality":
                st.session_state.logged_in = True
                st.session_state.user_info = {
                    "person_id": "ADM001",
                    "person_name": "DEVELOPER / ADMIN",
                    "nik": "ADMINISTRATOR",
                    "is_admin": True
                }
                st.success("⚡ Login Admin/Developer Berhasil!")
                st.rerun()
            else:
                user_match = df_personil[
                    (df_personil['person_name'].astype(str).str.strip().str.upper() == username_input.upper()) |
                    (df_personil['nik'].astype(str).str.strip() == username_input)
                ]
                
                if not user_match.empty:
                    person_row = user_match.iloc[0]
                    expected_pass = str(person_row['nik']) if pd.notnull(person_row['nik']) else "12345"
                    
                    if password_input in [expected_pass, "12345", str(person_row['person_name']).lower()]:
                        st.session_state.logged_in = True
                        st.session_state.user_info = {
                            "person_id": str(person_row.get("person_id", f"PRS{person_row.name:03d}")),
                            "person_name": str(person_row["person_name"]).strip(),
                            "nik": str(person_row["nik"]),
                            "is_admin": False
                        }
                        st.success(f"✅ Login Berhasil! Selamat datang {person_row['person_name']}")
                        st.rerun()
                    else:
                        st.error("❌ Password salah!")
                else:
                    st.error("❌ Nama / NIK Personil tidak ditemukan.")
                    
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 2. HALAMAN UTAMA ATAU SUB-HALAMAN MENU
# ==========================================
else:
    user = st.session_state.user_info
    is_admin = user.get("is_admin", False)
    
    active_periods = df_periode[df_periode["status"] == "OPEN"]["period_name"].tolist() if "status" in df_periode.columns else df_periode["period_name"].tolist()
    if not active_periods:
        active_periods = df_periode["period_name"].tolist()

    # --- SUB HALAMAN 1: DETAIL TOTAL TERJUAL ---
    if st.session_state.current_page == "detail_total":
        if st.button("⬅️ Kembali ke Menu Utama"):
            st.session_state.current_page = "main"
            st.rerun()
            
        st.markdown("<h2 style='color: #38bdf8;'>📊 Detail Transaksi Penjualan</h2>", unsafe_allow_html=True)
        st.caption("Rincian seluruh laporan transaksi yang masuk pada periode ini.")
        
        if not df_sales_p.empty:
            disp_cols = [c for c in ["updated_at", "person_name", "item_name", "actual_qty", "catatan"] if c in df_sales_p.columns]
            show_df = df_sales_p[disp_cols].copy()
            show_df.columns = ["Tanggal", "Personil", "Nama Item", "Qty (Pcs)", "Catatan"][:len(disp_cols)]
            st.dataframe(show_df, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data transaksi.")

    # --- SUB HALAMAN 2: DETAIL ITEM TERBANYAK ---
    elif st.session_state.current_page == "detail_item":
        if st.button("⬅️ Kembali ke Menu Utama"):
            st.session_state.current_page = "main"
            st.rerun()
            
        st.markdown("<h2 style='color: #38bdf8;'>🏆 Peringkat Penjualan Per Item</h2>", unsafe_allow_html=True)
        st.caption("Daftar produk paling laku diurutkan dari penjualan terbanyak.")
        
        if not df_sales_p.empty and df_sales_p["actual_qty"].sum() > 0:
            item_ranking = df_sales_p.groupby("item_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
            item_ranking.columns = ["Nama Produk / Item", "Total Qty Terjual (Pcs)"]
            st.dataframe(item_ranking, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada data item terjual.")

    # --- SUB HALAMAN 3: FORM INPUT LAPORAN ---
    elif st.session_state.current_page == "form_input":
        if st.button("⬅️ Kembali ke Menu Utama"):
            st.session_state.current_page = "main"
            st.rerun()

        st.markdown(f"<h2 style='color: #38bdf8;'>📝 Form Input Laporan {'(Mode Admin)' if is_admin else ''}</h2>", unsafe_allow_html=True)
        
        period_id = st.session_state.get("selected_period_id", "P01")
        target_person_name = st.session_state.get("target_person_name", user["person_name"])
        target_person_id = st.session_state.get("target_person_id", user["person_id"])
        selected_admin_target = st.session_state.get("selected_admin_target", "-- SEMUA PERSONIL (Toko) --")

        items_in_period = df_sales_i[(df_sales_i["period_id"] == period_id) & (df_sales_i["item_name"] != "NAMA ITEM")]["item_name"].tolist() if not df_sales_i.empty else []
        if not items_in_period:
            items_in_period = df_item[df_item["active"] == True]["item_name"].tolist() if "active" in df_item.columns else df_item["item_name"].tolist()
        
        with st.form("form_report_personil_page", clear_on_submit=True):
            if is_admin and selected_admin_target == "-- SEMUA PERSONIL (Toko) --":
                target_person_name_input = st.selectbox("👤 Inputkan Atas Nama Personil:", df_personil["person_name"].tolist())
                p_match2 = df_personil[df_personil["person_name"] == target_person_name_input]
                target_person_id_input = str(p_match2.iloc[0]["person_id"]) if not p_match2.empty and "person_id" in p_match2.columns else "PRS001"
            else:
                target_person_name_input = target_person_name
                target_person_id_input = target_person_id

            selected_item_name = st.selectbox("📦 Pilih Item PSM (Promosi Periode Ini)", items_in_period)
            item_row = df_item[df_item["item_name"] == selected_item_name]
            item_id = str(item_row.iloc[0]["item_id"]) if not item_row.empty else "ITM0001"
            
            c_qty, c_date = st.columns(2)
            with c_qty:
                input_qty = st.number_input("🔢 Qty Terjual (Pcs)", min_value=1, value=1, step=1)
            with c_date:
                input_date = st.date_input("📅 Tanggal Penjualan", value=datetime.now())
                
            input_catatan = st.text_area("💬 Catatan Harian / Kendala Penjualan Personil", placeholder="Contoh: Menawarkan ke 15 konsumen...")
            submit_report = st.form_submit_button("🚀 SIMPAN LAPORAN PENJUALAN")
            
            if submit_report:
                new_record_id = f"SP{len(df_sales_p_raw) + 1:05d}"
                today_str = str(datetime.now().strftime("%Y-%m-%d"))
                payload = {
                    "record_id": new_record_id,
                    "period_id": period_id,
                    "item_id": item_id,
                    "item_name": selected_item_name,
                    "person_id": target_person_id_input,
                    "person_name": target_person_name_input,
                    "actual_qty": int(input_qty),
                    "updated_at": today_str,
                    "tanggal_input": str(input_date),
                    "catatan": input_catatan
                }
                try:
                    res = requests.post(APPS_SCRIPT_URL, json=payload, timeout=8)
                    if res.status_code == 200:
                        st.success(f"✅ Laporan {selected_item_name} ({int(input_qty)} Pcs) Tersimpan!")
                        st.cache_data.clear()
                    else:
                        st.error("⚠️ Respon server gagal.")
                except Exception as ex:
                    st.error(f"❌ Terjadi kesalahan: {ex}")

    # --- SUB HALAMAN 4: RIWAYAT LAPORAN PENJUALAN ---
    elif st.session_state.current_page == "riwayat":
        if st.button("⬅️ Kembali ke Menu Utama"):
            st.session_state.current_page = "main"
            st.rerun()

        st.markdown("<h2 style='color: #38bdf8;'>📋 Riwayat Input Penjualan</h2>", unsafe_allow_html=True)
        
        period_id = st.session_state.get("selected_period_id", "P01")
        target_person_name = st.session_state.get("target_person_name", user["person_name"])
        selected_admin_target = st.session_state.get("selected_admin_target", "-- SEMUA PERSONIL (Toko) --")

        if is_admin and selected_admin_target == "-- SEMUA PERSONIL (Toko) --":
            user_sales_period = df_sales_p[df_sales_p["period_id"].astype(str).str.strip() == period_id] if not df_sales_p.empty else pd.DataFrame()
        else:
            user_sales_period = df_sales_p[
                (df_sales_p["person_name"].astype(str).str.strip().str.upper() == target_person_name.upper()) & 
                (df_sales_p["period_id"].astype(str).str.strip() == period_id)
            ] if not df_sales_p.empty else pd.DataFrame()

        if not user_sales_period.empty:
            if is_admin:
                st.info("💡 **Kelola Admin**: Klik tombol **Hapus** untuk menghapus record secara permanen.")
                for idx, row in user_sales_period.iterrows():
                    r_id = str(row.get("record_id", "")).strip()
                    p_name = str(row.get("person_name", "-"))
                    i_name = str(row.get("item_name", "-"))
                    qty = int(row.get("actual_qty", 0))
                    tgl = str(row.get("updated_at", "-"))
                    
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"🔹 **[{tgl}]** {p_name} - **{i_name}** ({qty} Pcs) - `ID: {r_id}`")
                    with col2:
                        if st.button("🗑️ Hapus", key=f"del_p_{r_id}_{idx}"):
                            delete_payload = {"action": "delete", "record_id": r_id}
                            try:
                                st.session_state.deleted_records.add(r_id.upper())
                                del_res = requests.post(APPS_SCRIPT_URL, json=delete_payload, timeout=8)
                                st.success(f"🗑️ Record {r_id} berhasil dihapus permanen!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Gagal menghapus: {e}")
                    st.divider()
            else:
                disp_cols = [c for c in ["period_id", "item_name", "actual_qty", "updated_at", "catatan"] if c in user_sales_period.columns]
                disp_df = user_sales_period[disp_cols].copy()
                disp_df.columns = ["Periode", "Nama Item", "Qty (Pcs)", "Tanggal", "Catatan Staf"][:len(disp_cols)]
                st.dataframe(disp_df, use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada riwayat input penjualan pada periode terpilih.")

    # ==========================================
    # HALAMAN UTAMA (DASBOR MENU UTAMA)
    # ==========================================
    else:
        if is_admin:
            st.markdown("""
            <div class='card-admin'>
                <div>
                    <span style='background-color: #f43f5e; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold;'>DEVELOPER ACCESS</span>
                    <h2 style='color: #ffffff; margin: 8px 0 2px 0; font-size: 22px;'>Mode Admin / Developer 🛠️</h2>
                    <p style='color: #fda4af; font-size: 12px; margin: 0;'>Akses Penuh: Input, Edit & Hapus Data Laporan Semua Personil</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='card-neon'>
                <div>
                    <span style='background-color: #0284c7; color: white; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold;'>PERSONIL TOKO</span>
                    <h2 style='color: #ffffff; margin: 8px 0 2px 0; font-size: 22px;'>Selamat Datang, {user['person_name']}! 👋</h2>
                    <p style='color: #94a3b8; font-size: 12px; margin: 0;'>NIK: {user["nik"]}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        col_a, col_b = st.columns([3, 1])
        with col_b:
            if st.button("🚪 Logout"):
                st.session_state.logged_in = False
                st.session_state.user_info = None
                st.session_state.current_page = "main"
                st.rerun()

        selected_period_name = st.selectbox("📌 Pilih Periode Promosi", active_periods)
        period_row = df_periode[df_periode["period_name"] == selected_period_name]
        period_id = str(period_row.iloc[0]["period_id"]) if not period_row.empty else "P01"
        st.session_state["selected_period_id"] = period_id
        
        target_person_name = user["person_name"]
        target_person_id = user["person_id"]
        selected_admin_target = "-- SEMUA PERSONIL (Toko) --"
        
        if is_admin:
            st.markdown("<h4 style='color: #f43f5e; margin-top: 10px;'>⚙️ Filter Tampilan Admin</h4>", unsafe_allow_html=True)
            all_personil_list = df_personil["person_name"].tolist() if not df_personil.empty else []
            selected_admin_target = st.selectbox("👤 Pilih Personil (Untuk Input / Kelola Data)", ["-- SEMUA PERSONIL (Toko) --"] + all_personil_list)
            st.session_state["selected_admin_target"] = selected_admin_target
            
            if selected_admin_target != "-- SEMUA PERSONIL (Toko) --":
                target_person_name = selected_admin_target
                p_match = df_personil[df_personil["person_name"] == target_person_name]
                target_person_id = str(p_match.iloc[0]["person_id"]) if not p_match.empty and "person_id" in p_match.columns else "PRS001"

        st.session_state["target_person_name"] = target_person_name
        st.session_state["target_person_id"] = target_person_id

        if is_admin and selected_admin_target == "-- SEMUA PERSONIL (Toko) --":
            user_sales_period = df_sales_p[df_sales_p["period_id"].astype(str).str.strip() == period_id] if not df_sales_p.empty else pd.DataFrame()
        else:
            user_sales_period = df_sales_p[
                (df_sales_p["person_name"].astype(str).str.strip().str.upper() == target_person_name.upper()) & 
                (df_sales_p["period_id"].astype(str).str.strip() == period_id)
            ] if not df_sales_p.empty else pd.DataFrame()
        
        total_qty_personil = int(user_sales_period["actual_qty"].sum()) if not user_sales_period.empty else 0

        if not is_admin:
            st.markdown(f"<div class='quote-box'>\"{get_motivational_quote(total_qty_personil)}\"</div><br>", unsafe_allow_html=True)

        st.markdown(f"<h3 style='color: #38bdf8; font-size: 18px;'>📊 Navigasi Menu {'Toko' if (is_admin and selected_admin_target == '-- SEMUA PERSONIL (Toko) --') else target_person_name}</h3>", unsafe_allow_html=True)
        
        # --- GRID 4 MENU UTAMA (2x2 BERSAMPINGAN) ---
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            btn_total = st.button("📊 TOTAL TERJUAL\n\n🔍 Klik Detail", key="btn_metric_total")
            if btn_total:
                st.session_state.current_page = "detail_total"
                st.rerun()

        with row1_col2:
            btn_item = st.button("🏆 ITEM TERBANYAK\n\n🔍 Klik Detail", key="btn_metric_item")
            if btn_item:
                st.session_state.current_page = "detail_item"
                st.rerun()

        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            btn_form = st.button("📝 INPUT LAPORAN\n\n➕ Tambah Data", key="btn_menu_form")
            if btn_form:
                st.session_state.current_page = "form_input"
                st.rerun()

        with row2_col2:
            btn_riwayat = st.button("📋 RIWAYAT LAPORAN\n\n📜 Liha/Kelola", key="btn_menu_riwayat")
            if btn_riwayat:
                st.session_state.current_page = "riwayat"
                st.rerun()
