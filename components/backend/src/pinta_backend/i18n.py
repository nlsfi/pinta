# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from __future__ import annotations

import gettext
from contextvars import ContextVar
from pathlib import Path

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "fi"}

LOCALES_DIR = Path(__file__).parent / "locales"
DOMAIN = "messages"

_current_language: ContextVar[str] = ContextVar(
    "current_language",
    default=DEFAULT_LANGUAGE,
)


def set_language(language: str | None) -> None:
    """Set the active language for the current request context."""
    if language is None or language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    _current_language.set(language)


def get_language() -> str:
    """Return the active language for the current request context."""
    return _current_language.get()


def get_translator() -> gettext.NullTranslations:
    """Return a gettext translator for the active language."""
    language = get_language()

    return gettext.translation(
        DOMAIN,
        localedir=LOCALES_DIR,
        languages=[language],
        fallback=True,
    )


def gettext_lazy(message: str) -> str:
    """Translate a message using the active language context."""
    translator = get_translator()
    return translator.gettext(message)


# alias like Django / Flask style
_ = gettext_lazy
