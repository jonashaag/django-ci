from ci.plugins import Plugin, BuildHook

class DebugBuildHook(BuildHook):
    def get_changed_branches(self):
        return [self.request.GET['branches']]

class ToxPlugin(Plugin):
    def get_build_hooks(self):
        return {'debug': DebugBuildHook}
