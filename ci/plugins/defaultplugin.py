import os
from ci.plugins import Plugin, CommandBasedBuilder

class ShellBuilder(CommandBasedBuilder):
    def get_cmd(self):
        return [os.environ.get('SHELL', '/bin/sh'), '-c',
                '\n'.join(self.build.configuration.parameters.splitlines())]

class DefaultPlugin(Plugin):
    def get_builders(self):
        return {'shell': ShellBuilder}
