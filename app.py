"""
King Shot — Bear Trap Rally Planner
Deploy on Streamlit Cloud — main file: app.py

Logistics model:
- Each wave gets players_per_wave = floor(total_players / waves)
- Each player in a wave = 1 rally HOST (creates empty rally at 0 troops)
- Wave members send troops into rallies in that wave only
- Default: 1 player -> 1 rally, sends min(avg_troops, rally_cap)
- Capacity per wave = hosts x rally_cap | Available = hosts x avg_troops
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="King Shot Rally Planner", page_icon="🐻", layout="wide")

TRAP_WINDOW_SEC = 30 * 60
RALLY_FILL_SEC = 5 * 60

WAVE_STYLE = {
    1: {"name": "Wave 1", "emoji": "🔵", "hex": "#4a9eff"},
    2: {"name": "Wave 2", "emoji": "🟣", "hex": "#a78bfa"},
    3: {"name": "Wave 3", "emoji": "🟢", "hex": "#34d399"},
}


def get_col_config():
    return {
        "#": st.column_config.TextColumn("#", width="small"),
        "Host": st.column_config.TextColumn("Host", width="small"),
        "Troops": st.column_config.TextColumn("Troops", width="small"),
        "Fill": st.column_config.TextColumn("Fill", width="small"),
        "L·Start": st.column_config.TextColumn("L Start", width="small"),
        "P·Start": st.column_config.TextColumn("P Start", width="small"),
        "L·Depart": st.column_config.TextColumn("L Depart", width="small"),
        "P·Depart": st.column_config.TextColumn("P Depart", width="small"),
        "L·Hit": st.column_config.TextColumn("L Hit", width="small"),
        "P·Hit": st.column_config.TextColumn("P Hit", width="small"),
        "L·Return": st.column_config.TextColumn("L Return", width="small"),
        "P·Return": st.column_config.TextColumn("P Return", width="small"),
        "OK": st.column_config.TextColumn("OK", width="small"),
    }


def format_time(seconds: int) -> str:
    s = max(0, round(seconds))
    m, sec = divmod(s, 60)
    return f"{m:02d}:{sec:02d}"


def format_countdown(elapsed_sec: int) -> str:
    return format_time(TRAP_WINDOW_SEC - elapsed_sec)


def format_troops(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:g}M"
    if n >= 1_000:
        return f"{n / 1_000:g}K"
    return f"{n:,}"


def time_pair(elapsed_sec: int) -> tuple:
    return format_countdown(elapsed_sec), format_time(elapsed_sec)


def recommend_wave_delay(wave_count: int, travel_sec: int, gap_sec: int) -> int:
    cycle = RALLY_FILL_SEC + travel_sec * 2 + gap_sec
    if wave_count == 1:
        return 0
    if wave_count == 2:
        return min(120, max(60, round(cycle * 0.35)))
    return min(120, max(45, round(cycle / wave_count)))


def fill_label(troops, rally_cap):
    if troops <= 0:
        return "EMPTY"
    if troops >= rally_cap:
        return "FULL"
    return f"PARTIAL {round(100 * troops / rally_cap)}%"


def allocate_wave_troops(players_in_wave, avg_troops, rally_cap, fill_mode):
    """
    Host creates empty rally; players send troops into wave rallies.

    fill_mode '1to1': each host rally gets min(avg, cap) from that player.
    fill_mode 'stack': fill rallies to cap in order until wave pool runs out.
    """
    wave_pool = players_in_wave * avg_troops
    wave_capacity = players_in_wave * rally_cap

    if fill_mode == "1to1":
        per_rally = min(avg_troops, rally_cap)
        allocations = [per_rally] * players_in_wave
        sent = sum(allocations)
        return allocations, wave_pool, wave_capacity, sent

    # stack: prioritize filling rallies to cap (best for max damage)
    allocations = []
    remaining = wave_pool
    for _ in range(players_in_wave):
        fill = min(rally_cap, remaining)
        allocations.append(fill)
        remaining -= fill
    return allocations, wave_pool, wave_capacity, sum(allocations)


def first_hit_breakdown(travel_sec):
    start = 0
    depart = start + RALLY_FILL_SEC
    hit = depart + travel_sec
    return {
        "depart_left": format_countdown(depart),
        "depart_passed": format_time(depart),
        "hit_left": format_countdown(hit),
        "hit_passed": format_time(hit),
    }


def wave_logistics_text(players, avg_k, cap_k, allocations, pool, capacity, sent):
    lines = [
        f"Hosts (empty rallies)     = {players}",
        f"Wave troop pool           = {players} x {avg_k}K = {format_troops(pool)}",
        f"Wave rally capacity     = {players} x {cap_k}K = {format_troops(capacity)}",
        f"Troops actually sent      = {format_troops(sent)}",
    ]
    if sent < capacity:
        lines.append(f"Unused rally space      = {format_troops(capacity - sent)}")
    if pool > sent:
        lines.append(f"Troops not sent           = {format_troops(pool - sent)}")
    return lines


def calculate_plan(num_players, avg_troops, rally_cap, travel_sec, gap_sec,
                   wave_count, wave_delay_sec, fill_mode):
    players_per_wave = num_players // wave_count
    leftover_players = num_players % wave_count

    all_rallies = []
    waves_data = []

    for wave_idx in range(wave_count):
        wave_num = wave_idx + 1
        wave_offset = 0 if wave_idx == 0 else wave_delay_sec * wave_idx

        allocations, pool, capacity, sent = allocate_wave_troops(
            players_per_wave, avg_troops, rally_cap, fill_mode
        )

        wave_rallies = []
        for i in range(players_per_wave):
            start = wave_offset + i * gap_sec
            depart = start + RALLY_FILL_SEC
            hit = depart + travel_sec
            ret = hit + travel_sec
            troops = allocations[i]

            rally = {
                "wave_rally_num": i + 1,
                "host": f"P{i + 1}",
                "start_sec": start,
                "depart_sec": depart,
                "hit_sec": hit,
                "return_sec": ret,
                "troops": troops,
                "fill": fill_label(troops, rally_cap),
                "on_time": hit <= TRAP_WINDOW_SEC and troops > 0,
            }
            wave_rallies.append(rally)
            all_rallies.append({**rally, "wave": wave_num})

        valid = [r for r in wave_rallies if r["on_time"]]
        logistics = wave_logistics_text(
            players_per_wave, avg_troops // 1000, rally_cap // 1000,
            allocations, pool, capacity, sent,
        )

        waves_data.append({
            "wave": wave_num,
            "players": players_per_wave,
            "rallies": wave_rallies,
            "troops_sent": sent,
            "pool": pool,
            "capacity": capacity,
            "logistics": logistics,
            "start_left": format_countdown(wave_offset),
            "first_hit": format_countdown(valid[0]["hit_sec"]) if valid else "—",
            "last_hit": format_countdown(valid[-1]["hit_sec"]) if valid else "—",
            "last_return": format_countdown(wave_rallies[-1]["return_sec"]) if wave_rallies else "—",
        })

    valid_all = [r for r in all_rallies if r["on_time"]]
    cycle_sec = RALLY_FILL_SEC + travel_sec * 2 + gap_sec
    total_sent = sum(w["troops_sent"] for w in waves_data)
    total_capacity = sum(w["capacity"] for w in waves_data)
    total_pool = sum(w["pool"] for w in waves_data)

    return {
        "waves": waves_data,
        "wave_count": wave_count,
        "players_per_wave": players_per_wave,
        "leftover_players": leftover_players,
        "num_rallies": players_per_wave * wave_count,
        "total_pool": total_pool,
        "total_capacity": total_capacity,
        "total_sent": total_sent,
        "troops_on_time": sum(r["troops"] for r in valid_all),
        "full_rallies": sum(1 for r in all_rallies if r["troops"] >= rally_cap),
        "partial_rallies": sum(1 for r in all_rallies if 0 < r["troops"] < rally_cap),
        "empty_rallies": sum(1 for r in all_rallies if r["troops"] == 0),
        "first_hit": format_countdown(min(r["hit_sec"] for r in valid_all)) if valid_all else "—",
        "last_hit": format_countdown(max(r["hit_sec"] for r in valid_all)) if valid_all else "—",
        "cycle_sec": cycle_sec,
        "all_rallies": all_rallies,
        "timing": first_hit_breakdown(travel_sec),
    }


def check_second_wave_window(waves, wave_delay_sec, cycle_sec):
    """Can wave 1 return before wave 2 hits? Logistics sanity check."""
    if len(waves) < 2:
        return None
    w1 = waves[0]
    w2 = waves[1]
    if not w1["rallies"] or not w2["rallies"]:
        return None
    w1_last_return = w1["rallies"][-1]["return_sec"]
    w2_first_hit = w2["rallies"][0]["hit_sec"]
    w2_starts = wave_delay_sec
    return {
        "w1_last_return_left": format_countdown(w1_last_return),
        "w2_starts_left": format_countdown(w2_starts),
        "w2_first_hit_left": format_countdown(w2_first_hit),
        "w1_back_before_w2": w1_last_return <= w2_starts,
        "cycle_sec": cycle_sec,
    }


def build_wave_table(wave_rallies):
    rows = []
    for r in wave_rallies:
        sl, sp = time_pair(r["start_sec"])
        dl, dp = time_pair(r["depart_sec"])
        hl, hp = time_pair(r["hit_sec"])
        rl, rp = time_pair(r["return_sec"])
        rows.append({
            "#": r["wave_rally_num"],
            "Host": r["host"],
            "Troops": format_troops(r["troops"]),
            "Fill": r["fill"],
            "L·Start": sl, "P·Start": sp,
            "L·Depart": dl, "P·Depart": dp,
            "L·Hit": hl, "P·Hit": hp,
            "L·Return": rl, "P·Return": rp,
            "OK": "OK" if r["on_time"] else ("LATE" if r["troops"] > 0 else "EMPTY"),
        })
    return pd.DataFrame(rows)


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700&family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@500&display=swap');
        html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; }
        .stApp { background: linear-gradient(165deg, #080a0f, #101520); color: #eef2f8; }
        .block-container { padding-top: 1rem; max-width: 100%; }
        .hero-wrap { text-align: center; padding: 1.4rem; margin-bottom: 1rem; border-radius: 16px;
            background: rgba(255,183,50,0.1); border: 1px solid rgba(255,183,50,0.25); }
        .hero-title { font-family: 'Cinzel', serif; font-size: 2rem; color: #ffb732; margin: 0; }
        .math-box { padding: 1rem; margin-bottom: 1rem; border-radius: 12px;
            background: rgba(74,158,255,0.08); border: 1px solid rgba(74,158,255,0.25);
            font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; line-height: 1.7; color: #cbd5e1; }
        .log-box { padding: 0.6rem 0.75rem; margin-bottom: 0.5rem; border-radius: 8px;
            background: rgba(0,0,0,0.25); font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem; line-height: 1.55; color: #94a3b8; }
        .troops-hero { text-align: center; padding: 1.2rem; margin-bottom: 1rem; border-radius: 14px;
            background: rgba(255,140,30,0.12); border: 1px solid rgba(255,183,50,0.3); }
        .troops-value { font-family: 'Cinzel', serif; font-size: 2.4rem; color: #ffb732; font-weight: 800; }
        .stat-row { display: grid; grid-template-columns: repeat(5,1fr); gap: 0.5rem; margin-bottom: 1rem; }
        @media (max-width:900px){ .stat-row{ grid-template-columns:repeat(2,1fr);} }
        .stat-box { padding: 0.7rem; border-radius: 10px; background: rgba(18,24,34,0.95);
            border: 1px solid rgba(255,255,255,0.06); }
        .stat-k { font-size: 0.62rem; letter-spacing: 0.1em; text-transform: uppercase; color: #6b7d96; }
        .stat-v { font-family: 'JetBrains Mono', monospace; font-size: 1.05rem; color: #f0f4fc; }
        .stat-v.gold { color: #ffb732; }
        .legend-box { padding: 0.65rem 0.9rem; margin-bottom: 1rem; border-radius: 10px;
            background: rgba(20,26,36,0.9); color: #94a3b8; font-size: 0.84rem; }
        .section-head { font-family: 'Cinzel', serif; color: #e8c878; font-size: 1.05rem;
            margin: 1rem 0 0.6rem; border-bottom: 1px solid rgba(255,183,50,0.2); padding-bottom: 0.3rem; }
        .wave-col-head { padding: 0.55rem 0.5rem; border-radius: 8px 8px 0 0; font-weight: 700; }
        .wave-meta { font-size: 0.74rem; color: #94a3b8; font-family: 'JetBrains Mono', monospace; margin-bottom: 0.3rem; }
        div[data-testid="stDataFrame"] { font-family: 'JetBrains Mono', monospace !important; font-size: 0.72rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_wave_table(col, wave_data):
    s = WAVE_STYLE[wave_data["wave"]]
    with col:
        st.markdown(
            f'<div class="wave-col-head" style="background:{s["hex"]}22;border-top:3px solid {s["hex"]};color:{s["hex"]};">'
            f'{s["emoji"]} {s["name"]}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="wave-meta">Start {wave_data["start_left"]} left · '
            f'Sent {format_troops(wave_data["troops_sent"])} / '
            f'Cap {format_troops(wave_data["capacity"])} · '
            f'Hits {wave_data["first_hit"]} → {wave_data["last_hit"]}</div>',
            unsafe_allow_html=True,
        )
        log_html = "<br>".join(wave_data["logistics"])
        st.markdown(f'<div class="log-box">{log_html}</div>', unsafe_allow_html=True)
        if wave_data["rallies"]:
            st.dataframe(
                build_wave_table(wave_data["rallies"]),
                use_container_width=True,
                hide_index=True,
                height=min(80 + len(wave_data["rallies"]) * 36, 440),
                column_config=get_col_config(),
            )


inject_css()

st.markdown(
    '<div class="hero-wrap"><h1 class="hero-title">King Shot Bear Trap Planner</h1>'
    '<p style="color:#94a3b8;margin:0.4rem 0 0;">Empty rallies · per-wave troop pools · side-by-side waves</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Battle setup")
    num_players = st.slider("Number of players", 5, 95, 10, 1)

    st.markdown("**Troops**")
    avg_k = st.slider("Avg troops each player sends (K)", 50, 1000, 200, 10)
    cap_k = st.slider("Rally troop cap (K)", 50, 1000, 400, 10,
                       help="Max troops one rally can hold. Host starts at 0.")
    avg_troops = avg_k * 1000
    rally_cap = cap_k * 1000

    fill_mode = st.radio(
        "How troops fill rallies",
        ["1to1", "stack"],
        format_func=lambda x: "1 host = 1 rally, each sends their troops" if x == "1to1"
        else "Fill rallies to cap in order (stack)",
        index=0,
    )

    travel_sec = st.number_input("Distance to trap (sec)", 10, 600, 10, 1)
    gap_sec = st.number_input("Gap between rally starts (sec)", 0, 120, 5, 1)

    st.markdown("---")
    wave_count = st.radio("Waves", [1, 2, 3],
                          format_func=lambda x: f"{x} wave" if x == 1 else f"{x} waves",
                          index=1, horizontal=True, label_visibility="collapsed")

    per_wave = num_players // wave_count
    rec_delay = recommend_wave_delay(wave_count, travel_sec, gap_sec)
    wave_delay_sec = st.number_input("Seconds between wave starts", 0, 600, rec_delay, 5)

    per_rally_1to1 = min(avg_troops, rally_cap)
    st.markdown("**Example (your wave split)**")
    st.code(
        f"Players per wave = {num_players} / {wave_count} = {per_wave}\n"
        f"Empty rallies made = {per_wave} (one host each)\n"
        f"Wave pool = {per_wave} x {avg_k}K = {format_troops(per_wave * avg_troops)}\n"
        f"Wave capacity = {per_wave} x {cap_k}K = {format_troops(per_wave * rally_cap)}\n"
        f"Each rally gets = min({avg_k}K, {cap_k}K) = {format_troops(per_rally_1to1)}",
        language=None,
    )
    if per_wave * avg_troops < per_wave * rally_cap:
        st.info(f"Each rally only {round(100*avg_k/cap_k)}% full — players don't have enough to fill {cap_k}K caps.")
    if num_players % wave_count:
        st.warning(f"{num_players % wave_count} player(s) sit out.")

plan = calculate_plan(
    num_players, avg_troops, rally_cap, travel_sec, gap_sec,
    wave_count, wave_delay_sec, fill_mode,
)
t = plan["timing"]
wave_gap = check_second_wave_window(plan["waves"], wave_delay_sec, plan["cycle_sec"])

st.markdown(
    f'<div class="math-box">'
    f'<b>First hit = {plan["first_hit"]}</b> (wave 1, rally starts at 30:00 left)<br>'
    f'Host opens EMPTY rally → 5:00 fill window → depart {t["depart_left"]} left ({t["depart_passed"]} passed)<br>'
    f'+ {travel_sec}s travel → <b>HIT {t["hit_left"]} left</b> ({t["hit_passed"]} passed)<br>'
    f'<span style="color:#64748b">30:00 − 5:00 − 0:{travel_sec:02d} = {t["hit_left"]}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

if wave_gap:
    msg = (
        f"Wave 1 last return: {wave_gap['w1_last_return_left']} left · "
        f"Wave 2 starts: {wave_gap['w2_starts_left']} left · "
        f"Wave 2 first hit: {wave_gap['w2_first_hit_left']} left"
    )
    if wave_gap["w1_back_before_w2"]:
        st.success(msg + " — Wave 1 is back before Wave 2 starts (clean handoff).")
    else:
        st.warning(msg + " — Wave 1 still marching when Wave 2 starts (overlap).")

st.markdown(
    f'<div class="troops-hero">'
    f'<div style="font-size:0.72rem;letter-spacing:0.15em;text-transform:uppercase;color:#c9a050;">Total troops hitting bear</div>'
    f'<div class="troops-value">{format_troops(plan["total_sent"])}</div>'
    f'<div style="color:#8899b0;margin-top:0.35rem;">'
    f'Capacity {format_troops(plan["total_capacity"])} · '
    f'{plan["full_rallies"]} FULL · {plan["partial_rallies"]} PARTIAL · '
    f'{format_troops(plan["troops_on_time"])} on time'
    f'</div></div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="stat-row">'
    f'<div class="stat-box"><div class="stat-k">Trap opens</div><div class="stat-v gold">30:00</div></div>'
    f'<div class="stat-box"><div class="stat-k">First hit</div><div class="stat-v gold">{plan["first_hit"]}</div></div>'
    f'<div class="stat-box"><div class="stat-k">Last hit</div><div class="stat-v">{plan["last_hit"]}</div></div>'
    f'<div class="stat-box"><div class="stat-k">Hosts/wave</div><div class="stat-v">{plan["players_per_wave"]}</div></div>'
    f'<div class="stat-box"><div class="stat-k">Cycle</div><div class="stat-v">{format_time(plan["cycle_sec"])}</div></div>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="legend-box">'
    'Each <b>host</b> opens rally at <b>0 troops</b> → wave players send troops during 5-min fill → '
    '<b>L</b> = time left on trap · <b>P</b> = time passed · '
    'Each wave uses ONLY its own players troops (separate pools)'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(f'<div class="section-head">Wave tables — {plan["wave_count"]} side by side</div>', unsafe_allow_html=True)
cols = st.columns(plan["wave_count"])
for idx, w in enumerate(plan["waves"][: plan["wave_count"]]):
    render_wave_table(cols[idx], w)

st.caption("King Shot Bear Trap Planner")
