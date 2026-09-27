import streamlit as st
import random
import time

st.set_page_config(page_title="Spirit Arena", layout="centered", initial_sidebar_state="collapsed")

# ============================================================
# URL GIF DARI GITHUB RAW
# ============================================================
BASE = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/assets"

WARRIOR = {
    "nama": "Warrior",
    "idle":   f"{BASE}/Warrior%20medieval/warrior_idle.gif",
    "attack": f"{BASE}/Warrior%20medieval/warrior_attack.gif",
    "hit":    f"{BASE}/Warrior%20medieval/warrior_hit.gif",
    "death":  f"{BASE}/Warrior%20medieval/warrior_death.gif",
}

WIZARD = {
    "nama": "Evil Wizard",
    "idle":   f"{BASE}/Evil%20wizard/wizzard_idle.gif",
    "attack": f"{BASE}/Evil%20wizard/wizzard_attack.gif",
    "hit":    f"{BASE}/Evil%20wizard/wizzard_hit.gif",
    "death":  f"{BASE}/Evil%20wizard/wizzard_death.gif",
}

# ============================================================
# CSS GLOBAL
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

/* ============ SPRITE GIF ============ */
.sprite-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 130px;
    margin: 6px 0;
    position: relative;
}
.sprite-gif {
    max-height: 100%;
    max-width: 100%;
    object-fit: contain;
    filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
    image-rendering: pixelated;
}

/* ============ ANIMASI CSS TAMBAHAN ============ */
/* Idle bob */
@keyframes idle-bob {
    0%,100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
}
.anim-idle { animation: idle-bob 3s ease-in-out infinite; }

/* Lunge kanan (player attack) */
@keyframes lunge-right {
    0% { transform: translateX(0) scale(1); }
    35% { transform: translateX(50px) scale(1.15); }
    55% { transform: translateX(65px) scale(1.25); }
    100% { transform: translateX(0) scale(1); }
}
.anim-attack-right { animation: lunge-right 1.6s ease-out !important; }

/* Lunge kiri (enemy attack) */
@keyframes lunge-left {
    0% { transform: translateX(0) scale(1); }
    35% { transform: translateX(-50px) scale(1.15); }
    55% { transform: translateX(-65px) scale(1.25); }
    100% { transform: translateX(0) scale(1); }
}
.anim-attack-left { animation: lunge-left 1.6s ease-out !important; }

/* Shake (hit) */
@keyframes shake {
    0%,100% { transform: translateX(0) rotate(0deg); }
    15% { transform: translateX(-12px) rotate(-5deg); }
    30% { transform: translateX(12px) rotate(5deg); }
    45% { transform: translateX(-8px) rotate(-3deg); }
    60% { transform: translateX(8px) rotate(3deg); }
    75% { transform: translateX(-4px) rotate(-1deg); }
    90% { transform: translateX(4px) rotate(1deg); }
}
.anim-hit { animation: shake 1.2s ease-out !important; }

/* Death fade */
@keyframes death-fade {
    0% { opacity: 1; transform: scale(1); }
    100% { opacity: 0.5; transform: scale(0.95); filter: grayscale(1); }
}
.anim-death { animation: death-fade 1.5s ease-out forwards; }

/* ============ SLASH EFFECT ============ */
@keyframes slash-line {
    0% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(0); }
    20% { opacity: 1; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1); }
    100% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1.3); }
}
.slash-mark {
    position: absolute;
    top: 50%; left: 50%;
    width: 100px; height: 6px;
    background: linear-gradient(90deg, transparent, #fff, #FF4B4B, #fff, transparent);
    box-shadow: 0 0 20px #FF4B4B, 0 0 40px #FF4B4B;
    animation: slash-line 1.2s ease-out forwards;
    pointer-events: none;
    z-index: 10;
    border-radius: 3px;
}
.slash-mark.line-1 { --rot: -45deg; }
.slash-mark.line-2 { --rot: -30deg; width: 130px; animation-delay: 0.12s; }
.slash-mark.line-3 { --rot: -60deg; width: 85px; animation-delay: 0.24s; }

/* ============ DAMAGE POPUP ============ */
@keyframes pop-dmg {
    0% { opacity: 0; transform: translate(-50%,-30%) scale(0.4); }
    25% { opacity: 1; transform: translate(-50%,-50%) scale(1.5); }
    70% { opacity: 1; transform: translate(-50%,-60%) scale(1.1); }
    100% { opacity: 0; transform: translate(-50%,-90%) scale(1); }
}
.dmg-pop {
    position: fixed; top: 35%; left: 50%;
    font-size: 46px; font-weight: 900; color: #FF4B4B;
    text-shadow: 0 0 20px #FF4B4B, 3px 3px 0 #000;
    animation: pop-dmg 1.5s ease-out forwards;
    pointer-events: none; z-index: 9999;
}

/* ============ HP BAR ============ */
.bar-wrap { background: #0a0a10; border: 1px solid #333; border-radius: 6px; height: 16px; overflow: hidden; margin: 3px 0; }
.bar-fill { height: 100%; transition: width 0.8s ease; border-radius: 6px 0 0 6px; }
.hp-high { background: linear-gradient(90deg, #09AB3B, #4ade80); }
.hp-mid  { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.hp-low  { background: linear-gradient(90deg, #dc2626, #ff4b4b); }
.bar-label { font-size: 10px; color: #bbb; text-align: left; margin: 2px 0 4px 0; font-family: monospace; }

/* ============ ROUND BANNER ============ */
@keyframes shine {
    0% { background-position: 0% 50%; }
    100% { background-position: 200% 50%; }
}
.round-banner {
    background: linear-gradient(90deg, #FF4B4B, #FFD700, #FF4B4B);
    background-size: 200% 100%;
    animation: shine 4s linear infinite;
    color: #111; text-align: center; font-weight: 800; font-size: 15px;
    padding: 6px; border-radius: 8px; margin: 12px 0; letter-spacing: 2px;
}

/* ============ TOMBOL ============ */
div[data-testid="stButton"] > button {
    width: 100%; border-radius: 10px; font-weight: 700; font-size: 13px;
    padding: 12px 0;
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(90deg, #FF4B4B, #FFD700) !important;
    color: #111 !important;
    border: none !important;
    font-size: 15px !important;
    font-weight: 900 !important;
    padding: 14px 0 !important;
    box-shadow: 0 0 20px rgba(255,75,75,0.5) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='text-align:center; margin:0 0 8px 0; letter-spacing:1px;'>⚔️ SPIRIT ARENA</h3>", unsafe_allow_html=True)

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
        f"<div class='bar-label'>{label} {value}/{max_value}</div>"
        f"<div class='bar-wrap'><div class='bar-fill {fill_class}' "
        f"style='width:{pct}%;'></div></div>"
    )

def sprite_html(url_gif, anim_class="anim-idle", counter=0, show_slash=False):
    overlay = ""
    if show_slash:
        overlay += (
            f"<div class='slash-mark line-1 anim-{counter}'></div>"
            f"<div class='slash-mark line-2 anim-{counter}'></div>"
            f"<div class='slash-mark line-3 anim-{counter}'></div>"
        )
    return (
        f"<div class='sprite-wrap'>{overlay}"
        f"<img class='sprite-gif {anim_class} anim-{counter}' src='{url_gif}'>"
        f"</div>"
    )

def fighter_html(data, hp, max_hp, side, anim_state="idle", show_slash=False, counter=0):
    hp_pct = hp / max_hp
    gif_url = data.get(anim_state, data["idle"])

    # Tentukan class animasi CSS tambahan
    if anim_state == "attack":
        anim_class = "anim-attack-right" if side == "ally" else "anim-attack-left"
    elif anim_state == "hit":
        anim_class = "anim-hit"
    elif anim_state == "death":
        anim_class = "anim-death"
    else:
        anim_class = "anim-idle"

    html = f"<div class='fighter {side}'>"
    html += sprite_html(gif_url, anim_class, counter, show_slash)
    html += f"<div style='font-weight:700; font-size:12px; color:#fff; margin-bottom:6px;'>{data['nama']}</div>"
    html += bar_html("HP", hp, max_hp, hp_class(hp_pct))
    html += "</div>"
    return html
    # ============================================================
# STATE
# ============================================================
if "spirit_v2" not in st.session_state:
    st.session_state.player = {"hp": 150, "max_hp": 150, "atk": 22}
    st.session_state.enemy  = {"hp": 200, "max_hp": 200, "atk": 18}
    st.session_state.round = 1
    st.session_state.phase = "select"
    st.session_state.log = ["⚔️ Pertarungan dimulai!"]
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    st.session_state.show_slash_enemy = False
    st.session_state.show_slash_player = False
    st.session_state.damage_popup = ""
    st.session_state.anim_counter = 0
    st.session_state.spirit_v2 = True

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

def aksi_player_attack():
    """Player attack: animasi lunge + slash + damage."""
    reset_efek()
    st.session_state.anim_counter += 1

    # Damage
    dmg = int(player["atk"] * random.uniform(0.9, 1.3))
    enemy["hp"] = max(0, enemy["hp"] - dmg)

    # Set animasi
    st.session_state.player_anim = "attack"
    st.session_state.enemy_anim = "hit"
    st.session_state.show_slash_enemy = True
    st.session_state.damage_popup = f"-{dmg}"
    log(f"🗡️ Warrior menyerang: {dmg} DMG ke Evil Wizard")

def aksi_musuh_attack():
    """Musuh attack: animasi lunge + slash + damage ke player."""
    reset_efek()
    st.session_state.anim_counter += 1

    dmg = int(enemy["atk"] * random.uniform(0.9, 1.3))
    player["hp"] = max(0, player["hp"] - dmg)

    st.session_state.enemy_anim = "attack"
    st.session_state.player_anim = "hit"
    st.session_state.show_slash_player = True
    st.session_state.damage_popup = f"-{dmg}"
    log(f"🔥 Evil Wizard menyerang: {dmg} DMG ke Warrior")

def reset_ronde():
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    reset_efek()
    st.session_state.damage_popup = ""
    st.session_state.round += 1
    st.session_state.phase = "select"
    # ============================================================
# RENDER ARENA
# ============================================================
# Cek death
if player["hp"] <= 0:
    st.session_state.player_anim = "death"
if enemy["hp"] <= 0:
    st.session_state.enemy_anim = "death"

arena_html = "<div class='arena-wrap'>"
arena_html += fighter_html(
    WIZARD, enemy["hp"], enemy["max_hp"], "enemy",
    anim_state=st.session_state.enemy_anim,
    show_slash=st.session_state.show_slash_enemy,
    counter=st.session_state.anim_counter,
)
arena_html += fighter_html(
    WARRIOR, player["hp"], player["max_hp"], "ally",
    anim_state=st.session_state.player_anim,
    show_slash=st.session_state.show_slash_player,
    counter=st.session_state.anim_counter,
)
arena_html += "</div>"
st.markdown(arena_html, unsafe_allow_html=True)

# Damage popup
if st.session_state.damage_popup:
    st.markdown(f"<div class='dmg-pop'>{st.session_state.damage_popup}</div>", unsafe_allow_html=True)

# Round banner
st.markdown(f"<div class='round-banner'>⚔️ RONDE {st.session_state.round} ⚔️</div>", unsafe_allow_html=True)

# ============================================================
# KONTROL
# ============================================================
if player["hp"] <= 0:
    st.error(f"💀 GAME OVER! Warrior tumbang di Ronde {st.session_state.round}.")
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("spirit_v2"):
                del st.session_state[k]
        st.rerun()

elif enemy["hp"] <= 0:
    st.success(f"🎉 VICTORY! Evil Wizard tumbang di Ronde {st.session_state.round}!")
    st.balloons()
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("spirit_v2"):
                del st.session_state[k]
        st.rerun()

elif st.session_state.phase == "select":
    st.markdown("<div style='font-size:12px; color:#aaa; margin-bottom:6px;'>⚔️ Tekan ATTACK untuk menyerang</div>", unsafe_allow_html=True)
    if st.button("⚔️  ATTACK!", use_container_width=True, type="primary"):
        aksi_player_attack()
        st.session_state.phase = "player_action"
        st.rerun()

elif st.session_state.phase == "player_action":
    time.sleep(1.6)
    st.info("💥 Seranganmu mengena! Tekan NEXT untuk giliran musuh.")
    if st.button("▶️  NEXT: GILIRAN MUSUH", use_container_width=True, type="primary"):
        reset_efek()
        st.session_state.damage_popup = ""
        st.session_state.player_anim = "idle"
        aksi_musuh_attack()
        st.session_state.phase = "enemy_action"
        st.rerun()

elif st.session_state.phase == "enemy_action":
    time.sleep(1.6)
    st.warning("😈 Musuh menyerang! Tekan NEXT untuk ronde baru.")
    if st.button("▶️  NEXT: RONDE BARU", use_container_width=True, type="primary"):
        reset_efek()
        st.session_state.damage_popup = ""
        st.session_state.enemy_anim = "idle"
        reset_ronde()
        st.rerun()

# ============================================================
# LOG
# ============================================================
st.markdown("---")
st.markdown("<div style='font-size:12px; color:#FFD700; margin-bottom:4px;'>📜 Log Pertarungan</div>", unsafe_allow_html=True)
with st.container(border=True):
    for line in reversed(st.session_state.log[-10:]):
        st.markdown(f"<div style='font-size:11px; color:#ccc; padding:3px 0; border-bottom:1px dashed #2a2a35;'>{line}</div>", unsafe_allow_html=True)
