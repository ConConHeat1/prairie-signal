# Data Sources

Only publicly and legally accessible sources may be integrated. Every adapter must keep transport
URLs, product identifiers, units, and parsing rules outside domain logic.

## Phase 1

### National Weather Service API

- Purpose: point metadata, official forecasts, observation stations, surface observations, and
  official alerts.
- Authority: [NWS API documentation](https://www.weather.gov/documentation/services-web-api).
- Requirements: a unique `User-Agent`, contact configuration, cache-friendly conditional
  requests, bounded retries, source and fetch timestamps, and no unbounded polling.
- Caveats: station observations are not hyperlocal and may be delayed; point forecasts normally
  cover about seven days; NWS radar-status endpoints are not display radar.

### U.S. Census Gazetteer

- Purpose: local, privacy-preserving city and ZIP/ZCTA search.
- Authority: [Census Gazetteer files](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2025.html).
- Imported products: Places and ZIP Code Tabulation Area representative coordinates.
- Caveat: a ZCTA is an approximation of a postal ZIP. The product labels this distinction.

## Milestone 2 Slice 1

### NOAA Multi-Radar/Multi-Sensor System (MRMS)

- Purpose: one current, observed, quality-controlled composite-reflectivity mosaic for the
  configured Lincoln-region scientific grid.
- Authority: NOAA/NSSL's operational MRMS product table and NOAA Open Data Dissemination's public
  `noaa-mrms-pds` bucket. The current verification date, source links, archive boundary, access
  contract, and operational caveats are maintained in the
  [detailed MRMS source dossier](data-sources/mrms.md).
- Implemented product: `MergedReflectivityQCComposite_00.50`, native dBZ, nominal two-minute
  cadence, regular `0.01`-degree geographic source grid.
- Access: anonymous HTTPS reads of canonical timestamped keys under the fixed CONUS/product prefix;
  mutable `latest` aliases are not scientific identities.
- Required handling: preserve original gzip/GRIB2 bytes and hashes; validate decoded product, time,
  unit, and grid; retain `-99` missing and `-999` no-coverage states separately; crop and reproject
  by the versioned configuration; publish derived Zarr atomically and without overwriting an
  existing scientific identity.
- Runtime: opt-in only through `make ingest-radar` and the Compose `radar` profile. The job handles
  one latest frame and exits; it is not a continuous operational feed.
- Current consumer boundary: normalized scientific storage and append-only provenance only. There
  is no public radar API, browser map, animation, rain-arrival output, or forecast model.
- Caveats: observed composite reflectivity is not precipitation rate, a ground observation, a
  warning, or a forecast. Radar geometry, blockage, outages, propagation, attenuation, bright band,
  mosaicking, quality control, missing objects, and delivery delay all limit interpretation.

The accepted implementation evidence and continuing claim boundary are recorded in the
[Slice 1 acceptance record](acceptance/MILESTONE_2_SLICE_1.md). The
[remaining implementation plan](REMAINING_IMPLEMENTATION_PLAN.md) defines later radar display and
prediction slices; code presence alone is not an accuracy claim or acceptance decision.

## Planned adapters

- Additional NOAA MRMS products, including precipitation products, only after the initial observed
  reflectivity slice is accepted.
- NEXRAD Level II/III for research-grade local radar features.
- NBM and HRRR or their operational successors for numerical guidance.
- GOES ABI/GLM for satellite and lightning features.
- SPC products for authoritative context and benchmarking.
- NOAA Storm Events for carefully qualified historical labels.
- Official METAR/ASOS sources for verification observations.
- Public elevation and land-cover sources for static features.

Exact product names, grids, formats, and licenses must be reverified from current official
documentation when each adapter is implemented. Commercial products must not be scraped.
