# AGENTS.md

Dieses Repo ist der zentrale Trainingskontext für meine Triathlonplanung.

Vor jeder Trainingsplanung oder Trainingsbewertung zuerst:
- data/current-state.md
- data/athlete-profile.md
- data/goals.md
- data/races.md
- data/availability.md
- data/thresholds.md
- data/zones.md, falls vorhanden
- relevante neueste health-, activity- und injury-logs
- noch nicht ausgewertete FIT-Dateien in `data/activities/`
- Zonen in data/zones.md mithilfe der aktuellsten Thresholds aus data/thresholds.md neu berechnen mit den gegebenen Grenzen. Benutze für Bike-HR-Threshold den Wert für die Run-HR-Threshold minus 5.

Regeln:
- data/current-state.md ist die einzige Quelle für den aktuellen Zustand.
- Vor jeder Trainingsplanung oder Trainingsbewertung die neuesten Einträge in `data/current-state.md` prüfen und daraus die `Aktuelle Zusammenfassung` in derselben Datei aktualisieren.
- Die `Aktuelle Zusammenfassung` in `data/current-state.md` als kurze Stichpunktliste pflegen, nicht als Tabelle.
- Jeder Stichpunkt in der `Aktuelle Zusammenfassung` soll eine aktuell gültige Aussage enthalten, idealerweise mit Datum oder Zeitraum, wenn die Aussage zeitabhängig ist.
- In `data/current-state.md` stehen unter `Neueste Updates` chronologische Roh-Updates des Athleten. Diese Updates nicht löschen.
- Bei Widersprüchen zwischen alten Updates und der `Aktuelle Zusammenfassung` gilt die `Aktuelle Zusammenfassung`.
- Historische Dateien nie als aktuellen Zustand interpretieren, außer sie werden ausdrücklich als aktuell referenziert.
- Wenn ein neuer Plan für dieselbe ISO-Woche erzeugt wird, die bestehende Datei `plans/YYYY-Www.html` ersatzlos überschreiben.
- Pläne anderer ISO-Wochen nicht überschreiben, außer der Nutzer verlangt es ausdrücklich.
- Vor jeder Trainingsplan-Erzeugung alle noch nicht ausgewerteten `.fit`-Dateien unter `data/activities/` auswerten.
- Eine `.fit`-Datei gilt als noch nicht ausgewertet, wenn keine gleichnamige `.md`-Datei daneben existiert oder wenn die `.fit`-Datei neuer ist als die `.md`-Auswertung.
- FIT-Auswertungen als gleichnamige Markdown-Dateien neben der FIT-Datei speichern und knapp zusammenfassen: Kurzfassung, Einordnung, relevante Laps/Intervalle.
- Bei Müdigkeit, Verletzung, schlechtem Schlaf, auffälliger HRV oder ungewöhnlich hohem Ruhepuls konservativ planen.
- Health-Daten werden nicht regelmäßig automatisiert bereitgestellt. Nur außergewöhnliche Health-, Müdigkeits- oder Beschwerdewerte aus `data/current-state.md` berücksichtigen.
- Unsicherheiten und fehlende Daten explizit nennen.
- Datumsformat: YYYY-MM-DD.
- Wochenformat: ISO-Woche, z.B. 2026-W23.

Session-Typen und Trainingslogik:
- Swim-Session-Typen: `Aerobic Short`, `Aerobic Long`, `Threshold`, `VO2max`.
- Bei Swim-Einheiten am Anfang standardmäßig `10 x 50m Technik` einplanen; das genügt als Technikanteil.
- Bike-Session-Typen: `Long`, `Basic`, `Tempo`, `Threshold`, `VO2max`, `Anaerobic`.
- Run-Session-Typen: `Long`, `Basic`, `Tempo`, `Threshold`, `VO2max`, `Anaerobic`, optional kurze `Run off Bike` Sessions mit konkreter Pace.
- Pro Woche und Sportart maximal eine Intervall-Session planen, z.B. maximal ein Bike-Intervall und maximal ein Run-Intervall.
- Als Intervall-Session zählen ausschließlich `Tempo`, `Threshold`, `VO2max` und `Anaerobic`.
- `Long` und `Basic` sind keine Intervall-Sessions.
- Bei Bike und Run keine generische Session-Art `Intervalle` verwenden; immer den konkreten Intervall-Typ benennen. Im fertigen Plan heißen diese Sessions nur `Tempo`, `Threshold`, `VO2max` oder `Anaerobic`, ohne den Zusatz `-Intervall`.
- Die hauptsächliche Planung soll auf den genannten Session-Typen beruhen. Falls trainingslogisch nötig, dürfen vereinzelt weitere Session-Typen genutzt werden.
- Die Wochenstruktur aus `data/availability.md` unter `Standard Woche` ist die dauerhafte Standardstruktur für Wochenpläne.
- Die Wochenstruktur soll grundsätzlich stabil bleiben: gleiche Session-Arten an gleichen Wochentagen planen, sofern Zustand, Rennen oder Verfügbarkeit nicht dagegen sprechen.
- Inhalte, Intervallformate, Zielwerte und Umfänge selbstständig festlegen und progressiv entwickeln.
- Intervall-Einheiten zu Beginn eines Aufbaus eher kurz und hart planen; in Richtung Race eher länger und race-specific planen.
- Bei Intervall-Workouts standardmäßig `5min Warmup` und `2min Cooldown` verwenden, sofern nicht ausdrücklich anders gewünscht.
- Bei Run-Intervallen standardmäßig eine `Trabpause` zwischen den aktiven Phasen verwenden, z.B. `8 x 2min @3:45/km,2min Trabpause`.
- Bei Bike-Intervallen die Pausen standardmäßig mit `100W` ansetzen, z.B. `8 x 2min @336W,1min @100W`.
- Von diesen Pausenstandards darf in besonderen Fällen abgewichen werden; jede Abweichung im Chat explizit nennen und begründen.
- Long Bike normal ungefähr `2:30h-4:00h` planen; in den letzten spezifischen Wochen vor dem wichtigsten Race gezielt bis maximal `5:00h`.
- Long Run normal ungefähr `1:15h-1:50h` planen; in den letzten spezifischen Wochen vor dem wichtigsten Race gezielt bis maximal `2:15h`.
- Die Long-Session-Maximalwerte sind Obergrenzen, keine wöchentlichen Zielwerte.
- Keine formalen Trainingsphasen erzwingen. Trainingsentscheidungen aus Zielen, Race-Kalender, aktueller Belastbarkeit und Standard-Wochenstruktur ableiten.
- Die Ausrichtung der Sessions nach der Wichtigkeit der Rennen in `data/races.md` gewichten.
- Das geplante Rennen mit der höchsten Wichtigkeit in `data/races.md` dynamisch als aktuelles Hauptrennen bestimmen; dieses Hauptrennen dominiert die langfristige Trainingsausrichtung.
- Kurz vor weniger priorisierten Rennen dürfen einzelne spezifische Sessions für diese Rennen geplant werden, solange sie die langfristige Ausrichtung auf das wichtigste Rennen nicht unverhältnismäßig stören.
- Beim Generieren neuer Pläne primär an die bestehenden Vorgaben halten.
- Wenn Vorgaben aus Trainingssicht nicht optimal sind, inkonsistent wirken oder eine Anpassung sinnvoll wäre, dies klar im Chatfenster kommunizieren und nicht stillschweigend ändern.
- Von Standardvorgaben darf abgewichen werden, wenn Zustand, Race-Nähe, Trainingslogik oder Inkonsistenzen es klar rechtfertigen.
- Jede Abweichung von Standardwoche, Verfügbarkeit, Session-Typen oder Formatvorgaben im Chat explizit nennen und begründen.
- Beispiele für klar zu kommunizierende Hinweise: mehr Schwimmeinheiten wären sinnvoll als die aktuelle Verfügbarkeit erlaubt; die Standardwoche sollte geändert werden; Brick Sessions wären sinnvoll; Vorgaben widersprechen sich; die langfristige Race-Ausrichtung passt nicht zur aktuellen Wochenstruktur.

Wochenreview:
- Vor jeder neuen Wochenplan-Erzeugung eine kurze Bewertung der letzten abgeschlossenen Trainingswoche erstellen.
- Die kanonische Bewertung unter `data/weekly-reviews/YYYY-Www.md` speichern.
- Der Dateiname der Wochenreview bezeichnet die bewertete ISO-Woche: `data/weekly-reviews/2026-W23.md` ist die Review für Woche 23.
- Die Review einer abgeschlossenen Woche soll im Plan der folgenden Woche erscheinen, z.B. `data/weekly-reviews/2026-W23.md` im Plan `plans/2026-W24.html`.
- Im HTML-Wochenplan eine kurze Box `Rückblick letzte Woche` anzeigen, die diese Bewertung knapp zusammenfasst.
- Für die Wochenreview primär die FIT-Auswertungen und Aktivitätsnotizen der letzten abgeschlossenen ISO-Woche bzw. der letzten 7 Tage verwenden.
- Als Grundlage für die Wochenreview `data/current-state.md`, FIT-Auswertungen, Aktivitätsnotizen, den Vorwochenplan, `data/goals.md` und `data/races.md` heranziehen.
- Ältere FIT-Auswertungen und Aktivitätsnotizen nur berücksichtigen, wenn sie für den aktuellen Zustand, erkennbare Trends oder die Zielbewertung noch relevant sind.
- Nicht alle historischen FIT-Dateien jedes Mal gleich stark gewichten; alte Aktivitäten sind Historie, nicht automatisch aktueller Zustand.
- Wenn ein Plan der Vorwoche existiert, einen kurzen Abgleich `geplant vs. absolviert` aufnehmen, ohne daraus eine lange Kontrollliste zu machen.
- Die Bewertung soll ungefähr 10 Sätze lang sein; wenn trainingslogisch nötig, darf sie etwas länger sein.
- Kurz auf einzelne Sessions eingehen, wenn sie besonders gut, besonders schlecht oder trainingslogisch auffällig waren.
- Daraus kurz ableiten, wie die aktuelle Form in den Sportarten Swim, Bike und Run momentan ist und ob diese in Einklang mit den Zielen in `data/goals.md` steht.
- Die Wochenreview soll beurteilen, ob der Athlet auf gutem Kurs für die Ziele aus `data/goals.md` und die Rennen aus `data/races.md` ist.
- Dabei getrennt auf kurzfristige, weniger wichtige Rennen und langfristige, wichtigere Ziele eingehen.
- Besonders das realistische Erreichen der Ziele beurteilen, z.B. Qualifikation, Leistungsaufbau, Rennspezifik und verbleibende Zeit.
- Eine kurze Konsequenz für die aktuelle Planwoche nennen, z.B. Umfang steigern, Intensität begrenzen, spezifischen Reiz setzen oder konservativ bleiben.
- Datenlücken wie fehlende Schlaf-, HRV- oder Müdigkeitsdaten nur dann erwähnen, wenn sie die Aussagekraft der Bewertung relevant begrenzen.

Wochenplan-Format:
- Wochenpläne als HTML-Dateien unter `plans/YYYY-Www.html` speichern.
- Zusätzlich im Repo-Root eine Datei `trainingplan.html` pflegen, die immer auf den aktuellsten Wochenplan verweist.
- Nach jeder Wochenplan-Erzeugung `trainingplan.html` ersatzlos aktualisieren, sodass sie auf die neu erzeugte bzw. aktuelle `plans/YYYY-Www.html` weiterleitet.
- Die HTML-Datei soll nur Struktur und Inhalte enthalten. Gemeinsames Styling liegt in `plans/training-plan.css`.
- Jede Wochenplan-HTML soll im `<head>` `assets/calendar.png` als Favicon einbinden; aus `plans/YYYY-Www.html` relativ mit `<link rel="icon" type="image/png" href="../assets/calendar.png">`.
- Die Wochenplan-Seite soll die volle Bildschirmbreite nutzen und keine maximale Content-Breite setzen.
- Oben im Wochenplan immer vier Umfangsboxen anzeigen: Gesamtumfang, Swim, Bike, Run.
- Gesamtumfang, Bike und Run in `h:mmh` angeben, z.B. `7:44h`; Swim in Metern, z.B. `3700m`.
- Keine Leerzeichen zwischen Zahlen und Einheiten verwenden, z.B. `60min`, `200W`, `136bpm`, `1700m`, `7:44h`.
- Keine Von-bis-Werte in Trainingsvorgaben verwenden. Immer konkrete Zielwerte angeben, z.B. `60min @200W`, `45min @136bpm`.
- Keine abstrakten Zonenangaben in Workout-Vorgaben verwenden. Statt `Z2`, `Z3` usw. konkrete Pace-, Power- oder HR-Werte aus `data/zones.md` ableiten.
- Bei Swim-Einheiten immer `200m Warmup` und `100m Cooldown` verwenden, sofern nicht ausdrücklich anders gewünscht.
- Die Dauer oder der Umfang einer Einheit steht oben rechts in der Session-Karte, auf gleicher Höhe wie das Sportart-Label.
- Die Dauer oder der Umfang steht nicht im Session-Namen.
- Session-Beschreibungen bewusst knapp halten. Bei einer einfachen Bike-/Run-Einheit reicht eine einzelne Angabe wie `60min @200W`; bei mehreren Schritten eine kurze Liste im gleichen Stil.
- Bei Zugseil-Einheiten keinen zusätzlichen Beschreibungstext verwenden.
- Ruhetage nicht als eigene Session mit `Ruhetag` darstellen; leere Tage bleiben leer.
- Unter oder über dem Trainingsplan eine kurze Review-Box `Rückblick letzte Woche` anzeigen, sofern eine Wochenreview nach den Regeln oben erstellt wurde.
- Unter dem Trainingsplan eine kurze Erklärungsbox anzeigen, die beschreibt, worauf die Woche abzielt und warum die wichtigsten Sessions so gewählt wurden.
- Die Erklärungsbox soll die Race-Ausrichtung nennen, z.B. langfristig ist die Planung auf das wichtigste anstehende Race (Ironman am `2027-05-01`) ausgelegt (daher die Sessions X1 und X2), aber für die Spezifizierung auf das weniger priorisierte Race wurden Session (Y1 und Y2) erstellt. Damit ist ein guter Mix aus Vorbereitung auf ein weniger wichtiges akutes Race und das langfristige Ziel im Hinterkopf gewährleistet.
- Die Erklärungsbox soll knapp bleiben und die Intention der Planung verständlich machen, ohne allgemeine Trainingslehre auszubreiten.
- Keine weiteren erklärenden Hinweisboxen, Steuerungsboxen oder Kontextboxen im Wochenplan anzeigen, außer der Nutzer fragt ausdrücklich danach.
