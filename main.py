import copy
import json
import random

cardlist = ["Fisher","clock","clocksmilk","Mysteriousash","atlas","greed","blackhole","blackholeAtlas","greedatlas","Breaker","Mirror","Milktoken"]
copylist=cardlist
for i in range(5):
  shuffled_list=copylist
  random.shuffle(copylist)
  filename = "player1.json"
  with open(filename, 'w') as f:
      json.dump(shuffled_list, f, indent=2)