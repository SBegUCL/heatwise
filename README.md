# HEATWISE: risk what-if dashboard

A what-if risk analysis exercise for SPCE0019 Project Simulation (UCL Centre for Systems Engineering).

Open the live page: https://sbegucl.github.io/heatwise/

Groups mitigate the High and Medium risks on a London heat-resilience retrofit project. They assess the residual and secondary risks of each response and balance probability and financial impact against the budget and the deadline. A Monte Carlo simulation (4,000 runs) forecasts the chance of staying within budget and of finishing on time, and reports project KPIs: SPI, schedule variance, milestones, CPI, cost and budget variance, rework, first-time acceptance, defects, crew utilisation, stakeholder satisfaction, ROI and benefits realisation. Round 2 is a week-10 update with an earned-value status (PV, EV, AC): one risk occurs, two risks close and the heat outlook worsens.

The heat-stoppage risk is forecast from real daily maximum temperatures, 1979 to September 2026, at Heathrow, Wisley and Rothamsted: Met Office series published through ECA&D. They are refreshed weekly by the open-data pipeline in `pipeline/` and `.github/workflows/fetch-weather.yml`. See `data/README.md` for sources, licences and data-quality notes.

- `index.html`: the dashboard. It is self-contained, runs entirely in the browser and sends no data anywhere. Saved scenarios stay in the viewer's own browser.
- `HEATWISE_Risk_WhatIf_Workbook.xlsx`: the companion workbook. It holds the risk register in the module template, an expected-value (EMV) view of the same model, the KPI definitions and a worked earned-value calculation, a scenario log, a decision sheet, the Round 2 brief and the student tasks.
- `data/`: open weather data, refreshed weekly. `pipeline/`: the script that fetches it.
- `archive/v1/`: the earlier monitoring-and-control version.

Data: Met Office National Climate Information Centre daily series via ECA&D blended data (Klein Tank, A.M.G. et al. (2002), Int. J. Climatol., 22, 1441–1453, https://www.ecad.eu), and Met Office historic station data (Open Government Licence).

Project costs, probabilities, response options and secondary risks are illustrative teaching assumptions.
