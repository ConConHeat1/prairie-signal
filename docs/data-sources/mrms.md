# NOAA Multi-Radar/Multi-Sensor System (MRMS)

- Verification date: 2026-07-31
- Adapter status: Milestone 2 Slice 1 accepted on 2026-07-31
- Initial product: `MergedReflectivityQCComposite_00.50`
- Initial domain: CONUS, cropped to the configured Lincoln region

This dossier separates facts verified from official NOAA/NSSL/NODD documentation from properties
that must be observed and recorded by the running ingestion system. Any operational discrepancy is
treated as a source-contract change, not silently normalized away.

## Official source name and authority

The source is the National Oceanic and Atmospheric Administration Multi-Radar/Multi-Sensor System,
an operational mosaic and multi-sensor product suite developed by the NOAA National Severe Storms
Laboratory and operated/disseminated through NOAA/NCEP.

Official references checked for this dossier:

- [NOAA/NSSL MRMS overview](https://www.nssl.noaa.gov/projects/mrms/)
- [NOAA/NSSL operational MRMS GRIB2 tables](https://www.nssl.noaa.gov/projects/mrms/operational/tables.php)
- [NOAA MRMS in the Registry of Open Data on AWS](https://registry.opendata.aws/noaa-mrms-pds/)
- [NCEP real-time Merged Reflectivity QC Composite directory](https://mrms.ncep.noaa.gov/2D/MergedReflectivityQCComposite/)
- [NOAA Virtual Lab MRMS home and product-guide links](https://vlab.noaa.gov/web/mrms)

The operational GRIB2 tables are the authority for the product identifier, frequency, units, and
sentinel values. The NODD registry is the authority for public cloud access. The live NCEP directory
is useful operational corroboration but is not the immutable archive used by this adapter.

## Access method and current service

Milestone 2 uses anonymous, unsigned S3 reads from the NOAA Open Data Dissemination copy:

```text
Bucket: s3://noaa-mrms-pds
Region: us-east-1
Authentication: none; unsigned public reads
```

The documented command-line access pattern is:

```bash
aws s3 ls --no-sign-request s3://noaa-mrms-pds/
```

The product archive key layout used by this adapter is:

```text
CONUS/{product}/YYYYMMDD/MRMS_{product}_YYYYMMDD-HHMMSS.grib2.gz
```

For the initial product:

```text
CONUS/MergedReflectivityQCComposite_00.50/YYYYMMDD/
MRMS_MergedReflectivityQCComposite_00.50_YYYYMMDD-HHMMSS.grib2.gz
```

Discovery must select timestamped keys. A mutable `latest` object or real-time-directory listing may
help operational diagnostics but must never become the scientific identity of an archived input.

The NODD registry also documents the `NewMRMSObject` SNS topic. Slice 1 does not subscribe to it;
scheduled/event-driven operation is a later slice.

## Geographic coverage

- Source domain used here: CONUS.
- Project subset: the versioned Lincoln and central Great Plains region configuration.
- Source grid: regular latitude/longitude grid at `0.01` degree spacing, approximately 1 km but not
  a constant metric distance in both axes.
- Normalized project grid: the repository's versioned regional grid. Reprojection is a derived step
  and must preserve the source grid metadata and missing/no-coverage mask.

The source is a geographic latitude/longitude GRIB2 grid, not a projected one-kilometer Cartesian
grid. `0.01` degree should not be mislabeled as exactly 1,000 meters. At Lincoln's latitude the
east-west cell size differs from the north-south cell size.

## Historical coverage

The NODD MRMS Version 12 archive layout is complete back to October 2020 for the intended archive
period. Slice 1 must not infer availability before that boundary or assume every expected two-minute
timestamp exists.

Runtime discovery must record:

- earliest and latest keys actually visible for the requested product/day;
- missing expected intervals;
- duplicate or revised-looking timestamps;
- object metadata needed to reproduce the selection.

Any historical backfill beyond the initial live sample is outside Slice 1 and requires its own
availability report.

## Update frequency and latency

- Documented product frequency: 2 minutes.
- Timestamp convention: UTC in the timestamped filename; the decoded GRIB2 valid time must also be
  read and compared with it.
- Typical latency: no bounded delivery latency or service-level guarantee is assumed.

Latency is an operational measurement, not a hard-coded source fact. For each object, ingestion must
record the source valid time, object/discovery time when available, download completion time, and
processing time. It must calculate observed data age and expose delayed/stale state from measured
age. Initial and ongoing latency distributions belong in operational reports after enough samples
exist.

## File format and integrity

- Transport object: gzip-compressed GRIB Edition 2 (`.grib2.gz`).
- Decoded scientific container: one or more GRIB2 messages as supplied by NOAA.
- Project raw storage: original bytes, immutable and content-addressed with a locally computed
  SHA-256 digest.
- Project normalized storage: versioned, chunked Zarr with data, mask, source metadata, and
  processing provenance.

An S3 ETag is recorded when available but is not treated as a portable content checksum. The adapter
must validate bounded object size, gzip integrity, successful GRIB2 parsing, expected product/grid,
and agreement between filename and decoded valid time before promotion to normalized storage.

## Product, variable, and units

| Field                   | Value                                                        |
| ----------------------- | ------------------------------------------------------------ |
| MRMS product            | `MergedReflectivityQCComposite_00.50`                        |
| Project variable        | Quality-controlled composite radar reflectivity              |
| Native units            | dBZ                                                          |
| Nominal source interval | 2 minutes                                                    |
| Source horizontal grid  | `0.01` degree regular latitude/longitude, approximately 1 km |
| Initial project use     | Observed radar only                                          |

Composite reflectivity is an observed mosaic product. It is not precipitation rate, rain
accumulation, a surface observation at a point, or a future forecast. It must not be labeled as any
of those products.

## Missing-value and quality behavior

The operational product contract uses distinct sentinel values:

| Native value | Meaning           | Required handling                                         |
| ------------ | ----------------- | --------------------------------------------------------- |
| `-99`        | Missing           | Set the missing-data mask; never convert to zero dBZ.     |
| `-999`       | No radar coverage | Preserve as a distinct no-coverage quality flag and mask. |

The raw native values remain recoverable through immutable source storage and normalized provenance.
Interpolation/reprojection may not invent coverage. A destination cell influenced only by masked
source cells remains masked. Any resampling method and edge behavior must be versioned and tested.

Reflectivity below a display threshold is not synonymous with missing data, and zero dBZ is a valid
numeric reflectivity value rather than a universal no-echo marker.

## Projection and normalization

The decoder must persist the complete source grid definition obtained from GRIB2, including
coordinate orientation, extent, spacing, dimensions, and scanning order. Normalization then:

1. applies sentinel masks before numeric resampling;
2. crops to a safe source window around the configured region;
3. reprojects onto the versioned project grid;
4. writes reflectivity, missing/no-coverage masks, and provenance together;
5. records the resampling method and processing version.

The configured project grid currently identifies `EPSG:5070` with nominal 1,000-meter resolution.
Runtime code must load and validate that configuration rather than relying on this document as its
configuration source.

## Licensing, public availability, and attribution

NOAA/NSSL describes the MRMS product suite as publicly available, and NODD provides it through a
public, anonymously readable bucket. Prairie Signal must attribute the data as NOAA MRMS and retain
the source link and access date in derived-product metadata.

Recommended dataset citation form, following the NODD registry:

```text
NOAA Multi-Radar/Multi-Sensor System (MRMS), accessed YYYY-MM-DD from
https://registry.opendata.aws/noaa-mrms-pds/.
```

This data-access statement does not grant or describe a license for MRMS software. The project uses
the published data product and must not copy third-party training material or software under an
assumed data license.

## Known operational changes

- MRMS product names, disseminated products, and formats have changed across operational releases.
- NOAA's operational GRIB2 table and product-guide pages may be updated on different schedules.
- Cloud key availability and the NCEP real-time directory are operational interfaces and must be
  probed rather than assumed from older tutorials.
- The Version 12 archive boundary in October 2020 is not permission to merge earlier products with
  different contracts without a separate adapter/version.

Every adapter release records the verification date, source URLs, selected product identifier, and
observed key sample. A product rename, sentinel change, grid change, cadence change, or timestamp
mismatch fails closed until reviewed.

## Reliability and scientific limitations

- Delivery can be late, missing, interrupted, or temporarily inconsistent; there is no assumed
  latency SLA.
- Radar coverage and quality vary with range, beam geometry, blockage, outages, anomalous
  propagation, attenuation, bright band, mosaicking, and quality-control behavior.
- A composite can emphasize reflectivity aloft and does not by itself prove precipitation is
  reaching the ground.
- The mosaic is not ground truth and must not be used as its own independent verification target
  without a documented evaluation design.
- Grid cells outside coverage must stay distinguishable from low or absent echoes.
- A timestamped object may arrive after its valid time; availability time, not just valid time, is
  required for leakage-safe training data.
- An upstream outage must yield an explicit delayed/stale/unavailable state rather than a fabricated
  clear-radar frame.

## Verified facts versus runtime measurements

### Verified from the official source contract on 2026-07-31

- Source identity and public NODD bucket
- Anonymous S3 access method and bucket region
- CONUS product/key naming convention
- `MergedReflectivityQCComposite_00.50` product identifier
- GRIB2 gzip format
- Two-minute documented frequency
- dBZ units
- Regular `0.01` degree latitude/longitude grid, approximately 1 km
- `-99` missing and `-999` no-coverage sentinel meanings
- Version 12 archive availability back to October 2020

### Must be measured or validated at runtime

- Current object availability and exact selected key
- Object size, ETag, last-modified time, and locally computed SHA-256
- Actual delivery latency and data age
- Filename time versus decoded GRIB2 valid time
- Decoded dimensions, coordinates, scanning order, and value distribution
- Daily gaps, duplicates, or operational changes
- Crop bounds, destination-grid alignment, resampling effects, and mask preservation
- Zarr chunking, atomic publication, idempotency, and processing duration

Runtime observations must be stored as provenance and copied into the Slice 1 acceptance record;
they must not be backfilled into this dossier as universal source guarantees.
