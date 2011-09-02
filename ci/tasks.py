from celery.task import task
from ci.models import Build
from ci.plugins import BUILDERS

@task
def execute_build(build_id, builder):
    build = Build.objects.get(id=build_id)
    BUILDERS[builder](build).execute_build()
    build.save()
