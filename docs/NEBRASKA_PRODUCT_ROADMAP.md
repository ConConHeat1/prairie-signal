# Nebraska Product and Deployment Roadmap

- Last updated: 2026-07-31
- Status: Approved product direction; implementation remains gated by milestone acceptance
- Public-service target: Every location in Nebraska, with enough surrounding weather context to
  show and predict systems moving into the state

## Product outcome

Prairie Signal should become a fast, distinctive Nebraska weather observatory: official current
conditions and alerts, statewide observed radar, useful forecast visualizations, and eventually
independently verified short-range predictions. Lincoln remains the first reference and acceptance
location, but it is no longer the final service boundary.

"Most accurate" is a measurable goal, not marketing copy. Prairie Signal may publish a superiority
claim only after archived, issue-time forecasts beat declared baselines on unseen Nebraska events
with reproducible metrics. Official National Weather Service alerts always remain authoritative.

## Current state

Implemented and verified:

- NWS current conditions, 48-hour hourly forecasts, day/night forecasts, and official alerts
- Regional city, ZCTA, and coordinate search
- Visible source freshness, unavailable states, bounded retries, cache, and stale fallback
- One accepted NOAA MRMS composite-reflectivity path from immutable source data through a
  Lincoln-region normalized Zarr artifact
- Local Docker application, database, cache, migrations, tests, CI definition, and observability

Not implemented yet:

- A public deployment
- Statewide Nebraska search and domain configuration
- Radar tiles, API routes, map, timeline, or animation
- Continuous radar ingestion and retained frame history
- Historical training/evaluation data or a public verification scoreboard
- Radar nowcasts, AI predictions, rain-arrival guidance, or proof of superior accuracy
- Advanced graphs, model comparison, county dashboards, or statewide performance evidence

## Publishing and hosting decision

GitHub is the source-of-truth and automation host; it is not the production runtime for the current
application. GitHub Pages serves static HTML, CSS, and JavaScript. It cannot run the FastAPI
service, PostgreSQL/PostGIS, Valkey, recurring ingestion, Rasterio/GRIB processing, or model
inference used by Prairie Signal.

The deployment will therefore be delivered in stages:

1. **Public source repository and CI.** Publish the scrubbed repository, protect `main`, and require
   the existing checks before promotion.
2. **Free public beta.** Host the web assets at a static/edge host and expose the lightweight NWS
   request path through an edge or on-demand service. This provides a public URL but may have
   free-tier cold starts or quotas; it must not be described as guaranteed always-on.
3. **Radar beta.** Generate statewide observed-radar tiles with scheduled scientific workers and
   publish immutable artifacts to object storage behind a CDN. A no-cost scheduler can be used for
   evaluation, but delayed or dropped executions must be visible as stale/unavailable radar.
4. **Always-on production.** Move API, ingestion, database, cache, object storage, and monitoring to
   continuously provisioned resources after measuring real CPU, memory, storage, bandwidth, and
   update-frequency requirements. A service-level claim requires monitoring and a recovery plan,
   not merely a free URL.

GitHub Pages remains suitable for project documentation or a future static client after the live
API is hosted elsewhere. It is not the selected full-stack production host.

## Target production topology

```text
GitHub repository and protected CI
  -> web build and deployment
    -> CDN/edge-hosted Nebraska interface
      -> versioned public API
        -> NWS live-data adapter and resilient cache
        -> PostgreSQL/PostGIS metadata and verification records
        -> object storage/CDN for radar and prediction tiles

Scheduled scientific workers
  -> NOAA MRMS, NBM/HRRR, GOES/GLM, and verified observations
    -> immutable raw archive
      -> statewide aligned products
        -> observed radar tiles
        -> archived baselines and model predictions
        -> public verification aggregates
```

Heavy GRIB/Rasterio processing and model inference stay outside request handlers. The website reads
already generated, versioned artifacts so a slow model run cannot make official weather or alerts
unavailable.

## Statewide Nebraska domain contract

Before adding statewide product behavior:

- Add a versioned `nebraska-statewide-v1` region configuration in `EPSG:5070` at 1 km nominal
  resolution.
- Use the official Nebraska boundary for the serving area and a 200 km surrounding processing
  context so fast-moving storms are visible before entering the state and two-hour nowcasts have
  upstream data.
- Keep the accepted Lincoln grid as a regression fixture and benchmark location.
- Load and test every Nebraska Census Place, ZCTA approximation, county, and coordinate within the
  state; no statewide query may silently fall back to Lincoln.
- Select NWS forecast offices, grids, and observation stations from each requested point rather
  than hard-coding an eastern-Nebraska office or station.
- Test at least Scottsbluff, Chadron, North Platte, McCook, Grand Island, Norfolk, Omaha, and Lincoln,
  plus border, rural, and radar no-coverage cases.
- Record county and time-zone handling explicitly. Nebraska spans Mountain and Central time.

## Execution roadmap

### Gate 0 — Publish a safe baseline

- Create the public `prairie-signal` repository under the intended GitHub account.
- Exclude `.env`, runtime data, local databases, caches, generated artifacts, credentials, and
  machine metadata.
- Add an intentional initial commit, repository description, branch protection, CI, dependency
  updates, and secret scanning.
- Decide whether source remains `UNLICENSED` or receives an explicit open-source license before
  inviting outside contributions.
- Record the public source URL separately from the eventual live application URL.

Exit: the exact tested source is recoverable from GitHub and CI passes on the remote commit.

### Gate 1 — Accept official weather statewide

- Close the remaining Phase 0 and Phase 1 acceptance gaps.
- Add the statewide region, search corpus, county identity, and dual-time-zone coverage.
- Run live NWS checks at the statewide reference locations.
- Add a whole-stack Compose test without mocking the API boundary.
- Inspect fresh, delayed, stale, partial, unavailable, and no-alert states.

Exit: any valid Nebraska coordinate can load honest official weather without a Lincoln-specific
assumption.

### Gate 2 — Display one statewide observed-radar frame

- Reproject one accepted MRMS frame to the Nebraska context grid.
- Generate deterministic versioned tiles with a documented dBZ palette and transparent no-data
  mask.
- Add read-only radar frame metadata and tile endpoints.
- Build a keyboard/touch-accessible map with state/county boundaries, cities, legend, source time,
  age, and explicit stale/unavailable behavior.
- Verify alignment at western, central, and eastern Nebraska reference points.

Exit: one observed frame is scientifically and visually accepted. It is labeled **Observed Radar**
and is not animated or described as a prediction.

### Gate 3 — Operational observed radar

- Schedule restartable MRMS ingestion at the verified source cadence.
- Retain a bounded frame history and generate an animation manifest atomically.
- Add play/pause, scrub, speed, reduced-motion, keyboard, and touch controls.
- Overlay official warning polygons without altering their meaning.
- Add precipitation-rate products only after source-contract and mask validation.
- Monitor frame delay, missing frames, tile errors, and storage retention.

Exit: statewide radar stays current through normal restarts and fails visibly during source or
pipeline outages.

### Gate 4 — Distinctive graphs and Nebraska experience

Build reusable, accessible chart primitives rather than isolated decorative graphics:

- Temperature and dew-point ribbon with observed/forecast transition and uncertainty bands
- Precipitation probability versus expected accumulation chart
- Wind/gust timeline with direction, thresholds, and local peak callouts
- Forecast-run evolution chart showing how guidance changed over time
- NBM/HRRR/NWS comparison view with provenance and initialization times
- Sunrise/daylight, heat, cold, fire-weather, and freeze context where official inputs support it
- County weather timeline combining official alerts, radar arrival, and forecast changes
- Public verification scorecards by lead time, threshold, season, county, and model version

The visual identity should feel Nebraska-specific through restrained prairie color, open-horizon
composition, county geography, local time, and storm-motion storytelling. Charts must remain
legible without color, support screen readers, and offer reduced motion and a compact table view.

Exit: the main forecast and radar experiences are useful on phone and desktop, visually distinct,
and meet accessibility/performance budgets.

### Gate 5 — Historical truth and evaluation platform

- Archive issue-time MRMS, NBM, HRRR, GOES/GLM, NWS forecasts, and verified surface observations
  under current source contracts.
- Build availability-time alignment so training never sees data that was unavailable at forecast
  issuance.
- Create event, year, season, geography, and storm-type holdouts across Nebraska.
- Add quality reports for gaps, radar coverage, station changes, model upgrades, and late data.
- Publish a fixed evaluation manifest before optimizing models.

Exit: every experimental forecast can be replayed and evaluated against future observations
without leakage or cherry-picking.

### Gate 6 — Nowcast baselines before AI

- Implement persistence, constant-motion, optical-flow, and ensemble advection baselines.
- Produce zero-to-two-hour probabilistic reflectivity/precipitation guidance.
- Archive every forecast before its valid time.
- Evaluate by lead time, intensity threshold, county, season, storm type, and radar-coverage quality.

Required radar metrics include Fractions Skill Score, CSI, ETS, probability of detection, false
alarm ratio, displacement, rain-arrival error, and reliability. Point forecasts add MAE/RMSE,
Brier score, CRPS, interval coverage, and calibration error as appropriate.

Exit: baseline strengths and failure cases are public and reproducible.

### Gate 7 — Promoted AI radar nowcast

- Train a reproducible spatiotemporal model only after the baseline dataset is accepted.
- Add HRRR, NBM, GOES imagery, and GLM lightning one source at a time; retain only inputs with
  measured incremental value and reliable operational availability.
- Produce ensembles or calibrated probabilities rather than a single falsely precise future.
- Use a champion/challenger registry with immutable datasets, checkpoints, metrics, and rollback.
- Promote only when unseen-event results beat the declared baselines and remain calibrated across
  western, central, and eastern Nebraska.

Exit: tiles are clearly labeled **AI Forecast Radar**, include model/initialization/valid time and
uncertainty, and pass the model-safety gate. Severe warnings remain exclusively official.

### Gate 8 — Nebraska point-forecast improvement

- Establish NWS, NBM, HRRR, persistence, and climatology baselines for temperature, dew point,
  wind, gusts, and precipitation.
- Train station- and terrain-aware corrections with calibrated quantiles.
- Validate rural and western Nebraska separately from the larger eastern cities.
- Blend corrections with official guidance only when the interface keeps provenance clear.

Exit: any accuracy improvement is supported by archived Nebraska-wide evidence and can be rolled
back by model version.

### Gate 9 — Reliability, cost, and launch

- Define development, staging, and production environments with immutable artifacts.
- Add CDN/object-storage retention rules, database backups, secret rotation, dependency scanning,
  uptime/data-freshness monitoring, and incident alerts.
- Load-test statewide traffic, tile bursts, severe-weather spikes, and ingestion backlogs.
- Test source outages, stale fallback, restore, model rollback, and cost ceilings.
- Publish data-source, model-card, verification, privacy, and limitation pages.

Exit: the public service has a monitored URL, tested recovery, an explicit operating budget, and
no unsupported availability or accuracy claim.

## Accuracy promotion rules

A candidate cannot be called better merely because one storm looks good. Promotion requires:

1. A frozen evaluation manifest and issue-time archive.
2. At least persistence, motion/optical-flow, raw numerical guidance, and current champion baselines.
3. Unseen event-, year-, geography-, and season-held-out results.
4. Aggregate and worst-segment results for western, central, and eastern Nebraska.
5. Calibration, misses, false alarms, displacement, arrival timing, and outage behavior.
6. Statistical uncertainty around score differences and no hidden regression at important hazards.
7. A model version, monitoring threshold, rollback trigger, and public limitations statement.

Until those rules pass, the product language is **experimental guidance**, never "Nebraska's most
accurate forecast."

## Immediate implementation order

1. Publish the safe GitHub baseline after GitHub authentication is restored.
2. Close and accept Phase 0/1 with the now-working live NWS configuration.
3. Add `nebraska-statewide-v1` and statewide location/time-zone tests.
4. Implement Milestone 2 Slice 2 as one statewide observed frame through tiles, API, and map.
5. Add continuous observed-radar history and animation.
6. Add the first shared forecast graph primitives.
7. Build the historical verification platform and only then begin predictive model promotion.
