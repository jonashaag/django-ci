import os
from ci.plugins.defaultplugin import ShellBuilder
from .plugins import CommandBasedBuilderTests

class ShellBuilderTests(CommandBasedBuilderTests):
    builder = ShellBuilder

    def execute_build(self, *args):
        self.config.parameters = open(os.path.join(self.repo.path, 'build.sh')).read()
        self.config.save()
        super(ShellBuilderTests, self).execute_build(*args)

    def test_carriage_return_in_script(self):
        self.commit({'build.sh': 'echo -n 1; \r\n echo -n 2'})
        self.execute_build()
        self.assertEqual(self.build.stderr.read(), '')
        self.assertEqual(self.build.stdout.read(), '12')
