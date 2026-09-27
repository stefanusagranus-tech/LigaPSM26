import streamlit as st
import random
import time

st.set_page_config(page_title="Ancient Legends", layout="centered", initial_sidebar_state="collapsed")

# ============================================================
# URL ASET
# ============================================================
BASE = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/assets"

PLAYER = {
    "nama": "Warrior",
    "idle":   f"{BASE}/Warrior%20medieval/warrior_idle.gif",
    "attack": f"{BASE}/Warrior%20medieval/warrior_attack.gif",
    "hit":    f"{BASE}/Warrior%20medieval/warrior_hit.gif",
    "death":  f"{BASE}/Warrior%20medieval/warrior_death.gif",
    "run":    f"{BASE}/Warrior%20medieval/warrior_run.gif",
    "faceset": "",
    "emoji": "⚔️",
}

ENEMY = {
    "nama": "Evil Wizard",
    "idle":   f"{BASE}/Evil%20wizard/wizzard_idle.gif",
    "attack": f"{BASE}/Evil%20wizard/wizzard_attack.gif",
    "hit":    f"{BASE}/Evil%20wizard/wizzard_hit.gif",
    "death":  f"{BASE}/Evil%20wizard/wizzard_death.gif",
    "run":    f"{BASE}/Evil%20wizard/wizzard_run.gif",
    "faceset": "",
    "emoji": "🧙",
}

# ============================================================
# CSS GLOBAL
# ============================================================
st.markdown("""
<style>
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 0.5rem; padding-bottom: 1rem; max-width: 720px; }

.stApp {
    background: radial-gradient(ellipse at center, #1a1025 0%, #0a0510 100%);
}

/* ============ TOP PANEL ============ */
.top-panel { display: flex; gap: 10px; margin-bottom: 12px; }
.top-card {
    flex: 1;
    background: linear-gradient(180deg, #1f1a2e 0%, #0f0a1a 100%);
    border: 2px solid #3a2a4a;
    border-radius: 12px;
    padding: 10px;
    display: flex;
    gap: 10px;
    align-items: center;
}
.top-card.enemy { border-color: #4a1a2a; }
.top-card.ally  { border-color: #1a2a4a; }

.faceset-box {
    width: 60px; height: 60px;
    border-radius: 10px;
    border: 2px solid #FFD700;
    background: linear-gradient(135deg, #2a1a3a, #1a0a2a);
    display: flex; justify-content: center; align-items: center;
    overflow: hidden; flex-shrink: 0;
    box-shadow: 0 0 10px rgba(255,215,0,0.3);
}
.faceset-img { width: 100%; height: 100%; object-fit: cover; }
.faceset-emoji { font-size: 36px; line-height: 1; }

.info-box { flex: 1; min-width: 0; }
.name-label {
    font-size: 13px; font-weight: 800; color: #FFD700;
    margin-bottom: 4px; letter-spacing: 0.5px;
    text-shadow: 0 0 8px rgba(255,215,0,0.4);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.bar-wrap {
    background: #0a0510; border: 1px solid #3a2a4a;
    border-radius: 6px; height: 14px; overflow: hidden; margin: 3px 0;
}
.bar-fill { height: 100%; transition: width 0.6s ease; border-radius: 6px 0 0 6px; }
.hp-high { background: linear-gradient(90deg, #09AB3B, #4ade80); }
.hp-mid  { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.hp-low  { background: linear-gradient(90deg, #dc2626, #ff4b4b); }
.bar-label { font-size: 10px; color: #ddd; text-align: left; margin: 2px 0 0 0; font-family: monospace; }

/* ============ ARENA ============ */
.arena-wrap {
    display: flex;
    gap: 10px;
    margin: 8px 0;
    position: relative;
}
.fighter {
    flex: 1;
    background: linear-gradient(180deg, #1a1025 0%, #0a0510 100%);
    border: 2px solid #3a2a4a;
    border-radius: 12px;
    padding: 12px 8px;
    text-align: center;
    position: relative;
    overflow: hidden;
    min-height: 200px;
}
.fighter.enemy { border-color: #5a1f1f; box-shadow: 0 0 12px rgba(255,75,75,0.18); }
.fighter.ally  { border-color: #1f3a5a; box-shadow: 0 0 12px rgba(28,131,225,0.18); }

/* ============ SPRITE ============ */
.sprite-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 160px;
    margin: 6px 0;
    position: relative;
}
.sprite-gif {
    max-height: 100%;
    max-width: 100%;
    object-fit: contain;
    filter: drop-shadow(0 4px 8px rgba(0,0,0,0.6));
    image-rendering: pixelated;
    image-rendering: crisp-edges;
}

/* ============ ANIMASI ============ */
/* Warrior mirror (hadap kiri), Wizard tidak (hadap kanan) */

/* IDLE */
@keyframes idle-bob-mirror {
    0%,100% { transform: translateY(0) scaleX(-1) scale(1.3); }
    50% { transform: translateY(-6px) scaleX(-1) scale(1.3); }
}
.anim-idle-mirror { animation: idle-bob-mirror 2s ease-in-out infinite; }

@keyframes idle-bob {
    0%,100% { transform: translateY(0) scale(1.3); }
    50% { transform: translateY(-6px) scale(1.3); }
}
.anim-idle { animation: idle-bob 2s ease-in-out infinite; }

/* RUN — Warrior lari dari kanan ke kiri (mirror) */
@keyframes run-left-mirror {
    0% { transform: translateX(40px) scaleX(-1) scale(1.3); }
    100% { transform: translateX(-40px) scaleX(-1) scale(1.3); }
}
.anim-run-left-mirror {
    animation: run-left-mirror 0.8s ease-in-out infinite alternate;
}

/* RUN — Wizard lari dari kiri ke kanan */
@keyframes run-right {
    0% { transform: translateX(-40px) scale(1.3); }
    100% { transform: translateX(40px) scale(1.3); }
}
.anim-run-right {
    animation: run-right 0.8s ease-in-out infinite alternate;
}

/* ATTACK — Warrior lunge ke kiri (mirror) */
@keyframes lunge-left-mirror {
    0% { transform: translateX(0) scaleX(-1) scale(1.3); }
    40% { transform: translateX(-50px) scaleX(-1) scale(1.45); }
    60% { transform: translateX(-60px) scaleX(-1) scale(1.5); }
    100% { transform: translateX(0) scaleX(-1) scale(1.3); }
}
.anim-attack-left-mirror { animation: lunge-left-mirror 1s ease-out !important; }

/* ATTACK — Wizard lunge ke kanan */
@keyframes lunge-right {
    0% { transform: translateX(0) scale(1.3); }
    40% { transform: translateX(50px) scale(1.45); }
    60% { transform: translateX(60px) scale(1.5); }
    100% { transform: translateX(0) scale(1.3); }
}
.anim-attack-right { animation: lunge-right 1s ease-out !important; }

/* HIT */
@keyframes shake-mirror {
    0%,100% { transform: translateX(0) scaleX(-1) scale(1.3); }
    20% { transform: translateX(10px) scaleX(-1) scale(1.3); }
    40% { transform: translateX(-10px) scaleX(-1) scale(1.3); }
    60% { transform: translateX(8px) scaleX(-1) scale(1.3); }
    80% { transform: translateX(-8px) scaleX(-1) scale(1.3); }
}
.anim-hit-mirror { animation: shake-mirror 0.8s ease-out !important; }

@keyframes shake {
    0%,100% { transform: translateX(0) scale(1.3); }
    20% { transform: translateX(-10px) scale(1.3); }
    40% { transform: translateX(10px) scale(1.3); }
    60% { transform: translateX(-8px) scale(1.3); }
    80% { transform: translateX(8px) scale(1.3); }
}
.anim-hit { animation: shake 0.8s ease-out !important; }

/* DEATH */
@keyframes death-fade-mirror {
    0% { opacity: 1; transform: scaleX(-1) scale(1.3); }
    100% { opacity: 0.4; transform: scaleX(-1) scale(1.3) rotate(-15deg); filter: grayscale(1); }
}
.anim-death-mirror { animation: death-fade-mirror 1s ease-out forwards; }

@keyframes death-fade {
    0% { opacity: 1; transform: scale(1.3); }
    100% { opacity: 0.4; transform: scale(1.3) rotate(15deg); filter: grayscale(1); }
}
.anim-death { animation: death-fade 1s ease-out forwards; }

/* ============ CAST EFFECT (Wizard) ============ */
@keyframes magic-circle {
    0% { opacity: 0; transform: translate(-50%,-50%) scale(0.3) rotate(0deg); }
    30% { opacity: 1; transform: translate(-50%,-50%) scale(1.2) rotate(180deg); }
    70% { opacity: 1; transform: translate(-50%,-50%) scale(1) rotate(360deg); }
    100% { opacity: 0; transform: translate(-50%,-50%) scale(1.5) rotate(540deg); }
}
.magic-circle {
    position: absolute;
    bottom: 10px; left: 50%;
    width: 100px; height: 100px;
    border-radius: 50%;
    border: 3px dashed #c084fc;
    box-shadow: 0 0 30px #c084fc, inset 0 0 30px rgba(192,132,252,0.5);
    animation: magic-circle 1.5s ease-out forwards;
    pointer-events: none;
    z-index: 5;
}

/* Partikel ungu naik */
@keyframes particle-up {
    0% { opacity: 0; transform: translateY(0) scale(0.5); }
    30% { opacity: 1; transform: translateY(-30px) scale(1); }
    100% { opacity: 0; transform: translateY(-80px) scale(0.5); }
}
.magic-particle {
    position: absolute;
    bottom: 20px;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #c084fc;
    box-shadow: 0 0 10px #c084fc;
    animation: particle-up 1.5s ease-out forwards;
    pointer-events: none;
    z-index: 6;
}
.mp-1 { left: 30%; animation-delay: 0.1s; }
.mp-2 { left: 50%; animation-delay: 0.2s; }
.mp-3 { left: 70%; animation-delay: 0.3s; }

/* Bola sihir terbang dari Wizard ke Warrior */
@keyframes orb-fly {
    0% { opacity: 0; transform: translate(0, 0) scale(0.5); }
    20% { opacity: 1; transform: translate(0, 0) scale(1.2); }
    100% { opacity: 0; transform: translate(200px, -30px) scale(0.8); }
}
.magic-orb {
    position: absolute;
    top: 50%; right: 20px;
    width: 30px; height: 30px;
    border-radius: 50%;
    background: radial-gradient(circle, #fff, #c084fc 40%, #7c3aed 70%);
    box-shadow: 0 0 20px #c084fc, 0 0 40px #7c3aed;
    animation: orb-fly 1.2s ease-out forwards;
    pointer-events: none;
    z-index: 7;
}

/* ============ SLASH ============ */
@keyframes slash-line {
    0% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(0); }
    25% { opacity: 1; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1); }
    100% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1.3); }
}
.slash-mark {
    position: absolute; top: 50%; left: 50%;
    width: 90px; height: 5px;
    background: linear-gradient(90deg, transparent, #fff, #FF4B4B, #fff, transparent);
    box-shadow: 0 0 20px #FF4B4B, 0 0 40px #FF4B4B;
    animation: slash-line 0.9s ease-out forwards;
    pointer-events: none; z-index: 10; border-radius: 3px;
}
.slash-mark.line-1 { --rot: -45deg; }
.slash-mark.line-2 { --rot: -30deg; width: 110px; animation-delay: 0.1s; }
.slash-mark.line-3 { --rot: -60deg; width: 80px; animation-delay: 0.2s; }

/* ============ SHIELD ============ */
@keyframes guard-shield {
    0% { opacity: 0; transform: translate(-50%,-50%) scale(0.3); }
    30% { opacity: 1; transform: translate(-50%,-50%) scale(1.1); }
    70% { opacity: 1; transform: translate(-50%,-50%) scale(1); }
    100% { opacity: 0; transform: translate(-50%,-50%) scale(1.4); }
}
.shield-overlay {
    position: absolute; top: 50%; left: 50%;
    width: 120px; height: 120px;
    border-radius: 50%; border: 4px solid #4da6ff;
    box-shadow: 0 0 30px #4da6ff, inset 0 0 30px rgba(77,166,255,0.5);
    animation: guard-shield 1.2s ease-out forwards;
    pointer-events: none; z-index: 5;
}

/* ============ MISS ============ */
@keyframes miss-fade {
    0% { opacity: 0; transform: translate(-50%,-50%) scale(0.5); }
    30% { opacity: 1; transform: translate(-50%,-50%) scale(1.2); }
    100% { opacity: 0; transform: translate(-50%,-100%) scale(1); }
}
.miss-pop {
    position: absolute; top: 50%; left: 50%;
    font-size: 26px; font-weight: 900; color: #4da6ff;
    text-shadow: 0 0 12px #4da6ff, 2px 2px 0 #000;
    animation: miss-fade 1s ease-out forwards;
    pointer-events: none; z-index: 11; letter-spacing: 2px;
}

/* ============ DAMAGE POPUP ============ */
@keyframes pop-dmg {
    0% { opacity: 0; transform: translate(-50%,-30%) scale(0.4); }
    25% { opacity: 1; transform: translate(-50%,-50%) scale(1.4); }
    70% { opacity: 1; transform: translate(-50%,-60%) scale(1.1); }
    100% { opacity: 0; transform: translate(-50%,-90%) scale(1); }
}
.dmg-pop {
    position: fixed; top: 35%; left: 50%;
    font-size: 44px; font-weight: 900; color: #FF4B4B;
    text-shadow: 0 0 20px #FF4B4B, 3px 3px 0 #000;
    animation: pop-dmg 1.2s ease-out forwards;
    pointer-events: none; z-index: 9999;
}
.dmg-pop.defend { color: #4da6ff; text-shadow: 0 0 20px #4da6ff, 3px 3px 0 #000; }
.dmg-pop.miss { color: #4da6ff; text-shadow: 0 0 20px #4da6ff, 3px 3px 0 #000; }
.dmg-pop.magic { color: #c084fc; text-shadow: 0 0 20px #c084fc, 3px 3px 0 #000; }

/* ============ ROUND BANNER ============ */
@keyframes shine {
    0% { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
}
.round-banner {
    background: linear-gradient(90deg, #FFD700, #FF4B4B, #FFD700);
    background-size: 200% 100%;
    animation: shine 3s linear infinite;
    color: #111; text-align: center; font-weight: 900; font-size: 14px;
    padding: 6px; border-radius: 8px; margin: 10px 0; letter-spacing: 3px;
    box-shadow: 0 0 15px rgba(255,215,0,0.4);
}

/* ============ TOMBOL ============ */
div[data-testid="stButton"] > button {
    width: 100%; border-radius: 10px; font-weight: 800; font-size: 13px;
    padding: 12px 0; transition: transform 0.15s ease;
    border: 2px solid #3a2a4a !important;
    background: linear-gradient(180deg, #2a1a3a, #1a0a2a) !important;
    color: #FFD700 !important;
}
div[data-testid="stButton"] > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 15px rgba(255,215,0,0.4);
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(90deg, #FF4B4B, #FFD700) !important;
    color: #111 !important; border: none !important;
    font-size: 14px !important; font-weight: 900 !important;
    box-shadow: 0 0 20px rgba(255,215,0,0.5) !important;
}

/* ============ LOG ============ */
.log-line {
    font-size: 11px; color: #ccc; padding: 4px 8px;
    border-bottom: 1px dashed #2a1a3a;
}
.log-line.player { border-left: 3px solid #4ade80; }
.log-line.enemy  { border-left: 3px solid #ef4444; }
.log-line.system { border-left: 3px solid #FFD700; color: #FFD700; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='text-align:center; margin:0 0 8px 0; letter-spacing:3px; color:#FFD700; text-shadow: 0 0 15px rgba(255,215,0,0.5);'>⚔️ ANCIENT LEGENDS ⚔️</h3>", unsafe_allow_html=True)
# ============================================================
# FUNGSI
# ============================================================
def hp_class(pct):
    if pct > 0.5: return "hp-high"
    if pct > 0.25: return "hp-mid"
    return "hp-low"

def bar_html(label, value, max_value, fill_class):
    pct = max(0, min(100, int(value / max_value * 100)))
    return (
        f"<div class='bar-wrap'><div class='bar-fill {fill_class}' "
        f"style='width:{pct}%;'></div></div>"
        f"<div class='bar-label'>{label} {value}/{max_value}</div>"
    )

def top_panel_html(data, hp, max_hp, side):
    hp_pct = hp / max_hp
    if data.get("faceset"):
        face = f"<img class='faceset-img' src='{data['faceset']}'>"
    else:
        face = f"<div class='faceset-emoji'>{data['emoji']}</div>"
    return (
        f"<div class='top-card {side}'>"
        f"<div class='faceset-box'>{face}</div>"
        f"<div class='info-box'>"
        f"<div class='name-label'>{data['nama']}</div>"
        f"{bar_html('HP', hp, max_hp, hp_class(hp_pct))}"
        f"</div>"
        f"</div>"
    )

def sprite_html(data, anim_state, side, show_slash=False, show_shield=False,
                show_miss=False, show_cast=False, show_orb=False):
    """Render sprite dengan animasi."""
    if anim_state == "attack":
        gif_url = data["attack"]
        anim_class = "anim-attack-left-mirror" if side == "ally" else "anim-attack-right"
    elif anim_state == "run":
        gif_url = data["run"]
        anim_class = "anim-run-left-mirror" if side == "ally" else "anim-run-right"
    elif anim_state == "hit":
        gif_url = data["hit"]
        anim_class = "anim-hit-mirror" if side == "ally" else "anim-hit"
    elif anim_state == "death":
        gif_url = data["death"]
        anim_class = "anim-death-mirror" if side == "ally" else "anim-death"
    else:
        gif_url = data["idle"]
        anim_class = "anim-idle-mirror" if side == "ally" else "anim-idle"

    overlay = ""
    if show_slash:
        overlay += (
            "<div class='slash-mark line-1'></div>"
            "<div class='slash-mark line-2'></div>"
            "<div class='slash-mark line-3'></div>"
        )
    if show_shield:
        overlay += "<div class='shield-overlay'></div>"
    if show_miss:
        overlay += "<div class='miss-pop'>MISS!</div>"
    if show_cast:
        overlay += (
            "<div class='magic-circle'></div>"
            "<div class='magic-particle mp-1'></div>"
            "<div class='magic-particle mp-2'></div>"
            "<div class='magic-particle mp-3'></div>"
        )
    if show_orb:
        overlay += "<div class='magic-orb'></div>"

    return (
        f"<div class='sprite-wrap'>{overlay}"
        f"<img class='sprite-gif {anim_class}' src='{gif_url}' loading='eager'>"
        f"</div>"
    )

def fighter_html(data, hp, max_hp, side, anim_state="idle",
                 show_slash=False, show_shield=False, show_miss=False,
                 show_cast=False, show_orb=False):
    html = f"<div class='fighter {side}'>"
    html += sprite_html(data, anim_state, side, show_slash, show_shield,
                        show_miss, show_cast, show_orb)
    html += "</div>"
    return html

# ============================================================
# STATE
# ============================================================
if "ancient_v3" not in st.session_state:
    st.session_state.player = {"hp": 150, "max_hp": 150, "atk": 22}
    st.session_state.enemy  = {"hp": 180, "max_hp": 180, "atk": 18}
    st.session_state.round = 1
    # phase: ready | intro | select | player_run | player_attack | player_return
    #        enemy_cast | enemy_attack | next_round | gameover
    st.session_state.phase = "ready"
    st.session_state.log = ["⚔️ Bersiap untuk bertarung..."]
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    st.session_state.show_slash_enemy = False
    st.session_state.show_slash_player = False
    st.session_state.show_shield_player = False
    st.session_state.show_miss_enemy = False
    st.session_state.show_miss_player = False
    st.session_state.show_cast_enemy = False
    st.session_state.show_orb_enemy = False
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.player_defend = False
    st.session_state.last_player_action = ""
    st.session_state.ancient_v3 = True

player = st.session_state.player
enemy = st.session_state.enemy

# ============================================================
# LOGIKA
# ============================================================
def log(msg):
    st.session_state.log.append(msg)

def reset_efek():
    st.session_state.show_slash_enemy = False
    st.session_state.show_slash_player = False
    st.session_state.show_shield_player = False
    st.session_state.show_miss_enemy = False
    st.session_state.show_miss_player = False
    st.session_state.show_cast_enemy = False
    st.session_state.show_orb_enemy = False

def pilih_aksi_skill1():
    reset_efek()
    st.session_state.last_player_action = "skill1"

def pilih_aksi_skill2():
    reset_efek()
    st.session_state.last_player_action = "skill2"

def pilih_aksi_defend():
    reset_efek()
    st.session_state.last_player_action = "defend"

def eksekusi_skill1():
    if random.random() < 0.20:
        st.session_state.show_miss_enemy = True
        st.session_state.damage_popup = "MISS!"
        st.session_state.popup_type = "miss"
        log("⚔️ Warrior [Skill 1]: MISS! Wizard menghindar.")
        return
    dmg = int(player["atk"] * random.uniform(0.9, 1.2))
    enemy["hp"] = max(0, enemy["hp"] - dmg)
    st.session_state.show_slash_enemy = True
    st.session_state.damage_popup = f"-{dmg}"
    st.session_state.popup_type = ""
    log(f"⚔️ Warrior [Skill 1]: {dmg} DMG ke Evil Wizard")

def eksekusi_skill2():
    if random.random() < 0.15:
        st.session_state.show_miss_enemy = True
        st.session_state.damage_popup = "MISS!"
        st.session_state.popup_type = "miss"
        log("🔥 Warrior [Skill 2]: MISS! Wizard menghindar.")
        return
    dmg = int(player["atk"] * random.uniform(1.3, 1.7))
    enemy["hp"] = max(0, enemy["hp"] - dmg)
    st.session_state.show_slash_enemy = True
    st.session_state.damage_popup = f"-{dmg}!"
    st.session_state.popup_type = ""
    log(f"🔥 Warrior [Skill 2]: {dmg} DMG (damage besar!)")

def eksekusi_defend():
    st.session_state.player_defend = True
    st.session_state.show_shield_player = True
    st.session_state.damage_popup = "DEFEND"
    st.session_state.popup_type = "defend"
    log("🛡️ Warrior [Defend]: damage dikurangi 60%")

def eksekusi_musuh():
    """Musuh cast sihir (tanpa lari) lalu attack."""
    reset_efek()
    st.session_state.show_cast_enemy = True
    aksi = random.choice(["skill1", "skill1", "skill2", "defend"])
    st.session_state.last_enemy_action = aksi

def eksekusi_musuh_attack():
    """Terapkan damage musuh."""
    aksi = st.session_state.get("last_enemy_action", "skill1")
    if aksi == "skill1":
        if random.random() < 0.20 and not st.session_state.player_defend:
            st.session_state.show_miss_player = True
            st.session_state.damage_popup = "MISS!"
            st.session_state.popup_type = "miss"
            log("⚔️ Evil Wizard: MISS! Warrior menghindar.")
            return
        dmg = int(enemy["atk"] * random.uniform(0.9, 1.2))
        if st.session_state.player_defend:
            dmg = int(dmg * 0.4)
            st.session_state.player_defend = False
            st.session_state.show_shield_player = True
            log(f"⚔️ Evil Wizard: {dmg} DMG (dikurangi Defend)")
        else:
            log(f"⚔️ Evil Wizard: {dmg} DMG")
        player["hp"] = max(0, player["hp"] - dmg)
        st.session_state.show_slash_player = True
        st.session_state.damage_popup = f"-{dmg}"
        st.session_state.popup_type = "magic"
    elif aksi == "skill2":
        if random.random() < 0.15 and not st.session_state.player_defend:
            st.session_state.show_miss_player = True
            st.session_state.damage_popup = "MISS!"
            st.session_state.popup_type = "miss"
            log("🔥 Evil Wizard [Skill 2]: MISS! Warrior menghindar.")
            return
        dmg = int(enemy["atk"] * random.uniform(1.3, 1.6))
        if st.session_state.player_defend:
            dmg = int(dmg * 0.4)
            st.session_state.player_defend = False
            st.session_state.show_shield_player = True
            log(f"🔥 Evil Wizard [Skill 2]: {dmg} DMG (dikurangi Defend)")
        else:
            log(f"🔥 Evil Wizard [Skill 2]: {dmg} DMG (damage besar!)")
        player["hp"] = max(0, player["hp"] - dmg)
        st.session_state.show_slash_player = True
        st.session_state.damage_popup = f"-{dmg}!"
        st.session_state.popup_type = "magic"
    else:
        st.session_state.damage_popup = "GUARD"
        st.session_state.popup_type = "defend"
        log("🛡️ Evil Wizard: Defend")

def reset_ronde():
    reset_efek()
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.last_player_action = ""
    st.session_state.round += 1
    st.session_state.phase = "select"
    # ============================================================
# CEK DEATH
# ============================================================
if player["hp"] <= 0:
    st.session_state.player_anim = "death"
if enemy["hp"] <= 0:
    st.session_state.enemy_anim = "death"

# ============================================================
# TOP PANEL
# ============================================================
top_html = "<div class='top-panel'>"
top_html += top_panel_html(ENEMY, enemy["hp"], enemy["max_hp"], "enemy")
top_html += top_panel_html(PLAYER, player["hp"], player["max_hp"], "ally")
top_html += "</div>"
st.markdown(top_html, unsafe_
