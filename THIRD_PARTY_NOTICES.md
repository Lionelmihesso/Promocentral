# Code et données de tiers

Tout est sous licence permissive (BSD-3-Clause pour le code, SIL Open Font License 1.1 pour les polices) : réutilisation
autorisée, à condition de conserver les mentions ci-dessous. Aucune dépendance à installer : le code repris est embarqué
et n'utilise que la bibliothèque standard.

| Élément | Où | Origine | Ce qui est repris |
|---|---|---|---|
| price-parser (tests) | `tests/corpus/price_strings.json` | github.com/scrapinghub/price-parser, `tests/test_price_parsing.py`, révision 6718bfe (2026-10-06) | 1 040 chaînes de prix réelles (le code n'est pas repris : notre lecteur fait déjà 99,6 % sur ce corpus) |
| Manrope (police) | `web/fonts/manrope-latin.woff`, intégrée à `web/app.html` | github.com/google/fonts, `ofl/manrope`, révision 47d54ca (2026-10-16) ; dessin de Mikhail Sharanda | police variable 200-800 réduite aux caractères latins (licence : `web/fonts/OFL-Manrope.txt`) |

Les illustrations de produits (`web/src/art.jsx`) et les pictogrammes sont des dessins originaux, sans élément de tiers.

## price-parser — BSD-3-Clause

Copyright (c) Scrapinghub
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.

    3. Neither the name of ScrapingHub nor the names of its contributors may be used
       to endorse or promote products derived from this software without
       specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
