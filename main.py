import json
import random

cardlist = ["Fisher","clock","clocksmilk","Mysteriousash","atlas","greed","blackhole","blackholeAtlas","greedatlas","Breaker","Mirror","Milktoken"]

player1_hand = random.choices(cardlist, k=5)
player2_hand = random.choices(cardlist, k=5)

with open("player1.json", 'w') as f:
    json.dump(player1_hand, f, indent=2)

with open("player2.json", 'w') as f:
    json.dump(player2_hand, f, indent=2)
