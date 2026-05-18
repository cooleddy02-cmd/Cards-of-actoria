import json
import random
from cards import deal_hand, draw_card

def save_hands(p1_hand, p2_hand):
    with open("player1.json", 'w') as f:
        json.dump(p1_hand, f, indent=2)
    with open("player2.json", 'w') as f:
        json.dump(p2_hand, f, indent=2)

def show_card(card, index=None):
    prefix = f"[{index}] " if index is not None else ""
    return f"{prefix}{card['name']} | ATK:{card['atk']} DEF:{card['def']}"

def show_field(field, label):
    print(f"\n  {label}'s field:")
    if not field:
        print("    (empty)")
    else:
        for i, card in enumerate(field):
            print(f"    {show_card(card, i)}")

def show_hand(hand):
    print("\n  Your hand:")
    for i, card in enumerate(hand):
        print(f"    {show_card(card, i)}")

def play_phase(name, hand, field):
    cards_played = 0
    while cards_played < 2:
        spaces_left = 4 - len(field)
        if spaces_left == 0:
            print("\n  Field is full (max 4 cards).")
            break
        if not hand:
            print("\n  No cards in hand.")
            break

        show_hand(hand)
        show_field(field, name)
        print(f"\n  {name}: Play a card ({cards_played}/2 played this turn, {spaces_left} field space left)")
        print("  Enter card number to play, or 's' to stop playing:")
        choice = input("  > ").strip().lower()

        if choice == 's':
            break
        elif choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(hand):
                card = hand.pop(idx)
                card['attacked'] = False
                field.append(card)
                print(f"\n  Played {card['name']}!")
                cards_played += 1
            else:
                print("  Invalid number, try again.")
        else:
            print("  Invalid input, try again.")

def attack_phase(name, field, opp_name, opp_field, opp_hp):
    if not field:
        print(f"\n  {name} has no cards to attack with.")
        return opp_hp

    print(f"\n-- {name}'s Attack Phase --")

    for card in field:
        if card.get('attacked'):
            continue

        show_field(field, name)
        show_field(opp_field, opp_name)
        print(f"\n  {show_card(card)} is attacking.")

        if opp_field:
            print("  Enter opponent card number to attack, or 's' to skip this card:")
        else:
            print("  Opponent field is empty — press Enter to attack directly or 's' to skip:")

        choice = input("  > ").strip().lower()

        if choice == 's':
            continue

        if not opp_field:
            opp_hp -= card['atk']
            print(f"  Direct hit! {opp_name} takes {card['atk']} damage! {opp_name} HP: {opp_hp}")
        elif choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(opp_field):
                target = opp_field[idx]
                target['def'] -= card['atk']
                print(f"  {card['name']} hits {target['name']} for {card['atk']} damage! {target['name']} DEF remaining: {target['def']}")
                if target['def'] <= 0:
                    print(f"  {target['name']} is destroyed!")
                    opp_field.pop(idx)
            else:
                print("  Invalid target, skipping.")
        else:
            print("  Invalid input, skipping.")

        card['attacked'] = True

        if opp_hp <= 0:
            break

    return opp_hp

def reset_attacks(field):
    for card in field:
        card['attacked'] = False

def main():
    print("=" * 40)
    print("        CARD GAME — LOCAL 2 PLAYER")
    print("=" * 40)

    p1_name = input("\n  Player 1, enter your name: ").strip() or "Player 1"
    p2_name = input("  Player 2, enter your name: ").strip() or "Player 2"

    print(f"\n  Welcome {p1_name} and {p2_name}!")

    input("\n  Press Enter to flip a coin and decide who goes first...")
    flip = random.choice(["heads", "tails"])
    print(f"  It's {flip.upper()}!")
    if flip == "heads":
        current = 1
        print(f"  {p1_name} goes first!")
    else:
        current = 2
        print(f"  {p2_name} goes first!")

    p1_hand = deal_hand(5)
    p2_hand = deal_hand(5)
    save_hands(p1_hand, p2_hand)

    p1_field = []
    p2_field = []
    p1_hp = 20
    p2_hp = 20
    turn = 1
    first_turn = {1: True, 2: True}

    while p1_hp > 0 and p2_hp > 0:
        print(f"\n{'=' * 40}")
        print(f"  Turn {turn} — {p1_name if current == 1 else p2_name}'s turn")
        print(f"  {p1_name} HP: {p1_hp}  |  {p2_name} HP: {p2_hp}")
        print(f"{'=' * 40}")

        if current == 1:
            hand, field = p1_hand, p1_field
            opp_field = p2_field
            name, opp_name = p1_name, p2_name
        else:
            hand, field = p2_hand, p2_field
            opp_field = p1_field
            name, opp_name = p2_name, p1_name

        if first_turn[current]:
            print(f"\n  {name}'s first turn — no draw this round.")
            first_turn[current] = False
        else:
            drawn = draw_card()
            hand.append(drawn)
            print(f"\n  {name} drew: {drawn['name']} | ATK:{drawn['atk']} DEF:{drawn['def']}")

        reset_attacks(field)

        play_phase(name, hand, field)

        new_opp_hp = attack_phase(name, field, opp_name, opp_field,
                                   p2_hp if current == 1 else p1_hp)

        if current == 1:
            p2_hp = new_opp_hp
        else:
            p1_hp = new_opp_hp

        save_hands(p1_hand, p2_hand)

        if p2_hp <= 0:
            print(f"\n{'=' * 40}")
            print(f"  {p1_name} wins!")
            print(f"{'=' * 40}")
            break
        if p1_hp <= 0:
            print(f"\n{'=' * 40}")
            print(f"  {p2_name} wins!")
            print(f"{'=' * 40}")
            break

        current = 2 if current == 1 else 1
        turn += 1

if __name__ == "__main__":
    main()
