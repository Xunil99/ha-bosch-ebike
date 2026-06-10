# Estimated-Range-Sensoren — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Zwei pro-Bike-Sensoren „Estimated Range (Full Battery)" und „Estimated Range (Current)", berechnet aus dem distanzgewichteten Ø-Verbrauch (Wh/km) der letzten ~500 km, klar als Schätzung gekennzeichnet.

**Architecture:** Reine Berechnungsfunktion in neuem Modul `range_estimate.py` (ohne HA-Imports, standalone testbar). Der Coordinator ruft sie einmal pro Poll auf und legt das Ergebnis pro Bike in `coordinator.data["range_estimate"]`. Zwei neue Sensor-Klassen in `sensor.py`; der Current-Sensor lauscht zusätzlich per State-Listener auf den Live-SoC-Sensor aus den Optionen.

**Tech Stack:** Home Assistant Custom Integration (Python 3.13+), DataUpdateCoordinator, CoordinatorEntity. Kein pytest im Repo → Plain-Assert-Testskript via `python3`.

**Design-Doc:** `docs/plans/2026-06-10-range-estimate-design.md`

**Repo:** `/tmp/hbcl` — Commits mit `git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe"`, NIEMALS Co-Author. NICHT pushen — Push + Release erst nach User-Freigabe (Task 8).

---

## Vorhandene Datenstrukturen (Referenz)

- `coordinator.data["all_activities"]`: Liste, neueste zuerst. Pro Activity: `id`, `distance` (**Meter!**), `startTime` (ISO-String), `startOdometer`.
- `coordinator.data["activity_consumption"]`: `{activity_id: {"consumed_wh": float, "percentage": float, "capacity_wh": float, "is_exact": bool}}`
- `coordinator.data["activity_bike"]`: `{activity_id: bike_id}` (Single-Bike-Konten: alle Activities gemappt)
- `coordinator.data["battery_capacity_wh"]`: float (Default 750)
- Optionen: `entry.options.get(CONF_LIVE_SOC_ENTITY)` (const: `live_soc_entity`)
- Sensor-Pattern: `CoordinatorEntity`, `_attr_has_entity_name = True`, `unique_id = f"{bike_id}_{key}"`, `DeviceInfo(identifiers={(DOMAIN, bike_id)}, ...)` — siehe `BoschBatteryConsumptionSensor` (sensor.py:678).

---

### Task 1: Reine Berechnungsfunktion (TDD)

**Files:**
- Create: `tests/test_range_estimate.py`
- Create: `custom_components/bosch_ebike/range_estimate.py`

**Step 1: Failing Test schreiben**

`tests/test_range_estimate.py` (Plain-Asserts, kein pytest nötig):

```python
"""Standalone tests for range_estimate.py — run with: python3 tests/test_range_estimate.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.bosch_ebike.range_estimate import compute_range_estimate


def act(aid, km, start="2026-06-01T10:00:00Z"):
    return {"id": aid, "distance": km * 1000, "startTime": start}


def test_happy_path():
    # 5 Touren à 20 km à 100 Wh -> 5 Wh/km
    activities = [act(f"a{i}", 20) for i in range(5)]
    bike_map = {f"a{i}": "bike1" for i in range(5)}
    cons = {f"a{i}": {"consumed_wh": 100.0} for i in range(5)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r is not None
    assert abs(r["wh_per_km"] - 5.0) < 0.001, r
    assert r["tours_used"] == 5
    assert abs(r["window_km"] - 100.0) < 0.001
    assert r["newest_tour_date"] == "2026-06-01T10:00:00Z"


def test_distance_weighted():
    # 100 km à 5 Wh/km + 10 km à 16.5 Wh/km -> (500+165)/110 Wh/km
    activities = [act("a1", 100), act("a2", 10)]
    bike_map = {"a1": "bike1", "a2": "bike1"}
    cons = {"a1": {"consumed_wh": 500.0}, "a2": {"consumed_wh": 165.0}}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert abs(r["wh_per_km"] - (665.0 / 110.0)) < 0.001


def test_window_stops_at_500km():
    # 12 Touren à 50 km: nach 10 Touren sind 500 km erreicht -> Tour 11/12 ignoriert
    activities = [act(f"a{i}", 50) for i in range(12)]
    bike_map = {f"a{i}": "bike1" for i in range(12)}
    cons = {f"a{i}": {"consumed_wh": 250.0} for i in range(12)}
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 10
    assert abs(r["window_km"] - 500.0) < 0.001


def test_min_data_thresholds():
    # nur 2 Touren -> None; 3 Touren aber < 30 km -> None
    activities = [act("a1", 20), act("a2", 20)]
    bike_map = {"a1": "bike1", "a2": "bike1"}
    cons = {"a1": {"consumed_wh": 100.0}, "a2": {"consumed_wh": 100.0}}
    assert compute_range_estimate(activities, bike_map, cons, "bike1") is None

    activities = [act(f"a{i}", 5) for i in range(3)]
    bike_map = {f"a{i}": "bike1" for i in range(3)}
    cons = {f"a{i}": {"consumed_wh": 25.0} for i in range(3)}
    assert compute_range_estimate(activities, bike_map, cons, "bike1") is None


def test_skips_invalid_tours():
    # Touren ohne Verbrauch, mit 0 Wh oder Mini-Distanz (<0.5 km) überspringen,
    # fremde Bikes ignorieren
    activities = [
        act("ok1", 20), act("nocons", 30), act("zero", 25),
        act("tiny", 0.3), act("other", 40), act("ok2", 20), act("ok3", 20),
    ]
    bike_map = {a["id"]: "bike1" for a in activities}
    bike_map["other"] = "bike2"
    cons = {
        "ok1": {"consumed_wh": 100.0}, "zero": {"consumed_wh": 0.0},
        "tiny": {"consumed_wh": 10.0}, "other": {"consumed_wh": 999.0},
        "ok2": {"consumed_wh": 100.0}, "ok3": {"consumed_wh": 100.0},
    }
    r = compute_range_estimate(activities, bike_map, cons, "bike1")
    assert r["tours_used"] == 3
    assert abs(r["wh_per_km"] - 5.0) < 0.001


def test_unmapped_activities_count_for_single_bike_fallback():
    # leere bike_map + fallback_all=True (Single-Bike-Konto, Attribution leer)
    activities = [act(f"a{i}", 20) for i in range(3)]
    cons = {f"a{i}": {"consumed_wh": 100.0} for i in range(3)}
    r = compute_range_estimate(activities, {}, cons, "bike1", fallback_all=True)
    assert r is not None and r["tours_used"] == 3


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
```

**Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd /tmp/hbcl && python3 tests/test_range_estimate.py`
Expected: `ModuleNotFoundError: No module named 'custom_components.bosch_ebike.range_estimate'`
(Falls stattdessen der HA-Import von `const.py` o. Ä. anschlägt: `range_estimate.py` darf KEINE
Imports aus dem Package ziehen — Konstanten als Funktions-Defaults, nicht aus `const.py` importieren.)

**Step 3: Implementierung**

`custom_components/bosch_ebike/range_estimate.py`:

```python
"""Pure range-estimation math for the Bosch eBike integration.

Deliberately free of Home Assistant imports so it can be unit-tested
standalone (see tests/test_range_estimate.py).
"""

from __future__ import annotations

from typing import Any

# Defaults mirror docs/plans/2026-06-10-range-estimate-design.md
DEFAULT_WINDOW_KM = 500.0
MIN_TOURS = 3
MIN_KM = 30.0
MIN_TOUR_KM = 0.5


def compute_range_estimate(
    activities: list[dict[str, Any]],
    activity_bike: dict[str, str],
    consumption: dict[str, dict[str, Any]],
    bike_id: str,
    window_km: float = DEFAULT_WINDOW_KM,
    fallback_all: bool = False,
) -> dict[str, Any] | None:
    """Distance-weighted average consumption over the last ~window_km.

    Walks activities newest-first, keeps tours that belong to the bike and
    have a valid consumption record, and accumulates until the distance
    window is filled (the tour crossing the threshold is still included).

    Returns ``{wh_per_km, tours_used, window_km, newest_tour_date}`` or
    ``None`` when the data base is too thin (< MIN_TOURS tours or < MIN_KM km).

    ``fallback_all=True`` treats unmapped activities as belonging to the
    bike (single-bike accounts where attribution is empty).
    """
    total_wh = 0.0
    total_km = 0.0
    tours = 0
    newest_date: str | None = None

    for activity in activities:
        aid = activity.get("id")
        if not aid:
            continue
        mapped = activity_bike.get(aid)
        if mapped != bike_id and not (mapped is None and fallback_all):
            continue
        entry = consumption.get(aid)
        if not entry:
            continue
        try:
            wh = float(entry.get("consumed_wh") or 0)
            km = float(activity.get("distance") or 0) / 1000.0
        except (TypeError, ValueError):
            continue
        if wh <= 0 or km <= MIN_TOUR_KM:
            continue

        total_wh += wh
        total_km += km
        tours += 1
        if newest_date is None:
            newest_date = activity.get("startTime")
        if total_km >= window_km:
            break

    if tours < MIN_TOURS or total_km < MIN_KM:
        return None

    return {
        "wh_per_km": round(total_wh / total_km, 2),
        "tours_used": tours,
        "window_km": round(total_km, 1),
        "newest_tour_date": newest_date,
    }
```

**Step 4: Test laufen lassen — muss bestehen**

Run: `cd /tmp/hbcl && python3 tests/test_range_estimate.py`
Expected: `PASS test_...` ×6, `ALL TESTS PASSED`

**Step 5: Commit**

```bash
cd /tmp/hbcl && git add tests/test_range_estimate.py custom_components/bosch_ebike/range_estimate.py
git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe" commit -m "feat(range): reine Berechnungsfunktion für Reichweiten-Schätzung (Wh/km über letzte ~500 km)"
```

---

### Task 2: Coordinator-Anbindung

**Files:**
- Modify: `custom_components/bosch_ebike/coordinator.py` (Import oben; Berechnung + data-Key im `_async_update_data`-Return, aktuell ~Zeile 567-578)

**Step 1: Import ergänzen** (bei den anderen relativen Imports):

```python
from .range_estimate import compute_range_estimate
```

**Step 2: Berechnung vor dem Return-Block einfügen** (nach dem `_check_service_and_maintenance`-Block, vor `if state_changed:`):

```python
        # Estimated range: distance-weighted Wh/km over the last ~500 km,
        # computed from data already in memory (no extra API calls).
        range_estimate: dict[str, dict[str, Any]] = {}
        single_bike = len(bikes) == 1
        for bike in bikes:
            bid = bike.get("id")
            if not bid:
                continue
            est = compute_range_estimate(
                self._all_activities,
                self._activity_bike,
                self._activity_consumption,
                bid,
                fallback_all=single_bike,
            )
            if est:
                range_estimate[bid] = est
```

**Step 3: Key ins Return-Dict aufnehmen** (im bestehenden `return {...}`):

```python
            "range_estimate": range_estimate,
```

**Step 4: Syntax prüfen**

Run: `cd /tmp/hbcl && python3 -m py_compile custom_components/bosch_ebike/coordinator.py && echo OK`
Expected: `OK`

**Step 5: Commit**

```bash
git add custom_components/bosch_ebike/coordinator.py
git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe" commit -m "feat(range): Reichweiten-Schätzung pro Bike im Coordinator berechnen"
```

---

### Task 3: Sensor „Estimated Range (Full Battery)"

**Files:**
- Modify: `custom_components/bosch_ebike/sensor.py`

**Step 1: Disclaimer-Konstante** (Modulebene, bei den anderen Konstanten):

```python
RANGE_DISCLAIMER = (
    "Estimate based on your past consumption over the last ~500 km. "
    "Actual range depends on assist mode, terrain, wind, temperature "
    "and battery age."
)
```

**Step 2: Sensor-Klasse** (nach `BoschBatteryConsumptionSensor`, gleiche Konventionen):

```python
class BoschRangeEstimateSensor(CoordinatorEntity[BoschEBikeCoordinator], SensorEntity):
    """Estimated range at full battery, derived from past consumption.

    Clearly labelled as an estimate: name prefix, disclaimer attribute and
    the underlying numbers (wh_per_km, tours_used, window_km) exposed.
    """

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:map-marker-distance"
    _attr_translation_key = "estimated_range_full"
    _attr_name = "Estimated Range (Full Battery)"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._bike_id = bike_id
        self._attr_unique_id = f"{bike_id}_estimated_range_full"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, bike_id)},
            name=drive_name,
            manufacturer="Bosch",
            model=drive_name,
        )

    def _estimate(self) -> dict[str, Any] | None:
        return (self.coordinator.data.get("range_estimate") or {}).get(self._bike_id)

    @property
    def native_value(self) -> int | None:
        est = self._estimate()
        if not est or not est.get("wh_per_km"):
            return None
        capacity = self.coordinator.data.get("battery_capacity_wh")
        if not capacity:
            return None
        return round(capacity / est["wh_per_km"])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        est = self._estimate()
        if not est:
            return {"disclaimer": RANGE_DISCLAIMER}
        return {
            "disclaimer": RANGE_DISCLAIMER,
            "wh_per_km": est.get("wh_per_km"),
            "tours_used": est.get("tours_used"),
            "window_km": est.get("window_km"),
            "newest_tour_date": est.get("newest_tour_date"),
            "battery_capacity_wh": self.coordinator.data.get("battery_capacity_wh"),
        }
```

Hinweis: `SensorStateClass` ist in sensor.py bereits importiert (prüfen, sonst zum bestehenden
`homeassistant.components.sensor`-Import ergänzen). `UnitOfLength` ebenso.

**Step 3: Registrierung in `async_setup_entry`** (in der bike-Schleife, nach den ServiceDue-Sensoren):

```python
        # Estimated range (clearly labelled estimate, derived from history)
        entities.append(BoschRangeEstimateSensor(coordinator, bike_id, drive_name))
```

**Step 4: Syntax prüfen**

Run: `python3 -m py_compile custom_components/bosch_ebike/sensor.py && echo OK`
Expected: `OK`

**Step 5: Commit**

```bash
git add custom_components/bosch_ebike/sensor.py
git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe" commit -m "feat(range): Sensor 'Estimated Range (Full Battery)'"
```

---

### Task 4: Sensor „Estimated Range (Current)" (Live-SoC)

**Files:**
- Modify: `custom_components/bosch_ebike/sensor.py`

**Step 1: Imports prüfen/ergänzen**

```python
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers.event import async_track_state_change_event
from .const import CONF_LIVE_SOC_ENTITY
```
(`callback` ggf. schon importiert; `CONF_LIVE_SOC_ENTITY` kommt aus `const.py`.)

**Step 2: Klasse** (erbt vom Full-Battery-Sensor, ergänzt SoC):

```python
class BoschCurrentRangeSensor(BoschRangeEstimateSensor):
    """Estimated remaining range from live SoC × capacity ÷ avg consumption.

    Only created when the live SoC sensor (ESPHome bridge) is linked in the
    options. Listens to that entity so the value updates immediately, not
    just on the 30-minute poll.
    """

    _attr_translation_key = "estimated_range_current"
    _attr_name = "Estimated Range (Current)"

    def __init__(
        self,
        coordinator: BoschEBikeCoordinator,
        bike_id: str,
        drive_name: str,
        soc_entity_id: str,
    ) -> None:
        super().__init__(coordinator, bike_id, drive_name)
        self._attr_unique_id = f"{bike_id}_estimated_range_current"
        self._soc_entity_id = soc_entity_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._soc_entity_id], self._on_soc_change
            )
        )

    @callback
    def _on_soc_change(self, event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    def _current_soc(self) -> float | None:
        state = self.hass.states.get(self._soc_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            soc = float(state.state)
        except ValueError:
            return None
        return max(0.0, min(100.0, soc))

    @property
    def native_value(self) -> int | None:
        full = super().native_value
        if full is None:
            return None
        soc = self._current_soc()
        if soc is None:
            return None
        return round(full * soc / 100.0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = dict(super().extra_state_attributes or {})
        attrs["soc_source"] = self._soc_entity_id
        attrs["current_soc"] = self._current_soc()
        return attrs
```

**Step 3: Bedingte Registrierung in `async_setup_entry`** (direkt nach Task-3-Zeile; `entry` ist dort verfügbar):

```python
        soc_entity = entry.options.get(CONF_LIVE_SOC_ENTITY)
        if soc_entity:
            entities.append(
                BoschCurrentRangeSensor(coordinator, bike_id, drive_name, soc_entity)
            )
```

**Step 4: Syntax prüfen + Tests erneut**

Run: `python3 -m py_compile custom_components/bosch_ebike/sensor.py && python3 tests/test_range_estimate.py | tail -1`
Expected: `ALL TESTS PASSED`

**Step 5: Commit**

```bash
git add custom_components/bosch_ebike/sensor.py
git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe" commit -m "feat(range): Sensor 'Estimated Range (Current)' mit Live-SoC-Listener"
```

---

### Task 5: Entity-Translations (de/en/nl)

**Files:**
- Modify: `custom_components/bosch_ebike/translations/de.json`, `en.json`, `nl.json` (Abschnitt `entity.sensor`)
- `strings.json` nur anfassen, falls dort ein `entity`-Abschnitt existiert (prüfen!)

**Step 1: Einträge ergänzen** (per Python-Skript, JSON-sicher):

| Key | de | en | nl |
|---|---|---|---|
| `estimated_range_full` | `Geschätzte Reichweite (voller Akku)` | `Estimated range (full battery)` | `Geschatte actieradius (volle accu)` |
| `estimated_range_current` | `Geschätzte Reichweite (aktuell)` | `Estimated range (current)` | `Geschatte actieradius (actueel)` |

```bash
cd /tmp/hbcl/custom_components/bosch_ebike && python3 - <<'PY'
import json
names = {
  "de.json": {"estimated_range_full": "Geschätzte Reichweite (voller Akku)",
              "estimated_range_current": "Geschätzte Reichweite (aktuell)"},
  "en.json": {"estimated_range_full": "Estimated range (full battery)",
              "estimated_range_current": "Estimated range (current)"},
  "nl.json": {"estimated_range_full": "Geschatte actieradius (volle accu)",
              "estimated_range_current": "Geschatte actieradius (actueel)"},
}
for fname, entries in names.items():
    path = f"translations/{fname}"
    d = json.load(open(path, encoding="utf-8"))
    sens = d.setdefault("entity", {}).setdefault("sensor", {})
    for key, name in entries.items():
        sens[key] = {"name": name}
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(path, "a", encoding="utf-8").write("\n")
    print("updated", fname)
PY
```

**Step 2: JSON validieren**

Run: `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('translations/*.json')]; print('JSON OK')"`
Expected: `JSON OK`

**Step 3: Commit**

```bash
git add translations/
git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe" commit -m "feat(range): Entity-Übersetzungen für die Reichweiten-Sensoren (de/en/nl)"
```

---

### Task 6: README-Dokumentation (6 Sprachen)

**Files:**
- Modify: `README.md` (DE-Teil + EN-Teil), `README.nl.md`, `README.fr.md`, `README.it.md`, `README.es.md`

**Step 1: Neuer Abschnitt** — im DE-Teil nach dem Abschnitt „Wartungs-Erinnerungen", im EN-Teil und in den Sprachdateien an der strukturgleichen Stelle. Deutscher Text (EN/NL/FR/IT/ES sinngemäß übersetzen, gleiche Struktur):

```markdown
### Reichweiten-Schätzung

Pro Bike gibt es zwei Sensoren, die die Reichweite **schätzen** — auf Basis
deines tatsächlichen Verbrauchs (distanzgewichteter Durchschnitt über die
letzten ~500 km Tour-Historie):

- **`Estimated Range (Full Battery)`** — geschätzte Reichweite mit vollem Akku
  (Akkukapazität ÷ Ø-Verbrauch in Wh/km). Rein aus Cloud-Daten, immer verfügbar.
- **`Estimated Range (Current)`** — geschätzte Restreichweite
  (aktueller Akkustand × Kapazität ÷ Ø-Verbrauch). Erscheint nur, wenn in den
  Integrations-Optionen der **Live-Akkustand-Sensor** der ESPHome-Bridge
  verknüpft ist; aktualisiert sich sofort bei SoC-Änderungen.

> ⚠️ **Das ist eine Schätzung, keine Garantie.** Die tatsächliche Reichweite
> hängt stark von Unterstützungsmodus, Topografie, Wind, Temperatur und
> Akkuzustand ab. Die Berechnungsgrundlage ist in den Sensor-Attributen
> einsehbar (`wh_per_km`, `tours_used`, `window_km`). Solange weniger als
> 3 Touren bzw. 30 km Verbrauchsdaten vorliegen, bleiben die Sensoren leer.
```

**Step 2: Sensor-Tabellen ergänzen** — in allen 6 READMEs in der Tabelle „Bike-Sensoren" (bzw. Übersetzung) zwei Zeilen:

```markdown
| Estimated Range (Full Battery) | km | Geschätzte Reichweite mit vollem Akku (aus Ø-Verbrauch, Schätzung!) |
| Estimated Range (Current) | km | Geschätzte Restreichweite (Live-SoC nötig, Schätzung!) |
```

**Step 3: Commit**

```bash
git add README.md README.nl.md README.fr.md README.it.md README.es.md
git -c user.email="v.hauffe@me.com" -c user.name="Volker Hauffe" commit -m "docs(range): Reichweiten-Schätzung in allen sechs READMEs dokumentiert"
```

---

### Task 7: Verifikation (User-Test, KEIN Push davor)

1. `python3 tests/test_range_estimate.py` → `ALL TESTS PASSED`
2. `python3 -m py_compile custom_components/bosch_ebike/*.py` → OK
3. **User-Test auf der HA-Instanz** (Dateien aus `/tmp/hbcl/custom_components/bosch_ebike/` rüberkopieren oder Pre-Release): beide Sensoren erscheinen, Werte plausibel gegen Flow-App, Attribute (Disclaimer, wh_per_km) sichtbar, Current-Sensor reagiert auf SoC-Änderung, frische Installation → Sensoren `unbekannt` ohne Fehler im Log.

### Task 8: Release (erst nach User-Freigabe!)

1. `manifest.json` → Version `1.18.0`
2. Commit + Push auf `main`
3. Annotiertes Tag `v1.18.0` + GitHub-Release, Notes **dreisprachig (DE/EN/NL)**, Schätzungs-Charakter im Text betonen. Kein Co-Author, nirgends.
