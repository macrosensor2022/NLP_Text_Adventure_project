"""
game.py - playable terminal prototype
"""

from world_state import WorldState

def main():
    ws = WorldState.load("game_state.json")
    print("="*50)
    print("  TEXT ADVENTURE — Engine Prototype")
    print("  Commands: go, take, drop, use, look,")
    print("  inventory, status, context, save, quit")
    print("="*50)
    print()
    print(ws.look())
    print()

    while True:
        raw = input("> ").strip().lower()
        if not raw:
            continue
        parts = raw.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "go":
            if not arg:
                print("Go Where?")
            else:
                success, msg = ws.move_player(arg)
                print(msg)
                if success:
                    print()
                    print(ws.look())
        elif cmd == "take":
            if not arg:
                print("Take What?")
            else:
                item = ws.find_item_by_name(arg)
                if item and ws.is_item_in_room(item.id, ws.get_current_room().id):
                    _, msg = ws.take_item(item.id)
                    print(msg)
                else:
                    print("You don't see that here.")
        
        elif cmd == "drop":
            if not arg:
                print("Drop What?")
            else:
                item = ws.find_item_by_name(arg)
                if item and ws.player_has_item(item.id):
                    _, msg = ws.drop_item(item.id)
                    print(msg)
                else:
                    print("You don't have that item.")
        
        elif cmd == "use":
            if not arg:
                print("Use What?")
            else:
                item = ws.find_item_by_name(arg)
                if item and ws.player_has_item(item.id):
                    _, msg = ws.use_item(item.id)
                    print(msg)
                else:
                    print("You don't have that item.")
        elif cmd == "look":
            print(ws.look())
        
        elif cmd in ("inventory", "inv", "i"):
            items = ws.get_player_inventory()
            if items:
                print("You are carrying:")
                for item in items:
                    print(f" - {item.name}:{item.description}")
            else:
                print("You are carrying nothing.")
        
        elif cmd == "status":
            print(ws.get_status())
        
        elif cmd == "context":
            import json
            print(json.dumps(ws.world.model_dump(), indent=2))
        
        elif cmd == "save":
            ws.save("game_state.json")
        
        elif cmd in ("quit","exit","q"):
            print("Farewell, adventurer!")
            break

        elif cmd == "help":
            print("go <dir> | take <item> | drop <item> | use <item>")
            print("look | inventory | status | context | save | quit")
        
        else:
            print(f"Unknown command: {cmd} Type help")

        print()

if __name__ == "__main__":
    main()