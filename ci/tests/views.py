from django.test import TestCase
from ci.models import BuildConfiguration, Build
from ci.plugins import BUILDERS, BUILD_HOOKS
from ci.plugins.base import BuildHook
from ci.tests.utils import BaseTestCase, default_branch, BuildDotShBuilder

class TestBuildHook(BuildHook):
    def get_changed_branches(self):
        return [default_branch]

class BuildHookTest(BaseTestCase):
    commits = [{'added': {'build.sh': 'exit 0'}}]

    def setUp(self):
        BUILDERS['sh'] = BuildDotShBuilder
        BUILD_HOOKS['testhook'] = TestBuildHook
        super(BuildHookTest, self).setUp()
        self.project.build_configurations.create(builder='sh')
        self.project.build_configurations.create(builder='sh')

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
        self.assertEqual(Build.objects.count(), 2)

    def test_hook_failing_build(self):
        self.commit({'changed': {'build.sh': 'exit 1'}, 'branch': 'fail'})
        class Hook(TestBuildHook):
            def get_changed_branches(self):
                return [default_branch, 'fail']
        BUILD_HOOKS['testhook'] = Hook

        self.assertEqual(self.client.get('/ci/p1/buildhook/testhook/').status_code, 200)
        self.assertEqual(Build.objects.count(), 4)

        failed_builds = Build.objects.filter(branch='fail')
        self.assertEqual(failed_builds.count(), 2)
        self.assertEqual([b.was_successful for b in failed_builds], [False, False])

        successful_builds = Build.objects.exclude(branch='fail')
        self.assertEqual(successful_builds.count(), 2)
        self.assertEqual([b.was_successful for b in successful_builds], [True, True])
