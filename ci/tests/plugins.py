from ci.utils import BuildFailed
from ci.plugins.base import Builder
from ci.tests.utils import BaseTestCase, BuildDotShBuilder, default_branch

class SimpleBuilder(Builder):
    def __init__(self, build, should_fail=False):
        self.should_fail = should_fail
        Builder.__init__(self, build)

    def run(self):
        if self.should_fail:
            raise BuildFailed


class BasePluginTest(BaseTestCase):
    builder = SimpleBuilder

    def setUp(self):
        super(BasePluginTest, self).setUp()
        self.config = self.project.configurations.create()
        commit = self.project.commits.create(branch=default_branch)
        self.build = commit.builds.create(configuration=self.config)
        self.builder = self.__class__.builder(self.build)

class BaseBuilderTests(BasePluginTest):
    def _test_build(self, success):
        self.builder.execute_build()
        changeset = self.repo.get_changeset()
        self.assertEqual(self.build.commit.vcs_id, changeset.raw_id)
        self.assertNotEqual(self.build.started, None)
        self.assertNotEqual(self.build.finished, None)
        self.assertEqual(self.build.was_successful, success)

    def test_successful_build(self):
        self._test_build(success=True)

    def test_failing_build(self):
        self.break_build()
        self._test_build(success=False)

    def break_build(self):
        self.builder.should_fail = True

class CommandBasedBuilderTests(BaseBuilderTests):
    builder = BuildDotShBuilder
    build_script = "echo error >&2; echo output; test ! -e should_fail"
    commits = [{'message': "Added build script",
                'added': {'build.sh': build_script}}]

    def _test_build(self, success):
        super(CommandBasedBuilderTests, self)._test_build(success)
        self.assertEqual(self.build.stdout.open().read(), 'output\n')
        self.assertEqual(self.build.stderr.open().read(), 'error\n')

    def break_build(self):
        self.commit({'message': "Broke the build", 'added': {'should_fail': ''}})
