from flask import Flask


def create_app(config="app.config.Config"):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config["PATH_DOWNLOADS"].mkdir(parents=True, exist_ok=True)

    from app.extensions import db, migrate
    from app import models  # noqa: F401  (registra os modelos para o Flask-Migrate)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.web import web
    from app.routes.api import api

    app.register_blueprint(web)
    app.register_blueprint(api)

    from app.cli import fila_cli

    app.cli.add_command(fila_cli)

    return app
