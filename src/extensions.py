"""Flask extension singletons, created unbound and attached in `create_app`.

Keeping them here (not in app.py) lets models and blueprints import `db` without a
circular import. NestJS analogy: shared providers registered once in the root module.
"""

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()          # ORM (Eloquent / TypeORM)
migrate = Migrate()        # schema migrations (php artisan migrate / typeorm migration:run)
jwt = JWTManager()         # JWT issuing and verification (Sanctum / @nestjs/jwt)
cors = CORS()              # CORS headers for the React dev server
