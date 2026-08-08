## What does this change?

<!-- A short description of what changed and why. -->

Closes #<!-- issue number, if any -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation only
- [ ] Firmware (ESPHome)
- [ ] Other (please describe above)

## Checklist

- [ ] I ran the Python test suite locally (`for f in tests/test_*.py; do python3 "$f" || break; done`) and it passes
- [ ] If I added/changed user-visible card text, I updated all seven languages in `bosch-ebike-i18n.js` and ran `node tests/check_card_i18n.mjs`
- [ ] If I touched ESPHome YAML/C++, it compiles locally (`esphome compile esphome/<file>.yaml`)
- [ ] If this is user-facing, I updated `README.md` (German + English at minimum)
- [ ] I didn't commit any real tokens, serial numbers, or other secrets (check `secrets.yaml`-shaped files and any pasted logs)

## Anything else the maintainer should know?

<!-- Design decisions, things you're unsure about, follow-up work you're aware of but left out on purpose, etc. -->
