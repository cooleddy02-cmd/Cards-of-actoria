import copy
import random

CARDLIST = [
    {"name": "Fisher",         "atk": 0, "def": 3,  "specials": []},
    {"name": "Clock",          "atk": 1, "def": 1,  "specials": [
        {"id": "quick_effect", "name": "Quick Effect",
         "desc": "Discard to cancel an enemy attack or summon. Once per turn."},
        {"id": "freeze", "name": "Freeze",
         "desc": "On attack: target cannot use effects until end of your next turn."}
    ]},
    {"name": "Clocksmilk",     "atk": 4, "def": 3,  "specials": []},
    {"name": "Mysteriousash",  "atk": 5, "def": 6,  "specials": []},
    {"name": "Atlas",          "atk": 4, "def": 5,  "specials": []},
    {"name": "Greed",          "atk": 6, "def": 4,  "specials": []},
    {"name": "Blackhole",      "atk": 7, "def": 3,  "specials": []},
    {"name": "BlackholeAtlas", "atk": 6, "def": 6,  "specials": []},
    {"name": "Greedatlas",     "atk": 5, "def": 5,  "specials": []},
    {"name": "Breaker",        "atk": 4, "def": 6,  "specials": []},
    {"name": "Mirror",         "atk": 2, "def": 7,  "specials": []},
    {"name": "Milktoken",      "atk": 1, "def": 2,  "specials": []},
]
