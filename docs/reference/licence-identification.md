---
title: Licence identification
description: The exact rules dex uses to classify licence text, labels and SPDX expressions.
---

# Licence identification

Implemented in `src/dex_trove/licenses.py`. Text is normalised first: lower-cased, typographic apostrophes
replaced, whitespace collapsed.

## 1. Deny markers (checked first)

If any of these phrases appears, the text is `LicenseRef-Proprietary` (**deny**), whatever else it contains:

| Marker |
| --- |
| `governed by your agreement with` |
| `users may not` |
| `you may not distribute` |
| `may not be redistributed` |
| `distribute, sublicense, or transfer these materials` |
| `does not convey or imply any license` |
| `proprietary and confidential` |
| `unauthorized copying of this file` |

## 2. Fingerprints (in this order)

| Phrase(s) | SPDX | Verdict |
| --- | --- | --- |
| `gnu affero general public license` | AGPL-3.0-only | deny |
| `gnu lesser general public license` | LGPL-3.0-only | review |
| `gnu general public license` | GPL-2.0-only (if "version 2" and not "version 3") else GPL-3.0-only | deny |
| `business source license` | BUSL-1.1 | deny |
| `server side public license` | SSPL-1.0 | deny |
| `sil open font license` | OFL-1.1 | allow |
| `mozilla public license` | MPL-2.0 | review |
| `apache license` + `version 2.0` | Apache-2.0 | allow |
| `permission is hereby granted, free of charge` + `the above copyright notice and this permission notice shall be included` | MIT | allow |
| `permission is hereby granted, free of charge` (without the notice clause) | MIT-0 | allow |
| `redistribution and use in source and binary forms` + `neither the name` | BSD-3-Clause | allow |
| `redistribution and use in source and binary forms` | BSD-2-Clause | allow |
| `permission to use, copy, modify, and/or distribute this software for any purpose` + `the above copyright notice` | ISC | allow |
| …same, without the notice clause | 0BSD | allow |
| `free and unencumbered software released into the public domain` | Unlicense | allow |
| `cc0 1.0 universal` / `creative commons legal code cc0` | CC0-1.0 | allow |
| `attribution-noncommercial` | CC-BY-NC-4.0 | deny |
| `attribution-noderivatives` / `attribution-noderivs` | CC-BY-ND-4.0 | deny |
| `attribution-sharealike 4.0` | CC-BY-SA-4.0 | review |
| `attribution 4.0 international` | CC-BY-4.0 | allow |
| `boost software license` | BSL-1.0 | allow |
| `altered source versions must be plainly marked` | Zlib | allow |

## 3. Fallbacks

| Condition | Result |
| --- | --- |
| `all rights reserved` with no fingerprint matched | LicenseRef-Proprietary (deny) |
| nothing matched | unknown (deny) |

## Labels and SPDX ids

Frontmatter values and short labels are normalised through aliases, case-insensitively:

| Input | SPDX |
| --- | --- |
| `MIT`, `MIT License`, `The MIT License` | MIT |
| `Apache-2.0`, `Apache 2.0`, `Apache-2`, `Apache License 2.0`, `Apache License, Version 2.0`, `Apache Software License` | Apache-2.0 |
| `BSD-3-Clause`, `BSD 3-Clause` | BSD-3-Clause |
| `CC0`, `CC0-1.0` | CC0-1.0 |
| `CC BY 4.0`, `CC-BY-4.0` | CC-BY-4.0 |
| `GPL-3.0`, `GPL-2.0`, `AGPL-3.0`, `LGPL-3.0` | the `-only` forms |

Any other well-formed token (e.g. `EPL-2.0`) is kept as-is, and its verdict comes from the prefix rules. Free text
that isn't an id, such as `Complete terms in LICENSE.txt`, returns *no answer*, and resolution falls through to
the item's licence file. Any value containing `proprietary` is denied.

## Expressions

| Expression | Rule |
| --- | --- |
| `A OR B` | best branch (allow > review > deny) |
| `A AND B` | worst branch; allowed only if every branch is |
| `A WITH exception` | evaluated as `A` |
| `(…)` | outer parentheses stripped |

## Licence files

| Purpose | Filenames (case-insensitive) |
| --- | --- |
| Item / ancestor / repo licence | `LICENSE`, `LICENCE`, `COPYING`, `UNLICENSE`, optionally followed by `.`, `-` or `_` and anything (`LICENSE.txt`, `LICENSE-MIT`) |
| Nested component licences | `LICENSE*`, `COPYING*`, `*-OFL.txt`, `*.OFL.txt`, `OFL.txt` anywhere inside the item |

## Copyright notices

Lines starting with `Copyright` or `©` are extracted (up to three), except lines that are licence prose
(containing `license`, `notice`, `owner`, `holder`, `statement`, `permission`, `the above` or `[`).

## Try it

```bash
dex license ./LICENSE
dex license path/to/skill/        # every licence file directly in the folder
```
