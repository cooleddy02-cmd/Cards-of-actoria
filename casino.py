"""Casino module: slots, blackjack, Texas Hold'em (vs bots + multiplayer)."""
import random
from collections import Counter

# ═══════════════════════════════════════════════════════
#  SLOTS
# ═══════════════════════════════════════════════════════
SLOT_SYMBOLS = ['🍒', '🍋', '🔔', '⭐', '💎', '7️⃣']
SLOT_WEIGHTS = [30,    25,    18,    14,    8,    5]
SLOT_PAYOUT  = {  # 3-in-a-row multiplier of bet
    '🍒': 2, '🍋': 3, '🔔': 5, '⭐': 10, '💎': 25, '7️⃣': 50,
}

def slot_spin(bet):
    reels = [random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=1)[0] for _ in range(3)]
    win = 0
    if reels[0] == reels[1] == reels[2]:
        win = bet * SLOT_PAYOUT[reels[0]]
    elif reels[0] == reels[1] or reels[1] == reels[2]:
        win = bet  # push (refund)
    return {'reels': reels, 'win': win, 'net': win - bet}

# ═══════════════════════════════════════════════════════
#  BLACKJACK
# ═══════════════════════════════════════════════════════
BJ_SUITS = ['♠', '♥', '♦', '♣']
BJ_RANKS = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']

def bj_new_deck():
    deck = [{'r': r, 's': s} for r in BJ_RANKS for s in BJ_SUITS]
    random.shuffle(deck)
    return deck

def bj_score(hand):
    total, aces = 0, 0
    for c in hand:
        r = c['r']
        if r == 'A': total += 11; aces += 1
        elif r in ('J','Q','K'): total += 10
        else: total += int(r)
    while total > 21 and aces > 0:
        total -= 10; aces -= 1
    return total

def bj_deal_initial(state):
    state['deck'] = bj_new_deck()
    state['player'] = [state['deck'].pop(), state['deck'].pop()]
    state['dealer'] = [state['deck'].pop(), state['deck'].pop()]
    state['done'] = False
    state['result'] = None
    if bj_score(state['player']) == 21:
        bj_dealer_play(state)

def bj_hit(state):
    if state['done']: return
    state['player'].append(state['deck'].pop())
    if bj_score(state['player']) >= 21:
        bj_dealer_play(state)

def bj_dealer_play(state):
    while bj_score(state['dealer']) < 17:
        state['dealer'].append(state['deck'].pop())
    state['done'] = True
    p, d = bj_score(state['player']), bj_score(state['dealer'])
    if p > 21: state['result'] = 'lose'
    elif d > 21: state['result'] = 'win'
    elif p > d: state['result'] = 'win'
    elif p == d: state['result'] = 'push'
    else: state['result'] = 'lose'

# ═══════════════════════════════════════════════════════
#  TEXAS HOLD'EM
# ═══════════════════════════════════════════════════════
RANK_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,
            'J':11,'Q':12,'K':13,'A':14}

def poker_new_deck():
    deck = [(r, s) for r in BJ_RANKS for s in BJ_SUITS]
    random.shuffle(deck)
    return deck

def _hand_rank_5(cards):
    """Returns (category, tiebreakers...) where higher = better. cards = list of 5 (rank, suit)."""
    vals = sorted([RANK_VAL[r] for r,_ in cards], reverse=True)
    suits = [s for _,s in cards]
    cnt = Counter(vals)
    by_count = sorted(cnt.items(), key=lambda x: (-x[1], -x[0]))
    flush = len(set(suits)) == 1
    # Straight detection (incl. A-2-3-4-5 wheel)
    uniq = sorted(set(vals), reverse=True)
    straight_hi = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4: straight_hi = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]: straight_hi = 5
    if flush and straight_hi == 14: return (9,)           # royal flush
    if flush and straight_hi:       return (8, straight_hi)  # straight flush
    if by_count[0][1] == 4: return (7, by_count[0][0], by_count[1][0])  # quads
    if by_count[0][1] == 3 and by_count[1][1] == 2:
        return (6, by_count[0][0], by_count[1][0])         # full house
    if flush: return (5, *vals)                            # flush
    if straight_hi: return (4, straight_hi)                # straight
    if by_count[0][1] == 3:
        kickers = sorted([v for v in vals if v != by_count[0][0]], reverse=True)
        return (3, by_count[0][0], *kickers)               # trips
    if by_count[0][1] == 2 and by_count[1][1] == 2:
        pairs = sorted([by_count[0][0], by_count[1][0]], reverse=True)
        kicker = max(v for v in vals if v not in pairs)
        return (2, *pairs, kicker)                         # two pair
    if by_count[0][1] == 2:
        kickers = sorted([v for v in vals if v != by_count[0][0]], reverse=True)
        return (1, by_count[0][0], *kickers)               # pair
    return (0, *vals)                                      # high card

def best_hand(cards7):
    """Best 5-card rank from 7 cards (2 hole + 5 community)."""
    from itertools import combinations
    best = (-1,)
    for combo in combinations(cards7, 5):
        r = _hand_rank_5(list(combo))
        if r > best: best = r
    return best

HAND_NAMES = ['High Card','Pair','Two Pair','Three of a Kind','Straight',
              'Flush','Full House','Four of a Kind','Straight Flush','Royal Flush']

def hand_name(rank_tuple):
    return HAND_NAMES[rank_tuple[0]]

# ═══════════════════════════════════════════════════════
#  HOLD'EM TABLE STATE
# ═══════════════════════════════════════════════════════
def new_poker_table(code, host_name, host_sid, host_user, small_blind=10):
    return {
        'code': code,
        'players': [{'name': host_name, 'sid': host_sid, 'user': host_user,
                     'chips': 0, 'hand': [], 'bet': 0, 'folded': False,
                     'all_in': False, 'is_bot': False, 'sit_out': False}],
        'community': [],
        'pot': 0,
        'deck': [],
        'phase': 'waiting',  # waiting / preflop / flop / turn / river / showdown
        'dealer_idx': 0,
        'turn_idx': 0,
        'small_blind': small_blind,
        'big_blind': small_blind * 2,
        'current_bet': 0,
        'min_raise': small_blind * 2,
        'last_aggressor': -1,
        'started_this_round': False,
        'showdown_info': None,
        'message': 'Waiting for players...',
    }

def add_bot(table, name):
    table['players'].append({
        'name': name, 'sid': None, 'user': None,
        'chips': 0, 'hand': [], 'bet': 0, 'folded': False,
        'all_in': False, 'is_bot': True, 'sit_out': False,
    })

def start_hand(table):
    active = [p for p in table['players'] if p['chips'] > 0 and not p['sit_out']]
    if len(active) < 2:
        table['phase'] = 'waiting'
        table['message'] = 'Need at least 2 players with chips.'
        return
    table['deck'] = poker_new_deck()
    table['community'] = []
    table['pot'] = 0
    table['current_bet'] = 0
    table['showdown_info'] = None
    for p in table['players']:
        p['hand'] = []
        p['bet'] = 0
        p['folded'] = p['chips'] <= 0 or p['sit_out']
        p['all_in'] = False
        p['acted'] = False
    # Deal 2 cards to active players
    for _ in range(2):
        for p in table['players']:
            if not p['folded']:
                p['hand'].append(table['deck'].pop())
    # Move dealer button
    table['dealer_idx'] = _next_active(table, table['dealer_idx'])
    # Post blinds
    sb_idx = _next_active(table, table['dealer_idx'])
    bb_idx = _next_active(table, sb_idx)
    _post_bet(table['players'][sb_idx], table['small_blind'])
    _post_bet(table['players'][bb_idx], table['big_blind'])
    table['current_bet'] = table['big_blind']
    table['min_raise'] = table['big_blind']
    table['last_aggressor'] = bb_idx
    table['turn_idx'] = _next_active(table, bb_idx)
    table['phase'] = 'preflop'
    table['message'] = f"Hand started. {table['players'][table['turn_idx']]['name']} to act."

def _next_active(table, start_idx):
    n = len(table['players'])
    for off in range(1, n + 1):
        i = (start_idx + off) % n
        p = table['players'][i]
        if not p['folded'] and not p['all_in']:
            return i
    return start_idx

def _post_bet(player, amount):
    amt = min(amount, player['chips'])
    player['chips'] -= amt
    player['bet'] += amt
    if player['chips'] == 0: player['all_in'] = True

def player_action(table, pidx, action, amount=0):
    """action: 'fold' | 'check' | 'call' | 'raise' | 'allin'"""
    if action not in ('fold','check','call','raise','allin'):
        return False, "Unknown action."
    if pidx != table['turn_idx']:
        return False, "Not your turn."
    p = table['players'][pidx]
    if p['folded'] or p['all_in']:
        return False, "Cannot act."
    to_call = table['current_bet'] - p['bet']
    old_current = table['current_bet']

    if action == 'fold':
        p['folded'] = True
    elif action == 'check':
        if to_call > 0: return False, "Cannot check."
    elif action == 'call':
        _post_bet(p, to_call)
    elif action == 'raise':
        if amount < to_call + table['min_raise']:
            amount = to_call + table['min_raise']
        if amount >= p['chips']:
            return player_action(table, pidx, 'allin')
        _post_bet(p, amount)
        table['min_raise'] = (p['bet'] - table['current_bet'])
        table['current_bet'] = p['bet']
        table['last_aggressor'] = pidx
    elif action == 'allin':
        _post_bet(p, p['chips'])
        if p['bet'] > table['current_bet']:
            raise_amt = p['bet'] - table['current_bet']
            if raise_amt >= table['min_raise']:
                table['min_raise'] = raise_amt
                table['last_aggressor'] = pidx
            table['current_bet'] = p['bet']

    p['acted'] = True
    # On aggression, reopen action for everyone else still live
    if table['current_bet'] > old_current:
        for i, other in enumerate(table['players']):
            if i != pidx and not other['folded'] and not other['all_in']:
                other['acted'] = False

    _advance_after_action(table)
    return True, "OK"

def _advance_after_action(table):
    # Folded down to one player → collect bets and award immediately
    in_hand = [i for i,p in enumerate(table['players']) if not p['folded']]
    if len(in_hand) == 1:
        _collect_bets(table)
        _award_pot(table, in_hand)
        table['phase'] = 'showdown'
        return
    # Round complete when every non-folded, non-all-in player has acted
    # AND has matched the current bet
    need_act = [i for i in in_hand
                if not table['players'][i]['all_in']
                and (not table['players'][i].get('acted', False)
                     or table['players'][i]['bet'] != table['current_bet'])]
    if not need_act:
        _next_street(table)
        return
    table['turn_idx'] = _next_active(table, table['turn_idx'])
    table['message'] = f"{table['players'][table['turn_idx']]['name']} to act."

def _collect_bets(table):
    for p in table['players']:
        table['pot'] += p['bet']
        p['bet'] = 0
    table['current_bet'] = 0
    table['min_raise'] = table['big_blind']

def _next_street(table):
    _collect_bets(table)
    for p in table['players']:
        p['acted'] = False
    if table['phase'] == 'preflop':
        table['deck'].pop()  # burn
        table['community'] = [table['deck'].pop() for _ in range(3)]
        table['phase'] = 'flop'
    elif table['phase'] == 'flop':
        table['deck'].pop()
        table['community'].append(table['deck'].pop())
        table['phase'] = 'turn'
    elif table['phase'] == 'turn':
        table['deck'].pop()
        table['community'].append(table['deck'].pop())
        table['phase'] = 'river'
    elif table['phase'] == 'river':
        _showdown(table)
        return
    # Set first to act after dealer
    table['turn_idx'] = _next_active(table, table['dealer_idx'])
    table['last_aggressor'] = table['turn_idx']
    # If all remaining are all-in, run out and showdown
    active_can_act = [i for i,p in enumerate(table['players'])
                      if not p['folded'] and not p['all_in']]
    if len(active_can_act) <= 1:
        # Auto-run remaining streets
        if table['phase'] != 'showdown':
            _next_street(table)
        return
    table['message'] = f"{['Flop','Turn','River'][['flop','turn','river'].index(table['phase'])]}! {table['players'][table['turn_idx']]['name']} to act."

def _showdown(table):
    in_hand = [i for i,p in enumerate(table['players']) if not p['folded']]
    if len(in_hand) == 1:
        _award_pot(table, in_hand)
        return
    ranks = {}
    for i in in_hand:
        seven = table['players'][i]['hand'] + table['community']
        ranks[i] = best_hand(seven)
    best = max(ranks.values())
    winners = [i for i,r in ranks.items() if r == best]
    _award_pot(table, winners, ranks)
    table['phase'] = 'showdown'

def _award_pot(table, winner_indices, ranks=None):
    share = table['pot'] // len(winner_indices)
    info = {'winners': [], 'pot': table['pot']}
    for i in winner_indices:
        table['players'][i]['chips'] += share
        winfo = {'idx': i, 'name': table['players'][i]['name'], 'won': share}
        if ranks and i in ranks:
            winfo['hand'] = hand_name(ranks[i])
        info['winners'].append(winfo)
    table['pot'] = 0
    table['showdown_info'] = info
    table['message'] = ' + '.join(f"{w['name']} wins {w['won']}" for w in info['winners'])

def bot_decide(table, pidx):
    """Simple bot: evaluates current hand strength, then folds/calls/raises."""
    p = table['players'][pidx]
    to_call = table['current_bet'] - p['bet']
    if not table['community']:
        # Pre-flop: use simple Chen-like score
        r1, r2 = sorted([RANK_VAL[c[0]] for c in p['hand']], reverse=True)
        s = r1 / 2 + (1 if r1 == r2 else 0) * 5
        if p['hand'][0][1] == p['hand'][1][1]: s += 2
        if abs(r1 - r2) == 1: s += 1
        strength = min(1.0, s / 12)
    else:
        seven = p['hand'] + table['community']
        if len(seven) >= 5:
            rank = best_hand(seven)
            strength = min(1.0, (rank[0] + 1) / 9)
        else:
            strength = 0.3
    r = random.random()
    if to_call == 0:
        if strength > 0.5 and r < 0.4:
            return ('raise', table['current_bet'] + table['big_blind'] * 2)
        return ('check', 0)
    pot_odds = to_call / max(1, table['pot'] + to_call)
    if strength < pot_odds * 0.7 and r < 0.6:
        return ('fold', 0)
    if strength > 0.7 and r < 0.35:
        return ('raise', table['current_bet'] + table['big_blind'] * 3)
    return ('call', 0)

def public_view(table, viewer_idx=None):
    """Sanitize: hide other players' hole cards unless showdown."""
    show_all = (table['phase'] == 'showdown')
    pubs = []
    for i, p in enumerate(table['players']):
        show = show_all or (viewer_idx == i)
        pubs.append({
            'idx': i, 'name': p['name'], 'chips': p['chips'], 'bet': p['bet'],
            'folded': p['folded'], 'all_in': p['all_in'], 'is_bot': p['is_bot'],
            'hand': p['hand'] if show else [{'r':'?','s':'?'} for _ in p['hand']],
        })
    return {
        'code': table['code'],
        'players': pubs,
        'community': table['community'],
        'pot': table['pot'] + sum(p['bet'] for p in table['players']),
        'phase': table['phase'],
        'turn_idx': table['turn_idx'],
        'dealer_idx': table['dealer_idx'],
        'current_bet': table['current_bet'],
        'big_blind': table['big_blind'],
        'message': table['message'],
        'showdown_info': table['showdown_info'],
    }
