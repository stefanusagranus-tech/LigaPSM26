import streamlit as st


def render_maintenance_panel(
    show=True,
    title="SEDANG UPDATE FITUR BARU!",
    message="Sistem sedang ditingkatkan. Mohon maklum kalau ada gangguan ya! 🙏",
    eta="Target selesai: Besok, 07:00 WIB",
    progress=25,
    type="update",              # ← Terima type, tapi belum dipakai
    badge_text="🚧 SEDANG DIKERJAKAN",  # ← Terima badge_text
):
    """Panel info sederhana — pasti jalan."""
    
    if not show:
        return
    
    # Warna per type
    colors = {
        "update": {"border": "#3b82f6", "bg": "rgba(59, 130, 246, 0.15)"},
        "maintenance": {"border": "#f59e0b", "bg": "rgba(245, 158, 11, 0.15)"},
        "info": {"border": "#10b981", "bg": "rgba(16, 185, 129, 0.15)"},
        "warning": {"border": "#ef4444", "bg": "rgba(239, 68, 68, 0.15)"},
    }
    c = colors.get(type, colors["update"])
    
    progress_bar = ""
    if progress is not None:
        p = max(0, min(100, progress))
        progress_bar = f"""
        <div style="background: rgba(0,0,0,0.4); border-radius: 5px; height: 8px; margin-top: 12px;">
            <div style="width: {p}%; height: 100%; background: linear-gradient(90deg, {c['border']}, #ffffff); border-radius: 5px; box-shadow: 0 0 10px {c['border']};"></div>
        </div>
        <p style="font-size: 10px; color: {c['border']}; text-align: right; margin: 4px 0 0 0;">{p}% SELESAI</p>
        """
    
    html = f"""
<div style="
    background: linear-gradient(135deg, {c['bg']}, rgba(0,0,0,0.2));
    border: 2px solid {c['border']};
    border-left: 6px solid {c['border']};
    border-radius: 12px;
    padding: 16px 20px;
    margin: 15px 0 20px 0;
    box-shadow: 0 0 15px {c['border']}50;
">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="font-family: monospace; font-size: 10px; color: {c['border']}; font-weight: 900; letter-spacing: 1.5px;">
            🔴 {badge_text}
        </span>
        <span style="font-size: 20px;">🚀</span>
    </div>
    <h3 style="color: #ffffff; font-family: monospace; font-size: 15px; font-weight: 900; margin: 0 0 8px 0;">
        🚀 {title}
    </h3>
    <p style="color: #e2e8f0; font-family: sans-serif; font-size: 12px; line-height: 1.6; margin: 0 0 10px 0;">
        {message}
    </p>
    <p style="color: {c['border']}; font-family: monospace; font-size: 10.5px; font-weight: 700; margin: 0; padding: 6px 10px; background: rgba(0,0,0,0.25); border-radius: 6px;">
        ⏳ {eta}
    </p>
    {progress_bar}
</div>
"""
    
    st.markdown(html, unsafe_allow_html=True)