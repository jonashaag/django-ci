import json
from ci.plugins import Plugin, BuildHook

class GitHubPlugin(Plugin):
    def get_build_hooks(self):
        return {'github': GitHubPostReceiveHook}

class GitHubPostReceiveHook(BuildHook):
    def get_changed_branches(self):
        try:
            payload = json.loads(self.request.POST['payload'])
            return [payload['ref'].replace('refs/heads/', '')]
        except (KeyError, ValueError):
            return []
