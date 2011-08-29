from ci.utils import get_subclasses
from ci.plugins.base import Plugin

BUILDERS = {}

def load_plugins():
    for cls in get_subclasses(Plugin):
        plugin = cls()
        builders = plugin.get_builders()
        BUILDERS.update({b.name: b for b in builders})

from ci.plugins import tox

load_plugins()
