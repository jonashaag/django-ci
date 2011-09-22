from sys import executable
from ci.plugins.base import Plugin, CommandBasedBuilder

class Unittest2Builder(CommandBasedBuilder):
    cmd = [executable, '-m', 'unittest', 'discover']

class Unittest2Plugin(Plugin):
    def get_builders(self):
        return {'unittest2': Unittest2Builder}
