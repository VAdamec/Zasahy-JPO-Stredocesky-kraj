# Fire Brno provider design

Date: 2026-10-16

## Decision and scope

Add Fire Brno as a second provider in the existing Home Assistant integration,
sharing the coordinator, sensors, and event interface. The user accepted this
architecture after the project and live backend review. This document records
the approved design and the implementation choices below. The user authorized
implementation without the unavailable writing-plans skill.

Keep Central Bohemian PKR support and existing installations compatible. The
first Fire Brno release covers incident polling, region/district filtering,
existing sensor equivalents, and new/updated incident events. Unit details,
images, map rendering, and coordinate conversion are outside this scope.

## Rationale

Separate provider modules isolate the different transports and data semantics
without duplicating Home Assistant entities and lifecycle code. Adding scattered
conditionals would couple the existing HTML parser to Fire Brno's JSON backend;
a separate integration would duplicate configuration, sensors, and event logic.

## Evidence from the review

- PKR currently uses an HTML table, a configured URL, and a name/place/time
  heuristic for incident matching.
- Fire Brno serves a JavaScript application with an unauthenticated JSON backend
  under `https://udalosti.firebrno.cz/api/`.
- A live date-range query with region `116` and repeated `stavIds` parameters
  returned 138 records. This is a sample, not proof of historical completeness.
- The site configuration defaults to region `116`, Jihomoravský.
- Lookup routes verified: `typy`, `podtypy`, `kraje`, `okresy`, `stavy`, and
  `konfigurace`.
- Sample incident fields include `id`, `casOhlaseni`, nullable `casVzniku`,
  `stavId`, `typId`, `podtypId`, `kraj`, `okres`, `obec`, `castObce`, `ORP`,
  `ulice`, `silnice`, and nullable `poznamkaProMedia`.
- No alarm level or last-updated timestamp was present in the sampled records.
- The frontend groups statuses `210, 400, 410, 420, 430, 440, 500` as open.
  Status `500` has the lookup label `Ukončená`, so display text cannot determine
  active state. The frontend's closed group is
  `510, 520, 600, 610, 620, 700, 710, 750, 760, 780, 800`.
- The existing comparison ignores a status change with an unchanged timestamp;
  this was reproduced with a parser smoke check.

These endpoints are an undocumented website backend. Their behavior and schema
must be validated and failures must be visible.

## Architecture and responsibilities

- `models.py`: shared incident representation and serialization. Move existing
  model behavior here with compatibility imports as needed.
- `providers/base.py`: small provider contract for asynchronous fetching and
  normalized results, plus source metadata and a provider factory.
- `providers/pkr.py`: existing PKR transport and parser adapter. Keep the current
  HTML parser and matching heuristic for records without native IDs.
- `providers/firebrno.py`: JSON requests, cached lookups, validation, filtering,
  field normalization, and source-specific status mapping.
- `coordinator.py`: provider selection, polling, first-refresh suppression,
  incident comparison, memory retention, and event dispatch.
- `sensor.py`: shared sensors over normalized incidents, with source-specific
  device metadata and documented timestamp semantics.
- `config_flow.py`: provider selection and provider-specific configuration.

Avoid a generic plugin framework: two implementations and one small contract are
sufficient. Parsing remains independently testable without Home Assistant.

## Configuration and compatibility

New entries select a source. PKR retains its filtered URL input. Fire Brno uses
region/district selectors backed by lookups, defaulting to Jihomoravský, with
district optional. Initially use one entry per selected region/district.

Store a provider identifier and source-specific settings. Treat entries lacking
a provider identifier as PKR. Preserve their configured URLs and existing config
entry unique IDs. Fire Brno duplicate detection uses provider plus normalized
filter values, excluding moving date bounds.

Preserve domain `pkr_zasahy`, entity unique IDs based on entry ID and sensor key,
and existing event names. Preserve existing PKR serialized fields and ID
behavior. Add provider/source metadata to event data without removing fields.
Update translations, manifest display name, README examples, and device
descriptions to cover both sources.

## Normalized data and event comparison

Keep existing Czech field names in serialized sensor/event data. Add optional
native incident ID, raw status ID, report time, update time, and source-specific
location/media fields. Resolve type/subtype IDs through lookups and normalize
category casing consistently with existing automation examples. Missing values
remain absent or null according to the documented schema, never fabricated.

For Fire Brno, use `(provider, native incident ID)` for stable identity. Compare
status and other meaningful normalized fields to detect updates even when report
time is unchanged. Retain the prior snapshot for event payloads. Do not include
fetch time in comparison. PKR retains its existing matching heuristic.

Keep `cas` compatible for PKR (source update time). For Fire Brno, use report time
and expose/document the distinction explicitly. Do not present observation time
as a source-provided update timestamp. Today/latest calculations follow the
documented per-source time. Alarm level is nullable for Fire Brno.

Map Fire Brno active state from numeric groups, preserving the display label.
Unknown statuses must not silently become inactive; represent the active state
as unknown and exclude them from a definitive active count or make that count
unavailable while reporting the reason. Final UI behavior for unknown status is
an implementation detail to settle consistently with Home Assistant conventions.

## Data flow and history

1. Resolve the provider from the entry, with PKR as the legacy default.
2. Fetch/cache required lookups for Fire Brno.
3. Query a bounded rolling history window, initially seven days in Europe/Prague
   converted to UTC request bounds. Include both open and closed status groups.
4. Validate and normalize the complete response, then sort by incident time.
5. On the first successful refresh, initialize memory without sending events.
6. On later refreshes, compare identities/content, emit events, and prune memory.
7. Publish shared coordinator data for all sensors.

Retain the current ten-minute default and five-minute minimum initially. Do not
fetch unit or image endpoints for every incident. Cache dictionaries with bounded
refresh and a controlled refresh attempt for unknown IDs.

The seven-day window must not be assumed to include every still-active incident.
Validate date-filter behavior and reconcile previously observed open incidents
where possible. An incident disappearing from a result is not evidence that it
closed. Explicitly document any completeness limit if older open records cannot
be retrieved reliably.

## Failures and edge cases

- Convert timeout, HTTP, invalid JSON, and schema failures into coordinator
  failures/unavailability, without publishing an empty success or clearing memory.
- Accept a valid empty result as zero matching incidents.
- Handle null optional fields and unknown dictionary values explicitly.
- A failed dictionary refresh may use a valid cache; no usable required lookup
  must produce an actionable failure rather than invented labels.
- Retain native IDs and raw status values for diagnosis and future mapping.
- Test day boundaries and daylight-saving transitions using aware datetimes.
- Preserve first-refresh suppression and bounded memory across both providers.

## Acceptance criteria and verification

1. Existing PKR entries load without reconfiguration and retain entity unique IDs.
2. Existing PKR fixture, sensor, and event behavior remains covered by regression
   checks.
3. Fire Brno setup supports the default region, optional district, duplicate
   detection, and useful connection/schema errors.
4. A native ID appearing after initialization emits one new-incident event;
   unchanged polling emits none.
5. The same ID changing status with unchanged `casOhlaseni` emits an update event.
6. Distinct IDs with identical names/places/times remain distinct incidents.
7. Open status `500` follows the site's open group despite its label.
8. Null fields, unknown lookup IDs/statuses, empty results, time boundaries,
   outages/recovery, and rolling-window disappearance have explicit tests.
9. First refresh/restart does not replay historical new-incident events.
10. Both sources provide the shared sensor set with correct device metadata,
    documented time semantics, and source identification in event data.

Use saved, minimized JSON fixtures and mocked HTTP responses for automated tests.
Perform a bounded live read and verify the rendered entities/events in a Home
Assistant test instance before claiming runtime support. During initial review,
parser smoke checks succeeded; the full suite was not run because the available
Python environment lacked pytest.

## Remaining validation

- Confirm maximum date range, truncation/pagination behavior, and handling of
  incidents open longer than the chosen window.
- Confirm native ID stability and report-time behavior across repeated snapshots.
- Verify any published backend usage requirements before release.
- Resolve unknown-status sensor presentation during implementation.


## Local implementation and validation

Implemented on branch `jmk`; changes are local, with no deployment or publication.
`origin` points at the VAdamec fork, and the original repository is `upstream`.

Implementation choices resolving the open design details:

- Source selection precedes the existing PKR URL form. Fire Brno has separate
  region/district selection steps; a whole region is supported.
- Legacy PKR entries require no migration. Existing entry and entity unique IDs
  remain unchanged, including user-renamed entity IDs.
- Fire Brno history covers seven local days. A second bounded query retrieves
  days 7–30 with all available status codes, retaining older open/unknown records
  and later closures for incidents observed open. This permits closure detection
  beyond the weekly window without inferring closure from disappearance.
- Tracking IDs survive temporary disappearance, with a 30-day bound on report
  times. Incidents reported more than 30 days ago are outside active coverage.
- An unknown status makes the active-count sensor `unknown`, and the affected
  records are exposed as `neznamy_stav`. Other sensors remain usable.
- Dictionary refreshes are cached for one day. Unknown codes trigger at most one
  extra refresh attempt per day; valid cached dictionaries survive refresh errors.
- Fire Brno's report timestamp is exposed as `cas` and `cas_ohlaseni`;
  `cas_aktualizace` is explicitly null. Alarm level remains null.
- Both languages, device/HACS metadata, fork links, and README have been updated.

Verification on Python 3.13 with Home Assistant 2026.2.3:

- 52 tests passed, including the existing parser/PKR checks, legacy config loading
  with a pre-existing entity ID, Fire Brno config/duplicate selection, shared
  sensors, new/update events with unchanged report timestamps, HTTP outage and
  recovery, restart suppression, lookup caching/failures, unknown statuses,
  nullable/malformed data, and Prague time/DST handling.
- Ruff checks passed, also with isolated default settings.
- A bounded live fetch through the implemented provider for Brno-město returned
  50 incidents, 50 distinct native IDs, one active incident, and no unknown
  statuses. These are a transient snapshot, not expected future counts.
- Automated tests use synthetic fixtures and mocked HTTP. No installed Home
  Assistant instance or rendered production dashboard was verified.

Backend pagination/truncation, long-term ID stability, and records older than
30 days remain outside the confirmed completeness guarantees. This limitation is
also documented in the README and setup UI.
