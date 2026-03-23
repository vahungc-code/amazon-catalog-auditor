import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'instance', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max upload
    DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'catalog_web.db')
    ALLOWED_EXTENSIONS = {'xlsx', 'xlsm'}
    RESULTS_PER_PAGE = 50

    # Stripe configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    STRIPE_PRICE_AMOUNT = int(os.environ.get('STRIPE_PRICE_AMOUNT', '999'))  # in cents ($9.99)
    STRIPE_CURRENCY = os.environ.get('STRIPE_CURRENCY', 'usd')

    # Public base URL (used for email links generated outside of request context)
    BASE_URL = os.environ.get('BASE_URL', 'https://flatfileoptimizer.com')

    # SendGrid configuration
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
    SENDGRID_FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL', 'reports@onlinesellersolutions.com')
