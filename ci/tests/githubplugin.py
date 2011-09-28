import json
from django.test import TestCase
from ci.plugins.github import GitHubPostReceiveHook

class GitHubBuildHookTests(TestCase):
    def _test_hook(self, ref, changed_branches):
        class fake_request:
            POST = {'payload': json.dumps({'ref': ref})}
        hook = GitHubPostReceiveHook(fake_request)
        self.assertEqual(hook.get_changed_branches(), changed_branches)

    def test_master(self):
        self._test_hook('refs/heads/master', ['master'])

    def test_feature_x(self):
        self._test_hook('refs/heads/feature/x', ['feature/x'])
