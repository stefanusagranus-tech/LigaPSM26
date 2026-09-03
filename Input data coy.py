# --- IMPORT LIBRARY ---
import math
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="PSM Toko - Sales Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

SPREADSHEET_ID = "1kJ-OsjLEsFuNyyBg2TwxlWz8Ape4lwF9h0t66q3ldQk"

# =========================================================
# 2. INISIALISASI KONEKSI GOOGLE SHEETS & FUNGSI DATABASE
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)


@st.cache_data(ttl=60)
def load_database():
  """Membaca data sheet secara bertahap sesuai modul PSM, PPS, dan Store Performance."""
  try:
    periods_df = conn.read(worksheet="PERIODE", ttl=0)
    time.sleep(0.3)
    items_df = conn.read(worksheet="MASTER_ITEM", ttl=0)
    time.sleep(0.3)
    person_df = conn.read(worksheet="MASTER_PERSONIL", ttl=0)
    time.sleep(0.3)
    sales_item_df = conn.read(worksheet="SALES_ITEM", ttl=0)
    time.sleep(0.3)
    sales_person_df = conn.read(worksheet="SALES_PERSONIL", ttl=0)
    time.sleep(0.3)

    periods_pps_df = conn.read(worksheet="PERIODE_PPS", ttl=0)
    time.sleep(0.3)
    sales_pps_df = conn.read(worksheet="SALES_PPS", ttl=0)
    time.sleep(0.3)

    periods_store_df = conn.read(worksheet="PERIODE_STOREPERFORMANCE", ttl=0)
    time.sleep(0.3)
    sales_store_df = conn.read(worksheet="SALES_STOREPERFORMANCE", ttl=0)

    all_dfs = [
        periods_df,
        items_df,
        person_df,
        sales_item_df,
        sales_person_df,
        periods_pps_df,
        sales_pps_df,
        periods_store_df,
        sales_store_df,
    ]
    for df in all_dfs:
      if not df.empty:
        df.columns = df.columns.astype(str).str.strip().str.lower()

    for df in all_dfs:
      if not df.empty and "period_id" in df.columns:
        df["period_id"] = df["period_id"].astype(str).str.strip()

    for df in [items_df, sales_item_df, sales_person_df]:
      if not df.empty and "item_id" in df.columns:
        df["item_id"] = df["item_id"].astype(str).str.strip()

    for df in [person_df, sales_person_df, sales_pps_df, sales_store_df]:
      for col in ["person_name", "staff_name", "kasir_name"]:
        if not df.empty and col in df.columns:
          df[col] = df[col].astype(str).str.strip().str.upper()
          df[col] = df[col].str.replace(r"\s+", " ", regex=True)

    return (
        periods_df,
        periods_pps_df,
        periods_store_df,
        items_df,
        person_df,
        sales_item_df,
        sales_person_df,
        sales_pps_df,
        sales_store_df,
    )
  except Exception as e:
    st.error(f"Gagal membaca Google Sheets: {e}")
    return tuple([pd.DataFrame() for _ in range(9)])


def save_database(
    sales_item_df, sales_person_df, sales_pps_df, sales_store_df
):
  """Menyimpan data transaksi ke Google Sheets dengan pengaman validasi data kosong."""
  try:
    if sales_item_df.empty or sales_person_df.empty:
      st.warning(
          "⚠️ Proses simpan dibatalkan: Data transaksi terdeteksi kosong untuk"
          " mencegah kehilangan data."
      )
      return False

    conn.update(worksheet="SALES_ITEM", data=sales_item_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_PERSONIL", data=sales_person_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_PPS", data=sales_pps_df)
    time.sleep(0.4)
    conn.update(worksheet="SALES_STOREPERFORMANCE", data=sales_store_df)

    st.toast(
        "Perubahan transaksi tersimpan permanen di Google Sheets!", icon="✅"
    )
    return True
  except Exception as e:
    st.error(
        f"❌ Gagal menyimpan transaksi ke Google Sheets (Kemungkinan terkena"
        f" limit/timeout): {e}"
    )
    return False


def save_master_table(sheet_name, df_data):
  """Menyimpan tabel master dengan pengaman validasi data kosong dan urutan kolom."""
  try:
    if df_data.empty:
      st.warning(f"⚠️ Master {sheet_name} batal disimpan karena data kosong.")
      return False

    if sheet_name == "MASTER_ITEM":
      expected_cols = ["period_id", "item_id", "item_name", "active", "category"]
      for col in expected_cols:
        if col not in df_data.columns:
          df_data[col] = ""
      df_data = df_data[expected_cols]

    conn.update(worksheet=sheet_name, data=df_data)
    time.sleep(0.3)
    st.toast(
        f"Master {sheet_name} berhasil diperbarui di Google Sheets!", icon="✅"
    )
    return True
  except Exception as e:
    st.error(f"❌ Gagal update master {sheet_name} (Terkena limit API): {e}")
    return False


def sync_store_sales_from_personnel():
  if (
      "sales_person_df" in st.session_state
      and "sales_item_df" in st.session_state
  ):
    sp_df = st.session_state.sales_person_df.copy()
    si_df = st.session_state.sales_item_df.copy()

    req_cols_sp = ["period_id", "item_id", "actual_qty"]
    req_cols_si = ["period_id", "item_id"]

    if sp_df.empty or not all(col in sp_df.columns for col in req_cols_sp):
      return
    if si_df.empty or not all(col in si_df.columns for col in req_cols_si):
      return

    sp_df["period_id"] = sp_df["period_id"].astype(str)
    sp_df["item_id"] = sp_df["item_id"].astype(str)
    si_df["period_id"] = si_df["period_id"].astype(str)
    si_df["item_id"] = si_df["item_id"].astype(str)

    sp_df["actual_qty"] = pd.to_numeric(
        sp_df["actual_qty"], errors="coerce"
    ).fillna(0)
    tot_per_item = (
        sp_df.groupby(["period_id", "item_id"])["actual_qty"]
        .sum()
        .reset_index()
    )
    tot_per_item.rename(columns={"actual_qty": "calc_actual_qty"}, inplace=True)

    if "calc_actual_qty" in si_df.columns:
      si_df.drop(columns=["calc_actual_qty"], inplace=True)

    merged = pd.merge(
        si_df, tot_per_item, on=["period_id", "item_id"], how="left"
    )
    merged["calc_actual_qty"] = merged["calc_actual_qty"].fillna(0)
    merged["actual_qty"] = merged["calc_actual_qty"]
    merged.drop(columns=["calc_actual_qty"], inplace=True)
    st.session_state.sales_item_df = merged


if "data_loaded" not in st.session_state:
  (
      p_df,
      p_pps_df,
      p_store_df,
      i_df,
      pers_df,
      si_df,
      sp_df,
      s_pps_df,
      s_store_df,
  ) = load_database()
  st.session_state.periods_df = p_df
  st.session_state.periods_pps_df = p_pps_df
  st.session_state.periods_store_df = p_store_df
  st.session_state.items_df = i_df
  st.session_state.person_df = pers_df
  st.session_state.sales_item_df = si_df
  st.session_state.sales_person_df = sp_df
  st.session_state.sales_pps_df = s_pps_df
  st.session_state.sales_store_df = s_store_df
  st.session_state.data_loaded = True

# ==========================================
# 3. WAKTU REALTIME GMT+7 (WIB)
# ==========================================
waktu_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
current_time_str = waktu_wib.strftime("%A, %d %B %Y | %H:%M WIB")

# ==========================================
# 4. DATABASE AKUN PENGGUNA (LOGIN)
# ==========================================
USER_DATABASE = {
    "admin": {"password": "lavitality", "nama": "admin"},
    "23044862": {"password": "c383kgs", "nama": "ARIS APRILIANTO"},
    "24091737": {"password": "c383kgs", "nama": "TIKA"},
    "24096619": {"password": "c383kgs", "nama": "RIZKI GUNAWAN"},
    "25037119": {"password": "c383kgs", "nama": "ADELIA PRATIWI"},
    "26065884": {"password": "c383kgs", "nama": "ILHAM PRIANDIKA"},
    "13127006": {"password": "c383kgs", "nama": "REZA PURNAMA AGUSTIN"},
    "16016359": {"password": "c383kgs", "nama": "SUBEKTI PANDU YULIANTO"},
    "19061965": {"password": "c383kgs", "nama": "KUSDEWI TIA NINGRUM"},
    "21046101": {"password": "c383kgs", "nama": "AHMAD ZAKI SYABANI ZEN"},
    "visitor": {"password": "visitor", "nama": "Pengunjung"},
}


def check_login(input_username, input_password):
  if "person_df" in st.session_state and not st.session_state.person_df.empty:
    df_users = st.session_state.person_df
  else:
    df_users = conn.read(worksheet="MASTER_PERSONIL", ttl=0)

  user_match = df_users[
      (
          df_users["username"].astype(str).str.strip().str.lower()
          == str(input_username).strip().lower()
      )
      & (
          df_users["password"].astype(str).str.strip()
          == str(input_password).strip()
      )
  ]

  if not user_match.empty:
    matched_user = user_match.iloc[0]
    st.session_state["username"] = matched_user["username"]
    st.session_state["user_role"] = matched_user.get("role", "Staff Toko")
    st.session_state["role"] = matched_user.get("role", "Staff Toko")
    return True
  return False


# ==========================================
# 5. HALAMAN UTAMA & NAVIGASI SIDEBAR
# ==========================================
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "username" not in st.session_state:
  st.session_state.username = ""
if "user_role" not in st.session_state:
  st.session_state.user_role = ""

if not st.session_state.logged_in:
  st.markdown(
      "<h2 style='text-align: center; color: #00f0ff;'>🔐 LOGIN SISTEM SALES"
      " PSM</h2>",
      unsafe_allow_html=True,
  )
  col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])

  with col_l2:
    with st.form("form_login"):
      u_input = st.text_input("NIK / Username").strip()
      p_input = st.text_input("Password", type="password").strip()
      btn_login = st.form_submit_button(
          "🚀 Masuk Aplikasi", use_container_width=True
      )

      if btn_login:
        if (
            u_input in USER_DATABASE
            and USER_DATABASE[u_input]["password"] == p_input
        ):
          st.session_state.logged_in = True
          st.session_state.username = u_input
          st.session_state.user_role = (
              "Admin" if u_input == "admin" else "Staff Toko"
          )
          st.toast("🎉 Login Berhasil!", icon="✅")
          time.sleep(0.8)
          st.rerun()
        elif check_login(u_input, p_input):
          st.session_state.logged_in = True
          st.toast("🎉 Login Berhasil!", icon="✅")
          time.sleep(0.8)
          st.rerun()
        else:
          st.error("❌ NIK atau Password salah!")

  st.stop()

with st.sidebar:
  st.markdown(
      "<h3 style='color: #00f0ff;'>🛒 PSM TOKO C383</h3>", unsafe_allow_html=True
  )
  st.markdown(f"👤 **User:** `{st.session_state.get('username', '-')}`")
  st.markdown(f"🏷️ **Role:** `{st.session_state.get('user_role', 'Staff')}`")
  st.markdown(f"🕒 `{current_time_str}`")
  st.markdown("---")

  selected_menu = st.radio(
      "🧭 **Navigasi Menu Utama**",
      [
          "🏠 Dashboard Utama",
          "📥 Input Sales Harian",
          "🎯 Program PPS & Sueger",
          "⚙️ Pengaturan",
      ],
  )

  st.markdown("---")
  if st.button("🚪 Keluar / Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_role = ""
    st.rerun()

sync_store_sales_from_personnel()

periods_dict = {}
if "periods_df" in st.session_state and not st.session_state.periods_df.empty:
  for _, row in st.session_state.periods_df.iterrows():
    p_id = str(row.get("period_id", ""))
    p_name = str(row.get("period_name", ""))
    if p_id and p_name:
      periods_dict[p_name] = p_id

selected_period_name = (
    list(periods_dict.keys())[0] if periods_dict else "Default"
)
selected_period_id = (
    periods_dict[selected_period_name]
    if selected_period_name in periods_dict
    else ""
)

# ==========================================
# 6. ROUTING KONDISI MENU UTAMA
# ==========================================
if selected_menu == "⚙️ Pengaturan":
  st.markdown(
      "<h2 style='color: #00f0ff; text-shadow: 0 0 10px rgba(0,240,255,0.5);'>⚙️"
      " Master Data & Pengaturan Sistem</h2>",
      unsafe_allow_html=True,
  )

  current_user = st.session_state.get("username", "visitor")
  user_lower = str(current_user).lower()
  is_admin = any(
      x in user_lower for x in ["admin", "chief", "cos", "lavitality"]
  )

  if not is_admin:
    st.error(
        "🔒 **Akses Ditolak!** Fitur Master Data & Pengaturan hanya dapat"
        " diakses oleh **Admin / COS**."
    )
    st.stop()

  tab_m1, tab_m2, tab_m3, tab_m4, tab_m5 = st.tabs([
      "➕ Penambahan Item & Target",
      "⚙️ Pengaturan Item",
      "📅 Pengaturan Periode",
      "🎯 Input & Master PPS/Sueger",
      "📊 Master Status & Summary",
  ])

  # SUB TAB 1: PENAMBAHAN ITEM & TARGET PER PERIODE
  with tab_m1:
    st.markdown(
        "<h4 style='color: #00ff88;'>➕ Tambah Produk & Target Per Periode</h4>",
        unsafe_allow_html=True,
    )
    with st.form("form_add_new_item"):
      col_add1, col_add2 = st.columns(2)
      with col_add1:
        add_period_name = st.selectbox(
            "Pilih Periode Alokasi Target",
            list(periods_dict.keys()),
            key="add_item_period",
        )
        add_period_id = periods_dict[add_period_name]

        new_item_id = (
            st.text_input(
                "ID Item (PLU / Barcode)", placeholder="Contoh: 100234"
            )
            .strip()
            .upper()
        )
        new_item_name = st.text_input(
            "Nama Produk / Item", placeholder="Contoh: MINYAK GORENG 2L"
        ).strip()

        new_category = st.text_input(
            "Kategori Produk", placeholder="Contoh: FOOD / NON-FOOD"
        ).strip()

      with col_add2:
        new_target_toko = st.number_input(
            "Target Toko (Total Pcs)", min_value=0, step=1, value=90
        )

        new_target_otomatis = (
            int(math.ceil(new_target_toko / 3)) if new_target_toko > 0 else 0
        )
        st.markdown(
            f"📦 **Target Otomatis (Target Toko / 3):**"
            f" `{new_target_otomatis} Pcs`"
        )
        new_target_kasir = new_target_otomatis

      btn_submit_add_item = st.form_submit_button(
          "💾 Simpan Produk & Target Baru", use_container_width=True
      )

      if btn_submit_add_item:
        if not new_item_id or not new_item_name:
          st.error("⚠️ ID Item dan Nama Produk wajib diisi!")
        else:
          try:
            if (
                "items_df" not in st.session_state
                or st.session_state.items_df is None
            ):
              st.session_state.items_df = pd.DataFrame(
                  columns=[
                      "period_id",
                      "item_id",
                      "item_name",
                      "active",
                      "category",
                  ]
              )

            m_items = st.session_state.items_df.copy()

            for col in [
                "period_id",
                "item_id",
                "item_name",
                "active",
                "category",
            ]:
              if col not in m_items.columns:
                m_items[col] = ""

            mask_master = (
                m_items["period_id"].astype(str) == str(add_period_id)
            ) & (m_items["item_id"].astype(str) == str(new_item_id))

            if not mask_master.any():
              new_m_row = pd.DataFrame([{
                  "period_id": str(add_period_id),
                  "item_id": str(new_item_id),
                  "item_name": str(new_item_name),
                  "active": "TRUE",
                  "category": str(new_category),
              }])
              st.session_state.items_df = pd.concat(
                  [m_items, new_m_row], ignore_index=True
              )
              save_master_table("MASTER_ITEM", st.session_state.items_df)

            if (
                "sales_item_df" not in st.session_state
                or st.session_state.sales_item_df is None
            ):
              st.session_state.sales_item_df = pd.DataFrame(
                  columns=[
                      "period_id",
                      "item_id",
                      "item_name",
                      "target_qty",
                      "target_kasir",
                      "actual_qty",
                  ]
              )

            s_items = st.session_state.sales_item_df.copy()
            mask_sales = (
                s_items["period_id"].astype(str) == str(add_period_id)
            ) & (s_items["item_id"].astype(str) == str(new_item_id))

            if mask_sales.any():
              s_items.loc[mask_sales, "item_name"] = str(new_item_name)
              s_items.loc[mask_sales, "target_qty"] = int(new_target_toko)
              s_items.loc[mask_sales, "target_kasir"] = int(new_target_kasir)
            else:
              new_si_row = pd.DataFrame([{
                  "period_id": str(add_period_id),
                  "item_id": str(new_item_id),
                  "item_name": str(new_item_name),
                  "target_qty": int(new_target_toko),
                  "target_kasir": int(new_target_kasir),
                  "actual_qty": 0,
              }])
              s_items = pd.concat([s_items, new_si_row], ignore_index=True)

            st.session_state.sales_item_df = s_items

            save_database(
                st.session_state.sales_item_df,
                st.session_state.sales_person_df,
                st.session_state.sales_pps_df,
                st.session_state.sales_store_df,
            )

            st.toast(f"✅ Produk {new_item_name} berhasil disimpan!", icon="🎉")
            time.sleep(1.5)
            st.rerun()
          except Exception as e:
            st.error(f"❌ Gagal menambahkan produk: {e}")

  # SUB TAB 2: PENGATURAN ITEM (PSM)
  with tab_m2:
    st.markdown(
        "<h4 style='color: #38bdf8;'>⚙️ Pengaturan, Edit & Hapus Item</h4>",
        unsafe_allow_html=True,
    )
    si_df = st.session_state.sales_item_df.copy()
    if si_df.empty:
      st.info("Belum ada data item terdaftar.")
    else:
      m_p_name = st.selectbox(
          "Pilih Periode Item",
          list(periods_dict.keys()),
          key="setting_item_period",
      )
      m_p_id = periods_dict[m_p_name]
      si_sub = si_df[si_df["period_id"] == m_p_id]

      if si_sub.empty:
        st.warning("Tidak ada item di periode ini.")
      else:
        selected_item_name = st.selectbox(
            "Pilih Item yang Ingin Diatur",
            si_sub["item_name"].unique(),
            key="setting_item_select",
        )
        curr_row = si_sub[si_sub["item_name"] == selected_item_name].iloc[0]

        with st.form("form_edit_item"):
          col_e1, col_e2 = st.columns(2)
          with col_e1:
            edit_item_name = st.text_input(
                "Nama Item / Produk", value=str(curr_row["item_name"])
            )
            target_toko_val = int(curr_row.get("target_qty", 0))
            edit_target_toko = st.number_input(
                "Target Toko", min_value=0, step=1, value=target_toko_val
            )
          with col_e2:
            target_kasir_val = int(curr_row.get("target_kasir", 0))
            edit_target_kasir = st.number_input(
                "Target Kasir / Staf",
                min_value=0,
                step=1,
                value=target_kasir_val,
            )
            edit_period_dest = st.selectbox(
                "Pindah ke Periode",
                list(periods_dict.keys()),
                index=list(periods_dict.keys()).index(m_p_name),
            )

          btn_save_item_setting = st.form_submit_button(
              "💾 Simpan Perubahan Item", use_container_width=True
          )

        if btn_save_item_setting:
          try:
            target_p_id = periods_dict[edit_period_dest]
            idx_list = st.session_state.sales_item_df[
                (st.session_state.sales_item_df["period_id"] == m_p_id)
                & (
                    st.session_state.sales_item_df["item_id"]
                    == str(curr_row["item_id"])
                )
            ].index

            st.session_state.sales_item_df.loc[
                idx_list, "item_name"
            ] = edit_item_name
            st.session_state.sales_item_df.loc[
                idx_list, "target_qty"
            ] = edit_target_toko
            st.session_state.sales_item_df.loc[
                idx_list, "target_kasir"
            ] = edit_target_kasir
            st.session_state.sales_item_df.loc[
                idx_list, "period_id"
            ] = target_p_id

            sp_idx = st.session_state.sales_person_df[
                st.session_state.sales_person_df["item_id"]
                == str(curr_row["item_id"])
            ].index
            st.session_state.sales_person_df.loc[
                sp_idx, "item_name"
            ] = edit_item_name

            save_database(
                st.session_state.sales_item_df,
                st.session_state.sales_person_df,
                st.session_state.sales_pps_df,
                st.session_state.sales_store_df,
            )
            st.toast("✅ Perubahan item berhasil disimpan!", icon="💾")
            time.sleep(1.5)
            st.rerun()
          except Exception as e:
            st.error(f"❌ Gagal memperbarui item: {e}")

        st.markdown("---")
        if st.button(
            f"🗑️ Hapus Item '{selected_item_name}' dari Periode Ini",
            use_container_width=True,
        ):
          st.session_state.sales_item_df = st.session_state.sales_item_df[
              ~(
                  (st.session_state.sales_item_df["period_id"] == m_p_id)
                  & (
                      st.session_state.sales_item_df["item_id"]
                      == str(curr_row["item_id"])
                  )
              )
          ]
          save_database(
              st.session_state.sales_item_df,
              st.session_state.sales_person_df,
              st.session_state.sales_pps_df,
              st.session_state.sales_store_df,
          )
          st.toast("⚠️ Item berhasil dihapus dari periode.", icon="🗑️")
          time.sleep(1.5)
          st.rerun()

  # SUB TAB 3: PENGATURAN PERIODE (PSM)
  with tab_m3:
    st.markdown(
        "<h4 style='color: #f59e0b;'>📅 Pengaturan Periode Promosi</h4>",
        unsafe_allow_html=True,
    )
    p_df = st.session_state.periods_df.copy()
    col_p1, col_p2 = st.columns([1, 1.2])

    with col_p1:
      st.markdown("##### ➕ Tambah Periode Baru")
      with st.form("form_add_period"):
        new_p_id = (
            st.text_input("ID Periode", placeholder="Contoh: P03")
            .strip()
            .upper()
        )
        new_p_name = st.text_input(
            "Nama Periode", placeholder="Contoh: Periode Maret 2026"
        ).strip()
        new_p_start = st.date_input(
            "Tanggal Mulai", value=waktu_wib.date(), key="add_p_start"
        )
        new_p_end = st.date_input(
            "Tanggal Selesai", value=waktu_wib.date(), key="add_p_end"
        )

        btn_add_p = st.form_submit_button(
            "💾 Tambah Periode Baru", use_container_width=True
        )

        if btn_add_p:
          if not new_p_id or not new_p_name:
            st.error("⚠️ ID dan Nama Periode wajib diisi!")
          elif new_p_start > new_p_end:
            st.error("⚠️ Tanggal Mulai tidak boleh melebihi Tanggal Selesai!")
          else:
            new_p_row = pd.DataFrame([{
                "period_id": new_p_id,
                "period_name": new_p_name,
                "start_date": str(new_p_start),
                "end_date": str(new_p_end),
            }])
            st.session_state.periods_df = pd.concat(
                [p_df, new_p_row], ignore_index=True
            )
            save_master_table("PERIODE", st.session_state.periods_df)
            st.toast(f"✅ Periode {new_p_name} berhasil ditambahkan!", icon="🎉")
            time.sleep(1.5)
            st.rerun()

    with col_p2:
      st.markdown("##### ✏️ Edit & Hapus Periode")
      if not p_df.empty:
        sel_p_edit = st.selectbox(
            "Pilih Periode yang Ingin Diubah",
            p_df["period_name"].tolist(),
            key="select_p_edit",
        )
        p_row_match = p_df[p_df["period_name"] == sel_p_edit].iloc[0]

        with st.form("form_edit_period"):
          edit_p_name = st.text_input(
              "Nama Periode", value=str(p_row_match["period_name"])
          )
          try:
            curr_start_d = pd.to_datetime(p_row_match["start_date"]).date()
            curr_end_d = pd.to_datetime(p_row_match["end_date"]).date()
          except Exception:
            curr_start_d, curr_end_d = (
                waktu_wib.date(),
                waktu_wib.date(),
            )

          edit_p_start = st.date_input(
              "Tanggal Mulai", value=curr_start_d, key="edit_p_start"
          )
          edit_p_end = st.date_input(
              "Tanggal Selesai", value=curr_end_d, key="edit_p_end"
          )

          btn_save_p_edit = st.form_submit_button(
              "💾 Update Tanggal & Nama Periode", use_container_width=True
          )

        if btn_save_p_edit:
          idx_p = st.session_state.periods_df[
              st.session_state.periods_df["period_id"]
              == str(p_row_match["period_id"])
          ].index
          st.session_state.periods_df.loc[idx_p, "period_name"] = edit_p_name
          st.session_state.periods_df.loc[idx_p, "start_date"] = str(
              edit_p_start
          )
          st.session_state.periods_df.loc[idx_p, "end_date"] = str(edit_p_end)

          save_master_table("PERIODE", st.session_state.periods_df)
          st.toast("✅ Periode berhasil diperbarui!", icon="💾")
          time.sleep(1.5)
          st.rerun()

  # SUB TAB 4: INPUT & PENGATURAN PERIODE PPS & SUEGER
  with tab_m4:
    st.markdown(
        "<h4 style='color: #c084fc;'>🎯 Input & Pengaturan Periode PPS &"
        " Sueger</h4>",
        unsafe_allow_html=True,
    )

    if "periode_pps_df" not in st.session_state:
      st.session_state.periode_pps_df = pd.DataFrame(columns=[
          "period_id",
          "start_date",
          "end_date",
          "period_name",
          "target_total",
          "status",
          "actual_qty",
      ])

    sub_sue, sub_pps, sub_edit, sub_mon = st.tabs([
        "➕ Tambah Sueger",
        "➕ Tambah Periode PPS",
        "✏️ Edit & Hapus Program",
        "📊 Monitoring Periode",
    ])

    with sub_sue:
      st.markdown("##### 📌 Form Input Program Sueger (Persentase)")
      with st.form("form_add_sueger_pure_only"):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
          sgr_id = (
              st.text_input(
                  "ID Periode Sueger", placeholder="Contoh: SGR01"
              )
              .strip()
              .upper()
          )
          sgr_name = st.text_input(
              "Nama Program Sueger", placeholder="Contoh: SUEGER MARET"
          ).strip()
        with col_s2:
          sgr_start = st.date_input(
              "Tanggal Mulai", value=waktu_wib.date(), key="sgr_start_only"
          )
          sgr_end = st.date_input(
              "Tanggal Akhir", value=waktu_wib.date(), key="sgr_end_only"
          )

        st.info(
            "ℹ️ Program **Sueger** menggunakan persentase (target_total = 0)"
            " dan hanya disimpan ke sheet `PERIODE_PPS`."
        )

        btn_submit_sgr = st.form_submit_button(
            "💾 Simpan Program Sueger", use_container_width=True
        )

        if btn_submit_sgr:
          if not sgr_id or not sgr_name:
            st.error("⚠️ ID Periode dan Nama Program wajib diisi!")
          elif sgr_start > sgr_end:
            st.error("⚠️ Tanggal mulai tidak boleh melebihi tanggal akhir!")
          else:
            try:
              new_sgr_row = pd.DataFrame([{
                  "period_id": sgr_id,
                  "start_date": str(sgr_start),
                  "end_date": str(sgr_end),
                  "period_name": sgr_name,
                  "target_total": 0,
                  "status": "Aktif",
                  "actual_qty": 0,
              }])

              st.session_state.periode_pps_df = pd.concat(
                  [st.session_state.periode_pps_df, new_sgr_row],
                  ignore_index=True,
              )
              save_master_table("PERIODE_PPS", st.session_state.periode_pps_df)

              st.toast(
                  "✅ Program Sueger berhasil disimpan ke PERIODE_PPS!",
                  icon="🎉",
              )
              time.sleep(1.2)
              st.rerun()
            except Exception as e:
              st.error(f"❌ Gagal menyimpan program Sueger: {e}")

    with sub_pps:
      st.markdown(
          "##### 📌 Form Input Periode PPS (Target Fisik & Pembulatan Otomatis)"
      )
      with st.form("form_add_pps_pure_only"):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
          pps_id = (
              st.text_input("ID Periode PPS", placeholder="Contoh: PPS01")
              .strip()
              .upper()
          )
          pps_name = st.text_input(
              "Nama Periode PPS", placeholder="Contoh: PPS MARET"
          ).strip()
          pps_target = st.number_input(
              "Target Total (Pcs)", min_value=0, step=1, value=180
          )
        with col_p2:
          pps_start = st.date_input(
              "Tanggal Mulai", value=waktu_wib.date(), key="pps_start_only"
          )
          pps_end = st.date_input(
              "Tanggal Akhir", value=waktu_wib.date(), key="pps_end_only"
          )

          pps_target_kasir_auto = (
              int(math.ceil(pps_target / 9)) if pps_target > 0 else 0
          )
          st.markdown(
              f"👤 **Target Otomatis Per Personil (Target Total / 9):**"
              f" `{pps_target_kasir_auto} Pcs`"
          )
          st.caption(
              "*(Nilai desimal dibulatkan ke atas secara otomatis dan disimpan"
              " ke PERIODE_PPS)*"
          )

        btn_submit_pps_exc = st.form_submit_button(
            "💾 Simpan Periode PPS", use_container_width=True
        )

        if btn_submit_pps_exc:
          if not pps_id or not pps_name:
            st.error("⚠️ ID Periode dan Nama Periode wajib diisi!")
          elif pps_start > pps_end:
            st.error("⚠️ Tanggal mulai tidak boleh melebihi tanggal akhir!")
          else:
            try:
              new_pps_row = pd.DataFrame([{
                  "period_id": pps_id,
                  "start_date": str(pps_start),
                  "end_date": str(pps_end),
                  "period_name": pps_name,
                  "target_total": int(pps_target),
                  "status": "Aktif",
                  "actual_qty": 0,
              }])

              st.session_state.periode_pps_df = pd.concat(
                  [st.session_state.periode_pps_df, new_pps_row],
                  ignore_index=True,
              )
              save_master_table("PERIODE_PPS", st.session_state.periode_pps_df)

              st.toast(
                  "✅ Periode PPS berhasil disimpan ke PERIODE_PPS!", icon="🎉"
              )
              time.sleep(1.2)
              st.rerun()
            except Exception as e:
              st.error(f"❌ Gagal menyimpan Periode PPS: {e}")

    with sub_edit:
      st.markdown("##### ✏️ Kelola / Edit & Hapus Program PERIODE_PPS")
      edit_df = st.session_state.periode_pps_df.copy()

      if (
          edit_df.empty
          or "period_id" not in edit_df.columns
          or edit_df["period_id"].dropna().empty
      ):
        st.info(
            "Belum ada data di tabel PERIODE_PPS yang tersimpan untuk diedit."
        )
      else:
        edit_df["period_id"] = edit_df["period_id"].astype(str).str.strip()
        edit_df["period_name"] = edit_df["period_name"].astype(str).str.strip()
        valid_edit_df = edit_df[edit_df["period_id"] != ""]

        if valid_edit_df.empty:
          st.info("Tidak ada ID Program valid.")
        else:
          list_options = (
              valid_edit_df["period_id"]
              + " - "
              + valid_edit_df["period_name"]
          ).tolist()

          if len(list_options) > 0:
            selected_opt = st.selectbox(
                "Pilih Program untuk Diedit/Dihapus",
                list_options,
                key="pure_edit_selectbox_only",
            )
            selected_id = (
                str(selected_opt).split(" - ")[0].strip()
                if selected_opt
                else None
            )

            if (
                selected_id
                and selected_id in valid_edit_df["period_id"].values
            ):
              matched = valid_edit_df[
                  valid_edit_df["period_id"] == selected_id
              ]

              if not matched.empty:
                rmatch = matched.iloc[0]

                with st.form("form_edit_pure_only_prog"):
                  col_e1, col_e2 = st.columns(2)
                  with col_e1:
                    edit_name = st.text_input(
                        "Nama Program", value=str(rmatch.get("period_name", ""))
                    )
                    try:
                      cs = pd.to_datetime(rmatch["start_date"]).date()
                      ce = pd.to_datetime(rmatch["end_date"]).date()
                    except Exception:
                      cs, ce = waktu_wib.date(), waktu_wib.date()

                    edit_s = st.date_input("Tanggal Mulai", value=cs)
                  with col_e2:
                    edit_e = st.date_input("Tanggal Akhir", value=ce)
                    edit_t = st.number_input(
                        "Target Total (Pcs)",
                        min_value=0,
                        step=1,
                        value=int(rmatch.get("target_total", 0)),
                    )

                    c_status = str(rmatch.get("status", "Aktif"))
                    idx_s = (
                        ["Aktif", "Non-Aktif", "Selesai"].index(c_status)
                        if c_status in ["Aktif", "Non-Aktif", "Selesai"]
                        else 0
                    )
                    edit_st = st.selectbox(
                        "Status",
                        ["Aktif", "Non-Aktif", "Selesai"],
                        index=idx_s,
                    )

                  btn_upd = st.form_submit_button(
                      "💾 Simpan Perubahan ke PERIODE_PPS",
                      use_container_width=True,
                  )

                  if btn_upd:
                    try:
                      idx_t = st.session_state.periode_pps_df[
                          st.session_state.periode_pps_df["period_id"].astype(
                              str
                          )
                          == str(selected_id)
                      ].index

                      st.session_state.periode_pps_df.loc[
                          idx_t, "period_name"
                      ] = edit_name
                      st.session_state.periode_pps_df.loc[
                          idx_t, "start_date"
                      ] = str(edit_s)
                      st.session_state.periode_pps_df.loc[
                          idx_t, "end_date"
                      ] = str(edit_e)
                      st.session_state.periode_pps_df.loc[
                          idx_t, "target_total"
                      ] = int(edit_t)
                      st.session_state.periode_pps_df.loc[
                          idx_t, "status"
                      ] = edit_st

                      save_master_table(
                          "PERIODE_PPS", st.session_state.periode_pps_df
                      )

                      st.toast(
                          "✅ Perubahan berhasil disimpan ke PERIODE_PPS!",
                          icon="💾",
                      )
                      time.sleep(1.2)
                      st.rerun()
                    except Exception as e:
                      st.error(f"❌ Gagal memperbarui: {e}")

                st.markdown("---")
                if st.button(
                    f"🗑️ Hapus Program ID: {selected_id}",
                    use_container_width=True,
                    key="pure_btn_del_only",
                ):
                  st.session_state.periode_pps_df = st.session_state[
                      "periode_pps_df"
                  ][
                      st.session_state.periode_pps_df["period_id"].astype(
                          str
                      )
                      != str(selected_id)
                  ]
                  save_master_table(
                      "PERIODE_PPS", st.session_state.periode_pps_df
                  )

                  st.toast(
                      "⚠️ Program berhasil dihapus dari PERIODE_PPS.",
                      icon="🗑️",
                  )
                  time.sleep(1.2)
                  st.rerun()

    with sub_mon:
      st.markdown("##### 📊 Monitoring Data PERIODE_PPS")
      if not st.session_state.periode_pps_df.empty:
        st.dataframe(st.session_state.periode_pps_df, use_container_width=True)
      else:
        st.info("Belum ada data periode yang tercatat di tabel `PERIODE_PPS`.")

  # SUB TAB 5: MASTER STATUS & SUMMARY (PSM)
  with tab_m5:
    st.markdown(
        "<h4 style='color: #00ff88;'>📊 Status Sistem & Summary Laporan</h4>",
        unsafe_allow_html=True,
    )

    c_s1, c_s2, c_s3 = st.columns(3)
    with c_s1:
      st.metric("🔗 Koneksi Database", "Terhubung (GSheets)")
    with c_s2:
      st.metric(
          "📦 Total Master Item", f"{len(st.session_state.items_df)} Item"
      )
    with c_s3:
      st.metric(
          "👥 Total Personil", f"{len(st.session_state.person_df)} Staf"
      )

    st.markdown("---")
    st.subheader("📋 Summary Laporan Penjualan")

    mode_summary = st.radio(
        "Pilih Jenis Laporan Summary:",
        ["Harian (Hari Ini)", "Per Periode (Aktif)", "Bulanan (Bulan Ini)"],
        horizontal=True,
    )

    sp_data = st.session_state.sales_person_df.copy()
    if not sp_data.empty and "actual_qty" in sp_data.columns:
      sp_data["actual_qty"] = pd.to_numeric(
          sp_data["actual_qty"], errors="coerce"
      ).fillna(0)
    else:
      sp_data["actual_qty"] = 0

    today_str = waktu_wib.strftime("%Y-%m-%d")
    current_month_str = waktu_wib.strftime("%Y-%m")

    if mode_summary == "Harian (Hari Ini)":
      if "updated_at" in sp_data.columns:
        filtered_sum = sp_data[
            sp_data["updated_at"].astype(str) == today_str
        ]
      else:
        filtered_sum = pd.DataFrame()
      title_sum = f"Laporan Harian ({waktu_wib.strftime('%d %B %Y')})"
    elif mode_summary == "Per Periode (Aktif)":
      if selected_period_id:
        filtered_sum = sp_data[sp_data["period_id"] == selected_period_id]
        title_sum = f"Laporan Periode ({selected_period_name})"
      else:
        filtered_sum = sp_data.copy()
        title_sum = "Laporan Semua Periode"
    else:
      if "updated_at" in sp_data.columns:
        filtered_sum = sp_data[
            sp_data["updated_at"].astype(str).str.startswith(current_month_str)
        ]
      else:
        filtered_sum = pd.DataFrame()
      title_sum = f"Laporan Bulanan ({waktu_wib.strftime('%B %Y')})"

    tot_actual_sum = filtered_sum["actual_qty"].sum()
    st.markdown(
        f"##### 📌 {title_sum} — Total Sales: **{tot_actual_sum:,.0f} Pcs**"
    )

    sum_item = (
        filtered_sum.groupby("item_name")["actual_qty"]
        .sum()
        .reset_index()
        .sort_values(by="actual_qty", ascending=False)
    )
    st.dataframe(sum_item, use_container_width=True)

    st.markdown("---")
    st.subheader("📲 Salin Laporan Format WhatsApp")
    wa_report_text = "*📊 REPORT PSM TOKO C383*\n"
    wa_report_text += f"*Jenis Laporan:* {title_sum}\n"
    wa_report_text += f"*Waktu Update:* {current_time_str}\n"
    wa_report_text += (
        f"--------------------------------------------------\n"
    )

    for idx, r in sum_item.iterrows():
      wa_report_text += (
          f"• *{r['item_name']}*: {int(r['actual_qty']):,} Pcs\n"
      )

    wa_report_text += (
        f"--------------------------------------------------\n"
    )
    wa_report_text += f"*TOTAL SALES:* *{int(tot_actual_sum):,} Pcs*\n\n"
    wa_report_text += f"_Laporan dihasilkan otomatis oleh System Sales PSM_"

    st.code(wa_report_text, language="markdown")
    st.caption(
        "💡 Klik tombol salin/copy di pojok kanan atas kotak kode di atas"
        " untuk menempelkannya langsung ke WhatsApp!"
    )

    st.markdown("---")
    st.subheader("📥 Export & Download Laporan")
    csv_data = sum_item.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📄 Download Laporan Data (CSV)",
        data=csv_data,
        file_name=f"Report_PSM_{mode_summary.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

else:
  st.markdown(
      f"<h2>🏠 Menu {selected_menu}</h2><p>Halaman sedang dipersiapkan atau"
      " diarahkan dari navigasi sidebar.</p>",
      unsafe_allow_html=True,
  )
