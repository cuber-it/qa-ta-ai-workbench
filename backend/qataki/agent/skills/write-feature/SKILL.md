---
name: write-feature
when_to_use: Wenn aus einer erkundeten oder beschriebenen Funktion ein Gherkin-.feature-Szenario formuliert werden soll.
---
# Gherkin-Feature schreiben

Ziel: ein werkzeug-unabhaengiges .feature in klarer Gherkin-Form, das ein
fachliches Verhalten beschreibt — nicht die technische Umsetzung.

Schritte:
1. Fachliches Ziel benennen: was soll aus Nutzersicht funktionieren?
2. Feature-Kopf: "Feature:" + ein bis zwei Saetze Kontext.
3. Pro relevantem Fall ein "Scenario:" mit sprechendem Titel.
4. Schritte in Given/When/Then:
   - Given = Ausgangszustand (Vorbedingung),
   - When  = die ausloesende Handlung,
   - Then  = das erwartete, beobachtbare Ergebnis.
5. Konkret, aber implementierungsfrei formulieren: "Wenn der Nutzer sich mit
   gueltigen Daten anmeldet", nicht "Wenn click auf #submit".
6. Auch den wichtigsten Negativfall abdecken (z. B. ungueltige Eingabe).
7. Sprache pro Datei einheitlich halten.

Ergebnis: ein .feature-Block, der ohne Werkzeugwissen lesbar ist und die
Grundlage fuer die spaeteren Step-Definitionen bildet.
