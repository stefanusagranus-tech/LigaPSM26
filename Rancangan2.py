import streamlit as st
import random
import time

st.set_page_config(page_title="Ancient Legends", layout="centered", initial_sidebar_state="collapsed")

# ============================================================
# URL ASET (GANTI DENGAN FILE KAMU)
# ============================================================
BASE = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/assets"

# Sementara pakai GIF yang sudah ada
PLAYER = {
    "nama": "Warrior",
    "sprite": f"{BASE}/Warrior%20medieval/warrior_idle.gif",
    "attack": f"{BASE}/Warrior%20medieval/warrior_attack.gif",
    "hit":    f"{BASE}/Warrior%20medieval/warrior_hit.gif",
    "death":  f"{BASE}/Warrior%20medieval/warrior_death.gif",
    "faceset": "",  # kosong dulu, pakai emoji
    "emoji": "⚔️",
}

ENEMY = {
    "nama": "Evil Wizard",
    "sprite": f"{BASE}/Evil%20wizard/wizzard_idle.gif",
    "attack": f"{BASE}/Evil%20wizard/wizzard_attack.gif",
    "hit":    f"{BASE}/Evil%20wizard/wizzard_hit.gif",
    "death":  f"{BASE}/Evil%20wizard/wizzard_death.gif",
    "faceset": "",
    "emoji": "🧙",
}

# ============================================================
# CSS GLOBAL — TEMA ANCIENT LEGENDS
# ============================================================
st.markdown("""
<style>
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 0.5rem; padding-bottom: 1rem; max-width: 720px; }

/* ============ BACKGROUND ARENA ============ */
.stApp {
    background: radial-gradient(ellipse at center, #1a1025 0%, #0a0510 100%);
}

/* ============ FACESET + HP BAR (ATAS) ============ */
.top-panel {
    display: flex;
    gap: 10px;
    margin-bottom: 12px;
    align-items: stretch;
}
.top-card {
    flex: 1;
    background: linear-gradient(180deg, #1f1a2e 0%, #0f0a1a 100%);
    border: 2px solid #3a2a4a;
    border-radius: 12px;
    padding: 10px;
    display: flex;
    gap: 10px;
    align-items: center;
    position: relative;
    overflow: hidden;
}
.top-card.enemy { border-color: #4a1a2a; }
.top-card.ally  { border-color: #1a2a4a; }

/* Faceset */
.faceset-box {
    width: 60px;
    height: 60px;
    border-radius: 10px;
    border: 2px solid #FFD700;
    background: linear-gradient(135deg, #2a1a3a, #1a0a2a);
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
    flex-shrink: 0;
    box-shadow: 0 0 10px rgba(255,215,0,0.3);
}
.faceset-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.faceset-emoji {
    font-size: 36px;
    line-height: 1;
}

/* Info kanan faceset */
.info-box {
    flex: 1;
    min-width: 0;
}
.name-label {
    font-size: 13px;
    font-weight: 800;
    color: #FFD700;
    margin-bottom: 4px;
    letter-spacing: 0.5px;
    text-shadow: 0 0 8px rgba(255,215,0,0.4);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* HP bar */
.bar-wrap {
    background: #0a0510;
    border: 1px solid #3a2a4a;
    border-radius: 6px;
    height: 14px;
    overflow: hidden;
    margin: 3px 0;
    position: relative;
}
.bar-fill {
    height: 100%;
    transition: width 0.6s ease;
    border-radius: 6px 0 0 6px;
}
.hp-high { background: linear-gradient(90deg, #09AB3B, #4ade80); }
.hp-mid  { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.hp-low  { background: linear-gradient(90deg, #dc2626, #ff4b4b); }
.bar-label {
    font-size: 10px;
    color: #ddd;
    text-align: left;
    margin: 2px 0 0 0;
    font-family: monospace;
}

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
    transform: scale(1.3);
}

/* Mirror: musuh hadap kiri */
.sprite-mirror {
    transform: scaleX(-1) scale(1.3);
}

/* ============ ANIMASI CSS ============ */
/* Idle bob — sedang (2s) */
@keyframes idle-bob {
    0%,100% { transform: translateY(0) scale(1.3); }
    50% { transform: translateY(-6px) scale(1.3); }
}
.anim-idle { animation: idle-bob 2s ease-in-out infinite; }

/* Idle bob mirror */
@keyframes idle-bob-mirror {
    0%,100% { transform: translateY(0) scaleX(-1) scale(1.3); }
    50% { transform: translateY(-6px) scaleX(-1) scale(1.3); }
}
.anim-idle-mirror { animation: idle-bob-mirror 2s ease-in-out infinite; }

/* Lunge kanan (player attack) — sedang (1s) */
@keyframes lunge-right {
    0% { transform: translateX(0) scale(1.3); }
    40% { transform: translateX(45px) scale(1.45); }
    60% { transform: translateX(55px) scale(1.5); }
    100% { transform: translateX(0) scale(1.3); }
}
.anim-attack-right { animation: lunge-right 1s ease-out !important; }

/* Lunge kiri (enemy attack) — sedang (1s) */
@keyframes lunge-left {
    0% { transform: translateX(0) scaleX(-1) scale(1.3); }
    40% { transform: translateX(-45px) scaleX(-1) scale(1.45); }
    60% { transform: translateX(-55px) scaleX(-1) scale(1.5); }
    100% { transform: translateX(0) scaleX(-1) scale(1.3); }
}
.anim-attack-left { animation: lunge-left 1s ease-out !important; }

/* Shake (hit) — sedang (0.8s) */
@keyframes shake {
    0%,100% { transform: translateX(0) rotate(0deg) scale(1.3); }
    20% { transform: translateX(-10px) rotate(-4deg) scale(1.3); }
    40% { transform: translateX(10px) rotate(4deg) scale(1.3); }
    60% { transform: translateX(-8px) rotate(-3deg) scale(1.3); }
    80% { transform: translateX(8px) rotate(3deg) scale(1.3); }
}
.anim-hit { animation: shake 0.8s ease-out !important; }

/* Shake mirror */
@keyframes shake-mirror {
    0%,100% { transform: translateX(0) scaleX(-1) scale(1.3); }
    20% { transform: translateX(10px) scaleX(-1) scale(1.3); }
    40% { transform: translateX(-10px) scaleX(-1) scale(1.3); }
    60% { transform: translateX(8px) scaleX(-1) scale(1.3); }
    80% { transform: translateX(-8px) scaleX(-1) scale(1.3); }
}
.anim-hit-mirror { animation: shake-mirror 0.8s ease-out !important; }

/* Death */
@keyframes death-fade {
    0% { opacity: 1; transform: scale(1.3); }
    100% { opacity: 0.4; transform: scale(1.3) rotate(15deg); filter: grayscale(1); }
}
.anim-death { animation: death-fade 1s ease-out forwards; }

/* ============ SLASH EFFECT ============ */
@keyframes slash-line {
    0% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(0); }
    25% { opacity: 1; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1); }
    100% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1.3); }
}
.slash-mark {
    position: absolute;
    top: 50%; left: 50%;
    width: 90px; height: 5px;
    background: linear-gradient(90deg, transparent, #fff, #FF4B4B, #fff, transparent);
    box-shadow: 0 0 20px #FF4B4B, 0 0 40px #FF4B4B;
    animation: slash-line 0.9s ease-out forwards;
    pointer-events: none;
    z-index: 10;
    border-radius: 3px;
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
    position: absolute;
    top: 50%; left: 50%;
    width: 120px; height: 120px;
    border-radius: 50%;
    border: 4px solid #4da6ff;
    box-shadow: 0 0 30px #4da6ff, inset 0 0 30px rgba(77,166,255,0.5);
    animation: guard-shield 1.2s ease-out forwards;
    pointer-events: none;
    z-index: 5;
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
    color: #111 !important;
    border: none !important;
    font-size: 14px !important;
    font-weight: 900 !important;
    box-shadow: 0 0 20px rgba(255,215,0,0.5) !important;
}

/* ============ LOG ============ */
.log-line {
    font-size: 11px;
    color: #ccc;
    padding: 4px 8px;
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
    """Faceset + nama + HP bar di atas."""
    hp_pct = hp / max_hp
    # Faceset: pakai gambar kalau ada, fallback ke emoji
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

def sprite_html(data, anim_state, side, show_slash=False, show_shield=False):
    """Render sprite dengan animasi."""
    if anim_state == "attack":
        gif_url = data["attack"]
        anim_class = "anim-attack-right" if side == "ally" else "anim-attack-left"
    elif anim_state == "hit":
        gif_url = data["hit"]
        anim_class = "anim-hit-mirror" if side == "enemy" else "anim-hit"
    elif anim_state == "death":
        gif_url = data["death"]
        anim_class = "anim-death"
    elif anim_state == "defend":
        gif_url = data["sprite"]
        anim_class = "anim-idle-mirror" if side == "enemy" else "anim-idle"
    else:  # idle
        gif_url = data["sprite"]
        anim_class = "anim-idle-mirror" if side == "enemy" else "anim-idle"

    overlay = ""
    if show_slash:
        overlay += (
            "<div class='slash-mark line-1'></div>"
            "<div class='slash-mark line-2'></div>"
            "<div class='slash-mark line-3'></div>"
        )
    if show_shield:
        overlay += "<div class='shield-overlay'></div>"

    return (
        f"<div class='sprite-wrap'>{overlay}"
        f"<img class='sprite-gif {anim_class}' src='{gif_url}' loading='eager'>"
        f"</div>"
    )

def fighter_html(data, hp, max_hp, side, anim_state="idle", show_slash=False, show_shield=False):
    html = f"<div class='fighter {side}'>"
    html += sprite_html(data, anim_state, side, show_slash, show_shield)
    html += "</div>"
    return html

# ============================================================
# STATE
# ============================================================
if "ancient_v1" not in st.session_state:
    st.session_state.player = {"hp": 150, "max_hp": 150, "atk": 22}
    st.session_state.enemy  = {"hp": 180, "max_hp": 180, "atk": 18}
    st.session_state.round = 1
    st.session_state.phase = "select"  # select | player_action | enemy_action | result | gameover
    st.session_state.log = ["⚔️ Pertarungan dimulai!"]
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    st.session_state.show_slash_enemy = False
    st.session_state.show_slash_player = False
    st.session_state.show_shield_player = False
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.player_defend = False
    st.session_state.ancient_v1 = True

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

def aksi_skill1():
    """Skill 1: Attack fisik."""
    reset_efek()
    dmg = int(player["atk"] * random.uniform(0.9, 1.2))
    enemy["hp"] = max(0, enemy["hp"] - dmg)
    st.session_state.player_anim = "attack"
    st.session_state.enemy_anim = "hit"
    st.session_state.show_slash_enemy = True
    st.session_state.damage_popup = f"-{dmg}"
    st.session_state.popup_type = ""
    log(f"⚔️ Warrior [Skill 1]: {dmg} DMG ke Evil Wizard")

def aksi_skill2():
    """Skill 2: Sihir / skill khusus."""
    reset_efek()
    dmg = int(player["atk"] * random.uniform(1.3, 1.7))
    enemy["hp"] = max(0, enemy["hp"] - dmg)
    st.session_state.player_anim = "attack"
    st.session_state.enemy_anim = "hit"
    st.session_state.show_slash_enemy = True
    st.session_state.damage_popup = f"-{dmg}!"
    st.session_state.popup_type = ""
    log(f"🔥 Warrior [Skill 2]: {dmg} DMG (damage besar!)")

def aksi_defend():
    """Defend: kurangi damage 60%."""
    reset_efek()
    st.session_state.player_defend = True
    st.session_state.player_anim = "defend"
    st.session_state.show_shield_player = True
    st.session_state.damage_popup = "DEFEND"
    st.session_state.popup_type = "defend"
    log(f"🛡️ Warrior [Defend]: damage dikurangi 60%")

def aksi_musuh():
    """Musuh pilih aksi random."""
    reset_efek()
    aksi = random.choice(["skill1", "skill1", "skill2", "defend"])
    if aksi == "skill1":
        dmg = int(enemy["atk"] * random.uniform(0.9, 1.2))
        if st.session_state.player_defend:
            dmg = int(dmg * 0.4)
            st.session_state.player_defend = False
            st.session_state.show_shield_player = True
            log(f"⚔️ Evil Wizard: {dmg} DMG (dikurangi Defend)")
        else:
            log(f"⚔️ Evil Wizard: {dmg} DMG")
        player["hp"] = max(0, player["hp"] - dmg)
        st.session_state.enemy_anim = "attack"
        st.session_state.player_anim = "hit"
        st.session_state.show_slash_player = True
        st.session_state.damage_popup = f"-{dmg}"
        st.session_state.popup_type = ""
    elif aksi == "skill2":
        dmg = int(enemy["atk"] * random.uniform(1.3, 1.6))
        if st.session_state.player_defend:
            dmg = int(dmg * 0.4)
            st.session_state.player_defend = False
            st.session_state.show_shield_player = True
            log(f"🔥 Evil Wizard [Skill 2]: {dmg} DMG (dikurangi Defend)")
        else:
            log(f"🔥 Evil Wizard [Skill 2]: {dmg} DMG (damage besar!)")
        player["hp"] = max(0, player["hp"] - dmg)
        st.session_state.enemy_anim = "attack"
        st.session_state.player_anim = "hit"
        st.session_state.show_slash_player = True
        st.session_state.damage_popup = f"-{dmg}!"
        st.session_state.popup_type = ""
    else:
        st.session_state.enemy_anim = "defend"
        st.session_state.damage_popup = "GUARD"
        st.session_state.popup_type = "defend"
        log(f"🛡️ Evil Wizard: Defend")

def reset_ronde():
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    reset_efek()
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
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
# TOP PANEL (Faceset + HP)
# ============================================================
top_html = "<div class='top-panel'>"
top_html += top_panel_html(ENEMY, enemy["hp"], enemy["max_hp"], "enemy")
top_html += top_panel_html(PLAYER, player["hp"], player["max_hp"], "ally")
top_html += "</div>"
st.markdown(top_html, unsafe_allow_html=True)

# ============================================================
# ARENA
# ============================================================
arena_html = "<div class='arena-wrap'>"
arena_html += fighter_html(
    ENEMY, enemy["hp"], enemy["max_hp"], "enemy",
    anim_state=st.session_state.enemy_anim,
    show_slash=st.session_state.show_slash_enemy,
)
arena_html += fighter_html(
    PLAYER, player["hp"], player["max_hp"], "ally",
    anim_state=st.session_state.player_anim,
    show_slash=st.session_state.show_slash_player,
    show_shield=st.session_state.show_shield_player,
)
arena_html += "</div>"
st.markdown(arena_html, unsafe_allow_html=True)

# Damage popup
if st.session_state.damage_popup:
    cls = "dmg-pop"
    if st.session_state.popup_type == "defend": cls += " defend"
    st.markdown(f"<div class='{cls}'>{st.session_state.damage_popup}</div>", unsafe_allow_html=True)

# Round banner
st.markdown(f"<div class='round-banner'>◆ RONDE {st.session_state.round} ◆</div>", unsafe_allow_html=True)

# ============================================================
# KONTROL
# ============================================================
if player["hp"] <= 0:
    st.error(f"💀 GAME OVER! Warrior tumbang di Ronde {st.session_state.round}.")
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("ancient_v1"):
                del st.session_state[k]
        st.rerun()

elif enemy["hp"] <= 0:
    st.success(f"🎉 VICTORY! Evil Wizard tumbang di Ronde {st.session_state.round}!")
    st.balloons()
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("ancient_v1"):
                del st.session_state[k]
        st.rerun()

elif st.session_state.phase == "select":
    st.markdown("<div style='font-size:11px; color:#aaa; margin-bottom:4px; text-align:center;'>Pilih Aksi</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⚔️ Skill 1", use_container_width=True):
            aksi_skill1()
            st.session_state.phase = "player_action"
            st.rerun()
    with c2:
        if st.button("🔥 Skill 2", use_container_width=True):
            aksi_skill2()
            st.session_state.phase = "player_action"
            st.rerun()
    with c3:
        if st.button("🛡️ Defend", use_container_width=True):
            aksi_defend()
            st.session_state.phase = "player_action"
            st.rerun()

elif st.session_state.phase == "player_action":
    time.sleep(1.2)  # tunggu animasi selesai
    if st.button("▶️ NEXT: GILIRAN MUSUH", use_container_width=True, type="primary"):
        # Reset animasi player
        st.session_state.player_anim = "idle"
        st.session_state.damage_popup = ""
        reset_efek()
        # Musuh aksi
        aksi_musuh()
        st.session_state.phase = "enemy_action"
        st.rerun()

elif st.session_state.phase == "enemy_action":
    time.sleep(1.2)
    if st.button("▶️ NEXT: RONDE BARU", use_container_width=True, type="primary"):
        st.session_state.enemy_anim = "idle"
        st.session_state.damage_popup = ""
        reset_efek()
        reset_ronde()
        st.rerun()

# ============================================================
# LOG
# ============================================================
st.markdown("---")
st.markdown("<div style='font-size:11px; color:#FFD700; margin-bottom:4px;'>📜 Log Pertarungan</div>", unsafe_allow_html=True)
with st.container(border=True):
    for line in reversed(st.session_state.log[-8:]):
        cls = "log-line"
        if "Warrior" in line: cls += " player"
        elif "Evil Wizard" in line: cls += " enemy"
        else: cls += " system"
        st.markdown(f"<div class='{cls}'>{line}</div>", unsafe_allow_html=True)
