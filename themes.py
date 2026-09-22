"""
themes.py
=========
Kumpulan CSS untuk LigaPSM.

Fungsi:
    load_global_css()          → CSS global (background, sidebar, radio, dll)
    load_laporan_buttons_css() → CSS tombol laporan (border berwarna)
    load_all_themes()          → Load semua CSS
"""
import streamlit as st


def load_global_css():
    """CSS global Royal Guild Theme."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=MedievalSharp&family=Quicksand:wght@600;700&family=Cinzel:wght@600;700;800&display=swap');
            
            /* BASE APP */
            .stApp {
                background: radial-gradient(ellipse at top, #1e3a5f 0%, #0f172a 45%, #0a0f1a 100%) !important;
                color: #f1e5c7 !important;
                font-family: 'Quicksand', sans-serif !important;
            }
            
            /* SCROLLBAR */
            ::-webkit-scrollbar { width: 12px; height: 12px; }
            ::-webkit-scrollbar-track { background: #0b0f19; }
            ::-webkit-scrollbar-thumb {
                background: linear-gradient(180deg, #d4af37, #9a7b38);
                border-radius: 6px;
                border: 2px solid #0b0f19;
            }
            
            /* LABEL */
            label, p[data-testid="stWidgetLabel"], div[data-testid="stWidgetLabel"] label, label p {
                color: #fef3c7 !important;
                font-family: 'Cinzel', serif !important;
                font-weight: 700 !important;
                font-size: 13px !important;
            }
            
            /* INPUT & DROPDOWN */
            div[data-baseweb="input"] input,
            div[data-baseweb="select"] input,
            div[data-baseweb="select"] span {
                color: #f1e5c7 !important;
                font-weight: bold !important;
            }
            div[data-baseweb="input"] > div,
            div[data-baseweb="select"] > div {
                background-color: rgba(15, 23, 42, 0.95) !important;
                border: 1.5px solid #b45309 !important;
                border-radius: 8px !important;
                min-height: 44px !important;
            }
            div[data-baseweb="input"] svg, div[data-baseweb="select"] svg {
                fill: #d4af37 !important;
            }
            
            /* METRIC */
            div[data-testid="stMetric"] {
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
                border: 1.5px solid #b45309 !important;
                padding: 16px !important;
                border-radius: 12px !important;
            }
            div[data-testid="stMetric"] label {
                color: #cbd5e1 !important;
                font-family: 'Quicksand', sans-serif !important;
                font-weight: 700 !important;
                font-size: 12px !important;
            }
            div[data-testid="stMetric"] [data-testid="stMetricValue"] {
                color: #f7e7b4 !important;
                font-family: 'MedievalSharp', serif !important;
                font-weight: 800 !important;
                font-size: 28px !important;
            }
            
            /* EXPANDER */
            div[data-testid="stExpander"] {
                background: rgba(12, 20, 39, 0.9) !important;
                border: 1.5px solid #9a7b38 !important;
                border-radius: 10px !important;
                margin-bottom: 12px !important;
            }
            div[data-testid="stExpander"] summary {
                background: linear-gradient(90deg, #1e3a5f 0%, #0f172a 100%) !important;
                color: #f7e7b4 !important;
                font-family: 'Cinzel', serif !important;
                font-weight: 700 !important;
                font-size: 14px !important;
                padding: 12px 16px !important;
                min-height: 44px !important;
            }
            div[data-testid="stExpander"] summary svg { fill: #d4af37 !important; }
            div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
                padding: 16px !important;
                background: rgba(8, 13, 25, 0.6) !important;
            }
            
            /* DATAFRAME */
            div[data-testid="stDataFrame"], div[data-testid="stTable"] {
                background-color: rgba(10, 17, 34, 0.9) !important;
                border: 1.5px solid #d4af37 !important;
                border-radius: 10px !important;
                padding: 4px !important;
            }
            
            /* SIDEBAR */
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0c1427 0%, #05070c 100%) !important;
                border-right: 2px solid #9a7b38 !important;
            }
            [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] span,
            [data-testid="stSidebar"] label {
                color: #f1e5c7 !important;
                font-weight: 600 !important;
            }
            
            /* TOMBOL DEFAULT — jangan lock background */
            div.stButton > button {
                border-radius: 8px !important;
                font-family: 'Cinzel', serif !important;
                font-weight: bold !important;
                font-size: 13px !important;
                min-height: 44px !important;
                padding: 10px 16px !important;
                transition: all 0.3s ease !important;
            }
            
            /* TAB */
            div[data-baseweb="tab-list"] button {
                background-color: transparent !important;
            }
            div[data-baseweb="tab-list"] button[aria-selected="true"] div[data-testid="stMarkdownContainer"] p {
                color: #f7e7b4 !important;
                font-weight: 800 !important;
            }
            div[data-baseweb="tab-highlight"] {
                background-color: #d4af37 !important;
            }
            
            /* ALERT */
            div[data-testid="stAlert"] {
                background: rgba(15, 23, 42, 0.95) !important;
                border: 1.5px solid #b45309 !important;
                border-radius: 10px !important;
            }
            div[data-testid="stAlert"] svg { fill: #d4af37 !important; }
            
            /* RADIO GLOBAL */
            div[data-testid="stRadio"] div[role="radiogroup"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: wrap !important;
                gap: 12px !important;
                justify-content: center !important;
                width: 100% !important;
            }
            div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child,
            div[data-testid="stRadio"] input[type="radio"] {
                display: none !important;
            }
            div[data-testid="stRadio"] div[role="radiogroup"] > label {
                background: linear-gradient(180deg, #2a1a0c 0%, #170d05 100%) !important;
                border: 2px solid #b8860b !important;
                border-radius: 8px !important;
                padding: 10px 16px !important;
                cursor: pointer !important;
                transition: all 0.25s ease !important;
            }
            div[data-testid="stRadio"] label * {
                color: #d4af37 !important;
                font-family: 'Georgia', serif !important;
                font-weight: bold !important;
                font-size: 11px !important;
                text-transform: uppercase !important;
            }
            div[data-testid="stRadio"] label:has(input:checked) {
                background: linear-gradient(180deg, #6e4218 0%, #3d230b 100%) !important;
                border: 2px solid #fff3b0 !important;
            }
            div[data-testid="stRadio"] label:has(input:checked) * {
                color: #ffffff !important;
            }
            
            /* SIDEBAR RADIO OVERRIDE */
            section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] {
                flex-direction: column !important;
                align-items: stretch !important;
            }
            section[data-testid="stSidebar"] div[data-testid="stRadio"] div[role="radiogroup"] > label {
                width: 100% !important;
                min-width: 100% !important;
                height: 44px !important;
                background: linear-gradient(180deg, #162447 0%, #0c1427 100%) !important;
                border: 1.5px solid #9a7b38 !important;
            }
            section[data-testid="stSidebar"] div[data-testid="stRadio"] label * {
                color: #f1e5c7 !important;
                font-family: 'Cinzel', serif !important;
                white-space: nowrap !important;
            }
            section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {
                background: linear-gradient(135deg, #b8860b 0%, #785805 100%) !important;
                border-color: #f7e7b4 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_laporan_buttons_css():
    """CSS tombol laporan — border berwarna."""
    st.markdown(
        """
        <style>
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) div[data-testid="stButton"] > button {
                border: 2.5px solid #d4af37 !important;
                color: #fbbf24 !important;
                background: transparent !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(1) div[data-testid="stButton"] > button:hover {
                background: linear-gradient(135deg, #b45309 0%, #d97706 100%) !important;
                color: #ffffff !important;
            }
            
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) div[data-testid="stButton"] > button {
                border: 2.5px solid #a855f7 !important;
                color: #c084fc !important;
                background: transparent !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) div[data-testid="stButton"] > button:hover {
                background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
                color: #ffffff !important;
            }
            
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) div[data-testid="stButton"] > button {
                border: 2.5px solid #f97316 !important;
                color: #fdba74 !important;
                background: transparent !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) div[data-testid="stButton"] > button:hover {
                background: linear-gradient(135deg, #c2410c 0%, #f97316 100%) !important;
                color: #ffffff !important;
            }
            
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) div[data-testid="stButton"] > button {
                border: 2.5px solid #06b6d4 !important;
                color: #67e8f9 !important;
                background: transparent !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(4) div[data-testid="stButton"] > button:hover {
                background: linear-gradient(135deg, #0e7490 0%, #06b6d4 100%) !important;
                color: #ffffff !important;
            }
            
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(5) div[data-testid="stButton"] > button {
                border: 3px solid #10b981 !important;
                color: #6ee7b7 !important;
                background: transparent !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(5) div[data-testid="stButton"] > button:hover {
                background: linear-gradient(135deg, #047857 0%, #10b981 100%) !important;
                color: #ffffff !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_all_themes():
    """Load semua CSS."""
    load_global_css()
    load_laporan_buttons_css()
