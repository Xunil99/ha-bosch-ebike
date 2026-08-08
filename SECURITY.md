# Security Policy

## Supported Versions

This is a hobby project maintained by one person, without a long-term
support branch. Security fixes are made against the latest release
(integration and firmware alike); there's no backport policy for older
versions. Updating to the latest release via HACS (integration) or
re-flashing the latest firmware build is the supported way to receive a fix.

## What counts as a security issue here

This project handles a few genuinely sensitive things worth reporting
privately rather than as a public issue:

- **Bosch OAuth tokens** (access/refresh tokens, client ID) stored by the
  Home Assistant integration - a bug that could leak these into logs,
  diagnostics exports, or another user's account.
- **BLE pairing/bonding** between the ESPHome bridges and the eBike - a way
  to bypass bonding, impersonate a paired bike/accessory, or read data
  intended for a different bonded device.
- **Wi-Fi/MQTT/API credentials** (`secrets.yaml`) or the ESPHome native API
  encryption key, if a firmware change caused them to be exposed (logged,
  broadcast, exfiltrated).
- Anything that would let one Home Assistant user's Bosch account data
  reach a different user.

Regular bugs (wrong sensor value, a card not rendering right, a ride
misattributed to the wrong bike) are **not** security issues - please use
the normal [bug report template](../../issues/new/choose) for those, they
get seen faster that way.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for a security concern.

Use GitHub's private vulnerability reporting instead: go to the
[Security tab](../../security/advisories/new) of this repository and click
**"Report a vulnerability"**. This opens a private conversation with the
maintainer only, and lets you attach logs/details that shouldn't be public.

If that's not available for some reason, opening an issue that says only
"I found a possible security issue, please contact me" (with no details in
the public body) works too - the maintainer will follow up privately to get
the specifics.

You should expect an initial response within a few days. This is a
spare-time project, so please be patient - a genuine vulnerability will be
taken seriously and fixed, just not necessarily on a corporate SLA.
