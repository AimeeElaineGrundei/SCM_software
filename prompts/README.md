# KI-Nutzungsnachweis (Aufgabenstellung 9.3)

Je Person eine Datei `<name>_NN_thema.md`. Pflichtangaben:

- System und Version
- Datum
- Zweck
- betroffene Dateien oder Funktionen
- Prompt wörtlich oder sinngemäß
- was übernommen bzw. geändert wurde
- wie geprüft wurde

## gruppe_01 – KI-Referenzentwurf

- **System:** Claude Opus 5.5 über claude.ai
- **Datum:** 05.–06.11.2026
- **Zweck:**
  - Konzept und Aufteilung aus Aufgabenstellung, Postern und Simulationskonzepten
  - Lieferanten- und Lieferwegdaten aus allen Postern zusammengeführt, fehlende Werte als Annahme
  - Referenzprogramm; danach vereinfacht (Tagesschleife statt SimPy) und auf die Mindestanforderungen reduziert
  - Dokumentation (README, ARCHITEKTUR, HERKUNFT, AUFTEILUNG)
- **Betroffen:** alle Dateien in `scm_lite/`, `app.py`, `tests/`, `data/`, `config/`, `docs/`
- **Prüfung:** automatische Tests (`python -m pytest`, 7 Tests). Die fachliche Prüfung der Daten und Annahmen durch die Gruppe steht noch aus.
