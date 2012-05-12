import os
import shutil
import tempfile

from django.test import TestCase
from django.contrib.auth.models import User

from ci import git
from ci.models import Project
from ci.plugins.base import CommandBasedBuilder


class BuildDotShBuilder(CommandBasedBuilder):
    cmd = ['sh', 'build.sh']


class BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('user', 'user@domain.tld', 'secret')
        self.project = self.create_project(slug='p1')

    def create_project(self, **kwargs):
        kwargs.update({'owner': self.user})
        return Project.objects.create(**kwargs)

class RepoTestCase(BaseTestCase):
    commits = []

    def setUp(self):
        super(RepoTestCase, self).setUp()
        self.repo = git.Repo.init(tempfile.mkdtemp())
        self.project.repo_uri = self.repo.path
        self.project.save()

        self.repo.commit('empty initial commit', empty=True)
        for commit in self.commits:
            self.commit(commit)

    def commit(self, files={}, **kwargs):
        for filename, content in files.items():
            with open(os.path.join(self.repo.path, filename), 'w') as f:
                f.write(content)

        kwargs.setdefault('branch', 'master')
        self.repo.commit("dummy message\n\nwith multiple lines",
                         files=files.keys(), **kwargs)

    def tearDown(self):
        if os.path.exists(self.repo.path):
            shutil.rmtree(self.repo.path)
