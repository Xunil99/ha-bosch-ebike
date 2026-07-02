# Bosch eBike Smart System – Home Assistant-integratie

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

> [Deutsch](README.md) | [English](README.md#english) | **Nederlands** | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md)

> **⚠️ Update-opmerking (vanaf v1.17.6):** De integratiemap heet nu `ha_bosch_ebike` (voorheen `bosch_ebike`). Je installatie, apparaten en instellingen blijven ongewijzigd. Als na de HACS-update **beide** mappen in `config/custom_components/` staan, verwijder dan eenmalig de oude `bosch_ebike` en herstart Home Assistant.

> ### ⚠️ Regionale vereiste
> Deze integratie werkt **uitsluitend met een Bosch SingleKey-ID-account dat binnen de EU is geregistreerd**. Ze gebruikt de officiële Bosch Data Act API, waarvan de beschikbaarheid beperkt is tot EU-accounts. Accounts uit andere regio's worden door het API-endpoint geweigerd en de integratie kan zich dan niet aanmelden.

> ### 🔌 Echte live-data via Bluetooth (smart system v19+)
> Dit repo bevat naast de HACS-integratie ook een **ESPHome-BLE-bridge** die van een ESP32 een brug naar het **Bosch eBike Live Data Interface** maakt. Daarmee stromen accu-SoC, snelheid, kilometerstand & co. in realtime naar Home Assistant.
>
> 🚀 **Flashen zonder ESPHome-installatie**: sluit een ESP32 (of ESP32-C3, bijv. "C3 Mini") via USB aan, open in Chrome / Edge **[https://xunil99.github.io/ha-bosch-ebike/](https://xunil99.github.io/ha-bosch-ebike/)** en klik op *Install*. De installer herkent de chip automatisch en flasht de juiste firmware. De wifi-setup verloopt in dezelfde browserstap. Volledige handleiding (DE/EN) incl. koppelen via de Flow-app: [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome).

> ### 🖥️ Optioneel: 4,3"-display voor datum, weer en live-data
> Naast de bridge is er nu een tweede firmware voor het **Guition/Sunton JC4827W543** (ESP32-S3 met 4,3" IPS-touchscreen). Deze leest de bridge-sensoren uit Home Assistant en toont datum, tijd, weer en maximaal twee eBikes tegelijk. Bestaande bridge-gebruikers hoeven niets te wijzigen; het display is puur additief. Setup-handleiding: [`esphome/DISPLAY.md`](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/DISPLAY.md).

---

## Nederlands

### Beschrijving

Deze custom integratie verbindt je **Bosch eBike Smart System** met Home Assistant. Ze leest fietsgegevens (kilometerstand, motoruren, acculaadcycli) en activiteitsgegevens (laatste rit, snelheid, cadans, vermogen) rechtstreeks uit de officiële Bosch Data Act API.

**Alleen eBikes met Bosch Smart System worden ondersteund** (niet het Classic Line-systeem).

### 🆕 eBike System 2 (BES2) – NIEUW, momenteel in test (alpha)

De integratie ondersteunt nu **ook** het oudere **eBike System 2 (BES2)**, niet alleen het Smart System. Bestaande Smart-System-gebruikers worden hierdoor **niet beïnvloed**: het systeem wordt **per integratie-item** gekozen, je bestaande installatie blijft ongewijzigd.

> **⚠️ Opmerking:** De BES2-ondersteuning is **nieuw en momenteel in test (alpha)**.

**Installatie (verschil met Smart System):** in het Bosch Data Act-portaal ([portal.bosch-ebike.com/data-act](https://portal.bosch-ebike.com/data-act)) melden BES2-eigenaren zich aan via **"Bosch eBike Connect user? Log in here"** (de eBike Connect-identiteit), **niet** via SingleKey ID. Maak daarna zoals gebruikelijk een App / Client-ID aan en verleen de Data Act-toestemming – de rest van de procedure is identiek. Bij het toevoegen van de integratie in Home Assistant kies je in de **eerste stap (systeemkeuze)** **eBike System 2** en voer je vervolgens de Client-ID in.

**Beperktere dataset dan het Smart System.** BES2 levert minder gegevens:

- **Beschikbaar:** ritten (afstand, duur, gem./max. snelheid, cadans, vermogen, hoogtemeters, calorieën, optioneel hartslag via de activiteitsdetails), totalen en de GPS-track op de kaart.
- **Niet beschikbaar:** kilometerstand, bereik per ondersteuningsmodus, volgende servicebeurt, acculaadcycli / Wh over de levensduur / State of Health, diefstal/locatie en de live-BLE-bridge.

Deze entiteiten bestaan voor BES2-fietsen eenvoudigweg niet.

### Functies

- **Fietsgegevens:** kilometerstand, motoruren (totaal & met ondersteuning), maximale ondersteuningssnelheid, actieve ondersteuningsmodi, loophulpsnelheid, kilometerstand volgende servicebeurt
- **Accugegevens:** geleverde Wh over de levensduur, laadcycli (totaal, op de fiets, extern)
- **Laatste rit:** afstand, duur, gemiddelde/maximale snelheid, cadans (gem./max.), vermogen van de rijder in watt (gem./max.), calorieverbruik, hoogtemeters (stijging/daling), titel, datum
- **Totaalstatistieken:** aantal ritten, totale afstand, totale rijtijd, totale calorieën, totale hoogtemeters, gemiddelden voor snelheid/vermogen/cadans over alle ritten
- **GPS-track-export:** export van alle ritten als GPX-bestanden (met snelheid, cadans en vermogen als Garmin TrackPointExtension)
- **Interactieve kaartweergave:** custom Lovelace-kaart met GPS-tracks, snelheidsafhankelijke kleurcodering, datumkiezer en prev/next-navigatie
- **3D-kaart met chase-cam, tijdschuif en gebouwschaduwen:** custom Lovelace-kaart (`bosch-ebike-3d-map-card`) voor de tour-detailweergave met 3D-gebouwen, een camera die de fiets van achteren volgt, proportionele afspeelsnelheid (standaard 60× realtime) en slagschaduwen volgens de zonnestand op het tijdstip van de tour (MapLibre + OpenFreeMap, gratis en zonder API-key)
- **Dashboard-kaart met fietsfoto, live-data en laadbediening:** custom Lovelace-kaart (`bosch-ebike-dashboard-card`) met eigen fietsfoto, kilometerstand, accuniveau, laadstatus, optionele laadvermogenssensor, doel-SoC-schuifregelaar en start-/stopknoppen via een slimme stekker
- **Automatische tokenvernieuwing** via refresh-token
- **Polling-interval van 30 minuten** (bij de eerste start worden alle ritten geïmporteerd)

### 🆕 Live-data via Bluetooth (ESPHome-bridge)

Naast de cloud-integratie vind je in de submap [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome) een **ESPHome external component** die van een ESP32 een brug naar het **Bosch eBike Live Data Interface (LDI)** (BLE, smart system v19+) maakt. Daarmee stromen realtime waarden (snelheid, accu-SoC, cadans, rijdersvermogen, kilometerstand, lichtstatus, lock-status, …) als ESPHome-sensoren naar HA – als aanvulling op de cloud-gebaseerde tourhistorie.

🚀 **Snelste weg zonder ESPHome-kennis**: ESP32 aansluiten, in Chrome / Edge naar **https://xunil99.github.io/ha-bosch-ebike/** gaan en op *Install* klikken. Firmware-flash en wifi-setup verlopen volledig in de browser – geen ESPHome-installatie nodig.

Volledige handleiding: **[esphome/README.md](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/README.md)**

> **Verwante projecten:** Geen ESP32 bij de hand, maar wel een Raspberry Pi? [ha-bosch-ebike-pibridge](https://github.com/possm/ha-bosch-ebike-pibridge) van [@possm](https://github.com/possm) is een community-port in Python (BlueZ + MQTT) die rechtstreeks op de Pi draait, **twee fietsen tegelijk** ondersteunt en een eigen webdashboard meebrengt.

#### Live-waarden gebruiken voor exacte tourberekening (optioneel, vanaf v1.10.0)

Als de bridge draait, kun je in de **integratie-instellingen** (HA → *Instellingen → Apparaten & diensten → Bosch eBike → Configureren*) twee sensoren opgeven:

- **Live-kilometerstandsensor** (bijv. `sensor.ebike_odometer_live`)
- **Live-accuniveausensor** (bijv. `sensor.ebike_battery_soc_live`)

Zijn deze ingesteld, dan vraagt de integratie bij elke tour-update de HA-recorder naar de waarde van deze sensoren bij tourstart en -einde. Uit de verschillen volgt:

- **Exacte tourafstand** (verschil in kilometerstand in plaats van cloud-GPS-berekening).
- **Exact accuverbruik in Wh** ((SoC-start − SoC-einde) × accucapaciteit / 100).

Deze waarden vervangen de eerdere snapshot-schatting in de sensoren *Last Ride Distance*, *Battery Consumption Wh*, *verbruik %* enz. Was er bij tourstart of -einde geen BLE-sample binnen het tolerantievenster (±5 min) beschikbaar (fiets buiten bereik), dan valt de integratie transparant terug op de oude cloud-logica. Beide velden zijn optioneel en onafhankelijk – je kunt ook maar één van beide instellen.

### Vereisten

1. Een eBike met **Bosch Smart System** (bijv. Performance Line CX, SX, enz.)
2. Een **Bosch SingleKey ID**-account ([singlekey-id.com](https://singlekey-id.com))
3. Toegang tot het **Bosch eBike Flow-portaal** ([portal.bosch-ebike.com](https://portal.bosch-ebike.com))

---

### Stapsgewijze handleiding

#### Vereisten

1. Een **Bosch SingleKey ID**-account – maak er zo nodig een aan op [singlekey-id.com](https://singlekey-id.com)
2. Je eBike moet gekoppeld zijn aan de **Bosch eBike Flow-app** ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))

---

#### Stap 1: app registreren in het Bosch Data Act-portaal

1. Ga naar [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Log in met je **SingleKey ID**
3. Klik op **"App aanmaken"**
4. Vul het formulier in:
   - **App-naam:** bijv. `Home Assistant`
   - **Confidential client:** **UIT** laten

   > **Let op, snel te verwisselen:** de volgende twee velden zijn allebei `my.home-assistant.io`-adressen en lijken op het eerste gezicht op elkaar. **De volgorde in het Bosch-formulier kan afwijken van deze tabel** - vul elke waarde in bij het veld met de **bijpassende naam**, niet op basis van de positie. Verwissel je ze, dan krijg je "Invalid parameters are given" bij het klikken op "Service aktivieren", of "Invalid parameter: redirect_uri" van Bosch bij het autoriseren in Home Assistant.

   | Veld in het Bosch-formulier | Waarde | Waarvoor |
   |---|---|---|
   | **Redirect URI** | `https://my.home-assistant.io/redirect/oauth` | Terugkeeradres **na** het inloggen bij Bosch (OAuth-callback) - moet exact dit zijn, dit is de officiële "My Home Assistant"-doorverwijzing waarmee Home Assistant de login automatisch afrondt. |
   | **Login URL** | `https://my.home-assistant.io/redirect/config_flow_start/?domain=ha_bosch_ebike` | Link die **"Service aktivieren"** in de eBike Manager opent om de installatie-flow rechtstreeks in jouw Home Assistant-instantie te **starten**. |

   > **Let op:** De integratie "My Home Assistant" moet in HA ingeschakeld zijn (standaard het geval). Heb je die uitgeschakeld, vul dan bij **Redirect URI** in plaats daarvan `https://<jouw-HA-URL>/auth/external/callback` in.

5. Na het aanmaken krijg je een **Client-ID** (formaat `euda-xxxxxxxx-...`).

#### Stap 2: Client-ID bewaren

Kopieer de **Client-ID** – je hebt hem zo meteen nodig.

#### Stap 3: integratie installeren in Home Assistant

Installeer de integratie via **HACS** (zie de sectie hieronder) en herstart Home Assistant. Pas daarna kan de vrijgave-link uit de eBike Manager de installatie-flow openen.

#### Stap 4: integratie instellen (via "Service aktivieren")

1. Open **Mijn eBike → eBike Manager** en daar het onderdeel **Data Act** (bereikbaar via **[flow.bosch-ebike.com](https://flow.bosch-ebike.com)**).
2. Klik bij het item voor je in stap 1 aangemaakte app op **"Service aktivieren"**. Daarop opent automatisch jouw Home Assistant-instantie (via de in stap 1 ingestelde Login-URL).
3. In Home Assistant opent de installatie-flow: **plak de Client-ID**, **Autoriseren**, log in bij Bosch en bevestig.
4. De integratie is nu ingesteld - **maar de entiteiten ontbreken nog**. Dat is normaal, ga verder met stap 5.

> **Let op:** Je kunt de integratie ook handmatig toevoegen (**Instellingen → Apparaten & diensten → Integratie toevoegen → "Bosch eBike"**, Client-ID plakken, Autoriseren). Geen localhost en geen kopiëren en plakken: Home Assistant handelt de login-terugkeer af via de "My Home Assistant"-doorverwijzing, het access- en refresh-token worden daarna automatisch vernieuwd.

#### Stap 5: gegevensdeling per fiets activeren

Zonder geactiveerde vrijgave antwoordt de API met **403 Forbidden** en verschijnen er geen entiteiten.

1. Ga terug naar **Mijn eBike → eBike Manager → Data Act**.
2. Activeer daar de **schakelaar (toggle)** voor de in stap 1 aangemaakte client - de vrijgave geldt **per fiets**. Bij een actieve vrijgave verandert de weergave in **"Service deaktivieren"**.
3. Herlaad in Home Assistant de **Bosch eBike** integratie (**⋮ → Herladen**). Daarna zijn **alle entiteiten** aanwezig.

> Krijg je direct na het activeren nog een 403 of ontbreken er entiteiten: wacht een paar minuten (de vrijgave wordt serverzijdig doorgevoerd) en herlaad opnieuw.

#### Stap 6: kaartweergave instellen (optioneel)

De integratie bevat een interactieve Lovelace-kaart voor het weergeven van je GPS-tracks.

**Stap A: resource registreren**

> **Opmerking:** Vanaf versie 1.16.27 registreert deze resource zich **automatisch** zodra Home Assistant volledig is gestart – veilig, zonder andere bestaande resources te wijzigen (de foutieve, dataverlies-gevoelige variant uit eerdere versies is vervangen). **Normaal gesproken hoef je hier dus niets te doen.** Alleen als de kaart toch als "Custom element doesn't exist" verschijnt (bijv. omdat je resources in YAML-modus beheert), voeg je hem eenmalig handmatig toe zoals hieronder.

1. Ga naar **Instellingen → Dashboards**
2. Klik rechtsboven op het **⋮-menu** → **Resources**
3. Klik op **+ Resource toevoegen** (rechtsonder)
4. Voer het volgende in:
   - **URL:** `/ha_bosch_ebike/bosch-ebike-map-card.js`
   - **Resourcetype:** JavaScript-module
5. Klik op **Aanmaken**

**Stap B: kaart aan het dashboard toevoegen**

1. Open het gewenste dashboard
2. Klik rechtsboven op het **potlood ✏️** (bewerkmodus)
3. Klik op **+ Kaart toevoegen**
4. Scrol helemaal naar beneden en kies **Handmatig** (YAML-invoer)
5. Plak de volgende code:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 400
   ```
6. Klik op **Opslaan**

> **Tip:** De hoogte (height) kun je aanpassen (200–1000 pixels). Aanbevolen: 400 voor smartphones, 500 voor desktops.

**De kaart toont:**
- GPS-track met snelheidsafhankelijke kleurcodering (blauw → groen → geel → rood)
- Startmarker (groen) en eindmarker (rood)
- Ritinformatie (afstand, duur, gem./max. snelheid, hoogtemeters, calorieën)
- **◀ Prev / Next ▶**-knoppen en **datumkiezer** om door alle ritten te bladeren
- **▶ Chase-cam-knop** opent de zichtbare tour in een fullscreen-overlay met de volledige 3D-kaartweergave (2D / 3D / satelliet, schuifregelaar, noord-fix-toggle, fullscreen). Sluiten via de X-knop of Escape.

> **Opmerking:** Wordt de kaart na een update niet correct weergegeven, leeg dan de browsercache met `Ctrl+Shift+R` (hard reload).

> **HACS-update voor de kaarten:** Alle vier de Lovelace-kaarten (Map, Heatmap, Calendar, Dashboard) zitten in één JS-bestand (`bosch-ebike-map-card.js`) en worden automatisch met de integratie bijgewerkt. Voer na een versie-update vanuit HACS een hard reload van de browsercache uit, anders kan de kaartkiezer een nieuwe kaart nog niet tonen.

#### HACS-installatie (alternatief)

1. Open HACS in Home Assistant
2. Klik op **"Custom repositories"** (drie puntjes rechtsboven)
3. Voeg de repository-URL toe: `https://github.com/Xunil99/ha-bosch-ebike`
4. Categorie: **Integratie**
5. Installeer de integratie en herstart Home Assistant

---

### Meerdere fietsen of accounts

De integratie ondersteunt zowel meerdere accounts als meerdere fietsen per account.

**Meerdere Bosch-accounts** (bijv. één fiets per gezinslid met eigen SingleKey ID):
1. Maak voor elk account in het Bosch Data Act-portaal een eigen app-registratie met eigen Client-ID aan
2. Voeg de integratie meermaals toe (**Instellingen → Apparaten & diensten → + Integratie toevoegen → Bosch eBike**) en voer telkens de andere Client-ID in
3. Elke instantie heeft zijn eigen sensoren en tours

**Meerdere fietsen onder één account** (bijv. twee fietsen met dezelfde SingleKey ID):
- De integratie maakt automatisch eigen sensoren per fiets aan (drive unit, accu, service enz.).
- Tours worden via een heuristiek (vergelijking van de fietsspecifieke `odometer`-stand met `startOdometer + distance` van de betreffende tour) automatisch aan de juiste fiets toegewezen.

**Filter in de kaart:** Zodra er meer dan één account en/of meer dan één fiets is, toont de Lovelace-kaart automatisch twee keuzevelden boven de lijst:
- **Account** (alleen zichtbaar bij meerdere accounts)
- **Fiets** (alleen zichtbaar bij meerdere fietsen)

De selectie filtert de getoonde tours live; sorteren werkt zoals gebruikelijk binnen het gefilterde resultaat.

#### Kaart vast aan een account of fiets koppelen

Moet een kaart permanent precies één account of fiets tonen (bijv. om twee kaarten naast elkaar te zetten voor vergelijkingen), dan vul je in de kaartconfiguratie `account_id` en/of `bike_id` in. De betreffende dropdown wordt dan verborgen en het filter is vergrendeld.

De ID's kun je in de editor (rechtsboven in de kaartbewerking) eenvoudig uit dropdowns kiezen – handmatig opzoeken is niet nodig. Optioneel kan `title` de kaartkop overschrijven:

```yaml
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Mijn fiets"
    account_id: <config_entry_id_account_a>
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Partnerfiets"
    account_id: <config_entry_id_account_b>
```

Beide kaarten tonen dan altijd tours van het vergrendelde account en kunnen met de datum-/sorteerkeuze onafhankelijk van elkaar door de tourhistorie bladeren – ideaal om bijv. twee op dezelfde dag gereden tours direct te vergelijken. Dezelfde opties werken ook in de `bosch-ebike-heatmap-card`.

### POI's langs de route

Op de kaart zit een 📍-toggle in de bedieningselementen. Is die actief, dan wordt op de achtergrond een Overpass-API-query gestart die de volgende punten langs de route vindt (max. ~500 m van het gereden pad):

- 🔌 **Laadstations** (`amenity=charging_station`)
- 🛠️ **Fietsenwinkels** en reparatiestations (`shop=bicycle`, `amenity=bicycle_repair_station`)
- 💧 **Drinkwater** (`amenity=drinking_water`)
- 🚻 **Toiletten** (`amenity=toilets`)
- 🍽️ **Horeca** (restaurants, cafés, biertuinen, snackbars — `amenity=restaurant/cafe/biergarten/fast_food`)

Klik op een marker → pop-up met naam, openingstijden/adres/website (voor zover bij OSM bekend) en een link naar OpenStreetMap. Per tour worden maximaal 100 markers getoond; resultaten worden gecachet in de localStorage van de browser.

### Onderhoudsherinneringen

#### Servicebeurt zelf instellen

Per fiets zijn er twee bewerkbare entiteiten:

- **`date.<bike>_service_due_date`** – datum waarop de volgende servicebeurt nodig is
- **`number.<bike>_service_due_odometer`** – kilometerstand waarbij de volgende servicebeurt nodig is

Bij de eerste gegevensophaal worden deze waarden automatisch vooringevuld vanuit de Bosch-API (indien daar aanwezig). Wijzigingen aan de entiteiten overschrijven de Bosch-waarden en worden gebruikt voor de serviceherinneringen. Zet je de kilometerstand op `0`, dan valt de weergave terug op de Bosch-waarde.

#### Eigen onderhoudsitems

Naast de door Bosch geleverde servicebeurt (`Next Service Date`/`Next Service Odometer`) kun je willekeurige eigen onderhoudsitems aanmaken – bijv. kettingvervanging elke 3000 km, inspectie elke 365 dagen. Per fiets wordt een sensor `Maintenance Items Due` aangemaakt; de waarde ervan is het aantal binnenkort verschuldigde of achterstallige items, het attribuut `items` bevat alle details (resterende kilometers, resterende dagen).

**Item aanmaken:** **Ontwikkelhulpmiddelen → Diensten**, roep de dienst `bosch_ebike.add_maintenance` aan met:
- `bike_id` (uit het sensorattribuut)
- `name` (bijv. "Kettingvervanging")
- `interval_km` en/of `interval_days`

**Item als afgerond markeren:** dienst `bosch_ebike.complete_maintenance` met `bike_id` en `item_id` (uit het sensorattribuut). Zet datum en kilometerstand terug naar nu.

**Item verwijderen:** dienst `bosch_ebike.remove_maintenance`.

**Events voor automatiseringen:** Bij het bereiken van de drempel (standaard: 30 dagen / 200 km vóór de vervaldatum) worden HA-events afgevuurd:
- `ha_bosch_ebike_service_due_soon` / `ha_bosch_ebike_service_overdue` (voor de Bosch-service)
- `ha_bosch_ebike_maintenance_due_soon` / `ha_bosch_ebike_maintenance_overdue` (voor eigen items)

Daarmee kun je bijv. een pushmelding of een verlichtingsherinnering bouwen.

### Actieradius-schatting

Per fiets zijn er twee sensoren die de actieradius **schatten** — op basis
van je werkelijke verbruik (afstandsgewogen gemiddelde over de laatste
~500 km tourgeschiedenis):

- **`Estimated Range (Full Battery)`** — geschatte actieradius met een volle
  accu (accucapaciteit ÷ gemiddeld verbruik in Wh/km). Puur uit cloud-data,
  altijd beschikbaar.
- **`Estimated Range (Current)`** — geschatte resterende actieradius
  (huidig accuniveau × capaciteit ÷ gemiddeld verbruik). Verschijnt alleen
  als in de integratie-opties de **live-accuniveau-sensor** van de
  ESPHome-bridge is gekoppeld; wordt direct bijgewerkt bij SoC-wijzigingen.

> ⚠️ **Dit is een schatting, geen garantie.** De werkelijke actieradius hangt
> sterk af van ondersteuningsmodus, topografie, wind, temperatuur en
> accuconditie. De berekeningsbasis is in te zien in de sensorattributen
> (`wh_per_km`, `tours_used`, `window_km`). Zolang er minder dan 3 tours
> of 30 km aan verbruiksgegevens beschikbaar zijn, blijven de sensoren leeg.

### Routeplanner-kaart (BRouter)

De kaart `bosch-ebike-routeplanner-card` plant fietsroutes direct in het
dashboard — op basis van de open-source-router [BRouter](https://brouter.de):

```yaml
type: custom:bosch-ebike-routeplanner-card
height: 480
```

- **Wegpunten per klik** op de kaart (start, bestemming, willekeurig veel
  tussenpunten; marker slepen = verplaatsen, aanklikken = verwijderen)
- **Profielen:** Trekking, Racefiets, MTB, Kortste
- **POI's langs de route** (📍-schakelaar): laadstations, fietsenwinkels/
  werkplaatsen, drinkwater, toiletten en **horeca** (restaurants, cafés,
  biertuinen) — gegevens van OpenStreetMap/Overpass
- **Resultaat:** afstand, stijging/daling, rijtijd, **geschat verbruik**
  (je gemiddelde verbruik uit de actieradius-schatting × afstand)
- **Accucheck:** stoplicht-indicator die toont of de route haalbaar is met
  het huidige accuniveau (vereist gekoppelde live-accuniveau-sensor) — net
  als de actieradius-sensoren een **schatting**, geen garantie
- **Hoogteprofiel** als diagram onder de kaart
- **GPX-export** van de geplande route (importeerbaar in Garmin Connect,
  Komoot, de Flow-app e.a.)
- **Routes opslaan & laden:** geplande routes onder een eigen naam bewaren
  (opgeslagen in Home Assistant, op al je apparaten beschikbaar), via de
  📁-lijst opnieuw laden, verder bewerken of verwijderen

Opties: `title`, `height`, `brouter_url` (eigen BRouter-instantie in plaats
van brouter.de), `entity` (actieradius-sensor), `soc_entity` (live-accuniveau).

> **Privacy:** De wegpunt-coördinaten worden voor de routeberekening naar de
> geconfigureerde BRouter-server gestuurd — standaard de door donaties
> gefinancierde publieke server `brouter.de`. Wil je dat niet, draai BRouter
> dan zelf (Docker) en vul de URL in onder `brouter_url`.

### Heatmap-kaart – alle tours op één kaart

Een tweede kaartvariant `bosch-ebike-heatmap-card` legt alle tours van een selectie als halftransparante lijnen over elkaar. Filter-dropdowns voor periode (30 dagen / 3 maanden / 12 maanden / alles), account en fiets. Daaronder een statusregel met het aantal tours en kilometers van de selectie.

```yaml
type: custom:bosch-ebike-heatmap-card
height: 600
```

De eerste weergave kan even duren – voor elke nog niet opgehaalde tour wordt een extra API-call gedaan (met concurrency-limiet). De tracks worden serverzijdig in het geheugen gecachet; volgende oproepen zijn direct.

### Kalender-kaart – GitHub-stijl heatmap van fietsdagen

De kaart `bosch-ebike-calendar-card` toont een jaarheatmap in de stijl van het GitHub-contributions-overzicht: 7 rijen voor de weekdagen, één kolom per kalenderweek, elke cel gekleurd naar gereden kilometers op die dag. Bij hoveren verschijnt een tooltip met datum, aantal tours en afstand. De statistiekregel eronder toont actieve dagen, tours en totale afstand in de gekozen periode.

```yaml
type: custom:bosch-ebike-calendar-card
```

Filter-dropdowns bovenaan voor periode (12 maanden / 24 maanden / 5 jaar / alles), account en fiets. Een vast account- of fietsfilter kan via YAML worden vergrendeld (zelfde opties als bij de map- en heatmap-kaart):

```yaml
type: custom:bosch-ebike-calendar-card
title: Volkers fietsjaar
account_id: 01HXYZ...
bike_id: bike-uuid-1
```

Kleurklassen per dag: leeg, 1-10 km, 10-25 km, 25-50 km, 50+ km. De kleuren komen uit de HA-theme-variabelen; lichte thema's ogen als GitHub-light, in donkere modus wordt automatisch het passende donkere palet geladen.

### 3D-kaart – chase-cam-volgen met tijdschuif en zonnestand

De kaart `bosch-ebike-3d-map-card` is een parallelle kaart naast de klassieke 2D-map. Ze start met een lijst van de laatste tours. Bij een klik op een tour opent de 3D-detailweergave met MapLibre en gratis OpenFreeMap-vector-tiles: de **camera volgt de fiets in third-person-perspectief** ("chase-cam"), de bearing draait mee met de rijrichting, pitch en zoom zijn configureerbaar. Bij het bewegen van de schuifregelaar zwenkt de camera mee. De kaartverlichting past zich aan de zonnestand op het tijdstip van de tour aan.

```yaml
type: custom:bosch-ebike-3d-map-card
title: Tour in 3D
height: 540
default_pitch: 55      # chase-cam-hellingshoek
chase_zoom: 17         # ca. 100 m zicht vooruit
playback_speed: 60     # 60x realtime (1 uur tour = 1 min weergave)
```

**Wat de kaart toont:**

- Tourlijst (standaardweergave) met datum, titel, afstand en duur
- 3D-chase-cam na klik op een tour, met gebouw-extrusies uit OpenStreetMap
- Track-polyline in twee lagen (glow + hoofdlijn) voor goede leesbaarheid
- Start- en eindmarkers plus een blauwe pulserende positiemarker die de fiets voorstelt
- Tijdschuif met start-/eindtijden van de tour, scrubbaar; de camera zwenkt synchroon mee
- Play/pauze-knop voor de versnelde weergave (duur configureerbaar)
- Live-statistieken bij de schuifpositie: cumulatieve afstand, snelheid, hoogte
- Tijd- en zonnechip in de overlay toont de actuele tijd en daglichtfase (nacht, schemering, gouden uur, daglicht)
- **Slagschaduwen van gebouwen** op de grond, geprojecteerd vanuit zonne-azimut en zonnehoogte op de schuiftijd. Schaduwen worden bij daglicht getoond, bij schemering korter, bij nacht verborgen. Automatische update wanneer de camera naar een nieuw stadsgebied zwenkt of de schuif wordt bewogen.
- **Video-export** rechts naast de schuifregelaar: de opnameknop start een weergave vanaf het begin van de tour en schrijft de kaartinhoud parallel weg als video. Bij het toureinde volgt automatisch een bestandsdownload (ca. 20-40 MB per minuut). Het formaat bepaalt de browser: **MP4** in modern Chrome (≥ 126) en Safari (≥ 14.4), anders **WebM**. Volledig in de browser via `canvas.captureStream()` + `MediaRecorder`; de HA-server heeft er niets mee te maken.
- Terug-knop keert terug naar de tourlijst

**Configuratie-opties van de kaart:**

| Optie | Standaard | Beschrijving |
|---|---|---|
| `title` | "Bosch eBike 3D-Touren" | Koptekst |
| `height` | 540 | Kaarthoogte in pixels |
| `default_pitch` | 55 | Chase-cam-hellingshoek (20-65°). 20 ≈ vogelperspectief, 65 ≈ first-person |
| `chase_zoom` | 17 | Chase-cam-zoom (14-19). Hoger = dichterbij, 17 ≈ 100 m zicht vooruit |
| `chase_lookahead` | 30 | Look-ahead-afstand in meters. Hoe ver het cameradoel vóór de fiets ligt. Kleiner = fiets hoger in beeld. 0 = camera direct op de fiets gecentreerd. |
| `smooth_window` | 15 | Bearing-afvlakvenster. Hoger = vloeiendere camera, maar snijdt bochten verder af. 5 voelt trillerig, 40 erg traag |
| `track_smooth_window` | 2 | Track-positie-afvlakking voor het camerapad. 0 = uit (ruwe GPS, kan trillen), 2 = zacht (standaard), 5+ snijdt mogelijk zichtbaar bochten af. De getoonde tracklijn blijft altijd de ruwe GPS tonen |
| `playback_speed` | 60 | Realtime-vermenigvuldiger bij de play-knop. 60 = 60× sneller dan de echte rit; een tour van 1 uur speelt af in 1 minuut, een tour van 30 minuten in 30 seconden |
| `animate_seconds` | — | Optioneel. Dwingt een vaste afspeelduur af (bijv. altijd 25 s), overschrijft `playback_speed` |
| `show_date` | 1 | Datumchip in de overlay tonen (0 = uit) |
| `show_time` | 1 | Tijdchip in de overlay tonen (0 = uit) |
| `show_sun` | 1 | Zonnestandchip in de overlay tonen (0 = uit) |
| `show_speed` | 1 | Snelheid in de statistiekbalk onderaan tonen (0 = uit) |
| `show_distance` | 1 | Cumulatieve afstand in de statistiekbalk tonen (0 = uit) |
| `show_elevation` | 1 | Hoogte tonen (0 = uit) |
| `stats_as_chips` | 0 | 1 = afstand, snelheid en hoogte als overlay-chips linksboven in plaats van onderaan in de statistiekbalk. 0 = klassieke statistiekregel in de bedieningsbalk (standaard) |
| `account_id` | (leeg) | Op één account vastzetten, zoals bij de 2D-kaart |
| `bike_id` | (leeg) | Op één fiets vastzetten |

Opmerking: verborgen overlay-elementen ontbreken automatisch ook in de gedownloade video, omdat de opname simpelweg de weergegeven kaartinhoud meeschrijft.

**Afhankelijkheden en opmerkingen:**

- MapLibre GL wordt bij de eerste oproep van unpkg.com nageladen (ca. 800 KB gzipped, daarna gecachet)
- OpenFreeMap levert de vector-tiles zonder API-key en zonder registratie
- De kaart wordt pas geladen wanneer de gebruiker hem daadwerkelijk opent. De bestaande kaarten (Map, Heatmap, Calendar, Dashboard) worden niet beïnvloed.
- 3D-rendering is vloeiend op desktop en moderne mobiele apparaten. Bij zeer lange tracks (> 10.000 punten) kan het op oudere apparaten haperen.
- De OSM-gebouwdekking is in steden dicht, op het platteland schaarser. Tours door stedelijk gebied profiteren het meest.
- **Terreinschaduwen** (bergen, heuvels) zijn bewust niet opgenomen. Die zouden een DEM-tile-source (Maptiler met API-key, AWS-Open-Data-SRTM of zelf gehoste hoogtedata) plus eigen ray-casting in de shader vereisen. Bij voldoende interesse kan dat in een latere versie worden toegevoegd.

### Dashboard-kaart – fietsfoto, live-data en laadbediening

De kaart `bosch-ebike-dashboard-card` is bedoeld als combi-weergave voor het woonkamerdashboard: bovenaan een eigen foto van de fiets, daaronder de live-waarden uit de ESPHome-bridge en optioneel de bedieningselementen voor een slimme stekker waaraan de lader hangt. Alle velden zijn optioneel – wat niet is geconfigureerd, verbergt de kaart netjes in plaats van een lege regel te renderen.

```yaml
type: custom:bosch-ebike-dashboard-card
title: Performance CX
bike_image: /local/ebike-cx.jpg
odometer_entity: sensor.ebike_odometer_live
battery_entity: sensor.ebike_battery_soc_live
charging_entity: binary_sensor.ebike_charger_connected
last_tour_distance_entity: sensor.bosch_ebike_last_activity_distance
charge_power_entity: sensor.ebike_smart_plug_power
range_entity: sensor.cx_estimated_range_current
charge_switch_entity: switch.ebike_smart_plug
target_soc_entity: input_number.ebike_target_soc
```

**Wat de kaart toont:**

- **Fietsfoto** met ingebouwde upload in de kaarteditor (afbeelding kiezen, de kaart schrijft het pad zelf). Alternatief klassiek via `/config/www/` en `/local/bestand.jpg` verwijzen. Placeholder met fietsicoon zolang er niets is ingesteld.
- **Kilometerstand-tegel** en optioneel **afstand laatste tour**, **laadvermogen in watt**
- **Geschatte actieradius** als tegel (`≈ 62 km`) — automatisch zodra de sensor "Geschatte actieradius (actueel)" bestaat, of expliciet via `range_entity`. Net als de sensoren een **schatting**.
- **Status-pills** voor laadstatus en accupercentage
- **Doel-SoC-schuifregelaar** die de waarde van een `input_number` instelt
- **Start- en stopknoppen** met dubbele-klik-bevestiging bij stop (bescherming tegen vergissingen)
- **Accubalk** onderaan, die onder 35 % naar oranje en onder 15 % naar rood verspringt
- **Onderhoudslijst** met willekeurig veel vrij definieerbare items (ketting smeren, servicebeurt, remmen controleren, …) – in de editor te kiezen uit 11 suggesties of als vrije tekst. Per item een trigger via km-interval of dagen-interval. Ze verschijnen automatisch in het dashboard zodra ze binnen de komende **500 km** of **30 dagen** vervallen – achterstallige items rood, binnenkort vervallende geel, gesorteerd op urgentie. Met een groene vinkjesknop per regel markeer je een item direct als "afgerond". **Opslag in Home Assistant** (`/config/.storage/`, per fiets gescheiden) in plaats van in de browsercache: de items overleven browserwissels, zijn op alle apparaten synchroon en kunnen ook via de HA-diensten `bosch_ebike.add_maintenance`, `bosch_ebike.update_maintenance`, `bosch_ebike.complete_maintenance` en `bosch_ebike.remove_maintenance` vanuit automatiseringen worden beheerd. In de kaarteditor kies je de fiets uit een dropdown; de bijbehorende onderhoudsitems verschijnen er direct onder en worden live in de backend opgeslagen.
- **CO₂- en brandstofkostenvergelijking** met de auto: twee tegels "totaal" en "laatste tour" met bespaarde kg CO₂ en €. In de editor kies je het vergelijkingsvoertuig uit 7 realistische presets (compacte klasse/middenklasse/SUV, telkens benzine of diesel, plus elektrische auto met groene stroom); optioneel kun je de brandstof-/stroomprijs per liter/kWh overschrijven.

**Vereisten voor volledige functionaliteit:**

- Een draaiende **ESPHome-Bosch-eBike-bridge** voor accuniveau, kilometerstand en laaddetectie
- Een **slimme stekker** (Shelly, Tasmota, Fritz!DECT, enz.) die in HA als `switch.*` en optioneel als vermogenssensor `sensor.*_power` verschijnt, als je start/stop en laadvermogen wilt zien
- Een `input_number.*` met bereik 0-100, als je de doel-SoC-schuifregelaar wilt gebruiken

**Auto-stop bij doel-SoC** is bewust niet in de kaart zelf geïmplementeerd, maar als HA-automatisering, zodat je toleranties, tijdsvoorwaarden of logica voor meerdere apparaten vrij kunt vormgeven. Voorbeeldautomatisering:

```yaml
alias: eBike auto-stop bij doel-SoC
trigger:
  - platform: numeric_state
    entity_id: sensor.ebike_battery_soc_live
    above: input_number.ebike_target_soc
action:
  - service: switch.turn_off
    target:
      entity_id: switch.ebike_smart_plug
mode: single
```

### Wikipedia-artikelen langs de route

Op de Lovelace-kaart zit een 📚-toggle in de kaartbediening. Is die actief, dan zoekt de kaart langs de gereden route elke 2 km naar nabijgelegen Wikipedia-artikelen en toont die als (i)-markers. Een klik opent een kleine pop-up met titel, voorbeeldafbeelding, korte beschrijving en een link naar het volledige artikel.

- **Taal** volgt de HA-taalinstelling; bij een lege treffer wordt teruggevallen op Engels
- **Maximaal 30 markers** per tour; dichte gebieden worden gebundeld
- **Toggle-status en resultaten** worden in de browser gecachet (`localStorage`); bij een tourwissel worden verse gegevens opgehaald
- **Privacy-opmerking**: bij het activeren van de laag worden steunpunt-coördinaten van de route naar de Wikipedia-API gestuurd; de laag staat standaard uit

### Probleemoplossing

| Probleem | Oplossing |
|----------|-----------|
| Geen entiteiten na het instellen | De gegevensdeling-schakelaar in de eBike Manager activeren (stap 5) |
| "Client niet gevonden" bij het inloggen | "Service aktivieren" in de eBike Manager gebruiken (stap 4) en de Client-ID controleren op typefouten/spaties |
| "Invalid state" / terugkeer mislukt | Is "My Home Assistant" ingeschakeld in HA? De redirect-URI in het portaal moet `https://my.home-assistant.io/redirect/oauth` zijn |
| "Invalid parameters are given" bij het klikken op "Service aktivieren", of "Invalid parameter: redirect_uri" van Bosch bij het autoriseren | Redirect URI en Login URL in het Bosch-portaal verwisseld? Controleer stap 1 - beide zijn `my.home-assistant.io`-adressen die op elkaar lijken; elke waarde moet in het veld met de bijpassende naam staan |
| Kilometerstand onrealistisch hoog | De odometer wordt in meters geleverd en automatisch omgerekend naar km |
| Activiteitsgegevens ontbreken | Controleer of het delen van activiteiten in het Flow-portaal actief is |
| Token niet geaccepteerd | Controleer of de Client-ID correct is ingevoerd |

---

### Beschikbare sensoren

#### Fietssensoren
| Sensor | Eenheid | Beschrijving |
|--------|---------|--------------|
| Odometer | km | Totale kilometerstand |
| Motor Total Hours | h | Totale motorlooptijd |
| Motor Assist Hours | h | Motorlooptijd met ondersteuning |
| Max Assist Speed | km/h | Maximale ondersteuningssnelheid |
| Active Assist Modes | - | Lijst van actieve ondersteuningsmodi |
| Walk Assist Speed | km/h | Loophulpsnelheid |
| Next Service Odometer | km | Kilometerstand volgende servicebeurt |
| Estimated Range (Full Battery) | km | Geschatte actieradius met volle accu (uit gem. verbruik, schatting!) |
| Estimated Range (Current) | km | Geschatte resterende actieradius (live-SoC vereist, schatting!) |

#### Accusensoren (per accu)
| Sensor | Eenheid | Beschrijving |
|--------|---------|--------------|
| Wh Lifetime | Wh | Geleverde wattuur over de levensduur |
| Charge Cycles | - | Totale laadcycli |
| Cycles On Bike | - | Laadcycli op de fiets |
| Cycles Off Bike | - | Laadcycli extern |

#### Activiteitssensoren (laatste rit)
| Sensor | Eenheid | Beschrijving |
|--------|---------|--------------|
| Last Ride Title | - | Naam van de rit |
| Last Ride Date | - | Datum/tijd |
| Last Ride Distance | km | Afstand |
| Last Ride Duration | min | Rijduur (zonder stops) |
| Last Ride Avg/Max Speed | km/h | Gemiddelde/maximale snelheid |
| Last Ride Avg/Max Cadence | rpm | Cadans |
| Last Ride Avg/Max Rider Power | W | Vermogen van de rijder |
| Last Ride Calories | kcal | Calorieverbruik |
| Last Ride Elevation Gain/Loss | m | Hoogtemeters (stijging/daling) |

#### Totaalstatistieken (over alle ritten)
| Sensor | Eenheid | Beschrijving |
|--------|---------|--------------|
| Total Rides | - | Aantal ritten |
| Total Distance (Activities) | km | Totale afstand van alle ritten |
| Total Ride Duration | h | Totale rijtijd |
| Total Calories | kcal | Totaal calorieverbruik |
| Total Elevation Gain | m | Totale hoogtemeters |
| Avg Speed (All Rides) | km/h | Gemiddelde snelheid over alle ritten |
| Avg Rider Power (All Rides) | W | Gemiddeld rijdersvermogen |
| Avg Cadence (All Rides) | rpm | Gemiddelde cadans |

#### Knoppen
| Knop | Beschrijving |
|------|--------------|
| Import All GPS Data | Exporteert GPS-tracks van alle ritten als GPX-bestanden |
| Import Latest GPS Data | Exporteert de GPS-track van de laatste rit als GPX |

> **Opslaglocatie:** De geëxporteerde GPX-bestanden worden lokaal opgeslagen in de Home Assistant-configuratiemap:
> ```
> /config/bosch_ebike_gps/
> ```

#### 🆕 Uitgebreide Data Act-entiteiten (vanaf v1.18.0)

Deze entiteiten verschijnen **automatisch** met de normale installatie. Er is **geen aanvullende of aparte Bosch-gegevensdeling nodig** – ze vallen onder de gebruikelijke autorisatie. Veel ervan staan afhankelijk van de fiets toch op "onbekend", omdat de onderliggende gegevens niet bestaan (zie de opmerking hieronder).

| Entiteit | Type/eenheid | Beschrijving |
|----------|--------------|--------------|
| Reachable Range {Eco/Tour/eMTB/Turbo} | sensor / km | Officiële Bosch-actieradiusschatting per rijmodus (één sensor per actieve modus) |
| Next Service Date | sensor / datum | Volgende servicebeurt als datum (aanvulling op de km-gebaseerde Next Service Odometer) |
| State of Health | sensor / % | Accugezondheid per accu, uit het digitale serviceboek |
| Measured Capacity | sensor / Wh | Door de dealer gemeten accucapaciteit per accu |
| Theft Reported | binary_sensor | Of er voor de fiets diefstal is gemeld (uit de Bike Pass) |
| Last Known Location | device_tracker | Laatst bekende locatie bij gemelde diefstal (uit de Bike Pass) |
| Software Update Available | binary_sensor | Of er een software-update voor de fiets beschikbaar is |
| Lifetime Distance {modus} | sensor / km | Levensduur-afstand per rijmodus (uit het serviceboek) |
| Lifetime Energy {modus} | sensor / Wh | Levensduur-energie per rijmodus (uit het serviceboek) |
| Last Service Date | sensor / datum | Datum van de laatste servicebeurt |
| Last Service Dealer | sensor | Dealer van de laatste servicebeurt |
| Last Service Odometer | sensor / km | Kilometerstand bij de laatste servicebeurt |
| Components | sensor (diagnose) | Gemonteerde componenten volgens diagnose |
| Last Ride Start Odometer | sensor / km | Start-kilometerstand van de laatste rit |
| Last Ride Max Altitude | sensor / m | Maximale hoogte van de laatste rit |

> **⚠️ Belangrijke opmerking over deze entiteiten:** Er is **geen aanvullende Bosch-gegevensdeling nodig** – ze vallen onder de normale autorisatie. Ze staan echter vaak op "onbekend", omdat de onderliggende gegevens alleen in bepaalde gevallen bestaan:
> - De **diefstallocatie** (`Last Known Location`) wordt **alleen gevuld wanneer er diefstal is gemeld** – er is **geen continue locatievolging**.
> - De **accugezondheid (State of Health)** en de gemeten capaciteit zijn **pas beschikbaar na een capaciteitsmeting bij de dealer**.
> - **Serviceboek- en klantrapportgegevens** (Last Service, levensduurwaarden) verschijnen alleen als zulke records bestaan.
>
> Anders tonen deze entiteiten "onbekend" – dat is **zo bedoeld** (by design).

---

### Licentie

MIT-licentie – zie [LICENSE](LICENSE) voor details.

### Credits

Gemaakt door [Volker Hauffe](https://github.com/Xunil99).

Deze integratie gebruikt de officiële [Bosch eBike Data Act API](https://portal.bosch-ebike.com/data-act).
