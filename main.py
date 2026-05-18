import json
import random

cardlist = ["Fisher","clock","clocksmilk","Mysteriousash","atlas","greed","blackhole","blackholeAtlas","greedatlas","Breaker","Mirror","Milktoken"]

hand = random.choices(cardlist, k=5)

with open("player1.json", 'w') as f:
    json.dump(hand, f, indent=2)
