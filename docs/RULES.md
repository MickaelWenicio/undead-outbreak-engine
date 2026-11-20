# Simulation rules

These rules are fixed from the first to the last day of every run: nothing changes mid-simulation, and no event is placed by hand. The only thing decided outside the engine is the choice of protagonists, made by rule on day zero, before the run starts. The exact numbers live in `config.py`.

## The undead

- **The bite.** A bitten person who survives turns within 2 to 24 hours (most often around 7).
- **Rising.** Anyone killed by the undead with the body intact rises within 10 to 60 minutes. A torn-apart body does not rise.
- **Stopping one.** Only a destroyed head, a dismembered body or a body burned until it gives way. A severed arm stops nothing. They feel no pain, never retreat and never tire.
- **Fire.** A burning corpse keeps attacking for a while and can set roofs on fire.
- **Speed.** They run after whoever they see or smell. With no prey nearby, they wander slowly.
- **Cold.** With nobody around they stand still; once they sense flesh, they wake and attack.
- **One-on-one fights** (resolved in rounds until one side falls):
  - a peasant with a tool almost always loses;
  - a soldier in chain mail wins a little over half the time;
  - a knight in full plate wins about 7 times in 10, and still gets bitten in one fight out of three;
  - three or four armed people together bring one down with relative safety.
- **Shelter.** A house door holds a few hours of pounding, longer if barricaded. Palisades and walls hold until the dead pile up and climb. Gates give way over time.
- **They learn.** Over time the dead surround houses and wait, pile up to climb, set ambushes on roads, look for the weak point and force gates together.
- **Expiry.** Every corpse has a deadline counted from when it rises:
  - a base of 200 to 295 days, most often around 260;
  - each person killed by the dead of a place adds 4 days, split among the dead there (a bite counts as a quarter of a person, and so does a farm animal), with at most 3 days gained per day;
  - winter preserves the body, so the deadline runs at half speed;
  - when it runs out, the body falls apart for good.

## What the living don't know at first

That a bite turns you, that the dead rise, and that only the head stops them. People learn by seeing it or from the news brought by those who flee. Until then they care for the bitten and hold wakes for the dead.

## The kingdom

- **Population:** about 10,000 people.
- **Walled capital:** about 3,500 inhabitants in four districts plus the king's citadel.
- **Other places:** three towns (one of them a port), about 18 villages, two noble castles, a monastery and a mine.
- **Social classes:** king and court, nobles, knights, soldiers, clergy, merchants, craftsmen, peasants, fishermen, woodcutters, miners, children and the elderly.
- **Economy:**
  - every trade produces; villages buy and sell, and prices rise with scarcity;
  - wood and carpentry become barricades and palisades, and blacksmiths make spears and armor;
  - the story starts in mid-September, right after the harvest, and the harvest returns every September;
  - granaries hold food for 200 days in a village, 150 in a town, 200 in a castle or monastery, 240 in the citadel, 90 in a capital district and 60 in the mine;
  - food expeditions scale with need: up to 60 men carrying 25 rations each, or 60 with a cart.

## The people

- **Attributes.** Faith, temper, cunning, courage, loyalty, ambition, cruelty and mercy. People and leaders decide by them and by what they know.
- **Decisions** cover gates, refugees, the bitten and the bodies, barricades, weapons, flight and evacuation, calls for help and sending soldiers.
- **Fights among the living** always have a recorded cause, and the log says why. Examples: a gate shut with a relative outside, hidden food, a hidden bite discovered, blame for whoever let the dead in, faith against burning the bodies, succession when a lord dies, desertion.
- **Hierarchy.** The king commands the mayors and lords; lords command the villages on their land. Orders can be obeyed or refused, and betrayals, campaigns and rumors follow from it.
- **Ideas.** People with the right attributes may have a clever idea. It can work, fail or cost lives. Nothing is guaranteed.
- **Coups.** Possible, but the same place never has two coups less than 25 days apart.
- **Recolonizing.** When a place is starving or has less than 7 days of food, and there is an abandoned village within 18 km with at most 3 undead, a clever leader (or any leader after 12 days of famine) may send families back to the fields. In a colony, settlers who are not farmers produce at 70% of a peasant.
- **Protagonists.** Five, chosen by rule on day zero. When one dies, the thread passes to someone connected to them.

## The kingdom's temperament

Each run draws offsets to the population's average for all eight attributes (1 point of deviation, capped at 2). With 10,000 people, attributes even out on average and runs used to look alike; the temperament breaks that. A cult becomes much more likely in a devout kingdom, and the scent trick in a resourceful one. `narrativa.temperamento` describes the kingdom in words.

## Time and ending

- **Step:** one hour.
- **Origin:** on day 3, at night, a ship with a bitten crew and corpses in the hold runs aground at a fishing village far from the capital.
- **Horizon:** up to 600 days.
- **Endings:**
  - `derrota` (defeat): nobody is left alive;
  - `vitoria` with `fim_tipo` "luta" (victory by fighting): the living destroyed the last corpse;
  - `vitoria` with `fim_tipo` "tempo" (victory by time): the last corpse rotted away.

## Calibration targets

Measured over many runs, blind, before choosing any particular one:

- the outbreak leaves the origin village in more than 80% of runs;
- at least two places fall in the first week;
- at the peak, 30% to 70% of the population is dead or undead;
- the capital is almost always threatened and falls in about half of the runs;
- endings vary: the living clear the island, a few strongholds remain, or everything falls;
- the undead stay present until near the end, with no long stretch without them.

## Variety

There is no typical ending to aim for: the goal is that runs are truly different from each other. `python sim.py variedade` measures that over many runs:

- how often each milestone happens (a milestone present in almost every run is a cliché, not a twist);
- the distance between story outlines;
- the coarse shapes (ending, losses, citadel, intrigue);
- the pacing, that is, at which phase of the story the major events fall.
