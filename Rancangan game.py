import streamlit as st
import random

# 1. Konfigurasi Halaman & Gaya Visual FGO Combo
st.set_page_config(page_title="FGO Combo Prototype", layout="centered")

st.markdown("""
<style>
    .card-box { 
        border: 2px solid #555; border-radius: 8px; padding: 10px; text-align: center; font-weight: bold; font-size: 14px;
    }
    .buster-box { border-color: #FF4B4B; background-color: rgba(255,75,75,0.1); color: #FF4B4B; }
    .arts-box { border-color: #1C83E1; background-color: rgba(28,131,225,0.1); color: #1C83E1; }
    .quick-box { border-color: #09AB3B; background-color: rgba(9,171,59,0.1); color: #09AB3B; }
    
    .slot-empty { border: 2px dashed #aaa; border-radius: 8px; height: 40px; text-align: center; line-height: 40px; color: #aaa; }
    .slot-filled { border: 2px solid #FFD700; background-color: rgba(255,215,0,0.1); border-radius: 8px; height: 40px; text-align: center; line-height: 40px; font-weight: bold; }
    
    @keyframes flash { 0% { opacity: 1; } 50% { opacity: 0; } 100% { opacity: 1; } }
    .hit-flash { animation: flash 0.15s ease-in-out 2; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ FGO Project: Combo Chain System")

URL_SERVANT = "https://itch.zone"
URL_BOSS = "https://itch.zone"

# 2. Fungsi Pembantu
def acak_5_kartu():
    return [random.choice(["Buster", "Arts", "Quick"]) for _ in range(5)]

# 3. Inisialisasi State Game
if "combo_game_initialized" not in st.session_state:
    st.session_state.servant = {"nama": "Mash / Saber", "hp": 150, "max_hp": 150, "np": 0, "max_np": 100, "atk": 22}
    st.session_state.boss = {"nama": "Goetia (AI Boss)", "hp": 350, "max_hp": 350, "atk": 20}
    st.session_state.kartu_tersedia = acak_5_kartu()
    st.session_state.antrean_combo = []  # Menyimpan combo yang sedang disusun (Maks 3)
    st.session_state.indeks_terpakai = [] # Menyimpan indeks kartu yang sudah diklik agar tidak bisa diklik lagi
    st.session_state.battle_log = ["⚔️ Susun 3 kartu combo Anda, lalu tekan tombol Serang!"]
    st.session_state.game_over = False
    st.session_state.flash_target = None
    st.session_state.combo_game_initialized = True

servant = st.session_state.servant
boss = st.session_state.boss

# 4. Logika Eksekusi Combo Berurutan (Sequential Turn Execution)
def eksekusi_seluruh_serangan():
    log_turn = []
    combo = st.session_state.antrean_combo
    
    log_turn.append("🎬 --- **FASE SERANGAN ANDA DIMULAI** ---")
    st.session_state.flash_target = "boss"
    
    # Cek Chain Bonus
    is_chain = len(set(combo)) == 1
    if is_chain:
        log_turn.append(f"🔥 **{combo[0]} Chain Sukses!** Semua kartu mendapatkan bonus efisiensi!")

    # Jalankan combo kartu secara berurutan (1 demi 1)
    for i, tipe in enumerate(combo):
        urutan_multiplier = 1.0 + (i * 0.25) # Kartu ke-2 dan ke-3 jauh lebih kuat
        
        if tipe == "Buster":
            mult = 2.2 if is_chain else 1.6
            dmg = int(servant["atk"] * mult * urutan_multiplier + random.randint(-2, 2))
            boss["hp"] = max(0, boss["hp"] - dmg)
            log_turn.append(f"💥 *Serangan {i+1}* -> **[Buster]** menghantam musuh sebesar **{dmg} DMG**!")
            
        elif tipe == "Arts":
            mult = 1.0
            dmg = int(servant["atk"] * mult * urutan_multiplier)
            np_gain = 40 if is_chain else 25
            boss["hp"] = max(0, boss["hp"] - dmg)
            servant["np"] = min(servant["max_np"], servant["np"] + np_gain)
            log_turn.append(f"🔮 *Serangan {i+1}* -> **[Arts]** memberikan {dmg} DMG & mengisi **+{np_gain}% NP Gauge**!")
            
        elif tipe == "Quick":
            mult = 0.9
            dmg = int(servant["atk"] * mult * urutan_multiplier)
            np_gain = 12
            boss["hp"] = max(0, boss["hp"] - dmg)
            servant["np"] = min(servant["max_np"], servant["np"] + np_gain)
            log_turn.append(f"⚡ *Serangan {i+1}* -> **[Quick]** tebasan cepat {dmg} DMG & menambah **+{np_gain}% NP Gauge**!")

    # --- FASE SERANGAN MUSUH (Hanya jika musuh masih hidup) ---
    if boss["hp"] > 0:
        log_turn.append("🎬 --- **FASE BALASAN MUSUH DIMULAI** ---")
        st.session_state.flash_target = "servant"
        
        # Musuh juga melakukan serangan berantai (2x serangan berturut-turut dalam 1 turn)
        for j in range(2):
            dmg_boss = int(boss["atk"] * random.uniform(0.8, 1.2))
            servant["hp"] = max(0, servant["hp"] - dmg_boss)
            log_turn.append(f"😈 **{boss['nama']}** melancarkan serangan ke-{j+1} sebesar **{dmg_boss} DMG**!")
            
    # Reset State untuk Turn Baru
    st.session_state.battle_log.extend(log_turn)
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.kartu_tersedia = acak_5_kartu()

# 5. TAMPILAN GRAFIS ARENA
col_servant, col_boss = st.columns(2)
with col_servant:
    st.subheader(f"🧑‍🚀 {servant['nama']}")
    st.markdown(f'<div class="{"hit-flash" if st.session_state.flash_target == "servant" else ""}"><img src="{URL_SERVANT}" width="160"></div>', unsafe_allow_html=True)
    st.progress(servant["hp"] / servant["max_hp"], text=f"HP: {servant['hp']} / {servant['max_hp']}")
    st.progress(servant["np"] / servant["max_np"], text=f"NP Gauge: {servant['np']}%")

with col_boss:
    st.subheader(f"😈 {boss['nama']}")
    st.markdown(f'<div class="{"hit-flash" if st.session_state.flash_target == "boss" else ""}"><img src="{URL_BOSS}" width="160"></div>', unsafe_allow_html=True)
    st.progress(boss["hp"] / boss["max_hp"], text=f"HP: {boss['hp']} / {boss['max_hp']}")

st.session_state.flash_target = None
st.markdown("---")

# 6. SLOT PANEL COMBO (Melihat kartu yang sudah Anda pilih untuk turn ini)
st.write("📥 **Rangkaian Combo Turn Ini:**")
col_slot1, col_slot2, col_slot3 = st.columns(3)
slots = [col_slot1, col_slot2, col_slot3]

for i in range(3):
    with slots[i]:
        if i < len(st.session_state.antrean_combo):
            kartu_nama = st.session_state.antrean_combo[i]
            warna_css = kartu_nama.lower()
            st.markdown(f'<div class="slot-filled {warna_css}-box">Slot {i+1}: {kartu_nama}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="slot-empty">Kosong</div>', unsafe_allow_html=True)

st.markdown("---")

# 7. LOG UTAS PERTEMPURAN
st.write("📜 **Ulasan Aksi JRPG:**")
with st.container(border=True):
    # Menampilkan 6 baris log terakhir agar rangkaian kombonya terlihat penuh
    for log in st.session_state.battle_log[-6:]:
        st.markdown(log)

st.markdown("---")

# Cek Status Akhir Game
if servant["hp"] <= 0:
    st.error("💀 Servant Anda kalah!")
    st.session_state.game_over = True
elif boss["hp"] <= 0:
    st.success("🎉 Selamat! Boss berhasil dikalahkan dengan kombo mematikan!")
    st.session_state.game_over = True

# 8. DEK TANGAN & KONTROL PEMILIHAN KARTU
if not st.session_state.game_over:
    st.write("🃏 **Pilih Kartu untuk Mengisi Slot Combo (Maksimal 3):**")
    
    # Render 5 Kartu sebagai Tombol Klik
    cols_dek = st.columns(5)
    for idx, tipe in enumerate(st.session_state.kartu_tersedia):
        with cols_dek[idx]:
            warna_css = tipe.lower()
            st.markdown(f'<div class="card-box {warna_css}-box">{tipe}</div>', unsafe_allow_html=True)
            
            # Nonaktifkan tombol jika slot penuh ATAU kartu ini sudah diklik
            sudah_diklik = idx in st.session_state.indeks_terpakai
            slot_penuh = len(st.session_state.antrean_combo) >= 3
            
            if st.button(f"Pilih #{idx+1}", key=f"btn_{idx}", disabled=(sudah_diklik or slot_penuh), use_container_width=True):
                st.session_state.antrean_combo.append(tipe)
                st.session_state.indeks_terpakai.append(idx)
                st.rerun()

    # Tombol Aksi Kontrol Utama
    btn_clear, btn_action = st.columns(2)
    with btn_clear:
        if st.button("🔄 Reset Pilihan Combo", use_container_width=True, disabled=(len(st.session_state.antrean_combo) == 0)):
            st.session_state.antrean_combo = []
            st.session_state.indeks_terpakai = []
            st.rerun()
            
    with btn_action:
        siap_serang = len(st.session_state.antrean_combo) == 3
        if st.button("⚔️ MULAI SERANG! (Execute Combo)", use_container_width=True, type="primary", disabled=not siap_serang):
            eksekusi_seluruh_serangan()
            st.rerun()
else:
    if st.button("🔄 Ulangi Pertandingan", use_container_width=True, type="primary"):
        del st.session_state.combo_game_initialized
        st.rerun()
