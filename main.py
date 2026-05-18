import json
import random

cardlist = ["Fisher","clock","clocksmilk","Mysteriousash","atlas","greed","blackhole","blackholeAtlas","greedatlas","Breaker","Mirror","Milktoken"]
shuffled_list = cardlist.copy()
random.shuffle(shuffled_list)
with open("player1.json", 'w') as f:
    json.dump(shuffled_list, f, indent=2)
