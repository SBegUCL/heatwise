# HEATWISE: risk what-if dashboard

A what-if risk analysis exercise for SPCE0019 Project Simulation (UCL Centre for Systems Engineering).

Open the live page: https://sbegucl.github.io/heatwise/

## What students see

The page has six tabs:

- **Overview**: purpose, scope statement (in and out of scope, assumptions, constraints, deliverables), SMART objectives and the VUCA statement.
- **Stakeholders**: power/interest matrix and RACI matrix.
- **Schedule**: WBS, a Gantt chart with float and milestones, and an activity-on-node network diagram showing the critical path. The Gantt marks the deadline and the group's current P50 finish.
- **Budget & cashflow**: the CBS, project budget (base cost plus contingency) and the forecast cashflow (planned cumulative spend against the group's expected and P80 outturn), with a monthly table.
- **Success**: output and outcome success criteria, with live status from the group's current scenario.
- **Risk what-if**: groups mitigate the High and Medium risks on a London heat-resilience retrofit. They weigh the residual and secondary risks of each response, balancing probability and financial impact against budget and deadline. A Monte Carlo simulation (4,000 runs) forecasts the chance of staying within budget and of finishing on time, and reports project KPIs: SPI, schedule variance, milestones, CPI, cost and budget variance, rework, first-time acceptance, defects, crew utilisation, stakeholder satisfaction, ROI and benefits realisation. Round 2 is a **week-14 review (12 July 2027)**, timed to match a session in mid-July 2027, when the project is about two-thirds through. It gives an earned-value status (PV, EV, AC, SPI, CPI); one risk has occurred, two have closed and two carry only the exposure still ahead. The heat forecast combines the hot days already observed in summer 2027 (from the live data feed, or an illustrative figure until those data exist) with a forecast for the rest of the season. Two **unforeseen issues** (council payments frozen; residents reject the sensors on data-protection grounds) go in an **issue log**, and two **change requests** (add two buildings; open the cooling centres early) go through **change control**. For each one the page shows who has authority to decide: the project manager within tolerance (£50k and 1 week, no change to scope or benefits), or the sponsor by exception and through the change control board. Groups can also use recovery actions.

## The only download: a 3- or 4-slide recommendation

Once a group has settled on its final scenario, **Download PowerPoint** (under "Your recommendation summary" on the Risk what-if tab) produces a UCL-branded PowerPoint (16:9, Aptos) built in the browser from the chosen scenario:

1. **Our recommendation**: the chosen responses, total spend, the change in the chance of meeting both targets, and the budget and time confidence against the targets.
2. **How we optimised**: the risk register with the chosen responses, secondary risks, and a chart comparing the scenarios the group saved.
3. **Week 14: issues and change control** (Round 2 scenarios only): the issue log and change control log with the group's decisions, their effects and the authority for each, plus prompts on escalation and on why the issues were not on the register.
4. **What the board must accept, and what we learned**: the top residual risks with owners, the KPI forecast, the ask of the board, and a group reflective statement (What? So what? Now what?).

The variables are filled in. Purple *[Edit: …]* prompts mark the generic narrative the group personalises, and each slide carries speaker notes.

To add the official UCL logo, save the artwork supplied by UCL Brand as `assets/ucl-logo.png`; the deck embeds it automatically when present.

## Using it in class

Any number of students can open the page at once. It is a static page: each browser runs its own copy of the model, and nothing is sent to a server. Saved scenarios stay in that browser. **Copy share link** puts the current settings in a link, so a group member or tutor can open exactly the same scenario on another device. Real-time shared editing would need a server and is not part of this design.

## Data

The heat-stoppage risk is forecast from real daily maximum temperatures, 1979 to September 2026, at Heathrow, Wisley and Rothamsted: Met Office series published through ECA&D. They are refreshed weekly by the open-data pipeline in `pipeline/` and `.github/workflows/fetch-weather.yml`. See `data/README.md` for sources, licences and data-quality notes.

## Files

- `index.html`: the dashboard. Self-contained apart from the slide library, which loads only when a group downloads its deck.
- `vendor/pptxgen.bundle.js`: PptxGenJS 4.0.1 (MIT licence), used to build the slides in the browser.
- `data/`: open weather data, refreshed weekly. `pipeline/`: the script that fetches it.
- `archive/v1/`: the earlier monitoring-and-control version.

Data: Met Office National Climate Information Centre daily series via ECA&D blended data (Klein Tank, A.M.G. et al. (2002), Int. J. Climatol., 22, 1441–1453, https://www.ecad.eu), and Met Office historic station data (Open Government Licence).

Project costs, probabilities, response options and secondary risks are illustrative teaching assumptions.
