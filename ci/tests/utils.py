from os import rmdir
from shutil import rmtree
from tempfile import mkdtemp
from vcs.nodes import FileNode
from vcs.backends import get_repo
from django.test import TestCase
from ci.models import Project
from ci.plugins.base import CommandBasedBuilder

VCS = 'git'
default_branch = 'master'

class BuildDotShBuilder(CommandBasedBuilder):
    cmd = ['sh', 'build.sh']

class BaseTestCase(TestCase):
    commits = [{'message': 'Empty initial commit'}]

    def setUp(self):
        self.repo_path = mkdtemp()
        rmdir(self.repo_path)
        self.repo = get_repo(self.repo_path, VCS, create=True)
        self.commit(self.commits)

        self.project = Project.objects.create(
            slug='p1', vcs_type=VCS,
            repo_uri=self.repo_path
        )

    def commit(self, commits):
        if isinstance(commits, dict):
            commits = [commits]
        for commit in commits:
            commit = commit.copy()
            stage = self.repo.in_memory_changeset
            for name, content in commit.pop('added', {}).items():
                stage.add(FileNode(name, content))
            for name, content in commit.pop('changed', {}).items():
                stage.change(FileNode(name, content))
            commit.setdefault('author', 'Tim Tester')
            commit.setdefault('message', 'dummy message')
            stage.commit(**commit)

    def tearDown(self):
        rmtree(self.repo_path)
