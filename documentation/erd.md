# Entity-Relationship Diagram - UrbanTransit IQ

_Generated from the PK/FK definitions in `documentation/schemas/*.json`._

Reading guide: `||--o{` means *one* row on the left relates to *zero or more* rows on the right (Laravel: `hasMany` / `belongsTo`).

```mermaid
erDiagram
    STOPS ||--o{ ROUTES : "origin_stop_id"
    STOPS ||--o{ ROUTES : "destination_stop_id"
    ROUTES ||--o{ ROUTE_STOPS : "route_id"
    STOPS ||--o{ ROUTE_STOPS : "stop_id"
    ROUTES ||--o{ SCHEDULES : "route_id"
    SERVICE_CALENDAR ||--o{ SCHEDULES : "service_id"
    STOPS ||--o{ PASSENGERS : "home_stop_id"
    ROUTES ||--o{ TRIPS : "route_id"
    SERVICE_CALENDAR ||--o{ TRIPS : "service_id"
    SCHEDULES ||--o{ TRIPS : "schedule_id"
    VEHICLES ||--o{ TRIPS : "vehicle_id"
    VEHICLES ||--o{ TRIPS : "original_vehicle_id"
    TRIPS ||--o{ PASSENGER_COUNTS : "trip_id"
    ROUTES ||--o{ PASSENGER_COUNTS : "route_id"
    VEHICLES ||--o{ PASSENGER_COUNTS : "vehicle_id"
    STOPS ||--o{ PASSENGER_COUNTS : "max_load_stop_id"
    PASSENGERS ||--o{ TICKETS : "passenger_id"
    TRIPS ||--o{ TICKETS : "trip_id"
    ROUTES ||--o{ TICKETS : "route_id"
    STOPS ||--o{ TICKETS : "entry_stop_id"
    STOPS ||--o{ TICKETS : "exit_stop_id"
    TRIPS ||--o{ DELAYS : "trip_id"
    ROUTES ||--o{ DELAYS : "route_id"
    STOPS ||--o{ DELAYS : "stop_id"
    VEHICLES ||--o{ GPS_EVENTS : "vehicle_id"
    TRIPS ||--o{ GPS_EVENTS : "trip_id"
    ROUTES ||--o{ GPS_EVENTS : "route_id"
    STOPS ||--o{ GPS_EVENTS : "stop_id"
    STOPS {
        string stop_id PK
        string stop_name
        double latitude
        double longitude
        string zone
        string stop_type
        boolean has_shelter
        date opened_date
    }
    ROUTES {
        string route_id PK
        string route_code
        string route_name
        string route_type
        string origin_stop_id FK
        string destination_stop_id FK
        double distance_km
        double base_fare
        double fare_per_km
        date launch_date
        string status
    }
    ROUTE_STOPS {
        string route_id PK,FK
        integer direction PK
        integer stop_sequence PK
        string stop_id FK
        double distance_from_start_km
        double scheduled_offset_min
        boolean is_timing_point
    }
    SERVICE_CALENDAR {
        string service_id PK
        string service_name
        string day_type
        string timetable_period
        array days_of_week
        date start_date
        date end_date
        array exceptions
    }
    SCHEDULES {
        string schedule_id PK
        string route_id FK
        string service_id FK
        integer direction
        string period
        string start_time
        string end_time
        integer headway_min
        double planned_runtime_min
        date valid_from
        date valid_to
    }
    VEHICLES {
        string vehicle_id PK
        string registration_no
        string vehicle_type
        integer capacity_seated
        integer capacity_total
        string depot
        string fuel_type
        date commission_date
        boolean has_apc
        string status
    }
    PASSENGERS {
        string passenger_id PK
        string card_number
        string passenger_type
        string age_group
        string gender
        string home_stop_id FK
        date registration_date
        string card_status
    }
    TRIPS {
        string trip_id PK
        string route_id FK
        integer direction
        date service_date
        string service_id FK
        string schedule_id FK
        string vehicle_id FK
        string original_vehicle_id FK
        timestamp scheduled_departure
        timestamp scheduled_arrival
        timestamp actual_departure
        timestamp actual_arrival
        string trip_status
        string trip_type
        string cancellation_reason
    }
    PASSENGER_COUNTS {
        string count_id PK
        string trip_id FK
        string route_id FK
        date service_date
        string vehicle_id FK
        integer boardings
        integer alightings
        integer max_load
        string max_load_stop_id FK
        integer denied_boardings
        integer card_taps
    }
    TICKETS {
        string ticket_id PK
        string passenger_id FK
        string trip_id FK
        string route_id FK
        date service_date
        string entry_stop_id FK
        string exit_stop_id FK
        timestamp entry_time
        timestamp exit_time
        string ticket_type
        string fare_category
        double fare_amount
        string payment_method
    }
    DELAYS {
        string delay_id PK
        string trip_id FK
        string route_id FK
        string stop_id FK
        date service_date
        timestamp scheduled_arrival
        timestamp actual_arrival
        timestamp scheduled_departure
        timestamp actual_departure
        double delay_minutes
        string delay_reason
        string record_source
    }
    GPS_EVENTS {
        string event_id PK
        string vehicle_id FK
        string trip_id FK
        string route_id FK
        string stop_id FK
        timestamp event_time
        string event_type
        double latitude
        double longitude
        double speed_kmh
    }
```

## How the tables fit together

- **Network (reference) tables:** `stops`, `routes`, `route_stops` (ordered stops per route and direction), `vehicles`, `passengers`.
- **Planning tables:** `service_calendar` (which days a timetable runs) and `schedules` (headways and planned running times per route, direction, service and period).
- **Operations (event) tables:** `trips` (each planned journey, with scheduled vs actual times and vehicle), and four tables derived from the same trip simulation: `passenger_counts` (APC loads), `tickets` (card tap-in/tap-out), `delays` (stop-level deviations with reasons) and `gps_events` (vehicle positions).
