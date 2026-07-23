# How to Build AI Chatbots

A hands-on, step-by-step guide to building chatbots in Python — starting from
a simple bot with no AI, then building a real AI chatbot powered by Claude.

## The three steps

| File | What it teaches | Needs an API key? |
| --- | --- | --- |
| `1_rule_based_bot.py` | The basic chat loop: read input → reply → repeat | No |
| `2_ai_chatbot.py` | Sending a message to Claude and getting a smart reply | Yes |
| `3_ai_chatbot_memory.py` | Giving the bot **memory** of the conversation | Yes |

Work through them in order — each one builds on the idea before it.

## How a chatbot works

Every chatbot, simple or advanced, follows the same loop:

1. **Read** what the user typed.
2. **Decide** on a reply.
3. **Print** the reply.
4. **Repeat** until the user quits.

The only thing that changes is *step 2*:
- The **rule-based bot** decides the reply with hand-written `if`/`else` rules.
- The **AI bot** asks Claude (a large language model) to write the reply.

## Setup for the AI bots (steps 2 and 3)

1. Install the library:
   ```
   pip install -r requirements.txt
   ```
2. Get an API key from https://console.anthropic.com
3. Save the key as an environment variable so the code can read it safely
   (never paste your key directly into the code):
   ```
   # Mac / Linux
   export ANTHROPIC_API_KEY="your-key-here"

   # Windows
   setx ANTHROPIC_API_KEY "your-key-here"
   ```

## The one big idea: memory

The Claude API is **stateless** — it does not remember previous messages on
its own. Step 2's bot forgets everything after each reply.

To give a bot memory, *we* keep the conversation in a list and send the whole
list on every request. That's the key lesson in `3_ai_chatbot_memory.py`:

```python
history = []
history.append({"role": "user", "content": message})   # remember what you said
response = client.messages.create(..., messages=history) # send the whole history
history.append({"role": "assistant", "content": reply}) # remember the bot's reply
```

## Where to go next

- Add a **system prompt** to give your bot a personality or a job.
- **Stream** the reply so text appears word-by-word instead of all at once.
- Give the bot **tools** (like a calculator or web search) so it can take
  actions, not just talk.
