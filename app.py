"""
King Shot — Bear Trap Rally Planner (Streamlit)

Deploy on Streamlit Community Cloud.
requirements.txt:
streamlit
pandas

Model summary
-------------
Fixed timing rules:
- Bear Trap window is 30:00.
- A rally stays open / fills for 5:00, then departs.
- The last rally can be opened at 5:00 left, so it departs at the buzzer.
- Troops are reused; they are not lost in Bear Trap.

Wave logic:
- A wave is a staggered rally slot, not a separate permanent group.
- With W waves, a new launch opens every 5:00 / W seconds by default.
- Players try to ride every launch. After their troops return, they join the next
  part-filled rally before it departs.

Hard logistics equations:
1) Per-launch troop pool = players * troops_each_player_sends_per_launch.
2) Rallies needed per launch must satisfy BOTH:
   - total capacity constraint: rallies >= ceil(pool / rally_capacity)
   - per-player march constraint: rallies >= ceil(troops_per_player / player_march_size)
   Example: a player has 200K to send per launch and march size is 100K, so the
   launch needs at least 2 rallies even if total rally capacity is large enough.
3) Concurrent rallies open = waves * rallies_per_launch.
   You need at least that many rally hosts/leaders available.
4) Catch-next-wave constraint:
   stagger >= 2 * bear_march_seconds + join_host_seconds + tap_buffer_seconds
   If this is not true, players cannot reliably return and reach the next host
   before the next rally departs.
"""

import math
from dataclasses import dataclass

import pandas as pd
import streamlit as st

WINDOW = 30 * 60                  # 30:00 event window
FILL = 5 * 60                     # rally fill/open time
LAST_LAUNCH_OPEN = WINDOW - FILL  # elapsed 25:00 = 5:00 left
WAVE_COLORS = ["#45c4ff", "#b78bff", "#4fe0a0", "#ffc061"]

st.set_page_config(page_title="Bear Trap Rally Planner", page_icon="🐻", layout="wide")


# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------

def fmt_clock(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    return f"{minutes}:{sec:02d}"


def fmt_left(elapsed: float) -> str:
    return fmt_clock(WINDOW - elapsed)


def fmt_troops(n: float) -> str:
    n = int(round(n))
    if n >= 1_000_000:
        v = n / 1_000_000
        return (f"{v:.1f}" if abs(v - round(v)) > 1e-9 else f"{int(round(v))}") + "M"
    if n >= 1_000:
        v = n / 1_000
        return (f"{v:.1f}" if abs(v - round(v)) > 1e-9 else f"{int(round(v))}") + "K"
    return f"{n:,}"


def pct(n: float) -> str:
    return f"{n:.0%}"


# -----------------------------------------------------------------------------
# Core model
# -----------------------------------------------------------------------------

@dataclass
class Plan:
    players: int
    waves: int
    troops_per_player: int
    march_size: int
    rally_cap: int
    hosts_available: int
    bear_march: int
    join_host: int
    tap_buffer: int
    requested_stagger: float
    natural_stagger: float
    min_stagger: float
    stagger: float
    clamped: bool
    pool_per_launch: int
    rallies_by_capacity: int
    rallies_by_march_size: int
    rallies_per_launch: int
    troops_per_player_per_rally: float
    troops_per_rally: float
    fill_pct: float
    concurrent_rallies: int
    host_shortfall: int
    feasible_hosts: bool
    feasible_timing: bool
    wait_after_join_logistics: float
    launches: list
    total_launches: int
    total_rallies: int
    total_troops_sent: int
    first_hit: float | None
    last_hit: float | None


def compute_plan(
    players: int,
    troops_per_player: int,
    march_size: int,
    rally_cap: int,
    hosts_available: int,
    waves: int,
    bear_march: int,
    join_host: int,
    tap_buffer: int,
    custom_stagger: float | None,
) -> Plan:
    pool = players * troops_per_player

    # The new logistics requirement: rallies must satisfy both total rally cap
    # and each player's individual march-size cap.
    rallies_by_capacity = max(1, math.ceil(pool / rally_cap))
    rallies_by_march_size = max(1, math.ceil(troops_per_player / march_size))
    rallies_per_launch = max(rallies_by_capacity, rallies_by_march_size)

    troops_per_player_per_rally = troops_per_player / rallies_per_launch
    troops_per_rally = pool / rallies_per_launch
    fill_pct = troops_per_rally / rally_cap

    natural = FILL / waves
    requested = custom_stagger if custom_stagger is not None else natural
    minimum = 2 * bear_march + join_host + tap_buffer
    stagger = max(requested, minimum)
    clamped = stagger > requested + 1e-9

    concurrent = waves * rallies_per_launch
    host_shortfall = max(0, concurrent - hosts_available)
    feasible_hosts = host_shortfall == 0
    feasible_timing = requested >= minimum
    wait_after_join = stagger - minimum

    launches = []
    i = 0
    open_time = 0.0
    while open_time <= LAST_LAUNCH_OPEN + 1e-9:
        lane = i % waves
        depart = open_time + FILL
        hit = depart + bear_march
        ret = hit + bear_march
        launches.append(
            {
                "idx": i + 1,
                "lane": lane,
                "open": open_time,
                "depart": depart,
                "hit": hit,
                "return": ret,
                "final": abs(open_time - LAST_LAUNCH_OPEN) < 1e-6,
                "rallies": rallies_per_launch,
                "troops": pool,
            }
        )
        i += 1
        open_time = i * stagger

    total_launches = len(launches)
    total_rallies = total_launches * rallies_per_launch
    total_troops_sent = total_launches * pool
    first_hit = launches[0]["hit"] if launches else None
    last_hit = launches[-1]["hit"] if launches else None

    return Plan(
        players=players,
        waves=waves,
        troops_per_player=troops_per_player,
        march_size=march_size,
        rally_cap=rally_cap,
        hosts_available=hosts_available,
        bear_march=bear_march,
        join_host=join_host,
        tap_buffer=tap_buffer,
        requested_stagger=requested,
        natural_stagger=natural,
        min_stagger=minimum,
        stagger=stagger,
        clamped=clamped,
        pool_per_launch=pool,
        rallies_by_capacity=rallies_by_capacity,
        rallies_by_march_size=rallies_by_march_size,
        rallies_per_launch=rallies_per_launch,
        troops_per_player_per_rally=troops_per_player_per_rally,
        troops_per_rally=troops_per_rally,
        fill_pct=fill_pct,
        concurrent_rallies=concurrent,
        host_shortfall=host_shortfall,
        feasible_hosts=feasible_hosts,
        feasible_timing=feasible_timing,
        wait_after_join_logistics=wait_after_join,
        launches=launches,
        total_launches=total_launches,
        total_rallies=total_rallies,
        total_troops_sent=total_troops_sent,
        first_hit=first_hit,
        last_hit=last_hit,
    )


def plan_for_waves(waves: int, base_kwargs: dict) -> Plan:
    kwargs = dict(base_kwargs)
    kwargs["waves"] = waves
    kwargs["custom_stagger"] = None
    return compute_plan(**kwargs)


# -----------------------------------------------------------------------------
# UI styling
# -----------------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #0a0e15; color: #e9eef6; }
        .block-container { max-width: 1200px; padding-top: 1.2rem; }
        div[data-testid="stMetric"] {
            background: #121a28;
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 14px;
            padding: 12px 14px;
        }
        .panel {
            background: #121a28;
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 16px;
            padding: 16px 18px;
            margin: 10px 0 16px 0;
        }
        .good { color: #4fe0a0; font-weight: 700; }
        .bad { color: #ff5d62; font-weight: 700; }
        .info { color: #ffc061; font-weight: 700; }
        .small { color: #9aa8ba; font-size: .92rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()

# -----------------------------------------------------------------------------
# Sidebar inputs
# -----------------------------------------------------------------------------

st.title("King Shot — Bear Trap Rally Planner")
st.caption(
    "Plans waves, rally count, host count, and catch timing. The planner checks that the logistics equations are true before calling a plan feasible."
)

with st.sidebar:
    st.header("Battle setup")

    players = st.slider("Players joining", 3, 100, 10, 1)
    troops_k = st.slider("Troops each player wants to send per launch (K)", 20, 2_000, 200, 10)
    march_size_k = st.slider("Player march size / max troops per rally (K)", 20, 1_000, 100, 10)
    rally_cap_k = st.slider("Rally capacity per host (K)", 100, 6_000, 1_000, 50)
    hosts_available = st.slider("Available rally hosts/leaders", 1, 50, 10, 1)

    st.header("Timing")
    waves = st.slider("Waves", 1, 4, 2, 1)
    bear_march = st.slider("March to bear, one way (seconds)", 1, 120, 10, 1)
    join_host = st.slider("Average time to reach rally host (seconds)", 0, 60, 10, 1)
    tap_buffer = st.slider("Join/tap buffer (seconds)", 0, 60, 5, 1)

    use_custom = st.checkbox("Use custom launch spacing", value=False)
    custom_stagger = None
    if use_custom:
        custom_stagger = st.slider("Custom launch spacing (seconds)", 30, 300, int(FILL / waves), 5)

base_kwargs = {
    "players": players,
    "troops_per_player": troops_k * 1000,
    "march_size": march_size_k * 1000,
    "rally_cap": rally_cap_k * 1000,
    "hosts_available": hosts_available,
    "waves": waves,
    "bear_march": bear_march,
    "join_host": join_host,
    "tap_buffer": tap_buffer,
    "custom_stagger": custom_stagger,
}
plan = compute_plan(**base_kwargs)

# -----------------------------------------------------------------------------
# Main metrics
# -----------------------------------------------------------------------------

st.subheader("Selected plan")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Hits", plan.total_launches)
c2.metric("Rallies per launch", plan.rallies_per_launch)
c3.metric("Concurrent rallies open", plan.concurrent_rallies)
c4.metric("Total rallies", plan.total_rallies)

c5, c6, c7, c8 = st.columns(4)
c5.metric("Launch spacing", fmt_clock(plan.stagger))
c6.metric("Troops per launch", fmt_troops(plan.pool_per_launch))
c7.metric("Troops per player per rally", fmt_troops(plan.troops_per_player_per_rally))
c8.metric("Rally fill", pct(plan.fill_pct))

# -----------------------------------------------------------------------------
# Logistics checks
# -----------------------------------------------------------------------------

st.subheader("Logistics checks")

checks = []
checks.append(
    {
        "Check": "Rally capacity",
        "Equation": f"ceil({fmt_troops(plan.pool_per_launch)} / {fmt_troops(plan.rally_cap)})",
        "Required rallies": plan.rallies_by_capacity,
        "Status": "OK",
    }
)
checks.append(
    {
        "Check": "Player march size",
        "Equation": f"ceil({fmt_troops(plan.troops_per_player)} / {fmt_troops(plan.march_size)})",
        "Required rallies": plan.rallies_by_march_size,
        "Status": "OK",
    }
)
checks.append(
    {
        "Check": "Hosts/leaders",
        "Equation": f"{plan.waves} waves × {plan.rallies_per_launch} rallies per launch",
        "Required rallies": plan.concurrent_rallies,
        "Status": "OK" if plan.feasible_hosts else f"Short {plan.host_shortfall}",
    }
)
checks.append(
    {
        "Check": "Catch next wave",
        "Equation": f"stagger {fmt_clock(plan.stagger)} ≥ 2×{bear_march}s + {join_host}s + {tap_buffer}s = {fmt_clock(plan.min_stagger)}",
        "Required rallies": "—",
        "Status": "OK" if not plan.clamped else "Spacing auto-increased",
    }
)

st.dataframe(pd.DataFrame(checks), hide_index=True, use_container_width=True)

if not plan.feasible_hosts:
    st.error(
        f"Not enough hosts. This setup needs {plan.concurrent_rallies} rallies open at the same time, "
        f"but you only have {hosts_available}. Add {plan.host_shortfall} host(s), reduce waves, or reduce rallies per launch."
    )
else:
    st.success(f"Host check passes: {hosts_available} host(s) available for {plan.concurrent_rallies} concurrent rallies.")

if plan.clamped:
    st.warning(
        f"Requested spacing was {fmt_clock(plan.requested_stagger)}, but the catch equation needs at least "
        f"{fmt_clock(plan.min_stagger)}. The planner increased spacing to {fmt_clock(plan.stagger)}."
    )
else:
    st.success(
        f"Timing check passes. After march back and reaching the next host, players have about "
        f"{fmt_clock(plan.wait_after_join_logistics)} of extra buffer."
    )

if plan.troops_per_player_per_rally > plan.march_size + 1e-9:
    st.error("Player march-size check failed. Increase rallies per launch or reduce troops per player.")
elif plan.troops_per_rally > plan.rally_cap + 1e-9:
    st.error("Rally-cap check failed. Increase rallies per launch or reduce troop pool.")
else:
    st.info(
        f"Each player sends about {fmt_troops(plan.troops_per_player_per_rally)} into each rally. "
        f"Each rally carries about {fmt_troops(plan.troops_per_rally)} of {fmt_troops(plan.rally_cap)} capacity."
    )

# -----------------------------------------------------------------------------
# Comparison table
# -----------------------------------------------------------------------------

st.subheader("1 vs 2 vs 3 vs 4 waves")

comparison = []
for w in range(1, 5):
    p = plan_for_waves(w, base_kwargs)
    comparison.append(
        {
            "Waves": w,
            "Hits": p.total_launches,
            "Launch spacing": fmt_clock(p.stagger),
            "Rallies / launch": p.rallies_per_launch,
            "Concurrent rallies": p.concurrent_rallies,
            "Hosts needed": p.concurrent_rallies,
            "Host status": "OK" if p.feasible_hosts else f"Short {p.host_shortfall}",
            "Timing status": "OK" if not p.clamped else "Auto-spaced",
            "Total troops sent": fmt_troops(p.total_troops_sent),
        }
    )

st.dataframe(pd.DataFrame(comparison), hide_index=True, use_container_width=True)

# -----------------------------------------------------------------------------
# Launch schedule
# -----------------------------------------------------------------------------

st.subheader("Launch schedule")

schedule_rows = []
for launch in plan.launches:
    schedule_rows.append(
        {
            "#": launch["idx"],
            "Wave": launch["lane"] + 1,
            "Open at trap time left": fmt_left(launch["open"]),
            "Depart at": fmt_left(launch["depart"]),
            "Hit at": fmt_left(launch["hit"]),
            "Return at": fmt_left(launch["return"]),
            "Rallies opened": launch["rallies"],
            "Troops sent": fmt_troops(launch["troops"]),
            "Final allowed open": "Yes" if launch["final"] else "",
        }
    )

st.dataframe(pd.DataFrame(schedule_rows), hide_index=True, use_container_width=True, height=460)

# -----------------------------------------------------------------------------
# Explanation
# -----------------------------------------------------------------------------

st.markdown(
    f"""
    <div class="panel">
    <b>How to read this:</b><br>
    This setup has <b>{players}</b> players. Each player is trying to send <b>{fmt_troops(plan.troops_per_player)}</b>
    per launch, but each march can carry only <b>{fmt_troops(plan.march_size)}</b>. Therefore the launch needs at least
    <b>{plan.rallies_by_march_size}</b> rally/rallies for the player march-size constraint. The total pool is
    <b>{fmt_troops(plan.pool_per_launch)}</b>, so rally capacity requires <b>{plan.rallies_by_capacity}</b> rally/rallies.
    The planner uses the higher number: <b>{plan.rallies_per_launch}</b> rally/rallies per launch.<br><br>
    With <b>{plan.waves}</b> wave(s), that means <b>{plan.concurrent_rallies}</b> rallies need to be open at once.
    The catch timing equation is <b>launch spacing ≥ 2 × bear march + time to reach host + buffer</b>.
    Here, that is <b>{fmt_clock(plan.stagger)} ≥ {fmt_clock(plan.min_stagger)}</b>.
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "This planner estimates timing, rallies, and troop flow. It does not estimate damage, which depends on heroes, buffs, lethality, and other game factors."
)
