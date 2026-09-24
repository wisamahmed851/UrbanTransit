# Data Dictionary - UrbanTransit IQ

_Generated from `documentation/schemas/*.json` by `data_generator/schema_registry.py`. Do not edit by hand: change the JSON schema and regenerate._

Timestamps are local transit time (Asia/Karachi, UTC+05:00) written as `YYYY-MM-DD HH:MM:SS` without a zone suffix. Dates are `YYYY-MM-DD`.

| Table | Format | Primary key | Description |
|---|---|---|---|
| [stops](#stops) | csv | stop_id | Physical bus stops and stations with their locations. Reference (dimension) table. |
| [routes](#routes) | csv | route_id | Bus routes with length, fare rules and launch date. Reference table. |
| [route_stops](#route_stops) | csv | route_id, direction, stop_sequence | Ordered list of stops served by each route in each direction (bridge table between routes and stops). |
| [service_calendar](#service_calendar) | json | service_id | Service calendars: which days a timetable runs, plus holiday exceptions. Stored as one JSON array (nested exceptions). |
| [schedules](#schedules) | csv | schedule_id | Timetable rules: for a route, direction, service calendar and time period, how often buses depart and how long the trip is planned to take. |
| [vehicles](#vehicles) | csv | vehicle_id | Bus fleet with capacity. Reference table. |
| [passengers](#passengers) | csv | passenger_id | Registered smart-card holders (anonymised; no names). Cash riders are not registered and appear only in passenger_counts. |
| [trips](#trips) | csv | trip_id | One row per planned vehicle journey on a date: vehicle assignment and scheduled vs actual departure/arrival at the terminals. Split by month. |
| [passenger_counts](#passenger_counts) | csv | count_id | Trip-level passenger counts from automatic passenger counters (APC): boardings, alightings, peak on-board load. One row per operated trip on an APC-equipped vehicle. Split by month. |
| [tickets](#tickets) | csv | ticket_id | Smart-card ticketing transactions: one row per registered-passenger journey, with tap-in (entry) and tap-out (exit). Split by month. |
| [delays](#delays) | csv | delay_id | Delay (and early-running) records at stop level: scheduled vs actual arrival and departure at the stop where the deviation was logged, with a reason. Split by month. |
| [gps_events](#gps_events) | jsonl | event_id | Simulated vehicle positions (AVL pings) at stop arrivals/departures and mid-segment, for a 7-day sample window. JSON Lines, one file per day. |

## stops

Physical bus stops and stations with their locations. Reference (dimension) table.

- **File layout:** `raw_data/<mode>/stops/stops.csv`
- **Primary key:** `stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| stop_id | `string` | no | PK | Stop ID, e.g. S0001 |
| stop_name | `string` | no |  | Human-readable stop name |
| latitude | `double` | no |  | WGS84 latitude (degrees) |
| longitude | `double` | no |  | WGS84 longitude (degrees) |
| zone | `string` | no |  | Fare zone A (centre), B or C (outer) by distance from the city centre |
| stop_type | `string` | no |  | hub | terminal | regular |
| has_shelter | `boolean` | no |  | Whether the stop has a passenger shelter |
| opened_date | `date` | no |  | Date the stop entered service (mid-year for new stops) |

## routes

Bus routes with length, fare rules and launch date. Reference table.

- **File layout:** `raw_data/<mode>/routes/routes.csv`
- **Primary key:** `route_id`
- **Foreign keys:** `origin_stop_id` -> `stops.stop_id`; `destination_stop_id` -> `stops.stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| route_id | `string` | no | PK | Route ID, e.g. R001 |
| route_code | `string` | no |  | Public route number shown on the bus, e.g. BRT1, T12, L34, F07 |
| route_name | `string` | no |  | Origin - destination name |
| route_type | `string` | no |  | brt | trunk | local | feeder |
| origin_stop_id | `string` | no | FK | First stop in direction 0 |
| destination_stop_id | `string` | no | FK | Last stop in direction 0 |
| distance_km | `double` | no |  | One-way route length in km (road distance) |
| base_fare | `double` | no |  | Boarding fare in PKR |
| fare_per_km | `double` | no |  | Distance-based fare component in PKR per km |
| launch_date | `date` | no |  | Date the route started service (mid-year for new routes) |
| status | `string` | no |  | active |

## route_stops

Ordered list of stops served by each route in each direction (bridge table between routes and stops).

- **File layout:** `raw_data/<mode>/route_stops/route_stops.csv`
- **Primary key:** `route_id, direction, stop_sequence`
- **Foreign keys:** `route_id` -> `routes.route_id`; `stop_id` -> `stops.stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| route_id | `string` | no | PK FK | Route |
| direction | `integer` | no | PK | 0 = origin to destination, 1 = return |
| stop_sequence | `integer` | no | PK | Position of the stop on the route, 1..n with no gaps |
| stop_id | `string` | no | FK | Stop |
| distance_from_start_km | `double` | no |  | Road distance from the first stop of this direction |
| scheduled_offset_min | `double` | no |  | Planned off-peak minutes from the first stop |
| is_timing_point | `boolean` | no |  | Stop used as a timetable timing point |

## service_calendar

Service calendars: which days a timetable runs, plus holiday exceptions. Stored as one JSON array (nested exceptions).

- **File layout:** `raw_data/<mode>/service_calendar/service_calendar.json`
- **Primary key:** `service_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| service_id | `string` | no | PK | Service ID, e.g. WKDY_AUT25 |
| service_name | `string` | no |  | Readable name |
| day_type | `string` | no |  | weekday | saturday | sunday | holiday | ramadan_weekday |
| timetable_period | `string` | no |  | autumn_2025 | winter_spring_2026 | summer_2026 | all_year | ramadan_2026 | autumn_2026 |
| days_of_week | `array<string>` | no |  | Days the service normally runs, e.g. ["mon","tue"] |
| start_date | `date` | no |  | First valid date |
| end_date | `date` | no |  | Last valid date |
| exceptions | `array<struct<date:date,exception_type:string,reason:string>>` | no |  | Dates where the service is removed or added (public holidays, Ramadan overlay) |

## schedules

Timetable rules: for a route, direction, service calendar and time period, how often buses depart and how long the trip is planned to take.

- **File layout:** `raw_data/<mode>/schedules/schedules.csv`
- **Primary key:** `schedule_id`
- **Foreign keys:** `route_id` -> `routes.route_id`; `service_id` -> `service_calendar.service_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| schedule_id | `string` | no | PK | Schedule ID, e.g. SCH000001 |
| route_id | `string` | no | FK | Route |
| service_id | `string` | no | FK | Service calendar this timetable belongs to |
| direction | `integer` | no |  | 0 or 1 |
| period | `string` | no |  | early | am_peak | midday | pm_peak | evening |
| start_time | `string` | no |  | Period start, HH:MM (Spark has no time-of-day type) |
| end_time | `string` | no |  | Period end, HH:MM |
| headway_min | `integer` | no |  | Planned minutes between departures |
| planned_runtime_min | `double` | no |  | Planned end-to-end running time in minutes |
| valid_from | `date` | no |  | First date the timetable applies |
| valid_to | `date` | no |  | Last date the timetable applies |

## vehicles

Bus fleet with capacity. Reference table.

- **File layout:** `raw_data/<mode>/vehicles/vehicles.csv`
- **Primary key:** `vehicle_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| vehicle_id | `string` | no | PK | Vehicle ID, e.g. V0001 |
| registration_no | `string` | no |  | Number plate |
| vehicle_type | `string` | no |  | articulated | standard | minibus |
| capacity_seated | `integer` | no |  | Seats |
| capacity_total | `integer` | no |  | Seats + standing (design capacity) |
| depot | `string` | no |  | Home depot |
| fuel_type | `string` | no |  | diesel | cng | hybrid | electric |
| commission_date | `date` | no |  | Date the vehicle entered service |
| has_apc | `boolean` | no |  | Fitted with an automatic passenger counter (produces passenger_counts) |
| status | `string` | no |  | active | spare |

## passengers

Registered smart-card holders (anonymised; no names). Cash riders are not registered and appear only in passenger_counts.

- **File layout:** `raw_data/<mode>/passengers/passengers.csv`
- **Primary key:** `passenger_id`
- **Foreign keys:** `home_stop_id` -> `stops.stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| passenger_id | `string` | no | PK | Passenger ID, e.g. P000001 |
| card_number | `string` | no |  | Smart-card number |
| passenger_type | `string` | no |  | regular | student | senior | disabled |
| age_group | `string` | no |  | under_18 | 18_25 | 26_40 | 41_60 | 60_plus |
| gender | `string` | no |  | M | F | X (not stated) |
| home_stop_id | `string` | no | FK | Stop nearest to the registered home address |
| registration_date | `date` | no |  | Card registration date (no travel before this) |
| card_status | `string` | no |  | active | blocked | expired |

## trips

One row per planned vehicle journey on a date: vehicle assignment and scheduled vs actual departure/arrival at the terminals. Split by month.

- **File layout:** `raw_data/<mode>/trips/trips_YYYY-MM.csv`
- **Primary key:** `trip_id`
- **Foreign keys:** `route_id` -> `routes.route_id`; `service_id` -> `service_calendar.service_id`; `schedule_id` -> `schedules.schedule_id`; `vehicle_id` -> `vehicles.vehicle_id`; `original_vehicle_id` -> `vehicles.vehicle_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| trip_id | `string` | no | PK | Trip ID, e.g. T2509000123 (yymm + running number) |
| route_id | `string` | no | FK | Route (empty only if corrupted) |
| direction | `integer` | no |  | 0 or 1 |
| service_date | `date` | no |  | Operating date |
| service_id | `string` | no | FK | Service calendar in force |
| schedule_id | `string` | no | FK | Timetable row that produced this trip |
| vehicle_id | `string` | yes | FK | Vehicle that operated (or was assigned to) the trip |
| original_vehicle_id | `string` | yes | FK | Set when the vehicle was changed (breakdown swap): the vehicle originally assigned |
| scheduled_departure | `timestamp` | no |  | Planned departure from the first stop |
| scheduled_arrival | `timestamp` | no |  | Planned arrival at the last stop |
| actual_departure | `timestamp` | yes |  | Actual departure (null if cancelled) |
| actual_arrival | `timestamp` | yes |  | Actual arrival (null if cancelled) |
| trip_status | `string` | no |  | completed | cancelled |
| trip_type | `string` | no |  | regular | event_extra |
| cancellation_reason | `string` | yes |  | Reason when cancelled |

## passenger_counts

Trip-level passenger counts from automatic passenger counters (APC): boardings, alightings, peak on-board load. One row per operated trip on an APC-equipped vehicle. Split by month.

- **File layout:** `raw_data/<mode>/passenger_counts/passenger_counts_YYYY-MM.csv`
- **Primary key:** `count_id`
- **Foreign keys:** `trip_id` -> `trips.trip_id`; `route_id` -> `routes.route_id`; `vehicle_id` -> `vehicles.vehicle_id`; `max_load_stop_id` -> `stops.stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| count_id | `string` | no | PK | Count record ID, e.g. PC2509000123 |
| trip_id | `string` | no | FK | Trip counted |
| route_id | `string` | no | FK | Route |
| service_date | `date` | no |  | Operating date |
| vehicle_id | `string` | no | FK | Vehicle whose APC produced the count |
| boardings | `integer` | no |  | Passengers who boarded during the trip (all fare types) |
| alightings | `integer` | no |  | Passengers who alighted (APC sensor, small counting noise) |
| max_load | `integer` | no |  | Highest number of passengers on board at once |
| max_load_stop_id | `string` | no | FK | Stop where the load peaked |
| denied_boardings | `integer` | no |  | Passengers left behind because the bus was full |
| card_taps | `integer` | no |  | Smart-card validations recorded by the on-board validator (should equal ticket rows for the trip) |

## tickets

Smart-card ticketing transactions: one row per registered-passenger journey, with tap-in (entry) and tap-out (exit). Split by month.

- **File layout:** `raw_data/<mode>/tickets/tickets_YYYY-MM.csv`
- **Primary key:** `ticket_id`
- **Foreign keys:** `passenger_id` -> `passengers.passenger_id`; `trip_id` -> `trips.trip_id`; `route_id` -> `routes.route_id`; `entry_stop_id` -> `stops.stop_id`; `exit_stop_id` -> `stops.stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| ticket_id | `string` | no | PK | Ticket transaction ID, e.g. TK2509000000123 |
| passenger_id | `string` | no | FK | Card holder |
| trip_id | `string` | no | FK | Trip travelled on |
| route_id | `string` | yes | FK | Route (empty only if corrupted) |
| service_date | `date` | no |  | Operating date of the trip |
| entry_stop_id | `string` | no | FK | Tap-in stop |
| exit_stop_id | `string` | no | FK | Tap-out stop |
| entry_time | `timestamp` | no |  | Tap-in time |
| exit_time | `timestamp` | no |  | Tap-out time |
| ticket_type | `string` | no |  | single | day_pass | monthly_pass |
| fare_category | `string` | no |  | standard | student | senior | disabled |
| fare_amount | `double` | no |  | Amount charged in PKR (0 when covered by a pass) |
| payment_method | `string` | no |  | smart_card | mobile_qr |

## delays

Delay (and early-running) records at stop level: scheduled vs actual arrival and departure at the stop where the deviation was logged, with a reason. Split by month.

- **File layout:** `raw_data/<mode>/delays/delays_YYYY-MM.csv`
- **Primary key:** `delay_id`
- **Foreign keys:** `trip_id` -> `trips.trip_id`; `route_id` -> `routes.route_id`; `stop_id` -> `stops.stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| delay_id | `string` | no | PK | Delay record ID, e.g. D2509000123 |
| trip_id | `string` | no | FK | Trip |
| route_id | `string` | no | FK | Route |
| stop_id | `string` | no | FK | Stop where the deviation was recorded |
| service_date | `date` | no |  | Operating date |
| scheduled_arrival | `timestamp` | no |  | Planned arrival at the stop |
| actual_arrival | `timestamp` | no |  | Actual arrival at the stop |
| scheduled_departure | `timestamp` | no |  | Planned departure from the stop |
| actual_departure | `timestamp` | no |  | Actual departure from the stop |
| delay_minutes | `double` | no |  | actual_arrival - scheduled_arrival in minutes (negative = early) |
| delay_reason | `string` | no |  | traffic_congestion | passenger_boarding | junction_bottleneck | late_vehicle | weather_fog | weather_rain | special_event | road_works | vehicle_breakdown | early_running | disruption |
| record_source | `string` | no |  | avl (automatic vehicle location) | driver_report | controller |

## gps_events

Simulated vehicle positions (AVL pings) at stop arrivals/departures and mid-segment, for a 7-day sample window. JSON Lines, one file per day.

- **File layout:** `raw_data/<mode>/gps_events/gps_events_YYYY-MM-DD.jsonl`
- **Primary key:** `event_id`
- **Foreign keys:** `vehicle_id` -> `vehicles.vehicle_id`; `trip_id` -> `trips.trip_id`; `route_id` -> `routes.route_id`; `stop_id` -> `stops.stop_id`

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| event_id | `string` | no | PK | Event ID, e.g. G251110000000123 |
| vehicle_id | `string` | no | FK | Vehicle |
| trip_id | `string` | no | FK | Trip being operated |
| route_id | `string` | no | FK | Route |
| stop_id | `string` | yes | FK | Stop for stop_arrival/stop_departure events, null in transit |
| event_time | `timestamp` | no |  | Ping time |
| event_type | `string` | no |  | stop_arrival | stop_departure | in_transit |
| latitude | `double` | no |  | Latitude with GPS noise |
| longitude | `double` | no |  | Longitude with GPS noise |
| speed_kmh | `double` | no |  | Instantaneous speed |
