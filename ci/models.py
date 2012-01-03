import os
from collections import defaultdict

import vcs

from django.db import models
from django.contrib.auth.models import User

from ci.fields import StringListField, NamedFileField
from ci.utils import make_choice_list
from ci.plugins import BUILDERS

VCS_CHOICES = make_choice_list(['git', 'hg'])
SHA1_LEN = 40

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
    vcs_type = models.CharField('VCS type', choices=VCS_CHOICES, max_length=10)
    repo_uri = models.CharField('Repository URI', max_length=500)
    important_branches = StringListField(blank=True, null=True, max_length=500)

    class Meta:
        unique_together = ['owner', 'slug']

    @property
    def builds(self):
        return Build.objects.filter(commit__project=self)

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return 'project', (), {'user': self.owner.username, 'slug': self.slug}

    def get_vcs_backend(self):
        return vcs.get_backend(self.vcs_type)

    # XXX too many similar names

    def get_branch_order(self):
        return self.important_branches or [self.get_vcs_backend().DEFAULT_BRANCH_NAME]

    def get_all_branches(self):
        return self.commits.order_by().values_list('branch', flat=True).distinct()

    def get_latest_branch_commits(self):
        # unordered
        branches = self.important_branches or self.get_all_branches()
        for branch in branches:
            try:
                yield self.commits.filter(branch=branch) \
                                  .exclude(was_successful=None)[0]
            except IndexError:
                pass

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


    def get_branch_commits(self):
        for branch in self.get_branches_ordered():
            commits = self.commits.filter(branch=branch)
            latest = first_or_none(commits.exclude(was_successful=None))
            latest_stable = first_or_none(commits.filter(was_successful=True))
            unfinished = commits.order_by('created').exclude(vcs_id=None) \
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


class Commit(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, related_name='commits')
    vcs_id = models.CharField(max_length=SHA1_LEN, blank=True, null=True)
    branch = models.CharField(max_length=100)
    short_message = models.CharField(max_length=100)
    was_successful = models.NullBooleanField()

    class Meta:
        ordering = ['-created']

    def __unicode__(self):
        return '/'.join([self.branch, self.vcs_id or '(unknown)'])

    @models.permalink
    def get_absolute_url(self):
        return 'commit', (), {'project_slug': self.project.slug, 'pk': self.id}

    @property
    def short_vcs_id(self):
        return self.vcs_id[:7]

    def get_builds_for_branch(self):
        return Build.objects.filter(commit__branch=self.branch)

    def get_active_builds_for_branch(self):
        return self.get_builds_for_branch().filter(started__isnull=False,
                                                   finished__isnull=True)

    def get_pending_builds_for_branch(self):
        return self.get_builds_for_branch().filter(started__isnull=True)


class Build(models.Model):
    configuration = models.ForeignKey(BuildConfiguration, related_name='builds')
    commit = models.ForeignKey(Commit, related_name='builds')
    started = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)
    was_successful = models.NullBooleanField()
    stdout = NamedFileField('stdout.txt', upload_to=make_build_log_filename)
    stderr = NamedFileField('stderr.txt', upload_to=make_build_log_filename)

    class Meta:
        unique_together = ['configuration', 'commit']

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
