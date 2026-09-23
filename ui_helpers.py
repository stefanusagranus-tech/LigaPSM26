"""
ui_helpers.py
=============
Utility untuk UI: splash screen, HTML escape, responsive helpers, dll.

Fitur:
    render_splash_screen(title, subtitle, duration_ms)
    escape_html(text)
    safe_html(*parts)
    show_loading_overlay(text)

Author: LigaPSM Team
Version: 1.0
"""

import streamlit as st
import streamlit.components.v1 as components
import html as _html_module


# =========================================================================
# 🎬 SPLASH SCREEN
# =========================================================================
def render_splash_screen(
    title="MEMUAT DATA GUILD",
    subtitle="Menyiapkan portal & menyinkronkan arsip...",
    icon="🔮",
    duration_ms=2000,
    session_key=None,
):
    """
    Tampilkan splash screen animasi medieval fantasy.
    
    Args:
        title (str): Judul splash
        subtitle (str): Subjudul
        icon (str): Emoji icon utama
        duration_ms (int): Durasi auto-hide (ms). 0 = tidak auto-hide
        session_key (str): Kalau diisi, splash cuma muncul sekali per session.
    
    Returns:
        placeholder object (bisa di-.empty() manual)
    """
    # Kalau pakai session_key, cek apakah sudah pernah tampil
    if session_key:
        _shown_key = f"_splash_shown_{session_key}"
        if st.session_state.get(_shown_key, False):
            return None  # Skip kalau sudah tampil
        st.session_state[_shown_key] = True
    
    _placeholder = st.empty()
    
    _splash_html = _build_splash_html(title, subtitle, icon, duration_ms)
    
    with _placeholder:
        components.html(_splash_html, height=100, scrolling=False)
        # CSS overlay fullscreen lewat markdown
        st.markdown(
            _build_splash_overlay_css(),
            unsafe_allow_html=True,
        )
    
    return _placeholder


def _build_splash_html(title, subtitle, icon, duration_ms):
    """Bangun HTML splash screen."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        .splash-overlay {{
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            z-index: 999999;
            background: radial-gradient(ellipse at top, #1e3a5f 0%, #0f172a 50%, #05070c 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Courier New', monospace;
            overflow: hidden;
            animation: splashFadeIn 0.5s ease-out;
        }}
        
        @keyframes splashFadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        @keyframes splashFadeOut {{
            from {{ opacity: 1; }}
            to {{ opacity: 0; visibility: hidden; }}
        }}
        
        .splash-overlay.hide {{
            animation: splashFadeOut 0.5s ease-out forwards;
        }}
        
        /* Ornamen Sudut */
        .splash-corner {{
            position: absolute;
            color: #d4af37;
            font-size: 22px;
            opacity: 0.7;
            filter: drop-shadow(0 0 8px rgba(212, 175, 55, 0.8));
            animation: cornerPulse 3s infinite ease-in-out;
        }}
        .splash-corner-tl {{ top: 20px; left: 20px; }}
        .splash-corner-tr {{ top: 20px; right: 20px; }}
        .splash-corner-bl {{ bottom: 20px; left: 20px; }}
        .splash-corner-br {{ bottom: 20px; right: 20px; }}
        
        @keyframes cornerPulse {{
            0%, 100% {{ opacity: 0.5; transform: scale(1); }}
            50% {{ opacity: 1; transform: scale(1.15); }}
        }}
        
        /* Sparkles */
        .spark {{
            position: absolute;
            color: #fbbf24;
            font-size: 16px;
            filter: drop-shadow(0 0 6px #fbbf24);
            animation: sparkFloat 3s infinite ease-in-out;
        }}
        .spark-1 {{ top: 20%; left: 25%; animation-delay: 0s; }}
        .spark-2 {{ top: 25%; right: 22%; animation-delay: 0.5s; }}
        .spark-3 {{ bottom: 25%; left: 20%; animation-delay: 1s; }}
        .spark-4 {{ bottom: 28%; right: 24%; animation-delay: 1.5s; }}
        
        @keyframes sparkFloat {{
            0%, 100% {{ transform: translateY(0) scale(0.8) rotate(0deg); opacity: 0.4; }}
            50% {{ transform: translateY(-15px) scale(1.3) rotate(180deg); opacity: 1; }}
        }}
        
        /* Portal Animasi */
        .portal-wrapper {{
            position: relative;
            width: 180px; height: 180px;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 30px;
        }}
        
        .portal-ring-1 {{
            position: absolute;
            width: 180px; height: 180px;
            border: 2px dashed #d4af37;
            border-radius: 50%;
            animation: spinCW 8s infinite linear;
            filter: drop-shadow(0 0 10px rgba(212, 175, 55, 0.7));
        }}
        .portal-ring-2 {{
            position: absolute;
            width: 130px; height: 130px;
            border: 2px dotted #38bdf8;
            border-radius: 50%;
            animation: spinCCW 5s infinite linear;
            filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.7));
        }}
        .portal-ring-3 {{
            position: absolute;
            width: 80px; height: 80px;
            border: 2px solid #fbbf24;
            border-radius: 50%;
            animation: pulseRing 2s infinite ease-in-out;
            filter: drop-shadow(0 0 15px rgba(251, 191, 36, 0.9));
        }}
        .portal-icon {{
            position: absolute;
            font-size: 45px;
            filter: drop-shadow(0 0 15px rgba(212, 175, 55, 0.9));
            animation: iconFloat 2.5s infinite ease-in-out;
        }}
        
        @keyframes spinCW {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
        @keyframes spinCCW {{ from {{ transform: rotate(360deg); }} to {{ transform: rotate(0deg); }} }}
        @keyframes pulseRing {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.15); opacity: 0.7; }}
        }}
        @keyframes iconFloat {{
            0%, 100% {{ transform: translateY(0) scale(1); }}
            50% {{ transform: translateY(-8px) scale(1.08); }}
        }}
        
        /* Text */
        .splash-title {{
            color: #fbbf24;
            font-size: 22px;
            font-weight: 900;
            letter-spacing: 3px;
            margin-bottom: 10px;
            text-shadow: 0 0 15px rgba(251, 191, 36, 0.8), 0 0 30px rgba(251, 191, 36, 0.4);
            animation: titleBlink 1.5s infinite ease-in-out;
            text-align: center;
            padding: 0 20px;
        }}
        
        @keyframes titleBlink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
        }}
        
        .splash-subtitle {{
            color: #94a3b8;
            font-size: 12px;
            margin-bottom: 30px;
            font-style: italic;
            letter-spacing: 0.5px;
            text-align: center;
            padding: 0 20px;
        }}
        
        /* Loading Dots */
        .loading-dots {{
            display: flex;
            gap: 8px;
            justify-content: center;
            margin-top: 20px;
        }}
        .loading-dots span {{
            width: 10px; height: 10px;
            background: #d4af37;
            border-radius: 50%;
            box-shadow: 0 0 10px #d4af37;
            animation: dotBounce 1.4s infinite ease-in-out;
        }}
        .loading-dots span:nth-child(2) {{
            animation-delay: 0.2s;
            background: #38bdf8;
            box-shadow: 0 0 10px #38bdf8;
        }}
        .loading-dots span:nth-child(3) {{
            animation-delay: 0.4s;
            background: #10b981;
            box-shadow: 0 0 10px #10b981;
        }}
        @keyframes dotBounce {{
            0%, 80%, 100% {{ transform: scale(0.6); opacity: 0.4; }}
            40% {{ transform: scale(1.2); opacity: 1; }}
        }}
        
        /* Progress Bar */
        .progress-bar-wrapper {{
            width: 280px; height: 8px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid #d4af37;
            border-radius: 5px;
            overflow: hidden;
            margin-top: 25px;
            box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.8);
        }}
        .progress-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #78350f, #d4af37, #fbbf24, #d4af37, #78350f);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite linear;
            border-radius: 5px;
        }}
        @keyframes shimmer {{
            0% {{ background-position: 0% 50%; }}
            100% {{ background-position: 200% 50%; }}
        }}
        
        @media (max-width: 480px) {{
            .portal-wrapper {{ width: 140px; height: 140px; }}
            .portal-ring-1 {{ width: 140px; height: 140px; }}
            .portal-ring-2 {{ width: 100px; height: 100px; }}
            .portal-ring-3 {{ width: 60px; height: 60px; }}
            .portal-icon {{ font-size: 35px; }}
            .splash-title {{ font-size: 18px; letter-spacing: 2px; }}
            .splash-subtitle {{ font-size: 11px; }}
            .progress-bar-wrapper {{ width: 220px; }}
        }}
    </style>
    </head>
    <body>
        <div class="splash-corner splash-corner-tl">⚜️</div>
        <div class="splash-corner splash-corner-tr">⚜️</div>
        <div class="splash-corner splash-corner-bl">⚜️</div>
        <div class="splash-corner splash-corner-br">⚜️</div>
        
        <div class="spark spark-1">✦</div>
        <div class="spark spark-2">✦</div>
        <div class="spark spark-3">✦</div>
        <div class="spark spark-4">✦</div>
        
        <div class="portal-wrapper">
            <div class="portal-ring-1"></div>
            <div class="portal-ring-2"></div>
            <div class="portal-ring-3"></div>
            <div class="portal-icon">{icon}</div>
        </div>
        
        <div class="splash-title">{title}</div>
        <div class="splash-subtitle">{subtitle}</div>
        
        <div class="loading-dots">
            <span></span><span></span><span></span>
        </div>
        
        <div class="progress-bar-wrapper">
            <div class="progress-bar-fill"></div>
        </div>
        
        <script>
            {"" if duration_ms <= 0 else f'''
            setTimeout(function() {{
                var overlay = document.querySelector(".splash-overlay");
                if (overlay) overlay.classList.add("hide");
            }}, {duration_ms});
            '''}
        </script>
    </body>
    </html>
    """


def _build_splash_overlay_css():
    """CSS untuk bikin overlay jadi fullscreen."""
    return """
    <style>
        div[data-testid="stIFrame"] {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            z-index: 999999 !important;
            border: none !important;
            pointer-events: auto !important;
        }
    </style>
    """


# =========================================================================
# 🔐 HTML ESCAPE (Anti HTML Bocor)
# =========================================================================
def escape_html(text):
    """
    Escape karakter HTML supaya aman dimasukkan ke HTML.
    
    Contoh:
        escape_html("<script>alert('xss')</script>")
        → "&lt;script&gt;alert('xss')&lt;/script&gt;"
    """
    if text is None:
        return ""
    return _html_module.escape(str(text), quote=True)


def safe_html(*parts):
    """
    Gabungkan parts jadi HTML string yang aman.
    Setiap part otomatis di-escape.
    
    Contoh:
        safe_html("<div>", escape_html(user_name), "</div>")
    """
    return "".join(str(p) for p in parts if p)


# =========================================================================
# ⏳ LOADING OVERLAY
# =========================================================================
def show_loading_overlay(text="⏳ Memuat data...", height=100):
    """
    Tampilkan loading overlay fullscreen sederhana.
    """
    _html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: transparent;
            font-family: 'Courier New', monospace;
        }}
        .loading-overlay {{
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            z-index: 99999;
            background: rgba(10, 15, 26, 0.9);
            backdrop-filter: blur(8px);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}
        .spinner {{
            width: 60px; height: 60px;
            border: 4px solid rgba(212, 175, 55, 0.2);
            border-top-color: #d4af37;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            box-shadow: 0 0 20px rgba(212, 175, 55, 0.5);
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .loading-text {{
            color: #fbbf24;
            margin-top: 20px;
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 2px;
            text-align: center;
            padding: 0 20px;
            text-shadow: 0 0 10px rgba(251, 191, 36, 0.6);
            animation: blink 1.5s infinite;
        }}
        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
    </head>
    <body>
        <div class="loading-overlay">
            <div class="spinner"></div>
            <div class="loading-text">{text}</div>
        </div>
    </body>
    </html>
    """
    return st.markdown(_html, unsafe_allow_html=True)


# =========================================================================
# 🎯 HELPER: Detect Perubahan Tab
# =========================================================================
def should_show_splash_on_tab_change(selected_tab, session_key="splash_tab"):
    """
    Cek apakah splash harus muncul karena ganti tab.
    
    Returns:
        bool: True kalau splash harus muncul
    """
    _last_tab_key = f"_last_shown_tab_{session_key}"
    _last_tab = st.session_state.get(_last_tab_key, None)
    
    if _last_tab != selected_tab:
        st.session_state[_last_tab_key] = selected_tab
        return True
    
    return False
