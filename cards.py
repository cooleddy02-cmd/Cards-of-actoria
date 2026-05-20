import copy
import random

# ── Drawable cards ─────────────────────────────────────────────────────────────
CARDLIST = [
    {"name": "Circus",       "atk": 2, "def": 2,  "specials": [
        {"id": "circus_bounce", "name": "Bounce",
         "desc": "Once per 2 turns: return one of your field cards back to your hand."}
    ]},
    {"name": "Star",         "atk": 0, "def": 0,  "specials": [
        {"id": "star_reroll", "name": "Reroll",
         "desc": "Each turn: 20% nothing, 40% gain 6 DEF, 40% gain 6 ATK."}
    ]},
    {"name": "Love",         "atk": 0, "def": 4,  "specials": [
        {"id": "love_heal", "name": "Last Gift",
         "desc": "When destroyed, owner heals +4 HP (can exceed max)."}
    ]},
    {"name": "Diamond",      "atk": 4, "def": 0,  "specials": [
        {"id": "diamond_gain", "name": "Greed Cut",
         "desc": "When this card destroys another, gains +1 ATK +1 DEF."}
    ]},
    {"name": "Health",       "atk": 0, "def": 2,  "specials": [
        {"id": "health_regen", "name": "Regenerate",
         "desc": "Every 2 turns, heals owner for 4 HP."}
    ]},
    {"name": "Bolt",         "atk": 2, "def": 0,  "specials": [
        {"id": "bolt_pierce", "name": "Pierce",
         "desc": "Ignores DEF — deals damage to both the card AND the player."}
    ]},
    {"name": "Equal",        "atk": 1, "def": 1,  "specials": [
        {"id": "equal_revenge", "name": "Equalise",
         "desc": "If destroyed within 4 turns of being played, both players take 4 damage."}
    ]},
    {"name": "Sun",          "atk": 0, "def": 0,  "specials": [
        {"id": "sun_aoe", "name": "Sunray",
         "desc": "Each turn, deals 1 damage to all enemy cards."}
    ]},
    {"name": "Side",         "atk": 3, "def": 3,  "specials": [
        {"id": "side_aoe", "name": "Sweep",
         "desc": "Attacks all enemy cards at once. Cannot deal direct damage to player."},
        {"id": "side_death", "name": "Collapse",
         "desc": "When destroyed, deals 4 damage to own player."}
    ]},
    {"name": "Hate",         "atk": 5, "def": 2,  "specials": [
        {"id": "hate_selfdmg", "name": "Bloodlust",
         "desc": "When this card attacks, it also deals damage to own player."}
    ]},
    {"name": "Guard",        "atk": 0, "def": 3,  "specials": [
        {"id": "guard_immunity", "name": "Fortify",
         "desc": "Cannot take damage or be destroyed for its first 2 turns on the field."}
    ]},
    {"name": "Apple",        "atk": 1, "def": 1,  "specials": [
        {"id": "apple_buff", "name": "Nourish",
         "desc": "Sacrifice from hand or field to give target card +2 DEF +1 ATK."},
        {"id": "apple_undying", "name": "Nourish (Undying)",
         "desc": "If used on Undying: +2 ATK +2 DEF and Undying can survive one lethal hit."}
    ]},
    {"name": "Clocksmilk",   "atk": 0, "def": 4,  "specials": [
        {"id": "milk_summon", "name": "Milk Token",
         "desc": "After 1 turn on field: each turn you may summon a Milk Token."},
        {"id": "milk_drink", "name": "Milk Drink",
         "desc": "Destroy a Milk Token to heal 2 HP. Requires Clock's Milk to be alive."}
    ]},
    {"name": "Greed",        "atk": 0, "def": 4,  "specials": [
        {"id": "greed_draw",  "name": "Greed Draw",
         "desc": "Each of your turns: draw +1 extra card (does not stack with multiple Greeds)."},
        {"id": "greed_decay", "name": "Greed Decay",
         "desc": "Each turn, all your cards lose 1 DEF (min −5)."},
        {"id": "greed_death", "name": "Greed's Toll",
         "desc": "When destroyed, owner takes 4 damage."},
        {"id": "greed_atlas", "name": "Atlas Summon",
         "desc": "Once per turn: special-summon Atlas, lose 2 HP."}
    ]},
    {"name": "v1-8",         "atk": 0, "def": -1, "specials": [
        {"id": "v18_reroll", "name": "Variable",
         "desc": "When summoned or revived, ATK is rerolled randomly from 0 to 8."}
    ]},
    {"name": "Sword",        "atk": 3, "def": 2,  "specials": [
        {"id": "sword_buff", "name": "Sharpen",
         "desc": "Sacrifice from hand or field to give target card +2 ATK."},
        {"id": "sword_nosac", "name": "Bound",
         "desc": "Cannot be sacrificed to summon other cards (except Trio-Sword)."}
    ]},
    {"name": "Duraza",       "atk": 2, "def": 4,  "specials": [
        {"id": "duraza_dual",      "name": "Double Strike",  "desc": "Attacks twice (2×2 damage)."},
        {"id": "no_revive",        "name": "No Revive",      "desc": "Cannot be revived."},
        {"id": "no_sacrifice",     "name": "No Sacrifice",   "desc": "Cannot be sacrificed."},
        {"id": "duraza_hit_limit", "name": "Resilient",      "desc": "Can only be hit once per turn."},
        {"id": "duraza_def_lock",  "name": "Iron DEF",       "desc": "DEF cannot be lowered by special abilities."}
    ]},
    {"name": "Mysteriousash","atk": 0, "def": 1,  "specials": [
        {"id": "ash_phoenix", "name": "Ash Rising",
         "desc": "If destroyed within 5 turns of being summoned, summons Phoenix."}
    ]},
    {"name": "Wrath",        "atk": 2, "def": 3,  "atk_max": 6, "specials": [
        {"id": "wrath_rage",     "name": "Rage",         "desc": "Gains +1 ATK each turn (max 6)."},
        {"id": "wrath_direct",   "name": "Direct Attack","desc": "Can attack the player directly."},
        {"id": "no_sacrifice",   "name": "No Sacrifice", "desc": "Cannot be sacrificed."},
        {"id": "aoe_immune",     "name": "AoE Immune",   "desc": "Cannot be hit by AoE attacks."},
        {"id": "no_revive",      "name": "No Revive",    "desc": "Cannot be revived."}
    ]},
    {"name": "CancelBlock",  "atk": 1, "def": 3, "block": 2, "block_max": 3, "specials": [
        {"id": "block_recharge", "name": "Block Recharge",
         "desc": "Gains +1 block every 4 turns (max 3)."}
    ]},
    {"name": "Block",        "atk": 0, "def": 2, "block": 1,  "specials": [
        {"id": "block_shield", "name": "Shield",
         "desc": "Can be placed on a friendly card to absorb all damage it would take."}
    ]},
    {"name": "Unknown",      "atk": 1, "def": 3,  "specials": [
        {"id": "aoe_immune",    "name": "AoE Immune",    "desc": "Cannot be hit by AoE damage."},
        {"id": "unknown_copy",  "name": "Mirror Stats",
         "desc": "After 3 turns, gains the ATK and DEF of the enemy card opposite to it."}
    ]},
    {"name": "Rewind",       "atk": 0, "def": 0,  "specials": [
        {"id": "rewind_quick",  "name": "Time Steal",
         "desc": "Quick effect (opponent's turn): destroy this card to take your turn. You take 3 damage, can't draw or deal damage. Once per 2 turns."},
        {"id": "rewind_play",   "name": "Rewind",
         "desc": "On play: revive last friendly dead card in original position with +2 DEF. Destroyed after 3 turns. On-destroy effects skip."}
    ]},
    {"name": "Undying",      "atk": 0, "def": -1, "specials": [
        {"id": "undying_donut", "name": "Donut",
         "desc": "Each turn: give a friendly card +1 ATK +1 DEF (max 2 donuts per card, can't target self)."}
    ]},
    {"name": "Fisher",       "atk": 0, "def": 3,  "specials": [
        {"id": "fisher_pull",  "name": "Abyssal Pull",
         "desc": "Once per turn: flip a coin. Heads = gain 1 Light Fish. Tails = gain 1 Dark Fish."},
        {"id": "fisher_catch", "name": "Abyss Catch",
         "desc": "Consume 1 Fish: Light Fish = target gets +2 DEF. Dark Fish = enemy card gets −2 ATK for 3 turns."},
        {"id": "fisher_share", "name": "Catch Share",
         "desc": "Give 1 of your Fish to another card."}
    ]},
    {"name": "Clock",        "atk": 1, "def": 1,  "specials": [
        {"id": "quick_effect", "name": "Quick Effect",
         "desc": "Discard to cancel an enemy attack or summon. Once per turn."},
        {"id": "freeze", "name": "Freeze",
         "desc": "On attack: target cannot use effects until end of your next turn."}
    ]},
    {"name": "Mirror",       "atk": 1, "def": 2,  "specials": [
        {"id": "mirror_reflect", "name": "Reflect",
         "desc": "When attacked, reflects exact damage back to the attacker. Reflected damage ignores the player even if overkill. Bypasses block."}
    ]},
    {"name": "Breaker",      "atk": 0, "def": 4, "block": 1,  "specials": [
        {"id": "breaker_destroy", "name": "Block Break",
         "desc": "When destroyed: removes all block from enemy cards. Enemy player takes 1 damage per block removed."}
    ]},
    {"name": "CoreStars",    "atk": 0, "def": 5,  "specials": [
        {"id": "core_dark_star", "name": "Dark Star",
         "desc": "Every 2 turns: place a Dark Star on an enemy card. Each star removes 1 DEF per turn (max 4 stars). Card destroyed at 0 DEF."},
        {"id": "no_sacrifice", "name": "No Sacrifice", "desc": "Cannot be sacrificed."},
        {"id": "no_revive",    "name": "No Revive",    "desc": "Cannot be revived."}
    ]},
    {"name": "Blackhole",    "atk": 7, "def": 3,  "specials": []},
    {"name": "Milktoken",    "atk": 1, "def": 1,  "no_draw": True, "specials": [
        {"id": "no_draw_flag", "name": "Special Summon Only",
         "desc": "Cannot be drawn into your hand normally."}
    ]},
]

# ── Non-drawable / special-summon only cards ──────────────────────────────────
SPECIAL_CARDS = [
    {"name": "Atlas",        "atk": 0, "def": 0, "no_draw": True, "specials": [
        {"id": "no_draw_flag", "name": "Special Summon Only", "desc": "Cannot be drawn normally."},
        {"id": "atlas_combine","name": "Fusion Ready",
         "desc": "After 4 turns on field, can combine with Greed or Blackhole."},
        {"id": "no_revive",    "name": "No Revive", "desc": "Cannot be revived."}
    ]},
    {"name": "Phoenix",      "atk": 1, "def": 6, "no_draw": True, "specials": [
        {"id": "no_draw_flag",    "name": "Special Summon Only", "desc": "Cannot be drawn normally."},
        {"id": "phoenix_revive",  "name": "Rebirth",
         "desc": "When destroyed, revives once at full DEF."},
        {"id": "phoenix_burn",    "name": "Scorch",
         "desc": "When this card attacks, target gains Burn: −1 DEF/turn for 3 turns."}
    ]},
    {"name": "BlackholeAtlas","atk": 6, "def": 6, "no_draw": True, "specials": []},
    {"name": "GreedAtlas",   "atk": 5, "def": 5, "no_draw": True, "specials": []},
]

ALL_CARDS = CARDLIST + SPECIAL_CARDS
