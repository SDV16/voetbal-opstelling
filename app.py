import streamlit as st
from collections import defaultdict
import math

st.set_page_config(layout="wide")

# ===== SESSION STATE =====
if "custom_schedule" not in st.session_state:
    st.session_state.custom_schedule = None

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
        blocks.append((f"{int(start)}-{int(end)}",size))
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
                    limit = -20
                if remaining[p] - b_min >= limit:
                    cands.append(p)
            if not cands:
                return False
            cands.sort(
                key=lambda p:(
                    -remaining[p],
                    position_rank(p,pos),
                    -scarcity_bonus(p,pos,players),
                    -tiebreak(p,cands)
                )
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
# OUTPUT
# =====================================================
if st.button("Genereer opstellingen"):
    if len(selected_players) < 10:
        st.error("Minimaal 10 spelers nodig")
    else:
        res = choose_best_blocks(list(selected_players.keys()),training_counts,priority_flags)

        if res[0] is None:
            st.error("Geen opstelling gevonden.")
        else:
            blocks,schedule,targets,mins,is_strict,max_dev,total_dev = res

            if st.session_state.custom_schedule is None:
                st.session_state.custom_schedule = schedule.copy()

            custom_schedule = st.session_state.custom_schedule

            st.subheader("Gebruikte blokken")
            st.write(", ".join(f"{n} ({int(m)} min)" for n,m in blocks))

            prev_players = set()

            for block_idx,(block_name,block_min) in enumerate(blocks):

                st.subheader(f"Blok {block_name} ({int(block_min)} min)")

                pos_map = custom_schedule[block_name]

                def row(d):
                    cols = st.columns(len(d))
                    for i,pos in d.items():
                        spelers_lijst = list(selected_players.keys())
                        current = pos_map.get(pos)

                        index = 0
                        if current in spelers_lijst:
                            index = spelers_lijst.index(current)

                        new_player = cols[i].selectbox(
                            pos,
                            spelers_lijst,
                            index=index,
                            key=f"{block_name}_{pos}"
                        )

                        custom_schedule[block_name][pos] = new_player

                row({0:"lb",3:"sp",6:"rb"})
                row({0:"cm1",3:"cm2",6:"cm3"})
                row({0:"la",2:"cv1",4:"cv2",6:"ra"})

            # ===== HERBEREKEN MINUTEN =====
            mins = defaultdict(float)
            for b_name, b_min in blocks:
                for pos, sp in custom_schedule[b_name].items():
                    mins[sp] += b_min

            # ===== VALIDATIE =====
            st.subheader("Validatie")
            for b_name,_ in blocks:
                spelers = list(custom_schedule[b_name].values())
                if len(spelers) != len(set(spelers)):
                    st.error(f"Dubbele speler in blok {b_name}")

            # ===== TABEL =====
            st.header("Minutenoverzicht")

            table = []
            for p in selected_players:
                g = mins[p]
                r = targets[p]
                diff = g - r

                table.append({
                    "Speler":p,
                    "Recht op":f"{int(round(r))} min",
                    "Gekregen":f"{int(round(g))} min",
                    "Verschil":f"{int(round(diff))} min",
                })

            st.table(table)
