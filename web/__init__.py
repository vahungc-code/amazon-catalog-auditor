import os
from flask import Flask
from .config import Config
from .database import init_db


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config.from_object(config_class)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)

    init_db(app)

    from .routes.main import main_bp
    from .routes.scan import scan_bp
    from .routes.history import history_bp
    from .routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(scan_bp, url_prefix='/scan')
    app.register_blueprint(history_bp, url_prefix='/history')
    app.register_blueprint(api_bp, url_prefix='/api')

    return app
