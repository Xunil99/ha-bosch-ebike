# Bosch eBike Smart System – Integración para Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

> [Deutsch](README.md) | [English](README.md#english) | [Nederlands](README.nl.md) | [Français](README.fr.md) | [Italiano](README.it.md) | **Español**

> ### ⚠️ Requisito regional
> Esta integración funciona **exclusivamente con una cuenta Bosch SingleKey-ID registrada dentro de la UE**. Utiliza la API oficial Bosch Data Act, cuya disponibilidad está limitada a cuentas de la UE. Las cuentas de otras regiones son rechazadas por el endpoint de la API y la integración no puede iniciar sesión.

> ### 🔌 Datos reales en vivo por Bluetooth (smart system v19+)
> Además de la integración HACS, este repositorio contiene un **puente BLE para ESPHome** que convierte un ESP32 en una pasarela hacia el **Bosch eBike Live Data Interface**. Con él, el SoC de la batería, la velocidad, el cuentakilómetros y demás fluyen en tiempo real hacia Home Assistant.
>
> 🚀 **Flashear sin instalar ESPHome**: conecta un ESP32 (o ESP32-C3, p. ej. "C3 Mini") por USB, abre en Chrome / Edge **[https://xunil99.github.io/ha-bosch-ebike/](https://xunil99.github.io/ha-bosch-ebike/)** y pulsa *Install*. El instalador detecta el chip automáticamente y flashea el firmware adecuado. La configuración WiFi se realiza en el mismo paso del navegador. Guía completa (DE/EN) incl. emparejamiento mediante la app Flow: [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome).

> ### 🖥️ Opcional: pantalla de 4,3" para fecha, tiempo meteorológico y datos en vivo
> Además del puente, ahora hay un segundo firmware para el **Guition/Sunton JC4827W543** (ESP32-S3 con pantalla táctil IPS de 4,3"). Lee los sensores del puente desde Home Assistant y muestra la fecha, la hora, el tiempo meteorológico y hasta dos eBikes en paralelo. Los usuarios actuales del puente no tienen que cambiar nada; la pantalla es puramente aditiva. Guía de instalación: [`esphome/DISPLAY.md`](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/DISPLAY.md).

---

## Español

### Descripción

Esta integración personalizada conecta tu **Bosch eBike Smart System** con Home Assistant. Lee los datos de la bicicleta (kilometraje, horas de motor, ciclos de carga de la batería) y los datos de actividad (último trayecto, velocidad, cadencia, potencia) directamente desde la API oficial Bosch Data Act.

**Solo se admiten eBikes con Bosch Smart System** (no el sistema Classic Line).

### Funciones

- **Datos de la bicicleta:** kilometraje, horas de motor (totales y con asistencia), velocidad máxima de asistencia, modos de asistencia activos, velocidad del asistente de empuje, kilometraje del próximo mantenimiento
- **Datos de la batería:** Wh suministrados durante la vida útil, ciclos de carga (totales, en la bici, externos)
- **Último trayecto:** distancia, duración, velocidad media/máxima, cadencia (media/máx.), potencia del ciclista en vatios (media/máx.), calorías consumidas, desnivel (ascenso/descenso), título, fecha
- **Estadísticas totales:** número total de trayectos, distancia total, tiempo total de conducción, calorías totales, desnivel total, valores medios de velocidad/potencia/cadencia de todos los trayectos
- **Exportación de tracks GPS:** exportación de todos los trayectos como archivos GPX (con velocidad, cadencia y potencia como Garmin TrackPointExtension)
- **Vista de mapa interactiva:** tarjeta Lovelace personalizada con tracks GPS, codificación de colores según la velocidad, selector de fecha y navegación prev/next
- **Mapa 3D con chase-cam, control deslizante de tiempo y sombras de edificios:** tarjeta Lovelace personalizada (`bosch-ebike-3d-map-card`) para la vista de detalle del recorrido con edificios en 3D, una cámara que sigue a la bici desde atrás, velocidad de reproducción proporcional (por defecto 60× tiempo real) y sombras proyectadas según la posición del sol a la hora del recorrido (MapLibre + OpenFreeMap, gratuito y sin clave de API)
- **Tarjeta de dashboard con foto de la bici, datos en vivo y control de carga:** tarjeta Lovelace personalizada (`bosch-ebike-dashboard-card`) con foto propia de la bici, kilometraje, nivel de batería, estado de carga, sensor opcional de potencia de carga, control deslizante de SoC objetivo y botones de inicio/parada mediante un enchufe inteligente
- **Renovación automática del token** mediante refresh-token
- **Intervalo de sondeo de 30 minutos** (en el primer arranque se importan todos los trayectos)

### 🆕 Datos en vivo por Bluetooth (puente ESPHome)

Además de la integración en la nube, en la subcarpeta [`esphome/`](https://github.com/Xunil99/ha-bosch-ebike/tree/main/esphome) encontrarás un **componente externo de ESPHome** que convierte un ESP32 en una pasarela hacia el **Bosch eBike Live Data Interface (LDI)** (BLE, smart system v19+). Con él, los valores en tiempo real (velocidad, SoC de la batería, cadencia, potencia del ciclista, kilometraje, estado de las luces, estado del bloqueo, …) llegan a HA como sensores ESPHome, como complemento del historial de recorridos basado en la nube.

🚀 **El camino más rápido sin conocimientos de ESPHome**: conecta el ESP32, abre en Chrome / Edge **https://xunil99.github.io/ha-bosch-ebike/** y pulsa *Install*. El flasheo del firmware y la configuración WiFi se realizan completamente en el navegador; no es necesario instalar ESPHome.

Guía completa: **[esphome/README.md](https://github.com/Xunil99/ha-bosch-ebike/blob/main/esphome/README.md)**

> **Proyectos relacionados:** ¿No tienes un ESP32 a mano, pero sí una Raspberry Pi? [ha-bosch-ebike-pibridge](https://github.com/possm/ha-bosch-ebike-pibridge) de [@possm](https://github.com/possm) es una adaptación de la comunidad en Python (BlueZ + MQTT) que se ejecuta directamente en la Pi, admite **dos bicis a la vez** e incluye su propio dashboard web.

#### Usar valores en vivo para el cálculo exacto de los recorridos (opcional, desde v1.10.0)

Cuando el puente está en marcha, puedes configurar dos sensores en los **ajustes de la integración** (HA → *Ajustes → Dispositivos y servicios → Bosch eBike → Configurar*):

- **Sensor de kilometraje en vivo** (p. ej. `sensor.ebike_odometer_live`)
- **Sensor de nivel de batería en vivo** (p. ej. `sensor.ebike_battery_soc_live`)

Si están configurados, en cada actualización de recorrido la integración consulta al recorder de HA el valor de estos sensores al inicio y al final del recorrido. De las diferencias se obtiene:

- **Distancia exacta del recorrido** (diferencia de kilometraje en lugar del cálculo GPS de la nube).
- **Consumo exacto de batería en Wh** ((SoC inicial − SoC final) × capacidad de la batería / 100).

Estos valores sustituyen la estimación por instantánea anterior en los sensores *Last Ride Distance*, *Battery Consumption Wh*, *consumo %*, etc. Si al inicio o al final del recorrido no había ninguna muestra BLE disponible dentro de la ventana de tolerancia (±5 min) (bici fuera de alcance), la integración recurre de forma transparente a la antigua lógica de la nube. Ambos campos son opcionales e independientes: también puedes configurar solo uno de ellos.

### Requisitos

1. Una eBike con **Bosch Smart System** (p. ej. Performance Line CX, SX, etc.)
2. Una cuenta **Bosch SingleKey ID** ([singlekey-id.com](https://singlekey-id.com))
3. Acceso al **portal Bosch eBike Flow** ([portal.bosch-ebike.com](https://portal.bosch-ebike.com))

---

### Guía paso a paso

#### Requisitos

1. Una cuenta **Bosch SingleKey ID**: si aún no tienes una, créala en [singlekey-id.com](https://singlekey-id.com)
2. Tu eBike debe estar vinculada a la **app Bosch eBike Flow** ([iOS](https://apps.apple.com/app/bosch-ebike-flow/id1504451498) / [Android](https://play.google.com/store/apps/details?id=com.bosch.ebike))

---

#### Paso 1: registrar la app en el portal Bosch Data Act (¡hazlo primero!)

Este es el paso más importante. Debes crear una "app" en el portal de Bosch para obtener un **Client-ID**.

1. Ve a [portal.bosch-ebike.com/data-act/app](https://portal.bosch-ebike.com/data-act/app)
2. Inicia sesión con tu SingleKey ID
3. Haz clic en **"Create App"** (crear app)
4. Rellena el formulario:
   - **Nombre de la app:** p. ej. `Home Assistant`
   - **Redirect URI:** `https://my.home-assistant.io/redirect/oauth`
   - **Login URL:** cualquiera (puramente informativa), p. ej. `https://github.com/Xunil99/ha-bosch-ebike`
   - **Confidential client:** dejar **DESACTIVADO** (Home Assistant usa un cliente público con PKCE, sin secret)

   > **Importante:** La **Redirect URI** debe ser exactamente `https://my.home-assistant.io/redirect/oauth`: es la redirección oficial de "My Home Assistant" con la que Home Assistant completa el inicio de sesión automáticamente. La integración "My Home Assistant" debe estar activada en HA (lo está por defecto). Si la has desactivado, registra en su lugar `https://<tu-URL-de-HA>/auth/external/callback`.

5. Tras crearla, recibirás un **Client-ID** (con el formato `euda-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

#### Paso 2: guardar el Client-ID

Copia el **Client-ID** que acabas de crear: lo necesitarás en seguida en Home Assistant.

> **Nota:** Todavía tienes que **activar** el Client-ID en el portal Flow (paso 5) antes de que funcione el inicio de sesión. Sin la activación, Bosch rechaza el inicio de sesión con "cliente no encontrado".

---

#### Paso 3: configurar la integración en Home Assistant

1. Instala la integración (mediante HACS o manualmente; ver más abajo) y reinicia Home Assistant
2. Ve a **Ajustes → Dispositivos y servicios → Añadir integración**
3. Busca **"Bosch eBike"**
4. Introduce tu **Client-ID** y haz clic en **Enviar**
5. Haz clic en **Autorizar**: serás redirigido al **inicio de sesión de Bosch**
6. Inicia sesión con tu **SingleKey ID** y confirma la autorización
7. Volverás **automáticamente** a Home Assistant: **ya no hay que copiar códigos**. La integración está configurada.

> **Sin localhost, sin copiar y pegar:** Desde el cambio a OAuth, Home Assistant gestiona por sí mismo todo el retorno del inicio de sesión (mediante la redirección de "My Home Assistant"). Después, la integración renueva automáticamente los tokens de acceso y de actualización.

#### Paso 4: comprobar el resultado

La integración debería estar configurada ahora, pero **¡todavía sin entidades!** Es normal. Continúa con el paso 5.

---

#### Paso 5: activar la compartición de datos

¡Sin la compartición de datos, la API devuelve un resultado vacío!

1. Ve a **[flow.bosch-ebike.com](https://flow.bosch-ebike.com)**
2. Inicia sesión con tu **SingleKey ID**
3. Selecciona **"Data Act"** en el menú superior
4. Busca la entrada **"Home Assistant"** y **actívala**

¡Ahora deberías ver en la página correspondiente de la API de Bosch la opción de activar el Client-ID!

#### Paso 6: recargar la integración

Después de activar el Client-ID en el portal Flow:

1. Vuelve a **Home Assistant → Ajustes → Dispositivos y servicios**
2. Busca la integración **Bosch eBike**
3. Haz clic en **⋮ (tres puntos)** → **Recargar**

La integración debería actualizarse ahora con **todas las entidades disponibles** (datos de la bici, batería, último trayecto, estadísticas totales).

#### 6. Configurar la vista de mapa (opcional)

La integración incluye una tarjeta Lovelace interactiva para mostrar tus tracks GPS.

**Paso A: registrar el recurso**

> **Nota:** A partir de la versión 1.16.27, este recurso se registra **automáticamente** en cuanto Home Assistant ha arrancado por completo, de forma segura y sin modificar otros recursos existentes (la variante defectuosa y propensa a la pérdida de datos de versiones anteriores ha sido sustituida). **Por lo general, aquí no tienes que hacer nada.** Solo si la tarjeta aparece igualmente como "Custom element doesn't exist" (p. ej. porque gestionas los recursos en modo YAML), añádela una sola vez manualmente como sigue.

1. Ve a **Ajustes → Paneles de control**
2. Haz clic arriba a la derecha en el **menú de tres puntos ⋮** → **Recursos**
3. Haz clic en **+ Añadir recurso** (abajo a la derecha)
4. Introduce los siguientes datos:
   - **URL:** `/ha_bosch_ebike/bosch-ebike-map-card.js`
   - **Tipo de recurso:** módulo JavaScript
5. Haz clic en **Crear**

**Paso B: añadir la tarjeta al dashboard**

1. Abre el dashboard que quieras
2. Haz clic arriba a la derecha en el **lápiz ✏️** (modo de edición)
3. Haz clic en **+ Añadir tarjeta**
4. Desplázate hasta abajo del todo y elige **Manual** (entrada YAML)
5. Pega el siguiente código:
   ```yaml
   type: custom:bosch-ebike-map-card
   height: 400
   ```
6. Haz clic en **Guardar**

> **Consejo:** Puedes ajustar la altura (height) entre 200 y 1000 píxeles. Recomendación: 400 para smartphones, 500 para ordenadores.

**La tarjeta muestra:**
- Track GPS con codificación de colores según la velocidad (azul → verde → amarillo → rojo)
- Marcador de inicio (verde) y marcador de destino (rojo)
- Información del trayecto (distancia, duración, velocidad media/máx., desnivel, calorías)
- Botones **◀ Prev / Next ▶** y **selector de fecha** para hojear todos los trayectos
- El **botón ▶ de chase-cam** abre el recorrido visible en ese momento en una superposición a pantalla completa con la reproducción completa de la tarjeta 3D (2D / 3D / satélite, control deslizante, fijación al norte, pantalla completa). Se cierra con el botón X o con Escape.

> **Nota:** Si la tarjeta no se muestra correctamente tras una actualización, vacía la caché del navegador con `Ctrl+Shift+R` (hard reload).

> **Actualización de las tarjetas por HACS:** Las cuatro tarjetas Lovelace (Map, Heatmap, Calendar, Dashboard) están en un único archivo JS (`bosch-ebike-map-card.js`) y se actualizan automáticamente con la integración. Tras una actualización de versión desde HACS, realiza un hard reload de la caché del navegador; de lo contrario, el selector de tarjetas puede no mostrar todavía una tarjeta nueva.

#### Instalación por HACS (alternativa)

1. Abre HACS en Home Assistant
2. Haz clic en **"Repositorios personalizados"** (tres puntos arriba a la derecha)
3. Añade la URL del repositorio: `https://github.com/Xunil99/ha-bosch-ebike`
4. Categoría: **Integración**
5. Instala la integración y reinicia Home Assistant

---

### Varias bicis o cuentas

La integración admite tanto varias cuentas como varias bicis por cuenta.

**Varias cuentas Bosch** (p. ej. una bici por miembro de la familia con su propio SingleKey ID):
1. Crea para cada cuenta un registro de app propio con su propio Client-ID en el portal Bosch Data Act
2. Añade la integración varias veces (**Ajustes → Dispositivos y servicios → + Añadir integración → Bosch eBike**) introduciendo cada vez el otro Client-ID
3. Cada instancia tiene sus propios sensores y recorridos

**Varias bicis bajo una cuenta** (p. ej. dos bicis con el mismo SingleKey ID):
- La integración crea automáticamente sensores propios por bici (drive unit, batería, mantenimiento, etc.).
- Los recorridos se asignan automáticamente a la bici correcta mediante una heurística (comparación del valor `odometer` específico de la bici con `startOdometer + distance` del recorrido correspondiente).

**Filtro en la tarjeta:** En cuanto hay más de una cuenta y/o más de una bici, la tarjeta Lovelace muestra automáticamente dos campos de selección encima de la lista:
- **Cuenta** (solo visible con varias cuentas)
- **Bici** (solo visible con varias bicis)

La selección filtra en vivo los recorridos mostrados; la ordenación funciona como de costumbre dentro del resultado filtrado.

#### Fijar una tarjeta a una cuenta o bici

Si una tarjeta debe mostrar permanentemente exactamente una cuenta o una bici (p. ej. para tener dos tarjetas una junto a otra como vistas comparativas), añade `account_id` y/o `bike_id` en la configuración de la tarjeta. El desplegable correspondiente se oculta entonces y el filtro queda bloqueado.

Puedes elegir cómodamente los ID desde desplegables en el editor (arriba a la derecha en la edición de la tarjeta); no hace falta buscarlos manualmente. Opcionalmente, `title` puede sobrescribir la cabecera de la tarjeta:

```yaml
type: horizontal-stack
cards:
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Mi bici"
    account_id: <config_entry_id_cuenta_a>
  - type: custom:bosch-ebike-map-card
    height: 400
    title: "Bici de mi pareja"
    account_id: <config_entry_id_cuenta_b>
```

Ambas tarjetas muestran entonces siempre los recorridos de la cuenta bloqueada correspondiente y se puede navegar por el historial de recorridos de forma independiente con la selección de fecha/ordenación, ideal para comparar directamente, p. ej., dos recorridos realizados el mismo día. Las mismas opciones funcionan también en la `bosch-ebike-heatmap-card`.

### POI a lo largo de la ruta

En el mapa hay un interruptor 📍 en los controles. Al activarlo, se inicia en segundo plano una consulta a la API de Overpass que encuentra los siguientes puntos a lo largo de la ruta (máx. ~500 m del camino recorrido):

- 🔌 **Estaciones de carga** (`amenity=charging_station`)
- 🛠️ **Tiendas de bicicletas** y estaciones de reparación (`shop=bicycle`, `amenity=bicycle_repair_station`)
- 💧 **Agua potable** (`amenity=drinking_water`)
- 🚻 **Aseos** (`amenity=toilets`)
- 🍽️ **Gastronomía** (restaurantes, cafeterías, cervecerías al aire libre, comida rápida — `amenity=restaurant/cafe/biergarten/fast_food`)

Clic en un marcador → ventana emergente con el nombre, horario de apertura/dirección/sitio web (si están registrados en OSM) y un enlace a OpenStreetMap. Se muestran hasta 100 marcadores por recorrido; los resultados se almacenan en la localStorage del navegador.

### Recordatorios de mantenimiento

#### Establecer tú mismo la fecha de mantenimiento

Por cada bici hay dos entidades editables:

- **`date.<bike>_service_due_date`**: fecha en la que vence el próximo mantenimiento
- **`number.<bike>_service_due_odometer`**: kilometraje en el que vence el próximo mantenimiento

En la primera recuperación de datos, estos valores se rellenan automáticamente desde la API de Bosch (si están registrados allí). Los cambios en las entidades sobrescriben los valores de Bosch y se utilizan para los recordatorios de mantenimiento. Si pones el kilometraje a `0`, la visualización vuelve al valor de Bosch.

#### Elementos de mantenimiento propios

Además del mantenimiento proporcionado por Bosch (`Next Service Date`/`Next Service Odometer`), puedes crear cualquier elemento de mantenimiento propio, p. ej. cambio de cadena cada 3000 km, inspección cada 365 días. Por cada bici se crea un sensor `Maintenance Items Due`; su valor es el número de elementos próximos a vencer o ya vencidos, y el atributo `items` enumera todos los detalles (kilómetros restantes, días restantes).

**Crear un elemento:** **Herramientas para desarrolladores → Servicios**, invoca el servicio `bosch_ebike.add_maintenance` con:
- `bike_id` (del atributo del sensor)
- `name` (p. ej. "Cambio de cadena")
- `interval_km` y/o `interval_days`

**Marcar un elemento como completado:** servicio `bosch_ebike.complete_maintenance` con `bike_id` e `item_id` (del atributo del sensor). Restablece la fecha y el kilometraje al momento actual.

**Eliminar un elemento:** servicio `bosch_ebike.remove_maintenance`.

**Eventos para automatizaciones:** Al alcanzar el umbral (por defecto: 30 días / 200 km antes del vencimiento) se lanzan eventos de HA:
- `ha_bosch_ebike_service_due_soon` / `ha_bosch_ebike_service_overdue` (para el mantenimiento de Bosch)
- `ha_bosch_ebike_maintenance_due_soon` / `ha_bosch_ebike_maintenance_overdue` (para los elementos propios)

Con ello puedes crear, p. ej., una notificación push o un recordatorio luminoso.

### Estimación de autonomía

Por cada bici hay dos sensores que **estiman** la autonomía — a partir de
tu consumo real (media ponderada por distancia sobre los últimos ~500 km
de historial de recorridos):

- **`Estimated Range (Full Battery)`** — autonomía estimada con la batería
  llena (capacidad de la batería ÷ consumo medio en Wh/km). Solo a partir
  de datos de la nube, siempre disponible.
- **`Estimated Range (Current)`** — autonomía restante estimada
  (nivel actual de batería × capacidad ÷ consumo medio). Solo aparece si en
  las opciones de la integración está vinculado el **sensor de nivel de
  batería en vivo** del puente ESPHome; se actualiza al instante con los
  cambios de SoC.

> ⚠️ **Es una estimación, no una garantía.** La autonomía real depende mucho
> del modo de asistencia, la topografía, el viento, la temperatura y el
> estado de la batería. La base de cálculo puede consultarse en los
> atributos del sensor (`wh_per_km`, `tours_used`, `window_km`). Mientras
> haya menos de 3 recorridos o 30 km de datos de consumo, los sensores
> permanecen vacíos.

### Tarjeta planificador de rutas (BRouter)

La tarjeta `bosch-ebike-routeplanner-card` planifica rutas en bici
directamente en el dashboard — sobre la base del router de código abierto
[BRouter](https://brouter.de):

```yaml
type: custom:bosch-ebike-routeplanner-card
height: 480
```

- **Puntos de ruta con un clic** en el mapa (salida, destino, tantos puntos
  intermedios como quieras; arrastrar un marcador = mover, hacer clic en él
  = eliminar)
- **Perfiles:** Trekking, Bicicleta de carretera, MTB, La más corta
- **POI a lo largo de la ruta** (botón 📍): estaciones de carga, tiendas de
  bicicletas/talleres, agua potable, baños y **gastronomía** (restaurantes,
  cafeterías, cervecerías al aire libre) — datos de OpenStreetMap/Overpass
- **Resultado:** distancia, ascenso/descenso, tiempo de marcha, **consumo
  estimado** (tu consumo medio de la estimación de autonomía × distancia)
- **Comprobación de batería:** indicador tipo semáforo que muestra si la
  ruta es viable con el nivel de batería actual (requiere el sensor de nivel
  de batería en vivo vinculado) — como los sensores de autonomía, una
  **estimación**, no una garantía
- **Perfil de elevación** como diagrama debajo del mapa
- **Exportación GPX** de la ruta planificada (importable en Garmin Connect,
  Komoot, la app Flow y otros)
- **Guardar y cargar rutas:** guarda las rutas planificadas con el nombre
  que quieras (almacenadas en Home Assistant, disponibles en todos tus
  dispositivos), recárgalas desde la lista 📁, sigue editándolas o elimínalas

Opciones: `title`, `height`, `brouter_url` (instancia BRouter propia en
lugar de brouter.de), `entity` (sensor de autonomía), `soc_entity` (nivel
de batería en vivo).

> **Privacidad:** Las coordenadas de los puntos de ruta se envían al servidor
> BRouter configurado para calcular la ruta — por defecto el servidor público
> `brouter.de`, financiado con donaciones. Si prefieres evitarlo, ejecuta
> BRouter por tu cuenta (Docker) e introduce la URL en `brouter_url`.

### Tarjeta heatmap: todos los recorridos en un solo mapa

Una segunda variante de tarjeta, `bosch-ebike-heatmap-card`, superpone todos los recorridos de una selección como líneas semitransparentes. Desplegables de filtro para el periodo (30 días / 3 meses / 12 meses / todo), cuenta y bici. Debajo, una línea de estado con el número de recorridos y kilómetros de la selección.

```yaml
type: custom:bosch-ebike-heatmap-card
height: 600
```

La primera visualización puede tardar un poco: por cada recorrido aún no recuperado se hace una llamada adicional a la API (con límite de concurrencia). Los tracks se almacenan en memoria en el lado del servidor; las llamadas posteriores son inmediatas.

### Tarjeta de calendario: heatmap estilo GitHub de los días de pedaleo

La tarjeta `bosch-ebike-calendar-card` muestra un heatmap anual al estilo del resumen de contribuciones de GitHub: 7 filas para los días de la semana, una columna por semana natural, cada celda coloreada según los kilómetros recorridos ese día. Al pasar el ratón aparece un tooltip con la fecha, el número de recorridos y la distancia. La línea de estadísticas inferior muestra los días activos, los recorridos y la distancia total del periodo elegido.

```yaml
type: custom:bosch-ebike-calendar-card
```

Desplegables de filtro arriba para el periodo (12 meses / 24 meses / 5 años / todo), cuenta y bici. Se puede bloquear a un filtro fijo de cuenta o bici mediante YAML (las mismas opciones que en las tarjetas de mapa y heatmap):

```yaml
type: custom:bosch-ebike-calendar-card
title: Año ciclista de Volker
account_id: 01HXYZ...
bike_id: bike-uuid-1
```

Categorías de color por día: vacío, 1-10 km, 10-25 km, 25-50 km, 50+ km. Los colores provienen de las variables del tema de HA; los temas claros se ven como GitHub-Light, y en modo oscuro se carga automáticamente la paleta oscura correspondiente.

### Mapa 3D: seguimiento con chase-cam, control deslizante de tiempo y posición del sol

La tarjeta `bosch-ebike-3d-map-card` es un mapa paralelo al mapa 2D clásico. Comienza con una lista de los últimos recorridos. Al hacer clic en un recorrido se abre la vista de detalle 3D con MapLibre y tiles vectoriales gratuitas de OpenFreeMap: la **cámara sigue a la bici en perspectiva de tercera persona** ("chase-cam"), el bearing gira acorde con la dirección de marcha, y el pitch y el zoom son configurables. Al mover el control deslizante, la cámara gira a la vez. La iluminación del mapa se adapta a la posición del sol a la hora del recorrido.

```yaml
type: custom:bosch-ebike-3d-map-card
title: Tour in 3D
height: 540
default_pitch: 55      # inclinación de la chase-cam
chase_zoom: 17         # aprox. 100 m de visión hacia delante
playback_speed: 60     # 60x tiempo real (recorrido de 1 h = 1 min de reproducción)
```

**Qué muestra la tarjeta:**

- Lista de recorridos (vista por defecto) con fecha, título, distancia y duración
- Chase-cam 3D tras hacer clic en un recorrido, con extrusiones de edificios de OpenStreetMap
- Polilínea del track en dos capas (resplandor + línea principal) para una buena legibilidad
- Marcadores de inicio y destino, además de un marcador de posición azul pulsante que representa la bici
- Control deslizante de tiempo con las horas de inicio/fin del recorrido, desplazable; la cámara gira de forma síncrona
- Botón de reproducción/pausa para la reproducción a cámara rápida (duración configurable)
- Estadísticas en vivo según la posición del control deslizante: distancia acumulada, velocidad, altitud
- El chip de hora y sol en la superposición muestra la hora actual y la fase de luz diurna (noche, crepúsculo, hora dorada, luz diurna)
- **Sombras proyectadas de los edificios** sobre el suelo, proyectadas a partir del acimut y la altura del sol a la hora del control deslizante. Las sombras se muestran con luz diurna, se acortan en el crepúsculo y se ocultan de noche. Se actualizan automáticamente cuando la cámara gira hacia una nueva zona urbana o se mueve el control deslizante.
- **Exportación de vídeo** a la derecha del control deslizante: el botón de grabación inicia una reproducción desde el principio del recorrido y graba en paralelo el contenido del mapa como vídeo. Al final del recorrido se descarga automáticamente el archivo (aprox. 20-40 MB por minuto). El formato lo determina el navegador: **MP4** en Chrome moderno (≥ 126) y Safari (≥ 14.4), de lo contrario **WebM**. Completamente en el navegador mediante `canvas.captureStream()` + `MediaRecorder`; el servidor de HA no interviene en absoluto.
- El botón de retorno vuelve a la lista de recorridos

**Opciones de configuración de la tarjeta:**

| Opción | Por defecto | Descripción |
|---|---|---|
| `title` | "Bosch eBike 3D-Touren" | Texto de la cabecera |
| `height` | 540 | Altura de la tarjeta en píxeles |
| `default_pitch` | 55 | Inclinación de la chase-cam (20-65°). 20 ≈ vista de pájaro, 65 ≈ primera persona |
| `chase_zoom` | 17 | Zoom de la chase-cam (14-19). Más alto = más cerca, 17 ≈ 100 m de visión hacia delante |
| `chase_lookahead` | 30 | Distancia de anticipación en metros. A qué distancia por delante de la bici se sitúa el objetivo de la cámara. Más pequeño = bici más arriba en la imagen. 0 = cámara centrada directamente en la bici. |
| `smooth_window` | 15 | Ventana de suavizado del bearing. Más alto = cámara más suave, pero recorta más las curvas. 5 se siente tembloroso, 40 resulta muy lento |
| `track_smooth_window` | 2 | Suavizado de la posición del track para la trayectoria de la cámara. 0 = desactivado (GPS en bruto, puede temblar), 2 = suave (por defecto), 5+ puede recortar visiblemente las curvas. La línea del track mostrada siempre refleja el GPS en bruto, independientemente de este valor |
| `playback_speed` | 60 | Multiplicador de tiempo real con el botón de reproducción. 60 = 60× más rápido que el trayecto real; un recorrido de 1 h se reproduce en 1 min, uno de 30 min en 30 s |
| `animate_seconds` | — | Opcional. Fuerza una duración de reproducción fija (p. ej. siempre 25 s), sobrescribe `playback_speed` |
| `show_date` | 1 | Mostrar el chip de fecha en la superposición (0 = desactivado) |
| `show_time` | 1 | Mostrar el chip de hora en la superposición (0 = desactivado) |
| `show_sun` | 1 | Mostrar el chip de posición del sol en la superposición (0 = desactivado) |
| `show_speed` | 1 | Mostrar la velocidad en la barra de estadísticas inferior (0 = desactivado) |
| `show_distance` | 1 | Mostrar la distancia acumulada en la barra de estadísticas (0 = desactivado) |
| `show_elevation` | 1 | Mostrar la altitud (0 = desactivado) |
| `stats_as_chips` | 0 | 1 = distancia, velocidad y altitud como chips de superposición arriba a la izquierda en lugar de abajo en la barra de estadísticas. 0 = línea de estadísticas clásica en la barra de control (por defecto) |
| `account_id` | (vacío) | Fijar a una cuenta, como en el mapa 2D |
| `bike_id` | (vacío) | Fijar a una bici |

Nota: los elementos de superposición ocultos faltan automáticamente también en el vídeo descargado, ya que la grabación simplemente captura el contenido del mapa mostrado.

**Dependencias y notas:**

- MapLibre GL se descarga desde unpkg.com en la primera apertura (aprox. 800 KB comprimido con gzip, luego se almacena en caché)
- OpenFreeMap proporciona las tiles vectoriales sin clave de API y sin registro
- El mapa solo se carga cuando el usuario lo abre realmente. Las tarjetas existentes (Map, Heatmap, Calendar, Dashboard) no se ven afectadas.
- El renderizado 3D es fluido en ordenadores y dispositivos móviles modernos. Con tracks muy largos (> 10.000 puntos) puede haber tirones en dispositivos antiguos.
- La cobertura de edificios de OSM es densa en las ciudades y más escasa en el campo. Los recorridos por zonas urbanas son los que más se benefician.
- Las **sombras del terreno** (montañas, colinas) no están incluidas deliberadamente. Requerirían una fuente de tiles DEM (Maptiler con clave de API, AWS-Open-Data-SRTM o datos de altitud alojados por uno mismo) más un ray-casting propio en el shader. Si hay interés, esto podría añadirse en una versión posterior.

### Tarjeta de dashboard: foto de la bici, datos en vivo y control de carga

La tarjeta `bosch-ebike-dashboard-card` está pensada como visualización combinada para el dashboard del salón: arriba, una foto propia de la bici; debajo, los valores en vivo del puente ESPHome y, opcionalmente, los elementos de control de un enchufe inteligente al que está conectado el cargador. Todos los campos son opcionales: lo que no esté configurado, la tarjeta lo oculta limpiamente en lugar de renderizar una línea vacía.

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

**Qué muestra la tarjeta:**

- **Foto de la bici** con carga integrada en el editor de la tarjeta (eliges la imagen y la tarjeta escribe la ruta por sí misma). Como alternativa, la referencia clásica mediante `/config/www/` y `/local/archivo.jpg`. Marcador de posición con icono de bicicleta mientras no haya nada configurado.
- **Casilla de kilometraje** y, opcionalmente, **distancia del último recorrido** y **potencia de carga en vatios**
- **Autonomía restante estimada** como casilla (`≈ 62 km`) — automática en cuanto existe el sensor "Autonomía estimada (actual)", o explícitamente mediante `range_entity`. Igual que los sensores, es una **estimación**.
- **Pills de estado** para el estado de carga y el porcentaje de batería
- **Control deslizante de SoC objetivo** que establece el valor de un `input_number`
- **Botones de inicio y parada** con confirmación de doble clic al parar (protección contra errores)
- **Barra de batería** abajo, que cambia a naranja por debajo del 35 % y a rojo por debajo del 15 %
- **Lista de mantenimiento** con tantos elementos libremente definibles como quieras (engrasar la cadena, mantenimiento, revisar los frenos, …); en el editor se eligen entre 11 sugerencias o como texto libre. Por cada elemento, un disparador por intervalo de km o por intervalo de días. Aparecen automáticamente en el dashboard en cuanto vencen en los próximos **500 km** o **30 días**: los elementos vencidos en rojo, los próximos a vencer en amarillo, ordenados por urgencia. Con un botón verde de marca de verificación por línea puedes marcar un elemento directamente como "completado". **Almacenamiento en Home Assistant** (`/config/.storage/`, separado por bici) en lugar de en la caché del navegador: los elementos sobreviven a los cambios de navegador, están sincronizados en todos los dispositivos y también pueden gestionarse desde automatizaciones mediante los servicios de HA `bosch_ebike.add_maintenance`, `bosch_ebike.update_maintenance`, `bosch_ebike.complete_maintenance` y `bosch_ebike.remove_maintenance`. En el editor de la tarjeta eliges la bici de un desplegable; los mantenimientos correspondientes aparecen justo debajo y se guardan en vivo en el backend.
- **Comparativa de CO₂ y costes de combustible** frente al coche: dos casillas, "total" y "último recorrido", con los kg de CO₂ y los € ahorrados. En el editor eliges el vehículo de comparación entre 7 presets realistas (utilitario/clase media/SUV, cada uno en gasolina o diésel, más coche eléctrico con energía verde); opcionalmente puedes sobrescribir el precio del combustible/electricidad por litro/kWh.

**Requisitos para la funcionalidad completa:**

- Un **puente ESPHome Bosch eBike** en funcionamiento para el nivel de batería, el kilometraje y la detección de carga
- Un **enchufe inteligente** (Shelly, Tasmota, Fritz!DECT, etc.) que aparezca en HA como `switch.*` y, opcionalmente, como sensor de potencia `sensor.*_power`, si quieres ver el inicio/parada y la potencia de carga
- Un `input_number.*` con rango 0-100, si quieres usar el control deslizante de SoC objetivo

La **parada automática al alcanzar el SoC objetivo** no está implementada deliberadamente en la propia tarjeta, sino como automatización de HA, para que puedas configurar libremente tolerancias, condiciones horarias o lógica de varios dispositivos. Automatización de ejemplo:

```yaml
alias: eBike parada automática al SoC objetivo
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

### Artículos de Wikipedia a lo largo de la ruta

En la tarjeta Lovelace hay un interruptor 📚 en los controles del mapa. Si está activado, la tarjeta busca cada 2 km a lo largo de la ruta recorrida artículos de Wikipedia cercanos y los muestra como marcadores (i). Un clic abre una pequeña ventana emergente con el título, una imagen de vista previa, una breve descripción y un enlace al artículo completo.

- El **idioma** se rige por la configuración de idioma de HA; si no hay resultados, se recurre al inglés
- **Máximo 30 marcadores** por recorrido; las zonas densas se agrupan
- El **estado del interruptor y los resultados** se almacenan en caché en el navegador (`localStorage`); al cambiar de recorrido se obtienen datos nuevos
- **Nota de privacidad**: al activar la capa se envían coordenadas de puntos de apoyo de la ruta a la API de Wikipedia; la capa está desactivada por defecto

### Solución de problemas

| Problema | Solución |
|----------|----------|
| Sin entidades tras la configuración | Activar la compartición de datos en el portal Flow (paso 5) |
| "Cliente no encontrado" al iniciar sesión | Activar el Client-ID en el portal Flow (paso 5) y comprobar errores tipográficos/espacios |
| "Invalid state" / falla el retorno | ¿Está "My Home Assistant" activado en HA? La Redirect URI en el portal debe ser `https://my.home-assistant.io/redirect/oauth` |
| Kilometraje irrealmente alto | El odómetro se entrega en metros y se convierte automáticamente a km |
| Faltan los datos de actividad | Comprueba si la compartición de actividades está activa en el portal Flow |
| Token no aceptado | Comprueba si el Client-ID se ha introducido correctamente |

---

### Sensores disponibles

#### Sensores de la bici
| Sensor | Unidad | Descripción |
|--------|--------|-------------|
| Odometer | km | Kilometraje total |
| Motor Total Hours | h | Tiempo total de funcionamiento del motor |
| Motor Assist Hours | h | Tiempo de funcionamiento del motor con asistencia |
| Max Assist Speed | km/h | Velocidad máxima de asistencia |
| Active Assist Modes | - | Lista de los modos de asistencia activos |
| Walk Assist Speed | km/h | Velocidad del asistente de empuje |
| Next Service Odometer | km | Kilometraje del próximo mantenimiento |
| Estimated Range (Full Battery) | km | Autonomía estimada con batería llena (a partir del consumo medio, ¡estimación!) |
| Estimated Range (Current) | km | Autonomía restante estimada (SoC en vivo necesario, ¡estimación!) |

#### Sensores de batería (por batería)
| Sensor | Unidad | Descripción |
|--------|--------|-------------|
| Wh Lifetime | Wh | Vatios-hora suministrados durante la vida útil |
| Charge Cycles | - | Ciclos de carga totales |
| Cycles On Bike | - | Ciclos de carga en la bici |
| Cycles Off Bike | - | Ciclos de carga externos |

#### Sensores de actividad (último trayecto)
| Sensor | Unidad | Descripción |
|--------|--------|-------------|
| Last Ride Title | - | Nombre del trayecto |
| Last Ride Date | - | Fecha/hora |
| Last Ride Distance | km | Distancia |
| Last Ride Duration | min | Duración del trayecto (sin paradas) |
| Last Ride Avg/Max Speed | km/h | Velocidad media/máxima |
| Last Ride Avg/Max Cadence | rpm | Cadencia |
| Last Ride Avg/Max Rider Power | W | Potencia del ciclista |
| Last Ride Calories | kcal | Calorías consumidas |
| Last Ride Elevation Gain/Loss | m | Desnivel (ascenso/descenso) |

#### Estadísticas totales (de todos los trayectos)
| Sensor | Unidad | Descripción |
|--------|--------|-------------|
| Total Rides | - | Número total de trayectos |
| Total Distance (Activities) | km | Distancia total de todos los trayectos |
| Total Ride Duration | h | Tiempo total de conducción |
| Total Calories | kcal | Consumo total de calorías |
| Total Elevation Gain | m | Desnivel total |
| Avg Speed (All Rides) | km/h | Velocidad media de todos los trayectos |
| Avg Rider Power (All Rides) | W | Potencia media del ciclista |
| Avg Cadence (All Rides) | rpm | Cadencia media |

#### Botones
| Botón | Descripción |
|-------|-------------|
| Import All GPS Data | Exporta los tracks GPS de todos los trayectos como archivos GPX |
| Import Latest GPS Data | Exporta el track GPS del último trayecto como GPX |

> **Ubicación de almacenamiento:** Los archivos GPX exportados se guardan localmente en el directorio de configuración de Home Assistant, en:
> ```
> /config/bosch_ebike_gps/
> ```

---

### Licencia

Licencia MIT: consulta [LICENSE](LICENSE) para más detalles.

### Créditos

Creado por [Volker Hauffe](https://github.com/Xunil99).

Esta integración utiliza la [Bosch eBike Data Act API](https://portal.bosch-ebike.com/data-act) oficial.
