from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room as sio_join_room
import random
import string
from cards import deal_hand, draw_card

ACCESS_CODE = "CLOCKPAPI"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clockpapi-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

rooms = {}

def make_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code

def broadcast_state(room_code):
    room = rooms.get(room_code)
    if not room:
        return
    players = room['players']
    for i, player in enumerate(players):
        opp = players[1 - i]
        socketio.emit('state_update', {
            'your_index': i,
            'your_name': player['name'],
            'opp_name': opp['name'],
            'your_hp': player['hp'],
            'opp_hp': opp['hp'],
            'your_hand': player['hand'],
            'your_field': player['field'],
            'opp_field': opp['field'],
            'current_turn': room['current_turn'],
            'phase': room['phase'],
            'cards_played': room['cards_played'],
            'message': room.get('message', ''),
            'winner': room.get('winner'),
        }, to=player['sid'])

@app.route('/')
def index():
    return render_template('index.html')

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
    rooms[code] = {
        'players': [
            {'sid': request.sid, 'name': name, 'hand': deal_hand(5), 'field': [], 'hp': 20}
        ],
        'state': 'waiting',
        'current_turn': 0,
        'first_turns': [True, True],
        'phase': 'waiting',
        'cards_played': 0,
        'message': 'Waiting for opponent...'
    }
    sio_join_room(code)
    emit('room_created', {'code': code})

@socketio.on('join_game')
def on_join_game(data):
    name = data.get('name', 'Player 2').strip() or 'Player 2'
    code = data.get('code', '').upper()

    if code not in rooms:
        emit('room_error', {'msg': f'Room "{code}" not found.'})
        return
    room = rooms[code]
    if len(room['players']) >= 2:
        emit('room_error', {'msg': 'Room is full.'})
        return
    if room['state'] != 'waiting':
        emit('room_error', {'msg': 'Game already in progress.'})
        return

    room['players'].append(
        {'sid': request.sid, 'name': name, 'hand': deal_hand(5), 'field': [], 'hp': 20}
    )
    sio_join_room(code)

    first = random.randint(0, 1)
    room['current_turn'] = first
    room['state'] = 'playing'
    room['phase'] = 'play'
    room['cards_played'] = 0
    first_name = room['players'][first]['name']
    room['message'] = f'{first_name} goes first!'

    for i, player in enumerate(room['players']):
        opp = room['players'][1 - i]
        socketio.emit('game_start', {
            'your_index': i,
            'room_code': code,
            'first_player': first_name,
            'coin': 'heads' if first == 0 else 'tails',
        }, to=player['sid'])

    broadcast_state(code)

@socketio.on('play_card')
def on_play_card(data):
    room_code = data.get('room')
    card_index = data.get('card_index')
    room = rooms.get(room_code)
    if not room:
        return

    players = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']:
        return
    if room['phase'] != 'play':
        return
    if room['cards_played'] >= 2:
        emit('error_msg', {'msg': 'Already played 2 cards this turn.'})
        return

    player = players[player_index]
    if len(player['field']) >= 4:
        emit('error_msg', {'msg': 'Your field is full (max 4).'})
        return
    if card_index < 0 or card_index >= len(player['hand']):
        return

    card = player['hand'].pop(card_index)
    card['attacked'] = False
    player['field'].append(card)
    room['cards_played'] += 1
    room['message'] = f"{player['name']} played {card['name']}."
    broadcast_state(room_code)

@socketio.on('end_play_phase')
def on_end_play_phase(data):
    room_code = data.get('room')
    room = rooms.get(room_code)
    if not room:
        return

    players = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']:
        return
    if room['phase'] != 'play':
        return

    room['phase'] = 'attack'
    room['message'] = f"{players[player_index]['name']}'s attack phase."
    broadcast_state(room_code)

@socketio.on('attack')
def on_attack(data):
    room_code = data.get('room')
    attacker_index = data.get('attacker_index')
    target_index = data.get('target_index')
    room = rooms.get(room_code)
    if not room:
        return

    players = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']:
        return
    if room['phase'] != 'attack':
        return

    attacker_player = players[player_index]
    defender_player = players[1 - player_index]

    if attacker_index < 0 or attacker_index >= len(attacker_player['field']):
        return

    atk_card = attacker_player['field'][attacker_index]
    if atk_card.get('attacked'):
        emit('error_msg', {'msg': f"{atk_card['name']} already attacked this turn."})
        return

    if target_index is None:
        if defender_player['field']:
            emit('error_msg', {'msg': "Can't attack directly — opponent has cards on the field."})
            return
        defender_player['hp'] -= atk_card['atk']
        room['message'] = f"{atk_card['name']} deals {atk_card['atk']} direct damage to {defender_player['name']}!"
        if defender_player['hp'] <= 0:
            defender_player['hp'] = 0
            room['winner'] = attacker_player['name']
            room['state'] = 'finished'
    else:
        if target_index < 0 or target_index >= len(defender_player['field']):
            return
        target = defender_player['field'][target_index]
        target['def'] -= atk_card['atk']
        room['message'] = f"{atk_card['name']} hits {target['name']} for {atk_card['atk']}! {target['name']} DEF: {max(0, target['def'])}"
        if target['def'] <= 0:
            room['message'] += f" — {target['name']} destroyed!"
            defender_player['field'].pop(target_index)

    atk_card['attacked'] = True
    broadcast_state(room_code)

@socketio.on('end_turn')
def on_end_turn(data):
    room_code = data.get('room')
    room = rooms.get(room_code)
    if not room or room['state'] == 'finished':
        return

    players = room['players']
    player_index = next((i for i, p in enumerate(players) if p['sid'] == request.sid), None)
    if player_index is None or player_index != room['current_turn']:
        return
    if room['phase'] != 'attack':
        return

    for card in players[player_index]['field']:
        card['attacked'] = False

    next_turn = 1 - player_index
    room['current_turn'] = next_turn
    room['phase'] = 'play'
    room['cards_played'] = 0

    next_player = players[next_turn]
    if room['first_turns'][next_turn]:
        room['first_turns'][next_turn] = False
        room['message'] = f"{next_player['name']}'s turn — no draw (first turn). Play phase."
    else:
        drawn = draw_card()
        next_player['hand'].append(drawn)
        room['message'] = f"{next_player['name']} drew a card. Play phase."

    broadcast_state(room_code)

@socketio.on('disconnect')
def on_disconnect():
    for code, room in list(rooms.items()):
        for player in room['players']:
            if player['sid'] == request.sid:
                room['state'] = 'finished'
                room['message'] = f"{player['name']} disconnected."
                for other in room['players']:
                    if other['sid'] != request.sid:
                        socketio.emit('opponent_left', {}, to=other['sid'])
                break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
