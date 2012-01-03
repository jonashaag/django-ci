from ci.utils import BuildFailed
from ci.plugins.base import Builder
from ci.tests.utils import RepoTestCase, BuildDotShBuilder, default_branch

class SimpleBuilder(Builder):
    def __init__(self, build):
        self.exception = None
        Builder.__init__(self, build)

    def run(self):
        if self.exception:
            raise self.exception

class BuilderTestCase(RepoTestCase):
    builder = SimpleBuilder

    def setUp(self):
        super(BuilderTestCase, self).setUp()
        self.config = self.project.configurations.create()
        commit = self.project.commits.create(branch=default_branch)
        self.build = commit.builds.create(configuration=self.config)
        self.builder = self.__class__.builder(self.build)

    def execute_build(self):
        self.builder.execute_build()

    def _test_build(self, success):
        self.execute_build()
        changeset = self.repo.get_changeset()
        self.assertEqual(self.build.commit.vcs_id, changeset.raw_id)
        self.assertEqual(self.build.was_successful, success)

    def test_successful_build(self):
        self._test_build(success=True)

    def test_build_failure(self):
        """ A build that raises BuildFailed """
        self.break_build()
        self._test_build(success=False)

    def _test_build_exception(self, exc, stderr_hook=None):
        """ A build that raises an unexpected exception """
        class BadBuilder(self.__class__.builder):
            def run(self):
                super(BadBuilder, self).run()
                raise exc
        self.builder = BadBuilder(self.build)
        self.assertRaises(exc, self._test_build, success=False)
        if stderr_hook:
            stderr_hook()
        stderr = self.build.stderr.read().strip().split('\n\n')
        self.assertEqual(stderr[0], '=' * 79)
        self.assertEqual(stderr[1], "Exception in django-ci/builder")
        self.assertTrue(stderr[2].startswith("Traceback (most recent"))

    def test_build_exception_1(self):
        self._test_build_exception(AttributeError)

    def test_build_exception_2(self):
        self._test_build_exception(TypeError)

    def test_build_exception_3(self):
        self._test_build_exception(ValueError)

    def break_build(self):
        self.builder.exception = BuildFailed


class CommandBasedBuilderTests(BuilderTestCase):
    builder = BuildDotShBuilder
    build_script = "echo -n error >&2; echo -n output; test ! -e should_fail"
    commits = [{'message': "Added build script",
                'added': {'build.sh': build_script}}]

    def _test_build(self, success, stdout='output', stderr='error'):
        super(CommandBasedBuilderTests, self)._test_build(success)
        self.assertEqual(self.build.stdout.read(), stdout)
        self.assertEqual(self.build.stderr.read(), stderr)

    def _test_build_exception(self, exc):
        def stderr_hook():
            self.assertEqual(self.build.stderr.read(len('error')), 'error')
        super(CommandBasedBuilderTests, self)._test_build_exception(exc, stderr_hook)

    def break_build(self):
        self.commit({'message': "Broke the build", 'added': {'should_fail': ''}})

    def test_tons_of_output(self):
        # XXX use thread + timeout
        self.commit({'changed': {'build.sh': 'yes hello | head -n 100000'}})
        self.execute_build()
        # use raw 'assert' here to avoid spamming the console in case of a failure
        assert self.build.stdout.read() ==  'hello\n'*100000
