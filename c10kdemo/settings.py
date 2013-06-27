# Django settings for c10kdemo project.

import os

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}

DEBUG = True

INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'c10ktools',
    'gameoflife',
)

LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
        },
    },
}

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
)

ROOT_URLCONF = 'c10kdemo.urls'

SECRET_KEY = os.environ.get('SECRET_KEY', 'whatever')

STATIC_URL = '/static/'

TIME_ZONE = 'Europe/Paris'

WSGI_APPLICATION = 'c10kdemo.wsgi.application'

del os
