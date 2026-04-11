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
# WISSELSPREIDING (aangepast met jouw verzoek)
# =====================================================
def merge_steps_same_minute(steps):
    """Combineer meerdere stappen met dezelfde minuut in één stap."""
    merged = {}
    for minute, pairs in steps:
        if minute not in merged:
            merged[minute] = []
        merged[minute].extend(pairs)
    return sorted([(m, merged[m]) for m in sorted(merged.keys())], key=lambda x: x[0])

def spread_substitutions(block_start, block_size, players_in, players_out):
    """
    Return: (steps, adjusted_block_start)
    - steps: list of (minute, [(in,out),...]) met geen duplicate minuten (samengevoegd).
    - adjusted_block_start: None of nieuwe start minuut (int) wanneer we willen tonen als bijv. 45-...
    """
    subs = list(zip(players_in, players_out))
    n = len(subs)

    # === JOUW NIEUWE WENS ===
    # Max 4 mensen per blok
    if n > 4:
        subs = subs[:4]
        n = 4

    # Max 2 wissels per keer
    max_per_step = 2

    # standaard afronden op veelvoud van 5
    minute = 5 * round(block_start / 5)

    # voorkom wissel precies op minuut 40: verplaats naar 45 (vast)
    adjusted_block_start = None
    if minute == 40:
        minute = 45
        adjusted_block_start = 45

    # klein blok of weinig wissels: alles in één moment
    if block_size < 15 or n <= max_per_step:
        steps = [(minute, subs)]
        return merge_steps_same_minute(steps), adjusted_block_start

    # anders spreiden in stappen van maximaal 2 wissels per moment
    steps = []
    i = 0
    step_offset = 0
    while i < n:
        step_in = subs[i:i+max_per_step]
        step_minute = 5 * round((block_start + 5 * step_offset) / 5)
        # voorkom dat een stap precies op 40 valt: verplaats naar 45
        if step_minute == 40:
            step_minute = 45
            if step_offset == 0:
                adjusted_block_start = 45
        steps.append((step_minute, step_in))
        i += max_per_step
        step_offset += 1

    return merge_steps_same_minute(steps), adjusted_block_start

# =====================================================
# EVALUATIE
# =====================================================
def evaluate_blocks(players,training_counts,priority_flags,pattern):
    blocks = build_blocks_from_pattern(pattern)
    if blocks is None:
        return float('inf'), None, None, None, None
    targets = calculate_target_minutes(players,training_counts)
    schedule,_ = generate_schedule(players,targets,priority_flags,blocks)
    if schedule is None:
        return float('inf'),None,None,None,None
    mins = defaultdict(float)
    for b_name,b_min in blocks:
        for pos,sp in schedule[b_name].items():
            if sp in players:
                mins[sp] += b_min
    total_dev = sum(abs(mins[p] - targets[p]) for p in players)
    return total_dev,blocks,schedule,targets,mins

# =====================================================
# BESTE BLOKKEN
# =====================================================
def choose_best_blocks(players,training_counts,priority_flags):
    targets = calculate_target_minutes(players,training_counts)
    for pat in generate_block_patterns(True):
        td,bl,sc,tg,mn = evaluate_blocks(players,training_counts,priority_flags,pat)
        if sc is None:
            continue
        devs = [abs(mn[p]-tg[p]) for p in players]
        md = max(devs)
        if md <= 9:
            return bl,sc,tg,mn,True,md,td
    best_score = float('inf')
    best = None,None,None,None
    for pat in generate_block_patterns(False):
        td,bl,sc,tg,mn = evaluate_blocks(players,training_counts,priority_flags,pat)
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
            st.subheader("Gebruikte blokken")
            st.write(", ".join(f"{n} ({int(m)} min)" for n,m in blocks))
            prev_players = set()
            for block_idx,(block_name,block_min) in enumerate(blocks):
                # bepaal huidige spelers voor dit blok
                current_players = set()
                for pos,speler in schedule[block_name].items():
                    if speler not in ("FOUT",None):
                        current_players.add(speler)
                # bepaal wissels (erin/eruit) vroeg zodat we adjusted_block_name kunnen bepalen
                eruit = sorted(prev_players - current_players)
                erin = sorted(current_players - prev_players)
                # vraag spread_substitutions alleen als er wissels zijn en dit niet het eerste blok
                adjusted_start = None
                steps = []
                if block_idx > 0 and (erin or eruit):
                    steps, adjusted_start = spread_substitutions(int(block_name.split("-")[0]), block_min, erin, eruit)
                # pas display block name aan als adjusted_start is gezet
                display_block_name = block_name
                if adjusted_start is not None:
                    end_min = int(block_name.split("-")[1])
                    display_block_name = f"{adjusted_start}-{end_min}"
                st.subheader(f"Blok {display_block_name} ({int(block_min)} min)")
                pos_map = schedule[block_name]
                # --- display-only swap logic: swap LB/RB en LA/RA alleen voor weergave
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
                    # swap for display only when both players explicitly prefer the other's side
                    if base(right) in fav_left and base(left) in fav_right:
                        display_map[left], display_map[right] = p_right, p_left
                def row(d):
                    cols = st.columns(20)
                    for i,pos in d.items():
                        cols[i].write(display_map.get(pos,"—"))
                row({0:"lb",3:"sp",6:"rb"})
                row({0:"cm1",3:"cm2",6:"cm3"})
                row({0:"la",2:"cv1",4:"cv2",6:"ra"})
                # Wissels tonen (gebruik samengevoegde stappen en geen dubbele Minuut 45)
                if block_idx > 0:
                    st.markdown("**Wissels dit blok:**")
                    if not (erin or eruit):
                        st.markdown("_Geen wissels dit blok_")
                    else:
                        # als we nog geen steps berekend (geen erin/eruit), bereken nu (fallback)
                        if not steps:
                            steps, _ = spread_substitutions(int(block_name.split("-")[0]), block_min, erin, eruit)
                        for minute, pairs in steps:
                            st.markdown(f"*Minuut {minute}*")
                            for sp_in, sp_out in pairs:
                                st.markdown(f"{sp_in} erin --> {sp_out} eruit")
                else:
                    st.markdown("_Eerste blok – iedereen erin_")
                prev_players = current_players.copy()
            st.header("Minutenoverzicht")
            table = []
            for p in selected_players:
                pd = defaultdict(float)
                blks = []
                for i,(bn,bm) in enumerate(blocks,1):
                    for pos,sp in schedule[bn].items():
                        if sp == p:
                            k = pos[:2] if pos.startswith(("cm","cv")) else pos
                            pd[k] += bm
                            blks.append(str(i))
                g = mins[p]
                r = targets[p]
                diff = g - r
                table.append({
                    "Speler":p,
                    "Trainingen":f"{training_counts[p]}x",
                    "Recht op":f"{int(round(r))} min",
                    "Gekregen":f"{int(round(g))} min",
                    "Verschil":f"{int(round(diff))} min",
                    "Posities":", ".join(f"{k}:{int(round(v))}" for k,v in pd.items()),
                    "Blokken":", ".join(blks)
                })
            table.sort(key=lambda x:(-int(x["Trainingen"][0]),-float(x["Gekregen"].split()[0])))
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
