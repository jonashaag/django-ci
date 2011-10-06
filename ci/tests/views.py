import random
from BeautifulSoup import BeautifulSoup
from datetime import datetime
from django.test import TestCase
from ci.models import Project, Commit, Build
from ci.plugins import BUILDERS, BUILD_HOOKS
from ci.plugins.base import BuildHook
from ci.tests.utils import BaseTestCase, VCS, default_branch, BuildDotShBuilder

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
        super(BuildHookTests, self).tearDown()
        del BUILDERS['sh']
        #if 'testhook' in BUILD_HOOKS:
        del BUILD_HOOKS['testhook']

    def assert404(self, response):
        self.assertEqual(response.status_code, 404)

    def test_project_404(self):
        self.assert404(self.client.get('/ci/no-such-project/buildhooks/somehook/'))

    def test_hook_404(self):
        self.assert404(self.client.get('/ci/p1/buildhooks/no-such-hook/'))

    def test_hook(self):
        self.assertEqual(Commit.objects.count(), 0)
        self.assertEqual(self.client.get('/ci/p1/buildhooks/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.count(), 1)
        self.assertEqual(Build.objects.count(), 2)
        self.assertTrue(Commit.objects.get().was_successful)

    def test_hook_failing_build(self):
        self.commit({'changed': {'build.sh': 'exit 1'}, 'branch': 'fail'})
        class Hook(TestBuildHook):
            def get_changed_branches(self):
                return [default_branch, 'fail']
        BUILD_HOOKS['testhook'] = Hook

        self.assertEqual(self.client.get('/ci/p1/buildhooks/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.count(), 2)
        self.assertEqual(Commit.objects.filter(was_successful=None).count(), 0)
        self.assertEqual(Build.objects.count(), 4)

        failed_commit = Commit.objects.get(branch='fail')
        self.assertEqual(failed_commit.short_message, 'dummy message')
        self.assertNotEqual(failed_commit.vcs_id, None)
        failed_builds = failed_commit.builds.all()
        self.assertEqual(failed_builds.count(), 2)
        self.assertEqual([b.was_successful for b in failed_builds], [False, False])

        successful_commit = Commit.objects.exclude(branch='fail').get()
        self.assertEqual(failed_commit.short_message, 'dummy message')
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
        self.assertEqual(self.client.get('/ci/p1/buildhooks/testhook/').status_code, 200)
        self.assertEqual(Commit.objects.get(branch='fail').builds.get().configuration, config_0)
        self.assertEqual(Commit.objects.exclude(branch='fail').get().builds.get().configuration, config_1)


class OverviewTests(TestCase):
    url = '/ci/'

    def setUp(self):
        self.project = Project.objects.create(name='p1', slug='p1')
        b1c1 = self.project.commits.create(vcs_id='c1', branch='b1', was_successful=True)
        b2c1 = self.project.commits.create(vcs_id='c1', branch='b2', was_successful=True)
        for commit in [b1c1, b1c1, b2c1]:
            self.add_build(commit, done=True, success=True)

        # here to ensure that only builds/commits that belong to each project
        # are taken into account (rather than *all* builds/commits)
        p2 = Project.objects.create(name='p2', slug='p2')
        foo1 = p2.commits.create(branch='foo', vcs_id='foo1', was_successful=False)
        bar1 = p2.commits.create(branch='bar', vcs_id='bar1', was_successful=True)
        self.add_build(foo1, started=False)
        self.add_build(bar1, done=False)
        self.add_build(foo1, done=True, success=False)
        self.add_build(bar1, done=True, success=True)

    def add_build(self, commit, started=True, done=None, success=None):
        kwargs = {'configuration_id': random.randint(1, 9999)}
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
        html = response.content
        content_start = html.find('<div id=content>')
        first_project_end = html.find('</a>', content_start)
        response.content = html[content_start:first_project_end]
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/ci/p1/')
        self.assertContains(response, 'class="project %s"' % state)
        self.assertContains(response, state_text)
        return response

    def _test_no_pending(self, *args):
        response = self._test_base(*args)
        self.assertNotContains(response, "active")
        self.assertNotContains(response, "pending")

    def test_no_commits(self):
        Commit.objects.all().delete()
        self._test_no_pending('unknown', "no builds")

    def test_success(self):
        self._test_no_pending('successful', "all builds successful")

    def test_failure(self):
        Build.objects.filter(commit__branch='b1').update(was_successful=False)
        self._test_no_pending('failed', "failures: 2/3")

    def test_important_branches(self):
        b3c1 = self.project.commits.create(branch='b3', vcs_id='c1', was_successful=False)
        self.add_build(b3c1, done=True, success=False)
        self._test_no_pending('failed', "failures: 1/4")
        self.project.important_branches = 'b1, b2, doesnotexist'
        self.project.save()
        self._test_no_pending('successful', "all builds successful")
        self.project.important_branches = 'b3'
        self.project.save()
        self._test_no_pending('failed', "failures: 1/1")

    def test_with_active(self):
        active = self.project.commits.create(vcs_id='c2', branch='b2')
        self.add_build(active, done=False)
        response = self._test_base('successful', "all builds successful")
        self.assertContains(response, "active: 1")
        self.assertNotContains(response, 'pending')
        self.add_build(active, done=False)
        response = self._test_base('successful', "all builds successful")
        self.assertContains(response, "active: 2")

        pending = self.project.commits.create(branch='c3')
        self.add_build(pending, started=False)
        Build.objects.filter(was_successful=True).update(was_successful=False)
        response = self._test_base('failed', "failures: 3/3")
        self.assertContains(response, "active: 2")
        self.assertContains(response, "pending: 1")
        self.add_build(pending, started=False)
        response = self._test_base('failed', "failures: 3/3")
        self.assertContains(response, "active: 2")
        self.assertContains(response, "pending: 2")

    def test_with_pending(self):
        pending = self.project.commits.create(branch='c3')
        self.add_build(pending, started=False)
        response = self._test_base('successful', "all builds successful")
        self.assertNotContains(response, "active")
        self.assertContains(response, "pending: 1")
        self.add_build(pending, started=False)
        response = self._test_base('successful', "all builds successful")
        self.assertContains(response, "pending: 2")


class ProjectDetailsTests(TestCase):
    # XXX show branches without builds (+ pending + active)
    url = '/ci/my-super-cool-project/'

    def setUp(self):
        # Project with two branches '$default_branch' and 'dev'.
        # Both branches get tested; docs are generated for '$default_branch' only.
        self.project = Project.objects.create(
            name='My super cool Project',
            slug='my-super-cool-project',
            vcs_type=VCS
        )
        self.project.configurations.create(name='tests')
        self.project.configurations.create(name='docs', branches=[default_branch])

        d1 = self.project.commits.create(branch='dev', vcs_id='dev1', was_successful=False)
        m1 = self.project.commits.create(branch=default_branch, vcs_id='def1', was_successful=False)

        # default: docs built successfully but the tests failed
        self.add_build(m1, 'tests', was_successful=False)
        self.add_build(m1, 'docs', was_successful=True)

        # dev: tests failed
        self.add_build(d1, 'tests', was_successful=False)

        self.branch_list = [
            (default_branch, {'latest': ('def1', [('tests', 'failed'), ('docs', 'successful')])}),
            ('dev', {'latest': ('dev1', [('tests', 'failed')])}),
        ]

    def add_build(self, commit, config, **kwargs):
        kwargs.setdefault('started', datetime.now())
        kwargs.setdefault('finished', datetime.now())
        config = self.project.configurations.get(name=config)
        return commit.builds.create(configuration=config, **kwargs)

    def assertBranchList(self, expected_branch_list):
        html = self.client.get(self.url).content
        dom = BeautifulSoup(html)
        branch_list = []

        for idx, node in enumerate(dom.findAll(None, 'latest')):
            commits = {}
            # Latest commit:
            branch, latest_commit = [span.text.strip() for span in
                                     node.find('a').findAll('span')]
            latest = [(b.text.strip(), b['class'].split()[1])
                      for b in node.findAll(None, 'build')]
            commits['latest'] = (latest_commit, latest)
            # Latest stable commit:
            stable = node.nextSibling.nextSibling
            if stable is not None:
                commits['stable'] = stable.findAll(None, 'commit')[0].text.strip()
            self.assertEqual(expected_branch_list[idx], (branch, commits))

    def test_1(self):
        self.assertBranchList(self.branch_list)
        self.project.commits.filter(branch=default_branch).update(was_successful=True)
        self.assertBranchList(self.branch_list)

    def test_last_stable(self):
        # dev: tests succeeded
        self.project.commits.filter(vcs_id='dev1').update(was_successful=True)
        d2 = self.project.commits.create(branch='dev', vcs_id='dev2', was_successful=False)
        self.add_build(d2, 'tests', was_successful=False)
        self.assertBranchList([
            self.branch_list[0],
            ('dev', {'latest': ('dev2', [('tests', 'failed')]), 'stable': 'dev1'})
        ])

    def test_important_branches(self):
        # if given, 'important_branches' specifies the branch order
        self.project.important_branches = ['dev', default_branch, 'doesnotexist']
        self.project.save()
        self.assertBranchList(self.branch_list[::-1])
        self.project.important_branches = 'dev'
        self.project.save()
        self.assertBranchList([self.branch_list[1]])

    def test_with_active_and_pending(self):
        active = self.project.commits.create(branch=default_branch, vcs_id='active')
        active.builds.create(started=datetime.now(), configuration_id=-1)
        self.assertBranchList(self.branch_list)

        response = self.client.get(self.url)
        self.assertContains(response, "active: 1")
        self.assertNotContains(response, "pending")
        active.builds.create(configuration_id=-2)

        response = self.client.get(self.url)
        self.assertContains(response, "active: 1")
        self.assertContains(response, "pending: 1")


class CommitDetailsTests(TestCase):
    url = '/ci/testproject/builds/1/'

    def setUp(self):
        self.project = Project.objects.create(slug='testproject')
        for name in ['good', 'bad', 'active', 'pending']:
            self.project.configurations.create(name=name)
        self.commit = self.project.commits.create(branch='testbranch', vcs_id='testid')

    def add_build(self, config, kwargs):
        config = self.project.configurations.get(name=config)
        config.builds.create(commit=self.commit, **kwargs)

    def test_1(self):
        now = datetime.now()
        builds = [
            ('active', {'started': now}),
            ('good', {'started': now, 'finished': now, 'was_successful': True}),
            ('bad', {'started': now, 'finished': now, 'was_successful': False}),
            ('pending', {})
        ]
        random.shuffle(builds)
        for config, kwargs in builds:
            self.add_build(config, kwargs)
        self.assertBuildList(['bad', 'good', 'active', 'pending'])

    def assertBuildList(self, l):
        html = self.client.get(self.url).content
        dom = BeautifulSoup(html)
        self.assertEqual([li.find('span').text for li in dom.findAll('li')], l)
