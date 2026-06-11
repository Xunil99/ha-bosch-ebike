# Bosch eBike Smart System – Intégration Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

> [Deutsch](README.md) | [English](README.md#english) | [Nederlands](README.nl.md) | **Français** | [Italiano](README.it.md) | [Español](README.es.md)

> ### ⚠️ Exigence régionale
> Cette intégration fonctionne **exclusivement avec un compte Bosch SingleKey ID enregistré au sein de l'UE**. Elle utilise l'API officielle Bosch Data Act, dont la disponibilité est limitée aux comptes de l'UE. Les comptes d'autres régions sont rejetés par le point de terminaison de l'API et l'intégration ne peut alors pas se connecter.

> ### 🔌 De vraies données en direct via Bluetooth (smart system v19+)
> En plus de l'intégration HACS, ce dépôt contient aussi une **passerelle BLE ESPHome** qui transforme un ESP32 en pont vers le **Bosch eBike Live Data Interface**. Le SoC de la batterie, la vitesse, le compteur kilométrique & co. arrivent ainsi en temps réel dans Home Assistant.
>
> 🚀 **Flasher sans installer ESPHome** : branche un ESP32 (ou ESP32-C3, par ex. « C3 Mini ») en USB, ouvre dans Chrome / Edge **[https://xunil99.github.io/ha-bosch-ebike/](https://xunil99.github.io/ha-bosch-ebike/)** et clique sur *Install*. L'installateur détecte automatiquement la puce et flashe le firmware adapté. La configuration Wi-Fi se fait dans la même étape du navigateur. Guide complet (DE/EN) avec l'appairage via l'app Flow : [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome).

> ### 🖥️ En option : écran 4,3" pour la date, la météo et les données en direct
> En plus de la passerelle, il existe maintenant un deuxième firmware pour le **Guition/Sunton JC4827W543** (ESP32-S3 avec écran tactile IPS 4,3"). Il lit les capteurs de la passerelle depuis Home Assistant et affiche la date, l'heure, la météo et jusqu'à deux eBikes en parallèle. Les utilisateurs existants de la passerelle n'ont rien à changer, l'écran est purement additif. Guide d'installation : [`esphome/DISPLAY.md`](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/DISPLAY.md).

---

## Français

### Description

Cette intégration personnalisée connecte ton **Bosch eBike Smart System** à Home Assistant. Elle lit les données du vélo (kilométrage, heures moteur, cycles de charge de la batterie) et les données d'activité (dernière sortie, vitesse, cadence, puissance) directement depuis l'API officielle Bosch Data Act.

**Seuls les eBikes équipés du Bosch Smart System sont pris en charge** (pas le système Classic Line).

### Fonctionnalités

- **Données du vélo :** kilométrage, heures moteur (total & avec assistance), vitesse maximale d'assistance, modes d'assistance actifs, vitesse de l'aide à la poussée, kilométrage du prochain entretien
- **Données de batterie :** Wh fournis sur la durée de vie, cycles de charge (total, sur le vélo, externe)
- **Dernière sortie :** distance, durée, vitesse moyenne/maximale, cadence (moy./max.), puissance du cycliste en watts (moy./max.), calories brûlées, dénivelé (montée/descente), titre, date
- **Statistiques globales :** nombre total de sorties, distance totale, temps de conduite total, calories totales, dénivelé total, moyennes de vitesse/puissance/cadence sur toutes les sorties
- **Export des traces GPS :** export de toutes les sorties en fichiers GPX (avec vitesse, cadence et puissance en tant que Garmin TrackPointExtension)
- **Affichage cartographique interactif :** carte Lovelace personnalisée avec traces GPS, code couleur selon la vitesse, sélecteur de date et navigation prev/next
- **Carte 3D avec chase-cam, curseur temporel et ombres des bâtiments :** carte Lovelace personnalisée (`bosch-ebike-3d-map-card`) pour la vue détaillée d'une sortie avec bâtiments en 3D, une caméra qui suit le vélo par derrière, vitesse de lecture proportionnelle (par défaut 60× le temps réel) et ombres portées selon la position du soleil à l'heure de la sortie (MapLibre + OpenFreeMap, gratuit et sans clé API)
- **Carte de tableau de bord avec photo du vélo, données en direct et pilotage de la charge :** carte Lovelace personnalisée (`bosch-ebike-dashboard-card`) avec ta propre photo du vélo, kilométrage, niveau de batterie, état de charge, capteur de puissance de charge optionnel, curseur de SoC cible ainsi que boutons Start/Stop via une prise connectée
- **Renouvellement automatique du token** via refresh token
- **Intervalle d'interrogation de 30 minutes** (toutes les sorties sont importées au premier démarrage)

### 🆕 Données en direct via Bluetooth (passerelle ESPHome)

En plus de l'intégration cloud, tu trouveras dans le sous-dossier [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome) un **composant externe ESPHome** qui transforme un ESP32 en pont vers le **Bosch eBike Live Data Interface (LDI)** (BLE, smart system v19+). Les valeurs en temps réel (vitesse, SoC de la batterie, cadence, puissance du cycliste, kilométrage, état des feux, état de verrouillage, …) arrivent ainsi dans HA sous forme de capteurs ESPHome – en complément de l'historique des sorties basé sur le cloud.

🚀 **Le chemin le plus rapide sans connaissances ESPHome** : branche l'ESP32, ouvre **https://xunil99.github.io/ha-bosch-ebike/** dans Chrome / Edge et clique sur *Install*. Le flash du firmware et la configuration Wi-Fi se déroulent entièrement dans le navigateur – aucune installation d'ESPHome nécessaire.

Guide complet : **[esphome/README.md](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/README.md)**

> **Projets apparentés :** Pas d'ESP32 sous la main, mais un Raspberry Pi ? [ha-bosch-ebike-pibridge](https://github.com/possm/ha-bosch-ebike-pibridge) de [@possm](https://github.com/possm) est un portage communautaire en Python (BlueZ + MQTT) qui tourne directement sur le Pi, prend en charge **deux vélos simultanément** et fournit son propre tableau de bord web.

#### Utiliser les valeurs en direct pour un calcul exact des sorties (optionnel, à partir de la v1.10.0)

Quand la passerelle fonctionne, tu peux renseigner deux capteurs dans les **options de l'intégration** (HA → *Paramètres → Appareils et services → Bosch eBike → Configurer*) :

- **Capteur de kilométrage en direct** (par ex. `sensor.ebike_odometer_live`)
- **Capteur de niveau de batterie en direct** (par ex. `sensor.ebike_battery_soc_live`)

S'ils sont définis, l'intégration interroge à chaque mise à jour de sortie le recorder de HA pour obtenir la valeur de ces capteurs au début et à la fin de la sortie. Les différences donnent :

- **Distance exacte de la sortie** (différence de kilométrage au lieu du calcul GPS du cloud).
- **Consommation exacte de batterie en Wh** ((SoC début − SoC fin) × capacité de la batterie / 100).

Ces valeurs remplacent l'ancienne estimation par instantané dans les capteurs *Last Ride Distance*, *Battery Consumption Wh*, *consommation %*, etc. Si aucun échantillon BLE n'était disponible dans la fenêtre de tolérance (±5 min) au début ou à la fin de la sortie (vélo hors de portée), l'intégration retombe de manière transparente sur l'ancienne logique cloud. Les deux champs sont optionnels et indépendants – tu peux aussi n'en définir qu'un seul.

### Prérequis

1. Un eBike avec **Bosch Smart System** (par ex. Performance Line CX, SX, etc.)
2. Un compte **Bosch SingleKey ID** ([singlekey-id.com](https://singlekey-id.com))
3. Un accès au **portail Bosch eBike Flow** ([portal.bosch-ebike.com](https://portal.bosch-ebike.com))

---

### Guide pas à pas

#### Prérequis

1. Un compte **Bosch SingleKey ID** – si tu n'en as pas encore, crée-en un sur [singlekey-id.com](https://singlekey-id.com)
2. Ton eBike doit être lié à l'**app Bosch eBike Flow** ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))

---

#### Étape 1 : enregistrer une app dans le portail Bosch Data Act (à faire en premier !)

C'est l'étape la plus importante. Tu dois créer une « app » dans le portail Bosch pour obtenir un **Client-ID**.

1. Va sur [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Connecte-toi avec ton SingleKey ID
3. Clique sur **« Create App »** (créer une app)
4. Remplis le formulaire :
   - **Nom de l'app :** par ex. `Home Assistant`
   - **Redirect URI :** `https://my.home-assistant.io/redirect/oauth`
   - **Login URL :** au choix (purement informatif), par ex. `https://github.com/Xunil99/ha-bosch-ebike`
   - **Confidential client :** laisser sur **OFF** (Home Assistant utilise un client public avec PKCE, sans secret)

   > **Important :** La **Redirect URI** doit être exactement `https://my.home-assistant.io/redirect/oauth` – c'est la redirection officielle « My Home Assistant » grâce à laquelle Home Assistant termine la connexion automatiquement. L'intégration « My Home Assistant » doit être activée dans HA (c'est le cas par défaut). Si tu l'as désactivée, enregistre à la place `https://<ton-URL-HA>/auth/external/callback`.

5. Après la création, tu reçois un **Client-ID** (au format `euda-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

#### Étape 2 : conserver le Client-ID

Copie le **Client-ID** que tu viens de créer – tu en auras besoin dans Home Assistant juste après.

> **Remarque :** Tu dois encore **activer** le Client-ID dans le portail Flow (étape 5) avant que la connexion ne fonctionne. Sans activation, Bosch rejette la connexion avec « client non trouvé ».

---

#### Étape 3 : configurer l'intégration dans Home Assistant

1. Installe l'intégration (via HACS ou manuellement – voir ci-dessous) et redémarre Home Assistant
2. Va dans **Paramètres → Appareils et services → Ajouter une intégration**
3. Cherche **« Bosch eBike »**
4. Saisis ton **Client-ID** et clique sur **Envoyer**
5. Clique sur **Autoriser** – tu es redirigé vers la **page de connexion Bosch**
6. Connecte-toi avec ton **SingleKey ID** et confirme l'autorisation
7. Tu es **automatiquement** ramené vers Home Assistant – **plus besoin de copier des codes**. L'intégration est configurée.

> **Plus de localhost, plus de copier-coller :** Depuis le passage à OAuth, Home Assistant gère lui-même tout le retour de connexion (via la redirection « My Home Assistant »). L'intégration renouvelle ensuite automatiquement les tokens d'accès et de rafraîchissement.

#### Étape 4 : vérifier le résultat

L'intégration devrait maintenant être configurée – mais **encore sans entités !** C'est normal. Continue avec l'étape 5.

---

#### Étape 5 : activer le partage de données

Sans partage de données, l'API renvoie un résultat vide !

1. Va sur **[flow.bosch-ebike.com](https://flow.bosch-ebike.com)**
2. Connecte-toi avec ton **SingleKey ID**
3. Sélectionne **« Data Act »** dans le menu en haut
4. Cherche l'entrée **« Home Assistant »** et **active-la**

Tu devrais maintenant voir sur la page Bosch API correspondante l'option permettant d'activer le Client-ID !

#### Étape 6 : recharger l'intégration

Après avoir activé le Client-ID dans le portail Flow :

1. Retourne dans **Home Assistant → Paramètres → Appareils et services**
2. Cherche l'intégration **Bosch eBike**
3. Clique sur **⋮ (trois points)** → **Recharger**

L'intégration devrait maintenant se mettre à jour avec **toutes les entités disponibles** (données du vélo, batterie, dernière sortie, statistiques globales).

#### 6. Configurer la vue cartographique (optionnel)

L'intégration contient une carte Lovelace interactive pour afficher tes traces GPS.

**Étape A : enregistrer la ressource**

> **Remarque :** À partir de la version 1.16.27, cette ressource s'enregistre **automatiquement** dès que Home Assistant a complètement démarré – en toute sécurité, sans modifier d'autres ressources existantes (la variante défectueuse et sujette aux pertes de données des versions précédentes a été remplacée). **En règle générale, tu n'as donc rien à faire ici.** Seulement si la carte apparaît malgré tout comme « Custom element doesn't exist » (par ex. parce que tu gères les ressources en mode YAML), ajoute-la une seule fois manuellement comme suit.

1. Va dans **Paramètres → Tableaux de bord**
2. Clique en haut à droite sur le **menu ⋮ à trois points** → **Ressources**
3. Clique sur **+ Ajouter une ressource** (en bas à droite)
4. Saisis les données suivantes :
   - **URL :** `/ha_bosch_ebike/bosch-ebike-map-card.js`
   - **Type de ressource :** module JavaScript
5. Clique sur **Créer**

**Étape B : ajouter la carte au tableau de bord**

1. Ouvre le tableau de bord souhaité
2. Clique en haut à droite sur le **crayon ✏️** (mode édition)
3. Clique sur **+ Ajouter une carte**
4. Fais défiler tout en bas et choisis **Manuel** (saisie YAML)
5. Colle le code suivant :
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 400
   ```
6. Clique sur **Enregistrer**

> **Astuce :** Tu peux ajuster la hauteur (height) (200–1000 pixels). Recommandation : 400 pour les smartphones, 500 pour les ordinateurs.

**La carte affiche :**
- Trace GPS avec code couleur selon la vitesse (bleu → vert → jaune → rouge)
- Marqueur de départ (vert) et marqueur d'arrivée (rouge)
- Informations sur la sortie (distance, durée, vitesse moy./max., dénivelé, calories)
- Boutons **◀ Prev / Next ▶** et **sélecteur de date** pour parcourir toutes les sorties
- Le **bouton chase-cam ▶** ouvre la sortie actuellement visible dans un overlay plein écran avec la lecture complète de la carte 3D (2D / 3D / satellite, curseur, bascule nord-fixe, plein écran). Fermeture via le bouton X ou Échap.

> **Remarque :** Si la carte ne s'affiche pas correctement après une mise à jour, vide le cache du navigateur avec `Ctrl+Shift+R` (hard reload).

> **Mise à jour HACS pour les cartes :** Les quatre cartes Lovelace (Map, Heatmap, Calendar, Dashboard) sont regroupées dans un seul fichier JS (`bosch-ebike-map-card.js`) et sont mises à jour automatiquement avec l'intégration. Après une mise à jour de version via HACS, effectue un hard reload du cache du navigateur, sinon le sélecteur de cartes peut ne pas encore afficher une nouvelle carte.

#### Installation HACS (alternative)

1. Ouvre HACS dans Home Assistant
2. Clique sur **« Dépôts personnalisés »** (trois points en haut à droite)
3. Ajoute l'URL du dépôt : `https://github.com/Xunil99/ha-bosch-ebike`
4. Catégorie : **Intégration**
5. Installe l'intégration et redémarre Home Assistant

---

### Plusieurs vélos ou comptes

L'intégration prend en charge aussi bien plusieurs comptes que plusieurs vélos par compte.

**Plusieurs comptes Bosch** (par ex. un vélo par membre de la famille avec son propre SingleKey ID) :
1. Crée pour chaque compte une inscription d'app distincte avec son propre Client-ID dans le portail Bosch Data Act
2. Ajoute l'intégration plusieurs fois (**Paramètres → Appareils et services → + Ajouter une intégration → Bosch eBike**) en saisissant à chaque fois l'autre Client-ID
3. Chaque instance a ses propres capteurs et ses propres sorties

**Plusieurs vélos sous un même compte** (par ex. deux vélos avec le même SingleKey ID) :
- L'intégration crée automatiquement des capteurs distincts par vélo (drive unit, batterie, service, etc.).
- Les sorties sont attribuées automatiquement au bon vélo via une heuristique (comparaison de la valeur `odometer` propre au vélo avec `startOdometer + distance` de la sortie concernée).

**Filtre dans la carte :** Dès qu'il y a plus d'un compte et/ou plus d'un vélo, la carte Lovelace affiche automatiquement deux champs de sélection au-dessus de la liste :
- **Compte** (visible uniquement avec plusieurs comptes)
- **Vélo** (visible uniquement avec plusieurs vélos)

La sélection filtre les sorties affichées en direct ; le tri fonctionne comme d'habitude au sein du résultat filtré.

#### Verrouiller une carte sur un compte ou un vélo

Si une carte doit afficher en permanence exactement un compte ou un vélo (par ex. pour mettre deux cartes côte à côte pour des comparaisons), renseigne `account_id` et/ou `bike_id` dans la configuration de la carte. Le menu déroulant choisi est alors masqué et le filtre est verrouillé.

Tu peux choisir facilement les ID dans l'éditeur (en haut à droite dans l'édition de la carte) via des menus déroulants – pas besoin de les chercher manuellement. En option, `title` peut remplacer l'en-tête de la carte :

```yaml
type: horizontal-stack
cards:
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Mon vélo"
    account_id: <config_entry_id_compte_a>
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Vélo du partenaire"
    account_id: <config_entry_id_compte_b>
```

Les deux cartes affichent alors toujours les sorties du compte verrouillé respectif et permettent, grâce à la sélection de date/tri, de parcourir l'historique des sorties indépendamment l'une de l'autre – idéal pour comparer directement, par exemple, deux sorties effectuées le même jour. Les mêmes options fonctionnent aussi dans la `bosch-ebike-heatmap-card`.

### POI le long de l'itinéraire

Sur la carte, il y a une bascule 📍 dans les commandes. Quand elle est activée, une requête Overpass API est lancée en arrière-plan pour trouver les points suivants le long de l'itinéraire (à max. ~500 m du chemin parcouru) :

- 🔌 **Stations de recharge** (`amenity=charging_station`)
- 🛠️ **Magasins de vélos** et stations de réparation (`shop=bicycle`, `amenity=bicycle_repair_station`)
- 💧 **Eau potable** (`amenity=drinking_water`)
- 🚻 **Toilettes** (`amenity=toilets`)

Clic sur un marqueur → popup avec nom, horaires d'ouverture/adresse/site web (si renseignés dans OSM) et lien vers OpenStreetMap. Jusqu'à 100 marqueurs sont affichés par sortie ; les résultats sont mis en cache dans le localStorage du navigateur.

### Rappels d'entretien

#### Définir soi-même l'échéance d'entretien

Pour chaque vélo, il existe deux entités modifiables :

- **`date.<bike>_service_due_date`** – date à laquelle le prochain entretien est dû
- **`number.<bike>_service_due_odometer`** – kilométrage auquel le prochain entretien est dû

Lors de la première récupération de données, ces valeurs sont automatiquement pré-remplies depuis l'API Bosch (si elles y sont renseignées). Les modifications des entités écrasent les valeurs Bosch et sont utilisées pour les rappels d'entretien. Si tu mets le kilométrage à `0`, l'affichage retombe sur la valeur Bosch.

#### Tâches d'entretien personnalisées

En plus de l'échéance d'entretien fournie par Bosch (`Next Service Date`/`Next Service Odometer`), tu peux créer autant de tâches d'entretien personnalisées que tu veux – par ex. changement de chaîne tous les 3000 km, inspection tous les 365 jours. Pour chaque vélo, un capteur `Maintenance Items Due` est créé ; sa valeur est le nombre de tâches bientôt dues ou en retard, l'attribut `items` liste tous les détails (kilomètres restants, jours restants).

**Créer une tâche :** **Outils de développement → Services**, appeler le service `bosch_ebike.add_maintenance` avec :
- `bike_id` (depuis l'attribut du capteur)
- `name` (par ex. « Changement de chaîne »)
- `interval_km` et/ou `interval_days`

**Marquer une tâche comme terminée :** service `bosch_ebike.complete_maintenance` avec `bike_id` et `item_id` (depuis l'attribut du capteur). Réinitialise la date et le kilométrage à maintenant.

**Supprimer une tâche :** service `bosch_ebike.remove_maintenance`.

**Événements pour les automatisations :** Lorsque le seuil est atteint (par défaut : 30 jours / 200 km avant l'échéance), des événements HA sont déclenchés :
- `ha_bosch_ebike_service_due_soon` / `ha_bosch_ebike_service_overdue` (pour l'entretien Bosch)
- `ha_bosch_ebike_maintenance_due_soon` / `ha_bosch_ebike_maintenance_overdue` (pour les tâches personnalisées)

Tu peux ainsi construire par exemple une notification push ou un rappel lumineux.

### Estimation de l'autonomie

Pour chaque vélo, deux capteurs **estiment** l'autonomie — sur la base de
ta consommation réelle (moyenne pondérée par la distance sur les derniers
~500 km d'historique de sorties) :

- **`Estimated Range (Full Battery)`** — autonomie estimée avec une batterie
  pleine (capacité de la batterie ÷ consommation moyenne en Wh/km).
  Uniquement à partir des données cloud, toujours disponible.
- **`Estimated Range (Current)`** — autonomie restante estimée
  (niveau de batterie actuel × capacité ÷ consommation moyenne). N'apparaît
  que si le **capteur de niveau de batterie en direct** de la passerelle
  ESPHome est lié dans les options de l'intégration ; se met à jour
  immédiatement lors des changements de SoC.

> ⚠️ **C'est une estimation, pas une garantie.** L'autonomie réelle dépend
> fortement du mode d'assistance, de la topographie, du vent, de la
> température et de l'état de la batterie. La base de calcul est consultable
> dans les attributs du capteur (`wh_per_km`, `tours_used`, `window_km`).
> Tant que moins de 3 sorties ou 30 km de données de consommation sont
> disponibles, les capteurs restent vides.

### Carte planificateur d'itinéraires (BRouter)

La carte `bosch-ebike-routeplanner-card` planifie des itinéraires à vélo
directement dans le dashboard — sur la base du routeur open source
[BRouter](https://brouter.de) :

```yaml
type: custom:bosch-ebike-routeplanner-card
height: 480
```

- **Points de passage par clic** sur la carte (départ, arrivée, autant de
  points intermédiaires que tu veux ; glisser un marqueur = déplacer,
  cliquer dessus = supprimer)
- **Profils :** Trekking, Vélo de route, MTB, Le plus court
- **POI le long de l'itinéraire** (bouton 📍) : bornes de recharge, magasins
  de vélos/ateliers, eau potable, toilettes et **restauration** (restaurants,
  cafés, biergartens) — données d'OpenStreetMap/Overpass
- **Résultat :** distance, dénivelé positif/négatif, temps de trajet,
  **consommation estimée** (ta consommation moyenne issue de l'estimation
  de l'autonomie × distance)
- **Contrôle de batterie :** indicateur en feu tricolore montrant si
  l'itinéraire est faisable avec le niveau de batterie actuel (nécessite le
  capteur de niveau de batterie en direct lié) — comme les capteurs
  d'autonomie, une **estimation**, pas une garantie
- **Profil d'altitude** sous forme de diagramme sous la carte
- **Export GPX** de l'itinéraire planifié (importable dans Garmin Connect,
  Komoot, l'app Flow, etc.)

Options : `title`, `height`, `brouter_url` (ta propre instance BRouter au
lieu de brouter.de), `entity` (capteur d'autonomie), `soc_entity` (niveau
de batterie en direct).

> **Confidentialité :** Les coordonnées des points de passage sont envoyées
> au serveur BRouter configuré pour le calcul de l'itinéraire — par défaut le
> serveur public `brouter.de`, financé par des dons. Si tu préfères éviter
> cela, héberge BRouter toi-même (Docker) et saisis l'URL sous `brouter_url`.

### Carte heatmap – toutes les sorties sur une seule carte

Une deuxième variante de carte, `bosch-ebike-heatmap-card`, superpose toutes les sorties d'une sélection sous forme de lignes semi-transparentes. Menus déroulants de filtre pour la période (30 jours / 3 mois / 12 mois / tout), le compte et le vélo. En dessous, une ligne d'état avec le nombre de sorties et de kilomètres de la sélection.

```yaml
type: custom:bosch-ebike-heatmap-card
height: 600
```

Le premier affichage peut prendre un peu de temps – pour chaque sortie pas encore récupérée, un appel API supplémentaire est effectué (avec limite de concurrence). Les traces sont mises en cache en mémoire côté serveur, les appels suivants sont immédiats.

### Carte calendrier – heatmap des jours de sortie façon GitHub

La carte `bosch-ebike-calendar-card` affiche une heatmap annuelle dans le style de l'aperçu des contributions GitHub : 7 lignes pour les jours de la semaine, une colonne par semaine calendaire, chaque cellule colorée selon les kilomètres parcourus ce jour-là. Au survol, une infobulle apparaît avec la date, le nombre de sorties et la distance. La ligne de statistiques en dessous affiche les jours actifs, les sorties et la distance totale sur la période choisie.

```yaml
type: custom:bosch-ebike-calendar-card
```

Menus déroulants de filtre en haut pour la période (12 mois / 24 mois / 5 ans / tout), le compte et le vélo. Un filtre fixe de compte ou de vélo peut être verrouillé via YAML (mêmes options que pour les cartes map et heatmap) :

```yaml
type: custom:bosch-ebike-calendar-card
title: L'année vélo de Volker
account_id: 01HXYZ...
bike_id: bike-uuid-1
```

Paliers de couleur par jour : vide, 1-10 km, 10-25 km, 25-50 km, 50+ km. Les couleurs proviennent des variables de thème HA ; les thèmes clairs ressemblent à GitHub-light, en mode sombre la palette sombre correspondante est chargée automatiquement.

### Carte 3D – suivi chase-cam avec curseur temporel et position du soleil

La carte `bosch-ebike-3d-map-card` est une carte parallèle à la carte 2D classique. Elle démarre avec une liste des dernières sorties. Au clic sur une sortie, la vue détaillée 3D s'ouvre avec MapLibre et les tuiles vectorielles gratuites d'OpenFreeMap : la **caméra suit le vélo en perspective à la troisième personne** (« chase-cam »), le bearing tourne en fonction de la direction de conduite, le pitch et le zoom sont configurables. Lorsqu'on déplace le curseur, la caméra pivote en même temps. L'éclairage de la carte s'adapte à la position du soleil à l'heure de la sortie.

```yaml
type: custom:bosch-ebike-3d-map-card
title: Sortie en 3D
height: 540
default_pitch: 55      # inclinaison de la chase-cam
chase_zoom: 17         # env. 100 m de visibilité vers l'avant
playback_speed: 60     # 60x temps réel (sortie d'1 h = 1 min de lecture)
```

**Ce que la carte affiche :**

- Liste des sorties (vue par défaut) avec date, titre, distance et durée
- Chase-cam 3D après un clic sur une sortie, avec extrusions de bâtiments issues d'OpenStreetMap
- Polyligne de la trace en deux couches (glow + ligne principale) pour une bonne lisibilité
- Marqueurs de départ et d'arrivée ainsi qu'un marqueur de position bleu pulsant qui représente le vélo
- Curseur temporel avec les heures de début/fin de la sortie, scrubbable ; la caméra pivote de manière synchrone
- Bouton lecture/pause pour la lecture en accéléré (durée configurable)
- Statistiques en direct à la position du curseur : distance cumulée, vitesse, altitude
- Le chip heure et soleil dans l'overlay affiche l'heure actuelle et la phase de lumière du jour (nuit, crépuscule, heure dorée, plein jour)
- **Ombres portées des bâtiments** au sol, projetées à partir de l'azimut et de la hauteur du soleil à l'heure du curseur. Les ombres sont affichées en plein jour, raccourcies au crépuscule, masquées la nuit. Mise à jour automatique quand la caméra pivote vers une nouvelle zone urbaine ou que le curseur est déplacé.
- **Export vidéo** à droite du curseur : le bouton d'enregistrement lance une lecture depuis le début de la sortie et enregistre en parallèle le contenu de la carte sous forme de vidéo. À la fin de la sortie, un téléchargement de fichier démarre automatiquement (env. 20-40 Mo par minute). Le format est déterminé par le navigateur : **MP4** dans un Chrome moderne (≥ 126) et Safari (≥ 14.4), sinon **WebM**. Entièrement dans le navigateur via `canvas.captureStream()` + `MediaRecorder`, le serveur HA n'intervient pas du tout.
- Le bouton retour ramène à la liste des sorties

**Options de configuration de la carte :**

| Option | Défaut | Description |
|---|---|---|
| `title` | "Bosch eBike 3D-Touren" | Texte de l'en-tête |
| `height` | 540 | Hauteur de la carte en pixels |
| `default_pitch` | 55 | Inclinaison de la chase-cam (20-65°). 20 ≈ vue aérienne, 65 ≈ first-person |
| `chase_zoom` | 17 | Zoom de la chase-cam (14-19). Plus haut = plus proche, 17 ≈ 100 m de visibilité vers l'avant |
| `chase_lookahead` | 30 | Distance de look-ahead en mètres. À quelle distance devant le vélo se trouve la cible de la caméra. Plus petit = vélo plus haut dans l'image. 0 = caméra centrée directement sur le vélo. |
| `smooth_window` | 15 | Fenêtre de lissage du bearing. Plus haut = caméra plus fluide, mais coupe les virages plus largement. 5 paraît tremblotant, 40 très lent |
| `track_smooth_window` | 2 | Lissage de la position de la trace pour le chemin de la caméra. 0 = désactivé (GPS brut, peut trembler), 2 = doux (défaut), 5+ coupe éventuellement visiblement les virages. La ligne de trace affichée montre quoi qu'il arrive toujours le GPS brut |
| `playback_speed` | 60 | Multiplicateur de temps réel pour le bouton lecture. 60 = 60× plus rapide que la vraie sortie, une sortie d'1 h se lit en 1 min, une sortie de 30 min en 30 s |
| `animate_seconds` | — | Optionnel. Force une durée de lecture fixe (par ex. toujours 25 s), remplace `playback_speed` |
| `show_date` | 1 | Afficher le chip de date dans l'overlay (0 = désactivé) |
| `show_time` | 1 | Afficher le chip d'heure dans l'overlay (0 = désactivé) |
| `show_sun` | 1 | Afficher le chip de position du soleil dans l'overlay (0 = désactivé) |
| `show_speed` | 1 | Afficher la vitesse dans la barre de stats en bas (0 = désactivé) |
| `show_distance` | 1 | Afficher la distance cumulée dans la barre de stats (0 = désactivé) |
| `show_elevation` | 1 | Afficher l'altitude (0 = désactivé) |
| `stats_as_chips` | 0 | 1 = distance, vitesse et altitude sous forme de chips d'overlay en haut à gauche au lieu de la barre de stats en bas. 0 = ligne de stats classique dans la barre de commandes (défaut) |
| `account_id` | (vide) | Verrouiller sur un compte, comme pour la carte 2D |
| `bike_id` | (vide) | Verrouiller sur un vélo |

Remarque : les éléments d'overlay masqués sont automatiquement absents aussi de la vidéo téléchargée, puisque l'enregistrement capture simplement le contenu affiché de la carte.

**Dépendances et remarques :**

- MapLibre GL est chargé depuis unpkg.com au premier appel (env. 800 Ko gzippé, ensuite mis en cache)
- OpenFreeMap fournit les tuiles vectorielles sans clé API et sans inscription
- La carte n'est chargée que lorsque l'utilisateur l'ouvre réellement. Les cartes existantes (Map, Heatmap, Calendar, Dashboard) ne sont pas affectées.
- Le rendu 3D est fluide sur ordinateur et sur les appareils mobiles modernes. Avec des traces très longues (> 10 000 points), des saccades peuvent apparaître sur des appareils plus anciens.
- La couverture des bâtiments OSM est dense en ville, plus clairsemée à la campagne. Les sorties en zone urbaine en profitent le plus.
- **Les ombres du terrain** (montagnes, collines) ne sont volontairement pas incluses. Elles nécessiteraient une source de tuiles DEM (Maptiler avec clé API, AWS Open Data SRTM ou données d'altitude auto-hébergées) plus un ray-casting maison dans le shader. Si l'intérêt est là, cela pourra être ajouté dans une version ultérieure.

### Carte de tableau de bord – photo du vélo, données en direct et pilotage de la charge

La carte `bosch-ebike-dashboard-card` est conçue comme un affichage combiné pour le tableau de bord du salon : en haut une photo personnelle du vélo, en dessous les valeurs en direct de la passerelle ESPHome et, en option, les éléments de commande d'une prise connectée à laquelle est branché le chargeur. Tous les champs sont optionnels – ce qui n'est pas configuré est masqué proprement par la carte au lieu d'afficher une ligne vide.

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

**Ce que la carte affiche :**

- **Photo du vélo** avec upload intégré dans l'éditeur de carte (choisir l'image, la carte écrit le chemin elle-même). Alternativement, référencement classique via `/config/www/` et `/local/fichier.jpg`. Placeholder avec une icône de vélo tant que rien n'est défini.
- **Tuile de kilométrage** et, en option, **distance de la dernière sortie**, **puissance de charge en watts**
- **Autonomie restante estimée** sous forme de tuile (`≈ 62 km`) — automatique dès que le capteur « Autonomie estimée (actuelle) » existe, ou explicitement via `range_entity`. Comme pour les capteurs, c'est une **estimation**.
- **Pastilles d'état** pour l'état de charge et le pourcentage de batterie
- **Curseur de SoC cible** qui définit la valeur d'un `input_number`
- **Boutons Start et Stop** avec confirmation à deux clics pour le Stop (protection contre les erreurs de manipulation)
- **Barre de batterie** en bas, qui passe à l'orange sous 35 % et au rouge sous 15 %
- **Liste d'entretien** avec autant de tâches librement définissables que tu veux (huiler la chaîne, entretien, vérifier les freins, …) – dans l'éditeur, à choisir parmi 11 suggestions ou en texte libre. Par tâche, déclenchement via un intervalle en km ou en jours. Elles apparaissent automatiquement dans le tableau de bord dès qu'elles sont dues dans les prochains **500 km** ou **30 jours** – les entrées en retard en rouge, celles bientôt dues en jaune, triées par urgence. Avec un bouton de validation vert par ligne, tu peux marquer une tâche directement comme « terminée ». **Stockage dans Home Assistant** (`/config/.storage/`, par vélo) au lieu du cache du navigateur : les entrées survivent à un changement de navigateur, sont synchronisées sur tous les appareils et peuvent aussi être gérées depuis des automatisations via les services HA `bosch_ebike.add_maintenance`, `bosch_ebike.update_maintenance`, `bosch_ebike.complete_maintenance` et `bosch_ebike.remove_maintenance`. Dans l'éditeur de carte, tu choisis le vélo dans un menu déroulant ; les entretiens correspondants apparaissent juste en dessous et sont enregistrés en direct dans le backend.
- **Comparaison CO₂ et coûts de carburant** avec la voiture : deux tuiles « Total » et « Dernière sortie » avec les kg de CO₂ et les € économisés. Dans l'éditeur, tu choisis le véhicule de comparaison parmi 7 presets réalistes (citadine/berline/SUV, chacun essence ou diesel, plus voiture électrique avec électricité verte) ; en option, tu peux remplacer le prix du carburant/de l'électricité par litre/kWh.

**Prérequis pour la fonctionnalité complète :**

- Une **passerelle ESPHome Bosch eBike** en fonctionnement pour le niveau de batterie, le kilométrage et la détection de charge
- Une **prise connectée** (Shelly, Tasmota, Fritz!DECT, etc.) qui apparaît dans HA comme `switch.*` et, en option, comme capteur de puissance `sensor.*_power`, si tu veux le Start/Stop et la puissance de charge
- Un `input_number.*` avec une plage de 0-100, si tu veux utiliser le curseur de SoC cible

**L'arrêt automatique au SoC cible** n'est volontairement pas implémenté dans la carte elle-même, mais sous forme d'automatisation HA, afin que tu puisses définir librement les tolérances, les conditions horaires ou la logique multi-appareils. Exemple d'automatisation :

```yaml
alias: eBike arrêt auto au SoC cible
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

### Articles Wikipédia le long de l'itinéraire

Sur la carte Lovelace, il y a une bascule 📚 dans les commandes de la carte. Quand elle est activée, la carte cherche tous les 2 km le long de l'itinéraire parcouru des articles Wikipédia à proximité et les affiche sous forme de marqueurs (i). Un clic ouvre un petit popup avec le titre, une image d'aperçu, une courte description et un lien vers l'article complet.

- **La langue** suit le paramètre de langue de HA ; en cas de résultat vide, l'anglais est utilisé en repli
- **Maximum 30 marqueurs** par sortie, les zones denses sont regroupées
- **L'état de la bascule et les résultats** sont mis en cache dans le navigateur (`localStorage`) ; lors d'un changement de sortie, des données fraîches sont récupérées
- **Note de confidentialité** : lors de l'activation de la couche, des coordonnées de points d'appui de l'itinéraire sont envoyées à l'API Wikipédia ; la couche est désactivée par défaut

### Dépannage

| Problème | Solution |
|----------|----------|
| Pas d'entités après la configuration | Activer le partage de données dans le portail Flow (étape 5) |
| « Client non trouvé » à la connexion | Activer le Client-ID dans le portail Flow (étape 5) et vérifier les fautes de frappe/espaces |
| « Invalid state » / le retour échoue | « My Home Assistant » est-il activé dans HA ? La Redirect URI dans le portail doit être `https://my.home-assistant.io/redirect/oauth` |
| Kilométrage anormalement élevé | L'odomètre est fourni en mètres et converti automatiquement en km |
| Données d'activité manquantes | Vérifie que le partage des activités est actif dans le portail Flow |
| Token non accepté | Vérifie que le Client-ID a été saisi correctement |

---

### Capteurs disponibles

#### Capteurs du vélo
| Capteur | Unité | Description |
|---------|-------|-------------|
| Odometer | km | Kilométrage total |
| Motor Total Hours | h | Durée de fonctionnement totale du moteur |
| Motor Assist Hours | h | Durée de fonctionnement du moteur avec assistance |
| Max Assist Speed | km/h | Vitesse maximale d'assistance |
| Active Assist Modes | - | Liste des modes d'assistance actifs |
| Walk Assist Speed | km/h | Vitesse de l'aide à la poussée |
| Next Service Odometer | km | Kilométrage du prochain entretien |
| Estimated Range (Full Battery) | km | Autonomie estimée avec batterie pleine (d'après la conso moyenne, estimation !) |
| Estimated Range (Current) | km | Autonomie restante estimée (SoC en direct requis, estimation !) |

#### Capteurs de batterie (par batterie)
| Capteur | Unité | Description |
|---------|-------|-------------|
| Wh Lifetime | Wh | Wattheures fournis sur la durée de vie |
| Charge Cycles | - | Cycles de charge totaux |
| Cycles On Bike | - | Cycles de charge sur le vélo |
| Cycles Off Bike | - | Cycles de charge externes |

#### Capteurs d'activité (dernière sortie)
| Capteur | Unité | Description |
|---------|-------|-------------|
| Last Ride Title | - | Nom de la sortie |
| Last Ride Date | - | Date/heure |
| Last Ride Distance | km | Distance |
| Last Ride Duration | min | Durée de conduite (sans les arrêts) |
| Last Ride Avg/Max Speed | km/h | Vitesse moyenne/maximale |
| Last Ride Avg/Max Cadence | rpm | Cadence |
| Last Ride Avg/Max Rider Power | W | Puissance du cycliste |
| Last Ride Calories | kcal | Calories brûlées |
| Last Ride Elevation Gain/Loss | m | Dénivelé (montée/descente) |

#### Statistiques globales (sur toutes les sorties)
| Capteur | Unité | Description |
|---------|-------|-------------|
| Total Rides | - | Nombre total de sorties |
| Total Distance (Activities) | km | Distance totale de toutes les sorties |
| Total Ride Duration | h | Temps de conduite total |
| Total Calories | kcal | Calories brûlées au total |
| Total Elevation Gain | m | Dénivelé total |
| Avg Speed (All Rides) | km/h | Vitesse moyenne sur toutes les sorties |
| Avg Rider Power (All Rides) | W | Puissance moyenne du cycliste |
| Avg Cadence (All Rides) | rpm | Cadence moyenne |

#### Boutons
| Bouton | Description |
|--------|-------------|
| Import All GPS Data | Exporte les traces GPS de toutes les sorties en fichiers GPX |
| Import Latest GPS Data | Exporte la trace GPS de la dernière sortie en GPX |

> **Emplacement de stockage :** Les fichiers GPX exportés sont enregistrés localement dans le répertoire de configuration de Home Assistant sous :
> ```
> /config/bosch_ebike_gps/
> ```

---

### Licence

Licence MIT – voir [LICENSE](LICENSE) pour les détails.

### Crédits

Créé par [Volker Hauffe](https://github.com/Xunil99).

Cette intégration utilise l'[API officielle Bosch eBike Data Act](https://portal.bosch-ebike.com/data-act).
