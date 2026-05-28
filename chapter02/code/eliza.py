"""
第二章示例代码：ELIZA 聊天机器人
基于规则的早期NLP系统 (1966)
"""

import re
import random

RULES = {
    r'I need (.*)': [
        "Why do you need {0}?",
        "Would it really help you to get {0}?",
        "Are you sure you need {0}?"
    ],
    r'Why don\'t you (.*)\?': [
        "Do you really think I don't {0}?",
        "Perhaps eventually I will {0}.",
        "Do you really want me to {0}?"
    ],
    r'Why can\'t I (.*)\?': [
        "Do you think you should be able to {0}?",
        "If you could {0}, what would you do?",
        "I don't know -- why can't you {0}?"
    ],
    r'I am (.*)': [
        "Did you come to me because you are {0}?",
        "How long have you been {0}?",
        "How do you feel about being {0}?"
    ],
    r'.* mother .*': [
        "Tell me more about your mother.",
        "What was your relationship with your mother like?",
        "How do you feel about your mother?"
    ],
    r'.* father .*': [
        "Tell me more about your father.",
        "How did your father make you feel?",
        "What has your father taught you?"
    ],
    r'.*': [
        "Please tell me more.",
        "Let's change focus a bit... Tell me about your family.",
        "Can you elaborate on that?"
    ]
}

PRONOUN_SWAP = {
    "i": "you", "you": "i", "me": "you", "my": "your",
    "your": "my", "yours": "mine", "mine": "yours",
    "am": "are", "are": "am", "was": "were"
}


def swap_pronouns(phrase):
    words = phrase.lower().split()
    swapped = [PRONOUN_SWAP.get(word, word) for word in words]
    return " ".join(swapped)


def respond(user_input):
    for pattern, responses in RULES.items():
        match = re.search(pattern, user_input, re.IGNORECASE)
        if match:
            captured = match.group(1) if match.groups() else ''
            swapped = swap_pronouns(captured)
            response = random.choice(responses).format(swapped)
            return response
    return random.choice(RULES[r'.*'])


if __name__ == '__main__':
    print("Therapist: Hello! How can I help you today?")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["quit", "exit", "bye"]:
            print("Therapist: Goodbye. It was nice talking to you.")
            break
        print(f"Therapist: {respond(user_input)}")
