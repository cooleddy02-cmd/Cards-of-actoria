from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room as sio_join_room
import random, string, copy, uuid, json, hashlib, os
from cards import (CARDLIST, SPECIAL_CARDS, ALL_CARDS,
                   DECK_WEIGHTS, DECK_INFO, GEM_REWARDS, BOT_NAMES, BOT_DECKS)

ACCESS_CODE = "CLOCKPAPI"
ADMIN_CODE  = "CYNIRZPAPI"
USERS_FILE  = "users.json"
STARTING_GEMS = 10

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clockpapi-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
rooms = {}

# ═══════════════════════════════════════════════════════════════
#  USER ACCOUNTS
# ═══════════════════════════════════════════════════════════════

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _gen_player_id():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=7))

def user_public(u):
    return {'gems': u['gems'], 'owned_decks': u['owned_decks'],
            'wins': u.get('wins', 0), 'losses': u.get('losses', 0),
            'player_id': u.get('player_id', '???????')}

# ═══════════════════════════════════════════════════════════════
#  CARD HELPERS
# ═══════════════════════════════════════════════════════════════

def new_card(base):
    c = copy.deepcopy(base)
    c['uid']            = str(uuid.uuid4())[:8]
    c['attacked']       = False
    c['frozen']         = False
    c['turns_on_field'] = 0
    c['hit_this_turn']  = 0
    c['base_def']       = base.get('def', 0)
    if 'block' not in c:
        c['block'] = 0
    if _has(c, 'guard_immunity'):
        c['guard_remaining'] = 2
    if _has(c, 'v18_reroll'):
        c['atk'] = random.randint(0, 8)
    if _has(c, 'omega_atk_lock'):
        c['base_atk'] = c.get('atk', 0)
    return c

def _buff_atk(card, amount):
    card['atk'] += amount
    if _has(card, 'omega_atk_lock') and 'base_atk' in card:
        card['atk'] = max(card['atk'], card['base_atk'])

def _is_dead(card):
    if card.get('base_def', 1) == 0:
        return card['def'] < 0
    return card['def'] <= 0

def draw_from_deck(deck_type='basic'):
    drawable = [c for c in CARDLIST if not c.get('no_draw')]
    weights  = DECK_WEIGHTS.get(deck_type, {})
    if not weights:
        return new_card(random.choice(drawable))
    pool = []
    for c in drawable:
        pool.extend([c] * weights.get(c['name'], 1))
    return new_card(random.choice(pool))

def deal_hand(deck_type='basic', k=5):
    return [draw_from_deck(deck_type) for _ in range(k)]

def _has(card, sid):
    return any(s['id'] == sid for s in card.get('specials', []))

def _has_eff(card, sid):
    if card.get('emp_turns', 0) > 0:
        return False
    return _has(card, sid)

def _find_by_uid(players, uid):
    for pi, p in enumerate(players):
        for fi, c in enumerate(p['field']):
            if c['uid'] == uid:
                return pi, fi, c
    return None, None, None

def _find_in_hand(players, uid):
    for pi, p in enumerate(players):
        for hi, c in enumerate(p['hand']):
            if c['uid'] == uid:
                return pi, hi, c
    return None, None, None

def make_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code

def new_room():
    return {
        'players': [], 'state': 'waiting', 'current_turn': 0,
        'first_turns': [True, True], 'phase': 'waiting',
        'cards_played': 0, 'quick_effect_used': [False, False],
        'pending_action': None, 'message': 'Waiting for opponent...',
        'winner': None, 'turn_count': 0,
        'is_bot': False, 'bot_difficulty': None, 'human_username': None,
    }

# ═══════════════════════════════════════════════════════════════
#  DESTROY SYSTEM
# ═══════════════════════════════════════════════════════════════

def destroy_card(room, room_code, owner_index, field_index,
                 bypass_guard=False, bypass_phoenix=False, skip_on_destroy=False):
    players = room['players']
    player  = players[owner_index]
    opp     = players[1 - owner_index]

    if field_index >= len(player['field']):
        return False
    card = player['field'][field_index]

    if not bypass_guard and card.get('guard_remaining', 0) > 0:
        return False

    if _has(card, 'angel_block_kill') and card.get('block', 0) > 0 and bypass_guard:
        return False

    if _has(card, 'golem_banish'):
        player['field'].pop(field_index)
        _check_win(room, players)
        return True

    if not bypass_phoenix and _has(card, 'phoenix_revive') and not card.get('revived'):
        base = next((c for c in SPECIAL_CARDS if c['name'] == 'Phoenix'), None)
        card['def']     = base['def'] if base else 6
        card['revived'] = True
        card['burn_turns'] = 0
        return False

    player['field'].pop(field_index)
    if skip_on_destroy:
        return True

    if _has(card, 'love_heal'):
        player['hp'] += 4
    if _has(card, 'equal_revenge') and card.get('turns_on_field', 0) <= 4:
        player['hp'] -= 4; opp['hp'] -= 4
    if _has(card, 'side_death'):
        player['hp'] -= 4
    if _has(card, 'greed_death'):
        player['hp'] -= 4
    if _has(card, 'ash_phoenix') and card.get('turns_on_field', 0) <= 5:
        base = next((c for c in SPECIAL_CARDS if c['name'] == 'Phoenix'), None)
        if base and len(player['field']) < 4:
            player['field'].append(new_card(base))
    if _has(card, 'breaker_destroy'):
        removed = 0
        for ec in opp['field']:
            if ec.get('block', 0) > 0:
                ec['block'] = 0; ec['block_disabled'] = True; removed += 1
        if removed:
            opp['hp'] -= removed

    if _has(card, 'atlas_bhh_death_dmg'):
        player['hp'] -= 2
    if _has(card, 'atlas_greed_death_dmg'):
        player['hp'] -= 3
    if _has(card, 'lich_death_buff'):
        for fc in player['field']:
            _buff_atk(fc, 1); fc['def'] += 1

    _check_win(room, players)
    return True

def _check_win(room, players):
    for i, p in enumerate(players):
        if p['hp'] <= 0:
            p['hp'] = 0
            if not room.get('winner'):
                room['winner'] = players[1 - i]['name']
                room['state']  = 'finished'

# ═══════════════════════════════════════════════════════════════
#  TURN EFFECTS
# ═══════════════════════════════════════════════════════════════

def process_turn_start(room, room_code, active_index):
    players = room['players']
    active  = players[active_index]
    opp     = players[1 - active_index]
    msgs    = []
    greed_draw_done = greed_decay_done = sun_done = False

    for card in list(active['field']):
        tof = card.get('turns_on_field', 0)

        if _has(card, 'star_reroll'):
            r = random.random()
            if r < 0.4:   card['def'] = 6; msgs.append(f"⭐ {card['name']}: +6 DEF!")
            elif r < 0.8: card['atk'] = 6; msgs.append(f"⭐ {card['name']}: +6 ATK!")

        if _has(card, 'wrath_rage') and card['atk'] < card.get('atk_max', 6):
            card['atk'] = min(card['atk'] + 1, card.get('atk_max', 6))
            msgs.append(f"😡 {card['name']} Rage! ATK→{card['atk']}")

        if _has(card, 'health_regen') and tof > 0 and tof % 2 == 0:
            active['hp'] += 4; msgs.append(f"💚 {card['name']} heals 4!")

        if _has(card, 'greed_draw') and not greed_draw_done and not room['first_turns'][active_index]:
            drawn = draw_from_deck(room.get('player_deck', {}).get(active_index, 'basic'))
            active['hand'].append(drawn); greed_draw_done = True
            msgs.append(f"💰 Greed: extra draw!")

        if _has(card, 'greed_decay') and not greed_decay_done:
            for c in active['field']:
                if not _has(c, 'duraza_def_lock'):
                    c['def'] = max(c['def'] - 1, -5)
            greed_decay_done = True
            msgs.append(f"💀 Greed Decay: all cards -1 DEF!")

        if _has(card, 'golem_regen') and not card.get('flipped'):
            card['def'] += 5
            msgs.append(f"🪨 {card['name']} constructs! DEF→{card['def']}")

        if _has(card, 'golem_flip') and not card.get('flipped') and tof >= 4:
            old_def = card['def']
            card['atk'] = old_def
            card['def'] = 1
            card['flipped'] = True
            msgs.append(f"🪨 {card['name']} flips! ATK→{card['atk']} DEF→1")

        if _has(card, 'sad_self_damage') and tof > 0 and tof % 4 == 0:
            active['hp'] -= 4
            msgs.append(f"💔 {card['name']} Sorrow: owner -{4} HP!")

        if _has(card, 'sun_aoe') and not sun_done:
            star_blocks = any(_has(c, 'star_aoe_block') for c in opp['field'])
            if star_blocks:
                msgs.append(f"⭐ The Star negated Sun AoE!")
            else:
                for ec in opp['field']:
                    if not _has(ec, 'aoe_immune') and not _has(ec, 'duraza_def_lock'):
                        ec['def'] -= 1
                msgs.append(f"☀️ Sun burns all enemy cards!")
            sun_done = True

        if _has(card, 'block_recharge') and tof > 0 and tof % 4 == 0:
            cap = card.get('block_max', 3)
            if card.get('block', 0) < cap and not card.get('block_disabled'):
                card['block'] = min(card.get('block', 0) + 1, cap)

        if _has(card, 'star_col_dmg') and card.get('guard_remaining', 0) == 0:
            fi = active['field'].index(card)
            if fi < len(opp['field']):
                ec = opp['field'][fi]
                if ec.get('guard_remaining', 0) == 0 and not _has(ec, 'aoe_immune'):
                    ec['def'] -= 2
                    msgs.append(f"⭐ The Star burns {ec['name']} -2 DEF!")

        if _has(card, 'atlas_greed_draw') and not greed_draw_done and not room['first_turns'][active_index]:
            drawn = draw_from_deck(room.get('player_deck', {}).get(active_index, 'basic'))
            active['hand'].append(drawn); greed_draw_done = True
            msgs.append(f"💰 Atlas Greed: extra draw!")

        if _has(card, 'omega_end_dmg') and not room['first_turns'][active_index]:
            opp['hp'] -= 1
            msgs.append(f"🔱 {card['name']} Pulse: opp -1 HP!")

        if _has(card, 'angel_dynamic_atk'):
            all_atks = [c['atk'] for p in players for c in p['field'] if c['uid'] != card['uid']]
            card['atk'] = max(all_atks) if all_atks else 0

    for pi, p in enumerate(players):
        for card in list(p['field']):
            if card.get('burn_turns', 0) > 0:
                card['def'] -= 1; card['burn_turns'] -= 1
                msgs.append(f"🔥 {card['name']} burns! DEF→{card['def']}")
            if card.get('dark_stars', 0) > 0:
                card['def'] -= card['dark_stars']
            if card.get('guard_remaining', 0) > 0:
                card['guard_remaining'] -= 1
            if card.get('frost_shield_turns', 0) > 0:
                card['frost_shield_turns'] -= 1
            if card.get('emp_turns', 0) > 0:
                card['emp_turns'] -= 1
            if card.get('ice_cream_turns', 0) > 0:
                card['ice_cream_turns'] -= 1
                if card['ice_cream_turns'] == 0:
                    card['atk'] -= card.pop('ice_cream_atk', 0)
                    card['def'] -= card.pop('ice_cream_def', 0)
                    msgs.append(f"🍦 {card['name']}: Ice Cream wore off!")

    for pi in range(2):
        i = 0
        while i < len(players[pi]['field']):
            c = players[pi]['field'][i]
            if _is_dead(c) and c.get('guard_remaining', 0) == 0:
                if not destroy_card(room, room_code, pi, i): i += 1
            else:
                i += 1

    for p in players:
        for card in p['field']:
            card['hit_this_turn'] = 0

    if msgs:
        room['message'] = ' | '.join(msgs[:4])

def increment_turns(room):
    for p in room['players']:
        for c in p['field']:
            c['turns_on_field'] = c.get('turns_on_field', 0) + 1

# ═══════════════════════════════════════════════════════════════
#  ATTACK
# ═══════════════════════════════════════════════════════════════

def apply_damage(card, damage, is_aoe=False, bypass_guard=False, bypass_block=False):
    if is_aoe and _has(card, 'aoe_immune'): return 0
    if not bypass_guard and card.get('guard_remaining', 0) > 0: return 0
    if _has(card, 'duraza_hit_limit'):
        if card.get('hit_this_turn', 0) >= 2: return 0
        card['hit_this_turn'] = card.get('hit_this_turn', 0) + 1
    if card.get('frost_shield_turns', 0) > 0:
        damage = max(0, damage // 2)
    if not bypass_block and card.get('block', 0) > 0:
        absorbed = min(card['block'], damage)
        card['block'] -= absorbed; damage -= absorbed
    card['def'] -= damage
    return damage

def _exec_attack(room, room_code, pi, ai, ti):
    players = room['players']
    apl = players[pi]; dpl = players[1 - pi]
    if ai >= len(apl['field']): return
    atk = apl['field'][ai]; msgs = []

    # Frozen check (Clock freeze or Ice counter-freeze)
    if atk.get('frozen'):
        room['message'] = f"❄️ {atk['name']} is frozen and can't attack!"
        room['phase'] = 'attack'
        broadcast_state(room_code); return

    # Trio-Sword triple strike (left / middle / right — not AoE)
    if _has(atk, 'trio_sword_tri'):
        field = dpl['field']
        positions = []
        if len(field) >= 1: positions.append(0)
        if len(field) >= 3: positions.append(len(field) // 2)
        if len(field) >= 2: positions.append(len(field) - 1)
        positions = list(dict.fromkeys(positions))
        for pos in positions:
            if pos < len(dpl['field']):
                ec = dpl['field'][pos]
                actual = apply_damage(ec, atk['atk'])
                if actual > 0: msgs.append(f"⚔️⚔️⚔️ Trio hits {ec['name']} -{actual}!")
        if not dpl['field']:
            dpl['hp'] -= atk['atk']; msgs.append(f"⚔️⚔️⚔️ Trio direct -{atk['atk']}!")
        atk['attacked'] = True
        _check_deaths(room, room_code, 1 - pi)
        _check_win(room, players)
        room['message'] = ' | '.join(msgs[:3]); room['phase'] = 'attack'
        broadcast_state(room_code); return

    # Side AoE
    if _has(atk, 'side_aoe'):
        star_blocks = any(_has(c, 'star_aoe_block') for c in dpl['field'])
        if star_blocks:
            msgs.append(f"⭐ The Star negated {atk['name']}'s AoE!")
            atk['attacked'] = True
            room['message'] = ' | '.join(msgs); room['phase'] = 'attack'
            broadcast_state(room_code); return
        for ec in list(dpl['field']):
            apply_damage(ec, atk['atk'], is_aoe=True)
        msgs.append(f"{atk['name']} sweeps all enemy cards!")
        if _has(atk, 'hate_selfdmg'): apl['hp'] -= atk['atk']
        atk['attacked'] = True
        _check_deaths(room, room_code, 1 - pi)
        _check_win(room, players)
        room['message'] = ' | '.join(msgs); room['phase'] = 'attack'
        broadcast_state(room_code); return

    # Amegma block break (before direct/target logic)
    if _has(atk, 'amegma_block_break') and ti is not None:
        if ti < len(dpl['field']):
            tgt_check = dpl['field'][ti]
            if tgt_check.get('block', 0) > 0:
                tgt_check['block'] = 0
                atk['attacked'] = True
                room['message'] = f"💥 {atk['name']} crushed {tgt_check['name']}'s block! No damage."
                room['phase'] = 'attack'
                broadcast_state(room_code); return

    # Direct
    if ti is None:
        if not _has(atk, 'wrath_direct') and not _has(atk, 'amegma_free_attack') and dpl['field']:
            room['message'] = "Can't attack directly — opponent has cards!"
            room['phase'] = 'attack'; broadcast_state(room_code); return
        dpl['hp'] -= atk['atk']
        msgs.append(f"{atk['name']} deals {atk['atk']} direct damage!")
        if _has(atk, 'hate_selfdmg'): apl['hp'] -= atk['atk']
        atk['attacked'] = True
        _check_win(room, players)
        room['message'] = ' | '.join(msgs); room['phase'] = 'attack'
        broadcast_state(room_code); return

    if ti >= len(dpl['field']): return
    tgt = dpl['field'][ti]; dmg = atk['atk']

    # Mirror
    if _has(tgt, 'mirror_reflect') and tgt.get('guard_remaining', 0) == 0:
        tgt['def'] -= dmg; atk['def'] -= dmg
        msgs.append(f"🪞 Mirror reflects {dmg} back!")
        if _is_dead(atk):
            idx = apl['field'].index(atk)
            destroy_card(room, room_code, pi, idx, bypass_guard=True)
            msgs.append(f"{atk['name']} destroyed by reflection!")
        if _is_dead(tgt):
            destroy_card(room, room_code, 1 - pi, ti)
        atk['attacked'] = True
        room['message'] = ' | '.join(msgs); room['phase'] = 'attack'
        broadcast_state(room_code); return

    # Bolt pierce
    if _has(atk, 'bolt_pierce'):
        tgt['def'] -= dmg; dpl['hp'] -= dmg
        msgs.append(f"⚡ Pierce: {dmg} to card AND player!")
    else:
        actual = apply_damage(tgt, dmg)
        if actual == 0: msgs.append(f"{tgt['name']} blocked!")
        else: msgs.append(f"{atk['name']} hits {tgt['name']} for {actual}!")
        if _has(atk, 'lich_def_leech') and actual > 0:
            gain = max(1, actual // 2)
            atk['def'] += gain
            msgs.append(f"💀 Lich drains: +{gain} DEF!")

    # Duraza double strike — hits twice with full ATK each time
    if _has(atk, 'duraza_dual') and not _has(atk, 'bolt_pierce'):
        second = apply_damage(tgt, dmg)
        if second > 0: msgs.append(f"⚡ Double Strike! +{second}!")

    # Freeze (Clock)
    if _has(atk, 'freeze') and not tgt.get('frozen'):
        tgt['frozen'] = True; tgt['freeze_by'] = pi; tgt['freeze_turns'] = 1
        msgs.append(f"❄️ {tgt['name']} frozen!")

    # Ice counter-freeze (Ice Shield)
    if _has(tgt, 'ice_counter_freeze') and actual > 0 and not atk.get('frozen') and random.random() < 0.5:
        atk['frozen'] = True; atk['freeze_by'] = 1 - pi; atk['freeze_turns'] = 1
        msgs.append(f"❄️ {tgt['name']} counter-froze {atk['name']}!")

    # Phoenix burn
    if _has(atk, 'phoenix_burn'):
        tgt['burn_turns'] = 3; msgs.append(f"🔥 {tgt['name']} burning!")

    # Hate self-damage
    if _has(atk, 'hate_selfdmg'):
        apl['hp'] -= dmg; msgs.append(f"Bloodlust: own player -{dmg}!")

    # Check target death
    if _is_dead(tgt) and tgt.get('guard_remaining', 0) == 0:
        excess = abs(tgt['def'])
        destroyed = destroy_card(room, room_code, 1 - pi, ti)
        if destroyed:
            msgs.append(f"{tgt['name']} destroyed!")
            if excess > 0: dpl['hp'] -= excess; msgs.append(f"{excess} excess damage!")
            if _has(atk, 'diamond_gain') and atk in apl['field']:
                _buff_atk(atk, 1); atk['def'] += 1; msgs.append(f"💎 +1/+1!")

    atk['attacked'] = True
    _check_win(room, players)
    room['message'] = ' | '.join(msgs[:5]); room['phase'] = 'attack'
    broadcast_state(room_code)

def _exec_play_card(room, room_code, pi, ci):
    player = room['players'][pi]
    if ci >= len(player['hand']): return
    card = player['hand'].pop(ci)
    card['attacked'] = False; card['turns_on_field'] = 0
    if _has(card, 'v18_reroll'):
        card['atk'] = random.randint(0, 8)
    player['field'].append(card)
    room['cards_played'] += 1
    room['message'] = f"{player['name']} played {card['name']}."
    room['phase'] = 'play'
    broadcast_state(room_code)

def _check_deaths(room, room_code, pi):
    players = room['players']
    i = 0
    while i < len(players[pi]['field']):
        c = players[pi]['field'][i]
        if _is_dead(c) and c.get('guard_remaining', 0) == 0:
            if not destroy_card(room, room_code, pi, i): i += 1
        else:
            i += 1

# ═══════════════════════════════════════════════════════════════
#  HAND TRAP
# ═══════════════════════════════════════════════════════════════

def _defender_has_qe(room):
    if room.get('is_bot'): return False
    di = 1 - room['current_turn']
    if room['quick_effect_used'][di]: return False
    return any(c['name'] == 'Clock' and not c.get('frozen')
               for c in room['players'][di]['hand'])

def _open_hand_trap(room, room_code, pending):
    room['pending_action'] = pending
    room['phase'] = 'hand_trap_window'
    actor = room['players'][room['current_turn']]['name']
    room['message'] = f"{actor} is {_pdesc(pending)} — Quick Effect?"
    broadcast_state(room_code)

def _pdesc(p):
    if not p: return ''
    return 'playing a card' if p.get('type') == 'play_card' else 'declaring an attack'

def _tick_freeze(room, ending_pi):
    for p in room['players']:
        for c in p['field']:
            if c.get('frozen') and c.get('freeze_by') == ending_pi:
                c['freeze_turns'] = c.get('freeze_turns', 1) - 1
                if c['freeze_turns'] <= 0:
                    c['frozen'] = False

# ═══════════════════════════════════════════════════════════════
#  BOT AI
# ═══════════════════════════════════════════════════════════════

def _bot_plays(bot, human, diff):
    hand = bot['hand']
    if not hand: return []
    if diff == 'easy':
        n = random.choice([0, 1, min(2, len(hand))])
        indices = random.sample(range(len(hand)), min(n, len(hand)))
        return sorted(indices, reverse=True)
    elif diff == 'medium':
        scored = sorted(range(len(hand)), key=lambda i: hand[i]['atk']+hand[i]['def'], reverse=True)
        return sorted(scored[:min(2, len(scored))], reverse=True)
    else:
        def sc(c):
            s = c['atk']*1.5 + max(c['def'], 0)
            if c.get('specials'): s += 3
            if c['name'] in ('Blackhole','Hate','Wrath','Diamond','CoreStars','Mirror','Guard'): s += 4
            return s
        scored = sorted(range(len(hand)), key=lambda i: sc(hand[i]), reverse=True)
        return sorted(scored[:min(2, len(scored))], reverse=True)

def _bot_attacks(bot, human, diff):
    attacks = []
    for ai, card in enumerate(bot['field']):
        if card.get('attacked'): continue
        if diff == 'easy':
            if random.random() < 0.6:
                if human['field']:
                    attacks.append((ai, random.randint(0, len(human['field'])-1)))
        elif diff == 'medium':
            if human['field']:
                ti = min(range(len(human['field'])), key=lambda i: human['field'][i]['def'])
                attacks.append((ai, ti))
            else:
                attacks.append((ai, None))
        else:
            if human['field']:
                if _has(card, 'hate_selfdmg') and bot['hp'] <= card['atk']:
                    continue
                # Kill weakest if possible, else hit strongest threat
                killable = [i for i,c in enumerate(human['field'])
                            if c['def'] <= card['atk'] and c.get('guard_remaining',0)==0]
                if killable:
                    attacks.append((ai, killable[0]))
                else:
                    ti = max(range(len(human['field'])), key=lambda i: human['field'][i]['atk'])
                    attacks.append((ai, ti))
            else:
                attacks.append((ai, None))
    return attacks

def bot_execute_turn(room_code):
    socketio.sleep(1.2)
    room = rooms.get(room_code)
    if not room or room.get('state') == 'finished': return
    bot   = room['players'][1]
    human = room['players'][0]
    diff  = room.get('bot_difficulty', 'easy')

    # Play phase
    plays = _bot_plays(bot, human, diff)
    for ci in plays:
        room = rooms.get(room_code)
        if not room or room.get('state') == 'finished': return
        if len(bot['field']) < 4 and ci < len(bot['hand']):
            _exec_play_card(room, room_code, 1, ci)
            socketio.sleep(0.85)

    room = rooms.get(room_code)
    if not room or room.get('state') == 'finished': return
    room['phase'] = 'attack'
    room['message'] = f"{bot['name']} is attacking..."
    broadcast_state(room_code)
    socketio.sleep(1.0)

    # Attack phase
    attacks = _bot_attacks(bot, human, diff)
    for ai, ti in attacks:
        room = rooms.get(room_code)
        if not room or room.get('state') == 'finished': return
        field = room['players'][1]['field']
        if ai < len(field) and not field[ai].get('attacked'):
            _exec_attack(room, room_code, 1, ai, ti)
            socketio.sleep(0.85)

    room = rooms.get(room_code)
    if not room or room.get('state') == 'finished': return
    socketio.sleep(0.4)
    _do_end_turn(room, room_code, 1)

# ═══════════════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════════════

def broadcast_state(room_code):
    room = rooms.get(room_code)
    if not room or len(room['players']) < 2: return
    players = room['players']
    for i, player in enumerate(players):
        if player['sid'] == 'BOT': continue
        opp = players[1 - i]
        is_ht = room['phase'] == 'hand_trap_window' and room['current_turn'] != i
        gem_reward = GEM_REWARDS.get(room.get('bot_difficulty'), 0) if room.get('is_bot') else 0
        socketio.emit('state_update', {
            'your_index':       i,
            'your_name':        player['name'],
            'opp_name':         opp['name'],
            'your_hp':          player['hp'],
            'opp_hp':           opp['hp'],
            'your_hand':        player['hand'],
            'your_field':       player['field'],
            'opp_field':        opp['field'],
            'opp_hand_count':   len(opp['hand']),
            'opp_player_id':    opp.get('player_id'),
            'current_turn':     room['current_turn'],
            'phase':            room['phase'],
            'cards_played':     room['cards_played'],
            'message':          room.get('message', ''),
            'winner':           room.get('winner'),
            'hand_trap_prompt': is_ht,
            'pending_desc':     _pdesc(room.get('pending_action')),
            'is_bot_game':      room.get('is_bot', False),
            'gem_reward':       gem_reward,
            'bot_difficulty':   room.get('bot_difficulty'),
        }, to=player['sid'])

# ═══════════════════════════════════════════════════════════════
#  SHARED END TURN
# ═══════════════════════════════════════════════════════════════

def _do_end_turn(room, room_code, pi):
    players = room['players']
    _tick_freeze(room, pi)
    for c in players[pi]['field']:
        c['attacked'] = False
    increment_turns(room)

    nt = 1 - pi
    room['current_turn']          = nt
    room['phase']                 = 'play'
    room['cards_played']          = 0
    room['quick_effect_used'][nt] = False
    room['turn_count']            = room.get('turn_count', 0) + 1

    decks = room.get('player_deck', {})
    nt_has_sad  = any(_has(c, 'sad_no_draw') for c in players[nt]['field'])
    pi_has_sad  = any(_has(c, 'sad_no_draw') for c in players[pi]['field'])
    if room['first_turns'][nt]:
        room['first_turns'][nt] = False
        room['message'] = f"{players[nt]['name']}'s turn — no draw (first turn)."
    elif nt_has_sad:
        room['message'] = f"{players[nt]['name']} can't draw (Sad Dream)!"
    elif players[nt].get('force_no_draw'):
        players[nt]['force_no_draw'] = False
        room['message'] = f"🔒 {players[nt]['name']} can't draw (Lockout)!"
    else:
        drawn = draw_from_deck(decks.get(nt, 'basic'))
        players[nt]['hand'].append(drawn)
        if pi_has_sad:
            drawn2 = draw_from_deck(decks.get(nt, 'basic'))
            players[nt]['hand'].append(drawn2)
            room['message'] = f"{players[nt]['name']} drew 2 cards (Sad Dream bonus)!"
        else:
            room['message'] = f"{players[nt]['name']} drew a card."

    process_turn_start(room, room_code, nt)

    # Award gems if bot game just ended with human winning
    if room.get('winner') and room.get('is_bot'):
        human_name = players[0]['name']
        if room['winner'] == human_name:
            username = room.get('human_username')
            if username:
                amt = GEM_REWARDS.get(room.get('bot_difficulty'), 0)
                _award_gems(username, amt, room.get('bot_difficulty'))
                socketio.emit('gem_reward', {'amount': amt, 'difficulty': room.get('bot_difficulty')},
                              to=players[0]['sid'])
        else:
            username = room.get('human_username')
            if username:
                _record_loss(username)

    broadcast_state(room_code)

    if room.get('is_bot') and nt == 1 and not room.get('winner'):
        socketio.start_background_task(bot_execute_turn, room_code)

def _award_gems(username, amount, difficulty):
    users = load_users()
    if username in users:
        users[username]['gems'] = users[username].get('gems', 0) + amount
        users[username]['wins'] = users[username].get('wins', 0) + 1
        save_users(users)

def _record_loss(username):
    users = load_users()
    if username in users:
        users[username]['losses'] = users[username].get('losses', 0) + 1
        save_users(users)

# ═══════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/decks')
def deck_info():
    return {'decks': DECK_INFO}

# ═══════════════════════════════════════════════════════════════
#  SOCKET EVENTS
# ═══════════════════════════════════════════════════════════════

@socketio.on('verify_access')
def on_verify_access(data):
    emit('access_granted' if data.get('code','').upper()==ACCESS_CODE else 'access_denied')

@socketio.on('register')
def on_register(data):
    username = data.get('username','').strip()
    password = data.get('password','').strip()
    if not username or not password:
        emit('auth_error', {'msg': 'Username and password required.'}); return
    if len(username) < 2 or len(username) > 20:
        emit('auth_error', {'msg': 'Username must be 2–20 characters.'}); return
    users = load_users()
    if username in users:
        emit('auth_error', {'msg': 'Username already taken.'}); return
    users[username] = {
        'pw_hash': hash_pw(password), 'gems': STARTING_GEMS,
        'owned_decks': ['basic'], 'wins': 0, 'losses': 0,
        'player_id': _gen_player_id()
    }
    save_users(users)
    emit('auth_ok', {'username': username, **user_public(users[username])})

@socketio.on('login')
def on_login(data):
    username = data.get('username','').strip()
    password = data.get('password','').strip()
    users = load_users()
    match = next((k for k in users if k.lower() == username.lower()), None)
    if not match or users[match]['pw_hash'] != hash_pw(password):
        emit('auth_error', {'msg': 'Invalid username or password.'}); return
    if 'player_id' not in users[match]:
        users[match]['player_id'] = _gen_player_id()
        save_users(users)
    emit('auth_ok', {'username': match, **user_public(users[match])})

@socketio.on('search_player')
def on_search_player(data):
    pid = data.get('player_id', '').strip().upper()
    if not pid:
        emit('player_found', {'found': False}); return
    users = load_users()
    match_key = next((k for k, v in users.items() if v.get('player_id') == pid), None)
    if not match_key:
        emit('player_found', {'found': False}); return
    u = users[match_key]
    emit('player_found', {
        'found': True, 'username': match_key,
        'player_id': pid,
        'wins': u.get('wins', 0), 'losses': u.get('losses', 0),
        'gems': u.get('gems', 0),
    })

@socketio.on('admin_login')
def on_admin_login(data):
    if data.get('code') != ADMIN_CODE:
        emit('admin_error', {'msg': 'Invalid admin code.'}); return
    users = load_users()
    player_list = sorted([
        {'username': k, 'player_id': v.get('player_id','???????'),
         'wins': v.get('wins', 0), 'losses': v.get('losses', 0),
         'gems': v.get('gems', 0)}
        for k, v in users.items()
    ], key=lambda x: x['username'].lower())
    emit('admin_ok', {'players': player_list})

@socketio.on('admin_set_gems')
def on_admin_set_gems(data):
    if data.get('code') != ADMIN_CODE:
        emit('admin_error', {'msg': 'Invalid admin code.'}); return
    username = data.get('username', '').strip()
    try: amount = int(data.get('amount', 0))
    except: emit('admin_error', {'msg': 'Invalid amount.'}); return
    users = load_users()
    if username not in users:
        emit('admin_error', {'msg': f'User "{username}" not found.'}); return
    users[username]['gems'] = max(0, amount)
    save_users(users)
    emit('admin_set_ok', {'username': username, 'gems': users[username]['gems']})

@socketio.on('buy_deck')
def on_buy_deck(data):
    username = data.get('username')
    deck_id  = data.get('deck_id')
    users = load_users()
    if username not in users:
        emit('buy_error', {'msg': 'Not logged in.'}); return
    u = users[username]
    deck = next((d for d in DECK_INFO if d['id'] == deck_id), None)
    if not deck:
        emit('buy_error', {'msg': 'Unknown deck.'}); return
    if deck_id in u.get('owned_decks', []):
        emit('buy_error', {'msg': 'Already owned.'}); return
    if u['gems'] < deck['cost']:
        emit('buy_error', {'msg': f"Not enough gems. Need {deck['cost']}, have {u['gems']}."}); return
    u['gems'] -= deck['cost']
    u.setdefault('owned_decks', ['basic']).append(deck_id)
    save_users(users)
    emit('buy_ok', {'gems': u['gems'], 'owned_decks': u['owned_decks']})

@socketio.on('create_room')
def on_create_room(data):
    name     = data.get('name','Player').strip() or 'Player'
    deck     = data.get('deck', 'basic')
    username = data.get('username')
    code     = make_room_code()
    room     = new_room()
    users    = load_users()
    pid      = users.get(username, {}).get('player_id') if username else None
    room['players'].append({
        'sid': request.sid, 'name': name, 'player_id': pid,
        'hand': deal_hand(deck), 'field': [], 'hp': 20
    })
    room['player_deck']     = {0: deck}
    room['human_username']  = username
    rooms[code] = room
    sio_join_room(code)
    emit('room_created', {'code': code})

@socketio.on('join_game')
def on_join_game(data):
    name = data.get('name','Player').strip() or 'Player'
    code = data.get('code','').upper()
    deck = data.get('deck', 'basic')
    if code not in rooms:
        emit('room_error', {'msg': f'Room "{code}" not found.'}); return
    room = rooms[code]
    if len(room['players']) >= 2:
        emit('room_error', {'msg': 'Room is full.'}); return
    if room['state'] != 'waiting':
        emit('room_error', {'msg': 'Game already started.'}); return
    username2 = data.get('username')
    users2    = load_users()
    pid2      = users2.get(username2, {}).get('player_id') if username2 else None
    room['players'].append({
        'sid': request.sid, 'name': name, 'player_id': pid2,
        'hand': deal_hand(deck), 'field': [], 'hp': 20
    })
    room.setdefault('player_deck', {})[1] = deck
    sio_join_room(code)
    first = random.randint(0, 1)
    room.update({'current_turn': first, 'state': 'playing',
                 'phase': 'play', 'cards_played': 0,
                 'message': f"{room['players'][first]['name']} goes first!"})
    for i, p in enumerate(room['players']):
        socketio.emit('game_start', {
            'your_index': i, 'room_code': code,
            'first_player': room['players'][first]['name'],
            'coin': 'heads' if first == 0 else 'tails',
        }, to=p['sid'])
    broadcast_state(code)

@socketio.on('start_bot_game')
def on_start_bot_game(data):
    name       = data.get('name','Player').strip() or 'Player'
    difficulty = data.get('difficulty', 'easy')
    deck       = data.get('deck', 'basic')
    username   = data.get('username')
    from cards import BOT_NAMES, BOT_DECKS
    bot_name   = BOT_NAMES.get(difficulty, 'Bot 🤖')
    bot_deck   = BOT_DECKS.get(difficulty, 'basic')
    code = make_room_code()
    room = new_room()
    room['is_bot']           = True
    room['bot_difficulty']   = difficulty
    room['human_username']   = username
    room['players'] = [
        {'sid': request.sid, 'name': name,
         'hand': deal_hand(deck), 'field': [], 'hp': 20},
        {'sid': 'BOT', 'name': bot_name,
         'hand': deal_hand(bot_deck), 'field': [], 'hp': 20},
    ]
    room['player_deck'] = {0: deck, 1: bot_deck}
    first = random.randint(0, 1)
    room.update({'current_turn': first, 'state': 'playing',
                 'phase': 'play', 'cards_played': 0,
                 'message': f"{'You go' if first==0 else bot_name+' goes'} first!"})
    rooms[code] = room
    sio_join_room(code)
    emit('game_start', {
        'your_index': 0, 'room_code': code,
        'first_player': room['players'][first]['name'],
        'coin': 'heads' if first == 0 else 'tails',
        'is_bot_game': True, 'difficulty': difficulty,
        'gem_reward': GEM_REWARDS.get(difficulty, 0),
    })
    broadcast_state(code)
    if first == 1:
        socketio.start_background_task(bot_execute_turn, code)

@socketio.on('play_card')
def on_play_card(data):
    room_code = data.get('room'); ci = data.get('card_index')
    room = rooms.get(room_code)
    if not room: return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi != room['current_turn']: return
    if room['phase'] != 'play': return
    if room['cards_played'] >= 2:
        emit('error_msg', {'msg': 'Already played 2 cards this turn.'}); return
    player = players[pi]
    if len(player['field']) >= 4:
        emit('error_msg', {'msg': 'Field is full (max 4).'}); return
    if ci < 0 or ci >= len(player['hand']): return
    if player['hand'][ci].get('no_normal_play'):
        emit('error_msg', {'msg': f"{player['hand'][ci]['name']} must be sacrifice-summoned — click it to open the ritual."}); return
    pending = {'type':'play_card','player_index':pi,'card_index':ci}
    if _defender_has_qe(room):
        _open_hand_trap(room, room_code, pending); return
    _exec_play_card(room, room_code, pi, ci)

@socketio.on('end_play_phase')
def on_end_play_phase(data):
    room_code = data.get('room'); room = rooms.get(room_code)
    if not room: return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi != room['current_turn'] or room['phase'] != 'play': return
    room['phase']   = 'attack'
    room['message'] = f"{players[pi]['name']}'s attack phase."
    broadcast_state(room_code)

@socketio.on('attack')
def on_attack(data):
    room_code = data.get('room'); ai = data.get('attacker_index'); ti = data.get('target_index')
    room = rooms.get(room_code)
    if not room: return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi != room['current_turn'] or room['phase'] != 'attack': return
    if ai >= len(players[pi]['field']): return
    if players[pi]['field'][ai].get('attacked'):
        emit('error_msg', {'msg': 'Already attacked.'}); return
    # Pull check: if opponent has a pull card active, must target it
    dpl_pull = players[1 - pi]
    pull_fi = next((fi for fi, c in enumerate(dpl_pull['field'])
                    if _has(c, 'atlas_bhh_pull') or _has(c, 'bhole_pull')), None)
    if pull_fi is not None and ti != pull_fi:
        emit('error_msg', {'msg': "An enemy pull card forces all attacks toward it!"}); return
    pending = {'type':'attack','player_index':pi,'attacker_index':ai,'target_index':ti}
    if _defender_has_qe(room):
        _open_hand_trap(room, room_code, pending); return
    _exec_attack(room, room_code, pi, ai, ti)

@socketio.on('quick_effect_response')
def on_qe_response(data):
    room_code = data.get('room'); use = data.get('use')
    room = rooms.get(room_code)
    if not room or room['phase'] != 'hand_trap_window': return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi == room['current_turn']: return
    pending = room.pop('pending_action', None)
    if use and pending:
        hand = players[pi]['hand']
        for i, c in enumerate(hand):
            if c['name'] == 'Clock': hand.pop(i); break
        room['quick_effect_used'][pi] = True
        room['phase']   = 'play' if pending['type']=='play_card' else 'attack'
        room['message'] = f"❄️ Clock's Quick Effect! Action cancelled."
        broadcast_state(room_code)
    elif pending:
        if pending['type'] == 'play_card':
            _exec_play_card(room, room_code, pending['player_index'], pending['card_index'])
        else:
            _exec_attack(room, room_code, pending['player_index'],
                         pending['attacker_index'], pending.get('target_index'))

@socketio.on('end_turn')
def on_end_turn(data):
    room_code = data.get('room'); room = rooms.get(room_code)
    if not room or room['state'] == 'finished': return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi != room['current_turn'] or room['phase'] != 'attack': return
    _do_end_turn(room, room_code, pi)
    # Award gems if game ended and human won
    if room.get('winner') and room.get('is_bot'):
        human_name = players[0]['name']
        if room['winner'] == human_name:
            username = room.get('human_username')
            if username:
                amt = GEM_REWARDS.get(room.get('bot_difficulty'), 0)
                users = load_users()
                if username in users:
                    users[username]['gems'] = users[username].get('gems',0) + amt
                    users[username]['wins']  = users[username].get('wins',0) + 1
                    save_users(users)
                socketio.emit('gem_reward',
                    {'amount': amt, 'difficulty': room.get('bot_difficulty'),
                     'total': users.get(username, {}).get('gems', amt)},
                    to=players[0]['sid'])

@socketio.on('use_ability')
def on_use_ability(data):
    room_code  = data.get('room')
    ability_id = data.get('ability_id')
    card_uid   = data.get('card_uid')
    target_uid = data.get('target_uid')
    room = rooms.get(room_code)
    if not room: return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi != room['current_turn']: return
    if room['phase'] not in ('play','attack'): return
    player = players[pi]; opp = players[1-pi]

    if ability_id == 'circus_bounce':
        _, cfi, ccard = _find_by_uid(players, card_uid)
        if ccard is None or not _has(ccard, 'circus_bounce'): return
        if ccard.get('frozen'): emit('error_msg',{'msg':'Card is frozen.'}); return
        if room['turn_count'] - ccard.get('last_bounce_turn',-99) < 2:
            emit('error_msg',{'msg':'Bounce on cooldown (once per 2 turns).'}); return
        t_pi,t_fi,t_card = _find_by_uid(players, target_uid)
        if t_pi != pi: emit('error_msg',{'msg':'Own cards only.'}); return
        if t_card.get('no_draw'): emit('error_msg',{'msg':'Cannot return this card.'}); return
        player['field'].pop(t_fi); player['hand'].append(t_card)
        ccard['last_bounce_turn'] = room['turn_count']
        room['message'] = f"🎪 {t_card['name']} returned to hand!"
        broadcast_state(room_code)

    elif ability_id in ('apple_buff','sword_buff'):
        _,sfi,scard = _find_by_uid(players, card_uid)
        shi = None
        if scard is None: _,shi,scard = _find_in_hand(players, card_uid)
        if scard is None or sfi is None and shi is None: return
        if scard.get('frozen'): emit('error_msg',{'msg':'Frozen.'}); return
        t_pi,t_fi,t_card = _find_by_uid(players, target_uid)
        if t_card is None: _,_,t_card = _find_in_hand(players, target_uid)
        if t_card is None: return
        if _has(t_card, 'golem_immune_friendly') and t_pi == pi:
            emit('error_msg', {'msg': 'Golem is immune to friendly effects.'}); return
        if ability_id == 'apple_buff':
            if t_card['name'] == 'Undying':
                _buff_atk(t_card, 2); t_card['def']+=2; t_card['lethal_block']=True
                room['message'] = "🍎 Apple on Undying: +2/+2 + lethal block!"
            else:
                t_card['def']+=2; _buff_atk(t_card, 1)
                room['message'] = f"🍎 Apple: {t_card['name']} +2 DEF +1 ATK!"
        else:
            _buff_atk(t_card, 2)
            room['message'] = f"⚔️ Sword: {t_card['name']} +2 ATK!"
        if sfi is not None: player['field'].pop(sfi)
        elif shi is not None: player['hand'].pop(shi)
        broadcast_state(room_code)

    elif ability_id == 'milk_summon':
        _,_,mc = _find_by_uid(players, card_uid)
        if mc is None or not _has(mc,'milk_summon'): return
        if mc.get('frozen'): emit('error_msg',{'msg':'Frozen.'}); return
        if mc.get('turns_on_field',0) < 1: emit('error_msg',{'msg':"Need 1 turn on field first."}); return
        if len(player['field']) >= 4: emit('error_msg',{'msg':'Field full.'}); return
        base = next((c for c in CARDLIST if c['name']=='Milktoken'),None)
        if base: player['field'].append(new_card(base)); room['message']="🥛 Milk Token summoned!"
        broadcast_state(room_code)

    elif ability_id == 'milk_drink':
        if not any(c['name']=='Clocksmilk' for c in player['field']):
            emit('error_msg',{'msg':"Clock's Milk must be alive."}); return
        t_pi,t_fi,t_card = _find_by_uid(players, target_uid)
        if t_pi != pi or t_card['name'] != 'Milktoken': return
        player['field'].pop(t_fi); player['hp']+=2
        room['message']="🥛 Milk Drink: +2 HP!"; broadcast_state(room_code)

    elif ability_id == 'greed_atlas':
        gc = next((c for c in player['field'] if _has(c,'greed_atlas')),None)
        if not gc or gc.get('frozen'): return
        if gc.get('atlas_used_turn') == room['turn_count']:
            emit('error_msg',{'msg':'Atlas summon: once per turn.'}); return
        if len(player['field']) >= 4: emit('error_msg',{'msg':'Field full.'}); return
        base = next((c for c in SPECIAL_CARDS if c['name']=='Atlas'),None)
        if base:
            player['hp']-=2; player['field'].append(new_card(base))
            gc['atlas_used_turn']=room['turn_count']
            room['message']="💰 Atlas summoned! -2 HP."; broadcast_state(room_code)

    elif ability_id == 'fisher_pull':
        _,_,fc = _find_by_uid(players, card_uid)
        if fc is None or not _has(fc,'fisher_pull'): return
        if fc.get('frozen'): emit('error_msg',{'msg':'Frozen.'}); return
        if fc.get('pull_used_turn')==room['turn_count']:
            emit('error_msg',{'msg':'Once per turn.'}); return
        fish_inv=fc.get('fish',[])
        if len(fish_inv)>=3: emit('error_msg',{'msg':'Fish storage full (max 3).'}); return
        result='light' if random.random()<0.5 else 'dark'
        fish_inv.append(result); fc['fish']=fish_inv
        fc['pull_used_turn']=room['turn_count']
        room['message']=f"🎣 {'🌟 Light' if result=='light' else '🌑 Dark'} Fish! ({len(fish_inv)}/3)"
        broadcast_state(room_code)

    elif ability_id == 'fisher_catch':
        _,_,fc = _find_by_uid(players, card_uid)
        if fc is None: return
        fish_type = data.get('fish_type')
        fish_inv  = fc.get('fish',[])
        if fish_type not in fish_inv:
            emit('error_msg',{'msg':f'No {fish_type} fish.'}); return
        fish_inv.remove(fish_type); fc['fish']=fish_inv
        t_pi,_,t_card = _find_by_uid(players, target_uid)
        if t_card is None: return
        if fish_type=='light':
            if _has(t_card, 'golem_immune_friendly') and t_pi == pi:
                emit('error_msg', {'msg': 'Golem is immune to friendly effects.'}); return
            t_card['def']+=2; room['message']=f"🌟 Light Fish: {t_card['name']} +2 DEF!"
        else:
            if t_pi==pi: emit('error_msg',{'msg':'Dark Fish targets enemy cards.'}); return
            t_card['atk']=max(0,t_card['atk']-2); t_card['dark_fish_turns']=3
            room['message']=f"🌑 Dark Fish: {t_card['name']} -2 ATK for 3 turns!"
        broadcast_state(room_code)

    elif ability_id == 'sad_send':
        sc = next((c for c in player['field'] if _has(c, 'sad_send')), None)
        if sc is None: return
        if sc.get('sad_sent'): emit('error_msg', {'msg': 'Pass On already used.'}); return
        if player['hp'] <= 3: emit('error_msg', {'msg': 'Not enough HP (need >3).'}); return
        player['hp'] -= 3
        player['field'].remove(sc)
        sc['sad_sent'] = True
        opp['field'].append(sc) if len(opp['field']) < 4 else player['field'].append(sc)
        room['message'] = f"💔 Sad Dream sent to opponent at cost of 3 HP!"
        broadcast_state(room_code)

    elif ability_id == 'frost_breath':
        ic = next((c for c in player['field'] if _has(c, 'frost_breath')), None)
        if ic is None: return
        if ic.get('frozen'): emit('error_msg', {'msg': 'Frozen.'}); return
        if ic.get('frost_breath_used_turn') == room['turn_count']:
            emit('error_msg', {'msg': 'Frost Breath: once per turn.'}); return
        for ec in opp['field']:
            ec['frozen'] = True; ec['freeze_by'] = pi; ec['freeze_turns'] = 1
            ec['frost_shield_turns'] = 2
        ic['frost_breath_used_turn'] = room['turn_count']
        room['message'] = f"🌬️ Frost Breath! All enemy cards frozen + 50% damage shield for 2 turns!"
        broadcast_state(room_code)

    elif ability_id == 'ice_cream_ability':
        ic2 = next((c for c in player['field'] if _has(c, 'ice_cream_ability')), None)
        if ic2 is None: return
        if ic2.get('frozen'): emit('error_msg', {'msg': 'Frozen.'}); return
        last = ic2.get('ice_cream_last_turn', -99)
        if room['turn_count'] - last < 5:
            emit('error_msg', {'msg': f"Ice Cream on cooldown ({5 - (room['turn_count'] - last)} turns)."}); return
        t_pi, _, t_card = _find_by_uid(players, target_uid)
        if t_card is None or t_pi != pi: return
        if _has(t_card, 'golem_immune_friendly'):
            emit('error_msg', {'msg': 'Golem is immune to friendly effects.'}); return
        _buff_atk(t_card, 2); t_card['def'] += 1
        t_card['ice_cream_atk'] = t_card.get('ice_cream_atk', 0) + 2
        t_card['ice_cream_def'] = t_card.get('ice_cream_def', 0) + 1
        t_card['ice_cream_turns'] = 2
        player['hp'] += 2
        ic2['ice_cream_last_turn'] = room['turn_count']
        room['message'] = f"🍦 {t_card['name']} gets Ice Cream! +2 ATK +1 DEF for 2 turns, +2 HP!"
        broadcast_state(room_code)

    elif ability_id == 'undying_donut':
        _,_,uc = _find_by_uid(players, card_uid)
        if uc is None or not _has(uc, 'undying_donut'): return
        if uc.get('frozen'): emit('error_msg', {'msg': 'Frozen.'}); return
        if uc.get('donut_used_turn') == room['turn_count']:
            emit('error_msg', {'msg': 'Donut: once per turn.'}); return
        t_pi, _, t_card = _find_by_uid(players, target_uid)
        if t_card is None or t_card['uid'] == uc['uid']: return
        if t_pi != pi: emit('error_msg', {'msg': 'Own cards only.'}); return
        if _has(t_card, 'golem_immune_friendly'):
            emit('error_msg', {'msg': 'Golem is immune to friendly effects.'}); return
        if t_card.get('donuts', 0) >= 2:
            emit('error_msg', {'msg': 'Max 2 donuts per card.'}); return
        _buff_atk(t_card, 1); t_card['def'] += 1
        t_card['donuts'] = t_card.get('donuts', 0) + 1
        uc['donut_used_turn'] = room['turn_count']
        room['message'] = f"🍩 {t_card['name']} +1/+1! ({t_card['donuts']}/2 donuts)"
        broadcast_state(room_code)

    elif ability_id == 'atlas_bhh_self_pull':
        _, sfi, scard = _find_by_uid(players, card_uid)
        if scard is None or sfi is None or not _has(scard, 'atlas_bhh_self_pull'): return
        if scard.get('gravity_well_used'):
            emit('error_msg', {'msg': 'Gravity Well already used.'}); return
        t_pi, t_fi, t_card = _find_by_uid(players, target_uid)
        if t_card is None or t_pi == pi:
            emit('error_msg', {'msg': 'Target enemy cards only.'}); return
        opp['field'].pop(t_fi)
        t_card['turns_on_field'] = 0
        opp['hand'].append(t_card)
        scard['gravity_well_used'] = True
        destroy_card(room, room_code, pi, sfi, bypass_guard=True, bypass_phoenix=True)
        room['message'] = f"🌌 Gravity Well! {t_card['name']} returned to opponent's hand. Atlas BHH self-destructed!"
        broadcast_state(room_code)

    elif ability_id == 'bhole_atlas_summon':
        bh = next((c for c in player['field'] if _has(c, 'bhole_atlas_summon')), None)
        if bh is None: return
        if bh.get('frozen'): emit('error_msg', {'msg': 'Frozen.'}); return
        if bh.get('atlas_summon_used_turn') == room['turn_count']:
            emit('error_msg', {'msg': 'Atlas Summon: once per turn.'}); return
        if len(player['field']) >= 4:
            emit('error_msg', {'msg': 'Field full.'}); return
        base = next((c for c in SPECIAL_CARDS if c['name'] == 'Atlas BHH'), None)
        if base:
            player['hp'] -= 4
            player['field'].append(new_card(base))
            bh['atlas_summon_used_turn'] = room['turn_count']
            room['message'] = f"🌌 Atlas BHH summoned! -4 HP."
            broadcast_state(room_code)

    elif ability_id == 'atlas_greed_nodraw':
        ag = next((c for c in player['field'] if _has(c, 'atlas_greed_nodraw')), None)
        if ag is None: return
        if ag.get('frozen'): emit('error_msg', {'msg': 'Frozen.'}); return
        if room['turn_count'] - ag.get('nodraw_last_turn', -99) < 2:
            emit('error_msg', {'msg': 'Lockout: once per 2 turns.'}); return
        opp['force_no_draw'] = True
        ag['nodraw_last_turn'] = room['turn_count']
        room['message'] = f"🔒 Lockout! {opp['name']} cannot draw next turn!"
        broadcast_state(room_code)

    elif ability_id == 'angel_emp':
        ang = next((c for c in player['field'] if _has(c, 'angel_emp')), None)
        if ang is None: return
        if ang.get('emp_used'):
            emit('error_msg', {'msg': 'E.M.P. already used.'}); return
        if ang['def'] > 10:
            emit('error_msg', {'msg': 'E.M.P. requires DEF ≤ 10.'}); return
        if player['hp'] >= 10:
            emit('error_msg', {'msg': 'E.M.P. requires HP below half (< 10).'}); return
        for p in players:
            for c in p['field']:
                if c['uid'] != ang['uid']:
                    c['emp_turns'] = 4
        ang['emp_used'] = True
        room['message'] = "⚡ E.M.P.! All other card effects suspended for 4 turns!"
        broadcast_state(room_code)

    elif ability_id == 'core_dark_star':
        _,_,sc2 = _find_by_uid(players, card_uid)
        if sc2 is None or not _has(sc2,'core_dark_star'): return
        if sc2.get('frozen'): emit('error_msg',{'msg':'Frozen.'}); return
        if room['turn_count']-sc2.get('last_star_turn',-99) < 2:
            emit('error_msg',{'msg':'Dark Star: once per 2 turns.'}); return
        t_pi,_,t_card = _find_by_uid(players, target_uid)
        if t_pi==pi: emit('error_msg',{'msg':'Targets enemy cards.'}); return
        if _has(t_card,'duraza_def_lock'): emit('error_msg',{'msg':'Immune.'}); return
        stars=t_card.get('dark_stars',0)
        if stars>=4: emit('error_msg',{'msg':'Max 4 Dark Stars.'}); return
        t_card['dark_stars']=stars+1; sc2['last_star_turn']=room['turn_count']
        room['message']=f"🌑 Dark Star on {t_card['name']}! ({t_card['dark_stars']} stars)"
        broadcast_state(room_code)

@socketio.on('sacrifice_summon')
def on_sacrifice_summon(data):
    room_code     = data.get('room')
    target_name   = data.get('target_name', '').strip()
    hand_card_idx = data.get('hand_card_index')
    field_sacs    = sorted(set(data.get('field_sacs', [])))
    hand_sacs     = sorted(set(data.get('hand_sacs', [])))

    room = rooms.get(room_code)
    if not room: return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi != room['current_turn'] or room['phase'] != 'play': return
    if room['cards_played'] >= 2:
        emit('error_msg', {'msg': 'Already played 2 cards this turn.'}); return

    player = players[pi]
    if len(player['field']) >= 4:
        emit('error_msg', {'msg': 'Field is full (max 4).'}); return
    if any(i < 0 or i >= len(player['field']) for i in field_sacs):
        emit('error_msg', {'msg': 'Invalid field sacrifice.'}); return
    if any(i < 0 or i >= len(player['hand']) for i in hand_sacs):
        emit('error_msg', {'msg': 'Invalid hand sacrifice.'}); return

    def _can_sac(card, for_trio=False):
        if _has(card, 'no_sacrifice'): return False
        if _has(card, 'sword_nosac') and not for_trio: return False
        return True

    # ── Hand-card sacrifice summons (Ace / Lich / Omega / Black Hole) ──
    if hand_card_idx is not None:
        if hand_card_idx < 0 or hand_card_idx >= len(player['hand']): return
        card_in_hand = player['hand'][hand_card_idx]
        if card_in_hand['name'] != target_name or not card_in_hand.get('no_normal_play'):
            emit('error_msg', {'msg': 'Invalid ritual card.'}); return
        req = {'Ace': 2, 'Lich': 3, 'Omega': 3, 'Black Hole': 3}.get(target_name)
        if req is None:
            emit('error_msg', {'msg': 'Unknown ritual card.'}); return
        if len(field_sacs) != req:
            emit('error_msg', {'msg': f'Must sacrifice exactly {req} field cards.'}); return
        for fi in field_sacs:
            if not _can_sac(player['field'][fi]):
                emit('error_msg', {'msg': f"{player['field'][fi]['name']} cannot be sacrificed."}); return
        for fi in sorted(field_sacs, reverse=True):
            destroy_card(room, room_code, pi, fi, bypass_guard=True, bypass_phoenix=True, skip_on_destroy=True)
        hand_card = player['hand'].pop(hand_card_idx)
        hand_card['attacked'] = False; hand_card['turns_on_field'] = 0
        if _has(hand_card, 'omega_atk_lock'):
            hand_card['base_atk'] = hand_card.get('atk', 0)
        player['field'].append(hand_card)
        room['cards_played'] += 1
        room['message'] = f"✨ {player['name']} ritual-summoned {target_name}!"
        broadcast_state(room_code); return

    # ── Special summons (Trio-Sword / The Star / Angel of End) ──
    base = next((c for c in SPECIAL_CARDS if c['name'] == target_name), None)
    if base is None:
        emit('error_msg', {'msg': 'Unknown special summon.'}); return

    if target_name == 'Trio-Sword':
        if len(field_sacs) != 3:
            emit('error_msg', {'msg': 'Trio-Sword: Sword + 2 other field cards required.'}); return
        sword_fi = next((fi for fi in field_sacs if player['field'][fi]['name'] == 'Sword'), None)
        if sword_fi is None:
            emit('error_msg', {'msg': 'Must include Sword in sacrifice.'}); return
        for fi in field_sacs:
            if fi != sword_fi and not _can_sac(player['field'][fi], for_trio=False):
                emit('error_msg', {'msg': f"{player['field'][fi]['name']} cannot be sacrificed."}); return

    elif target_name == 'The Star':
        if len(field_sacs) != 3:
            emit('error_msg', {'msg': 'The Star: Sun + 2 other field cards required.'}); return
        sun_fi = next((fi for fi in field_sacs if player['field'][fi]['name'] == 'Sun'), None)
        if sun_fi is None:
            emit('error_msg', {'msg': 'Must include Sun in sacrifice.'}); return
        for fi in field_sacs:
            if fi != sun_fi and not _can_sac(player['field'][fi]):
                emit('error_msg', {'msg': f"{player['field'][fi]['name']} cannot be sacrificed."}); return

    elif target_name == 'Angel of End':
        if len(field_sacs) + len(hand_sacs) != 4:
            emit('error_msg', {'msg': 'Angel of End: exactly 4 sacrifices required.'}); return
        evo_count = sum(1 for fi in field_sacs if player['field'][fi].get('evo'))
        if evo_count < 2:
            emit('error_msg', {'msg': 'Angel of End: need at least 2 evo cards from field.'}); return
        for fi in field_sacs:
            if not _can_sac(player['field'][fi]):
                emit('error_msg', {'msg': f"{player['field'][fi]['name']} cannot be sacrificed."}); return
        for hi in hand_sacs:
            if _has(player['hand'][hi], 'no_sacrifice'):
                emit('error_msg', {'msg': f"{player['hand'][hi]['name']} cannot be sacrificed."}); return
    else:
        emit('error_msg', {'msg': 'Cannot special summon that card.'}); return

    for fi in sorted(field_sacs, reverse=True):
        destroy_card(room, room_code, pi, fi, bypass_guard=True, bypass_phoenix=True, skip_on_destroy=True)
    for hi in sorted(hand_sacs, reverse=True):
        player['hand'].pop(hi)
    new_c = new_card(base)
    player['field'].append(new_c)
    room['cards_played'] += 1
    room['message'] = f"✨ {player['name']} summoned {target_name}!"
    broadcast_state(room_code)

@socketio.on('disconnect')
def on_disconnect():
    for code, room in list(rooms.items()):
        for player in room['players']:
            if player['sid'] == request.sid:
                room['state'] = 'finished'
                for other in room['players']:
                    if other['sid'] != request.sid and other['sid'] != 'BOT':
                        socketio.emit('opponent_left', {}, to=other['sid'])
                break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
