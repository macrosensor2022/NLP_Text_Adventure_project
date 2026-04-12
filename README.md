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

## Files

| File | Description |
|------|-------------|
| `models.py` | Pydantic data models — `Room`, `Item`, `NPC`, `Player`, `GameWorld`, `Intent`, `ParsedAction`, etc. |
| `world_state.py` | State engine — load/save, queries, precondition checks, mutations, event logging, LLM context builder |
| `game.py` | Playable terminal prototype with text commands |
| `game_state.json` | Game world data — 6 rooms, 6 items, 3 NPCs |
| `test_layer1.py` | 37 tests covering all engine functionality |

## Game World

- **6 Rooms:** Tavern, Stone Hallway, Old Armory (locked), Cellar Stairway, Wine Cellar, Castle Courtyard
- **6 Items:** Rusty Key, Wooden Torch, Iron Sword, Wooden Shield, Health Potion, Faded Map
- **3 NPCs:** Greta the Barkeep, Giant Rat, Elric the Merchant

## How to Run

### Prerequisites

```
pip install pydantic
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

**Commands:**

| Command | Action |
|---------|--------|
| `go <direction>` | Move (north, south, east, west, up, down) |
| `take <item>` | Pick up an item |
| `drop <item>` | Drop an item |
| `use <item>` | Use an item (e.g. unlock a door) |
| `look` | Describe current room |
| `inventory` | List carried items |
| `status` | Show HP and inventory |
| `context` | Dump full game state JSON |
| `save` | Save game to file |
| `quit` | Exit the game |

## Architecture

```
Player Input
    │
    ▼
┌──────────────┐
│  NLP Parser  │  (Layer 2 — planned)
│  Intent +    │
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

- **Layer 2:** NLP Parser — classify player intent, extract entities from free text
- **Layer 3:** LLM Integration — narrative generation, dialogue, dynamic storytelling
- **Layer 4:** Advanced mechanics — combat system, skill checks, quest tracking
