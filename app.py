"""
King Shot — Bear Trap Rally Planner  (Streamlit)
================================================
Deploy on Streamlit Community Cloud. Main file: app.py
requirements.txt needs only:
    streamlit
    pandas

THE MODEL  (read this before changing the math)
-----------------------------------------------
Fixed game rules:
  * Trap window = 30:00 (counts down 30:00 -> 0:00).
  * A rally fills for 5:00, then departs.
  * Last rally can be LAUNCHED at 5:00 left (25:00 elapsed); it departs at the buzzer.
  * March = `travel` seconds each way. Troops are not lost (bear doesn't fight back),
    so the SAME troops march over and over.

How waves actually work (the important bit):
  * EVERY player rides EVERY launch. Waves are NOT separate groups of people.
  * A "wave" is a staggered rally slot. With W waves, a fresh rally launches every
    `5:00 / W` seconds, and the whole roster rotates through all of them:
        ride wave 1 -> march home -> wave 2 is part-filled -> ride it -> home ->
        wave 1's next rally is part-filled -> ride it -> ...
  * Because everyone rides every launch, MORE WAVES = MORE LAUNCHES = MORE HITS.
        launches in window ~= 1500 / stagger ,  stagger = 5:00 / W
        W=1 -> a launch every 5:00   (~6 hits)
        W=2 -> a launch every 2:30   (~11 hits)
        W=3 -> a launch every 1:40   (~16 hits)
  * The HARD limit is march time: you can't launch faster than troops get home and
    back, so stagger >= 2*travel (+ a moment to tap-join). Long marches kill the
    benefit of extra waves.
  * The SOFT limit is coordination: W waves means W rallies filling at once (need
    that many leaders), and everyone must re-join within `stagger - 2*travel` of
    getting home. Great for a sharp alliance, risky for a slow one.
"""

import math
import pandas as pd
import streamlit as st

WINDOW = 30 * 60          # 1800s
FILL = 5 * 60             # 300s rally fill
LAST_LAUNCH = WINDOW - FILL   # 1500s elapsed = 5:00 left

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
# model
# ----------------------------------------------------------------------------
def min_stagger(travel, gap):
    """Tightest launch spacing: troops must get home (2*travel) plus a moment to join."""
    return 2 * travel + gap


def natural_stagger(waves):
    return FILL / waves


def launches_count(travel, gap, waves, stagger=None):
    if stagger is None:
        stagger = max(natural_stagger(waves), min_stagger(travel, gap))
    stagger = max(stagger, min_stagger(travel, gap))
    return int(LAST_LAUNCH // stagger) + 1, stagger


def compute_plan(players, avg, cap, travel, gap, waves, stagger_in):
    pool = players * avg
    rallies_per_launch = max(1, math.ceil(pool / cap))
    fill_pct = round(100 * pool / (rallies_per_launch * cap))

    min_st = min_stagger(travel, gap)
    stagger = max(stagger_in, min_st)
    clamped = stagger_in < min_st

    concurrent = max(1, math.ceil(FILL / stagger))      # rallies filling at once
    leaders_needed = concurrent * rallies_per_launch

    # all launches; everyone rides each one; color by wave slot (m % waves)
    launches = []
    m = 0
    while True:
        open_t = m * stagger
        if open_t > LAST_LAUNCH + 0.5:
            break
        depart = open_t + FILL
        hit = depart + travel
        ret = hit + travel
        launches.append({
            "m": m, "lane": m % waves, "open": open_t, "depart": depart,
            "hit": hit, "ret": ret, "rallies": rallies_per_launch, "troops": pool,
            "final": open_t >= LAST_LAUNCH - stagger + 1,
        })
        m += 1
        if m > 200:
            break

    total_launches = len(launches)
    total_troops = total_launches * pool
    total_rallies = total_launches * rallies_per_launch
    first_hit = launches[0]["hit"] if launches else None
    last_hit = launches[-1]["hit"] if launches else None
    wait_per_cycle = max(0, stagger - 2 * travel)       # time idling/filling after return

    return {
        "pool": pool, "rallies_per_launch": rallies_per_launch, "fill_pct": fill_pct,
        "stagger": stagger, "min_stagger": min_st, "clamped": clamped,
        "concurrent": concurrent, "leaders_needed": leaders_needed,
        "launches": launches, "total_launches": total_launches,
        "total_troops": total_troops, "total_rallies": total_rallies,
        "first_hit": first_hit, "last_hit": last_hit, "wait_per_cycle": wait_per_cycle,
        "waves": waves,
    }


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
    .hero p{color:var(--muted); font-size:14px; max-width:600px; margin:0 auto;}

    .card{background:linear-gradient(180deg,var(--panel),#0c1119); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin-bottom:14px;}
    .card.glow{box-shadow:0 24px 60px -42px rgba(255,146,51,.45);}
    .ctitle{font-family:var(--disp); font-weight:600; font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:var(--ember2); margin-bottom:10px; display:flex; align-items:center; gap:9px;}
    .ctitle:before{content:""; width:16px; height:2px; background:var(--ember); flex:none;}

    /* comparison cards */
    .cmp{display:grid; grid-template-columns:repeat(3,1fr); gap:12px;}
    @media(max-width:640px){.cmp{grid-template-columns:1fr;}}
    .cmpc{background:#0e1521; border:1px solid var(--line); border-radius:14px; padding:14px 16px; text-align:center; position:relative;}
    .cmpc.sel{border-color:var(--ember); box-shadow:0 0 0 1px var(--ember), 0 16px 40px -28px rgba(255,146,51,.6);}
    .cmpc .wv{font-family:var(--disp); font-weight:600; font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);}
    .cmpc .hits{font-family:var(--disp); font-weight:700; font-size:38px; color:var(--ember2); line-height:1.05; margin:4px 0;}
    .cmpc .hits small{font-size:13px; color:var(--muted); font-weight:500;}
    .cmpc .det{font-family:var(--mono); font-size:11.5px; color:var(--faint); line-height:1.5;}
    .cmpc .tag{position:absolute; top:-9px; left:50%; transform:translateX(-50%); font-family:var(--mono); font-size:9px; letter-spacing:.1em; text-transform:uppercase; background:var(--ember); color:#1a1206; padding:2px 8px; border-radius:20px;}

    .bignum{text-align:center;}
    .bignum .k{font-family:var(--mono); font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint);}
    .bignum .v{font-family:var(--disp); font-weight:700; font-size:clamp(30px,5.5vw,46px); color:var(--ember2); line-height:1.05; text-shadow:0 0 30px rgba(255,146,51,.25);}
    .bignum .s{color:var(--muted); font-size:13px; margin-top:4px;}

    .statrow{display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:12px;}
    @media(max-width:640px){.statrow{grid-template-columns:repeat(2,1fr);}}
    .stat{background:#0e1521; border:1px solid var(--line); border-radius:11px; padding:11px 13px;}
    .stat .k{font-family:var(--mono); font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--faint);}
    .stat .v{font-family:var(--mono); font-size:18px; font-weight:600; margin-top:3px;}
    .stat .v.em{color:var(--ember2);} .stat .v.blue{color:var(--w1);}

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


# ----------------------------------------------------------------------------
# timeline
# ----------------------------------------------------------------------------
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
        for cy in [c for c in plan["launches"] if c["lane"] == lane]:
            l = x_pct(cy["open"]); r = x_pct(cy["hit"]); width = max(0.5, r - l)
            title = (f'W{lane+1} launch {fmt_left(cy["open"])} left &rarr; hit {fmt_left(cy["hit"])} left '
                     f'&middot; {fmt_troops(cy["troops"])}')
            track += (f'<div class="cyc" title="{title}" style="left:{l:.2f}%; width:{width:.2f}%; '
                      f'background:linear-gradient(90deg,{hexc}33,{hexc});"><span class="imp"></span></div>')
        track += "</div>"
        tracks += track

    dead = f'<div class="dead" style="left:{x_pct(LAST_LAUNCH):.2f}%"></div>'
    leg = ('<div class="leg">'
           '<div class="it"><span class="sw" style="background:var(--w1)"></span>Wave 1</div>'
           '<div class="it"><span class="sw" style="background:var(--w2)"></span>Wave 2</div>'
           '<div class="it"><span class="sw" style="background:var(--w3)"></span>Wave 3</div>'
           '<div class="it"><span style="font-family:var(--mono);font-size:11px">bar = fill + march &middot;</span>'
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
    '<p>Everyone rides every launch. Staggering into more waves means a rally leaves more '
    'often, so you land more hits in the 30:00 window — as long as troops can march home in time.</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="ctitle">Battle setup</div>', unsafe_allow_html=True)
    num_players = st.slider("Players in the event", 3, 100, 10, 1)
    avg_k = st.slider("Avg troops each player sends (K)", 20, 2000, 100, 10)
    cap_k = st.slider("Rally capacity — a full rally (K)", 100, 6000, 1000, 50)
    avg = avg_k * 1000
    cap = cap_k * 1000

    c1, c2 = st.columns(2)
    travel = c1.number_input("March one-way (s)", 5, 300, 15, 1)
    gap = c2.number_input("Join buffer (s)", 0, 60, 5, 1,
                          help="Seconds for returning troops to tap into the next rally.")

    st.markdown("---")
    waves = st.radio("Waves", [1, 2, 3], index=1, horizontal=True)

    nat = natural_stagger(waves)
    min_st = min_stagger(travel, gap)
    default_stagger = int(round(max(nat, min_st)))
    stagger_in = st.number_input("Seconds between wave starts (stagger)", 10, 600,
                                 default_stagger, 5,
                                 help=f"Natural value for {waves} wave(s) is 5:00 ÷ {waves} = {fmt_clock(nat)}.")
    st.caption(f"A launch leaves every **{fmt_clock(max(stagger_in, min_st))}**. "
               f"Tightest your march allows: **{fmt_clock(min_st)}** (2× march + buffer).")

plan = compute_plan(num_players, avg, cap, travel, gap, waves, stagger_in)

# ---- comparison: 1 vs 2 vs 3 waves (the core question) ----
st.markdown('<div class="card glow">', unsafe_allow_html=True)
st.markdown('<div class="ctitle">Hits in 30:00 — 1 vs 2 vs 3 waves</div>', unsafe_allow_html=True)
cmp_html = '<div class="cmp">'
best_w = max(range(1, 4), key=lambda w: launches_count(travel, gap, w)[0])
for w in (1, 2, 3):
    cnt, st_w = launches_count(travel, gap, w)
    sel = " sel" if w == waves else ""
    tag = '<div class="tag">your pick</div>' if w == waves else (
        '<div class="tag" style="background:#2a3344;color:#cbd5e1">most hits</div>' if w == best_w and w != waves else "")
    cmp_html += (
        f'<div class="cmpc{sel}">{tag}'
        f'<div class="wv">{w} wave{"s" if w>1 else ""}</div>'
        f'<div class="hits">{cnt}<small> hits</small></div>'
        f'<div class="det">a launch every {fmt_clock(st_w)}<br>'
        f'{fmt_troops(cnt * plan["pool"])} troops total</div></div>'
    )
cmp_html += "</div>"
st.markdown(cmp_html, unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:12.5px;color:var(--muted);margin-top:10px;">More waves launch more often, '
    'so they land more hits — until the stagger hits your march floor (then extra waves stop helping). '
    'The catch: more waves need more rally leaders and faster re-joining.</div>',
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

# ---- selected plan headline ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(
    f'<div class="bignum"><div class="k">Your plan: {waves} wave{"s" if waves>1 else ""}</div>'
    f'<div class="v">{plan["total_launches"]} hits</div>'
    f'<div class="s">{fmt_troops(plan["total_troops"])} troops sent &middot; '
    f'{plan["total_rallies"]} rallies &middot; everyone rides every launch</div></div>',
    unsafe_allow_html=True,
)
fh = fmt_left(plan["first_hit"]) if plan["first_hit"] is not None else "—"
lh = fmt_left(plan["last_hit"]) if plan["last_hit"] is not None else "—"
st.markdown(
    f'<div class="statrow">'
    f'<div class="stat"><div class="k">First hit</div><div class="v em">{fh}</div></div>'
    f'<div class="stat"><div class="k">Last hit</div><div class="v">{lh}</div></div>'
    f'<div class="stat"><div class="k">Hit every</div><div class="v blue">{fmt_clock(plan["stagger"])}</div></div>'
    f'<div class="stat"><div class="k">Wait per cycle</div><div class="v">{fmt_clock(plan["wait_per_cycle"])}</div></div>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ---- warnings ----
warns = []
if plan["clamped"]:
    warns.append(("bad", "!", f'A launch every {fmt_clock(stagger_in)} is impossible — troops need '
                              f'{fmt_clock(2*travel)} to march home and back (+{gap}s to join). '
                              f'Capped at {fmt_clock(plan["stagger"])}.'))
if travel > 40:
    warns.append(("bad", "!", f"March is {travel}s. Over ~40s wastes window time and forces a wide "
                              f"stagger — move rally leaders' cities closer to the trap."))
if plan["rallies_per_launch"] > 1:
    warns.append(("info", "i", f'Your {fmt_troops(plan["pool"])} of troops need '
                               f'{plan["rallies_per_launch"]} rallies per launch (cap {fmt_troops(cap)}). '
                               f'With {waves} waves that\'s {plan["leaders_needed"]} rallies open at once — '
                               f'line up that many leaders.'))
else:
    warns.append(("info", "i", f'Everyone fits in one rally per launch ({plan["fill_pct"]}% of cap). '
                               f'You need {plan["concurrent"]} leader(s) holding rallies open at once.'))
# more-waves payoff vs 1 wave
one_cnt = launches_count(travel, gap, 1)[0]
if waves > 1:
    extra = plan["total_launches"] - one_cnt
    if extra > 0:
        warns.append(("good", "+", f'{waves} waves lands {extra} more hits than a single wave '
                                   f'({plan["total_launches"]} vs {one_cnt}) — and cuts the wait between '
                                   f'marches from {fmt_clock(FILL-2*travel)} to {fmt_clock(plan["wait_per_cycle"])}.'))
    else:
        warns.append(("info", "i", f'With a {travel}s march, {waves} waves can\'t launch any faster than '
                                   f'1 wave here — the march time is the bottleneck, not the wave count.'))
# coordination note as waves rise
if waves >= 2:
    warns.append(("info", "i", f'Tight plan: a launch every {fmt_clock(plan["stagger"])} means everyone '
                               f'must re-join within {fmt_clock(plan["wait_per_cycle"])} of getting home. '
                               f'Smooth if your alliance is quick; if people are slow, drop a wave.'))

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

# ---- schedule tables (one per wave slot) ----
st.markdown('<div class="ctitle" style="margin:18px 2px 6px;">Launch schedule</div>', unsafe_allow_html=True)
cols = st.columns(waves)
for lane in range(waves):
    hexc = WAVE_HEX[lane]
    lane_launches = [c for c in plan["launches"] if c["lane"] == lane]
    with cols[lane]:
        st.markdown(
            f'<div style="font-family:var(--disp);font-weight:700;font-size:13px;padding:4px 10px;'
            f'border-radius:7px;display:inline-block;background:{hexc}22;color:{hexc};'
            f'border:1px solid {hexc}55;">WAVE {lane+1}</div>'
            f'<div style="font-family:var(--mono);font-size:11.5px;color:var(--muted);margin:6px 0 8px;">'
            f'{len(lane_launches)} launches &middot; everyone rides &middot; '
            f'{plan["rallies_per_launch"]} rally each</div>',
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
                "Troops": fmt_troops(cy["troops"]),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                     height=min(80 + len(rows) * 35, 460))

# ---- how to read ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(
    f'<div class="how"><b>How to read this.</b> Times are <b>time left on the trap</b> (counts down '
    f'from 30:00). A rally is <b>launched</b> (opened), <b>fills 5:00</b>, <b>departs</b>, marches '
    f'<code>{travel}s</code> to the bear (<b>hit</b>), then marches back (<b>return</b>). '
    f'<b>The whole roster rides every launch</b> — when troops get home they pour into whichever wave\'s '
    f'rally is already part-filled, so they barely wait. More waves = a launch leaves more often = more '
    f'hits, capped by your march time. The ★ marks the final launch allowed at 5:00 left.</div>',
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

st.caption("Plans timing & hit count — not a damage number (that depends on lethality, heroes & buffs). "
           "Max reward unlocks around 1.2B damage.")
