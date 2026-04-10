import streamlit as st
from collections import defaultdict
import math

st.set_page_config(layout="wide")

# =====================================================
# SPELERSDATABASE
# =====================================================
PLAYERS = {
    "Jannick": {"favourite":["ra"], "alternative":["rb", "lb"], "emergency":["la"]},
    "Collin": {"favourite":["lb"], "alternative":["rb"], "emergency":["sp"]},
    "Wout": {"favourite":["rb"], "alternative":["lb"], "emergency":["sp"]},
    "Jaimy": {"favourite":["sp"], "alternative":["lb","rb"], "emergency":[]},
    "Sjoerd": {"favourite":["cm", "sp"], "alternative":[], "emergency":[]},
    "Pelle": {"favourite":["sp"], "alternative":["cm", "lb"], "emergency":["rb"]},
    "Tim": {"favourite":["sp"], "alternative":["cm"], "emergency":[]},
    "Steijn": {"favourite":["cm"], "alternative":[], "emergency":["sp"]},
    "Jorra": {"favourite":["cm"], "alternative":[], "emergency":[]},
    "Tycho": {"favourite":["cm"], "alternative":[], "emergency":[]},
    "Nord": {"favourite":["la"], "alternative":["ra"], "emergency":["cv"]},
    "Dinand": {"favourite":["ra", "la"], "alternative":[], "emergency":[]},
    "Sietse": {"favourite":["ra"], "alternative":["la"], "emergency":["cv"]},
    "Stijn": {"favourite":["cv"], "alternative":[], "emergency":["ra", "la"]},
    "Xander": {"favourite":["cv"], "alternative":[], "emergency":["ra","la"]},
    "Jens": {"favourite":["cv"], "alternative":[], "emergency":["ra","la"]},
    "Roef": {"favourite":["cv"], "alternative":[], "emergency":["cm"]},
    "Chris": {"favourite":["ra"], "alternative":["sp", "cv"], "emergency":["la", "rb", "lb"]},
    "Julius": {"favourite":["cv"], "alternative":[], "emergency":["ra", "la"]},
    "Tobias": {"favourite":["rb", "lb", "sp"], "alternative":[""], "emergency":[]},
    "Nicky": {"favourite":["ra", "la"], "alternative":[], "emergency":[]},
}

POSITIONS_ORDER = ["sp", "cv1", "cv2", "cm1", "cm2", "cm3", "lb", "rb", "la", "ra"]

TOTAL_FIELD_MINUTES = 90 * 10
BLOCK_OPTIONS = [30, 22.5, 20, 15, 10]

# =====================================================
# UI
# =====================================================
st.title("Opstelling Generator – Eerlijke Minuten & Dynamische Blokken")

st.sidebar.header("Training aftrek")
bonus_1 = st.sidebar.number_input("Aftrek bij 1 training", 0, 30, 10)
bonus_0 = st.sidebar.number_input("Aftrek bij 0 trainingen", 0, 30, 20)

st.header("Selecteer spelers")

selected_players = {}
training_counts = {}
priority_flags = {}

for player in PLAYERS:
    col1, col2, col3 = st.columns([2,3,2])
    with col1:
        selected = st.checkbox(player, key=f"sel_{player}")
    if selected:
        with col2:
            trainingen = st.radio(
                f"Trainingen {player}",
                options=[0,1,2],
                format_func=lambda x: f"{x} trainingen",
                horizontal=True,
                key=f"train_{player}"
            )
        with col3:
            priority = st.checkbox("Voorrang", key=f"prio_{player}")

        selected_players[player] = PLAYERS[player]
        training_counts[player] = trainingen
        priority_flags[player] = priority

# =====================================================
# TARGET MINUTEN
# =====================================================
def calculate_target_minutes(players, training_counts):
    n = len(players)
    base = TOTAL_FIELD_MINUTES / n

    raw = {}
    total_removed = 0

    for p in players:
        if training_counts[p] == 0:
            raw[p] = base - bonus_0
            total_removed += bonus_0
        elif training_counts[p] == 1:
            raw[p] = base - bonus_1
            total_removed += bonus_1
        else:
            raw[p] = base

    redistribute = total_removed / n if n>0 else 0

    final = {}
    for p in players:
        candidate = raw[p] + redistribute
        final[p] = min(candidate, 90)
        final[p] = 5 * round(final[p] / 5)

    return final

# =====================================================
# POSITIE RANKING
# =====================================================
def position_rank(player, pos):
    base_pos = pos[:2] if pos.startswith(("cm","cv")) else pos
    if base_pos in PLAYERS[player]["favourite"]:
        return 1
    if base_pos in PLAYERS[player]["alternative"]:
        return 2
    if base_pos in PLAYERS[player]["emergency"]:
        return 3
    return 999

# =====================================================
# SCHAARSTE BONUS
# =====================================================
def scarcity_bonus(player, pos, players):
    base_pos = pos[:2] if pos.startswith(("cm","cv")) else pos
    fav_players = [p for p in players if base_pos in PLAYERS[p]["favourite"]]
    if len(fav_players) <= 2:
        if base_pos in PLAYERS[player]["favourite"]:
            return 10
    return 0

# =====================================================
# BLOKGENERATOR
# =====================================================
def generate_block_patterns(strict=True):
    results = []
    max_10 = 2 if strict else 3
    max_15 = 2 if strict else 3

    def backtrack(remaining, start_idx, used_10, used_15, current):
        if abs(remaining) < 1e-6:
            if current[0] < 15 or current[-1] < 15:
                return
            results.append(list(current))
            return
        if remaining < 0 or len(current) > 8:
            return
        for i in range(start_idx, len(BLOCK_OPTIONS)):
            size = BLOCK_OPTIONS[i]
            if size == 10 and used_10 >= max_10:
                continue
            if size == 15 and used_15 >= max_15:
                continue
            current.append(size)
            backtrack(remaining - size, i, used_10 + (size==10), used_15 + (size==15), current)
            current.pop()

    backtrack(90,0,0,0,[])
    results.sort(key=lambda p:(len(p),[-x for x in p]))
    return results

def build_blocks_from_pattern(pattern):
    blocks = []
    start = 0
    for size in pattern:
        end = start + size

        if start < 45 < end:
            return None

        blocks.append((f"{int(start)}-{int(end)}", size))
        start = end

    return blocks

# =====================================================
# GENERATE SCHEDULE
# =====================================================
def generate_schedule(players, targets, priority_flags, blocks):
    remaining = targets.copy()
    schedule = {}
    played = defaultdict(list)

    def tiebreak(p,cands):
        if all(remaining[x] == remaining[p] for x in cands):
            return 1 if priority_flags.get(p,False) else 0
        return 0

    for b_name,b_min in blocks:
        schedule[b_name] = {}
        used = set()

        def assign(idx):
            if idx == len(POSITIONS_ORDER):
                return True
            pos = POSITIONS_ORDER[idx]
            cands = []
            for p in players:
                if p in used:
                    continue
                if position_rank(p,pos) > 3:
                    continue
                limit = -10
                if scarcity_bonus(p,pos,players) > 0:
                    limit = -15
                if remaining[p] - b_min >= limit:
                    cands.append(p)
            if not cands:
                return False
            cands.sort(
                key=lambda p:(-remaining[p], position_rank(p,pos), -scarcity_bonus(p,pos,players), -tiebreak(p,cands))
            )
            for ch in cands:
                schedule[b_name][pos] = ch
                used.add(ch)
                if assign(idx+1):
                    return True
                used.remove(ch)
                del schedule[b_name][pos]
            return False

        if not assign(0):
            return None,None

        for pos in POSITIONS_ORDER:
            ch = schedule[b_name][pos]
            remaining[ch] -= b_min
            played[ch].append((pos,b_min))

    return schedule,played

# =====================================================
# WISSELSPREIDING
# =====================================================
def merge_steps_same_minute(steps):
    merged = {}
    for minute, pairs in steps:
        if minute not in merged:
            merged[minute] = []
        merged[minute].extend(pairs)
    return sorted([(m, merged[m]) for m in sorted(merged.keys())], key=lambda x: x[0])

def spread_substitutions(block_start, block_size, players_in, players_out):
    subs = list(zip(players_in, players_out))
    subs = subs[:4]

    minute = 5 * round(block_start / 5)

    adjusted_block_start = None
    if minute == 40:
        minute = 45
        adjusted_block_start = 45

    if len(subs) <= 2:
        return [(minute, subs)], adjusted_block_start

    steps = []
    max_per_step = 2

    steps.append((minute, subs[:max_per_step]))

    minute2 = minute + 5
    if minute2 == 40:
        minute2 = 45
    steps.append((minute2, subs[max_per_step:]))

    return steps, adjusted_block_start

# =====================================================
# >>> DEEL 6 UPDATE <<<
# ECHTE MINUTEN ENGINE (DEEL 1)
# =====================================================
def compute_real_minutes(blocks, schedule, subs_per_block):
    segments = defaultdict(list)

    for block_name, _ in blocks:
        start, end = map(int, block_name.split("-"))

        active = {}
        for pos, p in schedule[block_name].items():
            active[p] = start

        for minute, pairs in subs_per_block.get(block_name, []):
            for p_in, p_out in pairs:

                if p_out in active:
                    segments[p_out].append((active[p_out], minute))
                    del active[p_out]

                if p_in not in active:
                    active[p_in] = minute

        for p, s in active.items():
            segments[p].append((s, end))

    real_minutes = {p: sum(e - s for s, e in segs) for p, segs in segments.items()}
    return real_minutes, segments

# =====================================================
# >>> DEEL 6 UPDATE <<<
# FAIRNESS MET ECHTE MINUTEN (DEEL 2)
# =====================================================
def evaluate_blocks(players,training_counts,priority_flags,pattern):
    blocks = build_blocks_from_pattern(pattern)
    if blocks is None:
        return float('inf'), None, None, None, None

    targets = calculate_target_minutes(players,training_counts)
    schedule,_ = generate_schedule(players,targets,priority_flags,blocks)
    if schedule is None:
        return float('inf'),None,None,None,None

    ### BELANGRIJK: subs_per_block wordt pas gevuld in de UI-loop
    ### Daarom gebruiken we een lege dict hier (fairness werkt pas volledig in de uiteindelijke run)
    empty_subs = {}

    real_minutes, _ = compute_real_minutes(blocks, schedule, empty_subs)
    mins = real_minutes

    total_dev = sum(abs(mins.get(p,0) - targets[p]) for p in players)

    return total_dev,blocks,schedule,targets,mins

# =====================================================
# BESTE BLOKKEN KIEZEN
# =====================================================
def choose_best_blocks(players, training_counts, priority_flags, strict=True):
    patterns = generate_block_patterns(strict=strict)
    best_score = float('inf')
    best = (None, None, None, None, None)

    for pattern in patterns:
        score, blocks, schedule, targets, mins = evaluate_blocks(
            players, training_counts, priority_flags, pattern
        )
        if score < best_score and blocks is not None:
            best_score = score
            best = (blocks, schedule, targets, mins, pattern)

    return best

# =====================================================
# HOOFDLOGICA / UI
# =====================================================
if not selected_players:
    st.warning("Selecteer minimaal één speler.")
else:
    players = list(selected_players.keys())

    blocks, schedule, targets, mins, pattern = choose_best_blocks(
        players, training_counts, priority_flags, strict=True
    )

    if blocks is None or schedule is None:
        st.error("Kon geen geldige blokverdeling maken met deze instellingen.")
    else:
        st.subheader("Gekozen blokpatroon")

        # FIX: geen None min meer
        st.write("Blokken:", ", ".join(f"{size} min" for _, size in blocks))

        # -------------------------------------------------
        # BLOKKEN + WISSELS + SUBS_PER_BLOCK (DEEL 3)
        # -------------------------------------------------
        subs_per_block = {}
        
        for block_idx, (block_name, block_min) in enumerate(blocks):
            st.markdown(f"## Blok {block_idx+1}: {block_name} ({block_min} min)")
        
            # -------------------------------------------------
            # FANCY 4‑3‑3 VISUELE OPSTELLING (GEFIXT)
            # -------------------------------------------------

            speler = schedule[block_name]
            
            sp  = speler["sp"]
            cv1 = speler["cv1"]
            cv2 = speler["cv2"]
            cm1 = speler["cm1"]
            cm2 = speler["cm2"]
            cm3 = speler["cm3"]
            lb  = speler["lb"]
            rb  = speler["rb"]
            la  = speler["la"]
            ra  = speler["ra"]
            
            # vaste breedte voor elke naam
            def f(n):
                return f"{n:^15}"
            
            opstelling = f"""
                            {f(la)}   {f(sp)}   {f(ra)}
            
                            {f(cm1)}   {f(cm2)}   {f(cm3)}
            
                        {f(lb)}   {f(cv1)}   {f(cv2)}   {f(rb)}
            """
            
            st.markdown(f"```text\n{opstelling}\n```")


            # -------------------------------------------------
            # WISSELS
            # -------------------------------------------------
            col1, col2 = st.columns(2)
        
            with col1:
                st.write("**Wissels in dit blok**")
        
                erin = st.multiselect(
                    f"Spelers erin in blok {block_name}",
                    options=players,
                    key=f"erin_{block_name}"
                )
        
                eruit = st.multiselect(
                    f"Spelers eruit in blok {block_name}",
                    options=[schedule[block_name][pos] for pos in POSITIONS_ORDER],
                    key=f"eruit_{block_name}"
                )
        
            with col2:
                if block_idx > 0 and (erin or eruit):
                    steps, adjusted_start = spread_substitutions(
                        int(block_name.split("-")[0]),
                        block_min,
                        erin,
                        eruit
                    )
                else:
                    steps = []
        
                subs_per_block[block_name] = steps
        
                if steps:
                    st.write("**Wisselmomenten:**")
                    for minute, pairs in steps:
                        txt = ", ".join(f"{p_out} → {p_in}" for p_in, p_out in pairs)
                        st.write(f"- minuut {minute}: {txt}")
                else:
                    st.write("Geen wissels in dit blok.")

        # -------------------------------------------------
        # MINUTENOVERZICHT (ECHTE MINUTEN + OUDE KOLLOMMEN)
        # -------------------------------------------------
        st.header("Minutenoverzicht (echte minuten)")

        real_minutes, segments = compute_real_minutes(blocks, schedule, subs_per_block)

        table = []
        for p in players:
            gekregen = real_minutes.get(p, 0)
            recht = targets[p]
            diff = gekregen - recht

            # posities per segment
            pos_minutes = defaultdict(int)
            blokken_gespeeld = []

            for (s, e) in segments.get(p, []):
                duration = e - s

                for block_name, _ in blocks:
                    b_start, b_end = map(int, block_name.split("-"))
                    if s >= b_start and e <= b_end:

                        # bloknummer
                        blok_index = [bn for bn, _ in blocks].index(block_name) + 1
                        blokken_gespeeld.append(str(blok_index))

                        # positie
                        for pos, speler in schedule[block_name].items():
                            if speler == p:
                                base = pos[:2] if pos.startswith(("cm","cv")) else pos
                                pos_minutes[base] += duration

            # oude kolommen terug
            trainingen = training_counts[p]
            prio = "Ja" if priority_flags.get(p, False) else "Nee"

            table.append({
                "Speler": p,
                "Trainingen": trainingen,
                "Voorrang": prio,
                "Recht op": f"{recht} min",
                "Gekregen": f"{gekregen} min",
                "Verschil": f"{diff:+} min",
                "Blokken": ", ".join(blokken_gespeeld) if blokken_gespeeld else "—",
                "Posities": ", ".join(f"{k}:{v}m" for k, v in pos_minutes.items()) if pos_minutes else "—",
            })

        st.table(table)

