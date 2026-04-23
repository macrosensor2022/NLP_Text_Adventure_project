import spacy
from models import ParsedAction, Intent
from typing import Optional
from inference import rewrite_to_command

nlp = spacy.load("en_core_web_sm")

VERB_TO_ACTION = {
    "go": ("go", Intent.MOVEMENT),
    "walk": ("go", Intent.MOVEMENT),
    "move": ("go", Intent.MOVEMENT),
    "run": ("go", Intent.MOVEMENT),
    "head": ("go", Intent.MOVEMENT),
    "travel": ("go", Intent.MOVEMENT),
    "climb": ("go", Intent.MOVEMENT),
    "enter": ("go", Intent.MOVEMENT),

    "take": ("take", Intent.INVENTORY),
    "pick up": ("take", Intent.INVENTORY),
    "grab": ("take", Intent.INVENTORY),
    "pick": ("take", Intent.INVENTORY),
    "collect": ("take", Intent.INVENTORY),
    "get": ("take", Intent.INVENTORY),
    "snatch": ("take", Intent.INVENTORY),
    "acquire": ("take", Intent.INVENTORY),
    "nab": ("take", Intent.INVENTORY),

    "drop": ("drop", Intent.INVENTORY),
    "throw": ("drop", Intent.INVENTORY),
    "discard": ("drop", Intent.INVENTORY),
    "toss": ("drop", Intent.INVENTORY),
    "leave": ("drop", Intent.INVENTORY),

    "use": ("use", Intent.INVENTORY),
    "equip": ("use", Intent.INVENTORY),

    "attack": ("attack", Intent.COMBAT),
    "hit": ("attack", Intent.COMBAT),
    "strike": ("attack", Intent.COMBAT),
    "fight": ("attack", Intent.COMBAT),
    "slash": ("attack", Intent.COMBAT),
    "stab": ("attack", Intent.COMBAT),
    "kill": ("attack", Intent.COMBAT),
    "punch": ("attack", Intent.COMBAT),
    "kick": ("attack", Intent.COMBAT),

    "talk": ("talk", Intent.DIALOGUE),
    "speak": ("talk", Intent.DIALOGUE),
    "ask": ("talk", Intent.DIALOGUE),
    "say": ("talk", Intent.DIALOGUE),
    "chat": ("talk", Intent.DIALOGUE),
    "persuade": ("talk", Intent.DIALOGUE),
    "tell": ("talk", Intent.DIALOGUE),

    "open": ("open", Intent.INTERACTION),
    "pull": ("pull", Intent.INTERACTION),
    "push": ("push", Intent.INTERACTION),
    "read": ("read", Intent.INTERACTION),
    "examine": ("examine", Intent.INTERACTION),
    "inspect": ("examine", Intent.INTERACTION),
    "look": ("examine", Intent.INTERACTION),
    "unlock": ("unlock", Intent.INTERACTION),
}

DIRECTIONS = {"north", "south", "east", "west", "up", "down"}

SYSTEM_COMMANDS = {"inventory", "inv", "i", "status", "save", "quit", "exit", "help", "look", "context"}
DIALOGUE_CUE_VERBS = {"talk", "speak", "ask", "say", "chat", "persuade", "tell"}


def match_entity(text: str, world_state) -> Optional[str]:
    """Match player words to known entity IDs."""
    world = world_state.world if hasattr(world_state, 'world') else world_state
    text_lower = text.lower()
    for filler in ["the", "a", "an", "that", "this", "my", "some"]:
        text_lower = text_lower.replace(filler + " ", "")
    text_lower = text_lower.strip()

    if not text_lower:
        return None

    for item_id, item in world.items.items():
        if text_lower in item.name.lower() or item.name.lower() in text_lower:
            return item_id

    for npc_id, npc in world.npcs.items():
        if text_lower in npc.name.lower() or npc.name.lower() in text_lower:
            return npc_id
        first_name = npc.name.split(" ")[0].lower()
        if first_name == text_lower:
            return npc_id

    for room_id, room in world.rooms.items():
        if text_lower in room.name.lower() or room.name.lower() in text_lower:
            return room_id

    return None


def parse_input(raw: str, world_state, _allow_rewrite: bool = True) -> ParsedAction:
    """
    Takes raw player text and returns a ParsedAction.

    Examples:
        "go north"                    -> MOVEMENT, go, direction=north
        "grab the rusty key"          -> INVENTORY, take, target=rusty_key
        "attack the rat"              -> COMBAT, attack, target=giant_rat
        "talk to greta"               -> DIALOGUE, talk, target=barkeep
        "I want to pick up the sword" -> INVENTORY, take, target=iron_sword
        "inventory"                   -> SYSTEM, inventory
    """
    raw = raw.strip().lower()
    if not raw:
        return ParsedAction(intent=Intent.SYSTEM, verb="help")

    if raw.split(" ")[0] in SYSTEM_COMMANDS:
        return ParsedAction(intent=Intent.SYSTEM, verb=raw.split(" ")[0])

    parts = raw.split(maxsplit=1)
    first_word = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    if first_word == "go" and rest in DIRECTIONS:
        return ParsedAction(intent=Intent.MOVEMENT, verb="go", direction=rest)

    if first_word in DIRECTIONS and not rest:
        return ParsedAction(intent=Intent.MOVEMENT, verb="go", direction=first_word)

    doc = nlp(raw)
    root_verb = None
    for token in doc:
        if token.dep_ == "ROOT" and token.pos_ == "VERB":
            root_verb = token
            break

    if not root_verb:
        for token in doc:
            if token.pos_ == "VERB":
                root_verb = token
                break

    if not root_verb:
        verb_text = first_word
    else:
        verb_text = root_verb.lemma_

    if verb_text in VERB_TO_ACTION:
        standard_verb, intent = VERB_TO_ACTION[verb_text]
    else:
        standard_verb = verb_text
        intent = Intent.INTERACTION

    if any(token.lemma_ in DIALOGUE_CUE_VERBS for token in doc):
        intent = Intent.DIALOGUE
        standard_verb = "talk"

    target_text = ""
    direction = None

    if root_verb:
        for child in root_verb.children:
            if child.dep_ in ("dobj", "pobj", "attr", "dative", "advcl", "oprd"):
                target_text = " ".join([token.text for token in child.subtree
                                        if token.dep_ != "aux" and token.pos_ != "PART"])
                break

        if not target_text:
            for child in root_verb.children:
                if child.dep_ == "prep":
                    for grandchild in child.children:
                        if grandchild.dep_ == "pobj":
                            target_text = " ".join([token.text for token in grandchild.subtree])
                            break

    if not target_text and rest:
        target_text = rest

    for word in target_text.split():
        if word in DIRECTIONS:
            direction = word
            if intent == Intent.MOVEMENT or verb_text in ("go", "walk", "move", "run", "head", "travel"):
                intent = Intent.MOVEMENT
                return ParsedAction(intent=intent, verb="go", direction=direction)

    target_id = None
    if target_text:
        target_id = match_entity(target_text, world_state)

    requires = []
    if root_verb:
        for child in root_verb.children:
            if child.dep_ == "prep" and child.text in ("with", "using"):
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        instrument_text = " ".join([token.text for token in grandchild.subtree])
                        instrument_id = match_entity(instrument_text, world_state)
                        if instrument_id:
                            requires.append(instrument_id)

    if _allow_rewrite and intent == Intent.INTERACTION and target_id is None:
        rewritten = rewrite_to_command(raw)
        if rewritten and rewritten != raw:
            return parse_input(rewritten, world_state, _allow_rewrite=False)

    return ParsedAction(intent=intent, verb=standard_verb, target=target_id, direction=direction, requires=requires)
