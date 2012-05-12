from django.conf import settings
from django.utils.importlib import import_module
from ci.utils import get_subclasses
from ci.plugins.base import *

BUILDERS = {}

def load_plugins():
    for cls in get_subclasses(Plugin):
        plugin = cls()
        BUILDERS.update(plugin.get_builders())

for plugin in settings.CI_PLUGINS:
    import_module(plugin)

load_plugins()
