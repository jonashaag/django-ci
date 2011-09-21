import os
from itertools import repeat

import vcs
from django.db import models
from django.db.utils import IntegrityError

from ci.utils import make_choice_list
from ci.plugins import BUILDERS

SHA1_LEN = 40

def make_build_log_filename(build, filename):
    return os.path.join('builds', str(build.id), filename)

class StringListField(models.CharField):
    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        if value and not isinstance(value, list):
            value = filter(None, [s.strip() for s in value.split(',')])
        return value

    def get_prep_value(self, value):
        if value:
            value = ','.join(value)
        return value


class Project(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    vcs_type = models.CharField('VCS type', choices=make_choice_list(vcs.BACKENDS),
                                max_length=10)
    repo_uri = models.CharField('Repository URI', max_length=500)
    important_branches = StringListField(blank=True, null=True, max_length=500)

    @property
    def builds(self):
        return Build.objects.filter(commit__project=self)

    @models.permalink
    def get_absolute_url(self):
        return 'project', (), {'slug': self.slug}

    def get_vcs_backend(self):
        return vcs.get_backend(self.vcs_type)

    def get_branch_order(self):
        return self.important_branches or [self.get_vcs_backend().DEFAULT_BRANCH_NAME]

    def get_latest_branch_builds(self):
        # Django supports neither SELECT ... FROM <subselect> nor GROUP BY :-(
        # Could use DISTINCT ON once #6422 is merged
        sql_params = [self.id]
        branch_names_sql = ''
        if self.important_branches:
            sql_params.extend(self.important_branches)
            branch_names_sql = ' AND branch IN (%s)' % \
                ', '.join(repeat('%s', len(self.important_branches)))
        return Build.objects.raw(
            '''
            SELECT * FROM ci_build
            WHERE commit_id IN (
              SELECT id FROM (
                SELECT * FROM ci_commit
                WHERE project_id=%%s AND done %s
                ORDER BY created
              )
              GROUP BY branch
            )
            ''' % branch_names_sql,
            sql_params
        )

    def get_active_builds(self):
        return self.builds.filter(started__isnull=False, finished__isnull=True)

    def get_pending_builds(self):
        return self.builds.filter(started__isnull=True)


class BuildConfiguration(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='configurations')
    builder = models.CharField(choices=make_choice_list(BUILDERS), max_length=20)
    branches = StringListField(blank=True, null=True, max_length=500)

    def should_build_branch(self, branch):
        return not self.branches or branch in self.branches


class Commit(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, related_name='commits')
    vcs_id = models.CharField(max_length=SHA1_LEN, blank=True, null=True)
    branch = models.CharField(max_length=100)
    done = models.BooleanField()

    class Meta:
        ordering = ['-created']

    @models.permalink
    def get_absolute_url(self):
        return 'commit', (), {'slug': self.project.slug, 'pk': self.id}

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
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    was_successful = models.NullBooleanField()
    stdout = models.FileField(upload_to=make_build_log_filename)
    stderr = models.FileField(upload_to=make_build_log_filename)

    class Meta:
        unique_together = ['configuration', 'commit']

    def save(self, *args, **kwargs):
        assert not (self.was_successful and not self.finished)
        assert not (self.finished and not self.started)
        return super(Build, self).save(*args, **kwargs)

    @property
    def done(self):
        return self.finished is not None

    @property
    def pending(self):
        return self.started is None

    @property
    def active(self):
        return not self.pending and not self.done
