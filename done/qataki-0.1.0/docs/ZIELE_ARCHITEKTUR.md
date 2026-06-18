# QATAKI Workbench – Ziele und Architektur

## Kurzbeschreibung

QATAKI ist eine lokale, erweiterbare Workbench für AI-assisted QA, Testautomatisierung und System Exploration.

QATAKI kombiniert:

- LLM-gestützte Analyse
- Playwright-basierte Web-Exploration
- OpenAPI-/REST-Analyse
- kontrollierte Testfallgenerierung
- Gherkin-Export
- reproduzierbare Run-Historie
- Kosten- und Sicherheitsleitplanken
- spätere Erweiterbarkeit über MCP und Adapter

QATAKI ist nicht als vollständig autonomer Testagent gedacht, sondern als Assistenzsystem für erfahrene QA Engineers.

---

## Leitidee

Nicht:

> AI replaces testers.

Sondern:

> AI supports structured QA thinking, system exploration and test automation.

QATAKI soll sichtbar machen:

- QA-Kompetenz
- Testdesign-Kompetenz
- Testautomatisierung
- KI-Integration
- Architekturverständnis
- kontrollierte Tool-Orchestrierung

---

## Zielgruppe

Primär:

- QA Engineers
- Test Automation Engineers
- technische Testmanager
- Entwickler mit QA-Fokus
- AI-assisted Engineering Teams

Sekundär:

- Consultants
- technische Trainer
- Teams, die KI sinnvoll in QA-Prozesse integrieren wollen

---

## V0.1-Ziele

Die erste Version soll lokal laufen und zeigen:

1. Projekt anlegen
2. Ziel-URL analysieren
3. DOM / Accessibility / Screenshot erfassen
4. LLM-gestützte UI-/Systemanalyse durchführen
5. Testideen ableiten
6. Gherkin-Szenarien erzeugen
7. Playwright-Testskizzen generieren
8. Run-Historie speichern
9. Kostenlimits beachten
10. Markdown-Report exportieren

---

## Nicht-Ziele V0.1

Explizit nicht Bestandteil der ersten Version:

- SaaS
- Multiuser
- Rollen-/Rechtemodell
- Kubernetes
- Native GUI Automation
- vollständige Vision-Automation
- vollständige autonome Testausführung
- Plugin Marketplace
- kommerzielles Lizenzmodell

---

## Architektur

```text
Frontend
  ↓
FastAPI Backend
  ↓
Run Orchestrator
  ├─ LLM Client
  ├─ Playwright Adapter
  ├─ OpenAPI Adapter
  ├─ Memory Store
  ├─ Artifact Store
  ├─ Cost Guard
  └─ Report Generator
