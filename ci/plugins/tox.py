from ci.plugins.base import Plugin, CommandBasedBuilder

class ToxBuilder(CommandBasedBuilder):
    cmd = ['tox']

class ToxPlugin(Plugin):
    def get_builders(self):
        return {'tox': ToxBuilder}
