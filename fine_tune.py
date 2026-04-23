from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset
import json


model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
    max_seq_length=2048,
    load_in_4bit=True,
    dtype=None,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=13,
)

rows = []
with open("light_1k.json") as f:
    for line in f:
        rows.append(json.loads(line))

dataset = Dataset.from_list(rows)


def format_chat(example):
    text = tokenizer.apply_chat_template(
        example["messages"], toknize=False, add_generation_prompt=False
    )
    return {"text": text}


dataset = dataset.map(format_chat)


trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=2048,
    packing=True,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        num_train_epochs=3,
        learning_rate=2e-4,
        lr_scheduler_type="constant",
        warmup_steps=0.05,
        fp16=True,
        logging_steps=10,
        output_dir="/content/drive/MyDrive/dataNLP/light_qwen_lora",
        save_strategy="epoch",
        seed=13,
        report_to="none",
    ),
)

stats = trainer.train()

model.save_pretrained("model/final")
tokenizer.save_pretrained("model/final")

FastLanguageModel.for_inference(model)

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

inputs = tokenizer.apply_chat_template(
    test_messages,
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt",
).to(model.device)

output = model.generate(
    input_ids=inputs,
    max_new_tokens=128,
    temperature=0.7,
    top_p=0.9,
)

response = tokenizer.decode(output[0][inputs.shape[-1] :], skip_special_tokens=True)
print(f"\n--- Test response ---\n{response}")
