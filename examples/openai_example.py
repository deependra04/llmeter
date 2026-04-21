"""Run: pip install openai llmeter && python examples/openai_example.py"""
import llmeter
import openai

llmeter.init()

client = openai.OpenAI()
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hi in 3 words."}],
)
print(resp.choices[0].message.content)
print("→ Run `llmeter stats` to see the cost.")
