"""
King Shot — Bear Trap Rally Planner  (Streamlit)
================================================
Deploy on Streamlit Community Cloud. Main file: app.py
requirements.txt needs only:
    streamlit
    pandas

THE DYNAMIC  (this is now a stepped simulation, not a formula)
--------------------------------------------------------------
Fixed game rules:
  * Trap window = 30:00 (counts down). Rally fills 5:00 then departs.
  * Last rally can LAUNCH at 5:00 left (25:00 elapsed); departs at the buzzer.
  * Troops aren't lost -> the same troops march again and again.

Troops & hosts:
  * total troops (pool)      = players * avg
  * hosts available per wave = players // waves          (equal split)
  * rallies NEEDED per wave  = ceil(pool / cap)          (to hold everyone)
  * rallies HOSTED per wave  = min(needed, hosts_available)
        -> if the host limit bites, capacity = hosted*cap < pool and the
           overflow troops wait for a later launch.

Two march times:
  * trap_travel = host city -> bear (one way)
  * join_travel = your city -> host, when you JOIN a rally
  * march loop  = 2*trap_travel + join_travel + buffer
        A returning player can be IN a rally only if
            free_time + join_travel + buffer <= that rally's depart time.

The simulation:
  * Launches happen every `stagger` seconds (default 5:00 / waves), wave = m % W.
  * Walking the clock to 5:00-left, at each launch we gather the players whose
    troops are home AND can reach a host in time, fill up to capacity, send them
    (busy until they march to the bear and back), and let the rest wait for the
    next launch. Everyone rides every launch they can catch.
"""

import math
import pandas as pd
import streamlit as st

WINDOW = 30 * 60
FILL = 5 * 60
LAST_LAUNCH = WINDOW - FILL          # 1500s elapsed = 5:00 left

WAVE_HEX = {0: "#45c4ff", 1: "#b78bff", 2: "#4fe0a0"}

st.set_page_config(page_title="Bear Trap Rally Planner", page_icon="🐻", layout="wide")


# ----------------------------------------------------------------------------
# formatting
# ----------------------------------------------------------------------------
def fmt_clock(sec):
    s = max(0, round(sec)); m, ss = divmod(s, 60)
    return f"{m:02d}:{ss:02d}"


def fmt_left(elapsed):
    return fmt_clock(WINDOW - elapsed)


def fmt_troops(n):
    n = round(n)
    if n >= 1_000_000:
        v = n / 1_000_000
        return (f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.2f}".rstrip("0").rstrip(".")) + "M"
    if n >= 1_000:
        v = n / 1000
        return (f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}".rstrip("0").rstrip(".")) + "K"
    return f"{n:,}"


# ----------------------------------------------------------------------------
# simulation
# ----------------------------------------------------------------------------
def march_loop(trap_travel, join_travel, buffer):
    return 2 * trap_travel + join_travel + buffer


def simulate(players, avg, cap, trap_travel, join_travel, buffer, waves, stagger, march_size):
    pool = players * avg
    needed = max(1, math.ceil(pool / cap))
    marches_per_player = max(1, math.ceil(avg / march_size))   # how many rallies one player sends into
    marches_per_rally = max(1, round(cap / march_size))        # sends it takes to fill a rally
    hosts_avail = players // waves                       # equal hosts per wave
    rallies_per_wave = min(needed, hosts_avail) if hosts_avail > 0 else 0
    capacity = rallies_per_wave * cap                    # troops one wave can hold per launch
    loop = march_loop(trap_travel, join_travel, buffer)

    # launch opening times (every `stagger`), wave = m % waves
    opens = []
    m = 0
    while m * stagger <= LAST_LAUNCH + 1e-9 and m <= 400:
        opens.append((m * stagger, m % waves))
        m += 1

    free = [0.0] * players          # time each player's troops are home & free to move
    launches = []
    for open_t, lane in opens:
        depart = open_t + FILL
        if rallies_per_wave == 0:
            continue
        # players who can reach a host before this rally departs
        avail = [i for i in range(players) if free[i] + join_travel + buffer <= depart]
        avail.sort(key=lambda i: free[i])
        troops_in = 0.0
        used = 0
        for i in avail:
            if troops_in + avg <= capacity + 1e-6:
                troops_in += avg; free[i] = depart + 2 * trap_travel; used += 1
            else:
                room = capacity - troops_in
                if room > 1e-6:
                    troops_in += room; free[i] = depart + 2 * trap_travel; used += 1
                break
        rallies_used = min(rallies_per_wave, max(1, math.ceil(troops_in / cap))) if troops_in > 0 else 0
        launches.append({
            "lane": lane, "open": open_t, "depart": depart,
            "hit": depart + trap_travel, "ret": depart + 2 * trap_travel,
            "troops": troops_in, "players": used, "rallies": rallies_used,
            "marches": round(troops_in / march_size),
            "fill": (troops_in / capacity) if capacity > 0 else 0,
            "final": open_t >= LAST_LAUNCH - stagger + 1,
        })

    live = [l for l in launches if l["troops"] > 0]
    total_troops = sum(l["troops"] for l in live)
    total_rallies = sum(l["rallies"] for l in live)
    total_launches = len(live)
    first_hit = live[0]["hit"] if live else None
    last_hit = live[-1]["hit"] if live else None
    avg_fill = (total_troops / (total_launches * capacity)) if (total_launches and capacity) else 0
    catch_ok = stagger >= loop

    return {
        "pool": pool, "needed": needed, "hosts_avail": hosts_avail,
        "rallies_per_wave": rallies_per_wave, "host_slots": rallies_per_wave * waves,
        "capacity": capacity, "loop": loop, "stagger": stagger, "catch_ok": catch_ok,
        "launches": launches, "live": live, "total_troops": total_troops,
        "total_rallies": total_rallies, "total_launches": total_launches,
        "first_hit": first_hit, "last_hit": last_hit, "avg_fill": avg_fill,
        "waves": waves, "hosts_short": rallies_per_wave < needed,
        "marches_per_player": marches_per_player, "marches_per_rally": marches_per_rally,
        "total_marches": round(total_troops / march_size), "march_size": march_size,
    }


def best_stagger(trap_travel, join_travel, buffer, waves):
    """Default stagger: the tighter of the natural 5:00/waves and the march loop."""
    nat = FILL / waves
    return int(round(nat))


# ----------------------------------------------------------------------------
# styling
# ----------------------------------------------------------------------------
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

    .hero{text-align:center; padding:6px 0 14px;}
    .hero .eyebrow{font-family:var(--mono); font-size:11px; letter-spacing:.34em; text-transform:uppercase; color:var(--ember);}
    .hero h1{font-family:var(--disp); font-weight:700; font-size:clamp(26px,4.4vw,40px); margin:6px 0 4px;
      background:linear-gradient(180deg,#fff,#ffca7a); -webkit-background-clip:text; background-clip:text; color:transparent;}
    .hero p{color:var(--muted); font-size:14px; max-width:640px; margin:0 auto;}

    .card{background:linear-gradient(180deg,var(--panel),#0c1119); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin-bottom:14px;}
    .card.glow{box-shadow:0 24px 60px -42px rgba(255,146,51,.45);}
    .ctitle{font-family:var(--disp); font-weight:600; font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:var(--ember2); margin-bottom:10px; display:flex; align-items:center; gap:9px;}
    .ctitle:before{content:""; width:16px; height:2px; background:var(--ember); flex:none;}

    .cmp{display:grid; grid-template-columns:repeat(3,1fr); gap:12px;}
    @media(max-width:640px){.cmp{grid-template-columns:1fr;}}
    .cmpc{background:#0e1521; border:1px solid var(--line); border-radius:14px; padding:14px 16px; text-align:center; position:relative;}
    .cmpc.sel{border-color:var(--ember); box-shadow:0 0 0 1px var(--ember), 0 16px 40px -28px rgba(255,146,51,.6);}
    .cmpc.dead{opacity:.45;}
    .cmpc .wv{font-family:var(--disp); font-weight:600; font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);}
    .cmpc .hits{font-family:var(--disp); font-weight:700; font-size:30px; color:var(--ember2); line-height:1.05; margin:4px 0;}
    .cmpc .hits small{font-size:12px; color:var(--muted); font-weight:500;}
    .cmpc .det{font-family:var(--mono); font-size:11px; color:var(--faint); line-height:1.55;}
    .cmpc .tag{position:absolute; top:-9px; left:50%; transform:translateX(-50%); font-family:var(--mono); font-size:9px; letter-spacing:.1em; text-transform:uppercase; padding:2px 8px; border-radius:20px;}
    .cmpc .tag.pick{background:var(--ember); color:#1a1206;}
    .cmpc .tag.best{background:#2a3344; color:#cbd5e1;}
    .cmpc .tag.no{background:rgba(255,93,98,.25); color:#ffb3b5;}

    .bignum{text-align:center;}
    .bignum .k{font-family:var(--mono); font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint);}
    .bignum .v{font-family:var(--disp); font-weight:700; font-size:clamp(30px,5.5vw,46px); color:var(--ember2); line-height:1.05; text-shadow:0 0 30px rgba(255,146,51,.25);}
    .bignum .s{color:var(--muted); font-size:13px; margin-top:4px;}

    .statrow{display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:12px;}
    @media(max-width:640px){.statrow{grid-template-columns:repeat(2,1fr);}}
    .stat{background:#0e1521; border:1px solid var(--line); border-radius:11px; padding:11px 13px;}
    .stat .k{font-family:var(--mono); font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--faint);}
    .stat .v{font-family:var(--mono); font-size:18px; font-weight:600; margin-top:3px;}
    .stat .v.em{color:var(--ember2);} .stat .v.blue{color:var(--w1);} .stat .v.bad{color:var(--danger);}

    .warn{display:flex; gap:10px; align-items:flex-start; font-size:13px; border-radius:11px; padding:10px 13px; border:1px solid; margin-bottom:8px;}
    .warn .ic{font-family:var(--disp); font-weight:700; flex:none;}
    .warn.bad{background:rgba(255,93,98,.08); border-color:rgba(255,93,98,.3); color:#ffb3b5;} .warn.bad .ic{color:var(--danger);}
    .warn.good{background:rgba(79,224,160,.07); border-color:rgba(79,224,160,.28); color:#a9efcf;} .warn.good .ic{color:var(--ok);}
    .warn.info{background:rgba(69,196,255,.06); border-color:rgba(69,196,255,.25); color:#bfe6ff;} .warn.info .ic{color:var(--w1);}

    .ruler{position:relative; height:18px; margin:2px 0;}
    .ruler .tk{position:absolute; top:0; bottom:0; width:1px; background:rgba(255,255,255,.12);}
    .ruler .lb{position:absolute; top:0; transform:translateX(-50%); font-family:var(--mono); font-size:10px; color:var(--faint);}
    .track{position:relative; height:30px; border-radius:8px; background:rgba(255,255,255,.025); border:1px solid var(--line); margin-top:9px;}
    .track .tag{position:absolute; left:8px; top:50%; transform:translateY(-50%); font-family:var(--mono); font-size:10px; color:var(--muted); z-index:3; text-shadow:0 0 6px #000;}
    .gl{position:absolute; top:0; bottom:0; width:1px; background:rgba(255,255,255,.04);}
    .cyc{position:absolute; top:50%; transform:translateY(-50%); height:7px; border-radius:6px; opacity:.92;}
    .cyc .imp{position:absolute; right:-5px; top:50%; transform:translateY(-50%); width:10px; height:10px; border-radius:50%; background:var(--ember2); box-shadow:0 0 8px var(--ember2);}
    .dead{position:absolute; top:18px; height:160px; right:0; background:repeating-linear-gradient(45deg,rgba(255,93,98,.10),rgba(255,93,98,.10) 6px,transparent 6px,transparent 12px); border-left:1px dashed rgba(255,93,98,.5); border-radius:0 8px 8px 0;}
    .leg{display:flex; flex-wrap:wrap; gap:14px; margin-top:12px; font-size:12px; color:var(--muted);}
    .leg .it{display:flex; align-items:center; gap:7px;}
    .sw{width:20px; height:7px; border-radius:4px;}

    .how{font-size:13px; color:var(--muted); line-height:1.65;}
    .how b{color:var(--ink);} .how code{font-family:var(--mono); background:rgba(255,255,255,.05); padding:1px 6px; border-radius:5px; color:var(--ember2); font-size:12px;}
    div[data-testid="stDataFrame"]{font-family:var(--mono) !important; font-size:12.5px !important;}
    .stSlider label, .stRadio label, .stNumberInput label{font-family:var(--body); color:var(--muted) !important;}
    </style>
    """, unsafe_allow_html=True)


def x_pct(elapsed):
    return max(0.0, min(100.0, elapsed / WINDOW * 100))


def build_timeline(plan, waves):
    ruler = '<div class="ruler">'
    t = 0
    while t <= WINDOW:
        x = x_pct(t)
        ruler += f'<div class="tk" style="left:{x:.2f}%"></div><div class="lb" style="left:{x:.2f}%">{fmt_left(t)}</div>'
        t += 300
    ruler += "</div>"

    tracks = ""
    for lane in range(waves):
        hexc = WAVE_HEX[lane]
        track = f'<div class="track"><span class="tag">W{lane+1}</span>'
        g = 300
        while g < WINDOW:
            track += f'<div class="gl" style="left:{x_pct(g):.2f}%"></div>'; g += 300
        for cy in [c for c in plan["live"] if c["lane"] == lane]:
            l = x_pct(cy["open"]); r = x_pct(cy["hit"]); width = max(0.5, r - l)
            op = 0.35 + 0.6 * cy["fill"]
            title = (f'W{lane+1} launch {fmt_left(cy["open"])} &rarr; hit {fmt_left(cy["hit"])} '
                     f'&middot; {cy["rallies"]} rallies &middot; {fmt_troops(cy["troops"])} ({round(cy["fill"]*100)}%)')
            track += (f'<div class="cyc" title="{title}" style="left:{l:.2f}%; width:{width:.2f}%; opacity:{op:.2f}; '
                      f'background:linear-gradient(90deg,{hexc}33,{hexc});"><span class="imp"></span></div>')
        track += "</div>"
        tracks += track

    dead = f'<div class="dead" style="left:{x_pct(LAST_LAUNCH):.2f}%"></div>'
    leg = ('<div class="leg">'
           '<div class="it"><span class="sw" style="background:var(--w1)"></span>Wave 1</div>'
           '<div class="it"><span class="sw" style="background:var(--w2)"></span>Wave 2</div>'
           '<div class="it"><span class="sw" style="background:var(--w3)"></span>Wave 3</div>'
           '<div class="it"><span style="font-family:var(--mono);font-size:11px">brighter = fuller rally &middot;</span>'
           '<span style="width:9px;height:9px;border-radius:50%;background:var(--ember2);box-shadow:0 0 8px var(--ember2)"></span>impact</div>'
           '<div class="it" style="color:var(--danger)">&#9638; last launch (5:00 left)</div></div>')
    return f'<div style="position:relative;">{ruler}{tracks}{dead}</div>{leg}'


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
inject_css()

st.markdown(
    '<div class="hero"><div class="eyebrow">King Shot &middot; Bear Hunt</div>'
    '<h1>Bear Trap Rally Planner</h1>'
    '<div style="font-family:var(--mono);font-size:11px;letter-spacing:.15em;color:var(--ember2);margin:2px 0 6px;">By DrD #2041</div>'
    '<p>The whole 30:00 is simulated launch by launch. The rally cap sets how many hosts each wave '
    'needs; the two march times decide whether returning troops catch the next rally before it leaves.</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="ctitle">Battle setup</div>', unsafe_allow_html=True)
    num_players = st.slider("Players in the event", 3, 100, 10, 1)
    avg_k = st.slider("Avg troops per player — total (K)", 20, 2000, 200, 10,
                      help="How many troops one player has to send in total.")
    march_k = st.slider("Avg march size — per send (K)", 10, 2000, 100, 10,
                        help="Troops in a single rally-join. A player with more than this splits "
                             "into several marches across rallies (e.g. 300K ÷ 100K = 3 sends).")
    cap_k = st.slider("Rally capacity — a full rally (K)", 100, 6000, 500, 50)
    avg = avg_k * 1000
    march_size = march_k * 1000
    cap = cap_k * 1000

    st.markdown("**March times**")
    c1, c2 = st.columns(2)
    trap_travel = c1.number_input("To bear (s)", 5, 300, 10, 1,
                                  help="One-way march from a host's city to the bear.")
    join_travel = c2.number_input("To host (s)", 0, 300, 10, 1,
                                  help="March to reach the host when you JOIN a rally.")
    buffer = st.number_input("Tap buffer (s)", 0, 60, 5, 1,
                             help="Slack for a returning player to react and tap join.")

    st.markdown("---")
    waves = st.radio("Waves", [1, 2, 3], index=1, horizontal=True)

    loop = march_loop(trap_travel, join_travel, buffer)
    nat = FILL / waves
    default_stagger = best_stagger(trap_travel, join_travel, buffer, waves)
    stagger = st.number_input("Seconds between wave starts (stagger)", 10, 600,
                              default_stagger, 5,
                              help=f"Natural value for {waves} wave(s) = 5:00 ÷ {waves} = {fmt_clock(nat)}. "
                                   f"Keep ≥ {fmt_clock(loop)} (your march loop) so rallies fill full.")
    st.caption(f"March loop = 2×{trap_travel}s + {join_travel}s + {buffer}s = **{fmt_clock(loop)}**. "
               f"Hosts available per wave = {num_players} ÷ {waves} = **{num_players // waves}**.")

plan = simulate(num_players, avg, cap, trap_travel, join_travel, buffer, waves, stagger, march_size)

# ---- comparison 1/2/3 (each at its natural stagger) ----
st.markdown('<div class="card glow">', unsafe_allow_html=True)
st.markdown('<div class="ctitle">Compare 1 / 2 / 3 waves</div>', unsafe_allow_html=True)
sims = {w: simulate(num_players, avg, cap, trap_travel, join_travel, buffer, w,
                    best_stagger(trap_travel, join_travel, buffer, w), march_size) for w in (1, 2, 3)}
feasible = [w for w in (1, 2, 3) if sims[w]["rallies_per_wave"] > 0]
best_w = max(feasible, key=lambda w: sims[w]["total_troops"]) if feasible else 1
cmp_html = '<div class="cmp">'
for w in (1, 2, 3):
    s = sims[w]
    ok = s["rallies_per_wave"] > 0
    classes = "cmpc" + (" sel" if w == waves else "") + ("" if ok else " dead")
    if not ok:
        tag = '<div class="tag no">too many waves</div>'
    elif w == waves:
        tag = '<div class="tag pick">your pick</div>'
    elif w == best_w:
        tag = '<div class="tag best">most troops</div>'
    else:
        tag = ""
    fillnote = "rallies full" if s["avg_fill"] >= 0.985 else f'~{round(s["avg_fill"]*100)}% full'
    hostnote = (f'{s["rallies_per_wave"]} hosts/wave' +
                (f' (wanted {s["needed"]})' if s["hosts_short"] else ''))
    cmp_html += (
        f'<div class="{classes}">{tag}'
        f'<div class="wv">{w} wave{"s" if w>1 else ""}</div>'
        f'<div class="hits">{fmt_troops(s["total_troops"])}<small> troops</small></div>'
        f'<div class="det">{s["total_rallies"]} rally hits &middot; {s["total_launches"]} launches<br>'
        f'{hostnote}<br>{fillnote}</div></div>'
    )
cmp_html += "</div>"
st.markdown(cmp_html, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---- selected plan headline ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(
    f'<div class="bignum"><div class="k">Your plan: {waves} wave{"s" if waves>1 else ""}</div>'
    f'<div class="v">{fmt_troops(plan["total_troops"])}</div>'
    f'<div class="s">{plan["total_rallies"]} rally hits &middot; {plan["total_launches"]} launches &middot; '
    f'{plan["rallies_per_wave"]} hosts per wave &middot; {plan["marches_per_player"]} marches/player</div></div>',
    unsafe_allow_html=True,
)
fh = fmt_left(plan["first_hit"]) if plan["first_hit"] is not None else "—"
lh = fmt_left(plan["last_hit"]) if plan["last_hit"] is not None else "—"
host_cls = "bad" if plan["hosts_short"] else "em"
st.markdown(
    f'<div class="statrow">'
    f'<div class="stat"><div class="k">Total troops</div><div class="v em">{fmt_troops(plan["pool"])}</div></div>'
    f'<div class="stat"><div class="k">Hosts / wave</div><div class="v {host_cls}">{plan["rallies_per_wave"]}'
    f'{"/" + str(plan["needed"]) if plan["hosts_short"] else ""}</div></div>'
    f'<div class="stat"><div class="k">Hit every</div><div class="v blue">{fmt_clock(plan["stagger"])}</div></div>'
    f'<div class="stat"><div class="k">Rally fill</div>'
    f'<div class="v {"bad" if plan["avg_fill"]<0.985 else ""}">{round(plan["avg_fill"]*100)}%</div></div>'
    f'</div>'
    f'<div class="statrow">'
    f'<div class="stat"><div class="k">First hit</div><div class="v em">{fh}</div></div>'
    f'<div class="stat"><div class="k">Last hit</div><div class="v">{lh}</div></div>'
    f'<div class="stat"><div class="k">March loop</div><div class="v">{fmt_clock(plan["loop"])}</div></div>'
    f'<div class="stat"><div class="k">Catch</div>'
    f'<div class="v {"" if plan["catch_ok"] else "bad"}">{"OK" if plan["catch_ok"] else "tight"}</div></div>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ---- warnings ----
warns = []
if plan["rallies_per_wave"] == 0:
    warns.append(("bad", "!", f'{waves} waves leaves fewer than 1 host per wave ({num_players} ÷ {waves}). '
                              f'Use fewer waves.'))
if plan["hosts_short"]:
    short_cap = plan["rallies_per_wave"] * cap
    warns.append(("bad", "!", f'You need {plan["needed"]} rallies to hold {fmt_troops(plan["pool"])}, but '
                              f'{waves} waves only leaves {plan["rallies_per_wave"]} hosts per wave '
                              f'({fmt_troops(short_cap)} of room). The overflow waits for the next launch — '
                              f'fewer waves or a bigger cap fixes it.'))
if not plan["catch_ok"] and plan["rallies_per_wave"] > 0:
    warns.append(("bad", "!", f'Tight catch: launches are {fmt_clock(plan["stagger"])} apart but the march '
                              f'loop is {fmt_clock(plan["loop"])}, so troops miss some rallies and they leave '
                              f'~{round(plan["avg_fill"]*100)}% full. Widen the stagger or shorten marches.'))
elif plan["catch_ok"] and plan["rallies_per_wave"] > 0 and waves > 1:
    warns.append(("good", "+", f'Returning troops reach the next host in time — every rally fills '
                               f'(~{round(plan["avg_fill"]*100)}%).'))
if trap_travel > 40 or join_travel > 40:
    warns.append(("bad", "!", "A march over ~40s wastes window time — have hosts teleport closer to the trap."))
if plan["rallies_per_wave"] > 0:
    warns.append(("info", "i", f'Each wave opens {plan["rallies_per_wave"]} rally(s) '
                               f'({fmt_troops(plan["pool"])} ÷ {fmt_troops(cap)} cap), and across '
                               f'{waves} waves that\'s {plan["host_slots"]} hosts out of {num_players} players. '
                               f'Each player sends {plan["marches_per_player"]} march(es) of ~{fmt_troops(march_size)}; '
                               f'it takes {plan["marches_per_rally"]} to fill one rally.'))
one = sims[1]
if waves > 1 and plan["rallies_per_wave"] > 0 and plan["total_troops"] > one["total_troops"] + 1:
    warns.append(("good", "+", f'{waves} waves delivers {fmt_troops(plan["total_troops"]-one["total_troops"])} '
                               f'more than a single wave ({fmt_troops(plan["total_troops"])} vs '
                               f'{fmt_troops(one["total_troops"])}).'))

st.markdown('<div class="card">', unsafe_allow_html=True)
for kind, ic, msg in warns:
    st.markdown(f'<div class="warn {kind}"><span class="ic">{ic}</span><span>{msg}</span></div>',
                unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---- timeline ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="ctitle">Strike timeline</div>', unsafe_allow_html=True)
st.markdown(build_timeline(plan, waves), unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---- schedule tables ----
st.markdown('<div class="ctitle" style="margin:18px 2px 6px;">Launch schedule (simulated)</div>',
            unsafe_allow_html=True)
if plan["rallies_per_wave"] == 0:
    st.info("Reduce the wave count to see a schedule.")
else:
    cols = st.columns(waves)
    for lane in range(waves):
        hexc = WAVE_HEX[lane]
        lane_launches = [c for c in plan["launches"] if c["lane"] == lane and c["troops"] > 0]
        with cols[lane]:
            st.markdown(
                f'<div style="font-family:var(--disp);font-weight:700;font-size:13px;padding:4px 10px;'
                f'border-radius:7px;display:inline-block;background:{hexc}22;color:{hexc};'
                f'border:1px solid {hexc}55;">WAVE {lane+1}</div>'
                f'<div style="font-family:var(--mono);font-size:11.5px;color:var(--muted);margin:6px 0 8px;">'
                f'{len(lane_launches)} launches &middot; up to {plan["rallies_per_wave"]} rallies each</div>',
                unsafe_allow_html=True,
            )
            rows = []
            for i, cy in enumerate(lane_launches, 1):
                rows.append({
                    "#": f'{i}{"  ★" if cy["final"] else ""}',
                    "Launch": fmt_left(cy["open"]),
                    "Depart": fmt_left(cy["depart"]),
                    "Hit": fmt_left(cy["hit"]),
                    "Return": fmt_left(cy["ret"]),
                    "Rallies": cy["rallies"],
                    "Marches": cy["marches"],
                    "Troops": fmt_troops(cy["troops"]),
                    "Fill": f'{round(cy["fill"]*100)}%',
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                         height=min(80 + len(rows) * 35, 460))

# ---- how to read ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(
    f'<div class="how"><b>How it\'s simulated.</b> Times are <b>time left on the trap</b>. '
    f'Each player has <b>{fmt_troops(avg)}</b> total but sends it <b>{fmt_troops(march_size)}</b> at a time, so '
    f'{plan["marches_per_player"]} march(es) each; a {fmt_troops(cap)} rally takes {plan["marches_per_rally"]} of '
    f'those to fill. {fmt_troops(plan["pool"])} of troops ÷ {fmt_troops(cap)} cap = {plan["needed"]} rallies to hold '
    f'everyone; with {waves} waves you have {num_players // waves} hosts per wave, so each wave opens '
    f'<b>{plan["rallies_per_wave"]}</b>. A rally fills 5:00, departs, marches <code>{trap_travel}s</code> to '
    f'the bear (<b>hit</b>) and back. The clock is walked launch by launch: when troops return they march '
    f'<code>{join_travel}s</code> to the next host and join if they arrive before it leaves — otherwise they '
    f'wait for the one after. The ★ marks the last launch allowed at 5:00 left.</div>',
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

st.caption("Plans timing, hosts & troops landed — not a damage number (depends on lethality, heroes & "
           "buffs). Max reward unlocks around 1.2B damage.")
