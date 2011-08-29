from os import rmdir
from tempfile import mkdtemp
from shutil import rmtree
from vcs.backends import get_repo
from vcs.nodes import FileNode
from django.test import TestCase
from ci.models import Project, BuildConfiguration, Build
from ci.plugins.base import Builder, CommandBasedBuilder
from ci.utils import BuildFailed

class FailingBuilder(Builder):
    def run(self):
        raise BuildFailed

class BuildDotShBuilder(CommandBasedBuilder):
    cmd = ['sh', 'build.sh']

class BaseTestCase(TestCase):
    vcs = 'git'
    commits = [{'message': 'Empty initial commit'}]

    def setUp(self):
        self.setup_repo()

        self.project = Project.objects.create(
            slug='p1',
            vcs_type=self.vcs,
            repo_uri=self.repo_path
        )
        self.config = self.project.build_configurations.create()
        self.build = self.config.builds.create()
        self.builder = Builder(self.build)

    def setup_repo(self):
        self.repo_path = mkdtemp()
        rmdir(self.repo_path)
        self.repo = get_repo(self.repo_path, self.vcs, create=True)
        self.commit(self.commits)

    def commit(self, commits):
        for commit in commits:
            commit = commit.copy()
            stage = self.repo.in_memory_changeset
            for name, content in commit.pop('added', {}).iteritems():
                stage.add(FileNode(name, content))
            commit.setdefault('author', 'Tim Tester')
            stage.commit(**commit)

    def tearDown(self):
        rmtree(self.repo_path)


class TestBaseBuilder(BaseTestCase):
    def _test_build(self, success):
        self.builder.execute_build()
        self.assertEqual(self.build.commit, self.repo.get_changeset().raw_id)
        self.assertNotEqual(self.build.started, None)
        self.assertNotEqual(self.build.finished, None)
        self.assertEqual(self.build.was_successful, success)

    def test_successful_build(self):
        self._test_build(success=True)

    def test_failing_build(self):
        self.builder = FailingBuilder(self.build)
        self._test_build(success=False)

class TestCommandBasedBuilder(BaseTestCase):
    commits = [{'message': 'Added build script',
                'added': {'build.sh': 'echo error >&2; echo output; test ! -e should_fail'}}]

    def setUp(self):
        super(TestCommandBasedBuilder, self).setUp()
        self.builder = BuildDotShBuilder(self.build)

    def _test_build(self, success):
        self.builder.execute_build()
        self.assertEqual(self.build.was_successful, success)
        self.assertEqual(self.build.stdout.open().read(), 'output\n')
        self.assertEqual(self.build.stderr.open().read(), 'error\n')

    def test_successful_build(self):
        self._test_build(success=True)

    def test_failing_build(self):
        self.commit([{'message': 'Broke the build', 'added': {'should_fail': ''}}])
        self._test_build(success=False)
