import streamlit as st
from collections import defaultdict
from itertools import product
import math
active_time = defaultdict(list)
failure_log = defaultdict(list)

st.set_page_config(layout="wide")

# =====================================================
# SPELERSDATABASE
# =====================================================
PLAYERS = {
    "Jannick": {"favourite":["ra"], "alternative":["rb", "lb"], "emergency":["la"]},
    "Collin": {"favourite":["lb"], "alternative":["rb"], "emergency":["sp"]},
    "Wout": {"favourite":["rb"], "alternative":["lb"], "emergency":["sp"]},
    "Jaimy": {"favourite":["sp"], "alternative":["lb","rb"], "emergency":[]},
    "Sjoerd": {"favourite":["cm"], "alternative":["sp"], "emergency":[]},
    "Pelle": {"favourite":["sp", "rb"], "alternative":["cm", "lb"], "emergency":[]},
    "Tim": {"favourite":["cm"], "alternative":["sp"], "emergency":[]},
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
    "Julius": {"favourite":["cv"], "alternative":["ra", "la"], "emergency":[]},
    "Tobias": {"favourite":["sp"], "alternative":["rb", "lb"], "emergency":[]},
    "Nicky": {"favourite":["ra", "la"], "alternative":[], "emergency":["cv"]},
    "Leon": {"favourite":["cm"], "alternative":[""], "emergency":["lb", "rb"]},
    "Cas": {"favourite":["sp", "lb", "rb"], "alternative":["cm"], "emergency":[]},
    "Teun": {"favourite":["sp"], "alternative":["lb", "rb"], "emergency":["cm"]},
    "Lukas": {"favourite":["cv"], "alternative":[], "emergency":["la", "ra"]},
    "Abel": {"favourite":["lb", "rb"], "alternative":[], "emergency":[]},
    "Niels": {"favourite":["ra", "la"], "alternative":["cm"], "emergency":[]},
}

def compute_dynamic_position_order(players):
    base_positions = ["sp", "cv", "cm", "lb", "rb", "la", "ra"]

    def count_pool(bp):
        fav   = sum(bp in PLAYERS[p]["favourite"]    for p in players)
        alt   = sum(bp in PLAYERS[p]["alternative"]  for p in players)
        emg   = sum(bp in PLAYERS[p]["emergency"]    for p in players)
        total = fav + alt + emg
        return total, fav, alt, emg

    sorted_bases = sorted(base_positions, key=lambda bp: count_pool(bp))

    expanded = []
    for bp in sorted_bases:
        if bp == "cm":
            expanded += ["cm1", "cm2", "cm3"]
        elif bp == "cv":
            expanded += ["cv1", "cv2"]
        else:
            expanded.append(bp)

    return expanded

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
training_counts  = {}
priority_flags   = {}
max_minutes      = {}

availability_flags = defaultdict(lambda: {"first": False, "second": False})

for player in PLAYERS:
    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        selected = st.checkbox(player, key=f"sel_{player}")

    if selected:
        with col2:
            trainingen = st.radio(
                f"Trainingen {player}",
                options=[0, 1, 2],
                format_func=lambda x: f"{x} trainingen",
                horizontal=True,
                key=f"train_{player}"
            )

        with col3:
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                priority = st.checkbox("Voorang", key=f"prio_{player}")
            with c2:
                first_half_only  = st.checkbox("1ste Helft", key=f"fh_{player}")
            with c3:
                second_half_only = st.checkbox("2de Helft",  key=f"sh_{player}")
            with c4:
                max_min = st.number_input(
                    "Max minuten",
                    min_value=0, max_value=90, value=90, step=5,
                    key=f"max_{player}"
                )

        selected_players[player]       = PLAYERS[player]
        training_counts[player]        = trainingen
        priority_flags[player]         = priority
        max_minutes[player]            = max_min
        availability_flags[player]     = {"first": first_half_only, "second": second_half_only}


def allowed_in_block(player, block_name, availability_flags):
    start = int(block_name.split("-")[0])
    fh    = availability_flags[player]["first"]
    sh    = availability_flags[player]["second"]
    if not fh and not sh:
        return True
    if fh and start >= 45:
        return False
    if sh and start < 45:
        return False
    return True

# =====================================================
# TARGET MINUTEN
# =====================================================
def calculate_target_minutes(players, training_counts, max_minutes):
    n    = len(players)
    base = TOTAL_FIELD_MINUTES / n
    raw  = {}
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
    redistribute = total_removed / n if n > 0 else 0
    final = {}
    for p in players:
        candidate = raw[p] + redistribute
        cap       = min(max_minutes.get(p, 90), 90)
        final[p]  = min(candidate, cap)
    return final

# =====================================================
# POSITIE RANKING
# =====================================================
def position_rank(player, pos):
    base_pos = pos[:2] if pos.startswith(("cm", "cv")) else pos
    if base_pos in PLAYERS[player]["favourite"]:   return 1
    if base_pos in PLAYERS[player]["alternative"]: return 2
    if base_pos in PLAYERS[player]["emergency"]:   return 3
    return 999

# =====================================================
# SCHAARSTE BONUS
# =====================================================
def scarcity_bonus(player, pos, players):
    base_pos    = pos[:2] if pos.startswith(("cm", "cv")) else pos
    fav_players = [p for p in players if base_pos in PLAYERS[p]["favourite"]]
    if len(fav_players) <= 2 and base_pos in PLAYERS[player]["favourite"]:
        return 10
    return 0

# =====================================================
# POSITIE SWAP OPTIMALISATIE
# =====================================================
def optimize_position_swaps(block_assignment):
    """Wissel spelers onderling van positie als dat hun voorkeur verbetert."""
    improved = True
    while improved:
        improved  = False
        positions = list(block_assignment.keys())
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                pos_a    = positions[i]
                pos_b    = positions[j]
                player_a = block_assignment[pos_a]
                player_b = block_assignment[pos_b]

                huidige_score = position_rank(player_a, pos_a) + position_rank(player_b, pos_b)
                swap_score    = position_rank(player_a, pos_b) + position_rank(player_b, pos_a)

                if swap_score < huidige_score:
                    if position_rank(player_a, pos_b) != 999 and position_rank(player_b, pos_a) != 999:
                        block_assignment[pos_a] = player_b
                        block_assignment[pos_b] = player_a
                        improved = True
    return block_assignment

# =====================================================
# BLOKGENERATOR
# =====================================================
def generate_block_patterns(strict=True):
    results  = []
    max_10   = 2 if strict else 3
    max_15   = 2 if strict else 3

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
            if size == 10 and used_10 >= max_10: continue
            if size == 15 and used_15 >= max_15: continue
            current.append(size)
            backtrack(remaining - size, i, used_10 + (size == 10), used_15 + (size == 15), current)
            current.pop()

    backtrack(90, 0, 0, 0, [])
    results.sort(key=lambda p: (len(p), [-x for x in p]))
    return results

def build_blocks_from_pattern(pattern):
    blocks = []
    start  = 0
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
    remaining        = targets.copy()
    schedule         = {}
    played           = defaultdict(list)
    assigned_minutes = defaultdict(int)

    for b_name, b_min in blocks:
        schedule[b_name] = {}
        used = set()

        def assign(idx):
            if idx == len(POSITIONS_ORDER):
                return True

            pos      = POSITIONS_ORDER[idx]
            base_pos = pos[:2] if pos.startswith(("cm", "cv")) else pos

            cands = []
            for p in players:
                if p in used:                                       continue
                if not allowed_in_block(p, b_name, availability_flags): continue
                if position_rank(p, pos) == 999:                   continue
                if remaining[p] - b_min < -5:                      continue
                cands.append(p)

            if not cands:
                failure_log["short"].append(f"{b_name} - {pos}: geen kandidaten")
                return False

            def score(p):
                rank         = position_rank(p, pos)
                over_target  = assigned_minutes[p] - targets[p]
                under_target = max(0, targets[p] - assigned_minutes[p])
                return (
                    over_target  * 15
                    - under_target * 10
                    + (rank - 1)   * 40
                    - scarcity_bonus(p, pos, players)
                    + (-8 if priority_flags.get(p, False) else 0)
                )

            cands.sort(key=score)

            for ch in cands:
                schedule[b_name][pos] = ch
                used.add(ch)
                if assign(idx + 1):
                    return True
                used.remove(ch)
                del schedule[b_name][pos]

            return False

        if not assign(0):
            return None, None

        # Optimaliseer posities binnen dit blok
        schedule[b_name] = optimize_position_swaps(schedule[b_name])

        for pos in POSITIONS_ORDER:
            ch = schedule[b_name][pos]
            assigned_minutes[ch] += b_min
            if assigned_minutes[ch] > max_minutes.get(ch, 90):
                failure_log["short"].append(f"{ch} overschrijdt max minuten in blok {b_name}")
                return None, None
            remaining[ch] -= b_min
            played[ch].append((pos, b_min))

    return schedule, played

# =====================================================
# EVALUATIE
# =====================================================
def evaluate_blocks(players, training_counts, priority_flags, pattern, max_minutes):
    blocks = build_blocks_from_pattern(pattern)
    if blocks is None:
        return float('inf'), None, None, None, None
    targets  = calculate_target_minutes(players, training_counts, max_minutes)
    schedule, _ = generate_schedule(players, targets, priority_flags, blocks)
    if schedule is None:
        return float('inf'), None, None, None, None
    mins = defaultdict(float)
    for b_name, b_min in blocks:
        for pos, sp in schedule[b_name].items():
            if sp in players:
                if mins[sp] + b_min > max_minutes.get(sp, 90):
                    return float('inf'), None, None, None, None
                mins[sp] += b_min
    total_dev = sum(abs(mins[p] - targets[p]) for p in players)
    return total_dev, blocks, schedule, targets, mins

# =====================================================
# BESTE BLOKKEN
# =====================================================
def choose_best_blocks(players, training_counts, priority_flags, max_minutes):
    for pat in generate_block_patterns(True):
        td, bl, sc, tg, mn = evaluate_blocks(players, training_counts, priority_flags, pat, max_minutes)
        if sc is None: continue
        devs = [abs(mn[p] - tg[p]) for p in players]
        if max(devs) <= 9:
            return bl, sc, tg, mn, True, max(devs), td

    best_score = float('inf')
    best       = None, None, None, None
    best_md    = 0
    best_td    = 0

    for pat in generate_block_patterns(False):
        td, bl, sc, tg, mn = evaluate_blocks(players, training_counts, priority_flags, pat, max_minutes)
        if sc is None: continue
        devs           = [abs(mn[p] - tg[p]) for p in players]
        md             = max(devs)
        deviation_cost = sum((max(0, abs(d) - 5)) ** 2 for d in devs)
        big_outliers   = sum(1 for d in devs if abs(d) >= 10) * 20000
        score          = deviation_cost * 200 + big_outliers + md * 10000
        if score < best_score:
            best_score = score
            best       = bl, sc, tg, mn
            best_md    = md
            best_td    = td

    if best[0] is not None:
        return *best, False, best_md, best_td
    return None, None, None, None, None, 0, 0

# =====================================================
# OUTPUT
# =====================================================
if st.button("Genereer opstellingen"):
    failure_log.clear()
    if len(selected_players) < 10:
        st.error("Minimaal 10 spelers nodig")
    else:
        POSITIONS_ORDER = compute_dynamic_position_order(selected_players.keys())
        res = choose_best_blocks(list(selected_players.keys()), training_counts, priority_flags, max_minutes)

        if res[0] is None:
            st.error("Geen opstelling gevonden.")
            if failure_log["short"]:
                st.subheader("Waarom niet gelukt:")
                from collections import Counter
                counts = Counter(failure_log["short"])
                for msg, count in counts.items():
                    st.write(f"- {msg}" + (f" (x{count})" if count > 1 else ""))
        else:
            blocks, schedule, targets, mins, is_strict, max_dev, total_dev = res

            st.subheader("Gebruikte blokken")
            st.write(", ".join(f"{n} ({int(m)} min)" for n, m in blocks))

            prev_players       = set()
            all_moment_plans   = {}   # moment_plan per blok, voor minutenoverzicht
            actual_mins_so_far = defaultdict(int)  # echte minuten per speler t/m vorig blok

            for block_idx, (block_name, block_min) in enumerate(blocks):

                current_players = set(
                    sp for pos, sp in schedule[block_name].items()
                    if sp not in ("FOUT", None)
                )

                col_opstelling, col_wissels = st.columns([1, 2])

                # ---- OPSTELLING ----
                with col_opstelling:
                    st.subheader(f"Blok {block_name} ({int(block_min)} min)")

                    pos_map     = schedule[block_name]
                    display_map = dict(pos_map)

                    def base(pos):
                        return pos[:2] if pos.startswith(("cm", "cv")) else pos

                    for left, right in [("lb", "rb"), ("la", "ra")]:
                        p_left  = pos_map.get(left)
                        p_right = pos_map.get(right)
                        if not p_left or not p_right:          continue
                        if p_left  in (None, "FOUT"):          continue
                        if p_right in (None, "FOUT"):          continue
                        fav_left  = PLAYERS.get(p_left,  {}).get("favourite", [])
                        fav_right = PLAYERS.get(p_right, {}).get("favourite", [])
                        if base(right) in fav_left and base(left) in fav_right:
                            display_map[left], display_map[right] = p_right, p_left

                    def row(d):
                        cols = st.columns(7)
                        for i, pos in d.items():
                            cols[i].write(display_map.get(pos, "—"))

                    row({0: "lb", 3: "sp", 6: "rb"})
                    row({0: "cm1", 3: "cm2", 6: "cm3"})
                    row({0: "la", 2: "cv1", 4: "cv2", 6: "ra"})

                # ---- WISSELS ----
                with col_wissels:
                    st.subheader("Wissels")

                    if block_idx == 0:
                        st.markdown("_Eerste blok – iedereen erin_")
                        prev_players = current_players.copy()
                        all_moment_plans[block_name] = {}
                        # Eerste blok: iedereen speelt de volle bloktijd
                        for sp in current_players:
                            actual_mins_so_far[sp] += block_min
                        continue

                    pos_map    = schedule[block_name]
                    player_pos = {sp: pos[:2] for pos, sp in pos_map.items()}

                    eruit = list(prev_players - current_players)
                    erin  = list(current_players - prev_players)

                    def pos_score(i, o):
                        if player_pos.get(i) == player_pos.get(o):          return 0
                        if player_pos.get(i) in PLAYERS[o]["favourite"]:     return 1
                        if player_pos.get(i) in PLAYERS[o]["alternative"]:   return 2
                        return 3

                    pairs  = []
                    used_o = set()

                    for i in erin:
                        best = None
                        for o in eruit:
                            if o in used_o: continue
                            sc = pos_score(i, o) + abs(mins[i] - mins[o]) * 0.01
                            if best is None or sc < best[0]:
                                best = (sc, i, o)
                        if best:
                            _, i_best, o_best = best
                            pairs.append((i_best, o_best))
                            used_o.add(o_best)

                    remaining_i = [p for p in erin  if p not in [x for x, _ in pairs]]
                    remaining_o = [p for p in eruit if p not in [y for _, y in pairs]]
                    for i, o in zip(remaining_i, remaining_o):
                        pairs.append((i, o))

                    if not pairs:
                        st.markdown("_Geen logische wissels mogelijk_")
                        all_moment_plans[block_name] = {}
                        for sp in current_players:
                            actual_mins_so_far[sp] += block_min
                    else:
                        base_minute = 5 * round(int(block_name.split("-")[0]) / 5)

                        if base_minute == 45:
                            # Rust: alle wissels tegelijk toegestaan
                            time_slots     = [45]
                            MAX_PER_MOMENT = len(pairs)
                        else:
                            time_slots     = [base_minute, base_minute + 5]
                            MAX_PER_MOMENT = 2

                        # Sorteer op urgentie met echte minuten:
                        # invaller met grootste tekort → eerst het veld op
                        # uitvaller met grootste overschot → eerst eraf
                        pairs_sorted = sorted(
                            pairs,
                            key=lambda pair: (
                                (targets[pair[0]] - actual_mins_so_far[pair[0]])    # invaller tekort
                                + (actual_mins_so_far[pair[1]] - targets[pair[1]]) # uitvaller overschot
                            ),
                            reverse=True  # hoogste urgentie eerst
                        )

                        # --- NIEUW: twee varianten proberen (vroeg->laat en laat->vroeg) ---
                        best_score   = math.inf
                        best_plan    = None
                        best_minutes = None
                        
                        block_start = int(block_name.split("-")[0])
                        block_end   = int(block_name.split("-")[1])
                        
                        for choices in product(time_slots, repeat=len(pairs_sorted)):
                            # bouw plan: welke wissel op welke minuut
                            plan = {m: [] for m in time_slots}
                            valid = True
                            for (inv, out), m in zip(pairs_sorted, choices):
                                if len(plan[m]) >= MAX_PER_MOMENT:
                                    valid = False
                                    break
                                plan[m].append((inv, out))
                            if not valid:
                                continue
                        
                            # minuten simuleren zonder echte data te overschrijven
                            temp_minutes = actual_mins_so_far.copy()
                            current_set  = set(schedule[block_name].values())
                            t = block_start
                        
                            for m in sorted(plan.keys()):
                                elapsed = m - t
                                for sp in current_set:
                                    temp_minutes[sp] += elapsed
                                for i, o in plan[m]:
                                    if o in current_set:
                                        current_set.remove(o)
                                    current_set.add(i)
                                t = m
                        
                            for sp in current_set:
                                temp_minutes[sp] += block_end - t
                        
                            # totale afwijking berekenen
                            score = sum(abs(temp_minutes[p] - targets[p]) for p in selected_players.keys())
                        
                            if score < best_score:
                                best_score   = score
                                best_plan    = plan
                                best_minutes = temp_minutes
                        
                        # beste plan kiezen
                        moment_plan        = best_plan
                        actual_mins_so_far = best_minutes



                        for m in time_slots:
                            if moment_plan[m]:
                                st.markdown(f"**Minuut {m}**")
                                for i, o in moment_plan[m]:
                                    st.markdown(f"{i} → {o}")

                        all_moment_plans[block_name] = moment_plan

                        # Update actual_mins_so_far op basis van echte wissel-momenten
                        block_start  = int(block_name.split("-")[0])
                        block_end    = int(block_name.split("-")[1])
                        current_set  = set(schedule[block_name].values())
                        t            = block_start

                        for m in sorted(moment_plan.keys()):
                            elapsed = m - t
                            for sp in current_set:
                                actual_mins_so_far[sp] += elapsed
                            for i, o in moment_plan[m]:
                                current_set.discard(o)
                                current_set.add(i)
                            t = m

                        for sp in current_set:
                            actual_mins_so_far[sp] += block_end - t

                    prev_players = current_players.copy()

            # =====================================================
            # MINUTENOVERZICHT
            # =====================================================
            st.header("Minutenoverzicht")
            table = []

            for p in selected_players:
                active_time_list = []
                pd   = defaultdict(float)

                for bn, bm in blocks:
                    block_start         = int(bn.split("-")[0])
                    block_end           = int(bn.split("-")[1])
                    pos_map             = schedule[bn]
                    current_players_set = set(pos_map.values())

                    events = []
                    for m, pairs in all_moment_plans.get(bn, {}).items():
                        for i, o in pairs:
                            events.append((m, i, o))
                    events.sort()

                    t = block_start
                    for m, i, o in events:
                        for sp in current_players_set:
                            active_time_list.append((sp, t, m))
                        if o in current_players_set:
                            current_players_set.remove(o)
                        current_players_set.add(i)
                        t = m
                    for sp in current_players_set:
                        active_time_list.append((sp, t, block_end))

                    for pos, sp in pos_map.items():
                        if sp == p:
                            base_p = pos[:2] if pos.startswith(("cm", "cv")) else pos
                            pd[base_p] += bm

                total = sum(end - start for sp, start, end in active_time_list if sp == p)
                r     = targets[p]
                diff  = total - r

                table.append({
                    "Speler":     p,
                    "Trainingen": f"{training_counts[p]}x",
                    "Recht op":   f"{int(round(r))} min",
                    "Gekregen":   f"{int(round(total))} min",
                    "Verschil":   f"{int(round(diff))} min",
                    "Posities":   ", ".join(f"{k}:{int(v)}" for k, v in pd.items()),
                })

            table.sort(key=lambda x: (-int(x["Trainingen"][0]), -float(x["Gekregen"].split()[0])))
            st.table(table)

            # =====================================================
            # POSITIE-OVERZICHT
            # =====================================================
            base_positions = ["sp", "cv", "cm", "lb", "rb", "la", "ra"]
            slots_per_base = {
                bp: sum(1 for p in POSITIONS_ORDER if (p[:2] if p.startswith(("cm", "cv")) else p) == bp)
                for bp in base_positions
            }
            selected_list = list(selected_players.keys())
            players_order = list(PLAYERS.keys())

            def ordered_names_from_list(name_list):
                return ", ".join([p for p in players_order if p in name_list]) if name_list else "—"

            pos_table = []
            for bp in base_positions:
                slots       = slots_per_base[bp]
                total_pool  = [p for p in selected_list if (
                    bp in PLAYERS.get(p, {}).get("favourite",   []) or
                    bp in PLAYERS.get(p, {}).get("alternative", []) or
                    bp in PLAYERS.get(p, {}).get("emergency",   [])
                )]
                slots_total = f"{slots}/{len(total_pool)}"
                pos_table.append({
                    "Positie":             bp,
                    "Slots/Totaal":        slots_total,
                    "Favourite (namen)":   ordered_names_from_list([p for p in selected_list if bp in PLAYERS.get(p, {}).get("favourite",   [])]),
                    "Alternative (namen)": ordered_names_from_list([p for p in selected_list if bp in PLAYERS.get(p, {}).get("alternative", [])]),
                    "Emergency (namen)":   ordered_names_from_list([p for p in selected_list if bp in PLAYERS.get(p, {}).get("emergency",   [])]),
                })
            pos_table.sort(key=lambda x: (
                -int(x["Slots/Totaal"].split("/")[0]),
                -int(x["Slots/Totaal"].split("/")[1]) if x["Slots/Totaal"].split("/")[1].isdigit() else 0
            ))
            st.subheader("Positie overzicht — slots/totaal en voorkeuren (namen in PLAYERS volgorde)")
            st.table(pos_table)
