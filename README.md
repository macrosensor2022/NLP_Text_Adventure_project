# NLP Text Adventure Game

A text-based adventure game powered by Natural Language Processing. The game uses a deterministic state engine as the foundation, with an LLM narrator layer planned for future development.

## Project Status

### Layer 1: Deterministic State Engine (Complete)

The core game engine that owns all ground-truth state. The LLM will act as narrator; this layer enforces rules and tracks data.

**Capabilities:**
- Load/save full game state from a single JSON file
- Query rooms, items, NPCs, inventory, and exits
- Deterministic precondition checking — rejects impossible actions before they reach the LLM
- State mutations: move player, take/drop items, use keys, auto-unlock doors
- NPC attitude tracking (-100 to +100)
- Player HP and damage system
- Append-only event log with turn counter and state change records
- Context package builder for LLM prompt injection
- Rollback-safe state resolution for LLM-suggested changes

### Layer 2: NLP Input Parser (Complete)

Natural language understanding layer using spaCy. Players can type free-form English instead of rigid keyword commands.

**Capabilities:**
- spaCy-powered parsing using the `en_core_web_sm` language model
- 40+ verb synonyms mapped to 7 intent categories (MOVEMENT, INVENTORY, COMBAT, DIALOGUE, INTERACTION, SOCIAL_INTERACTION, SYSTEM)
- Dependency tree extraction — finds targets via dobj, pobj, advcl, dative, and prepositional phrase traversal
- Fuzzy entity matching — maps natural words like "rusty key", "greta", "rat" to game entity IDs (`rusty_key`, `barkeep`, `giant_rat`)
- Instrument detection — parses "with"/"using" phrases for item requirements
- Direction extraction from natural sentences (e.g. "walk to the north")
- Integrated into the game loop with precondition checking before action execution

**Example inputs that work:**
| Input | Parsed As |
|-------|-----------|
| `go north` | MOVEMENT, direction=north |
| `walk to the north` | MOVEMENT, direction=north |
| `grab the rusty key` | INVENTORY, take, target=rusty_key |
| `I want to pick up the sword` | INVENTORY, take, target=iron_sword |
| `attack the rat` | COMBAT, attack, target=giant_rat |
| `talk to greta` | DIALOGUE, talk, target=barkeep |
| `examine the shield` | INTERACTION, examine, target=wooden_shield |
| `unlock the door with the key` | INTERACTION, unlock, requires=[rusty_key] |

## Files

| File | Description |
|------|-------------|
| `models.py` | Pydantic data models — `Room`, `Item`, `NPC`, `Player`, `GameWorld`, `Intent`, `ParsedAction`, etc. |
| `world_state.py` | State engine — load/save, queries, precondition checks, mutations, event logging, LLM context builder |
| `input_parser.py` | NLP parser — spaCy-powered natural language understanding, verb mapping, entity matching, dependency extraction |
| `game.py` | Playable terminal prototype with NLP-powered input |
| `game_state.json` | Game world data — 6 rooms, 6 items, 3 NPCs |
| `test_layer1.py` | 37 tests covering all engine functionality |

## Game World

- **6 Rooms:** Tavern, Stone Hallway, Old Armory (locked), Cellar Stairway, Wine Cellar, Castle Courtyard
- **6 Items:** Rusty Key, Wooden Torch, Iron Sword, Wooden Shield, Health Potion, Faded Map
- **3 NPCs:** Greta the Barkeep, Giant Rat, Elric the Merchant

## How to Run

### Prerequisites

```
pip install pydantic spacy
python -m spacy download en_core_web_sm
```

### Run Tests

```
python test_layer1.py
```

Runs 37 tests covering loading, queries, preconditions, inventory, movement, locked doors, NPC attitude, damage, context packages, and persistence.

### Play the Game

```
python game.py
```

**Commands — supports natural language:**

| What you can type | What happens |
|-------------------|--------------|
| `go north` / `walk to the north` / `north` | Move in a direction |
| `grab the rusty key` / `take the key` / `pick up the torch` | Pick up an item |
| `drop the torch` / `toss the key` | Drop an item |
| `use the rusty key` / `equip the sword` | Use an item |
| `attack the rat` / `hit the giant rat` / `fight the rat` | Attack an NPC (placeholder) |
| `talk to greta` / `speak with elric` | Talk to an NPC (placeholder) |
| `examine the shield` / `inspect the map` / `read the map` | Interact with objects (placeholder) |
| `look` | Describe current room |
| `inventory` / `i` | List carried items |
| `status` | Show HP and inventory |
| `context` | Dump full game state JSON |
| `save` | Save game to file |
| `help` | Show example commands |
| `quit` | Exit the game |

## Architecture

```
Player Input
    │
    ▼
┌──────────────┐
│  NLP Parser  │  (Layer 2 — complete)
│  spaCy +     │  input_parser.py
│  Entities    │
└──────┬───────┘
       │ ParsedAction
       ▼
┌──────────────┐
│ Precondition │  Deterministic gate — rejects
│   Checker    │  impossible actions
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  LLM Narrator│  (Layer 3 — planned)
│  + Context   │  Receives context package,
│   Package    │  returns narrative + StateChanges
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   State      │  Applies validated changes
│   Engine     │  with rollback on error
└──────────────┘
```

## Planned Layers

- ~~**Layer 2:** NLP Parser — classify player intent, extract entities from free text~~ **Done**
- **Layer 3:** LLM Integration — narrative generation, dialogue, dynamic storytelling
- **Layer 4:** Advanced mechanics — combat system, skill checks, quest tracking
