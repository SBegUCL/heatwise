# HEATWISE open weather data

This folder is refreshed every Monday by the GitHub Actions workflow `.github/workflows/fetch-weather.yml`, which runs `pipeline/fetch_weather.py`. It can also be run by hand from the repository's **Actions** tab. `fetch_report.json` records what each run downloaded.

## Files the dashboard uses

| File | What it is | Source and licence |
|---|---|---|
| `ecad_london_tx.csv` | Daily maximum temperature, 1979 to the latest complete month, for the four London-area stations held by ECA&D. Only observations with quality flag 0 (valid) are kept. | Series supplied by the **Met Office National Climate Information Centre** to the European Climate Assessment & Dataset (ECA&D) blended dataset; recent days are completed from Met Office synoptic (SYNOP) reports. Klein Tank et al. (2002), *Int. J. Climatol.* 22, 1441–1453. https://www.ecad.eu. Free for non-commercial research and education. |
| `london_summary.json` | Hot-day counts (days ≥28, 30 and 32°C, May–September) per station and year, plus the latest summer's daily maxima. | Built from `ecad_london_tx.csv`. |
| `metoffice_heathrow_monthly.csv` / `.txt` | Met Office monthly station data for Heathrow (mean maximum and minimum temperature, frost days, rain, sun), 1948 to the latest month. Recent months are provisional. | Met Office historic station data. © Crown copyright, Open Government Licence v3. |
| `metoffice_region_SE_tmax_monthly.csv` / `.txt` | Met Office monthly mean maximum temperature for the England SE and Central S region, 1884 onwards. | Met Office UK and regional series. © Crown copyright, Open Government Licence v3. |

### Stations

| Station | Where | Daily record used |
|---|---|---|
| Heathrow | West London (airport) | 1979 – Sep 2026 |
| Wisley | Surrey, 33 km south-west of central London | 1979 – Sep 2026 (2003, 2004 and 2007 incomplete) |
| Rothamsted | Hertfordshire, 37 km north-west | 1979 – Sep 2026 |
| Hampstead | North London | 1979 – Jul 2016 (station closed) |

**Quality check.** Heathrow's daily values from ECA&D, averaged by month, match the Met Office's published monthly mean maximum to within about ±0.25°C for May–September 2025 and 2026.

## Supplementary files: a data-quality exercise

`london_daily_tmax.csv` and `london_summary_meteostat.json` come from **Meteostat** (CC BY 4.0). Meteostat redistributes airport and synoptic reports from NOAA (GHCN-D and ISD), Deutscher Wetterdienst and METAR for Heathrow, Northolt, Kenley, London City Airport and Biggin Hill. Days filled from forecast models have been removed. The dashboard does **not** use these files, because a comparison with the Met Office-supplied series shows that:

- the Meteostat daily maxima are dated one day later than the Met Office climate day (the match is 86% within 0.3°C once shifted by a day, and 17% without the shift);
- values derived from hourly reports (ISD, DWD and METAR) read about 0.5–0.9°C below the official daily maximum, because they miss the peak between reports.

These differences change hot-day counts considerably. For example, Heathrow had 19 days ≥30°C in 2018 in the Met Office series but 13 in Meteostat. This makes a useful exercise in data provenance and fitness for purpose.

## Optional: Met Office MIDAS Open

The Met Office's own daily station archive (MIDAS Open, Open Government Licence) covers many more London stations, including St James's Park, Kew Gardens and Northolt, but only to the end of the previous year, and downloads require a free CEDA account. To include it, register at https://services.ceda.ac.uk/, then add repository secrets `CEDA_USERNAME` and `CEDA_PASSWORD` (Settings → Secrets and variables → Actions). The next run writes `midas_open_london_daily_temp.csv`.

## Not openly available

The Met Office does not publish daily 2026 station observations for London as an open bulk download. Its Weather DataHub observations service holds only the last 48 hours and requires a subscription.
