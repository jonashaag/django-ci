from django.contrib.admin import ModelAdmin, site
from models import Project, BuildConfiguration, Build, Commit

class ProjectAdmin(ModelAdmin):
    prepopulated_fields = {'slug': ['name']}

site.register(Project, ProjectAdmin)
site.register(BuildConfiguration)
site.register(Build)
site.register(Commit)
