from os import rmdir
from shutil import rmtree
from tempfile import mkdtemp
from vcs.nodes import FileNode
from vcs.backends import get_repo

from django.test import TestCase
from django.contrib.auth.models import User

from ci.models import Project
from ci.plugins.base import CommandBasedBuilder

VCS = 'git'
default_branch = 'master'

class BuildDotShBuilder(CommandBasedBuilder):
    cmd = ['sh', 'build.sh']


class BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user', 'user@domain.tld', 'secret')
        self.project = self.create_project(slug='p1')

    def create_project(self, **kwargs):
        kwargs.update({'owner': self.user, 'vcs_type': VCS})
        return Project.objects.create(**kwargs)

class RepoTestCase(BaseTestCase):
    commits = [{'message': "Empty initial commit"}]

    def setUp(self):
        super(RepoTestCase, self).setUp()
        self.repo_path = mkdtemp()
        rmdir(self.repo_path)
        self.repo = get_repo(self.repo_path, VCS, create=True)
        self.commit(self.commits)

        self.project.repo_uri = self.repo_path
        self.project.save()

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
            commit.setdefault('author', "Tim Tester")
            commit.setdefault('message', "dummy message\n\nwith multiple lines")
            stage.commit(**commit)

    def tearDown(self):
        rmtree(self.repo_path)
