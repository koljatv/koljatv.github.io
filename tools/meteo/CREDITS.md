# PREVISÃO DO TEMPO: credits

The segment (tools/tempo_video.py) and the site's Tempo page (public/tempo/).

## Music
| Where | Piece | Source | Licence |
|---|---|---|---|
| The whole segment (72 s bed) | Piano and warm keys, a continuous original arrangement for KÖLJA TV, approved local music direction of 2 November 2026 | Final broadcast master: `trilha.m4a`; production sources, approval and provenance retained in the private production archive | Production licence records retained privately |

`trilha.py` is retained as the historical source of the previous score; it does not regenerate the current master.

## Data
| What | Source | Licence | Credit on air |
|---|---|---|---|
| Forecast: daily max/min, weather code, chance of rain for the 27 capitals | Open-Meteo forecast API, https://open-meteo.com/ (free, no key) | CC BY 4.0 (attribution) | Footer of every frame: "Previsão Open-Meteo.com · atualizada às HH:MM"; closing card: "Dados: Open-Meteo.com"; Tempo page: "Previsão: Open-Meteo.com (CC BY 4.0)" |
| Map: Brazil's states | IBGE, malhas API (`servicodados.ibge.gov.br/api/v3/malhas/paises/BR?intrarregiao=UF&qualidade=minima`), simplified to outer rings in `brasil.json` | Brazilian federal open data | Tempo page: "Mapa: IBGE" |

## Type and look
- Barlow Condensed and Jost (SIL Open Font License 1.1), the same faces the site self-hosts; `fonts/*.ttf` are static instances of the site's woff2 files.
- The KÖLJA TV logo (`logo.png`) is a render of the site's `public/img/logo.svg`.
- Weather icons: drawn in code by `tools/tempo_video.py` (`--icons` writes the page's PNGs).
