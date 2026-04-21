"""Tag each call with user/feature metadata so `llmeter stats --by=tag.user` works."""
import llmeter
import openai

llmeter.init(tags={"app": "my-saas"})

client = openai.OpenAI()

for user_id in ["alice", "bob", "carol"]:
    llmeter.configure(tags={"app": "my-saas", "user": user_id})
    client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Greet {user_id}"}],
    )

print("→ llmeter stats --by=tag.user")
