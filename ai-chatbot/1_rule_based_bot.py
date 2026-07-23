"""
Step 1: A rule-based chatbot (no AI, no internet, no API key needed)

This is the simplest kind of chatbot. It just looks at what the user typed
and replies with a matching answer. Great for understanding the basic
"loop": read input -> decide a reply -> print reply -> repeat.

Run it with:
    python 1_rule_based_bot.py
"""


def get_reply(message):
    """Return a reply based on simple keyword matching."""
    text = message.lower().strip()

    if text in ("hi", "hello", "hey"):
        return "Hello! How can I help you today?"
    elif "your name" in text:
        return "I'm a simple Python chatbot."
    elif "how are you" in text:
        return "I'm just code, but I'm running fine. Thanks for asking!"
    elif "bye" in text:
        return "Goodbye! Have a great day."
    else:
        return "Sorry, I don't understand that yet. Try 'hello' or 'bye'."


def main():
    print("Rule-based Bot (type 'bye' to quit)")
    while True:
        message = input("You: ")
        reply = get_reply(message)
        print("Bot:", reply)
        if "bye" in message.lower():
            break


if __name__ == "__main__":
    main()
