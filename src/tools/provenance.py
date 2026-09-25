"""Provenance check: did this argument come from the USER, or did the LLM make it up?

Found in the eval (case 29, routing): the code required a non-empty justification, and the LLM wrote
"No justification was provided for the access." — non-empty, so it passed. Validating the FORM is easy;
validating the ORIGIN needs a source of truth the LLM can't touch: the raw user messages, kept by the CODE.

The idea in one line: the justification is what's LEFT after removing the request itself (the words of the
other arguments, e.g. the resource, and request verbs like "I need"). Then:
- nothing left            → it only restates the request ("I need access to SAP") → refused;
- what's left isn't mostly the user's words → the LLM wrote it → refused.

Limits (measured in the eval): fuzzy on purpose, because the LLM rephrases ("lançar" → "lançamento") — so a
threshold that can fail both ways. And provenance is not MEANING: the user's own words used out of context
(the reason for a password reset attached to an SAP request) pass. Judging meaning is for an LLM judge
(module 6) or the manager who approves (decision D2).
"""

import re
import unicodedata

MIN_OVERLAP = 0.5  # fraction of the leftover words that must appear in the user's messages

# Grammar words: carry no meaning, never count as evidence.
_FILLER = {
    "para", "pra", "com", "que", "por", "uma", "dos", "das", "nos", "nas", "meu", "minha", "seu", "sua",
    "the", "and", "for", "with", "that", "this", "from", "your",
}
# Request words: they say "I want something", not WHY. Part of the request, not of the reason.
_REQUEST_WORDS = {
    "preciso", "precisa", "quero", "solicito", "solicita", "solicitou", "pedido", "acesso", "acessar",
    "need", "needs", "want", "request", "requested", "access",
}


def content_words(text: str) -> set[str]:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()  # "lançar" → "lancar"
    return {w for w in re.findall(r"[a-z0-9]+", text) if len(w) > 2 and w not in _FILLER}


def _in_user_words(word: str, user_words: set[str]) -> bool:
    # Same word, or same 5-letter stem ("lancamento" ~ "lancar"); short words must match exactly.
    return word in user_words or (len(word) >= 5 and any(len(u) >= 5 and u[:5] == word[:5] for u in user_words))


def check(arg: str, value: str, user_texts: list[str], request_text: str = "") -> str | None:
    """None if `value` passes; otherwise the error message for the LLM (it should ask the user)."""
    problem = _problem(value, user_texts, request_text)
    if problem is None:
        return None
    return f"'{arg}' must be the user's own reason, but {problem}. Ask the user for it — don't write it yourself."


def _problem(value: str, user_texts: list[str], request_text: str) -> str | None:
    if not value.strip():
        return "it is empty"
    leftover = content_words(value) - content_words(request_text) - _REQUEST_WORDS
    if not leftover:
        return "it only restates the request, it doesn't say WHY"
    user_words = set().union(*(content_words(t) for t in user_texts))
    found = sum(1 for w in leftover if _in_user_words(w, user_words))
    if found / len(leftover) < MIN_OVERLAP:
        return "it wasn't found in the user's messages"
    return None
