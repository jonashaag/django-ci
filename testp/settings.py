from django.conf.global_settings import *
from local_settings import *

TEMPLATE_CONTEXT_PROCESSORS += ('ci.context_processors.site',
                                'ci.context_processors.git_rev',)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.admin',

    'djkombu',
    'djcelery',

    'ci',
]

TEST_RUNNER = 'djcelery.contrib.test_runner.CeleryTestSuiteRunner'
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

CI_PLUGINS = ['ci.plugins.defaultplugin']
