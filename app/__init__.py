from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    from app.model import db, migrate
    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.web import web
    app.register_blueprint(web)

    from app.routes.api import api
    app.register_blueprint(api)

    return app

