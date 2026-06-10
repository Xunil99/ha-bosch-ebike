# Design: Reichweiten-Schätzungs-Sensoren (Estimated Range)

**Datum:** 2026-06-10
**Status:** Genehmigt (User-Review am 2026-06-10)

## Ziel

Zwei neue Sensoren pro Bike, die die Reichweite aus den bisherigen Verbräuchen
(Wh pro Tour) und Distanzen schätzen. Die Werte müssen klar als **Schätzung**
gekennzeichnet sein (Name, Disclaimer-Attribut, README).

## Entscheidungen (mit User abgestimmt)

1. **Beide Varianten:** „voller Akku" (rein Cloud, immer verfügbar) und
   „aktuell" (benötigt Live-SoC-Sensor der ESPHome-Bridge).
2. **Verbrauchsfenster: letzte ~500 km**, distanzgewichtet.

## Berechnung (Coordinator, pro Bike)

- Touren des Bikes rückwärts ab der neuesten durchgehen.
- Nur Touren mit gültigem Verbrauchseintrag zählen:
  `consumed_wh > 0` und `distance_km > 0.5`.
- Aufsummieren, bis Σ Distanz ≥ 500 km (die Tour, die die Schwelle
  überschreitet, wird noch voll mitgenommen).
- `wh_per_km = Σ consumed_wh / Σ distance_km` (distanzgewichtet).
- **Mindest-Datenbasis:** ≥ 3 Touren und ≥ 30 km im Fenster,
  sonst kein Ergebnis (Sensor `unknown`).
- Ergebnis pro Bike in `coordinator.data["range_estimate"][bike_id]`:
  `{wh_per_km, tours_used, window_km, newest_tour_date}`.
- Berechnung einmal pro Poll (30 min) — kein zusätzlicher API-Call,
  alles aus vorhandenen Daten (`activity_consumption`, Aktivitätsliste,
  Tour-zu-Bike-Heuristik).

## Sensoren (sensor.py, englische Namen wie Bestand)

| Sensor | Wert | Verfügbarkeit |
|---|---|---|
| `Estimated Range (Full Battery)` | `battery_capacity_wh / wh_per_km` → km | immer (sobald Datenbasis reicht) |
| `Estimated Range (Current)` | `soc% × battery_capacity_wh / wh_per_km` → km | nur wenn `live_soc_entity` in den Optionen gesetzt |

- `device_class: distance`, Einheit `km`, `state_class: measurement`,
  Icon `mdi:map-marker-distance`, Werte auf ganze km gerundet.
- **Current-Sensor:** lauscht per `async_track_state_change_event` auf den
  SoC-Sensor und aktualisiert sofort (nicht erst beim Poll). SoC nicht
  verfügbar / nicht numerisch → `unknown`.

## Kennzeichnung als Schätzung

- Name beginnt mit **„Estimated"**.
- Attribute beider Sensoren: `disclaimer` (lokalisierter Text: Schätzung auf
  Basis des bisherigen Verbrauchs; tatsächliche Reichweite hängt von Modus,
  Topografie, Wind, Temperatur ab), `wh_per_km`, `tours_used`, `window_km`,
  `newest_tour_date`, `battery_capacity_wh`.
- README-Abschnitt in allen 6 Sprachen mit ausdrücklichem Hinweis.

## Randfälle

- Kapazitätsänderung (`set_battery_capacity`) fließt beim nächsten
  Berechnen automatisch ein.
- Touren ohne Verbrauchsdaten werden übersprungen; das Fenster greift
  entsprechend weiter zurück.
- Mehrere Bikes pro Konto: Zuordnung über bestehende Heuristik
  (`startOdometer + distance` vs. Bike-Odometer).
- Neue Installationen ohne Historie: Sensoren bleiben `unknown`,
  kein Fehler.

## Bewusst nicht enthalten (YAGNI)

- Keine Steigungs-/Wetter-/Temperatur-Korrektur.
- Keine Differenzierung nach Unterstützungsmodus (liefert die API nicht).
- Kein konfigurierbares Fenster (fest 500 km; kann später Option werden).

## Test/Verifikation

- Repo hat kein Test-Framework → Verifikation auf der HA-Instanz des
  Maintainers: Werte gegen Bosch-Flow-App-Reichweite plausibilisieren,
  Verhalten bei fehlendem SoC-Sensor und frischer Installation prüfen.
