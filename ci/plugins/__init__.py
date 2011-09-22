from django.conf import settings
from ci.utils import get_subclasses
from ci.plugins.base import Plugin

BUILDERS = {}
BUILD_HOOKS = {}

def load_plugins():
    for cls in get_subclasses(Plugin):
        plugin = cls()
        BUILDERS.update(plugin.get_builders())
        BUILD_HOOKS.update(plugin.get_build_hooks())

from ci.plugins import tox, unittest2
if settings.DEBUG:
    from ci.plugins import debug
load_plugins()
