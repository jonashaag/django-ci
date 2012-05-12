import os
import tempfile
from collections import defaultdict

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User

from ci import git
from ci.fields import StringListField, NamedFileField
from ci.utils import make_choice_list
from ci.plugins import BUILDERS

def first_or_none(qs):
    try:
        return qs[0]
    except IndexError:
        return None

def make_build_log_filename(build, filename):
    return os.path.join('builds', str(build.id), filename)

class Project(models.Model):
    owner = models.ForeignKey(User, related_name='projects')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    repo_uri = models.CharField(max_length=500)
    important_branches = StringListField(blank=True, null=True, max_length=500)

    class Meta:
        unique_together = ['owner', 'slug']

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return 'project', (), {'user': self.owner.username, 'slug': self.slug}

    # XXX too many methods, too many similar names

    def clone_repo(self, **kwargs):
        return git.Repo.clone(self.repo_uri, tempfile.mkdtemp(), **kwargs)

    def get_branch_order(self):
        return self.important_branches or ['master']

    def get_branches_ordered(self):
        all_branches = list(self.get_all_branches())
        for branch in self.get_branch_order():
            try:
                all_branches.remove(branch)
                yield branch
            except ValueError:
                pass
        for branch in all_branches:
            yield branch

    def get_all_branches(self):
        tracked_branches = BuildConfiguration.objects.values_list('branches', flat=True)
        return set(sum(tracked_branches, []))

    def get_latest_branch_builds(self):
        branches = self.important_branches or self.get_all_branches()
        for branch in branches:
            yield self.get_latest_build(branch)

    def get_latest_branch_build(self, branch):
        for commit in git.log(self, branch):
            try:
                yield Build.objects.filter(sha=commit)
                break
            except Build.DoesNotExist:
                pass

    def get_branch_commits(self):
        for branch in self.get_branches_ordered():
            commits = self.commits.filter(branch=branch)
            latest = first_or_none(commits.exclude(was_successful=None))
            latest_stable = first_or_none(commits.filter(was_successful=True))
            unfinished = commits.order_by('created').exclude(sha=None) \
                                                    .filter(was_successful=None)
            unfinished_builds = defaultdict(int)
            for commit in unfinished:
                for build in commit.builds.all():
                    unfinished_builds[build.state] += 1
            yield latest, latest_stable, unfinished_builds, unfinished

    def get_active_builds(self):
        return self.builds.exclude(started=None).filter(finished=None)

    def get_pending_builds(self):
        return self.builds.filter(started=None)


class BuildConfiguration(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='configurations')
    builder = models.CharField(choices=make_choice_list(BUILDERS), max_length=20)
    branches = StringListField(blank=True, null=True, max_length=500)
    parameters = models.TextField(null=True)

    def __unicode__(self):
        return '%s: %s (%s)' % (self.project, self.name, self.builder)

    def should_build_branch(self, branch):
        return not self.branches or branch in self.branches


class Build(models.Model):
    configuration = models.ForeignKey(BuildConfiguration, related_name='builds')
    sha = models.CharField(max_length=40)
    started = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)
    was_successful = models.NullBooleanField()
    stdout = NamedFileField('stdout.txt', upload_to=make_build_log_filename)
    stderr = NamedFileField('stderr.txt', upload_to=make_build_log_filename)

    @property
    def project(self):
        return self.configuration.project

    class Meta:
        unique_together = ['configuration', 'sha']

    def save(self, *args, **kwargs):
        assert not (self.was_successful and not self.finished)
        assert not (self.finished and not self.started)
        return super(Build, self).save(*args, **kwargs)

    @property
    def state(self):
        if self.finished:
            return ('failed', 'successful')[self.was_successful]
        else:
            return ('pending', 'active')[bool(self.started)]

    @property
    def duration(self):
        return self.finished - self.started
