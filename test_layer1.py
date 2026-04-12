"""
test_layer1.py — Run all state engine tests.
Run:  python test_layer1.py
"""

import os
from models import ParsedAction, Intent
from world_state import WorldState


def test(name, condition):
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}")
    assert condition, f"FAILED: {name}"


def run():
    print("=" * 50)
    print("  LAYER 1 TESTS")
    print("=" * 50)

    # 1. Load
    print("\n1. Loading")
    ws = WorldState.load("game_state.json")
    test("World loads", ws is not None)
    test("6 rooms", len(ws.world.rooms) == 6)
    test("6 items", len(ws.world.items) == 6)
    test("3 NPCs", len(ws.world.npcs) == 3)
    test("Player in tavern", ws.world.player.current_room == "tavern")

    # 2. Queries
    print("\n2. Queries")
    test("Get tavern", ws.get_room("tavern") is not None)
    test("Tavern has 2 exits", len(ws.get_room("tavern").exits) == 2)
    test("Armory locked", ws.get_room("armory").locked)
    test("Key is_key", ws.get_item("rusty_key").is_key)
    test("Sword is_weapon", ws.get_item("iron_sword").is_weapon)
    test("Barkeep in tavern", ws.is_npc_in_room("barkeep", "tavern"))
    test("Find by name", ws.find_item_by_name("rusty") is not None)

    # 3. Preconditions
    print("\n3. Preconditions")
    ok, _ = ws.check_preconditions(ParsedAction(intent=Intent.MOVEMENT, verb="go", direction="north"))
    test("Can go north", ok)
    ok, _ = ws.check_preconditions(ParsedAction(intent=Intent.MOVEMENT, verb="go", direction="west"))
    test("Cannot go west (no exit)", not ok)
    ok, _ = ws.check_preconditions(ParsedAction(intent=Intent.INVENTORY, verb="take", target="rusty_key"))
    test("Can take key (in room)", ok)
    ok, _ = ws.check_preconditions(ParsedAction(intent=Intent.INVENTORY, verb="take", target="iron_sword"))
    test("Cannot take sword (not here)", not ok)
    ok, _ = ws.check_preconditions(ParsedAction(intent=Intent.COMBAT, verb="attack", target="barkeep"))
    test("Can attack barkeep", ok)
    ok, _ = ws.check_preconditions(ParsedAction(intent=Intent.COMBAT, verb="attack", target="giant_rat"))
    test("Cannot attack rat (wrong room)", not ok)
    ok, _ = ws.check_preconditions(ParsedAction(intent=Intent.INTERACTION, verb="pick_lock", requires=["lockpick"]))
    test("Cannot pick lock (no lockpick)", not ok)

    # 4. Take item
    print("\n4. Take item")
    ok, _ = ws.take_item("rusty_key")
    test("Take key succeeds", ok)
    test("Key in inventory", ws.player_has_item("rusty_key"))
    test("Key gone from room", "rusty_key" not in ws.get_current_room().items)

    # 5. Movement + locked door
    print("\n5. Movement + locked door")
    ok, _ = ws.move_player("north")
    test("Move north OK", ok)
    test("In hallway", ws.world.player.current_room == "hallway")
    ok, _ = ws.move_player("east")  # auto-unlocks with key
    test("Enter armory (auto-unlock)", ok)
    test("Armory now unlocked", not ws.get_room("armory").locked)

    # 6. Drop
    print("\n6. Drop item")
    ok, _ = ws.drop_item("rusty_key")
    test("Drop key OK", ok)
    test("Key not in inventory", not ws.player_has_item("rusty_key"))
    test("Key in armory", "rusty_key" in ws.get_room("armory").items)

    # 7. NPC attitude
    print("\n7. NPC attitude")
    ws.move_player("west")
    ws.move_player("south")
    ok, _ = ws.update_npc_attitude("barkeep", -50)
    test("Attitude change OK", ok)
    test("Barkeep at -20", ws.get_npc("barkeep").attitude == -20)

    # 8. Damage
    print("\n8. Player damage")
    ok, _ = ws.damage_player(30)
    test("Damage OK", ok)
    test("HP is 70", ws.world.player.hp == 70)

    # 9. Context package
    print("\n9. Context package")
    ctx = ws.build_context_package()
    test("Has current_room", "current_room" in ctx)
    test("Has player", "player" in ctx)
    test("Has adjacent_rooms", "adjacent_rooms" in ctx)
    test("Has recent_events", "recent_events" in ctx)
    test("Events logged", len(ctx["recent_events"]) > 0)

    # 10. Save/load
    print("\n10. Persistence")
    ws.save("test_save.json")
    ws2 = WorldState.load("test_save.json")
    test("Reload OK", ws2 is not None)
    test("Room preserved", ws2.world.player.current_room == ws.world.player.current_room)
    test("HP preserved", ws2.world.player.hp == 70)
    test("Turn preserved", ws2.world.turn == ws.world.turn)
    test("Events preserved", len(ws2.world.events) == len(ws.world.events))
    os.remove("test_save.json")

    print("\n" + "=" * 50)
    print("  ALL TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    run()