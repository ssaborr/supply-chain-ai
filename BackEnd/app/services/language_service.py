from typing import Optional


def normalize_ai_language(language: Optional[str]) -> str:
    code = (language or "en").strip().lower()
    return "French" if code in {"fr", "fr-fr", "french", "francais", "français"} else "English"


def ai_language_instruction(language: Optional[str]) -> str:
    return f" Answer in {normalize_ai_language(language)}."
