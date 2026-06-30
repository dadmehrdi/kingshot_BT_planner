
"""
King Shot — Bear Trap Rally Planner
Author: Dr. D. #2041

requirements.txt:
streamlit
pandas

Main fix:
For every hit, rallies opened = exact rallies needed, not all available hosts.
Example: 10 players x 200K = 2,000K troop pool. Rally cap 500K => 4 rallies.
If 2 waves split 10 hosts into 5 hosts per wave, the planner opens 4 rallies and leaves 1 host unused.
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


def fmt_troops(n: float) -> str:
    n = int(round(n))
    if n >= 1_000_000:
        v = n / 1_000_000
        return (f"{v:.1f}" if v % 1 else f"{int(v)}") + "M"
    if n >= 1_000:
        v = n / 1_000
        return (f"{v:.1f}" if v % 1 else f"{int(v)}") + "K"
    return f"{n:,}"


def pct(x: float) -> str:
    return f"{x:.0%}"


@dataclass
class Plan:
    players: int
    waves: int
    hosts_total: int
    hosts_per_wave: int
    troop_each: int
    march_size: int
    rally_cap: int
    pool: int
    rallies_by_cap: int
    rallies_by_march_size: int
    rallies_per_hit: int
    hosts_used_per_hit: int
    unused_hosts_in_active_wave: int
    active_wave_shortfall: int
    natural_stagger: float
    requested_stagger: float
    min_stagger: float
    stagger: float
    spacing_increased: bool
    catch_buffer: float
    overlapping_waves: int
    peak_open_rallies: int
    peak_host_shortfall: int
    avg_per_rally: float
    avg_player_per_rally: float
    fill_pct: float
    launches: list
    total_hits: int
    total_rallies: int
    total_troops: int


def compute_plan(
    players: int,
    waves: int,
    hosts_total: int,
    troop_each: int,
    march_size: int,
    rally_cap: int,
    march_to_bear: int,
    reach_host: int,
    tap_buffer: int,
    custom_stagger: Optional[float],
) -> Plan:
    waves = max(1, min(4, waves))
    hosts_per_wave = hosts_total // waves
    pool = players * troop_each

    # Required equation 1: total troop pool must fit into rally capacity.
    rallies_by_cap = max(1, math.ceil(pool / rally_cap))

    # Required equation 2: each player cannot put more than march size into one rally.
    rallies_by_march_size = max(1, math.ceil(troop_each / march_size))

    # Final requirement: satisfy both equations. This avoids empty rallies.
    rallies_per_hit = max(rallies_by_cap, rallies_by_march_size)

    hosts_used_per_hit = min(rallies_per_hit, hosts_per_wave)
    unused_hosts = max(0, hosts_per_wave - rallies_per_hit)
    active_wave_shortfall = max(0, rallies_per_hit - hosts_per_wave)

    natural_stagger = FILL / waves
    requested_stagger = custom_stagger if custom_stagger is not None else natural_stagger
    min_stagger = 2 * march_to_bear + reach_host + tap_buffer
    stagger = max(requested_stagger, min_stagger)
    spacing_increased = stagger > requested_stagger + 1e-9
    catch_buffer = stagger - min_stagger

    # Several wave slots can be filling at the same time because each rally remains open for 5:00.
    overlapping_waves = min(waves, max(1, math.ceil(FILL / stagger)))
    peak_open_rallies = overlapping_waves * rallies_per_hit
    peak_host_shortfall = max(0, peak_open_rallies - hosts_total)

    avg_per_rally = pool / rallies_per_hit
    avg_player_per_rally = troop_each / rallies_per_hit
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
            "Hosts used": hosts_used_per_hit,
            "Unused hosts in wave": unused_hosts,
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
        hosts_total=hosts_total,
        hosts_per_wave=hosts_per_wave,
        troop_each=troop_each,
        march_size=march_size,
        rally_cap=rally_cap,
        pool=pool,
        rallies_by_cap=rallies_by_cap,
        rallies_by_march_size=rallies_by_march_size,
        rallies_per_hit=rallies_per_hit,
        hosts_used_per_hit=hosts_used_per_hit,
        unused_hosts_in_active_wave=unused_hosts,
        active_wave_shortfall=active_wave_shortfall,
        natural_stagger=natural_stagger,
        requested_stagger=requested_stagger,
        min_stagger=min_stagger,
        stagger=stagger,
        spacing_increased=spacing_increased,
        catch_buffer=catch_buffer,
        overlapping_waves=overlapping_waves,
        peak_open_rallies=peak_open_rallies,
        peak_host_shortfall=peak_host_shortfall,
        avg_per_rally=avg_per_rally,
        avg_player_per_rally=avg_player_per_rally,
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
    players = st.slider("Players joining", 3, 100, 10, 1)
    waves = st.slider("Waves", 1, 4, 2, 1)
    hosts_total = st.slider("Total rally hosts/leaders", 1, 80, 10, 1)

    st.markdown("### Troops and caps")
    troop_each_k = st.slider("Troops each player sends per hit (K)", 20, 2_000, 200, 10)
    march_size_k = st.slider("Player march size / max per rally (K)", 20, 1_000, 200, 10)
    rally_cap_k = st.slider("Rally cap per host (K)", 100, 6_000, 500, 50)

    st.markdown("### Timing")
    march_to_bear = st.slider("March to bear, one way (seconds)", 1, 120, 10, 1)
    reach_host = st.slider("Average time to reach rally host (seconds)", 0, 90, 10, 1)
    tap_buffer = st.slider("Join/tap safety buffer (seconds)", 0, 90, 5, 1)

    custom_on = st.checkbox("Custom launch spacing", value=False)
    custom_stagger = None
    if custom_on:
        custom_stagger = st.slider("Launch spacing (seconds)", 30, 300, int(FILL / waves), 5)

plan = compute_plan(
    players=players,
    waves=waves,
    hosts_total=hosts_total,
    troop_each=troop_each_k * 1000,
    march_size=march_size_k * 1000,
    rally_cap=rally_cap_k * 1000,
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
  <div class="copy">Plan clean waves, calculate the exact rallies needed for each hit, avoid empty rallies, and check whether players can catch the next wave.</div>
</div>
""", unsafe_allow_html=True)

st.subheader("Plan snapshot")
cols = st.columns(4)
cols[0].metric("Hits in window", plan.total_hits)
cols[1].metric("Rallies per hit", plan.rallies_per_hit)
cols[2].metric("Hosts used / active wave", plan.hosts_used_per_hit)
cols[3].metric("Total rallies opened", plan.total_rallies)

cols = st.columns(4)
cols[0].metric("Troop pool / hit", fmt_troops(plan.pool))
cols[1].metric("Avg troops / rally", fmt_troops(plan.avg_per_rally))
cols[2].metric("Launch spacing", fmt_clock(plan.stagger))
cols[3].metric("Rally fill", pct(plan.fill_pct))

st.markdown(f"""
<div class="card">
  <span class="pill">{plan.players} players</span>
  <span class="pill">{plan.waves} waves</span>
  <span class="pill">{plan.hosts_total} total hosts</span>
  <span class="pill">{plan.hosts_per_wave} hosts per wave</span>
  <span class="pill">{fmt_troops(plan.rally_cap)} rally cap</span>
  <span class="pill">{fmt_troops(plan.troop_each)} troops/player/hit</span>
</div>
""", unsafe_allow_html=True)

st.subheader("Logistics equations")
checks = pd.DataFrame([
    {"Check":"Troop pool per hit", "Equation":f"{players} players × {fmt_troops(plan.troop_each)}", "Result":fmt_troops(plan.pool), "Status":"OK"},
    {"Check":"Rallies from rally cap", "Equation":f"ceil({fmt_troops(plan.pool)} / {fmt_troops(plan.rally_cap)})", "Result":plan.rallies_by_cap, "Status":"OK"},
    {"Check":"Rallies from player march size", "Equation":f"ceil({fmt_troops(plan.troop_each)} / {fmt_troops(plan.march_size)})", "Result":plan.rallies_by_march_size, "Status":"OK"},
    {"Check":"Rallies opened per hit", "Equation":"max(cap requirement, march-size requirement)", "Result":plan.rallies_per_hit, "Status":"No empty rallies"},
    {"Check":"Hosts in active wave", "Equation":f"{plan.rallies_per_hit} rallies needed ≤ {plan.hosts_per_wave} hosts in that wave", "Result":plan.hosts_used_per_hit, "Status":"OK" if plan.active_wave_shortfall == 0 else f"Short {plan.active_wave_shortfall}"},
    {"Check":"Catch next wave", "Equation":f"{fmt_clock(plan.stagger)} ≥ 2×{march_to_bear}s + {reach_host}s + {tap_buffer}s", "Result":fmt_clock(plan.min_stagger), "Status":"OK" if not plan.spacing_increased else "Spacing increased"},
])
st.dataframe(checks, hide_index=True, use_container_width=True)

if plan.active_wave_shortfall:
    st.error(f"Host issue: each active wave needs {plan.rallies_per_hit} rallies, but only {plan.hosts_per_wave} hosts are assigned per wave. Short {plan.active_wave_shortfall} per wave.")
elif plan.unused_hosts_in_active_wave:
    st.success(f"No empty rallies: the active wave has {plan.hosts_per_wave} hosts available, but only {plan.rallies_per_hit} rallies are needed. {plan.unused_hosts_in_active_wave} host(s) stay unused for that hit.")
else:
    st.success("Host check passes: active-wave hosts match the rallies needed.")

if plan.spacing_increased:
    st.warning(f"Spacing was increased from {fmt_clock(plan.requested_stagger)} to {fmt_clock(plan.stagger)} so players can return, reach the next host, and join.")
else:
    st.success(f"Catch timing passes. Extra catch buffer is about {fmt_clock(plan.catch_buffer)}.")

if plan.peak_host_shortfall:
    st.warning(f"Overlap note: because rallies stay open for 5:00, up to {plan.overlapping_waves} wave slot(s) may overlap. Peak open rallies can reach {plan.peak_open_rallies}; total hosts are short by {plan.peak_host_shortfall} if all overlapping rallies need separate hosts.")
else:
    st.info(f"Overlap check passes: peak open rallies are about {plan.peak_open_rallies}, covered by {plan.hosts_total} total hosts.")

if players == 10 and waves == 2 and hosts_total == 10 and troop_each_k == 200 and rally_cap_k == 500:
    st.markdown("""
    <div class="card">
      <b>Example check:</b> 10 players × 200K = 2,000K troops. With a 500K rally cap, the planner opens exactly <b>4 rallies</b> per hit. Since there are 5 hosts in the active wave, 1 host stays unused. No empty rally is opened.
    </div>
    """, unsafe_allow_html=True)

st.subheader("Wave comparison")
comparison = []
for w in range(1, 5):
    p = compute_plan(players, w, hosts_total, troop_each_k * 1000, march_size_k * 1000, rally_cap_k * 1000, march_to_bear, reach_host, tap_buffer, None)
    comparison.append({
        "Waves": w,
        "Hits": p.total_hits,
        "Spacing": fmt_clock(p.stagger),
        "Hosts / wave": p.hosts_per_wave,
        "Rallies / hit": p.rallies_per_hit,
        "Unused hosts / active wave": p.unused_hosts_in_active_wave,
        "Peak open rallies": p.peak_open_rallies,
        "Host status": "OK" if p.active_wave_shortfall == 0 else f"Short {p.active_wave_shortfall}/wave",
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
        st.caption(f"Wave {wave_no}: {len(rows)} hit(s). Each hit opens {plan.rallies_per_hit} rally/rallies, not every available host slot.")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.markdown(f"""
<div class="card">
  <b>Planner rule:</b> rallies per hit = max(ceil(total troop pool / rally cap), ceil(troops per player / player march size)).<br><br>
  Current math: max(ceil({fmt_troops(plan.pool)} / {fmt_troops(plan.rally_cap)}), ceil({fmt_troops(plan.troop_each)} / {fmt_troops(plan.march_size)})) = <b>{plan.rallies_per_hit}</b> rally/rallies per hit.
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="footer">Bear Trap Rally Planner | Author: Dr. D. #2041 | timing planner only, not damage calculator</div>', unsafe_allow_html=True)
