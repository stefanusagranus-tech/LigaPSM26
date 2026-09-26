import streamlit as st
import random
import streamlit.components.v1 as components
from streamlit_lottie import st_lottie
import requests

st.set_page_config(page_title="FGO Arena JRPG", layout="centered", initial_sidebar_state="collapsed")

# ============================================================
# GANTI DENGAN URL GAMBAR KAMU (kosongkan kalau belum ada)
# ============================================================
URL_MASH   = ""   # contoh: "https://raw.githubusercontent.com/USER/REPO/main/assets/mash.png"
URL_GOETIA = ""   # contoh: "https://raw.githubusercontent.com/USER/REPO/main/assets/goetia.png"

# ============================================================
# BAGIAN 1: CSS GLOBAL
# ============================================================
st.markdown("""
<style>
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 720px; }

/* ============ ARENA ============ */
.arena-wrap { display: flex; gap: 10px; margin-bottom: 8px; }
.fighter {
    flex: 1;
    background: linear-gradient(180deg, #1a1a24 0%, #0f0f16 100%);
    border: 2px solid #2e2e3e;
    border-radius: 12px;
    padding: 12px 8px;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.fighter.enemy { border-color: #5a1f1f; box-shadow: 0 0 12px rgba(255,75,75,0.18); }
.fighter.ally  { border-color: #1f3a5a; box-shadow: 0 0 12px rgba(28,131,225,0.18); }

/* ============ SPRITE WRAP ============ */
.sprite-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 120px;
    margin: 6px 0;
    position: relative;
}
.sprite-img {
    max-height: 100%;
    max-width: 100%;
    object-fit: contain;
    filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
}
.sprite-emoji {
    font-size: 76px;
    line-height: 1;
    filter: drop-shadow(0 0 8px rgba(255,255,255,0.15));
}

/* ============ LOOPING: IDLE BOB ============ */
@keyframes idle-bob {
    0%,100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}
[class*="sprite-idle"] {
    animation: idle-bob 2.5s ease-in-out infinite;
}

/* ============ LOOPING: GLOW PULSE (NP penuh) ============ */
@keyframes glow-pulse {
    0%,100% { filter: drop-shadow(0 0 6px #FFD700); }
    50% { filter: drop-shadow(0 0 22px #FFD700); }
}
[class*="sprite-np"] {
    animation: idle-bob 2.5s ease-in-out infinite, glow-pulse 1.2s ease-in-out infinite;
}

/* ============ ONE-SHOT: SHAKE (kena damage) ============ */
@keyframes shake {
    0%,100% { transform: translateX(0) rotate(0deg); }
    20% { transform: translateX(-12px) rotate(-4deg); }
    40% { transform: translateX(12px) rotate(4deg); }
    60% { transform: translateX(-8px) rotate(-2deg); }
    80% { transform: translateX(8px) rotate(2deg); }
}
[class*="sprite-hit"] {
    animation: shake 0.6s ease-out !important;
}

/* ============ ONE-SHOT: LUNGE RIGHT (Player attack) ============ */
@keyframes lunge-right {
    0% { transform: translateX(0) scale(1); }
    40% { transform: translateX(60px) scale(1.25); }
    60% { transform: translateX(70px) scale(1.3); }
    100% { transform: translateX(0) scale(1); }
}
[class*="sprite-attack-right"] {
    animation: lunge-right 0.9s ease-out !important;
}

/* ============ ONE-SHOT: LUNGE LEFT (Enemy attack) ============ */
@keyframes lunge-left {
    0% { transform: translateX(0) scale(1); }
    40% { transform: translateX(-60px) scale(1.25); }
    60% { transform: translateX(-70px) scale(1.3); }
    100% { transform: translateX(0) scale(1); }
}
[class*="sprite-attack-left"] {
    animation: lunge-left 0.9s ease-out !important;
}

/* ============ ONE-SHOT: SHIELD (bertahan) ============ */
@keyframes guard-shield {
    0% { opacity: 0; transform: translate(-50%,-50%) scale(0.3); }
    25% { opacity: 1; transform: translate(-50%,-50%) scale(1.2); }
    60% { opacity: 1; transform: translate(-50%,-50%) scale(1); }
    100% { opacity: 0; transform: translate(-50%,-50%) scale(1.6); }
}
[class*="shield-overlay"] {
    position: absolute;
    top: 50%; left: 50%;
    width: 140px; height: 140px;
    border-radius: 50%;
    border: 5px solid #4da6ff;
    box-shadow: 0 0 40px #4da6ff, inset 0 0 40px rgba(77,166,255,0.6);
    animation: guard-shield 1.2s ease-out forwards;
    pointer-events: none;
    z-index: 5;
}

/* ============ ONE-SHOT: BUFF AURA (mengaum) ============ */
@keyframes buff-aura {
    0% { opacity: 0; transform: translate(-50%,-50%) scale(0.5) rotate(0deg); }
    50% { opacity: 1; transform: translate(-50%,-50%) scale(1.3) rotate(180deg); }
    100% { opacity: 0; transform: translate(-50%,-50%) scale(1.8) rotate(360deg); }
}
[class*="buff-overlay"] {
    position: absolute;
    top: 50%; left: 50%;
    width: 150px; height: 150px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(255,215,0,0.6) 0%, rgba(255,215,0,0) 70%);
    border: 3px dashed #FFD700;
    animation: buff-aura 1.2s ease-out forwards;
    pointer-events: none;
    z-index: 5;
}

/* ============ HP / NP BAR ============ */
.bar-wrap { background: #0a0a10; border: 1px solid #333; border-radius: 6px; height: 16px; overflow: hidden; margin: 3px 0; }
.bar-fill { height: 100%; transition: width 0.6s ease; border-radius: 6px 0 0 6px; }
.hp-high { background: linear-gradient(90deg, #09AB3B, #4ade80); }
.hp-mid  { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.hp-low  { background: linear-gradient(90deg, #dc2626, #ff4b4b); }
.np-fill { background: linear-gradient(90deg, #7c3aed, #c084fc); }

@keyframes np-charge {
    0% { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
}
.np-fill.ready {
    background: linear-gradient(90deg, #FFD700, #FFF8B0, #FFD700);
    background-size: 200% 100%;
    animation: np-charge 1.5s linear infinite;
}
.bar-label { font-size: 10px; color: #bbb; text-align: left; margin: 2px 0 4px 0; font-family: monospace; }

/* ============ BUBBLE ============ */
.bubble { display: inline-block; background: #ff9800; color: #111; font-weight: 700; font-size: 10px; padding: 3px 8px; border-radius: 10px; margin-top: 4px; }
.bubble.enemy { background: #ef4444; color: #fff; }

/* ============ ROUND BANNER ============ */
@keyframes shine {
    0% { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
}
.round-banner {
    background: linear-gradient(90deg, #FF4B4B, #FFD700, #FF4B4B);
    background-size: 200% 100%;
    animation: shine 3s linear infinite;
    color: #111; text-align: center; font-weight: 800; font-size: 15px;
    padding: 6px; border-radius: 8px; margin: 12px 0; letter-spacing: 2px;
}

/* ============ SLOT COMBO ============ */
.slot { border-radius: 8px; height: 34px; text-align: center; line-height: 34px; font-weight: 700; font-size: 12px; }
.slot-empty { border: 2px dashed #3a3a4a; color: #555; background: rgba(255,255,255,0.02); }
.slot-buster { border: 2px solid #FF4B4B; background: rgba(255,75,75,0.18); color: #FF4B4B; box-shadow: 0 0 8px rgba(255,75,75,0.3); }
.slot-arts   { border: 2px solid #1C83E1; background: rgba(28,131,225,0.18); color: #4da6ff; box-shadow: 0 0 8px rgba(28,131,225,0.3); }
.slot-quick  { border: 2px solid #09AB3B; background: rgba(9,171,59,0.18); color: #22d364; box-shadow: 0 0 8px rgba(9,171,59,0.3); }

/* ============ PREDIKSI ============ */
.predict { background: linear-gradient(90deg, #262730, #1a1a24); border-left: 4px solid #FFD700; padding: 8px 12px; border-radius: 6px; font-size: 12px; color: #ddd; margin: 6px 0; }

/* ============ FIX MOBILE ============ */
[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
[data-testid="stHorizontalBlock"] > div { min-width: 0 !important; }

/* ============ TOMBOL UMUM ============ */
div[data-testid="stButton"] > button {
    width: 100%; border-radius: 10px; font-weight: 700; font-size: 12px;
    padding: 10px 0; transition: transform 0.15s ease, box-shadow 0.2s ease;
}
div[data-testid="stButton"] > button:hover { transform: translateY(-2px); }

/* Tombol SERANG (primary) */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(90deg, #FF4B4B, #FFD700) !important;
    color: #111 !important;
    border: none !important;
    font-size: 15px !important;
    font-weight: 900 !important;
    letter-spacing: 1.5px !important;
    padding: 14px 0 !important;
    box-shadow: 0 0 20px rgba(255,75,75,0.5) !important;
    text-shadow: 0 1px 0 rgba(255,255,255,0.3);
}

/* ============ LOOPING: KARTU PICKABLE ============ */
@keyframes card-pulse {
    0%,100% { box-shadow: 0 0 0 rgba(255,215,0,0); }
    50% { box-shadow: 0 0 14px rgba(255,215,0,0.6); }
}
.card-pickable div[data-testid="stButton"] > button:not(:disabled) {
    animation: card-pulse 2s ease-in-out infinite;
}

/* ============ ONE-SHOT: DAMAGE POPUP ============ */
@keyframes pop-dmg {
    0% { opacity: 0; transform: translate(-50%,-30%) scale(0.4); }
    25% { opacity: 1; transform: translate(-50%,-50%) scale(1.4); }
    70% { opacity: 1; transform: translate(-50%,-60%) scale(1.1); }
    100% { opacity: 0; transform: translate(-50%,-90%) scale(1); }
}
.dmg-pop {
    position: fixed; top: 35%; left: 50%;
    font-size: 52px; font-weight: 900; color: #FF4B4B;
    text-shadow: 0 0 20px #FF4B4B, 3px 3px 0 #000;
    animation: pop-dmg 1.1s ease-out forwards;
    pointer-events: none; z-index: 9999;
}
.dmg-pop.heal { color: #4ade80; text-shadow: 0 0 20px #4ade80, 3px 3px 0 #000; }
.dmg-pop.buff { color: #FFD700; text-shadow: 0 0 20px #FFD700, 3px 3px 0 #000; }

/* Hide audio player dari st.audio kalau dipakai */
div[data-testid="stAudio"] {
    position: absolute; left: -9999px;
    width: 1px; height: 1px; opacity: 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='text-align:center; margin:0 0 8px 0; letter-spacing:1px;'>🛡️ FGO ARENA</h3>", unsafe_allow_html=True)

# ============================================================
# BAGIAN 2: SOUND (pakai components.html biar script jalan)
# ============================================================
def play_sound_beep(freq=440, duration=0.1, kind="hit"):
    if kind == "hit":
        js = f"""<script>(function(){{
            const ctx = new (window.AudioContext||window.webkitAudioContext)();
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.type='square'; osc.frequency.setValueAtTime({freq},ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime({freq*0.4},ctx.currentTime+{duration});
            gain.gain.setValueAtTime(0.15,ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+{duration});
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(); osc.stop(ctx.currentTime+{duration});
        }})();</script>"""
    elif kind == "slash":
        js = f"""<script>(function(){{
            const ctx = new (window.AudioContext||window.webkitAudioContext)();
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.type='sawtooth'; osc.frequency.setValueAtTime({freq*0.5},ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime({freq*3},ctx.currentTime+{duration});
            gain.gain.setValueAtTime(0.1,ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+{duration});
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(); osc.stop(ctx.currentTime+{duration});
        }})();</script>"""
    elif kind == "buff":
        js = f"""<script>(function(){{
            const ctx = new (window.AudioContext||window.webkitAudioContext)();
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.type='sine'; osc.frequency.setValueAtTime({freq},ctx.currentTime);
            osc.frequency.linearRampToValueAtTime({freq*2},ctx.currentTime+{duration});
            gain.gain.setValueAtTime(0.12,ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+{duration});
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(); osc.stop(ctx.currentTime+{duration});
        }})();</script>"""
    else:
        return
    components.html(js, height=0)

# ============================================================
# BAGIAN 3: LOTTIE LOADER
# ============================================================
@st.cache_data(show_spinner=False)
def load_lottie(url):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

# ============================================================
# BAGIAN 4: FUNGSI GAME
# ============================================================
def acak_5_kartu():
    return [random.choice(["Buster", "Arts", "Quick"]) for _ in range(5)]

def hp_class(pct):
    if pct > 0.5: return "hp-high"
    if pct > 0.25: return "hp-mid"
    return "hp-low"

def bar_html(label, value, max_value, fill_class, extra_class=""):
    pct = max(0, min(100, int(value / max_value * 100)))
    return (
        f"<div class='bar-label'>{label} {value}/{max_value}</div>"
        f"<div class='bar-wrap'><div class='bar-fill {fill_class} {extra_class}' "
        f"style='width:{pct}%;'></div></div>"
    )

def sprite_html(url_img, emoji, anim_class="", counter=0):
    unique_class = f"{anim_class} anim-{counter}" if anim_class else f"anim-{counter}"
    if url_img:
        return f"<div class='sprite-wrap'><img class='sprite-img {unique_class}' src='{url_img}'></div>"
    return f"<div class='sprite-wrap'><div class='sprite-emoji {unique_class}'>{emoji}</div></div>"

def fighter_html(name, emoji, hp, max_hp, np_val, max_np, side,
                 anim_class="", np_ready=False, url_img="",
                 show_shield=False, show_buff=False, counter=0):
    hp_pct = hp / max_hp
    if anim_class:
        sprite_anim = anim_class
    elif np_ready and side == "ally":
        sprite_anim = "sprite-np"
    else:
        sprite_anim = "sprite-idle"

    html = f"<div class='fighter {side}'>"
    html += sprite_html(url_img, emoji, sprite_anim, counter)
    if show_shield:
        html += f"<div class='shield-overlay anim-{counter}'></div>"
    if show_buff:
        html += f"<div class='buff-overlay anim-{counter}'></div>"
    html += f"<div class='fname'>{name}</div>"
    html += bar_html("HP", hp, max_hp, hp_class(hp_pct))
    if side == "ally":
        np_extra = "ready" if np_val >= max_np else ""
        html += bar_html("NP", np_val, max_np, "np-fill", np_extra)
    html += "</div>"
    return html

# ============================================================
# BAGIAN 5: STATE INIT
# ============================================================
if "fgo_v11" not in st.session_state:
    st.session_state.servant = {"nama": "Mash", "hp": 150, "max_hp": 150, "np": 0, "max_np": 100, "atk": 22, "emoji": "🛡️", "url": URL_MASH}
    st.session_state.boss = {"nama": "Goetia", "hp": 350, "max_hp": 350, "atk": 20, "emoji": "👹", "url": URL_GOETIA}
    st.session_state.round = 1
    st.session_state.boss_last_action = "Bersiap"
    st.session_state.kartu_tersedia = acak_5_kartu()
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.battle_log = ["⚔️ Pertandingan dimulai!"]
    st.session_state.game_over = False
    st.session_state.phase = "select"

    # Efek state
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.sound_to_play = ""

    # Animasi state
    st.session_state.servant_anim = "sprite-idle"
    st.session_state.boss_anim = "sprite-idle"
    st.session_state.show_shield_ally = False
    st.session_state.show_shield_enemy = False
    st.session_state.show_buff_enemy = False

    # Counter unik untuk restart animasi CSS
    st.session_state.anim_counter = 0

    st.session_state.fgo_v11 = True

servant = st.session_state.servant
boss = st.session_state.boss

# ============================================================
# BAGIAN 6: LOGIKA
# ============================================================
def hitung_prediksi_dmg(combo):
    total = 0
    is_chain = len(combo) == 3 and len(set(combo)) == 1
    for i, tipe in enumerate(combo):
        mult = 1.0 + (i * 0.25)
        if tipe == "Buster":
            total += int(servant["atk"] * (2.2 if is_chain else 1.6) * mult)
        elif tipe == "Arts":
            total += int(servant["atk"] * 1.0 * mult)
        elif tipe == "Quick":
            total += int(servant["atk"] * 0.9 * mult)
    return total

def hitung_serangan_player():
    combo = st.session_state.antrean_combo
    is_chain = len(set(combo)) == 1
    total_dmg = 0

    for i, tipe in enumerate(combo):
        mult = 1.0 + (i * 0.25)
        if tipe == "Buster":
            dmg = int(servant["atk"] * (2.2 if is_chain else 1.6) * mult + random.randint(-2, 2))
            boss["hp"] = max(0, boss["hp"] - dmg)
            total_dmg += dmg
            st.session_state.battle_log.append(f"🔴 Hit {i+1} [Buster]: **{dmg} DMG**")
        elif tipe == "Arts":
            dmg = int(servant["atk"] * 1.0 * mult)
            gain = 40 if is_chain else 25
            boss["hp"] = max(0, boss["hp"] - dmg)
            servant["np"] = min(servant["max_np"], servant["np"] + gain)
            total_dmg += dmg
            st.session_state.battle_log.append(f"🔵 Hit {i+1} [Arts]: {dmg} DMG (+{gain}% NP)")
        elif tipe == "Quick":
            dmg = int(servant["atk"] * 0.9 * mult)
            servant["np"] = min(servant["max_np"], servant["np"] + 12)
            boss["hp"] = max(0, boss["hp"] - dmg)
            total_dmg += dmg
            st.session_state.battle_log.append(f"🟢 Hit {i+1} [Quick]: {dmg} DMG (+12% NP)")

    # Trigger animasi player
    st.session_state.anim_counter += 1
    st.session_state.servant_anim = "sprite-attack-right"
    st.session_state.boss_anim = "sprite-hit"
    st.session_state.damage_popup = f"-{total_dmg}"
    st.session_state.popup_type = ""
    st.session_state.sound_to_play = "hit"

def hitung_serangan_musuh():
    if boss["hp"] <= 0:
        st.session_state.boss_last_action = "Tumbang"
        st.session_state.boss_anim = "sprite-idle"
        return

    aksi = random.choice(["Tebasan Kegelapan", "Mengaum (Buff ATK)", "Kuda-Kuda Bertahan"])
    st.session_state.boss_last_action = aksi
    st.session_state.anim_counter += 1

    if aksi == "Tebasan Kegelapan":
        d = int(boss["atk"] * random.uniform(0.9, 1.3))
        servant["hp"] = max(0, servant["hp"] - d)
        st.session_state.boss_anim = "sprite-attack-left"
        st.session_state.servant_anim = "sprite-hit"
        st.session_state.damage_popup = f"-{d}"
        st.session_state.popup_type = ""
        st.session_state.sound_to_play = "slash"
        st.session_state.battle_log.append(f"😈 **{boss['nama']}** *{aksi}* (-{d} HP)")

    elif aksi == "Mengaum (Buff ATK)":
        boss["atk"] += 2
        st.session_state.boss_anim = "sprite-idle"
        st.session_state.show_buff_enemy = True
        st.session_state.damage_popup = "ATK +2"
        st.session_state.popup_type = "buff"
        st.session_state.sound_to_play = "buff"
        st.session_state.battle_log.append(f"😈 **{boss['nama']}** *Mengaum* (+2 ATK)")

    else:
        d = int(boss["atk"] * 0.6)
        servant["hp"] = max(0, servant["hp"] - d)
        st.session_state.boss_anim = "sprite-idle"
        st.session_state.show_shield_enemy = True
        st.session_state.servant_anim = "sprite-hit"
        st.session_state.damage_popup = f"-{d}"
        st.session_state.popup_type = ""
        st.session_state.sound_to_play = "hit"
        st.session_state.battle_log.append(f"😈 **{boss['nama']}** *Bertahan* (-{d} HP)")

def reset_ke_select():
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.kartu_tersedia = acak_5_kartu()
    st.session_state.phase = "select"
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.sound_to_play = ""
    st.session_state.servant_anim = "sprite-idle"
    st.session_state.boss_anim = "sprite-idle"
    st.session_state.show_shield_ally = False
    st.session_state.show_shield_enemy = False
    st.session_state.show_buff_enemy = False
    st.session_state.anim_counter += 1
    st.session_state.round += 1

# ============================================================
# BAGIAN 7: RENDER ARENA
# ============================================================
np_ready = servant["np"] >= servant["max_np"]

arena_html = "<div class='arena-wrap'>"
arena_html += fighter_html(
    f"😈 {boss['nama']}", boss["emoji"],
    boss["hp"], boss["max_hp"], 0, 1, "enemy",
    anim_class=st.session_state.boss_anim,
    url_img=boss.get("url", ""),
    show_shield=st.session_state.show_shield_enemy,
    show_buff=st.session_state.show_buff_enemy,
    counter=st.session_state.anim_counter,
)
arena_html += fighter_html(
    f"🛡️ {servant['nama']}", servant["emoji"],
    servant["hp"], servant["max_hp"], servant["np"], servant["max_np"], "ally",
    anim_class=st.session_state.servant_anim,
    np_ready=np_ready,
    url_img=servant.get("url", ""),
    show_shield=st.session_state.show_shield_ally,
    counter=st.session_state.anim_counter,
)
arena_html += "</div>"
st.markdown(arena_html, unsafe_allow_html=True)

# ============================================================
# BAGIAN 8: EFEK VISUAL
# ============================================================
if st.session_state.damage_popup:
    cls = "dmg-pop"
    if st.session_state.popup_type == "heal":
        cls += " heal"
    elif st.session_state.popup_type == "buff":
        cls += " buff"
    st.markdown(f"<div class='{cls}'>{st.session_state.damage_popup}</div>", unsafe_allow_html=True)

if st.session_state.sound_to_play:
    if st.session_state.sound_to_play == "hit":
        play_sound_beep(220, 0.15, "hit")
    elif st.session_state.sound_to_play == "slash":
        play_sound_beep(440, 0.2, "slash")
    elif st.session_state.sound_to_play == "buff":
        play_sound_beep(330, 0.25, "buff")
st.session_state.sound_to_play = ""

# ============================================================
# BAGIAN 9: ROUND BANNER & GAME OVER
# ============================================================
st.markdown(f"<div class='round-banner'>⚔️ RONDE {st.session_state.round} ⚔️</div>", unsafe_allow_html=True)

if servant["hp"] <= 0 or boss["hp"] <= 0:
    st.session_state.game_over = True

# ============================================================
# BAGIAN 10: KONTROL PER PHASE
# ============================================================
if st.session_state.game_over:
    if servant["hp"] <= 0:
        st.error(f"💀 GAME OVER! Bertahan hingga Ronde {st.session_state.round - 1}.")
    else:
        st.success(f"🎉 VICTORY! Menang di Ronde {st.session_state.round - 1}!")
        st.balloons()
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("fgo_v11"):
                del st.session_state[k]
        st.rerun()

elif st.session_state.phase == "select":
    st.markdown("<div style='font-size:12px; color:#aaa; margin-bottom:4px;'>📥 Antrean Combo (Maks 3)</div>", unsafe_allow_html=True)
    slot_classes = {"Buster": "slot-buster", "Arts": "slot-arts", "Quick": "slot-quick"}
    c1, c2, c3 = st.columns(3)
    for i, col in enumerate([c1, c2, c3]):
        with col:
            if i < len(st.session_state.antrean_combo):
                t = st.session_state.antrean_combo[i]
                st.markdown(f"<div class='slot {slot_classes[t]}'>{t}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='slot slot-empty'>—</div>", unsafe_allow_html=True)

    pred = hitung_prediksi_dmg(st.session_state.antrean_combo)
    sisa = max(0, boss["hp"] - pred)
    st.markdown(f"<div class='predict'>📊 Prediksi: <b style='color:#FFD700;'>{pred} DMG</b> &nbsp;·&nbsp; Sisa HP Boss: <b>{sisa}</b></div>", unsafe_allow_html=True)

    # ===== KARTU AKSI 5 SEJAJAR + WARNA DINAMIS =====
    st.markdown("<div style='font-size:12px; color:#aaa; margin:6px 0 4px 0;'>🃏 Pilih Kartu Aksi</div>", unsafe_allow_html=True)

    kartu_css = ""
    warna_map = {
        "Buster": ("#FF4B4B", "rgba(255,75,75,0.30)", "rgba(255,75,75,0.08)", "#ff8080", "rgba(255,75,75,0.5)"),
        "Arts":   ("#1C83E1", "rgba(28,131,225,0.30)", "rgba(28,131,225,0.08)", "#66b8ff", "rgba(28,131,225,0.5)"),
        "Quick":  ("#09AB3B", "rgba(9,171,59,0.30)", "rgba(9,171,59,0.08)", "#3ddc6b", "rgba(9,171,59,0.5)"),
    }
    for idx, tipe in enumerate(st.session_state.kartu_tersedia):
        border, bg_top, bg_bot, text, glow = warna_map[tipe]
        kartu_css += f"""
        div[data-testid="stHorizontalBlock"] > div:nth-child({idx+1}) div[data-testid="stButton"] > button {{
            border: 2px solid {border} !important;
            background: linear-gradient(180deg, {bg_top} 0%, {bg_bot} 100%) !important;
            color: {text} !important;
            box-shadow: 0 0 10px {glow} !important;
            font-size: 13px !important;
            font-weight: 800 !important;
            letter-spacing: 0.5px !important;
        }}
        div[data-testid="stHorizontalBlock"] > div:nth-child({idx+1}) div[data-testid="stButton"] > button:disabled {{
            opacity: 0.3 !important;
        }}
        """
    st.markdown(f"<style>{kartu_css}</style>", unsafe_allow_html=True)

    cols = st.columns(5)
    for idx, tipe in enumerate(st.session_state.kartu_tersedia):
        with cols[idx]:
            disabled = (idx in st.session_state.indeks_terpakai) or (len(st.session_state.antrean_combo) >= 3)
            pickable = "card-pickable" if not disabled else ""
            st.markdown(f"<div class='{pickable}'>", unsafe_allow_html=True)
            if st.button(tipe, key=f"k_{idx}", disabled=disabled, use_container_width=True):
                st.session_state.antrean_combo.append(tipe)
                st.session_state.indeks_terpakai.append(idx)
                st.session_state.sound_to_play = "hit"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # ===== TOMBOL SERANG + RESET =====
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns([3, 1])
    with b1:
        if st.button("⚔️  SERANG!", use_container_width=True, type="primary", disabled=len(st.session_state.antrean_combo) != 3):
            hitung_serangan_player()
            st.session_state.phase = "player_attack"
            st.rerun()
    with b2:
        if st.button("↺ Reset", use_container_width=True, disabled=len(st.session_state.antrean_combo) == 0):
            st.session_state.antrean_combo = []
            st.session_state.indeks_terpakai = []
            st.rerun()

elif st.session_state.phase == "player_attack":
    st.info("💥 Seranganmu mengena! Tekan tombol untuk lanjut ke giliran musuh.")
    if st.button("▶️  LANJUT: GILIRAN MUSUH", use_container_width=True, type="primary"):
        st.session_state.servant_anim = "sprite-idle"
        st.session_state.boss_anim = "sprite-idle"
        st.session_state.damage_popup = ""
        st.session_state.popup_type = ""
        hitung_serangan_musuh()
        st.session_state.phase = "enemy_attack"
        st.rerun()

elif st.session_state.phase == "enemy_attack":
    st.warning(f"😈 {boss['nama']} melakukan: **{st.session_state.boss_last_action}**")
    if st.button("▶️  LANJUT", use_container_width=True, type="primary"):
        if boss["hp"] <= 0 or servant["hp"] <= 0:
            st.session_state.phase = "result"
        else:
            reset_ke_select()
        st.rerun()

elif st.session_state.phase == "result":
    st.success("🎉 Ronde selesai!")
    if st.button("▶️  RONDE BARU", use_container_width=True, type="primary"):
        reset_ke_select()
        st.rerun()

# ============================================================
# BAGIAN 11: LOG
# ============================================================
with st.expander("📜 Log Pertarungan", expanded=False):
    for log in reversed(st.session_state.battle_log[-10:]):
        st.markdown(f"<div style='font-size:11px; color:#ccc; padding:3px 0; border-bottom:1px dashed #2a2a35;'>{log}</div>", unsafe_allow_html=True)
