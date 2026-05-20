from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room as sio_join_room
import random, string, copy, uuid
from cards import CARDLIST, SPECIAL_CARDS, ALL_CARDS

ACCESS_CODE = "CLOCKPAPI"
app = Flask(__name__)
app.config['SECRET_KEY'] = 'clockpapi-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
rooms = {}

# ═══════════════════════════════════════════════════════════════
#  CARD HELPERS
# ═══════════════════════════════════════════════════════════════

def new_card(base):
    c = copy.deepcopy(base)
    c['uid']           = str(uuid.uuid4())[:8]
    c['attacked']      = False
    c['frozen']        = False
    c['turns_on_field']= 0
    c['hit_this_turn'] = 0
    if 'block' not in c:
        c['block'] = 0
    if _has(c, 'guard_immunity'):
        c['guard_remaining'] = 2
    if _has(c, 'v18_reroll'):
        c['atk'] = random.randint(0, 8)
    return c

def deal_hand(k=5):
    drawable = [c for c in CARDLIST if not c.get('no_draw')]
    return [new_card(random.choice(drawable)) for _ in range(k)]

def draw_one():
    drawable = [c for c in CARDLIST if not c.get('no_draw')]
    return new_card(random.choice(drawable))

def _has(card, sid):
    return any(s['id'] == sid for s in card.get('specials', []))

def _find_by_uid(players, uid):
    """Return (player_index, field_index, card) or (None,None,None)."""
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
        'players':           [],
        'state':             'waiting',
        'current_turn':      0,
        'first_turns':       [True, True],
        'phase':             'waiting',
        'cards_played':      0,
        'quick_effect_used': [False, False],
        'pending_action':    None,
        'message':           'Waiting for opponent...',
        'winner':            None,
        'turn_count':        0,
        'ability_pending':   None,
    }

# ═══════════════════════════════════════════════════════════════
#  DESTROY SYSTEM
# ═══════════════════════════════════════════════════════════════

def destroy_card(room, room_code, owner_index, field_index, bypass_guard=False, bypass_phoenix=False, skip_on_destroy=False):
    """
    Remove a card from the field and trigger on-destroy effects.
    Returns True if destroyed, False if blocked (guard / phoenix revive).
    """
    players = room['players']
    player  = players[owner_index]
    opp     = players[1 - owner_index]

    if field_index >= len(player['field']):
        return False
    card = player['field'][field_index]

    # Guard immunity
    if not bypass_guard and card.get('guard_remaining', 0) > 0:
        return False

    # Phoenix auto-revive
    if not bypass_phoenix and _has(card, 'phoenix_revive') and not card.get('revived'):
        base = next((c for c in SPECIAL_CARDS if c['name'] == 'Phoenix'), None)
        card['def']     = base['def'] if base else 6
        card['revived'] = True
        card['burn_turns'] = 0
        return False

    player['field'].pop(field_index)

    if skip_on_destroy:
        return True

    # ── On-destroy effects ──
    if _has(card, 'love_heal'):
        player['hp'] += 4

    if _has(card, 'equal_revenge') and card.get('turns_on_field', 0) <= 4:
        player['hp'] -= 4
        opp['hp']    -= 4

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
                ec['block']          = 0
                ec['block_disabled'] = True
                removed += 1
        if removed:
            opp['hp'] -= removed

    # Clamp HPs
    for p in players:
        if p['hp'] <= 0:
            p['hp'] = 0
            if not room.get('winner'):
                winner_index = 1 - players.index(p)
                room['winner'] = players[winner_index]['name']
                room['state']  = 'finished'

    return True

# ═══════════════════════════════════════════════════════════════
#  TURN EFFECTS
# ═══════════════════════════════════════════════════════════════

def process_turn_start(room, room_code, active_index):
    """Run all start-of-turn passive effects."""
    players = room['players']
    active  = players[active_index]
    opp     = players[1 - active_index]
    msgs    = []

    # ── Active player's field ──
    greed_draw_done  = False
    greed_decay_done = False
    sun_done         = False

    for card in list(active['field']):
        tof = card.get('turns_on_field', 0)

        # Star reroll
        if _has(card, 'star_reroll'):
            r = random.random()
            if r < 0.2:
                pass
            elif r < 0.6:
                card['def'] = 6
                msgs.append(f"⭐ {card['name']} rerolled: +6 DEF!")
            else:
                card['atk'] = 6
                msgs.append(f"⭐ {card['name']} rerolled: +6 ATK!")

        # Wrath rage
        if _has(card, 'wrath_rage'):
            cap = card.get('atk_max', 6)
            if card['atk'] < cap:
                card['atk'] = min(card['atk'] + 1, cap)
                msgs.append(f"😡 {card['name']} Rage! ATK→{card['atk']}")

        # Health regen (every 2 turns on field)
        if _has(card, 'health_regen') and tof > 0 and tof % 2 == 0:
            active['hp'] += 4
            msgs.append(f"💚 {card['name']} heals {active['name']} for 4!")

        # Greed draw (once even if multiple Greeds)
        if _has(card, 'greed_draw') and not greed_draw_done and not room['first_turns'][active_index]:
            drawn = draw_one()
            active['hand'].append(drawn)
            greed_draw_done = True
            msgs.append(f"💰 Greed: {active['name']} draws an extra card!")

        # Greed decay (once per turn)
        if _has(card, 'greed_decay') and not greed_decay_done:
            for c in active['field']:
                if not _has(c, 'duraza_def_lock'):
                    c['def'] = max(c['def'] - 1, -5)
            greed_decay_done = True
            msgs.append(f"💀 Greed Decay: all your cards lose 1 DEF!")

        # Undying donut
        if _has(card, 'undying_donut'):
            eligible = [c for c in active['field']
                        if c['uid'] != card['uid'] and c.get('donuts', 0) < 2]
            if eligible:
                target = eligible[0]
                target['atk'] += 1
                target['def'] += 1
                target['donuts'] = target.get('donuts', 0) + 1
                msgs.append(f"🍩 {card['name']} gives donut to {target['name']}!")

        # Sun AoE (once per turn)
        if _has(card, 'sun_aoe') and not sun_done:
            for ec in list(opp['field']):
                if not _has(ec, 'aoe_immune') and not _has(ec, 'duraza_def_lock'):
                    ec['def'] -= 1
            sun_done = True
            msgs.append(f"☀️ Sun deals 1 damage to all enemy cards!")

        # CancelBlock recharge (every 4 turns)
        if _has(card, 'block_recharge') and tof > 0 and tof % 4 == 0:
            cap = card.get('block_max', 3)
            if card.get('block', 0) < cap and not card.get('block_disabled'):
                card['block'] = min(card.get('block', 0) + 1, cap)
                msgs.append(f"🛡️ {card['name']} recharges 1 block!")

    # ── Both sides: status ticks ──
    for pi, p in enumerate(players):
        for card in list(p['field']):
            # Burn tick
            if card.get('burn_turns', 0) > 0:
                card['def'] -= 1
                card['burn_turns'] -= 1
                msgs.append(f"🔥 {card['name']} burns! DEF→{card['def']}")

            # Dark stars tick
            if card.get('dark_stars', 0) > 0:
                card['def'] -= card['dark_stars']
                msgs.append(f"🌑 {card['name']} loses {card['dark_stars']} DEF from Dark Stars!")

            # Decrement guard
            if card.get('guard_remaining', 0) > 0:
                card['guard_remaining'] -= 1

    # ── Check deaths from passive effects ──
    for pi in range(2):
        i = 0
        while i < len(players[pi]['field']):
            card = players[pi]['field'][i]
            if card['def'] <= 0 and card.get('guard_remaining', 0) == 0:
                destroyed = destroy_card(room, room_code, pi, i)
                if not destroyed:
                    i += 1
            else:
                i += 1

    # Reset per-turn hit trackers
    for p in players:
        for card in p['field']:
            card['hit_this_turn'] = 0

    if msgs:
        room['message'] = ' | '.join(msgs[:4])

# ═══════════════════════════════════════════════════════════════
#  INCREMENT TURNS ON FIELD
# ═══════════════════════════════════════════════════════════════

def increment_turns(room):
    for p in room['players']:
        for card in p['field']:
            card['turns_on_field'] = card.get('turns_on_field', 0) + 1

# ═══════════════════════════════════════════════════════════════
#  ATTACK EXECUTION
# ═══════════════════════════════════════════════════════════════

def apply_damage_to_card(room, room_code, target_card, damage, owner_index,
                          bypass_guard=False, bypass_block=False, is_aoe=False):
    """
    Apply `damage` to a card. Returns actual damage dealt.
    Handles block, guard, duraza hit limit, duraza def lock (for specials).
    Does NOT destroy the card — caller checks def <= 0.
    """
    # AoE immune
    if is_aoe and _has(target_card, 'aoe_immune'):
        return 0

    # Guard
    if not bypass_guard and target_card.get('guard_remaining', 0) > 0:
        return 0

    # Duraza hit limit
    if _has(target_card, 'duraza_hit_limit'):
        if target_card.get('hit_this_turn', 0) >= 1:
            return 0
        target_card['hit_this_turn'] = target_card.get('hit_this_turn', 0) + 1

    # Block absorbs first
    if not bypass_block and target_card.get('block', 0) > 0:
        absorbed = min(target_card['block'], damage)
        target_card['block'] -= absorbed
        damage -= absorbed

    target_card['def'] -= damage
    return damage

def _exec_attack(room, room_code, player_index, attacker_idx, target_idx):
    players         = room['players']
    attacker_player = players[player_index]
    defender_player = players[1 - player_index]

    if attacker_idx >= len(attacker_player['field']):
        room['phase'] = 'attack'; broadcast_state(room_code); return

    atk_card = attacker_player['field'][attacker_idx]
    msgs = []

    # ── Side AoE attack ──
    if _has(atk_card, 'side_aoe'):
        for ec in list(defender_player['field']):
            apply_damage_to_card(room, room_code, ec, atk_card['atk'], 1 - player_index,
                                 is_aoe=True)
        msgs.append(f"{atk_card['name']} sweeps all enemy cards!")
        # Check deaths
        _check_deaths(room, room_code, 1 - player_index)

        # Hate self-damage on AoE still triggers
        if _has(atk_card, 'hate_selfdmg'):
            attacker_player['hp'] -= atk_card['atk']
            msgs.append(f"{atk_card['name']}'s Bloodlust hits own player for {atk_card['atk']}!")

        atk_card['attacked'] = True
        room['message'] = ' | '.join(msgs)
        room['phase'] = 'attack'
        broadcast_state(room_code)
        return

    # ── Direct attack ──
    if target_idx is None:
        # Wrath has direct attack, otherwise check field is empty
        if not _has(atk_card, 'wrath_direct') and defender_player['field']:
            room['message'] = "Can't attack directly — opponent has cards on the field."
            room['phase'] = 'attack'; broadcast_state(room_code); return

        dmg = atk_card['atk']
        defender_player['hp'] -= dmg
        msgs.append(f"{atk_card['name']} deals {dmg} direct damage to {defender_player['name']}!")

        if _has(atk_card, 'hate_selfdmg'):
            attacker_player['hp'] -= dmg
            msgs.append(f"Bloodlust: {attacker_player['name']} also takes {dmg}!")

        atk_card['attacked'] = True
        _clamp_and_check_winner(room, players, attacker_player, defender_player)
        room['message'] = ' | '.join(msgs)
        room['phase'] = 'attack'
        broadcast_state(room_code)
        return

    # ── Attack a specific card ──
    if target_idx >= len(defender_player['field']):
        room['phase'] = 'attack'; broadcast_state(room_code); return

    target = defender_player['field'][target_idx]
    damage = atk_card['atk']

    # Mirror reflect
    if _has(target, 'mirror_reflect') and target.get('guard_remaining', 0) == 0:
        # Mirror takes damage
        target['def'] -= damage
        msgs.append(f"🪞 Mirror reflects {damage} back at {atk_card['name']}!")
        # Attacker takes reflected damage (bypasses everything)
        atk_card['def'] -= damage
        # Check attacker death (no on-destroy effects from reflection)
        if atk_card['def'] <= 0:
            idx = attacker_player['field'].index(atk_card)
            destroy_card(room, room_code, player_index, idx, bypass_guard=True)
            msgs.append(f"{atk_card['name']} was destroyed by reflection!")
        # Check mirror death
        if target['def'] <= 0:
            destroy_card(room, room_code, 1 - player_index, target_idx)
            msgs.append(f"Mirror was destroyed!")
        atk_card['attacked'] = True
        room['message'] = ' | '.join(msgs)
        room['phase'] = 'attack'
        broadcast_state(room_code)
        return

    # Bolt pierce: damage goes to both card and player, ignoring DEF/block
    if _has(atk_card, 'bolt_pierce'):
        target['def'] -= damage
        defender_player['hp'] -= damage
        msgs.append(f"⚡ {atk_card['name']} pierces {target['name']} for {damage}! Player also takes {damage}!")
    else:
        # Standard damage (with block and guard)
        actual = apply_damage_to_card(room, room_code, target, damage, 1 - player_index)
        if actual == 0:
            msgs.append(f"{target['name']} blocked the attack!")
        else:
            msgs.append(f"{atk_card['name']} hits {target['name']} for {actual}! DEF→{target['def']}")

    # Duraza double strike (second hit)
    if _has(atk_card, 'duraza_dual'):
        second = apply_damage_to_card(room, room_code, target, damage, 1 - player_index)
        if second > 0:
            msgs.append(f"Double Strike! Hits again for {second}!")

    # Apply freeze (Clock)
    if _has(atk_card, 'freeze') and not target.get('frozen'):
        target['frozen']       = True
        target['freeze_by']    = player_index
        target['freeze_turns'] = 1
        msgs.append(f"❄️ {target['name']} is frozen!")

    # Phoenix burn
    if _has(atk_card, 'phoenix_burn'):
        if not target.get('burn_turns', 0) > 0:
            target['burn_turns'] = 3
        else:
            target['burn_turns'] = 3  # Reset timer
        msgs.append(f"🔥 {target['name']} is burning!")

    # Hate self-damage
    if _has(atk_card, 'hate_selfdmg'):
        attacker_player['hp'] -= damage
        msgs.append(f"Bloodlust: {attacker_player['name']} takes {damage}!")

    # Check if target destroyed
    target_destroyed = False
    if target['def'] <= 0 and target.get('guard_remaining', 0) == 0:
        # Excess damage to player
        excess = abs(target['def'])
        destroyed = destroy_card(room, room_code, 1 - player_index, target_idx)
        if destroyed:
            target_destroyed = True
            msgs.append(f"{target['name']} destroyed!")
            if excess > 0 and not _has(atk_card, 'side_aoe'):
                defender_player['hp'] -= excess
                msgs.append(f"{excess} excess damage to {defender_player['name']}!")
            # Diamond stat gain
            if _has(atk_card, 'diamond_gain') and atk_card in attacker_player['field']:
                atk_card['atk'] += 1
                atk_card['def'] += 1
                msgs.append(f"💎 {atk_card['name']} gains +1/+1!")

    atk_card['attacked'] = True
    _clamp_and_check_winner(room, players, attacker_player, defender_player)
    room['message'] = ' | '.join(msgs[:5])
    room['phase'] = 'attack'
    broadcast_state(room_code)

def _exec_play_card(room, room_code, player_index, card_index):
    player = room['players'][player_index]
    if card_index >= len(player['hand']): return
    card = player['hand'].pop(card_index)
    card['attacked']       = False
    card['turns_on_field'] = 0
    # v1-8 reroll on summon
    if _has(card, 'v18_reroll'):
        card['atk'] = random.randint(0, 8)
    player['field'].append(card)
    room['cards_played'] += 1
    room['phase']   = 'play'
    room['message'] = f"{player['name']} played {card['name']}."
    broadcast_state(room_code)

def _check_deaths(room, room_code, player_index):
    players = room['players']
    i = 0
    while i < len(players[player_index]['field']):
        card = players[player_index]['field'][i]
        if card['def'] <= 0 and card.get('guard_remaining', 0) == 0:
            d = destroy_card(room, room_code, player_index, i)
            if not d:
                i += 1
        else:
            i += 1

def _clamp_and_check_winner(room, players, attacker_player, defender_player):
    for p in players:
        if p['hp'] <= 0:
            p['hp'] = 0
            if not room.get('winner'):
                wi = players.index(attacker_player)
                room['winner'] = players[wi]['name']
                room['state']  = 'finished'

# ═══════════════════════════════════════════════════════════════
#  HAND TRAP HELPERS
# ═══════════════════════════════════════════════════════════════

def _defender_has_quick_effect(room):
    di = 1 - room['current_turn']
    if room['quick_effect_used'][di]: return False
    for card in room['players'][di]['hand']:
        if card['name'] == 'Clock' and not card.get('frozen'):
            return True
    return False

def _open_hand_trap(room, room_code, pending):
    actor   = room['players'][room['current_turn']]['name']
    dfender = room['players'][1 - room['current_turn']]['name']
    room['pending_action'] = pending
    room['phase']   = 'hand_trap_window'
    room['message'] = (f"{actor} is {_pending_desc(pending)}. "
                       f"{dfender}: Use Clock's Quick Effect?")
    broadcast_state(room_code)

def _pending_desc(p):
    if not p: return ''
    return 'playing a card' if p['type'] == 'play_card' else 'declaring an attack'

def _tick_freeze(room, ending_player_index):
    for p in room['players']:
        for card in p['field']:
            if card.get('frozen') and card.get('freeze_by') == ending_player_index:
                card['freeze_turns'] = card.get('freeze_turns', 1) - 1
                if card['freeze_turns'] <= 0:
                    card['frozen'] = False

# ═══════════════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════════════

def broadcast_state(room_code):
    room = rooms.get(room_code)
    if not room or len(room['players']) < 2: return
    players = room['players']
    for i, player in enumerate(players):
        opp = players[1 - i]
        is_ht_defender = (room['phase'] == 'hand_trap_window' and room['current_turn'] != i)
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
            'current_turn':     room['current_turn'],
            'phase':            room['phase'],
            'cards_played':     room['cards_played'],
            'message':          room.get('message', ''),
            'winner':           room.get('winner'),
            'hand_trap_prompt': is_ht_defender,
            'pending_desc':     _pending_desc(room.get('pending_action')),
        }, to=player['sid'])

# ═══════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

# ═══════════════════════════════════════════════════════════════
#  SOCKET EVENTS
# ═══════════════════════════════════════════════════════════════

@socketio.on('verify_access')
def on_verify_access(data):
    emit('access_granted' if data.get('code','').upper() == ACCESS_CODE else 'access_denied')

@socketio.on('create_room')
def on_create_room(data):
    name = data.get('name','Player 1').strip() or 'Player 1'
    code = make_room_code()
    room = new_room()
    room['players'].append({'sid': request.sid, 'name': name, 'hand': deal_hand(5), 'field': [], 'hp': 20})
    rooms[code] = room
    sio_join_room(code)
    emit('room_created', {'code': code})

@socketio.on('join_game')
def on_join_game(data):
    name = data.get('name','Player 2').strip() or 'Player 2'
    code = data.get('code','').upper()
    if code not in rooms:
        emit('room_error', {'msg': f'Room "{code}" not found.'}); return
    room = rooms[code]
    if len(room['players']) >= 2:
        emit('room_error', {'msg': 'Room is full.'}); return
    if room['state'] != 'waiting':
        emit('room_error', {'msg': 'Game already started.'}); return
    room['players'].append({'sid': request.sid, 'name': name, 'hand': deal_hand(5), 'field': [], 'hp': 20})
    sio_join_room(code)
    first = random.randint(0, 1)
    room.update({'current_turn': first, 'state': 'playing', 'phase': 'play',
                 'cards_played': 0, 'message': f"{room['players'][first]['name']} goes first!"})
    for i, p in enumerate(room['players']):
        socketio.emit('game_start', {'your_index': i, 'room_code': code,
            'first_player': room['players'][first]['name'],
            'coin': 'heads' if first == 0 else 'tails'}, to=p['sid'])
    broadcast_state(code)

@socketio.on('play_card')
def on_play_card(data):
    room_code  = data.get('room'); card_index = data.get('card_index')
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
    if card_index < 0 or card_index >= len(player['hand']): return
    pending = {'type': 'play_card', 'player_index': pi, 'card_index': card_index}
    if _defender_has_quick_effect(room):
        _open_hand_trap(room, room_code, pending); return
    _exec_play_card(room, room_code, pi, card_index)

@socketio.on('end_play_phase')
def on_end_play_phase(data):
    room_code = data.get('room'); room = rooms.get(room_code)
    if not room: return
    players = room['players']
    pi = next((i for i,p in enumerate(players) if p['sid']==request.sid), None)
    if pi is None or pi != room['current_turn']: return
    if room['phase'] != 'play': return
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
    if pi is None or pi != room['current_turn']: return
    if room['phase'] != 'attack': return
    if ai >= len(players[pi]['field']): return
    atk_card = players[pi]['field'][ai]
    if atk_card.get('attacked'):
        emit('error_msg', {'msg': f"{atk_card['name']} already attacked."}); return
    pending = {'type':'attack','player_index':pi,'attacker_index':ai,'target_index':ti}
    if _defender_has_quick_effect(room):
        _open_hand_trap(room, room_code, pending); return
    _exec_attack(room, room_code, pi, ai, ti)

@socketio.on('quick_effect_response')
def on_quick_effect_response(data):
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
            if c['name'] == 'Clock':
                hand.pop(i); break
        room['quick_effect_used'][pi] = True
        actor = players[room['current_turn']]['name']
        room['phase']   = 'play' if pending['type'] == 'play_card' else 'attack'
        room['message'] = f"❄️ Clock's Quick Effect! {actor}'s action was cancelled."
        broadcast_state(room_code)
    else:
        if not pending: return
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
    if pi is None or pi != room['current_turn']: return
    if room['phase'] != 'attack': return

    _tick_freeze(room, pi)
    for card in players[pi]['field']:
        card['attacked'] = False

    increment_turns(room)

    nt = 1 - pi
    room['current_turn']           = nt
    room['phase']                  = 'play'
    room['cards_played']           = 0
    room['quick_effect_used'][nt]  = False
    room['turn_count']             = room.get('turn_count', 0) + 1

    np_ = players[nt]
    if room['first_turns'][nt]:
        room['first_turns'][nt] = False
        room['message'] = f"{np_['name']}'s turn — no draw (first turn)."
    else:
        drawn = draw_one()
        np_['hand'].append(drawn)
        room['message'] = f"{np_['name']} drew a card."

    process_turn_start(room, room_code, nt)
    broadcast_state(room_code)

# ── Active Abilities ───────────────────────────────────────────

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
    if room['phase'] not in ('play', 'attack'): return

    player = players[pi]
    opp    = players[1 - pi]

    # ── Circus bounce (return field card to hand) ──
    if ability_id == 'circus_bounce':
        circus_pi, circus_fi, circus_card = _find_by_uid(players, card_uid)
        if circus_pi != pi or not _has(circus_card, 'circus_bounce'): return
        if circus_card.get('frozen'): emit('error_msg', {'msg': 'Card is frozen.'}); return
        last_use = circus_card.get('last_bounce_turn', -99)
        if room['turn_count'] - last_use < 2:
            emit('error_msg', {'msg': 'Bounce on cooldown (once per 2 turns).'}); return
        t_pi, t_fi, t_card = _find_by_uid(players, target_uid)
        if t_pi != pi: emit('error_msg', {'msg': 'Can only bounce your own cards.'}); return
        if t_card.get('no_draw'): emit('error_msg', {'msg': "That card can't be returned to hand."}); return
        player['field'].pop(t_fi)
        player['hand'].append(t_card)
        circus_card['last_bounce_turn'] = room['turn_count']
        room['message'] = f"🎪 {t_card['name']} returned to hand!"
        broadcast_state(room_code)

    # ── Apple/Sword buff (sacrifice from hand or field) ──
    elif ability_id in ('apple_buff', 'sword_buff'):
        # Find the Apple/Sword in hand or field
        src_pi, src_fi, src_card = _find_by_uid(players, card_uid)
        src_hi = None
        if src_card is None:
            src_pi, src_hi, src_card = _find_in_hand(players, card_uid)
        if src_pi != pi: return
        if src_card.get('frozen'): emit('error_msg', {'msg': 'Card is frozen.'}); return

        t_pi, t_fi, t_card = _find_by_uid(players, target_uid)
        if t_card is None:
            t_pi2, t_hi, t_card = _find_in_hand(players, target_uid)
            if t_card is None: emit('error_msg', {'msg': 'Target not found.'}); return

        if ability_id == 'apple_buff':
            if t_card['name'] == 'Undying':
                t_card['atk'] += 2; t_card['def'] += 2
                t_card['lethal_block'] = True
                room['message'] = f"🍎 Apple on Undying: +2/+2 + lethal block!"
            else:
                t_card['def'] += 2; t_card['atk'] += 1
                room['message'] = f"🍎 Apple: {t_card['name']} gains +2 DEF +1 ATK!"
        else:
            t_card['atk'] += 2
            room['message'] = f"⚔️ Sword: {t_card['name']} gains +2 ATK!"

        # Remove source card
        if src_fi is not None:
            player['field'].pop(src_fi)
        elif src_hi is not None:
            player['hand'].pop(src_hi)
        broadcast_state(room_code)

    # ── Clocksmilk: summon Milk Token ──
    elif ability_id == 'milk_summon':
        milk_pi, milk_fi, milk_card = _find_by_uid(players, card_uid)
        if milk_pi != pi or not _has(milk_card, 'milk_summon'): return
        if milk_card.get('frozen'): emit('error_msg', {'msg': 'Card is frozen.'}); return
        if milk_card.get('turns_on_field', 0) < 1:
            emit('error_msg', {'msg': "Clock's Milk needs 1 turn on field first."}); return
        if len(player['field']) >= 4:
            emit('error_msg', {'msg': 'Field is full.'}); return
        base = next((c for c in CARDLIST if c['name'] == 'Milktoken'), None)
        if base:
            token = new_card(base)
            player['field'].append(token)
            room['message'] = f"🥛 Milk Token summoned!"
        broadcast_state(room_code)

    # ── Milk Drink: destroy Milk Token to heal 2 ──
    elif ability_id == 'milk_drink':
        # Check Clock's Milk is alive on field
        has_milk = any(c['name'] == 'Clocksmilk' for c in player['field'])
        if not has_milk:
            emit('error_msg', {'msg': "Clock's Milk must be on field to use Milk Drink."}); return
        t_pi, t_fi, t_card = _find_by_uid(players, target_uid)
        if t_pi != pi or t_card['name'] != 'Milktoken': return
        player['field'].pop(t_fi)
        player['hp'] += 2
        room['message'] = f"🥛 Milk Drink: {player['name']} heals 2 HP!"
        broadcast_state(room_code)

    # ── Greed: summon Atlas ──
    elif ability_id == 'greed_atlas':
        greed_card = next((c for c in player['field'] if _has(c, 'greed_atlas')), None)
        if not greed_card or greed_card.get('frozen'): return
        if greed_card.get('atlas_used_turn') == room['turn_count']:
            emit('error_msg', {'msg': 'Atlas summon: once per turn.'}); return
        if len(player['field']) >= 4:
            emit('error_msg', {'msg': 'Field is full.'}); return
        base = next((c for c in SPECIAL_CARDS if c['name'] == 'Atlas'), None)
        if base:
            player['hp'] -= 2
            player['field'].append(new_card(base))
            greed_card['atlas_used_turn'] = room['turn_count']
            room['message'] = f"💰 Atlas summoned! {player['name']} loses 2 HP."
        broadcast_state(room_code)

    # ── Fisher: pull fish ──
    elif ability_id == 'fisher_pull':
        fish_pi, fish_fi, fish_card = _find_by_uid(players, card_uid)
        if fish_pi != pi or not _has(fish_card, 'fisher_pull'): return
        if fish_card.get('frozen'): emit('error_msg', {'msg': 'Card is frozen.'}); return
        if fish_card.get('pull_used_turn') == room['turn_count']:
            emit('error_msg', {'msg': 'Abyssal Pull: once per turn.'}); return
        fish_inv = fish_card.get('fish', [])
        if len(fish_inv) >= 3:
            emit('error_msg', {'msg': 'Fish storage full (max 3).'}); return
        result = 'light' if random.random() < 0.5 else 'dark'
        fish_inv.append(result)
        fish_card['fish'] = fish_inv
        fish_card['pull_used_turn'] = room['turn_count']
        room['message'] = f"🎣 Fisher pulled a {'🌟 Light' if result=='light' else '🌑 Dark'} Fish! ({len(fish_inv)}/3)"
        broadcast_state(room_code)

    # ── Fisher: use fish ──
    elif ability_id == 'fisher_catch':
        fish_pi, fish_fi, fish_card = _find_by_uid(players, card_uid)
        if fish_pi != pi or not _has(fish_card, 'fisher_catch'): return
        fish_type = data.get('fish_type')  # 'light' or 'dark'
        fish_inv  = fish_card.get('fish', [])
        if fish_type not in fish_inv:
            emit('error_msg', {'msg': f'No {fish_type} fish available.'}); return
        fish_inv.remove(fish_type)
        fish_card['fish'] = fish_inv
        t_pi, t_fi, t_card = _find_by_uid(players, target_uid)
        if t_card is None: return
        if fish_type == 'light':
            t_card['def'] += 2
            room['message'] = f"🌟 Light Fish: {t_card['name']} gains +2 DEF!"
        else:
            if t_pi == pi:
                emit('error_msg', {'msg': 'Dark Fish targets enemy cards only.'}); return
            t_card['atk'] = max(0, t_card['atk'] - 2)
            t_card['dark_fish_turns'] = 3
            room['message'] = f"🌑 Dark Fish: {t_card['name']} loses 2 ATK for 3 turns!"
        broadcast_state(room_code)

    # ── Core Stars: place dark star ──
    elif ability_id == 'core_dark_star':
        src_pi, src_fi, src_card = _find_by_uid(players, card_uid)
        if src_pi != pi or not _has(src_card, 'core_dark_star'): return
        if src_card.get('frozen'): emit('error_msg', {'msg': 'Card is frozen.'}); return
        last = src_card.get('last_star_turn', -99)
        if room['turn_count'] - last < 2:
            emit('error_msg', {'msg': 'Dark Star: once per 2 turns.'}); return
        t_pi, t_fi, t_card = _find_by_uid(players, target_uid)
        if t_pi == pi: emit('error_msg', {'msg': 'Dark Star targets enemy cards.'}); return
        if _has(t_card, 'duraza_def_lock'):
            emit('error_msg', {'msg': "Can't place Dark Star on this card."}); return
        stars = t_card.get('dark_stars', 0)
        if stars >= 4:
            emit('error_msg', {'msg': 'Max 4 Dark Stars on one card.'}); return
        t_card['dark_stars'] = stars + 1
        src_card['last_star_turn'] = room['turn_count']
        room['message'] = f"🌑 Dark Star placed on {t_card['name']}! ({t_card['dark_stars']} stars)"
        broadcast_state(room_code)

@socketio.on('disconnect')
def on_disconnect():
    for code, room in list(rooms.items()):
        for player in room['players']:
            if player['sid'] == request.sid:
                room['state'] = 'finished'
                for other in room['players']:
                    if other['sid'] != request.sid:
                        socketio.emit('opponent_left', {}, to=other['sid'])
                break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
