import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'instance', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max upload
    DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'catalog_web.db')
    ALLOWED_EXTENSIONS = {'xlsx', 'xlsm'}
    RESULTS_PER_PAGE = 50
