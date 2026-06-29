"""
King Shot — Bear Trap Rally Planner
Deploy on Streamlit Cloud — main file: app.py
"""

import streamlit as st
import pandas as pd

TRAP_WINDOW_SEC = 30 * 60   # 30-minute bear trap window
RALLY_FILL_SEC = 5 * 60       # 5 minutes to fill rally before march

WAVE_STYLE = {
    1: {"name": "Wave 1", "emoji": "🔵", "hex": "#4a9eff"},
    2: {"name": "Wave 2", "emoji": "🟣", "hex": "#a78bfa"},
    3: {"name": "Wave 3", "emoji": "🟢", "hex": "#34d399"},
}

COL_CONFIG = {
    "#": st.column_config.TextColumn("#", width="small"),
    "Troops": st.column_config.TextColumn("Troops", width="small"),
    "L·Start": st.column_config.TextColumn("⏳ L Start", width="small"),
    "P·Start": st.column_config.TextColumn("⏱ P Start", width="small"),
    "L·Depart": st.column_config.TextColumn("⏳ L Depart", width="small"),
    "P·Depart": st.column_config.TextColumn("⏱ P Depart", width="small"),
    "L·Hit": st.column_config.TextColumn("⏳ L Hit", width="small"),
    "P·Hit": st.column_config.TextColumn("⏱ P Hit", width="small"),
    "L·Return": st.column_config.TextColumn("⏳ L Return", width="small"),
    "P·Return": st.column_config.TextColumn("⏱ P Return", width="small"),
    "OK": st.column_config.TextColumn("✓", width="small"),
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

def time_pair(elapsed_sec: int) -> tuple[str, str]:
    return format_countdown(elapsed_sec), format_time(elapsed_sec)

def recommend_wave_delay(wave_count: int, travel_sec: int, gap_sec: int) -> int:
    cycle = RALLY_FILL_SEC + travel_sec * 2 + gap_sec
    if wave_count == 1:
        return 0
    if wave_count == 2:
        return min(120, max(60, round(cycle * 0.35)))
    return min(120, max(45, round(cycle / wave_count)))

def calculate_plan(num_players, rally_troops, travel_sec, gap_sec, wave_count, wave_delay_sec):
    players_per_wave = num_players // wave_count
    leftover = num_players % wave_count
    all_rallies = []
    waves_data = []
    gid = 1

    for wave_idx in range(wave_count):
        wave_num = wave_idx + 1
        wave_offset = 0 if wave_idx == 0 else wave_delay_sec * wave_idx
        wave_rallies = []

        for i in range(players_per_wave):
            start = wave_offset + i * gap_sec
            depart = start + RALLY_FILL_SEC
            hit = depart + travel_sec
            ret = hit + travel_sec
            rally = {
                "wave_rally_num": i + 1,
                "start_sec": start,
                "depart_sec": depart,
                "hit_sec": hit,
                "return_sec": ret,
                "troops": rally_troops,
                "on_time": hit <= TRAP_WINDOW_SEC,
            }
            wave_rallies.append(rally)
            all_rallies.append({**rally, "wave": wave_num, "id": gid})
            gid += 1

        valid = [r for r in wave_rallies if r["on_time"]]
        l0, p0 = time_pair(wave_offset)
        waves_data.append({
            "wave": wave_num,
            "players": players_per_wave,
            "rallies": wave_rallies,
            "troops": players_per_wave * rally_troops,
            "troops_on_time": sum(r["troops"] for r in valid),
            "start_left": l0,
            "start_passed": p0,
            "first_hit": format_countdown(valid[0]["hit_sec"]) if valid else "—",
            "last_hit": format_countdown(valid[-1]["hit_sec"]) if valid else "—",
        })

    valid_all = [r for r in all_rallies if r["on_time"]]
    cycle_sec = RALLY_FILL_SEC + travel_sec * 2 + gap_sec

    return {
        "waves": waves_data,
        "wave_count": wave_count,
        "players_per_wave": players_per_wave,
        "leftover": leftover,
        "total_rallies": len(all_rallies),
        "total_troops": sum(r["troops"] for r in all_rallies),
        "troops_on_time": sum(r["troops"] for r in valid_all),
        "first_hit": format_countdown(min(r["hit_sec"] for r in valid_all)) if valid_all else "—",
        "last_hit": format_countdown(max(r["hit_sec"] for r in valid_all)) if valid_all else "—",
        "cycle_sec": cycle_sec,
        "recommended_delay": recommend_wave_delay(wave_count, travel_sec, gap_sec),
        "all_rallies": all_rallies,
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
            "Troops": format_troops(r["troops"]),
            "L·Start": sl, "P·Start": sp,
            "L·Depart": dl, "P·Depart": dp,
            "L·Hit": hl, "P·Hit": hp,
            "L·Return": rl, "P·Return": rp,
            "OK": "✅" if r["on_time"] else "❌",
        })
    return pd.DataFrame(rows)

def bonus_cycles(travel_sec, gap_sec, first_return_sec, max_cycles=4):
    cycle = RALLY_FILL_SEC + travel_sec * 2 + gap_sec
    rows = []
    for c in range(1, max_cycles + 1):
        start = first_return_sec + (c - 1) * cycle + gap_sec
        hit = start + RALLY_FILL_SEC + travel_sec
        if hit > TRAP_WINDOW_SEC:
            break
        sl, sp = time_pair(start)
        hl, hp = time_pair(hit)
        rows.append({"Cycle": c + 1, "L·Start": sl, "P·Start": sp, "L·Hit": hl, "P·Hit": hp})
    return rows

FANCY_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700;800&family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@500;600&display=swap');
html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; }
.stApp {
    background: radial-gradient(ellipse 100% 60% at 50% -20%, rgba(255,183,50,0.15), transparent),
                linear-gradient(165deg, #080a0f, #101520, #0a0e14);
    color: #eef2f8;
}
.block-container { padding-top: 1rem; max-width: 100%; }
.hero-wrap {
    text-align: center; padding: 1.75rem 1rem; margin-bottom: 1rem; border-radius: 18px;
    background: linear-gradient(135deg, rgba(255,183,50,0.13), rgba(255,80,20,0.04));
    border: 1px solid rgba(255,183,50,0.28);
}
.hero-badge { font-size: 0.7rem; letter-spacing: 0.28em; text-transform: uppercase; color: #ffb732;
    padding: 0.35rem 1rem; border-radius: 999px; border: 1px solid rgba(255,183,50,0.4); display: inline-block; }
.hero-title { font-family: 'Cinzel', serif; font-size: clamp(1.8rem, 4vw, 2.6rem); font-weight: 800; margin: 0.5rem 0 0;
    background: linear-gradient(135deg, #fff0c0, #ffb732); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; background-clip: text; }
.hero-sub { color: #94a3b8; margin: 0.4rem 0 0; }
.troops-hero { text-align: center; padding: 1.4rem; margin-bottom: 1rem; border-radius: 16px;
    background: linear-gradient(145deg, rgba(255,140,30,0.14), rgba(80,30,10,0.06));
    border: 1px solid rgba(255,183,50,0.35); }
.troops-label { font-size: 0.75rem; letter-spacing: 0.2em; text-transform: uppercase; color: #c9a050; font-weight: 700; }
.troops-value { font-family: 'Cinzel', serif; font-size: clamp(2rem, 5vw, 3.2rem); font-weight: 800;
    background: linear-gradient(180deg, #fff8dc, #ffb732); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; background-clip: text; }
.troops-sub { color: #8899b0; font-size: 0.95rem; margin-top: 0.4rem; }
.stat-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.6rem; margin-bottom: 1rem; }
@media (max-width: 900px) { .stat-row { grid-template-columns: repeat(2, 1fr); } }
.stat-box { padding: 0.75rem; border-radius: 12px; background: rgba(18,24,34,0.95); border: 1px solid rgba(255,255,255,0.06); }
.stat-box.gold { border-color: rgba(255,183,50,0.35); }
.stat-k { font-size: 0.65rem; letter-spacing: 0.12em; text-transform: uppercase; color: #6b7d96; font-weight: 700; }
.stat-v { font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; font-weight: 600; color: #f0f4fc; }
.stat-v.gold { color: #ffb732; }
.legend-box { padding: 0.7rem 1rem; margin-bottom: 1rem; border-radius: 10px;
    background: rgba(20,26,36,0.9); border: 1px solid rgba(255,255,255,0.06); color: #94a3b8; font-size: 0.88rem; }
.section-head { font-family: 'Cinzel', serif; font-size: 1.1rem; color: #e8c878; font-weight: 700;
    margin: 1rem 0 0.75rem; border-bottom: 1px solid rgba(255,183,50,0.2); padding-bottom: 0.35rem; }
.wave-col-head { padding: 0.65rem 0.5rem; border-radius: 10px 10px 0 0; margin-bottom: 0.25rem; font-weight: 700; }
.wave-meta { font-size: 0.78rem; color: #94a3b8; line-height: 1.5; margin-bottom: 0.35rem; font-family: 'JetBrains Mono', monospace; }
.wave-foot { font-size: 0.75rem; color: #64748b; margin-top: 0.35rem; text-align: center; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0c1018, #141c28); }
div[data-testid="stDataFrame"] { font-family: 'JetBrains Mono', monospace !important; font-size: 0.78rem !important; }
"""

def render_wave_table(col, wave_data):
    wnum = wave_data["wave"]
    s = WAVE_STYLE[wnum]

    with col:
        st.markdown(
            f"""<div class="wave-col-head" style="background:{s['hex']}22;border-top:3px solid {s['hex']};
            color:{s['hex']};">{s['emoji']} {s['name']}</div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""<div class="wave-meta">
            👥 {wave_data['players']} players · ⚔ {format_troops(wave_data['troops'])}<br>
            ▶ Start: <b>{wave_data['start_left']}</b> left / <b>{wave_data['start_passed']}</b> passed<br>
            💥 Hits: <b>{wave_data['first_hit']}</b> → <b>{wave_data['last_hit']}</b> left
            </div>""",
            unsafe_allow_html=True,
        )

        if wave_data["rallies"]:
            df = build_wave_table(wave_data["rallies"])
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=min(70 + len(df) * 35, 400),
                column_config=COL_CONFIG,
            )
            st.markdown(
                '<div class="wave-foot">🔒 Trap closes · 00:00 left · 30:00 passed</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No players in this wave.")

st.set_page_config(page_title="King Shot Rally Planner", page_icon="🐻", layout="wide")
st.markdown(FANCY_CSS, unsafe_allow_html=True)

st.markdown(
    """<div class="hero-wrap"><div class="hero-badge">⚔ King Shot Bear Trap ⚔</div>
    <h1 class="hero-title">Rally Wave Tracker</h1>
    <p class="hero-sub">3 wave tables side-by-side · Time left + passed · Equal players per wave</p></div>""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### ⚙ Battle setup")
    num_players = st.slider("Number of players", 5, 95, 15, 1)
    rally_size_k = st.slider("Rally size (thousands)", 50, 900, 100, 10,
                             help="100 = 100,000 troops. Range 50K–900K.")
    rally_troops = rally_size_k * 1000
    travel_sec = st.number_input("Distance to trap (sec, one way)", 10, 600, 10, 1,
                                 help="Min 10 sec. Same time to return.")
    gap_sec = st.number_input("Time to start next rally (sec)", 0, 120, 5, 1)

    st.markdown("---")
    wave_count = st.radio("Waves", [1, 2, 3],
                          format_func=lambda x: f"{x} wave" if x == 1 else f"{x} waves",
                          index=1, horizontal=True, label_visibility="collapsed")

    per_wave = num_players // wave_count
    leftover = num_players % wave_count
    rec_delay = recommend_wave_delay(wave_count, travel_sec, gap_sec)
    wave_delay_sec = st.number_input("Seconds between wave starts", 0, 600, rec_delay, 5,
                                     help=f"Suggested: {rec_delay}s (~2 min for 2 waves)")

    st.markdown(
        f"""<div style="padding:0.75rem;border-radius:10px;background:rgba(255,183,50,0.08);
        border:1px solid rgba(255,183,50,0.2);line-height:1.65;font-size:0.9rem;">
        ⚖️ <b>Equal waves</b><br>{num_players} ÷ {wave_count} = <b>{per_wave}</b> each (round down)<br>
        📋 {wave_count} table{"s" if wave_count > 1 else ""} shown side-by-side</div>""",
        unsafe_allow_html=True,
    )
    if leftover:
        st.warning(f"{leftover} player(s) sit out.")
    st.markdown("---")
    st.markdown(
        f"""**Rules baked in:**<br>
        · 30:00 trap window<br>
        · 5:00 rally fill<br>
        · {travel_sec}s to trap + {travel_sec}s return<br>
        · {gap_sec}s gap between rallies""",
        unsafe_allow_html=True,
    )

plan = calculate_plan(num_players, rally_troops, travel_sec, gap_sec, wave_count, wave_delay_sec)

st.markdown(
    f"""<div class="troops-hero"><div class="troops-label">Total troops to bear trap</div>
    <div class="troops-value">{format_troops(plan['total_troops'])}</div>
    <div class="troops-sub">{plan['total_rallies']} rallies × {format_troops(rally_troops)}
    · {format_troops(plan['troops_on_time'])} hit before 00:00</div></div>""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""<div class="stat-row">
    <div class="stat-box gold"><div class="stat-k">Trap opens</div><div class="stat-v gold">30:00 L</div></div>
    <div class="stat-box"><div class="stat-k">First hit</div><div class="stat-v">{plan['first_hit']}</div></div>
    <div class="stat-box"><div class="stat-k">Last hit</div><div class="stat-v">{plan['last_hit']}</div></div>
    <div class="stat-box"><div class="stat-k">Players/wave</div><div class="stat-v">{plan['players_per_wave']}</div></div>
    <div class="stat-box"><div class="stat-k">Rally cycle</div><div class="stat-v">{format_time(plan['cycle_sec'])}</div></div>
    </div>""",
    unsafe_allow_html=True,
)

st.markdown(
    """<div class="legend-box">
    <b>Time left (L)</b> = in-game countdown (30:00 → 00:00) &nbsp;|&nbsp;
    <b>Time passed (P)</b> = elapsed since bear trapped (00:00 → 30:00) &nbsp;|&nbsp;
    Each rally: <b>Start → 5min fill → Depart → Hit → Return</b>
    </div>""",
    unsafe_allow_html=True,
)

active = plan["waves"][: plan["wave_count"]]
st.markdown(f'<div class="section-head">Wave tables — {plan["wave_count"]} side by side</div>', unsafe_allow_html=True)

cols = st.columns(plan["wave_count"])
for idx, w in enumerate(active):
    render_wave_table(cols[idx], w)

if plan["all_rallies"]:
    first_ret = plan["all_rallies"][0]["return_sec"]
    bonus = bonus_cycles(travel_sec, gap_sec, first_ret)
    if bonus:
        with st.expander("🔄 Bonus — second rally cycle (same players return & restart immediately)"):
            st.caption("Extra hits possible before trap closes at 00:00 left.")
            st.dataframe(pd.DataFrame(bonus), use_container_width=True, hide_index=True)

st.caption("🐻 King Shot Bear Trap · Upload app.py + requirements.txt to GitHub · Streamlit Cloud main file: app.py")
