import streamlit as st
from collections import defaultdict
import math
active_time = defaultdict(list)

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
    "Pelle": {"favourite":["sp", "rb"], "alternative":["cm", "lb"], "emergency":[]},
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
    "Julius": {"favourite":["cv"], "alternative":[], "emergency":[]},
    "Tobias": {"favourite":["sp"], "alternative":["rb", "lb"], "emergency":[]},
    "Nicky": {"favourite":["ra", "la"], "alternative":[], "emergency":["cv"]},
    "Leon": {"favourite":["cm"], "alternative":[""], "emergency":["lb", "rb"]},
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
max_minutes = {}

availability_flags = defaultdict(lambda: {"first": False, "second": False})

for player in PLAYERS:

    col1, col2, col3, col4 = st.columns([1,2,2,2])

    with col1:
        selected = st.checkbox(player, key=f"sel_{player}")

    if selected:

        with col2:
            first_half_only = st.checkbox("Alleen 1e helft", key=f"fh_{player}")
            second_half_only = st.checkbox("Alleen 2e helft", key=f"sh_{player}")

        availability_flags[player] = {
            "first": first_half_only,
            "second": second_half_only
        }

        with col3:
            trainingen = st.radio(
                f"Trainingen {player}",
                options=[0,1,2],
                horizontal=True,
                key=f"train_{player}"
            )

        with col4:
            priority = st.checkbox("Voorrang", key=f"prio_{player}")
            max_min = st.number_input(
                "Max min",
                min_value=0,
                max_value=90,
                value=90,
                step=5,
                key=f"max_{player}"
            )

        selected_players[player] = PLAYERS[player]
        training_counts[player] = trainingen
        priority_flags[player] = priority
        max_minutes[player] = max_min
        
def allowed_in_block(player, block_name, availability_flags):
    start = int(block_name.split("-")[0])

    fh = availability_flags[player]["first"]
    sh = availability_flags[player]["second"]

    # geen vinkjes → altijd beschikbaar
    if not fh and not sh:
        return True

    # alleen 1e helft
    if fh and start >= 45:
        return False

    # alleen 2e helft
    if sh and start < 45:
        return False

    return True
# =====================================================
# TARGET MINUTEN
# =====================================================
def calculate_target_minutes(players, training_counts, max_minutes):
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
    
        # max cap toepassen
        cap = min(max_minutes.get(p, 90), 90)

        capped = min(candidate, cap)
        
        # NOOIT afronden hier
        final[p] = capped
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
        # blok mag niet door de rust heen
        if start < 45 < end:
            return None # ongeldig patroon
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

    # houdt bij hoeveel minuten iemand al heeft gekregen
    assigned_minutes = defaultdict(int)

    for b_name, b_min in blocks:
        schedule[b_name] = {}
        used = set()

        def assign(idx):
            if idx == len(POSITIONS_ORDER):
                return True

            pos = POSITIONS_ORDER[idx]
            base_pos = pos[:2] if pos.startswith(("cm","cv")) else pos

            cands = []
            for p in players:
            
                if p in used:
                    continue
            
                if not allowed_in_block(p, b_name, availability_flags):
                    continue
            
                rank = position_rank(p, pos)
                if rank == 999:
                    continue
            
                if remaining[p] - b_min < -10:
                    continue
            
                cands.append(p)

            if not cands:
                return False

            def score(p):
                rank = position_rank(p, pos)

                # remaining minuten (hoe hoger tekort, hoe eerder kiezen)
                rem = -remaining[p]

                # prioriteit
                prio = -5 if priority_flags.get(p, False) else 0

                # schaarste (jouw bestaande functie)
                scarcity = -scarcity_bonus(p, pos, players)

                # ranking penalty (favourite / alt / emergency)
                rank_penalty = rank * 500

                # ==============================
                # NIEUW: under-target correctie
                # ==============================
                under_target = max(0, targets[p] - assigned_minutes[p])

                under_target_bonus = -under_target * 2

                return rem + rank_penalty + scarcity + prio + under_target_bonus

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

        # update administratie
        for pos in POSITIONS_ORDER:
            ch = schedule[b_name][pos]
            assigned_minutes[ch] += b_min

            # harde cap check
            if assigned_minutes[ch] > max_minutes.get(ch, 90):
                return None, None
            remaining[ch] -= b_min
            played[ch].append((pos, b_min))

    return schedule, played

# =====================================================
# EVALUATIE
# =====================================================
def evaluate_blocks(players,training_counts,priority_flags,pattern, max_minutes):
    blocks = build_blocks_from_pattern(pattern)
    if blocks is None:
        return float('inf'), None, None, None, None
    targets = calculate_target_minutes(players, training_counts, max_minutes)
    schedule,_ = generate_schedule(players,targets,priority_flags,blocks)
    if schedule is None:
        return float('inf'),None,None,None,None
    mins = defaultdict(float)

    for b_name, b_min in blocks:
        for pos, sp in schedule[b_name].items():
            if sp in players:
    
                # cap check per update
                if mins[sp] + b_min > max_minutes.get(sp, 90):
                    return float('inf'), None, None, None, None
    
                mins[sp] += b_min
    total_dev = sum(abs(mins[p] - targets[p]) for p in players)
    return total_dev,blocks,schedule,targets,mins

# =====================================================
# BESTE BLOKKEN
# =====================================================
def choose_best_blocks(players, training_counts, priority_flags, max_minutes):
    targets = calculate_target_minutes(players, training_counts, max_minutes)
    for pat in generate_block_patterns(True):
        td,bl,sc,tg,mn = evaluate_blocks(players,training_counts,priority_flags,pat, max_minutes)
        if sc is None:
            continue
        devs = [abs(mn[p]-tg[p]) for p in players]
        md = max(devs)
        if md <= 9:
            return bl,sc,tg,mn,True,md,td
    best_score = float('inf')
    best = None,None,None,None
    for pat in generate_block_patterns(False):
        td,bl,sc,tg,mn = evaluate_blocks(players,training_counts,priority_flags,pat, max_minutes)
        if sc is None:
            continue
        devs = [abs(mn[p]-tg[p]) for p in players]
        md = max(devs)
        deviation_cost = sum((max(0,abs(d)-5))**2 for d in devs)
        big_outliers = sum(1 for d in devs if abs(d)>=10)*20000
        score = deviation_cost*200 + big_outliers + md*10000
        if score < best_score:
            best_score = score
            best = bl,sc,tg,mn
            best_md = md
            best_td = td
    if best[0] is not None:
        return *best,False,best_md,best_td
    return None,None,None,None,None,0,0

def compatible(i, o):
    """True als i logisch kan vervangen door o"""
    i_pos = set()
    o_pos = set()

    for p in PLAYERS[i]["favourite"] + PLAYERS[i]["alternative"] + PLAYERS[i]["emergency"]:
        i_pos.add(p)

    for p in PLAYERS[o]["favourite"] + PLAYERS[o]["alternative"] + PLAYERS[o]["emergency"]:
        o_pos.add(p)

    # overlap in mogelijke posities
    return len(i_pos & o_pos) > 0

# =====================================================
# OUTPUT
# =====================================================
if st.button("Genereer opstellingen"):
    if len(selected_players) < 10:
        st.error("Minimaal 10 spelers nodig")
    else:
        res = choose_best_blocks(list(selected_players.keys()),training_counts,priority_flags,max_minutes)
        if res[0] is None:
            st.error("Geen opstelling gevonden.")
        else:
            blocks, schedule, targets, mins, is_strict, max_dev, total_dev = res

            st.subheader("Gebruikte blokken")
            st.write(", ".join(f"{n} ({int(m)} min)" for n, m in blocks))
            
            prev_players = set()
            
            for block_idx, (block_name, block_min) in enumerate(blocks):
            
                # =============================
                # VOORBEREIDING
                # =============================
                current_players = set(
                    speler
                    for pos, speler in schedule[block_name].items()
                    if speler not in ("FOUT", None)
                )
            
                # RAW diff (GEEN limiet hier)
                eruit = sorted(prev_players - current_players)
                erin = sorted(current_players - prev_players)
            
                display_block_name = block_name
            
                # =============================
                # KOLOMMEN (HIER GEBEURT HET)
                # =============================
                col_opstelling, col_wissels = st.columns([1,2])
            
                # =============================
                # LINKS: OPSTELLING
                # =============================
                with col_opstelling:
                    st.subheader(f"Blok {display_block_name} ({int(block_min)} min)")
            
                    pos_map = schedule[block_name]
            
                    display_map = dict(pos_map)
                    mirror_pairs = [("lb", "rb"), ("la", "ra")]
            
                    def base(pos):
                        return pos[:2] if pos.startswith(("cm","cv")) else pos
            
                    for left, right in mirror_pairs:
                        p_left = pos_map.get(left)
                        p_right = pos_map.get(right)
            
                        if not p_left or not p_right:
                            continue
                        if p_left in (None, "FOUT") or p_right in (None, "FOUT"):
                            continue
            
                        fav_left = PLAYERS.get(p_left, {}).get("favourite", [])
                        fav_right = PLAYERS.get(p_right, {}).get("favourite", [])
            
                        if base(right) in fav_left and base(left) in fav_right:
                            display_map[left], display_map[right] = p_right, p_left
            
                    def row(d):
                        cols = st.columns(7)
                        for i,pos in d.items():
                            cols[i].write(display_map.get(pos,"—"))
            
                    row({0:"lb",3:"sp",6:"rb"})
                    row({0:"cm1",3:"cm2",6:"cm3"})
                    row({0:"la",2:"cv1",4:"cv2",6:"ra"})
                
                # =============================
                # RECHTS: WISSELS (NIEUW MODEL)
                # =============================

                with col_wissels:
                    st.subheader("Wissels")
                
                    if block_idx == 0:
                        st.markdown("_Eerste blok – iedereen erin_")
                        prev_players = current_players.copy()
                        continue
                
                    pos_map = schedule[block_name]
                
                    # speler -> positie
                    player_pos = {}
                    for pos, sp in pos_map.items():
                        player_pos[sp] = pos[:2]
                
                    eruit = list(prev_players - current_players)
                    erin = list(current_players - prev_players)
                
                    # positie-match functie
                    def pos_score(i, o):
                        if player_pos.get(i) == player_pos.get(o):
                            return 0
                        if player_pos.get(i) in PLAYERS[o]["favourite"]:
                            return 1
                        if player_pos.get(i) in PLAYERS[o]["alternative"]:
                            return 2
                        return 3
                
                    pairs = []
                    used_o = set()
                
                    for i in erin:
                        best = None
                
                        for o in eruit:
                            if o in used_o:
                                continue
                
                            score = pos_score(i, o) + abs(mins[i] - mins[o]) * 0.01
                
                            if best is None or score < best[0]:
                                best = (score, i, o)
                
                        if best:
                            _, i_best, o_best = best
                            pairs.append((i_best, o_best))
                            used_o.add(o_best)
                
                    # fallback: alles wat overblijft koppelen
                    remaining_i = [p for p in erin if p not in [x for x,_ in pairs]]
                    remaining_o = [p for p in eruit if p not in [y for _,y in pairs]]
                
                    for i, o in zip(remaining_i, remaining_o):
                        pairs.append((i, o))
                
                    if not pairs:
                        st.markdown("_Geen logische wissels mogelijk_")
                    else:
                        base_minute = int(block_name.split("-")[0])
                        base_minute = 5 * round(base_minute / 5)
                        time_slots = [base_minute, base_minute + 5]
                
                        moment_plan = {m: [] for m in time_slots}
                
                        MAX_PER_MOMENT = 2

                        moment_plan = {m: [] for m in time_slots}
                        
                        i = 0
                        for pair in pairs:
                            placed = False
                        
                            for m in time_slots:
                                if len(moment_plan[m]) < MAX_PER_MOMENT:
                                    moment_plan[m].append(pair)
                                    placed = True
                                    break
                        
                            # als alles vol zit: stop
                            if not placed:
                                break
                
                        for m in time_slots:
                            if moment_plan[m]:
                                st.markdown(f"**Minuut {m}**")
                                for i, o in moment_plan[m]:
                                    st.markdown(f"{i} → {o}")
                
                    prev_players = current_players.copy()
                
            st.header("Minutenoverzicht")
            table = []
            
            for p in selected_players:
            
                active_time = []
                pd = defaultdict(float)
                blks = []
            
                for bn, bm in blocks:
            
                    block_start = int(bn.split("-")[0])
                    block_end = int(bn.split("-")[1])
            
                    pos_map = schedule[bn]
            
                    # start-opstelling
                    current_players = set(pos_map.values())
            
                    # events (wissels binnen dit blok)
                    events = []
                    if "moment_plan" in locals() and bn in moment_plan:
                        for m in sorted(moment_plan[bn].keys()) if isinstance(moment_plan[bn], dict) else []:
                            for i, o in moment_plan[bn].get(m, []):
                                events.append((m, i, o))
            
                    events.sort()
            
                    t = block_start
            
                    for m, i, o in events:
            
                        # minuten voor iedereen die speelt in segment
                        for sp in current_players:
                            active_time.append((sp, t, m))
            
                        # wissel uitvoeren
                        if o in current_players:
                            current_players.remove(o)
                        current_players.add(i)
            
                        t = m
            
                    # laatste segment
                    for sp in current_players:
                        active_time.append((sp, t, block_end))
            
                    # position tracking per blok (op basis van startopstelling)
                    for pos, sp in pos_map.items():
                        if sp == p:
                            base = pos[:2] if pos.startswith(("cm", "cv")) else pos
                            pd[base] += bm
                            blks.append(f"{int(block_start)}-{int(block_end)}")
            
                # totaal minuten optellen uit tijdlijn
                total = sum(end - start for sp, start, end in active_time if sp == p)
            
                g = total
                r = targets[p]
                diff = g - r
            
                table.append({
                    "Speler": p,
                    "Trainingen": f"{training_counts[p]}x",
                    "Recht op": f"{int(round(r))} min",
                    "Gekregen": f"{int(round(g))} min",
                    "Verschil": f"{int(round(diff))} min",
                    "Posities": ", ".join(f"{k}:{int(v)}" for k, v in pd.items()),
                })
            
            table.sort(key=lambda x: (-int(x["Trainingen"][0]), -float(x["Gekregen"].split()[0])))
            st.table(table)
            # =====================================================
            # POSITIE-OVERZICHT (Slots/Totaal: slots / aantal geselecteerde spelers die die basispositie kunnen spelen)
            # =====================================================
            base_positions = ["sp", "cv", "cm", "lb", "rb", "la", "ra"]
            slots_per_base = {bp: sum(1 for p in POSITIONS_ORDER if (p[:2] if p.startswith(("cm","cv")) else p) == bp) for bp in base_positions}
            selected_list = list(selected_players.keys())
            players_order = list(PLAYERS.keys())
            def ordered_names_from_list(name_list):
                return ", ".join([p for p in players_order if p in name_list]) if name_list else "—"
            pos_table = []
            for bp in base_positions:
                slots = slots_per_base[bp]
                total_pool = [p for p in selected_list if (bp in PLAYERS.get(p, {}).get("favourite", [])
                                                        or bp in PLAYERS.get(p, {}).get("alternative", [])
                                                        or bp in PLAYERS.get(p, {}).get("emergency", []))]
                total_count = len(total_pool)
                slots_total = f"{slots}/{total_count}"
                fav_list = [p for p in selected_list if bp in PLAYERS.get(p, {}).get("favourite", [])]
                alt_list = [p for p in selected_list if bp in PLAYERS.get(p, {}).get("alternative", [])]
                emg_list = [p for p in selected_list if bp in PLAYERS.get(p, {}).get("emergency", [])]
                pos_table.append({
                    "Positie": bp,
                    "Slots/Totaal": slots_total,
                    "Favourite (namen)": ordered_names_from_list(fav_list),
                    "Alternative (namen)": ordered_names_from_list(alt_list),
                    "Emergency (namen)": ordered_names_from_list(emg_list),
                })
            pos_table.sort(key=lambda x: (-int(x["Slots/Totaal"].split("/")[0]), -int(x["Slots/Totaal"].split("/")[1]) if x["Slots/Totaal"].split("/")[1].isdigit() else 0))
            st.subheader("Positie overzicht — slots/totaal en voorkeuren (namen in PLAYERS volgorde)")
            st.table(pos_table)
