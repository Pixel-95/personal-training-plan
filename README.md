# Personal Training Plan

Dieses Repository verwaltet profilabhängige Triathlon-Daten, synchronisiert Intervals.icu-Daten, wertet FIT-Dateien aus und rendert Wochenpläne als HTML und PDF.

## Voraussetzungen

- Python 3.11 oder neuer
- Git
- Google Chrome, Chromium oder Microsoft Edge für den PDF-Export
- Ein Intervals.icu-API-Key für Synchronisationen

Unter macOS können Git und Python beispielsweise über die Xcode Command Line Tools und Homebrew installiert werden. Codex kann die Repository-Skripte ausführen, ersetzt aber keine fehlende lokale Python- oder Git-Installation.

## Einrichtung

```powershell
git clone <REPOSITORY_URL>
cd personal-training-plan
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Unter macOS oder Linux wird die virtuelle Umgebung mit `source .venv/bin/activate` aktiviert und `.env.example` mit `cp .env.example .env` kopiert.

In `.env` müssen anschließend genau diese Werte gepflegt werden:

```text
TRAINING_PROFILE=PROFILE_DIRECTORY_NAME
intervals_icu_api_key=YOUR_INTERVALS_ICU_API_KEY
intervals_icu_athlete_id=YOUR_INTERVALS_ICU_ATHLETE_ID
```

`TRAINING_PROFILE` entspricht exakt dem Verzeichnisnamen unter `profiles/`. Skripte und LLM-Regeln leiten das aktive Profil ausschließlich daraus ab.

Ein lokaler Checkout hat immer genau ein aktives Profil. Prozesse mit unterschiedlichen `TRAINING_PROFILE`-Werten dürfen nicht parallel im selben Checkout laufen, weil `trainingplan.html` eine gemeinsame lokale Profilweiterleitung verwendet.

## Wichtige Befehle

```powershell
# Repository und aktives Profil prüfen
python scripts/validate_repo.py

# Vor der ersten Trainingsplanung Demo-Platzhalter ausschließen
python scripts/validate_repo.py --planning-ready

# Regressionstests ausführen
python -m unittest discover -s tests -v

# Daten vor einer neuen Trainingsplanung synchronisieren
python scripts/pre_plan_sync.py --days 30 --newest YYYY-MM-DD

# Einen Plan des aktiven Profils rendern
python scripts/render_plan.py --plan YYYY-Www.json --newest YYYY-MM-DD --pdf
```

Der Renderer akzeptiert nur Pläne innerhalb von `profiles/<TRAINING_PROFILE>/plans/`. Dadurch können Plan und Health-Daten verschiedener Profile nicht versehentlich vermischt werden.

Ein vorbereitetes Demo-Profil besteht die normale Strukturprüfung, aber nicht `--planning-ready`. Codex muss die gemeldeten Platzhalter vor der ersten Planung beim Nutzer abfragen und durch bestätigte Werte ersetzen.

## Repository-Struktur

- `profiles/<Name>/data/`: profilspezifische Stammdaten, Health-Historien und Aktivitäten
- `profiles/<Name>/plans/`: profilspezifische JSON-, HTML-, PDF- und SVG-Artefakte
- `plan-format/`: gemeinsames JSON-Schema und CSS
- `scripts/`: Synchronisation, Analyse, Plot- und Renderinglogik
- `tests/`: Regressionstests ohne externe Testbibliothek
- `AGENTS.md`: verbindliche fachliche Regeln für Codex und andere LLM-Agenten

`.env`, API-Schlüssel, technische Intervals.icu-Caches und temporäre PDF-Dateien werden nicht versioniert. Profildaten werden in diesem privaten Repository bewusst versioniert.
