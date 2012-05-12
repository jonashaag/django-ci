import random
from collections import OrderedDict, defaultdict
from datetime import datetime

from BeautifulSoup import BeautifulSoup

from django.test import TestCase
from django.contrib.auth.models import User

from ci.models import Project, Build
from ci.plugins import BUILDERS
from ci.tests.utils import BaseTestCase, RepoTestCase, BuildDotShBuilder

class BuildHookTests(RepoTestCase):
    commits = [{'build.sh': 'exit 0'}]

    def setUp(self):
        super(BuildHookTests, self).setUp()
        BUILDERS['sh'] = BuildDotShBuilder
        self.config1 = self.project.configurations.create(builder='sh', name='c1')
        self.config2 = self.project.configurations.create(builder='sh', name='c2')

    def assert404(self, response):
        self.assertEqual(response.status_code, 404)

    def test_project_404(self):
        self.assert404(self.client.get('/ci/user/no-such-project/update/'))
        self.assert404(self.client.get('/ci/no-such-user/p1/update/'))

    def test_hook(self):
        self.assertEqual(Build.objects.count(), 0)
        self.assertEqual(self.client.get('/ci/user/p1/update/').status_code, 200)
        self.assertEqual(Build.objects.count(), 2)
        self.assertEqual(Build.objects.filter(was_successful=True).count(), 2)

    def test_commit_in_multiple_branches(self):
        self.test_hook()
        self.commit({'foo': 'bar'})
        self.client.get('/ci/user/p1/update/')
        self.assertEqual(Build.objects.count(), 4)

        self.repo.make_branch('branch2')
        self.client.get('/ci/user/p1/update/')
        self.assertEqual(Build.objects.count(), 4)

    def test_commit_without_builds(self):
        self.project.configurations.all().delete()
        self.assertEqual(self.client.get('/ci/user/p1/update/').status_code, 200)
        self.assertEqual(Build.objects.count(), 0)

    def test_hook_failing_build(self):
        self.client.get('/ci/user/p1/update/')
        self.commit({'build.sh': 'exit 1'}, branch='fail')
        self.client.get('/ci/user/p1/update/')

        branches = self.repo.get_branches()

        self.assertEqual(Build.objects.filter(was_successful=False).count(), 2)
        for build in Build.objects.filter(was_successful=False):
            self.assertEqual(build.sha, branches['fail'])

        self.assertEqual(Build.objects.filter(was_successful=True).count(), 2)
        for build in Build.objects.filter(was_successful=True):
            self.assertEqual(build.sha, branches['master'])

    def test_configuration(self):
        self.config1.branches = ['branch2']
        self.config2.branches = ['notabranch']
        self.config1.save()
        self.config2.save()

        self.assertEqual(self.client.get('/ci/user/p1/update/').status_code, 200)
        self.assertEqual(Build.objects.count(), 0)

        self.commit({'build.sh': 'exit 1'}, branch='branch3')

        self.assertEqual(self.client.get('/ci/user/p1/update/').status_code, 200)
        self.assertEqual(Build.objects.count(), 0)

        self.repo.make_branch('branch2')
        self.client.get('/ci/user/p1/update/')
        self.assertEqual(Build.objects.count(), 1)
        self.assertEqual(Build.objects.get().was_successful, False)
        self.assertEqual(Build.objects.get().configuration, self.config1)
