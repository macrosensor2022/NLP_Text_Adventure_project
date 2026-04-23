from llama_cpp import Llama

llm = Llama(model_path="model-Q4_K_M.gguf", n_ctx=2048, n_threads=8, verbose=False)

test_messages = [
    {
        "role": "system",
        "content": (
            "You are a mysterious elven ranger in a text adventure game.\n"
            "Persona: I patrol the ancient forest, protecting it from dark forces. "
            "I speak little but observe much. My bow never misses.\n"
            "Location: Dark Forest Clearing - A small clearing surrounded by towering "
            "ancient oaks. Moonlight filters through the canopy. A stone altar sits "
            "in the center, covered in moss."
        ),
    },
    {
        "role": "user",
        "content": "traveler: Hail, ranger! I am lost and seek passage through this forest. Who are you? What will you do to me?",
    },
]

response = llm.create_chat_completion(
    messages=test_messages, max_tokens=128, temperature=0.9
)


print(test_messages[1]["content"])
print()
print(response["choices"][0]["message"]["content"])
