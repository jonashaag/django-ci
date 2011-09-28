from ci.plugins.defaultplugin import ShellBuilder
from .plugins import CommandBasedBuilderTests

class ShellBuilderTests(CommandBasedBuilderTests):
    builder = ShellBuilder

    def setUp(self):
        super(ShellBuilderTests, self).setUp()
        self.config.parameters = self.build_script
        self.config.save()
