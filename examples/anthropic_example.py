"""Run: pip install anthropic llmeter && python examples/anthropic_example.py"""
import anthropic
import llmeter

llmeter.init()

client = anthropic.Anthropic()
resp = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=50,
    messages=[{"role": "user", "content": "Say hi in 3 words."}],
)
print(resp.content[0].text)
print("→ Run `llmeter stats` to see the cost.")
