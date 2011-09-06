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
        self.commit0 = self.project.commits.create(
            vcs_id='commit0',
            branch='branch0',
            was_successful=True
        )
        self.commit1 = self.project.commits.create(
            vcs_id='commit1',
            branch='branch1',
            was_successful=True
        )

    def _test_base(self, state):
        response = self.client.get(self.url)
        self.assertContains(response, '/ci/p1/')
        self.assertContains(response, 'class="project %s"' % state)
        if state == 'unknown':
            self.assertContains(response, "No builds")
        else:
            self.assertContains(response, "Latest build: %s" % state)
            self.assertContains(response, 'branch1/commit1')
        self.assertNotContains(response, 'branch0/commit0')
        return response

    def _test_no_pending(self, state):
        response = self._test_base(state)
        self.assertNotContains(response, 'Currently building')
        self.assertNotContains(response, 'pending')

    def test_no_commits(self):
        Commit.objects.all().delete()
        self._test_no_pending('unknown')

    def test_success(self):
        self._test_no_pending('successful')

    def test_failure(self):
        Commit.objects.update(was_successful=False)
        self._test_no_pending('failed')

    def test_with_building(self):
        commit = self.project.commits.create(vcs_id='commit2', branch='branch2')
        url = commit.get_absolute_url()
        response = self._test_base('successful')
        self.assertContains(response,
            'Currently building <a class=commit href="%s">branch2/commit2</a>' % url)
        self.assertNotContains(response, 'pending')

        Commit.objects.filter(was_successful=True).update(was_successful=False)
        self.project.commits.create()
        response = self._test_base('failed')
        self.assertContains(response, 'plus 1 more build(s) pending')
        self.project.commits.create()
        response = self._test_base('failed')
        self.assertContains(response, 'plus 2 more build(s) pending')

    def test_with_pending(self):
        self.project.commits.create()
        response = self._test_base('successful')
        self.assertNotContains(response, 'Currently building')
        self.assertContains(response, '1 pending build(s)')
        self.project.commits.create()
        response = self._test_base('successful')
        self.assertContains(response, '2 pending build(s)')
