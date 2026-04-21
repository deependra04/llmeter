"""LangChain works without extra wiring — tokenly patches the underlying
OpenAI / Anthropic SDK so anything LangChain drives through them is tracked.

    pip install langchain langchain-openai openai tokenly
    python examples/langchain_example.py
"""
import tokenly
from langchain_openai import ChatOpenAI

tokenly.init(tags={"framework": "langchain"})

llm = ChatOpenAI(model="gpt-4o-mini")
resp = llm.invoke("Say hi in three words.")
print(resp.content)
print("→ Run `tokenly stats --by=tag.framework` to see LangChain usage.")
