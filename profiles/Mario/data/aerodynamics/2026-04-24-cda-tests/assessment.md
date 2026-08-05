# CdA-Auswertung Canyon Speedmax CFR

Stand der Messdaten: 2026-04-24

## Aktuelles Setup

- Fahrrad: Canyon Speedmax CFR
- Unterarmwinkel: 24°
- Das Setup ist Marios aktuell und künftig verwendete Position.

## Modellannahmen

| Parameter | Wert |
|-|-|
| Fahrer inklusive Kleidung | 82,7kg |
| Fahrrad | 13,0kg |
| Gesamtmasse | 95,7kg |
| Temperatur | 18°C |
| Relative Luftfeuchtigkeit | 30% |
| Luftdruck | 1.023hPa |
| Luftdichte | 1,22126kg/m³ |
| Antriebswirkungsgrad | 0,975 ± 0,005 |

Das Modell schätzt Rollwiderstandskoeffizient und CdA gemeinsam aus sechs Leistungs-Geschwindigkeits-Punkten. Die Unsicherheiten von Geschwindigkeit, Leistung und Antriebswirkungsgrad werden mit 4.000 Monte-Carlo-Durchläufen berücksichtigt.

## Ergebnis

| Kennzahl | Wert |
|-|-|
| CdA | 0,2138m² |
| 68%-Unsicherheit CdA | 0,2019 bis 0,2256m² |
| Crr | 0,00576 |
| 68%-Unsicherheit Crr | 0,00489 bis 0,00662 |
| Reduziertes Chi-Quadrat | 0,493 |
| Modellierte Leistung bei 40km/h | 245,3W |
| Modellierte Geschwindigkeit bei 230W | 38,98km/h |

## Bewertung

Ein CdA um 0,213m² ist für einen 192cm großen Fahrer mit Race-Cockpit sehr gut. Die Position ist aerodynamisch grundsätzlich für schnelle Mittel- und Langdistanzrennen geeignet.

Der Wert ist eine testspezifische Schätzung und kein universeller Outdoor-CdA. Die Unsicherheit ist relativ groß, weil Crr und CdA aus nur sechs Punkten derselben Messreihe gleichzeitig bestimmt werden. Der zentrale Wert eignet sich als Ausgangsbasis für künftige Tests, nicht als millimetergenaue absolute Wahrheit.

Für die Wettkampfleistung ist jetzt wichtiger, wie lange die Position ohne Leistungs-, Komfort- oder Kontrollverlust gehalten werden kann. Der nächste relevante Nachweis ist daher eine zwei- bis fünfstündige Fahrt mit hoher Zeit in Aeroposition, stabiler Leistung, dokumentiertem Fueling und anschließendem Brick Run.

## Grenzen der Messung

- Pro Geschwindigkeitsstufe liegt im verwendeten Datensatz nur ein bidirektional zusammengefasster Messwert vor.
- Wind, Böen, minimaler Gradient, Verkehr, Linienwahl, Reifendruck und Positionsstabilität werden nicht separat modelliert.
- Das Modell setzt Luftgeschwindigkeit im Wesentlichen mit Fahrgeschwindigkeit gleich.
- Der absolute CdA hängt von den Annahmen für Crr, Gesamtmasse, Luftdichte und Antriebswirkungsgrad ab.
- Die ursprüngliche Cockpitaufnahme ist nicht erforderlich, um die kanonischen Messdaten oder den Fit zu reproduzieren, und wird deshalb nicht im Profil gespeichert.

## Kanonische Dateien

- `data.dat`: verwendete Messdaten
- `fit_cda.py`: reproduzierbarer Fit mit Unsicherheitsrechnung
- `assessment.md`: Annahmen, Ergebnis und Einordnung
