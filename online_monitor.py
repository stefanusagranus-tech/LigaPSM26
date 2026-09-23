"""
online_monitor.py
=================
Modul monitoring user online & auto-logout untuk LigaPSM.

Fitur:
    get_online_users(max_idle_minutes)  → daftar user yang sedang online
    get_user_status(username)           → status 1 user (online/offline)
    render_sidebar_online_panel()       → panel "Sedang Online" di sidebar
    get_online_avatar(name)             → avatar emoji konsisten per user
    cleanup_stale_on_login(threshold)   → bersihkan user lama saat login baru

Author: LigaPSM Team
Version: 1.0
"""

import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo


# =========================================================================
# 🎨 KONSTANTA
# =========================================================================
_AVATAR_POOL = [
    "🧙‍♂️", "🧝‍♂️", "🧝‍♀️", "⚔️", "🎯", "🛡️", "🦁", "🦅",
    "🐺", "👑", "💎", "🔮", "🔥", "🏹", "🪄", "🗡️",
    "⚗️", "🧛‍♂️", "🧟‍♂️", "🐉", "🦉", "🐻", "🦊", "🦌"
]

_ONLINE_IDLE_THRESHOLD_MIN = 2  # User dianggap online kalau heartbeat < 2 menit
_MAX_ONLINE_DISPLAY = 10        # Max user tampil di panel sidebar
_SKIP_USERS = ["DEBUG_TEST", "DEBUG_HEARTBEAT", "SYSTEM"]


# =========================================================================
# 🎨 HELPER: AVATAR EMOJI KONSISTEN
# =========================================================================
def get_online_avatar(name):
    """
    Bikin avatar emoji konsisten per user (hash-based).
    User dengan nama sama selalu dapat emoji sama.
    """
    if not name:
        return "👤"
    h = int(hashlib.md5(str(name).upper().encode()).hexdigest(), 16)
    return _AVATAR_POOL[h % len(_AVATAR_POOL)]


# =========================================================================
# 📡 CORE: GET ONLINE USERS
# =========================================================================
def get_online_users(max_idle_minutes=None):
    """
    Ambil daftar user yang sedang ONLINE dari ACTIVITY_HEARTBEAT.
    
    User dianggap online kalau heartbeat terakhirnya < max_idle_minutes.
    
    Args:
        max_idle_minutes (int): Threshold dianggap online. Default 2 menit.
    
    Returns:
        list of dict: [
            {
                username: str,
                role: str,
                last_heartbeat: str,
                selisih_detik: int,
                durasi_str: str,
                avatar: str,
            },
            ...
        ] (sorted dari yang paling baru)
    """
    if max_idle_minutes is None:
        max_idle_minutes = _ONLINE_IDLE_THRESHOLD_MIN
    
    try:
        from spreadsheet_connector import get_ws_audit
        
        ws = get_ws_audit("ACTIVITY_HEARTBEAT")
        if ws is None:
            return []
        
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return []
        
        # Map kolom
        header = all_values[0]
        col_idx = {}
        for idx, h in enumerate(header):
            col_idx[h.lower().strip()] = idx
        
        if "username" not in col_idx or "last_heartbeat" not in col_idx:
            return []
        
        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        online_users = []
        
        for row in all_values[1:]:
            if len(row) < 4:
                continue
            
            try:
                _username = row[col_idx["username"]].strip()
                _role = row[col_idx.get("role", 2)].strip() if "role" in col_idx else "-"
                _last_hb_str = row[col_idx["last_heartbeat"]].strip()
                
                # Skip kosong & sistem
                if not _username or not _last_hb_str:
                    continue
                if _username.upper() in _SKIP_USERS:
                    continue
                
                # Parse waktu
                _last_hb = datetime.strptime(
                    _last_hb_str, "%d/%m/%Y %H:%M:%S"
                ).replace(tzinfo=ZoneInfo("Asia/Jakarta"))
                _selisih_detik = (now - _last_hb).total_seconds()
                _selisih_menit = _selisih_detik / 60
                
                # Filter online
                if _selisih_menit <= max_idle_minutes:
                    # Format durasi human-readable
                    if _selisih_detik < 60:
                        _durasi_str = f"{int(_selisih_detik)}s lalu"
                    elif _selisih_menit < 60:
                        _durasi_str = f"{int(_selisih_menit)}m lalu"
                    else:
                        _durasi_str = f"{int(_selisih_menit / 60)}j lalu"
                    
                    online_users.append({
                        "username": _username,
                        "role": _role,
                        "last_heartbeat": _last_hb_str,
                        "selisih_detik": int(_selisih_detik),
                        "durasi_str": _durasi_str,
                        "avatar": get_online_avatar(_username),
                    })
            except Exception as e_row:
                print(f"[ONLINE_USER SKIP] {e_row}")
                continue
        
        # Sort paling baru duluan
        online_users.sort(key=lambda x: x["selisih_detik"])
        return online_users
    
    except Exception as e:
        print(f"[GET_ONLINE_USERS ERROR] {e}")
        return []


# =========================================================================
# 👤 HELPER: STATUS 1 USER
# =========================================================================
def get_user_status(username, max_idle_minutes=2):
    """
    Cek status 1 user (online/offline).
    
    Returns:
        dict: {
            is_online: bool,
            status_str: str,      # "🟢 SEDANG ONLINE" / "🟡 5m lalu" / dll
            durasi_str: str,      # "12s lalu" / "5m lalu"
        }
    """
    if not username:
        return {
            "is_online": False,
            "status_str": "⚪ BELUM LOGIN",
            "durasi_str": "-",
        }
    
    try:
        online_list = get_online_users(max_idle_minutes=max_idle_minutes)
        _username_upper = username.strip().upper()
        
        for u in online_list:
            if u["username"].upper() == _username_upper:
                return {
                    "is_online": True,
                    "status_str": "🟢 SEDANG ONLINE",
                    "durasi_str": u["durasi_str"],
                }
        
        return {
            "is_online": False,
            "status_str": "🔴 OFFLINE",
            "durasi_str": "-",
        }
    
    except Exception as e:
        print(f"[GET_USER_STATUS ERROR] {e}")
        return {
            "is_online": False,
            "status_str": "⚠️ ERROR",
            "durasi_str": "-",
        }


# =========================================================================
# 🎨 UI: SIDEBAR ONLINE PANEL
# =========================================================================
def render_sidebar_online_panel():
    """
    Render panel "Sedang Online" di sidebar Streamlit.
    
    Panggil fungsi ini di dalam script utama (setelah user login).
    """
    try:
        # Skip kalau sidebar collapsed
        if st.session_state.get("sidebar_collapsed", False):
            return
        
        # Ambil user online
        online_users = get_online_users(max_idle_minutes=_ONLINE_IDLE_THRESHOLD_MIN)
        online_count = len(online_users)
        
        # CSS
        st.sidebar.markdown(
            """
            <style>
                .online-panel {
                    background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.15));
                    border: 1.5px solid #10b981;
                    border-left: 4px solid #34d399;
                    border-radius: 10px;
                    padding: 12px 14px;
                    margin: 12px 0;
                    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.2);
                }
                .online-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 10px;
                    padding-bottom: 8px;
                    border-bottom: 1px dashed rgba(52, 211, 153, 0.3);
                }
                .online-title {
                    font-family: monospace;
                    font-size: 11px;
                    font-weight: 900;
                    color: #34d399;
                    letter-spacing: 1px;
                }
                .online-count {
                    background: #10b981;
                    color: #ffffff;
                    font-family: monospace;
                    font-size: 11px;
                    font-weight: 900;
                    padding: 2px 8px;
                    border-radius: 10px;
                    box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
                }
                .online-pulse {
                    display: inline-block;
                    width: 8px;
                    height: 8px;
                    background: #34d399;
                    border-radius: 50%;
                    margin-right: 6px;
                    animation: onlinePulse 1.5s infinite;
                    box-shadow: 0 0 8px #34d399;
                }
                @keyframes onlinePulse {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.5; transform: scale(1.3); }
                }
                .online-user-row {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 6px 8px;
                    margin-bottom: 4px;
                    background: rgba(15, 23, 42, 0.5);
                    border-radius: 6px;
                    border-left: 2px solid #34d399;
                    font-family: monospace;
                }
                .online-user-row:last-child {
                    margin-bottom: 0;
                }
                .online-user-avatar {
                    font-size: 14px;
                    flex-shrink: 0;
                }
                .online-user-info {
                    flex: 1;
                    min-width: 0;
                }
                .online-user-name {
                    color: #f1e5c7;
                    font-size: 10px;
                    font-weight: 900;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .online-user-time {
                    color: #94a3b8;
                    font-size: 8.5px;
                    margin-top: 1px;
                }
                .online-empty {
                    text-align: center;
                    color: #64748b;
                    font-size: 10px;
                    font-style: italic;
                    padding: 8px;
                    font-family: monospace;
                }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Bangun HTML
        _html = f"""
        <div class="online-panel">
            <div class="online-header">
                <span class="online-title"><span class="online-pulse"></span>SEDANG ONLINE</span>
                <span class="online-count">{online_count}</span>
            </div>
        """
        
        if online_users:
            for _u in online_users[:_MAX_ONLINE_DISPLAY]:
                _html += f"""
                <div class="online-user-row">
                    <span class="online-user-avatar">{_u['avatar']}</span>
                    <div class="online-user-info">
                        <div class="online-user-name">{_u['username'][:18]}</div>
                        <div class="online-user-time">🟢 {_u['durasi_str']}</div>
                    </div>
                </div>
                """
            
            if online_count > _MAX_ONLINE_DISPLAY:
                _html += f"""
                <div class="online-empty">... dan {online_count - _MAX_ONLINE_DISPLAY} user lainnya</div>
                """
        else:
            _html += """
            <div class="online-empty">😴 Tidak ada user online</div>
            """
        
        _html += "</div>"
        st.sidebar.markdown(_html, unsafe_allow_html=True)
        
        # Tombol refresh
        if st.sidebar.button(
            "🔄 Refresh Status Online",
            use_container_width=True,
            key="btn_refresh_online_panel"
        ):
            st.rerun()
    
    except Exception as e:
        print(f"[RENDER_SIDEBAR_ONLINE_PANEL ERROR] {e}")


# =========================================================================
# 🧹 CLEANUP ON LOGIN
# =========================================================================
def cleanup_stale_on_login(threshold_minutes=15):
    """
    🧹 CLEANUP ON LOGIN
    Dipanggil setiap kali user baru login.
    Hapus SEMUA heartbeat yang sudah idle > threshold,
    meskipun user lain baru masuk 1 jam atau 4 jam kemudian.
    
    Args:
        threshold_minutes (int): Threshold idle untuk cleanup (default 15)
    
    Returns:
        int: Jumlah user yang di-cleanup
    """
    try:
        from spreadsheet_connector import (
            get_ws_audit,
            get_stale_heartbeats,
            remove_heartbeat_from_sheet,
            append_logs_to_sheet,
        )
        
        _current_user = st.session_state.get("username", "").strip()
        
        print(f"[CLEANUP_LOGIN] Mulai (threshold={threshold_minutes} menit)")
        
        # Ambil SEMUA user stale
        stale_users = get_stale_heartbeats(threshold_minutes=threshold_minutes)
        
        if not stale_users:
            print(f"[CLEANUP_LOGIN] ✅ Tidak ada user stale")
            return 0
        
        print(f"[CLEANUP_LOGIN] 🔍 Ditemukan {len(stale_users)} user stale")
        
        # Filter: jangan hapus diri sendiri
        stale_users = [
            u for u in stale_users
            if u["username"].upper() != _current_user.upper()
        ]
        
        # Max 10 user per cleanup
        MAX_PER_CLEANUP = 10
        stale_users = stale_users[:MAX_PER_CLEANUP]
        
        if not stale_users:
            print(f"[CLEANUP_LOGIN] ✅ Tidak ada user lain yang stale")
            return 0
        
        _waktu = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
        _total_logout = 0
        
        for _user in stale_users:
            try:
                _username = str(_user["username"])
                
                # Hapus heartbeat
                _ok_del, _msg_del = remove_heartbeat_from_sheet(_username)
                print(f"[CLEANUP_LOGIN] {_username}: {_msg_del}")
                
                if not _ok_del:
                    continue
                
                # Log AUTO_LOGOUT
                try:
                    _log_entry = {
                        "timestamp": _waktu,
                        "username": _username,
                        "role": str(_user.get("role", "-")),
                        "action": "AUTO_LOGOUT",
                        "detail": (
                            f"Auto-logout saat login user baru "
                            f"({_user['selisih_menit']} menit idle)"
                        ),
                        "session_id": str(_user.get("session_id", "-")),
                    }
                    _count, _msg = append_logs_to_sheet([_log_entry])
                    print(f"[CLEANUP_LOGIN LOG] {_username}: {_msg}")
                    _total_logout += 1
                except Exception as e_log:
                    print(f"[CLEANUP_LOGIN LOG FAIL] {_username}: {e_log}")
            
            except Exception as e_user:
                print(f"[CLEANUP_LOGIN ERROR] {_user.get('username', '?')}: {e_user}")
        
        print(f"[CLEANUP_LOGIN] ✅ Total {_total_logout} user di-cleanup")
        return _total_logout
    
    except Exception as e:
        print(f"[CLEANUP_LOGIN ERROR] {e}")
        return 0
