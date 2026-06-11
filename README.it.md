# Bosch eBike Smart System – Integrazione per Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

> [Deutsch](README.md) | [English](README.md#english) | [Nederlands](README.nl.md) | [Français](README.fr.md) | **Italiano** | [Español](README.es.md)

> ### ⚠️ Requisito regionale
> Questa integrazione funziona **esclusivamente con un account Bosch SingleKey-ID registrato all'interno dell'UE**. Utilizza l'API ufficiale Bosch Data Act, la cui disponibilità è limitata agli account UE. Gli account di altre regioni vengono rifiutati dall'endpoint API e l'integrazione non può autenticarsi.

> ### 🔌 Veri dati live via Bluetooth (smart system v19+)
> Oltre all'integrazione HACS, questo repo contiene anche una **bridge BLE ESPHome** che trasforma un ESP32 in un ponte verso il **Bosch eBike Live Data Interface**. In questo modo SoC della batteria, velocità, chilometraggio & co. arrivano in tempo reale in Home Assistant.
>
> 🚀 **Flash senza installare ESPHome**: collega un ESP32 (o ESP32-C3, ad es. "C3 Mini") via USB, apri in Chrome / Edge **[https://xunil99.github.io/ha-bosch-ebike/](https://xunil99.github.io/ha-bosch-ebike/)** e clicca su *Install*. L'installer riconosce automaticamente il chip e flasha il firmware adatto. La configurazione Wi-Fi avviene nello stesso passaggio nel browser. Guida completa (DE/EN) incl. abbinamento tramite l'app Flow: [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome).

> ### 🖥️ Opzionale: display da 4,3" per data, meteo e dati live
> Oltre alla bridge è ora disponibile un secondo firmware per il **Guition/Sunton JC4827W543** (ESP32-S3 con touchscreen IPS da 4,3"). Legge i sensori della bridge da Home Assistant e mostra data, ora, meteo e fino a due eBike in parallelo. Gli utenti esistenti della bridge non devono cambiare nulla: il display è puramente aggiuntivo. Guida alla configurazione: [`esphome/DISPLAY.md`](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/DISPLAY.md).

---

## Italiano

### Descrizione

Questa integrazione custom collega il tuo **Bosch eBike Smart System** a Home Assistant. Legge i dati della bici (chilometraggio, ore motore, cicli di ricarica della batteria) e i dati delle attività (ultimo giro, velocità, cadenza, potenza) direttamente dall'API ufficiale Bosch Data Act.

**Sono supportate esclusivamente le eBike con Bosch Smart System** (non il sistema Classic Line).

### Funzionalità

- **Dati della bici:** chilometraggio, ore motore (totali e con assistenza), velocità massima di assistenza, modalità di assistenza attive, velocità dell'assistenza alla spinta, chilometraggio del prossimo tagliando
- **Dati della batteria:** Wh erogati nell'intera vita utile, cicli di ricarica (totali, sulla bici, esterni)
- **Ultimo giro:** distanza, durata, velocità media/massima, cadenza (media/max), potenza del ciclista in watt (media/max), calorie consumate, dislivello (salita/discesa), titolo, data
- **Statistiche complessive:** numero totale di giri, distanza totale, tempo di guida totale, calorie totali, dislivello totale, valori medi di velocità/potenza/cadenza su tutti i giri
- **Export delle tracce GPS:** esportazione di tutti i giri come file GPX (con velocità, cadenza e potenza come Garmin TrackPointExtension)
- **Visualizzazione interattiva su mappa:** custom card Lovelace con tracce GPS, colorazione in base alla velocità, selettore di data e navigazione prev/next
- **Mappa 3D con chase-cam, slider temporale e ombre degli edifici:** custom card Lovelace (`bosch-ebike-3d-map-card`) per la vista di dettaglio del tour, con edifici 3D, una telecamera che segue la bici da dietro, velocità di riproduzione proporzionale (default 60× il tempo reale) e ombre proiettate in base alla posizione del sole all'ora del tour (MapLibre + OpenFreeMap, gratuiti e senza API key)
- **Dashboard card con foto della bici, dati live e controllo della ricarica:** custom card Lovelace (`bosch-ebike-dashboard-card`) con foto personalizzata della bici, chilometraggio, livello della batteria, stato di ricarica, sensore opzionale di potenza di ricarica, slider per il SoC target e pulsanti Start/Stop tramite una presa smart
- **Rinnovo automatico del token** tramite refresh token
- **Intervallo di polling di 30 minuti** (al primo avvio vengono importati tutti i giri)

### 🆕 Dati live via Bluetooth (bridge ESPHome)

Oltre all'integrazione cloud, nella sottocartella [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome) trovi un **ESPHome external component** che trasforma un ESP32 in un ponte verso il **Bosch eBike Live Data Interface (LDI)** (BLE, smart system v19+). In questo modo i valori in tempo reale (velocità, SoC della batteria, cadenza, potenza del ciclista, chilometraggio, stato delle luci, stato del blocco, …) arrivano in HA come sensori ESPHome – a complemento dello storico dei tour basato sul cloud.

🚀 **La via più rapida senza conoscenze di ESPHome**: collega l'ESP32, apri in Chrome / Edge **https://xunil99.github.io/ha-bosch-ebike/** e tocca *Install*. Flash del firmware e configurazione Wi-Fi avvengono interamente nel browser – non serve alcuna installazione di ESPHome.

Guida completa: **[esphome/README.md](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/README.md)**

> **Progetti correlati:** Nessun ESP32 a portata di mano, ma un Raspberry Pi? [ha-bosch-ebike-pibridge](https://github.com/possm/ha-bosch-ebike-pibridge) di [@possm](https://github.com/possm) è un porting della community in Python (BlueZ + MQTT) che gira direttamente sul Pi, supporta **due bici contemporaneamente** e include un proprio dashboard web.

#### Usare i valori live per il calcolo esatto del tour (opzionale, da v1.10.0)

Quando la bridge è in funzione, nelle **opzioni dell'integrazione** (HA → *Impostazioni → Dispositivi e servizi → Bosch eBike → Configura*) puoi impostare due sensori:

- **Sensore live del chilometraggio** (ad es. `sensor.ebike_odometer_live`)
- **Sensore live del livello batteria** (ad es. `sensor.ebike_battery_soc_live`)

Se impostati, a ogni aggiornamento dei tour l'integrazione interroga il recorder di HA per il valore di questi sensori all'inizio e alla fine del tour. Dalle differenze risultano:

- **Distanza esatta del tour** (differenza di chilometraggio invece del calcolo GPS dal cloud).
- **Consumo esatto della batteria in Wh** ((SoC iniziale − SoC finale) × capacità della batteria / 100).

Questi valori sostituiscono la precedente stima basata su snapshot nei sensori *Last Ride Distance*, *Battery Consumption Wh*, *consumo %* ecc. Se all'inizio o alla fine del tour non era disponibile alcun campione BLE entro la finestra di tolleranza (±5 min) (bici fuori portata), l'integrazione ricade in modo trasparente sulla vecchia logica cloud. Entrambi i campi sono opzionali e indipendenti – puoi anche impostarne solo uno dei due.

### Requisiti

1. Una eBike con **Bosch Smart System** (ad es. Performance Line CX, SX, ecc.)
2. Un account **Bosch SingleKey ID** ([singlekey-id.com](https://singlekey-id.com))
3. Accesso al **portale Bosch eBike Flow** ([portal.bosch-ebike.com](https://portal.bosch-ebike.com))

---

### Guida passo passo

#### Requisiti

1. Un account **Bosch SingleKey ID** – se non ne hai ancora uno, creane uno su [singlekey-id.com](https://singlekey-id.com)
2. La tua eBike deve essere collegata all'app **Bosch eBike Flow** ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))

---

#### Passo 1: registrare l'app nel portale Bosch Data Act (da fare per primo!)

Questo è il passaggio più importante. Devi creare una "app" nel portale Bosch per ottenere una **Client-ID**.

1. Vai su [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Accedi con la tua SingleKey ID
3. Clicca su **"Create App"** (crea app)
4. Compila il modulo:
   - **Nome app:** ad es. `Home Assistant`
   - **Redirect URI:** `https://my.home-assistant.io/redirect/oauth`
   - **Login URL:** a piacere (puramente informativo), ad es. `https://github.com/Xunil99/ha-bosch-ebike`
   - **Confidential client:** lascia **OFF** (Home Assistant usa un public client con PKCE, senza secret)

   > **Importante:** La **Redirect URI** deve essere esattamente `https://my.home-assistant.io/redirect/oauth` – è il redirect ufficiale di "My Home Assistant", tramite il quale Home Assistant completa automaticamente il login. L'integrazione "My Home Assistant" deve essere attivata in HA (lo è di default). Se l'hai disattivata, registra invece `https://<il-tuo-URL-HA>/auth/external/callback`.

5. Dopo la creazione ricevi una **Client-ID** (nel formato `euda-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

#### Passo 2: salvare la Client-ID

Copia la **Client-ID** appena creata – ti servirà tra poco in Home Assistant.

> **Nota:** Devi ancora **attivare** la Client-ID nel portale Flow (passo 5) prima che il login funzioni. Senza attivazione, Bosch rifiuta l'accesso con "client non trovato".

---

#### Passo 3: configurare l'integrazione in Home Assistant

1. Installa l'integrazione (tramite HACS o manualmente – vedi sotto) e riavvia Home Assistant
2. Vai su **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**
3. Cerca **"Bosch eBike"**
4. Inserisci la tua **Client-ID** e clicca su **Invia**
5. Clicca su **Autorizza** – verrai reindirizzato al **login Bosch**
6. Accedi con la tua **SingleKey ID** e conferma il consenso
7. Verrai riportato **automaticamente** a Home Assistant – **non serve più copiare alcun codice**. L'integrazione è configurata.

> **Niente più localhost, niente più copia e incolla:** Dal passaggio a OAuth, Home Assistant gestisce da solo l'intero ritorno dal login (tramite il redirect "My Home Assistant"). L'access token e il refresh token vengono poi rinnovati automaticamente dall'integrazione.

#### Passo 4: verificare il risultato

L'integrazione dovrebbe ora essere configurata – ma **ancora senza entità!** È normale. Prosegui con il passo 5.

---

#### Passo 5: attivare la condivisione dei dati

Senza condivisione dei dati l'API restituisce un risultato vuoto!

1. Vai su **[flow.bosch-ebike.com](https://flow.bosch-ebike.com)**
2. Accedi con la tua **SingleKey ID**
3. Seleziona **"Data Act"** nel menu in alto
4. Cerca la voce **"Home Assistant"** e **attivala**

Ora, nella pagina Bosch-API corrispondente, dovresti vedere l'opzione per attivare la Client-ID!

#### Passo 6: ricaricare l'integrazione

Dopo aver attivato la Client-ID nel portale Flow:

1. Torna a **Home Assistant → Impostazioni → Dispositivi e servizi**
2. Cerca l'integrazione **Bosch eBike**
3. Clicca su **⋮ (tre puntini)** → **Ricarica**

L'integrazione dovrebbe ora aggiornarsi con **tutte le entità disponibili** (dati della bici, batteria, ultimo giro, statistiche complessive).

#### 6. Configurare la vista mappa (opzionale)

L'integrazione include una card Lovelace interattiva per visualizzare le tue tracce GPS.

**Passo A: registrare la risorsa**

> **Nota:** Dalla versione 1.16.27 questa risorsa si registra **automaticamente** non appena Home Assistant è completamente avviato – in modo sicuro, senza modificare altre risorse esistenti (la variante difettosa e soggetta a perdita di dati delle versioni precedenti è stata sostituita). **Di norma quindi qui non devi fare nulla.** Solo se la card appare comunque come "Custom element doesn't exist" (ad es. perché gestisci le risorse in modalità YAML), aggiungila manualmente una volta come segue.

1. Vai su **Impostazioni → Dashboard**
2. Clicca in alto a destra sul **menu a tre puntini ⋮** → **Risorse**
3. Clicca su **+ Aggiungi risorsa** (in basso a destra)
4. Inserisci i seguenti dati:
   - **URL:** `/ha_bosch_ebike/bosch-ebike-map-card.js`
   - **Tipo di risorsa:** modulo JavaScript
5. Clicca su **Crea**

**Passo B: aggiungere la card al dashboard**

1. Apri il dashboard desiderato
2. Clicca in alto a destra sulla **matita ✏️** (modalità modifica)
3. Clicca su **+ Aggiungi scheda**
4. Scorri fino in fondo e seleziona **Manuale** (inserimento YAML)
5. Incolla il seguente codice:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 400
   ```
6. Clicca su **Salva**

> **Suggerimento:** Puoi regolare l'altezza (height) tra 200 e 1000 pixel. Consiglio: 400 per smartphone, 500 per desktop.

**La card mostra:**
- Traccia GPS con colorazione in base alla velocità (blu → verde → giallo → rosso)
- Marker di partenza (verde) e di arrivo (rosso)
- Informazioni sul giro (distanza, durata, velocità media/max, dislivello, calorie)
- Pulsanti **◀ Prev / Next ▶** e **selettore di data** per sfogliare tutti i giri
- **▶ Pulsante chase-cam** apre il tour attualmente visibile in un overlay a schermo intero con la riproduzione completa della card 3D (2D / 3D / satellite, slider, toggle nord fisso, schermo intero). Chiusura tramite il pulsante X o Escape.

> **Nota:** Se dopo un aggiornamento la card non viene visualizzata correttamente, svuota la cache del browser con `Ctrl+Shift+R` (hard reload).

> **Aggiornamento HACS per le card:** Tutte e quattro le card Lovelace (Map, Heatmap, Calendar, Dashboard) si trovano in un unico file JS (`bosch-ebike-map-card.js`) e vengono aggiornate automaticamente insieme all'integrazione. Dopo un aggiornamento di versione da HACS esegui un hard reload della cache del browser, altrimenti il selettore delle card potrebbe non mostrare ancora una nuova card.

#### Installazione tramite HACS (alternativa)

1. Apri HACS in Home Assistant
2. Clicca su **"Repository personalizzati"** (tre puntini in alto a destra)
3. Aggiungi l'URL del repository: `https://github.com/Xunil99/ha-bosch-ebike`
4. Categoria: **Integrazione**
5. Installa l'integrazione e riavvia Home Assistant

---

### Più bici o più account

L'integrazione supporta sia più account sia più bici per account.

**Più account Bosch** (ad es. una bici per ogni membro della famiglia, ciascuno con la propria SingleKey ID):
1. Crea per ogni account una propria registrazione app nel portale Bosch Data Act, con una propria Client-ID
2. Aggiungi l'integrazione più volte (**Impostazioni → Dispositivi e servizi → + Aggiungi integrazione → Bosch eBike**) inserendo ogni volta l'altra Client-ID
3. Ogni istanza ha i propri sensori e i propri tour

**Più bici sotto un unico account** (ad es. due bici con la stessa SingleKey ID):
- L'integrazione crea automaticamente sensori separati per ogni bici (drive unit, batteria, service ecc.).
- I tour vengono assegnati automaticamente alla bici giusta tramite un'euristica (confronto del valore `odometer` specifico della bici con `startOdometer + distance` del rispettivo tour).

**Filtri nella card:** Non appena è presente più di un account e/o più di una bici, la card Lovelace mostra automaticamente due campi di selezione sopra la lista:
- **Account** (visibile solo con più account)
- **Bici** (visibile solo con più bici)

La selezione filtra i tour visualizzati in tempo reale; l'ordinamento funziona come di consueto all'interno del risultato filtrato.

#### Fissare una card a un account o a una bici

Se una card deve mostrare in modo permanente esattamente un account o una bici (ad es. per avere due card affiancate per viste di confronto), inserisci nella configurazione della card `account_id` e/o `bike_id`. Il dropdown corrispondente viene quindi nascosto e il filtro è bloccato.

Puoi selezionare comodamente gli ID dai dropdown nell'editor (in alto a destra nella modifica della card) – non è necessario cercarli manualmente. Opzionalmente `title` può sovrascrivere l'intestazione della card:

```yaml
type: horizontal-stack
cards:
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "La mia bici"
    account_id: <config_entry_id_account_a>
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Bici del partner"
    account_id: <config_entry_id_account_b>
```

Entrambe le card mostrano quindi sempre i tour dell'account bloccato e possono essere sfogliate indipendentemente l'una dall'altra nello storico dei tour con la selezione di data/ordinamento – ideale ad es. per confrontare direttamente due tour percorsi lo stesso giorno. Le stesse opzioni funzionano anche nella `bosch-ebike-heatmap-card`.

### POI lungo il percorso

Sulla mappa c'è un toggle 📍 nei controlli. Se attivato, in background viene avviata una query all'API Overpass che trova i seguenti punti lungo il percorso (max. ~500 m dal tracciato percorso):

- 🔌 **Stazioni di ricarica** (`amenity=charging_station`)
- 🛠️ **Negozi di biciclette** e stazioni di riparazione (`shop=bicycle`, `amenity=bicycle_repair_station`)
- 💧 **Acqua potabile** (`amenity=drinking_water`)
- 🚻 **Servizi igienici** (`amenity=toilets`)

Clic su un marker → popup con nome, orari di apertura/indirizzo/sito web (se presenti in OSM) e link a OpenStreetMap. Per ogni tour vengono mostrati fino a 100 marker; i risultati vengono memorizzati nella localStorage del browser.

### Promemoria di manutenzione

#### Impostare manualmente la scadenza del tagliando

Per ogni bici ci sono due entità modificabili:

- **`date.<bike>_service_due_date`** – data in cui è previsto il prossimo tagliando
- **`number.<bike>_service_due_odometer`** – chilometraggio al quale è previsto il prossimo tagliando

Al primo recupero dei dati questi valori vengono precompilati automaticamente dall'API Bosch (se lì presenti). Le modifiche alle entità sovrascrivono i valori Bosch e vengono usate per i promemoria di manutenzione. Se imposti il chilometraggio su `0`, la visualizzazione torna al valore Bosch.

#### Voci di manutenzione personalizzate

Oltre al tagliando fornito da Bosch (`Next Service Date`/`Next Service Odometer`) puoi creare voci di manutenzione personalizzate a piacere – ad es. cambio catena ogni 3000 km, ispezione ogni 365 giorni. Per ogni bici viene creato un sensore `Maintenance Items Due`; il suo valore è il numero di voci in scadenza imminente o scadute, l'attributo `items` elenca tutti i dettagli (chilometri restanti, giorni restanti).

**Creare una voce:** **Strumenti per sviluppatori → Servizi**, richiama il servizio `bosch_ebike.add_maintenance` con:
- `bike_id` (dall'attributo del sensore)
- `name` (ad es. "Cambio catena")
- `interval_km` e/o `interval_days`

**Contrassegnare una voce come completata:** servizio `bosch_ebike.complete_maintenance` con `bike_id` e `item_id` (dall'attributo del sensore). Reimposta data e chilometraggio a ora.

**Eliminare una voce:** servizio `bosch_ebike.remove_maintenance`.

**Eventi per le automazioni:** Al raggiungimento della soglia (default: 30 giorni / 200 km prima della scadenza) vengono generati eventi HA:
- `ha_bosch_ebike_service_due_soon` / `ha_bosch_ebike_service_overdue` (per il service Bosch)
- `ha_bosch_ebike_maintenance_due_soon` / `ha_bosch_ebike_maintenance_overdue` (per le voci personalizzate)

Con questi puoi ad es. creare una notifica push o un promemoria luminoso.

### Stima dell'autonomia

Per ogni bici ci sono due sensori che **stimano** l'autonomia — sulla base
del tuo consumo reale (media ponderata per distanza sugli ultimi ~500 km
di storico dei tour):

- **`Estimated Range (Full Battery)`** — autonomia stimata con batteria piena
  (capacità della batteria ÷ consumo medio in Wh/km). Solo da dati cloud,
  sempre disponibile.
- **`Estimated Range (Current)`** — autonomia residua stimata
  (livello attuale della batteria × capacità ÷ consumo medio). Compare solo
  se nelle opzioni dell'integrazione è collegato il **sensore live del
  livello batteria** della bridge ESPHome; si aggiorna immediatamente al
  variare del SoC.

> ⚠️ **È una stima, non una garanzia.** L'autonomia reale dipende fortemente
> da modalità di assistenza, topografia, vento, temperatura e condizioni
> della batteria. La base di calcolo è consultabile negli attributi del
> sensore (`wh_per_km`, `tours_used`, `window_km`). Finché sono disponibili
> meno di 3 tour o 30 km di dati di consumo, i sensori restano vuoti.

### Card pianificatore di percorsi (BRouter)

La card `bosch-ebike-routeplanner-card` pianifica percorsi in bici
direttamente nella dashboard — sulla base del router open source
[BRouter](https://brouter.de):

```yaml
type: custom:bosch-ebike-routeplanner-card
height: 480
```

- **Punti del percorso con un clic** sulla mappa (partenza, destinazione,
  punti intermedi a piacere; trascina un marker = sposta, cliccalo = elimina)
- **Profili:** Trekking, Bici da corsa, MTB, Più breve
- **POI lungo il percorso** (interruttore 📍): stazioni di ricarica, negozi
  di biciclette/officine, acqua potabile, bagni e **ristorazione** (ristoranti,
  caffè, birrerie all'aperto) — dati da OpenStreetMap/Overpass
- **Risultato:** distanza, salita/discesa, tempo di percorrenza, **consumo
  stimato** (il tuo consumo medio dalla stima dell'autonomia × distanza)
- **Controllo batteria:** indicatore a semaforo che mostra se il percorso è
  fattibile con il livello di batteria attuale (richiede il sensore live del
  livello batteria collegato) — come i sensori di autonomia, una **stima**,
  non una garanzia
- **Profilo altimetrico** come diagramma sotto la mappa
- **Esportazione GPX** del percorso pianificato (importabile in Garmin
  Connect, Komoot, l'app Flow e altri)
- **Salvare e caricare percorsi:** salva i percorsi pianificati con un nome
  a scelta (memorizzati in Home Assistant, disponibili su tutti i tuoi
  dispositivi), ricaricali dalla lista 📁, continua a modificarli o eliminali

Opzioni: `title`, `height`, `brouter_url` (istanza BRouter propria invece di
brouter.de), `entity` (sensore di autonomia), `soc_entity` (livello batteria
live).

> **Privacy:** Le coordinate dei punti del percorso vengono inviate al server
> BRouter configurato per il calcolo del percorso — di default il server
> pubblico `brouter.de`, finanziato da donazioni. Se preferisci evitarlo,
> esegui BRouter in autonomia (Docker) e inserisci l'URL in `brouter_url`.

### Heatmap card – tutti i tour su una sola mappa

Una seconda variante della card, `bosch-ebike-heatmap-card`, sovrappone tutti i tour di una selezione come linee semitrasparenti. Dropdown di filtro per periodo (30 giorni / 3 mesi / 12 mesi / tutti), account e bici. Sotto, una riga di stato con il numero di tour e di chilometri della selezione.

```yaml
type: custom:bosch-ebike-heatmap-card
height: 600
```

La prima visualizzazione può richiedere un po' di tempo – per ogni tour non ancora recuperato viene effettuata una chiamata API aggiuntiva (con limite di concorrenza). Le tracce vengono memorizzate in cache lato server in memoria; le chiamate successive sono immediate.

### Calendar card – heatmap in stile GitHub dei giorni di guida

La card `bosch-ebike-calendar-card` mostra una heatmap annuale nello stile della panoramica dei contributi di GitHub: 7 righe per i giorni della settimana, una colonna per ogni settimana di calendario, ogni cella colorata in base ai chilometri percorsi quel giorno. Al passaggio del mouse appare un tooltip con data, numero di tour e distanza. La riga delle statistiche sottostante mostra giorni attivi, tour e distanza totale nel periodo selezionato.

```yaml
type: custom:bosch-ebike-calendar-card
```

Dropdown di filtro in alto per periodo (12 mesi / 24 mesi / 5 anni / tutti), account e bici. Tramite YAML è possibile bloccare un filtro fisso su account o bici (stesse opzioni delle card map e heatmap):

```yaml
type: custom:bosch-ebike-calendar-card
title: L'anno in bici di Volker
account_id: 01HXYZ...
bike_id: bike-uuid-1
```

Fasce di colore per giorno: vuoto, 1-10 km, 10-25 km, 25-50 km, 50+ km. I colori provengono dalle variabili del tema HA: i temi chiari assomigliano a GitHub light, in modalità scura viene caricata automaticamente la palette scura adatta.

### Mappa 3D – inseguimento chase-cam con slider temporale e posizione del sole

La card `bosch-ebike-3d-map-card` è una mappa parallela alla classica mappa 2D. Si avvia con un elenco degli ultimi tour. Cliccando su un tour si apre la vista di dettaglio 3D con MapLibre e i vector tile gratuiti di OpenFreeMap: la **telecamera segue la bici in prospettiva in terza persona** ("chase-cam"), il bearing ruota in base alla direzione di marcia, pitch e zoom sono configurabili. Muovendo lo slider la telecamera segue il movimento. L'illuminazione della mappa si adatta alla posizione del sole all'ora del tour.

```yaml
type: custom:bosch-ebike-3d-map-card
title: Tour in 3D
height: 540
default_pitch: 55      # inclinazione della chase-cam
chase_zoom: 17         # ca. 100 m di visuale in avanti
playback_speed: 60     # 60x il tempo reale (tour di 1 ora = 1 min di riproduzione)
```

**Cosa mostra la card:**

- Elenco dei tour (vista predefinita) con data, titolo, distanza e durata
- Chase-cam 3D dopo il clic su un tour, con estrusioni degli edifici da OpenStreetMap
- Polilinea della traccia su due livelli (glow + linea principale) per una buona leggibilità
- Marker di partenza e arrivo più un marker di posizione blu pulsante che rappresenta la bici
- Slider temporale con gli orari di inizio/fine del tour, scrubbabile; la telecamera segue in modo sincrono
- Pulsante play/pausa per la riproduzione accelerata (durata configurabile)
- Statistiche live alla posizione dello slider: distanza cumulativa, velocità, altitudine
- Chip di ora e sole nell'overlay che mostra l'ora corrente e la fase di luce diurna (notte, crepuscolo, ora dorata, luce diurna)
- **Ombre proiettate dagli edifici** sul terreno, calcolate dall'azimut e dall'altezza del sole all'ora dello slider. Le ombre vengono mostrate con la luce diurna, si accorciano al crepuscolo e scompaiono di notte. Aggiornamento automatico quando la telecamera si sposta su una nuova zona urbana o si muove lo slider.
- **Export video** a destra dello slider: il pulsante di registrazione avvia una riproduzione dall'inizio del tour e registra in parallelo il contenuto della mappa come video. Al termine del tour parte automaticamente il download del file (ca. 20-40 MB al minuto). Il formato è determinato dal browser: **MP4** nei Chrome moderni (≥ 126) e Safari (≥ 14.4), altrimenti **WebM**. Tutto avviene nel browser tramite `canvas.captureStream()` + `MediaRecorder`; il server HA non ha alcun ruolo.
- Il pulsante Indietro riporta all'elenco dei tour

**Opzioni di configurazione della card:**

| Opzione | Default | Descrizione |
|---|---|---|
| `title` | "Bosch eBike 3D-Touren" | Testo dell'intestazione |
| `height` | 540 | Altezza della card in pixel |
| `default_pitch` | 55 | Inclinazione della chase-cam (20-65°). 20 ≈ vista a volo d'uccello, 65 ≈ prima persona |
| `chase_zoom` | 17 | Zoom della chase-cam (14-19). Più alto = più vicino, 17 ≈ 100 m di visuale in avanti |
| `chase_lookahead` | 30 | Distanza di look-ahead in metri. Quanto il punto di mira della telecamera precede la bici. Più piccolo = bici più in alto nell'inquadratura. 0 = telecamera centrata direttamente sulla bici. |
| `smooth_window` | 15 | Finestra di smussamento del bearing. Più alto = telecamera più fluida, ma taglia di più le curve. 5 risulta tremolante, 40 molto pigro |
| `track_smooth_window` | 2 | Smussamento della posizione della traccia per il percorso della telecamera. 0 = disattivato (GPS grezzo, può tremolare), 2 = morbido (default), 5+ può tagliare visibilmente le curve. La linea della traccia visualizzata mostra comunque sempre il GPS grezzo |
| `playback_speed` | 60 | Moltiplicatore del tempo reale con il pulsante play. 60 = 60× più veloce della corsa reale; un tour di 1 ora viene riprodotto in 1 minuto, un tour di 30 minuti in 30 secondi |
| `animate_seconds` | — | Opzionale. Impone una durata di riproduzione fissa (ad es. sempre 25 s), sovrascrive `playback_speed` |
| `show_date` | 1 | Mostra il chip della data nell'overlay (0 = off) |
| `show_time` | 1 | Mostra il chip dell'ora nell'overlay (0 = off) |
| `show_sun` | 1 | Mostra il chip della posizione del sole nell'overlay (0 = off) |
| `show_speed` | 1 | Mostra la velocità nella barra delle statistiche in basso (0 = off) |
| `show_distance` | 1 | Mostra la distanza cumulativa nella barra delle statistiche (0 = off) |
| `show_elevation` | 1 | Mostra l'altitudine (0 = off) |
| `stats_as_chips` | 0 | 1 = distanza, velocità e altitudine come chip overlay in alto a sinistra invece che in basso nella barra delle statistiche. 0 = classica riga delle statistiche nella barra dei controlli (default) |
| `account_id` | (vuoto) | Fissa la card su un account, come nella mappa 2D |
| `bike_id` | (vuoto) | Fissa la card su una bici |

Nota: gli elementi overlay nascosti mancano automaticamente anche nel video scaricato, poiché la registrazione cattura semplicemente il contenuto della mappa visualizzato.

**Dipendenze e note:**

- MapLibre GL viene caricato da unpkg.com alla prima apertura (ca. 800 KB gzip, poi in cache)
- OpenFreeMap fornisce i vector tile senza API key e senza registrazione
- La mappa viene caricata solo quando l'utente la apre effettivamente. Le card esistenti (Map, Heatmap, Calendar, Dashboard) non sono interessate.
- Il rendering 3D è fluido su desktop e sui dispositivi mobili moderni. Con tracce molto lunghe (> 10.000 punti) può scattare sui dispositivi più vecchi.
- La copertura degli edifici OSM è fitta nelle città, più rada in campagna. I tour attraverso aree urbane ne beneficiano maggiormente.
- **Le ombre del terreno** (montagne, colline) sono volutamente escluse. Richiederebbero una sorgente di tile DEM (Maptiler con API key, AWS Open Data SRTM o dati altimetrici self-hosted) più un ray-casting dedicato nello shader. In caso di interesse, potranno essere aggiunte in una versione futura.

### Dashboard card – foto della bici, dati live e controllo della ricarica

La card `bosch-ebike-dashboard-card` è pensata come vista combinata per il dashboard del soggiorno: in alto una foto personalizzata della bici, sotto i valori live dalla bridge ESPHome e, opzionalmente, gli elementi di controllo per una presa smart a cui è collegato il caricabatterie. Tutti i campi sono opzionali – ciò che non è configurato viene nascosto in modo pulito dalla card, invece di mostrare una riga vuota.

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

**Cosa mostra la card:**

- **Foto della bici** con upload integrato nell'editor della card (scegli l'immagine, la card scrive il percorso da sola). In alternativa, in modo classico tramite `/config/www/` e riferimento `/local/file.jpg`. Segnaposto con icona di bicicletta finché non è impostato nulla.
- **Riquadro del chilometraggio** e, opzionalmente, **distanza dell'ultimo tour**, **potenza di ricarica in watt**
- **Autonomia residua stimata** come riquadro (`≈ 62 km`) — automatica non appena esiste il sensore "Autonomia stimata (attuale)", oppure esplicitamente tramite `range_entity`. Come i sensori, è una **stima**.
- **Status pill** per lo stato di ricarica e la percentuale della batteria
- **Slider del SoC target**, che imposta il valore di un `input_number`
- **Pulsanti Start e Stop** con conferma a doppio clic per lo Stop (protezione dagli errori)
- **Barra della batteria** in basso, che passa all'arancione sotto il 35 % e al rosso sotto il 15 %
- **Lista di manutenzione** con un numero illimitato di voci liberamente definibili (oliare la catena, tagliando, controllare i freni, …) – selezionabili nell'editor tra 11 suggerimenti o come testo libero. Per ogni voce un trigger tramite intervallo in km o in giorni. Compaiono automaticamente nel dashboard non appena scadono entro i prossimi **500 km** o **30 giorni** – le voci scadute in rosso, quelle in scadenza imminente in giallo, ordinate per urgenza. Con un pulsante verde con segno di spunta per riga puoi contrassegnare direttamente una voce come "completata". **Salvataggio in Home Assistant** (`/config/.storage/`, separato per bici) invece che nella cache del browser: le voci sopravvivono al cambio di browser, sono sincronizzate su tutti i dispositivi e possono essere gestite anche dalle automazioni tramite i servizi HA `bosch_ebike.add_maintenance`, `bosch_ebike.update_maintenance`, `bosch_ebike.complete_maintenance` e `bosch_ebike.remove_maintenance`. Nell'editor della card scegli la bici da un dropdown; le manutenzioni associate compaiono direttamente sotto e vengono salvate live nel backend.
- **Confronto di CO₂ e costi di carburante** con l'auto: due riquadri "Totale" e "Ultimo tour" con i kg di CO₂ e gli € risparmiati. Nell'editor scegli il veicolo di confronto tra 7 preset realistici (utilitaria/berlina media/SUV, ciascuno a benzina o diesel, più auto elettrica con energia verde); opzionalmente puoi sovrascrivere il prezzo del carburante/dell'energia per litro/kWh.

**Requisiti per la piena funzionalità:**

- Una **bridge ESPHome Bosch eBike** in funzione per livello della batteria, chilometraggio e rilevamento della ricarica
- Una **presa smart** (Shelly, Tasmota, Fritz!DECT, ecc.) che compare in HA come `switch.*` e opzionalmente come sensore di potenza `sensor.*_power`, se vuoi usare Start/Stop e vedere la potenza di ricarica
- Un `input_number.*` con intervallo 0-100, se vuoi usare lo slider del SoC target

**Lo stop automatico al SoC target** non è volutamente implementato nella card stessa, ma come automazione HA, in modo che tu possa configurare liberamente tolleranze, condizioni orarie o logiche per più dispositivi. Esempio di automazione:

```yaml
alias: eBike stop automatico al SoC target
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

### Articoli Wikipedia lungo il percorso

Sulla card Lovelace c'è un toggle 📚 nei controlli della mappa. Se attivato, la card cerca ogni 2 km lungo il percorso effettuato articoli Wikipedia nelle vicinanze e li mostra come marker (i). Un clic apre un piccolo popup con titolo, immagine di anteprima, breve descrizione e un link all'articolo completo.

- **La lingua** segue l'impostazione della lingua di HA; in caso di risultato vuoto si ricade sull'inglese
- **Massimo 30 marker** per tour; le zone dense vengono raggruppate
- **Stato del toggle e risultati** vengono memorizzati nella cache del browser (`localStorage`); al cambio di tour vengono recuperati dati freschi
- **Nota sulla privacy**: attivando il layer, le coordinate dei punti di appoggio del percorso vengono inviate all'API di Wikipedia; il layer è disattivato di default

### Risoluzione dei problemi

| Problema | Soluzione |
|----------|-----------|
| Nessuna entità dopo la configurazione | Attivare la condivisione dei dati nel portale Flow (passo 5) |
| "Client non trovato" al login | Attivare la Client-ID nel portale Flow (passo 5) e controllare errori di battitura/spazi |
| "Invalid state" / il ritorno fallisce | "My Home Assistant" è attivato in HA? La Redirect URI nel portale deve essere `https://my.home-assistant.io/redirect/oauth` |
| Chilometraggio irrealisticamente alto | L'odometro viene fornito in metri e convertito automaticamente in km |
| Mancano i dati delle attività | Verifica che la condivisione delle attività sia attiva nel portale Flow |
| Token non accettato | Verifica che la Client-ID sia stata inserita correttamente |

---

### Sensori disponibili

#### Sensori della bici
| Sensore | Unità | Descrizione |
|---------|-------|-------------|
| Odometer | km | Chilometraggio totale |
| Motor Total Hours | h | Tempo di funzionamento totale del motore |
| Motor Assist Hours | h | Tempo di funzionamento del motore con assistenza |
| Max Assist Speed | km/h | Velocità massima di assistenza |
| Active Assist Modes | - | Elenco delle modalità di assistenza attive |
| Walk Assist Speed | km/h | Velocità dell'assistenza alla spinta |
| Next Service Odometer | km | Chilometraggio del prossimo tagliando |
| Estimated Range (Full Battery) | km | Autonomia stimata con batteria piena (dal consumo medio, stima!) |
| Estimated Range (Current) | km | Autonomia residua stimata (SoC live necessario, stima!) |

#### Sensori della batteria (per batteria)
| Sensore | Unità | Descrizione |
|---------|-------|-------------|
| Wh Lifetime | Wh | Wattora erogati nell'intera vita utile |
| Charge Cycles | - | Cicli di ricarica totali |
| Cycles On Bike | - | Cicli di ricarica sulla bici |
| Cycles Off Bike | - | Cicli di ricarica esterni |

#### Sensori delle attività (ultimo giro)
| Sensore | Unità | Descrizione |
|---------|-------|-------------|
| Last Ride Title | - | Nome del giro |
| Last Ride Date | - | Data/ora |
| Last Ride Distance | km | Distanza |
| Last Ride Duration | min | Durata del giro (senza soste) |
| Last Ride Avg/Max Speed | km/h | Velocità media/massima |
| Last Ride Avg/Max Cadence | rpm | Cadenza |
| Last Ride Avg/Max Rider Power | W | Potenza del ciclista |
| Last Ride Calories | kcal | Calorie consumate |
| Last Ride Elevation Gain/Loss | m | Dislivello (salita/discesa) |

#### Statistiche complessive (su tutti i giri)
| Sensore | Unità | Descrizione |
|---------|-------|-------------|
| Total Rides | - | Numero totale di giri |
| Total Distance (Activities) | km | Distanza totale di tutti i giri |
| Total Ride Duration | h | Tempo di guida totale |
| Total Calories | kcal | Calorie totali consumate |
| Total Elevation Gain | m | Dislivello totale |
| Avg Speed (All Rides) | km/h | Velocità media su tutti i giri |
| Avg Rider Power (All Rides) | W | Potenza media del ciclista |
| Avg Cadence (All Rides) | rpm | Cadenza media |

#### Pulsanti
| Pulsante | Descrizione |
|----------|-------------|
| Import All GPS Data | Esporta le tracce GPS di tutti i giri come file GPX |
| Import Latest GPS Data | Esporta la traccia GPS dell'ultimo giro come GPX |

> **Posizione di salvataggio:** I file GPX esportati vengono salvati localmente nella directory di configurazione di Home Assistant in:
> ```
> /config/bosch_ebike_gps/
> ```

---

### Licenza

Licenza MIT – vedi [LICENSE](LICENSE) per i dettagli.

### Crediti

Creato da [Volker Hauffe](https://github.com/Xunil99).

Questa integrazione utilizza l'API ufficiale [Bosch eBike Data Act](https://portal.bosch-ebike.com/data-act).
