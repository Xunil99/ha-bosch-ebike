# Bosch eBike Live Data Interface – Charge Limiter

This implementation turns an Sonoff BASICR4 into a charge limiter for your Bosch eBike.

The charge limit can be configured and the output will be turned off when the charge limit is reached. This happens
within the charge limiter itself, ensuring charging can be done anywhere.

**Sonderfall 100 % / Special case 100 %:** Wird das Limit auf `100` gesetzt, schaltet der Limiter **nicht** ab.
Bosch zieht nach Erreichen von 100 % SoC noch ca. 30-45 Minuten Strom für das Cell-Balancing; ein sofortiges
Abschalten bei 100 % würde diese Phase verhindern. Bei `100` bleibt der Ausgang daher an, bis Rad/Ladegerät den
Vorgang selbst beenden. (When the limit is set to `100`, the limiter does **not** cut off: Bosch keeps drawing power
for ~30-45 min after reaching 100 % SoC for cell balancing, so the output stays on and charging/balancing can finish.)

![charge-limiter](https://github.com/user-attachments/assets/b7e0ed87-42b8-4179-a7bf-c8000ad82836)
![charge-limiter](https://github.com/user-attachments/assets/4dd49d1f-4060-4b2d-a960-b45a17447b22)

The full config is in [example-charge-limiter.yaml](example-charge-limiter.yaml).

Note: the BASICR4 switches mains voltage. Only flash and wire this on the
Sonoff BASICR4 it is written for, and treat mains wiring with the usual care.

Contributed by [@henri98](https://github.com/henri98). Thanks!
