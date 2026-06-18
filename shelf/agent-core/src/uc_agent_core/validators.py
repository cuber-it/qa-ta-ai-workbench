"""
Output-Validatoren — optionale Pruefung der finalen Antwort.

Ein Validator ist Callable[[str], str | None]: Rueckgabe None = ok, sonst ein
Fehlertext, der dem LLM einmal zurueckgespielt wird, damit es die Antwort
korrigiert (analog pydantic-ai ModelRetry). Default: keiner -> keine Pruefung.

Reine Stdlib -> mit dem Framework-Kern extrahierbar.
"""
from __future__ import annotations


def gherkin(text: str) -> str | None:
    """Grobe Form-Pruefung fuer ein Gherkin-.feature."""
    t = text or ""
    if "Feature:" not in t:
        return "Die Antwort muss ein 'Feature:' enthalten."
    if "Scenario:" not in t and "Szenario:" not in t:
        return "Mindestens ein 'Scenario:'/'Szenario:' fehlt."
    steps = ("Given", "When", "Then", "And", "Angenommen", "Wenn", "Dann", "Und")
    if not any(k in t for k in steps):
        return "Es fehlen Schritte (Given/When/Then bzw. Angenommen/Wenn/Dann)."
    return None
