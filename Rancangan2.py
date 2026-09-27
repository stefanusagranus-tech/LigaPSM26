import streamlit as st
import random
import time

st.set_page_config(page_title="FGO Arena JRPG", layout="centered", initial_sidebar_state="collapsed")

# ============================================================
# URL SPRITE SHEET
# ============================================================
BASE = "https://raw.githubusercontent.com/stefanusagranus-tech/LigaPSM26/main/assets"

# Warrior (Player)
WARRIOR = {
    "idle":     f"{BASE}/Warrior%20medieval/Idle.png",
    "attack1":  f"{BASE}/Warrior%20medieval/Attack1.png",
    "attack2":  f"{BASE}/Warrior%20medieval/Attack2.png",
    "attack3":  f"{BASE}/Warrior%20medieval/Attack3.png",
    "hit":      f"{BASE}/Warrior%20medieval/Get_Hit.png",
    "death":    f"{BASE}/Warrior%20medieval/Death.png",
    "frames":   {"idle": 10, "attack1": 5, "attack2": 5, "attack3": 4, "hit": 3, "death": 9},
}

# Wizard (Enemy)
WIZARD = {
    "idle":     f"{BASE}/Evil%20wizard/Idle.png",
    "attack1":  f"{BASE}/Evil%20wizard/Attack1.png",
    "attack2":  f"{BASE}/Evil%20wizard/Attack2.png",
    "hit":      f"{BASE}/Evil%20wizard/Take_Hit.png",
    "death":    f"{BASE}/Evil%20wizard/Death.png",
    "frames":   {"idle": 8, "attack1": 5, "attack2": 8, "hit": 3, "death": 8},
}

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

/* ============ SPRITE SHEET VIEWPORT ============ */
.sprite-viewport {
    width: 100%;
    height: 120px;
    margin: 6px 0;
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
    overflow: hidden;
}
.sprite-anim {
    width: 100%;
    height: 100%;
    background-repeat: no-repeat;
    background-position: 0 0;
    image-rendering: pixelated;
    image-rendering: crisp-edges;
    filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
}

/* ============ ANIMASI SPRITE (frame-by-frame) ============ */
/* Idle: loop 10 frame */
@keyframes play-idle-w {
    from { background-position: 0 0; }
    to   { background-position: -1000% 0; }  /* 10 frame */
}
.anim-idle-w { animation: play-idle-w 1.5s steps(10) infinite; }

/* Idle Wizard: 8 frame */
@keyframes play-idle-z {
    from { background-position: 0 0; }
    to   { background-position: -800% 0; }
}
.anim-idle-z { animation: play-idle-z 1.2s steps(8) infinite; }

/* Attack1 Warrior: 5 frame, play sekali */
@keyframes play-atk1-w {
    from { background-position: 0 0; }
    to   { background-position: -500% 0; }
}
.anim-attack1-w { animation: play-atk1-w 0.6s steps(5) 1 forwards; }

/* Attack2 Warrior: 5 frame */
@keyframes play-atk2-w {
    from { background-position: 0 0; }
    to   { background-position: -500% 0; }
}
.anim-attack2-w { animation: play-atk2-w 0.6s steps(5) 1 forwards; }

/* Attack3 Warrior: 4 frame */
@keyframes play-atk3-w {
    from { background-position: 0 0; }
    to   { background-position: -400% 0; }
}
.anim-attack3-w { animation: play-atk3-w 0.5s steps(4) 1 forwards; }

/* Attack1 Wizard: 5 frame */
@keyframes play-atk1-z {
    from { background-position: 0 0; }
    to   { background-position: -500% 0; }
}
.anim-attack1-z { animation: play-atk1-z 0.6s steps(5) 1 forwards; }

/* Attack2 Wizard: 8 frame */
@keyframes play-atk2-z {
    from { background-position: 0 0; }
    to   { background-position: -800% 0; }
}
.anim-attack2-z { animation: play-atk2-z 0.9s steps(8) 1 forwards; }

/* Hit Warrior: 3 frame */
@keyframes play-hit-w {
    from { background-position: 0 0; }
    to   { background-position: -300% 0; }
}
.anim-hit-w { animation: play-hit-w 0.5s steps(3) 1 forwards; }

/* Hit Wizard: 3 frame */
@keyframes play-hit-z {
    from { background-position: 0 0; }
    to   { background-position: -300% 0; }
}
.anim-hit-z { animation: play-hit-z 0.5s steps(3) 1 forwards; }

/* Death Warrior: 9 frame, freeze di akhir */
@keyframes play-death-w {
    from { background-position: 0 0; }
    to   { background-position: -900% 0; }
}
.anim-death-w { animation: play-death-w 1s steps(9) 1 forwards; }

/* Death Wizard: 8 frame */
@keyframes play-death-z {
    from { background-position: 0 0; }
    to   { background-position: -800% 0; }
}
.anim-death-z { animation: play-death-z 1s steps(8) 1 forwards; }

/* ============ SLASH OVERLAY ============ */
@keyframes slash-line {
    0% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(0); }
    20% { opacity: 1; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1); }
    100% { opacity: 0; transform: translate(-50%,-50%) rotate(var(--rot, -45deg)) scaleX(1.2); }
}
.slash-mark {
    position: absolute;
    top: 50%; left: 50%;
    width: 100px; height: 5px;
    background: linear-gradient(90deg, transparent, #fff, #FF4B4B, #fff, transparent);
    box-shadow: 0 0 20px #FF4B4B, 0 0 40px #FF4B4B;
    animation: slash-line 1s ease-out forwards;
    pointer-events: none;
    z-index: 10;
    border-radius: 3px;
}
.slash-mark.line-1 { --rot: -45deg; }
.slash-mark.line-2 { --rot: -30deg; width: 120px; animation-delay: 0.12s; }
.slash-mark.line-3 { --rot: -60deg; width: 85px; animation-delay: 0.24s; }

/* ============ DEFEND SHIELD ============ */
@keyframes guard-shield {
    0% { opacity: 0; transform: translate(-50%,-50%) scale(0.3); }
    25% { opacity: 1; transform: translate(-50%,-50%) scale(1.2); }
    60% { opacity: 1; transform: translate(-50%,-50%) scale(1); }
    100% { opacity: 0; transform: translate(-50%,-50%) scale(1.6); }
}
.shield-overlay {
    position: absolute;
    top: 50%; left: 50%;
    width: 130px; height: 130px;
    border-radius: 50%;
    border: 5px solid #4da6ff;
    box-shadow: 0 0 40px #4da6ff, inset 0 0 40px rgba(77,166,255,0.6);
    animation: guard-shield 1.5s ease-out forwards;
    pointer-events: none;
    z-index: 5;
}

/* ============ RUN / DODGE ============ */
@keyframes dodge-slide {
    0% { transform: translateX(0); opacity: 1; }
    30% { transform: translateX(-40px); opacity: 0.4; }
    60% { transform: translateX(-40px); opacity: 0.4; }
    100% { transform: translateX(0); opacity: 1; }
}
.dodge-anim { animation: dodge-slide 1.2s ease-in-out forwards; }

/* ============ MISS ============ */
@keyframes miss-fade {
    0% { opacity: 0; transform: translate(-50%,-50%) scale(0.5); }
    30% { opacity: 1; transform: translate(-50%,-50%) scale(1.2); }
    100% { opacity: 0; transform: translate(-50%,-100%) scale(1); }
}
.miss-pop {
    position: absolute;
    top: 50%; left: 50%;
    font-size: 28px; font-weight: 900;
    color: #4da6ff;
    text-shadow: 0 0 12px #4da6ff, 2px 2px 0 #000;
    animation: miss-fade 1.2s ease-out forwards;
    pointer-events: none;
    z-index: 11;
    letter-spacing: 2px;
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
    animation: pop-dmg 1.3s ease-out forwards;
    pointer-events: none; z-index: 9999;
}
.dmg-pop.defend { color: #4da6ff; text-shadow: 0 0 20px #4da6ff, 3px 3px 0 #000; }
.dmg-pop.dodge { color: #4da6ff; text-shadow: 0 0 20px #4da6ff, 3px 3px 0 #000; }

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

/* ============ KARTU AKSI ============ */
.kartu {
    border-radius: 10px;
    padding: 10px 4px;
    text-align: center;
    font-weight: 800;
    font-size: 12px;
    min-height: 60px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    border: 2px solid;
    transition: transform 0.15s ease;
}
.kartu:hover { transform: translateY(-3px); }
.kartu .icon { font-size: 20px; margin-bottom: 2px; }
.kartu .label { font-size: 11px; letter-spacing: 0.5px; }
.kartu-attack { border-color: #FF4B4B; background: linear-gradient(180deg, rgba(255,75,75,0.3), rgba(255,75,75,0.08)); color: #ff8080; }
.kartu-defend { border-color: #1C83E1; background: linear-gradient(180deg, rgba(28,131,225,0.3), rgba(28,131,225,0.08)); color: #66b8ff; }
.kartu-run    { border-color: #09AB3B; background: linear-gradient(180deg, rgba(9,171,59,0.3), rgba(9,171,59,0.08)); color: #3ddc6b; }

/* ============ TOMBOL ============ */
div[data-testid="stButton"] > button {
    width: 100%; border-radius: 10px; font-weight: 700; font-size: 12px;
    padding: 10px 0;
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

/* ============ LOG ============ */
.log-line {
    font-size: 11px;
    color: #ccc;
    padding: 4px 8px;
    border-bottom: 1px dashed #2a2a35;
}
.log-line.player { border-left: 3px solid #4ade80; }
.log-line.enemy  { border-left: 3px solid #ef4444; }
.log-line.system { border-left: 3px solid #FFD700; color: #FFD700; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='text-align:center; margin:0 0 8px 0; letter-spacing:1px;'>⚔️ SPIRIT ARENA</h3>", unsafe_allow_html=True)
# ============================================================
# BAGIAN 2: FUNGSI
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

def sprite_viewport(char_data, anim_state, side, counter, show_slash=False, show_shield=False, show_miss=False):
    """Render sprite sheet dengan animasi frame-by-frame."""
    frame_map = {
        "idle":    ("idle",     "w" if side == "ally" else "z"),
        "attack1": ("attack1",  "w" if side == "ally" else "z"),
        "attack2": ("attack2",  "w" if side == "ally" else "z"),
        "attack3": ("attack3",  "w"),
        "hit":     ("hit",      "w" if side == "ally" else "z"),
        "death":   ("death",    "w" if side == "ally" else "z"),
    }
    anim_key, suffix = frame_map.get(anim_state, ("idle", "w"))
    url = char_data.get(anim_key, char_data["idle"])
    anim_class = f"anim-{anim_key}-{suffix}"

    overlay = ""
    if show_slash:
        overlay += (
            f"<div class='slash-mark line-1 anim-{counter}'></div>"
            f"<div class='slash-mark line-2 anim-{counter}'></div>"
            f"<div class='slash-mark line-3 anim-{counter}'></div>"
        )
    if show_miss:
        overlay += f"<div class='miss-pop anim-{counter}'>MISS!</div>"
    if show_shield:
        overlay += f"<div class='shield-overlay anim-{counter}'></div>"

    return (
        f"<div class='sprite-viewport'>"
        f"{overlay}"
        f"<div class='sprite-anim {anim_class} anim-{counter}' "
        f"style='background-image:url(\"{url}\"); background-size: 1000% 100%;'></div>"
        f"</div>"
    )

def fighter_html(name, char_data, hp, max_hp, side,
                 anim_state="idle", show_slash=False, show_shield=False, show_miss=False, counter=0):
    hp_pct = hp / max_hp
    html = f"<div class='fighter {side}'>"
    html += sprite_viewport(char_data, anim_state, side, counter, show_slash, show_shield, show_miss)
    html += f"<div style='font-weight:700; font-size:12px; color:#fff; margin-bottom:6px;'>{name}</div>"
    html += bar_html("HP", hp, max_hp, hp_class(hp_pct))
    html += "</div>"
    return html

def buat_kartu():
    """Bikin 5 kartu random dari pool."""
    pool = ["attack", "attack", "attack", "defend", "run"]
    random.shuffle(pool)
    return pool

def buat_kartu_5():
    """5 kartu dengan komposisi 3 attack, 1 defend, 1 run, lalu di-shuffle."""
    kartu = ["attack", "attack", "attack", "defend", "run"]
    random.shuffle(kartu)
    return kartu

# ============================================================
# BAGIAN 3: STATE
# ============================================================
if "spirit_v1" not in st.session_state:
    st.session_state.player = {"nama": "Warrior", "hp": 150, "max_hp": 150, "atk": 22}
    st.session_state.enemy  = {"nama": "Evil Wizard", "hp": 200, "max_hp": 200, "atk": 18}
    st.session_state.round = 1
    st.session_state.kartu = buat_kartu_5()
    st.session_state.kartu_terpakai = []
    st.session_state.phase = "select"   # select | player_action | enemy_action | result | gameover
    st.session_state.log = ["⚔️ Pertarungan dimulai!"]
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    st.session_state.show_slash_enemy = False
    st.session_state.show_slash_player = False
    st.session_state.show_shield_player = False
    st.session_state.show_shield_enemy = False
    st.session_state.show_miss_player = False
    st.session_state.show_miss_enemy = False
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.anim_counter = 0
    st.session_state.player_defend = False  # apakah player sedang defend
    st.session_state.last_action = ""
    st.session_state.spirit_v1 = True

player = st.session_state.player
enemy = st.session_state.enemy
# ============================================================
# BAGIAN 4: LOGIKA AKSI
# ============================================================
def log(msg, kind="system"):
    st.session_state.log.append(f"__{kind}__{msg}")

def reset_efek():
    st.session_state.show_slash_enemy = False
    st.session_state.show_slash_player = False
    st.session_state.show_shield_player = False
    st.session_state.show_shield_enemy = False
    st.session_state.show_miss_player = False
    st.session_state.show_miss_enemy = False

def aksi_player(jenis):
    """Eksekusi aksi player: attack / defend / run."""
    reset_efek()
    st.session_state.anim_counter += 1

    if jenis == "attack":
        # Pilih random attack1/2/3
        varian = random.choice(["attack1", "attack2", "attack3"])
        st.session_state.player_anim = varian
        # Damage
        base = player["atk"] * random.uniform(0.9, 1.2)
        dmg = int(base)
        enemy["hp"] = max(0, enemy["hp"] - dmg)
        st.session_state.enemy_anim = "hit"
        st.session_state.show_slash_enemy = True
        st.session_state.damage_popup = f"-{dmg}"
        st.session_state.popup_type = ""
        log(f"🗡️ Warrior [{varian.upper()}]: {dmg} DMG ke Evil Wizard", "player")
        st.session_state.last_action = f"attack_{varian}"

    elif jenis == "defend":
        st.session_state.player_defend = True
        st.session_state.player_anim = "idle"
        st.session_state.show_shield_player = True
        st.session_state.damage_popup = "DEFEND"
        st.session_state.popup_type = "defend"
        log(f"🛡️ Warrior [DEFEND]: mengurangi damage 60% di giliran berikutnya", "player")
        st.session_state.last_action = "defend"

    elif jenis == "run":
        # 70% evade
        if random.random() < 0.70:
            st.session_state.show_miss_player = True
            st.session_state.damage_popup = "DODGE!"
            st.session_state.popup_type = "dodge"
            log(f"💨 Warrior [RUN]: berhasil menghindar dari serangan berikutnya!", "player")
            st.session_state.last_action = "run_success"
        else:
            log(f"💨 Warrior [RUN]: gagal menghindar!", "player")
            st.session_state.last_action = "run_fail"

def aksi_musuh():
    """Musuh menyerang / defend."""
    reset_efek()
    st.session_state.anim_counter += 1

    # Musuh pilih aksi random
    aksi = random.choice(["attack1", "attack2", "attack1", "attack2", "defend"])
    # Attack1 40%, Attack2 40%, Defend 20%
    roll = random.random()
    if roll < 0.40:
        aksi = "attack1"
    elif roll < 0.80:
        aksi = "attack2"
    else:
        aksi = "defend"

    if aksi in ["attack1", "attack2"]:
        st.session_state.enemy_anim = aksi

        # Cek apakah player defend / run sukses
        if st.session_state.get("last_action") == "run_success":
            # Player menghindar
            st.session_state.show_miss_player = True
            st.session_state.damage_popup = "MISS!"
            st.session_state.popup_type = "dodge"
            st.session_state.player_anim = "idle"
            log(f"💨 Evil Wizard [{aksi.upper()}]: **MISS!** Warrior menghindar.", "enemy")
            st.session_state.last_action = ""
            return

        base_dmg = enemy["atk"] * random.uniform(0.85, 1.2)
        dmg = int(base_dmg)

        # Kalau player defend, kurangi 60%
        if st.session_state.player_defend:
            dmg = int(dmg * 0.4)
            st.session_state.show_shield_player = True
            log(f"🛡️ Evil Wizard [{aksi.upper()}]: {dmg} DMG (dikurangi Defend)", "enemy")
            st.session_state.player_defend = False  # reset setelah dipakai
        else:
            log(f"🔥 Evil Wizard [{aksi.upper()}]: {dmg} DMG ke Warrior", "enemy")

        player["hp"] = max(0, player["hp"] - dmg)
        st.session_state.player_anim = "hit"
        st.session_state.show_slash_player = True
        st.session_state.damage_popup = f"-{dmg}"
        st.session_state.popup_type = ""
        st.session_state.last_action = ""

    else:  # defend
        st.session_state.enemy_anim = "idle"
        st.session_state.show_shield_enemy = True
        st.session_state.damage_popup = "GUARD"
        st.session_state.popup_type = "defend"
        log(f"🛡️ Evil Wizard [DEFEND]: bertahan", "enemy")
        st.session_state.last_action = ""

def reset_ronde():
    st.session_state.kartu = buat_kartu_5()
    st.session_state.kartu_terpakai = []
    st.session_state.player_anim = "idle"
    st.session_state.enemy_anim = "idle"
    reset_efek()
    st.session_state.damage_popup = ""
    st.session_state.popup_type = ""
    st.session_state.player_defend = False
    st.session_state.round += 1
    st.session_state.phase = "select"
  # ============================================================
# BAGIAN 5: RENDER ARENA
# ============================================================
# Cek death
if player["hp"] <= 0:
    st.session_state.player_anim = "death"
if enemy["hp"] <= 0:
    st.session_state.enemy_anim = "death"

arena_html = "<div class='arena-wrap'>"
arena_html += fighter_html(
    f"😈 {enemy['nama']}", WIZARD, enemy["hp"], enemy["max_hp"], "enemy",
    anim_state=st.session_state.enemy_anim,
    show_slash=st.session_state.show_slash_enemy,
    show_shield=st.session_state.show_shield_enemy,
    show_miss=st.session_state.show_miss_enemy,
    counter=st.session_state.anim_counter,
)
arena_html += fighter_html(
    f"⚔️ {player['nama']}", WARRIOR, player["hp"], player["max_hp"], "ally",
    anim_state=st.session_state.player_anim,
    show_slash=st.session_state.show_slash_player,
    show_shield=st.session_state.show_shield_player,
    show_miss=st.session_state.show_miss_player,
    counter=st.session_state.anim_counter,
)
arena_html += "</div>"
st.markdown(arena_html, unsafe_allow_html=True)

# Damage popup
if st.session_state.damage_popup:
    cls = "dmg-pop"
    if st.session_state.popup_type == "defend": cls += " defend"
    elif st.session_state.popup_type == "dodge": cls += " dodge"
    st.markdown(f"<div class='{cls}'>{st.session_state.damage_popup}</div>", unsafe_allow_html=True)

# Round banner
st.markdown(f"<div class='round-banner'>⚔️ RONDE {st.session_state.round} ⚔️</div>", unsafe_allow_html=True)

# ============================================================
# BAGIAN 6: KONTROL PER PHASE
# ============================================================
if player["hp"] <= 0:
    st.error(f"💀 GAME OVER! Warrior tumbang di Ronde {st.session_state.round}.")
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("spirit_v1"):
                del st.session_state[k]
        st.rerun()

elif enemy["hp"] <= 0:
    st.success(f"🎉 VICTORY! Evil Wizard tumbang di Ronde {st.session_state.round}!")
    st.balloons()
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("spirit_v1"):
                del st.session_state[k]
        st.rerun()

elif st.session_state.phase == "select":
    st.markdown("<div style='font-size:12px; color:#aaa; margin-bottom:6px;'>🃏 Pilih Kartu Aksi (5 kartu)</div>", unsafe_allow_html=True)

    # Render kartu 5 sejajar
    cols = st.columns(5)
    for idx, jenis in enumerate(st.session_state.kartu):
        with cols[idx]:
            terpakai = idx in st.session_state.kartu_terpakai
            if jenis == "attack":
                icon, label, cls = "🗡️", "Attack", "kartu-attack"
            elif jenis == "defend":
                icon, label, cls = "🛡️", "Defend", "kartu-defend"
            else:
                icon, label, cls = "💨", "Run", "kartu-run"

            st.markdown(
                f"<div class='kartu {cls}' style='opacity:{0.3 if terpakai else 1};'>"
                f"<div class='icon'>{icon}</div>"
                f"<div class='label'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            if st.button("Pilih", key=f"kartu_{idx}", disabled=terpakai, use_container_width=True):
                st.session_state.kartu_terpakai.append(idx)
                aksi_player(jenis)
                st.session_state.phase = "player_action"
                st.rerun()

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    if st.button("↺ Reset Kartu", use_container_width=True, disabled=len(st.session_state.kartu_terpakai) == 0):
        st.session_state.kartu_terpakai = []
        st.session_state.player_anim = "idle"
        reset_efek()
        st.rerun()

elif st.session_state.phase == "player_action":
    time.sleep(1.3)
    st.info("▶️ Aksi selesai. Tekan NEXT untuk giliran musuh.")
    if st.button("▶️  NEXT: GILIRAN MUSUH", use_container_width=True, type="primary"):
        reset_efek()
        st.session_state.damage_popup = ""
        st.session_state.player_anim = "idle"
        aksi_musuh()
        st.session_state.phase = "enemy_action"
        st.rerun()

elif st.session_state.phase == "enemy_action":
    time.sleep(1.3)
    st.warning("▶️ Musuh selesai. Tekan NEXT untuk ronde baru.")
    if st.button("▶️  NEXT: RONDE BARU", use_container_width=True, type="primary"):
        reset_efek()
        st.session_state.damage_popup = ""
        st.session_state.enemy_anim = "idle"
        reset_ronde()
        st.rerun()

# ============================================================
# BAGIAN 7: LOG
# ============================================================
st.markdown("---")
st.markdown("<div style='font-size:12px; color:#FFD700; margin-bottom:4px;'>📜 Log Pertarungan</div>", unsafe_allow_html=True)
with st.container(border=True):
    for line in reversed(st.session_state.log[-15:]):
        if line.startswith("__player__"):
            st.markdown(f"<div class='log-line player'>{line[10:]}</div>", unsafe_allow_html=True)
        elif line.startswith("__enemy__"):
            st.markdown(f"<div class='log-line enemy'>{line[9:]}</div>", unsafe_allow_html=True)
        elif line.startswith("__system__"):
            st.markdown(f"<div class='log-line system'>{line[10:]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='log-line'>{line}</div>", unsafe_allow_html=True)
