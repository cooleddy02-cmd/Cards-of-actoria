import json
import random

cardlist = ["Fisher","clock","clocksmilk","Mysteriousash","atlas","greed","blackhole","blackholeAtlas","greedatlas","Breaker","Mirror","Milktoken"]

all_shuffles = []
for i in range(5):
    shuffled_list = cardlist.copy()
    random.shuffle(shuffled_list)
    all_shuffles.append(shuffled_list)

with open("player1.json", 'w') as f:
    json.dump(all_shuffles, f, indent=2)
