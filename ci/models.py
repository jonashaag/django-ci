import os
import vcs
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

    def __unicode__(self):
        return self.name

class BuildConfiguration(models.Model):
    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, related_name='configurations')
    builder = models.CharField(choices=make_choice_list(BUILDERS), max_length=20)
    branches = StringListField(blank=True, null=True, max_length=500)

    def should_build_branch(self, branch):
        return not self.branches or branch in self.branches

    def __unicode__(self):
        return '%s %s (%s)' % (self.project.name, self.name, self.builder)

class Commit(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    project = models.ForeignKey(Project, related_name='commits')
    vcs_id = models.CharField(max_length=SHA1_LEN, blank=True, null=True)
    branch = models.CharField(max_length=100)

    @property
    def was_successful(self):
        return not self.builds.filter(was_successful=False).count()

class Build(models.Model):
    configuration = models.ForeignKey(BuildConfiguration)
    commit = models.ForeignKey(Commit, related_name='builds')
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    was_successful = models.NullBooleanField()
    stdout = models.FileField(upload_to=make_build_log_filename)
    stderr = models.FileField(upload_to=make_build_log_filename)
