"""Offline mock LLM used by the completed lab."""
import random
import time


RESPONSES = {
    "docker": "Docker packages an application and its dependencies into a portable container.",
    "deploy": "Deployment makes an application available on a server or cloud platform.",
    "default": "The production agent received your question and is working correctly.",
}


def ask(question: str, delay: float = 0.05) -> str:
    time.sleep(delay + random.uniform(0, 0.02))
    lowered = question.lower()
    for keyword, response in RESPONSES.items():
        if keyword != "default" and keyword in lowered:
            return response
    return RESPONSES["default"]
