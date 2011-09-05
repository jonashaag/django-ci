from ci.plugins.base import Builder
from ci.utils import BuildFailed
from ci.tests.utils import BaseTestCase, BuildDotShBuilder, default_branch

class SimpleBuilder(Builder):
    def __init__(self, build, should_fail=False):
        self.should_fail = should_fail
        Builder.__init__(self, build)

    def run(self):
        if self.should_fail:
            raise BuildFailed


class BasePluginTest(BaseTestCase):
    def setUp(self):
        super(BasePluginTest, self).setUp()
        config = self.project.configurations.create()
        commit = self.project.commits.create(branch=default_branch)
        self.build = commit.builds.create(configuration=config)
        self.builder = SimpleBuilder(self.build)

class BaseBuilderTests(BasePluginTest):
    def _test_build(self, success):
        self.builder.execute_build()
        self.assertEqual(self.build.commit.vcs_id, self.repo.get_changeset().raw_id)
        self.assertNotEqual(self.build.started, None)
        self.assertNotEqual(self.build.finished, None)
        self.assertEqual(self.build.was_successful, success)

    def test_successful_build(self):
        self._test_build(success=True)

    def test_failing_build(self):
        self.builder.should_fail = True
        self._test_build(success=False)

class CommandBasedBuilderTests(BasePluginTest):
    commits = [{'message': 'Added build script',
                'added': {'build.sh': 'echo error >&2; echo output; test ! -e should_fail'}}]

    def setUp(self):
        super(CommandBasedBuilderTests, self).setUp()
        self.builder = BuildDotShBuilder(self.build)

    def _test_build(self, success):
        self.builder.execute_build()
        self.assertEqual(self.build.was_successful, success)
        self.assertEqual(self.build.stdout.open().read(), 'output\n')
        self.assertEqual(self.build.stderr.open().read(), 'error\n')

    def test_successful_build(self):
        self._test_build(success=True)

    def test_failing_build(self):
        self.commit({'message': 'Broke the build', 'added': {'should_fail': ''}})
        self._test_build(success=False)
