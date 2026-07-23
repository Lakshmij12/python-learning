"""
Step 3: An AI chatbot that REMEMBERS the conversation

The bot in step 2 forgot everything after each message. If you said
"My name is Lakshmi" and then asked "What's my name?", it wouldn't know.

Why? The Claude API is "stateless" - it doesn't remember past messages on
its own. To give the bot a memory, WE keep the conversation history in a
list and send the whole list every time. That's the one big idea here.

Setup is the same as step 2 (pip install anthropic + set ANTHROPIC_API_KEY).

Run it with:
    python 3_ai_chatbot_memory.py
"""

import anthropic

client = anthropic.Anthropic()

MODEL = "claude-opus-4-8"


def main():
    print("AI Bot with memory (type 'bye' to quit)")

    # This list is the bot's memory. Each turn we append to it.
    history = []

    while True:
        message = input("You: ")
        if message.lower().strip() in ("bye", "quit", "exit"):
            print("Bot: Goodbye!")
            break

        # 1. Add the user's message to the history.
        history.append({"role": "user", "content": message})

        # 2. Send the ENTIRE history to Claude, not just the latest line.
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system="You are a friendly assistant. Remember details the user shares.",
            messages=history,
        )

        # 3. Pull the text out of the reply.
        reply = ""
        for block in response.content:
            if block.type == "text":
                reply = block.text

        # 4. Add Claude's reply to the history so it's remembered next turn.
        history.append({"role": "assistant", "content": reply})

        print("Bot:", reply)


if __name__ == "__main__":
    main()
