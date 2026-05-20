import copy, random

CARDLIST = [
    {"name":"Circus",       "atk":2,"def":2, "specials":[
        {"id":"circus_bounce","name":"Bounce","desc":"Once per 2 turns: return one of your field cards back to your hand."}]},
    {"name":"Star",         "atk":0,"def":0, "specials":[
        {"id":"star_reroll","name":"Reroll","desc":"Each turn: 20% nothing, 40% +6 DEF, 40% +6 ATK."}]},
    {"name":"Love",         "atk":0,"def":4, "specials":[
        {"id":"love_heal","name":"Last Gift","desc":"When destroyed, owner heals +4 HP."}]},
    {"name":"Diamond",      "atk":4,"def":0, "specials":[
        {"id":"diamond_gain","name":"Greed Cut","desc":"When this card destroys another, gains +1 ATK +1 DEF."}]},
    {"name":"Health",       "atk":0,"def":2, "specials":[
        {"id":"health_regen","name":"Regenerate","desc":"Every 2 turns, heals owner for 4 HP."}]},
    {"name":"Bolt",         "atk":2,"def":0, "specials":[
        {"id":"bolt_pierce","name":"Pierce","desc":"Ignores DEF: deals damage to both the card AND the player."}]},
    {"name":"Equal",        "atk":1,"def":1, "specials":[
        {"id":"equal_revenge","name":"Equalise","desc":"If destroyed within 4 turns of being played, both players take 4 damage."}]},
    {"name":"Sun",          "atk":0,"def":0, "specials":[
        {"id":"sun_aoe","name":"Sunray","desc":"Each turn, deals 1 damage to all enemy cards."}]},
    {"name":"Side",         "atk":3,"def":3, "specials":[
        {"id":"side_aoe","name":"Sweep","desc":"Attacks all enemy cards at once. Cannot deal direct damage to player."},
        {"id":"side_death","name":"Collapse","desc":"When destroyed, deals 4 damage to own player."}]},
    {"name":"Hate",         "atk":5,"def":2, "specials":[
        {"id":"hate_selfdmg","name":"Bloodlust","desc":"When this card attacks, it also deals damage to own player."}]},
    {"name":"Guard",        "atk":0,"def":3, "specials":[
        {"id":"guard_immunity","name":"Fortify","desc":"Cannot take damage or be destroyed for its first 2 turns on the field."}]},
    {"name":"Apple",        "atk":1,"def":1, "specials":[
        {"id":"apple_buff","name":"Nourish","desc":"Sacrifice to give a card +2 DEF +1 ATK."},
        {"id":"apple_undying","name":"Nourish+","desc":"If used on Undying: +2/+2 and survives one lethal hit."}]},
    {"name":"Clocksmilk",   "atk":0,"def":4, "specials":[
        {"id":"milk_summon","name":"Milk Token","desc":"After 1 turn: each turn may summon a Milk Token."},
        {"id":"milk_drink","name":"Milk Drink","desc":"Destroy a Milk Token to heal 2 HP."}]},
    {"name":"Greed",        "atk":0,"def":4, "specials":[
        {"id":"greed_draw","name":"Greed Draw","desc":"Each turn: draw +1 extra card."},
        {"id":"greed_decay","name":"Decay","desc":"Each turn, all your cards lose 1 DEF (min -5)."},
        {"id":"greed_death","name":"Toll","desc":"When destroyed, owner takes 4 damage."},
        {"id":"greed_atlas","name":"Atlas Summon","desc":"Once per turn: summon Atlas, lose 2 HP."}]},
    {"name":"v1-8",         "atk":0,"def":-1, "specials":[
        {"id":"v18_reroll","name":"Variable","desc":"On summon/revive, ATK rerolls 0–8."}]},
    {"name":"Sword",        "atk":3,"def":2, "specials":[
        {"id":"sword_buff","name":"Sharpen","desc":"Sacrifice to give a card +2 ATK."},
        {"id":"sword_nosac","name":"Bound","desc":"Cannot be sacrificed except for Trio-Sword."}]},
    {"name":"Duraza",       "atk":2,"def":4, "specials":[
        {"id":"duraza_dual","name":"Double Strike","desc":"Attacks twice (2x2 damage)."},
        {"id":"no_revive","name":"No Revive","desc":"Cannot be revived."},
        {"id":"no_sacrifice","name":"No Sacrifice","desc":"Cannot be sacrificed."},
        {"id":"duraza_hit_limit","name":"Resilient","desc":"Can only be hit once per turn."},
        {"id":"duraza_def_lock","name":"Iron DEF","desc":"DEF cannot be lowered by special abilities."}]},
    {"name":"Mysteriousash","atk":0,"def":1, "specials":[
        {"id":"ash_phoenix","name":"Ash Rising","desc":"If destroyed within 5 turns, summons Phoenix."}]},
    {"name":"Wrath",        "atk":2,"def":3,"atk_max":6, "specials":[
        {"id":"wrath_rage","name":"Rage","desc":"Gains +1 ATK each turn (max 6)."},
        {"id":"wrath_direct","name":"Direct Attack","desc":"Can attack the player directly."},
        {"id":"no_sacrifice","name":"No Sacrifice","desc":"Cannot be sacrificed."},
        {"id":"aoe_immune","name":"AoE Immune","desc":"Cannot be hit by AoE attacks."},
        {"id":"no_revive","name":"No Revive","desc":"Cannot be revived."}]},
    {"name":"CancelBlock",  "atk":1,"def":3,"block":2,"block_max":3, "specials":[
        {"id":"block_recharge","name":"Block Recharge","desc":"Gains +1 block every 4 turns (max 3)."}]},
    {"name":"Block",        "atk":0,"def":2,"block":1, "specials":[
        {"id":"block_shield","name":"Shield","desc":"Can be placed on a friendly card to absorb damage."}]},
    {"name":"Unknown",      "atk":1,"def":3, "specials":[
        {"id":"aoe_immune","name":"AoE Immune","desc":"Cannot be hit by AoE damage."},
        {"id":"unknown_copy","name":"Mirror Stats","desc":"After 3 turns, gains ATK/DEF of the enemy card opposite to it."}]},
    {"name":"Rewind",       "atk":0,"def":0, "specials":[
        {"id":"rewind_quick","name":"Time Steal","desc":"Quick effect: destroy to take your turn. Take 3 damage, can't draw/deal damage. Once per 2 turns."},
        {"id":"rewind_play","name":"Rewind","desc":"On play: revive last friendly dead card with +2 DEF. Destroyed after 3 turns."}]},
    {"name":"Undying",      "atk":0,"def":-1, "specials":[
        {"id":"undying_donut","name":"Donut","desc":"Each turn: give a friendly card +1/+1 (max 2 donuts per card)."}]},
    {"name":"Fisher",       "atk":0,"def":3, "specials":[
        {"id":"fisher_pull","name":"Abyssal Pull","desc":"Once per turn: flip coin. Heads=Light Fish, Tails=Dark Fish."},
        {"id":"fisher_catch","name":"Abyss Catch","desc":"Use Fish: Light=target +2 DEF, Dark=enemy -2 ATK for 3 turns."},
        {"id":"fisher_share","name":"Catch Share","desc":"Give 1 Fish to another card."}]},
    {"name":"Clock",        "atk":1,"def":1, "specials":[
        {"id":"quick_effect","name":"Quick Effect","desc":"Discard to cancel an enemy attack or summon. Once per turn."},
        {"id":"freeze","name":"Freeze","desc":"On attack: target cannot use effects until end of your next turn."}]},
    {"name":"Mirror",       "atk":1,"def":2, "specials":[
        {"id":"mirror_reflect","name":"Reflect","desc":"When attacked, reflects exact damage back to the attacker. Bypasses block."}]},
    {"name":"Breaker",      "atk":0,"def":4,"block":1, "specials":[
        {"id":"breaker_destroy","name":"Block Break","desc":"When destroyed: removes all enemy block. Enemy takes 1 damage per block removed."}]},
    {"name":"CoreStars",    "atk":0,"def":5, "specials":[
        {"id":"core_dark_star","name":"Dark Star","desc":"Every 2 turns: place a Dark Star on an enemy card (-1 DEF/turn, max 4)."},
        {"id":"no_sacrifice","name":"No Sacrifice","desc":"Cannot be sacrificed."},
        {"id":"no_revive","name":"No Revive","desc":"Cannot be revived."}]},
    {"name":"Blackhole",    "atk":7,"def":3, "specials":[]},
    {"name":"Milktoken",    "atk":1,"def":1,"no_draw":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."}]},
]

SPECIAL_CARDS = [
    {"name":"Atlas",        "atk":0,"def":0,"no_draw":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."},
        {"id":"atlas_combine","name":"Fusion Ready","desc":"After 4 turns, can combine with Greed or Blackhole."},
        {"id":"no_revive","name":"No Revive","desc":"Cannot be revived."}]},
    {"name":"Phoenix",      "atk":1,"def":6,"no_draw":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."},
        {"id":"phoenix_revive","name":"Rebirth","desc":"When destroyed, revives once at full DEF."},
        {"id":"phoenix_burn","name":"Scorch","desc":"On attack: target gains Burn (-1 DEF/turn for 3 turns)."}]},
    {"name":"BlackholeAtlas","atk":6,"def":6,"no_draw":True,"specials":[]},
    {"name":"GreedAtlas",   "atk":5,"def":5,"no_draw":True,"specials":[]},
]

ALL_CARDS = CARDLIST + SPECIAL_CARDS

DECK_WEIGHTS = {
    'basic':    {},
    'brawler':  {'Hate':4,'Bolt':4,'Diamond':4,'Sword':4,'Wrath':4,'Duraza':4,'Side':4,'Blackhole':4},
    'guardian': {'Guard':4,'Health':4,'Love':4,'CoreStars':4,'Breaker':4,'CancelBlock':4,'Block':4},
    'mystic':   {'Clock':4,'Mirror':4,'Fisher':4,'Undying':4,'Clocksmilk':4,'Unknown':4},
    'chaos':    {'Star':4,'v1-8':4,'Greed':4,'Equal':4,'Circus':4,'Mysteriousash':4},
}

DECK_INFO = [
    {'id':'basic',   'name':'Starter Deck', 'icon':'🃏','cost':0,
     'desc':'A balanced mix of all cards. Perfect for learning.'},
    {'id':'brawler', 'name':'Brawler Deck', 'icon':'⚔️','cost':15,
     'desc':'High-damage cards. Pierce, cleave, and overwhelm your opponent.'},
    {'id':'guardian','name':'Guardian Deck','icon':'🛡️','cost':15,
     'desc':'Defensive powerhouse. Block, regenerate, and outlast your foes.'},
    {'id':'mystic',  'name':'Mystic Deck',  'icon':'🔮','cost':20,
     'desc':'Ability-focused. Trap, reflect, and control the battlefield.'},
    {'id':'chaos',   'name':'Chaos Deck',   'icon':'🌀','cost':25,
     'desc':'Unpredictable wildcards. High risk, high reward.'},
]

GEM_REWARDS = {'easy':2,'medium':4,'hard':7}
BOT_NAMES   = {'easy':'Rookie 🤖','medium':'Fighter 🤖','hard':'Champion 🤖'}
BOT_DECKS   = {'easy':'basic','medium':'guardian','hard':'brawler'}
