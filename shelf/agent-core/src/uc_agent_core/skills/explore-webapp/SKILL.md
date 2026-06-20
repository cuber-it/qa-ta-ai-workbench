---
name: explore-webapp
when_to_use: Wenn eine unbekannte Weboberflaeche zuerst systematisch erkundet werden soll, bevor Tests geschrieben werden.
---
# Weboberflaeche erkunden

Ziel: ein belastbares Bild der Seite gewinnen (Struktur, Bedienelemente,
Navigationswege), das spaeter als Grundlage fuer Tests dient.

Schritte:
1. Mit pw__open die Start-URL oeffnen.
2. pw__title und pw__url pruefen — bist du, wo du sein willst?
3. pw__content holen und den sichtbaren Inhalt grob einordnen
   (Ueberschriften, Hauptbereiche, Formulare).
4. Interaktive Elemente erfassen: pw__find_role fuer button, link, textbox,
   checkbox; pw__links fuer die Navigation.
5. Auffaellige Eingabefelder und Aktionen notieren (Label, Rolle, Zweck).
6. Noch nichts veraendern oder absenden — in dieser Phase nur beobachten.

Wenn von mehreren Seiten ein Screenshot gebraucht wird: pro Seite genau einen
pw__shot(filename, url)-Aufruf mit url — der navigiert und knipst zusammen.
Niemals erst alle Seiten durchnavigieren und danach knipsen (dann zeigt jeder
Screenshot nur die zuletzt geoeffnete Seite).

Ergebnis: eine knappe Bestandsaufnahme — welche Elemente gibt es, welche
Aktionen sind moeglich, welche Pfade fuehren wohin.
