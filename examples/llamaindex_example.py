"""LlamaIndex works without extra wiring — tokenly patches the underlying
OpenAI SDK so anything LlamaIndex drives through it is tracked.

    pip install llama-index-llms-openai openai tokenly
    python examples/llamaindex_example.py
"""
import tokenly
from llama_index.llms.openai import OpenAI

tokenly.init(tags={"framework": "llamaindex"})

llm = OpenAI(model="gpt-4o-mini")
resp = llm.complete("Say hi in three words.")
print(resp.text)
print("→ Run `tokenly stats --by=tag.framework` to see LlamaIndex usage.")
