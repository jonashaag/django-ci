import os
import shutil
import traceback
import tempfile
from subprocess import Popen, PIPE

from ci import git
from ci.utils import BuildFailed

__all__ = ['Plugin', 'Builder', 'CommandBasedBuilder']

class Plugin(object):
    def get_builders(self):
        return {}

class Builder(object):
    def __init__(self, build):
        self.build = build

    def execute_build(self):
        try:
            self.setup_build()
            self.run()
            self.build.was_successful = True
        except BuildFailed:
            print 'fail'
            traceback.print_exc()
            self.build.was_successful = False
        except:
            traceback.print_exc()
            self.build.was_successful = False
            # XXX #16964
            if not self.build.stderr:
                self.build.stderr.save_named('', save=False)
            self.build.stderr.file.close()
            self.build.stderr.open('a')
            self.build.stderr.write(self.format_exception())
            self.build.stderr.close()
            self.build.stderr.open()
            raise
        finally:
            self.teardown_build()

    def setup_build(self):
        # TODO use init + checkout?
        self.local_repo = self.build.project.clone_repo()
        self.local_repo.checkout(self.build.sha)

    def teardown_build(self):
        try:
            shutil.rmtree(self.local_repo.path)
        except AttributeError:
            pass

    def format_exception(self):
        return '\n\n' + '\n\n'.join([
            '=' * 79,
            "Exception in django-ci/builder",
            traceback.format_exc()
        ])

    def run(self):
        raise NotImplementedError


class CommandBasedBuilder(Builder):
    def run(self):
        cmd = self.get_cmd()
        # XXX directly pipe into files
        proc = Popen(cmd, cwd=self.local_repo.path, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        self.build.stderr.save_named(stderr, save=False)
        self.build.stdout.save_named(stdout, save=False)
        if proc.returncode:
            raise BuildFailed("Command %s returned with code %d" % (cmd, proc.returncode))

    def get_cmd(self):
        return self.cmd
