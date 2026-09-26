import streamlit as st
import random
import time

# 1. Konfigurasi Halaman & Gaya Tampilan (JRPG Retro Style)
st.set_page_config(page_title="Streamlit 1v1 JRPG Battle", layout="centered")

# CSS Kustom untuk membuat efek berkedip (flash) saat menyerang dan merubah tampilan log
st.markdown("""
<style>
    .battle-log-text { font-family: 'Courier New', Courier, monospace; font-size: 14px; }
    @keyframes flash {
        0% { opacity: 1; }
        50% { opacity: 0; }
        100% { opacity: 1; }
    }
    .hit-flash { animation: flash 0.2s ease-in-out 2; }
</style>
""", unsafe_allow_html=True)

st.title("⚔️ JRPG Project: Arena Takdir (VS Computer)")

# URL Karakter Sementara (Pixel Art Retro)
URL_HERO = "https://itch.zone" # Contoh sprite Ksatria
URL_DEMON = "https://itch.zone" # Contoh sprite Raja Iblis

# 2. Inisialisasi State Game
if "game_initialized" not in st.session_state:
    st.session_state.player = {
        "nama": "Pahlawan (Anda)", "hp": 100, "max_hp": 100,
        "mp": 30, "max_mp": 30, "atk": 16, "def": 5,
        "buff_atk": 0, "is_defending": False
    }
    st.session_state.enemy = {
        "nama": "Raja Iblis (AI)", "hp": 130, "max_hp": 130,
        "atk": 14, "def": 4, "is_defending": False
    }
    st.session_state.battle_log = ["⚔️ Pertarungan dimulai! Pilih aksi Anda di menu bawah."]
    st.session_state.game_over = False
    st.session_state.flash_target = None # Untuk mendeteksi siapa yang terkena efek serang/flash
    st.session_state.game_initialized = True

player = st.session_state.player
enemy = st.session_state.enemy

# 3. Logika Otomatis / Giliran AI (VS Computer)
def eksekusi_giliran_musuh():
    if enemy["hp"] <= 0:
        return
    
    # AI Memilih aksi secara cerdas (75% Serang, 25% Bertahan)
    pilihan_ai = random.choice(["serang", "serang", "serang", "bertahan"])
    
    if pilihan_ai == "serang":
        # Efek visual serang ke Pemain
        st.session_state.flash_target = "player"
        
        # Hitung kalkulasi damage
        damage_base = enemy["atk"] - (player["def"] * 2.5 if player["is_defending"] else player["def"])
        damage = max(4, int(damage_base + random.randint(-2, 2)))
        player["hp"] = max(0, player["hp"] - damage)
        
        log = f"💥 **{enemy['nama']}** melancarkan tebasan kegelapan sebesar **{damage} DMG** ke Anda!"
        if player["is_defending"]:
            log += " *(Berhasil diredam oleh shield Anda)*"
        st.session_state.battle_log.append(log)
        
    elif pilihan_ai == "bertahan":
        enemy["is_defending"] = True
        st.session_state.battle_log.append(f"🛡️ **{enemy['nama']}** mengambil kuda-kuda bertahan! DEF meningkat.")

    # Reset pertahanan pemain di akhir putaran giliran musuh
    player["is_defending"] = False

# 4. TAMPILAN KARAKTER & STATUS (Desain Layout Grafis JRPG)
col_player, col_enemy = st.columns(2)

with col_player:
    st.subheader(f"🧑‍🎤 {player['nama']}")
    # Terapkan efek flash jika player diserang
    if st.session_state.flash_target == "player":
        st.markdown(f'<div class="hit-flash"><img src="{URL_HERO}" width="180"></div>', unsafe_allow_html=True)
    else:
        st.image(URL_HERO, width=180)
        
    # Bar Status Mekanik
    st.progress(player["hp"] / player["max_hp"], text=f"HP: {player['hp']} / {player['max_hp']}")
    st.progress(player["mp"] / player["max_mp"], text=f"MP: {player['mp']} / {player['max_mp']}")
    
    # Notifikasi Efek Status
    if player["buff_atk"] > 0:
        st.info(f"✨ Buff ATK aktif ({player['buff_atk']} giliran lagi)")
    if player["is_defending"]:
        st.warning("🛡️ Sedang bersiap bertahan")

with col_enemy:
    st.subheader(f"😈 {enemy['nama']}")
    # Terapkan efek flash jika enemy diserang
    if st.session_state.flash_target == "enemy":
        st.markdown(f'<div class="hit-flash"><img src="{URL_DEMON}" width="180"></div>', unsafe_allow_html=True)
    else:
        st.image(URL_DEMON, width=180)
        
    # Bar Status Mekanik Musuh
    st.progress(enemy["hp"] / enemy["max_hp"], text=f"HP: {enemy['hp']} / {enemy['max_hp']}")
    st.write("") # Penyeimbang bar MP pemain
    
    if enemy["is_defending"]:
        st.warning("🛡️ Sedang bersiap bertahan")

# Reset target efek flash agar tidak berkedip selamanya saat halaman dimuat ulang
st.session_state.flash_target = None

st.markdown("---")

# 5. AREA LOG PERTANDINGAN (Papan Teks Aksi JRPG)
st.write("📜 **Log Aksi Pertarungan:**")
with st.container(border=True):
    # Menampilkan 4 baris log pertarungan terakhir
    for log in st.session_state.battle_log[-4:]:
        st.markdown(f'<p class="battle-log-text">{log}</p>', unsafe_allow_html=True)

st.markdown("---")

# 6. MENU PERINTAH (Sistem Giliran Pemain)
st.write("🎮 **Menu Perintah Anda:**")

# Validasi Akhir Game (Menang / Kalah)
if player["hp"] <= 0:
    st.error("💀 GAME OVER! Anda dikalahkan oleh Raja Iblis. Dunia jatuh ke dalam kegelapan...")
    st.session_state.game_over = True
elif enemy["hp"] <= 0:
    st.success("🎉 VICTORY! Anda berhasil menumbangkan Raja Iblis dan menyelamatkan kerajaan!")
    st.session_state.game_over = True

# Tampilkan tombol menu aksi jika pertarungan masih berlangsung
if not st.session_state.game_over:
    btn_serang, btn_bertahan, btn_buff, btn_selesai = st.columns(4)
    
    with btn_serang:
        if st.button("⚔️ Serang", use_container_width=True, type="primary"):
            # Reset status pertahanan musuh dari giliran sebelumnya
            enemy["is_defending"] = False
            st.session_state.flash_target = "enemy"
            
            # Hitung kalkulasi serangan pahlawan
            total_atk = player["atk"] + (6 if player["buff_atk"] > 0 else 0)
            damage_base = total_atk - (enemy["def"] * 2 if enemy["is_defending"] else enemy["def"])
            damage = max(5, int(damage_base + random.randint(-3, 3)))
            enemy["hp"] = max(0, enemy["hp"] - damage)
            
            st.session_state.battle_log.append(f"⚔️ **Anda** menebas {enemy['nama']} senilai **{damage} DMG**!")
            
            # Update durasi buff
            if player["buff_atk"] > 0:
                player["buff_atk"] -= 1
            
            # Giliran Komputer membalas
            eksekusi_giliran_musuh()
            st.rerun()

    with btn_bertahan:
        if st.button("🛡️ Bertahan", use_container_width=True):
            player["is_defending"] = True
            st.session_state.battle_log.append("🛡️ Anda memasang posisi bertahan! DMG musuh berikutnya dikurangi drastis.")
            
            if player["buff_atk"] > 0:
                player["buff_atk"] -= 1
                
            eksekusi_giliran_musuh()
            st.rerun()

    with btn_buff:
        bisa_cast = player["mp"] >= 10
        if st.button("✨ Buff (10 MP)", use_container_width=True, disabled=not bisa_cast):
            player["mp"] -= 10
            player["buff_atk"] = 3
            st.session_state.battle_log.append("✨ Anda mengucapkan mantra! Daya serang meningkat **(+6 ATK)** selama 3 giliran.")
            
            eksekusi_giliran_musuh()
            st.rerun()

    with btn_selesai:
        if st.button("🏳️ Selesai", use_container_width=True):
            st.session_state.battle_log.append("🏳️ Anda memutuskan melarikan diri dari pertarungan...")
            player["hp"] = 0
            st.rerun()

# Tombol Reset ketika Game Selesai
else:
    if st.button("🔄 Tantang Lagi (Reset Pertandingan)", use_container_width=True):
        del st.session_state.game_initialized
        st.rerun()
