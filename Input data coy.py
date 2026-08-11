import streamlit as st
import pandas as pd
from datetime import datetime
import random
import requests

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

# --- CSS STYLING (DARK NEON MOBILE VERSION) ---
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
"""
st.markdown(css_code, unsafe_allow_html=True)

# --- BACA DATA REALTIME GOOGLE SHEETS ---
@st.cache_data(ttl=2)
def load_data():
    try:
        def read_sheet_csv(sheet_name):
            url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
            return pd.read_csv(url)

        df_personil = read_sheet_csv("MASTER_PERSONIL")
        df_item = read_sheet_csv("MASTER_ITEM")
        df_periode = read_sheet_csv("PERIODE")
        df_sales_i = read_sheet_csv("SALES_ITEM")
        df_sales_p = read_sheet_csv("SALES_PERSONIL")
        
        if "actual_qty" in df_sales_p.columns:
            df_sales_p["actual_qty"] = pd.to_numeric(df_sales_p["actual_qty"], errors="coerce").fillna(0).astype(int)
            
        return df_personil, df_item, df_periode, df_sales_i, df_sales_p
    except Exception as e:
        st.error(f"❌ Gagal membaca database Google Sheets: {e}")
        st.stop()

df_personil, df_item, df_periode, df_sales_i, df_sales_p = load_data()

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
            # --- CEK HAK AKSES DEVELOPER / ADMIN ---
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
                        st.error("❌ Password salah! (Default password adalah NIK Anda).")
                else:
                    st.error("❌ Nama / NIK Personil tidak ditemukan dalam Database.")
                    
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 2. HALAMAN UTAMA (SETELAH LOGIN)
# ==========================================
else:
    user = st.session_state.user_info
    is_admin = user.get("is_admin", False)
    
    active_periods = df_periode[df_periode["status"] == "OPEN"]["period_name"].tolist() if "status" in df_periode.columns else df_periode["period_name"].tolist()
    if not active_periods:
        active_periods = df_periode["period_name"].tolist()

    # BANNER DASHBOARD (ADMIN VS PERSONIL)
    if is_admin:
        st.markdown(f"""
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
            st.rerun()

    selected_period_name = st.selectbox("📌 Pilih Periode Promosi", active_periods)
    period_row = df_periode[df_periode["period_name"] == selected_period_name]
    period_id = str(period_row.iloc[0]["period_id"]) if not period_row.empty else "P01"
    
    # JIKA ADMIN: BISA PILIH PERSONIL YANG INGIN DI-INPUTKAN
    target_person_name = user["person_name"]
    target_person_id = user["person_id"]
    
    if is_admin:
        st.markdown("<h4 style='color: #f43f5e; margin-top: 10px;'>⚙️ Pengaturan Admin</h4>", unsafe_allow_html=True)
        all_personil_list = df_personil["person_name"].tolist() if not df_personil.empty else []
        selected_admin_target = st.selectbox("👤 Pilih Personil (Untuk Input / Lihat Data)", ["-- SEMUA PERSONIL (Toko) --"] + all_personil_list)
        
        if selected_admin_target != "-- SEMUA PERSONIL (Toko) --":
            target_person_name = selected_admin_target
            p_match = df_personil[df_personil["person_name"] == target_person_name]
            target_person_id = str(p_match.iloc[0]["person_id"]) if not p_match.empty and "person_id" in p_match.columns else "PRS001"

    target_toko = float(period_row.iloc[0]["target_total"]) if not period_row.empty and pd.notnull(period_row.iloc[0]["target_total"]) else 0.0
    active_personil_count = len(df_personil[df_personil["active"] == True]) if "active" in df_personil.columns else len(df_personil)
    target_personil = target_toko / active_personil_count if active_personil_count > 0 else 0.0
    
    # Filter Penjualan Spesifik Personil / Semua
    if is_admin and selected_admin_target == "-- SEMUA PERSONIL (Toko) --":
        user_sales_period = df_sales_p[df_sales_p["period_id"].astype(str).str.strip() == period_id] if not df_sales_p.empty else pd.DataFrame()
    else:
        user_sales_period = df_sales_p[
            (df_sales_p["person_name"].astype(str).str.strip().str.upper() == target_person_name.upper()) & 
            (df_sales_p["period_id"].astype(str).str.strip() == period_id)
        ] if not df_sales_p.empty else pd.DataFrame()
    
    total_qty_personil = int(user_sales_period["actual_qty"].sum()) if not user_sales_period.empty else 0
    pct_ach_personil = (total_qty_personil / (target_toko if (is_admin and selected_admin_target == "-- SEMUA PERSONIL (Toko) --") else target_personil) * 100) if target_personil > 0 else 0.0
    
    top_item_name = "-"
    top_item_qty = 0
    top_item_pct = 0.0
    
    if not user_sales_period.empty and user_sales_period["actual_qty"].sum() > 0:
        top_group = user_sales_period.groupby("item_name")["actual_qty"].sum().reset_index().sort_values(by="actual_qty", ascending=False)
        top_item_name = top_group.iloc[0]["item_name"]
        top_item_qty = int(top_group.iloc[0]["actual_qty"])
        
        item_target_row = df_sales_i[(df_sales_i["period_id"] == period_id) & (df_sales_i["item_name"] == top_item_name)]
        if not item_target_row.empty and pd.to_numeric(item_target_row.iloc[0]["target_qty"], errors="coerce") is not None:
            item_target_store = float(item_target_row.iloc[0]["target_qty"])
            item_target_person = item_target_store / active_personil_count if active_personil_count > 0 else 0.0
            top_item_pct = (top_item_qty / item_target_person * 100) if item_target_person > 0 else 0.0

    if not is_admin:
        st.markdown(f"<div class='quote-box'>\"{get_motivational_quote(total_qty_personil)}\"</div><br>", unsafe_allow_html=True)

    st.markdown(f"<h3 style='color: #38bdf8; font-size: 18px;'>📊 Performa Penjualan {'Toko' if (is_admin and selected_admin_target == '-- SEMUA PERSONIL (Toko) --') else target_person_name}</h3>", unsafe_allow_html=True)
    
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

    # FORM INPUT PENJUALAN
    st.markdown(f"<h3 style='color: #38bdf8; font-size: 18px; margin-top: 10px;'>📝 Form Input Laporan {'(Mode Admin)' if is_admin else ''}</h3>", unsafe_allow_html=True)
    
    items_in_period = df_sales_i[(df_sales_i["period_id"] == period_id) & (df_sales_i["item_name"] != "NAMA ITEM")]["item_name"].tolist() if not df_sales_i.empty else []
    if not items_in_period:
        items_in_period = df_item[df_item["active"] == True]["item_name"].tolist() if "active" in df_item.columns else df_item["item_name"].tolist()
    
    with st.form("form_report_personil", clear_on_submit=True):
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
            
        input_catatan = st.text_area("💬 Catatan Harian / Kendala Penjualan Personil", placeholder="Contoh: Menawarkan ke 15 konsumen, stokdisplay rapi...")
        
        submit_report = st.form_submit_button("🚀 SIMPAN LAPORAN PENJUALAN")
        
        if submit_report:
            new_record_id = f"SP{len(df_sales_p) + 1:05d}"
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
                    st.success(f"✅ Laporan {selected_item_name} ({int(input_qty)} Pcs) Atas Nama {target_person_name_input} Tersimpan!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("⚠️ Gagal menyimpan ke Google Sheets, pastikan Apps Script Deploy diset 'Anyone'.")
            except Exception as ex:
                st.error(f"❌ Terjadi kesalahan saat mengirim data: {ex}")

    # RIWAYAT & MANAGEMENT HAPUS OLEH ADMIN
    st.markdown("<h3 style='color: #38bdf8; font-size: 18px; margin-top: 20px;'>📋 Riwayat Input Penjualan</h3>", unsafe_allow_html=True)
    
    if not user_sales_period.empty:
        if is_admin:
            st.info("💡 **Fitur Admin**: Anda dapat menghapus baris laporan yang salah langsung dari tabel di bawah.")
            for idx, row in user_sales_period.iterrows():
                r_id = str(row.get("record_id", f"SP{idx:05d}"))
                p_name = str(row.get("person_name", "-"))
                i_name = str(row.get("item_name", "-"))
                qty = int(row.get("actual_qty", 0))
                tgl = str(row.get("updated_at", "-"))
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"🔹 **[{tgl}]** {p_name} - **{i_name}** ({qty} Pcs)")
                with col2:
                    if st.button("🗑️ Hapus", key=f"del_{r_id}_{idx}"):
                        delete_payload = {"action": "delete", "record_id": r_id}
                        try:
                            del_res = requests.post(APPS_SCRIPT_URL, json=delete_payload, timeout=8)
                            st.success(f"🗑️ Laporan {r_id} berhasil dihapus!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal menghapus: {e}")
                st.divider()
        else:
            disp_cols = [c for c in ["period_id", "item_name", "actual_qty", "
