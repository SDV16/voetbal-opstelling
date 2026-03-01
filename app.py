import streamlit as st
from collections import defaultdict
import math

st.set_page_config(layout="wide")

# =====================================================
# SPELERSDATABASE
# =====================================================
PLAYERS = {
    "Jannick": {"favourite":["ra"], "alternative":["rb", "lb"], "emergency":["la"]},
    "Collin": {"favourite":["lb"], "alternative":["rb", "sp"], "emergency":["sp"]},
    "Wout": {"favourite":["rb"], "alternative":["lb"], "emergency":["sp"]},
    "Jaimy": {"favourite":["sp"], "alternative":["lb","rb"], "emergency":[]},
    "Sjoerd": {"favourite":["cm"], "alternative":["sp"], "emergency":[]},
    "Pelle": {"favourite":["cm"], "alternative":["sp", "lb", "rb"], "emergency":[]},
    "Tim": {"favourite":["sp"], "alternative":[], "emergency":["sp"]},
    "Steijn": {"favourite":["cm"], "alternative":[], "emergency":["sp"]},
    "Jorra": {"favourite":["cm"], "alternative":[], "emergency":[]},
    "Tycho": {"favourite":["cm"], "alternative":[], "emergency":[]},
    "Nord": {"favourite":["la"], "alternative":["ra"], "emergency":[]},
    "Dinand": {"favourite":["ra", "la"], "alternative":[], "emergency":[]},
    "Sietse": {"favourite":["ra"], "alternative":["la"], "emergency":["cv"]},
    "Stijn": {"favourite":["cv"], "alternative":[], "emergency":[]},
    "Xander": {"favourite":["cv"], "alternative":[], "emergency":["ra","la"]},
    "Jens": {"favourite":["cv"], "alternative":[], "emergency":["ra","la"]},
    "Roef": {"favourite":["cv"], "alternative":[], "emergency":["cm"]},
    "Chris": {"favourite":["ra"], "alternative":["sp"], "emergency":["la", "rb", "lb"]},
}

POSITIONS_ORDER = ["sp", "cv1", "cv2", "cm1", "cm2", "cm3", "lb", "rb", "la", "ra"]

TOTAL_FIELD_MINUTES = 90 * 10
BLOCK_OPTIONS = [30, 22.5, 20, 15, 10]

# =====================================================
# UI
# =====================================================
st.title("Opstelling Generator – Eerlijke Minuten & Dynamische Blokken")

st.sidebar.header("Training aftrek")
bonus_1 = st.sidebar.number_input("Aftrek bij 1 training", 0, 30, 5)
bonus_0 = st.sidebar.number_input("Aftrek bij 0 trainingen", 0, 30, 10)

st.header("Selecteer spelers")

selected_players = {}
training_counts = {}
priority_flags = {}

for player in PLAYERS:
    col1, col2, col3 = st.columns([2, 3, 2])
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
# TARGET MINUTEN – nooit meer dan 90
# =====================================================
def calculate_target_minutes(players, training_counts):
    n = len(players)
    base = TOTAL_FIELD_MINUTES / n

    raw = {}
    total_removed = 0.0

    for p in players:
        if training_counts[p] == 0:
            raw[p] = base - bonus_0
            total_removed += bonus_0
        elif training_counts[p] == 1:
            raw[p] = base - bonus_1
            total_removed += bonus_1
        else:
            raw[p] = base

    redistribute = total_removed / n

    final = {}
    for p in players:
        candidate = raw[p] + redistribute
        final[p] = min(candidate, 90.0)
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
# BLOKGENERATOR
# =====================================================
def generate_block_patterns(strict=True):
    results = []
    max_10 = 2 if strict else 3
    max_15 = 2 if strict else 3

    def backtrack(remaining, start_idx, used_10, used_15, current):
        if abs(remaining) < 1e-6:
            results.append(list(current))
            return
        if remaining < 0 or len(current) > 8:
            return
        for i in range(start_idx, len(BLOCK_OPTIONS)):
            size = BLOCK_OPTIONS[i]
            if size == 10 and used_10 >= max_10: continue
            if size == 15 and used_15 >= max_15: continue
            current.append(size)
            backtrack(remaining - size, i, used_10 + (size==10), used_15 + (size==15), current)
            current.pop()

    backtrack(90, 0, 0, 0, [])
    results.sort(key=lambda p: (len(p), [-x for x in p]))
    return results

def build_blocks_from_pattern(pattern):
    blocks = []
    start = 0.0
    for size in pattern:
        end = start + size
        blocks.append((f"{int(start)}-{int(end)}", size))
        start = end
    return blocks

# =====================================================
# GENERATE SCHEDULE + FIX BLOCK
# =====================================================
def generate_schedule(players, targets, priority_flags, blocks):
    remaining = targets.copy()
    schedule = {}
    played = defaultdict(list)

    def tiebreak(p, cands):
        if all(remaining[x] == remaining[p] for x in cands):
            return 1 if priority_flags.get(p, False) else 0
        return 0

    for b_name, b_min in blocks:
        schedule[b_name] = {}
        used = set()

        def assign(idx):
            if idx == len(POSITIONS_ORDER): return True
            pos = POSITIONS_ORDER[idx]
            cands = [p for p in players if p not in used and position_rank(p, pos) <= 3 and remaining[p] - b_min >= -10]
            if not cands: return False
            cands.sort(key=lambda p: (-remaining[p], position_rank(p, pos), -tiebreak(p, cands)))
            for ch in cands:
                schedule[b_name][pos] = ch
                used.add(ch)
                if assign(idx + 1): return True
                used.remove(ch)
                del schedule[b_name][pos]
            return False

        if not assign(0) or len(schedule[b_name]) != len(POSITIONS_ORDER):
            return None, None

        for pos in POSITIONS_ORDER:
            ch = schedule[b_name][pos]
            remaining[ch] -= b_min
            played[ch].append((pos, b_min))

        # fix_block
        improved = True
        while improved:
            improved = False
            pos_list = list(schedule[b_name].keys())
            for i in range(len(pos_list)):
                for j in range(i+1, len(pos_list)):
                    p1_pos, p2_pos = pos_list[i], pos_list[j]
                    p1, p2 = schedule[b_name][p1_pos], schedule[b_name][p2_pos]
                    if p1 in ("FOUT", None) or p2 in ("FOUT", None): continue
                    s_before = position_rank(p1, p1_pos) + position_rank(p2, p2_pos)
                    s_after  = position_rank(p2, p1_pos) + position_rank(p1, p2_pos)
                    if s_after < s_before:
                        schedule[b_name][p1_pos], schedule[b_name][p2_pos] = p2, p1
                        improved = True

    return schedule, played

# =====================================================
# EVALUATIE
# =====================================================
def evaluate_blocks(players, training_counts, priority_flags, pattern):
    blocks = build_blocks_from_pattern(pattern)
    targets = calculate_target_minutes(players, training_counts)
    schedule, _ = generate_schedule(players, targets, priority_flags, blocks)
    if schedule is None:
        return float('inf'), None, None, None, None

    mins = defaultdict(float)
    for b_name, b_min in blocks:
        for pos, sp in schedule[b_name].items():
            if sp in players and sp != "FOUT":
                mins[sp] += b_min

    total_dev = sum(abs(mins[p] - targets[p]) for p in players)
    return total_dev, blocks, schedule, targets, mins

# =====================================================
# BESTE BLOKKEN KIEZEN – VARIANT A
# =====================================================
def choose_best_blocks(players, training_counts, priority_flags):
    targets = calculate_target_minutes(players, training_counts)

    # Fase 1: strikt binnen ±9
    for pat in generate_block_patterns(True):
        td, bl, sc, tg, mn = evaluate_blocks(players, training_counts, priority_flags, pat)
        if sc is None: continue
        devs = [abs(mn[p] - tg[p]) for p in players]
        md = max(devs) if devs else 0
        if md <= 9:
            return bl, sc, tg, mn, True, md, td

    # Fase 2: versoepeld – VARIANT A: kwadratische straf boven ±5
    best_score = float('inf')
    best = None, None, None, None
    best_md = best_td = float('inf')

    for pat in generate_block_patterns(False):
        td, bl, sc, tg, mn = evaluate_blocks(players, training_counts, priority_flags, pat)
        if sc is None: continue
        devs = [abs(mn[p] - tg[p]) for p in players]
        md = max(devs) if devs else 0
        
        deviation_cost = sum((max(0, abs(d) - 5)) ** 2 for d in devs)
        big_outliers = sum(1 for d in devs if abs(d) >= 10) * 20000
        
        score = deviation_cost * 200 + big_outliers + md * 10000
        
        if score < best_score:
            best_score = score
            best = bl, sc, tg, mn
            best_md, best_td = md, td

    if best[0] is not None:
        return *best, False, best_md, best_td

    return None, None, None, None, None, 0, 0

# =====================================================
# KNOP & OUTPUT – aangepaste wissel-weergave
# =====================================================
if st.button("Genereer opstellingen"):
    if len(selected_players) < 10:
        st.error("Minimaal 10 spelers nodig")
    else:
        res = choose_best_blocks(selected_players, training_counts, priority_flags)
        if res[0] is None:
            st.error("Geen opstelling gevonden binnen de grenzen.")
        else:
            blocks, schedule, targets, mins, is_strict, max_dev, total_dev = res

            st.subheader("Gebruikte blokken")
            st.write(", ".join(f"{n} ({int(m)} min)" for n,m in blocks))

            used_10 = sum(m == 10 for _,m in blocks)
            used_15 = sum(m == 15 for _,m in blocks)

            devs = [abs(mins[p] - targets[p]) for p in selected_players]
            num_above_5 = sum(abs(d) > 5 for d in devs)
            num_above_10 = sum(abs(d) >= 10 for d in devs)

            if is_strict:
                st.success(
                    f"Binnen ±9 min\n"
                    f"Max afwijking: {max_dev} min\n"
                    f"Totaal afwijking: {total_dev:.1f} min\n"
                    f"Spelers buiten ±5 min: {num_above_5}"
                )
            else:
                st.warning(
                    f"⚠️ Versoepeld ({used_10}x 10, {used_15}x 15)\n\n"
                    f"Max afwijking: **{max_dev}** min\n"
                    f"Totaal afwijking: **{total_dev:.1f}** min\n"
                    f"Spelers met >5 min afwijking: **{num_above_5}**\n"
                    f"Daarvan ≥10 min: **{num_above_10}**"
                )

            # Hou vorige spelers bij
            prev_players = set()

            for block_idx, (block_name, block_min) in enumerate(blocks):
                current_players = set()
                for pos, speler in schedule[block_name].items():
                    if speler not in ("FOUT", None):
                        current_players.add(speler)

                st.subheader(f"Blok {block_name} ({int(block_min)} min)")

                # Veldopstelling
                pos_map = schedule[block_name]
                def row(d):
                    cols = st.columns(20)
                    for i, pos in d.items():
                        cols[i].write(pos_map.get(pos, "—"))
                row({0:"lb", 3:"sp", 6:"rb"})
                row({0:"cm1", 3:"cm2", 6:"cm3"})
                row({0:"la", 2:"cv1", 4:"cv2", 6:"ra"})

                # Wissels tonen (vanaf tweede blok)
                if block_idx > 0:
                    eruit = sorted(prev_players - current_players)
                    erin  = sorted(current_players - prev_players)

                    st.markdown("**Wissels dit blok:**")

                    if not (erin or eruit):
                        st.markdown("_Geen wissels dit blok_")
                    else:
                        for sp_in in erin:
                            if sp_in in erin and sp_in in prev_players:  # zou niet moeten, maar veiligheid
                                continue
                            line = f"{sp_in} erin"
                            # Zoek of er iemand uitgaat die we kunnen koppelen (optioneel, maar mooier)
                            if eruit:
                                # Neem de eerste uitgaande als voorbeeld (of sorteer op naam)
                                sp_out = eruit.pop(0) if eruit else None
                                if sp_out:
                                    line += f" --> {sp_out} eruit"
                                else:
                                    line += ""
                            st.markdown(line)

                        # Rest van eruit als er nog over zijn
                        for sp_out in eruit:
                            st.markdown(f"{sp_out} eruit")

                else:
                    st.markdown("_Eerste blok – iedereen erin_")

                # Update voor volgende blok
                prev_players = current_players.copy()

            # Minutenoverzicht tabel (blijft hetzelfde)
            st.header("Minutenoverzicht")
            table = []
            for p in selected_players:
                pd = defaultdict(float)
                blks = []
                for i, (bn, bm) in enumerate(blocks, 1):
                    for pos, sp in schedule[bn].items():
                        if sp == p:
                            k = pos[:2] if pos.startswith(("cm","cv")) else pos
                            pd[k] += bm
                            blks.append(str(i))
                g = mins[p]
                r = targets[p]
                diff = g - r
                table.append({
                    "Speler": p,
                    "Trainingen": f"{training_counts[p]}x",
                    "Recht op": f"{int(round(r))} min",
                    "Gekregen": f"{int(round(g))} min",
                    "Verschil": f"{int(round(diff))} min",
                    "Posities": ", ".join(f"{k}:{int(round(v))}" for k,v in pd.items()),
                    "Blokken": ", ".join(blks)
                })

            table.sort(key=lambda x: (-int(x["Trainingen"][0]), -float(x["Gekregen"].split()[0])))
            st.table(table)