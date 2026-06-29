"""
King Shot — Bear Trap Rally Planner
Single-file Streamlit app. Deploy on Streamlit Cloud with main file: app.py
"""

import streamlit as st
import pandas as pd

# ── Game constants ──────────────────────────────────────────────────────────
TRAP_WINDOW_SEC = 30 * 60   # 30 minutes countdown
RALLY_FILL_SEC = 5 * 60     # 5 minutes to fill a rally before it marches

# ── Timing logic ────────────────────────────────────────────────────────────
def format_time(seconds: int) -> str:
    s = max(0, round(seconds))
    m, sec = divmod(s, 60)
    return f"{m:02d}:{sec:02d}"

def format_countdown(elapsed_sec: int) -> str:
    """Show time remaining on the 30-minute trap timer."""
    return format_time(TRAP_WINDOW_SEC - elapsed_sec)

def distribute_rallies_across_waves(total_rallies: int, wave_count: int) -> list:
    if total_rallies <= 0 or wave_count <= 0:
        return []
    waves = [[] for _ in range(wave_count)]
    for i in range(total_rallies):
        waves[i % wave_count].append(i + 1)
    return [w for w in waves if w]

def recommend_wave_delay(wave_count: int, travel_sec: int, gap_sec: int) -> int:
    cycle_hint = RALLY_FILL_SEC + travel_sec * 2 + gap_sec
    if wave_count == 1:
        return 0
    if wave_count == 2:
        return min(120, max(60, round(cycle_hint * 0.35)))
    return min(120, max(45, round(cycle_hint / wave_count)))

def calculate_plan(total_players, rally_size, travel_sec, gap_sec, wave_count, wave_delay_sec):
    full_rallies = total_players // rally_size
    partial_players = total_players % rally_size
    waves = distribute_rallies_across_waves(full_rallies, wave_count)
    rallies = []
    rally_index = 0

    for wave_idx, wave_rallies in enumerate(waves):
        wave_start = 0 if wave_idx == 0 else wave_delay_sec * wave_idx
        for idx_in_wave, _ in enumerate(wave_rallies):
            start = wave_start + idx_in_wave * gap_sec
            depart = start + RALLY_FILL_SEC
            hit = depart + travel_sec
            ret = hit + travel_sec
            rallies.append({
                "id": rally_index + 1,
                "wave": wave_idx + 1,
                "start_sec": start,
                "depart_sec": depart,
                "hit_sec": hit,
                "return_sec": ret,
                "players": rally_size,
                "on_time": hit <= TRAP_WINDOW_SEC,
                "partial": False,
            })
            rally_index += 1

    if partial_players > 0:
        if rallies:
            start = rallies[-1]["start_sec"] + gap_sec
            wave = rallies[-1]["wave"]
        else:
            start = 0
            wave = 1
        depart = start + RALLY_FILL_SEC
        hit = depart + travel_sec
        ret = hit + travel_sec
        rallies.append({
            "id": len(rallies) + 1,
            "wave": wave,
            "start_sec": start,
            "depart_sec": depart,
            "hit_sec": hit,
            "return_sec": ret,
            "players": partial_players,
            "on_time": hit <= TRAP_WINDOW_SEC,
            "partial": True,
        })

    valid = [r for r in rallies if r["on_time"]]
    first_hit = min((r["hit_sec"] for r in valid), default=None)
    last_hit = max((r["hit_sec"] for r in valid), default=None)

    return {
        "rallies": rallies,
        "full_rallies": full_rallies,
        "partial_players": partial_players,
        "valid_count": len(valid),
        "first_hit": format_countdown(first_hit) if first_hit is not None else "—",
        "last_hit": format_countdown(last_hit) if last_hit is not None else "—",
        "cycle_sec": RALLY_FILL_SEC + travel_sec * 2 + gap_sec,
        "recommended_delay": recommend_wave_delay(wave_count, travel_sec, gap_sec),
    }

def build_event_log(rallies):
    rows = [{"Countdown": "30:00", "Elapsed": "+00:00", "Event": "Bear trapped — timer starts"}]

    for r in rallies:
        n = r["id"]
        w = r["wave"]
        late = "" if r["on_time"] else " ⚠ TOO LATE"
        rows.append({"Countdown": format_countdown(r["start_sec"]), "Elapsed": f"+{format_time(r['start_sec'])}",
                       "Event": f"Rally #{n} (Wave {w}) — START ({r['players']} players)"})
        rows.append({"Countdown": format_countdown(r["depart_sec"]), "Elapsed": f"+{format_time(r['depart_sec'])}",
                       "Event": f"Rally #{n} (Wave {w}) — DEPARTS (5 min fill done)"})
        rows.append({"Countdown": format_countdown(r["hit_sec"]), "Elapsed": f"+{format_time(r['hit_sec'])}",
                       "Event": f"Rally #{n} (Wave {w}) — HITS TRAP{late}"})
        rows.append({"Countdown": format_countdown(r["return_sec"]), "Elapsed": f"+{format_time(r['return_sec'])}",
                       "Event": f"Rally #{n} (Wave {w}) — returns home"})

    rows.append({"Countdown": "00:00", "Elapsed": "+30:00", "Event": "Trap window closes"})
    return rows

# ── Streamlit UI ────────────────────────────────────────────────────────────
st.set_page_config(page_title="King Shot Rally Planner", page_icon="🐻", layout="wide")

st.title("🐻 King Shot — Bear Trap Rally Planner")
st.write("Enter your alliance details. All times count **down from 30:00** until the trap closes at **00:00**.")

with st.sidebar:
    st.header("Inputs")

    total_players = st.number_input(
        "Number of players",
        min_value=1, max_value=9999, value=100, step=1,
        help="How many players will join the bear attack",
    )

    rally_size = st.number_input(
        "Average rally size",
        min_value=1, max_value=999, value=20, step=1,
        help="How many players fit in one rally",
    )

    travel_sec = st.number_input(
        "Distance from trap (seconds, one way)",
        min_value=10, max_value=600, value=10, step=1,
        help="Seconds to march to the trap (minimum 10). Same time to return.",
    )

    gap_sec = st.number_input(
        "Time to start a new rally (seconds)",
        min_value=0, max_value=120, value=5, step=1,
        help="Seconds between one player starting a rally and the next",
    )

    wave_count = st.radio(
        "Wave strategy",
        options=[1, 2, 3],
        format_func=lambda x: f"{x} wave" if x == 1 else f"{x} waves",
        index=1,
        horizontal=True,
    )

    recommended = recommend_wave_delay(wave_count, travel_sec, gap_sec)
    wave_delay_sec = st.number_input(
        "Seconds between wave starts",
        min_value=0, max_value=600, value=recommended, step=5,
        help=f"Recommended for your settings: {recommended}s",
    )

    full = total_players // rally_size
    partial = total_players % rally_size
    extra = f" + 1 partial rally ({partial} players)" if partial else ""
    st.info(f"You can run **{full} full rallies**{extra}")

plan = calculate_plan(total_players, rally_size, travel_sec, gap_sec, wave_count, wave_delay_sec)

# Summary
c1, c2, c3, c4 = st.columns(4)
c1.metric("First hit on trap", plan["first_hit"])
c2.metric("Last hit on trap", plan["last_hit"])
c3.metric("Rallies that hit in time", f"{plan['valid_count']} / {len(plan['rallies'])}")
c4.metric("Full rally cycle", format_time(plan["cycle_sec"]))

# Rally-by-rally schedule
st.subheader("Rally schedule — Rally 1, 2, 3… until 00:00")

if plan["rallies"]:
    schedule = []
    for r in plan["rallies"]:
        schedule.append({
            "Rally": f"#{r['id']}",
            "Wave": r["wave"],
            "Players": r["players"],
            "Start rally at": format_countdown(r["start_sec"]),
            "Depart at": format_countdown(r["depart_sec"]),
            "Hit trap at": format_countdown(r["hit_sec"]),
            "Return at": format_countdown(r["return_sec"]),
            "OK?": "✅" if r["on_time"] else "❌ Too late",
        })
    st.dataframe(pd.DataFrame(schedule), use_container_width=True, hide_index=True)
else:
    st.error("Not enough players for even one rally.")

# Full event log
st.subheader("Full timeline (every step)")
st.dataframe(
    pd.DataFrame(build_event_log(plan["rallies"])),
    use_container_width=True,
    hide_index=True,
    height=450,
)

st.markdown("---")
st.caption("Deploy this file on Streamlit Cloud → share the link with your alliance.")
