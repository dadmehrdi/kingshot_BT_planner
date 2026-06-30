
"""
King Shot — Bear Trap Rally Planner
Author: Dr. D. #2041

requirements.txt:
streamlit
pandas

Current model:
- Waves are limited to 1–3.
- The app calculates the rally leaders/hosts needed; it does not ask for host count.
- Inputs use short K-based labels: Troop cap (K) and Rally cap (K).
- Rally cap is the same capacity regardless of who hosts.
- For every hit, rallies opened = ceil(total troop pool / rally cap). No empty rallies.
"""

import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st

WINDOW = 30 * 60
FILL = 5 * 60
LAST_OPEN = WINDOW - FILL

st.set_page_config(page_title="Bear Trap Rally Planner", page_icon="BT", layout="wide")


def fmt_clock(sec: float) -> str:
    sec = max(0, int(round(sec)))
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}"


def fmt_left(elapsed: float) -> str:
    return fmt_clock(WINDOW - elapsed)


def fmt_k(n: float) -> str:
    n = float(n)
    if abs(n - round(n)) < 1e-9:
        return f"{int(round(n)):,}K"
    return f"{n:,.1f}K"


def fmt_troops(n: float) -> str:
    n = int(round(n))
    if n >= 1_000_000:
        v = n / 1_000_000
        return (f"{v:.1f}" if abs(v - round(v)) > 1e-9 else f"{int(round(v))}") + "M"
    if n >= 1_000:
        v = n / 1_000
        return (f"{v:.1f}" if abs(v - round(v)) > 1e-9 else f"{int(round(v))}") + "K"
    return f"{n:,}"


def pct(x: float) -> str:
    return f"{x:.0%}"


@dataclass
class Plan:
    players: int
    waves: int
    troop_cap_k: int
    rally_cap_k: int
    troop_cap: int
    rally_cap: int
    pool: int
    rallies_per_hit: int
    rally_leaders_per_hit: int
    natural_stagger: float
    requested_stagger: float
    min_stagger: float
    stagger: float
    spacing_increased: bool
    catch_buffer: float
    overlapping_waves: int
    peak_open_rallies: int
    peak_rally_leaders_needed: int
    avg_per_rally: float
    fill_pct: float
    launches: list
    total_hits: int
    total_rallies: int
    total_troops: int


def compute_plan(
    players: int,
    waves: int,
    troop_cap_k: int,
    rally_cap_k: int,
    march_to_bear: int,
    reach_host: int,
    tap_buffer: int,
    custom_stagger: Optional[float],
) -> Plan:
    waves = max(1, min(3, waves))
    troop_cap = troop_cap_k * 1000
    rally_cap = rally_cap_k * 1000
    pool = players * troop_cap

    # Exact rallies needed for each hit. Rally cap is the same for every host.
    # No empty rallies are opened.
    rallies_per_hit = max(1, math.ceil(pool / rally_cap))
    rally_leaders_per_hit = rallies_per_hit

    natural_stagger = FILL / waves
    requested_stagger = custom_stagger if custom_stagger is not None else natural_stagger
    min_stagger = 2 * march_to_bear + reach_host + tap_buffer
    stagger = max(requested_stagger, min_stagger)
    spacing_increased = stagger > requested_stagger + 1e-9
    catch_buffer = stagger - min_stagger

    # Rallies stay open for 5:00. If waves are staggered, several wave slots can be open at once.
    overlapping_waves = min(waves, max(1, math.ceil(FILL / stagger)))
    peak_open_rallies = overlapping_waves * rallies_per_hit
    peak_rally_leaders_needed = peak_open_rallies

    avg_per_rally = pool / rallies_per_hit
    fill_pct = avg_per_rally / rally_cap

    launches = []
    i = 0
    open_t = 0.0
    while open_t <= LAST_OPEN + 1e-9:
        depart = open_t + FILL
        hit = depart + march_to_bear
        ret = hit + march_to_bear
        launches.append({
            "Hit #": i + 1,
            "Wave": (i % waves) + 1,
            "Open": fmt_left(open_t),
            "Depart": fmt_left(depart),
            "Hit": fmt_left(hit),
            "Return": fmt_left(ret),
            "Rallies opened": rallies_per_hit,
            "Rally leaders needed": rally_leaders_per_hit,
            "Troops sent": fmt_troops(pool),
            "Avg troops/rally": fmt_troops(avg_per_rally),
            "Fill": pct(fill_pct),
            "Final open": "Yes" if abs(open_t - LAST_OPEN) < 1e-9 else "",
        })
        i += 1
        open_t = i * stagger

    return Plan(
        players=players,
        waves=waves,
        troop_cap_k=troop_cap_k,
        rally_cap_k=rally_cap_k,
        troop_cap=troop_cap,
        rally_cap=rally_cap,
        pool=pool,
        rallies_per_hit=rallies_per_hit,
        rally_leaders_per_hit=rally_leaders_per_hit,
        natural_stagger=natural_stagger,
        requested_stagger=requested_stagger,
        min_stagger=min_stagger,
        stagger=stagger,
        spacing_increased=spacing_increased,
        catch_buffer=catch_buffer,
        overlapping_waves=overlapping_waves,
        peak_open_rallies=peak_open_rallies,
        peak_rally_leaders_needed=peak_rally_leaders_needed,
        avg_per_rally=avg_per_rally,
        fill_pct=fill_pct,
        launches=launches,
        total_hits=len(launches),
        total_rallies=len(launches) * rallies_per_hit,
        total_troops=len(launches) * pool,
    )


def css() -> None:
    st.markdown("""
    <style>
    :root{
      --bg:#070b12; --panel:#111a29; --line:rgba(255,255,255,.10);
      --ink:#edf5ff; --muted:#9aaaBF; --gold:#ffbc58; --blue:#58c7ff;
      --purple:#b990ff; --green:#55e6a5; --red:#ff6470;
    }
    .stApp{
      background:
        radial-gradient(900px 360px at 15% -8%, rgba(88,199,255,.20), transparent 60%),
        radial-gradient(760px 360px at 90% 0%, rgba(255,188,88,.18), transparent 62%),
        radial-gradient(780px 500px at 45% 112%, rgba(185,144,255,.12), transparent 62%),
        linear-gradient(180deg,#0b1020,#070b12 45%,#050810);
      color:var(--ink);
    }
    .block-container{max-width:1240px;padding-top:1.1rem;}
    section[data-testid="stSidebar"]{background:linear-gradient(180deg,#111a29,#070b12);border-right:1px solid var(--line);}
    h1,h2,h3{letter-spacing:.2px;}
    .hero{
      border:1px solid var(--line); border-radius:28px; padding:24px 28px; margin-bottom:18px;
      background:linear-gradient(135deg,rgba(255,188,88,.18),rgba(88,199,255,.12),rgba(185,144,255,.16)),rgba(17,26,41,.80);
      box-shadow:0 18px 70px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.05);
    }
    .kicker{color:var(--gold);font-family:monospace;font-weight:800;text-transform:uppercase;letter-spacing:.15em;font-size:.82rem;}
    .title{font-size:2.55rem;font-weight:900;line-height:1.05;margin:.25rem 0;}
    .byline{color:var(--muted);font-family:monospace;font-size:.95rem;}
    .copy{color:#cbd7e8;margin-top:.7rem;max-width:850px;}
    .card{background:rgba(17,26,41,.84);border:1px solid var(--line);border-radius:20px;padding:16px 18px;margin:12px 0;box-shadow:0 12px 40px rgba(0,0,0,.22);}
    .pill{display:inline-block;padding:5px 10px;margin:3px 5px 3px 0;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.055);font-family:monospace;font-size:.84rem;color:#dce8f8;}
    div[data-testid="stMetric"]{background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.025));border:1px solid var(--line);border-radius:18px;padding:14px 15px;}
    div[data-testid="stMetricLabel"]{color:#aab8cc;}
    .footer{text-align:center;color:var(--muted);font-family:monospace;font-size:.84rem;margin:22px 0 8px;}
    </style>
    """, unsafe_allow_html=True)


css()

with st.sidebar:
    st.markdown("### Battle setup")
    players = st.slider("Players", 3, 100, 10, 1)
    waves = st.slider("Waves", 1, 3, 2, 1)

    st.markdown("### Caps")
    troop_cap_k = st.slider("Troop cap (K)", 20, 2_000, 200, 10)
    rally_cap_k = st.slider("Rally cap (K)", 100, 6_000, 500, 50)

    st.markdown("### Timing")
    march_to_bear = st.slider("March to bear, one way (sec)", 1, 120, 10, 1)
    reach_host = st.slider("Reach rally host (sec)", 0, 90, 10, 1)
    tap_buffer = st.slider("Join buffer (sec)", 0, 90, 5, 1)

    custom_on = st.checkbox("Custom launch spacing", value=False)
    custom_stagger = None
    if custom_on:
        custom_stagger = st.slider("Launch spacing (sec)", 30, 300, int(FILL / waves), 5)

plan = compute_plan(
    players=players,
    waves=waves,
    troop_cap_k=troop_cap_k,
    rally_cap_k=rally_cap_k,
    march_to_bear=march_to_bear,
    reach_host=reach_host,
    tap_buffer=tap_buffer,
    custom_stagger=custom_stagger,
)

st.markdown("""
<div class="hero">
  <div class="kicker">King Shot Planner</div>
  <div class="title">Bear Trap Rally Planner</div>
  <div class="byline">Author: Dr. D. #2041</div>
  <div class="copy">Plan clean waves, calculate the rally leaders needed, avoid empty rallies, and check whether players can catch the next wave.</div>
</div>
""", unsafe_allow_html=True)

st.subheader("Plan snapshot")
cols = st.columns(4)
cols[0].metric("Hits in window", plan.total_hits)
cols[1].metric("Rallies per hit", plan.rallies_per_hit)
cols[2].metric("Leaders per hit", plan.rally_leaders_per_hit)
cols[3].metric("Peak leaders needed", plan.peak_rally_leaders_needed)

cols = st.columns(4)
cols[0].metric("Troop pool / hit", fmt_troops(plan.pool))
cols[1].metric("Avg troops / rally", fmt_troops(plan.avg_per_rally))
cols[2].metric("Launch spacing", fmt_clock(plan.stagger))
cols[3].metric("Rally fill", pct(plan.fill_pct))

st.markdown(f"""
<div class="card">
  <span class="pill">{plan.players} players</span>
  <span class="pill">{plan.waves} waves</span>
  <span class="pill">{fmt_k(plan.troop_cap_k)} troop cap</span>
  <span class="pill">{fmt_k(plan.rally_cap_k)} rally cap</span>
  <span class="pill">{plan.rallies_per_hit} rallies per hit</span>
  <span class="pill">{plan.peak_rally_leaders_needed} peak leaders needed</span>
</div>
""", unsafe_allow_html=True)

st.subheader("Logistics equations")
checks = pd.DataFrame([
    {"Check": "Troop pool per hit", "Equation": f"{players} players × {fmt_k(troop_cap_k)}", "Result": fmt_troops(plan.pool), "Status": "OK"},
    {"Check": "Rallies per hit", "Equation": f"ceil({fmt_troops(plan.pool)} / {fmt_k(rally_cap_k)})", "Result": plan.rallies_per_hit, "Status": "No empty rallies"},
    {"Check": "Rally leaders per hit", "Equation": "same as rallies per hit", "Result": plan.rally_leaders_per_hit, "Status": "Calculated"},
    {"Check": "Peak leaders needed", "Equation": f"{plan.overlapping_waves} overlapping wave slot(s) × {plan.rallies_per_hit} rallies", "Result": plan.peak_rally_leaders_needed, "Status": "Calculated"},
    {"Check": "Catch next wave", "Equation": f"{fmt_clock(plan.stagger)} ≥ 2×{march_to_bear}s + {reach_host}s + {tap_buffer}s", "Result": fmt_clock(plan.min_stagger), "Status": "OK" if not plan.spacing_increased else "Spacing increased"},
])
st.dataframe(checks, hide_index=True, use_container_width=True)

st.success(f"The planner opens exactly {plan.rallies_per_hit} rallies per hit. Extra people can host if needed, but the app does not create empty rallies.")

if plan.spacing_increased:
    st.warning(f"Spacing was increased from {fmt_clock(plan.requested_stagger)} to {fmt_clock(plan.stagger)} so players can return, reach the host, and join.")
else:
    st.info(f"Catch timing passes. Extra catch buffer is about {fmt_clock(plan.catch_buffer)}.")

if players == 10 and waves == 2 and troop_cap_k == 200 and rally_cap_k == 500:
    st.markdown("""
    <div class="card">
      <b>Example check:</b> 10 players × 200K = 2,000K troops. With a 500K rally cap, the planner opens exactly <b>4 rallies</b> per hit. No 5th empty rally is added.
    </div>
    """, unsafe_allow_html=True)

st.subheader("Wave comparison")
comparison = []
for w in range(1, 4):
    p = compute_plan(players, w, troop_cap_k, rally_cap_k, march_to_bear, reach_host, tap_buffer, None)
    comparison.append({
        "Waves": w,
        "Hits": p.total_hits,
        "Spacing": fmt_clock(p.stagger),
        "Rallies / hit": p.rallies_per_hit,
        "Leaders / hit": p.rally_leaders_per_hit,
        "Peak leaders needed": p.peak_rally_leaders_needed,
        "Total rallies": p.total_rallies,
        "Total troops sent": fmt_troops(p.total_troops),
    })
st.dataframe(pd.DataFrame(comparison), hide_index=True, use_container_width=True)

st.subheader("Hit schedule — rallies shown for every wave hit")
st.dataframe(pd.DataFrame(plan.launches), hide_index=True, use_container_width=True, height=460)

st.subheader("Per-wave view")
tabs = st.tabs([f"Wave {i}" for i in range(1, plan.waves + 1)])
for wave_no, tab in enumerate(tabs, 1):
    with tab:
        rows = [r for r in plan.launches if r["Wave"] == wave_no]
        st.caption(f"Wave {wave_no}: {len(rows)} hit(s). Each hit opens {plan.rallies_per_hit} rally/rallies and needs {plan.rally_leaders_per_hit} rally leader(s).")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.markdown(f"""
<div class="card">
  <b>Planner rule:</b> rallies per hit = ceil(total troop pool / rally cap).<br><br>
  Current math: ceil({fmt_troops(plan.pool)} / {fmt_k(plan.rally_cap_k)}) = <b>{plan.rallies_per_hit}</b> rally/rallies per hit.<br>
  Rally leaders needed are calculated from that number; everyone can be a leader if the plan needs them.
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="footer">Bear Trap Rally Planner | Author: Dr. D. #2041 | timing planner only, not damage calculator</div>', unsafe_allow_html=True)
