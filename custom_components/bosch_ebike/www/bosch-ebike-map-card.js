/**
 * Bosch eBike Map Card for Home Assistant
 * Robust rewrite focused on view switches, iOS WebView quirks, and hidden-container recovery.
 */

// ---------------------------------------------------------------------------
// i18n — strings localized for English, German, Dutch.
// Selection follows hass.locale.language with fallback to English.
// ---------------------------------------------------------------------------
const I18N = {
  en: {
    // Main card
    rides_title: "Bosch eBike Rides",
    sort_label: "Sort by:",
    sort_dir_title: "Reverse sort direction",
    account_label: "Account:",
    bike_label: "Bike:",
    all_accounts: "All accounts",
    all_bikes: "All bikes",
    sort_date: "Date",
    sort_distance: "Distance",
    sort_duration: "Duration",
    sort_avg_speed: "Avg speed",
    sort_max_speed: "Max speed",
    sort_elevation: "Elevation",
    sort_calories: "Calories",
    sort_difficulty: "Difficulty",
    sort_battery_wh: "Battery Wh",
    sort_battery_pct: "Battery %",
    // Map controls
    btn_change_style: "Change map style",
    btn_wiki: "Wikipedia articles",
    btn_poi: "Charging stations, repair shops, drinking water, toilets",
    btn_gpx: "Download GPX",
    btn_fullscreen: "Fullscreen",
    btn_prev: "Previous ride",
    btn_next: "Next ride",
    btn_fit: "Fit route",
    btn_close: "Close",
    btn_view_label: "Fullscreen view",
    tab_map: "Map",
    tab_elevation: "Elevation",
    // Stats labels
    stat_distance: "Distance",
    stat_duration: "Duration",
    stat_avg_kmh: "Ø km/h",
    stat_max_kmh: "Max km/h",
    stat_elevation_up: "Elevation ↑",
    stat_calories: "Calories",
    stat_difficulty: "Difficulty",
    stat_battery: "Battery",
    stat_battery_pct: "Battery %",
    // Speed legend
    speed_legend: "Speed",
    // Status / messages
    msg_loading_route: "Loading route …",
    msg_no_gps: "No GPS points found",
    msg_no_rides: "No rides found",
    msg_no_filter_match: "No rides match this filter",
    msg_unnamed_ride: "Unnamed ride",
    msg_error_prefix: "Error: ",
    err_leaflet_load: "Leaflet could not be loaded",
    err_create_map: "Could not create the map",
    // Profile chart
    profile_title: "Elevation profile",
    profile_no_data: "No elevation data available",
    profile_min_max: (min, max) => `Min ${min} m · Max ${max} m`,
    profile_ascent: "Ascent",
    profile_descent: "Descent",
    profile_avg_speed: "Avg speed",
    profile_max_speed: "Max speed",
    profile_cadence: "Cadence",
    profile_power: "Power",
    profile_avg_max_rpm: (avg, max) => `Ø ${avg} rpm · Max ${max} rpm`,
    profile_avg_max_w: (avg, max) => `Ø ${avg} W · Max ${max} W`,
    // Wikipedia popup
    wiki_loading_preview: "Loading preview …",
    wiki_no_preview: "Preview not available.",
    wiki_open_link: "Open on Wikipedia",
    // POI popups
    poi_charging: "Charging station",
    poi_bicycle_shop: "Bike shop",
    poi_repair: "Repair station",
    poi_water: "Drinking water",
    poi_toilet: "Toilet",
    poi_open_osm: "Open on OpenStreetMap",
    // Editor
    editor_height: "Card height (px)",
    editor_title: "Title (optional)",
    editor_title_hint: "Shown in the card header — useful when you have multiple pinned cards side by side.",
    editor_account_label: "Pin to account (optional)",
    editor_account_hint: "When set, the account dropdown is hidden and the card only shows rides from this account.",
    editor_bike_label: "Pin to bike (optional)",
    editor_bike_hint: "When set, the bike dropdown is hidden and the card only shows rides from this bike.",
    editor_wiki_radius: "Wikipedia search radius",
    editor_wiki_radius_hint: "How far around each route sample point Wikipedia articles are searched. Larger radius = more results, more data.",
    editor_poi_radius: "POI search radius",
    editor_poi_radius_hint: "How far around the route charging stations, repair shops, drinking water and toilets are searched.",
    editor_select_all: "All",
    radius_default_suffix: "(default)",
    // Heatmap card
    heatmap_title: "Bosch eBike Heatmap",
    heat_range_label: "Period:",
    heat_account_label: "Account:",
    heat_bike_label: "Bike:",
    heat_range_30: "30 days",
    heat_range_90: "3 months",
    heat_range_365: "12 months",
    heat_range_all: "All",
    heat_loading: "Loading rides …",
    heat_load_failed: "Error loading rides",
    heat_no_match: "No rides match this filter",
    heat_stat_rides: "Rides",
    heat_stat_distance: "Distance",
    // Calendar card
    calendar_title: "Bosch eBike Calendar",
    cal_range_label: "Period:",
    cal_account_label: "Account:",
    cal_bike_label: "Bike:",
    cal_range_1y: "12 months",
    cal_range_2y: "24 months",
    cal_range_5y: "5 years",
    cal_range_all: "All time",
    cal_loading: "Loading rides …",
    cal_load_failed: "Error loading rides",
    cal_no_match: "No rides match this filter",
    cal_stat_rides: "Rides",
    cal_stat_distance: "Distance",
    cal_stat_active_days: "Active days",
    cal_legend_less: "Less",
    cal_legend_more: "More",
    cal_day_summary: (date, rides, km) =>
      `${date}: ${rides} ride${rides === 1 ? "" : "s"}, ${km.toFixed(1)} km`,
    cal_no_rides_day: (date) => `${date}: no rides`,
    // Map style names
    style_standard: "Standard",
    style_topo: "Topo",
    style_sat: "Satellite",
    // Dashboard card
    dash_no_image: "No image configured",
    dash_no_image_hint: "Set a bike_image URL in the card editor.",
    dash_label_odo: "Odometer",
    dash_label_last_tour: "Last tour",
    dash_label_battery: "Battery",
    dash_label_charge_power: "Charging power",
    dash_label_target_soc: "Stop charging at",
    dash_state_charging: "Charging",
    dash_state_not_charging: "Not charging",
    dash_state_unknown: "n/a",
    dash_btn_start: "Start charging",
    dash_btn_stop: "Stop charging",
    dash_btn_confirm: "Sure?",
    dash_editor_title: "Title (optional)",
    dash_editor_image: "Bike image",
    dash_editor_image_hint: "Pick a file with Upload, or paste a URL (/local/..., /media/local/..., or https://...). Upload stores the file in Home Assistant and fills the URL automatically.",
    dash_editor_image_upload: "Upload",
    dash_editor_image_uploading: "Uploading…",
    dash_editor_image_upload_failed: "Upload failed: ",
    dash_editor_image_clear: "Clear",
    dash_editor_bike_name: "Bike name (optional)",
    dash_editor_bike_name_hint: "Defaults to the title if empty.",
    dash_editor_odo: "Odometer entity",
    dash_editor_battery: "Battery SoC entity (0..100)",
    dash_editor_charging: "Charging-detected entity (binary)",
    dash_editor_last_tour: "Last tour distance entity (optional)",
    dash_editor_charge_power: "Charging power entity (W, optional)",
    dash_editor_charge_switch: "Charger switch entity (optional)",
    dash_editor_target_soc: "Target SoC input_number entity (optional)",
    dash_editor_target_soc_hint: "When set, an HA automation can read this value and stop the smart plug when the battery reaches it.",
    // 3D map card
    map3d_title: "Bosch eBike 3D Tours",
    map3d_loading: "Loading tours…",
    map3d_loading_track: "Loading 3D track…",
    map3d_loading_map: "Loading map engine…",
    map3d_no_rides: "No tours found.",
    map3d_no_gps: "This tour has no GPS data.",
    map3d_back: "Back",
    map3d_open: "Open in 3D",
    map3d_play: "Play",
    map3d_pause: "Pause",
    map3d_speed_label: "Speed",
    map3d_distance_label: "Distance",
    map3d_elevation_label: "Elevation",
    map3d_sun_label: "Sun",
    map3d_err_maplibre: "MapLibre could not be loaded.",
    map3d_err_style: "Map tiles unavailable (OpenFreeMap).",
    map3d_editor_title: "Title (optional)",
    map3d_editor_height: "Card height (px)",
    map3d_editor_account: "Pin to account (optional)",
    map3d_editor_bike: "Pin to bike (optional)",
    map3d_editor_default_pitch: "Chase-cam pitch (20-65°)",
    map3d_editor_default_pitch_hint: "Camera tilt while following the bike. 20 = nearly top-down, 55 = third-person, 65 = almost first-person.",
    map3d_editor_chase_zoom: "Chase-cam zoom (14-19)",
    map3d_editor_chase_zoom_hint: "Higher zoom = closer to the bike. 17 ≈ 100 m ahead visible.",
    map3d_editor_animate_seconds: "Playback duration (seconds)",
    map3d_editor_animate_seconds_hint: "How long a full Play-cycle takes from tour start to tour end.",
    map3d_editor_smooth_window: "Bearing-smoothing window",
    map3d_editor_smooth_window_hint: "Higher = smoother camera, slower to react. 15 is a good default; 5 is twitchy, 40 sweeps corners wide.",
    map3d_editor_track_smooth: "Track-position smoothing window",
    map3d_editor_track_smooth_hint: "Smooths GPS jitter in the camera path. 0 = off (raw GPS), 2 = gentle (default), 5+ may visibly cut corners. The displayed track polyline always shows raw GPS regardless.",
    map3d_editor_playback_speed: "Playback speed factor (×)",
    map3d_editor_playback_speed_hint: "Real-time multiplier. 60 = 60× faster than reality, so a 1-hour ride plays in 1 minute and a 2-hour ride in 2 minutes. Higher = faster.",
    map3d_editor_animate_seconds_override_hint: "Optional. If set, forces a fixed playback duration regardless of tour length and overrides the speed factor.",
    map3d_sun_night: "Night",
    map3d_sun_twilight: "Twilight",
    map3d_sun_golden: "Golden hour",
    map3d_sun_morning: "Daylight",
    map3d_sun_day: "Daylight",
    map3d_record_start: "Record",
    map3d_record_stop: "Stop",
    map3d_record_active: "Recording…",
    map3d_record_unsupported: "Recording not supported in this browser",
  },
  de: {
    rides_title: "Bosch eBike Rides",
    sort_label: "Sortierung:",
    sort_dir_title: "Sortierrichtung umkehren",
    account_label: "Konto:",
    bike_label: "Bike:",
    all_accounts: "Alle Konten",
    all_bikes: "Alle Bikes",
    sort_date: "Datum",
    sort_distance: "Distanz",
    sort_duration: "Dauer",
    sort_avg_speed: "Ø Geschw.",
    sort_max_speed: "Max Geschw.",
    sort_elevation: "Höhenmeter",
    sort_calories: "Kalorien",
    sort_difficulty: "Schwierigkeit",
    sort_battery_wh: "Akku Wh",
    sort_battery_pct: "Akku %",
    btn_change_style: "Kartenstil wechseln",
    btn_wiki: "Wikipedia-Artikel",
    btn_poi: "Ladestationen, Werkstätten, Trinkwasser, Toiletten",
    btn_gpx: "GPX herunterladen",
    btn_fullscreen: "Vollbild",
    btn_prev: "Vorherige Fahrt",
    btn_next: "Nächste Fahrt",
    btn_fit: "Route einpassen",
    btn_close: "Schließen",
    btn_view_label: "Vollbildansicht",
    tab_map: "Karte",
    tab_elevation: "Höhenmeter",
    stat_distance: "Distanz",
    stat_duration: "Dauer",
    stat_avg_kmh: "Ø km/h",
    stat_max_kmh: "Max km/h",
    stat_elevation_up: "Höhenmeter ↑",
    stat_calories: "Kalorien",
    stat_difficulty: "Schwierigkeit",
    stat_battery: "Akku",
    stat_battery_pct: "Akku %",
    speed_legend: "Geschwindigkeit",
    msg_loading_route: "Lade Route …",
    msg_no_gps: "Keine GPS-Punkte gefunden",
    msg_no_rides: "Keine Fahrten gefunden",
    msg_no_filter_match: "Keine Fahrten für diesen Filter",
    msg_unnamed_ride: "Unbenannte Fahrt",
    msg_error_prefix: "Fehler: ",
    err_leaflet_load: "Leaflet konnte nicht geladen werden",
    err_create_map: "Fehler beim Erzeugen der Karte",
    profile_title: "Höhenprofil",
    profile_no_data: "Keine Höhendaten verfügbar",
    profile_min_max: (min, max) => `Min ${min} m · Max ${max} m`,
    profile_ascent: "Aufstieg",
    profile_descent: "Abstieg",
    profile_avg_speed: "Ø Geschwindigkeit",
    profile_max_speed: "Max Geschwindigkeit",
    profile_cadence: "Trittfrequenz",
    profile_power: "Leistung",
    profile_avg_max_rpm: (avg, max) => `Ø ${avg} rpm · Max ${max} rpm`,
    profile_avg_max_w: (avg, max) => `Ø ${avg} W · Max ${max} W`,
    wiki_loading_preview: "Lade Vorschau …",
    wiki_no_preview: "Vorschau nicht verfügbar.",
    wiki_open_link: "Auf Wikipedia öffnen",
    poi_charging: "Ladestation",
    poi_bicycle_shop: "Fahrradgeschäft",
    poi_repair: "Reparaturstation",
    poi_water: "Trinkwasser",
    poi_toilet: "Toilette",
    poi_open_osm: "Auf OpenStreetMap",
    editor_height: "Kartenhöhe (px)",
    editor_title: "Titel (optional)",
    editor_title_hint: "Wird in der Kopfzeile der Karte angezeigt — nützlich, wenn Du mehrere fest verdrahtete Karten nebeneinander hast.",
    editor_account_label: "Konto fest auswählen (optional)",
    editor_account_hint: "Wenn gesetzt, wird das Konto-Dropdown ausgeblendet und die Karte zeigt nur Touren dieses Kontos.",
    editor_bike_label: "Bike fest auswählen (optional)",
    editor_bike_hint: "Wenn gesetzt, wird das Bike-Dropdown ausgeblendet und die Karte zeigt nur Touren dieses Bikes.",
    editor_wiki_radius: "Wikipedia-Suchradius",
    editor_wiki_radius_hint: "Wie weit um jeden Stützpunkt der Route Wikipedia-Artikel gesucht werden. Größerer Radius = mehr Treffer, mehr Daten.",
    editor_poi_radius: "POI-Suchradius",
    editor_poi_radius_hint: "Wie weit um die Route Ladestationen, Werkstätten, Trinkwasser und Toiletten gesucht werden.",
    editor_select_all: "Alle",
    radius_default_suffix: "(Standard)",
    heatmap_title: "Bosch eBike Heatmap",
    heat_range_label: "Zeitraum:",
    heat_account_label: "Konto:",
    heat_bike_label: "Bike:",
    heat_range_30: "30 Tage",
    heat_range_90: "3 Monate",
    heat_range_365: "12 Monate",
    heat_range_all: "Alle",
    heat_loading: "Lade Touren …",
    heat_load_failed: "Fehler beim Laden der Touren",
    heat_no_match: "Keine Touren in diesem Filter",
    heat_stat_rides: "Touren",
    heat_stat_distance: "Distanz",
    calendar_title: "Bosch eBike Kalender",
    cal_range_label: "Zeitraum:",
    cal_account_label: "Konto:",
    cal_bike_label: "Bike:",
    cal_range_1y: "12 Monate",
    cal_range_2y: "24 Monate",
    cal_range_5y: "5 Jahre",
    cal_range_all: "Alle",
    cal_loading: "Lade Touren …",
    cal_load_failed: "Fehler beim Laden der Touren",
    cal_no_match: "Keine Touren in diesem Filter",
    cal_stat_rides: "Touren",
    cal_stat_distance: "Distanz",
    cal_stat_active_days: "Aktive Tage",
    cal_legend_less: "Weniger",
    cal_legend_more: "Mehr",
    cal_day_summary: (date, rides, km) =>
      `${date}: ${rides} Tour${rides === 1 ? "" : "en"}, ${km.toFixed(1)} km`,
    cal_no_rides_day: (date) => `${date}: keine Touren`,
    style_standard: "Standard",
    style_topo: "Topo",
    style_sat: "Satellit",
    // Dashboard card
    dash_no_image: "Kein Bild hinterlegt",
    dash_no_image_hint: "Im Karten-Editor unter Bike-Bild-URL ein Bild eintragen.",
    dash_label_odo: "Tachostand",
    dash_label_last_tour: "Letzte Tour",
    dash_label_battery: "Akku",
    dash_label_charge_power: "Ladeleistung",
    dash_label_target_soc: "Laden stoppen bei",
    dash_state_charging: "Lädt",
    dash_state_not_charging: "Lädt nicht",
    dash_state_unknown: "n/v",
    dash_btn_start: "Laden starten",
    dash_btn_stop: "Laden stoppen",
    dash_btn_confirm: "Sicher?",
    dash_editor_title: "Titel (optional)",
    dash_editor_image: "Bike-Bild",
    dash_editor_image_hint: "Datei per Hochladen wählen oder URL eintragen (/local/..., /media/local/... oder https://...). Beim Hochladen wird die Datei in Home Assistant gespeichert und der Pfad automatisch eingetragen.",
    dash_editor_image_upload: "Hochladen",
    dash_editor_image_uploading: "Wird hochgeladen…",
    dash_editor_image_upload_failed: "Upload fehlgeschlagen: ",
    dash_editor_image_clear: "Entfernen",
    dash_editor_bike_name: "Bike-Name (optional)",
    dash_editor_bike_name_hint: "Fällt auf den Titel zurück, wenn leer.",
    dash_editor_odo: "Tachostand-Entity",
    dash_editor_battery: "Akku-SoC-Entity (0..100)",
    dash_editor_charging: "Lade-Erkennung-Entity (binär)",
    dash_editor_last_tour: "Letzte-Tour-Distanz-Entity (optional)",
    dash_editor_charge_power: "Ladeleistung-Entity (W, optional)",
    dash_editor_charge_switch: "Charger-Switch-Entity (optional)",
    dash_editor_target_soc: "Ziel-SoC input_number-Entity (optional)",
    dash_editor_target_soc_hint: "Wenn gesetzt, kann eine HA-Automation diesen Wert lesen und die Steckdose abschalten, sobald der Akku ihn erreicht.",
    // 3D map card
    map3d_title: "Bosch eBike 3D-Touren",
    map3d_loading: "Touren werden geladen…",
    map3d_loading_track: "3D-Track wird geladen…",
    map3d_loading_map: "Karten-Engine wird geladen…",
    map3d_no_rides: "Keine Touren gefunden.",
    map3d_no_gps: "Diese Tour hat keine GPS-Daten.",
    map3d_back: "Zurück",
    map3d_open: "In 3D öffnen",
    map3d_play: "Abspielen",
    map3d_pause: "Pause",
    map3d_speed_label: "Geschwindigkeit",
    map3d_distance_label: "Distanz",
    map3d_elevation_label: "Höhe",
    map3d_sun_label: "Sonne",
    map3d_err_maplibre: "MapLibre konnte nicht geladen werden.",
    map3d_err_style: "Karten-Tiles nicht erreichbar (OpenFreeMap).",
    map3d_editor_title: "Titel (optional)",
    map3d_editor_height: "Karten-Höhe (px)",
    map3d_editor_account: "Auf Konto fixieren (optional)",
    map3d_editor_bike: "Auf Bike fixieren (optional)",
    map3d_editor_default_pitch: "Chase-Cam-Neigung (20-65°)",
    map3d_editor_default_pitch_hint: "Kamera-Neigung beim Verfolgen des Bikes. 20 = fast Vogelperspektive, 55 = Third-Person, 65 = fast First-Person.",
    map3d_editor_chase_zoom: "Chase-Cam-Zoom (14-19)",
    map3d_editor_chase_zoom_hint: "Höherer Zoom = näher am Bike. 17 ≈ 100 m Sicht nach vorne.",
    map3d_editor_animate_seconds: "Abspieldauer (Sekunden)",
    map3d_editor_animate_seconds_hint: "Wie lange ein voller Play-Durchlauf von Tour-Start bis Tour-Ende dauert.",
    map3d_editor_smooth_window: "Bearing-Glättungsfenster",
    map3d_editor_smooth_window_hint: "Höher = glattere Kamera, träger. 15 ist guter Default; 5 zittrig, 40 schneidet Kurven weit.",
    map3d_editor_track_smooth: "Track-Positions-Glättungsfenster",
    map3d_editor_track_smooth_hint: "Glättet GPS-Rauschen im Kamerapfad. 0 = aus (rohes GPS), 2 = sanft (Default), 5+ schneidet ggf. sichtbar Kurven. Die angezeigte Track-Linie zeigt unabhängig davon immer das rohe GPS.",
    map3d_editor_playback_speed: "Abspielgeschwindigkeit (×)",
    map3d_editor_playback_speed_hint: "Echtzeit-Multiplikator. 60 = 60× schneller als die echte Fahrt, eine 1h-Tour läuft in 1 Min, eine 2h-Tour in 2 Min. Höher = schneller.",
    map3d_editor_animate_seconds_override_hint: "Optional. Wenn gesetzt, erzwingt eine feste Abspieldauer unabhängig von der Tour-Länge und überschreibt den Speed-Faktor.",
    map3d_sun_night: "Nacht",
    map3d_sun_twilight: "Dämmerung",
    map3d_sun_golden: "Goldene Stunde",
    map3d_sun_morning: "Tageslicht",
    map3d_sun_day: "Tageslicht",
    map3d_record_start: "Aufnehmen",
    map3d_record_stop: "Stopp",
    map3d_record_active: "Aufnahme läuft…",
    map3d_record_unsupported: "Aufnahme in diesem Browser nicht unterstützt",
  },
  nl: {
    rides_title: "Bosch eBike Ritten",
    sort_label: "Sortering:",
    sort_dir_title: "Sorteervolgorde omkeren",
    account_label: "Account:",
    bike_label: "Fiets:",
    all_accounts: "Alle accounts",
    all_bikes: "Alle fietsen",
    sort_date: "Datum",
    sort_distance: "Afstand",
    sort_duration: "Duur",
    sort_avg_speed: "Gem. snelheid",
    sort_max_speed: "Max. snelheid",
    sort_elevation: "Hoogtemeters",
    sort_calories: "Calorieën",
    sort_difficulty: "Moeilijkheid",
    sort_battery_wh: "Accu Wh",
    sort_battery_pct: "Accu %",
    btn_change_style: "Kaartstijl wisselen",
    btn_wiki: "Wikipedia-artikelen",
    btn_poi: "Laadstations, werkplaatsen, drinkwater, toiletten",
    btn_gpx: "GPX downloaden",
    btn_fullscreen: "Volledig scherm",
    btn_prev: "Vorige rit",
    btn_next: "Volgende rit",
    btn_fit: "Route inpassen",
    btn_close: "Sluiten",
    btn_view_label: "Volledig schermweergave",
    tab_map: "Kaart",
    tab_elevation: "Hoogteprofiel",
    stat_distance: "Afstand",
    stat_duration: "Duur",
    stat_avg_kmh: "Ø km/u",
    stat_max_kmh: "Max km/u",
    stat_elevation_up: "Hoogtemeters ↑",
    stat_calories: "Calorieën",
    stat_difficulty: "Moeilijkheid",
    stat_battery: "Accu",
    stat_battery_pct: "Accu %",
    speed_legend: "Snelheid",
    msg_loading_route: "Route laden …",
    msg_no_gps: "Geen GPS-punten gevonden",
    msg_no_rides: "Geen ritten gevonden",
    msg_no_filter_match: "Geen ritten voldoen aan dit filter",
    msg_unnamed_ride: "Naamloze rit",
    msg_error_prefix: "Fout: ",
    err_leaflet_load: "Leaflet kon niet worden geladen",
    err_create_map: "Kan kaart niet maken",
    profile_title: "Hoogteprofiel",
    profile_no_data: "Geen hoogtegegevens beschikbaar",
    profile_min_max: (min, max) => `Min ${min} m · Max ${max} m`,
    profile_ascent: "Stijging",
    profile_descent: "Daling",
    profile_avg_speed: "Gem. snelheid",
    profile_max_speed: "Max. snelheid",
    profile_cadence: "Trapfrequentie",
    profile_power: "Vermogen",
    profile_avg_max_rpm: (avg, max) => `Ø ${avg} rpm · Max ${max} rpm`,
    profile_avg_max_w: (avg, max) => `Ø ${avg} W · Max ${max} W`,
    wiki_loading_preview: "Voorbeeld laden …",
    wiki_no_preview: "Voorbeeld niet beschikbaar.",
    wiki_open_link: "Op Wikipedia openen",
    poi_charging: "Laadstation",
    poi_bicycle_shop: "Fietsenwinkel",
    poi_repair: "Reparatiestation",
    poi_water: "Drinkwater",
    poi_toilet: "Toilet",
    poi_open_osm: "Op OpenStreetMap openen",
    editor_height: "Kaarthoogte (px)",
    editor_title: "Titel (optioneel)",
    editor_title_hint: "Wordt in de koptekst van de kaart getoond — handig als je meerdere vastgezette kaarten naast elkaar hebt.",
    editor_account_label: "Vastzetten op account (optioneel)",
    editor_account_hint: "Indien ingesteld wordt het account-dropdown verborgen en toont de kaart alleen ritten van dit account.",
    editor_bike_label: "Vastzetten op fiets (optioneel)",
    editor_bike_hint: "Indien ingesteld wordt het fiets-dropdown verborgen en toont de kaart alleen ritten van deze fiets.",
    editor_wiki_radius: "Wikipedia-zoekstraal",
    editor_wiki_radius_hint: "Hoe ver er rond elk steunpunt van de route naar Wikipedia-artikelen wordt gezocht. Grotere straal = meer treffers, meer data.",
    editor_poi_radius: "POI-zoekstraal",
    editor_poi_radius_hint: "Hoe ver er rond de route naar laadstations, werkplaatsen, drinkwater en toiletten wordt gezocht.",
    editor_select_all: "Alle",
    radius_default_suffix: "(standaard)",
    heatmap_title: "Bosch eBike Heatmap",
    heat_range_label: "Periode:",
    heat_account_label: "Account:",
    heat_bike_label: "Fiets:",
    heat_range_30: "30 dagen",
    heat_range_90: "3 maanden",
    heat_range_365: "12 maanden",
    heat_range_all: "Alle",
    heat_loading: "Ritten laden …",
    heat_load_failed: "Fout bij laden van ritten",
    heat_no_match: "Geen ritten voldoen aan dit filter",
    heat_stat_rides: "Ritten",
    heat_stat_distance: "Afstand",
    calendar_title: "Bosch eBike Kalender",
    cal_range_label: "Periode:",
    cal_account_label: "Account:",
    cal_bike_label: "Fiets:",
    cal_range_1y: "12 maanden",
    cal_range_2y: "24 maanden",
    cal_range_5y: "5 jaar",
    cal_range_all: "Alles",
    cal_loading: "Ritten laden …",
    cal_load_failed: "Fout bij het laden van ritten",
    cal_no_match: "Geen ritten voldoen aan dit filter",
    cal_stat_rides: "Ritten",
    cal_stat_distance: "Afstand",
    cal_stat_active_days: "Actieve dagen",
    cal_legend_less: "Minder",
    cal_legend_more: "Meer",
    cal_day_summary: (date, rides, km) =>
      `${date}: ${rides} rit${rides === 1 ? "" : "ten"}, ${km.toFixed(1)} km`,
    cal_no_rides_day: (date) => `${date}: geen ritten`,
    style_standard: "Standaard",
    style_topo: "Topo",
    style_sat: "Satelliet",
    // Dashboard card
    dash_no_image: "Geen afbeelding ingesteld",
    dash_no_image_hint: "Stel in de kaart-editor een bike_image URL in.",
    dash_label_odo: "Kilometerstand",
    dash_label_last_tour: "Laatste rit",
    dash_label_battery: "Accu",
    dash_label_charge_power: "Laadvermogen",
    dash_label_target_soc: "Laden stoppen bij",
    dash_state_charging: "Aan het laden",
    dash_state_not_charging: "Niet aan het laden",
    dash_state_unknown: "n.v.t.",
    dash_btn_start: "Laden starten",
    dash_btn_stop: "Laden stoppen",
    dash_btn_confirm: "Zeker weten?",
    dash_editor_title: "Titel (optioneel)",
    dash_editor_image: "Fiets-afbeelding",
    dash_editor_image_hint: "Kies een bestand met Uploaden of plak een URL (/local/..., /media/local/... of https://...). Bij uploaden wordt het bestand in Home Assistant opgeslagen en het pad automatisch ingevuld.",
    dash_editor_image_upload: "Uploaden",
    dash_editor_image_uploading: "Wordt geüpload…",
    dash_editor_image_upload_failed: "Upload mislukt: ",
    dash_editor_image_clear: "Verwijderen",
    dash_editor_bike_name: "Naam fiets (optioneel)",
    dash_editor_bike_name_hint: "Valt terug op de titel als leeg.",
    dash_editor_odo: "Kilometerstand-entity",
    dash_editor_battery: "Accu-SoC-entity (0..100)",
    dash_editor_charging: "Laden-detectie-entity (binair)",
    dash_editor_last_tour: "Entity laatste rit-afstand (optioneel)",
    dash_editor_charge_power: "Laadvermogen-entity (W, optioneel)",
    dash_editor_charge_switch: "Lader-schakelaar-entity (optioneel)",
    dash_editor_target_soc: "Doel-SoC input_number-entity (optioneel)",
    dash_editor_target_soc_hint: "Indien ingesteld kan een HA-automation deze waarde uitlezen en de stekker uitschakelen zodra de accu deze bereikt.",
    // 3D map card
    map3d_title: "Bosch eBike 3D-tours",
    map3d_loading: "Tours worden geladen…",
    map3d_loading_track: "3D-track wordt geladen…",
    map3d_loading_map: "Kaart-engine wordt geladen…",
    map3d_no_rides: "Geen tours gevonden.",
    map3d_no_gps: "Deze tour heeft geen GPS-gegevens.",
    map3d_back: "Terug",
    map3d_open: "3D openen",
    map3d_play: "Afspelen",
    map3d_pause: "Pauze",
    map3d_speed_label: "Snelheid",
    map3d_distance_label: "Afstand",
    map3d_elevation_label: "Hoogte",
    map3d_sun_label: "Zon",
    map3d_err_maplibre: "MapLibre kon niet worden geladen.",
    map3d_err_style: "Kaart-tiles niet beschikbaar (OpenFreeMap).",
    map3d_editor_title: "Titel (optioneel)",
    map3d_editor_height: "Kaart-hoogte (px)",
    map3d_editor_account: "Account vastzetten (optioneel)",
    map3d_editor_bike: "Bike vastzetten (optioneel)",
    map3d_editor_default_pitch: "Chase-cam helling (20-65°)",
    map3d_editor_default_pitch_hint: "Camerakanteling tijdens het volgen van de fiets. 20 = bijna van bovenaf, 55 = third-person, 65 = bijna first-person.",
    map3d_editor_chase_zoom: "Chase-cam zoom (14-19)",
    map3d_editor_chase_zoom_hint: "Hogere zoom = dichter bij de fiets. 17 ≈ 100 m vooruit zichtbaar.",
    map3d_editor_animate_seconds: "Afspeelduur (seconden)",
    map3d_editor_animate_seconds_hint: "Hoe lang een volledige Play-cyclus duurt van begin tot einde van de tour.",
    map3d_editor_smooth_window: "Bearing-smoothingvenster",
    map3d_editor_smooth_window_hint: "Hoger = soepelere camera, trager. 15 is goede default; 5 schokkerig, 40 snijdt bochten breed af.",
    map3d_editor_track_smooth: "Track-positie smoothingvenster",
    map3d_editor_track_smooth_hint: "Smoothet GPS-jitter in het camerapad. 0 = uit (ruwe GPS), 2 = mild (default), 5+ kan zichtbaar bochten afsnijden. De weergegeven track-lijn toont altijd de ruwe GPS, ongeacht deze instelling.",
    map3d_editor_playback_speed: "Afspeelsnelheid (×)",
    map3d_editor_playback_speed_hint: "Realtime-vermenigvuldiger. 60 = 60× sneller dan de echte rit; een 1u-rit speelt in 1 min, 2u-rit in 2 min. Hoger = sneller.",
    map3d_editor_animate_seconds_override_hint: "Optioneel. Indien ingesteld dwingt dit een vaste afspeelduur af, ongeacht de toerlengte, en overschrijft de snelheidsfactor.",
    map3d_sun_night: "Nacht",
    map3d_sun_twilight: "Schemering",
    map3d_sun_golden: "Gouden uur",
    map3d_sun_morning: "Daglicht",
    map3d_sun_day: "Daglicht",
    map3d_record_start: "Opnemen",
    map3d_record_stop: "Stop",
    map3d_record_active: "Opname loopt…",
    map3d_record_unsupported: "Opname in deze browser niet ondersteund",
  },
};

/**
 * Look up a localized string. `hass` may be null during early init.
 * Falls back to English when the requested key is missing.
 */
function ebT(hass, key, ...args) {
  const lang = ((hass && hass.locale && hass.locale.language) || "en")
    .slice(0, 2).toLowerCase();
  const dict = I18N[lang] || I18N.en;
  const value = dict[key] !== undefined ? dict[key] : I18N.en[key];
  if (value === undefined) return key;
  return typeof value === "function" ? value(...args) : value;
}

const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";

function ensureLeafletCss() {
  if (document.querySelector(`link[href="${LEAFLET_CSS}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = LEAFLET_CSS;
  document.head.appendChild(link);
}

const MAP_STYLES = {
  osm: {
    label: "OSM",
    nameKey: "style_standard",
    url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
    options: { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2, attribution: '&copy; OpenStreetMap contributors &copy; CARTO' }
  },
  topo: {
    label: "Topo",
    nameKey: "style_topo",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 17, updateWhenIdle: true, keepBuffer: 2 }
  },
  sat: {
    label: "Sat",
    nameKey: "style_sat",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    options: { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2 }
  }
};

const LEAFLET_INLINE_CSS = `
.leaflet-pane, .leaflet-tile, .leaflet-marker-icon, .leaflet-marker-shadow,
.leaflet-tile-container, .leaflet-pane > svg, .leaflet-pane > canvas,
.leaflet-zoom-box, .leaflet-image-layer, .leaflet-layer {
  position: absolute; left: 0; top: 0;
}
.leaflet-container { overflow: hidden; font-family: inherit; font-size: 12px; }
.leaflet-tile, .leaflet-marker-icon, .leaflet-marker-shadow { user-select: none; -webkit-user-select: none; }
.leaflet-tile { filter: inherit; visibility: hidden; }
.leaflet-tile-loaded { visibility: inherit; }
.leaflet-tile-container { pointer-events: none; }
.leaflet-zoom-animated { transform-origin: 0 0; }
.leaflet-tile { image-rendering: auto; width: 256px; height: 256px; }
.leaflet-container { background: #ddd; outline-offset: 1px; }
.leaflet-container a { color: #0078A8; }
.leaflet-zoom-box { border: 2px dotted #38f; background: rgba(255,255,255,0.5); }
.leaflet-pane { z-index: 400; }
.leaflet-tile-pane { z-index: 200; }
.leaflet-overlay-pane { z-index: 400; }
.leaflet-shadow-pane { z-index: 500; }
.leaflet-marker-pane { z-index: 600; }
.leaflet-tooltip-pane { z-index: 650; }
.leaflet-popup-pane { z-index: 700; }
.leaflet-map-pane canvas { z-index: 100; }
.leaflet-map-pane svg { z-index: 200; }
.leaflet-control { position: relative; z-index: 800; pointer-events: visiblePainted; pointer-events: auto; }
.leaflet-top, .leaflet-bottom { position: absolute; z-index: 1000; pointer-events: none; }
.leaflet-top { top: 0; }
.leaflet-right { right: 0; }
.leaflet-bottom { bottom: 0; }
.leaflet-left { left: 0; }
.leaflet-top .leaflet-control, .leaflet-bottom .leaflet-control { margin-top: 10px; }
.leaflet-top .leaflet-control:first-child { margin-top: 0; }
.leaflet-bottom .leaflet-control { margin-bottom: 10px; }
.leaflet-left .leaflet-control { margin-left: 10px; }
.leaflet-right .leaflet-control { margin-right: 10px; }
.leaflet-fade-anim .leaflet-popup { opacity: 1; transition: opacity 0.2s linear; }
.leaflet-fade-anim .leaflet-map-pane .leaflet-popup { opacity: 1; }
.leaflet-zoom-anim .leaflet-zoom-animated { transition: transform 0.25s cubic-bezier(0,0,0.25,1); }
.leaflet-pan-anim .leaflet-tile, .leaflet-zoom-anim .leaflet-zoom-hide { visibility: hidden; }
.leaflet-zoom-anim .leaflet-zoom-animated { will-change: transform; }
.leaflet-control-zoom a { width: 30px; height: 30px; line-height: 30px; display: block; text-align: center; text-decoration: none; color: black; background: white; border-bottom: 1px solid #ccc; }
.leaflet-control-zoom a:hover { background: #f4f4f4; }
.leaflet-control-zoom-in { border-top-left-radius: 4px; border-top-right-radius: 4px; font-size: 18px; }
.leaflet-control-zoom-out { border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; font-size: 20px; }
.leaflet-control-zoom { box-shadow: 0 1px 5px rgba(0,0,0,0.4); border-radius: 5px; }
.leaflet-touch .leaflet-control-zoom a { width: 36px; height: 36px; line-height: 36px; font-size: 20px; }
.leaflet-interactive { cursor: pointer; }
.leaflet-grab { cursor: grab; }
.leaflet-crosshair, .leaflet-crosshair .leaflet-interactive { cursor: crosshair; }
.leaflet-dragging .leaflet-grab, .leaflet-dragging .leaflet-grab .leaflet-interactive,
.leaflet-dragging .leaflet-marker-draggable { cursor: move; cursor: grabbing; }
.leaflet-image-layer, .leaflet-pane > svg path, .leaflet-tile-container { pointer-events: none; }
.leaflet-image-layer.leaflet-interactive, .leaflet-pane > svg path.leaflet-interactive, svg.leaflet-image-layer.leaflet-interactive path { pointer-events: visiblePainted; pointer-events: auto; }
.leaflet-container a.leaflet-active { outline: 2px solid orange; }
.leaflet-tooltip { position: absolute; padding: 4px 8px; background-color: #fff; border: 1px solid #fff; border-radius: 3px; color: #222; white-space: nowrap; pointer-events: none; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }
`;

function ensureLeaflet() {
  ensureLeafletCss();
  if (window.L && typeof window.L.map === "function") return Promise.resolve(window.L);
  if (window.__ebikeLeafletPromise) return window.__ebikeLeafletPromise;

  window.__ebikeLeafletPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${LEAFLET_JS}"]`);
    if (existing) {
      const finish = () => {
        if (window.L && typeof window.L.map === "function") resolve(window.L);
        else reject(new Error("Leaflet wurde geladen, ist aber nicht verfügbar"));
      };
      existing.addEventListener("load", finish, { once: true });
      existing.addEventListener("error", () => reject(new Error("Leaflet konnte nicht geladen werden")), { once: true });
      if (window.L && typeof window.L.map === "function") finish();
      return;
    }

    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.async = true;
    script.onload = () => {
      if (window.L && typeof window.L.map === "function") resolve(window.L);
      else reject(new Error("Leaflet wurde geladen, ist aber nicht verfügbar"));
    };
    script.onerror = () => reject(new Error("Leaflet konnte nicht geladen werden"));
    document.head.appendChild(script);
  });

  return window.__ebikeLeafletPromise;
}

// ===========================================================================
// MapLibre GL + OpenFreeMap helpers for the 3D Map card (lazy-loaded)
// ===========================================================================
const MAPLIBRE_JS = "https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.js";
const MAPLIBRE_CSS = "https://unpkg.com/maplibre-gl@5.6.0/dist/maplibre-gl.css";
const OPENFREEMAP_LIBERTY = "https://tiles.openfreemap.org/styles/liberty";

function ensureMapLibre() {
  if (window.maplibregl) return Promise.resolve(window.maplibregl);
  if (window.__ebikeMapLibrePromise) return window.__ebikeMapLibrePromise;
  window.__ebikeMapLibrePromise = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${MAPLIBRE_CSS}"]`)) {
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = MAPLIBRE_CSS;
      document.head.appendChild(l);
    }
    if (window.maplibregl) return resolve(window.maplibregl);
    const s = document.createElement("script");
    s.src = MAPLIBRE_JS;
    s.onload = () => resolve(window.maplibregl);
    s.onerror = () => reject(new Error("MapLibre GL could not be loaded"));
    document.head.appendChild(s);
  });
  return window.__ebikeMapLibrePromise;
}

// Lightweight NOAA-based sun position. Returns { altitude, azimuth } in radians.
function sunPositionAt(date, lat, lon) {
  const rad = Math.PI / 180;
  const dayMs = 86400000;
  const J1970 = 2440588;
  const J2000 = 2451545;
  const toJulian = (d) => d.valueOf() / dayMs - 0.5 + J1970;
  const toDays = (d) => toJulian(d) - J2000;
  const e = rad * 23.4397;
  const solarMeanAnomaly = (d) => rad * (357.5291 + 0.98560028 * d);
  const eclipticLongitude = (M) => {
    const C = rad * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M));
    const P = rad * 102.9372;
    return M + C + P + Math.PI;
  };
  const declination = (l) => Math.asin(Math.sin(e) * Math.sin(l));
  const rightAscension = (l) => Math.atan2(Math.sin(l) * Math.cos(e), Math.cos(l));
  const siderealTime = (d, lw) => rad * (280.16 + 360.9856235 * d) - lw;
  const d = toDays(date);
  const M = solarMeanAnomaly(d);
  const L = eclipticLongitude(M);
  const ra = rightAscension(L);
  const dec = declination(L);
  const lw = rad * -lon;
  const phi = rad * lat;
  const H = siderealTime(d, lw) - ra;
  const altitude = Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(H));
  const azimuth = Math.atan2(Math.sin(H), Math.cos(H) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi));
  return { altitude, azimuth };
}

// Andrew's monotone-chain convex hull. Input: [[x,y], ...]. Output: hull
// vertices in CCW order (NOT closed; caller pushes hull[0] to close).
function convexHull2D(points) {
  if (points.length < 3) return points.slice();
  const sorted = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (O, A, B) =>
    (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0]);
  const lower = [];
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
      lower.pop();
    }
    lower.push(p);
  }
  const upper = [];
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
      upper.pop();
    }
    upper.push(p);
  }
  return lower.concat(upper.slice(1, -1));
}

// Project a building footprint's cast shadow on the ground.
// sunAlt, sunAz: radians (sunAz convention from sunPositionAt: 0 = south,
// +π/2 = west, ±π = north). Returns a closed GeoJSON Polygon ring (last
// vertex equals first) or null if the sun is below the horizon.
function buildingShadowRing(ring, heightM, sunAlt, sunAz, refLat) {
  if (sunAlt <= 0) return null;
  if (!ring || ring.length < 3) return null;
  if (!Number.isFinite(heightM) || heightM <= 0) return null;
  // Shadow compass bearing (from north clockwise) = sun.azimuth + 2π mod 2π
  // (because sun compass = my_az + π, shadow compass = sun_compass + π).
  const shadowCompass = (sunAz + 2 * Math.PI) % (2 * Math.PI);
  const shadowLenM = Math.min(400, heightM / Math.tan(sunAlt));
  // Convert meters to lat/lon offsets
  const dLatPerM = 1 / 111320;
  const cosLat = Math.cos(refLat * Math.PI / 180);
  const dLonPerM = 1 / (111320 * Math.max(0.05, cosLat));
  const dLat = shadowLenM * Math.cos(shadowCompass) * dLatPerM;
  const dLon = shadowLenM * Math.sin(shadowCompass) * dLonPerM;
  // Original ring + projected ring, then convex hull
  const all = [];
  for (const v of ring) {
    if (!Array.isArray(v) || v.length < 2) continue;
    all.push([v[0], v[1]]);
    all.push([v[0] + dLon, v[1] + dLat]);
  }
  if (all.length < 3) return null;
  const hull = convexHull2D(all);
  if (hull.length < 3) return null;
  hull.push(hull[0]); // close the ring
  return hull;
}

// Map a sun altitude (degrees) to a tint that conveys time of day.
function sunMoodFor(altDeg) {
  if (altDeg < -6)  return { fog: "#0c1228", sky: "#0a1530", sun: "#2a3a5a", label: "night" };
  if (altDeg < 0)   return { fog: "#3a2638", sky: "#cf6a3e", sun: "#ff7e3e", label: "twilight" };
  if (altDeg < 10)  return { fog: "#c89c6a", sky: "#ffb777", sun: "#ffa566", label: "golden" };
  if (altDeg < 30)  return { fog: "#d9c8a3", sky: "#bfdcff", sun: "#ffd884", label: "morning" };
  return                { fog: "#cfe2f2", sky: "#a8d2ff", sun: "#ffffff", label: "day" };
}

class BoschEBikeMapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._allActivities = [];   // unfiltered, all accounts/bikes
    this._activities = [];      // filtered view
    this._instances = [];        // [{config_entry_id, label, bikes:[{id,label}]}]
    this._filterAccount = "all"; // "all" | config_entry_id
    this._filterBike = "all";    // "all" | bike_id
    this._idx = 0;
    this._currentTrack = [];
    this._currentTrackActivityId = null;
    // Wikipedia overlay
    this._wikiEnabled = (typeof localStorage !== "undefined" && localStorage.getItem("eb-wiki-enabled") === "1");
    this._wikiArticles = new Map();   // activityId → [{pageId, title, lat, lon, lang}]
    this._wikiLoading = new Set();    // activity IDs currently being fetched
    this._wikiSummaries = new Map();  // pageId → {extract, thumbnail}
    this._wikiGroup = null;
    this._fullscreenWikiGroup = null;
    // Which activityId is currently rendered on each map (avoid re-rendering and killing open popups)
    this._wikiRenderedInline = null;
    this._wikiRenderedFullscreen = null;
    // POI overlay (Overpass)
    this._poiEnabled = (typeof localStorage !== "undefined" && localStorage.getItem("eb-poi-enabled") === "1");
    this._poiData = new Map();        // activityId → [{lat, lon, name, category, tags}]
    this._poiLoading = new Set();
    this._poiGroup = null;
    this._fullscreenPoiGroup = null;
    this._poiRenderedInline = null;
    this._poiRenderedFullscreen = null;

    this._map = null;
    this._trackGroup = null;
    this._inlineBaseLayer = null;
    this._legend = null;
    this._fullscreenMap = null;
    this._fullscreenTrackGroup = null;
    this._fullscreenBaseLayer = null;
    this._fullscreenLegend = null;
    this._resizeObserver = null;
    this._intersectionObserver = null;
    this._timers = new Set();

    this._fullscreenOpen = false;
    this._mapStyle = "osm";
    this._fullscreenTab = "map";
    this._sortKey = "date";
    this._sortAsc = false;
    this._inlineBaseLayer = null;
    this._fullscreenBaseLayer = null;

    this._ready = false;
    this._booting = false;
    this._connected = false;
    this._busy = false;
    this._leafletReady = false;
    this._mapVisible = false;
    this._pendingRender = false;
    this._loadSeq = 0;
    this._appliedLoadSeq = 0;

    this._boundVisibility = this._onVisibilityChange.bind(this);
    this._boundFocus = this._onFocus.bind(this);
    this._boundPageShow = this._onPageShow.bind(this);
    this._boundKeydown = this._onKeydown.bind(this);
  }

  setConfig(config) {
    const prevRadius = this._wikiRadius;
    this._config = { height: config.height || 400, ...config };
    // Allow pinning the card to a specific account / bike via Lovelace config.
    // When set, the corresponding dropdown is hidden and the filter is locked.
    if (config.account_id) {
      this._filterAccount = config.account_id;
      this._lockedAccount = true;
    } else {
      this._lockedAccount = false;
    }
    if (config.bike_id) {
      this._filterBike = config.bike_id;
      this._lockedBike = true;
    } else {
      this._lockedBike = false;
    }
    // Wikipedia search radius (m). Default 1000. Allowed: 500, 1000, 2000, 5000, 10000.
    const allowed = [500, 1000, 2000, 5000, 10000];
    const requested = parseInt(config.wiki_radius_m, 10);
    this._wikiRadius = allowed.includes(requested) ? requested : 1000;
    // POI proximity radius (m) — how far from the route a POI may be. Default 1000.
    const prevPoiRadius = this._poiRadius;
    const poiAllowed = [500, 1000, 2000, 5000, 10000];
    const poiRequested = parseInt(config.poi_radius_m, 10);
    this._poiRadius = poiAllowed.includes(poiRequested) ? poiRequested : 1000;

    // If the card was already built once (re-config without re-creation),
    // refresh UI and re-render
    if (this._ready) {
      this._applyConfigTitle();
      this._populateFilterUI();
      this._applyFilter();
      // Wikipedia radius changed → invalidate cached articles, re-fetch if layer active
      if (prevRadius !== undefined && prevRadius !== this._wikiRadius) {
        this._wikiArticles.clear();
        this._wikiRenderedInline = null;
        this._wikiRenderedFullscreen = null;
        if (this._wikiGroup) try { this._wikiGroup.clearLayers(); } catch (_) {}
        if (this._fullscreenWikiGroup) try { this._fullscreenWikiGroup.clearLayers(); } catch (_) {}
        if (this._wikiEnabled && this._currentTrackActivityId) this._loadAndRenderWiki();
      }
      // POI radius changed → invalidate cached POIs, re-fetch if layer active
      if (prevPoiRadius !== undefined && prevPoiRadius !== this._poiRadius) {
        this._poiData.clear();
        this._poiRenderedInline = null;
        this._poiRenderedFullscreen = null;
        if (this._poiGroup) try { this._poiGroup.clearLayers(); } catch (_) {}
        if (this._fullscreenPoiGroup) try { this._fullscreenPoiGroup.clearLayers(); } catch (_) {}
        if (this._poiEnabled && this._currentTrackActivityId) this._loadAndRenderPoi();
      }
      if (this._activities.length) this._show(0, true);
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
    else if (this._connected) this._scheduleActivation("hass update");
  }

  connectedCallback() {
    this._connected = true;
    if (this._ready) {
      this._attachLifecycleHooks();
      this._scheduleActivation("connected");
    }
  }

  disconnectedCallback() {
    this._connected = false;
    this._detachLifecycleHooks();
    this._clearTimers();
    this._destroyFullscreenMap();
    this._destroyMap(false);
  }

  getCardSize() {
    return Math.ceil((this._config.height || 400) / 50) + 4;
  }

  static getConfigElement() { return document.createElement("bosch-ebike-map-card-editor"); }
  static getStubConfig() { return { height: 400 }; }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;

    if (!this._ready) {
      this._buildDOM();
      this._attachLifecycleHooks();
      this._ready = true;
    }

    try {
      await ensureLeaflet();
      this._leafletReady = true;
      this._applyConfigTitle();
      await this._fetchInstances();
      await this._fetchActivities();
      this._scheduleActivation("boot finished");
    } catch (error) {
      console.error("[Bosch eBike Map] boot error", error);
      this._msg(this._t("msg_error_prefix") + (error?.message || error));
    } finally {
      this._booting = false;
    }
  }

  _buildDOM() {
    const h = this._config.height || 400;
    this.innerHTML = "";

    const card = document.createElement("ha-card");
    this.appendChild(card);

    const style = document.createElement("style");
    style.textContent = LEAFLET_INLINE_CSS + `
      .eb-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .eb-head svg { flex-shrink:0; }
      .eb-nav {
        display:flex; align-items:center; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .eb-nav button, .eb-icon-btn {
        width:36px; height:36px; flex-shrink:0;
        background:var(--primary-color,#03a9f4); color:#fff;
        border:none; border-radius:8px; cursor:pointer; font-size:16px;
        display:flex; align-items:center; justify-content:center;
      }
      .eb-nav button:disabled, .eb-icon-btn:disabled { opacity:.35; cursor:not-allowed; }
      .eb-nav input[type="date"] {
        flex:1; min-width:0; padding:6px 10px;
        border:1px solid var(--divider-color,#ccc); border-radius:6px; font-size:14px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .eb-ctr { font-size:13px; color:var(--secondary-text-color,#666); white-space:nowrap; flex-shrink:0; }
      .eb-sort {
        display:flex; align-items:center; gap:8px; padding:6px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .eb-sort select {
        flex:1; min-width:0; padding:5px 8px;
        border:1px solid var(--divider-color,#ccc); border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .eb-sort button {
        width:36px; height:36px; flex-shrink:0;
        background:var(--primary-color,#03a9f4); color:#fff;
        border:none; border-radius:8px; cursor:pointer; font-size:16px;
        display:flex; align-items:center; justify-content:center;
      }
      .eb-sort-lbl { font-size:12px; color:var(--secondary-text-color,#666); white-space:nowrap; flex-shrink:0; }
      .eb-icon-btn.eb-active {
        background:rgba(11,132,199,.95) !important;
        outline:2px solid rgba(255,255,255,.6);
      }
      .eb-icon-btn.eb-loading {
        opacity:.6;
        animation:eb-pulse 1.2s ease-in-out infinite;
      }
      @keyframes eb-pulse {
        0%,100% { opacity:.55; }
        50%     { opacity:.95; }
      }
      .eb-wiki-marker {
        background:rgba(255,255,255,.95);
        border:1.5px solid #0b84c7;
        border-radius:50%;
        width:14px !important; height:14px !important;
        display:flex; align-items:center; justify-content:center;
        font-family:Georgia,serif; font-style:italic; font-weight:700;
        color:#0b84c7; font-size:10px; line-height:1;
        box-shadow:0 1px 3px rgba(0,0,0,.3);
        cursor:pointer;
      }
      .eb-wiki-popup { font-family:inherit; max-width:280px; }
      .eb-wiki-popup .eb-wiki-title { font-size:15px; font-weight:600; margin-bottom:6px; color:#222; }
      .eb-wiki-popup .eb-wiki-thumb {
        max-width:100%; max-height:140px; border-radius:6px; margin-bottom:6px; display:block;
      }
      .eb-wiki-popup .eb-wiki-extract { font-size:12px; color:#444; line-height:1.35; margin-bottom:8px; }
      .eb-wiki-popup .eb-wiki-link {
        display:inline-block; padding:4px 10px;
        background:#0b84c7; color:#fff; border-radius:6px;
        text-decoration:none; font-size:12px; font-weight:500;
      }
      .eb-wiki-popup .eb-wiki-link:hover { background:#096ba3; }
      .eb-wiki-popup .eb-wiki-loading { font-size:12px; color:#888; }
      .eb-poi-marker {
        background:rgba(255,255,255,.95);
        border-radius:50%;
        width:18px !important; height:18px !important;
        display:flex; align-items:center; justify-content:center;
        font-size:12px; line-height:1;
        box-shadow:0 1px 3px rgba(0,0,0,.3);
        cursor:pointer;
      }
      .eb-poi-marker.eb-poi-charging { border:1.5px solid #2e7d32; }
      .eb-poi-marker.eb-poi-bicycle  { border:1.5px solid #c62828; }
      .eb-poi-marker.eb-poi-water    { border:1.5px solid #1565c0; }
      .eb-poi-marker.eb-poi-toilet   { border:1.5px solid #6a1b9a; }
      .eb-poi-popup { font-family:inherit; max-width:240px; font-size:13px; }
      .eb-poi-popup .eb-poi-title { font-weight:600; margin-bottom:4px; }
      .eb-poi-popup .eb-poi-cat { font-size:11px; color:#666; margin-bottom:6px; }
      .eb-poi-popup .eb-poi-link {
        display:inline-block; padding:3px 8px;
        background:#0b84c7; color:#fff; border-radius:6px;
        text-decoration:none; font-size:11px; font-weight:500;
      }
      .eb-map-wrap { position:relative; }
      .eb-map { width:100% !important; height:${h}px !important; min-height:${h}px; z-index:0; position:relative; }
      .eb-overlay-msg {
        position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
        color:var(--secondary-text-color,#999); font-size:14px; background:transparent; pointer-events:none;
      }
      .eb-map-tools {
        position:absolute; right:12px; top:12px; z-index:1100;
        display:flex; gap:8px;
      }
      .eb-map-tools .eb-icon-btn {
        width:40px; height:40px;
        background:rgba(33,33,33,.72); backdrop-filter:blur(4px);
        box-shadow:0 2px 8px rgba(0,0,0,.25);
      }
      .eb-title { text-align:center; padding:10px 16px 2px; font-size:16px; font-weight:600; color:var(--primary-text-color,#333); }
      .eb-datelbl { text-align:center; font-size:12px; color:var(--secondary-text-color,#666); padding:0 16px 6px; }
      .eb-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:4px; padding:8px 16px 14px; }
      .eb-stat { text-align:center; }
      .eb-val { font-size:20px; font-weight:700; color:var(--primary-text-color,#212121); }
      .eb-lbl { font-size:11px; color:var(--secondary-text-color,#757575); }

      .eb-fullscreen {
        position:fixed; inset:0; z-index:99999;
        display:none; align-items:stretch; justify-content:stretch;
        background:rgba(0,0,0,.72);
      }
      .eb-fullscreen.open { display:flex; }
      .eb-fullscreen-card {
        width:min(1400px, 100vw); height:100vh; margin:auto;
        background:var(--card-background-color,#111);
        display:flex; flex-direction:column;
        overflow-y:auto;
        -webkit-overflow-scrolling:touch;
      }
      .eb-fullscreen-head {
        display:flex; align-items:center; gap:8px;
        padding:10px 12px; color:#fff;
        background:rgba(0,0,0,.35);
        border-bottom:1px solid rgba(255,255,255,.12);
      }
      .eb-fullscreen-title { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:600; }
      .eb-fullscreen-nav { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
      .eb-fullscreen-nav input[type="date"] { min-width:170px; padding:6px 10px; border:1px solid rgba(255,255,255,.2); border-radius:8px; background:rgba(255,255,255,.12); color:#fff; }
      .eb-fullscreen-nav .eb-ctr { color:rgba(255,255,255,.8); }
      .eb-fullscreen-map { flex:1; min-height:280px; position:relative; }
      .eb-profile { background:var(--card-background-color,#fff); border-top:1px solid var(--divider-color,#ddd); padding:12px 14px 8px; overflow:visible; }
      .eb-profile-head { display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin-bottom:8px; }
      .eb-profile-title { font-size:16px; font-weight:600; color:var(--primary-text-color,#222); }
      .eb-profile-range { font-size:12px; color:var(--secondary-text-color,#666); }
      .eb-profile-chart { width:100%; height:180px; display:block; }
      .eb-profile-axis { display:flex; justify-content:space-between; font-size:11px; color:var(--secondary-text-color,#777); margin-top:4px; }
      .eb-profile-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:10px; }
      .eb-profile-stat { background:var(--secondary-background-color,#f5f5f5); border-radius:10px; padding:10px 8px; text-align:center; }
      .eb-profile-stat .eb-pv { font-size:16px; font-weight:700; color:var(--primary-text-color,#212121); }
      .eb-profile-stat .eb-pl { font-size:11px; color:var(--secondary-text-color,#757575); margin-top:2px; }
      .eb-fullscreen-meta {
        padding:8px 12px; display:grid; grid-template-columns:repeat(4,1fr); gap:8px;
        background:var(--card-background-color,#fff);
        border-top:1px solid var(--divider-color,#ddd);
      }
      .eb-fullscreen-meta .eb-stat { background:var(--secondary-background-color,#f5f5f5); border-radius:10px; padding:8px 4px; }
      .eb-fullscreen-tabs {
        display:flex; gap:8px; padding:10px 12px 0;
        background:#fff !important;
        border-bottom:1px solid var(--divider-color,#ddd);
      }
      .eb-fullscreen-tabs .eb-fullscreen-tab {
        appearance:none; border:none; background:transparent !important; color:#222 !important;
        opacity:1 !important; visibility:visible !important;
        padding:10px 2px 12px; margin:0 10px 0 0; font-size:14px; font-weight:600; cursor:pointer;
        border-bottom:2px solid transparent;
      }
      .eb-fullscreen-tabs .eb-fullscreen-tab.active {
        color:#111 !important; border-bottom-color:var(--primary-color,#03a9f4);
      }
      .eb-hidden { display:none !important; }
      @media (max-width: 700px) {
        .eb-stats { grid-template-columns:repeat(2,1fr); }
        .eb-profile-stats { grid-template-columns:repeat(2,1fr); }
        .eb-fullscreen-meta { grid-template-columns:repeat(2,1fr); }
        .eb-fullscreen-head { flex-wrap:wrap; }
        .eb-fullscreen-title { width:100%; }
        .eb-fullscreen-nav { width:100%; }
        .eb-fullscreen-nav input[type="date"] { flex:1; min-width:0; }
        .eb-fullscreen-card { overflow-y:auto; -webkit-overflow-scrolling:touch; }
      }
    `;
    card.appendChild(style);

    const wrap = document.createElement("div");
    const t = (k) => this._t(k);
    wrap.innerHTML = `
      <div class="eb-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M15.5,5.5C16.9,5.5 18,6.6 18,8C18,9.4 16.9,10.5 15.5,10.5C14.1,10.5 13,9.4 13,8C13,6.6 14.1,5.5 15.5,5.5M5,12C2.2,12 0,14.2 0,17C0,19.8 2.2,22 5,22C7.8,22 10,19.8 10,17C10,14.2 7.8,12 5,12M5,20.5C3.1,20.5 1.5,18.9 1.5,17C1.5,15.1 3.1,13.5 5,13.5C6.9,13.5 8.5,15.1 8.5,17C8.5,18.9 6.9,20.5 5,20.5M19,12C16.2,12 14,14.2 14,17C14,19.8 16.2,22 19,22C21.8,22 24,19.8 24,17C24,14.2 21.8,12 19,12M19,20.5C17.1,20.5 15.5,18.9 15.5,17C15.5,15.1 17.1,13.5 19,13.5C20.9,13.5 22.5,15.1 22.5,17C22.5,18.9 20.9,20.5 19,20.5M12.5,11.5L10.1,8.8C10.6,7.8 11.4,7.3 12.3,7.3H14.2L12.9,6H10.3C9.1,6 8,6.7 7.5,7.8L6.1,10.8L5,12.1L7.2,13.5L8.3,11.5H12.5Z"/></svg>
        <span>${t("rides_title")}</span>
      </div>
      <div class="eb-nav">
        <button id="eb-prev">◀</button>
        <input type="date" id="eb-date">
        <button id="eb-next">▶</button>
        <span id="eb-ctr" class="eb-ctr">–</span>
      </div>
      <div class="eb-sort" id="eb-filter-account-wrap" style="display:none;">
        <span class="eb-sort-lbl">${t("account_label")}</span>
        <select id="eb-filter-account">
          <option value="all">${t("all_accounts")}</option>
        </select>
      </div>
      <div class="eb-sort" id="eb-filter-bike-wrap" style="display:none;">
        <span class="eb-sort-lbl">${t("bike_label")}</span>
        <select id="eb-filter-bike">
          <option value="all">${t("all_bikes")}</option>
        </select>
      </div>
      <div class="eb-sort">
        <span class="eb-sort-lbl">${t("sort_label")}</span>
        <select id="eb-sort-key">
          <option value="date">${t("sort_date")}</option>
          <option value="distance">${t("sort_distance")}</option>
          <option value="duration">${t("sort_duration")}</option>
          <option value="avgSpeed">${t("sort_avg_speed")}</option>
          <option value="maxSpeed">${t("sort_max_speed")}</option>
          <option value="elevation">${t("sort_elevation")}</option>
          <option value="calories">${t("sort_calories")}</option>
          <option value="difficulty">${t("sort_difficulty")}</option>
          <option value="batteryWh">${t("sort_battery_wh")}</option>
          <option value="batteryPct">${t("sort_battery_pct")}</option>
        </select>
        <button id="eb-sort-dir" title="${t("sort_dir_title")}">↓</button>
      </div>
      <div class="eb-map-wrap">
        <div id="eb-map" class="eb-map"></div>
        <div class="eb-map-tools">
          <button id="eb-style" class="eb-icon-btn eb-style-btn" title="${t("btn_change_style")}" aria-label="${t("btn_change_style")}">OSM</button>
          <button id="eb-wiki" class="eb-icon-btn" title="${t("btn_wiki")}" aria-label="${t("btn_wiki")}">📚</button>
          <button id="eb-poi" class="eb-icon-btn" title="${t("btn_poi")}" aria-label="${t("btn_poi")}">📍</button>
          <button id="eb-gpx" class="eb-icon-btn" title="${t("btn_gpx")}" aria-label="${t("btn_gpx")}">GPX</button>
          <button id="eb-fullscreen" class="eb-icon-btn" title="${t("btn_fullscreen")}" aria-label="${t("btn_fullscreen")}">
            <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M7,14H5V19H10V17H7V14M5,10H7V7H10V5H5V10M17,17H14V19H19V14H17V17M14,5V7H17V10H19V5H14Z"/></svg>
          </button>
        </div>
        <div id="eb-overlay-msg" class="eb-overlay-msg"></div>
      </div>
      <div id="eb-title" class="eb-title"></div>
      <div id="eb-date-lbl" class="eb-datelbl"></div>
      <div id="eb-stats" class="eb-stats"></div>
      <div id="eb-fullscreen-overlay" class="eb-fullscreen" aria-hidden="true">
        <div class="eb-fullscreen-card">
          <div class="eb-fullscreen-head">
            <div id="eb-fullscreen-title" class="eb-fullscreen-title">${t("rides_title")}</div>
            <div class="eb-fullscreen-nav">
              <button id="eb-full-prev" class="eb-icon-btn" title="${t("btn_prev")}" aria-label="${t("btn_prev")}">◀</button>
              <input type="date" id="eb-full-date">
              <button id="eb-full-next" class="eb-icon-btn" title="${t("btn_next")}" aria-label="${t("btn_next")}">▶</button>
              <span id="eb-full-ctr" class="eb-ctr">–</span>
            </div>
            <button id="eb-full-style" class="eb-icon-btn eb-style-btn" title="${t("btn_change_style")}" aria-label="${t("btn_change_style")}">OSM</button>
            <button id="eb-full-wiki" class="eb-icon-btn" title="${t("btn_wiki")}" aria-label="${t("btn_wiki")}">📚</button>
            <button id="eb-full-poi" class="eb-icon-btn" title="${t("btn_poi")}" aria-label="${t("btn_poi")}">📍</button>
            <button id="eb-full-gpx" class="eb-icon-btn" title="${t("btn_gpx")}" aria-label="${t("btn_gpx")}">GPX</button>
            <button id="eb-fit" class="eb-icon-btn" title="${t("btn_fit")}" aria-label="${t("btn_fit")}">
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M4,4H10V6H6V10H4V4M14,4H20V10H18V6H14V4M4,14H6V18H10V20H4V14M18,14H20V20H14V18H18V14Z"/></svg>
            </button>
            <button id="eb-full-close" class="eb-icon-btn" title="${t("btn_close")}" aria-label="${t("btn_close")}">
              <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z"/></svg>
            </button>
          </div>
          <div class="eb-fullscreen-tabs" role="tablist" aria-label="${t("btn_view_label")}">
            <button id="eb-tab-map" class="eb-fullscreen-tab active" role="tab" aria-selected="true">${t("tab_map")}</button>
            <button id="eb-tab-elevation" class="eb-fullscreen-tab" role="tab" aria-selected="false">${t("tab_elevation")}</button>
          </div>
          <div id="eb-fullscreen-map" class="eb-fullscreen-map"></div>
          <div id="eb-fullscreen-profile" class="eb-profile eb-hidden"></div>
          <div id="eb-fullscreen-meta" class="eb-fullscreen-meta"></div>
        </div>
      </div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this._$("eb-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-next").addEventListener("click", () => this._go(1));
    this._$("eb-date").addEventListener("change", (e) => this._jumpDate(e.target.value));
    this._$("eb-style").addEventListener("click", () => this._cycleMapStyle());
    this._$("eb-gpx").addEventListener("click", () => this._downloadCurrentGpx());
    this._$("eb-fullscreen").addEventListener("click", () => this._openFullscreen());
    this._$("eb-full-style").addEventListener("click", () => this._cycleMapStyle());
    this._$("eb-full-gpx").addEventListener("click", () => this._downloadCurrentGpx());
    this._$("eb-full-close").addEventListener("click", () => this._closeFullscreen());
    this._$("eb-wiki").addEventListener("click", () => this._toggleWikipedia());
    const fullWiki = this._$("eb-full-wiki");
    if (fullWiki) fullWiki.addEventListener("click", () => this._toggleWikipedia());
    this._$("eb-poi").addEventListener("click", () => this._togglePoi());
    const fullPoi = this._$("eb-full-poi");
    if (fullPoi) fullPoi.addEventListener("click", () => this._togglePoi());
    this._$("eb-tab-map").addEventListener("click", () => this._setFullscreenTab("map"));
    this._$("eb-tab-elevation").addEventListener("click", () => this._setFullscreenTab("elevation"));
    this._$("eb-full-prev").addEventListener("click", () => this._go(-1));
    this._$("eb-full-next").addEventListener("click", () => this._go(1));
    this._$("eb-full-date").addEventListener("change", (e) => this._jumpDate(e.target.value));
    this._$("eb-fit").addEventListener("click", () => {
      this._fullscreenUserAdjustedView = false;
      this._needsFullscreenFit = false;
      this._fitMapToTrack(this._fullscreenMap, this._currentTrack, [60, 60]);
    });
    this._$("eb-fullscreen-overlay").addEventListener("click", (e) => {
      if (e.target === this._$("eb-fullscreen-overlay")) this._closeFullscreen();
    });

    this._$("eb-sort-key").addEventListener("change", (e) => {
      this._sortKey = e.target.value;
      this._applySort();
    });
    this._$("eb-sort-dir").addEventListener("click", () => {
      this._sortAsc = !this._sortAsc;
      this._$("eb-sort-dir").textContent = this._sortAsc ? "↑" : "↓";
      this._applySort();
    });

    const accountSel = this._$("eb-filter-account");
    if (accountSel) {
      accountSel.addEventListener("change", (e) => {
        this._filterAccount = e.target.value;
        this._populateFilterUI(); // refresh bike dropdown to match account
        this._applyFilter();
        if (this._activities.length) {
          this._show(0, true);
        } else {
          this._msg(this._t("msg_no_filter_match"));
        }
      });
    }
    const bikeSel = this._$("eb-filter-bike");
    if (bikeSel) {
      bikeSel.addEventListener("change", (e) => {
        this._filterBike = e.target.value;
        this._applyFilter();
        if (this._activities.length) {
          this._show(0, true);
        } else {
          this._msg(this._t("msg_no_filter_match"));
        }
      });
    }

    this._updateStyleButtons();
    this._updateWikiButtons();
    this._updatePoiButtons();
  }

  _attachLifecycleHooks() {
    const mapEl = this._$("eb-map");
    if (!mapEl) return;

    if (window.ResizeObserver && !this._resizeObserver) {
      this._resizeObserver = new ResizeObserver(() => {
        this._scheduleActivation("resize");
      });
      this._resizeObserver.observe(mapEl);
    }

    if (window.IntersectionObserver && !this._intersectionObserver) {
      this._intersectionObserver = new IntersectionObserver((entries) => {
        const entry = entries[0];
        this._mapVisible = !!entry && (entry.isIntersecting || entry.intersectionRatio > 0);
        if (this._mapVisible) this._scheduleActivation("intersection");
      }, { threshold: [0, 0.01, 0.1, 0.25] });
      this._intersectionObserver.observe(mapEl);
    }

    document.addEventListener("visibilitychange", this._boundVisibility);
    window.addEventListener("focus", this._boundFocus);
    window.addEventListener("pageshow", this._boundPageShow);
    window.addEventListener("keydown", this._boundKeydown);
  }

  _detachLifecycleHooks() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
    if (this._intersectionObserver) {
      this._intersectionObserver.disconnect();
      this._intersectionObserver = null;
    }
    document.removeEventListener("visibilitychange", this._boundVisibility);
    window.removeEventListener("focus", this._boundFocus);
    window.removeEventListener("pageshow", this._boundPageShow);
    window.removeEventListener("keydown", this._boundKeydown);
  }

  _onVisibilityChange() {
    if (!document.hidden) this._scheduleActivation("visibilitychange");
  }

  _onFocus() {
    this._scheduleActivation("focus");
  }

  _onPageShow() {
    this._scheduleActivation("pageshow");
    if (this._fullscreenOpen) this._scheduleFullscreenSync("pageshow");
  }

  _onKeydown(ev) {
    if (ev.key === "Escape" && this._fullscreenOpen) this._closeFullscreen();
  }

  _$(id) {
    return this.querySelector("#" + id);
  }

  _msg(text) {
    const overlay = this._$("eb-overlay-msg");
    if (overlay) overlay.textContent = text || "";
  }

  _clearTimers() {
    for (const id of this._timers) window.clearTimeout(id);
    this._timers.clear();
  }

  _setTimer(fn, delay) {
    const id = window.setTimeout(() => {
      this._timers.delete(id);
      fn();
    }, delay);
    this._timers.add(id);
    return id;
  }

  _scheduleActivation(reason = "") {
    if (!this._connected || !this._leafletReady || !this._activities.length) return;
    if (this._pendingRender) return;
    this._pendingRender = true;

    const steps = [0, 120, 350, 900];
    steps.forEach((delay) => {
      this._setTimer(() => this._activateMap(reason), delay);
    });
    this._setTimer(() => {
      if (this._fullscreenOpen) this._scheduleFullscreenSync(reason || "activation");
      this._pendingRender = false;
    this._loadSeq = 0;
    this._appliedLoadSeq = 0;
    }, Math.max(...steps) + 50);
  }

  _scheduleFullscreenSync(reason = "") {
    if (!this._fullscreenOpen) return;
    [0, 120, 350].forEach((delay) => {
      this._setTimer(() => this._syncFullscreenMap(reason), delay);
    });
  }

  _isContainerUsable() {
    const mapEl = this._$("eb-map");
    if (!mapEl || !this.isConnected) return false;
    const rect = mapEl.getBoundingClientRect();
    return rect.width > 40 && rect.height > 40;
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (e) {
      this._instances = [];
    }
    this._populateFilterUI();
  }

  async _fetchActivities() {
    const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
    this._allActivities = (res.activities || []).sort((a, b) => new Date(b.startTime) - new Date(a.startTime));
    this._applyFilter();

    if (!this._activities.length) {
      this._msg(this._filtersActive() ? this._t("msg_no_filter_match") : this._t("msg_no_rides"));
      return;
    }

    await this._show(0, false);
  }

  _filtersActive() {
    return this._filterAccount !== "all" || this._filterBike !== "all";
  }

  /// Apply current account/bike filter to _allActivities → _activities
  _applyFilter() {
    let list = [...this._allActivities];
    if (this._filterAccount !== "all") {
      list = list.filter((a) => a.accountId === this._filterAccount);
    }
    if (this._filterBike !== "all") {
      list = list.filter((a) => a.bikeId === this._filterBike);
    }
    this._activities = list;
  }

  /// Build the dropdown options for accounts and bikes based on _instances.
  /// When `account_id`/`bike_id` is set in card config, the corresponding
  /// dropdown is hidden entirely (the filter is locked to the configured value).
  _populateFilterUI() {
    const accountSel = this._$("eb-filter-account");
    const bikeSel = this._$("eb-filter-bike");
    const accountWrap = this._$("eb-filter-account-wrap");
    const bikeWrap = this._$("eb-filter-bike-wrap");
    if (!accountSel || !bikeSel) return;

    // Account dropdown: hidden if locked via config OR if only one instance
    if (this._lockedAccount) {
      if (accountWrap) accountWrap.style.display = "none";
    } else if (this._instances.length > 1) {
      const opts = ['<option value="all">Alle Konten</option>'];
      for (const inst of this._instances) {
        opts.push(`<option value="${inst.config_entry_id}">${this._escapeHtml(inst.label)}</option>`);
      }
      accountSel.innerHTML = opts.join("");
      accountSel.value = this._filterAccount;
      if (accountWrap) accountWrap.style.display = "";
    } else {
      if (accountWrap) accountWrap.style.display = "none";
    }

    // Bike dropdown: union of all bikes (or filtered to selected account)
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) {
        const label = this._instances.length > 1 ? `${inst.label} — ${b.label}` : b.label;
        bikes.push({ id: b.id, label });
      }
    }

    // Bike dropdown: hidden if locked via config OR <=1 bike total
    if (this._lockedBike) {
      if (bikeWrap) bikeWrap.style.display = "none";
    } else {
      const bikeOpts = [`<option value="all">${this._t("all_bikes")}</option>`];
      for (const b of bikes) {
        bikeOpts.push(`<option value="${b.id}">${this._escapeHtml(b.label)}</option>`);
      }
      bikeSel.innerHTML = bikeOpts.join("");
      // Reset bike filter if currently selected bike isn't in the new list
      if (this._filterBike !== "all" && !bikes.some((b) => b.id === this._filterBike)) {
        this._filterBike = "all";
      }
      bikeSel.value = this._filterBike;
      if (bikeWrap) bikeWrap.style.display = bikes.length > 1 ? "" : "none";
    }
  }

  /// Apply config.title to the card header if present
  _applyConfigTitle() {
    const head = this.querySelector(".eb-head span");
    if (head && this._config && this._config.title) {
      head.textContent = this._config.title;
    }
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  _t(key, ...args) {
    return ebT(this._hass, key, ...args);
  }

  _getSortValue(activity, key) {
    switch (key) {
      case "date": return new Date(activity.startTime || 0).getTime();
      case "distance": return activity.distance || 0;
      case "duration": return activity.durationWithoutStops || 0;
      case "avgSpeed": return activity.speed?.average ?? 0;
      case "maxSpeed": return activity.speed?.maximum ?? 0;
      case "elevation": return activity.elevation?.gain ?? 0;
      case "calories": return activity.caloriesBurned ?? 0;
      case "difficulty": {
        const d = activity.distance ? activity.distance / 1000 : 0;
        return d > 0 ? (activity.elevation?.gain ?? 0) / d : 0;
      }
      case "batteryWh": return activity.consumption?.consumed_wh ?? 0;
      case "batteryPct": return activity.consumption?.percentage ?? 0;
      default: return 0;
    }
  }

  _applySort() {
    const key = this._sortKey;
    const asc = this._sortAsc;
    this._activities.sort((a, b) => {
      const va = this._getSortValue(a, key);
      const vb = this._getSortValue(b, key);
      return asc ? va - vb : vb - va;
    });
    this._show(0, true);
  }

  async _show(index, forceTrackReload = true) {
    if (index < 0 || index >= this._activities.length) return;
    this._idx = index;
    const activity = this._activities[index];

    if (activity.startTime) {
      const dateValue = activity.startTime.substring(0, 10);
      this._$("eb-date").value = dateValue;
      const fullDate = this._$("eb-full-date");
      if (fullDate) fullDate.value = dateValue;
    }
    this._$("eb-ctr").textContent = `${index + 1} / ${this._activities.length}`;
    const fullCtr = this._$("eb-full-ctr");
    if (fullCtr) fullCtr.textContent = `${index + 1} / ${this._activities.length}`;
    this._$("eb-prev").disabled = index <= 0;
    this._$("eb-next").disabled = index >= this._activities.length - 1;
    const fullPrev = this._$("eb-full-prev");
    const fullNext = this._$("eb-full-next");
    if (fullPrev) fullPrev.disabled = index <= 0;
    if (fullNext) fullNext.disabled = index >= this._activities.length - 1;
    this._$("eb-title").textContent = activity.title || this._t("msg_unnamed_ride");

    if (activity.startTime) {
      this._$("eb-date-lbl").textContent = new Date(activity.startTime).toLocaleDateString("de-DE", {
        weekday: "long", year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit"
      });
    } else {
      this._$("eb-date-lbl").textContent = "";
    }

    const dist = activity.distance ? (activity.distance / 1000).toFixed(1) : "–";
    const dur = activity.durationWithoutStops ? Math.round(activity.durationWithoutStops / 60) : "–";
    const avgS = activity.speed?.average != null ? activity.speed.average.toFixed(1) : "–";
    const maxS = activity.speed?.maximum != null ? activity.speed.maximum.toFixed(1) : "–";
    const ele = activity.elevation?.gain != null ? Math.round(activity.elevation.gain) : "–";
    const cal = activity.caloriesBurned != null ? Math.round(activity.caloriesBurned) : "–";

    // Difficulty: elevation gain per km
    const distKm = activity.distance ? activity.distance / 1000 : 0;
    const eleGain = activity.elevation?.gain ?? 0;
    const difficulty = distKm > 0 ? (eleGain / distKm).toFixed(1) : "–";

    // Battery consumption
    const cons = activity.consumption;
    const battWh = cons?.consumed_wh != null ? cons.consumed_wh.toFixed(1) : "–";
    const battPct = cons?.percentage != null ? cons.percentage.toFixed(1) : "–";

    const statsHtml = `
      <div class="eb-stat"><div class="eb-val">${dist} km</div><div class="eb-lbl">${this._t("stat_distance")}</div></div>
      <div class="eb-stat"><div class="eb-val">${dur} min</div><div class="eb-lbl">${this._t("stat_duration")}</div></div>
      <div class="eb-stat"><div class="eb-val">${avgS}</div><div class="eb-lbl">${this._t("stat_avg_kmh")}</div></div>
      <div class="eb-stat"><div class="eb-val">${maxS}</div><div class="eb-lbl">${this._t("stat_max_kmh")}</div></div>
      <div class="eb-stat"><div class="eb-val">${ele} m</div><div class="eb-lbl">${this._t("stat_elevation_up")}</div></div>
      <div class="eb-stat"><div class="eb-val">${cal} kcal</div><div class="eb-lbl">${this._t("stat_calories")}</div></div>
      <div class="eb-stat"><div class="eb-val">${difficulty} m/km</div><div class="eb-lbl">${this._t("stat_difficulty")}</div></div>
      <div class="eb-stat"><div class="eb-val">${battWh} Wh</div><div class="eb-lbl">${this._t("stat_battery")}</div></div>
      <div class="eb-stat"><div class="eb-val">${battPct} %</div><div class="eb-lbl">${this._t("stat_battery_pct")}</div></div>
    `;
    this._$("eb-stats").innerHTML = statsHtml;
    this._$("eb-fullscreen-title").textContent = activity.title || this._t("msg_unnamed_ride");
    this._$("eb-fullscreen-meta").innerHTML = statsHtml;
    this._renderFullscreenProfile();

    if (forceTrackReload || this._currentTrackActivityId !== activity.id || !this._currentTrack.length) {
      this._destroyMap(true);
      if (this._fullscreenOpen) this._destroyFullscreenMap();
      await this._loadTrack(activity.id, activity.accountId);
    } else {
      this._scheduleActivation("show cached track");
    }
  }

  async _loadTrack(activityId, accountId) {
    const loadSeq = ++this._loadSeq;
    this._msg(this._t("msg_loading_route"));

    try {
      const params = { type: "bosch_ebike/get_track", activity_id: activityId };
      if (accountId) params.config_entry_id = accountId;
      const res = await this._hass.callWS(params);
      if (loadSeq < this._loadSeq) return;

      const pts = Array.isArray(res.track) ? res.track.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon)) : [];
      this._currentTrack = pts;
      this._currentTrackActivityId = activityId;
      this._appliedLoadSeq = loadSeq;
      this._inlineUserAdjustedView = false;
      this._fullscreenUserAdjustedView = false;
      this._needsInlineFit = true;
      this._needsFullscreenFit = true;

      this._destroyMap(true);
      if (this._fullscreenOpen) this._destroyFullscreenMap();

      if (!pts.length) {
        this._msg(this._t("msg_no_gps"));
        this._clearTrackLayers();
        this._renderFullscreenProfile();
        return;
      }

      this._renderFullscreenProfile();
      this._msg("");
      [0, 80, 220, 500].forEach((delay) => {
        this._setTimer(() => this._activateMap("track loaded"), delay);
      });
      if (this._fullscreenOpen) this._scheduleFullscreenSync("track loaded");
      if (this._wikiEnabled) {
        // Slight delay so the map is initialized before placing markers
        this._setTimer(() => this._loadAndRenderWiki(), 600);
      }
      if (this._poiEnabled) {
        this._setTimer(() => this._loadAndRenderPoi(), 700);
      }
    } catch (error) {
      if (loadSeq < this._loadSeq) return;
      console.error("[Bosch eBike Map] track load error", error);
      this._msg(this._t("msg_error_prefix") + (error?.message || error));
    }
  }

  _activateMap(reason = "") {
    if (!this._connected || !this._leafletReady || !this._currentTrack.length) return;
    if (!this._isContainerUsable()) return;

    const mapEl = this._$("eb-map");
    if (!mapEl) return;

    if (!this._map) {
      this._createMap();
    } else if (this._map.getContainer() !== mapEl || !mapEl.querySelector(".leaflet-pane")) {
      this._destroyMap(true);
      this._createMap();
    }

    if (!this._map) return;

    this._renderCurrentTrack();
    this._safeInvalidate();
    if (this._fullscreenOpen) this._scheduleFullscreenSync(reason || "activate");
  }

  _createMap() {
    const mapEl = this._$("eb-map");
    const Leaflet = window.L;
    if (!mapEl || !Leaflet || typeof Leaflet.map !== "function") {
      this._msg(this._t("msg_error_prefix") + this._t("err_leaflet_load"));
      return;
    }

    mapEl.innerHTML = "";

    try {
      this._map = Leaflet.map(mapEl, {
        zoomControl: true,
        attributionControl: false,
        preferCanvas: true,
        zoomAnimation: true,
        fadeAnimation: true,
        markerZoomAnimation: true,
      }).setView([48.7, 12.4], 10);

      this._applyBaseLayer(this._map, "inline", true);

      this._trackGroup = Leaflet.layerGroup().addTo(this._map);
      this._bindMapInteractionState(this._map, "inline");
    } catch (error) {
      console.error("[Bosch eBike Map] map create error", error);
      this._destroyMap(true);
      this._msg(this._t("err_create_map"));
    }
  }


  _styleDef(styleKey = this._mapStyle) {
    return MAP_STYLES[styleKey] || MAP_STYLES.osm;
  }

  _updateStyleButtons() {
    const label = this._styleDef().label;
    const inlineBtn = this._$("eb-style");
    const fullBtn = this._$("eb-full-style");
    if (inlineBtn) inlineBtn.textContent = label;
    if (fullBtn) fullBtn.textContent = label;
  }

  _makeBaseLayer(Leaflet, styleKey = this._mapStyle) {
    const def = this._styleDef(styleKey);
    return Leaflet.tileLayer(def.url, def.options);
  }

  _applyBaseLayer(targetMap, kind = "inline", force = false) {
    const Leaflet = window.L;
    if (!Leaflet || !targetMap) return;

    const prop = kind === "fullscreen" ? "_fullscreenBaseLayer" : "_inlineBaseLayer";
    const current = this[prop];
    if (current && !force) return;

    if (current) {
      try { targetMap.removeLayer(current); } catch (_) {}
      this[prop] = null;
    }

    const layer = this._makeBaseLayer(Leaflet, this._mapStyle);
    layer.addTo(targetMap);
    this[prop] = layer;
  }

  _cycleMapStyle() {
    const keys = Object.keys(MAP_STYLES);
    const index = keys.indexOf(this._mapStyle);
    const next = keys[(index + 1) % keys.length];
    this._setMapStyle(next);
  }

  _setMapStyle(styleKey) {
    if (!MAP_STYLES[styleKey] || this._mapStyle === styleKey) return;
    this._mapStyle = styleKey;
    this._updateStyleButtons();

    if (this._map) this._applyBaseLayer(this._map, "inline", true);
    if (this._fullscreenMap) this._applyBaseLayer(this._fullscreenMap, "fullscreen", true);

    this._setTimer(() => this._safeInvalidate(), 0);
    if (this._fullscreenOpen) this._scheduleFullscreenSync("style change");
  }


  _bindMapInteractionState(map, kind = "inline") {
    if (!map || map._boschInteractionBound) return;

    const markAdjusted = () => {
      if (kind === "fullscreen") {
        this._fullscreenUserAdjustedView = true;
        this._needsFullscreenFit = false;
      } else {
        this._inlineUserAdjustedView = true;
        this._needsInlineFit = false;
      }
    };

    map.on("zoomstart", markAdjusted);
    map.on("dragstart", markAdjusted);
    map.on("movestart", (ev) => {
      if (ev?.originalEvent) markAdjusted();
    });
    map._boschInteractionBound = true;
  }

  _destroyMap(keepContainer = true) {
    try {
      if (this._legend && this._map) {
        this._map.removeControl(this._legend);
      }
    } catch (_) {}
    this._legend = null;

    try {
      if (this._map) {
        this._map.remove();
      }
    } catch (_) {}

    this._map = null;
    this._trackGroup = null;
    this._wikiGroup = null;
    this._wikiRenderedInline = null;
    this._poiGroup = null;
    this._poiRenderedInline = null;
    this._inlineBaseLayer = null;

    const mapEl = this._$("eb-map");
    if (!keepContainer && mapEl) mapEl.innerHTML = "";
  }

  _destroyFullscreenMap() {
    try {
      if (this._fullscreenLegend && this._fullscreenMap) {
        this._fullscreenMap.removeControl(this._fullscreenLegend);
      }
    } catch (_) {}
    this._fullscreenLegend = null;

    try {
      if (this._fullscreenMap) {
        this._fullscreenMap.remove();
      }
    } catch (_) {}

    this._fullscreenMap = null;
    this._fullscreenTrackGroup = null;
    this._fullscreenWikiGroup = null;
    this._wikiRenderedFullscreen = null;
    this._fullscreenPoiGroup = null;
    this._poiRenderedFullscreen = null;
    this._fullscreenBaseLayer = null;

    const mapEl = this._$("eb-fullscreen-map");
    if (mapEl) mapEl.innerHTML = "";
  }

  // -- Wikipedia overlay --

  _updateWikiButtons() {
    const inlineBtn = this._$("eb-wiki");
    const fullBtn = this._$("eb-full-wiki");
    if (inlineBtn) inlineBtn.classList.toggle("eb-active", this._wikiEnabled);
    if (fullBtn) fullBtn.classList.toggle("eb-active", this._wikiEnabled);
  }

  _toggleWikipedia() {
    this._wikiEnabled = !this._wikiEnabled;
    try { localStorage.setItem("eb-wiki-enabled", this._wikiEnabled ? "1" : "0"); } catch (_) {}
    this._updateWikiButtons();

    if (this._wikiEnabled) {
      this._loadAndRenderWiki();
    } else {
      this._clearWikiLayers();
    }
  }

  _clearWikiLayers() {
    if (this._wikiGroup) {
      try { this._wikiGroup.clearLayers(); } catch (_) {}
    }
    if (this._fullscreenWikiGroup) {
      try { this._fullscreenWikiGroup.clearLayers(); } catch (_) {}
    }
    this._wikiRenderedInline = null;
    this._wikiRenderedFullscreen = null;
  }

  /// Wikipedia language code based on HA locale, fallback en
  _wikiLanguage() {
    const locale = (this._hass && this._hass.locale && this._hass.locale.language) || "en";
    return String(locale).slice(0, 2).toLowerCase() || "en";
  }

  /// Subsample the route every ~2 km along the actual driven distance.
  _wikiSamplePoints(track) {
    if (!Array.isArray(track) || track.length < 2) return [];
    const pts = [];
    let lastSampleDist = -Infinity;
    let cumKm = 0;
    pts.push({ lat: track[0].lat, lon: track[0].lon });
    lastSampleDist = 0;
    for (let i = 1; i < track.length; i += 1) {
      cumKm += this._distanceMeters(track[i - 1], track[i]) / 1000;
      if (cumKm - lastSampleDist >= 2) {
        pts.push({ lat: track[i].lat, lon: track[i].lon });
        lastSampleDist = cumKm;
      }
    }
    // Always include the last point as well
    const last = track[track.length - 1];
    pts.push({ lat: last.lat, lon: last.lon });
    return pts;
  }

  async _loadAndRenderWiki() {
    if (!this._currentTrackActivityId || !this._currentTrack.length) return;
    const aid = this._currentTrackActivityId;
    // Cache is keyed by activity AND radius so different radii don't collide
    const cacheKey = `eb-wiki-${aid}-${this._wikiRadius}`;

    // From cache? Empty arrays from older versions or transient failures are
    // ignored so navigating between tours always re-tries when nothing was
    // found before — matches the POI handling in _loadAndRenderPoi.
    let articles = this._wikiArticles.get(aid);
    if (!articles || articles.length === 0) {
      try {
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            articles = parsed;
            this._wikiArticles.set(aid, parsed);
          }
        }
      } catch (_) {}
    }

    if (!articles || articles.length === 0) {
      if (this._wikiLoading.has(aid)) return;
      this._wikiLoading.add(aid);
      try {
        articles = await this._fetchWikiArticles(this._currentTrack);
        this._wikiArticles.set(aid, articles);
        if (articles.length > 0) {
          try { localStorage.setItem(cacheKey, JSON.stringify(articles)); } catch (_) {}
        }
      } catch (err) {
        console.warn("[Bosch eBike Wiki] fetch failed", err);
        articles = [];
      } finally {
        this._wikiLoading.delete(aid);
      }
    }

    this._renderWikiMarkers(articles);
  }

  async _fetchWikiArticles(track) {
    const samples = this._wikiSamplePoints(track);
    if (!samples.length) return [];
    const lang = this._wikiLanguage();
    const seen = new Map(); // pageId → article

    // Process in batches of 5 with a small pause between batches
    const BATCH_SIZE = 5;
    for (let i = 0; i < samples.length; i += BATCH_SIZE) {
      const batch = samples.slice(i, i + BATCH_SIZE);
      const results = await Promise.all(
        batch.map((p) => this._geosearchOnce(lang, p.lat, p.lon))
      );
      for (const list of results) {
        for (const art of list) {
          if (!seen.has(art.pageId)) seen.set(art.pageId, art);
        }
      }
      if (i + BATCH_SIZE < samples.length) {
        await new Promise((r) => setTimeout(r, 100));
      }
    }

    let arr = Array.from(seen.values());
    // Cap at 30 markers — keep the closest to any sample point
    if (arr.length > 30) {
      arr.sort((a, b) => (a.dist || 0) - (b.dist || 0));
      arr = arr.slice(0, 30);
    }
    return arr;
  }

  async _geosearchOnce(lang, lat, lon) {
    const url = new URL(`https://${lang}.wikipedia.org/w/api.php`);
    url.searchParams.set("action", "query");
    url.searchParams.set("list", "geosearch");
    url.searchParams.set("gscoord", `${lat}|${lon}`);
    url.searchParams.set("gsradius", String(this._wikiRadius || 1000));
    url.searchParams.set("gslimit", "10");
    url.searchParams.set("format", "json");
    url.searchParams.set("origin", "*");
    try {
      const resp = await fetch(url.toString());
      if (!resp.ok) return [];
      const data = await resp.json();
      const list = (data && data.query && data.query.geosearch) || [];
      return list.map((a) => ({
        pageId: a.pageid,
        title: a.title,
        lat: a.lat,
        lon: a.lon,
        dist: a.dist,
        lang,
      }));
    } catch (_) {
      return [];
    }
  }

  async _fetchWikiSummary(pageId, title, lang) {
    if (this._wikiSummaries.has(pageId)) return this._wikiSummaries.get(pageId);
    const url = `https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}?redirect=true`;
    try {
      const resp = await fetch(url, { headers: { Accept: "application/json" } });
      if (!resp.ok) return null;
      const data = await resp.json();
      const summary = {
        extract: data.extract || "",
        thumbnail: data.thumbnail && data.thumbnail.source ? data.thumbnail.source : null,
        link: (data.content_urls && data.content_urls.desktop && data.content_urls.desktop.page)
          || `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(title)}`,
      };
      this._wikiSummaries.set(pageId, summary);
      return summary;
    } catch (_) {
      return null;
    }
  }

  _renderWikiMarkers(articles) {
    if (!this._wikiEnabled) return;
    const Leaflet = window.L;
    if (!Leaflet) return;
    const aid = this._currentTrackActivityId;

    const popupOpts = {
      maxWidth: 300,
      closeOnClick: false,  // don't close when clicking on the map
      autoClose: false,     // don't close when another popup opens
    };

    const renderTo = (map, groupRefName, renderedRefName) => {
      if (!map) return;
      // Already rendered for this activity → keep markers (and any open popup) alive
      if (this[renderedRefName] === aid && this[groupRefName]) return;

      let group = this[groupRefName];
      if (!group) {
        group = Leaflet.layerGroup().addTo(map);
        this[groupRefName] = group;
      }
      group.clearLayers();
      for (const art of articles) {
        if (!Number.isFinite(art.lat) || !Number.isFinite(art.lon)) continue;
        const icon = Leaflet.divIcon({
          className: "",
          html: '<div class="eb-wiki-marker">i</div>',
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });
        const marker = Leaflet.marker([art.lat, art.lon], { icon, title: art.title });
        marker.bindPopup(this._wikiPopupHtml(art, true), popupOpts);
        marker.on("popupopen", async () => {
          const summary = await this._fetchWikiSummary(art.pageId, art.title, art.lang);
          marker.setPopupContent(this._wikiPopupHtml(art, false, summary));
        });
        marker.addTo(group);
      }
      this[renderedRefName] = aid;
    };

    renderTo(this._map, "_wikiGroup", "_wikiRenderedInline");
    renderTo(this._fullscreenMap, "_fullscreenWikiGroup", "_wikiRenderedFullscreen");
  }

  // -- POI overlay (Overpass) --

  _updatePoiButtons() {
    const inlineBtn = this._$("eb-poi");
    const fullBtn = this._$("eb-full-poi");
    if (inlineBtn) inlineBtn.classList.toggle("eb-active", this._poiEnabled);
    if (fullBtn) fullBtn.classList.toggle("eb-active", this._poiEnabled);
  }

  _togglePoi() {
    this._poiEnabled = !this._poiEnabled;
    try { localStorage.setItem("eb-poi-enabled", this._poiEnabled ? "1" : "0"); } catch (_) {}
    this._updatePoiButtons();
    if (this._poiEnabled) {
      this._loadAndRenderPoi();
    } else {
      this._clearPoiLayers();
    }
  }

  _clearPoiLayers() {
    if (this._poiGroup) {
      try { this._poiGroup.clearLayers(); } catch (_) {}
    }
    if (this._fullscreenPoiGroup) {
      try { this._fullscreenPoiGroup.clearLayers(); } catch (_) {}
    }
    this._poiRenderedInline = null;
    this._poiRenderedFullscreen = null;
  }

  /// Bounding box around the route; clamped to a sensible buffer.
  _routeBoundingBox(track) {
    let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
    for (const p of track) {
      if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
      if (p.lat < minLat) minLat = p.lat;
      if (p.lat > maxLat) maxLat = p.lat;
      if (p.lon < minLon) minLon = p.lon;
      if (p.lon > maxLon) maxLon = p.lon;
    }
    if (!Number.isFinite(minLat)) return null;
    return { minLat, maxLat, minLon, maxLon };
  }

  _setPoiLoadingUI(loading) {
    for (const id of ["eb-poi", "eb-full-poi"]) {
      const btn = this._$(id);
      if (btn) {
        btn.classList.toggle("eb-loading", !!loading);
        btn.disabled = !!loading;
      }
    }
  }

  async _loadAndRenderPoi() {
    if (!this._currentTrackActivityId || !this._currentTrack.length) return;
    const aid = this._currentTrackActivityId;
    // Cache key includes the radius so different radii don't collide
    const cacheKey = `eb-poi-${aid}-${this._poiRadius || 1000}`;

    let pois = this._poiData.get(aid);
    if (!pois || pois.length === 0) {
      // In-memory cache empty → check localStorage but only honour non-empty cached results
      try {
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            pois = parsed;
            this._poiData.set(aid, parsed);
          }
        }
      } catch (_) {}
    }

    if (!pois || pois.length === 0) {
      if (this._poiLoading.has(aid)) return;
      this._poiLoading.add(aid);
      this._setPoiLoadingUI(true);
      try {
        pois = await this._fetchPois(this._currentTrack);
        this._poiData.set(aid, pois);
        // Only persist NON-EMPTY results — otherwise a transient Overpass
        // error would poison the cache and hide POIs forever.
        if (pois.length > 0) {
          try { localStorage.setItem(cacheKey, JSON.stringify(pois)); } catch (_) {}
        }
      } catch (err) {
        console.warn("[Bosch eBike POI] fetch failed", err);
        pois = [];
      } finally {
        this._poiLoading.delete(aid);
        this._setPoiLoadingUI(false);
      }
    }

    this._renderPoiMarkers(pois);
  }

  async _fetchPois(track) {
    const bbox = this._routeBoundingBox(track);
    if (!bbox) return [];
    // Bbox padding scales with the configured proximity radius (in degrees, ~111 km/°)
    const radiusM = this._poiRadius || 1000;
    const pad = radiusM / 111000 + 0.001;
    const south = bbox.minLat - pad;
    const north = bbox.maxLat + pad;
    const west = bbox.minLon - pad;
    const east = bbox.maxLon + pad;

    // Route the Overpass query through the HA backend (avoids CORS issues
    // that overpass-api.de's tightened policy causes for browser requests).
    let elements = [];
    try {
      const res = await this._hass.callWS({
        type: "bosch_ebike/get_pois",
        south, west, north, east,
      });
      elements = (res && Array.isArray(res.elements)) ? res.elements : [];
    } catch (err) {
      console.warn("[Bosch eBike POI] backend Overpass call failed:", err);
      return [];
    }

    if (!elements.length) {
      console.info("[Bosch eBike POI] Overpass returned no POIs in route bbox", bbox);
    }
    // Sample track points every ~radius/2 so the proximity filter has no gaps
    const MAX_DIST_M = radiusM;
    const sampled = this._poiSamplePoints(track, MAX_DIST_M / 2);

    const out = [];
    for (const el of elements) {
      if (typeof el.lat !== "number" || typeof el.lon !== "number") continue;
      // Only keep POIs within MAX_DIST_M of any sampled track point
      let near = false;
      for (const sp of sampled) {
        if (this._haversineMeters(el.lat, el.lon, sp.lat, sp.lon) <= MAX_DIST_M) {
          near = true; break;
        }
      }
      if (!near) continue;
      const tags = el.tags || {};
      const cat = this._poiCategory(tags);
      if (!cat) continue;
      out.push({
        lat: el.lat,
        lon: el.lon,
        category: cat.key,
        catLabel: cat.label,
        catIcon: cat.icon,
        name: tags.name || cat.label,
        osmId: el.id,
        tags,
      });
    }
    // Cap at 100 markers to avoid clutter
    return out.slice(0, 100);
  }

  _poiCategory(tags) {
    if (tags.amenity === "charging_station") {
      return { key: "charging", label: this._t("poi_charging"), icon: "🔌" };
    }
    if (tags.shop === "bicycle") {
      return { key: "bicycle", label: this._t("poi_bicycle_shop"), icon: "🛠️" };
    }
    if (tags.amenity === "bicycle_repair_station") {
      return { key: "bicycle", label: this._t("poi_repair"), icon: "🛠️" };
    }
    if (tags.amenity === "drinking_water") {
      return { key: "water", label: this._t("poi_water"), icon: "💧" };
    }
    if (tags.amenity === "toilets") {
      return { key: "toilet", label: this._t("poi_toilet"), icon: "🚻" };
    }
    return null;
  }

  /// Sample points every `intervalM` metres along the actual driven distance.
  /// Default 250 m; caller passes radius/2 so the proximity filter has no gaps
  /// even when the route makes sharp turns.
  _poiSamplePoints(track, intervalM = 250) {
    if (!Array.isArray(track) || track.length < 2) return [];
    const intervalKm = Math.max(0.05, intervalM / 1000);
    const pts = [];
    pts.push({ lat: track[0].lat, lon: track[0].lon });
    let cumKm = 0;
    let lastSampled = 0;
    for (let i = 1; i < track.length; i += 1) {
      cumKm += this._distanceMeters(track[i - 1], track[i]) / 1000;
      if (cumKm - lastSampled >= intervalKm) {
        pts.push({ lat: track[i].lat, lon: track[i].lon });
        lastSampled = cumKm;
      }
    }
    const last = track[track.length - 1];
    pts.push({ lat: last.lat, lon: last.lon });
    return pts;
  }

  _haversineMeters(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const toRad = (d) => d * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2
      + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  _renderPoiMarkers(pois) {
    if (!this._poiEnabled) return;
    const Leaflet = window.L;
    if (!Leaflet) return;
    const aid = this._currentTrackActivityId;

    const popupOpts = { maxWidth: 260, closeOnClick: false, autoClose: false };

    const renderTo = (map, groupRefName, renderedRefName) => {
      if (!map) return;
      if (this[renderedRefName] === aid && this[groupRefName]) return;
      let group = this[groupRefName];
      if (!group) {
        group = Leaflet.layerGroup().addTo(map);
        this[groupRefName] = group;
      }
      group.clearLayers();
      for (const poi of pois) {
        const icon = Leaflet.divIcon({
          className: "",
          html: `<div class="eb-poi-marker eb-poi-${poi.category}">${poi.catIcon}</div>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        });
        const marker = Leaflet.marker([poi.lat, poi.lon], { icon, title: `${poi.catIcon} ${poi.name}` });
        marker.bindPopup(this._poiPopupHtml(poi), popupOpts);
        marker.addTo(group);
      }
      this[renderedRefName] = aid;
    };

    renderTo(this._map, "_poiGroup", "_poiRenderedInline");
    renderTo(this._fullscreenMap, "_fullscreenPoiGroup", "_poiRenderedFullscreen");
  }

  _poiPopupHtml(poi) {
    const safeName = this._escapeHtml(poi.name);
    const osmUrl = `https://www.openstreetmap.org/node/${poi.osmId}`;
    let extra = "";
    if (poi.tags.opening_hours) {
      extra += `<div>🕒 ${this._escapeHtml(poi.tags.opening_hours)}</div>`;
    }
    if (poi.tags["addr:street"]) {
      const addr = [poi.tags["addr:street"], poi.tags["addr:housenumber"]].filter(Boolean).join(" ");
      extra += `<div>📍 ${this._escapeHtml(addr)}</div>`;
    }
    if (poi.tags.website) {
      const url = poi.tags.website.startsWith("http") ? poi.tags.website : "https://" + poi.tags.website;
      extra += `<div>🌐 <a href="${this._escapeHtml(url)}" target="_blank" rel="noopener">Website</a></div>`;
    }
    return `<div class="eb-poi-popup">
      <div class="eb-poi-title">${poi.catIcon} ${safeName}</div>
      <div class="eb-poi-cat">${this._escapeHtml(poi.catLabel)}</div>
      ${extra}
      <a class="eb-poi-link" href="${osmUrl}" target="_blank" rel="noopener noreferrer">${this._t("poi_open_osm")}</a>
    </div>`;
  }

  _wikiPopupHtml(article, loading, summary = null) {
    const safeTitle = this._escapeHtml(article.title);
    if (loading) {
      return `<div class="eb-wiki-popup">
        <div class="eb-wiki-title">${safeTitle}</div>
        <div class="eb-wiki-loading">${this._t("wiki_loading_preview")}</div>
      </div>`;
    }
    if (!summary) {
      const fallbackUrl = `https://${article.lang}.wikipedia.org/wiki/${encodeURIComponent(article.title)}`;
      return `<div class="eb-wiki-popup">
        <div class="eb-wiki-title">${safeTitle}</div>
        <div class="eb-wiki-extract">${this._t("wiki_no_preview")}</div>
        <a class="eb-wiki-link" href="${fallbackUrl}" target="_blank" rel="noopener noreferrer">${this._t("wiki_open_link")}</a>
      </div>`;
    }
    const thumb = summary.thumbnail
      ? `<img class="eb-wiki-thumb" src="${summary.thumbnail}" alt="">` : "";
    const extract = this._escapeHtml(summary.extract || "");
    return `<div class="eb-wiki-popup">
      <div class="eb-wiki-title">${safeTitle}</div>
      ${thumb}
      <div class="eb-wiki-extract">${extract}</div>
      <a class="eb-wiki-link" href="${summary.link}" target="_blank" rel="noopener noreferrer">${this._t("wiki_open_link")}</a>
    </div>`;
  }

  _clearTrackLayers() {
    if (this._trackGroup) this._trackGroup.clearLayers();
    if (this._legend && this._map) {
      try { this._map.removeControl(this._legend); } catch (_) {}
    }
    this._legend = null;
  }

  _renderCurrentTrack() {
    if (!this._map || !this._trackGroup || !this._currentTrack.length) return;
    this._renderTrackToMap(this._map, this._trackGroup, {
      padding: [40, 40],
      legend: "inline",
      fit: this._needsInlineFit && !this._inlineUserAdjustedView,
    });
    this._needsInlineFit = false;
    this._msg("");

    // Restore Wikipedia markers from cache if active
    if (this._wikiEnabled) {
      const cached = this._wikiArticles.get(this._currentTrackActivityId);
      if (cached) this._renderWikiMarkers(cached);
    }
    // Restore POI markers from cache if active
    if (this._poiEnabled) {
      const cached = this._poiData.get(this._currentTrackActivityId);
      if (cached) this._renderPoiMarkers(cached);
    }
  }

  _renderTrackToMap(targetMap, targetGroup, { padding = [40, 40], legend = "inline", fit = false } = {}) {
    const Leaflet = window.L;
    if (!targetMap || !targetGroup || !Leaflet || !this._currentTrack.length) return;

    targetGroup.clearLayers();
    const pts = this._currentTrack;

    for (let i = 0; i < pts.length - 1; i += 1) {
      const speed = pts[i].speed || 0;
      Leaflet.polyline(
        [[pts[i].lat, pts[i].lon], [pts[i + 1].lat, pts[i + 1].lon]],
        { color: this._color(speed), weight: 5, opacity: 0.9, lineCap: "round" }
      ).addTo(targetGroup);
    }

    Leaflet.circleMarker([pts[0].lat, pts[0].lon], {
      radius: 8, fillColor: "#4CAF50", color: "#fff", weight: 3, fillOpacity: 1,
    }).bindTooltip("Start").addTo(targetGroup);

    const last = pts[pts.length - 1];
    Leaflet.circleMarker([last.lat, last.lon], {
      radius: 8, fillColor: "#f44336", color: "#fff", weight: 3, fillOpacity: 1,
    }).bindTooltip("Ziel").addTo(targetGroup);

    if (fit) this._fitMapToTrack(targetMap, pts, padding);
    this._addLegend(targetMap, legend);
  }

  _fitMapToTrack(targetMap, pts = this._currentTrack, padding = [40, 40]) {
    const Leaflet = window.L;
    if (!targetMap || !Leaflet || !pts?.length) return;
    const bounds = Leaflet.latLngBounds(pts.map((p) => [p.lat, p.lon]));
    try {
      targetMap.fitBounds(bounds, { padding, animate: false });
    } catch (_) {}
  }

  _safeInvalidate() {
    if (!this._map || !this._isContainerUsable()) return;
    try {
      this._map.invalidateSize({ pan: false, animate: false });
    } catch (_) {}
  }

  _color(kmh) {
    if (kmh <= 5) return "#2196F3";
    if (kmh <= 12) return "#4CAF50";
    if (kmh <= 20) return "#8BC34A";
    if (kmh <= 27) return "#FFC107";
    if (kmh <= 33) return "#FF9800";
    return "#f44336";
  }

  _addLegend(targetMap = this._map, kind = "inline") {
    const Leaflet = window.L;
    if (!targetMap || !Leaflet) return;

    if (kind === "fullscreen") {
      if (this._fullscreenLegend) {
        try { this._fullscreenMap.removeControl(this._fullscreenLegend); } catch (_) {}
      }
    } else if (this._legend) {
      try { this._map.removeControl(this._legend); } catch (_) {}
    }

    const speedLabel = this._t("speed_legend");
    const Legend = Leaflet.Control.extend({
      options: { position: "bottomright" },
      onAdd() {
        const div = Leaflet.DomUtil.create("div");
        div.style.cssText = "background:rgba(255,255,255,.92);padding:6px 10px;border-radius:6px;font-size:11px;box-shadow:0 1px 5px rgba(0,0,0,.25);line-height:1.6";
        div.innerHTML =
          `<b>${speedLabel}</b><br>` +
          '<i style="background:#2196F3;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 0 ' +
          '<i style="background:#4CAF50;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 12 ' +
          '<i style="background:#FFC107;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 25 ' +
          '<i style="background:#f44336;width:14px;height:3px;display:inline-block;border-radius:2px;vertical-align:middle"></i> 35+ km/h';
        return div;
      }
    });

    const legend = new Legend();
    targetMap.addControl(legend);
    if (kind === "fullscreen") this._fullscreenLegend = legend;
    else this._legend = legend;
  }



  _pointElevation(point) {
    const v = Number.isFinite(point?.ele) ? point.ele
      : Number.isFinite(point?.alt) ? point.alt
      : Number.isFinite(point?.altitude) ? point.altitude
      : null;
    return Number.isFinite(v) ? v : null;
  }

  _distanceMeters(a, b) {
    if (!a || !b) return 0;
    const R = 6371000;
    const toRad = (deg) => (deg * Math.PI) / 180;
    const dLat = toRad((b.lat || 0) - (a.lat || 0));
    const dLon = toRad((b.lon || 0) - (a.lon || 0));
    const lat1 = toRad(a.lat || 0);
    const lat2 = toRad(b.lat || 0);
    const sinLat = Math.sin(dLat / 2);
    const sinLon = Math.sin(dLon / 2);
    const x = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;
    return 2 * R * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
  }

  _buildElevationProfileData() {
    const pts = Array.isArray(this._currentTrack) ? this._currentTrack : [];
    if (pts.length < 2) return null;

    const pointDistancesKm = [];
    const rawElevations = [];
    const rawCadences = [];
    const rawPowers = [];
    let cumulative = 0;

    for (let i = 0; i < pts.length; i += 1) {
      if (i > 0) cumulative += this._distanceMeters(pts[i - 1], pts[i]);
      pointDistancesKm.push(cumulative / 1000);
      rawElevations.push(this._pointElevation(pts[i]));
      const c = pts[i].cadence;
      rawCadences.push(Number.isFinite(c) ? c : null);
      const p = pts[i].power;
      rawPowers.push(Number.isFinite(p) ? p : null);
    }

    const validEntries = rawElevations
      .map((ele, idx) => ({ ele, idx }))
      .filter(({ ele }) => Number.isFinite(ele));

    if (!validEntries.length) return null;

    const firstPositiveEntry = validEntries.find(({ ele }) => ele > 0);
    const startIdx = firstPositiveEntry ? firstPositiveEntry.idx : validEntries[0].idx;

    const trimmedDistancesKm = pointDistancesKm.slice(startIdx);
    const trimmedElevations = rawElevations.slice(startIdx);
    const trimmedCadences = rawCadences.slice(startIdx);
    const trimmedPowers = rawPowers.slice(startIdx);
    if (trimmedDistancesKm.length < 2 || trimmedElevations.length < 2) return null;

    const distanceOffsetKm = trimmedDistancesKm[0] || 0;
    const normalizedDistancesKm = trimmedDistancesKm.map((d) => Math.max(0, d - distanceOffsetKm));

    const validTrimmedElevations = trimmedElevations.filter((v) => Number.isFinite(v));
    if (!validTrimmedElevations.length) return null;

    const fallbackEle = validTrimmedElevations[0];
    const sanitizedElevations = trimmedElevations.map((ele) => Number.isFinite(ele) ? ele : fallbackEle);

    let minEle = Infinity;
    let maxEle = -Infinity;
    let ascent = 0;
    let descent = 0;
    let lastEle = null;

    for (const ele of sanitizedElevations) {
      minEle = Math.min(minEle, ele);
      maxEle = Math.max(maxEle, ele);
      if (lastEle != null) {
        const delta = ele - lastEle;
        if (delta > 0) ascent += delta;
        else descent += Math.abs(delta);
      }
      lastEle = ele;
    }

    if (!Number.isFinite(minEle) || !Number.isFinite(maxEle)) return null;

    const samples = 180;
    const totalKm = normalizedDistancesKm[normalizedDistancesKm.length - 1] || 0;
    const sampleDistances = [];
    const sampleElevations = [];
    const sampleCadences = [];
    const samplePowers = [];

    // Bucket boundaries (by index in the trimmed arrays)
    const n = normalizedDistancesKm.length;
    for (let i = 0; i < samples; i += 1) {
      const targetKm = totalKm * (i / Math.max(1, samples - 1));
      let idx = normalizedDistancesKm.findIndex((d) => d >= targetKm);
      if (idx === -1) idx = n - 1;
      idx = Math.max(0, Math.min(sanitizedElevations.length - 1, idx));
      sampleDistances.push(targetKm);
      sampleElevations.push(sanitizedElevations[idx]);

      // Bucket average for cadence / power (smooths noise, shows pauses correctly)
      const bucketStart = Math.floor((i / Math.max(1, samples)) * n);
      const bucketEnd = Math.max(bucketStart + 1, Math.floor(((i + 1) / Math.max(1, samples)) * n));
      let cSum = 0, cCount = 0, pSum = 0, pCount = 0;
      for (let j = bucketStart; j < bucketEnd && j < n; j += 1) {
        if (trimmedCadences[j] != null) { cSum += trimmedCadences[j]; cCount += 1; }
        if (trimmedPowers[j] != null) { pSum += trimmedPowers[j]; pCount += 1; }
      }
      sampleCadences.push(cCount > 0 ? cSum / cCount : null);
      samplePowers.push(pCount > 0 ? pSum / pCount : null);
    }

    // Stats for cadence / power (only over non-null moving values)
    const cadencesValid = trimmedCadences.filter((v) => v != null && v > 0);
    const powersValid = trimmedPowers.filter((v) => v != null);
    const avgCadence = cadencesValid.length ? cadencesValid.reduce((a, b) => a + b, 0) / cadencesValid.length : null;
    const maxCadence = cadencesValid.length ? Math.max(...cadencesValid) : null;
    const avgPower = powersValid.length ? powersValid.reduce((a, b) => a + b, 0) / powersValid.length : null;
    const maxPower = powersValid.length ? Math.max(...powersValid) : null;

    const hasCadence = sampleCadences.some((v) => v != null);
    const hasPower = samplePowers.some((v) => v != null);

    const activity = this._activities[this._idx] || {};
    const avgSpeed = activity.speed?.average;
    const maxSpeed = activity.speed?.maximum;

    return {
      minEle,
      maxEle,
      ascent,
      descent,
      totalKm,
      sampleDistances,
      sampleElevations,
      sampleCadences,
      samplePowers,
      hasCadence,
      hasPower,
      avgCadence,
      maxCadence,
      avgPower,
      maxPower,
      avgSpeed: Number.isFinite(avgSpeed) ? avgSpeed : null,
      maxSpeed: Number.isFinite(maxSpeed) ? maxSpeed : null,
    };
  }

  _renderMiniChart(title, rangeText, samples, unit, color, fillColor, minValue, maxValue, showAxis) {
    const width = 1000;
    const height = 160;
    const padL = 46;
    const padR = 8;
    const padT = 18;
    const padB = showAxis ? 24 : 8;
    const chartW = width - padL - padR;
    const chartH = height - padT - padB;
    const span = Math.max(1, maxValue - minValue);

    // Build polyline with null-handling: break line where no data
    const segments = [];
    let current = [];
    samples.forEach((v, i) => {
      if (v == null) {
        if (current.length) { segments.push(current); current = []; }
      } else {
        const x = padL + (chartW * i) / Math.max(1, samples.length - 1);
        const y = padT + chartH - (((v - minValue) / span) * chartH);
        current.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
    });
    if (current.length) segments.push(current);

    const linesSvg = segments.map((seg) =>
      `<polyline points="${seg.join(' ')}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>`
    ).join('');

    // Fill (only useful for elevation — keep optional)
    let fillSvg = '';
    if (fillColor && segments.length === 1) {
      const seg = segments[0];
      const firstX = seg[0].split(',')[0];
      const lastX = seg[seg.length - 1].split(',')[0];
      fillSvg = `<polyline points="${firstX},${height - padB} ${seg.join(' ')} ${lastX},${height - padB}" fill="${fillColor}" stroke="none"></polyline>`;
    }

    const gridTicks = [0, 0.5, 1].map((t) => {
      const y = padT + chartH - (chartH * t);
      const label = Math.round(minValue + span * t);
      return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}" stroke="rgba(0,0,0,.08)" stroke-dasharray="3 4" />
              <text x="0" y="${(y + 4).toFixed(1)}" font-size="11" fill="rgba(0,0,0,.55)">${label}</text>`;
    }).join('');

    return `
      <div class="eb-profile-head">
        <div class="eb-profile-title">${title}</div>
        <div class="eb-profile-range">${rangeText}</div>
      </div>
      <svg class="eb-profile-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="${title}">
        ${gridTicks}
        ${fillSvg}
        ${linesSvg}
        <text x="${padL - 4}" y="${padT - 4}" font-size="10" fill="rgba(0,0,0,.55)" text-anchor="end">${unit}</text>
      </svg>
    `;
  }

  _renderFullscreenProfile() {
    const el = this._$("eb-fullscreen-profile");
    if (!el) return;

    const profile = this._buildElevationProfileData();
    if (!profile) {
      el.innerHTML = `<div class="eb-profile-title">${this._t("profile_title")}</div><div class="eb-profile-range">${this._t("profile_no_data")}</div>`;
      return;
    }

    const {
      minEle, maxEle, ascent, descent, totalKm,
      sampleElevations, sampleCadences, samplePowers,
      hasCadence, hasPower,
      avgCadence, maxCadence, avgPower, maxPower,
      avgSpeed, maxSpeed,
    } = profile;

    const fmtKm = (v) => `${v.toFixed(v >= 10 ? 1 : 2).replace('.', ',')} km`;
    const axisLabels = [0, 0.25, 0.5, 0.75, 1].map((t) => fmtKm(totalKm * t));

    // Höhe
    const eleChart = this._renderMiniChart(
      this._t("profile_title"),
      this._t("profile_min_max", Math.round(minEle), Math.round(maxEle)),
      sampleElevations,
      "m",
      "#89b52b",
      "rgba(139,195,74,.20)",
      minEle, maxEle,
      false
    );

    // Kadenz
    let cadChart = '';
    if (hasCadence) {
      const cadMin = 0;
      const cadMax = Math.max(20, Math.ceil((maxCadence || 0) / 10) * 10);
      cadChart = this._renderMiniChart(
        this._t("profile_cadence"),
        this._t("profile_avg_max_rpm",
          avgCadence != null ? Math.round(avgCadence) : '–',
          maxCadence != null ? Math.round(maxCadence) : '–'),
        sampleCadences,
        "rpm",
        "#f39c12",
        null,
        cadMin, cadMax,
        false
      );
    }

    // Leistung
    let powChart = '';
    if (hasPower) {
      const powMin = 0;
      const powMax = Math.max(50, Math.ceil((maxPower || 0) / 50) * 50);
      powChart = this._renderMiniChart(
        this._t("profile_power"),
        this._t("profile_avg_max_w",
          avgPower != null ? Math.round(avgPower) : '–',
          maxPower != null ? Math.round(maxPower) : '–'),
        samplePowers,
        "W",
        "#e74c3c",
        null,
        powMin, powMax,
        true
      );
    }

    el.innerHTML = `
      ${eleChart}
      ${cadChart}
      ${powChart}
      <div class="eb-profile-axis">
        ${axisLabels.map((label) => `<span>${label}</span>`).join('')}
      </div>
      <div class="eb-profile-stats">
        <div class="eb-profile-stat"><div class="eb-pv">${Math.round(ascent)} m</div><div class="eb-pl">${this._t("profile_ascent")}</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${Math.round(descent)} m</div><div class="eb-pl">${this._t("profile_descent")}</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${avgSpeed != null ? avgSpeed.toFixed(1).replace('.', ',') : '–'} km/h</div><div class="eb-pl">${this._t("profile_avg_speed")}</div></div>
        <div class="eb-profile-stat"><div class="eb-pv">${maxSpeed != null ? maxSpeed.toFixed(1).replace('.', ',') : '–'} km/h</div><div class="eb-pl">${this._t("profile_max_speed")}</div></div>
      </div>
    `;
  }


  _setFullscreenTab(tab) {
    const next = tab === "elevation" ? "elevation" : "map";
    this._fullscreenTab = next;
    const isMap = next === "map";
    const mapBtn = this._$("eb-tab-map");
    const eleBtn = this._$("eb-tab-elevation");
    const mapEl = this._$("eb-fullscreen-map");
    const profileEl = this._$("eb-fullscreen-profile");
    const fitBtn = this._$("eb-fit");
    if (mapBtn) {
      mapBtn.classList.toggle("active", isMap);
      mapBtn.setAttribute("aria-selected", isMap ? "true" : "false");
    }
    if (eleBtn) {
      eleBtn.classList.toggle("active", !isMap);
      eleBtn.setAttribute("aria-selected", !isMap ? "true" : "false");
    }
    if (mapEl) mapEl.classList.toggle("eb-hidden", !isMap);
    if (profileEl) profileEl.classList.toggle("eb-hidden", isMap);
    if (fitBtn) fitBtn.classList.toggle("eb-hidden", !isMap);
    if (isMap) {
      this._scheduleFullscreenSync("tab map");
    } else {
      this._renderFullscreenProfile();
    }
  }

  _slugify(text) {
    return String(text || "ride")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "ride";
  }

  _escapeXml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }

  _trackPointTime(point, index) {
    const candidates = [point?.time, point?.timestamp, point?.ts, point?.dateTime, point?.recordedAt];
    for (const candidate of candidates) {
      if (!candidate) continue;
      const date = new Date(candidate);
      if (!Number.isNaN(date.getTime())) return date.toISOString();
    }

    const activity = this._activities[this._idx];
    const base = activity?.startTime ? new Date(activity.startTime) : null;
    if (base && !Number.isNaN(base.getTime())) {
      const offsetSeconds = Math.max(0, index);
      return new Date(base.getTime() + offsetSeconds * 1000).toISOString();
    }

    return null;
  }

  _buildCurrentGpx() {
    if (!Array.isArray(this._currentTrack) || !this._currentTrack.length) return null;

    const activity = this._activities[this._idx] || {};
    const title = activity.title || "Bosch eBike Ride";
    const type = activity.type || "Ride";

    const trackPoints = this._currentTrack.map((point, index) => {
      const ele = Number.isFinite(point?.ele) ? point.ele
        : Number.isFinite(point?.alt) ? point.alt
        : Number.isFinite(point?.altitude) ? point.altitude
        : null;
      const time = this._trackPointTime(point, index);
      return `    <trkpt lat="${point.lat}" lon="${point.lon}">` +
        (ele != null ? `\n      <ele>${ele}</ele>` : "") +
        (time ? `\n      <time>${time}</time>` : "") +
        `\n    </trkpt>`;
    }).join("\n");

    const metaTime = activity.startTime ? new Date(activity.startTime) : null;
    const metaTimeXml = metaTime && !Number.isNaN(metaTime.getTime())
      ? `\n    <time>${metaTime.toISOString()}</time>` : "";

    return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Home Assistant Bosch eBike Map Card" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${this._escapeXml(title)}</name>${metaTimeXml}
  </metadata>
  <trk>
    <name>${this._escapeXml(title)}</name>
    <type>${this._escapeXml(type)}</type>
    <trkseg>
${trackPoints}
    </trkseg>
  </trk>
</gpx>`;
  }

  _currentGpxFilename() {
    const activity = this._activities[this._idx] || {};
    const date = activity.startTime ? new Date(activity.startTime) : null;
    const datePart = date && !Number.isNaN(date.getTime()) ? date.toISOString().slice(0, 10) : "ride";
    const titlePart = this._slugify(activity.title || "bosch-ebike-ride");
    return `${datePart}-${titlePart}.gpx`;
  }

  _downloadCurrentGpx() {
    const gpx = this._buildCurrentGpx();
    if (!gpx) {
      this._msg("Kein GPX für diese Route verfügbar");
      this._setTimer(() => this._msg(""), 2200);
      return;
    }

    try {
      const blob = new Blob([gpx], { type: "application/gpx+xml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = this._currentGpxFilename();
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      this._setTimer(() => URL.revokeObjectURL(url), 2000);
    } catch (error) {
      console.error("[Bosch eBike Map] GPX download error", error);
      this._msg("GPX-Download fehlgeschlagen");
      this._setTimer(() => this._msg(""), 2200);
    }
  }


  _openFullscreen() {
    this._fullscreenOpen = true;
    const overlay = this._$("eb-fullscreen-overlay");
    if (!overlay) return;
    overlay.classList.add("open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    this._setFullscreenTab(this._fullscreenTab || "map");
    this._scheduleFullscreenSync("open");
  }

  _closeFullscreen() {
    this._fullscreenOpen = false;
    const overlay = this._$("eb-fullscreen-overlay");
    if (overlay) {
      overlay.classList.remove("open");
      overlay.setAttribute("aria-hidden", "true");
    }
    document.body.style.overflow = "";
    this._destroyFullscreenMap();
    this._rebuildInlineMapAfterFullscreen();
  }

  _rebuildInlineMapAfterFullscreen() {
    if (!this._connected || !this._currentTrack.length) return;
    this._destroyMap(true);
    this._needsInlineFit = true;
    this._inlineUserAdjustedView = false;

    [0, 100, 280, 700].forEach((delay) => {
      this._setTimer(() => {
        this._activateMap("fullscreen closed");
      }, delay);
    });
  }

  _syncFullscreenMap(reason = "") {
    if (!this._fullscreenOpen || !this._currentTrack.length) return;
    const Leaflet = window.L;
    const mapEl = this._$("eb-fullscreen-map");
    if (!Leaflet || !mapEl) return;

    const rect = mapEl.getBoundingClientRect();
    if (rect.width < 100 || rect.height < 100) return;

    if (!this._fullscreenMap) {
      try {
        mapEl.innerHTML = "";
        this._fullscreenMap = Leaflet.map(mapEl, {
          zoomControl: true,
          attributionControl: false,
          preferCanvas: true,
          zoomAnimation: true,
          fadeAnimation: true,
          markerZoomAnimation: true,
        }).setView([48.7, 12.4], 10);

        this._applyBaseLayer(this._fullscreenMap, "fullscreen", true);

        this._fullscreenTrackGroup = Leaflet.layerGroup().addTo(this._fullscreenMap);
      } catch (error) {
        console.error("[Bosch eBike Map] fullscreen map create error", error);
        this._destroyFullscreenMap();
        return;
      }
    }

    try {
      this._fullscreenMap.invalidateSize({ pan: false, animate: false });
    } catch (_) {}

    this._renderTrackToMap(this._fullscreenMap, this._fullscreenTrackGroup, {
      padding: [60, 60],
      legend: "fullscreen",
      fit: this._needsFullscreenFit && !this._fullscreenUserAdjustedView,
    });
    this._needsFullscreenFit = false;

    // Re-render Wikipedia markers if enabled (covers cached articles instantly)
    if (this._wikiEnabled) {
      const cached = this._wikiArticles.get(this._currentTrackActivityId);
      if (cached) {
        this._renderWikiMarkers(cached);
      } else {
        this._loadAndRenderWiki();
      }
    }
    // Re-render POI markers
    if (this._poiEnabled) {
      const cached = this._poiData.get(this._currentTrackActivityId);
      if (cached) {
        this._renderPoiMarkers(cached);
      } else {
        this._loadAndRenderPoi();
      }
    }

    this._setTimer(() => {
      try { this._fullscreenMap?.invalidateSize({ pan: false, animate: false }); } catch (_) {}
    }, 150);
  }

  _go(dir) {
    const next = this._idx + dir;
    if (next >= 0 && next < this._activities.length) this._show(next, true);
  }

  _jumpDate(str) {
    if (!str) return;
    const target = new Date(str).getTime();
    let best = 0;
    let bestDiff = Infinity;

    this._activities.forEach((activity, index) => {
      const diff = Math.abs(new Date(activity.startTime).getTime() - target);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = index;
      }
    });

    this._show(best, true);
  }
}

// ============================================================================
// Heatmap card — overlays all rides on one map
// ============================================================================

class BoschEBikeHeatmapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._tracks = [];
    this._instances = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._filterRange = "365"; // days; "all" for everything
    this._map = null;
    this._tracksGroup = null;
    this._baseLayer = null;
    this._mapStyle = "osm";
    this._ready = false;
    this._booting = false;
    this._loaded = false;
  }

  setConfig(config) {
    this._config = {
      height: config.height || 500,
      ...config,
    };
    if (config.account_id) {
      this._filterAccount = config.account_id;
      this._lockedAccount = true;
    } else {
      this._lockedAccount = false;
    }
    if (config.bike_id) {
      this._filterBike = config.bike_id;
      this._lockedBike = true;
    } else {
      this._lockedBike = false;
    }
    if (this._ready) {
      this._applyHeatTitle();
      this._populateFilters();
      this._renderTracks();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  static getConfigElement() {
    return document.createElement("bosch-ebike-heatmap-card-editor");
  }

  static getStubConfig() {
    return { height: 500 };
  }

  getCardSize() {
    return Math.ceil((this._config.height || 500) / 50) + 2;
  }

  _applyHeatTitle() {
    const head = this.querySelector(".heat-head span");
    if (head && this._config && this._config.title) {
      head.textContent = this._config.title;
    }
  }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildDOM();
      this._ready = true;
      this._applyHeatTitle();
      await ensureLeaflet();
      await this._fetchInstances();
      this._populateFilters();
      this._createMap();
      await this._loadTracks();
      this._renderTracks();
    } catch (err) {
      console.error("[Bosch eBike Heatmap] boot error", err);
      const msg = this.querySelector("#heat-msg");
      if (msg) msg.textContent = "Fehler: " + (err?.message || err);
    } finally {
      this._booting = false;
    }
  }

  _buildDOM() {
    const h = this._config.height || 500;
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);
    const style = document.createElement("style");
    style.textContent = LEAFLET_INLINE_CSS + `
      .heat-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .heat-filters {
        display:flex; flex-wrap:wrap; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .heat-filters select {
        padding:5px 8px; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .heat-filter-lbl { font-size:12px; color:var(--secondary-text-color,#666); align-self:center; }
      .heat-map-wrap { position:relative; }
      .heat-map { width:100% !important; height:${h}px !important; min-height:${h}px; z-index:0; position:relative; }
      .heat-overlay {
        position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
        color:var(--secondary-text-color,#999); font-size:14px; pointer-events:none;
      }
      .heat-stats { padding:8px 16px 12px; font-size:13px; color:var(--secondary-text-color,#666); display:flex; gap:16px; flex-wrap:wrap; }
      .heat-stats b { color:var(--primary-text-color,#333); }
    `;
    card.appendChild(style);

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="heat-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M3,3H21V5H3V3M3,7H21V9H3V7M3,11H21V13H3V11M3,15H21V17H3V15M3,19H21V21H3V19Z"/></svg>
        <span>${t("heatmap_title")}</span>
      </div>
      <div class="heat-filters">
        <span class="heat-filter-lbl">${t("heat_range_label")}</span>
        <select id="heat-range">
          <option value="30">${t("heat_range_30")}</option>
          <option value="90">${t("heat_range_90")}</option>
          <option value="365" selected>${t("heat_range_365")}</option>
          <option value="all">${t("heat_range_all")}</option>
        </select>
        <span class="heat-filter-lbl" id="heat-acc-lbl" style="display:none;">${t("heat_account_label")}</span>
        <select id="heat-account" style="display:none;">
          <option value="all">${t("all_accounts")}</option>
        </select>
        <span class="heat-filter-lbl" id="heat-bike-lbl" style="display:none;">${t("heat_bike_label")}</span>
        <select id="heat-bike" style="display:none;">
          <option value="all">${t("all_bikes")}</option>
        </select>
      </div>
      <div class="heat-map-wrap">
        <div id="heat-map" class="heat-map"></div>
        <div class="heat-overlay" id="heat-msg">${t("heat_loading")}</div>
      </div>
      <div class="heat-stats" id="heat-stats"></div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this.querySelector("#heat-range").addEventListener("change", async (e) => {
      this._filterRange = e.target.value;
      await this._loadTracks();
      this._renderTracks();
    });
    this.querySelector("#heat-account").addEventListener("change", (e) => {
      this._filterAccount = e.target.value;
      this._populateBikeFilter();
      this._renderTracks();
    });
    this.querySelector("#heat-bike").addEventListener("change", (e) => {
      this._filterBike = e.target.value;
      this._renderTracks();
    });
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) {
      this._instances = [];
    }
  }

  _populateFilters() {
    const accountSel = this.querySelector("#heat-account");
    const accLbl = this.querySelector("#heat-acc-lbl");
    if (this._lockedAccount) {
      if (accountSel) accountSel.style.display = "none";
      if (accLbl) accLbl.style.display = "none";
    } else if (this._instances.length > 1) {
      const opts = ['<option value="all">Alle Konten</option>'];
      for (const inst of this._instances) {
        opts.push(`<option value="${inst.config_entry_id}">${this._escapeHtml(inst.label)}</option>`);
      }
      accountSel.innerHTML = opts.join("");
      accountSel.value = this._filterAccount;
      accountSel.style.display = "";
      accLbl.style.display = "";
    }
    this._populateBikeFilter();
  }

  _populateBikeFilter() {
    const bikeSel = this.querySelector("#heat-bike");
    const lbl = this.querySelector("#heat-bike-lbl");
    if (this._lockedBike) {
      if (bikeSel) bikeSel.style.display = "none";
      if (lbl) lbl.style.display = "none";
      return;
    }
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) {
        const label = this._instances.length > 1 ? `${inst.label} — ${b.label}` : b.label;
        bikes.push({ id: b.id, label });
      }
    }
    if (bikes.length > 1) {
      const opts = ['<option value="all">Alle Bikes</option>'];
      for (const b of bikes) {
        opts.push(`<option value="${b.id}">${this._escapeHtml(b.label)}</option>`);
      }
      bikeSel.innerHTML = opts.join("");
      if (this._filterBike !== "all" && !bikes.some((x) => x.id === this._filterBike)) {
        this._filterBike = "all";
      }
      bikeSel.value = this._filterBike;
      bikeSel.style.display = "";
      lbl.style.display = "";
    } else {
      bikeSel.style.display = "none";
      lbl.style.display = "none";
    }
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  _createMap() {
    const Leaflet = window.L;
    const mapEl = this.querySelector("#heat-map");
    if (!Leaflet || !mapEl) return;
    this._map = Leaflet.map(mapEl, {
      zoomControl: true,
      attributionControl: false,
      preferCanvas: true,
    }).setView([48.7, 12.4], 6);
    const def = MAP_STYLES.osm;
    this._baseLayer = Leaflet.tileLayer(def.url, def.options).addTo(this._map);
    this._tracksGroup = Leaflet.layerGroup().addTo(this._map);
  }

  async _loadTracks() {
    const msg = this.querySelector("#heat-msg");
    if (msg) { msg.textContent = ebT(this._hass, "heat_loading"); msg.style.display = ""; }
    const params = { type: "bosch_ebike/get_all_tracks" };
    if (this._filterRange !== "all") {
      params.max_age_days = parseInt(this._filterRange, 10);
    }
    try {
      const res = await this._hass.callWS(params);
      this._tracks = res.tracks || [];
      this._loaded = true;
    } catch (err) {
      console.error("[Bosch eBike Heatmap] load failed", err);
      this._tracks = [];
      if (msg) msg.textContent = ebT(this._hass, "heat_load_failed");
      return;
    }
    if (msg) msg.style.display = "none";
  }

  _renderTracks() {
    if (!this._map || !this._tracksGroup) return;
    const Leaflet = window.L;
    this._tracksGroup.clearLayers();

    const filtered = this._tracks.filter((t) => {
      if (this._filterAccount !== "all" && t.account_id !== this._filterAccount) return false;
      if (this._filterBike !== "all" && t.bike_id !== this._filterBike) return false;
      return true;
    });

    let totalDist = 0;
    let allLatLngs = [];
    for (const t of filtered) {
      if (!t.points || t.points.length < 2) continue;
      const latlngs = t.points.map((p) => [p.lat, p.lon]);
      Leaflet.polyline(latlngs, {
        color: "#d32f2f",
        weight: 2.5,
        opacity: 0.35,
        smoothFactor: 1.5,
      }).addTo(this._tracksGroup);
      allLatLngs = allLatLngs.concat(latlngs);
      totalDist += t.distance || 0;
    }

    if (allLatLngs.length) {
      try {
        const bounds = Leaflet.latLngBounds(allLatLngs);
        this._map.fitBounds(bounds, { padding: [40, 40], animate: false });
      } catch (_) {}
    }

    const stats = this.querySelector("#heat-stats");
    if (stats) {
      stats.innerHTML = `
        <div>${ebT(this._hass, "heat_stat_rides")}: <b>${filtered.length}</b></div>
        <div>${ebT(this._hass, "heat_stat_distance")}: <b>${(totalDist / 1000).toFixed(0)} km</b></div>
      `;
    }
    const msg = this.querySelector("#heat-msg");
    if (msg) {
      if (!filtered.length) {
        msg.textContent = ebT(this._hass, "heat_no_match");
        msg.style.display = "";
      } else {
        msg.style.display = "none";
      }
    }
  }
}

class BoschEBikeMapCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._loadInstances();
  }

  async _loadInstances() {
    if (!this._hass) return;
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) {
      this._instances = [];
    }
    this._render();
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  _emit() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
  }

  _bikeOptionsForAccount(accountId) {
    const out = [];
    for (const inst of (this._instances || [])) {
      if (accountId && accountId !== "all" && inst.config_entry_id !== accountId) continue;
      for (const b of (inst.bikes || [])) {
        const hasMultiInst = (this._instances || []).length > 1;
        const label = hasMultiInst && !accountId ? `${inst.label} — ${b.label}` : b.label;
        out.push({ id: b.id, label });
      }
    }
    return out;
  }

  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    const radii = [
      { v: 500, l: "500 m" },
      { v: 1000, l: "1 km" },
      { v: 2000, l: "2 km" },
      { v: 5000, l: "5 km" },
      { v: 10000, l: "10 km" },
    ];
    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const defaultSuffix = " " + t("radius_default_suffix");
    const selectedWikiRadius = parseInt(cfg.wiki_radius_m, 10) || 1000;
    const wikiRadiusOpts = radii.map((r) => {
      const sel = r.v === selectedWikiRadius ? " selected" : "";
      const label = r.v === 1000 ? `${r.l}${defaultSuffix}` : r.l;
      return `<option value="${r.v}"${sel}>${label}</option>`;
    }).join("");

    const selectedPoiRadius = parseInt(cfg.poi_radius_m, 10) || 1000;
    const poiRadiusOpts = radii.map((r) => {
      const sel = r.v === selectedPoiRadius ? " selected" : "";
      const label = r.v === 1000 ? `${r.l}${defaultSuffix}` : r.l;
      return `<option value="${r.v}"${sel}>${label}</option>`;
    }).join("");

    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_height")}</label>
      <input type="number" value="${cfg.height || 400}" min="200" max="1000" step="50" style="${inputStyle}" id="h-in">

      <label style="${labelStyle}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("rides_title")}" style="${inputStyle}" id="title-in">
      <span style="${hintStyle}">${t("editor_title_hint")}</span>

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>

      <label style="${labelStyle}">${t("editor_wiki_radius")}</label>
      <select id="wiki-radius-in" style="${inputStyle}">${wikiRadiusOpts}</select>
      <span style="${hintStyle}">${t("editor_wiki_radius_hint")}</span>

      <label style="${labelStyle}">${t("editor_poi_radius")}</label>
      <select id="poi-radius-in" style="${inputStyle}">${poiRadiusOpts}</select>
      <span style="${hintStyle}">${t("editor_poi_radius_hint")}</span>
    </div>`;

    this.querySelector("#h-in").addEventListener("change", (e) => {
      this._config = { ...this._config, height: parseInt(e.target.value, 10) || 400 };
      this._emit();
    });
    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v;
      else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v;
      else delete this._config.account_id;
      // Reset bike when account changes
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v;
      else delete this._config.bike_id;
      this._emit();
    });
    this.querySelector("#wiki-radius-in").addEventListener("change", (e) => {
      const v = parseInt(e.target.value, 10);
      this._config = { ...this._config };
      if (v && v !== 1000) this._config.wiki_radius_m = v;
      else delete this._config.wiki_radius_m;
      this._emit();
    });
    this.querySelector("#poi-radius-in").addEventListener("change", (e) => {
      const v = parseInt(e.target.value, 10);
      this._config = { ...this._config };
      if (v && v !== 1000) this._config.poi_radius_m = v;
      else delete this._config.poi_radius_m;
      this._emit();
    });
  }
}

// Heatmap card editor — same UX as the map card editor minus title customisation
class BoschEBikeHeatmapCardEditor extends BoschEBikeMapCardEditor {
  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_height")}</label>
      <input type="number" value="${cfg.height || 500}" min="200" max="1500" step="50" style="${inputStyle}" id="h-in">

      <label style="${labelStyle}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("heatmap_title")}" style="${inputStyle}" id="title-in">

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>
    </div>`;

    this.querySelector("#h-in").addEventListener("change", (e) => {
      this._config = { ...this._config, height: parseInt(e.target.value, 10) || 500 };
      this._emit();
    });
    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v;
      else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v;
      else delete this._config.account_id;
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v;
      else delete this._config.bike_id;
      this._emit();
    });
  }
}

/* ===========================================================================
 * Calendar Card - GitHub-contributions-style per-day distance heatmap
 * ===========================================================================
 *
 * Reads all activities from the existing bosch_ebike/list_activities WS,
 * aggregates them per local-time day, and renders a 7-row grid of weeks.
 * Each cell is colored by total km on that day. Hover shows a tooltip.
 *
 * Lockable to a single account / bike (same pattern as the other cards).
 * No backend changes required.
 */

class BoschEBikeCalendarCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._activities = [];
    this._instances = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._filterRange = "365";   // days, or "all"
    this._lockedAccount = false;
    this._lockedBike = false;
    this._ready = false;
    this._booting = false;
  }

  setConfig(config) {
    this._config = { ...config };
    if (config.account_id) { this._filterAccount = config.account_id; this._lockedAccount = true; }
    else { this._lockedAccount = false; }
    if (config.bike_id) { this._filterBike = config.bike_id; this._lockedBike = true; }
    else { this._lockedBike = false; }
    if (this._ready) {
      this._applyTitle();
      this._populateFilters();
      this._render();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  static getConfigElement() { return document.createElement("bosch-ebike-calendar-card-editor"); }
  static getStubConfig() { return {}; }
  getCardSize() { return 5; }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildDOM();
      this._ready = true;
      this._applyTitle();
      await this._fetchInstances();
      this._populateFilters();
      await this._loadActivities();
      this._render();
    } catch (err) {
      console.error("[Bosch eBike Calendar] boot error", err);
      const msg = this.querySelector("#cal-msg");
      if (msg) msg.textContent = "Fehler: " + (err?.message || err);
    } finally {
      this._booting = false;
    }
  }

  _applyTitle() {
    const head = this.querySelector(".cal-head span");
    if (head && this._config && this._config.title) head.textContent = this._config.title;
  }

  _buildDOM() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);
    const style = document.createElement("style");
    style.textContent = `
      .cal-head {
        display:flex; align-items:center; gap:8px; padding:12px 16px;
        background:var(--primary-color,#03a9f4); color:#fff; font-size:16px; font-weight:500;
      }
      .cal-filters {
        display:flex; flex-wrap:wrap; gap:8px; padding:8px 12px;
        background:var(--secondary-background-color,#f5f5f5);
        border-bottom:1px solid var(--divider-color,#e0e0e0);
      }
      .cal-filters select {
        padding:5px 8px; border:1px solid var(--divider-color,#ccc);
        border-radius:6px; font-size:13px;
        background:var(--card-background-color,#fff); color:var(--primary-text-color,#333);
      }
      .cal-filter-lbl { font-size:12px; color:var(--secondary-text-color,#666); align-self:center; }
      .cal-body { padding:14px 16px; overflow-x:auto; }
      .cal-grid {
        display:inline-grid;
        grid-template-rows: 14px repeat(7, 12px);
        gap:3px;
        font-size:10px;
      }
      .cal-month-label {
        font-size:10px; color:var(--secondary-text-color,#666);
        white-space:nowrap;
        text-align:left;
      }
      .cal-cell {
        width:12px; height:12px; border-radius:2px;
        background:var(--cal-bucket-0,#ebedf0);
        cursor:default;
      }
      .cal-cell.b1 { background:var(--cal-bucket-1,#9be9a8); }
      .cal-cell.b2 { background:var(--cal-bucket-2,#40c463); }
      .cal-cell.b3 { background:var(--cal-bucket-3,#30a14e); }
      .cal-cell.b4 { background:var(--cal-bucket-4,#216e39); }
      .cal-cell.spacer { background:transparent; pointer-events:none; }
      .cal-legend { display:flex; align-items:center; gap:6px; padding:0 16px 8px; font-size:11px; color:var(--secondary-text-color,#666); }
      .cal-legend .cal-cell { width:10px; height:10px; }
      .cal-stats { padding:8px 16px 14px; font-size:13px; color:var(--secondary-text-color,#666); display:flex; gap:18px; flex-wrap:wrap; }
      .cal-stats b { color:var(--primary-text-color,#333); }
      .cal-overlay {
        padding:18px 16px; color:var(--secondary-text-color,#999); font-size:13px; text-align:center;
      }
      @media (prefers-color-scheme: dark) {
        .cal-cell { background:var(--cal-bucket-0-dark,#1b1f23); }
        .cal-cell.b1 { background:var(--cal-bucket-1-dark,#0e4429); }
        .cal-cell.b2 { background:var(--cal-bucket-2-dark,#006d32); }
        .cal-cell.b3 { background:var(--cal-bucket-3-dark,#26a641); }
        .cal-cell.b4 { background:var(--cal-bucket-4-dark,#39d353); }
      }
    `;
    card.appendChild(style);

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="cal-head">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="white" d="M19,3H18V1H16V3H8V1H6V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.9 20.1,3 19,3M19,19H5V8H19V19M7,10H12V15H7V10Z"/></svg>
        <span>${t("calendar_title")}</span>
      </div>
      <div class="cal-filters">
        <span class="cal-filter-lbl">${t("cal_range_label")}</span>
        <select id="cal-range">
          <option value="365" selected>${t("cal_range_1y")}</option>
          <option value="730">${t("cal_range_2y")}</option>
          <option value="1825">${t("cal_range_5y")}</option>
          <option value="all">${t("cal_range_all")}</option>
        </select>
        <span class="cal-filter-lbl" id="cal-acc-lbl" style="display:none;">${t("cal_account_label")}</span>
        <select id="cal-account" style="display:none;">
          <option value="all">${t("cal_account_label")}</option>
        </select>
        <span class="cal-filter-lbl" id="cal-bike-lbl" style="display:none;">${t("cal_bike_label")}</span>
        <select id="cal-bike" style="display:none;">
          <option value="all">${t("cal_bike_label")}</option>
        </select>
      </div>
      <div class="cal-body" id="cal-body">
        <div class="cal-overlay" id="cal-msg">${t("cal_loading")}</div>
      </div>
      <div class="cal-legend" id="cal-legend"></div>
      <div class="cal-stats" id="cal-stats"></div>
    `;
    while (wrap.firstChild) card.appendChild(wrap.firstChild);

    this.querySelector("#cal-range").addEventListener("change", (e) => {
      this._filterRange = e.target.value;
      this._render();
    });
    this.querySelector("#cal-account").addEventListener("change", (e) => {
      this._filterAccount = e.target.value;
      this._filterBike = "all";
      this._populateBikeFilter();
      this._render();
    });
    this.querySelector("#cal-bike").addEventListener("change", (e) => {
      this._filterBike = e.target.value;
      this._render();
    });
  }

  async _fetchInstances() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
      this._instances = res.instances || [];
    } catch (_) { this._instances = []; }
  }

  async _loadActivities() {
    try {
      const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
      this._activities = res.activities || [];
    } catch (err) {
      console.error("[Bosch eBike Calendar] load_activities failed", err);
      this._activities = [];
    }
  }

  _populateFilters() {
    const accSel = this.querySelector("#cal-account");
    const accLbl = this.querySelector("#cal-acc-lbl");
    if (this._lockedAccount) {
      if (accSel) accSel.style.display = "none";
      if (accLbl) accLbl.style.display = "none";
    } else if (this._instances.length > 1) {
      const t = (k) => ebT(this._hass, k);
      const opts = [`<option value="all">${t("cal_account_label").replace(":", "")}</option>`];
      for (const inst of this._instances) {
        opts.push(`<option value="${this._escapeHtml(inst.config_entry_id)}">${this._escapeHtml(inst.label)}</option>`);
      }
      accSel.innerHTML = opts.join("");
      accSel.value = this._filterAccount;
      accSel.style.display = "";
      accLbl.style.display = "";
    }
    this._populateBikeFilter();
  }

  _populateBikeFilter() {
    const bikeSel = this.querySelector("#cal-bike");
    const bikeLbl = this.querySelector("#cal-bike-lbl");
    if (this._lockedBike) {
      if (bikeSel) bikeSel.style.display = "none";
      if (bikeLbl) bikeLbl.style.display = "none";
      return;
    }
    const bikes = [];
    for (const inst of this._instances) {
      if (this._filterAccount !== "all" && inst.config_entry_id !== this._filterAccount) continue;
      for (const b of (inst.bikes || [])) bikes.push(b);
    }
    if (bikes.length <= 1) {
      bikeSel.style.display = "none";
      bikeLbl.style.display = "none";
      return;
    }
    const t = (k) => ebT(this._hass, k);
    const opts = [`<option value="all">${t("cal_bike_label").replace(":", "")}</option>`];
    for (const b of bikes) {
      opts.push(`<option value="${this._escapeHtml(b.id)}">${this._escapeHtml(b.label)}</option>`);
    }
    bikeSel.innerHTML = opts.join("");
    bikeSel.value = this._filterBike;
    bikeSel.style.display = "";
    bikeLbl.style.display = "";
  }

  _escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  _filteredActivities() {
    return (this._activities || []).filter((a) => {
      if (this._filterAccount !== "all" && a.accountId !== this._filterAccount) return false;
      if (this._filterBike !== "all" && a.bikeId !== this._filterBike) return false;
      return true;
    });
  }

  _aggregateByDay(acts) {
    // Returns Map<YYYY-MM-DD, { rides, distanceMeters }>
    const byDay = new Map();
    for (const a of acts) {
      const ts = a.startTime;
      if (!ts) continue;
      let d;
      try { d = new Date(ts); } catch (_) { continue; }
      if (isNaN(d.getTime())) continue;
      const key = this._localDateKey(d);
      const entry = byDay.get(key) || { rides: 0, distanceMeters: 0 };
      entry.rides += 1;
      entry.distanceMeters += a.distance || 0;
      byDay.set(key, entry);
    }
    return byDay;
  }

  _localDateKey(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
  }

  _bucketForKm(km) {
    if (km <= 0) return 0;
    if (km < 10) return 1;
    if (km < 25) return 2;
    if (km < 50) return 3;
    return 4;
  }

  _render() {
    if (!this._ready) return;
    const body = this.querySelector("#cal-body");
    const stats = this.querySelector("#cal-stats");
    const legend = this.querySelector("#cal-legend");
    if (!body) return;

    const acts = this._filteredActivities();
    const byDay = this._aggregateByDay(acts);

    // Range: pick start/end
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let startDate;
    if (this._filterRange === "all") {
      if (acts.length === 0) {
        body.innerHTML = `<div class="cal-overlay">${ebT(this._hass, "cal_no_match")}</div>`;
        stats.innerHTML = "";
        legend.innerHTML = "";
        return;
      }
      let earliest = Infinity;
      for (const a of acts) {
        const t = Date.parse(a.startTime);
        if (!isNaN(t) && t < earliest) earliest = t;
      }
      startDate = new Date(earliest);
      startDate.setHours(0, 0, 0, 0);
    } else {
      const days = parseInt(this._filterRange, 10);
      startDate = new Date(today.getTime() - (days - 1) * 86400000);
    }

    // Align start to Monday (so the column-based grid is week-aligned).
    // Monday = 1, Sunday = 0 in JS; we want column 0 to be Monday.
    const dow = (startDate.getDay() + 6) % 7; // Mon=0, Sun=6
    const gridStart = new Date(startDate.getTime() - dow * 86400000);
    const totalDays = Math.floor((today.getTime() - gridStart.getTime()) / 86400000) + 1;
    const totalWeeks = Math.ceil(totalDays / 7);

    // Build grid: row 0 = month labels, rows 1..7 = day cells
    const cells = [];
    let activeDays = 0;
    let totalRides = 0;
    let totalDistance = 0;
    let lastMonthLabel = -1;
    const monthFmt = new Intl.DateTimeFormat(this._hassLocale(), { month: "short" });
    const dateFmt = new Intl.DateTimeFormat(this._hassLocale(), { year: "numeric", month: "short", day: "numeric" });

    // Row 0: month labels (one per week column at row 0).
    for (let w = 0; w < totalWeeks; w++) {
      const firstDayOfWeek = new Date(gridStart.getTime() + w * 7 * 86400000);
      const m = firstDayOfWeek.getMonth();
      let label = "";
      if (m !== lastMonthLabel && firstDayOfWeek.getDate() <= 14) {
        label = monthFmt.format(firstDayOfWeek);
        lastMonthLabel = m;
      }
      cells.push({ row: 1, col: w + 1, type: "month", text: label });
    }

    // Rows 1..7 (Mon..Sun) for each week column
    for (let w = 0; w < totalWeeks; w++) {
      for (let d = 0; d < 7; d++) {
        const day = new Date(gridStart.getTime() + (w * 7 + d) * 86400000);
        if (day > today) {
          cells.push({ row: d + 2, col: w + 1, type: "spacer" });
          continue;
        }
        if (day < startDate) {
          cells.push({ row: d + 2, col: w + 1, type: "spacer" });
          continue;
        }
        const key = this._localDateKey(day);
        const info = byDay.get(key);
        const rides = info ? info.rides : 0;
        const km = info ? info.distanceMeters / 1000 : 0;
        if (rides > 0) {
          activeDays += 1;
          totalRides += rides;
          totalDistance += info.distanceMeters;
        }
        const bucket = this._bucketForKm(km);
        const dateStr = dateFmt.format(day);
        let title;
        if (rides > 0) {
          title = ebT(this._hass, "cal_day_summary", dateStr, rides, km);
        } else {
          title = ebT(this._hass, "cal_no_rides_day", dateStr);
        }
        cells.push({ row: d + 2, col: w + 1, type: "cell", bucket, title });
      }
    }

    // Build the DOM
    body.innerHTML = "";
    const grid = document.createElement("div");
    grid.className = "cal-grid";
    grid.style.gridTemplateColumns = `repeat(${totalWeeks}, 12px)`;
    for (const c of cells) {
      const el = document.createElement("div");
      el.style.gridRow = String(c.row);
      el.style.gridColumn = String(c.col);
      if (c.type === "month") {
        el.className = "cal-month-label";
        el.textContent = c.text || "";
      } else if (c.type === "spacer") {
        el.className = "cal-cell spacer";
      } else {
        el.className = "cal-cell" + (c.bucket > 0 ? " b" + c.bucket : "");
        el.title = c.title;
      }
      grid.appendChild(el);
    }
    body.appendChild(grid);

    // Stats row
    const t = (k) => ebT(this._hass, k);
    stats.innerHTML = `
      <div>${t("cal_stat_active_days")}: <b>${activeDays}</b></div>
      <div>${t("cal_stat_rides")}: <b>${totalRides}</b></div>
      <div>${t("cal_stat_distance")}: <b>${(totalDistance / 1000).toFixed(0)} km</b></div>
    `;

    // Legend row
    legend.innerHTML = `
      <span>${t("cal_legend_less")}</span>
      <div class="cal-cell"></div>
      <div class="cal-cell b1"></div>
      <div class="cal-cell b2"></div>
      <div class="cal-cell b3"></div>
      <div class="cal-cell b4"></div>
      <span>${t("cal_legend_more")}</span>
    `;
  }

  _hassLocale() {
    // Try to honor HA's configured locale; fall back to browser default.
    if (this._hass && this._hass.locale && this._hass.locale.language) {
      return this._hass.locale.language;
    }
    return (this._hass && this._hass.language) || navigator.language || "en-GB";
  }
}

// Calendar card editor - reuses the heatmap editor pattern (same fields).
class BoschEBikeCalendarCardEditor extends BoschEBikeMapCardEditor {
  _render() {
    if (!this._config) return;
    const cfg = this._config;
    const inputStyle = "width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);";
    const labelStyle = "display:block;margin-top:14px;margin-bottom:6px;font-weight:500";
    const hintStyle = "display:block;margin-top:4px;font-size:12px;color:var(--secondary-text-color,#777)";

    let accountOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const inst of (this._instances || [])) {
      const selected = cfg.account_id === inst.config_entry_id ? " selected" : "";
      accountOpts += `<option value="${this._escapeHtml(inst.config_entry_id)}"${selected}>${this._escapeHtml(inst.label)}</option>`;
    }

    let bikeOpts = `<option value="">${ebT(this._hass, "editor_select_all")}</option>`;
    for (const b of this._bikeOptionsForAccount(cfg.account_id)) {
      const selected = cfg.bike_id === b.id ? " selected" : "";
      bikeOpts += `<option value="${this._escapeHtml(b.id)}"${selected}>${this._escapeHtml(b.label)}</option>`;
    }

    const t = (k, ...a) => ebT(this._hass, k, ...a);
    this.innerHTML = `<div style="padding:16px">
      <label style="${labelStyle.replace('margin-top:14px;', '')}">${t("editor_title")}</label>
      <input type="text" value="${this._escapeHtml(cfg.title || '')}" placeholder="${t("calendar_title")}" style="${inputStyle}" id="title-in">

      <label style="${labelStyle}">${t("editor_account_label")}</label>
      <select id="acc-in" style="${inputStyle}">${accountOpts}</select>
      <span style="${hintStyle}">${t("editor_account_hint")}</span>

      <label style="${labelStyle}">${t("editor_bike_label")}</label>
      <select id="bike-in" style="${inputStyle}">${bikeOpts}</select>
      <span style="${hintStyle}">${t("editor_bike_hint")}</span>
    </div>`;

    this.querySelector("#title-in").addEventListener("change", (e) => {
      const v = e.target.value.trim();
      this._config = { ...this._config };
      if (v) this._config.title = v; else delete this._config.title;
      this._emit();
    });
    this.querySelector("#acc-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.account_id = v; else delete this._config.account_id;
      delete this._config.bike_id;
      this._emit();
      this._render();
    });
    this.querySelector("#bike-in").addEventListener("change", (e) => {
      const v = e.target.value;
      this._config = { ...this._config };
      if (v) this._config.bike_id = v; else delete this._config.bike_id;
      this._emit();
    });
  }
}

// ===========================================================================
// Dashboard card: user-uploaded image + live ESPHome data + smart-plug control
// ===========================================================================
class BoschEBikeDashboardCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._built = false;
    this._pendingStop = false;
    this._pendingStopTimer = null;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = { ...config };
    if (this._built) { this._applyStatic(); this._render(); }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    this._render();
  }

  static getConfigElement() { return document.createElement("bosch-ebike-dashboard-card-editor"); }
  static getStubConfig() {
    return {
      bike_image: "",
      odometer_entity: "",
      battery_entity: "",
      charging_entity: "",
    };
  }
  getCardSize() { return 6; }

  _t(key, ...args) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    const v = dict[key] != null ? dict[key] : I18N.en[key];
    return typeof v === "function" ? v(...args) : v;
  }

  _build() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);

    const style = document.createElement("style");
    style.textContent = `
      .dash-wrap { padding: 16px; box-sizing: border-box; }
      .dash-title {
        text-align: center; font-size: 20px; font-weight: 600;
        margin: 0 0 8px 0; color: var(--primary-text-color);
      }
      .dash-image-wrap {
        width: 100%; aspect-ratio: 16/10;
        display: flex; align-items: center; justify-content: center;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 12px; overflow: hidden; margin-bottom: 14px;
      }
      .dash-image-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
      .dash-no-image {
        text-align: center; padding: 16px; color: var(--secondary-text-color);
        font-size: 13px; line-height: 1.4;
      }
      .dash-no-image .ico {
        display: block; margin: 0 auto 8px; opacity: .5;
      }
      .dash-row {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 12px; margin-bottom: 12px;
      }
      .dash-tile {
        display: flex; flex-direction: column; align-items: center;
        gap: 4px; padding: 6px 4px;
      }
      .dash-tile ha-icon { --mdc-icon-size: 24px; color: var(--secondary-text-color); }
      .dash-tile ha-icon.accent { color: var(--primary-color, #03a9f4); }
      .dash-tile .val { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .dash-tile .lbl { font-size: 11px; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .04em; }
      .dash-pills {
        display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;
        margin: 6px 0 14px;
      }
      .dash-pill {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 6px 12px; border-radius: 999px;
        background: var(--secondary-background-color, #f0f0f0);
        font-size: 13px; color: var(--primary-text-color);
      }
      .dash-pill ha-icon { --mdc-icon-size: 18px; }
      .dash-pill.charging { background: rgba(76,175,80,.18); color: #2e7d32; }
      .dash-pill.charging ha-icon { color: #2e7d32; }
      .dash-controls {
        display: flex; gap: 10px; margin: 14px 0 12px; flex-wrap: wrap;
      }
      .dash-btn {
        flex: 1 1 140px;
        display: inline-flex; align-items: center; justify-content: center; gap: 6px;
        padding: 10px 14px; border-radius: 10px; border: 0; cursor: pointer;
        font-size: 14px; font-weight: 500;
        background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff);
        transition: filter .15s ease;
      }
      .dash-btn:hover { filter: brightness(1.08); }
      .dash-btn.stop { background: #e53935; }
      .dash-btn.stop.confirm { background: #b71c1c; }
      .dash-btn:disabled { opacity: .4; cursor: not-allowed; }
      .dash-slider-row {
        display: flex; align-items: center; gap: 10px; margin: 10px 0 14px;
      }
      .dash-slider-row .lbl { flex: 0 0 auto; font-size: 13px; color: var(--secondary-text-color); }
      .dash-slider-row input[type=range] { flex: 1; }
      .dash-slider-row .val {
        flex: 0 0 auto; min-width: 38px; text-align: right;
        font-size: 14px; font-weight: 600; color: var(--primary-text-color);
      }
      .dash-batbar-wrap {
        margin-top: 6px;
        background: var(--secondary-background-color, #eee);
        border-radius: 999px; overflow: hidden; height: 22px; position: relative;
      }
      .dash-batbar {
        height: 100%; background: linear-gradient(90deg,#66bb6a,#43a047);
        transition: width .4s ease;
      }
      .dash-batbar.low { background: linear-gradient(90deg,#ffb74d,#fb8c00); }
      .dash-batbar.crit { background: linear-gradient(90deg,#ef5350,#e53935); }
      .dash-batbar-label {
        position: absolute; right: 12px; top: 0; bottom: 0; display: flex;
        align-items: center; font-size: 13px; font-weight: 600;
        color: var(--primary-text-color);
      }
    `;
    card.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "dash-wrap";
    card.appendChild(wrap);

    wrap.innerHTML = `
      <div class="dash-title" id="dash-title"></div>
      <div class="dash-image-wrap" id="dash-image-wrap"></div>
      <div class="dash-row" id="dash-row-stats"></div>
      <div class="dash-pills" id="dash-pills"></div>
      <div class="dash-slider-row" id="dash-slider-row" style="display:none">
        <span class="lbl" id="dash-slider-lbl"></span>
        <input type="range" id="dash-slider" min="20" max="100" step="5" value="80" />
        <span class="val" id="dash-slider-val">80%</span>
      </div>
      <div class="dash-controls" id="dash-controls" style="display:none"></div>
      <div class="dash-batbar-wrap" id="dash-batbar-wrap">
        <div class="dash-batbar" id="dash-batbar" style="width:0%"></div>
        <div class="dash-batbar-label" id="dash-batbar-label">--%</div>
      </div>
    `;

    // Slider live preview + commit on change
    const slider = wrap.querySelector("#dash-slider");
    const sliderVal = wrap.querySelector("#dash-slider-val");
    slider.addEventListener("input", () => { sliderVal.textContent = slider.value + "%"; });
    slider.addEventListener("change", () => {
      const target = this._config.target_soc_entity;
      if (!target || !this._hass) return;
      this._hass.callService("input_number", "set_value", {
        entity_id: target, value: Number(slider.value),
      }).catch((err) => console.error("[Bosch eBike Dashboard] set_value failed", err));
    });

    this._built = true;
    this._applyStatic();
  }

  _applyStatic() {
    const title = this.querySelector("#dash-title");
    if (title) {
      title.textContent =
        this._config.bike_name || this._config.title || "eBike";
    }
  }

  _state(entityId) {
    if (!entityId || !this._hass) return null;
    return this._hass.states[entityId] || null;
  }

  _num(entityId, fallback = null) {
    const s = this._state(entityId);
    if (!s) return fallback;
    const v = Number(s.state);
    return Number.isFinite(v) ? v : fallback;
  }

  _onOff(entityId) {
    const s = this._state(entityId);
    if (!s) return null;
    return s.state === "on" || s.state === "true" || s.state === "charging";
  }

  _formatKm(v) {
    if (v == null || !Number.isFinite(v)) return this._t("dash_state_unknown");
    return v.toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km";
  }
  _formatW(v) {
    if (v == null || !Number.isFinite(v)) return this._t("dash_state_unknown");
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " W";
  }
  _formatPct(v) {
    if (v == null || !Number.isFinite(v)) return this._t("dash_state_unknown");
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " %";
  }

  _render() {
    if (!this._built || !this._hass) return;

    const cfg = this._config;

    // ---------- Image ----------
    const imgWrap = this.querySelector("#dash-image-wrap");
    if (imgWrap) {
      imgWrap.innerHTML = "";
      if (cfg.bike_image) {
        const img = document.createElement("img");
        img.src = cfg.bike_image;
        img.alt = cfg.bike_name || "eBike";
        imgWrap.appendChild(img);
      } else {
        const placeholder = document.createElement("div");
        placeholder.className = "dash-no-image";
        placeholder.innerHTML = `
          <ha-icon class="ico" icon="mdi:bicycle-electric" style="--mdc-icon-size:48px"></ha-icon>
          <div>${this._t("dash_no_image")}</div>
          <div style="opacity:.6;margin-top:4px">${this._t("dash_no_image_hint")}</div>
        `;
        imgWrap.appendChild(placeholder);
      }
    }

    // ---------- Stat tiles ----------
    const odo = this._num(cfg.odometer_entity);
    const lastTour = this._num(cfg.last_tour_distance_entity);
    const power = this._num(cfg.charge_power_entity);
    const battery = this._num(cfg.battery_entity);
    const isCharging = this._onOff(cfg.charging_entity);

    const row = this.querySelector("#dash-row-stats");
    if (row) {
      row.innerHTML = "";
      const tiles = [
        { icon: "mdi:counter", label: this._t("dash_label_odo"), val: this._formatKm(odo) },
      ];
      if (cfg.last_tour_distance_entity) {
        tiles.push({ icon: "mdi:map-marker-distance", label: this._t("dash_label_last_tour"), val: this._formatKm(lastTour) });
      }
      if (cfg.charge_power_entity) {
        tiles.push({
          icon: "mdi:flash",
          label: this._t("dash_label_charge_power"),
          val: this._formatW(power),
          accent: !!(isCharging && power && power > 0),
        });
      }
      for (const t of tiles) {
        const el = document.createElement("div");
        el.className = "dash-tile";
        el.innerHTML = `
          <ha-icon class="${t.accent ? "accent" : ""}" icon="${t.icon}"></ha-icon>
          <div class="val">${t.val}</div>
          <div class="lbl">${t.label}</div>
        `;
        row.appendChild(el);
      }
    }

    // ---------- Status pills ----------
    const pills = this.querySelector("#dash-pills");
    if (pills) {
      pills.innerHTML = "";
      const stateLabel = isCharging == null
        ? this._t("dash_state_unknown")
        : isCharging ? this._t("dash_state_charging") : this._t("dash_state_not_charging");
      const stateIcon = isCharging ? "mdi:battery-charging" : "mdi:power-plug-off";
      const pill = document.createElement("span");
      pill.className = "dash-pill" + (isCharging ? " charging" : "");
      pill.innerHTML = `<ha-icon icon="${stateIcon}"></ha-icon><span>${stateLabel}</span>`;
      pills.appendChild(pill);

      if (cfg.battery_entity) {
        const bp = document.createElement("span");
        bp.className = "dash-pill";
        bp.innerHTML = `<ha-icon icon="mdi:battery"></ha-icon><span>${this._formatPct(battery)}</span>`;
        pills.appendChild(bp);
      }
    }

    // ---------- Slider ----------
    const sliderRow = this.querySelector("#dash-slider-row");
    const slider = this.querySelector("#dash-slider");
    const sliderVal = this.querySelector("#dash-slider-val");
    const sliderLbl = this.querySelector("#dash-slider-lbl");
    if (cfg.target_soc_entity) {
      sliderRow.style.display = "flex";
      sliderLbl.textContent = this._t("dash_label_target_soc");
      const targetState = this._state(cfg.target_soc_entity);
      if (targetState) {
        const a = targetState.attributes || {};
        if (a.min != null) slider.min = a.min;
        if (a.max != null) slider.max = a.max;
        if (a.step != null) slider.step = a.step;
        const v = Number(targetState.state);
        if (Number.isFinite(v) && document.activeElement !== slider) {
          slider.value = v;
          sliderVal.textContent = v + "%";
        }
      }
    } else {
      sliderRow.style.display = "none";
    }

    // ---------- Buttons ----------
    const controls = this.querySelector("#dash-controls");
    if (controls) {
      controls.innerHTML = "";
      if (cfg.charge_switch_entity) {
        controls.style.display = "flex";
        const sw = this._state(cfg.charge_switch_entity);
        const swOn = sw && sw.state === "on";
        const startBtn = document.createElement("button");
        startBtn.className = "dash-btn";
        startBtn.innerHTML = `<ha-icon icon="mdi:play"></ha-icon><span>${this._t("dash_btn_start")}</span>`;
        startBtn.disabled = swOn === true;
        startBtn.addEventListener("click", () => this._callSwitch("turn_on"));
        controls.appendChild(startBtn);

        const stopBtn = document.createElement("button");
        stopBtn.className = "dash-btn stop" + (this._pendingStop ? " confirm" : "");
        stopBtn.innerHTML = `<ha-icon icon="mdi:stop"></ha-icon><span>${this._pendingStop ? this._t("dash_btn_confirm") : this._t("dash_btn_stop")}</span>`;
        stopBtn.disabled = swOn === false;
        stopBtn.addEventListener("click", () => this._handleStop());
        controls.appendChild(stopBtn);
      } else {
        controls.style.display = "none";
      }
    }

    // ---------- Battery bar ----------
    const bar = this.querySelector("#dash-batbar");
    const barLbl = this.querySelector("#dash-batbar-label");
    if (bar && barLbl) {
      const pct = battery != null && Number.isFinite(battery) ? Math.max(0, Math.min(100, battery)) : 0;
      bar.style.width = pct + "%";
      bar.classList.remove("low", "crit");
      if (pct < 15) bar.classList.add("crit");
      else if (pct < 35) bar.classList.add("low");
      barLbl.textContent = battery != null && Number.isFinite(battery)
        ? Math.round(battery) + " %" : "--%";
    }
  }

  _handleStop() {
    if (!this._pendingStop) {
      this._pendingStop = true;
      this._render();
      this._pendingStopTimer = setTimeout(() => {
        this._pendingStop = false;
        this._render();
      }, 3000);
      return;
    }
    clearTimeout(this._pendingStopTimer);
    this._pendingStop = false;
    this._callSwitch("turn_off");
  }

  _callSwitch(action) {
    const entityId = this._config.charge_switch_entity;
    if (!entityId || !this._hass) return;
    const [domain] = entityId.split(".");
    this._hass.callService(domain, action, { entity_id: entityId })
      .catch((err) => console.error("[Bosch eBike Dashboard] switch call failed", err));
  }
}

// Editor for Dashboard card
class BoschEBikeDashboardCardEditor extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._built = false;
  }

  setConfig(config) {
    this._config = { ...config };
    if (this._built) this._sync();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
  }

  _t(key) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    return dict[key] != null ? dict[key] : I18N.en[key];
  }

  _emit() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
  }

  _entities(filter) {
    if (!this._hass) return [];
    return Object.keys(this._hass.states).filter(filter).sort();
  }

  _build() {
    this.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:12px;";
    this.appendChild(wrap);

    const mk = (label, hint, makeInput) => {
      const block = document.createElement("div");
      block.style.cssText = "display:flex;flex-direction:column;gap:4px;";
      const lbl = document.createElement("label");
      lbl.textContent = label;
      lbl.style.fontWeight = "500";
      block.appendChild(lbl);
      const input = makeInput();
      block.appendChild(input);
      if (hint) {
        const h = document.createElement("small");
        h.textContent = hint;
        h.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
        block.appendChild(h);
      }
      wrap.appendChild(block);
      return input;
    };

    const mkText = (key, labelKey, hintKey) => {
      const input = mk(this._t(labelKey), hintKey ? this._t(hintKey) : null, () => {
        const i = document.createElement("input");
        i.type = "text";
        i.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
        return i;
      });
      input.value = this._config[key] || "";
      input.addEventListener("input", () => {
        if (input.value) this._config[key] = input.value;
        else delete this._config[key];
        this._emit();
      });
      return input;
    };

    const mkEntity = (key, labelKey, hintKey, filter) => {
      const input = mk(this._t(labelKey), hintKey ? this._t(hintKey) : null, () => {
        const sel = document.createElement("select");
        sel.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
        const opt0 = document.createElement("option");
        opt0.value = ""; opt0.textContent = "—";
        sel.appendChild(opt0);
        for (const e of this._entities(filter)) {
          const o = document.createElement("option");
          o.value = e; o.textContent = e;
          sel.appendChild(o);
        }
        return sel;
      });
      input.value = this._config[key] || "";
      input.addEventListener("change", () => {
        if (input.value) this._config[key] = input.value;
        else delete this._config[key];
        this._emit();
      });
      return input;
    };

    const mkImage = (key, labelKey, hintKey) => {
      // Composite widget: text input + Upload button + preview + Clear button.
      // Uses HA's built-in /api/image/upload endpoint (image_upload integration,
      // active in HA core since 2023.4). Files persist under /config/image/
      // and survive HACS updates.
      const block = document.createElement("div");
      block.style.cssText = "display:flex;flex-direction:column;gap:6px;";

      const lbl = document.createElement("label");
      lbl.textContent = this._t(labelKey);
      lbl.style.fontWeight = "500";
      block.appendChild(lbl);

      const row = document.createElement("div");
      row.style.cssText = "display:flex;gap:6px;align-items:center;flex-wrap:wrap;";
      block.appendChild(row);

      const text = document.createElement("input");
      text.type = "text";
      text.placeholder = "/local/bike.webp";
      text.style.cssText = "flex:1 1 220px;min-width:160px;padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
      row.appendChild(text);

      const file = document.createElement("input");
      file.type = "file";
      file.accept = "image/*";
      file.style.display = "none";
      row.appendChild(file);

      const uploadBtn = document.createElement("button");
      uploadBtn.type = "button";
      uploadBtn.textContent = this._t("dash_editor_image_upload");
      uploadBtn.style.cssText = "padding:8px 12px;border-radius:4px;border:0;background:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff);cursor:pointer;font-weight:500;";
      uploadBtn.addEventListener("click", () => file.click());
      row.appendChild(uploadBtn);

      const clearBtn = document.createElement("button");
      clearBtn.type = "button";
      clearBtn.textContent = this._t("dash_editor_image_clear");
      clearBtn.style.cssText = "padding:8px 12px;border-radius:4px;border:1px solid var(--divider-color);background:transparent;color:var(--primary-text-color);cursor:pointer;";
      clearBtn.addEventListener("click", () => {
        text.value = "";
        delete this._config[key];
        this._refreshPreview(preview, "");
        this._emit();
      });
      row.appendChild(clearBtn);

      const status = document.createElement("div");
      status.style.cssText = "font-size:12px;color:var(--secondary-text-color);min-height:16px;";
      block.appendChild(status);

      const preview = document.createElement("div");
      preview.style.cssText = "margin-top:4px;max-width:260px;aspect-ratio:16/10;background:var(--secondary-background-color,#f5f5f5);border-radius:8px;overflow:hidden;display:flex;align-items:center;justify-content:center;";
      block.appendChild(preview);

      if (hintKey) {
        const h = document.createElement("small");
        h.textContent = this._t(hintKey);
        h.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
        block.appendChild(h);
      }

      text.value = this._config[key] || "";
      this._refreshPreview(preview, text.value);

      text.addEventListener("input", () => {
        if (text.value) this._config[key] = text.value;
        else delete this._config[key];
        this._refreshPreview(preview, text.value);
        this._emit();
      });

      file.addEventListener("change", async () => {
        if (!file.files || !file.files[0]) return;
        const picked = file.files[0];
        status.textContent = this._t("dash_editor_image_uploading");
        uploadBtn.disabled = true;
        try {
          const url = await this._uploadImage(picked);
          text.value = url;
          this._config[key] = url;
          this._refreshPreview(preview, url);
          status.textContent = "";
          this._emit();
        } catch (err) {
          console.error("[Bosch eBike Dashboard] image upload failed", err);
          status.textContent = this._t("dash_editor_image_upload_failed") + (err?.message || err);
        } finally {
          uploadBtn.disabled = false;
          file.value = "";
        }
      });

      wrap.appendChild(block);
      return text;  // return text input so _sync() can still set its value
    };

    this._fields = {
      title: mkText("title", "dash_editor_title"),
      bike_image: mkImage("bike_image", "dash_editor_image", "dash_editor_image_hint"),
      bike_name: mkText("bike_name", "dash_editor_bike_name", "dash_editor_bike_name_hint"),
      odometer_entity: mkEntity("odometer_entity", "dash_editor_odo", null,
        (e) => e.startsWith("sensor.")),
      battery_entity: mkEntity("battery_entity", "dash_editor_battery", null,
        (e) => e.startsWith("sensor.")),
      charging_entity: mkEntity("charging_entity", "dash_editor_charging", null,
        (e) => e.startsWith("binary_sensor.") || e.startsWith("sensor.")),
      last_tour_distance_entity: mkEntity("last_tour_distance_entity", "dash_editor_last_tour", null,
        (e) => e.startsWith("sensor.")),
      charge_power_entity: mkEntity("charge_power_entity", "dash_editor_charge_power", null,
        (e) => e.startsWith("sensor.")),
      charge_switch_entity: mkEntity("charge_switch_entity", "dash_editor_charge_switch", null,
        (e) => e.startsWith("switch.")),
      target_soc_entity: mkEntity("target_soc_entity", "dash_editor_target_soc", "dash_editor_target_soc_hint",
        (e) => e.startsWith("input_number.")),
    };

    this._built = true;
  }

  _sync() {
    if (!this._fields) return;
    for (const [key, input] of Object.entries(this._fields)) {
      input.value = this._config[key] || "";
    }
  }

  _refreshPreview(container, url) {
    if (!container) return;
    container.innerHTML = "";
    if (!url) {
      const ph = document.createElement("ha-icon");
      ph.setAttribute("icon", "mdi:image-outline");
      ph.style.cssText = "--mdc-icon-size:36px;color:var(--secondary-text-color);";
      container.appendChild(ph);
      return;
    }
    const img = document.createElement("img");
    img.src = url;
    img.alt = "preview";
    img.style.cssText = "max-width:100%;max-height:100%;object-fit:contain;";
    img.addEventListener("error", () => {
      container.innerHTML = "";
      const broken = document.createElement("ha-icon");
      broken.setAttribute("icon", "mdi:image-broken-variant");
      broken.style.cssText = "--mdc-icon-size:36px;color:#e53935;";
      container.appendChild(broken);
    });
    container.appendChild(img);
  }

  async _uploadImage(file) {
    if (!this._hass) throw new Error("Home Assistant connection not available");
    const token = this._hass.auth && this._hass.auth.data && this._hass.auth.data.access_token;
    if (!token) throw new Error("No access token available");

    // HA's image_upload endpoint imposes a 10 MB ceiling and rejects formats
    // PIL cannot decode. Surface that upfront so the user does not chase a
    // network error when the file is simply too big.
    const MAX_BYTES = 10 * 1024 * 1024;
    if (file.size > MAX_BYTES) {
      throw new Error(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB, max 10 MB)`);
    }

    const fd = new FormData();
    fd.append("file", file, file.name || "bike.webp");
    const resp = await fetch("/api/image/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    if (!resp.ok) {
      // Try JSON first, fall back to plain text so the user sees the server's
      // own message (e.g. "Unable to decode image") in the editor.
      let detail = "";
      const ctype = resp.headers.get("content-type") || "";
      try {
        if (ctype.includes("application/json")) {
          const j = await resp.json();
          detail = j?.message || j?.error || JSON.stringify(j);
        } else {
          detail = (await resp.text()).slice(0, 200);
        }
      } catch (_) { /* ignore */ }
      throw new Error(`HTTP ${resp.status}${detail ? " - " + detail : ""}`);
    }
    const data = await resp.json();
    if (!data || !data.id) throw new Error("Upload response missing id");
    return `/api/image/serve/${data.id}/original`;
  }
}

// ===========================================================================
// 3D Map card: MapLibre + OpenFreeMap, opens individual tours in 3D with
// a time slider, animated marker and sun-mood lighting.
//
// Architecture:
// - Initial view: scrollable list of recent tours matching the configured
//   filters (account_id / bike_id, locked via card YAML).
// - Detail view: click a tour, swap to 3D map. Track polyline, animated
//   marker, time slider, play/pause, info chips, back-button.
// - MapLibre is lazy-loaded from CDN the first time the card mounts.
// ===========================================================================
class BoschEBike3DMapCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._instances = [];
    this._activities = [];
    this._allActivities = [];
    this._filterAccount = "all";
    this._filterBike = "all";
    this._lockedAccount = false;
    this._lockedBike = false;
    this._ready = false;
    this._booting = false;
    this._mode = "list";          // "list" or "detail"
    this._currentActivity = null;
    this._currentTrack = null;
    this._map = null;
    this._marker = null;
    this._fitDone = false;
    this._animRAF = null;
    this._animStartTs = 0;
    this._animStartIndex = 0;
    this._isPlaying = false;
    this._cumDist = null;
    this._totalDistM = 0;
  }

  setConfig(config) {
    this._config = { ...config };
    if (config.account_id) { this._filterAccount = config.account_id; this._lockedAccount = true; }
    if (config.bike_id) { this._filterBike = config.bike_id; this._lockedBike = true; }
    if (this._ready) {
      this._applyHeight();
      this._renderRoot();
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._boot();
  }

  static getConfigElement() { return document.createElement("bosch-ebike-3d-map-card-editor"); }
  static getStubConfig() { return { height: 540, default_pitch: 55, chase_zoom: 17, smooth_window: 15, track_smooth_window: 2, playback_speed: 60 }; }
  getCardSize() { return 7; }

  _t(key, ...args) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    const v = dict[key] != null ? dict[key] : I18N.en[key];
    return typeof v === "function" ? v(...args) : v;
  }

  async _boot() {
    if (this._booting || this._ready) return;
    this._booting = true;
    try {
      this._buildShell();
      this._ready = true;
      this._applyHeight();
      this._showMessage(this._t("map3d_loading"));
      try {
        const res = await this._hass.callWS({ type: "bosch_ebike/list_instances" });
        this._instances = res.instances || [];
      } catch (e) { /* ignore */ }
      const res = await this._hass.callWS({ type: "bosch_ebike/list_activities" });
      this._allActivities = (res.activities || []).sort(
        (a, b) => new Date(b.startTime) - new Date(a.startTime)
      );
      this._applyFilter();
      this._renderRoot();
    } catch (err) {
      console.error("[Bosch eBike 3D] boot error", err);
      this._showMessage("Fehler: " + (err?.message || err));
    } finally {
      this._booting = false;
    }
  }

  _applyFilter() {
    let list = [...this._allActivities];
    if (this._filterAccount !== "all") list = list.filter((a) => a.accountId === this._filterAccount);
    if (this._filterBike !== "all") list = list.filter((a) => a.bikeId === this._filterBike);
    this._activities = list;
  }

  _buildShell() {
    this.innerHTML = "";
    const card = document.createElement("ha-card");
    this.appendChild(card);

    const style = document.createElement("style");
    style.textContent = `
      .map3d-root { position: relative; padding: 0; overflow: hidden; }
      .map3d-head {
        display: flex; align-items: center; gap: 8px; padding: 12px 16px;
        background: var(--primary-color, #03a9f4); color: #fff;
        font-size: 16px; font-weight: 500;
      }
      .map3d-head .title { flex: 1; }
      .map3d-back-btn {
        background: rgba(255,255,255,.15); border: 0; color: #fff;
        padding: 4px 10px; border-radius: 6px; cursor: pointer;
        font-size: 13px; display: inline-flex; align-items: center; gap: 4px;
      }
      .map3d-back-btn:hover { background: rgba(255,255,255,.25); }
      .map3d-list {
        max-height: var(--m3d-h, 540px); overflow-y: auto;
        background: var(--card-background-color);
      }
      .map3d-tour {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 16px; cursor: pointer;
        border-bottom: 1px solid var(--divider-color, #e3e3e5);
        transition: background-color .12s ease;
      }
      .map3d-tour:hover { background: var(--secondary-background-color); }
      .map3d-tour .date { flex: 0 0 110px; font-size: 13px; color: var(--secondary-text-color); }
      .map3d-tour .meta { flex: 1; font-size: 14px; color: var(--primary-text-color); }
      .map3d-tour .right { font-size: 13px; color: var(--secondary-text-color); }
      .map3d-tour .right b { color: var(--primary-text-color); font-weight: 600; }
      .map3d-tour ha-icon { color: var(--primary-color); --mdc-icon-size: 20px; }
      .map3d-msg { padding: 24px; text-align: center; color: var(--secondary-text-color); }
      .map3d-detail { position: relative; }
      .map3d-canvas { width: 100%; height: var(--m3d-h, 540px); position: relative; }
      .map3d-overlay {
        position: absolute; top: 8px; left: 8px; right: 8px;
        display: flex; flex-wrap: wrap; gap: 6px; pointer-events: none;
      }
      .map3d-chip {
        background: rgba(20,24,32,.78); color: #fff; backdrop-filter: blur(6px);
        padding: 4px 10px; border-radius: 999px; font-size: 12px;
        display: inline-flex; align-items: center; gap: 5px;
        pointer-events: auto;
      }
      .map3d-chip ha-icon { --mdc-icon-size: 14px; }
      .map3d-controls {
        position: absolute; left: 8px; right: 8px; bottom: 8px;
        background: rgba(20,24,32,.78); color: #fff; backdrop-filter: blur(8px);
        border-radius: 12px; padding: 10px 12px;
        display: flex; flex-direction: column; gap: 8px;
      }
      .map3d-controls .row1 {
        display: flex; align-items: center; gap: 10px;
      }
      .map3d-play-btn {
        background: var(--primary-color, #03a9f4); color: #fff; border: 0;
        width: 36px; height: 36px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer;
      }
      .map3d-play-btn ha-icon { --mdc-icon-size: 22px; }
      .map3d-rec-btn {
        background: rgba(255,255,255,.18); color: #fff; border: 0;
        width: 32px; height: 32px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; flex: 0 0 32px;
      }
      .map3d-rec-btn:hover { background: rgba(255,255,255,.32); }
      .map3d-rec-btn.active { background: #e53935; color: #fff; }
      .map3d-rec-btn:disabled { opacity: .35; cursor: not-allowed; }
      .map3d-rec-btn ha-icon { --mdc-icon-size: 20px; }
      .map3d-rec-badge { background: rgba(229,57,53,.85); color: #fff; }
      .map3d-rec-badge ha-icon { color: #fff; animation: ebike-rec-blink 1s ease-in-out infinite; }
      @keyframes ebike-rec-blink {
        0%, 49% { opacity: 1; }
        50%, 100% { opacity: 0.25; }
      }
      .map3d-time { font-variant-numeric: tabular-nums; font-size: 13px; }
      .map3d-slider { flex: 1; }
      .map3d-stats {
        display: flex; gap: 14px; font-size: 12px; opacity: .85;
      }
      .map3d-stats .v { font-weight: 600; }
      .maplibregl-canvas:focus { outline: none; }
      .ebike-3d-marker {
        position: relative;
        width: 22px; height: 22px; border-radius: 50%;
        background: #03a9f4; border: 4px solid #fff;
        box-shadow: 0 2px 8px rgba(0,0,0,.5);
        z-index: 10;
      }
      .ebike-3d-marker::before {
        content: ""; position: absolute;
        inset: -10px; border-radius: 50%;
        border: 3px solid #03a9f4; opacity: 0.6;
        animation: ebike-3d-pulse 1.6s ease-out infinite;
      }
      @keyframes ebike-3d-pulse {
        0%   { transform: scale(0.6); opacity: 0.8; }
        100% { transform: scale(1.7); opacity: 0; }
      }
      /* MapLibre marker container z-stacking: ensure the current-position
         marker sits above the start/end dot markers */
      .maplibregl-marker:has(.ebike-3d-marker) { z-index: 5; }
    `;
    card.appendChild(style);

    this._root = document.createElement("div");
    this._root.className = "map3d-root";
    card.appendChild(this._root);
  }

  _applyHeight() {
    const h = Number.isFinite(Number(this._config.height)) ? Number(this._config.height) : 540;
    this._root.style.setProperty("--m3d-h", h + "px");
  }

  _showMessage(text) {
    if (!this._root) return;
    this._root.innerHTML = `
      <div class="map3d-head"><div class="title">${this._config.title || this._t("map3d_title")}</div></div>
      <div class="map3d-msg">${text}</div>
    `;
  }

  _renderRoot() {
    if (!this._root) return;
    if (this._mode === "detail" && this._currentActivity) {
      this._renderDetail();
    } else {
      this._renderList();
    }
  }

  _renderList() {
    this._destroyMap();
    if (!this._activities.length) {
      this._showMessage(this._t("map3d_no_rides"));
      return;
    }
    const lang = (this._hass && this._hass.language) ? this._hass.language : "de-DE";
    const fmtDate = (iso) => {
      try { return new Date(iso).toLocaleDateString(lang, { day: "2-digit", month: "short", year: "numeric" }); }
      catch { return iso; }
    };
    const fmtKm = (m) => (m != null && Number.isFinite(m)) ? (m / 1000).toFixed(1) + " km" : "–";
    const fmtDur = (s) => {
      if (!Number.isFinite(s) || s <= 0) return "–";
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
      return h > 0 ? `${h}h ${m}min` : `${m} min`;
    };
    const rows = this._activities.slice(0, 50).map((a, i) => {
      const km = fmtKm(a.distance);
      const dur = fmtDur(this._tourDurationSec(a));
      const title = a.title || this._t("msg_unnamed_ride");
      return `
        <div class="map3d-tour" data-idx="${i}">
          <div class="date">${fmtDate(a.startTime)}</div>
          <div class="meta">${this._escapeHtml(title)}</div>
          <div class="right"><b>${km}</b> · ${dur}</div>
          <ha-icon icon="mdi:chevron-right"></ha-icon>
        </div>
      `;
    }).join("");
    this._root.innerHTML = `
      <div class="map3d-head"><div class="title">${this._config.title || this._t("map3d_title")}</div></div>
      <div class="map3d-list">${rows}</div>
    `;
    this._root.querySelectorAll(".map3d-tour").forEach((el) => {
      el.addEventListener("click", () => {
        const idx = Number(el.getAttribute("data-idx"));
        const act = this._activities[idx];
        if (act) this._openTour(act);
      });
    });
  }

  _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async _openTour(activity) {
    this._mode = "detail";
    this._currentActivity = activity;
    this._currentTrack = null;
    this._shadowDiagLogged = false;
    this._showMessage(this._t("map3d_loading_track"));
    try {
      const params = { type: "bosch_ebike/get_track", activity_id: activity.id };
      if (activity.accountId) params.config_entry_id = activity.accountId;
      const res = await this._hass.callWS(params);
      const pts = Array.isArray(res.track)
        ? res.track.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon))
        : [];
      if (!pts.length) {
        this._showMessage(this._t("map3d_no_gps"));
        return;
      }
      // Keep the raw GPS samples for the visible polyline so the track
      // on the map matches what was actually recorded. The chase cam,
      // marker, bearings and distance counter use a smoothed copy to
      // damp GPS jitter and avoid motion sickness during playback.
      this._rawTrack = pts;
      const wRaw = this._config.track_smooth_window;
      const w = Number.isFinite(Number(wRaw)) && wRaw !== "" && wRaw !== null
        ? Math.max(0, Math.min(15, Number(wRaw))) : 2;
      this._currentTrack = this._smoothTrackPositions(pts, w);
      this._buildCumulativeDistances();
      this._precomputeBearings();
      this._renderDetail();
    } catch (err) {
      console.error("[Bosch eBike 3D] track load failed", err);
      this._showMessage("Fehler: " + (err?.message || err));
    }
  }

  // Moving-average smoothing of lat/lon. Used to give the chase cam a
  // calm path that does not surface raw GPS wobble. Returns a NEW array
  // so the raw points stay available for the visible polyline.
  _smoothTrackPositions(pts, window) {
    if (!pts || pts.length < 3 || window <= 0) {
      return pts ? pts.slice() : [];
    }
    const W = Math.floor(window);
    const N = pts.length;
    const out = new Array(N);
    for (let i = 0; i < N; i++) {
      const lo = Math.max(0, i - W);
      const hi = Math.min(N - 1, i + W);
      let sLat = 0, sLon = 0, n = 0;
      for (let j = lo; j <= hi; j++) {
        sLat += pts[j].lat;
        sLon += pts[j].lon;
        n++;
      }
      out[i] = {
        ...pts[i],
        lat: sLat / n,
        lon: sLon / n,
      };
    }
    return out;
  }

  _buildCumulativeDistances() {
    const pts = this._currentTrack;
    const cum = [0];
    let total = 0;
    for (let i = 1; i < pts.length; i++) {
      total += this._haversine(pts[i - 1], pts[i]);
      cum.push(total);
    }
    this._cumDist = cum;
    this._totalDistM = total;
  }

  _haversine(a, b) {
    const R = 6371000;
    const rad = Math.PI / 180;
    const dLat = (b.lat - a.lat) * rad;
    const dLon = (b.lon - a.lon) * rad;
    const lat1 = a.lat * rad, lat2 = b.lat * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  // Best-available tour duration in seconds. The backend exposes
  // `durationWithoutStops` (preferred) and `endTime`; legacy callers may
  // also pass a `duration` field. We try them in that order and fall
  // back to 0 if nothing usable is present.
  _tourDurationSec(a) {
    if (!a) return 0;
    if (Number.isFinite(a.durationWithoutStops) && a.durationWithoutStops > 0) {
      return a.durationWithoutStops;
    }
    if (Number.isFinite(a.duration) && a.duration > 0) {
      return a.duration;
    }
    if (a.startTime && a.endTime) {
      const d = (new Date(a.endTime).getTime() - new Date(a.startTime).getTime()) / 1000;
      if (Number.isFinite(d) && d > 0) return d;
    }
    return 0;
  }

  _renderDetail() {
    const a = this._currentActivity;
    if (!a) return;
    const title = a.title || this._t("msg_unnamed_ride");
    this._root.innerHTML = `
      <div class="map3d-head">
        <button class="map3d-back-btn" type="button">
          <ha-icon icon="mdi:arrow-left"></ha-icon><span>${this._t("map3d_back")}</span>
        </button>
        <div class="title">${this._escapeHtml(title)}</div>
      </div>
      <div class="map3d-detail">
        <div class="map3d-canvas" id="m3d-canvas"></div>
        <div class="map3d-overlay">
          <span class="map3d-chip" id="m3d-time-chip">
            <ha-icon icon="mdi:clock-outline"></ha-icon><span id="m3d-time-text">--:--</span>
          </span>
          <span class="map3d-chip" id="m3d-sun-chip">
            <ha-icon icon="mdi:white-balance-sunny" id="m3d-sun-ico"></ha-icon><span id="m3d-sun-text">--</span>
          </span>
          <span class="map3d-chip map3d-rec-badge" id="m3d-rec-badge" style="display:none">
            <ha-icon icon="mdi:record"></ha-icon><span>${this._t("map3d_record_active")}</span>
          </span>
        </div>
        <div class="map3d-controls">
          <div class="row1">
            <button class="map3d-play-btn" type="button" id="m3d-play">
              <ha-icon icon="mdi:play" id="m3d-play-ico"></ha-icon>
            </button>
            <span class="map3d-time" id="m3d-t-start">--:--</span>
            <input type="range" class="map3d-slider" id="m3d-slider" min="0" max="100" step="0.01" value="0">
            <span class="map3d-time" id="m3d-t-end">--:--</span>
            <button class="map3d-rec-btn" type="button" id="m3d-rec" title="${this._t("map3d_record_start")}">
              <ha-icon icon="mdi:record-circle-outline" id="m3d-rec-ico"></ha-icon>
            </button>
          </div>
          <div class="map3d-stats">
            <span><span>${this._t("map3d_distance_label")}: </span><span class="v" id="m3d-stat-dist">–</span></span>
            <span><span>${this._t("map3d_speed_label")}: </span><span class="v" id="m3d-stat-speed">–</span></span>
            <span><span>${this._t("map3d_elevation_label")}: </span><span class="v" id="m3d-stat-ele">–</span></span>
          </div>
        </div>
      </div>
    `;

    this._root.querySelector(".map3d-back-btn").addEventListener("click", () => {
      this._stopAnim();
      this._destroyMap();
      this._mode = "list";
      this._currentActivity = null;
      this._currentTrack = null;
      this._renderRoot();
    });

    const slider = this._root.querySelector("#m3d-slider");
    slider.max = String(this._currentTrack.length - 1);
    slider.addEventListener("input", () => {
      this._stopAnim();
      this._applyIndex(Number(slider.value));
    });
    slider.addEventListener("change", () => {
      // Refresh shadows once the user releases the slider (sun has moved)
      this._updateShadows();
    });

    const playBtn = this._root.querySelector("#m3d-play");
    playBtn.addEventListener("click", () => this._togglePlay());

    const recBtn = this._root.querySelector("#m3d-rec");
    if (recBtn) {
      if (typeof MediaRecorder === "undefined" ||
          typeof HTMLCanvasElement.prototype.captureStream !== "function") {
        recBtn.disabled = true;
        recBtn.title = this._t("map3d_record_unsupported");
      } else {
        recBtn.addEventListener("click", () => this._toggleRecording());
      }
    }

    this._initMap();
  }

  async _initMap() {
    let mlib;
    try {
      mlib = await ensureMapLibre();
    } catch (e) {
      this._showMessage(this._t("map3d_err_maplibre"));
      return;
    }
    const a = this._currentActivity;
    const pts = this._currentTrack;
    const startTime = a.startTime ? new Date(a.startTime) : new Date();
    const meanLat = pts.reduce((s, p) => s + p.lat, 0) / pts.length;
    const meanLon = pts.reduce((s, p) => s + p.lon, 0) / pts.length;

    const sun = sunPositionAt(startTime, meanLat, meanLon);
    const altDeg = sun.altitude * 180 / Math.PI;
    const azDeg = ((sun.azimuth * 180 / Math.PI) + 180 + 360) % 360;
    const mood = sunMoodFor(altDeg);

    const canvas = this._root.querySelector("#m3d-canvas");
    // Chase-cam: pitch ~55° (looking forward over the bike) and zoom ~17
    // (about 100 m of road visible ahead). User can override via config.
    const chasePitch = Math.max(20, Math.min(65, Number(this._config.default_pitch) || 55));
    const chaseZoom = Math.max(14, Math.min(19, Number(this._config.chase_zoom) || 17));
    this._chasePitch = chasePitch;
    this._chaseZoom = chaseZoom;

    // Wait for layout to settle so the canvas has a real height. Without
    // this, MapLibre boots with a 0x0 WebGL viewport.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    void canvas.offsetHeight;

    // Initial pose: chase-cam look-target ~60 m AHEAD of the bike along
    // the smoothed bearing. That places the bike behind the camera focus,
    // so the rendered bike sits in the lower part of the screen and the
    // upcoming road fills the rest.
    const initialBearing = this._bearingAt(0);
    const lookAt = this._lookAheadCoord(pts[0], initialBearing, 60);
    this._currentIndex = 0;
    this._map = new mlib.Map({
      container: canvas,
      style: OPENFREEMAP_LIBERTY,
      center: lookAt,
      zoom: chaseZoom,
      pitch: chasePitch,
      bearing: initialBearing,
      attributionControl: false,
      // Generous cache so the chase cam does not re-fetch tiles when
      // the bike loops back through a visited area.
      maxTileCacheSize: 200,
      // Required for canvas.captureStream() / MediaRecorder so the
      // exported video gets real frames instead of empty squares.
      preserveDrawingBuffer: true,
    });
    this._map.addControl(new mlib.AttributionControl({ compact: true }), "bottom-right");
    this._map.addControl(new mlib.NavigationControl({ visualizePitch: true }), "top-right");

    // Keep the map sized to its container even if the parent resizes later.
    if (typeof ResizeObserver !== "undefined") {
      this._resizeObs = new ResizeObserver(() => {
        if (this._map) { try { this._map.resize(); } catch (_) {} }
      });
      this._resizeObs.observe(canvas);
    }

    this._map.on("error", (e) => {
      console.warn("[Bosch eBike 3D] map error", e && e.error);
    });

    this._map.on("load", () => {
      // Lighting & sky from sun mood
      try {
        this._map.setLight({
          anchor: "viewport",
          color: mood.sun,
          intensity: altDeg > 0 ? 0.6 : 0.15,
          position: [1.15, azDeg, Math.max(5, 90 - altDeg)],
        });
      } catch (_) { /* older MapLibre versions */ }

      // Polyline shows raw GPS, chase cam uses smoothed positions
      this._addTrackLayers(this._rawTrack || pts);
      this._addBuildingsIfNeeded();
      this._initShadowLayer();

      // Recompute shadows whenever the camera settles in a new spot
      // (new buildings come into view). queryRenderedFeatures only sees
      // currently-rendered tiles, so we wait for moveend.
      this._map.on("moveend", () => this._updateShadows());

      // Initial shadow pass: wait a beat so buildings have actually
      // rasterised, then compute. Repeat once more shortly after to
      // catch slow-loading building tiles.
      setTimeout(() => this._updateShadows(), 400);
      setTimeout(() => this._updateShadows(), 1500);

      // Start + end markers
      this._addPointMarker(pts[0], "#42c76a", "S");
      this._addPointMarker(pts[pts.length - 1], "#e53935", "Z");

      // Animated current-position marker (added LAST so it stacks above
      // the start/end dots when at index 0). Inline styles so it always
      // renders, even if the card-scoped CSS rule does not apply.
      const el = document.createElement("div");
      el.className = "ebike-3d-marker";
      el.style.cssText =
        "position:relative;width:22px;height:22px;border-radius:50%;" +
        "background:#03a9f4;border:4px solid #fff;" +
        "box-shadow:0 2px 8px rgba(0,0,0,.5);z-index:10;";
      this._marker = new mlib.Marker({ element: el, anchor: "center" })
        .setLngLat([pts[0].lon, pts[0].lat])
        .addTo(this._map);

      // Resize once after layers are added, then apply the chase-cam at
      // index 0. _applyIndex jumps the camera to the bike's position,
      // bearing-aligned with the direction of travel.
      try { this._map.resize(); } catch (_) {}

      this._applyIndex(0, true);
      this._updateTimeChips(0, startTime, altDeg, mood);
      this._updateRangeLabels();
    });
  }

  // Pre-compute a smoothed bearing for every track point. The chase-cam
  // then looks up the value instead of recomputing on every frame, which
  // both eliminates jitter and removes per-frame cost.
  //
  // Smoothing uses a sliding window of W points on each side and
  // averages bearings as unit vectors (cos, sin) so that the 0°/360°
  // wrap-around is handled correctly (averaging 350° and 10° yields 0°,
  // not 180°).
  _precomputeBearings() {
    const pts = this._currentTrack;
    if (!pts || pts.length < 2) {
      this._smoothedBearings = null;
      return;
    }
    // Raw bearings between consecutive points
    const raw = new Array(pts.length);
    for (let i = 0; i < pts.length - 1; i++) {
      raw[i] = this._calcBearing(pts[i], pts[i + 1]);
    }
    raw[pts.length - 1] = raw[pts.length - 2] != null ? raw[pts.length - 2] : 0;

    // Wider window = smoother camera but corners are taken wider.
    const W = Math.max(1, Math.min(60, Number(this._config.smooth_window) || 15));
    const smoothed = new Array(raw.length);
    const rad = Math.PI / 180;
    for (let i = 0; i < raw.length; i++) {
      const lo = Math.max(0, i - W);
      const hi = Math.min(raw.length - 1, i + W);
      let sx = 0, sy = 0;
      for (let j = lo; j <= hi; j++) {
        const a = raw[j] * rad;
        sx += Math.cos(a);
        sy += Math.sin(a);
      }
      smoothed[i] = (Math.atan2(sy, sx) * 180 / Math.PI + 360) % 360;
    }
    this._smoothedBearings = smoothed;
  }

  _bearingAt(i) {
    if (this._smoothedBearings) {
      const idx = Math.max(0, Math.min(this._smoothedBearings.length - 1, Math.round(i)));
      return this._smoothedBearings[idx];
    }
    return 0;
  }

  _calcBearing(a, b) {
    const rad = Math.PI / 180;
    const lat1 = a.lat * rad, lat2 = b.lat * rad;
    const dLon = (b.lon - a.lon) * rad;
    const y = Math.sin(dLon) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
    const brng = Math.atan2(y, x) * 180 / Math.PI;
    return (brng + 360) % 360;
  }

  // Coordinate `distanceMeters` ahead of `p` along compass `bearingDeg`.
  // Equirectangular approximation, accurate enough for chase-cam offsets
  // of a few dozen metres.
  _lookAheadCoord(p, bearingDeg, distanceMeters) {
    const bRad = bearingDeg * Math.PI / 180;
    const metersPerDegLat = 111320;
    const metersPerDegLon = 111320 * Math.cos(p.lat * Math.PI / 180);
    const dLat = (distanceMeters * Math.cos(bRad)) / metersPerDegLat;
    const dLon = (distanceMeters * Math.sin(bRad)) / Math.max(1, metersPerDegLon);
    return [p.lon + dLon, p.lat + dLat];
  }


  _addPointMarker(p, color, _label) {
    if (!this._map || !window.maplibregl) return;
    const el = document.createElement("div");
    el.style.cssText = `width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4);`;
    new window.maplibregl.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(this._map);
  }

  // Track polyline (glow + main stroke). Idempotent: removes existing
  // ebike layers/sources first so it can be safely called after a
  // style.setStyle() swap. Always uses the RAW GPS samples (not the
  // smoothed camera-path copy) so the line on the map matches what was
  // actually recorded.
  _addTrackLayers(pts) {
    if (!this._map) return;
    pts = pts || this._rawTrack || this._currentTrack;
    if (!pts || !pts.length) return;
    const coords = pts.map((p) => [p.lon, p.lat]);
    try { if (this._map.getLayer("ebike-track")) this._map.removeLayer("ebike-track"); } catch (_) {}
    try { if (this._map.getLayer("ebike-track-glow")) this._map.removeLayer("ebike-track-glow"); } catch (_) {}
    try { if (this._map.getSource("ebike-track")) this._map.removeSource("ebike-track"); } catch (_) {}
    this._map.addSource("ebike-track", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} },
    });
    this._map.addLayer({
      id: "ebike-track-glow",
      type: "line",
      source: "ebike-track",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#03a9f4", "line-width": 9, "line-opacity": 0.25, "line-blur": 3 },
    });
    this._map.addLayer({
      id: "ebike-track",
      type: "line",
      source: "ebike-track",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#03a9f4", "line-width": 4.5, "line-opacity": 0.95 },
    });
  }

  // Discover all style layers that visualise buildings, regardless of
  // the exact id used by the upstream OpenFreeMap / OpenMapTiles
  // variant. Used both to find the layer to insert shadows before, and
  // to know which layers to query for building features.
  _findBuildingLayers() {
    if (!this._map || !this._map.getStyle) return [];
    const style = this._map.getStyle();
    if (!style || !style.layers) return [];
    return style.layers
      .filter((l) =>
        (l["source-layer"] === "building") ||
        (typeof l.id === "string" &&
         (l.id === "building" || l.id.startsWith("building-") || l.id.includes("buildings"))))
      .map((l) => l.id);
  }

  // Empty shadow source + layer, populated by _updateShadows() once the
  // map has settled. Placed BEFORE the first building-related layer so
  // building extrusions render on top of their own shadows.
  _initShadowLayer() {
    if (!this._map) return;
    try {
      if (this._map.getSource("ebike-shadows")) return;
      this._map.addSource("ebike-shadows", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      const buildingLayers = this._findBuildingLayers();
      const beforeId = buildingLayers[0]; // may be undefined; that is fine
      this._map.addLayer({
        id: "ebike-shadows",
        type: "fill",
        source: "ebike-shadows",
        minzoom: 13,
        paint: {
          "fill-color": "#0a1018",
          "fill-opacity": 0.55,
          "fill-antialias": true,
        },
      }, beforeId);
      console.log("[Bosch eBike 3D] shadow layer ready. beforeId =", beforeId, "buildingLayers =", buildingLayers);
    } catch (e) {
      console.warn("[Bosch eBike 3D] shadow layer init failed", e);
    }
  }

  // Re-project all visible building footprints into ground-level cast
  // shadows for the sun position at the current slider index. Throttled
  // so a busy chase cam does not hammer it every frame.
  _updateShadows() {
    if (!this._map || !this._map.loaded()) return;
    const now = performance.now();
    if (this._shadowsThrottleUntil && now < this._shadowsThrottleUntil) {
      if (!this._shadowsPending) {
        this._shadowsPending = true;
        setTimeout(() => {
          this._shadowsPending = false;
          this._updateShadows();
        }, this._shadowsThrottleUntil - now);
      }
      return;
    }
    this._shadowsThrottleUntil = now + 500;

    const pts = this._currentTrack;
    if (!pts || !pts.length) return;
    const i = this._currentIndex != null ? this._currentIndex : 0;
    const p = pts[i];

    // Sun position at the slider's interpolated time
    const a = this._currentActivity;
    const dur = this._tourDurationSec(a);
    const startTime = a?.startTime ? new Date(a.startTime) : new Date();
    const t = new Date(startTime.getTime() + (i / Math.max(1, pts.length - 1)) * dur * 1000);
    const sun = sunPositionAt(t, p.lat, p.lon);

    const src = this._map.getSource("ebike-shadows");
    if (!src) return;
    if (sun.altitude <= 0) {
      // Below horizon: clear shadows
      src.setData({ type: "FeatureCollection", features: [] });
      return;
    }

    const layerIds = this._findBuildingLayers().filter((id) => this._map.getLayer(id));
    if (!layerIds.length) {
      console.warn("[Bosch eBike 3D] no building layers found in the active style; shadows skipped");
      src.setData({ type: "FeatureCollection", features: [] });
      return;
    }

    let buildings = [];
    try {
      buildings = this._map.queryRenderedFeatures(undefined, { layers: layerIds });
    } catch (e) {
      console.warn("[Bosch eBike 3D] queryRenderedFeatures failed", e);
    }

    const features = [];
    const seen = new Set();
    let skippedHeight = 0;
    let skippedGeom = 0;
    for (const b of buildings) {
      // Dedupe across tile boundaries
      const key = b.id != null ? `i:${b.id}` :
        `g:${b.geometry?.coordinates?.[0]?.[0]?.join(",")}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const props = b.properties || {};
      // OpenMapTiles uses 'render_height'; some vector schemas use 'height',
      // 'min_height' is the building base. Fall back to a 6 m default so
      // small buildings without an explicit height still cast a shadow.
      let h = Number(props.render_height);
      if (!Number.isFinite(h) || h <= 0) h = Number(props.height);
      if (!Number.isFinite(h) || h <= 0) {
        const levels = Number(props["building:levels"] || props.levels);
        if (Number.isFinite(levels) && levels > 0) h = levels * 3;
      }
      if (!Number.isFinite(h) || h <= 0) h = 6;
      if (h < 1) { skippedHeight++; continue; }

      const rings = b.geometry?.type === "Polygon"
        ? [b.geometry.coordinates[0]]
        : b.geometry?.type === "MultiPolygon"
          ? b.geometry.coordinates.map((poly) => poly[0])
          : null;
      if (!rings) { skippedGeom++; continue; }

      for (const ring of rings) {
        const shadow = buildingShadowRing(ring, h, sun.altitude, sun.azimuth, p.lat);
        if (shadow) {
          features.push({
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [shadow] },
            properties: {},
          });
        }
      }
    }
    if (!this._shadowDiagLogged) {
      this._shadowDiagLogged = true;
      console.log("[Bosch eBike 3D] shadow diagnostic:", {
        layerIds,
        rawBuildings: buildings.length,
        uniqueBuildings: seen.size,
        skippedHeight,
        skippedGeom,
        shadowFeatures: features.length,
        sunAltDeg: (sun.altitude * 180 / Math.PI).toFixed(1),
        sampleProps: buildings[0]?.properties,
        sampleGeomType: buildings[0]?.geometry?.type,
      });
    }
    src.setData({ type: "FeatureCollection", features });
  }

  // Add a 3D building-extrusion fallback layer if the active style does
  // not already provide one. Most Liberty style variants ship a building
  // layer, but a few revisions disable it; this guarantees extrusion.
  _addBuildingsIfNeeded() {
    if (!this._map) return;
    if (this._map.getLayer("building-3d") || this._map.getLayer("building") || this._map.getLayer("ebike-buildings-3d")) {
      return;
    }
    try {
      this._map.addLayer({
        id: "ebike-buildings-3d",
        type: "fill-extrusion",
        source: "openmaptiles",
        "source-layer": "building",
        minzoom: 14,
        paint: {
          "fill-extrusion-color": ["case", ["has", "colour"], ["get", "colour"], "#c9c4be"],
          "fill-extrusion-height": ["coalesce", ["get", "render_height"], ["get", "height"], 6],
          "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
          "fill-extrusion-opacity": 0.85,
        },
      });
    } catch (_) { /* style without openmaptiles source */ }
  }


  // Linearly interpolate two values, treating non-finite operands gracefully.
  _lerpFinite(a, b, f) {
    const af = Number.isFinite(a), bf = Number.isFinite(b);
    if (af && bf) return a + (b - a) * f;
    if (af) return a;
    if (bf) return b;
    return NaN;
  }

  // Shortest-arc circular interpolation of two compass bearings in degrees.
  _lerpBearing(a, b, f) {
    const diff = (((b - a + 540) % 360) - 180);
    return ((a + diff * f) + 360) % 360;
  }

  // Fractional version of _bearingAt: looks up two adjacent smoothed
  // bearings and shortest-arc-interpolates between them. The chase cam
  // then turns smoothly across the gap between two GPS samples instead
  // of snapping at each integer index.
  _bearingAtFractional(idx) {
    const arr = this._smoothedBearings;
    if (!arr || !arr.length) return 0;
    const N = arr.length - 1;
    const c = Math.max(0, Math.min(N, idx));
    const i0 = Math.floor(c);
    const i1 = Math.min(N, i0 + 1);
    const f = c - i0;
    return this._lerpBearing(arr[i0], arr[i1], f);
  }

  _applyIndex(idx, isInitial) {
    const pts = this._currentTrack;
    if (!pts || !pts.length) return;
    const clamped = Math.max(0, Math.min(pts.length - 1, idx));
    const i0 = Math.floor(clamped);
    const i1 = Math.min(pts.length - 1, i0 + 1);
    const f = clamped - i0;
    const a0 = pts[i0];
    const a1 = pts[i1];
    // Interpolated current bike state. All downstream visual updates
    // (marker, camera, stats, sun) use this fractional position so the
    // chase cam glides between GPS samples instead of jumping every
    // time the rounded index increments.
    const p = {
      lat: a0.lat + (a1.lat - a0.lat) * f,
      lon: a0.lon + (a1.lon - a0.lon) * f,
      ele: this._lerpFinite(a0.ele, a1.ele, f),
      speed: this._lerpFinite(a0.speed, a1.speed, f),
    };
    this._currentIndex = i0;       // for shadow snapping (integer-anchored)
    this._currentFracIndex = clamped;

    if (this._marker) this._marker.setLngLat([p.lon, p.lat]);

    // Chase-cam: look-target sits ~60 m ahead of the bike along the
    // smoothed (and now also fractionally interpolated) bearing.
    if (this._map && this._map.loaded()) {
      try {
        const bearing = this._bearingAtFractional(clamped);
        const lookAt = this._lookAheadCoord(p, bearing, 60);
        const camera = {
          center: lookAt,
          zoom: this._chaseZoom != null ? this._chaseZoom : 17,
          pitch: this._chasePitch != null ? this._chasePitch : 55,
          bearing,
        };
        if (isInitial) {
          this._map.easeTo({ ...camera, duration: 900 });
        } else {
          this._map.jumpTo(camera);
        }
      } catch (e) { console.warn("[Bosch eBike 3D] chase-cam update failed", e); }
    }

    // Per-frame interpolated tour time
    const a = this._currentActivity;
    const dur = this._tourDurationSec(a);
    const startTime = a?.startTime ? new Date(a.startTime) : new Date();
    const t = new Date(startTime.getTime() + (clamped / Math.max(1, pts.length - 1)) * dur * 1000);
    const sun = sunPositionAt(t, p.lat, p.lon);
    const altDeg = sun.altitude * 180 / Math.PI;
    const mood = sunMoodFor(altDeg);
    this._updateTimeChips(clamped, t, altDeg, mood);

    if (this._map && this._map.loaded()) {
      try {
        const azDeg = ((sun.azimuth * 180 / Math.PI) + 180 + 360) % 360;
        this._map.setLight({
          anchor: "viewport",
          color: mood.sun,
          intensity: altDeg > 0 ? 0.6 : 0.15,
          position: [1.15, azDeg, Math.max(5, 90 - altDeg)],
        });
      } catch (_) { /* ignore */ }
    }

    // Stats: also interpolated. Distance uses the cumulative array.
    const cum = this._cumDist;
    const dist = cum ? this._lerpFinite(cum[i0], cum[i1], f) : 0;
    const distLbl = Number.isFinite(dist)
      ? (dist / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km"
      : "–";
    this._root.querySelector("#m3d-stat-dist").textContent = distLbl;
    const sp = Number.isFinite(p.speed) ? p.speed : null;
    this._root.querySelector("#m3d-stat-speed").textContent =
      sp != null ? sp.toLocaleString(undefined, { maximumFractionDigits: 1 }) + " km/h" : "–";
    const ele = Number.isFinite(p.ele) ? p.ele : null;
    this._root.querySelector("#m3d-stat-ele").textContent =
      ele != null ? Math.round(ele) + " m" : "–";

    const slider = this._root.querySelector("#m3d-slider");
    if (slider && document.activeElement !== slider) {
      slider.value = String(clamped);
    }
  }

  _updateTimeChips(_i, time, altDeg, mood) {
    const fmtHm = (d) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    const tt = this._root.querySelector("#m3d-time-text");
    if (tt) tt.textContent = fmtHm(time);
    const st = this._root.querySelector("#m3d-sun-text");
    if (st) {
      // Word label, not a degree value: degree symbol on a sun-themed chip
      // was being mistaken for a temperature reading.
      const key = "map3d_sun_" + (mood?.label || "day");
      st.textContent = this._t(key);
    }
    const sico = this._root.querySelector("#m3d-sun-ico");
    if (sico) {
      sico.setAttribute("icon",
        altDeg < -6 ? "mdi:weather-night" :
        altDeg < 0  ? "mdi:weather-sunset" :
        altDeg < 10 ? "mdi:weather-sunset-up" :
                      "mdi:white-balance-sunny");
      sico.style.color = mood.sun;
    }
  }

  _updateRangeLabels() {
    const a = this._currentActivity;
    const dur = this._tourDurationSec(a);
    const start = a?.startTime ? new Date(a.startTime) : new Date();
    const end = new Date(start.getTime() + dur * 1000);
    const fmt = (d) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    const s = this._root.querySelector("#m3d-t-start");
    const e = this._root.querySelector("#m3d-t-end");
    if (s) s.textContent = fmt(start);
    if (e) e.textContent = fmt(end);
  }

  _togglePlay() {
    if (this._isPlaying) this._stopAnim();
    else this._startAnim();
  }

  // Total playback duration in milliseconds. Two modes:
  //   1. If the user set `animate_seconds` explicitly, that wins and the
  //      whole tour plays in that fixed duration regardless of length.
  //   2. Otherwise the tour plays at `playback_speed` × real-time. 60×
  //      means 1 h of riding becomes 1 min of playback. Clamped to
  //      [2 s, 10 min] so absurd configs do not produce unusable values.
  _playbackDurationMs() {
    const cfg = this._config || {};
    if (cfg.animate_seconds != null && cfg.animate_seconds !== "" &&
        Number.isFinite(Number(cfg.animate_seconds))) {
      const fixed = Math.max(2, Number(cfg.animate_seconds));
      return fixed * 1000;
    }
    const factor = Math.max(1, Number(cfg.playback_speed) || 60);
    const tourSec = this._tourDurationSec(this._currentActivity);
    const ms = tourSec > 0 ? (tourSec * 1000) / factor : 25000;
    return Math.max(2000, Math.min(600000, ms));
  }

  _startAnim() {
    if (!this._currentTrack || !this._currentTrack.length) return;
    this._isPlaying = true;
    const icon = this._root.querySelector("#m3d-play-ico");
    if (icon) icon.setAttribute("icon", "mdi:pause");
    // moveend does not fire during continuous chase-cam playback, so we
    // also refresh shadows on a slow interval. 800 ms is fast enough to
    // catch sun-angle changes during a play-through, slow enough not to
    // hurt frame rate.
    if (this._shadowPlayInterval) clearInterval(this._shadowPlayInterval);
    this._shadowPlayInterval = setInterval(() => this._updateShadows(), 800);
    const slider = this._root.querySelector("#m3d-slider");
    const startIdx = Number(slider.value) || 0;
    const totalIdx = this._currentTrack.length - 1;
    const wrapAt = startIdx >= totalIdx ? 0 : startIdx;
    this._animStartIndex = wrapAt;
    this._animStartTs = performance.now();
    const fullDurMs = this._playbackDurationMs();
    // If the user pressed Play partway through, only the remaining
    // fraction should be replayed in proportion to that.
    const remainingFrac = totalIdx > 0 ? (totalIdx - wrapAt) / totalIdx : 1;
    const dur = Math.max(500, fullDurMs * remainingFrac);
    const step = (ts) => {
      if (!this._isPlaying) return;
      const elapsed = ts - this._animStartTs;
      const frac = Math.min(1, elapsed / dur);
      const idx = wrapAt + (totalIdx - wrapAt) * frac;
      this._applyIndex(idx);
      if (frac >= 1) { this._stopAnim(); return; }
      this._animRAF = requestAnimationFrame(step);
    };
    this._animRAF = requestAnimationFrame(step);
  }

  _stopAnim() {
    this._isPlaying = false;
    if (this._animRAF) cancelAnimationFrame(this._animRAF);
    this._animRAF = null;
    if (this._shadowPlayInterval) {
      clearInterval(this._shadowPlayInterval);
      this._shadowPlayInterval = null;
    }
    const icon = this._root.querySelector("#m3d-play-ico");
    if (icon) icon.setAttribute("icon", "mdi:play");
    // One final shadow refresh now that the bike has stopped
    this._updateShadows();
    // If a recording session was tied to this play-through, finish it
    if (this._isRecording) this._stopRecording();
  }

  // Toggle recording. The exported file is a WebM video of exactly the
  // canvas content during a single play-through, no audio. Renders in
  // the user's browser via MediaRecorder + canvas.captureStream(); HA
  // server is not involved.
  _toggleRecording() {
    if (this._isRecording) this._stopRecording();
    else this._startRecording();
  }

  _startRecording() {
    if (this._isRecording) return;
    if (!this._map) return;
    const canvas = this._map.getCanvas();
    if (!canvas || typeof canvas.captureStream !== "function") {
      console.warn("[Bosch eBike 3D] canvas.captureStream not available");
      return;
    }

    // Pick the best mime type the browser actually supports. MP4 is
    // preferred because it plays everywhere out of the box (QuickTime,
    // Windows Media Player, mobile Photos apps). It is only exposed by
    // MediaRecorder in newer Chromium (Chrome 126+) and Safari 14.4+;
    // Firefox does not expose MP4 at all. WebM is the universal fallback.
    const mimeCandidates = [
      "video/mp4;codecs=avc1.42E01E,mp4a.40.2",  // H.264 baseline + AAC
      "video/mp4;codecs=avc1",                    // generic H.264 in mp4
      "video/mp4",                                // any mp4 the browser likes
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ];
    let mimeType = "";
    for (const m of mimeCandidates) {
      if (MediaRecorder.isTypeSupported(m)) { mimeType = m; break; }
    }

    let stream;
    try {
      stream = canvas.captureStream(30);
    } catch (e) {
      console.warn("[Bosch eBike 3D] captureStream failed", e);
      return;
    }

    this._recChunks = [];
    try {
      this._mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 4_000_000 })
        : new MediaRecorder(stream);
    } catch (e) {
      console.warn("[Bosch eBike 3D] MediaRecorder construction failed", e);
      return;
    }

    this._mediaRecorder.ondataavailable = (ev) => {
      if (ev.data && ev.data.size > 0) this._recChunks.push(ev.data);
    };
    this._mediaRecorder.onstop = () => this._finalizeRecording(mimeType);
    this._mediaRecorder.onerror = (e) => {
      console.warn("[Bosch eBike 3D] MediaRecorder error", e);
    };

    try {
      this._mediaRecorder.start(1000);  // chunk every 1 s
    } catch (e) {
      console.warn("[Bosch eBike 3D] MediaRecorder start failed", e);
      this._mediaRecorder = null;
      return;
    }

    this._isRecording = true;
    this._updateRecordUI(true);

    // Reset to start and play through the whole tour so the recording
    // covers the full visual sequence. _stopAnim() at the end will
    // automatically stop the recording too.
    this._stopAnim();
    const slider = this._root.querySelector("#m3d-slider");
    if (slider) slider.value = "0";
    this._applyIndex(0);
    this._startAnim();
  }

  _stopRecording() {
    if (!this._isRecording) return;
    this._isRecording = false;
    this._updateRecordUI(false);
    try {
      if (this._mediaRecorder && this._mediaRecorder.state !== "inactive") {
        this._mediaRecorder.stop();
      }
    } catch (e) {
      console.warn("[Bosch eBike 3D] MediaRecorder stop failed", e);
    }
  }

  _finalizeRecording(mimeType) {
    const chunks = this._recChunks || [];
    this._recChunks = null;
    this._mediaRecorder = null;
    if (!chunks.length) return;
    const blobType = mimeType || "video/webm";
    const blob = new Blob(chunks, { type: blobType });

    // Pick the file extension from the chosen mime so QuickTime,
    // Windows Photos etc. open it as expected. MP4 wins where the
    // browser supports it, WebM is the fallback.
    const ext = blobType.startsWith("video/mp4") ? "mp4"
              : blobType.startsWith("video/x-matroska") ? "mkv"
              : "webm";

    // Build a filename from tour date + title where possible
    const a = this._currentActivity || {};
    const dateStr = a.startTime
      ? new Date(a.startTime).toISOString().slice(0, 19).replace(/[:T]/g, "-")
      : "tour";
    const safeTitle = (a.title || "ebike-tour")
      .toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
    const filename = `${safeTitle || "ebike-tour"}-${dateStr}.${ext}`;

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  _updateRecordUI(active) {
    const btn = this._root.querySelector("#m3d-rec");
    const ico = this._root.querySelector("#m3d-rec-ico");
    const badge = this._root.querySelector("#m3d-rec-badge");
    if (btn) btn.classList.toggle("active", active);
    if (ico) ico.setAttribute("icon", active ? "mdi:stop" : "mdi:record-circle-outline");
    if (btn) btn.title = active ? this._t("map3d_record_stop") : this._t("map3d_record_start");
    if (badge) badge.style.display = active ? "inline-flex" : "none";
  }

  _destroyMap() {
    this._stopAnim();
    if (this._isRecording) this._stopRecording();
    if (this._resizeObs) { try { this._resizeObs.disconnect(); } catch (_) {} this._resizeObs = null; }
    if (this._marker) { try { this._marker.remove(); } catch (_) {} this._marker = null; }
    if (this._map) { try { this._map.remove(); } catch (_) {} this._map = null; }
  }
}

class BoschEBike3DMapCardEditor extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._built = false;
  }
  setConfig(config) { this._config = { ...config }; if (this._built) this._sync(); }
  set hass(hass) { this._hass = hass; if (!this._built) this._build(); }
  _t(key) {
    const lang = (this._hass && this._hass.language) ? this._hass.language.split("-")[0] : "en";
    const dict = (I18N && I18N[lang]) || I18N.en;
    return dict[key] != null ? dict[key] : I18N.en[key];
  }
  _emit() { this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } })); }
  _build() {
    this.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;flex-direction:column;gap:12px;padding:12px;";
    this.appendChild(wrap);

    const mkLabeled = (labelKey, hintKey, makeInput) => {
      const block = document.createElement("div");
      block.style.cssText = "display:flex;flex-direction:column;gap:4px;";
      const lbl = document.createElement("label");
      lbl.textContent = this._t(labelKey);
      lbl.style.fontWeight = "500";
      block.appendChild(lbl);
      const input = makeInput();
      block.appendChild(input);
      if (hintKey) {
        const h = document.createElement("small");
        h.textContent = this._t(hintKey);
        h.style.cssText = "color:var(--secondary-text-color);font-size:11px;";
        block.appendChild(h);
      }
      wrap.appendChild(block);
      return input;
    };

    const mkText = (key, labelKey, hintKey, type) => {
      const i = mkLabeled(labelKey, hintKey, () => {
        const el = document.createElement("input");
        el.type = type || "text";
        el.style.cssText = "padding:8px;border-radius:4px;border:1px solid var(--divider-color);background:var(--card-background-color);color:var(--primary-text-color);";
        return el;
      });
      i.value = this._config[key] != null ? this._config[key] : "";
      i.addEventListener("input", () => {
        const v = i.value;
        if (v === "" || v == null) delete this._config[key];
        else if (i.type === "number") this._config[key] = Number(v);
        else this._config[key] = v;
        this._emit();
      });
      return i;
    };

    this._fields = {
      title: mkText("title", "map3d_editor_title", null, "text"),
      height: mkText("height", "map3d_editor_height", null, "number"),
      default_pitch: mkText("default_pitch", "map3d_editor_default_pitch", "map3d_editor_default_pitch_hint", "number"),
      chase_zoom: mkText("chase_zoom", "map3d_editor_chase_zoom", "map3d_editor_chase_zoom_hint", "number"),
      smooth_window: mkText("smooth_window", "map3d_editor_smooth_window", "map3d_editor_smooth_window_hint", "number"),
      track_smooth_window: mkText("track_smooth_window", "map3d_editor_track_smooth", "map3d_editor_track_smooth_hint", "number"),
      playback_speed: mkText("playback_speed", "map3d_editor_playback_speed", "map3d_editor_playback_speed_hint", "number"),
      animate_seconds: mkText("animate_seconds", "map3d_editor_animate_seconds", "map3d_editor_animate_seconds_override_hint", "number"),
      account_id: mkText("account_id", "map3d_editor_account", null, "text"),
      bike_id: mkText("bike_id", "map3d_editor_bike", null, "text"),
    };
    this._built = true;
  }
  _sync() {
    if (!this._fields) return;
    for (const [k, el] of Object.entries(this._fields)) {
      el.value = this._config[k] != null ? this._config[k] : "";
    }
  }
}

if (!customElements.get("bosch-ebike-map-card")) {
  customElements.define("bosch-ebike-map-card", BoschEBikeMapCard);
}
if (!customElements.get("bosch-ebike-map-card-editor")) {
  customElements.define("bosch-ebike-map-card-editor", BoschEBikeMapCardEditor);
}
if (!customElements.get("bosch-ebike-heatmap-card")) {
  customElements.define("bosch-ebike-heatmap-card", BoschEBikeHeatmapCard);
}
if (!customElements.get("bosch-ebike-heatmap-card-editor")) {
  customElements.define("bosch-ebike-heatmap-card-editor", BoschEBikeHeatmapCardEditor);
}
if (!customElements.get("bosch-ebike-calendar-card")) {
  customElements.define("bosch-ebike-calendar-card", BoschEBikeCalendarCard);
}
if (!customElements.get("bosch-ebike-calendar-card-editor")) {
  customElements.define("bosch-ebike-calendar-card-editor", BoschEBikeCalendarCardEditor);
}
if (!customElements.get("bosch-ebike-dashboard-card")) {
  customElements.define("bosch-ebike-dashboard-card", BoschEBikeDashboardCard);
}
if (!customElements.get("bosch-ebike-dashboard-card-editor")) {
  customElements.define("bosch-ebike-dashboard-card-editor", BoschEBikeDashboardCardEditor);
}
if (!customElements.get("bosch-ebike-3d-map-card")) {
  customElements.define("bosch-ebike-3d-map-card", BoschEBike3DMapCard);
}
if (!customElements.get("bosch-ebike-3d-map-card-editor")) {
  customElements.define("bosch-ebike-3d-map-card-editor", BoschEBike3DMapCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === "bosch-ebike-map-card")) {
  window.customCards.push({
    type: "bosch-ebike-map-card",
    name: "Bosch eBike Map",
    description: "Interaktive Karte mit GPS-Tracks deiner Bosch eBike-Fahrten",
    preview: true,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-heatmap-card")) {
  window.customCards.push({
    type: "bosch-ebike-heatmap-card",
    name: "Bosch eBike Heatmap",
    description: "Alle Touren einer Auswahl auf einer Karte überlagert",
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-calendar-card")) {
  window.customCards.push({
    type: "bosch-ebike-calendar-card",
    name: "Bosch eBike Calendar",
    description: "Kalender-Heatmap der Fahrtage (GitHub-Contributions-Stil)",
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-dashboard-card")) {
  window.customCards.push({
    type: "bosch-ebike-dashboard-card",
    name: "Bosch eBike Dashboard",
    description: "Bike-Bild, Live-Daten und optional Ladesteuerung (für ESPHome-Bridge + Smart-Plug)",
    preview: false,
  });
}
if (!window.customCards.find((c) => c.type === "bosch-ebike-3d-map-card")) {
  window.customCards.push({
    type: "bosch-ebike-3d-map-card",
    name: "Bosch eBike 3D-Karte",
    description: "Tour-Detailansicht in 3D mit Gebäude-Extrusionen, Zeit-Slider und Sonnenstand-Lichteffekt (MapLibre + OpenFreeMap)",
    preview: false,
  });
}
