import streamlit as st


def render_maintenance_panel(
    show=True,
    title="SEDANG UPDATE FITUR BARU!",
    message="Sistem sedang ditingkatkan. Mohon maklum kalau ada gangguan ya!",
    eta="Target selesai: Hari ini, 22:00 WIB",
    progress=75,
    type="update",
    badge_text="🚧 SEDANG DIKERJAKAN",
):
    """
    Panel info 'Under Maintenance' untuk halaman Menu Utama.
    Versi ultra-simple — semua HTML dalam 1 string.
    """
    if not show:
        return

    # Warna per tipe
    colors = {
        "update": "#3b82f6",
        "maintenance": "#f59e0b",
        "info": "#10b981",
        "warning": "#ef4444",
    }
    border = colors.get(type, "#3b82f6")

    # Progress bar — disusun sebagai string
    if progress is not None:
        p = max(0, min(100, progress))
        progress_html = (
            '<div style="background: rgba(0,0,0,0.4); border-radius: 5px; '
            'height: 8px; margin-top: 12px; overflow: hidden;">'
            f'<div style="width: {p}%; height: 100%; '
            f'background: linear-gradient(90deg, {border}, #ffffff); '
            f'border-radius: 5px; box-shadow: 0 0 10px {border};"></div>'
            '</div>'
            f'<p style="font-size: 10px; color: {border}; '
            f'text-align: right; margin: 4px 0 0 0; font-weight: 900;">'
            f'{p}% SELESAI</p>'
        )
    else:
        progress_html = ""

    # Bangun HTML utama sebagai satu string utuh
    html = (
        f'<div style="'
        f'background: linear-gradient(135deg, {border}26, {border}0d); '
        f'border: 2px solid {border}; '
        f'border-left: 6px solid {border}; '
        f'border-radius: 12px; '
        f'padding: 16px 20px; '
        f'margin: 15px 0 20px 0; '
        f'box-shadow: 0 0 15px {border}50; '
        f'font-family: sans-serif;'
        f'">'
        
        # Header: label + icon
        f'<div style="display: flex; justify-content: space-between; '
        f'align-items: center; margin-bottom: 10px;">'
        f'<span style="font-family: monospace; font-size: 10px; '
        f'color: {border}; font-weight: 900; letter-spacing: 1.5px;">'
        f'&#128308; {badge_text}</span>'
        f'<span style="font-size: 20px;">&#128640;</span>'
        f'</div>'
        
        # Judul
        f'<h3 style="color: #ffffff; font-family: monospace; '
        f'font-size: 15px; font-weight: 900; margin: 0 0 10px 0;">'
        f'&#128640; {title}</h3>'
        
        # Pesan
        f'<p style="color: #e2e8f0; font-size: 12px; line-height: 1.6; '
        f'margin: 0 0 12px 0;">{message}</p>'
        
        # ETA
        f'<p style="color: {border}; font-family: monospace; '
        f'font-size: 10.5px; font-weight: 700; margin: 0; '
        f'padding: 6px 10px; background: rgba(0,0,0,0.25); '
        f'border-radius: 6px;">'
        f'&#9203; {eta}</p>'
        
        # Progress
        f'{progress_html}'
        
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)