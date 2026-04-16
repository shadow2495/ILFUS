"""
SecureFileShare — Streamlit Frontend v2.0
Cyberpunk-styled blockchain file sharing dashboard
"""

import json, os, time, hashlib
from datetime import datetime
from io import BytesIO

import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False

# ─── CONFIG ───────────────────────────────────────────────────────────────────
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="SecureFileShare · Blockchain Storage",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS (injected once) ─────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

:root{
  --bg0:#06080f;--bg1:#0a0e1a;--bg2:#0f1628;--bg3:#141c2e;--bg4:#1a2440;
  --cyan:#00d4ff;--purple:#7c3aed;--green:#10b981;--amber:#f59e0b;--red:#ef4444;
  --t1:#e2e8f0;--t2:#94a3b8;--t3:#475569;--border:#1e2d4a;
}
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif;background:var(--bg0)!important;color:var(--t1)}
.block-container{padding-top:1rem!important}
section[data-testid="stSidebar"]{background:var(--bg2)!important;border-right:1px solid var(--border)}
section[data-testid="stSidebar"] *{color:var(--t1)!important}
header[data-testid="stHeader"]{background:transparent!important}

/* ── Metric card ── */
.mc{background:linear-gradient(135deg,var(--bg3),#0f1e38);border:1px solid var(--border);border-radius:16px;padding:1.25rem;text-align:center;position:relative;overflow:hidden;transition:transform .2s,border-color .2s}
.mc:hover{border-color:var(--cyan);transform:translateY(-2px)}
.mc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--cyan),var(--purple))}
.mc .v{font-size:2rem;font-weight:700;color:var(--cyan);font-family:'JetBrains Mono',monospace}
.mc .l{font-size:.7rem;color:var(--t2);letter-spacing:.08em;text-transform:uppercase;margin-top:.2rem}

/* ── File card ── */
.fc{background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:.9rem 1.1rem;margin-bottom:.6rem;display:flex;align-items:center;gap:.85rem;transition:all .2s}
.fc:hover{border-color:var(--cyan);background:var(--bg4);transform:translateX(2px)}
.fi{font-size:1.6rem;width:38px;text-align:center}
.fn{font-weight:600;font-size:.9rem;color:var(--t1)}
.fm{font-size:.72rem;color:var(--t2);font-family:'JetBrains Mono',monospace}

/* ── Badges ── */
.b{display:inline-block;padding:.12rem .55rem;border-radius:20px;font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.bg{background:rgba(16,185,129,.15);color:#34d399;border:1px solid rgba(16,185,129,.3)}
.bc{background:rgba(0,212,255,.12);color:#00d4ff;border:1px solid rgba(0,212,255,.25)}
.ba{background:rgba(245,158,11,.12);color:#fcd34d;border:1px solid rgba(245,158,11,.25)}
.br{background:rgba(239,68,68,.12);color:#f87171;border:1px solid rgba(239,68,68,.25)}
.bp{background:rgba(124,58,237,.15);color:#a78bfa;border:1px solid rgba(124,58,237,.3)}

/* ── Hash badge ── */
.hb{background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.2);border-radius:6px;padding:.18rem .45rem;font-family:'JetBrains Mono',monospace;font-size:.68rem;color:var(--cyan);word-break:break-all}

/* ── Top bar ── */
.tb{background:linear-gradient(90deg,var(--bg2),var(--bg3));border:1px solid var(--border);border-radius:12px;padding:.85rem 1.25rem;display:flex;align-items:center;justify-content:space-between;margin-bottom:1.2rem}

/* ── Logo glow ── */
.lg{font-size:1.5rem;font-weight:700;background:linear-gradient(90deg,#00d4ff,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-.02em}

/* ── Chain verify box ── */
.cv{background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.25);border-radius:12px;padding:.9rem 1.1rem;margin-top:.6rem}

/* ── Upload area ── */
.ua{border:2px dashed rgba(0,212,255,.3);border-radius:16px;padding:2rem;text-align:center;background:rgba(0,212,255,.03);margin:1rem 0}

/* ── Audit row ── */
.ar{display:flex;align-items:center;gap:.7rem;padding:.55rem 0;border-bottom:1px solid var(--border);font-size:.8rem}
.ar:last-child{border-bottom:none}

/* ── Card ── */
.cd{background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:.85rem;transition:border-color .2s}
.cd:hover{border-color:var(--cyan)}

/* ── Buttons ── */
.stButton>button{background:linear-gradient(135deg,#0ea5e9,#7c3aed)!important;color:#fff!important;border:none!important;border-radius:8px!important;font-family:'Space Grotesk',sans-serif!important;font-weight:600!important;padding:.45rem 1.1rem!important;transition:opacity .2s!important}
.stButton>button:hover{opacity:.88!important}

/* ── Inputs ── */
.stTextInput>div>div>input,.stSelectbox>div>div,.stMultiSelect>div>div,.stTextArea>div>div>textarea{background:var(--bg2)!important;border:1px solid var(--border)!important;color:var(--t1)!important;border-radius:8px!important}

.stProgress>div>div{background:linear-gradient(90deg,var(--cyan),var(--purple))!important}

/* ── Notification dot ── */
.nd{width:8px;height:8px;background:var(--red);border-radius:50%;display:inline-block;margin-left:4px;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* ── Login animations ── */
@keyframes gradientShift{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
@keyframes float{0%,100%{transform:translateY(0);opacity:.6}50%{transform:translateY(-20px);opacity:1}}
@keyframes slideUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
@keyframes orbit{from{transform:rotate(0) translateX(120px) rotate(0)}to{transform:rotate(360deg) translateX(120px) rotate(-360deg)}}

.login-bg{position:fixed;top:0;left:0;right:0;bottom:0;background:linear-gradient(-45deg,#0a0e1a,#0d1b3e,#1a0a2e,#0a1628,#0e2a3d);background-size:400% 400%;animation:gradientShift 15s ease infinite;z-index:0}
.lp{position:fixed;top:0;left:0;right:0;bottom:0;z-index:1;pointer-events:none;overflow:hidden}
.p{position:absolute;border-radius:50%}
.p:nth-child(1){width:4px;height:4px;background:#00d4ff;top:10%;left:15%;animation:float 6s ease-in-out infinite}
.p:nth-child(2){width:6px;height:6px;background:#7c3aed;top:20%;left:80%;animation:float 8s ease-in-out infinite 1s}
.p:nth-child(3){width:3px;height:3px;background:#10b981;top:60%;left:10%;animation:float 7s ease-in-out infinite 2s}
.p:nth-child(4){width:5px;height:5px;background:#00d4ff;top:80%;left:70%;animation:float 9s ease-in-out infinite .5s}
.p:nth-child(5){width:4px;height:4px;background:#f59e0b;top:40%;left:90%;animation:float 6.5s ease-in-out infinite 3s}
.p:nth-child(6){width:7px;height:7px;background:#7c3aed;top:70%;left:40%;animation:float 10s ease-in-out infinite 1.5s}
.p:nth-child(7){width:3px;height:3px;background:#00d4ff;top:30%;left:55%;animation:float 5.5s ease-in-out infinite 2.5s}
.p:nth-child(8){width:5px;height:5px;background:#10b981;top:90%;left:25%;animation:float 7.5s ease-in-out infinite 4s}

.lc{position:relative;z-index:2}

/* Login card */
.lcard{background:rgba(15,22,40,.7);backdrop-filter:blur(24px);border:1px solid rgba(0,212,255,.12);border-radius:24px;padding:2rem;position:relative;overflow:hidden;animation:slideUp .8s ease-out .2s both;box-shadow:0 0 80px rgba(0,212,255,.06),0 25px 60px rgba(0,0,0,.4)}
.lcard::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#00d4ff,#7c3aed,transparent)}

.lf{display:flex;align-items:center;gap:.7rem;padding:.55rem .85rem;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:12px;transition:all .3s;margin-bottom:.5rem}
.lf:hover{background:rgba(0,212,255,.06);border-color:rgba(0,212,255,.2);transform:translateX(4px)}

.ls-row{display:flex;justify-content:center;gap:1.5rem;margin-top:1.2rem;padding-top:.8rem;border-top:1px solid rgba(255,255,255,.05)}
.ls-v{font-size:1.1rem;font-weight:700;color:#00d4ff;font-family:'JetBrains Mono',monospace}
.ls-l{font-size:.6rem;color:#475569;text-transform:uppercase;letter-spacing:.08em;margin-top:2px}

/* Timeline / activity */
.tl{position:relative;padding-left:24px}
.tl::before{content:'';position:absolute;left:8px;top:0;bottom:0;width:2px;background:linear-gradient(180deg,var(--cyan),var(--purple),transparent)}
.tl-item{position:relative;padding:.5rem 0;padding-left:.5rem}
.tl-item::before{content:'';position:absolute;left:-20px;top:.65rem;width:10px;height:10px;border-radius:50%;background:var(--cyan);border:2px solid var(--bg3)}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
for k, v in {"token": None, "user": None, "files": [], "page": "dashboard"}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── API HELPERS ──────────────────────────────────────────────────────────────
def api(method, path, **kw):
    headers = kw.pop("headers", {})
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        return getattr(requests, method)(f"{API_BASE}{path}", headers=headers, timeout=30, **kw)
    except Exception:
        return None

def human_size(n):
    for u in ["B","KB","MB","GB"]:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def ficon(mime):
    if mime.startswith("image"): return "🖼️"
    if mime.startswith("video"): return "🎬"
    if mime.startswith("audio"): return "🎵"
    if "pdf" in mime: return "📄"
    if "zip" in mime or "tar" in mime: return "📦"
    if any(x in mime for x in ["python","json","javascript","text"]): return "💻"
    if "word" in mime or "document" in mime: return "📝"
    if "sheet" in mime or "excel" in mime: return "📊"
    return "📁"

# ─── LOGIN PAGE ───────────────────────────────────────────────────────────────
def page_login():
    st.markdown("""<div class="login-bg"></div>
    <div class="lp"><div class="p"></div><div class="p"></div><div class="p"></div><div class="p"></div>
    <div class="p"></div><div class="p"></div><div class="p"></div><div class="p"></div></div>
    <style>section[data-testid="stSidebar"]{display:none!important}header[data-testid="stHeader"]{background:transparent!important}.block-container{max-width:100%!important}</style>
    """, unsafe_allow_html=True)

    col_hero, _, col_form = st.columns([5, 1, 5])

    with col_hero:
        st.markdown("""<div style="padding:2rem 1rem;animation:slideUp .8s ease-out">
            <div style="font-size:2.5rem;font-weight:700;line-height:1.1;margin-bottom:.75rem;
                        background:linear-gradient(135deg,#00d4ff,#7c3aed 50%,#10b981);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent">
                Secure Your Files<br>On The Blockchain</div>
            <div style="font-size:.95rem;color:#94a3b8;line-height:1.6;margin-bottom:1.5rem;max-width:420px">
                End-to-end encrypted file storage with blockchain verification,
                IPFS pinning, and granular access control.</div></div>""", unsafe_allow_html=True)

        for ic, bg, t, d in [
            ("🔐","rgba(0,212,255,.1)","AES-256-GCM Encryption","Military-grade file encryption"),
            ("⛓️","rgba(124,58,237,.1)","Blockchain Verified","Immutable on-chain audit trail"),
            ("🌐","rgba(16,185,129,.1)","IPFS Distributed Storage","Content-addressed decentralized hosting"),
            ("🔑","rgba(245,158,11,.1)","RSA Key Exchange","Secure peer-to-peer key sharing"),
        ]:
            st.markdown(f'<div class="lf"><div style="font-size:1.2rem;width:32px;height:32px;display:flex;align-items:center;justify-content:center;border-radius:10px;background:{bg}">{ic}</div><div><div style="font-size:.82rem;color:#e2e8f0;font-weight:500">{t}</div><div style="font-size:.68rem;color:#64748b">{d}</div></div></div>', unsafe_allow_html=True)

        st.markdown("""<div class="ls-row">
            <div style="text-align:center"><div class="ls-v">256-bit</div><div class="ls-l">Encryption</div></div>
            <div style="text-align:center"><div class="ls-v">100%</div><div class="ls-l">Uptime</div></div>
            <div style="text-align:center"><div class="ls-v">0 KB</div><div class="ls-l">Data Leaks</div></div>
            <div style="text-align:center"><div class="ls-v">∞</div><div class="ls-l">Decentralized</div></div>
        </div>""", unsafe_allow_html=True)

    with col_form:
        st.markdown("""<div class="lcard" style="pointer-events:none">
            <div style="text-align:center;margin-bottom:1rem">
                <div style="font-size:2.2rem">🔐</div>
                <div style="font-size:1.4rem;font-weight:700;background:linear-gradient(90deg,#00d4ff,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent">SecureFileShare</div>
                <div style="font-size:.75rem;color:#64748b">Blockchain-Encrypted File Vault</div>
            </div></div>""", unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["🚀 Sign In", "✨ Create Account"])

        with tab_login:
            with st.form("login_form"):
                wallet = st.text_input("Wallet Address", placeholder="0x...")
                pwd = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In →", use_container_width=True):
                    if wallet and pwd:
                        r = api("post", "/auth/login", json={"wallet_address": wallet, "password": pwd})
                        if r and r.status_code == 200:
                            d = r.json()
                            st.session_state.token = d["access_token"]
                            st.session_state.user = d["user"]
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                    else:
                        st.warning("Fill all fields")

        with tab_register:
            with st.form("register_form"):
                wallet = st.text_input("Wallet Address", key="rw", placeholder="0x...")
                c1, c2 = st.columns(2)
                uname = c1.text_input("Username")
                email = c2.text_input("Email (optional)")
                c3, c4 = st.columns(2)
                pwd = c3.text_input("Password", type="password", key="rp")
                pwd2 = c4.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account →", use_container_width=True):
                    if pwd != pwd2:
                        st.error("Passwords don't match")
                    elif wallet and uname and pwd:
                        r = api("post", "/auth/register", json={"wallet_address": wallet, "username": uname, "email": email or None, "password": pwd})
                        if r and r.status_code == 200:
                            d = r.json()
                            st.session_state.token = d["access_token"]
                            st.session_state.user = d["user"]
                            st.rerun()
                        elif r:
                            st.error(r.json().get("detail", "Failed"))
                    else:
                        st.warning("Fill required fields")

        st.markdown('<div style="text-align:center;margin-top:.8rem"><span style="font-size:.65rem;color:#475569">🔒 Secured by AES-256 · IPFS · Ethereum</span></div>', unsafe_allow_html=True)


# ─── TOP BAR ──────────────────────────────────────────────────────────────────
def render_top_bar():
    u = st.session_state.user or {}
    st.markdown(f'<div class="tb"><div class="lg">🔐 SecureFileShare</div><div style="font-size:.82rem;color:var(--t2)"><span style="color:var(--green)">●</span>&nbsp;<b style="color:var(--t1)">{u.get("username","")}</b>&nbsp;&nbsp;<span class="b bp">{u.get("plan","free").upper()}</span></div></div>', unsafe_allow_html=True)


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown('<div class="lg" style="font-size:1.1rem;padding:.4rem 0">🔐 SecureFileShare</div>', unsafe_allow_html=True)
        st.divider()

        menu_items = ["Dashboard", "My Files", "Upload", "Share File", "Shared With Me", "Audit Trail", "File Integrity", "Analytics", "Blockchain", "Notifications", "Settings"]
        menu_icons = ["speedometer2", "folder2", "cloud-upload", "share", "people", "journal-text", "shield-check", "bar-chart", "link-45deg", "bell", "gear"]

        if HAS_OPTION_MENU:
            choice = option_menu(
                menu_title=None, options=menu_items, icons=menu_icons, default_index=0,
                styles={
                    "container": {"background-color": "transparent", "padding": "0"},
                    "icon": {"color": "#94a3b8", "font-size": "13px"},
                    "nav-link": {"font-family": "Space Grotesk", "font-size": "12px", "color": "#94a3b8", "padding": "7px 10px"},
                    "nav-link-selected": {"background-color": "rgba(0,212,255,.12)", "color": "#00d4ff", "font-weight": "600"},
                },
            )
        else:
            choice = st.radio("Navigation", menu_items, label_visibility="collapsed")

        st.divider()
        u = st.session_state.user or {}
        used = u.get("storage_used_mb", 0) or 0
        lim = 500
        st.caption("STORAGE")
        st.progress(min(used / lim, 1.0))
        st.caption(f"{used:.1f} MB / {lim} MB")
        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            for k in ["token", "user", "files"]:
                st.session_state[k] = None if k != "files" else []
            st.rerun()
    return choice


# ─── DASHBOARD ────────────────────────────────────────────────────────────────
def page_dashboard():
    render_top_bar()
    st.markdown("### 📊 Dashboard")

    r = api("get", "/dashboard/stats")
    s = r.json() if r and r.status_code == 200 else {}

    c1, c2, c3, c4 = st.columns(4)
    for col, lbl, val, ic in [
        (c1, "TOTAL FILES", s.get("total_files", 0), "📁"),
        (c2, "SHARES GIVEN", s.get("shares_given", 0), "↗️"),
        (c3, "ENCRYPTED", s.get("encrypted_files", 0), "🔒"),
        (c4, "STORAGE", f'{s.get("storage_used_mb", 0):.1f} MB', "💾"),
    ]:
        col.markdown(f'<div class="mc"><div style="font-size:1.6rem">{ic}</div><div class="v">{val}</div><div class="l">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown("")
    cl, cr = st.columns([3, 2])

    with cl:
        st.markdown("#### 🗂️ Recent Files")
        rf = api("get", "/files")
        if rf and rf.status_code == 200:
            files = rf.json()[:6]
            if files:
                for f in files:
                    ic = ficon(f["mime_type"])
                    enc = '<span class="b bg">🔒 ENC</span>' if f.get("is_encrypted") else ''
                    chain = '<span class="b bp">⛓ ON-CHAIN</span>' if f.get("blockchain_confirmed") else ''
                    st.markdown(f'<div class="fc"><div class="fi">{ic}</div><div style="flex:1"><div class="fn">{f["file_name"]}</div><div class="fm">{human_size(f["file_size"])} &nbsp;·&nbsp; {f["created_at"][:10]} &nbsp;{enc} {chain}</div></div></div>', unsafe_allow_html=True)
            else:
                st.info("No files yet. Upload your first file!")

        st.markdown("#### ⏱️ Activity Timeline")
        ra = api("get", "/dashboard/activity?limit=5")
        if ra and ra.status_code == 200:
            acts = ra.json()
            if acts:
                act_icons = {"UPLOAD": "☁️", "DOWNLOAD": "⬇️", "SHARE": "🔗", "REVOKE": "🚫", "DELETE": "🗑️"}
                st.markdown('<div class="tl">', unsafe_allow_html=True)
                for a in acts:
                    ai = act_icons.get(a["action"], "📌")
                    st.markdown(f'<div class="tl-item"><span style="font-size:.9rem">{ai}</span> <span class="b bc">{a["action"]}</span> <span style="color:var(--t2);font-size:.78rem">{a.get("file_name","")}</span> <span style="color:var(--t3);font-size:.7rem">{a["created_at"][:16]}</span></div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

    with cr:
        st.markdown("#### 🔗 Blockchain Status")
        rb = api("get", "/blockchain/status")
        if rb and rb.status_code == 200:
            bs = rb.json()
            st.markdown(f'''<div class="cv">
              <div style="font-size:.78rem;color:var(--green);font-weight:600">● CONNECTED</div>
              <div style="font-size:.72rem;color:var(--t2);margin-top:.4rem;font-family:'JetBrains Mono',monospace">
                Network: {bs.get("network","")}<br>Block: #{bs.get("latest_block","")}<br>
                Gas: {bs.get("gas_price_gwei","")} Gwei<br>Peers: {bs.get("peer_count","")}<br>
                Contract: {bs.get("contract_address","")[:16]}…
              </div></div>''', unsafe_allow_html=True)

        st.markdown("#### 📊 Storage Breakdown")
        rk = api("get", "/dashboard/storage-breakdown")
        if rk and rk.status_code == 200:
            bd = rk.json()
            if bd:
                labels = [x["category"] for x in bd]
                values = [x["total_size"] for x in bd]
                fig = go.Figure(go.Pie(labels=labels, values=values, hole=.55,
                    marker=dict(colors=["#00d4ff","#7c3aed","#10b981","#f59e0b","#ef4444","#a78bfa","#34d399","#fcd34d"]),
                    textfont=dict(color="#e2e8f0", size=11)))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8"), height=280, margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(font=dict(size=10)))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No files to analyze yet.")

        st.markdown("#### 🛡️ Security")
        for feat, on in [("AES-256 Encryption",True),("IPFS Pinning",True),("On-Chain Audit",True),("Access Expiry",True)]:
            a, b = st.columns([3,1])
            a.caption(feat)
            b.markdown(f'<span class="b {"bg" if on else "br"}">{"ON" if on else "OFF"}</span>', unsafe_allow_html=True)


# ─── MY FILES ─────────────────────────────────────────────────────────────────
def page_my_files():
    render_top_bar()
    st.markdown("### 📁 My Files")

    c1, c2, c3 = st.columns([3, 1, 1])
    search = c1.text_input("🔍 Search files", placeholder="filename, tag...")
    sort = c2.selectbox("Sort", ["Newest", "Oldest", "Name", "Size"])
    type_f = c3.selectbox("Type", ["All", "Images", "Documents", "Videos", "Archives", "PDFs"])

    sort_map = {"Newest": "newest", "Oldest": "oldest", "Name": "name", "Size": "size"}
    r = api("get", f"/files?sort_by={sort_map.get(sort,'newest')}&file_type={type_f}" + (f"&search={search}" if search else ""))
    if not r or r.status_code != 200:
        st.error("Could not load files"); return

    files = r.json()
    if not files:
        st.info("No files uploaded yet."); return

    st.caption(f"{len(files)} files")
    for f in files:
        ic = ficon(f["mime_type"])
        with st.expander(f"{ic} {f['file_name']}  •  {human_size(f['file_size'])}"):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("**IPFS CID**")
                st.markdown(f'<div class="hb">{f.get("ipfs_cid","N/A")}</div>', unsafe_allow_html=True)
                st.markdown("**SHA-256 Hash**")
                st.markdown(f'<div class="hb">{f.get("file_hash","N/A")}</div>', unsafe_allow_html=True)
                if f.get("tags"):
                    for t in f["tags"]:
                        st.markdown(f'<span class="b bc">{t}</span>&nbsp;', unsafe_allow_html=True)
                if f.get("description"):
                    st.caption(f"📝 {f['description']}")
            with c2:
                st.markdown(f"**Version:** `v{f.get('version',1)}`")
                st.markdown(f"**Encrypted:** {'✅' if f.get('is_encrypted') else '❌'}")
                st.markdown(f"**On-Chain:** {'⛓️' if f.get('blockchain_confirmed') else '❌'}")
                st.caption(f"Uploaded: {f['created_at'][:19]}")
                if f.get("tx_hash"):
                    st.markdown(f'<span class="hb">{f["tx_hash"][:20]}…</span>', unsafe_allow_html=True)

            bc1, bc2, bc3 = st.columns(3)
            if bc1.button("⬇ Download", key=f"dl_{f['id']}"):
                dr = api("get", f"/files/{f['id']}/download")
                if dr and dr.status_code == 200:
                    st.download_button("💾 Save", dr.content, f["original_name"], mime=f["mime_type"], key=f"save_{f['id']}")
            if bc2.button("🔍 Verify", key=f"vf_{f['id']}"):
                vr = api("get", f"/files/{f['id']}/verify")
                if vr and vr.status_code == 200:
                    vd = vr.json()
                    if vd.get("integrity_valid"):
                        st.success("✅ File integrity verified!")
                    else:
                        st.error("❌ Integrity check failed!")
            if bc3.button("🗑 Delete", key=f"del_{f['id']}"):
                dr = api("delete", f"/files/{f['id']}")
                if dr and dr.status_code == 200:
                    st.success("Deleted!"); st.rerun()


# ─── UPLOAD ───────────────────────────────────────────────────────────────────
def page_upload():
    render_top_bar()
    st.markdown("### ☁️ Upload File")

    with st.form("upload_form"):
        st.markdown('<div class="ua">📁 Drop your file here or click Browse</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Choose File", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        desc = c1.text_area("Description", height=80)
        tags_raw = c2.text_input("Tags (comma separated)")
        ec1, ec2 = st.columns(2)
        encrypt = ec1.checkbox("🔒 Encrypt file (recommended)", value=True)
        chain = ec2.checkbox("⛓ Register on blockchain", value=True)
        submitted = st.form_submit_button("🚀 Upload & Secure", use_container_width=True)

        if submitted and uploaded:
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            prog = st.progress(0, text="Encrypting...")
            time.sleep(0.3)
            prog.progress(30, text="Pinning to IPFS...")
            time.sleep(0.3)
            r = api("post", "/files/upload",
                    files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                    data={"description": desc, "tags": json.dumps(tags)})
            prog.progress(70, text="Writing to blockchain...")
            time.sleep(0.3)
            prog.progress(100, text="Done!")

            if r and r.status_code == 200:
                d = r.json()
                st.success("✅ File secured and stored!")
                st.markdown(f'''<div class="cv">
                  <b>📦 {d["file_name"]}</b>&nbsp;
                  <span class="b bg">ENCRYPTED</span>
                  <span class="b bp">IPFS</span>
                  {"<span class='b bc'>ON-CHAIN</span>" if chain else ""}
                  <br><br>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:.75rem">
                    CID: {d["cid"]}<br>Hash: {d["file_hash"]}<br>
                    Size: {human_size(d["size"])}<br>Tx: {d["tx_hash"][:32]}…
                  </div></div>''', unsafe_allow_html=True)
            elif r:
                st.error(f"Upload failed: {r.json().get('detail')}")


# ─── SHARE ────────────────────────────────────────────────────────────────────
def page_share():
    render_top_bar()
    st.markdown("### 🔗 Share File")

    r = api("get", "/files")
    files = r.json() if r and r.status_code == 200 else []
    opts = {f["file_name"]: f["id"] for f in files}

    if not opts:
        st.info("Upload files first to share them."); return

    with st.form("share_form"):
        fname = st.selectbox("Select File", list(opts.keys()))
        grantee = st.text_input("Recipient Wallet Address", placeholder="0x...")
        c1, c2 = st.columns(2)
        level = c1.selectbox("Access Level", ["VIEW", "DOWNLOAD", "RESHARE"])
        expires = c2.selectbox("Expiry", ["Never", "1 hour", "24 hours", "7 days", "30 days"])
        reshare = st.checkbox("Allow recipient to re-share")
        exp_map = {"Never": None, "1 hour": 1, "24 hours": 24, "7 days": 168, "30 days": 720}

        if st.form_submit_button("🔗 Grant Access", use_container_width=True):
            if grantee and fname:
                r = api("post", "/share", json={
                    "file_id": opts[fname], "grantee_wallet": grantee,
                    "access_level": level, "can_reshare": reshare, "expires_hours": exp_map[expires]
                })
                if r and r.status_code == 200:
                    d = r.json()
                    st.success("✅ Access granted on blockchain!")
                    st.markdown(f'<div class="cv"><b>Grant ID:</b> <span class="hb">{d["grant_id"]}</span><br><b>Expires:</b> {d.get("expires_at") or "∞ Never"}<br><b>Tx:</b> <span class="hb">{d["tx_hash"][:24]}…</span></div>', unsafe_allow_html=True)
                elif r:
                    st.error(r.json().get("detail", "Share failed"))

    st.divider()
    st.markdown("#### 📤 Active Shares Given")
    rg = api("get", "/share/given")
    if rg and rg.status_code == 200:
        grants = rg.json()
        if grants:
            for g in grants:
                status = "🚫 REVOKED" if g["is_revoked"] else "✅ ACTIVE"
                badge_cls = "br" if g["is_revoked"] else "bg"
                st.markdown(f'<div class="fc"><div class="fi">📂</div><div style="flex:1"><div class="fn">{g["file_name"]} → {g["grantee_name"]}</div><div class="fm"><span class="b {badge_cls}">{g["access_level"]}</span>&nbsp;{status}&nbsp;·&nbsp;{g["created_at"][:10]}</div></div></div>', unsafe_allow_html=True)
                if not g["is_revoked"]:
                    if st.button("Revoke", key=f"rev_{g['id']}"):
                        rv = api("post", f"/share/{g['id']}/revoke")
                        if rv and rv.status_code == 200:
                            st.success("Revoked!"); st.rerun()
        else:
            st.caption("No active shares.")


# ─── SHARED WITH ME ──────────────────────────────────────────────────────────
def page_shared_with_me():
    render_top_bar()
    st.markdown("### 📬 Shared With Me")
    r = api("get", "/share/received")
    if not r or r.status_code != 200:
        st.error("Could not load"); return
    grants = r.json()
    if not grants:
        st.info("No files shared with you yet."); return

    for g in grants:
        badge_map = {"VIEW": "bc", "DOWNLOAD": "bg", "RESHARE": "bp"}
        exp = g.get("expires_at")
        exp_str = f"Expires {exp[:10]}" if exp else "No expiry"
        ic = ficon(g.get("mime_type", ""))
        st.markdown(f'''<div class="fc">
          <div class="fi">{ic}</div>
          <div style="flex:1">
            <div class="fn">{g["file_name"]}</div>
            <div class="fm">
              from <span style="color:var(--cyan)">{g.get("granter_name","")}</span>&nbsp;·&nbsp;
              {human_size(g.get("file_size",0))}&nbsp;·&nbsp;
              <span class="b {badge_map.get(g["access_level"],"bc")}">{g["access_level"]}</span>&nbsp;
              {"<span class='b ba'>RESHARE</span>&nbsp;" if g["can_reshare"] else ""}
              {exp_str}
            </div>
          </div></div>''', unsafe_allow_html=True)


# ─── AUDIT TRAIL ──────────────────────────────────────────────────────────────
def page_audit():
    render_top_bar()
    st.markdown("### 📜 Audit Trail")
    r = api("get", "/files")
    files = r.json() if r and r.status_code == 200 else []
    if not files:
        st.info("No files to audit."); return

    opts = {f["file_name"]: f["id"] for f in files}
    sel = st.selectbox("Select file", list(opts.keys()))
    if sel:
        r2 = api("get", f"/files/{opts[sel]}/audit")
        if r2 and r2.status_code == 200:
            logs = r2.json()
            if logs:
                act_icons = {"UPLOAD":"☁️","DOWNLOAD":"⬇️","SHARE":"🔗","REVOKE":"🚫","DELETE":"🗑️","ACCESS":"👁️"}
                for log in logs:
                    ai = act_icons.get(log["action"], "📌")
                    tx = log.get("tx_hash") or "off-chain"
                    st.markdown(f'<div class="ar"><span style="font-size:1rem">{ai}</span><span class="b bc">{log["action"]}</span><span style="color:var(--t2);font-size:.75rem">{log.get("actor_name","")}</span><span style="flex:1;color:var(--t3);font-size:.72rem">{log["created_at"][:19]}</span><span class="hb">{tx[:16]}…</span></div>', unsafe_allow_html=True)
            else:
                st.info("No audit logs.")


# ─── FILE INTEGRITY ──────────────────────────────────────────────────────────
def page_integrity():
    render_top_bar()
    st.markdown("### 🔍 File Integrity Verification")
    st.markdown("Verify that your stored files haven't been tampered with by recomputing their SHA-256 hash and comparing against the blockchain record.")

    r = api("get", "/files")
    files = r.json() if r and r.status_code == 200 else []
    if not files:
        st.info("No files to verify."); return

    opts = {f["file_name"]: f["id"] for f in files}
    sel = st.selectbox("Select file to verify", list(opts.keys()))

    if st.button("🔍 Verify Integrity", use_container_width=True):
        with st.spinner("Recomputing hash..."):
            vr = api("get", f"/files/{opts[sel]}/verify")
        if vr and vr.status_code == 200:
            vd = vr.json()
            if vd.get("integrity_valid"):
                st.success("✅ INTEGRITY VERIFIED — File has not been tampered with!")
            else:
                st.error("❌ INTEGRITY FAILED — File may have been modified!")

            st.markdown(f'''<div class="cv">
              <div style="font-family:'JetBrains Mono',monospace;font-size:.75rem">
                <b>File:</b> {vd.get("file_name","")}<br>
                <b>Stored Hash:</b> <span class="hb">{vd.get("stored_hash","")}</span><br>
                <b>Computed Hash:</b> <span class="hb">{vd.get("computed_hash","N/A")}</span><br>
                <b>IPFS CID:</b> <span class="hb">{vd.get("ipfs_cid","")}</span><br>
                <b>Blockchain:</b> <span class="b {"bg" if vd.get("blockchain_confirmed") else "br"}">{"CONFIRMED" if vd.get("blockchain_confirmed") else "PENDING"}</span><br>
                <b>Tx Hash:</b> <span class="hb">{(vd.get("tx_hash") or "")[:32]}…</span>
              </div></div>''', unsafe_allow_html=True)


# ─── ANALYTICS ────────────────────────────────────────────────────────────────
def page_analytics():
    render_top_bar()
    st.markdown("### 📈 Analytics")

    r = api("get", "/dashboard/stats")
    s = r.json() if r and r.status_code == 200 else {}

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="mc"><div class="v">{s.get("total_files",0)}</div><div class="l">Total Files</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="mc"><div class="v">{s.get("shares_given",0)+s.get("shares_received",0)}</div><div class="l">Total Shares</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="mc"><div class="v">{s.get("blockchain_txns",0)}</div><div class="l">Chain Txns</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="mc"><div class="v">{s.get("storage_used_mb",0):.1f}</div><div class="l">MB Used</div></div>', unsafe_allow_html=True)

    cl, cr = st.columns(2)
    with cl:
        st.markdown("#### Storage by Type")
        rb = api("get", "/dashboard/storage-breakdown")
        if rb and rb.status_code == 200:
            bd = rb.json()
            if bd:
                fig = go.Figure(go.Bar(x=[x["category"] for x in bd], y=[x["total_size"]/(1024*1024) for x in bd],
                    marker_color=["#00d4ff","#7c3aed","#10b981","#f59e0b","#ef4444","#a78bfa","#34d399","#fcd34d"][:len(bd)]))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8"), height=300, margin=dict(t=20,b=40,l=40,r=20),
                    xaxis=dict(gridcolor="#1e2d4a"), yaxis=dict(gridcolor="#1e2d4a", title="MB"))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No data yet.")

    with cr:
        st.markdown("#### File Count by Type")
        if rb and rb.status_code == 200:
            bd = rb.json()
            if bd:
                fig = go.Figure(go.Pie(labels=[x["category"] for x in bd], values=[x["file_count"] for x in bd], hole=.5,
                    marker=dict(colors=["#00d4ff","#7c3aed","#10b981","#f59e0b","#ef4444","#a78bfa"][:len(bd)]),
                    textfont=dict(color="#e2e8f0")))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8"), height=300, margin=dict(t=20,b=20,l=20,r=20))
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### 🕐 Recent Activity")
    ra = api("get", "/dashboard/activity?limit=10")
    if ra and ra.status_code == 200:
        acts = ra.json()
        if acts:
            df = pd.DataFrame(acts)
            df = df[["created_at", "action", "file_name", "actor_name"]]
            df.columns = ["Time", "Action", "File", "User"]
            st.dataframe(df, use_container_width=True, hide_index=True)


# ─── BLOCKCHAIN ───────────────────────────────────────────────────────────────
def page_blockchain():
    render_top_bar()
    st.markdown("### ⛓ Blockchain Explorer")

    rb = api("get", "/blockchain/status")
    if rb and rb.status_code == 200:
        bs = rb.json()
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="mc"><div style="font-size:1.2rem">⛓</div><div class="v" style="font-size:1.2rem">{bs.get("network","")}</div><div class="l">Network</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="mc"><div class="v">#{bs.get("latest_block","")}</div><div class="l">Latest Block</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="mc"><div class="v">{bs.get("gas_price_gwei","")} </div><div class="l">Gas (Gwei)</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="mc"><div class="v">{bs.get("peer_count","")}</div><div class="l">Peers</div></div>', unsafe_allow_html=True)

        st.markdown(f'''<div class="cv" style="margin-top:1rem">
          <div style="font-size:.78rem;color:var(--green);font-weight:600">● {"CONNECTED" if bs.get("connected") else "DISCONNECTED"}</div>
          <div style="font-size:.72rem;color:var(--t2);margin-top:.4rem;font-family:'JetBrains Mono',monospace">
            Chain ID: {bs.get("chain_id","")}<br>Node: {bs.get("node_version","")}<br>
            Contract: {bs.get("contract_address","")}<br>Syncing: {"No" if not bs.get("syncing") else "Yes"}
          </div></div>''', unsafe_allow_html=True)

    st.divider()
    st.markdown("#### 📋 Recent Transactions")
    rt = api("get", "/blockchain/transactions?limit=15")
    if rt and rt.status_code == 200:
        txns = rt.json()
        if txns:
            for tx in txns:
                type_badge = {"FILE_UPLOAD":"bg","FILE_SHARE":"bp","FILE_DELETE":"br","ACCESS_REVOKE":"ba"}.get(tx["tx_type"],"bc")
                st.markdown(f'<div class="ar"><span class="b {type_badge}">{tx["tx_type"]}</span><span class="hb" style="flex:1">{tx["tx_hash"][:32]}…</span><span style="color:var(--t2);font-size:.72rem">Block #{tx["block_number"]}</span><span style="color:var(--t3);font-size:.68rem">{tx["created_at"][:16]}</span></div>', unsafe_allow_html=True)
        else:
            st.info("No transactions yet.")

    st.divider()
    st.markdown("#### 🔍 Verify Transaction")
    tx_input = st.text_input("Enter transaction hash", placeholder="0x...")
    if st.button("Verify", key="verify_tx"):
        if tx_input:
            vr = api("get", f"/blockchain/verify/{tx_input}")
            if vr and vr.status_code == 200:
                vd = vr.json()
                if vd.get("verified"):
                    st.success(f"✅ Verified! Block #{vd['block_number']} — {vd['tx_type']}")
                else:
                    st.warning("Transaction not found in records.")


# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────
def page_notifications():
    render_top_bar()
    st.markdown("### 🔔 Notifications")

    if st.button("Mark All Read", use_container_width=False):
        api("post", "/notifications/read-all")
        st.rerun()

    rn = api("get", "/notifications?limit=30")
    if rn and rn.status_code == 200:
        notifs = rn.json()
        if notifs:
            for n in notifs:
                bg = "var(--bg4)" if not n["is_read"] else "var(--bg3)"
                dot = '<span class="nd"></span>' if not n["is_read"] else ""
                type_icons = {"welcome":"🎉","upload":"☁️","share":"🔗","revoke":"🚫","system":"⚙️"}
                ic = type_icons.get(n["type"], "📌")
                st.markdown(f'<div class="cd" style="background:{bg}"><div style="display:flex;align-items:start;gap:.6rem"><span style="font-size:1.2rem">{ic}</span><div style="flex:1"><div style="font-weight:600;font-size:.85rem">{n["title"]}{dot}</div><div style="font-size:.78rem;color:var(--t2);margin-top:.15rem">{n["message"]}</div><div style="font-size:.65rem;color:var(--t3);margin-top:.3rem">{n["created_at"][:16]}</div></div></div></div>', unsafe_allow_html=True)
                if not n["is_read"]:
                    if st.button("Mark read", key=f"mr_{n['id']}"):
                        api("post", f"/notifications/{n['id']}/read")
                        st.rerun()
        else:
            st.info("No notifications.")


# ─── SETTINGS ─────────────────────────────────────────────────────────────────
def page_settings():
    render_top_bar()
    st.markdown("### ⚙️ Settings")
    r = api("get", "/auth/me")
    if not r or r.status_code != 200:
        st.error("Could not load profile"); return
    me = r.json()

    t1, t2, t3 = st.tabs(["👤 Profile", "🔒 Security", "🔑 Keys"])
    with t1:
        with st.form("profile_form"):
            st.text_input("Username", value=me["username"], disabled=True)
            new_email = st.text_input("Email", value=me.get("email") or "")
            st.text_input("Wallet Address", value=me["wallet"], disabled=True)
            st.markdown(f'<span class="b bp">{me["plan"].upper()} PLAN</span>&nbsp;<span class="b bg">{me.get("storage_used_mb",0):.1f} MB USED</span>', unsafe_allow_html=True)
            if st.form_submit_button("Update Profile"):
                api("put", "/auth/update-profile", json={"email": new_email})
                st.success("Profile updated!")

    with t2:
        with st.form("pwd_form"):
            cur = st.text_input("Current Password", type="password")
            new = st.text_input("New Password", type="password")
            cnf = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password"):
                if new != cnf:
                    st.error("Passwords don't match")
                elif cur and new:
                    pr = api("post", "/auth/change-password", json={"current_password": cur, "new_password": new})
                    if pr and pr.status_code == 200:
                        st.success("Password changed!")
                    elif pr:
                        st.error(pr.json().get("detail", "Failed"))

    with t3:
        st.markdown("#### Your Public Key")
        st.code(me.get("public_key", "N/A"), language="text")
        st.caption("Used for encrypting files shared with you.")
        st.markdown('<span class="b bg">● KEY ACTIVE</span>', unsafe_allow_html=True)
        if st.button("🔄 Rotate Keypair"):
            st.warning("⚠️ Rotating will revoke access to previously encrypted files until re-encrypted.")


# ─── ROUTER ───────────────────────────────────────────────────────────────────
def main():
    if not st.session_state.token:
        page_login()
        return

    r = api("get", "/dashboard/stats")
    if r and r.status_code == 200:
        st.session_state.user = {**(st.session_state.user or {}), **r.json()}

    page = render_sidebar()
    pages = {
        "Dashboard": page_dashboard, "My Files": page_my_files,
        "Upload": page_upload, "Share File": page_share,
        "Shared With Me": page_shared_with_me, "Audit Trail": page_audit,
        "File Integrity": page_integrity, "Analytics": page_analytics,
        "Blockchain": page_blockchain, "Notifications": page_notifications,
        "Settings": page_settings,
    }
    pages.get(page, page_dashboard)()

if __name__ == "__main__":
    main()
