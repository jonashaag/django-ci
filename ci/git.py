import os
import re
import logging
from subprocess import Popen, PIPE

logger = logging.getLogger('ci.git')

def assert_successful(proc):
    assert not proc.wait(), proc.returncode

class Repo(object):
    def __init__(self, path):
        self.path = path

    @classmethod
    def clone(cls, src, path, bare=False, depth=None):
        repo = cls(path)
        repo._create_dir()
        cmd = ['git', 'clone', '--no-checkout']
        if bare:
            cmd.extend(['--bare'])
        if depth:
            cmd.extend(['--depth', str(depth)])
        repo._execute(cmd + [src, repo.path])
        return repo

    @classmethod
    def init(cls, *args, **kwargs):
        repo = cls(*args, **kwargs)
        repo._create_dir()
        repo._execute(['git', 'init'])
        return repo

    def fetch(self):
        self._execute(['git', 'fetch'])
        #self._execute(['

    def checkout(self, sha):
        self._execute(['git', 'diff', '--exit-code'])
        self._execute(['git', 'reset', '--hard', sha])

    def log(self, branch):
        proc = self._popen(['git', 'log', '--format=%H', branch], stdout=PIPE)
        for line in proc.stdout:
            yield line.strip()
        assert_successful(proc)

    def get_branches(self):
        proc = self._popen(['git', 'branch', '-v', '--no-abbrev'], stdout=PIPE)
        stdout, _ = proc.communicate()
        assert_successful(proc)
        return dict(line[2:].split()[:2] for line in stdout.splitlines())

    def get_remote_branches(self):
        proc = self._popen(['git', 'ls-remote', '--heads'], stdout=PIPE)
        stdout, _ = proc.communicate()
        assert_successful(proc)
        return {refspec.replace('refs/heads/', ''): branch
                for branch, refspec in (re.split('\s+', line) for line in
                                        stdout.splitlines())}

    def commit(self, msg, files=None, branch=None, empty=False):
        assert empty or files
        if branch:
            self._execute(['git', 'checkout', '-B', branch])
        if empty:
            self._execute(['git', 'commit', '--allow-empty', '-m', msg])
        else:
            self._execute(['git', 'add'] + files)
            self._execute(['git', 'commit', '-m', msg])

    def make_branch(self, name):
        self._execute(['git', 'branch', name])

    def _execute(self, cmd):
        assert_successful(self._popen(cmd))

    def _popen(self, cmd, **kwargs):
        logger.info('(%s) Executing %s', self.path, cmd)
        return Popen(cmd, cwd=self.path, **kwargs)

    def _create_dir(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)
