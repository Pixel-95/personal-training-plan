# AGENTS.md

Dieses Repo ist der zentrale Trainingskontext für meine Triathlonplanung.

Aktives Profil:
- Vor jeder profilbezogenen Arbeit `.env` lesen und den Wert von `TRAINING_PROFILE` exakt und ohne eigene Interpretation übernehmen.
- `<TRAINING_PROFILE>` in allen profilbezogenen Pfaden durch genau diesen Wert ersetzen. Profilnamen nicht aus vorhandenen Ordnern ableiten oder in profilbezogener Logik hart codieren. Ausnahme: `trainingplan.html` ist ein bewusst fester Root-Einstieg auf Marios aktuellen Wochenplan.
- Wenn `TRAINING_PROFILE` fehlt, leer ist oder der zugehörige Ordner unter `profiles/` nicht existiert, die profilbezogene Arbeit mit einer klaren Fehlermeldung abbrechen.
- Vor der ersten Trainingsplanung für ein Profil `python scripts/validate_repo.py --planning-ready` ausführen. Bei Platzhaltern wie `DEMO`, `1900-01-01` oder `-1` keinen Plan erzeugen, sondern die fehlenden persönlichen Angaben beim Nutzer abfragen und ausschließlich mit bestätigten Werten ersetzen.
- Leere skriptgenerierte Historien sind kein Setup-Fehler. Manuell gepflegte Stammdaten, Ziele, Verfügbarkeit und geplante Rennen müssen jedoch vor der ersten Planung echte Werte enthalten.

Profilübergreifende Änderungen:
- Änderungen unter `scripts/`, `plan-format/`, `AGENTS.md` und `trainingplan.html` sind gemeinsame Regeln oder Implementierungen und dürfen nicht profilspezifisch dupliziert werden.
- Nach einer gemeinsamen Änderung alle vorhandenen Verzeichnisse direkt unter `profiles/` dynamisch ermitteln und jedes Profil strukturell validieren. Profilnamen dabei nicht hart codieren.
- Wenn eine gemeinsame Änderung Rendering, Plots oder Darstellung betrifft, alle davon betroffenen vorhandenen Plan-JSONs profilweise neu rendern. Profile ohne Plan-JSON benötigen keine künstlichen Planartefakte.
- Änderungen unter `profiles/<TRAINING_PROFILE>/data/` oder `profiles/<TRAINING_PROFILE>/plans/` gelten dagegen nur für das aktive Profil, sofern der Nutzer nicht ausdrücklich eine profilübergreifende Datenänderung verlangt.

Vor jeder Trainingsplanung oder Trainingsbewertung zuerst:
- profiles/<TRAINING_PROFILE>/data/current-state.md
- profiles/<TRAINING_PROFILE>/data/athlete-profile.md
- profiles/<TRAINING_PROFILE>/data/goals.md
- profiles/<TRAINING_PROFILE>/data/races.md
- profiles/<TRAINING_PROFILE>/data/availability.md
- profiles/<TRAINING_PROFILE>/data/thresholds/thresholds_bike.md
- profiles/<TRAINING_PROFILE>/data/thresholds/thresholds_run.md
- profiles/<TRAINING_PROFILE>/data/thresholds/thresholds_swim.md
- profiles/<TRAINING_PROFILE>/data/VO2max/VO2max_bike.md
- profiles/<TRAINING_PROFILE>/data/VO2max/VO2max_run.md
- profiles/<TRAINING_PROFILE>/data/health/hrv.md
- profiles/<TRAINING_PROFILE>/data/health/resting_heart_rate.md
- profiles/<TRAINING_PROFILE>/data/health/sleep.md
- profiles/<TRAINING_PROFILE>/data/health/steps.md
- profiles/<TRAINING_PROFILE>/data/health/weight.md
- profiles/<TRAINING_PROFILE>/data/health/loads.md
- profiles/<TRAINING_PROFILE>/data/zones.md
- relevante neueste health-, activity- und injury-logs
- noch nicht ausgewertete FIT-Dateien in `profiles/<TRAINING_PROFILE>/data/activities/YYYY-Www/`
- Zonen in `profiles/<TRAINING_PROFILE>/data/zones.md` mithilfe der aktuellsten Thresholds aus `profiles/<TRAINING_PROFILE>/data/thresholds/` und den zentralen Prozentvorgaben in dieser Datei neu berechnen. Benutze für Bike-HR-Threshold den Wert für die Run-HR-Threshold minus 5.
- In `profiles/<TRAINING_PROFILE>/data/zones.md` nur die ausgerechneten absoluten Zonen speichern. Die allgemeinen Prozentvorgaben nicht in Profil-Dateien duplizieren.

Zentrale Zonenvorgaben:
- Diese Prozentvorgaben gelten für alle Profile. Beim wöchentlichen Neuberechnen der absoluten Zonen werden nur die Profil-Thresholds ausgetauscht, nicht die Prozentgrenzen.
- Swim- und Run-Speed-Prozente beziehen sich auf CSS bzw. LT-Speed und werden für `zones.md` in Pace-Grenzen umgerechnet.
- Bike-Power-Prozente beziehen sich auf FTP. Run-HR-Prozente beziehen sich auf Run-LTHR. Bike-HR-Prozente beziehen sich auf Bike-HR-Threshold, berechnet als Run-LTHR minus 5.

## Swim-Zonenvorgabe

| Zone | Zonenname | Untere Speed-Grenze / % | Obere Speed-Grenze / % |
|-|-|-|-|
| Z5 | Very fast | 103% | 109% |
| Z4 | Fast | 98% | 103% |
| Z3 | Moderate | 90% | 98% |
| Z2 | Easy | 87% | 90% |

## Bike-Zonenvorgabe

| Zone | Zonenname | Untere HR-Grenze / % | Obere HR-Grenze / % | Untere Power-Grenze / % | Obere Power-Grenze / % |
|-|-|-|-|-|-|
| Z6 | Anaerobic | 110% | / | 110% | / |
| Z5 | VO2max | 104% | 110% | 105% | 110% |
| Z4 | Threshold | 95% | 104% | 90% | 105% |
| Z3 | Tempo | 82% | 95% | 74% | 90% |
| Z2 | Endurance | 75% | 82% | 56% | 74% |
| Z1 | Recovery | / | 75% | / | 56% |

## Run-Zonenvorgabe

| Zone | Zonenname | Untere HR-Grenze / % | Obere HR-Grenze / % | Untere Speed-Grenze / % | Obere Speed-Grenze / % |
|-|-|-|-|-|-|
| Z6 | Anaerobic | 110% | / | 108% | / |
| Z5 | VO2max | 104% | 110% | 103% | 108% |
| Z4 | Threshold | 95% | 104% | 93% | 103% |
| Z3 | Tempo | 87% | 95% | 87% | 93% |
| Z2 | Endurance | 80% | 87% | 80% | 87% |
| Z1 | Recovery | / | 80% | / | 80% |

Regeln:
- profiles/<TRAINING_PROFILE>/data/current-state.md ist die einzige Quelle für den aktuellen Zustand.
- Vor jeder Trainingsplanung oder Trainingsbewertung die neuesten Einträge in `profiles/<TRAINING_PROFILE>/data/current-state.md` prüfen und daraus die `Aktuelle Zusammenfassung` in derselben Datei aktualisieren.
- Die `Aktuelle Zusammenfassung` in `profiles/<TRAINING_PROFILE>/data/current-state.md` als kurze Stichpunktliste pflegen, nicht als Tabelle.
- Jeder Stichpunkt in der `Aktuelle Zusammenfassung` soll eine aktuell gültige Aussage enthalten, idealerweise mit Datum oder Zeitraum, wenn die Aussage zeitabhängig ist.
- In `profiles/<TRAINING_PROFILE>/data/current-state.md` stehen unter `Neueste Updates` chronologische Roh-Updates des Athleten. Diese Updates nicht löschen.
- Bei Widersprüchen zwischen alten Updates und der `Aktuelle Zusammenfassung` gilt die `Aktuelle Zusammenfassung`.
- Historische Dateien nie als aktuellen Zustand interpretieren, außer sie werden ausdrücklich als aktuell referenziert.
- Wenn ein neuer Plan für dieselbe ISO-Woche erzeugt wird, die bestehende Datei `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.html` ersatzlos überschreiben.
- Pläne anderer ISO-Wochen nicht überschreiben, außer der Nutzer verlangt es ausdrücklich.
- Aktivitäten werden nach ISO-Wochen gruppiert: FIT-Dateien, Aktivitätsauswertungen und Wochenreviews liegen unter `profiles/<TRAINING_PROFILE>/data/activities/YYYY-Www/`.
- Wenn `scripts/pre_plan_sync.py` existiert und in `profiles/<TRAINING_PROFILE>/.env` ein gültiger `intervals_icu_api_key` hinterlegt ist, vor jeder Trainingsplan-Erzeugung dieses Skript ausführen.
- `scripts/pre_plan_sync.py` führt die automatisierte Vorstufe aus: FIT-Download, Health-Markdown-Update, FIT-Auswertung und Load-Berechnung.
- Die Einzelschritte liegen in `scripts/download_fit_files.py`, `scripts/update_health.py`, `scripts/analyze_fit_files.py` und `scripts/update_loads.py`.
- Bei jedem Intervals.icu-Sync den lokal neuesten bereits synchronisierten Kalendertag zusätzlich als Überlappungstag erneut abrufen, auch wenn er knapp außerhalb des normalen `--days`-Fensters liegt.
- Den Überlappungstag nach dem frischen Abruf gegen die lokale Darstellung abgleichen und in den technischen Cache-Dateien sowie den kanonischen Health-Historien gezielt überschreiben, damit unvollständige Werte eines laufenden Tages nicht dauerhaft hängen bleiben.
- Teilwerte des aktuellen Tages aus Intervals.icu, z.B. Schritte während des laufenden Tages, sind erwartbar unvollständig; sie dürfen gespeichert werden, müssen aber bei späteren Syncs desselben Tages oder am Folgetag erneut ersetzt werden.
- Nach jeder automatisierten Vorstufe die erzeugten Änderungen und Skript-Warnungen als LLM plausibilisieren; Inkonsistenzen im Chat nennen, z.B. fehlende oder umbenannte Intervals.icu-Felder, unklare TSS-Quellen, nicht eindeutig gematchte Activities oder auffällige Werte.
- Wenn bei einer Planerzeugung, FIT-Auswertung, Health-Aktualisierung, Load-Berechnung oder History-Aktualisierung Inkonsistenzen, Fehler oder wiederholungsgefährdete Schwächen auffallen, diese nicht nur im Chat melden, sondern auch die Ursache genauer beschreiben.
- Wenn die Ursache durch eine Regel, Dokumentation oder Skriptlogik künftig vermeidbar ist, die passende Stelle im Repo direkt nachführen, z.B. `AGENTS.md`, README/Formatdateien oder das betroffene Skript.
- Im Chat ausdrücklich sagen, ob die Korrektur für zukünftige Durchläufe bereits umgesetzt wurde oder ob sie noch offen ist.
- Wenn eine Korrektur nicht sicher automatisierbar ist, im Chat klar benennen, welche Plausibilitätsprüfung beim nächsten Durchlauf weiterhin manuell durch das LLM erfolgen muss.
- Wenn `scripts/pre_plan_sync.py` fehlt, die Einzelschritte manuell mit den vorhandenen Skripten oder nach den folgenden Regeln ausführen.
- `scripts/intervals_icu_sync.py` lädt keine FIT-Dateien herunter und benennt daher auch keine FIT-Dateien; es synchronisiert nur Intervals.icu-Roh-/Cache-Daten für Health, Activities und Sport Settings.
- Manuell abgelegte oder künftig automatisch heruntergeladene FIT-Dateien unter `profiles/<TRAINING_PROFILE>/data/activities/YYYY-Www/` speichern.
- FIT-Dateien mit lokalem Aktivitätsdatum und genau einem Leerzeichen nach dem Datum benennen: `YYYY-MM-DD Aktivitätsname.fit`, z.B. `2026-06-03 VO2max Bike 8x 2min @360W.fit`.
- Emojis aus automatisch erzeugten FIT-Dateinamen entfernen; den Namen ansonsten gut lesbar lassen.
- Ungültige Dateizeichen aus Aktivitätsnamen entfernen oder ersetzen, aber den Namen gut lesbar lassen.
- Die Markdown-Auswertung einer FIT-Datei immer gleichnamig neben der FIT-Datei speichern, nur mit Endung `.md`, z.B. `YYYY-MM-DD Aktivitätsname.md`.
- Vor jeder Trainingsplan-Erzeugung alle noch nicht ausgewerteten `.fit`-Dateien rekursiv unter `profiles/<TRAINING_PROFILE>/data/activities/` auswerten.
- Intervals.icu-Sync darf Roh-/Cache-Dateien nach `profiles/<TRAINING_PROFILE>/data/health/` schreiben; diese Cache-Dateien sind nicht kanonisch.
- Intervals.icu-Daten ergänzen den Trainingskontext, ersetzen aber nicht `profiles/<TRAINING_PROFILE>/data/current-state.md` als Quelle für den aktuellen subjektiven Zustand.

Zwei-Phasen-Planung:
- Neue Wochenpläne standardmäßig in zwei Phasen erstellen: zuerst Planvorschlag im Chat, danach erst nach ausdrücklicher Freigabe finaler Wochenplan als JSON/HTML/PDF.
- Wenn der Nutzer einen Planvorschlag anfordert, zuerst `python scripts/prepare_plan_context.py --week YYYY-Www` ausführen, sofern das Skript existiert. Falls keine Zielwoche genannt wurde, die gemeinte Woche im Chat konkret benennen und die vom Skript ausgegebene Zielwoche verwenden.
- `scripts/prepare_plan_context.py` führt nur die deterministische Vorbereitung aus: Planungsvalidierung, automatisierte Vorstufe bzw. Sync, Zielwoche, Analysewoche und Kontext-Checkliste. Das Skript erzeugt keinen Wochenplan.
- Nach dem Vorbereitungsskript die erzeugten Änderungen und Warnungen plausibilisieren, alle Pflichtkontextdateien lesen, relevante neueste Logs prüfen, `current-state.md` aktualisieren und die Wochenreview der Analysewoche erstellen oder aktualisieren.
- Im Vorschlagsmodus darf die Review-Datei `profiles/<TRAINING_PROFILE>/data/activities/YYYY-Www/review_YYYY-Www.md` geschrieben werden, weil sie kanonische Historie ist. Planartefakte unter `profiles/<TRAINING_PROFILE>/plans/` dürfen im Vorschlagsmodus nicht erzeugt oder überschrieben werden.
- Den ersten Trainingsplan nur im Chat vorschlagen, in einfacher Tagesform mit den wichtigsten Einheiten, z.B. `Mo: Threshold Run (3x15min @4:00/km)`.
- Direkt nach dem einfachen Chat-Vorschlag die neue Trainingswoche in ungefähr `5 bis 10` Sätzen begründen, je nach Datenlage und notwendiger Erklärungstiefe.
- Diese Begründung muss die letzte Trainingswoche, die aktuellen Alltags- und Health-Parameter wie Ruhepuls, Schlaf, HRV, Gewicht, Schritte und Load-Status sowie das aktuelle Feedback aus `current-state.md` zusammenführen.
- Die Begründung soll erklären, warum Umfang, Intensität, Session-Typen und Entlastungstage der vorgeschlagenen Woche zur aktuellen Belastbarkeit, zur verbleibenden Zeit bis zu den kommenden Races/Zielen und zu deren Wichtigkeit passen.
- Dieselbe inhaltliche Begründung muss beim Finalisieren in die Wochenreview der Analysewoche aufgenommen werden, damit sie in der `Wochenanalyse`-Box des finalen Plans erscheint.
- Im Chat-Vorschlag keine Von-bis-Angaben verwenden. Immer konkrete Zielwerte nennen, z.B. `295W` statt `290-300W`.
- Wenn ein fachlicher Zielbereich gemeint ist, im Chat-Vorschlag den Mittelwert oder den sinnvollsten Einzelzielwert verwenden.
- Swim-Einheiten im Chat-Vorschlag nur mit Session-Typ und Hauptset darstellen, ohne Warmup, Cooldown und Technikblock, z.B. `Aerobic Short Swim (10x100m + 5x200m)`.
- Endurance-, Basic- und Long-Sessions bei Bike und Run im Chat-Vorschlag kompakt als Session-Typ mit Dauer und Zielwert darstellen, z.B. `Long Run (1:20h @5:00/km)` oder `Basic Bike (60min @200W)`.
- Ruhetage im Chat-Vorschlag als `Rest` oder leerer Tag darstellen; keine künstliche Session daraus machen.
- Nach Nutzerkommentaren den Chat-Vorschlag iterativ anpassen und Rückfragen beantworten, ohne Planartefakte zu schreiben.
- Erst bei ausdrücklicher Freigabe wie `Erstelle jetzt den finalen Plan für 2026-W27` den finalen Plan erzeugen. Dann `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.json` schreiben, validieren und mit `scripts/render_plan.py` zu HTML/PDF rendern.
- Ohne ausdrückliche Finalisierungsfreigabe keine Datei unter `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.json`, `.html` oder `.pdf` erzeugen oder überschreiben.
- Für laufbezogene Auswertungen, Statistiken und Rückblicke standardmäßig `GAP` (Grade Adjusted Pace) bzw. grade-adjusted running speed verwenden, nicht die rohe Pace, sofern Höhendaten vorliegen.
- Wenn Höhendaten in einer Run-Aktivität fehlen oder nicht belastbar sind, `GAP = Pace` setzen und trotzdem durchgehend als `GAP` sprechen.
- Diese GAP-Regel gilt für Run-FIT-Auswertungen, Run-Lap-Tabellen, Run-Effizienzkennzahlen, Run-HR-Drift/Decoupling, Wochenreview und sonstige laufbezogene statistische Einordnungen aus absolvierten Aktivitäten.
- Diese GAP-Regel gilt nicht zwingend für Trainingsvorgaben im Wochenplan; dort dürfen konkrete Vorgaben weiter als normale Pace wie `4:20/km` stehen bleiben.
- Garmin-Threshold-Historien und andere direkt aus Gerätefeldern gelesene Run-Schwellenwerte bleiben in ihrer gespeicherten Form `min:sec/km`, solange keine separate belastbare GAP-Historie dafür berechnet wird.
- Vor jeder Trainingsplan-Erzeugung die kanonischen Health-Historien aus Intervals.icu-Wellness-/Daily-Daten aktualisieren, in den Markdown-Dateien speichern und für Trainingssteuerung, Wochenreview und Erklärungstext auswerten.
- Wellness-Health-Metriken (`hrv.md`, `resting_heart_rate.md`, `sleep.md`, `steps.md`, `weight.md`) nur aus Intervals.icu-Wellness-/Daily-Daten ableiten, nicht aus einzelnen Aktivitätsdaten.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md` ist die Ausnahme: Load-Metriken werden aus den `TSS`-Werten der Aktivitätsauswertungen berechnet, nicht aus den Wellness-/Daily-Daten.
- Health-Historien unter `profiles/<TRAINING_PROFILE>/data/health/` pflegen: `hrv.md`, `resting_heart_rate.md`, `sleep.md`, `steps.md`, `weight.md`, `loads.md` und optional manuell `calories.md`.
- Health-Historien mit neuesten Einträgen oben führen.
- Für Wellness-Historien jeden Kalendertag eine Zeile schreiben; fehlende Wellness-Werte mit `-` eintragen.
- Gewicht täglich eintragen; wenn Intervals.icu in der Wellness-Tageszeile kein `weight` liefert, `-` eintragen und nicht das letzte bekannte Gewicht fortschreiben.
- Wenn möglich das Körpergewicht standardisiert morgens direkt nach dem Aufstehen, nach dem Toilettengang und vor dem ersten Essen oder Trinken messen; diesen Messzeitpunkt als bevorzugten Referenzwert für die Gewichtshistorie behandeln.
- `profiles/<TRAINING_PROFILE>/data/health/hrv.md`: Tages-RMSSD aus Intervals.icu `hrv` übernehmen.
- `profiles/<TRAINING_PROFILE>/data/health/hrv.md`: `7-Tage-RMSSD` als geometrisches Mittel der Tages-RMSSD-Werte im 7-Kalendertage-Fenster inklusive aktuellem Tag berechnen; fehlende Tageswerte ignorieren; nur berechnen, wenn mindestens `4 von 7` Werten vorhanden sind.
- `profiles/<TRAINING_PROFILE>/data/health/hrv.md`: 90-Tage-RMSSD-Grenzen aus dem 90-Kalendertage-Fenster inklusive aktuellem Tag berechnen; fehlende Tageswerte ignorieren; nur berechnen, wenn mindestens `45 von 90` Werten vorhanden sind.
- `profiles/<TRAINING_PROFILE>/data/health/hrv.md`: HRV-Formeln verwenden: `7-Tage = ROUND(GEOMEAN(Werte),0)`, `Grenze unten = ROUND(GEOMEAN(Werte)/EXP(STDEVP(LN(Werte)))^0.5,0)`, `Grenze oben = ROUND(GEOMEAN(Werte)*EXP(STDEVP(LN(Werte)))^1.5,0)`.
- `profiles/<TRAINING_PROFILE>/data/health/resting_heart_rate.md`: Ruhepuls aus Intervals.icu `restingHR` übernehmen.
- `profiles/<TRAINING_PROFILE>/data/health/sleep.md`: Schlafdauer aus Intervals.icu `sleepSecs` in `h:mm` umrechnen und Sleep Score aus `sleepScore` übernehmen.
- `profiles/<TRAINING_PROFILE>/data/health/steps.md`: Schritte aus Intervals.icu `steps` übernehmen.
- `profiles/<TRAINING_PROFILE>/data/health/steps.md`: `7-Tage-Mittel-Schritte` als arithmetisches Mittel der Schrittwerte im 7-Kalendertage-Fenster inklusive aktuellem Tag berechnen; fehlende Tageswerte ignorieren; nur berechnen, wenn mindestens `4 von 7` Werten vorhanden sind.
- `profiles/<TRAINING_PROFILE>/data/health/calories.md` ist optional und wird manuell gepflegt, nicht aus Intervals.icu abgeleitet. Wenn vorhanden, enthält die Datei die Spalten `Datum`, `Ruhe-Kalorien` und `Aktiv-Kalorien`; neueste Einträge stehen oben.
- Wenn `profiles/<TRAINING_PROFILE>/data/health/calories.md` existiert, vor jedem Planvorschlag prüfen, ob Kalorien mindestens bis zum jeweils gestrigen Kalendertag eingetragen sind. Wenn der neueste Kalorientag älter als gestern ist, dies vor dem Planvorschlag im Chat melden.
- Die Schritte-Tabelle `profiles/<TRAINING_PROFILE>/data/health/steps.md` weiterhin automatisiert pflegen, auch wenn im Plan statt des Schritte-Plots ein Kalorien-Plot angezeigt wird.
- `profiles/<TRAINING_PROFILE>/data/health/weight.md`: Gewicht aus Intervals.icu `weight` übernehmen.
- `profiles/<TRAINING_PROFILE>/data/health/weight.md`: `7-Tage-Mittel-Gewicht` im 7-Kalendertage-Fenster inklusive aktuellem Tag berechnen; fehlende Tageswerte ignorieren; bei `5-7` vorhandenen Werten höchsten und niedrigsten Wert streichen und das arithmetische Mittel der übrigen Werte bilden; bei genau `4` vorhandenen Werten das normale arithmetische Mittel bilden; bei weniger als `4` vorhandenen Werten `-` eintragen; den Mittelwert immer mit `2` Nachkommastellen speichern.
- `profiles/<TRAINING_PROFILE>/data/health/weight.md`: Körperfett aus Intervals.icu `bodyFat` übernehmen.
- `profiles/<TRAINING_PROFILE>/data/health/weight.md`: `7-Tage-Mittel-Körperfettanteil` im 7-Kalendertage-Fenster inklusive aktuellem Tag berechnen; fehlende Tageswerte ignorieren; bei `5-7` vorhandenen Werten höchsten und niedrigsten Wert streichen und das arithmetische Mittel der übrigen Werte bilden; bei genau `4` vorhandenen Werten das normale arithmetische Mittel bilden; bei weniger als `4` vorhandenen Werten `-` eintragen; den Mittelwert immer mit `2` Nachkommastellen speichern.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: Vor jeder Trainingsplan-Erzeugung neu berechnen und mit den Spalten `Datum`, `Tages-TSS`, `ATL`, `CTL`, `TSB`, `ACR` führen.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: Für jeden Kalendertag eine Zeile schreiben; neueste Einträge oben.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: `Tages-TSS` als Summe aller Activity-`TSS`-Werte dieses Kalendertags berechnen; Ruhetage oder Tage ohne Aktivitäts-`TSS` mit `0` eintragen.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: Der älteste vorhandene Eintrag mit ATL/CTL gilt als Startwert; ältere Werte nicht rückwirkend neu erfinden, außer der Nutzer verlangt es ausdrücklich.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: Ab dem Startwert ATL und CTL vorwärts berechnen mit `ATL_heute = ATL_gestern + (TSS_heute - ATL_gestern) / 7` und `CTL_heute = CTL_gestern + (TSS_heute - CTL_gestern) / 42`.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: `TSB = CTL - ATL` berechnen.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: `ACR = ATL / CTL` berechnen; wenn `CTL = 0`, `ACR` als `-` eintragen.
- `profiles/<TRAINING_PROFILE>/data/health/loads.md`: ATL, CTL und TSB auf sinnvolle ganze Werte runden; ACR mit drei Nachkommastellen speichern.
- Vor jeder Trainingsplanung die neuesten Health-Werte analysieren: HRV-Status anhand Tages-RMSSD, 7-Tage-RMSSD und 90-Tage-Korridor; Ruhepuls-Trend; Schlafdauer und Sleep Score; Gewichtstrend; Schritte als Kontext für Alltagsbelastung.
- Vor jeder Trainingsplanung Load-Status aus `profiles/<TRAINING_PROFILE>/data/health/loads.md` analysieren: Tages-TSS, ATL, CTL, TSB und ACR als Belastungs-, Ermüdungs- und Risikoindikatoren für die aktuelle Planwoche berücksichtigen.
- Health-Analyse in die Trainingsentscheidung einbeziehen: bei HRV deutlich unter Korridor, auffällig hohem Ruhepuls, sehr schlechtem Schlaf, starkem Gewichtsabfall oder hoher Alltagsbelastung konservativer planen.
- Wenn Health-Werte unauffällig oder gut sind, dürfen sie eine geplante Progression unterstützen, aber nicht allein eine aggressive Belastungssteigerung begründen.
- Eine `.fit`-Datei gilt als noch nicht ausgewertet, wenn keine gleichnamige `.md`-Datei daneben existiert oder wenn die `.fit`-Datei neuer ist als die `.md`-Auswertung.
- FIT-Auswertungen als gleichnamige Markdown-Dateien neben der FIT-Datei speichern und knapp zusammenfassen: Kurzfassung, kurzer Bericht, Einordnung, relevante Laps/Intervalle.
- FIT-Auswertungen sollen zusätzlich eine strukturierte Zonenauswertung enthalten.
- Jede FIT-Auswertung muss einen Abschnitt `Bericht` enthalten, auch ältere bereits vorhandene Auswertungen, wenn sie erneut angefasst oder im Rahmen einer Nachpflege aktualisiert werden.
- Der Bericht soll ca. 5 bis 6 kurze Sätze enthalten und die einzelne Einheit bewerten: Trainingsreiz, Qualität der Durchführung, auffällige Daten, mögliche Einschränkungen und kurze Konsequenz für die weitere Planung.
- Der Bericht soll keine lange Wochenreview ersetzen; er bewertet nur diese eine Aktivität.
- Ältere Aktivitätsauswertungen können noch nach früheren Formatregeln erstellt worden sein; wenn eine Aktivitätsauswertung neu erstellt oder aktualisiert wird, an die aktuellen Regeln in dieser Datei anpassen.
- In jeder FIT-Auswertung immer genau einen `TSS`-Wert angeben.
- `TSS` in den Markdown-Auswertungen ist der einheitliche Planungs-Load, nicht zwingend FIT-/Garmin-TSS.
- Für `TSS` bei Swim/Bike/Run bevorzugt `icu_training_load` aus Intervals.icu verwenden.
- Bei Aktivitäten außerhalb von Swim/Bike/Run, z.B. Skifahren, bevorzugt `hr_load` aus Intervals.icu als `TSS`/Planungs-Load verwenden.
- Wenn im Aktivitätsnamen `Zustieg` oder `Rückweg` steht, die Aktivität als Hin- bzw. Rückweg fürs Canyoning einordnen.
- Canyoning-Zustiege und -Rückwege nicht als sportartspezifische Swim/Bike/Run-Trainingseinheiten interpretieren, sondern als relevante zusätzliche Outdoor-/Alltagsbelastung mit möglicher muskulärer und orthopädischer Ermüdung.
- Diese Aktivitäten bei Load, Wochenreview und Planungsentscheidung als Kontext berücksichtigen, besonders bei vielen Schritten, Höhenmetern, langer Dauer, hoher Herzfrequenz oder müden Beinen.
- Wenn Intervals.icu keinen `icu_training_load` liefert, als Fallback FIT `session.training_load_peak` verwenden.
- Wenn auch `training_load_peak` fehlt, als weiteren Fallback Intervals.icu `hr_load` verwenden.
- Wenn keine belastbare TSS-/Load-Quelle verfügbar ist, `TSS: -` eintragen und diesen Eintrag für `profiles/<TRAINING_PROFILE>/data/health/loads.md` nicht als Belastungswert mitzählen.
- Den `TSS`-Wert in der Markdown-Auswertung nur als `TSS: <Wert>` ausgeben und keine Quellenangabe in Klammern daneben schreiben.
- FIT `session.training_stress_score` darf als ergänzende Information intern berücksichtigt werden, ersetzt aber den einheitlichen Planungs-`TSS` nur, wenn kein besserer Planungs-Load nach den obigen Prioritäten verfügbar ist.
- In FIT-Auswertungen `Aerobic Training Effect` und `Anaerobic Training Effect` aufnehmen, sofern im FIT oder aus Intervals.icu verfügbar; fehlende Werte nicht schätzen.
- Bei Bike- und Run-Auswertungen eine einfache Effizienzkennzahl aufnehmen: Bike als `Power/HF` in `W/bpm`, Run trendfähig als `GAP-Speed/HF` in `m/s/bpm` und zusätzlich lesbar als `GAP @ Avg HR`.
- Bei Bike- und Run-Auswertungen die Zeit in den aktuellen Zonen aus `profiles/<TRAINING_PROFILE>/data/zones.md` auswerten und in der FIT-Zusammenfassung speichern.
- Bei Swim-Auswertungen die Distanz in den aktuellen Zonen aus `profiles/<TRAINING_PROFILE>/data/zones.md` auswerten und in der FIT-Zusammenfassung speichern; dafür nach Möglichkeit die einzelnen Bahnen/Lengths anhand ihrer Pace zonieren, bei fehlenden Length-Daten ersatzweise über sinnvolle Lap-Blöcke.
- Die primäre Zonierungslogik soll explizit sein: Swim-Zonen nach Pace, Bike-Zonen nach Power, Run-Zonen nach GAP.
- Herzfrequenzzonen sind für diese Zonenauswertungen und Wochen-Zonenplots nur ergänzender Kontext und nicht die primäre Zuordnungslogik.
- Für Swim-Zonenauswertungen langsamer als die definierte `Z2` analytisch als `Z1` behandeln, damit Warmup-, Technik- und sehr lockere Bahnen in der Verteilung nicht verloren gehen.
- Bei `Basic`- und `Long`-Sessions von Bike und Run HR-Drift bzw. Decoupling berechnen, sofern die Datenqualität ausreicht.
- HR-Drift über vergleichbare steady Abschnitte berechnen, bevorzugt erste vs. zweite Hälfte ohne Pausen, offensichtliche Stops, Warmup/Cooldown und nicht repräsentative Intervalle.
- Bei Run für HR-Drift nach Möglichkeit GAP-basierte Geschwindigkeit statt roher Pace/Geschwindigkeit verwenden.
- HR-Drift in Prozent angeben und kurz einordnen, z.B. stabil, moderat driftend oder deutlich driftend; bei unruhigem Profil oder zu kurzen Daten `HR-Drift: nicht sinnvoll berechenbar` schreiben.
- Bei Run-Auswertungen Schrittfrequenz, Schrittlänge, Bodenkontaktzeit und vertikale Bewegung aufnehmen, sofern im FIT vorhanden.
- Run-Technikwerte zeitabhängig darstellen: in der Lap-/Intervalltabelle zusätzliche Spalten für `Cadence`, `Stride`, `GCT` und `Vert.` verwenden, wenn diese Werte pro Lap oder Intervall sinnvoll aggregierbar sind.
- In Run-Lap-/Intervalltabellen `GAP` statt `Pace` anzeigen.
- In Swim-Lap-Tabellen zusätzlich die zugeordnete Zone anzeigen, sofern eine sinnvolle Pace-Zuordnung möglich ist.
- Bei Bike-Auswertungen Kadenz, Links/Rechts-Balance und Torque Effectiveness aufnehmen, sofern im FIT vorhanden.
- Bike-Technikwerte zeitabhängig darstellen: in der Lap-/Intervalltabelle zusätzliche Spalten für `Cadence`, `L/R Balance` und `Torque Eff.` verwenden, wenn diese Werte pro Lap oder Intervall sinnvoll aggregierbar sind.
- Wenn sehr viele Laps vorhanden sind, die Technik- und Effizienzwerte nicht für jede irrelevante Auto-Lap ausbreiten; stattdessen relevante Arbeitsabschnitte, Intervalle oder aggregierte Blöcke darstellen.
- Fehlende Sensorfelder in FIT-Auswertungen nicht als Problem behandeln, sondern einfach weglassen oder mit `-` markieren, wenn die Tabellenstruktur sonst klarer bleibt.
- Run-off-Bike-Sessions selbstständig anhand der Uhrzeiten erkennen: Wenn an einem Tag ein Run zeitlich kurz nach einer Bike-Aktivität startet, diesen Run als möglichen Brick/Run off Bike einordnen.
- Dafür Start- und Endzeitpunkte der FIT-Dateien vergleichen; ein Run innerhalb von ungefähr `0-30min` nach Bike-Ende gilt in der Regel als Run off Bike, innerhalb von ungefähr `30-90min` als wahrscheinlicher oder möglicher Run off Bike, abhängig von Kontext und Aktivitätsnamen.
- Wenn die Uhrzeit-Erkennung unsicher ist, dies in der FIT-Auswertung und Wochenreview als wahrscheinlich/möglich formulieren und nicht als sichere Tatsache behaupten.
- Erkannte Run-off-Bike-Sessions bei der Trainingsbewertung als spezifischen Kopplungsreiz berücksichtigen, nicht als isolierten normalen Run.
- Vor jeder Trainingsplan-Erzeugung aus allen neuen Bike- und Run-FIT-Dateien die Garmin-Thresholds auslesen und die Threshold-Historie aktualisieren.
- Bike-Thresholds unter `profiles/<TRAINING_PROFILE>/data/thresholds/thresholds_bike.md` speichern; beim Bike ausschließlich `FTP / W` tracken.
- Bike-FTP aus FIT-Dateien aus `session.threshold_power` lesen.
- Run-Thresholds unter `profiles/<TRAINING_PROFILE>/data/thresholds/thresholds_run.md` speichern; beim Run ausschließlich `LT / bpm` und `LT / min:sec/km` tracken.
- Run-LTHR aus FIT-Dateien bevorzugt aus `unknown_79` (`global_mesg_num = 79`, FitFileViewer: `User Metrics`) Field `11` lesen; alternativ aus `zones_target.threshold_heart_rate` oder `time_in_zone.threshold_heart_rate`, wenn `unknown_79` fehlt.
- Run-LTSpeed aus FIT-Dateien bevorzugt aus `unknown_79` (`global_mesg_num = 79`, FitFileViewer: `User Metrics`) Field `13` lesen; der Rohwert ist in `km/h * 10` codiert, z.B. `157` = `15.7km/h`, und muss in Pace `min:sec/km` umgerechnet werden.
- Run-LTSpeed als Fallback aus `user_profile` Field `37` lesen, wenn `unknown_79` fehlt.
- Run-Threshold-Power (`ltpower`, z.B. `unknown_79` Field `12`) nicht tracken.
- Bike-Threshold-HR nicht tracken, da dieser Wert in FIT-Dateien statisch oder unzuverlässig sein kann.
- Threshold-Einträge auf das Datum des jeweils letzten vorherigen FIT-Files derselben Sportart datieren, weil die Garmin-Thresholds im FIT die Einstellung zu Beginn der Session beschreiben und neue Thresholds erst eine Session später sichtbar werden.
- Wenn für ein FIT-File kein vorheriges FIT-File derselben Sportart im Repo vorhanden ist, den darin gefundenen Threshold nicht in die History schreiben, weil kein korrektes Rückdatierungsdatum bestimmt werden kann.
- Neue Thresholds nur eintragen, wenn sich der relevante Wert gegenüber dem letzten Eintrag der jeweiligen Threshold-Datei geändert hat; identische Wiederholungen mit neuem Datum nicht speichern.
- Vor jeder Trainingsplan-Erzeugung aus allen neuen Bike- und Run-FIT-Dateien die Garmin-VO2max-Werte auslesen und die VO2max-Historie aktualisieren.
- Bike-VO2max unter `profiles/<TRAINING_PROFILE>/data/VO2max/VO2max_bike.md` speichern; Run-VO2max unter `profiles/<TRAINING_PROFILE>/data/VO2max/VO2max_run.md` speichern.
- VO2max bevorzugt aus `activity_metrics` (`global_mesg_num = 140`, FitFileViewer: `Activity Metrics`) Field `7` lesen; der Rohwert wird mit `raw / 18724.571428571428` in `ml/kg/min` umgerechnet.
- `activity_metrics.vo2_max` beschreibt den Wert nach der Aktivität; VO2max-Einträge deshalb auf das Datum derselben FIT-Aktivität datieren und nicht auf das vorherige FIT-File zurückdatieren.
- Wenn `activity_metrics` Field `7` fehlt oder `0` ist, als Fallback `user_metrics` (`global_mesg_num = 79`, FitFileViewer: `User Metrics`) Field `0` verwenden; der Rohwert wird mit `raw / 292.57142857142856` in `ml/kg/min` umgerechnet.
- VO2max-Werte mit sinnvoller Nachkommastelle gemäß Datei/Parser speichern; bestehende Tabellenstruktur der jeweiligen `profiles/<TRAINING_PROFILE>/data/VO2max/VO2max_<sport>.md` beibehalten.
- Bei VO2max-Historien sind die Spaltennamen `VO2max / ml/min/kg` und `VO2max / ml/kg/min` inhaltlich gleich zu behandeln; bestehende Dateien nicht nur wegen dieser Einheitenschreibweise umformatieren.
- Neue VO2max-Werte nur eintragen, wenn sich der relevante Wert gegenüber dem letzten Eintrag der jeweiligen VO2max-Datei geändert hat; identische Wiederholungen mit neuem Datum nicht speichern.
- Bei Run-FIT-Auswertungen manuelle Timer-Stops von ungefähr `1-2min` als wahrscheinlichen GI-Hinweis interpretieren, insbesondere wenn sie ohne trainingslogische Pause auftreten.
- Direkte Herzfrequenzabfälle nach solchen Stops nicht als normale Belastungsreaktion oder bessere Erholung fehlinterpretieren; sie können durch die unterbrochene Aktivität entstehen.
- Wenn bei Runs wiederkehrende Stop-Muster auftreten, dies im Chat als möglichen GI-/Stuhldrang-Hinweis und mit praktischen Tipps ansprechen.
- GI-/Stuhldrang-Muster nicht automatisch in die Wochenreview, die `Aktuelle Zusammenfassung` oder den Wochenplan schreiben, außer der Nutzer bittet ausdrücklich darum oder es ist für die Trainingsentscheidung zwingend relevant.
- Bei Müdigkeit, Verletzung, schlechtem Schlaf, auffälliger HRV oder ungewöhnlich hohem Ruhepuls konservativ planen.
- Automatisierte Health-Historien aus `profiles/<TRAINING_PROFILE>/data/health/` als objektiven Kontext nutzen; subjektive oder außergewöhnliche Health-, Müdigkeits- und Beschwerdeangaben aus `profiles/<TRAINING_PROFILE>/data/current-state.md` zusätzlich berücksichtigen und bei Widersprüchen explizit einordnen.
- Manuelle Anpassungen des Athleten am Wochenplan, z.B. geänderte Umfänge, verschobene Einheiten oder bewusst härter/weicher gefahrene Intervalle je nach Tagesform, als relevantes Trainingssignal behandeln und nicht nur als einfache Planabweichung.
- Wenn Einheiten nur zwischen Wochentagen getauscht wurden, dies als organisatorische Verschiebung erkennen und beim Matching `geplant vs. absolviert` berücksichtigen; nicht krampfhaft die falsche absolvierte Einheit mit einer anderen geplanten Einheit matchen, wenn inhaltlich eigentlich nur ein Tagestausch vorliegt.
- Unsicherheiten und fehlende Daten explizit nennen.
- Im gesamten Repo sind deutsche Umlaute und `ß` erlaubt und gewünscht; neue oder aktualisierte deutsche Texte nicht in ASCII-Umschreibungen wie `ae`, `oe`, `ue` oder `ss` ausweichen lassen, wenn eigentlich `ä`, `ö`, `ü` oder `ß` gemeint ist.
- Datumsformat: YYYY-MM-DD.
- Wochenformat: ISO-Woche, z.B. 2026-W23.
- Chronologische Historientabellen, z.B. VO2max-, Threshold- und absolvierte Race-Listen, mit den neuesten Einträgen oben führen; neue Einträge oben direkt unter dem Tabellenkopf einfügen.

Session-Typen und Trainingslogik:
- Swim-Session-Typen: `Aerobic Short`, `Aerobic Long`, `Threshold`, `VO2max`.
- Bei Swim-Einheiten am Anfang standardmäßig `10 x 50m Technik` einplanen; das genügt als Technikanteil.
- Swim-Hauptsets darf das LLM selbst passend zu Session-Typ, Race-Nähe und aktueller Belastbarkeit wählen.
- Swim-Hauptsets bewusst einfach halten: pro Einheit darf ein einzelnes Hauptset genügen; wenn mehrere Hauptsets sinnvoll sind, eher nur zwei, maximal drei unterschiedliche Hauptset-Strukturen verwenden.
- Bike-Session-Typen: `Long`, `Basic`, `Tempo`, `Threshold`, `VO2max`, `Anaerobic`.
- Run-Session-Typen: `Long`, `Basic`, `Tempo`, `Threshold`, `VO2max`, `Anaerobic`, optional kurze `Run off Bike` Sessions mit konkreter Pace.
- Pro Woche und Sportart maximal eine Intervall-Session planen, z.B. maximal ein Bike-Intervall und maximal ein Run-Intervall.
- Als Intervall-Session zählen ausschließlich `Tempo`, `Threshold`, `VO2max` und `Anaerobic`.
- `Long` und `Basic` sind keine Intervall-Sessions.
- Bei Bike und Run keine generische Session-Art `Intervalle` verwenden; immer den konkreten Intervall-Typ benennen. Im fertigen Plan heißen diese Sessions nur `Tempo`, `Threshold`, `VO2max` oder `Anaerobic`, ohne den Zusatz `-Intervall`.
- Die hauptsächliche Planung soll auf den genannten Session-Typen beruhen. Falls trainingslogisch nötig, dürfen vereinzelt weitere Session-Typen genutzt werden.
- Die Wochenstruktur aus `profiles/<TRAINING_PROFILE>/data/availability.md` unter `Standard Woche` ist die dauerhafte Standardstruktur für Wochenpläne.
- Die Wochenstruktur soll grundsätzlich stabil bleiben: gleiche Session-Arten an gleichen Wochentagen planen, sofern Zustand, Rennen oder Verfügbarkeit nicht dagegen sprechen.
- Bei Sonderverfügbarkeiten möglichst alle wesentlichen Session-Arten der Standardwoche sinnvoll auf die verfügbaren Tage verteilen oder durch gleichwertige geplante Belastungen ersetzen. Keine Einheit nur zur Vollständigkeit zusätzlich erzwingen, wenn sie den Wochenreiz unnötig dupliziert oder Erholung und Trainingswirkung verschlechtert.
- Inhalte, Intervallformate, Zielwerte und Umfänge selbstständig festlegen und progressiv entwickeln.
- Zielwerte für Pace, Power und HR standardmäßig aus der Mitte der passenden Zone in `profiles/<TRAINING_PROFILE>/data/zones.md` ableiten, sofern keine spezifischere Vorgabe oder trainingslogische Abweichung dagegen spricht.
- Intervall-Einheiten zu Beginn eines Aufbaus eher kurz und hart planen; in Richtung Race eher länger und race-specific planen.
- Bei Intervall-Workouts standardmäßig `5min Warmup` und `2min Cooldown` verwenden, sofern nicht ausdrücklich anders gewünscht.
- Bei Run-Intervallen standardmäßig eine `Trabpause` zwischen den aktiven Phasen verwenden, z.B. `8 x 2min @3:45/km,2min Trabpause`.
- Bei Bike-Intervallen die Pausen standardmäßig mit der persönlichen Standard Bike-Pausenleistung aus `profiles/<TRAINING_PROFILE>/data/athlete-profile.md` ansetzen.
- Von diesen Pausenstandards darf in besonderen Fällen abgewichen werden; jede Abweichung im Chat explizit nennen und begründen.

Subjektive Intervallsteuerung:
- Für Bike und Run die Progression von Intervall-Sessions getrennt bewerten.
- Intervall-Sessions sollen den geplanten physiologischen Zielreiz klar treffen, aber nicht standardmäßig als maximale Tests geplant werden.
- Die letzte Wiederholung soll fordernd sein, aber technisch sauber und kontrolliert bleiben.
- Nach Intervall-Sessions `RPE` und `Gefühl` aus der FIT-Auswertung berücksichtigen, sofern vorhanden.
- `RPE` prüft, ob die Einheit grob zum geplanten Session-Typ gepasst hat.
- `Gefühl` ist der primäre Progressionsregler für die nächste ähnliche Intervall-Session derselben Sportart.
- `RPE` gilt als grob passend, wenn es ungefähr im erwarteten Bereich des Session-Typs liegt; eine Toleranz von etwa `+/-2` ist akzeptabel.
- Wenn `RPE` grob passt, nach `Gefühl` steuern: bei `+2` klar progressiv planen, bei `+1` leicht progressiv planen, bei `0` stabil halten, bei `-1` leicht entschärfen, bei `-2` deutlich entschärfen oder kontrollierteren Reiz wählen.
- Wenn `RPE` deutlich zu niedrig ist und `Gefühl` neutral bis positiv ist, war der Reiz vermutlich zu soft; die nächste ähnliche Session stärker steigern.
- Wenn `RPE` deutlich zu hoch ist, nicht stark progressieren, auch wenn `Gefühl` positiv ist; eher stabilisieren oder nur minimal steigern.
- Wenn `Gefühl` negativ ist, vorsichtig planen, unabhängig davon ob `RPE` im Zielbereich lag.
- Wenn objektive Daten gegen das subjektive Gefühl sprechen, z.B. ungewöhnlich hohe HF, deutlicher Leistungsabfall, abgebrochene Einheit oder auffällig hoher TSS, konservativ entscheiden.
- Progression bevorzugt über eine Variable vornehmen, nicht gleichzeitig deutlich Umfang und Intensität erhöhen.
- Bike-Progression bevorzugt über Wiederholungszahl, Intervalllänge, dann erst Zielpower steuern.
- Run-Progression bevorzugt über Wiederholungszahl oder Intervalllänge steuern; Pace nur vorsichtig erhöhen.
- Beim Run konservativer progressieren als beim Bike, weil das orthopädische Risiko höher ist.

- Long-Bike- und Long-Run-Umfang anhand der persönlichen Long-Session-Richtwerte aus `profiles/<TRAINING_PROFILE>/data/athlete-profile.md` planen.
- Die dort hinterlegten Long-Session-Maximalwerte sind Obergrenzen, keine wöchentlichen Zielwerte.
- Keine formalen Trainingsphasen erzwingen. Trainingsentscheidungen aus Zielen, Race-Kalender, aktueller Belastbarkeit und Standard-Wochenstruktur ableiten.
- Die Ausrichtung der Sessions nach der Wichtigkeit der Rennen in `profiles/<TRAINING_PROFILE>/data/races.md` gewichten.
- Die neue Trainingswoche so planen, dass sie die kommenden Ziele aus `profiles/<TRAINING_PROFILE>/data/goals.md` und die geplanten Rennen aus `profiles/<TRAINING_PROFILE>/data/races.md` möglichst gut abdeckt.
- Die Priorisierung der Trainingsreize aus der Kombination von verbleibender Zeit bis zum Race/Ziel, Wichtigkeit des Race/Ziels, aktueller Belastbarkeit und nötigem Anpassungsreiz ableiten.
- Nahe, wichtige Ziele dürfen die Woche stärker spezifisch prägen; weiter entfernte oder weniger wichtige Ziele sollen eher über grundlegende, nachhaltige Entwicklungsreize berücksichtigt werden.
- Das geplante Rennen mit der höchsten Wichtigkeit in `profiles/<TRAINING_PROFILE>/data/races.md` dynamisch als aktuelles Hauptrennen bestimmen; dieses Hauptrennen dominiert die langfristige Trainingsausrichtung.
- Kurz vor weniger priorisierten Rennen dürfen einzelne spezifische Sessions für diese Rennen geplant werden, solange sie die langfristige Ausrichtung auf das wichtigste Rennen nicht unverhältnismäßig stören.

Planungsurteil vor Regelbefolgung:
- Bei jeder Planerstellung die bestehenden Vorgaben, Standardwoche, Verfügbarkeit, Long-Session-Richtwerte, Intervallbegrenzungen, Session-Typen und bisherigen Wochenrhythmus aktiv gegen den aktuellen Kontext prüfen.
- Regeln sind Leitplanken, keine blinde Ausführungsanweisung. Wenn aktuelle Belastbarkeit, Health-Werte, subjektives Feedback, Race-Nähe, Zielpriorität, Verletzungsrisiko oder Trainingslogik gegen die Standardlösung sprechen, soll das LLM eine bessere abweichende Lösung vorschlagen.
- Sinnvolle Abweichungen können z.B. geänderte Wochentage, veränderte Long-Session-Dauer, weniger oder andere Intervalle, ein anderer Wochenrhythmus, ein Tempodauerlauf, Sweet-Spot-Finish in einer Long Session, zusätzliche Entlastung, eine bewusst gestrichene Einheit oder eine andere Session-Art sein.
- Eine Abweichung darf nur erfolgen, wenn sie trainingslogisch begründet ist und das Ziel besser erfüllt als die Standardvorgabe.
- Jede relevante Abweichung von Standardwoche, Verfügbarkeit, Long-Session-Richtwerten, Intervallregeln oder üblichen Session-Typen im Chat klar nennen und begründen.
- Wenn die Standardvorgaben trotz Alternativen sinnvoll bleiben, dies kurz begründen, insbesondere wenn naheliegende Abweichungen bewusst nicht gewählt wurden.
- Im Planvorschlag nicht nur ausführen, was erlaubt ist, sondern aktiv erklären, warum die gewählte Woche im Vergleich zu naheliegenden Alternativen die sinnvollere Lösung ist.
- Beispiele für klar zu kommunizierende Hinweise: mehr Schwimmeinheiten wären sinnvoll als die aktuelle Verfügbarkeit erlaubt; die Standardwoche sollte geändert werden; Brick Sessions wären sinnvoll; Vorgaben widersprechen sich; die langfristige Race-Ausrichtung passt nicht zur aktuellen Wochenstruktur.

Wochenreview:
- Vor jeder neuen Wochenplan-Erzeugung eine ausführliche Bewertung der letzten abgeschlossenen Trainingswoche erstellen.
- Die kanonische Bewertung im jeweiligen Aktivitätsordner speichern: `profiles/<TRAINING_PROFILE>/data/activities/YYYY-Www/review_YYYY-Www.md`.
- Der Dateiname der Wochenreview bezeichnet die bewertete ISO-Woche: `profiles/<TRAINING_PROFILE>/data/activities/2026-W23/review_2026-W23.md` ist die Review für Woche 23.
- Die Review einer abgeschlossenen Woche soll im Plan der folgenden Woche erscheinen, z.B. `profiles/<TRAINING_PROFILE>/data/activities/2026-W23/review_2026-W23.md` im Plan `profiles/<TRAINING_PROFILE>/plans/2026-W24.html`.
- Die Review-Datei ist der kanonische Fließtext für die große Analyse-Box im Wochenplan; sie soll nicht nur den Rückblick enthalten, sondern auch die trainingslogischen Implikationen für die kommende Planwoche.
- Im HTML-Wochenplan eine große Box `Wochenanalyse` anzeigen, die diesen Fließtext ausführlich wiedergibt und nicht auf wenige Sätze verkürzt.
- In jeder Wochenreview zusätzlich einen strukturierten Abschnitt `Wochenstatistik` pflegen.
- `Wochenstatistik` soll mindestens die aufsummierte Dauer und die aufsummierten TSS-Werte der Woche für Swim, Bike und Run enthalten.
- Diese Wochenstatistik wird aus den Aktivitätsauswertungen der jeweiligen ISO-Woche gebildet und dient als kanonische Quelle für aggregierte Wochenplots.
- Für die Wochenreview primär die FIT-Auswertungen und Aktivitätsnotizen der letzten abgeschlossenen ISO-Woche bzw. der letzten 7 Tage verwenden.
- Als Grundlage für die Wochenreview `profiles/<TRAINING_PROFILE>/data/current-state.md`, FIT-Auswertungen, Aktivitätsnotizen, den Vorwochenplan, `profiles/<TRAINING_PROFILE>/data/goals.md` und `profiles/<TRAINING_PROFILE>/data/races.md` heranziehen.
- Health-Historien aus `profiles/<TRAINING_PROFILE>/data/health/hrv.md`, `profiles/<TRAINING_PROFILE>/data/health/resting_heart_rate.md`, `profiles/<TRAINING_PROFILE>/data/health/sleep.md`, `profiles/<TRAINING_PROFILE>/data/health/steps.md`, `profiles/<TRAINING_PROFILE>/data/health/weight.md` und `profiles/<TRAINING_PROFILE>/data/health/loads.md` in die Wochenreview einbeziehen.
- Im Wochenfazit kurz einordnen, ob die Health-Werte die Trainingsbelastung der neuen Woche unterstützen oder ob sie für konservativere Planung sprechen.
- Die Wochenreview soll vollständig trainingswissenschaftlich und athletenbezogen formuliert sein; technische Repo-, Skript-, Import-, Sync-, Parser-, Intervals-Matching- oder FIT-Verfügbarkeits-Hinweise gehören ausschließlich in den Chat, nicht in die Review und nicht in die HTML-Review-Box.
- In der Wochenreview keine Formulierungen wie `FIT-Dateien wurden nachgeladen`, `fehlende Dateien`, `kein Intervals-Match`, `FIT-Fallback`, `Skriptwarnung`, `Parser`, `technische Datenlage` oder ähnliche technische Hinweise verwenden.
- Wenn technische Unsicherheiten die Trainingsbewertung beeinflussen, diese im Chat benennen; in der Review nur die trainingsrelevante Konsequenz formulieren, z.B. `der rechnerische Belastungswert wirkt für die kurze Dauer auffällig hoch und wird daher konservativ interpretiert`.
- Die Wochenreview soll nicht primär Einheiten nacherzählen, sondern erklären, was die Woche trainingslogisch bedeutet.
- Aufbau der Wochenreview: 1. Kurzfazit zum Charakter der Woche; 2. knapper Abgleich geplant vs. absolviert mit Fokus auf relevante Abweichungen; 3. gesetzte Trainingsreize, z.B. aerobe Basis, VO2max, Threshold, race-specific oder Kopplung; 4. Belastungswirkung anhand TSS, ATL, CTL, TSB, ACR und Belastungsverteilung; 5. Health-Response anhand HRV, Ruhepuls, Schlaf, Gewicht, Schritte und subjektivem Zustand; 6. Sportarten-Entwicklung für Swim, Bike und Run mit Zusammenspiel und aktueller Limitierung; 7. Zielbezug zu kurzfristigen Rennen und langfristigem Hauptrennen; 8. Risiko oder Limitierung; 9. konkrete Konsequenz und Planungsimplikation für die nächste Planwoche.
- Key Sessions nur als Belege für diese Punkte verwenden, nicht als vollständige Nacherzählung jeder Einheit.
- Zusammenhänge explizit erklären, z.B. warum eine gute Bike-Woche trotzdem zu vorsichtiger Laufplanung führen kann, oder warum gute Schlafwerte eine hohe akute Last nur teilweise kompensieren.
- Health-Daten nicht isoliert aufzählen, sondern als Reaktion auf Training interpretieren, z.B. HRV unter Korridor nach hoher Wochenendlast, guter Schlaf als entlastender Faktor, hoher ACR als Grund für konservative Planung.
- Wenn die Daten, Trends oder Beobachtungen konkrete Verbesserungsmöglichkeiten nahelegen, soll die Wochenreview auch kurze, konkrete Tipps enthalten.
- Diese Tipps dürfen Health-, Performance- und Trainingsaspekte betreffen, z.B. Schlaf, Energiebilanz, Körperfettentwicklung, Ernährungsverhalten, sinnvolle Supplement-Themen, Pacing, Kadenz, Technik, Warmup-Gestaltung, Intervallsteuerung oder Belastungsverteilung.
- Solche Tipps sind optional und nur dann aufzunehmen, wenn es dafür echte Anhaltspunkte aus den Daten, FIT-Auswertungen, dem aktuellen Zustand oder wiederkehrenden Mustern gibt; keine generischen Standardratschläge ohne Bezug zum Athleten.
- Health-Tipps sollen leistungsorientiert und pragmatisch formuliert sein, z.B. wie ein Ziel-Körperfettanteil realistischer erreicht werden kann oder welche Recovery-Gewohnheit aktuell den größten Hebel hätte.
- Trainings- und Performance-Tipps sollen möglichst konkret und umsetzbar sein, z.B. leicht andere Kadenz, kontrollierterer Intervallstart, andere Pausengestaltung, bessere Belastungsreihenfolge oder konservativerer Laufaufbau.
- Wenn Ernährung, Supplements oder Health-Maßnahmen erwähnt werden, nur als vorsichtige leistungsbezogene Empfehlung oder Diskussionsanstoß formulieren, nicht als medizinische Gewissheit.
- Die Wochenreview darf analytisch und interpretierend sein; sie soll klar sagen, welche Annahmen aus den Daten abgeleitet werden und wo trainingswissenschaftliche Unsicherheit bleibt.
- Ton der Wochenreview: analytisch, erklärend, trainingswissenschaftlich und athletenbezogen.
- Nicht nur beschreiben, was passiert ist, sondern warum es für die Entwicklung relevant ist.
- Keine generische Trainingslehre; immer auf konkrete Daten, Ziele, Race-Kontext und aktuellen Zustand beziehen.
- Ältere FIT-Auswertungen und Aktivitätsnotizen nur berücksichtigen, wenn sie für den aktuellen Zustand, erkennbare Trends oder die Zielbewertung noch relevant sind.
- Nicht alle historischen FIT-Dateien jedes Mal gleich stark gewichten; alte Aktivitäten sind Historie, nicht automatisch aktueller Zustand.
- Wenn ein Plan der Vorwoche existiert, einen kurzen Abgleich `geplant vs. absolviert` aufnehmen, ohne daraus eine lange Kontrollliste zu machen.
- Wenn der Athlet den Plan manuell angepasst hat, diese Anpassungen bewusst erkennen und trainingslogisch einordnen: Was wurde geändert, warum war die Anpassung wahrscheinlich sinnvoll oder nicht sinnvoll, und ob daraus ein Muster für die zukünftige Planung ableitbar ist.
- Reine Tagestausche von Einheiten aus privaten/organisatorischen Gründen im Wochenreview normalerweise nicht ausdrücklich hervorheben, außer sie hatten trainingslogisch relevante Nachteile oder Risiken, z.B. ungünstige orthopädische Belastungsreihenfolge.
- Solche manuellen Anpassungen als mögliches Lernsignal für die nächste Planung nutzen, z.B. wenn Intervalle regelmäßig über Zielleistung gefahren werden, wenn Umfang an bestimmten Tagen wiederholt besser toleriert wird oder wenn bestimmte Einheiten systematisch reduziert/verschoben werden.
- Reine organisatorische Tagestausche nicht als neues Planungsmuster für die nächste Woche lernen; für die neue Woche gilt weiterhin die Standardwoche, sofern nicht trainingslogisch begründet davon abgewichen werden sollte.
- Die Bewertung soll ungefähr 10 bis 15 Sätze lang sein; wenn trainingslogisch nötig, darf sie etwas länger sein.
- Kurz auf einzelne Sessions eingehen, wenn sie besonders gut, besonders schlecht oder trainingslogisch auffällig waren.
- Daraus kurz ableiten, wie die aktuelle Form in den Sportarten Swim, Bike und Run momentan ist und ob diese in Einklang mit den Zielen in `profiles/<TRAINING_PROFILE>/data/goals.md` steht.
- Die Wochenreview soll beurteilen, ob der Athlet auf gutem Kurs für die Ziele aus `profiles/<TRAINING_PROFILE>/data/goals.md` und die Rennen aus `profiles/<TRAINING_PROFILE>/data/races.md` ist.
- Dabei getrennt auf kurzfristige, weniger wichtige Rennen und langfristige, wichtigere Ziele eingehen.
- Besonders das realistische Erreichen der Ziele beurteilen, z.B. Qualifikation, Leistungsaufbau, Rennspezifik und verbleibende Zeit.
- Eine kurze Konsequenz für die aktuelle Planwoche nennen, z.B. Umfang steigern, Intensität begrenzen, spezifischen Reiz setzen oder konservativ bleiben.
- Trainingsrelevante Datenlücken wie fehlende Schlaf-, HRV- oder Müdigkeitsdaten nur dann erwähnen, wenn sie die Aussagekraft der Bewertung relevant begrenzen; technische Gründe für Datenlücken nur im Chat erklären.

Wochenplan-Format:
- Der kanonische strukturierte Wochenplaninhalt liegt in `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.json`.
- `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.json` ist das Zwischenformat, das vom LLM inhaltlich erzeugt oder aktualisiert wird; `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.html` und `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.pdf` sind daraus deterministisch gerenderte Artefakte.
- Das JSON-Schema des Wochenplans liegt in `plan-format/plan.schema.json` und ist bei neuen oder geänderten Wochenplänen einzuhalten.
- Das LLM soll Wochenpläne künftig nicht mehr direkt als HTML schreiben, sondern den inhaltlichen Plan in `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.json` pflegen.
- Jede Tageszeile im JSON enthält `date` und `sessions`; jede Session enthält mindestens `sport`, `title`, `amount` und `duration`, optional `tag` und `content`.
- `amount` ist der rechts oben angezeigte Wert in der Card; `duration` ist die für Summen und Rendering maßgebliche Dauer der Session. Bei Swim ist `amount` typischerweise die Distanz, während `duration` die geschätzte Dauer für den Gesamtumfang bleibt.
- Wenn eine Woche eine Race-Session als einen gemeinsamen Block enthält und die vier Umfangsboxen dadurch nicht sauber automatisch aus Swim/Bike/Run ableitbar sind, darf das JSON zusätzlich ein `summary_override` mit `total`, `swim`, `bike` und `run` enthalten.
- Für Wettkampftage darf ein eigener Session-Typ `race` verwendet werden.
- Nach jeder JSON-Änderung den Wochenplan mit `python scripts/render_plan.py --plan profiles/<TRAINING_PROFILE>/plans/YYYY-Www.json --newest YYYY-MM-DD --pdf` rendern, sofern PDF ebenfalls aktualisiert werden soll.
- `scripts/render_plan.py` ist der kanonische Renderer für Wochenpläne. Er liest das Plan-JSON, zieht die Analyse aus `profiles/<TRAINING_PROFILE>/data/activities/YYYY-Www/review_YYYY-Www.md`, erzeugt daraus HTML, stößt die Trendplot-Erzeugung an und rendert optional das PDF.
- Der PDF-Export soll nicht im breiten Desktop-Layout erfolgen, sondern in einer erzwungenen schmalen `pdf-mobile`-Variante, die dem kleinsten responsiven HTML-Modus entspricht: genau eine Tagesspalte, einspaltige Plotgruppen und insgesamt auf großen Handy-Querformat-Screens gut lesbar.
- Die PDF-Seitenbreite der `pdf-mobile`-Variante bewusst deutlich schmaler als die Desktop-PDF wählen, ungefähr im Bereich eines großen Handy-/kleinen Tablet-Querformats; Richtwert aktuell etwa ein Drittel der bisherigen A3-Landscape-Breite. Die Cards und Plots sollen dabei einfach die verfügbare PDF-Breite ausfüllen.
- In dieser `pdf-mobile`-Variante sollen alle Trendplot-Karten auf eine einheitliche visuelle Höhe gebracht werden; insbesondere darf der Long-Session-Plot dort nicht wegen seines Seitenverhältnisses deutlich höher ausfallen als die übrigen Plots.
- Manuelle direkte Änderungen an `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.html` vermeiden; wenn Darstellungslogik angepasst werden muss, den Renderer oder das CSS ändern.
- Wochenpläne als HTML-Dateien unter `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.html` speichern.
- Nach Fertigstellung des HTML-Wochenplans als letzten Schritt zusätzlich ein PDF `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.pdf` aus genau dieser HTML-Datei erzeugen, sodass PDF und HTML dieselbe Darstellung, dasselbe CSS und dieselben SVG-Plots verwenden.
- Für den PDF-Export nach Möglichkeit Browser-/Print-to-PDF-Rendering der fertigen HTML-Datei verwenden, nicht eine separate manuelle PDF-Nachbildung.
- Wenn kein lokaler Browser, Headless-Renderer oder PDF-Exportwerkzeug verfügbar ist, dies im Chat klar melden; die HTML-Datei bleibt dann die kanonische Darstellung.
- Zusätzlich im Repo-Root eine Datei `trainingplan.html` pflegen, die auf Marios neuesten gerenderten Wochenplan `profiles/Mario/plans/YYYY-Www.html` weiterleitet.
- `scripts/render_plan.py` aktualisiert `trainingplan.html` bei jedem Rendern eines Mario-Plans automatisch auf die höchste vorhandene ISO-Woche. Das LLM darf diese Weiterleitung nicht manuell im Rahmen einer Wochenplanung ändern.
- Wenn ein Plan bewusst für eine andere als die aktuelle ISO-Woche geöffnet werden soll, direkt die konkrete Datei unter `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.html` öffnen.
- Die HTML-Datei soll nur Struktur und Inhalte enthalten. Gemeinsames Styling liegt in `plan-format/training-plan.css`; aus `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.html` wird es relativ mit `../../../plan-format/training-plan.css` eingebunden.
- Jede Wochenplan-HTML soll im `<head>` `assets/calendar.png` als Favicon einbinden; aus `profiles/<TRAINING_PROFILE>/plans/YYYY-Www.html` relativ mit `<link rel="icon" type="image/png" href="../../../assets/calendar.png">`.
- Die Wochenplan-Seite soll die volle Bildschirmbreite nutzen und keine maximale Content-Breite setzen.
- Oben im Wochenplan immer vier Umfangsboxen anzeigen: Gesamtumfang, Swim, Bike, Run.
- Gesamtumfang, Bike und Run in `h:mmh` angeben, z.B. `7:44h`; Swim in Metern, z.B. `3700m`.
- Keine Leerzeichen zwischen Zahlen und Einheiten verwenden, z.B. `60min`, `200W`, `136bpm`, `1700m`, `7:44h`.
- Keine Von-bis-Werte in Trainingsvorgaben verwenden. Immer konkrete Zielwerte angeben, z.B. `60min @200W`, `45min @136bpm`.
- Wenn fachlich ein Zielbereich gemeint ist, im Plan den Mittelwert als konkreten Zielwert schreiben, z.B. statt `295-305W` nur `300W`.
- Keine abstrakten Zonenangaben in Workout-Vorgaben verwenden. Statt `Z2`, `Z3` usw. konkrete Pace-, Power- oder HR-Werte aus `profiles/<TRAINING_PROFILE>/data/zones.md` ableiten.
- Pausen bei Intervallen knapp im gleichen Stil wie Belastungen angeben, z.B. `5min @<Pausenleistung>`; keine erklärenden Zusätze wie `zwischen den Intervallen` verwenden.
- Bei Intervallpausen keine eigene Wiederholungszahl vor die Pause schreiben. Statt `3x16min @300W,2x4min @100W` immer `3x16min @300W,4min @100W` schreiben.
- Bei Swim-Einheiten immer `200m Warmup` und `100m Cooldown` verwenden, sofern nicht ausdrücklich anders gewünscht.
- Die Dauer oder der Umfang einer Einheit steht oben rechts in der Session-Karte, auf gleicher Höhe wie das Sportart-Label.
- Die Dauer oder der Umfang steht nicht im Session-Namen.
- Session-Beschreibungen bewusst knapp halten. Bei einer einfachen Bike-/Run-Einheit reicht eine einzelne Angabe wie `60min @200W`; bei mehreren Schritten eine kurze Liste im gleichen Stil.
- Bei Zugseil-Einheiten keinen zusätzlichen Beschreibungstext verwenden.
- Ruhetage nicht als eigene Session mit `Ruhetag` darstellen; leere Tage bleiben leer.
- Unter oder über dem Trainingsplan genau eine große Analyse-Box `Wochenanalyse` anzeigen, sofern eine Wochenreview nach den Regeln oben erstellt wurde.
- Diese Box ersetzt die getrennten Boxen `Rückblick letzte Woche` und `Intention der Woche`.
- Die Box soll den kanonischen Text aus `profiles/<TRAINING_PROFILE>/data/activities/YYYY-Www/review_YYYY-Www.md` in den Wochenplan übernehmen.
- Die Box soll als Fließtext mit optionalen Absätzen aufgebaut sein und logisch von der Analyse der letzten Woche über die Health- und Load-Einordnung bis zu den Implikationen für die kommende Woche führen.
- Die Box ist nicht nur Rückblick, sondern umfassendes Fazit, Analyse und optionaler Tipp-Block in einem zusammenhängenden Text.
- Die Box soll zugleich ein sinnvoller Startpunkt für spätere Diskussionen mit dem LLM über die kommenden Trainingswochen sein.
- Die Box soll die Race-Ausrichtung nennen, z.B. langfristig ist die Planung auf das wichtigste anstehende Race aus `profiles/<TRAINING_PROFILE>/data/races.md` ausgelegt, aber einzelne Sessions können kurzfristig auf ein weniger priorisiertes Race spezifizieren.
- In dieser großen Analyse-Box knapp erwähnen, wenn Health-Werte die Planungsentscheidung relevant beeinflusst haben, z.B. konservativer Einstieg wegen niedriger HRV/schlechtem Schlaf oder normale Progression bei unauffälligem Health-Kontext.
- Die Box soll verständlich machen, worauf die Woche abzielt und warum die wichtigsten Sessions so gewählt wurden, ohne allgemeine Trainingslehre auszubreiten.
- Wenn `scripts/generate_trend_plots.py` existiert, nach jeder Wochenplan-Erzeugung die Trendplots für die Planwoche erzeugen und in den HTML-Wochenplan einbinden, bevorzugt mit `python scripts/generate_trend_plots.py --week YYYY-Www --newest YYYY-MM-DD --update-html`.
- Trendplots als statische SVG-Dateien unter `profiles/<TRAINING_PROFILE>/plans/assets/YYYY-Www/` speichern; die HTML-Datei bindet sie relativ mit `assets/YYYY-Www/<datei>.svg` ein.
- Für Trendplots ausschließlich kanonische Markdown-Historien aus `profiles/<TRAINING_PROFILE>/data/health/`, `profiles/<TRAINING_PROFILE>/data/thresholds/` und `profiles/<TRAINING_PROFILE>/data/VO2max/` verwenden; technische Cache-Dateien sind keine Plotquelle.
- Die Plotsektion im Wochenplan heißt `Trends`, steht unter der großen Box `Wochenanalyse` und zeigt die Plotgruppen in dieser Reihenfolge: Performance, Belastung, Readiness, Alltag.
- Zwischen die oberen vier bestehenden Plots (Performance und Belastung) und die unteren vier bestehenden Plots (Readiness und Alltag) vier zusätzliche Trainingsplots einfügen.
- Diese vier zusätzlichen Trainingsplots stehen als eigener Mittelblock zwischen oberer und unterer Plotsektion.
- Plot 1 links oben im Mittelblock: `Wochenumfang pro Sportart (12 Wochen)` als gestapelte Balken, Swim unten blau, Bike mittig grün, Run oben rot.
- Plot 2 rechts oben im Mittelblock: `Wochen-TSS pro Sportart (12 Wochen)` als gestapelte Balken im gleichen Farbschema.
- Die 12-Wochen-Plots sollen auf den letzten `12` abgeschlossenen Wochen basieren und nicht mit einer noch laufenden, unvollständigen aktuellen Woche enden.
- Plot 3 links unten im Mittelblock mit ungefähr `3/4` der Breite: `Zeit in Zonen pro Woche und Sportart (letzte Woche)` als eine gemeinsame Card mit drei Teilplots für Swim, Bike und Run.
- Im Zonenplot Swim als Distanz pro Zone darstellen, Bike und Run als Zeit pro Zone.
- Die Teilplot-Überschriften im Zonenplot sollen explizit lauten: `Swim nach Pace`, `Bike nach Power`, `Run nach GAP`.
- Im Zonenplot über jedem Balken zusätzlich den absoluten Wert und darunter den Prozentanteil der Vorwochen-Gesamtsumme dieser Sportart anzeigen, z.B. `3:23h` und darunter `23%`; bei Swim den absoluten Wert als Distanz in `m` schreiben.
- Die Zonenhistogramme in abgestuften Sportfarben darstellen: Swim in ruhigen bis kräftigen Blautönen, Bike in ruhigen bis kräftigen Grüntönen, Run in ruhigen bis kräftigen Rottönen; höhere Zonen jeweils kräftiger.
- Plot 4 rechts unten im Mittelblock mit ungefähr `1/4` der Breite: `Long Sessions (12 Wochen)` mit längster Bike-Session und längster Run-Session je Woche; Bike grün, Run rot.
- Für den Long-Session-Plot zwei Y-Achsen verwenden, eine für Bike und eine für Run.
- Der Long-Session-Plot soll trotz schmalerer Card dieselbe visuelle Höhe, Schriftgröße, Punktgröße und allgemeine Lesbarkeit wie die übrigen Plots behalten; dafür die SVG intrinsisch schmäler rendern statt sie nur im HTML kleiner zu skalieren.
- Wenn der Long-Session-Plot gegenüber dem linken Nachbarplot noch minimal zu niedrig wirkt, die intrinsische SVG-Höhe weiter erhöhen statt die Schrift künstlich zu skalieren; Ziel ist gleiche visuelle Höhe bei schmalerer Breite.
- Die Trendsektion als zweispaltiges Dashboard anordnen: oben links `Performance (12 Monate)`, oben rechts `Belastung (90 Tage)`, darunter links `Readiness (90 Tage)` und darunter rechts `Alltag (90 Tage)`.
- Innerhalb jeder Plotgruppe die zugehörigen Plot-Cards vertikal untereinander anordnen, nicht nebeneinander.
- Die vier Plotgruppen im zweispaltigen Dashboard bündig als sauberes `2x2`-Grid ausrichten; Gruppen dürfen nicht durch abweichende Top-Margins gegeneinander vertikal versetzt sein.
- Die Zeitdauer der Plotgruppen in die Gruppenüberschrift schreiben, z.B. `Alltag (90 Tage)`.
- Plotgruppen mit gleicher Zeitdauer direkt untereinander bzw. nebeneinander mit identischer X-Achse darstellen.
- Die Zeitdauer nur in den Plotgruppen-Überschriften anzeigen, z.B. `Alltag (90 Tage)`, nicht in den einzelnen SVG-/Card-Titeln; eine Card heißt z.B. nur `Gewicht`, nicht `Gewicht (90 Tage)`.
- In den SVG-Plots rechts oben kompakte Legenden platzieren.
- Plot-SVGs ausreichend hoch und gut lesbar gestalten; Schriftgrößen so wählen, dass die Werte im HTML-Plan ohne Zoomen erkennbar bleiben.
- Legenden so platzieren, dass Marker und Beschriftung nicht überlappen. Zwischen Marker und zugehöriger Beschriftung einen klaren Abstand lassen; der Abstand zwischen zwei verschiedenen Legendeneinträgen soll deutlich größer sein als der Abstand zwischen Marker und Beschriftung.
- Readiness über 90Tage plotten: HRV mit Tages-RMSSD als dezente graue Punkte mit sehr dünner grauer Verbindungslinie, 7-Tage-RMSSD als Linie und 90-Tage-Korridor als hellgrünes Band.
- Die HRV-7-Tage-Linie grün zeichnen, wenn sie innerhalb des HRV-Korridors liegt, und orange, wenn sie außerhalb des Korridors liegt.
- Ruhepuls zusammen mit Schlafdauer und Sleepscore in einem Plot mit mehreren kompakten Y-Skalen darstellen; Schlafdauer mit `0` als Minimalwert plotten und Ruhepuls so skalieren, dass er im unteren Drittel bleibt und Schlaf/Sleepscore gut lesbar bleiben.
- Schlafdauer-Balken mit einem vertikalen Verlauf zeichnen: oben kräftiger, nach unten zur X-Achse transparenter, unten ungefähr `20%` Opacity.
- Belastung über 90Tage plotten: Tages-TSS als sehr dünne Balken und ATL/CTL als Linien in einem Plot; zusätzlich einen dezenten grünen CTL-Korridor von `80%` bis `140%` der CTL-Linie darstellen.
- Die Y-Achse im Load-Plot immer bei `0` starten lassen.
- TSB über 90Tage direkt darunter bzw. daneben in einem zweiten Plot mit gleicher X-Achse darstellen; ACR nicht im Plot anzeigen. TSB invertiert plotten, sodass negativere Werte oben liegen.
- TSB-Linie und TSB-Punkte schwarz zeichnen.
- Im Balance-Plot TSB-Hintergrundzonen darstellen: `-10 bis -30` als hellgrüner Formaufbau-Korridor, `< -30` als dezenter Risikobereich, `-10 bis +10` als neutraler Bereich, `+10 bis +25` als dezenter `Race Ready`-Bereich und `> +25` als Bereich für möglichen Fitnessverlust.
- Weil TSB invertiert geplottet wird, müssen die Hintergrundzonen ebenfalls invertiert positioniert werden: negativer TSB liegt im Plot weiter oben.
- Körper/Alltag für Gewicht, Körperfett und Schritte über 90Tage plotten.
- Im Gewichtsplot Gewicht und Körperfett in einem gemeinsamen Chart mit getrennter vertikaler Signalfläche und getrennten Skalen darstellen: Gewicht in der oberen Charthälfte, Körperfett in der unteren Charthälfte.
- Im Gewichtsplot die vier sichtbaren Y-Achsen-Minimum-/Maximum-Labels für Gewicht und Körperfett alle links anzeigen, nicht zwischen linker und rechter Seite aufteilen.
- Gewicht im Plot nicht bei `0` starten lassen, sondern dynamisch auf den sichtbaren 90-Tage-Wertebereich mit Padding skalieren.
- Gewicht als helle graublaue Tagesbalken im Hintergrund zeichnen, die nach unten über die gesamte Charthöhe transparenter/heller ausfaden; die eigentlichen Gewichtswerte und die Gewichtslinie müssen in der oberen Charthälfte liegen.
- Körperfett im Gewichtsplot als hellrote Tagesbalken in der unteren Charthälfte mit eigener Körperfett-Skala zeichnen; fehlende Tageswerte nicht zeichnen und niemals als `0` darstellen.
- Im Gewichtsplot zusätzlich zwei 7-Tage-Mittel-Linien zeichnen: Gesamtgewicht als dunkle Linie und Körperfett als dunklere rote Linie; beide im gleichen visuellen Stil mit Linie und Punkten wie die bisherige Gewichts-Mittellinie.
- Im Gewichtsplot die aktuellsten 7-Tage-Mittelwerte rechts innerhalb der Card anzeigen, analog zu Threshold/VO2max/Load/Balance: Gewicht in `kg` in der Gewichtslinienfarbe und Körperfett in `%` in der Körperfett-Linienfarbe; beide Werte mit `2` Nachkommastellen anzeigen.
- Im Gewichtsplot in der Legende nur die beiden 7-Tage-Mittelwert-Linien benennen; Tageswert-Balken nicht zusätzlich als Zahlen oder Legendeneinträge ausweisen.
- Wenn `profiles/<TRAINING_PROFILE>/data/health/calories.md` existiert, im Alltag-Block statt des Schritte-Plots einen Kalorien-Plot über 90Tage anzeigen. Ruhe-Kalorien als hellorange unteren Balken und Aktiv-Kalorien als dunkelorange oben gestapelt plotten; die Y-Achse startet immer bei `0`.
- Im Kalorien-Plot rechts zwei Mittelwerte anzeigen: durchschnittliche Aktiv-Kalorien und durchschnittliche Gesamt-Kalorien über die im sichtbaren 90-Tage-Zeitraum vorhandenen Kalorientage, jeweils als `∅ XXXXkcal`.
- Wenn `profiles/<TRAINING_PROFILE>/data/health/calories.md` nicht existiert, Schritte im gleichen visuellen Stil als Tageswert-Balken plus 7-Tage-Mittel-Linie über 90Tage und mit `0` als Minimalwert plotten.
- Performance über 12Monate plotten: Thresholds in einem gemeinsamen Plot, Swim CSS blau, Bike FTP grün und Run LT dunkelrot; Run-HR-Threshold nicht im Trendplot darstellen.
- Für Load, Balance, Threshold und VO2max die aktuellsten Werte rechts außerhalb der inneren Plotfläche, aber innerhalb der äußeren SVG-Karte anzeigen; diese Endwerte ohne Präfixe wie `ATL`, `CTL` oder `TSB` schreiben.
- Bei Load und Balance die rechte Endwertspalte schmal halten, weil dort nur kurze maximal dreistellige Zahlen ohne Einheit stehen; Threshold- und VO2max-Plots dürfen mehr rechten Platz für längere Labels behalten.
- Den tagesaktuellen Tages-TSS-Wert nicht als Endwert anzeigen; Tages-TSS bleibt nur als dünner Balken und Legendenreihe sichtbar.
- Plots ohne aktuelle Endwerte sollen die innere Plotfläche nach rechts deutlich weiter ausnutzen.
- VO2max über 12Monate in einem gemeinsamen Plot darstellen, Bike grün und Run rot.
- Wenn Plotdaten fehlen, sehr dünn sind oder Spaltennamen nicht erkannt werden, dies im Chat als technische Plausibilitätswarnung nennen und nicht in Wochenreview oder Wochenanalyse schreiben.
- Die Plotdarstellung soll modern, schlicht und ruhig sein, ähnlich Apple-Health/Apple-Fitness: helle Flächen, dezente Raster, klare Linien, keine dekorativen Effekte.
- Keine weiteren erklärenden Hinweisboxen, Steuerungsboxen oder Kontextboxen im Wochenplan anzeigen, außer der Nutzer fragt ausdrücklich danach.
