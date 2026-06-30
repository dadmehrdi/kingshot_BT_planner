"""
King Shot — Bear Trap Rally Planner (Streamlit)

LOGISTICS MODEL (hard constraints — all must hold or the plan is invalid)

Inputs
N players in event
A avg troops each player sends per march
C rally capacity (troops per rally)
T one-way march time (s)
J tap-join time after troops arrive home (s)
W waves (staggered rally slots)

Constants
WINDOW = 1800 s (30:00 trap)
FILL = 300 s (rally fill)
LAST_LAUNCH = 1500 s (must launch by 5:00 left)

Cap split (parallel rallies per launch)
R = ceil(N*A / C)
per_rally = A / R (each player splits evenly across R rallies)
All R rallies in a launch open, depart, hit, and return together.

Stagger between consecutive launches
natural = FILL / W
floor = 2*T + J (round-trip march + tap-join)
s = max(natural, floor)

Catch rule (hard)
Player rides launch k (depart d_k), returns at d_k + 2T, ready at d_k + 2T + J.
Must arrive before next depart: d_k + 2T + J <= d_{k+1} ⇔ s >= 2T + J.
Enforced by the stagger equation above.

Launches in window
L = floor(LAST_LAUNCH / s) + 1

Leaders open at once
W waves overlap during fill; each wave needs R rally leaders.
leaders = W * R
"""
import math
import pandas as pd
import streamlit as st

WINDOW = 30 * 60
FILL = 5 * 60
LAST_LAUNCH = WINDOW - FILL

WAVE_HEX = {0: "#45c4ff", 1: "#b78bff", 2: "#4fe0a0"}

st.set_page_config(page_title="Bear Trap Rally Planner", page_icon="🐻", layout="wide")

# ---------- formatting ----------
def fmt_clock(sec):
s = max(0, round(sec)); m, ss = divmod(s, 60)
return f"{m:02d}:{ss:02d}"

def fmt_left(elapsed):
return fmt_clock(WINDOW - elapsed)

def fmt_troops(n):
n = round(n)
if n >= 1_000_000:
v = n / 1_000_000
return (f"{v:.2f}".rstrip("0").rstrip(".")) + "M"
if n >= 1_000:
v = n / 1000
return (f"{v:.1f}".rstrip("0").rstrip(".")) + "K"
return f"{n:,}"

# ---------- model ----------
def stagger_floor(travel, gap):
"""Minimum time between launches: round-trip march + tap-join."""
return 2 * travel + gap

def natural_stagger(waves):
return FILL / waves

def effective_stagger(travel, gap, waves):
return max(natural_stagger(waves), stagger_floor(travel, gap))

def launches_count(travel, gap, waves):
s = effective_stagger(travel, gap, waves)
return int(LAST_LAUNCH // s) + 1, s

def compute_plan(players, avg, cap, travel, gap, waves):
pool = players * avg
R = max(1, math.ceil(pool / cap))
per_player_per_rally = avg / R
troops_per_rally = pool / R
fill_pct = round(100 * troops_per_rally / cap)

nat = natural_stagger(waves)
floor_s = stagger_floor(travel, gap)
s = max(nat, floor_s)
clamped = nat < floor_s
L = int(LAST_LAUNCH // s) + 1

leaders_concurrent = waves * R

launches = []
for k in range(L):
open_t = k * s
depart = open_t + FILL
hit = depart + travel
ret = hit + travel
lane = k % waves
launches.append({
"k": k + 1, "lane": lane,
"open": open_t, "depart": depart, "hit": hit, "ret": ret,
"troops": pool, "rallies": R,
"final": (k == L - 1),
})

first_hit = launches[0]["hit"] if launches else None
last_hit = launches[-1]["hit"] if launches else None
wait_per_cycle = max(0, s - 2 * travel)

return {
"pool": pool, "rallies_per_launch": R,
"troops_per_rally": troops_per_rally,
"troops_per_player_per_rally": per_player_per_rally,
"fill_pct": fill_pct,
"stagger": s, "natural_stagger": nat, "floor": floor_s, "clamped": clamped,
"total_launches": L, "total_rallies": L * R, "total_troops": L * pool,
"leaders_concurrent": leaders_concurrent,
"first_hit": first_hit, "last_hit": last_hit,
"wait_per_cycle": wait_per_cycle,
"launches": launches,
}

# ---------- styling ----------
def inject_css():
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root{
--bg:#0a0e15; --panel:#121a28; --line:rgba(255,255,255,.07);
--ink:#e9eef6; --muted:#8b99ad; --faint:#5b6a80;
--ember:#ff9233; --ember2:#ffc061; --danger:#ff5d62; --ok:#4fe0a0;
--w1:#45c4ff; --w2:#b78bff; --w3:#4fe0a0;
--mono:'IBM Plex Mono',monospace; --disp:'Chakra Petch',sans-serif; --body:'IBM Plex Sans',sans-serif;
}
.stApp{background:radial-gradient(1100px 480px at 50% -160px, rgba(255,146,51,.10), transparent 70%),
linear-gradient(180deg,#090d14,#0a0e15 45%,#080b11); color:var(--ink); font-family:var(--body);}
html,body,[class*="css"]{font-family:var(--body);}
.block-container{padding-top:1.2rem; max-width:1200px;}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d1420,#0a0f18); border-right:1px solid var(--line);}
section[data-testid="stSidebar"] *{color:var(--ink);}

.brand{font-family:var(--disp); letter-spacing:.18em; font-size:.78rem; color:var(--ember); text-transform:uppercase;}
.title{font-family:var(--disp); font-size:2.1rem; font-weight:700; margin:.2rem 0 .35rem 0;}
.sub{color:var(--muted); margin-bottom:1.2rem;}

.card{background:linear-gradient(180deg,var(--panel),#0f1623); border:1px solid var(--line);
border-radius:14px; padding:14px 16px; margin-bottom:10px;}
.card h3{font-family:var(--disp); letter-spacing:.05em; font-size:.95rem; margin:0 0 .5rem 0; color:var(--ember2);}

.cmp-row{display:grid; grid-template-columns:repeat(3,1fr); gap:10px;}
.cmp{background:#0f1623; border:1px solid var(--line); border-radius:12px; padding:12px;}
.cmp.sel{border-color:var(--ember); box-shadow:0 0 0 1px rgba(255,146,51,.25) inset;}
.cmp .w{font-family:var(--disp); font-size:1.05rem;}
.cmp .big{font-family:var(--mono); font-size:1.6rem; color:var(--ember2);}
.cmp .lo{color:var(--muted); font-size:.85rem;}
.cmp .tag{display:inline-block; font-size:.7rem; padding:2px 8px; border-radius:99px;
background:rgba(255,146,51,.15); color:var(--ember2); margin-left:6px;}

.headline{display:flex; flex-wrap:wrap; gap:16px; align-items:baseline;
padding:14px 16px; border:1px solid var(--line); border-radius:14px;
background:linear-gradient(180deg,#13202f,#0d1623); margin-bottom:10px;}
.headline .h-w{font-family:var(--disp); color:var(--ember2); font-size:1.25rem;}
.headline .h-n{font-family:var(--mono); font-size:1.4rem;}
.headline .h-s{color:var(--muted);}

.kv{display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:10px;}
.kv .b{background:#0f1623; border:1px solid var(--line); border-radius:12px; padding:10px 12px;}
.kv .b .k{color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.08em;}
.kv .b .v{font-family:var(--mono); font-size:1.15rem;}

.warn{display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:10px;
border:1px solid var(--line); margin:6px 0; background:#0f1623;}
.warn.bad{border-color:rgba(255,93,98,.45); background:rgba(255,93,98,.06);}
.warn.good{border-color:rgba(79,224,160,.4); background:rgba(79,224,160,.05);}
.warn.info{border-color:rgba(139,153,173,.3);}
.warn .ic{width:22px; height:22px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center;
font-weight:700; flex-shrink:0;}
.warn.bad .ic{background:rgba(255,93,98,.18); color:var(--danger);}
.warn.good .ic{background:rgba(79,224,160,.18); color:var(--ok);}
.warn.info .ic{background:rgba(139,153,173,.18); color:var(--muted);}
.warn .msg{font-size:.92rem;}

.tl{position:relative; height:140px; background:#0c1320; border:1px solid var(--line);
border-radius:12px; overflow:hidden;}
.tl .tk{position:absolute; bottom:4px; color:var(--faint); font-family:var(--mono);
font-size:.7rem; transform:translateX(-50%);}
.tl .tkl{position:absolute; top:0; bottom:18px; width:1px; background:rgba(255,255,255,.05);}
.tl .lane{position:absolute; left:0; right:0; height:32px; border-bottom:1px dashed rgba(255,255,255,.05);}
.tl .pip{position:absolute; width:11px; height:11px; border-radius:50%;
transform:translate(-50%,-50%); box-shadow:0 0 0 3px rgba(0,0,0,.4);}

.eqbox{font-family:var(--mono); font-size:.85rem; background:#0c1320;
border:1px dashed rgba(255,255,255,.12); border-radius:10px; padding:10px 12px;
white-space:pre-wrap; line-height:1.55;}
.eqbox .lbl{color:var(--ember2);}
.eqbox .ok{color:var(--ok);}
.eqbox .bad{color:var(--danger);}

.lane-card{background:#0f1623; border:1px solid var(--line); border-radius:12px;
padding:10px 12px; margin-bottom:8px;}
.lane-card .lbl{font-family:var(--disp); letter-spacing:.12em; font-size:.8rem;}
.lane-card .meta{color:var(--muted); font-size:.85rem;}
</style>
""", unsafe_allow_html=True)

# ---------- timeline ----------
def x_pct(elapsed):
return max(0.0, min(100.0, elapsed / WINDOW * 100))

def build_timeline(plan, waves):
ruler = ""
t = 0
while t <= WINDOW:
x = x_pct(t)
ruler += f'<div class="tkl" style="left:{x}%"></div>'
ruler += f'<div class="tk" style="left:{x}%">{fmt_left(t)}</div>'
t += 300

lanes_html = ""
lane_h = 32
for w in range(waves):
top = 10 + w * (lane_h + 2)
lanes_html += f'<div class="lane" style="top:{top}px"></div>'

pips = ""
for c in plan["launches"]:
x = x_pct(c["hit"])
lane = c["lane"]
top = 10 + lane * (lane_h + 2) + lane_h / 2
color = WAVE_HEX.get(lane, "#ffffff")
pips += f'<div class="pip" style="left:{x}%; top:{top}px; background:{color}"></div>'

return f'<div class="tl">{ruler}{lanes_html}{pips}</div>'

# ---------- UI ----------
inject_css()

st.markdown(
'<div class="brand">King Shot · Bear Hunt</div>'
'<div class="title">Bear Trap Rally Planner</div>'
'<div class="sub">Everyone rides every launch. More waves means rallies leave more often — but only '
'if troops can march home, regroup, and tap into the next rally before it departs.</div>',
unsafe_allow_html=True,
)

with st.sidebar:
st.markdown('<div class="brand">Battle setup</div>', unsafe_allow_html=True)
num_players = st.slider("Players in the event", 3, 100, 10, 1)
avg_k = st.slider("Avg troops each player sends (K)", 20, 2000, 100, 10)
cap_k = st.slider("Rally capacity — a full rally (K)", 100, 6000, 1000, 50)
avg = avg_k * 1000
cap = cap_k * 1000

st.markdown('<div class="brand" style="margin-top:1rem">March logistics</div>', unsafe_allow_html=True)
travel = st.slider("One-way march time (s)", 5, 90, 20, 1)
gap = st.slider("Tap-join time after arriving home (s)", 0, 60, 10, 1)

st.markdown('<div class="brand" style="margin-top:1rem">Wave plan</div>', unsafe_allow_html=True)
waves = st.radio("Waves (staggered rally slots)", [1, 2, 3], index=1, horizontal=True)

plan = compute_plan(num_players, avg, cap, travel, gap, waves)

# ---- comparison ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<h3>Hits in 30:00 — 1 vs 2 vs 3 waves</h3>', unsafe_allow_html=True)
cmp_html = '<div class="cmp-row">'
best_w = max(range(1, 4), key=lambda w: launches_count(travel, gap, w)[0])
for w in (1, 2, 3):
cnt, s_w = launches_count(travel, gap, w)
sel = " sel" if w == waves else ""
tag = '<span class="tag">your pick</span>' if w == waves else (
'<span class="tag">most hits</span>' if w == best_w and w != waves else "")
cmp_html += (
f'<div class="cmp{sel}">'
f'<div class="w">{w} wave{"s" if w>1 else ""}{tag}</div>'
f'<div class="big">{cnt} hits</div>'
f'<div class="lo">a launch every {fmt_clock(s_w)}</div>'
f'<div class="lo">{fmt_troops(cnt * plan["pool"])} troops total</div>'
f'</div>'
)
cmp_html += "</div>"
st.markdown(cmp_html, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---- headline ----
st.markdown(
f'<div class="headline">'
f'<span class="h-w">Your plan: {waves} wave{"s" if waves>1 else ""}</span>'
f'<span class="h-n">{plan["total_launches"]} hits</span>'
f'<span class="h-s">{fmt_troops(plan["total_troops"])} troops sent · '
f'{plan["total_rallies"]} rallies · everyone rides every launch</span>'
f'</div>',
unsafe_allow_html=True,
)

fh = fmt_left(plan["first_hit"]) if plan["first_hit"] is not None else "—"
lh = fmt_left(plan["last_hit"]) if plan["last_hit"] is not None else "—"
st.markdown(
f'<div class="kv">'
f'<div class="b"><div class="k">First hit</div><div class="v">{fh}</div></div>'
f'<div class="b"><div class="k">Last hit</div><div class="v">{lh}</div></div>'
f'<div class="b"><div class="k">Hit every</div><div class="v">{fmt_clock(plan["stagger"])}</div></div>'
f'<div class="b"><div class="k">Idle per cycle</div><div class="v">{fmt_clock(plan["wait_per_cycle"])}</div></div>'
f'</div>',
unsafe_allow_html=True,
)

# ---- logistics check (the hard equations) ----
pool = plan["pool"]; R = plan["rallies_per_launch"]
per_p = plan["troops_per_player_per_rally"]; nat = plan["natural_stagger"]
floor_s = plan["floor"]; s = plan["stagger"]

if nat >= floor_s:
stagger_line = (f'<span class="lbl">stagger s</span> = max(natural,
