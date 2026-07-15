import os
from pathlib import Path

# --- CHEMINS ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SÉCURITÉ ---
# Clé secrète : prend celle de Render, sinon utilise une clé locale par défaut
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-temporary-key')

# DEBUG est True en local, mais devient False automatiquement sur Render (grâce à la variable d'env)
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# En prod (DEBUG=False), on restreint les hôtes. En local, on accepte tout.
if not DEBUG:
    ALLOWED_HOSTS = ['medical-moyanoli.onrender.com', '.onrender.com'] # Remplace par ton vrai nom de domaine Render
else:
    ALLOWED_HOSTS = ['*'] # Permet de tester sur localhost, 127.0.0.1 ou ton IP locale (192.168.1.77)

# --- APPLICATIONS ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps',  # Ton application Medical-Moyanoli
    'crispy_forms',
    'crispy_bootstrap4',
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

# --- MIDDLEWARE ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Gère les fichiers statiques en prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'conf.urls'

# --- TEMPLATES ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'conf.wsgi.application'

# --- BASE DE DONNÉES ---
# Utilise SQLite en local pour développer facilement, et PostgreSQL en production
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Configuration pour la production (Render).
    # Il est fortement conseillé d'utiliser dj-database-url pour lire l'URL de base de données Render.
    import dj_database_url
   

# --- VALIDATION DES MOTS DE PASSE ---
# Désactivé en local (plus simple pour créer des comptes tests) mais activé en Prod
if not DEBUG:
    AUTH_PASSWORD_VALIDATORS = [
        {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    ]
else:
    AUTH_PASSWORD_VALIDATORS = []

# --- INTERNATIONALISATION ---
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Kinshasa'  # Heure de Kinshasa
USE_I18N = True
USE_L10N = True
USE_TZ = False

DATE_INPUT_FORMATS = [
    '%d/%m/%Y', # Format jour/mois/année (ex: 15/05/2026)
    '%Y-%m-%d', # Format standard de la base de données
]

# --- FICHIERS STATIQUES (CSS, JS) ---
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Whitenoise gère le stockage uniquement en production (quand DEBUG est False)
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# --- FICHIERS MÉDIAS (Photos, Uploads) ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- AUTHENTIFICATION --- 
LOGIN_REDIRECT_URL = '/dashboard/'
LOGIN_URL = '/login/'
LOGOUT_REDIRECT_URL = '/home/'

# --- SÉCURITÉ EN PRODUCTION ---
if not DEBUG:
    # Active ces options si ton site est bien configuré en HTTPS (fortement recommandé sur Render !)
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
else:
    # Sécurité relâchée pour le développement local
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'