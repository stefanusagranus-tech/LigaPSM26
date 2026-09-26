import streamlit as st
import random

st.set_page_config(page_title="FGO Arena JRPG", layout="centered", initial_sidebar_state="collapsed")

# ============================================================
# CSS GLOBAL
# ============================================================
st.markdown("""
<style>
    /* Sembunyikan header Streamlit biar lebih immersive */
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 720px; }

    /* -------- ARENA FIGHTER -------- */
    .arena-wrap {
        display: flex;
        gap: 10px;
        margin-bottom: 8px;
    }
    .fighter {
        flex: 1;
        background: linear-gradient(180deg, #1a1a24 0%, #0f0f16 100%);
        border: 2px solid #2e2e3e;
        border-radius: 12px;
        padding: 10px 8px;
        text-align: center;
        position: relative;
        box-shadow: 0 0 12px rgba(255,75,75,0.08);
    }
    .fighter.enemy { border-color: #5a1f1f; box-shadow: 0 0 12px rgba(255,75,75,0.18); }
    .fighter.ally  { border-color: #1f3a5a; box-shadow: 0 0 12px rgba(28,131,225,0.18); }

    .sprite { font-size: 64px; line-height: 1; margin: 4px 0 6px 0; filter: drop-shadow(0 0 6px rgba(255,255,255,0.15)); }
    .fname  { font-weight: 700; font-size: 13px; color: #fff; margin-bottom: 8px; letter-spacing: 0.5px; }

    /* -------- HP / NP BAR CUSTOM -------- */
    .bar-wrap {
        background: #0a0a10;
        border: 1px solid #333;
        border-radius: 6px;
        height: 16px;
        overflow: hidden;
        margin: 3px 0;
        position: relative;
    }
    .bar-fill {
        height: 100%;
        transition: width 0.4s ease;
        border-radius: 6px 0 0 6px;
    }
    .hp-high { background: linear-gradient(90deg, #09AB3B, #4ade80); }
    .hp-mid  { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
    .hp-low  { background: linear-gradient(90deg, #dc2626, #ff4b4b); }
    .np-fill { background: linear-gradient(90deg, #7c3aed, #c084fc); }

    .bar-label {
        font-size: 10px;
        color: #bbb;
        text-align: left;
        margin: 2px 0 4px 0;
        font-family: monospace;
    }

    /* -------- ACTION BUBBLE -------- */
    .bubble {
        display: inline-block;
        background: #ff9800;
        color: #111;
        font-weight: 700;
        font-size: 10px;
        padding: 3px 8px;
        border-radius: 10px;
        margin-top: 4px;
    }
    .bubble.enemy { background: #ef4444; color: #fff; }

    /* -------- ROUND BANNER -------- */
    .round-banner {
        background: linear-gradient(90deg, #FF4B4B, #FFD700, #FF4B4B);
        background-size: 200% 100%;
        animation: shine 3s linear infinite;
        color: #111;
        text-align: center;
        font-weight: 800;
        font-size: 15px;
        padding: 6px;
        border-radius: 8px;
        margin: 12px 0;
        letter-spacing: 2px;
    }
    @keyframes shine {
        0% { background-position: 0% 50%; }
        100% { background-position: 200% 50%; }
    }

    /* -------- SLOT COMBO -------- */
    .slot {
        border-radius: 8px;
        height: 34px;
        text-align: center;
        line-height: 34px;
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 0.5px;
    }
    .slot-empty { border: 2px dashed #3a3a4a; color: #555; background: rgba(255,255,255,0.02); }
    .slot-buster { border: 2px solid #FF4B4B; background: rgba(255,75,75,0.18); color: #FF4B4B; box-shadow: 0 0 8px rgba(255,75,75,0.3); }
    .slot-arts   { border: 2px solid #1C83E1; background: rgba(28,131,225,0.18); color: #4da6ff; box-shadow: 0 0 8px rgba(28,131,225,0.3); }
    .slot-quick  { border: 2px solid #09AB3B; background: rgba(9,171,59,0.18); color: #22d364; box-shadow: 0 0 8px rgba(9,171,59,0.3); }

    /* -------- PREDIKSI BOX -------- */
    .predict {
        background: linear-gradient(90deg, #262730, #1a1a24);
        border-left: 4px solid #FFD700;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        color: #ddd;
        margin: 6px 0;
    }

    /* -------- TOMBOL KARTU AKSI (override st.button) -------- */
    div[data-testid="stButton"] > button {
        width: 100%;
        border-radius: 10px;
        font-weight: 700;
        font-size: 13px;
        padding: 10px 0;
        transition: transform 0.1s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-2px);
    }

    /* Kartu warna: kita pakai wrapper div dengan class khusus */
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
    .card-quick div[data-testid="stButton"] > button:disabled {
        opacity: 0.35;
    }

    /* Tombol utama SERANG */
    .btn-execute div[data-testid="stButton"] > button {
        background: linear-gradient(90deg, #FF4B4B, #FFD700) !important;
        color: #111 !important;
        border: none !important;
        font-size: 15px !important;
        font-weight: 800 !important;
        letter-spacing: 1px;
        padding: 12px 0 !important;
        box-shadow: 0 0 15px rgba(255,75,75,0.4);
    }
    .btn-reset div[data-testid="stButton"] > button {
        background: transparent !important;
        color: #aaa !important;
        border: 1px solid #444 !important;
        font-size: 11px !important;
    }

    /* -------- LOG BOX -------- */
    .log-line {
        font-size: 11px;
        color: #ccc;
        padding: 3px 0;
        border-bottom: 1px dashed #2a2a35;
    }

    /* Responsive mobile */
    @media (max-width: 640px) {
        .sprite { font-size: 48px; }
        .fname { font-size: 11px; }
        div[data-testid="stButton"] > button { font-size: 11px; padding: 8px 0; }
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h3 style='text-align:center; margin:0 0 8px 0; letter-spacing:1px;'>🛡️ FGO ARENA</h3>", unsafe_allow_html=True)

# ============================================================
# FUNGSI
# ============================================================
def acak_5_kartu():
    return [random.choice(["Buster", "Arts", "Quick"]) for _ in range(5)]

def hp_class(pct):
    if pct > 0.5: return "hp-high"
    if pct > 0.25: return "hp-mid"
    return "hp-low"

def render_bar(label, value, max_value, fill_class, extra_class=""):
    pct = max(0, min(100, int(value / max_value * 100)))
    return f"""
    <div class='bar-label'>{label} {value}/{max_value}</div>
    <div class='bar-wrap'>
        <div class='bar-fill {fill_class} {extra_class}' style='width:{pct}%;'></div>
    </div>
    """

# ============================================================
# STATE
# ============================================================
if "fgo_v7_init" not in st.session_state:
    st.session_state.servant = {"nama": "Mash (Shielder)", "hp": 150, "max_hp": 150, "np": 0, "max_np": 100, "atk": 22, "emoji": "🛡️"}
    st.session_state.boss = {"nama": "Goetia", "hp": 350, "max_hp": 350, "atk": 20, "emoji": "👹"}
    st.session_state.round = 1
    st.session_state.boss_last_action = "Bersiap"
    st.session_state.kartu_tersedia = acak_5_kartu()
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.battle_log = ["⚔️ Pertandingan dimulai! Susun strategi kombo Anda."]
    st.session_state.game_over = False
    st.session_state.fgo_v7_init = True

servant = st.session_state.servant
boss = st.session_state.boss

# ============================================================
# LOGIKA
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

def eksekusi():
    log_turn = [f"🔄 **Ronde {st.session_state.round}**"]
    combo = st.session_state.antrean_combo
    is_chain = len(set(combo)) == 1

    for i, tipe in enumerate(combo):
        mult = 1.0 + (i * 0.25)
        if tipe == "Buster":
            dmg = int(servant["atk"] * (2.2 if is_chain else 1.6) * mult + random.randint(-2, 2))
            boss["hp"] = max(0, boss["hp"] - dmg)
            log_turn.append(f"🔴 Hit {i+1} [Buster]: **{dmg} DMG**")
        elif tipe == "Arts":
            dmg = int(servant["atk"] * 1.0 * mult)
            gain = 40 if is_chain else 25
            boss["hp"] = max(0, boss["hp"] - dmg)
            servant["np"] = min(servant["max_np"], servant["np"] + gain)
            log_turn.append(f"🔵 Hit {i+1} [Arts]: {dmg} DMG (+{gain}% NP)")
        elif tipe == "Quick":
            dmg = int(servant["atk"] * 0.9 * mult)
            servant["np"] = min(servant["max_np"], servant["np"] + 12)
            boss["hp"] = max(0, boss["hp"] - dmg)
            log_turn.append(f"🟢 Hit {i+1} [Quick]: {dmg} DMG (+12% NP)")

    if boss["hp"] > 0:
        aksi = random.choice(["Tebasan Kegelapan", "Mengaum (Buff ATK)", "Kuda-Kuda Bertahan"])
        st.session_state.boss_last_action = aksi
        if aksi == "Tebasan Kegelapan":
            d = int(boss["atk"] * random.uniform(0.9, 1.3))
            servant["hp"] = max(0, servant["hp"] - d)
            log_turn.append(f"😈 **{boss['nama']}** *{aksi}* (-{d} HP)")
        elif aksi == "Mengaum (Buff ATK)":
            boss["atk"] += 2
            log_turn.append(f"😈 **{boss['nama']}** *Mengaum* (+2 ATK)")
        else:
            d = int(boss["atk"] * 0.6)
            servant["hp"] = max(0, servant["hp"] - d)
            log_turn.append(f"😈 **{boss['nama']}** *Bertahan* (-{d} HP)")
    else:
        st.session_state.boss_last_action = "Tumbang"

    st.session_state.round += 1
    st.session_state.battle_log.extend(log_turn)
    st.session_state.antrean_combo = []
    st.session_state.indeks_terpakai = []
    st.session_state.kartu_tersedia = acak_5_kartu()

# ============================================================
# RENDER ARENA
# ============================================================
hp_pct_boss = boss["hp"] / boss["max_hp"]
hp_pct_serv = servant["hp"] / servant["max_hp"]

st.markdown(f"""
<div class='arena-wrap'>
    <div class='fighter enemy'>
        <div class='sprite'>{boss['emoji']}</div>
        <div class='fname'>😈 {boss['nama']}</div>
        {render_bar("HP", boss['hp'], boss['max_hp'], hp_class(hp_pct_boss))}
        <div class='bubble enemy'>Aksi: {st.session_state.boss_last_action}</div>
    </div>
    <div class='fighter ally'>
        <div class='sprite'>{servant['emoji']}</div>
        <div class='fname'>🛡️ {servant['nama']}</div>
        {render_bar("HP", servant['hp'], servant['max_hp'], hp_class(hp_pct_serv))}
        {render_bar("NP", servant['np'], servant['max_np'], 'np-fill')}
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# RONDE & GAME OVER
# ============================================================
st.markdown(f"<div class='round-banner'>⚔️ RONDE {st.session_state.round} ⚔️</div>", unsafe_allow_html=True)

if servant["hp"] <= 0 or boss["hp"] <= 0:
    st.session_state.game_over = True

if st.session_state.game_over:
    if servant["hp"] <= 0:
        st.error(f"💀 GAME OVER! Bertahan hingga Ronde {st.session_state.round - 1}.")
    else:
        st.success(f"🎉 VICTORY! Menang di Ronde {st.session_state.round - 1}!")
        st.balloons()
    if st.button("🔄 Main Lagi", use_container_width=True, type="primary"):
        for k in list(st.session_state.keys()):
            if k.startswith("fgo_v7"):
                del st.session_state[k]
        st.rerun()
else:
    # -------- SLOT COMBO --------
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

    # -------- PREDIKSI --------
    pred = hitung_prediksi_dmg(st.session_state.antrean_combo)
    sisa = max(0, boss["hp"] - pred)
    st.markdown(f"""
    <div class='predict'>
        📊 Prediksi: <b style='color:#FFD700;'>{pred} DMG</b> &nbsp;·&nbsp; Sisa HP Boss: <b>{sisa}</b>
    </div>
    """, unsafe_allow_html=True)

    # -------- KARTU AKSI --------
    st.markdown("<div style='font-size:12px; color:#aaa; margin:6px 0 4px 0;'>🃏 Pilih Kartu Aksi</div>", unsafe_allow_html=True)
    cols = st.columns(5)
    for idx, tipe in enumerate(st.session_state.kartu_tersedia):
        with cols[idx]:
            wrap_class = f"card-{tipe.lower()}"
            st.markdown(f"<div class='{wrap_class}'>", unsafe_allow_html=True)
            disabled = (idx in st.session_state.indeks_terpakai) or (len(st.session_state.antrean_combo) >= 3)
            if st.button(tipe, key=f"k_{idx}", disabled=disabled, use_container_width=True):
                st.session_state.antrean_combo.append(tipe)
                st.session_state.indeks_terpakai.append(idx)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # -------- TOMBOL AKSI --------
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns([3, 1])
    with b1:
        st.markdown("<div class='btn-execute'>", unsafe_allow_html=True)
        if st.button("⚔️  SERANG!", use_container_width=True, disabled=len(st.session_state.antrean_combo) != 3):
            eksekusi()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with b2:
        st.markdown("<div class='btn-reset'>", unsafe_allow_html=True)
        if st.button("↺ Reset", use_container_width=True, disabled=len(st.session_state.antrean_combo) == 0):
            st.session_state.antrean_combo = []
            st.session_state.indeks_terpakai = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# LOG
# ============================================================
with st.expander("📜 Log Pertarungan", expanded=False):
    for log in reversed(st.session_state.battle_log[-8:]):
        st.markdown(f"<div class='log-line'>{log}</div>", unsafe_allow_html=True)
