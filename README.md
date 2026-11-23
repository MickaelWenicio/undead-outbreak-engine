# Undead Outbreak Engine

A simulation engine that unleashes the undead on a medieval kingdom of about 10,000 people and follows, hour by hour, what happens to each of them until the story ends.

There is no script and no hand-placed event. The outbreak always starts the same way: a ship with a bitten crew runs aground at a fishing village. From then on, everything comes from the rules and from the people's own decisions. Each seed produces a different island: in some the living clear the kingdom, in others a single stronghold holds out, in others everything falls.

> The code, comments and command output are in Brazilian Portuguese.

## What the engine simulates

**The undead**
- A bitten person turns within 2 to 24 hours. Anyone who dies with their body intact rises within 10 to 60 minutes.
- They only stop when the head is destroyed or the body is torn apart or burned. They feel no pain, never retreat and never tire.
- They chase whoever they see or smell, wander slowly when there is no prey, and stand still in the cold.
- They learn over time: they surround houses, pile up to climb walls, set ambushes on the roads and force gates together.
- They expire: the body rots and falls for good after about 200 to 295 days, more slowly in winter and later when they feed.

**The kingdom**
- A walled capital with districts and a citadel, towns, a port, villages, castles, a monastery and a mine.
- The social classes of the era: king and court, nobles, knights, soldiers, clergy, merchants, craftsmen, peasants, fishermen and others.
- A simple economy: every trade produces, prices rise with scarcity, wood becomes barricades and the blacksmith makes spears and armor. There are granaries, a harvest every September, famine and food expeditions.

**The people**
- Each person has attributes (faith, temper, cunning, courage, loyalty, ambition, cruelty and mercy) and decides by them and by what they know.
- At first nobody knows that a bite turns you, that the dead rise, or that only the head stops them. People learn by seeing it or from the news brought by those who flee.
- Leaders decide about gates, refugees, the bitten, bodies, barricades, flight, evacuation and calls for help.
- Every fight among the living has a recorded cause: a gate shut with a relative outside, hidden food, a hidden bite discovered, the succession of a lord who died. Coups, cults, betrayals and new colonies can also happen.
- Each island draws a temperament (a devout kingdom, a resourceful one, a cruel one), so the stories don't look alike.
- Five protagonists are chosen by rule on day zero and followed to the end. When one dies, the story passes to someone connected to them.

**The ending**
- **Victory by fighting:** the living destroy the last of the undead.
- **Victory by time:** the last of the undead rots away.
- **Defeat:** no one is left alive.
- The maximum horizon is 600 days.

The full rules are in [`docs/RULES.md`](docs/RULES.md). Every parameter lives in `config.py`.

## How to use

**Requirements:** Python 3.12 (the version the engine was tested with) and numpy.

```bash
git clone https://github.com/MickaelWenicio/undead-outbreak-engine.git
cd undead-outbreak-engine
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

On Windows, set `PYTHONUTF8=1` (or run `python -X utf8 sim.py ...`) so the Portuguese output prints correctly.

**Create a kingdom and run the story:**

```bash
python sim.py init --seed 7       # creates the kingdom with seed 7 (writes state.json)
python sim.py run --dias 600      # runs until day 600, or until the story ends
python sim.py summary             # places, protagonists and latest events
```

The same seed always produces the same kingdom and the same story.

**Read what happened:**

```bash
python sim.py log --de 1 --ate 30          # the log from day 1 to day 30
python sim.py log --tipos golpe,traicao    # only some event types (coup, betrayal)
python sim.py person 1234                  # one person's sheet and story
python sim.py citaveis --n 15              # who, besides the protagonists, changed the story
python sim.py export historia.json         # exports the full state and log
```

**Run many islands at once** (to study the engine's behavior or look for an interesting story):

```bash
python sim.py ensemble --n 100 --dias 180    # statistics over 100 islands
python sim.py variedade --n 100              # how much the stories differ from each other
python buscar.py 50 busca.json               # runs 50 seeds to the end and summarizes each
```

## Files

| File | What it does |
|---|---|
| `sim.py` | The command line. |
| `motor.py` | The engine: the world, the one-hour step, the undead, the fights and the decisions. |
| `mundo.py` | Kingdom generation: places, roads, families, trades, equipment, leaders and protagonists. |
| `hierarquia.py` | Who commands whom, orders, betrayals, campaigns, walls and rumors. |
| `ideias.py` | The clever ideas of the living, which can work, fail or cost lives. |
| `narrativa.py` | Reading the log: the kingdom's temperament and who deserves to be named. |
| `config.py` | Every parameter. |
| `enredo.py` | Runs one island and prints a summary of its story. |
| `checar_ilha.py` | Scans an island's log for known defects. |
| `buscar.py`, `calibrar.py` | Run many islands, to search for stories or test parameter combinations. |
| `docs/RULES.md` | The simulation rules in detail. |
