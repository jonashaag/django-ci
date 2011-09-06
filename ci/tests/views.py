from django.test import TestCase
from ci.models import Project, BuildConfiguration, Commit, Build
from ci.plugins import BUILDERS, BUILD_HOOKS
from ci.plugins.base import BuildHook
from ci.tests.utils import BaseTestCase, default_branch, BuildDotShBuilder

class TestBuildHook(BuildHook):
    def get_changed_branches(self):
        return [default_branch]

class BuildHookTests(BaseTestCase):
    commits = [{'added': {'build.sh': 'exit 0'}}]

    def setUp(self):
        BUILDERS['sh'] = BuildDotShBuilder
        BUILD_HOOKS['testhook'] = TestBuildHook
        super(BuildHookTests, self).setUp()
        self.project.configurations.create(builder='sh')
        self.project.configurations.create(builder='sh')

    def tearDown(self):
        del BUILDERS['sh']
        #if 'testhook' in BUILD_HOOKS:
        del BUILD_HOOKS['testhook']

    def assert404(self, response):
        self.assertEqual(response.status_code, 404)

    def test_project_404(self):
        self.assert404(self.client.get('/ci/no-such-project/buildhook/somehook/'))

    def test_hook_404(self):
        self.assert404(self.client.get('/ci/p1/buildhook/no-such-hook/'))

    def test_hook(self):
        self.assertEqual(self.client.get('/ci/p1/buildhook/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.count(), 1)
        self.assertEqual(Build.objects.count(), 2)
        self.assertTrue(Commit.objects.get().was_successful)

    def test_hook_failing_build(self):
        self.commit({'changed': {'build.sh': 'exit 1'}, 'branch': 'fail'})
        class Hook(TestBuildHook):
            def get_changed_branches(self):
                return [default_branch, 'fail']
        BUILD_HOOKS['testhook'] = Hook

        self.assertEqual(self.client.get('/ci/p1/buildhook/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.count(), 2)
        self.assertEqual(Build.objects.count(), 4)

        failed_commit = Commit.objects.get(branch='fail')
        self.assertNotEqual(failed_commit.vcs_id, None)
        self.assertFalse(failed_commit.was_successful)
        failed_builds = failed_commit.builds.all()
        self.assertEqual(failed_builds.count(), 2)
        self.assertEqual([b.was_successful for b in failed_builds], [False, False])

        successful_commit = Commit.objects.exclude(branch='fail').get()
        self.assertNotEqual(successful_commit.vcs_id, None)
        self.assertTrue(successful_commit.was_successful)
        successful_builds = successful_commit.builds.all()
        self.assertEqual(successful_builds.count(), 2)
        self.assertEqual([b.was_successful for b in successful_builds], [True, True])

        Commit.objects.all().delete()
        config_0, config_1 = self.project.configurations.all()
        config_0.branches = ['fail']
        config_1.branches = default_branch
        config_0.save()
        config_1.save()
        self.assertEqual(self.client.get('/ci/p1/buildhook/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.get(branch='fail').builds.get().configuration, config_0)
        self.assertEqual(Commit.objects.exclude(branch='fail').get().builds.get().configuration, config_1)


class OverviewTests(TestCase):
    url = '/ci/'

    def setUp(self):
        self.project = Project.objects.create(name='Project 1', slug='p1')
        self.config = self.project.configurations.create()
        self.commit1 = self.project.commits.create(
            branch='master',
            vcs_id='abcdefghijkl',
            was_successful=True
        )

    def test_no_commits(self):
        Commit.objects.all().delete()
        response = self.client.get(self.url)
        self.assertContains(response, '/ci/p1/')
        self.assertContains(response, 'class="project unknown"')
        self.assertContains(response, "No builds")

    def test_success(self):
        response = self.client.get(self.url)
        self.assertContains(response, '/ci/p1/')
        self.assertContains(response, 'class="project successful"')
        self.assertContains(response, "Latest build: successful")

    def test_failure(self):
        Commit.objects.update(was_successful=False)
        response = self.client.get(self.url)
        self.assertContains(response, '/ci/p1/')
        self.assertContains(response, 'class="project failed"')
        self.assertContains(response, "Latest build: failed")
