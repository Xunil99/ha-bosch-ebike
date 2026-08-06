# Bosch eBike Smart System – integrace pro Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

> [Deutsch](README.md) | [English](README.md#english) | [Nederlands](README.nl.md) | [Français](README.fr.md) | [Italiano](README.it.md) | [Español](README.es.md) | **Čeština**

> **⚠️ Poznámka k aktualizaci (od v1.17.6):** Složka integrace se nyní jmenuje `ha_bosch_ebike` (dříve `bosch_ebike`). Tvoje instalace, zařízení i nastavení zůstávají beze změny. Pokud po aktualizaci přes HACS existují v `config/custom_components/` **obě** složky, smaž jednorázově tu starou `bosch_ebike` a restartuj Home Assistant.

> ### ⚠️ Regionální požadavek
> Tato integrace funguje **výhradně s účtem Bosch SingleKey ID registrovaným v rámci EU**. Používá oficiální Bosch Data Act API, jehož dostupnost je omezena na účty z EU. Účty z jiných regionů koncový bod API odmítne a integrace se pak nedokáže přihlásit.

> ### 🔌 Skutečná živá data přes Bluetooth (smart system v19+)
> Tento repozitář obsahuje kromě integrace pro HACS také **ESPHome BLE bridge**, který z ESP32 udělá bridge k **Bosch eBike Live Data Interface**. Díky tomu proudí stav nabití baterie, rychlost, najeté kilometry a spol. v reálném čase do Home Assistantu.
>
> 🚀 **Flashování bez instalace ESPHome**: připoj ESP32 (nebo ESP32-C3, např. „C3 Mini“) přes USB, otevři v prohlížeči Chrome / Edge **[https://xunil99.github.io/ha-bosch-ebike/](https://xunil99.github.io/ha-bosch-ebike/)** a klikni na *Install*. Instalátor rozpozná čip automaticky a nahraje správný firmware. Nastavení Wi-Fi proběhne ve stejném kroku v prohlížeči. Kompletní návod (DE/EN) včetně párování přes aplikaci Flow: [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome).

> ### 🖥️ Volitelně: 4,3" displej pro datum, počasí a živá data
> Vedle bridge je nyní k dispozici i druhý firmware pro **Guition/Sunton JC4827W543** (ESP32-S3 se 4,3" IPS dotykovým displejem). Načítá senzory bridge z Home Assistantu a zobrazuje datum, čas, počasí a data až dvou kol současně. Stávající uživatelé bridge nemusí nic měnit, displej je čistě doplněk. Návod k nastavení: [`esphome/DISPLAY.md`](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/DISPLAY.md).

---

## Čeština

### Popis

Tato vlastní integrace propojí tvůj **Bosch eBike Smart System** s Home Assistantem. Načítá data o kole (najeté kilometry, motohodiny, nabíjecí cykly baterie) a data o aktivitách (poslední jízda, rychlost, kadence, výkon) přímo z oficiálního Bosch Data Act API.

**Podporována jsou pouze kola s Bosch Smart System** (nikoli systém Classic Line).

### 🆕 eBike System 2 (BES2) – NOVÉ, momentálně v testování (alpha)

Integrace nyní podporuje **také** starší **eBike System 2 (BES2)**, nejen Smart System. Stávající uživatelé Smart Systemu tím **nejsou nijak dotčeni**: systém se volí **pro každou položku integrace zvlášť**, tvoje stávající instalace zůstává beze změny.

> **⚠️ Poznámka:** Podpora BES2 je **nová a momentálně v testování (alpha)**.

**Instalace (rozdíl oproti Smart System):** na portálu Bosch Data Act ([portal.bosch-ebike.com/data-act](https://portal.bosch-ebike.com/data-act)) se majitelé BES2 přihlašují přes **„Bosch eBike Connect user? Log in here“** (identita eBike Connect), **nikoli** přes SingleKey ID, a jako obvykle vytvoří App / Client ID. Pro **udělení souhlasu se sdílením dat** ale běžný vstupní bod flow.bosch-ebike.com u účtů eBike Connect často nefunguje – místo něj potřebuješ tento přímý odkaz, který tě přihlásí jako uživatele eBike Connect a zavede rovnou na stránku Data Act: [flow.bosch-ebike.com/login?returnTo=%2Fdata-act&kc_idp_hint=ebike-connect](https://flow.bosch-ebike.com/login?returnTo=%2Fdata-act&kc_idp_hint=ebike-connect). Tam aktivuj přepínač pro Client vytvořený v předchozím kroku. Při přidávání integrace do Home Assistantu zvol v **prvním kroku (volba systému)** možnost **eBike System 2** a následně zadej Client ID.

**Menší rozsah dat než u Smart Systemu.** BES2 poskytuje méně údajů:

- **K dispozici:** jízdy (vzdálenost, doba trvání, prům./max. rychlost, kadence, výkon, převýšení, kalorie, volitelně tepová frekvence přes detaily aktivity), souhrny a GPS trasa na mapě.
- **Není k dispozici:** najeté kilometry, dojezd podle režimu podpory, příští servisní prohlídka, nabíjecí cykly baterie / Wh za celou životnost / State of Health, krádež/poloha a živý BLE bridge.

Tyto entity pro kola s BES2 jednoduše neexistují.

### Funkce

- **Data o kole:** najeté kilometry, motohodiny (celkem a s podporou), maximální rychlost podpory, aktivní režimy podpory, rychlost asistence při vedení, najeté kilometry do příští servisní prohlídky
- **Data o baterii:** dodané Wh za celou životnost, nabíjecí cykly (celkem, na kole, externě)
- **Poslední jízda:** vzdálenost, doba trvání, průměrná/maximální rychlost, kadence (prům./max.), výkon jezdce ve wattech (prům./max.), spotřeba kalorií, převýšení (stoupání/klesání), název, datum
- **Souhrnné statistiky:** počet jízd, celková vzdálenost, celkový čas jízdy, celkové kalorie, celkové převýšení, průměry rychlosti/výkonu/kadence přes všechny jízdy
- **Export GPS tras:** export všech jízd jako soubory GPX (s rychlostí, kadencí a výkonem jako Garmin TrackPointExtension)
- **Interaktivní zobrazení mapy:** vlastní Lovelace karta s GPS trasami, barevným rozlišením podle rychlosti, výběrem data a navigací prev/next
- **3D mapa s chase-cam, časovým posuvníkem a stíny budov:** vlastní Lovelace karta (`bosch-ebike-3d-map-card`) pro detailní zobrazení jízdy s 3D budovami, kamerou sledující kolo zezadu, poměrnou rychlostí přehrávání (standardně 60× reálný čas) a vrženými stíny podle polohy slunce v čase jízdy (MapLibre + OpenFreeMap, zdarma a bez API klíče)
- **Dashboardová karta s fotkou kola, živými daty a ovládáním nabíjení:** vlastní Lovelace karta (`bosch-ebike-dashboard-card`) s vlastní fotkou kola, najetými kilometry, stavem baterie, stavem nabíjení, volitelným senzorem nabíjecího výkonu, posuvníkem cílového SoC a tlačítky start/stop přes chytrou zásuvku
- **Automatická obnova tokenu** pomocí refresh tokenu
- **Interval dotazování 10 minut** (při prvním spuštění se naimportují všechny jízdy)

### 🆕 Živá data přes Bluetooth (ESPHome bridge)

Kromě cloudové integrace najdeš v podsložce [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome) **ESPHome external component**, která z ESP32 udělá bridge k **Bosch eBike Live Data Interface (LDI)** (BLE, smart system v19+). Díky tomu proudí do HA hodnoty v reálném čase (rychlost, SoC baterie, kadence, výkon jezdce, najeté kilometry, stav světel, stav zámku, …) jako ESPHome senzory – jako doplněk k cloudové historii jízd.

🚀 **Nejrychlejší cesta bez znalosti ESPHome**: připoj ESP32, přejdi v Chrome / Edge na **https://xunil99.github.io/ha-bosch-ebike/** a klikni na *Install*. Nahrání firmwaru i nastavení wifi proběhne kompletně v prohlížeči – žádná instalace ESPHome není potřeba.

Kompletní návod: **[esphome/README.md](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/README.md)**

> **Související projekty:** Nemáš po ruce ESP32, ale máš Raspberry Pi? [ha-bosch-ebike-pibridge](https://github.com/possm/ha-bosch-ebike-pibridge) od [@possm](https://github.com/possm) je komunitní port v Pythonu (BlueZ + MQTT), který běží přímo na Pi, podporuje **dvě kola současně** a přináší vlastní webový dashboard.

#### Využití živých hodnot pro přesný výpočet jízdy (volitelné, od v1.10.0)

Když bridge běží, můžeš v **nastavení integrace** (HA → *Nastavení → Zařízení a služby → Bosch eBike → Konfigurovat*) zadat dva senzory:

- **Živý senzor najetých kilometrů** (např. `sensor.ebike_odometer_live`)
- **Živý senzor stavu baterie** (např. `sensor.ebike_battery_soc_live`)

Pokud jsou nastavené, integrace si při každé aktualizaci jízdy vyžádá od HA recorderu hodnoty těchto senzorů na začátku a na konci jízdy. Z rozdílů pak vyplývá:

- **Přesná vzdálenost jízdy** (rozdíl najetých kilometrů místo cloudového výpočtu z GPS).
- **Přesná spotřeba baterie ve Wh** ((SoC start − SoC konec) × kapacita baterie / 100).

Tyto hodnoty nahrazují dřívější odhad ze snapshotů v senzorech *Last Ride Distance*, *Battery Consumption Wh*, *spotřeba %* atd. Pokud na začátku nebo na konci jízdy nebyl v tolerančním okně (±5 min) k dispozici žádný BLE vzorek (kolo mimo dosah), integrace se transparentně vrátí ke staré cloudové logice. Obě pole jsou volitelná a nezávislá – klidně můžeš nastavit jen jedno z nich.

### Předpoklady

1. eBike s **Bosch Smart System** (např. Performance Line CX, SX atd.)
2. Účet **Bosch SingleKey ID** ([singlekey-id.com](https://singlekey-id.com))
3. Přístup k **portálu Bosch eBike Flow** ([portal.bosch-ebike.com](https://portal.bosch-ebike.com))

---

### Návod krok za krokem

#### Předpoklady

1. Účet **Bosch SingleKey ID** – v případě potřeby si ho založ na [singlekey-id.com](https://singlekey-id.com)
2. Tvoje eBike musí být spárované s aplikací **Bosch eBike Flow** ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))

---

#### Krok 1: registrace aplikace v portálu Bosch Data Act

1. Přejdi na [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Přihlas se svým **SingleKey ID**
3. Klikni na **„Vytvořit aplikaci“**
4. Vyplň formulář:
   - **Název aplikace:** např. `Home Assistant`
   - **Confidential client:** nechat **VYPNUTÉ**

   > **Pozor, snadno se zamění:** následující dvě pole jsou obě adresy `my.home-assistant.io` a na první pohled vypadají podobně. **Pořadí v Bosch formuláři se může od této tabulky lišit** - každou hodnotu vyplň do pole s **odpovídajícím názvem**, ne podle pozice. Pokud je zaměníš, dostaneš při kliknutí na „Service aktivieren“ hlášku "Invalid parameters are given", nebo od Bosch při autorizaci v Home Assistant "Invalid parameter: redirect_uri".

   | Pole v Bosch formuláři | Hodnota | K čemu |
   |---|---|---|
   | **Redirect URI** | `https://my.home-assistant.io/redirect/oauth` | Návratová adresa **po** přihlášení u Bosch (OAuth callback) - musí být přesně tato, jde o oficiální přesměrování „My Home Assistant“, díky kterému Home Assistant přihlášení automaticky dokončí. |
   | **Login URL** | `https://my.home-assistant.io/redirect/config_flow_start/?domain=ha_bosch_ebike` | Odkaz, který otevře **„Service aktivieren“** v eBike Manageru, aby se instalační flow **spustil** přímo ve tvé instanci Home Assistant. |

   > **Pozor:** Integrace „My Home Assistant“ musí být v HA zapnutá (což je výchozí stav). Pokud jsi ji vypnul, vyplň do pole **Redirect URI** místo toho `https://<tvoje-HA-URL>/auth/external/callback`.

5. Po vytvoření dostaneš **Client-ID** (formát `euda-xxxxxxxx-...`).

#### Krok 2: uložení Client-ID

Zkopíruj si **Client-ID** – za chvíli ho budeš potřebovat.

#### Krok 3: instalace integrace do Home Assistant

Nainstaluj integraci přes **HACS** (viz sekce níže) a restartuj Home Assistant. Teprve potom může odkaz na uvolnění dat z eBike Manageru otevřít instalační flow.

#### Krok 4: nastavení integrace (přes „Service aktivieren“)

1. Otevři **Moje eBike → eBike Manager** a v něm část **Data Act** (dostupné přes **[flow.bosch-ebike.com](https://flow.bosch-ebike.com)**).
2. U položky pro aplikaci vytvořenou v kroku 1 klikni na **„Service aktivieren“**. Tím se automaticky otevře tvoje instance Home Assistant (přes Login URL nastavenou v kroku 1).
3. V Home Assistant se otevře instalační flow: **vlož Client-ID**, **Autorizovat**, přihlas se u Bosch a potvrď.
4. Integrace je teď nastavená - **ale entity ještě chybí**. To je normální, pokračuj krokem 5.

> **Pozor:** Integraci můžeš přidat i ručně (**Nastavení → Zařízení a služby → Přidat integraci → „Bosch eBike“**, vložit Client-ID, Autorizovat). Žádný localhost a žádné kopírování a vkládání: Home Assistant vyřídí návrat z přihlášení přes přesměrování „My Home Assistant“, access a refresh token se pak obnovují automaticky.

#### Krok 5: aktivace sdílení dat pro jednotlivá kola

Bez aktivovaného uvolnění dat odpovídá API chybou **403 Forbidden** a žádné entity se neobjeví.

1. Vrať se do **Moje eBike → eBike Manager → Data Act**.
2. Tam aktivuj **přepínač (toggle)** pro klienta vytvořeného v kroku 1 - uvolnění platí **pro každé kolo zvlášť**. Při aktivním uvolnění se zobrazení změní na **„Service deaktivieren“**.
3. V Home Assistant znovu načti integraci **Bosch eBike** (**⋮ → Znovu načíst**). Poté jsou k dispozici **všechny entity**.

> Pokud hned po aktivaci dostaneš ještě 403 nebo entity chybí: počkej pár minut (uvolnění se propisuje na straně serveru) a načti integraci znovu.

#### Krok 6: nastavení zobrazení mapy (volitelné)

Integrace obsahuje interaktivní Lovelace kartu pro zobrazení tvých GPS tras.

**Krok A: registrace resource**

> **Poznámka:** Od verze 1.16.27 se tento resource registruje **automaticky**, jakmile je Home Assistant plně nastartovaný – bezpečně, bez změny jiných existujících resources (chybná varianta náchylná ke ztrátě dat z dřívějších verzí byla nahrazena). **Normálně tedy nemusíš dělat vůbec nic.** Jen pokud se karta přesto zobrazí jako "Custom element doesn't exist" (např. protože spravuješ resources v YAML režimu), přidej ji jednorázově ručně, jak je popsáno níže.

1. Přejdi do **Nastavení → Dashboardy**
2. Klikni vpravo nahoře na **menu ⋮** → **Resources**
3. Klikni na **+ Přidat resource** (vpravo dole)
4. Zadej následující:
   - **URL:** `/ha_bosch_ebike/bosch-ebike-map-card.js`
   - **Typ resource:** JavaScript modul
5. Klikni na **Vytvořit**

**Krok B: přidání karty na dashboard**

1. Otevři požadovaný dashboard
2. Klikni vpravo nahoře na **tužku ✏️** (režim úprav)
3. Klikni na **+ Přidat kartu**
4. Sroluj úplně dolů a zvol **Ručně** (zadání YAML)
5. Vlož následující kód:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 400
   ```
6. Klikni na **Uložit**

> **Tip:** Výšku (height) můžeš upravit (200–1000 pixelů). Doporučení: 400 pro chytré telefony, 500 pro desktop.

**Karta zobrazuje:**
- GPS trasu s barevným rozlišením podle rychlosti (modrá → zelená → žlutá → červená)
- Startovní marker (zelený) a cílový marker (červený)
- Informace o jízdě (vzdálenost, doba trvání, průměrná/max. rychlost, převýšení, kalorie)
- Tlačítka **◀ Prev / Next ▶** a **výběr data** pro listování všemi jízdami
- **Tlačítko ▶ Chase-cam** otevře zobrazenou jízdu v celoobrazovkovém překryvu s plným 3D zobrazením mapy (2D / 3D / satelit, posuvník, přepínač fixace severu, celá obrazovka). Zavřeš ho tlačítkem X nebo klávesou Escape.

> **Poznámka:** Pokud se karta po aktualizaci nezobrazuje správně, vyprázdni cache prohlížeče pomocí `Ctrl+Shift+R` (hard reload).

> **HACS aktualizace karet:** Všechny čtyři Lovelace karty (Map, Heatmap, Calendar, Dashboard) jsou v jednom JS souboru (`bosch-ebike-map-card.js`) a aktualizují se automaticky spolu s integrací. Po aktualizaci verze z HACS proveď hard reload cache prohlížeče, jinak nemusí výběr karet novou kartu ještě nabídnout.

#### Instalace přes HACS (alternativa)

1. Otevři HACS v Home Assistant
2. Klikni na **„Custom repositories“** (tři tečky vpravo nahoře)
3. Přidej URL repozitáře: `https://github.com/Xunil99/ha-bosch-ebike`
4. Kategorie: **Integrace**
5. Nainstaluj integraci a restartuj Home Assistant

---

### Více kol nebo účtů

Integrace podporuje jak více účtů, tak více kol na jeden účet.

**Více účtů Bosch** (např. jedno kolo pro každého člena rodiny s vlastním SingleKey ID):
1. Pro každý účet vytvoř v portálu Bosch Data Act vlastní registraci aplikace s vlastním Client-ID
2. Přidej integraci vícekrát (**Nastavení → Zařízení a služby → + Přidat integraci → Bosch eBike**) a pokaždé zadej jiné Client-ID
3. Každá instance má vlastní senzory a jízdy

**Více kol pod jedním účtem** (např. dvě kola se stejným SingleKey ID):
- Integrace automaticky vytvoří vlastní senzory pro každé kolo (pohonná jednotka, baterie, servis atd.).
- Jízdy se automaticky přiřazují ke správnému kolu pomocí heuristiky (porovnání stavu `odometer` konkrétního kola s hodnotou `startOdometer + distance` dané jízdy).

**Filtr v kartě:** Jakmile existuje více než jeden účet a/nebo více než jedno kolo, zobrazí karta Lovelace nad seznamem automaticky dvě výběrová pole:
- **Účet** (viditelné pouze při více účtech)
- **Kolo** (viditelné pouze při více kolech)

Výběr filtruje zobrazené jízdy živě; řazení funguje jako obvykle v rámci vyfiltrovaného výsledku.

#### Trvalé svázání karty s účtem nebo kolem

Pokud má karta trvale zobrazovat právě jeden účet nebo jedno kolo (např. abys mohl postavit dvě karty vedle sebe pro porovnání), vyplň v konfiguraci karty `account_id` a/nebo `bike_id`. Příslušná rozbalovací nabídka se pak skryje a filtr je uzamčen.

ID můžeš jednoduše vybrat z rozbalovacích nabídek v editoru (vpravo nahoře při úpravě karty) – ruční dohledávání není nutné. Volitelně může `title` přepsat záhlaví karty:

```yaml
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Moje kolo"
    account_id: <config_entry_id_account_a>
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Kolo partnera"
    account_id: <config_entry_id_account_b>
```

Obě karty pak vždy zobrazují jízdy uzamčeného účtu a pomocí výběru data/řazení lze v historii jízd listovat nezávisle na sobě – ideální třeba pro přímé porovnání dvou jízd absolvovaných ve stejný den. Stejné volby fungují i v `bosch-ebike-heatmap-card`.

### Body zájmu podél trasy

Na mapě je v ovládacích prvcích přepínač 📍. Když je aktivní, spustí se na pozadí dotaz na Overpass API, který najde následující body podél trasy (max. ~500 m od projeté cesty):

- 🔌 **Nabíjecí stanice** (`amenity=charging_station`)
- 🛠️ **Cykloservisy** a opravárenské stojany (`shop=bicycle`, `amenity=bicycle_repair_station`)
- 💧 **Pitná voda** (`amenity=drinking_water`)
- 🚻 **Toalety** (`amenity=toilets`)
- 🍽️ **Občerstvení** (restaurace, kavárny, pivní zahrádky, rychlá občerstvení — `amenity=restaurant/cafe/biergarten/fast_food`)

Klikni na značku → vyskočí okno s názvem, otevírací dobou/adresou/webem (pokud jsou v OSM známé) a odkazem na OpenStreetMap. Na jednu jízdu se zobrazí maximálně 100 značek; výsledky se ukládají do mezipaměti v localStorage prohlížeče.

### Připomínky údržby

#### Vlastní nastavení servisní prohlídky

Pro každé kolo existují dvě upravitelné entity:

- **`date.<bike>_service_due_date`** – datum, ke kterému je potřeba další servisní prohlídka
- **`number.<bike>_service_due_odometer`** – stav kilometrů, při kterém je potřeba další servisní prohlídka

Dokud sám nic nevyplníš, zobrazují obě hodnotu z Bosch API (pokud tam je k dispozici), jinak nic. Změny těchto entit přepíšou hodnoty od Bosche a použijí se pro připomínky servisu.

Pro vrácení zpět je pro každé kolo k dispozici tlačítko **`button.<bike>_reset_service_due`** („Reset Service Due“): to smaže obě ručně zadané hodnoty, načež znovu platí hodnota od Bosche (nebo nic, pokud ji Bosch nedodává). U stavu kilometrů stačí i zadání `0`. Tlačítko je nutné, protože výběr data v Home Assistant nezná „prázdno“.

#### Vlastní položky údržby

Kromě servisní prohlídky dodávané Boschem (`Next Service Date`/`Next Service Odometer`) si můžeš vytvořit libovolné vlastní položky údržby – např. výměna řetězu každých 3000 km, prohlídka každých 365 dní. Pro každé kolo se vytvoří senzor `Maintenance Items Due`; jeho hodnotou je počet položek, které jsou brzy splatné nebo už po termínu, atribut `items` obsahuje všechny podrobnosti (zbývající kilometry, zbývající dny).

**Vytvoření položky:** **Vývojářské nástroje → Akce**, zavolej službu `bosch_ebike.add_maintenance` s:
- `bike_id` (z atributu senzoru)
- `name` (např. „Výměna řetězu“)
- `interval_km` a/nebo `interval_days`

**Označení položky za dokončenou:** služba `bosch_ebike.complete_maintenance` s `bike_id` a `item_id` (z atributu senzoru). Nastaví datum a stav kilometrů zpět na aktuální hodnoty.

**Smazání položky:** služba `bosch_ebike.remove_maintenance`.

**Události pro automatizace:** Při dosažení prahové hodnoty (výchozí: 30 dní / 200 km před termínem) se vyvolají události HA:
- `ha_bosch_ebike_service_due_soon` / `ha_bosch_ebike_service_overdue` (pro servis od Bosche)
- `ha_bosch_ebike_maintenance_due_soon` / `ha_bosch_ebike_maintenance_overdue` (pro vlastní položky)

Díky tomu si můžeš postavit třeba push oznámení nebo světelnou připomínku.

**Událost při nové jízdě (od v1.19.36):** Jakmile se dokončená jízda poprvé objeví při některém z pravidelných dotazů, vyvolá se `ha_bosch_ebike_new_activity` – přesně jednou za jízdu. U jízd, které už existovaly při prvním nastavení integrace, se to záměrně **nestane**, takže novou automatizaci nezahltí stovky starých jízd.

Data události jsou plochá a rovnou v jednotkách, které používají senzory, šablona tedy nemusí nic přepočítávat:

| Pole | Jednotka | Obsah |
|---|---|---|
| `bike_id` | - | Kolo, ke kterému byla jízda přiřazena (u účtů s více koly může být `null`) |
| `activity_id`, `title`, `start_time` | - | Identifikátor, název a čas začátku jízdy |
| `distance_km` | km | Vzdálenost |
| `duration_min` | min | Čas jízdy bez přestávek |
| `average_speed`, `max_speed` | km/h | Průměrná a nejvyšší rychlost |
| `elevation_gain` | m | Nastoupané převýšení |
| `calories` | kcal | Spálené kalorie |
| `has_tricks` | - | `true`, pokud Bosch k jízdě dodává data funkce Trick Check |
| `tricks` | - | Kompletní hodnoty funkce Trick Check, jinak `null` |

Kterékoli pole může být `null`, pokud ho Bosch pro danou jízdu nedodá. Důležité: Bosch zveřejní jízdu až ve chvíli, kdy ji nahraje aplikace – událost tedy přijde, jakmile se jízda dostane do cloudu, ne v okamžiku, kdy sesedneš z kola.

### Odhad dojezdu

Pro každé kolo existují dva senzory, které **odhadují** dojezd — na základě
tvé skutečné spotřeby (vážený průměr podle vzdálenosti za posledních
~500 km historie jízd):

- **`Estimated Range (Full Battery)`** — odhadovaný dojezd s plnou
  baterií (kapacita baterie ÷ průměrná spotřeba ve Wh/km). Čistě z cloudových
  dat, vždy k dispozici.
- **`Estimated Range (Current)`** — odhadovaný zbývající dojezd
  (aktuální stav nabití × kapacita ÷ průměrná spotřeba). Objeví se pouze
  tehdy, když je v možnostech integrace propojeno **živý senzor stavu nabití**
  z ESPHome bridge; aktualizuje se okamžitě při změnách SoC.

> ⚠️ **Jde o odhad, nikoli o záruku.** Skutečný dojezd silně závisí
> na režimu podpory, topografii, větru, teplotě a stavu baterie.
> Základ výpočtu si můžeš prohlédnout v atributech čidla
> (`wh_per_km`, `tours_used`, `window_km`). Dokud jsou k dispozici údaje
> o spotřebě z méně než 3 jízd nebo z méně než 30 km, zůstávají čidla prázdná.

### Souhrn nabíjení

Cloud od Bosche pojem „nabíjení“ vůbec nezná – hlásí jen stav nabití k okamžiku poslední synchronizace. Kdo ale provozuje [ESPHome LDI bridge](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome), ten má **živý stav nabití**, a z něj se dá celý nabíjecí cyklus zrekonstruovat.

Pokud je v nastavení integrace pro kolo zadán živý senzor SoC, vznikne pro něj senzor **`Last Charge Energy`** (Wh). Jeho hodnotou je energie dodaná při posledním dokončeném nabíjení, vypočtená z nárůstu stavu nabití a z nastavené kapacity baterie. Jako atributy jsou k dispozici:

| Atribut | Obsah |
|---|---|
| `start_soc`, `end_soc`, `soc_delta` | Stav nabití na začátku a na konci a rozdíl mezi nimi (%) |
| `energy_wh` | Dodaná energie ve Wh (`null`, pokud není známá kapacita) |
| `duration_min` | Doba nabíjení v minutách |
| `started_at`, `ended_at` | Začátek a konec jako časové značky ISO 8601 |
| `signal_gaps` | Kolikrát během nabíjení vypadl živý senzor |
| `in_progress` | `true`, dokud nabíjení probíhá |

**Proč to přežije výpadky spojení:** BLE bridge kolo tu a tam ztratí – to je normální stav, ne výjimka (viz issue #68). Výpadek proto nabíjení **nikdy** neukončí, jen se započítá do `signal_gaps`. Jinak by se každé krátké vyjetí z dosahu hlásilo jako dokončené nabití o 20 %.

Nabíjení se považuje za ukončené, jakmile stav nabití buď klesne alespoň o 1 % (na kole se zase jezdí), nebo 30 minut nestoupá (nabíječka je hotová nebo odpojená). Hlásí se vždy **nejvyšší dosažená hodnota**, ne poslední naměřená – baterie, která dosáhne 100 % a pak samovybíjením klesne na 99 %, byla nabita na 100 %. Nabíjení pod 3 % se vůbec nezveřejňují, aby krátké dobití na chodbě nepřepsalo skutečné noční nabíjení.

Senzor přežije restart Home Assistantu: poslední dokončené nabíjení se obnoví. Nabíjení, které v okamžiku restartu *probíhalo*, se záměrně nerekonstruuje. Funguje i s eBike System 2, protože se vyhodnocuje výhradně živý signál.

#### V energetickém dashboardu

Navíc vzniká senzor **`Total Charged Energy`**, průběžně rostoucí počítadlo přes všechna dokončená nabíjení. Přidat ho můžeš v **Nastavení → Dashboardy → Energie → Jednotlivá zařízení** – eBike se pak objeví s vlastními náklady vedle domácí spotřeby.

> ⚠️ **Jde o energii, která jde do baterie, ne o energii odebranou ze zásuvky.** Počítá se z nárůstu stavu nabití a z nastavené kapacity baterie. Nabíječka ztratí zhruba 10 až 15 procent, skutečně účtovaná elektřina je tedy vyšší. Kdo má na nabíječce měřicí chytrou zásuvku, měl by do energetického dashboardu zadat **ji** místo tohoto senzoru, protože měří přesně to, co se účtuje.

Stávající senzor `Wh Lifetime` se k tomu mimochodem nehodí, i když ho Home Assistant nabízí: počítá energii **dodanou** baterií, tedy jízdu, ne nabíjení.

### Karta plánovače tras (BRouter)

Karta `bosch-ebike-routeplanner-card` plánuje cyklotrasy přímo v
dashboardu — na základě open-source routeru [BRouter](https://brouter.de):

```yaml
type: custom:bosch-ebike-routeplanner-card
height: 480
```

- **Trasové body kliknutím** na mapu (start, cíl, libovolný počet
  mezibodů; tažení značky = přesunutí, kliknutí = odstranění)
- **Profily:** Trekking, Silniční kolo, MTB, Nejkratší
- **Body zájmu podél trasy** (přepínač 📍): nabíjecí stanice, cykloprodejny/
  servisy, pitná voda, toalety a **občerstvení** (restaurace, kavárny,
  pivní zahrádky) — data z OpenStreetMap/Overpass
- **Výsledek:** vzdálenost, stoupání/klesání, doba jízdy, **odhadovaná spotřeba**
  (tvoje průměrná spotřeba z odhadu dojezdu × vzdálenost)
- **Kontrola baterie:** semaforový indikátor, který ukazuje, zda je trasa
  zvládnutelná s aktuálním stavem nabití (vyžaduje propojené živé čidlo stavu
  nabití) — stejně jako u čidel dojezdu jde o **odhad**, ne o záruku
- **Výškový profil** jako graf pod mapou
- **Export GPX** naplánované trasy (importovatelný do Garmin Connect,
  Komoot, aplikace Flow a dalších)
- **Ukládání a načítání tras:** naplánované trasy ulož pod vlastním názvem
  (uloženo v Home Assistant, dostupné na všech tvých zařízeních), přes
  seznam 📁 je znovu načti, dál uprav nebo smaž

Možnosti: `title`, `height`, `brouter_url` (vlastní instance BRouteru místo
brouter.de), `entity` (senzor dojezdu), `soc_entity` (živý stav nabití).

> **Soukromí:** Souřadnice trasových bodů se pro výpočet trasy odesílají na
> nakonfigurovaný BRouter server — standardně na veřejný server `brouter.de`
> financovaný z darů. Pokud to nechceš, provozuj BRouter sám (Docker) a
> zadej URL do `brouter_url`.

### Karta s heatmapou – všechny jízdy na jedné mapě

Druhá varianta mapy `bosch-ebike-heatmap-card` překrývá všechny jízdy z výběru jako poloprůhledné čáry. Rozbalovací filtry pro období (30 dní / 3 měsíce / 12 měsíců / vše), účet a kolo. Pod nimi stavový řádek s počtem jízd a kilometrů ve výběru.

```yaml
type: custom:bosch-ebike-heatmap-card
height: 600
```

První zobrazení může chvíli trvat – pro každou dosud nenačtenou jízdu se provede další API volání (s limitem souběžnosti). Trasy se ukládají do mezipaměti na straně serveru; další vyvolání jsou okamžitá.

### Kalendářová karta – heatmapa jízdních dnů ve stylu GitHubu

Karta `bosch-ebike-calendar-card` zobrazuje roční heatmapu ve stylu přehledu příspěvků na GitHubu: 7 řádků pro dny v týdnu, jeden sloupec na kalendářní týden, každá buňka je obarvená podle najetých kilometrů v daný den. Při najetí myší se zobrazí tooltip s datem, počtem jízd a vzdáleností. Řádek se statistikami pod tím ukazuje aktivní dny, jízdy a celkovou vzdálenost ve zvoleném období.

```yaml
type: custom:bosch-ebike-calendar-card
```

Nahoře jsou rozbalovací filtry pro období (12 měsíců / 24 měsíců / 5 let / vše), účet a kolo. Pevný filtr účtu nebo kola lze uzamknout přes YAML (stejné volby jako u mapové karty a heatmapy):

```yaml
type: custom:bosch-ebike-calendar-card
title: Volkerův cyklistický rok
account_id: 01HXYZ...
bike_id: bike-uuid-1
```

Barevné třídy podle dne: prázdný, 1-10 km, 10-25 km, 25-50 km, 50+ km. Barvy vycházejí z proměnných motivu HA; světlé motivy vypadají jako GitHub-light, v tmavém režimu se automaticky načte odpovídající tmavá paleta.

### 3D karta – sledování chase-cam s časovým posuvníkem a polohou Slunce

Karta `bosch-ebike-3d-map-card` je paralelní kartou vedle klasické 2D mapy. Startuje seznamem posledních jízd. Po kliknutí na jízdu se otevře 3D detailní zobrazení s MapLibre a bezplatnými vektorovými dlaždicemi OpenFreeMap: **kamera sleduje kolo ve third-person perspektivě** („chase-cam“), bearing se otáčí podle směru jízdy, pitch a zoom jsou konfigurovatelné. Při posouvání posuvníku se kamera natáčí s ním. Osvětlení mapy se přizpůsobuje poloze Slunce v čase dané jízdy.

```yaml
type: custom:bosch-ebike-3d-map-card
title: Jízda ve 3D
height: 540
default_pitch: 55      # sklon chase-cam
chase_zoom: 17         # cca 100 m výhledu dopředu
playback_speed: 60     # 60x realtime (1 hodina jízdy = 1 min přehrávání)
```

**Co karta zobrazuje:**

- Seznam jízd (výchozí zobrazení) s datem, názvem, vzdáleností a dobou trvání
- 3D chase-cam po kliknutí na jízdu, s extruzemi budov z OpenStreetMap
- Polyline trasy ve dvou vrstvách (glow + hlavní čára) pro dobrou čitelnost
- Značky startu a cíle plus modrá pulzující značka pozice, která představuje kolo
- Časový posuvník s časem startu a konce jízdy, lze jím posouvat; kamera se natáčí synchronně
- Tlačítko play/pauza pro zrychlené přehrávání (délka konfigurovatelná)
- Živé statistiky v pozici posuvníku: kumulativní vzdálenost, rychlost, nadmořská výška
- Časový a sluneční chip v překryvu ukazuje aktuální čas a fázi denního světla (noc, soumrak, zlatá hodina, denní světlo)
- **Vržené stíny budov** na zemi, promítnuté z azimutu a výšky Slunce v čase posuvníku. Stíny se zobrazují za denního světla, při nízkém slunci jsou delší (omezené na 400 m), v noci jsou skryté. Automatická aktualizace, když se kamera natočí do nové městské oblasti nebo se pohne posuvníkem.
- **Export videa** vpravo vedle posuvníku: tlačítko nahrávání spustí přehrávání od začátku jízdy a paralelně zapisuje obsah mapy jako video. Na konci jízdy následuje automaticky stažení souboru (cca 20-40 MB za minutu). Formát určuje prohlížeč: **MP4** v moderním Chrome (≥ 126) a Safari (≥ 14.4), jinak **WebM**. Kompletně v prohlížeči přes `canvas.captureStream()` + `MediaRecorder`; server HA s tím nemá nic společného.
- Tlačítko zpět vrací na seznam jízd

**Možnosti konfigurace karty:**

| Volba | Výchozí | Popis |
|---|---|---|
| `title` | "Bosch eBike 3D-Touren" | Nadpis |
| `height` | 540 | Výška mapy v pixelech |
| `default_pitch` | 55 | Sklon chase-cam (20-65°). 20 ≈ pohled z ptačí perspektivy, 65 ≈ first-person |
| `chase_zoom` | 17 | Zoom chase-cam (14-19). Vyšší = blíž, 17 ≈ 100 m výhledu dopředu |
| `chase_lookahead` | 30 | Vzdálenost look-ahead v metrech. Jak daleko před kolem leží cíl kamery. Menší = kolo výš v obraze. 0 = kamera vycentrovaná přímo na kolo. |
| `smooth_window` | 15 | Okno vyhlazování bearingu. Vyšší = plynulejší kamera, ale více ořezává zatáčky. 5 působí roztřeseně, 40 velmi pomalu |
| `track_smooth_window` | 2 | Vyhlazování pozice trasy pro dráhu kamery. 0 = vypnuto (surové GPS, může se třást), 2 = jemné (výchozí), 5+ může viditelně ořezávat zatáčky. Zobrazená čára trasy vždy ukazuje surové GPS |
| `playback_speed` | 60 | Násobič realtime u tlačítka play. 60 = 60× rychleji než skutečná jízda; hodinová jízda se přehraje za 1 minutu, třicetiminutová za 30 sekund |
| `animate_seconds` | — | Volitelné. Vynutí pevnou délku přehrávání (např. vždy 25 s), přepíše `playback_speed` |
| `show_date` | 1 | Zobrazit datový chip v překryvu (0 = vypnuto) |
| `show_time` | 1 | Zobrazit časový chip v překryvu (0 = vypnuto) |
| `show_sun` | 1 | Zobrazit chip s polohou Slunce v překryvu (0 = vypnuto) |
| `show_speed` | 1 | Zobrazit rychlost ve statistické liště dole (0 = vypnuto) |
| `show_distance` | 1 | Zobrazit kumulativní vzdálenost ve statistické liště (0 = vypnuto) |
| `show_elevation` | 1 | Zobrazit nadmořskou výšku (0 = vypnuto) |
| `stats_as_chips` | 0 | 1 = vzdálenost, rychlost a výška jako překryvné chipy vlevo nahoře místo dole ve statistické liště. 0 = klasický řádek statistik v ovládací liště (výchozí) |
| `account_id` | (prázdné) | Zafixovat na jeden účet, stejně jako u 2D karty |
| `bike_id` | (prázdné) | Zafixovat na jedno kolo |

Poznámka: skryté prvky překryvu automaticky chybí i ve staženém videu, protože nahrávání jednoduše zapisuje zobrazený obsah mapy.

**Závislosti a poznámky:**

- MapLibre GL se při prvním vyvolání donačte z unpkg.com (cca 800 KB gzipped, poté se ukládá do cache)
- OpenFreeMap dodává vektorové dlaždice bez API klíče a bez registrace
- Karta se načte teprve tehdy, když ji uživatel skutečně otevře. Stávající karty (Map, Heatmap, Calendar, Dashboard) tím nejsou ovlivněny.
- 3D vykreslování je plynulé na desktopu a moderních mobilních zařízeních. U velmi dlouhých tras (> 10 000 bodů) může na starších zařízeních zadrhávat.
- Pokrytí budovami v OSM je ve městech husté, na venkově řidší. Nejvíc z toho těží jízdy v městském prostředí.
- **Stíny terénu** (hory, kopce) záměrně nejsou zahrnuté. Vyžadovaly by DEM tile source (Maptiler s API klíčem, AWS Open Data SRTM nebo vlastní hostovaná výšková data) plus vlastní ray-casting v shaderu. Při dostatečném zájmu to lze doplnit v pozdější verzi.

### Dashboardová karta – fotka kola, živá data a ovládání nabíjení

Karta `bosch-ebike-dashboard-card` je zamýšlena jako kombinované zobrazení pro dashboard v obýváku: nahoře vlastní fotka kola, pod ní živé hodnoty z ESPHome bridge a volitelně ovládací prvky pro chytrou zásuvku, na které visí nabíječka. Všechna pole jsou volitelná – co není nakonfigurované, to karta úhledně skryje místo toho, aby vykreslila prázdný řádek.

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

**Co karta zobrazuje:**

- **Fotku kola** s vestavěným nahráváním v editoru karty (vybereš obrázek, karta si cestu zapíše sama). Alternativně klasicky přes `/config/www/` a odkaz `/local/soubor.jpg`. Zástupný obrázek s ikonou kola, dokud není nic nastaveno.
- **Dlaždici s najetými kilometry** a volitelně **vzdálenost poslední jízdy**, **nabíjecí výkon ve wattech**
- **Odhadovaný dojezd** jako dlaždici (`≈ 62 km`) — automaticky, jakmile existuje senzor „Odhadovaný dojezd (aktuální)“, nebo výslovně přes `range_entity`. Stejně jako senzory jde o **odhad**.
- **Stavové pilulky** pro stav nabíjení a procenta baterie
- **Posuvník cílového SoC**, který nastavuje hodnotu `input_number`
- **Tlačítka start a stop** s potvrzením dvojklikem u stopu (ochrana proti omylu)
- **Sloupec baterie** dole, který pod 35 % přeskočí do oranžové a pod 15 % do červené
- **Seznam údržby** s libovolným počtem volně definovatelných položek (mazání řetězu, servisní prohlídka, kontrola brzd, …) – v editoru na výběr z 11 návrhů nebo jako volný text. U každé položky spouštěč přes kilometrový nebo denní interval. V dashboardu se objeví automaticky, jakmile jsou splatné během nejbližších **500 km** nebo **30 dnů** – prošlé položky červeně, brzy splatné žlutě, seřazené podle naléhavosti. Zeleným tlačítkem s fajfkou u každého řádku označíš položku rovnou jako „hotovo“. **Ukládání v Home Assistant** (`/config/.storage/`, odděleně pro každé kolo) místo v cache prohlížeče: položky přežijí změnu prohlížeče, jsou synchronní na všech zařízeních a lze je spravovat i z automatizací přes služby HA `bosch_ebike.add_maintenance`, `bosch_ebike.update_maintenance`, `bosch_ebike.complete_maintenance` a `bosch_ebike.remove_maintenance`. V editoru karty vybereš kolo z rozbalovacího seznamu; příslušné položky údržby se objeví hned pod ním a ukládají se živě do backendu.
- **Srovnání CO₂ a nákladů na palivo** s autem: dvě dlaždice „celkem“ a „poslední jízda“ s ušetřenými kg CO₂ a €. V editoru vybereš srovnávací vozidlo ze 7 realistických přednastavení (nižší střední třída/střední třída/SUV, vždy benzin nebo diesel, plus elektromobil se zelenou elektřinou); volitelně můžeš přepsat cenu paliva/elektřiny za litr/kWh.

**Předpoklady pro plnou funkčnost:**

- Běžící **ESPHome Bosch eBike bridge** pro stav baterie, najeté kilometry a detekci nabíjení
- **Chytrá zásuvka** (Shelly, Tasmota, Fritz!DECT atd.), která se v HA objeví jako `switch.*` a volitelně jako senzor výkonu `sensor.*_power`, pokud chceš vidět start/stop a nabíjecí výkon
- `input_number.*` s rozsahem 0-100, pokud chceš používat posuvník cílového SoC

**Automatické zastavení při cílovém SoC** není záměrně implementované v samotné kartě, ale jako automatizace HA, abys mohl volně nastavit tolerance, časové podmínky nebo logiku pro více zařízení. Ukázková automatizace:

```yaml
alias: eBike auto-stop při cílovém SoC
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

### Články z Wikipedie podél trasy

Na Lovelace kartě je v ovládání mapy přepínač 📚. Když je aktivní, hledá karta podél projeté trasy každé 2 km blízké články z Wikipedie a zobrazuje je jako značky (i). Kliknutím se otevře malé vyskakovací okno s názvem, náhledovým obrázkem, krátkým popisem a odkazem na celý článek.

- **Jazyk** se řídí nastavením jazyka v HA; při prázdném výsledku se přejde na angličtinu
- **Maximálně 30 značek** na jízdu; husté oblasti se shlukují
- **Stav přepínače a výsledky** se ukládají do cache prohlížeče (`localStorage`); při změně jízdy se načtou čerstvá data
- **Poznámka k soukromí**: při aktivaci vrstvy se souřadnice opěrných bodů trasy odesílají do API Wikipedie; vrstva je ve výchozím stavu vypnutá

### Řešení problémů

| Problém | Řešení |
|---------|--------|
| Po nastavení se neobjeví žádné entity | Aktivuj přepínač sdílení dat v eBike Manageru (krok 5) |
| BES2: hlášen úspěch, ale 0 kol | Aktivuj sdílení dat přes odkaz pro eBike Connect výše |
| „Client not found“ při přihlašování | Použij „Service aktivieren“ v eBike Manageru (krok 4) a zkontroluj Client-ID na překlepy/mezery |
| „Invalid state“ / návrat se nezdařil | Je v HA zapnuté „My Home Assistant“? Redirect URI v portálu musí být `https://my.home-assistant.io/redirect/oauth` |
| „Invalid parameters are given“ při kliknutí na „Service aktivieren“, nebo „Invalid parameter: redirect_uri“ od Bosch při autorizaci | Nemáš prohozené Redirect URI a Login URL v portálu Bosch? Zkontroluj krok 1 - obojí jsou adresy `my.home-assistant.io`, které vypadají podobně; každá hodnota musí být v poli s odpovídajícím názvem |
| Najeté kilometry jsou nerealisticky vysoké | Odometr se dodává v metrech a automaticky se přepočítává na km |
| Chybí data o jízdách | Zkontroluj, zda je ve Flow portálu aktivní sdílení aktivit |
| Token nebyl přijat | Zkontroluj, zda je Client-ID zadané správně |

---

### Dostupné senzory

#### Senzory kola
| Senzor | Jednotka | Popis |
|--------|----------|-------|
| Odometer | km | Celkové najeté kilometry |
| Motor Total Hours | h | Celková doba běhu motoru |
| Motor Assist Hours | h | Doba běhu motoru s podporou |
| Max Assist Speed | km/h | Maximální rychlost podpory |
| Active Assist Modes | - | Seznam aktivních režimů podpory |
| Walk Assist Speed | km/h | Rychlost asistence při vedení |
| Next Service Odometer | km | Stav kilometrů při příštím servisu |
| Estimated Range (Full Battery) | km | Odhadovaný dojezd s plnou baterií (z prům. spotřeby, odhad!) |
| Estimated Range (Current) | km | Odhadovaný zbývající dojezd (vyžaduje živý SoC, odhad!) |
| Last Charge Energy | Wh | Energie posledního nabíjení (vyžaduje živý SoC) |
| Total Charged Energy | Wh | Součet všech nabíjení, pro energetický dashboard (vyžaduje živý SoC) |

#### Senzory baterie (pro každou baterii)
| Senzor | Jednotka | Popis |
|--------|----------|-------|
| Wh Lifetime | Wh | Dodané watthodiny za celou životnost |
| Charge Cycles | - | Celkový počet nabíjecích cyklů |
| Cycles On Bike | - | Nabíjecí cykly na kole |
| Cycles Off Bike | - | Nabíjecí cykly mimo kolo |

#### Senzory aktivit (poslední jízda)
| Senzor | Jednotka | Popis |
|--------|----------|-------|
| Last Ride Title | - | Název jízdy |
| Last Ride Date | - | Datum/čas |
| Last Ride Distance | km | Vzdálenost |
| Last Ride Duration | min | Doba jízdy (bez zastávek) |
| Last Ride Avg/Max Speed | km/h | Průměrná/maximální rychlost |
| Last Ride Avg/Max Cadence | rpm | Kadence |
| Last Ride Avg/Max Rider Power | W | Výkon jezdce |
| Last Ride Calories | kcal | Spálené kalorie |
| Last Ride Elevation Gain/Loss | m | Převýšení (stoupání/klesání) |

#### Celkové statistiky (přes všechny jízdy)
| Senzor | Jednotka | Popis |
|--------|----------|-------|
| Total Rides | - | Počet jízd |
| Total Distance (Activities) | km | Celková vzdálenost všech jízd |
| Total Ride Duration | h | Celková doba jízdy |
| Total Calories | kcal | Celkem spálené kalorie |
| Total Elevation Gain | m | Celkové převýšení |
| Avg Speed (All Rides) | km/h | Průměrná rychlost přes všechny jízdy |
| Avg Rider Power (All Rides) | W | Průměrný výkon jezdce |
| Avg Cadence (All Rides) | rpm | Průměrná kadence |

#### Tlačítka
| Tlačítko | Popis |
|----------|-------|
| Import All GPS Data | Exportuje GPS trasy všech jízd jako soubory GPX |
| Import Latest GPS Data | Exportuje GPS trasu poslední jízdy jako GPX |

> **Místo uložení:** Exportované soubory GPX se ukládají lokálně do konfiguračního adresáře Home Assistant:
> ```
> /config/bosch_ebike_gps/
> ```

#### 🆕 Rozšířené entity Data Act (od v1.18.0)

Tyto entity se objeví **automaticky** při běžné instalaci. **Není potřeba žádné dodatečné ani samostatné sdílení dat s Bosch** – spadají pod obvyklou autorizaci. Mnoho z nich přesto podle konkrétního kola zůstává na „neznámé“, protože podkladová data neexistují (viz poznámka níže).

| Entita | Typ/jednotka | Popis |
|--------|--------------|-------|
| Reachable Range {Eco/Tour/eMTB/Turbo} | sensor / km | Oficiální odhad dojezdu od Bosch pro každý jízdní režim (jeden senzor na aktivní režim) |
| Next Service Date | sensor / datum | Příští servis jako datum (doplněk k Next Service Odometer založenému na km) |
| State of Health | sensor / % | Kondice baterie pro každou baterii, z digitální servisní knížky |
| Measured Capacity | sensor / Wh | Kapacita baterie naměřená prodejcem, pro každou baterii |
| Theft Reported | binary_sensor | Zda byla u kola nahlášena krádež (z Bike Pass) |
| Last Known Location | device_tracker | Poslední známá poloha při nahlášené krádeži (z Bike Pass) |
| Software Update Available | binary_sensor | Zda je pro kolo k dispozici aktualizace softwaru |
| Lifetime Distance {režim} | sensor / km | Vzdálenost za celou životnost pro každý jízdní režim (ze servisní knížky) |
| Lifetime Energy {režim} | sensor / Wh | Energie za celou životnost pro každý jízdní režim (ze servisní knížky) |
| Last Service Date | sensor / datum | Datum posledního servisu |
| Last Service Dealer | sensor | Prodejce posledního servisu |
| Last Service Odometer | sensor / km | Stav kilometrů při posledním servisu |
| Components | sensor (diagnostika) | Namontované komponenty podle diagnostiky |
| Last Ride Start Odometer | sensor / km | Počáteční stav kilometrů poslední jízdy |
| Last Ride Max Altitude | sensor / m | Maximální nadmořská výška poslední jízdy |

> **⚠️ Důležitá poznámka k těmto entitám:** **Není potřeba žádné dodatečné sdílení dat s Bosch** – spadají pod běžnou autorizaci. Často však zůstávají na „neznámé“, protože podkladová data existují jen v určitých případech:
> - **Poloha při krádeži** (`Last Known Location`) se **naplní pouze tehdy, když je nahlášena krádež** – **žádné průběžné sledování polohy neprobíhá**.
> - **Kondice baterie (State of Health)** a naměřená kapacita jsou **k dispozici až po měření kapacity u prodejce**.
> - **Data ze servisní knížky a zákaznických zpráv** (Last Service, hodnoty za celou životnost) se objeví jen tehdy, pokud takové záznamy existují.
>
> Jinak tyto entity ukazují „neznámé“ – to je **záměrné** (by design).

---

### Licence

Licence MIT – podrobnosti viz [LICENSE](LICENSE).

### Poděkování

Vytvořil [Volker Hauffe](https://github.com/Xunil99).

Tato integrace používá oficiální [Bosch eBike Data Act API](https://portal.bosch-ebike.com/data-act).
