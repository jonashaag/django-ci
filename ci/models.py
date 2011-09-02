import os
import vcs
from django.db import models
from django.core.files.base import ContentFile
from django.db.models.fields.files import FieldFile
from ci.utils import make_choice_list
from ci.plugins import BUILDERS

SHA1_LEN = 40

class ExtraFieldFile(FieldFile):
    def touch(self, filename, **kwargs):
        self.save(filename, ContentFile(''), **kwargs)
        self.close()

class LogFileField(models.FileField):
    attr_class = ExtraFieldFile

    def __init__(self):
        super(LogFileField, self).__init__(upload_to=self.make_filename)

    def make_filename(self, build, filename):
        return os.path.join('builds', str(build.id), filename)


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
    project = models.ForeignKey(Project, related_name='build_configurations')
    builder = models.CharField(choices=make_choice_list(BUILDERS), max_length=20)

    def __unicode__(self):
        return '%s %s (%s)' % (self.project.name, self.name, self.builder)

class Build(models.Model):
    configuration = models.ForeignKey(BuildConfiguration, related_name='builds')
    branch = models.CharField(max_length=100, blank=True, null=True)
    commit = models.CharField(max_length=SHA1_LEN)
    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    was_successful = models.NullBooleanField()
    stdout = LogFileField()
    stderr = LogFileField()
