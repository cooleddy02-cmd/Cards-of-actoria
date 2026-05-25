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
    {"name":"Undying",      "atk":0,"def":1, "specials":[
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
    {"name":"Blackhole",    "atk":0,"def":3, "specials":[]},
    {"name":"Milktoken",    "atk":1,"def":1,"no_draw":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."}]},
    {"name":"Golem",        "atk":0,"def":5, "specials":[
        {"id":"golem_regen","name":"Construction","desc":"Each turn: gains +5 DEF (stops after flip)."},
        {"id":"golem_flip","name":"Flip","desc":"After 4 turns: ATK becomes current DEF, DEF resets to 1."},
        {"id":"golem_immune_friendly","name":"Inert","desc":"Cannot be buffed by cards on your own side."},
        {"id":"golem_banish","name":"Banish","desc":"When destroyed, banished — no revive and no death effects."}]},
    {"name":"Sad Dream",    "atk":0,"def":2,"block":1, "specials":[
        {"id":"sad_no_draw","name":"Nightmare","desc":"You can't draw cards. Your opponent draws +1 each turn while this is on the field."},
        {"id":"sad_send","name":"Pass On","desc":"Once: spend 3 HP to send this card to your opponent's side."},
        {"id":"sad_self_damage","name":"Sorrow","desc":"Every 4 turns: deals 4 damage to its owner."},
        {"id":"no_revive","name":"No Revive","desc":"Cannot be revived."},
        {"id":"no_sacrifice","name":"No Sacrifice","desc":"Cannot be sacrificed."}]},
    {"name":"Amegma",       "atk":2,"def":2, "specials":[
        {"id":"amegma_free_attack","name":"Free Aim","desc":"Can attack any enemy card on the field, ignoring slot lock."},
        {"id":"amegma_block_break","name":"Block Crush","desc":"When attacking a card with block: removes all block but deals no damage that attack."}]},
    {"name":"Ice",          "atk":1,"def":3, "specials":[
        {"id":"ice_counter_freeze","name":"Ice Shield","desc":"When hit: freezes the attacker so it can't attack next turn."},
        {"id":"frost_breath","name":"Frost Breath","desc":"Active: freeze all enemy cards for 1 turn, but they take 50% less damage for 2 turns."},
        {"id":"ice_cream_ability","name":"Ice Cream","desc":"Active: give a card +2 ATK +1 DEF for 2 turns and heal yourself 2 HP. 5-turn cooldown."}]},
    {"name":"Ace",        "atk":5,"def":5, "no_normal_play":True, "specials":[
        {"id":"ace_sac","name":"Sacrifice Summon","desc":"Summon by sacrificing 2 cards from your field. Cannot be played normally."}]},
    {"name":"Lich",       "atk":4,"def":3, "no_normal_play":True, "specials":[
        {"id":"lich_sac","name":"Sacrifice Summon","desc":"Summon by sacrificing 3 cards from your field. Cannot be played normally."},
        {"id":"lich_def_leech","name":"Soul Drain","desc":"Gains DEF equal to half the damage it deals."},
        {"id":"lich_death_buff","name":"Death Boon","desc":"When destroyed, all remaining ally cards gain +1 ATK +1 DEF."}]},
    {"name":"Omega",      "atk":4,"def":10, "no_normal_play":True, "specials":[
        {"id":"omega_sac","name":"Sacrifice Summon","desc":"Summon by sacrificing 3 cards from your field. Cannot be played normally."},
        {"id":"omega_end_dmg","name":"Omega Pulse","desc":"Each of your turns: deals 1 damage to the opponent."},
        {"id":"omega_atk_lock","name":"Absolute Force","desc":"ATK cannot go below its base amount."}]},
    {"name":"Void Singularity", "atk":0,"def":15, "no_normal_play":True, "specials":[
        {"id":"bhole_sac","name":"Sacrifice Summon","desc":"Summon by sacrificing 3 cards from your field. Cannot be played normally."},
        {"id":"bhole_pull","name":"Void Pull","desc":"Enemy cards can only attack this card."},
        {"id":"bhole_atlas_summon","name":"Atlas Summon","desc":"Once per turn: summon Atlas BHH to your field, lose 4 HP."}]},
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
    {"name":"Trio-Sword",  "atk":4,"def":2, "no_draw":True,"evo":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."},
        {"id":"trio_sword_tri","name":"Triple Strike","desc":"Attacks left, middle, and right of opponent's field separately. Not counted as AoE."},
        {"id":"no_sacrifice","name":"No Sacrifice","desc":"Cannot be sacrificed."}]},
    {"name":"The Star",    "atk":0,"def":3, "no_draw":True,"evo":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."},
        {"id":"guard_immunity","name":"Star Shield","desc":"Cannot take damage or be destroyed for its first 2 turns on the field."},
        {"id":"star_col_dmg","name":"Column Burn","desc":"The enemy card in the same column takes 2 damage every turn."},
        {"id":"star_aoe_block","name":"Anti-AoE","desc":"While on field, all enemy AoE attacks are negated."},
        {"id":"no_sacrifice","name":"No Sacrifice","desc":"Cannot be sacrificed."},
        {"id":"no_revive","name":"No Revive","desc":"Cannot be revived."}]},
    {"name":"Atlas BHH",   "atk":0,"def":10,"no_draw":True,"evo":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."},
        {"id":"guard_immunity","name":"Heavy Armor","desc":"Cannot take damage or be destroyed for its first 2 turns on the field."},
        {"id":"atlas_bhh_pull","name":"Atlas Pull","desc":"Enemy cards can only attack this card."},
        {"id":"atlas_bhh_self_pull","name":"Gravity Well","desc":"Once: destroy this card to send one enemy field card back to their hand."},
        {"id":"atlas_bhh_death_dmg","name":"Collapse","desc":"When destroyed, owner takes 2 damage."},
        {"id":"no_revive","name":"No Revive","desc":"Cannot be revived."}]},
    {"name":"Atlas Greed", "atk":3,"def":3, "no_draw":True,"evo":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."},
        {"id":"atlas_greed_draw","name":"Endless Greed","desc":"Each turn: draw +1 extra card. Does not stack with other Greed cards."},
        {"id":"atlas_greed_death_dmg","name":"Greed's Toll","desc":"When destroyed, owner takes 3 damage."},
        {"id":"atlas_greed_nodraw","name":"Lockout","desc":"Active (once per 2 turns): force your opponent to skip their next draw."}]},
    {"name":"Angel of End","atk":0,"def":15,"block":4,"no_draw":True,"evo":True, "specials":[
        {"id":"no_draw_flag","name":"Special Only","desc":"Cannot be drawn normally."},
        {"id":"angel_no_defuse","name":"Inviolable","desc":"Cannot be countered by hand traps."},
        {"id":"angel_block_kill","name":"Block Guard","desc":"Instant-kill effects only work when all blocks are gone."},
        {"id":"angel_dynamic_atk","name":"Apex Power","desc":"ATK equals the highest ATK of any card on the field."},
        {"id":"golem_banish","name":"Banished","desc":"When destroyed, it is banished — no death effects trigger."},
        {"id":"angel_emp","name":"E.M.P.","desc":"Once, when DEF ≤ 10 and your HP is below half: remove all specials from every other card for 4 turns."}]},
]

ALL_CARDS = CARDLIST + SPECIAL_CARDS

DECK_WEIGHTS = {}

DECK_POOLS = {
    'basic':    ['Sword','Guard','Health','Clock','Star','Circus','Block','Bolt',
                 'Mirror','Greed','Apple','Side','Love','Diamond'],
    'brawler':  ['Sword','Diamond','Hate','Wrath','Bolt','Duraza','Side',
                 'Amegma','Hate','Sword','Diamond','Bolt'],
    'guardian': ['Guard','Health','Love','Block','CoreStars','Breaker',
                 'CancelBlock','Ice','Apple','Guard','Health','Block'],
    'mystic':   ['Clock','Mirror','Fisher','Undying','Rewind','Unknown',
                 'Clocksmilk','Clock','Mirror','Fisher','Rewind','Unknown'],
    'chaos':    ['Star','v1-8','Greed','Equal','Circus','Mysteriousash',
                 'Star','v1-8','Equal','Circus','Greed','Sad Dream'],
    'storm':    ['Amegma','Ice','Bolt','Sun','Side','Blackhole',
                 'Amegma','Ice','Bolt','Sun','Mysteriousash','Wrath'],
    'dream':    ['Sad Dream','Mirror','Greed','Circus','Equal','Unknown',
                 'Sad Dream','Mirror','Greed','Star','v1-8','Love'],
    'titan':    ['Golem','Duraza','Block','Apple','Health','Guard',
                 'Golem','Duraza','Block','CancelBlock','CoreStars','Ice'],
    # ── NEW RIVAL DECKS ──
    'venom':    ['Greed','Sad Dream','Sun','Mysteriousash','Equal','Hate',
                 'Bolt','v1-8','Star','Amegma','Circus','Love'],
    'phoenix':  ['Mysteriousash','Rewind','Love','Apple','Health','Undying',
                 'Clocksmilk','Wrath','Ice','Guard','Circus','Star'],
    'warlord':  ['Sword','Apple','Diamond','Hate','Wrath','Side',
                 'Duraza','Blackhole','Hate','Bolt','Equal','Star'],
    'trickster':['Circus','Mirror','Unknown','Clock','Fisher','Rewind',
                 'Star','Side','v1-8','Equal','Greed','Sad Dream'],
}

DECK_COUNTERS = {
    'basic':    'Balanced — no strong counter, but no edge either.',
    'brawler':  'Beats Guardian (raw pierce). Loses to Storm (status slows) & Phoenix (revives outlast).',
    'guardian': 'Beats Storm (blocks + heals through it). Loses to Brawler & Warlord (big sacrifices break blocks).',
    'mystic':   'Beats Dream (cancels curses) & Venom (cancels DoT). Loses to Chaos (disruption).',
    'chaos':    'Beats Mystic (breaks combos) & Phoenix (banishes revives). Loses to Titan (durable).',
    'storm':    'Beats Brawler (slows attackers). Loses to Guardian & Trickster (bounces AoE setups).',
    'dream':    'Beats Titan (curses bypass armor). Loses to Mystic.',
    'titan':    'Beats Chaos (weathers RNG). Loses to Dream (curses) & Venom (DoT chips through DEF).',
    'venom':    'Beats Titan (poison bypasses armor). Loses to Mystic (cancels DoT) & Phoenix (rebirth burns curses).',
    'phoenix':  'Beats Brawler (revives outlast kills) & Venom (rebirth wipes DoT). Loses to Chaos (banish stops revives) & Warlord (mass sacrifice eats revives).',
    'warlord':  'Beats Guardian (one big strike breaks blocks). Loses to Trickster (bounces big summons) & Phoenix.',
    'trickster':'Beats Storm (returns AoE before it fires) & Warlord (bounces boss plays). Loses to Venom (DoT outlasts tricks).',
}

DECK_INFO = [
    {'id':'basic',    'name':'Starter Deck',  'icon':'🃏','cost':0,
     'desc':'Balanced mix. Perfect for learning. ⚖️ No counter advantage.'},
    {'id':'brawler',  'name':'Brawler Deck',  'icon':'⚔️','cost':15,
     'desc':'Raw ATK + pierce. ✅ Beats Guardian.  ❌ Loses to Storm & Phoenix.'},
    {'id':'guardian', 'name':'Guardian Deck', 'icon':'🛡️','cost':15,
     'desc':'Block + regen. ✅ Beats Storm.  ❌ Loses to Brawler & Warlord.'},
    {'id':'mystic',   'name':'Mystic Deck',   'icon':'🔮','cost':20,
     'desc':'Cancel + control. ✅ Beats Dream & Venom.  ❌ Loses to Chaos.'},
    {'id':'chaos',    'name':'Chaos Deck',    'icon':'🌀','cost':25,
     'desc':'RNG disruption. ✅ Beats Mystic & Phoenix.  ❌ Loses to Titan.'},
    {'id':'storm',    'name':'Storm Deck',    'icon':'🌩️','cost':20,
     'desc':'Status + AoE. ✅ Beats Brawler.  ❌ Loses to Guardian & Trickster.'},
    {'id':'dream',    'name':'Dream Deck',    'icon':'🌙','cost':25,
     'desc':'Curse + mirror. ✅ Beats Titan.  ❌ Loses to Mystic.'},
    {'id':'titan',    'name':'Titan Deck',    'icon':'🏔️','cost':30,
     'desc':'Heavy defense. ✅ Beats Chaos.  ❌ Loses to Dream & Venom.'},
    {'id':'venom',    'name':'Venom Deck',    'icon':'🐍','cost':30,
     'desc':'Poison + decay. Chips through any armor. ✅ Beats Titan.  ❌ Loses to Mystic & Phoenix.'},
    {'id':'phoenix',  'name':'Phoenix Deck',  'icon':'🔥','cost':35,
     'desc':'Revive + rebirth. Comes back swinging. ✅ Beats Brawler & Venom.  ❌ Loses to Chaos & Warlord.'},
    {'id':'warlord',  'name':'Warlord Deck',  'icon':'⚜️','cost':35,
     'desc':'Sacrifice for boss plays. ✅ Beats Guardian.  ❌ Loses to Trickster & Phoenix.'},
    {'id':'trickster','name':'Trickster Deck','icon':'🎭','cost':30,
     'desc':'Bounce + mirror + quick. ✅ Beats Storm & Warlord.  ❌ Loses to Venom.'},
]

GEM_REWARDS = {'easy':10,'medium':25,'hard':50}
BOT_NAMES   = {'easy':'Rookie 🤖','medium':'Fighter 🤖','hard':'Champion 🤖'}
BOT_DECKS   = {'easy':'basic','medium':'guardian','hard':'brawler'}
