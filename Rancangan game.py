import streamlit as st
import random

# 1. Konfigurasi Halaman & Gaya Visual JRPG Modern
st.set_page_config(page_title="FGO Arena JRPG", layout="centered")

st.markdown("""
<style>
    /* Header Bar Darah Besar */
    .hp-header-box { background-color: #1e1e24; border: 2px solid #444; padding: 12px; border-radius: 8px; margin-bottom: 15px; }
    .hp-title { font-weight: bold; font-size: 14px; margin-bottom: 2px; }
    
    /* Panel Aksi / Notifikasi Animasi */
    .round-banner { background: linear-gradient(90deg, #FF4B4B, #FFD700); color: white; text-align: center; font-weight: bold; font-size: 18px; padding: 6px; border-radius: 4px; margin-bottom: 15px; }
    .action-bubble { background-color: #ff9800; color: white; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; display: inline-block; margin-top: 5px; }
    
    /* Desain Kartu & Slot */
    .card-box { border: 2px solid #555; border-radius: 8px; padding: 6px; text-align: center; font-weight: bold; font-size: 13px; }
    .buster-box { border-color: #FF4B4B; background-color: rgba(255,75,75,0.1); color: #FF4B4B; }
    .arts-box { border-color: #1C83E1; background-color: rgba(28,131,225,0.1); color: #1C83E1; }
    .quick-box { border-color: #09AB3B; background-color: rgba(9,171,59,0.1); color: #09AB3B; }
    
    .slot-empty { border: 1px dashed #aaa; border-radius: 6px; height: 30px; text-align: center; line-height: 30px; color: #aaa; font-size: 12px; }
    .slot-filled { border: 1px solid #FFD700; background-color: rgba(255,215,0,0.1); border-radius: 6px; height: 30px; text-align: center; line-height: 30px; font-weight: bold; font-size: 12px; }
    .predict-box { background-color: #262730; border-left: 5px solid #FF4B4B; padding: 10px; border-radius: 4px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Chaldea Arena: Layout Fight 1v1")

URL_SERVANT = "https://itch.zone"
URL_BOSS = "https://itch.zone"

def acak_5_kartu():
    return [random.choice(["Buster", "Arts", "Quick"]) for _ in range(5)]

# 2. Inisialisasi State Game
if "fgo_v4_initialized" not in st.session_state:
    st.session_state.servant = {"nama": "Mash / Saber (Anda)", "hp": 150, "max_hp": 150, "np": 0, "max_np": 100, "atk": 22}
    st.session_state.boss = {"nama": "Goetia (AI Boss)", "hp": 350, "max_hp": 350, "atk": 20}
    st.session_state.round = 1
    st.session_state.boss_last_action = "Bersiap Menyerang" 
    st.session_state.kartu_tersedia = acak_5_kartu()
    st.session_state.antrean_combo = []  
    st.session_state.indeks_terpakai = [] 
    st.session_state.battle_log = ["⚔️ Pertandingan dimulai! Susun strategi kombo Anda."]
    st.session_state.game_over = False
    st.session_state.fgo_v4_initialized = True

servant = st.session_state.servant
boss = st.session_state.boss

# 3. Fungsi Hitung Prediksi Damage
def hitung_prediksi_dmg(combo):
    total_prediksi = 0
    is_chain = len(combo) == 3 and len(set(combo)) == 1
    for i, tipe in enumerate(combo):
        urutan_multiplier = 1.0 + (i * 0.25)
        if tipe == "Buster":
            total_prediksi += int(servant["atk"] * (2.2 if is_chain else 1.6) * urutan_multiplier)
        elif tipe == "Arts":
            total_prediksi += int(servant["atk"] * 1.0 * urutan_multiplier)
        elif tipe == "Quick":
            total_prediksi += int(servant["atk"] * 0.9 * urutan_multiplier)
    return total_prediksi

# 4. Logika Eksekusi Turn & AI
def eksekusi_seluruh_serangan():
    log_turn = []
    combo = st.session_state.antrean_combo
    log_turn.append(f"🔄 --- **LAPORAN RONDE {st.session_state.round}** ---")
    is_chain = len(set(combo)) == 1

    # Serangan Player
    for i, tipe in enumerate(combo):
        urutan_multiplier = 1.0 + (i * 0.25)
        if tipe == "Buster":
            dmg = int(servant["atk"] * (2.2 if is_chain else 1.6) * urutan_multiplier + random.randint(-2, 2))
            boss["hp"] = max(0, boss["hp"] - dmg)
            log_turn.append(f"🔴 *Serangan {i+1}* [Buster]: **{dmg} DMG**")
        elif tipe == "Arts":
            dmg = int(servant["atk"] * 1.0 * urutan_multiplier)
            np_gain = 40 if is_chain else 25
            boss["hp"] = max(0, boss["hp"] - dmg)
            servant["np"] = min(servant["max_np"], servant["np"] + np_gain)
            log_turn.append(f"🔵 *Serangan {i+1}* [Arts]: {dmg} DMG (+{np_gain}% NP)")
        elif tipe == "Quick":
            dmg = int(servant["atk"] * 0.9 * urutan_multiplier)
            servant["np"] = min(servant["max_np"], servant["np"] + 12)
            boss["hp"] = max(0, boss["hp"] - dmg)
            log_turn.append(f"🟢 *Serangan {i+1}* [Quick]: {dmg} DMG (+12% NP)")

    # Perilaku & Serangan Musuh (AI)
    if boss["hp"] > 0:
        aksi_pilihan_ai = random.choice(["Tebasan Kegelapan", "Mengaum (Buff ATK)", "Kuda-Kuda Bertahan"])
        st.session_state.boss_last_action = aksi_pilihan_ai
        
        if aksi_pilihan_ai == "Tebasan Kegelapan":
            dmg_boss = int(boss["atk"] * random.uniform(0.9, 1.3))
            servant["hp"] = max(0, servant["hp"] - dmg_boss)
            log_turn.append(f"😈 **{boss['nama']}** mengeluarkan *{aksi_pilihan_ai}* sebesar **{dmg_boss} DMG**!")
        elif aksi_pilihan_ai == "Mengaum (Buff ATK)":
            boss["atk"] += 2
            log_turn.append(f"😈 **{boss['nama']}** *Mengaum*! Daya serang naik (+2 ATK)!")
        elif aksi_pilihan_ai == "Kuda-Kuda Bertahan":
            dmg_boss = int(boss["atk"] * 0.6)
            servant["hp"] = max(0, servant["hp"] - dmg_boss)
            log_turn.append(f"😈 **{boss['nama']}** mengambil posisi *Bertahan* & memberikan serangan balik kecil **{dmg_boss} DMG**.")
    else:
        st.session_state.boss_last_action = "Kalah / Tumbang"

    # Naikkan Ronde & Reset Pilihan
    st.session_state.round += 1
    st.session_state.battle_log.extend(log_turn)
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.kartu_tersedia = acak_5_kartu()
# 5. HEADER BAR DARAH (Paling Atas Layar)
st.markdown("<div class='hp-header-box'>", unsafe_allow_html=True)
col_h_boss, col_h_servant = st.columns(2)
with col_h_boss:
    st.markdown(f"<p class='hp-title'>😈 {boss['nama']}</p>", unsafe_allow_html=True)
    st.progress(boss["hp"] / boss["max_hp"], text=f"HP: {boss['hp']} / {boss['max_hp']}")
with col_h_servant:
    st.markdown(f"<p class='hp-title' style='text-align: right;'>🧑‍🚀 {servant['nama']}</p>", unsafe_allow_html=True)
    st.progress(servant["hp"] / servant["max_hp"], text=f"HP: {servant['hp']} / {servant['max_hp']}")
st.markdown("</div>", unsafe_allow_html=True)

# 6. BANNER INDIKATOR RONDE 
st.markdown(f"<div class='round-banner'>⚔️ RONDE {st.session_state.round} ⚔️</div>", unsafe_allow_html=True)

# 7. VISUAL KARAKTER: KIRI (MUSUH) vs KANAN (KITA)
col_visual_boss, col_visual_servant = st.columns(2)
with col_visual_boss:
    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    st.image(URL_BOSS, width=140)
    st.markdown(f"<span class='action-bubble'>Aksi Terakhir: {st.session_state.boss_last_action}</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col_visual_servant:
    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    st.image(URL_SERVANT, width=140)
    st.progress(servant["np"] / servant["max_np"], text=f"NP Gauge: {servant['np']}%")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# Cek Status Akhir Game
if servant["hp"] <= 0 or boss["hp"] <= 0:
    st.session_state.game_over = True

# 8. PANEL MENU PILIHAN KARTU & PREDIKSI
if not st.session_state.game_over:
    st.write("📥 **Rangkaian Combo Saat Ini:**")
    col_s1, col_s2, col_s3 = st.columns(3)
    slots = [col_s1, col_s2, col_s3]
    for i in range(3):
        with slots[i]:
            if i < len(st.session_state.antrean_combo):
                k_nama = st.session_state.antrean_combo[i]
                st.markdown(f'<div class="slot-filled {k_nama.lower()}-box">{k_nama}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="slot-empty">-</div>', unsafe_allow_html=True)

    # Prediksi Live Damage
    prediksi_dmg = hitung_prediksi_dmg(st.session_state.antrean_combo)
    sisa_hp_boss_prediksi = max(0, boss["hp"] - prediksi_dmg)
    st.markdown(f"""
    <div class="predict-box">
        📊 <b>Simulasi Efek Combo Anda:</b> Total Daya Hancur ➔ <span style='color:#FF4B4B; font-weight:bold;'>{prediksi_dmg} DMG</span> (Musuh tersisa sekitar: {sisa_hp_boss_prediksi} HP)
    </div>
    """, unsafe_allow_html=True)

    # Dek Kartu
    st.write("🃏 **Pilih Kartu Aksi:**")
    cols_dek = st.columns(5)
    for idx, tipe in enumerate(st.session_state.kartu_tersedia):
        with cols_dek[idx]:
            warna_css = tipe.lower()
            st.markdown(f'<div class="card-box {warna_css}-box">{tipe}</div>', unsafe_allow_html=True)
            sudah_diklik = idx in st.session_state.indeks_terpakai
            slot_penuh = len(st.session_state.antrean_combo) >= 3
            if st.button(f"Pilih", key=f"btn_{idx}", disabled=(sudah_diklik or slot_penuh), use_container_width=True):
                st.session_state.antrean_combo.append(tipe)
                st.session_state.indeks_terpakai.append(idx)
                st.rerun()

    # Tombol Kontrol Aksi
    st.write("")
    btn_clear, btn_action = st.columns(2)
    with btn_clear:
        if st.button("🔄 Reset Pilihan", use_container_width=True, disabled=(len(st.session_state.antrean_combo) == 0)):
            st.session_state.antrean_combo = []
            st.session_state.indeks_terpakai = []
            st.rerun()
    with btn_action:
        siap_serang = len(st.session_state.antrean_combo) == 3
        if st.button("⚔️ MULAI SERANG!", use_container_width=True, type="primary", disabled=not siap_serang):
            eksekusi_seluruh_serangan()
            st.rerun()

# JIKA GAME OVER
else:
    if servant["hp"] <= 0:
        st.error(f"💀 GAME OVER! Anda bertahan hingga Ronde {st.session_state.round - 1}.")
    else:
        st.success(f"🎉 VICTORY! Anda memenangkan pertarungan di Ronde {st.session_state.round - 1}!")
        
    if st.button("🔄 Mulai Baru (Reset Game)", use_container_width=True, type="primary"):
        del st.session_state.fgo_v4_initialized
        st.rerun()

st.markdown("---")

# 9. PANEL HISTORI DI PALING BAWAH
st.write("📜 **Catatan Riwayat Pertarungan:**")
with st.container(border=True):
    for log in st.session_state.battle_log[-4:]:
        st.markdown(log)
        
    
