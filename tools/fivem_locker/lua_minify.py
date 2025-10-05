import re

_COMMENT = re.compile(r"--\[(=*)\[[\s\S]*?\]\1\]|--.*?$", re.M)
_WS = re.compile(r"\s+")

# Basic safe minifier: strips comments and excessive whitespace without altering strings

def minify_lua(source: str) -> str:
    # Protect strings
    placeholders: list[str] = []

    def _protect(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"__STR{len(placeholders)-1}__"

    source = re.sub(r"(?s)\[(=*)\[[\s\S]*?\]\1\]", _protect, source)  # long strings
    source = re.sub(r"(?s)\"(?:\\.|[^\\\n\"])*\"|\'(?:\\.|[^\\\n\'])*\'", _protect, source)

    # Remove comments
    source = _COMMENT.sub("", source)

    # Collapse whitespace around tokens conservatively
    # Keep newlines around end/then/else/function/local/return for safety
    tokens_keep_nl = r"\b(end|then|else|elseif|function|local|return|do|repeat|until)\b"
    source = re.sub(tokens_keep_nl, r"\n\1\n", source)
    source = _WS.sub(" ", source)
    source = re.sub(r"\s*([=+\-*/%#<>~:,;(){}\[\]])\s*", r"\1", source)

    # Restore strings
    for i, s in enumerate(placeholders):
        source = source.replace(f"__STR{i}__", s)

    # Final tidy
    source = re.sub(r"\n+", "\n", source).strip()
    return source
