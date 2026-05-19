from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room as sio_join_room
import random
import string
import copy
import uuid
from cards import CARDLIST

ACCESS_CODE = "CLOCKPAPI"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clockpapi-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

rooms = {}


# ── Card helpers ──────────────────────────────────────────────────────────────

def new_card(base):
    c = copy.deepcopy(base)
    c['uid']      = str(uuid.uuid4())[:8]
    c['attacked'] = False
    c['frozen']   = False
    return c

def deal_hand(k=5):
    return [new_card(random.choice(CARDLIST)) for _ in range(k)]

def draw_card():
    return new_card(random.choice(CARDLIST))


# ── Room helpers ──────────────────────────────────────────────────────────────

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
    }


# ── Broadcast ─────────────────────────────────────────────────────────────────

def broadcast_state(room_code):
    room = rooms.get(room_code)
    if not room or len(room['players']) < 2:
        return
    players = room['players']
    for i, player in enumerate(players):
        opp = players[1 - i]
        is_hand_trap_defender = (
            room['phase'] == 'hand_trap_window' and
            room['current_turn'] != i
        )
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
            'hand_trap_prompt': is_hand_trap_defender,
            'pending_desc':     _pending_desc(room.get('pending_action')),
        }, to=player['sid'])

def _pending_desc(p):
    if not p:
        return ''
    if p['type'] == 'play_card':
        return 'playing a card'
    if p['type'] == 'attack':
        return 'declaring an attack'
    return 'an action'


# ── Specials helpers ──────────────────────────────────────────────────────────

def _has_special(card, special_id):
    return any(s['id'] == special_id for s in card.get('specials', []))

def _defender_has_quick_effect(room):
    """True if the non-active player has an unfrozen Clock in hand with QE available."""
    defender_index = 1 - room['current_turn']
    if room['quick_effect_used'][defender_index]:
        return False
    for card in room['players'][defender_index]['hand']:
        if card['name'] == 'Clock' and not card.get('frozen'):
            return True
    return False

def _open_hand_trap(room, room_code, pending):
    """Open hand-trap window. Returns True so caller can bail early."""
    actor   = room['players'][room['current_turn']]['name']
    defender = room['players'][1 - room['current_turn']]['name']
    room['pending_action'] = pending
    room['phase']   = 'hand_trap_window'
    room['message'] = (
        f"{actor} is {_pending_desc(pending)}. "
        f"{defender}: activate Clock's Quick Effect?"
    )
    broadcast_state(room_code)
    return True

def _tick_freeze(room, ending_player_index):
    """Decrement freeze counters for cards frozen by ending_player_index."""
    for p in room['players']:
        to_remove = []
        for card in p['field']:
            if card.get('frozen') and card.get('freeze_by') == ending_player_index:
                card['freeze_turns'] = card.get('freeze_turns', 1) - 1
                if card['freeze_turns'] <= 0:
                    card['frozen']       = False
                    card['freeze_by']    = None
                    card['freeze_turns'] = 0


# ── Action executors ──────────────────────────────────────────────────────────

def _exec_play_card(room, room_code, player_index, card_index):
    player = room['players'][player_index]
    if card_index < 0 or card_index >= len(player['hand']):
        return
    card = player['hand'].pop(card_index)
    card['attacked'] = False
    player['field'].append(card)
    room['cards_played'] += 1
    room['phase']   = 'play'
    room['message'] = f"{player['name']} played {card['name']}."
    broadcast_state(room_code)

def _exec_attack(room, room_code, player_index, attacker_idx, target_idx):
    players          = room['players']
    attacker_player  = players[player_index]
    defender_player  = players[1 - player_index]

    if attacker_idx < 0 or attacker_idx >= len(attacker_player['field']):
        room['phase'] = 'attack'
        broadcast_state(room_code)
        return

    atk_card = attacker_player['field'][attacker_idx]

    if target_idx is None:
        # ── Direct attack ──
        if defender_player['field']:
            room['phase']   = 'attack'
            room['message'] = "Can't attack directly — opponent has cards on the field."
            broadcast_state(room_code)
            return
        defender_player['hp'] -= atk_card['atk']
        room['message'] = (
            f"{atk_card['name']} deals {atk_card['atk']} direct damage "
            f"to {defender_player['name']}!"
        )
        if defender_player['hp'] <= 0:
            defender_player['hp'] = 0
            room['winner'] = attacker_player['name']
            room['state']  = 'finished'
    else:
        # ── Attack a card ──
        if target_idx < 0 or target_idx >= len(defender_player['field']):
            room['phase'] = 'attack'
            broadcast_state(room_code)
            return

        target = defender_player['field'][target_idx]
        damage = atk_card['atk']
        target['def'] -= damage

        # Apply Freeze if attacker is Clock on field
        if _has_special(atk_card, 'freeze') and not target.get('frozen'):
            target['frozen']       = True
            target['freeze_by']    = player_index
            target['freeze_turns'] = 1

        if target['def'] <= 0:
            excess = abs(target['def'])
            name   = target['name']
            defender_player['field'].pop(target_idx)
            room['message'] = f"{atk_card['name']} destroys {name}!"
            if excess > 0:
                defender_player['hp'] -= excess
                room['message'] += (
                    f" {excess} excess damage to {defender_player['name']}!"
                    f" ({defender_player['name']} HP: {max(0, defender_player['hp'])})"
                )
                if defender_player['hp'] <= 0:
                    defender_player['hp'] = 0
                    room['winner'] = attacker_player['name']
                    room['state']  = 'finished'
        else:
            room['message'] = (
                f"{atk_card['name']} hits {target['name']} for {damage}! "
                f"{target['name']} DEF: {target['def']}"
            )
            if target.get('frozen'):
                room['message'] += " ❄️ (Frozen)"

    atk_card['attacked'] = True
    room['phase'] = 'attack'
    broadcast_state(room_code)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── Socket events ─────────────────────────────────────────────────────────────

@socketio.on('verify_access')
def on_verify_access(data):
    if data.get('code', '').upper() == ACCESS_CODE:
        emit('access_granted')
    else:
        emit('access_denied')

@socketio.on('create_room')
def on_create_room(data):
    name = data.get('name', 'Player 1').strip() or 'Player 1'
    code = make_room_code()
    room = new_room()
    room['players'].append(
        {'sid': request.sid, 'name': name, 'hand': deal_hand(5), 'field': [], 'hp': 20}
    )
    rooms[code] = room
    sio_join_room(code)
    emit('room_created', {'code': code})

@socketio.on('join_game')
def on_join_game(data):
    name = data.get('name', 'Player 2').strip() or 'Player 2'
    code = data.get('code', '').upper()

    if code not in rooms:
        emit('room_error', {'msg': f'Room "{code}" not found.'}); return
    room = rooms[code]
    if len(room['players']) >= 2:
        emit('room_error', {'msg': 'Room is full.'}); return
    if room['state'] != 'waiting':
        emit('room_error', {'msg': 'Game already started.'}); return

    room['players'].append(
        {'sid': request.sid, 'name': name, 'hand': deal_hand(5), 'field': [], 'hp': 20}
    )
    sio_join_room(code)

    first = random.randint(0, 1)
    room.update({
        'current_turn': first,
        'state':        'playing',
        'phase':        'play',
        'cards_played': 0,
        'message':      f"{room['players'][first]['name']} goes first!",
    })

    for i, player in enumerate(room['players']):
        socketio.emit('game_start', {
            'your_index':   i,
            'room_code':    code,
            'first_player': room['players'][first]['name'],
            'coin':         'heads' if first == 0 else 'tails',
        }, to=player['sid'])

    broadcast_state(code)

@socketio.on('play_card')
def on_play_card(data):
    room_code  = data.get('room')
    card_index = data.get('card_index')
    room = rooms.get(room_code)
    if not room: return

    players      = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']: return
    if room['phase'] != 'play': return
    if room['cards_played'] >= 2:
        emit('error_msg', {'msg': 'Already played 2 cards this turn.'}); return

    player = players[player_index]
    if len(player['field']) >= 4:
        emit('error_msg', {'msg': 'Your field is full (max 4).'}); return
    if card_index < 0 or card_index >= len(player['hand']): return

    pending = {'type': 'play_card', 'player_index': player_index, 'card_index': card_index}
    if _defender_has_quick_effect(room):
        _open_hand_trap(room, room_code, pending); return

    _exec_play_card(room, room_code, player_index, card_index)

@socketio.on('end_play_phase')
def on_end_play_phase(data):
    room_code = data.get('room')
    room = rooms.get(room_code)
    if not room: return

    players      = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']: return
    if room['phase'] != 'play': return

    room['phase']   = 'attack'
    room['message'] = f"{players[player_index]['name']}'s attack phase."
    broadcast_state(room_code)

@socketio.on('attack')
def on_attack(data):
    room_code      = data.get('room')
    attacker_index = data.get('attacker_index')
    target_index   = data.get('target_index')
    room = rooms.get(room_code)
    if not room: return

    players      = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']: return
    if room['phase'] != 'attack': return

    if attacker_index < 0 or attacker_index >= len(players[player_index]['field']): return
    atk_card = players[player_index]['field'][attacker_index]
    if atk_card.get('attacked'):
        emit('error_msg', {'msg': f"{atk_card['name']} already attacked this turn."}); return

    pending = {
        'type':           'attack',
        'player_index':   player_index,
        'attacker_index': attacker_index,
        'target_index':   target_index,
    }
    if _defender_has_quick_effect(room):
        _open_hand_trap(room, room_code, pending); return

    _exec_attack(room, room_code, player_index, attacker_index, target_index)

@socketio.on('quick_effect_response')
def on_quick_effect_response(data):
    room_code  = data.get('room')
    use_effect = data.get('use')
    room = rooms.get(room_code)
    if not room or room['phase'] != 'hand_trap_window': return

    players      = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index == room['current_turn']: return

    pending = room.pop('pending_action', None)

    if use_effect and pending:
        # Discard Clock from hand
        hand = players[player_index]['hand']
        for i, c in enumerate(hand):
            if c['name'] == 'Clock':
                hand.pop(i); break
        room['quick_effect_used'][player_index] = True
        actor_name = players[room['current_turn']]['name']
        room['phase']   = pending['type'] == 'play_card' and 'play' or 'attack'
        room['message'] = f"❄️ Clock's Quick Effect! {actor_name}'s action was cancelled."
        broadcast_state(room_code)
    else:
        # Pass — execute the action
        if not pending: return
        if pending['type'] == 'play_card':
            _exec_play_card(room, room_code, pending['player_index'], pending['card_index'])
        elif pending['type'] == 'attack':
            _exec_attack(room, room_code, pending['player_index'],
                         pending['attacker_index'], pending.get('target_index'))

@socketio.on('end_turn')
def on_end_turn(data):
    room_code = data.get('room')
    room = rooms.get(room_code)
    if not room or room['state'] == 'finished': return

    players      = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']: return
    if room['phase'] != 'attack': return

    # Tick freeze counters for cards frozen by this player
    _tick_freeze(room, player_index)

    # Reset attacked flags
    for card in players[player_index]['field']:
        card['attacked'] = False

    next_turn   = 1 - player_index
    next_player = players[next_turn]

    room['current_turn']              = next_turn
    room['phase']                     = 'play'
    room['cards_played']              = 0
    room['quick_effect_used'][next_turn] = False

    if room['first_turns'][next_turn]:
        room['first_turns'][next_turn] = False
        room['message'] = f"{next_player['name']}'s turn — no draw (first turn)."
    else:
        drawn = draw_card()
        next_player['hand'].append(drawn)
        room['message'] = f"{next_player['name']} drew a card."

    broadcast_state(room_code)

@socketio.on('disconnect')
def on_disconnect():
    for code, room in list(rooms.items()):
        for player in room['players']:
            if player['sid'] == request.sid:
                room['state']   = 'finished'
                room['message'] = f"{player['name']} disconnected."
                for other in room['players']:
                    if other['sid'] != request.sid:
                        socketio.emit('opponent_left', {}, to=other['sid'])
                break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
