"""
King Shot — Bear Trap Rally Planner  (Streamlit)
================================================
Deploy on Streamlit Community Cloud. Main file: app.py
requirements.txt only needs:
    streamlit
    pandas

MODEL (the important part — read this if you want to tweak the math)
--------------------------------------------------------------------
Fixed game rules:
  * Trap window = 30:00 (counts down 30:00 -> 0:00).
  * A rally fills for 5:00, then departs.
  * Last rally can be LAUNCHED at 5:00 left (so latest launch = 25:00 elapsed).
  * March = `travel` seconds each way (out and back). Bear deals no damage.

Why more waves help with MANY players but not with FEW:
  * players_per_rally = ceil(cap / avg)   -> bodies needed to fill one rally.
  * sustainable_rallies = players // players_per_rally
        = how many full rallies you can keep filling in parallel.
  * effective_waves W_eff = min(chosen_waves, sustainable_rallies).
        You can't overlap more rallies than you have players to fill.
  * WAIT PER MARCH = 5:00 / W_eff.
        Single wave  -> everyone fills in lockstep -> full 5:00 wait every march.
        W staggered waves -> a returning march drops into a rally already
        part-filled -> wait shrinks to ~5:00 / W_eff.
  * TOTAL troops sent is ~the same regardless of wave count (it's capped by
    players x cycles x troops). Waves do NOT magically add total damage -
    they cut the wait and turn one big pulse into a steady stream.
  * So: few players -> 1 wave (fuller rallies, no overlap possible).
       many players -> more waves (less wait, steady hits).
"""

import math
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------------
WINDOW = 30 * 60          # 1800s trap window
FILL = 5 * 60             # 300s rally fill
LAST_LAUNCH = WINDOW - FILL   # 1500s elapsed = 5:00 left = latest legal launch

WAVE_HEX = {1: "#45c4ff", 2: "#b78bff", 3: "#4fe0a0"}

st.set_page_config(page_title="Bear Trap Rally Planner", page_icon="🐻", layout="wide")


# ----------------------------------------------------------------------------
# formatting helpers
# ----------------------------------------------------------------------------
def fmt_clock(sec: float) -> str:
    s = max(0, round(sec))
    m, ss = divmod(s, 60)
    return f"{m:02d}:{ss:02d}"


def fmt_left(elapsed: float) -> str:
    """Time LEFT on the trap (the way the in-game timer reads)."""
    return fmt_clock(WINDOW - elapsed)


def fmt_troops(n: float) -> str:
    n = round(n)
    if n >= 1_000_000:
        v = n / 1_000_000
        txt = f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.2f}".rstrip("0").rstrip(".")
        return txt + "M"
    if n >= 1_000:
        v = n / 1000
        txt = f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}".rstrip("0").rstrip(".")
        return txt + "K"
    return f"{n:,}"


# ----------------------------------------------------------------------------
# core model
# ----------------------------------------------------------------------------
def players_per_rally(avg, cap):
    return max(1, math.ceil(cap / avg))


def sustainable_rallies(players, avg, cap):
    return max(1, players // players_per_rally(avg, cap))


def recommend_waves(players, avg, cap):
    return min(3, sustainable_rallies(players, avg, cap))


def recommend_delay(recycle, waves):
    if waves <= 1:
        return 0
    # even stagger: tile the recycle period across the waves
    return int(round(recycle / waves / 5) * 5)


def compute_plan(players, avg, cap, travel, gap, waves, wave_delay):
    p_r = players_per_rally(avg, cap)
    r_sustain = sustainable_rallies(players, avg, cap)
    w_eff = min(waves, r_sustain)

    wait = FILL / w_eff                     # avg fill-wait per march
    recycle = 2 * travel + gap + wait       # effective time between a wave's launches
    single_wait = FILL                      # what a lone wave would wait every march

    players_per_wave = players // waves
    leftover = players % waves
    pool = players_per_wave * avg

    # When recycle < FILL the wave runs overlapping rallies, so only a SLICE of
    # the wave launches at each tick (the rest are mid-cycle). This keeps the
    # total supply-correct instead of conjuring free troops.
    slice_frac = min(1.0, recycle / FILL)
    troops_per_launch = pool * slice_frac
    rallies_per_launch = max(1, math.ceil(troops_per_launch / cap)) if pool > 0 else 0
    fill_pct = round(100 * troops_per_launch / (rallies_per_launch * cap)) if rallies_per_launch else 0

    waves_data = []
    all_hits = []
    for w in range(waves):
        offset = w * wave_delay
        cycles = []
        k = 0
        while players_per_wave > 0 and k < 80:
            launch = offset + k * recycle
            if launch > LAST_LAUNCH + 0.5:
                break
            depart = launch + FILL
            hit = depart + travel
            ret = hit + travel
            cycles.append({
                "n": k + 1, "launch": launch, "depart": depart,
                "hit": hit, "ret": ret,
                "rallies": rallies_per_launch, "troops": troops_per_launch,
                "final": launch >= LAST_LAUNCH - recycle + 1,
            })
            all_hits.append(hit)
            k += 1
        waves_data.append({
            "wave": w + 1, "players": players_per_wave, "pool": pool,
            "rallies_per_launch": rallies_per_launch,
            "troops_per_launch": troops_per_launch, "fill_pct": fill_pct,
            "offset": offset, "cycles": cycles,
        })

    total_launches = sum(len(wd["cycles"]) for wd in waves_data)
    total_rallies = sum(len(wd["cycles"]) * wd["rallies_per_launch"] for wd in waves_data)
    total_troops = sum(len(wd["cycles"]) * wd["troops_per_launch"] for wd in waves_data)
    first_hit = min(all_hits) if all_hits else None
    last_hit = max(all_hits) if all_hits else None

    # how often the bear gets hit (cadence) across all waves
    cadence = recycle / w_eff if w_eff else recycle

    return {
        "p_r": p_r, "r_sustain": r_sustain, "w_eff": w_eff,
        "wait": wait, "single_wait": single_wait, "recycle": recycle,
        "cadence": cadence, "players_per_wave": players_per_wave, "leftover": leftover,
        "waves": waves_data, "total_launches": total_launches,
        "total_rallies": total_rallies, "total_troops": total_troops,
        "first_hit": first_hit, "last_hit": last_hit, "slice_frac": slice_frac,
    }


# ----------------------------------------------------------------------------
# styling
# ----------------------------------------------------------------------------
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

    :root{
      --bg:#0a0e15; --panel:#121a28; --panel2:#172234; --line:rgba(255,255,255,.07);
      --ink:#e9eef6; --muted:#8b99ad; --faint:#5b6a80;
      --ember:#ff9233; --ember2:#ffc061; --danger:#ff5d62; --ok:#4fe0a0;
      --w1:#45c4ff; --w2:#b78bff; --w3:#4fe0a0;
      --mono:'IBM Plex Mono',monospace; --disp:'Chakra Petch',sans-serif; --body:'IBM Plex Sans',sans-serif;
    }
    .stApp{
      background:
        radial-gradient(1100px 480px at 50% -160px, rgba(255,146,51,.10), transparent 70%),
        linear-gradient(180deg,#090d14,#0a0e15 45%,#080b11);
      color:var(--ink); font-family:var(--body);
    }
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

    .bignum{text-align:center; padding:6px 0 4px;}
    .bignum .k{font-family:var(--mono); font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint);}
    .bignum .v{font-family:var(--disp); font-weight:700; font-size:clamp(34px,6vw,50px); color:var(--ember2); line-height:1.05; text-shadow:0 0 30px rgba(255,146,51,.25);}
    .bignum .s{color:var(--muted); font-size:13px; margin-top:4px;}

    .statrow{display:grid; grid-template-columns:repeat(4,1fr); gap:10px;}
    @media(max-width:640px){.statrow{grid-template-columns:repeat(2,1fr);}}
    .stat{background:#0e1521; border:1px solid var(--line); border-radius:11px; padding:11px 13px;}
    .stat .k{font-family:var(--mono); font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--faint);}
    .stat .v{font-family:var(--mono); font-size:19px; font-weight:600; margin-top:3px;}
    .stat .v.em{color:var(--ember2);} .stat .v.blue{color:var(--w1);}

    .waitwrap{display:grid; grid-template-columns:1.1fr 1fr; gap:14px;}
    @media(max-width:640px){.waitwrap{grid-template-columns:1fr;}}
    .waitbar{height:18px; border-radius:9px; background:#0e1521; border:1px solid var(--line); overflow:hidden; position:relative; margin:6px 0 3px;}
    .waitbar > span{position:absolute; left:0; top:0; bottom:0; border-radius:9px;}
    .waitlabel{display:flex; justify-content:space-between; font-family:var(--mono); font-size:11px; color:var(--muted);}

    .warn{display:flex; gap:10px; align-items:flex-start; font-size:13px; border-radius:11px; padding:10px 13px; border:1px solid; margin-bottom:8px;}
    .warn .ic{font-family:var(--disp); font-weight:700; flex:none;}
    .warn.bad{background:rgba(255,93,98,.08); border-color:rgba(255,93,98,.3); color:#ffb3b5;} .warn.bad .ic{color:var(--danger);}
    .warn.good{background:rgba(79,224,160,.07); border-color:rgba(79,224,160,.28); color:#a9efcf;} .warn.good .ic{color:var(--ok);}
    .warn.info{background:rgba(69,196,255,.06); border-color:rgba(69,196,255,.25); color:#bfe6ff;} .warn.info .ic{color:var(--w1);}

    /* timeline */
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
# timeline builder (pure HTML/CSS, % positioned)
# ----------------------------------------------------------------------------
def x_pct(elapsed):
    return max(0.0, min(100.0, elapsed / WINDOW * 100))


def build_timeline(plan):
    # ruler
    ruler = '<div class="ruler">'
    t = 0
    while t <= WINDOW:
        x = x_pct(t)
        ruler += f'<div class="tk" style="left:{x:.2f}%"></div>'
        ruler += f'<div class="lb" style="left:{x:.2f}%">{fmt_left(t)}</div>'
        t += 300
    ruler += "</div>"

    tracks = ""
    for i, wd in enumerate(plan["waves"]):
        hexc = WAVE_HEX[wd["wave"]]
        track = f'<div class="track"><span class="tag">W{wd["wave"]}</span>'
        g = 300
        while g < WINDOW:
            track += f'<div class="gl" style="left:{x_pct(g):.2f}%"></div>'
            g += 300
        for cy in wd["cycles"]:
            l = x_pct(cy["launch"])
            r = x_pct(cy["hit"])
            width = max(0.5, r - l)
            title = (f'W{wd["wave"]} launch {fmt_left(cy["launch"])} left '
                     f'&rarr; hit {fmt_left(cy["hit"])} left &middot; '
                     f'{cy["rallies"]} rally &middot; {fmt_troops(cy["troops"])}')
            track += (f'<div class="cyc" title="{title}" '
                      f'style="left:{l:.2f}%; width:{width:.2f}%; '
                      f'background:linear-gradient(90deg,{hexc}33,{hexc});">'
                      f'<span class="imp"></span></div>')
        track += "</div>"
        tracks += track

    dead_left = x_pct(LAST_LAUNCH)
    dead = f'<div class="dead" style="left:{dead_left:.2f}%"></div>'

    leg = ('<div class="leg">'
           '<div class="it"><span class="sw" style="background:var(--w1)"></span>Wave 1</div>'
           '<div class="it"><span class="sw" style="background:var(--w2)"></span>Wave 2</div>'
           '<div class="it"><span class="sw" style="background:var(--w3)"></span>Wave 3</div>'
           '<div class="it"><span style="font-family:var(--mono);font-size:11px">bar = fill + march &middot;</span>'
           '<span style="width:9px;height:9px;border-radius:50%;background:var(--ember2);box-shadow:0 0 8px var(--ember2)"></span>impact</div>'
           '<div class="it" style="color:var(--danger)">&#9638; last launch (5:00 left)</div>'
           '</div>')

    return (f'<div style="position:relative;">{ruler}{tracks}{dead}</div>{leg}')


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
inject_css()

st.markdown(
    '<div class="hero"><div class="eyebrow">King Shot &middot; Bear Hunt</div>'
    '<h1>Bear Trap Rally Planner</h1>'
    '<p>Set your numbers once and everyone reads the same clock — when to launch, when it lands, '
    'and how long troops sit waiting. The trap runs 30:00 down to 0:00.</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="ctitle">Battle setup</div>', unsafe_allow_html=True)
    num_players = st.slider("Players in the event", 5, 100, 30, 1)
    avg_k = st.slider("Avg troops each player sends (K)", 20, 1500, 150, 10)
    cap_k = st.slider("Rally capacity — a full rally (K)", 100, 2000, 1000, 50)
    avg = avg_k * 1000
    cap = cap_k * 1000

    c1, c2 = st.columns(2)
    travel = c1.number_input("March one-way (s)", 5, 300, 15, 1)
    gap = c2.number_input("Relaunch gap (s)", 0, 60, 5, 1)

    st.markdown("---")
    waves = st.radio("Waves", [1, 2, 3], index=1, horizontal=True)

    # recommended values depend on the model, compute a provisional recycle
    p_r0 = players_per_rally(avg, cap)
    r_sus0 = sustainable_rallies(num_players, avg, cap)
    w_eff0 = min(waves, r_sus0)
    recycle0 = 2 * travel + gap + FILL / w_eff0
    rec_delay = recommend_delay(recycle0, waves)
    wave_delay = st.number_input("Seconds between wave starts", 0, 600,
                                 rec_delay if waves > 1 else 0, 5)

    rec_waves = recommend_waves(num_players, avg, cap)
    st.caption(
        f"Each full rally needs ~{p_r0} players. With {num_players} players you can sustain "
        f"~{r_sus0} parallel rall{'y' if r_sus0 == 1 else 'ies'} → "
        f"**recommended waves: {rec_waves}**."
    )

plan = compute_plan(num_players, avg, cap, travel, gap, waves, wave_delay)

# ---- headline ----
st.markdown('<div class="card glow">', unsafe_allow_html=True)
st.markdown(
    f'<div class="bignum"><div class="k">Troops sent into the bear</div>'
    f'<div class="v">{fmt_troops(plan["total_troops"])}</div>'
    f'<div class="s">{plan["total_rallies"]} rallies &middot; {plan["total_launches"]} launches &middot; '
    f'{waves} wave{"s" if waves > 1 else ""}</div></div>',
    unsafe_allow_html=True,
)
fh = fmt_left(plan["first_hit"]) if plan["first_hit"] is not None else "—"
lh = fmt_left(plan["last_hit"]) if plan["last_hit"] is not None else "—"
st.markdown(
    f'<div class="statrow">'
    f'<div class="stat"><div class="k">Trap opens</div><div class="v em">30:00</div></div>'
    f'<div class="stat"><div class="k">First hit</div><div class="v em">{fh}</div></div>'
    f'<div class="stat"><div class="k">Last hit</div><div class="v">{lh}</div></div>'
    f'<div class="stat"><div class="k">Hit every</div><div class="v blue">{fmt_clock(plan["cadence"])}</div></div>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ---- WAIT panel (the thing you asked for) ----
wait_pct = 100 * plan["wait"] / plan["single_wait"]
saved = plan["single_wait"] - plan["wait"]
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="ctitle">Wait time per march</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="waitwrap">'
    f'<div>'
    f'<div class="waitlabel"><span>This plan ({waves} wave{"s" if waves>1 else ""})</span>'
    f'<span style="color:var(--ember2)">{fmt_clock(plan["wait"])} per march</span></div>'
    f'<div class="waitbar"><span style="width:{wait_pct:.0f}%; background:linear-gradient(90deg,var(--ember),#e07a1f)"></span></div>'
    f'<div class="waitlabel"><span>Single big wave</span><span>05:00 per march</span></div>'
    f'<div class="waitbar"><span style="width:100%; background:#2a3344"></span></div>'
    f'</div>'
    f'<div style="font-size:13px;color:var(--muted);line-height:1.6">'
    f'Your roster can overlap <b style="color:var(--ink)">{plan["w_eff"]}</b> rall'
    f'{"y" if plan["w_eff"]==1 else "ies"} at once, so a returning march drops into a '
    f'rally that\'s already part-filled instead of starting a fresh 5:00 fill. '
    f'That cuts the wait by <b style="color:var(--ok)">{fmt_clock(saved)}</b> every cycle — '
    f'which is exactly why each wave gets through more launches.'
    f'</div></div>',
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

# ---- warnings ----
warns = []
ppw = plan["players_per_wave"]
if ppw <= 0:
    warns.append(("bad", "!", f"More waves than players. Drop to {num_players} waves or fewer."))
if plan["leftover"] > 0:
    warns.append(("info", "i", f'{plan["leftover"]} player(s) aren\'t in a wave — have them join '
                               f'open rallies instead of sitting idle.'))
if travel > 40:
    warns.append(("bad", "!", f"March is {travel}s. Over ~40s wastes window time — move rally "
                              f"leaders' cities closer to the trap."))
if ppw > 0:
    wd0 = plan["waves"][0]
    if wd0["fill_pct"] < 60 and waves > 1:
        warns.append(("info", "i", f'Splitting into {waves} waves leaves rallies only '
                                   f'~{wd0["fill_pct"]}% full. Fewer waves = fuller, harder-hitting rallies.'))
if waves > plan["r_sustain"]:
    warns.append(("info", "i", f'You picked {waves} waves but only have players to sustain '
                               f'{plan["r_sustain"]}. Extra waves don\'t cut the wait further — '
                               f'they just thin out your rallies.'))
elif waves == 1 and plan["r_sustain"] >= 2 and ppw > 0:
    warns.append(("info", "i", f'You can sustain {plan["r_sustain"]} parallel rallies. Going to '
                               f'{recommend_waves(num_players, avg, cap)} waves would cut wait per march '
                               f'from 05:00 to {fmt_clock(FILL/min(recommend_waves(num_players,avg,cap),plan["r_sustain"]))}.'))
if waves > 1 and ppw > 0:
    w1 = plan["waves"][0]
    if w1["cycles"]:
        ret0 = w1["cycles"][0]["ret"]
        if wave_delay >= ret0 - 1:
            warns.append(("good", "+", f'Wave 1 is home ({fmt_left(ret0)} left) before Wave 2 launches '
                                       f'— clean handoff, troops never sit idle.'))

if warns:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    for kind, ic, msg in warns:
        st.markdown(f'<div class="warn {kind}"><span class="ic">{ic}</span><span>{msg}</span></div>',
                    unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---- timeline ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="ctitle">Strike timeline</div>', unsafe_allow_html=True)
st.markdown(build_timeline(plan), unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---- per-wave schedule tables ----
st.markdown('<div class="ctitle" style="margin:18px 2px 6px;">Launch schedule</div>',
            unsafe_allow_html=True)
if ppw <= 0:
    st.info("Add more players or fewer waves to see a schedule.")
else:
    cols = st.columns(waves)
    for i, wd in enumerate(plan["waves"]):
        hexc = WAVE_HEX[wd["wave"]]
        with cols[i]:
            st.markdown(
                f'<div style="font-family:var(--disp);font-weight:700;font-size:13px;'
                f'padding:4px 10px;border-radius:7px;display:inline-block;'
                f'background:{hexc}22;color:{hexc};border:1px solid {hexc}55;">WAVE {wd["wave"]}</div>'
                f'<div style="font-family:var(--mono);font-size:11.5px;color:var(--muted);margin:6px 0 8px;">'
                f'{wd["players"]} players &middot; {wd["rallies_per_launch"]} rally/launch &middot; '
                f'{wd["fill_pct"]}% full &middot; {len(wd["cycles"])} launches</div>',
                unsafe_allow_html=True,
            )
            rows = []
            for cy in wd["cycles"]:
                rows.append({
                    "#": f'{cy["n"]}{"  ★" if cy["final"] else ""}',
                    "Launch": fmt_left(cy["launch"]),
                    "Depart": fmt_left(cy["depart"]),
                    "Hit": fmt_left(cy["hit"]),
                    "Return": fmt_left(cy["ret"]),
                    "Rallies": cy["rallies"],
                    "Troops": fmt_troops(cy["troops"]),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                         height=min(80 + len(rows) * 35, 460))

# ---- how to read ----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(
    f'<div class="how"><b>How to read this.</b> Every time is <b>time left on the trap</b> '
    f'(it counts down from 30:00). A group <b>launches</b> a rally, it <b>fills for 5:00</b>, '
    f'<b>departs</b>, marches <code>{travel}s</code> to the bear (<b>hit</b>), then marches back '
    f'(<b>return</b>). Waves are groups that launch staggered so the bear takes a steady stream and '
    f'returning troops always have an open rally to pour into. '
    f'Overlapping bars on a track are normal once you run multiple waves — it means new rallies open '
    f'before old ones depart, which is the whole point (and why you need enough players to staff them). '
    f'The ★ marks the final launch allowed at 5:00 left.</div>',
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

st.caption("Plans timing & troop logistics — not a damage number (that depends on your lethality, "
           "heroes & buffs). Max reward unlocks around 1.2B damage.")
