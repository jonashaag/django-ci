from ci.plugins.defaultplugin import ShellBuilder
from .plugins import CommandBasedBuilderTests

class ShellBuilderTests(CommandBasedBuilderTests):
    builder = ShellBuilder

    def execute_build(self):
        self.config.parameters = self.repo.get_changeset().get_file_content('build.sh')
        self.config.save()
        self.builder.execute_build()

    def test_carriage_return_in_script(self):
        self.commit({'changed': {'build.sh': 'echo -n 1; \r\n echo -n 2'}})
        self.execute_build()
        self.assertEqual(self.build.stderr.read(), '')
        self.assertEqual(self.build.stdout.read(), '12')
