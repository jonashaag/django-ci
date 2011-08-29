from os import rmdir
from datetime import datetime
from subprocess import Popen, PIPE
from tempfile import mkdtemp
from shutil import rmtree
from vcs import get_backend
from django.core.files.base import ContentFile
from ci.utils import BuildFailed

class Plugin(object):
    def get_builders(self):
        return []

class Builder(object):
    name = None

    def __init__(self, build):
        self.build = build

    def execute_build(self):
        self.build.started = datetime.now()
        self.setup_build()
        try:
            self.run()
            self.build.was_successful = True
        except BuildFailed:
            self.build.was_successful = False
        finally:
            self.build.finished = datetime.now()
            self.teardown_build()

    def setup_build(self):
        self.repo_path = mkdtemp()
        rmdir(self.repo_path)
        Repository = get_backend(self.build.configuration.project.vcs_type)
        self.repo = Repository(
            self.repo_path,
            create=True,
            src_url=self.build.configuration.project.repo_uri,
            update_after_clone=True
        )
        self.repo.workdir.checkout_branch(self.build.branch)
        self.build.commit = self.repo.workdir.get_changeset().raw_id

    def teardown_build(self):
        rmtree(self.repo_path)

    def run(self):
        pass


class CommandBasedBuilder(Builder):
    def run(self):
        cmd = self.get_cmd()
        proc = Popen(cmd, cwd=self.repo_path, stdout=PIPE, stderr=PIPE)
        proc.wait()
        self.build.stderr.save('stderr', ContentFile(proc.stderr.read()), save=False)
        self.build.stdout.save('stdout', ContentFile(proc.stdout.read()), save=False)
        if proc.returncode:
            raise BuildFailed("Command %s returned with code %d" % (cmd, proc.returncode))

    def get_cmd(self):
        return self.cmd
