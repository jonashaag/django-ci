from ci.plugins.base import Plugin, Builder

class ToxBuilder(Builder):
    cmd = ['tox']

class ToxPlugin(Plugin):
    def get_builders(self):
        return {'tox': ToxBuilder}
