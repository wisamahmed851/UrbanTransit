"""UrbanTransit IQ backend (Flask + MySQL).

Layout, with the Laravel / NestJS equivalents:

| here              | Laravel                    | NestJS                     |
|-------------------|----------------------------|----------------------------|
| `app.create_app`  | `bootstrap/app.php`        | `NestFactory.create()`     |
| `blueprints/*`    | route groups + controllers | modules + controllers      |
| `models/*`        | Eloquent models            | TypeORM entities           |
| `services/*`      | service classes            | providers                  |
| `security.py`     | middleware / policies      | guards + `@Roles()`        |
| `errors.py`       | `app/Exceptions/Handler`   | global exception filter    |
| `database/migrations` (Flask-Migrate) | `database/migrations` | TypeORM migrations |
"""
