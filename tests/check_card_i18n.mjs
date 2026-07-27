// Structural parity check for the Lovelace card translations.
//
//   node tests/check_card_i18n.mjs [path-to-bosch-ebike-i18n.js]
//
// English is the reference: every other language must carry the same keys,
// in the same order, with function-valued strings still being functions of
// the same arity that actually interpolate all of their arguments. Those are
// exactly the mistakes that are easy to make when adding or editing a
// language by hand, and none of them are visible until the card renders.
// Exits non-zero on any structural problem; the closing note about
// untranslated-looking values is informational only.
import { pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const target = process.argv[2]
  ? resolve(process.argv[2])
  : resolve(here, "../custom_components/ha_bosch_ebike/www/bosch-ebike-i18n.js");

const { I18N } = await import(pathToFileURL(target).href);

// Spelled out rather than derived from the file, because deriving it would
// make the most important failure invisible: delete a whole language block
// and a self-derived list simply reports one language fewer and passes.
// Adding a language is a deliberate act, so adding it here too is correct.
const EXPECTED = ["en", "de", "nl", "fr", "it", "es", "cs"];

const langs = Object.keys(I18N);
const en = I18N.en;
if (!en) {
  console.log("FAIL en block missing - it is the reference for every other language");
  process.exit(1);
}
const enKeys = Object.keys(en);
let bad = 0;
const fail = (m) => { console.log("FAIL " + m); bad++; };

console.log(`languages: ${langs.join(", ")}  (${enKeys.length} keys each)`);

for (const lang of EXPECTED) {
  if (!I18N[lang]) fail(`language block "${lang}" is missing entirely`);
}
for (const lang of langs) {
  if (!EXPECTED.includes(lang))
    fail(`language block "${lang}" is not in EXPECTED - add it there if it is intentional`);
}

for (const lang of langs) {
  const keys = Object.keys(I18N[lang]);
  const missing = enKeys.filter((k) => !(k in I18N[lang]));
  const extra = keys.filter((k) => !(k in en));
  if (missing.length)
    fail(`${lang}: missing ${missing.length} key(s) -> ${missing.slice(0, 8).join(", ")}`);
  if (extra.length)
    fail(`${lang}: ${extra.length} unknown key(s) -> ${extra.slice(0, 8).join(", ")}`);
  // Same order too, so diffs between languages stay readable.
  if (!missing.length && !extra.length && !keys.every((k, i) => k === enKeys[i]))
    fail(`${lang}: key order differs from en`);
}

// Type parity in both directions plus a usability check on the value
// itself. Key-name parity alone lets a null, an empty string, or a string
// where English has a function through, and the card then renders "null" or
// "[object Object]" at the user rather than text.
for (const k of enKeys) {
  for (const lang of langs) {
    const v = I18N[lang][k];
    if (v === undefined) continue; // already reported as a missing key
    if (typeof v !== typeof en[k]) {
      fail(`${lang}.${k}: is a ${typeof v}, en has a ${typeof en[k]}`);
      continue;
    }
    if (typeof v === "string" && v.trim() === "")
      fail(`${lang}.${k}: empty string`);
    if (v === null) fail(`${lang}.${k}: null`);
  }
}

for (const k of enKeys) {
  if (typeof en[k] !== "function") continue;
  const n = en[k].length;
  // Some of these format numbers (.toFixed/.toLocaleString), so string
  // markers throw; fall back to distinctive numbers and look for the digits.
  const strArgs = Array.from({ length: n }, (_, i) => `«${i}»`);
  const numArgs = Array.from({ length: n }, (_, i) => 1000 + i);
  let args = strArgs;
  let probes = strArgs;
  try {
    en[k](...strArgs);
  } catch {
    args = numArgs;
    probes = numArgs.map(String);
  }
  for (const lang of langs) {
    const v = I18N[lang][k];
    if (typeof v !== "function") continue; // already reported by the type-parity pass
    if (v.length !== n) { fail(`${lang}.${k}: arity ${v.length}, en has ${n}`); continue; }
    let out;
    try { out = String(v(...args)); }
    catch (e) { fail(`${lang}.${k}: threw ${e.message}`); continue; }
    const lost = probes.filter((p) => !out.includes(p));
    if (lost.length) fail(`${lang}.${k}: lost placeholder(s) ${lost.join(", ")} -> "${out}"`);
  }
}

// Informational: a value byte-identical to English is usually an untranslated
// leftover, but product names and units legitimately match, so this never
// fails the build. Useful right after adding a language.
for (const lang of langs) {
  if (lang === "en") continue;
  const same = enKeys.filter(
    (k) => typeof en[k] === "string" && I18N[lang][k] === en[k] && en[k].length > 3);
  if (same.length) console.log(`note ${lang}: ${same.length} value(s) identical to English`);
}

console.log(bad === 0 ? "STRUCTURE OK" : `${bad} STRUCTURAL PROBLEM(S)`);
process.exit(bad === 0 ? 0 : 1);
