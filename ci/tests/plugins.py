from ci.utils import BuildFailed
from ci.plugins.base import Builder
from ci.tests.utils import RepoTestCase, BuildDotShBuilder

class AlwaysSuccessfulBuilder(Builder):
    def run(self):
        pass

class BuilderTestCase(RepoTestCase):
    builder = AlwaysSuccessfulBuilder

    def setUp(self):
        super(BuilderTestCase, self).setUp()
        self.config = self.project.configurations.create()

    def execute_build(self, builder=None):
        self.build = self.config.builds.create(sha=self.repo.get_branches()['master'])
        builder = (builder or self.__class__.builder)(self.build)
        builder.execute_build()

    def _test_build(self, success):
        self.execute_build()
        self.assertEqual(self.build.was_successful, success)

    def test_build_success(self):
        self._test_build(success=True)

    def test_build_failure(self):
        """ A build that raises BuildFailed """
        class FailingBuild(Builder):
            def run(self):
                raise BuildFailed

        self.execute_build(FailingBuild)
        self.assertEqual(self.build.was_successful, False)

    def test_build_exception_1(self):
        self._test_build_exception(AttributeError)

    def test_build_exception_2(self):
        self._test_build_exception(TypeError)

    def test_build_exception_3(self):
        self._test_build_exception(ValueError)

    def _test_build_exception(self, exc, stderr_hook=None):
        """ A build that raises an unexpected exception """

        class BadBuilder(self.__class__.builder):
            def run(self):
                super(BadBuilder, self).run()
                raise exc

        self.assertRaises(exc, self.execute_build, BadBuilder)

        if stderr_hook:
            stderr_hook()

        stderr = self.build.stderr.read().strip().split('\n\n')
        self.assertEqual(stderr[0], '=' * 79)
        self.assertEqual(stderr[1], "Exception in django-ci/builder")
        self.assertTrue(stderr[2].startswith("Traceback (most recent"))


class CommandBasedBuilderTests(BuilderTestCase):
    builder = BuildDotShBuilder
    commits = [{'build.sh': "echo -n error >&2; echo -n output; test ! -e should_fail"}]

    def _test_build(self, success, stdout='output', stderr='error'):
        super(CommandBasedBuilderTests, self)._test_build(success)
        self.assertEqual(self.build.stdout.read(), stdout)
        if stderr:
            self.assertEqual(self.build.stderr.read(), stderr)

    def _test_build_exception(self, exc):
        def stderr_hook():
            self.assertEqual(self.build.stderr.read(len('error')), 'error')
        super(CommandBasedBuilderTests, self)._test_build_exception(exc, stderr_hook)

    def break_build(self):
        self.commit({'should_fail': ''})

    def test_tons_of_output(self):
        # XXX use thread + timeout
        self.commit({'build.sh': 'yes hello | head -n 100000'})
        self._test_build(True, stdout='hello\n'*100000, stderr=None)
