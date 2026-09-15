from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f'{name} must be an integer.') from exc
    if value < 1:
        raise RuntimeError(f'{name} must be greater than zero.')
    return value


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    chat_model: str
    embedding_model: str
    embedding_dimensions: int
    rag_message_threshold: int
    rag_character_threshold: int
    direct_context_messages: int
    rag_recent_messages: int
    rag_top_k: int

    @classmethod
    def load(cls, env_file: Path | None = None) -> 'Settings':
        load_dotenv(env_file or Path(__file__).resolve().parents[1] / '.env')
        key = os.getenv('OPENAI_API_KEY', '').strip() or None
        return cls(
            openai_api_key=key,
            chat_model=os.getenv('OPENAI_CHAT_MODEL', 'gpt-4.1-mini').strip(),
            embedding_model=os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small').strip(),
            embedding_dimensions=_positive_int('OPENAI_EMBEDDING_DIMENSIONS', 512),
            rag_message_threshold=_positive_int('RAG_MESSAGE_THRESHOLD', 80),
            rag_character_threshold=_positive_int('RAG_CHARACTER_THRESHOLD', 24000),
            direct_context_messages=_positive_int('DIRECT_CONTEXT_MESSAGES', 80),
            rag_recent_messages=_positive_int('RAG_RECENT_MESSAGES', 12),
            rag_top_k=_positive_int('RAG_TOP_K', 8),
        )
