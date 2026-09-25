"""
pdf_generator.py
================
Modul generator laporan PDF untuk LigaPSM.
- generate_pdf_report()  → Report PPS (multi-page)
- generate_ikt_pdf()     → Simulasi IKT (1-page + pie chart)
"""

import io
import streamlit as st
from fpdf import FPDF
from datetime import datetime
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# =========================================================================
# 📄 FUNGSI 1: REPORT PPS (Multi-page)
# =========================================================================
def generate_pdf_report(title, sections_data, generated_time_str):
    """
    Generate PDF Report PPS Toko Karang Satria — versi ringkas tanpa progress bar.
    """
    try:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_margins(left=12, top=12, right=12)

        # --- WARNA TEMA ---
        CLR_DARK = (12, 20, 39)
        CLR_GOLD = (212, 175, 55)
        CLR_GOLD_LIGHT = (247, 231, 180)
        CLR_TEXT = (30, 30, 30)
        CLR_GRAY = (120, 120, 120)
        CLR_GREEN = (16, 185, 129)
        CLR_BLUE = (59, 130, 246)
        CLR_PURPLE = (168, 85, 247)
        CLR_ORANGE = (245, 158, 11)
        CLR_PINK = (236, 72, 153)

        def _clean(text):
            if text is None:
                return ""
            reps = {
                "—": "-", "–": "-", "•": "*", "→": "->", "←": "<-",
                "≥": ">=", "≤": "<=", "×": "x", "…": "...",
                "“": '"', "”": '"', "‘": "'", "’": "'",
                "📦": "", "⚡": "", "💧": "", "🎁": "", "🥤": "", "🏆": "",
                "🎯": "", "📊": "", "📈": "", "📝": "", "✅": "[OK]",
                "⚠️": "[!]", "❌": "[X]", "⭐": "*", "👑": "", "💡": "",
            }
            for k, v in reps.items():
                text = str(text).replace(k, v)
            return text.encode("latin-1", "replace").decode("latin-1")

        def section_color(title_str):
            t = title_str.upper()
            if "PSM" in t: return CLR_BLUE
            if "PWP" in t: return CLR_PURPLE
            if "SUEGER" in t: return CLR_GREEN
            if "SG" in t or "SERBA" in t: return CLR_ORANGE
            if "TOTAL" in t or "POIN" in t: return CLR_GOLD
            return CLR_GOLD

        def parse_stat_line(line):
            s = str(line)
            if ":" in s:
                parts = s.split(":", 1)
                return parts[0].strip(), parts[1].strip()
            return None

        # =========================================================
        # HEADER BANNER
        # =========================================================
        pdf.set_fill_color(*CLR_DARK)
        pdf.rect(0, 0, 210, 30, style="F")

        pdf.set_draw_color(*CLR_GOLD)
        pdf.set_line_width(0.8)
        pdf.line(0, 30, 210, 30)

        pdf.set_xy(12, 8)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(*CLR_GOLD_LIGHT)
        pdf.cell(186, 10, "REPORT PPS TOKO KARANG SATRIA", ln=1, align="C")

        pdf.set_x(12)
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(*CLR_GOLD)
        pdf.cell(186, 5, _clean(generated_time_str), ln=1, align="C")

        pdf.ln(8)

        # =========================================================
        # SECTION LOOP
        # =========================================================
        for section in sections_data:
            sec_title_raw = str(section.get("title", "-"))
            sec_lines = section.get("lines", [])
            accent = section_color(sec_title_raw)

            title_upper = sec_title_raw.upper()
            if "CEBAN" in title_upper:
                continue

            is_total_section = ("TOTAL" in title_upper) or ("POIN" in title_upper and "TOTAL" in title_upper)

            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(255, 255, 255)
            pdf.set_fill_color(*accent)
            pdf.cell(186, 8, "  " + _clean(sec_title_raw), ln=1, fill=True)
            pdf.ln(2)

            all_stats = []
            for line in sec_lines:
                if not str(line).strip():
                    continue
                parsed = parse_stat_line(line)
                if parsed:
                    label, value = parsed
                    label_upper = label.upper()
                    if any(x in label_upper for x in ["SYARAT REDEEM", "TOTAL REDEEM", "ACH. REDEEM", "ACH REDEEM"]):
                        continue
                    all_stats.append((label, value))

            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(*CLR_TEXT)

            for i, (label, value) in enumerate(all_stats):
                col_x = 12 if i % 2 == 0 else 108
                col_w = 92

                pdf.set_x(col_x)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(col_w * 0.6, 6, _clean(label), ln=0)

                pdf.set_font("Helvetica", "B", 10)
                if is_total_section:
                    pdf.set_text_color(*CLR_DARK)
                else:
                    pdf.set_text_color(*accent)
                pdf.cell(col_w * 0.4, 6, _clean(value), ln=0, align="R")

                if i % 2 == 1:
                    pdf.ln(6)
                elif i == len(all_stats) - 1:
                    pdf.ln(6)

            pdf.ln(3)

            pdf.set_draw_color(*CLR_GOLD)
            pdf.set_line_width(0.4)
            pdf.line(12, pdf.get_y(), 198, pdf.get_y())
            pdf.ln(5)

        # =========================================================
        # FOOTER
        # =========================================================
        pdf.ln(2)
        pdf.set_draw_color(*CLR_GOLD)
        pdf.set_line_width(0.6)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
        pdf.ln(3)

        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(*CLR_GRAY)
        pdf.cell(0, 5, _clean("Catatan: Data sesuai inputan pada website"), align="C", ln=1)

        pdf_output = pdf.output(dest="S")
        if isinstance(pdf_output, str):
            return pdf_output.encode("latin-1")
        return bytes(pdf_output)

    except Exception as e:
        st.error(f"Gagal generate PDF: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None


# =========================================================================
# 📄 FUNGSI 2: SIMULASI IKT (1-page + Pie Chart)
# =========================================================================
def generate_ikt_pdf(data):
    """
    Generate PDF Simulasi IKT — 1 halaman, dengan 3 pie chart.
    Layout: header logo + 3 pie chart + best estimate + tanda tangan.
    """
    try:
        import io as _io
        import os as _os

        # === WARNA ===
        CLR_DARK = (12, 20, 39)
        CLR_NAVY = (30, 58, 95)
        CLR_GOLD = (212, 175, 55)
        CLR_GOLD_LIGHT = (247, 231, 180)
        CLR_GREEN = (16, 185, 129)
        CLR_RED = (239, 68, 68)
        CLR_ORANGE = (245, 158, 11)
        CLR_BLUE = (59, 130, 246)
        CLR_PURPLE = (168, 85, 247)
        CLR_TEXT = (30, 30, 30)
        CLR_GRAY = (120, 120, 120)

        def _clean(text):
            if text is None:
                return ""
            reps = {
                "—": "-", "–": "-", "•": "*", "→": "->",
                "≥": ">=", "≤": "<=", "×": "x", "…": "...",
                "“": '"', "”": '"', "‘": "'", "’": "'",
                "📊": "", "💰": "", "📅": "", "📄": "", "🧾": "",
                "📈": "", "🎯": "", "💎": "", "✅": "[OK]",
                "⚠️": "[!]", "🔴": "[X]", "⚜️": "", "🏢": "",
            }
            for k, v in reps.items():
                text = str(text).replace(k, v)
            return text.encode("latin-1", "replace").decode("latin-1")

        def _fmt_rp(v):
            return f"Rp {int(v):,}"

        # === BUAT PIE CHART ===
        def _buat_pie_chart(actual, target):
            _gap = max(target - actual, 0)
            _sisa = max(actual, 0)

            if _sisa + _gap == 0:
                return None

            if actual >= target:
                _labels = ["Actual", "Over"]
                _sizes = [target, max(actual - target, 0)]
                _colors = ["#10b981", "#fbbf24"]
            else:
                _labels = ["Actual", "Gap"]
                _sizes = [_sisa, _gap]
                _colors = ["#10b981", "#ef4444"]

            _fig, _ax = plt.subplots(figsize=(2.2, 2.2), facecolor="white")
            _wedges, _texts, _autotexts = _ax.pie(
                _sizes,
                labels=_labels,
                colors=_colors,
                autopct="%1.0f%%",
                startangle=90,
                textprops={"fontsize": 7, "fontweight": "bold", "color": "#1f2937"},
                wedgeprops={"edgecolor": "#78350f", "linewidth": 1.2},
            )
            for _at in _autotexts:
                _at.set_color("white")
                _at.set_fontsize(7)
                _at.set_fontweight("bold")
            _ax.axis("equal")

            _buf = _io.BytesIO()
            _fig.savefig(_buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
            plt.close(_fig)
            _buf.seek(0)
            return _buf

        # === INIT PDF ===
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
        pdf.set_margins(left=12, top=12, right=12)

        # ==========================================
        # 🎨 HEADER
        # ==========================================
        pdf.set_fill_color(*CLR_DARK)
        pdf.rect(0, 0, 210, 34, style="F")

        pdf.set_draw_color(*CLR_GOLD)
        pdf.set_line_width(1)
        pdf.line(0, 34, 210, 34)

        # Logo di kiri
        _logo_path = "alfamart_logo.png"
        _logo_loaded = False
        if _os.path.exists(_logo_path):
            try:
                pdf.image(_logo_path, x=12, y=5, w=22, h=22)
                _logo_loaded = True
            except Exception:
                _logo_loaded = False

        if not _logo_loaded:
            pdf.set_xy(12, 10)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(*CLR_GOLD)
            pdf.cell(30, 10, "ALFAMART", ln=0, align="C")

        # Judul di kanan
        _x_judul = 20 if _logo_loaded else 30
        _lebar_judul = 210 - _x_judul - 12

        pdf.set_xy(_x_judul, 6)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*CLR_GOLD_LIGHT)
        pdf.cell(_lebar_judul, 7, "INSENTIF KINERJA TOKO (IKT)", ln=1, align="C")

        pdf.set_x(_x_judul)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*CLR_GOLD)
        pdf.cell(_lebar_judul, 6, "TOKO C383 - KARANG SATRIA", ln=1, align="C")

        pdf.set_x(_x_judul)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*CLR_GOLD_LIGHT)
        pdf.cell(
            _lebar_judul, 5,
            _clean(f"{data['bulan']} {data['tahun']}  |  Hari ke-{data['hari_berjalan']} dari {data['jhk']} (sisa {data['sisa_hari']} hari)"),
            ln=1, align="C"
        )

        # ==========================================
        # 🥧 SECTION 1: 3 PIE CHART
        # ==========================================
        pdf.set_y(38)

        _charts_data = [
            {
                "title": "NET SALES",
                "target": data["target_ns"],
                "actual": data["actual_ns"],
                "ach": data["ach_ns"],
                "gap": data["gap_ns"],
                "is_pct": False,
            },
            {
                "title": "GM% (GROSS MARGIN)",
                "target": data["target_gm"],
                "actual": data["actual_gm"],
                "ach": data["ach_gm"],
                "gap": data["gap_gm"],
                "is_pct": True,
            },
            {
                "title": "GM RUPIAH",
                "target": data["target_gm_rupiah"],
                "actual": data["actual_gm_rupiah"],
                "ach": data["ach_gm_rupiah"],
                "gap": data["gap_gm_rupiah"],
                "is_pct": False,
            },
        ]

        _row_height = 42
        _pie_w = 30

        for _i, _chart in enumerate(_charts_data):
            _y_start = 38 + (_i * _row_height)

            _bg_color = (250, 250, 250) if _i % 2 == 0 else (245, 248, 252)
            pdf.set_fill_color(*_bg_color)
            pdf.rect(12, _y_start, 186, _row_height - 2, style="F")

            pdf.set_draw_color(*CLR_GOLD)
            pdf.set_line_width(0.3)
            pdf.rect(12, _y_start, 186, _row_height - 2, style="D")

            _pie_buf = _buat_pie_chart(_chart["actual"], _chart["target"])
            if _pie_buf:
                pdf.image(_pie_buf, x=15, y=_y_start + 3, w=_pie_w, h=_pie_w)

            _x_text = 15 + _pie_w + 8

            pdf.set_xy(_x_text, _y_start + 3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*CLR_DARK)
            pdf.cell(150, 6, _clean(_chart["title"]), ln=1)

            # Target
            pdf.set_x(_x_text)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*CLR_GRAY)
            pdf.cell(30, 5, _clean("Target"), ln=0)

            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*CLR_TEXT)
            _target_str = f"{_chart['target']:.2f}%" if _chart["is_pct"] else _fmt_rp(_chart["target"])
            pdf.cell(120, 5, _clean(_target_str), ln=1)

            # Actual
            pdf.set_x(_x_text)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*CLR_GRAY)
            pdf.cell(30, 5, _clean("Actual"), ln=0)

            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*CLR_BLUE)
            _actual_str = f"{_chart['actual']:.2f}%" if _chart["is_pct"] else _fmt_rp(_chart["actual"])
            pdf.cell(120, 5, _clean(_actual_str), ln=1)

            # Ach%
            pdf.set_x(_x_text)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*CLR_GRAY)
            pdf.cell(30, 5, _clean("Achievement"), ln=0)

            _ach_color = CLR_GREEN if _chart["ach"] >= 100 else (CLR_ORANGE if _chart["ach"] >= 80 else CLR_RED)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*_ach_color)
            pdf.cell(120, 5, _clean(f"{_chart['ach']:.2f}%"), ln=1)

            # Gap
            pdf.set_x(_x_text)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*CLR_GRAY)
            pdf.cell(30, 5, _clean("Gap"), ln=0)

            _gap_color = CLR_GREEN if _chart["gap"] >= 0 else CLR_RED
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*_gap_color)
            if _chart["is_pct"]:
                _gap_str = f"{_chart['gap']:+.2f}%"
            else:
                _gap_str = f"{_fmt_rp(_chart['gap'])}" if _chart["gap"] < 0 else f"+{_fmt_rp(_chart['gap'])}"
            pdf.cell(120, 5, _clean(_gap_str), ln=1)

        # ==========================================
        # 🎯 SECTION 2: BEST ESTIMATE
        # ==========================================
        _y_be = 38 + (3 * _row_height) + 2

        pdf.set_fill_color(*CLR_NAVY)
        pdf.rect(12, _y_be, 186, 26, style="F")

        pdf.set_xy(15, _y_be + 2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*CLR_GOLD_LIGHT)
        pdf.cell(180, 6, _clean("BEST ESTIMATE NET SALES (per hari)"), ln=1)

        _be_items = [
            ("Capai 100%", data["be_ns_100"]),
            ("Capai 103%", data["be_ns_103"]),
            ("Capai 105%", data["be_ns_105"]),
        ]

        _box_w = 58
        _box_gap = 3
        _box_start_x = 15

        for _i, (_label, _value) in enumerate(_be_items):
            _bx = _box_start_x + (_i * (_box_w + _box_gap))
            _by = _y_be + 10

            pdf.set_fill_color(*CLR_GOLD)
            pdf.rect(_bx, _by, _box_w, 13, style="F")

            pdf.set_xy(_bx, _by + 1)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*CLR_DARK)
            pdf.cell(_box_w, 4, _clean(_label), ln=1, align="C")

            pdf.set_xy(_bx, _by + 5)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*CLR_DARK)
            pdf.cell(_box_w, 6, _clean(_fmt_rp(_value)), ln=1, align="C")

        # ==========================================
        # ✍️ SECTION 3: TANDA TANGAN
        # ==========================================
        _y_ttd = _y_be + 32

        pdf.set_draw_color(*CLR_GOLD)
        pdf.set_line_width(0.5)
        pdf.line(12, _y_ttd, 198, _y_ttd)

        _x_ttd = 130

        pdf.set_xy(_x_ttd, _y_ttd + 4)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*CLR_TEXT)
        pdf.cell(68, 5, _clean("Dibuat oleh,"), ln=1, align="C")

        pdf.ln(15)

        pdf.set_x(_x_ttd)
        pdf.set_draw_color(*CLR_DARK)
        pdf.set_line_width(0.4)
        pdf.line(_x_ttd, _y_ttd + 32, _x_ttd + 68, _y_ttd + 32)

        pdf.set_xy(_x_ttd, _y_ttd + 33)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*CLR_DARK)
        pdf.cell(68, 5, _clean("Staf Toko Karang Satria"), ln=1, align="C")

        _tgl_hari_ini = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
        pdf.set_x(_x_ttd)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*CLR_GRAY)
        pdf.cell(68, 5, _clean(f"Karang Satria, {_tgl_hari_ini}"), ln=1, align="C")

        # === OUTPUT ===
        pdf_output = pdf.output(dest="S")
        if isinstance(pdf_output, str):
            return pdf_output.encode("latin-1")
        return bytes(pdf_output)

    except Exception as e:
        st.error(f"❌ Gagal generate PDF IKT: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None
