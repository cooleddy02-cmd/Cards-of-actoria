import copy
import random

CARDLIST = [
    {"name": "Fisher",         "atk": 3, "def": 5},
    {"name": "Clock",          "atk": 2, "def": 4},
    {"name": "Clocksmilk",     "atk": 4, "def": 3},
    {"name": "Mysteriousash",  "atk": 5, "def": 6},
    {"name": "Atlas",          "atk": 4, "def": 5},
    {"name": "Greed",          "atk": 6, "def": 4},
    {"name": "Blackhole",      "atk": 7, "def": 3},
    {"name": "BlackholeAtlas", "atk": 6, "def": 6},
    {"name": "Greedatlas",     "atk": 5, "def": 5},
    {"name": "Breaker",        "atk": 4, "def": 6},
    {"name": "Mirror",         "atk": 2, "def": 7},
    {"name": "Milktoken",      "atk": 1, "def": 2},
]

def deal_hand(k=5):
    return [copy.deepcopy(random.choice(CARDLIST)) for _ in range(k)]

def draw_card():
    return copy.deepcopy(random.choice(CARDLIST))
