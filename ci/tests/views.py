from datetime import datetime
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
        self.assertEqual(Commit.objects.count(), 0)
        self.assertEqual(self.client.get('/ci/p1/buildhook/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.count(), 1)
        self.assertEqual(Build.objects.count(), 2)
        self.assertTrue(Commit.objects.get().done)

    def test_hook_failing_build(self):
        self.commit({'changed': {'build.sh': 'exit 1'}, 'branch': 'fail'})
        class Hook(TestBuildHook):
            def get_changed_branches(self):
                return [default_branch, 'fail']
        BUILD_HOOKS['testhook'] = Hook

        self.assertEqual(self.client.get('/ci/p1/buildhook/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.count(), 2)
        self.assertEqual(Commit.objects.filter(done=False).count(), 0)
        self.assertEqual(Build.objects.count(), 4)

        failed_commit = Commit.objects.get(branch='fail')
        self.assertNotEqual(failed_commit.vcs_id, None)
        failed_builds = failed_commit.builds.all()
        self.assertEqual(failed_builds.count(), 2)
        self.assertEqual([b.was_successful for b in failed_builds], [False, False])

        successful_commit = Commit.objects.exclude(branch='fail').get()
        self.assertNotEqual(successful_commit.vcs_id, None)
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
        self.project = Project.objects.create(name='p1', slug='p1')
        b1c1 = self.project.commits.create(vcs_id='c1', branch='b1', done=True)
        b2c1 = self.project.commits.create(vcs_id='c1', branch='b2', done=True)
        for commit in [b1c1, b1c1, b2c1]:
            self.add_build(commit, done=True, success=True)

        # here to ensure that only builds/commits that belong to each project
        # are taken into account (rather than *all* builds/commits)
        p2 = Project.objects.create(name='p2', slug='p2')
        foo1 = p2.commits.create(branch='foo', vcs_id='foo1')
        bar1 = p2.commits.create(branch='bar', vcs_id='bar1')
        self.add_build(foo1, done=False)
        self.add_build(foo1, done=True, success=False)
        self.add_build(bar1, done=True, success=True)

    def add_build(self, commit, started=True, done=None, success=None):
        kwargs = {'configuration_id': 0}
        if started:
            assert done is not None
            kwargs['started'] = datetime.now()
        if done:
            kwargs['finished'] = datetime.now()
            assert success is not None
            kwargs['was_successful'] = success
        commit.builds.create(**kwargs)

    def _test_base(self, state, state_text):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response.content = response.content[:response.content.find('</div>')]
        self.assertContains(response, '/ci/p1/')
        self.assertContains(response, 'class="project %s"' % state)
        self.assertContains(response, state_text)
        return response

    def _test_no_pending(self, *args):
        response = self._test_base(*args)
        self.assertNotContains(response, "Currently executing")
        self.assertNotContains(response, "pending")

    def test_no_commits(self):
        Commit.objects.all().delete()
        self._test_no_pending('unknown', "No builds")

    def test_success(self):
        self._test_no_pending('successful', "State: all builds successful")

    def test_failure(self):
        Build.objects.filter(commit__branch='b1').update(was_successful=False)
        self._test_no_pending('failed', "State: 2/3 build(s) failed")

    def test_important_branches(self):
        b3c1 = self.project.commits.create(branch='b3', vcs_id='c1', done=True)
        self.add_build(b3c1, done=True, success=False)
        self._test_no_pending('failed', "State: 1/4 build(s) failed")
        self.project.important_branches = 'b1, b2'
        self.project.save()
        self._test_no_pending('successful', "State: all builds successful")
        self.project.important_branches = 'b3'
        self.project.save()
        self._test_no_pending('failed', "State: 1/1 build(s) failed")

    def test_with_building(self):
        building = self.project.commits.create(vcs_id='c2', branch='b2')
        self.add_build(building, done=False)
        response = self._test_base('successful', "State: all builds successful")
        self.assertContains(response, "Currently executing 1 build(s)")
        self.assertNotContains(response, 'pending')
        self.add_build(building, done=False)
        response = self._test_base('successful', "State: all builds successful")
        self.assertContains(response, "Currently executing 2 build(s)")

        pending = self.project.commits.create(branch='c3')
        self.add_build(pending, started=False)
        Build.objects.filter(was_successful=True).update(was_successful=False)
        response = self._test_base('failed', "State: 3/3 build(s) failed")
        self.assertContains(response, "Currently executing 2 build(s)")
        self.assertContains(response, "plus 1 more build(s) pending")
        self.add_build(pending, started=False)
        response = self._test_base('failed', "State: 3/3 build(s) failed")
        self.assertContains(response, "Currently executing 2 build(s)")
        self.assertContains(response, "plus 2 more build(s) pending")

    def test_with_pending(self):
        pending = self.project.commits.create(branch='c3')
        self.add_build(pending, started=False)
        response = self._test_base('successful', "State: all builds successful")
        self.assertNotContains(response, "Currently executing")
        self.assertContains(response, "1 pending build(s)")
        self.add_build(pending, started=False)
        response = self._test_base('successful', "State: all builds successful")
        self.assertContains(response, "2 pending build(s)")
