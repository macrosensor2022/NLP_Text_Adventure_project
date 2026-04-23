"""
game.py - playable terminal prototype
"""

from world_state import WorldState
from input_parser import parse_input
from models import Intent


def main():
    ws = WorldState.load("game_state.json")
    print("=" * 50)
    print("  TEXT ADVENTURE — Engine Prototype")
    print("  Commands: go, take, drop, use, look,")
    print("  inventory, status, context, save, quit")
    print("=" * 50)
    print()
    print(ws.look())
    print()

    while True:
        raw = input("> ").strip().lower()
        if not raw:
            continue

        action = parse_input(raw, ws)
        if action.intent == Intent.SYSTEM:
            if action.verb == "look":
                print(ws.look())
            elif action.verb in ("inventory", "inv", "i"):
                items = ws.get_player_inventory()
                if items:
                    print("You are carrying:")
                    for item in items:
                        print(f" - {item.name}:{item.description}")
                else:
                    print("You are carrying nothing.")
            elif action.verb == "status":
                print(ws.get_status())
            elif action.verb == "context":
                import json

                print(json.dumps(ws.world.model_dump(), indent=2))
            elif action.verb == "save":
                ws.save("game_state.json")
            elif action.verb in ("quit", "exit", "q"):
                print("Farewell, adventurer!")
                break
            elif action.verb == "help":
                print("Try natural language ! Examples:")
                print("  'go north' or 'walk to the north'")
                print("  'grab the rusty key' or 'pick up the torch'")
                print("  'attack the rat' or 'hit the giant rat'")
                print("  'talk to greta'")
                print("  look | inventory | status | context | save | quit")
            else:
                print(f"Unknown command. Type 'help'.")
        else:
            ok, msg = ws.check_preconditions(action)
            if not ok:
                print(msg)
            else:
                if action.intent == Intent.MOVEMENT:
                    success, msg = ws.move_player(action.direction)
                    print(msg)
                    if success:
                        print()
                        print(ws.look())
                elif action.intent == Intent.INVENTORY:
                    if action.verb == "take":
                        _, msg = ws.take_item(action.target)
                        print(msg)
                    elif action.verb == "drop":
                        _, msg = ws.drop_item(action.target)
                        print(msg)
                    elif action.verb in ("use", "equip"):
                        _, msg = ws.use_item(action.target)
                        print(msg)
                elif action.intent == Intent.COMBAT:
                    print(
                        f"You attack the {action.target}! (combat system coming soon)"
                    )
                elif action.intent == Intent.DIALOGUE:
                    print(
                        f"You talk to the {action.target}! (dialogue system coming soon)"
                    )
                elif action.intent == Intent.INTERACTION:
                    print(f"You try to {action.verb}. (interaction system coming soon)")
        print()


if __name__ == "__main__":
    main()

