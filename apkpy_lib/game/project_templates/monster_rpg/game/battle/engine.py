"""A battle as rules only: choices go in, lines of what happened come out (BATTLE.lines), for the presenter to
show. It draws nothing and can be played without a screen (see tests/ and tools/advanced/bot).
"""
import random

from game.data.defs import EFFECTS, ITEMS, MOVES, SPECIES, STATUSES, TRAINERS, fill, game_info, named, rules, word
from game.rules.combat import CAPTURE_CHECKS, best_move, capture_shakes, effectiveness, hit_damage, random_move, stage_factor
from game.rules.items import apply
from game.rules.monsters import add_ev, become, display_name, evolves_now, exp_for_level, exp_progress, learn, look, make_monster, max_hp, stat, wild_variant
from game.state.store import BATTLE, SESSION, BattleLine, Monster, add_item


def line(kind: str, text: str, foe: bool, value: int, name: str) -> None:
    BATTLE.lines.append(BattleLine(kind, text, foe, value, name))


def say(text: str) -> None:
    line("say", text, False, 0, "")


def ally() -> Monster:
    return SESSION.save.team[BATTLE.ally_at]


def foe() -> Monster:
    return BATTLE.foes[BATTLE.foe_at]


def first_able() -> int:
    i = 0
    for m in SESSION.save.team:
        if m.hp > 0:
            return i
        i += 1
    return -1


def reset_run() -> None:
    BATTLE.foes.clear()
    BATTLE.lines.clear()
    BATTLE.foe_at = 0
    BATTLE.ally_at = max(0, first_able())
    reset_stages(False)
    reset_stages(True)
    BATTLE.won = False
    BATTLE.over = False
    BATTLE.must_switch = False
    BATTLE.flee_tries = 0


def reset_stages(is_foe: bool) -> None:
    if is_foe:
        BATTLE.foe_attack = 0
        BATTLE.foe_defense = 0
        BATTLE.foe_special = 0
        BATTLE.foe_speed = 0
    else:
        BATTLE.ally_attack = 0
        BATTLE.ally_defense = 0
        BATTLE.ally_special = 0
        BATTLE.ally_speed = 0


def stage_of(is_foe: bool, stat_name: str) -> int:
    if stat_name == "attack":
        return BATTLE.foe_attack if is_foe else BATTLE.ally_attack
    if stat_name == "defense":
        return BATTLE.foe_defense if is_foe else BATTLE.ally_defense
    if stat_name == "special":
        return BATTLE.foe_special if is_foe else BATTLE.ally_special
    if stat_name == "speed":
        return BATTLE.foe_speed if is_foe else BATTLE.ally_speed
    return 0


def change_stage(is_foe: bool, stat_name: str, amount: int) -> None:
    limit = rules().stage_limit
    value = max(-limit, min(limit, stage_of(is_foe, stat_name) + amount))
    if stat_name == "attack":
        if is_foe:
            BATTLE.foe_attack = value
        else:
            BATTLE.ally_attack = value
    elif stat_name == "defense":
        if is_foe:
            BATTLE.foe_defense = value
        else:
            BATTLE.ally_defense = value
    elif stat_name == "special":
        if is_foe:
            BATTLE.foe_special = value
        else:
            BATTLE.ally_special = value
    elif stat_name == "speed":
        if is_foe:
            BATTLE.foe_speed = value
        else:
            BATTLE.ally_speed = value


def begin_wild(species: str, level: int) -> None:
    reset_run()
    BATTLE.wild = True
    BATTLE.trainer = ""
    wild = make_monster(species, level)
    wild.variant = wild_variant(species)
    BATTLE.foes.append(wild)
    SESSION.save.seen[species] = 1
    line("send", named("wild_appears", display_name(wild)), True, 0, look(wild))
    send_ally()


def begin_trainer(trainer: str) -> None:
    reset_run()
    t = TRAINERS.get(trainer)
    BATTLE.wild = False
    BATTLE.trainer = trainer
    for row in t.team:
        m = make_monster(row.species, row.level)
        if row.variant != "default":
            m.variant = row.variant
        BATTLE.foes.append(m)
    SESSION.save.seen[foe().species] = 1
    say(named("wants_fight", t.name))
    line("send", fill(named("sends_out", t.name), "monster", display_name(foe())), True, 0, look(foe()))
    send_ally()


def send_ally() -> None:
    a = ally()
    line("send", named("go", display_name(a)), False, 0, look(a))
    line("hp", "", False, a.hp, "")


# ── effects ──────────────────────────────────────────────────────────────


def apply_effect(effect_id: str, user_is_foe: bool, target: Monster, user: Monster) -> None:
    """What data/effects.json says the move does: a status, a stat that goes up or down, or HP back."""
    e = EFFECTS.get(effect_id)
    who = user if e.target == "self" else target
    who_is_foe = user_is_foe if e.target == "self" else not user_is_foe
    if e.status is not None:
        if who.status != "":
            return
        st = STATUSES.get(e.status)
        who.status = e.status
        if st.max_turns > 0:
            who.sleep_turns = random.randint(st.min_turns, st.max_turns)
        say(named_text(st.apply_text, display_name(who)))
    if e.stat != "":
        change_stage(who_is_foe, e.stat, e.amount)
        say(named_text(e.text, display_name(who)))
    if e.heal_percent > 0:
        who.hp = min(max_hp(who), who.hp + max_hp(who) * e.heal_percent // 100)
        line("hp", named_text(e.text, display_name(who)), who_is_foe, who.hp, "")


def named_text(text: str, name: str) -> str:
    return fill(text, "name", name)


def use_move(user: Monster, target: Monster, move_id: str, user_is_foe: bool) -> None:
    if move_id == "":
        say(named("nothing_to_do", display_name(user)))
        return
    if user.status != "" and STATUSES.get(user.status).max_turns > 0:
        st = STATUSES.get(user.status)
        user.sleep_turns -= 1
        if user.sleep_turns > 0:
            say(named_text(st.still_text, display_name(user)))
            return
        user.status = ""
        say(named_text(st.wake_text, display_name(user)))
    move = MOVES.get(move_id)
    for slot in user.moves:
        if slot.move == move_id:
            slot.pp = max(0, slot.pp - 1)
    say(fill(named("uses", display_name(user)), "move", move.name))
    if random.randint(1, 100) > move.accuracy:
        say(word("missed"))
        return
    if move.power > 0:
        critical = random.randint(1, 100) <= rules().critical_percent
        kind = "attack" if move.kind == "physical" else "special"
        guard = "defense" if move.kind == "physical" else "special"
        attack = float(stat(user, kind)) * stage_factor(stage_of(user_is_foe, kind))
        defense = float(stat(target, guard)) * stage_factor(stage_of(not user_is_foe, guard))
        if kind == "attack" and user.status != "":
            attack = attack * STATUSES.get(user.status).attack_factor
        factor = effectiveness(move, target)
        amount = hit_damage(user, attack, defense, target, move, critical)
        target.hp = max(0, target.hp - amount)
        line("hp", "", not user_is_foe, target.hp, "")
        if factor == 0.0:
            say(word("no_effect"))
        elif factor > 1.0:
            say(word("hits_hard"))
        elif factor < 1.0:
            say(word("barely"))
        if critical and factor > 0:
            say(word("critical"))
    if move.effect is not None and target.hp > 0 and random.randint(1, 100) <= move.chance:
        apply_effect(move.effect, user_is_foe, target, user)


def end_of_turn_status(m: Monster, is_foe: bool) -> None:
    if m.hp <= 0 or m.status == "" or STATUSES.get(m.status).turn_share <= 0:
        return
    st = STATUSES.get(m.status)
    m.hp = max(0, m.hp - max(rules().status_damage_minimum, max_hp(m) // st.turn_share))
    say(named_text(st.turn_text, display_name(m)))
    line("hp", "", is_foe, m.hp, "")


# ── a turn ───────────────────────────────────────────────────────────────


def foe_move() -> str:
    return random_move(foe()) if BATTLE.wild else best_move(foe(), ally())


def fight(move_id: str) -> None:
    """The player chose a move."""
    a = ally()
    f = foe()
    ally_speed = int(stat(a, "speed") * stage_factor(BATTLE.ally_speed))
    foe_speed = int(stat(f, "speed") * stage_factor(BATTLE.foe_speed))
    ally_first = ally_speed * 1000 + random.randint(0, 999) >= foe_speed * 1000 + random.randint(0, 999)
    if ally_first:
        use_move(a, f, move_id, False)
        if not check_faints():
            use_move(f, a, foe_move(), True)
    else:
        use_move(f, a, foe_move(), True)
        if not check_faints():
            use_move(a, f, move_id, False)
    if not BATTLE.over and not BATTLE.must_switch and not check_faints():
        end_of_turn_status(a, False)
        end_of_turn_status(f, True)
        check_faints()


def foe_acts() -> None:
    """The player spent the turn on an item or a switch."""
    use_move(foe(), ally(), foe_move(), True)
    if not check_faints():
        end_of_turn_status(ally(), False)
        end_of_turn_status(foe(), True)
        check_faints()


def switch_to(index: int) -> None:
    forced = BATTLE.must_switch
    BATTLE.must_switch = False
    BATTLE.ally_at = index
    reset_stages(False)
    send_ally()
    if not forced:
        foe_acts()


def run_away() -> None:
    if not BATTLE.wild:
        say(game_info().no_flee_text)
        return
    BATTLE.flee_tries += 1
    if stat(ally(), "speed") * rules().flee_speed_factor + BATTLE.flee_tries * rules().flee_per_try > random.randint(0, 255):
        say(word("got_away"))
        finish(False, True)
    else:
        say(word("no_escape"))
        foe_acts()


def use_item(item_id: str, target_index: int) -> None:
    item = ITEMS.get(item_id)
    add_item(item_id, -1)
    if item.capture > 0:
        throw_knot(item_id)
        return
    target = SESSION.save.team[target_index]
    apply(item, target)
    if item.heal > 0:
        say(named("feels_better", display_name(target)))
        if target_index == BATTLE.ally_at:
            line("hp", "", False, target.hp, "")
    else:
        say(named("itself_again", display_name(target)))
    foe_acts()


def throw_knot(item_id: str) -> None:
    item = ITEMS.get(item_id)
    f = foe()
    if not BATTLE.wild:
        say(game_info().owned_text)
        foe_acts()
        return
    say(fill(word("tie_knot"), "item", item.name))
    rate = SPECIES.get(f.species).catch_rate
    shakes = capture_shakes(max_hp(f), f.hp, rate, item.capture, f.status)
    for i in range(shakes):
        line("shake", "", True, i, "")
    if shakes >= CAPTURE_CHECKS:
        SESSION.save.caught[f.species] = 1
        SESSION.save.seen[f.species] = 1
        keep(f)
        line("caught", named("bonded", display_name(f)), True, 0, "")
        finish(True, True)
    else:
        say(named("slips", display_name(f)))
        line("send", "", True, 0, look(f))
        foe_acts()


def keep(m: Monster) -> None:
    if len(SESSION.save.team) < rules().team_size:
        SESSION.save.team.append(m)
    else:
        SESSION.save.box.append(m)
        say(named("to_box", display_name(m)))


# ── fainting and the end ─────────────────────────────────────────────────


def check_faints() -> bool:
    """True when the turn cannot go on."""
    if BATTLE.over or BATTLE.must_switch:
        return True
    f = foe()
    stop = False
    if f.hp <= 0:
        line("faint", named("faints", display_name(f)), True, 0, "")
        give_exp(f)
        if BATTLE.foe_at + 1 < len(BATTLE.foes):
            BATTLE.foe_at += 1
            reset_stages(True)
            next_foe = foe()
            SESSION.save.seen[next_foe.species] = 1
            line("send", named("next_comes", display_name(next_foe)), True, 0, look(next_foe))
        else:
            finish(True, False)
        stop = True
    if not BATTLE.over and ally().hp <= 0:
        line("faint", named("faints", display_name(ally())), False, 0, "")
        if first_able() >= 0:
            BATTLE.must_switch = True
        else:
            finish(False, False)
        stop = True
    return stop


def give_exp(beaten: Monster) -> None:
    """Everyone with HP left gets some; who fought gets all of it, the others half."""
    gain = SPECIES.get(beaten.species).exp_yield * beaten.level // 5 + 1
    i = 0
    for m in SESSION.save.team:
        if m.hp > 0:
            share = gain if i == BATTLE.ally_at else gain * rules().exp_share_percent // 100
            m.exp += share
            add_ev(m, SPECIES.get(beaten.species).ev_stat, rules().ev_gain)
            if i == BATTLE.ally_at:
                say(fill(named("gained", display_name(m)), "count", str(share)))
            level_up(m, i == BATTLE.ally_at)
            if i == BATTLE.ally_at:
                line("xp", "", False, exp_progress(m), "")
        i += 1


def level_up(m: Monster, shown: bool) -> None:
    while m.level < rules().max_level and m.exp >= exp_for_level(m.level + 1):
        if shown:
            line("xp", "", False, 1000, "")          # the bar fills up...
        before = max_hp(m)
        m.level += 1
        m.hp += max_hp(m) - before
        line("level", fill(named("level_up", display_name(m)), "level", str(m.level)), False, m.hp if shown else -1, "")
        if shown:
            line("xp", "", False, 0, "")             # ...and starts again
        for entry in SPECIES.get(m.species).learnset:
            if entry.level == m.level and learn(m, entry.move):
                say(fill(named("learned", display_name(m)), "move", MOVES.get(entry.move).name))
        target = evolves_now(m)
        if target != "":
            old = display_name(m)
            become(m, target)
            line("evolve", named("changing", old), False, 0, look(m))
            say(fill(named("became", old), "monster", SPECIES.get(target).name))


def finish(won: bool, quiet: bool) -> None:
    BATTLE.over = True
    BATTLE.won = won
    if won and not quiet and not BATTLE.wild:
        t = TRAINERS.get(BATTLE.trainer)
        say(fill(named("trainer_says", t.name), "words", t.lose_text))
        SESSION.save.money += t.reward
        say(fill(word("earned"), "count", str(t.reward)))
    if not won and not quiet:
        lost = SESSION.save.money * rules().lost_money_percent // 100
        SESSION.save.money -= lost
        say(game_info().lost_text.replace("{money}", str(lost)).replace("{currency}", game_info().currency))
    line("end", "", False, 0, "")
