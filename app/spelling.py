"""Words the speech model keeps getting wrong, learned from this person's own fixes.

Every time a subtitle line is changed by hand (capcut_edit.set_line_text), the words that changed are kept in
corrections.json beside ClipKit (this machine only, never synced to the team). New transcripts get them fixed
before anyone sees them. Only whole words are swapped, so "กอ" -> "ก็" never touches "กอง".
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "corrections.json"
MAX_WORDS = 3  # a longer change is a rewrite, not a mishearing


def _words(text: str) -> list[str]:
    from pythainlp.tokenize import word_tokenize
    return word_tokenize(text, keep_whitespace=True)


def load() -> dict[str, dict]:
    """{wrong: {"right": ..., "n": times fixed}}; a broken file raises."""
    if not FILE.is_file():
        return {}
    data = json.loads(FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{FILE} is not a JSON object")
    return data


def learn(old: str, new: str) -> list[tuple[str, str]]:
    """Keep the words changed between a heard line and its fixed version; returns the pairs learned."""
    a, b = _words(old), _words(new)
    pairs = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        wrong, right = "".join(a[i1:i2]).strip(), "".join(b[j1:j2]).strip()
        if op == "replace" and wrong and right and wrong != right and max(i2 - i1, j2 - j1) <= MAX_WORDS:
            pairs.append((wrong, right))
    if pairs:
        data = load()
        for wrong, right in pairs:
            seen = data.get(wrong)
            data[wrong] = {"right": right, "n": seen["n"] + 1 if seen and seen["right"] == right else 1}
        FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return pairs


def fix(text: str, data: dict[str, dict] | None = None) -> str:
    """The line with every learned mishearing swapped, matched on whole words only."""
    data = load() if data is None else data
    if not data:
        return text
    words, out, i = _words(text), [], 0
    longest = max(len(_words(w)) for w in data)
    while i < len(words):
        for n in range(min(longest, len(words) - i), 0, -1):
            hit = data.get("".join(words[i:i + n]).strip())
            if hit and words[i].strip() and words[i + n - 1].strip():
                out.append(hit["right"])
                i += n
                break
        else:
            out.append(words[i])
            i += 1
    return "".join(out)
