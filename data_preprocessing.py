import pickle
import json
import random


def build_system_prompt(episode, char_idx):
    agent = episode["agents"][char_idx]
    setting = episode["setting"]

    prompt = (
        f"You are {agent['name']} in a text adventure game.\n"
        f"Persona: {agent['persona']}\n"
        f"Location: {setting['name']} - {setting['description']}"
    )

    if episode.get("all_descriptions"):
        desc = [f"{k}: {v}" for k, v in episode["all_descriptions"].items()]
        if desc:
            prompt += f"\nNearby items: {'; '.join(desc)}"

    return prompt


def format_turn(speech, emote, action):
    parts = []
    if emote:
        parts.append(f"*{emote}*")
    if action:
        parts.append(f"[{action}]")
    if speech:
        parts.append(speech)
    return " ".join(parts) if parts else None


def episode_to_conversation(episode):
    speech = episode["speech"]
    emote = episode["emote"]
    action = episode["action"]
    character = episode["character"]
    agent = episode["agents"]

    num_turns = len(speech)

    if num_turns < 4:
        return

    conversation = []

    for perspect in [0, 1]:
        system = build_system_prompt(episode, perspect)
        name = agent[perspect]["name"]
        other_name = agent[1 - perspect]["name"]
        messages = [{"role": "system", "content": system}]

        for i in range(num_turns):
            turn = format_turn(speech[i], emote[i], action[i])

            if not turn:
                continue

            speaker = character[i]
            if speaker == name:
                messages.append({"role": "assistant", "content": turn})
            else:
                messages.append({"role": "user", "content": f"{other_name}: {turn}"})
        cleaned = [messages[0]]
        for message in messages[1:]:
            if cleaned[-1]["role"] == message["role"] and message["role"] != "system":
                cleaned[-1]["content"] += "\n" + message["content"]
            else:
                cleaned.append(message)

        non_system = [clean for clean in cleaned if clean["role"] != "system"]
        has_user = any(ns["role"] == "user" for ns in non_system)
        has_assistant = any(ns["role"] == "assistant" for ns in non_system)

        if has_user and has_assistant:
            conversation.append({"messages": cleaned})

    return conversation


def main():
    with open("light-dialog-processed-small7.pkl", "rb") as f:
        data = pickle.load(f)

    all_conversations = []

    for episode in data:
        convo = episode_to_conversation(episode)
        if convo:
            all_conversations.extend(convo)

    random.seed(13)
    random.shuffle(all_conversations)

    all_conversations = all_conversations[:5000]

    with open("light_1k.json", "w") as f:
        for convo in all_conversations:
            f.write(json.dumps(convo) + "\n")


if __name__ == "__main__":
    main()
