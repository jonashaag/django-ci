import os
import vcs
from itertools import repeat

from django.db import models
from django.core.files.base import ContentFile
from django.db.models.fields.files import FieldFile

from ci.utils import make_choice_list
from ci.plugins import BUILDERS

SHA1_LEN = 40

def make_build_log_filename(build, filename):
    return os.path.join('builds', str(build.id), filename)

class StringListField(models.CharField):
    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        if value and not isinstance(value, list):
            value = [s.strip() for s in value.split(',')]
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

    @models.permalink
    def get_absolute_url(self):
        return 'project', (), {'slug': self.slug}

    def get_finished_builds(self):
        # Django supports neither SELECT ... FROM <subselect> nor GROUP BY :-(
        # Could use DISTINCT ON once #6422 is merged
        sql_params = [self.id]
        branch_names_sql = ''
        if self.important_branches:
            sql_params.extend(self.important_branches)
            branch_names_sql = ' AND branch IN (%s)' % \
                ', '.join(repeat('%s', len(self.important_branches)))
        return Commit.objects.raw(
            '''
            SELECT * FROM (
              SELECT * FROM ci_commit
              WHERE project_id=%%s AND was_successful IS NOT NULL %s
              ORDER BY created
            )
            GROUP BY branch
            ''' % branch_names_sql,
            sql_params
        )

    def get_building_commits(self):
        return self.commits.filter(was_successful=None).exclude(vcs_id=None)

    def get_pending_commits(self):
        return self.commits.filter(was_successful=None, vcs_id=None)


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
    was_successful = models.NullBooleanField()

    class Meta:
        ordering = ['-created']

    @models.permalink
    def get_absolute_url(self):
        return 'commit', (), {'slug': self.project.slug, 'pk': self.id}

    @property
    def done(self):
        return self.was_successful is not None

    @property
    def short_vcs_id(self):
        return self.vcs_id[:7]


class Build(models.Model):
    configuration = models.ForeignKey(BuildConfiguration)
    commit = models.ForeignKey(Commit, related_name='builds')
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    was_successful = models.NullBooleanField()
    stdout = models.FileField(upload_to=make_build_log_filename)
    stderr = models.FileField(upload_to=make_build_log_filename)

    @property
    def done(self):
        return self.was_successful is not None
