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
        from itertools import product
        self.project = Project.objects.create(name='Project 1', slug='p1')
        self.config = self.project.configurations.create()
        for branch_n, commit_n in product([0, 1, 2], [0, 1, 2]):
            self.project.commits.create(
                vcs_id='c_%d_%d' % (branch_n, commit_n),
                branch='b_%d' % branch_n,
                was_successful=(commit_n==2)
            )

    def _test_base(self, state, state_text):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/ci/p1/')
        self.assertContains(response, 'class="project %s"' % state)
        self.assertContains(response, state_text)
        return response

    def _test_no_pending(self, *args):
        response = self._test_base(*args)
        self.assertNotContains(response, "Currently building")
        self.assertNotContains(response, "pending")

    def test_no_commits(self):
        Commit.objects.all().delete()
        self._test_no_pending('unknown', "No builds")

    def test_success(self):
        response = self._test_no_pending('successful', "State: all builds successful")

    def test_success_important_branches(self):
        Commit.objects.filter(branch='b_0').update(was_successful=False)
        self.project.important_branches = 'b_1, b_2'
        self.project.save()
        self._test_no_pending('successful', "State: all builds successful")

    def test_failure(self):
        Commit.objects.exclude(branch='b_2').update(was_successful=False)
        self._test_no_pending('failed', "State: 2/3 build(s) failed")

    def test_failure_important_branches(self):
        self.project.commits.create(vcs_id='b_3_1', branch='b_3')
        Commit.objects.update(was_successful=False)
        self.project.important_branches = 'b_0, b_2'
        self.project.save()
        self._test_no_pending('failed', "State: 2/2 build(s) failed")
        Commit.objects.filter(branch='b_0').update(was_successful=True)
        self._test_no_pending('failed', "State: 1/2 build(s) failed")

    def test_with_building(self):
        self.project.commits.create(vcs_id='b_3_1', branch='b_3')
        response = self._test_base('successful', "State: all builds successful")
        self.assertContains(response, "Currently building 1 commit(s)")
        self.assertNotContains(response, 'pending')
        self.project.commits.create(vcs_id='b_3_1', branch='b_4')
        response = self._test_base('successful', "State: all builds successful")
        self.assertContains(response, "Currently building 2 commit(s)")

        Commit.objects.filter(was_successful=True).update(was_successful=False)
        self.project.commits.create()
        response = self._test_base('failed', "State: 3/3 build(s) failed")
        self.assertContains(response, "Currently building 2 commit(s)")
        self.assertContains(response, "plus 1 more build(s) pending")
        self.project.commits.create()
        response = self._test_base('failed', "State: 3/3 build(s) failed")
        self.assertContains(response, "Currently building 2 commit(s)")
        self.assertContains(response, "plus 2 more build(s) pending")

    def test_with_pending(self):
        self.project.commits.create()
        response = self._test_base('successful', "State: all builds successful")
        self.assertNotContains(response, "Currently building")
        self.assertContains(response, "1 pending build(s)")
        self.project.commits.create()
        response = self._test_base('successful', "State: all builds successful")
        self.assertContains(response, "2 pending build(s)")
