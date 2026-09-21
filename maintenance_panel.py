"""
maintenance_panel.py
====================
Panel info "Under Maintenance" / Update / Info untuk halaman Menu Utama.

Cara pakai:
    from maintenance_panel import render_maintenance_panel
    render_maintenance_panel()
    
Kustomisasi:
    Edit CONFIG di bawah, atau pass parameter saat panggil.
"""
import streamlit as st


# =========================================================================
# 🎛️ KONFIGURASI DEFAULT
# =========================================================================
# Edit di sini untuk ubah konten panel.
# Kalau mau beda per-panggilan, pass parameter saat panggil fungsi.
# =========================================================================
DEFAULT_CONFIG = {
    "show": True,                    # True = tampil, False = sembunyi
    "type": "update",                # "update" | "maintenance" | "info" | "warning"
    "title": "SEDANG UPDATE FITUR BARU!",
    "message": "Sistem sedang ditingkatkan untuk pengalaman yang lebih baik. Beberapa fitur mungkin belum stabil, mohon maklum ya! 🙏",
    "eta": "Target selesai: Hari ini, 22:00 WIB",
    "progress": 75,                  # 0-100, atau None kalau tidak ada
    "show_animasi": True,            # True = animasi lengkap
    "badge_text": "LIVE UPDATE",     # Teks kecil di kiri atas
}


# =========================================================================
# 🎨 TEMA WARNA
# =========================================================================
_THEMES = {
    "update": {
        "primary": "#3b82f6",
        "secondary": "#60a5fa",
        "bg": "linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(96, 165, 250, 0.08))",
        "border": "#3b82f6",
        "icon": "🚀",
    },
    "maintenance": {
        "primary": "#f59e0b",
        "secondary": "#fbbf24",
        "bg": "linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(251, 191, 36, 0.08))",
        "border": "#f59e0b",
        "icon": "🔧",
    },
    "info": {
        "primary": "#10b981",
        "secondary": "#34d399",
        "bg": "linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(52, 211, 153, 0.08))",
        "border": "#10b981",
        "icon": "ℹ️",
    },
    "warning": {
        "primary": "#ef4444",
        "secondary": "#f87171",
        "bg": "linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(248, 113, 113, 0.08))",
        "border": "#ef4444",
        "icon": "⚠️",
    },
}


# =========================================================================
# ⚡ CSS ANIMASI (di-inject sekali saja per render)
# =========================================================================
def _inject_animation_css():
    st.markdown(
        """
        <style>
            /* Pulse glow — panel menyala redup-terang */
            @keyframes mp_pulse_glow {
                0%, 100% { 
                    box-shadow: 0 0 8px var(--mp-glow), inset 0 0 8px rgba(0,0,0,0.3);
                }
                50% { 
                    box-shadow: 0 0 24px var(--mp-glow), 0 0 40px var(--mp-glow), inset 0 0 12px rgba(0,0,0,0.5);
                }
            }
            
            /* Icon float — emoji naik-turun */
            @keyframes mp_icon_float {
                0%, 100% { transform: translateY(0) rotate(0deg); }
                50% { transform: translateY(-4px) rotate(8deg); }
            }
            
            /* Shimmer text — judul berkilau */
            @keyframes mp_shimmer_slide {
                0% { background-position: -200% center; }
                100% { background-position: 200% center; }
            }
            
            /* Progress stripe — garis berjalan */
            @keyframes mp_progress_stripe {
                0% { background-position: 0 0; }
                100% { background-position: 40px 0; }
            }
            
            /* Blinking dot — titik live berkedip */
            @keyframes mp_blink_dot {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.3; transform: scale(0.7); }
            }
            
            /* Slide in dari atas */
            @keyframes mp_slide_in {
                0% { 
                    opacity: 0; 
                    transform: translateY(-20px);
                    filter: blur(4px);
                }
                100% { 
                    opacity: 1; 
                    transform: translateY(0);
                    filter: blur(0);
                }
            }
            
            /* Icon spin pelan */
            @keyframes mp_spin_slow {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
            
            .mp-panel {
                animation: mp_pulse_glow 3s infinite ease-in-out, 
                           mp_slide_in 0.6s cubic-bezier(0.25, 1, 0.5, 1);
            }
            
            .mp-icon {
                animation: mp_icon_float 2s infinite ease-in-out;
                display: inline-block;
            }
            
            .mp-label-shimmer {
                background: linear-gradient(
                    90deg, 
                    var(--mp-secondary) 0%, 
                    #ffffff 25%, 
                    var(--mp-secondary) 50%, 
                    #ffffff 75%, 
                    var(--mp-secondary) 100%
                );
                background-size: 200% auto;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                animation: mp_shimmer_slide 3s linear infinite;
            }
            
            .mp-live-dot {
                display: inline-block;
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: var(--mp-primary);
                box-shadow: 0 0 8px var(--mp-primary), 0 0 15px var(--mp-primary);
                animation: mp_blink_dot 1.5s infinite ease-in-out;
                margin-right: 5px;
                vertical-align: middle;
            }
            
            .mp-progress-bar {
                position: relative;
                overflow: hidden;
                background: rgba(0, 0, 0, 0.35);
                border-radius: 5px;
                height: 8px;
                margin-top: 10px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            
            .mp-progress-bar::after {
                content: "";
                position: absolute;
                inset: 0;
                background-image: linear-gradient(
                    45deg,
                    rgba(255,255,255,0.15) 25%,
                    transparent 25%,
                    transparent 50%,
                    rgba(255,255,255,0.15) 50%,
                    rgba(255,255,255,0.15) 75%,
                    transparent 75%,
                    transparent
                );
                background-size: 40px 40px;
                animation: mp_progress_stripe 1s linear infinite;
                pointer-events: none;
            }
            
            .mp-spinner {
                display: inline-block;
                animation: mp_spin_slow 3s linear infinite;
            }
            
            /* Responsive: kecilkan di HP */
            @media (max-width: 768px) {
                .mp-panel {
                    padding: 12px 14px !important;
                }
                .mp-title {
                    font-size: 13px !important;
                }
                .mp-message {
                    font-size: 10.5px !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================================
# 🎨 RENDER PANEL
# =========================================================================
def render_maintenance_panel(
    show=None,
    type=None,
    title=None,
    message=None,
    eta=None,
    progress=None,
    show_animasi=None,
    badge_text=None,
):
    """
    Render panel info "Under Maintenance" / Update.
    
    Semua parameter opsional. Kalau tidak di-pass, ambil dari DEFAULT_CONFIG.
    """
    cfg = DEFAULT_CONFIG.copy()
    if show is not None: cfg["show"] = show
    if type is not None: cfg["type"] = type
    if title is not None: cfg["title"] = title
    if message is not None: cfg["message"] = message
    if eta is not None: cfg["eta"] = eta
    if progress is not None: cfg["progress"] = progress
    if show_animasi is not None: cfg["show_animasi"] = show_animasi
    if badge_text is not None: cfg["badge_text"] = badge_text
    
    if not cfg["show"]:
        return
    
    t = _THEMES.get(cfg["type"], _THEMES["info"])
    
    # Inject CSS animasi
    if cfg["show_animasi"]:
        _inject_animation_css()
    
    # Progress bar
    _progress_html = ""
    if cfg["progress"] is not None:
        _p = max(0, min(100, cfg["progress"]))
        _progress_html = f"""
        <div class="mp-progress-bar">
            <div style="
                height: 100%;
                width: {_p}%;
                background: linear-gradient(90deg, {t['primary']}, {t['secondary']});
                box-shadow: 0 0 10px {t['primary']}, 0 0 20px {t['primary']}80;
                border-radius: 5px;
                transition: width 0.8s cubic-bezier(0.25, 1, 0.5, 1);
                position: relative;
                z-index: 2;
            "></div>
        </div>
        <div style="
            font-family: 'Courier New', monospace;
            font-size: 10px;
            color: {t['secondary']};
            text-align: right;
            margin-top: 4px;
            font-weight: 900;
            letter-spacing: 0.5px;
        ">{_p}% SELESAI</div>
        """
    
    # Ornamen sudut (kecil)
    _corner_html = f"""
    <div style="position: absolute; top: 6px; right: 10px; color: {t['primary']}; font-size: 10px; opacity: 0.6;">⚜</div>
    <div style="position: absolute; bottom: 6px; right: 10px; color: {t['primary']}; font-size: 10px; opacity: 0.6;">⚜</div>
    """
    
    _html = f"""
    <div class="mp-panel" style="
        --mp-primary: {t['primary']};
        --mp-secondary: {t['secondary']};
        --mp-glow: {t['primary']}80;
        background: {t['bg']};
        border: 1.5px solid {t['border']};
        border-left: 5px solid {t['primary']};
        border-radius: 12px;
        padding: 16px 18px 14px 18px;
        margin: 15px auto 20px auto;
        max-width: 100%;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
    ">
        {_corner_html}
        
        <!-- Garis emas atas -->
        <div style="
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, {t['primary']}, {t['secondary']}, {t['primary']}, transparent);
            box-shadow: 0 0 10px {t['primary']};
        "></div>
        
        <!-- Header: label + icon -->
        <div style="
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        ">
            <div style="
                font-family: 'Courier New', monospace;
                font-size: 10px;
                font-weight: 900;
                color: {t['secondary']};
                letter-spacing: 2px;
                display: flex;
                align-items: center;
            ">
                <span class="mp-live-dot"></span>
                <span class="mp-label-shimmer">{cfg['badge_text']}</span>
            </div>
            <div class="mp-icon" style="font-size: 22px; filter: drop-shadow(0 0 8px {t['primary']});">
                {t['icon']}
            </div>
        </div>
        
        <!-- Judul -->
        <div class="mp-title" style="
            font-family: 'Cinzel', 'Georgia', serif;
            font-size: 16px;
            font-weight: 900;
            color: #ffffff;
            letter-spacing: 1px;
            margin-bottom: 8px;
            line-height: 1.3;
            text-shadow: 0 0 10px {t['primary']}80, 1px 1px 2px rgba(0,0,0,0.8);
        ">
            {t['icon']} {cfg['title']}
        </div>
        
        <!-- Pesan -->
        <div class="mp-message" style="
            font-family: 'Quicksand', 'Courier New', sans-serif;
            font-size: 12px;
            color: #e2e8f0;
            line-height: 1.6;
            margin-bottom: 10px;
            font-weight: 600;
        ">
            {cfg['message']}
        </div>
        
        <!-- ETA -->
        <div style="
            font-family: 'Courier New', monospace;
            font-size: 10.5px;
            color: {t['secondary']};
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            background: rgba(0, 0, 0, 0.25);
            border-radius: 6px;
            border-left: 3px solid {t['primary']};
            margin-bottom: 4px;
        ">
            <span class="mp-spinner">⏳</span>
            <span>{cfg['eta']}</span>
        </div>
        
        {_progress_html}
    </div>
    """
    
    st.markdown(_html, unsafe_allow_html=True)
