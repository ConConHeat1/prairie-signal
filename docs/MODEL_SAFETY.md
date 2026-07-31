# Model and Hazard Safety

Phase 1 contains no AI weather output. These rules are established before model work begins.

## Non-negotiable separation

- A model cannot create, replace, cancel, paraphrase, or visually impersonate an official alert.
- Official NWS alerts remain more prominent than every experimental score.
- Observed radar, extrapolation, numerical simulation, and AI forecast radar use distinct labels
  and visual treatments.
- Every predicted radar frame must say **AI Forecast Radar**.
- A tornado probability cannot trigger an official-warning presentation.

Wherever experimental severe-weather guidance is displayed, show this exact message:

> Experimental AI guidance. Not an official warning. Follow National Weather Service alerts and
> local emergency instructions during dangerous weather.

## Public severe-guidance gate

Experimental severe guidance remains internal until all of the following are documented:

1. Complete event-, year-, and geography-held-out evaluation.
2. Reliability calibration and precision-recall results at operationally useful thresholds.
3. Misses, false alarms, displacement, and lead time by event type and season.
4. Data-availability and temporal-leakage audits.
5. Independent meteorological and product-safety review.
6. A rollback owner, model version, monitoring thresholds, and incident procedure.

AI severe notifications are out of scope until a later, separately approved gate.
