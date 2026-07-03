from pydantic import BaseModel


def format_sse(event: BaseModel) -> str:
    return f"data: {event.model_dump_json()}\n\n"