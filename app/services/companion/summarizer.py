"""Mock conversation memory summarizer (no external LLM)."""

from app.models.llm import ChatMessage


def summarize_turns(messages: list[ChatMessage]) -> str:
    """Concatenate key points from user messages in the given turn batch."""
    user_lines = [
        msg.content.strip()
        for msg in messages
        if msg.role == "user" and msg.content.strip()
    ]
    if not user_lines:
        return ""
    joined = "; ".join(user_lines)
    return f"Key points from earlier conversation: {joined}"