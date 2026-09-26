import streamlit as st
import random
import base64
from streamlit_lottie import st_lottie
import requests

st.set_page_config(page_title="FGO Arena JRPG", layout="centered", initial_sidebar_state="collapsed")

# ============================================================
# BAGIAN 1: CSS GLOBAL (One-Shot + Looping)
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
    padding: 10px 8px;
    text-align: center;
    position: relative;
}
.fighter.enemy { border-color: #5a1f1f; box-shadow: 0 0 12px rgba(255,75,75,0.18); }
.fighter.ally  { border-color: #1f3a5a; box-shadow: 0 0 12px rgba(28,131,225,0.18); }

/* ============ LOOPING: IDLE BOB ============ */
@keyframes idle-bob {
    0%,100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
}
.sprite { font-size: 64px; line-height: 1; margin: 4px 0 6px 0; animation: idle-bob 2.5s ease-in-out infinite; }

/* ============ LOOPING: GLOW PULSE (saat NP penuh) ============ */
@keyframes glow-pulse {
    0%,100% { filter: drop-shadow(0 0 4px #FFD700); }
    50% { filter: drop-shadow(0 0 18px #FFD700); }
}
.sprite.np-ready { animation: idle-bob 2.5s ease-in-out infinite, glow-pulse 1.2s ease-in-out infinite; }

/* ============ ONE-SHOT: SHAKE (kena damage) ============ */
@keyframes shake {
    0%,100% { transform: translateX(0); }
    20% { transform: translateX(-8px); }
    40% { transform: translateX(8px); }
    60% { transform: translateX(-6px); }
    80% { transform: translateX(6px); }
}
.fighter.hit { animation: shake 0.5s ease; }

/* ============ ONE-SHOT: FLASH MERAH ============ */
@keyframes flash-red {
    0% { background: rgba(255,75,75,0.7); }
    100% { background: transparent; }
}
.fighter.hit::after {
    content: ''; position: absolute; inset: 0; border-radius: 12px;
    animation: flash-red 0.5s ease;
    pointer-events: none;
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

/* ============ HP / NP BAR ============ */
.bar-wrap { background: #0a0a10; border: 1px solid #333; border-radius: 6px; height: 16px; overflow: hidden; margin: 3px 0; }
.bar-fill { height: 100%; transition: width 0.6s ease; border-radius: 6px 0 0 6px; }
.hp-high { background: linear-gradient(90deg, #09AB3B, #4ade80); }
.hp-mid  { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.hp-low  { background: linear-gradient(90deg, #dc2626, #ff4b4b); }
.np-fill { background: linear-gradient(90deg, #7c3aed, #c084fc); }

/* Looping: NP bar berdenyut saat penuh */
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

/* ============ FIX MOBILE: kolom tidak turun ============ */
[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
[data-testid="stHorizontalBlock"] > div { min-width: 0 !important; }

/* ============ TOMBOL ============ */
div[data-testid="stButton"] > button {
    width: 100%; border-radius: 10px; font-weight: 700; font-size: 12px;
    padding: 10px 0; transition: transform 0.15s ease;
}
div[data-testid="stButton"] > button:hover { transform: translateY(-2px); }

.card-buster div[data-testid="stButton"] > button {
    border: 2px solid #FF4B4B !important;
    background: linear-gradient(180deg, rgba(255,75,75,0.25), rgba(255,75,75,0.08)) !important;
    color: #ff8080 !important;
}
.card-arts div[data-testid="stButton"] > button {
    border: 2px solid #1C83E1 !important;
    background: linear-gradient(180deg, rgba(28,131,225,0.25), rgba(28,131,225,0.08)) !important;
    color: #66b8ff !important;
}
.card-quick div[data-testid="stButton"] > button {
    border: 2px solid #09AB3B !important;
    background: linear-gradient(180deg, rgba(9,171,59,0.25), rgba(9,171,59,0.08)) !important;
    color: #3ddc6b !important;
}
.card-buster div[data-testid="stButton"] > button:disabled,
.card-arts div[data-testid="stButton"] > button:disabled,
.card-quick div[data-testid="stButton"] > button:disabled { opacity: 0.3; }

/* Looping: kartu yang bisa dipilih "berdenyut" */
@keyframes card-pulse {
    0%,100% { box-shadow: 0 0 0 rgba(255,215,0,0); }
    50% { box-shadow: 0 0 12px rgba(255,215,0,0.5); }
}
.card-pickable div[data-testid="stButton"] > button:not(:disabled) {
    animation: card-pulse 2s ease-in-out infinite;
}

.btn-execute div[data-testid="stButton"] > button {
    background: linear-gradient(90deg, #FF4B4B, #FFD700) !important;
    color: #111 !important; border: none !important;
    font-size: 14px !important; font-weight: 800 !important;
    letter-spacing: 1px; padding: 12px 0 !important;
    box-shadow: 0 0 15px rgba(255,75,75,0.4);
}
.btn-reset div[data-testid="stButton"] > button {
    background: transparent !important; color: #aaa !important;
    border: 1px solid #444 !important; font-size: 11px !important;
}

/* ============ LOTTIE CONTAINER ============ */
.lottie-overlay {
    position: fixed; top: 30%; left: 50%; transform: translate(-50%,-50%);
    z-index: 9998; pointer-events: none;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='text-align:center; margin:0 0 8px 0; letter-spacing:1px;'>🛡️ FGO ARENA</h3>", unsafe_allow_html=True)

# ============================================================
# BAGIAN 2: SOUND EFFECT (Base64 / Web Audio)
# ============================================================
def play_sound_beep(freq=440, duration=0.1, kind="hit"):
    """
    Bikin sound effect sederhana pakai Web Audio API.
    Tidak butuh file audio — generate nada langsung di browser.
    """
    if kind == "hit":
        # Nada turun (hit)
        js = f"""
        <script>
        (function() {{
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime({freq}, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime({freq*0.4}, ctx.currentTime + {duration});
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + {duration});
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(); osc.stop(ctx.currentTime + {duration});
        }})();
        </script>
        """
    elif kind == "slash":
        # Nada naik (slash)
        js = f"""
        <script>
        (function() {{
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime({freq*0.5}, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime({freq*3}, ctx.currentTime + {duration});
            gain.gain.setValueAtTime(0.1, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + {duration});
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(); osc.stop(ctx.currentTime + {duration});
        }})();
        </script>
        """
    elif kind == "buff":
        # Nada naik lembut (buff)
        js = f"""
        <script>
        (function() {{
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime({freq}, ctx.currentTime);
            osc.frequency.linearRampToValueAtTime({freq*2}, ctx.currentTime + {duration});
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + {duration});
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(); osc.stop(ctx.currentTime + {duration});
        }})();
        </script>
        """
    st.markdown(js, unsafe_allow_html=True)

# ============================================================
# BAGIAN 3: LOTTIE LOADER
# ============================================================
@st.cache_data(show_spinner=False)
def load_lottie(url):
    """Load Lottie JSON dari URL, cache biar gak request berulang."""
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

def fighter_html(name, emoji, hp, max_hp, np_val, max_np, side, extra_class="", np_ready=False):
    hp_pct = hp / max_hp
    sprite_extra = "np-ready" if np_ready else ""
    html = f"<div class='fighter {side} {extra_class}'>"
    html += f"<div class='sprite {sprite_extra}'>{emoji}</div>"
    html += f"<div class='fname'>{name}</div>"
    html += bar_html("HP", hp, max_hp, hp_class(hp_pct))
    if side == "ally":
        np_extra = "ready" if np_val >= max_np else ""
        html += bar_html("NP", np_val, max_np, "np-fill", np_extra)
    html += "</div>"
    return html

# ============================================================
# BAGIAN 5: STATE
# ============================================================
if "fgo_v9" not in st.session_state:
    st.session_state.servant = {"nama": "Mash", "hp": 150, "max_hp": 150, "np": 0, "max_np": 100, "atk": 22, "emoji": "🛡️"}
    st.session_state.boss = {"nama": "Goetia", "hp": 350, "max_hp": 350, "atk": 20, "emoji": "👹"}
    st.session_state.round = 1
    st.session_state.boss_last_action = "Bersiap"
    st.session_state.kartu_tersedia = acak_5_kartu()
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.battle_log = ["⚔️ Pertandingan dimulai!"]
    st.session_state.game_over = False
    st.session_state.phase = "select"
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""          # "" | "heal" | "buff"
    st.session_state.shake_target = ""        # "" | "enemy" | "ally"
    st.session_state.sound_to_play = ""       # "" | "hit" | "slash" | "buff"
    st.session_state.lottie_effect = ""       # "" | "slash" | "explosion"
    st.session_state.fgo_v9 = True

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

    # Trigger efek
    st.session_state.damage_popup = f"-{total_dmg}"
    st.session_state.popup_type = ""
    st.session_state.shake_target = "enemy"
    st.session_state.sound_to_play = "hit"
    st.session_state.lottie_effect = "slash" if is_chain else ""

def hitung_serangan_musuh():
    if boss["hp"] <= 0:
        st.session_state.boss_last_action = "Tumbang"
        return

    aksi = random.choice(["Tebasan Kegelapan", "Mengaum (Buff ATK)", "Kuda-Kuda Bertahan"])
    st.session_state.boss_last_action = aksi

    if aksi == "Tebasan Kegelapan":
        d = int(boss["atk"] * random.uniform(0.9, 1.3))
        servant["hp"] = max(0, servant["hp"] - d)
        st.session_state.damage_popup = f"-{d}"
        st.session_state.popup_type = ""
        st.session_state.shake_target = "ally"
        st.session_state.sound_to_play = "slash"
        st.session_state.lottie_effect = "explosion"
        st.session_state.battle_log.append(f"😈 **{boss['nama']}** *{aksi}* (-{d} HP)")
    elif aksi == "Mengaum (Buff ATK)":
        boss["atk"] += 2
        st.session_state.damage_popup = "ATK +2"
        st.session_state.popup_type = "buff"
        st.session_state.shake_target = ""
        st.session_state.sound_to_play = "buff"
        st.session_state.lottie_effect = ""
        st.session_state.battle_log.append(f"😈 **{boss['nama']}** *Mengaum* (+2 ATK)")
    else:
        d = int(boss["atk"] * 0.6)
        servant["hp"] = max(0, servant["hp"] - d)
        st.session_state.damage_popup = f"-{d}"
        st.session_state.popup_type = ""
        st.session_state.shake_target = "ally"
        st.session_state.sound_to_play = "hit"
        st.session_state.lottie_effect = ""
        st.session_state.battle_log.append(f"😈 **{boss['nama']}** *Bertahan* (-{d} HP)")

def reset_ke_select():
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.kartu_tersedia = acak_5_kartu()
    st.session_state.phase = "select"
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.shake_target = ""
    st.session_state.sound_to_play = ""
    st.session_state.lottie_effect = ""
    st.session_state.round += 1

# ============================================================
# BAGIAN 7: RENDER ARENA
# ============================================================
shake_enemy = "hit" if st.session_state.shake_target == "enemy" else ""
shake_ally = "hit" if st.session_state.shake_target == "ally" else ""
np_ready = servant["np"] >= servant["max_np"]

arena_html = "<div class='arena-wrap'>"
arena_html += fighter_html(f"😈 {boss['nama']}", boss["emoji"], boss["hp"], boss["max_hp"], 0, 1, "enemy", shake_enemy)
arena_html += fighter_html(f"🛡️ {servant['nama']}", servant["emoji"], servant["hp"], servant["max_hp"], servant["np"], servant["max_np"], "ally", shake_ally, np_ready)
arena_html += "</div>"
st.markdown(arena_html, unsafe_allow_html=True)

# ============================================================
# BAGIAN 8: EFEK VISUAL (popup, lottie, sound)
# ============================================================
# Damage popup
if st.session_state.damage_popup:
    cls = "dmg-pop"
    if st.session_state.popup_type == "heal": cls += " heal"
    elif st.session_state.popup_type == "buff": cls += " buff"
    st.markdown(f"<div class='{cls}'>{st.session_state.damage_popup}</div>", unsafe_allow_html=True)

# Lottie overlay (kalau ada)
if st.session_state.lottie_effect:
    LOTTIE_URLS = {
        "slash": "https://assets5.lottiefiles.com/packages/lf20_kkflmtur.json",
        "explosion": "https://assets2.lottiefiles.com/packages/lf20_rovf9gzu.json",
    }
    url = LOTTIE_URLS.get(st.session_state.lottie_effect)
    if url:
        anim = load_lottie(url)
        if anim:
            with st.container():
                st.markdown("<div class='lottie-overlay'>", unsafe_allow_html=True)
                st_lottie(anim, height=180, key=f"fx_{st.session_state.lottie_effect}_{st.session_state.round}")
                st.markdown("</div>", unsafe_allow_html=True)

# Sound effect
if st.session_state.sound_to_play:
    if st.session_state.sound_to_play == "hit":
        play_sound_beep(220, 0.15, "hit")
    elif st.session_state.sound_to_play == "slash":
        play_sound_beep(440, 0.2, "slash")
    elif st.session_state.sound_to_play == "buff
