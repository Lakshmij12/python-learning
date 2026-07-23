"""
Step 2: A real AI chatbot using Claude

The rule-based bot could only answer things we wrote by hand. A real AI
chatbot sends the user's message to a large language model (Claude) and
gets back a smart, natural reply.

Setup (one time):
    1. pip install anthropic
    2. Get an API key from https://console.anthropic.com
    3. Set it as an environment variable so the code can read it:
         Mac/Linux:  export ANTHROPIC_API_KEY="your-key-here"
         Windows:    setx ANTHROPIC_API_KEY "your-key-here"

Run it with:
    python 2_ai_chatbot.py
"""

import anthropic

# The client automatically reads your key from the ANTHROPIC_API_KEY
# environment variable. Never paste your key directly into code.
client = anthropic.Anthropic()

MODEL = "claude-opus-4-8"


def ask_claude(message):
    """Send one message to Claude and return the text reply."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system="You are a friendly, concise assistant helping someone learn Python.",
        messages=[
            {"role": "user", "content": message},
        ],
    )
    # The reply is a list of "content blocks"; we want the text ones.
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def main():
    print("AI Bot powered by Claude (type 'bye' to quit)")
    while True:
        message = input("You: ")
        if message.lower().strip() in ("bye", "quit", "exit"):
            print("Bot: Goodbye!")
            break
        reply = ask_claude(message)
        print("Bot:", reply)


if __name__ == "__main__":
    main()
