from celery.task import task
from ci.models import Build

@task
def execute_build(build_id):
    Build.objects.get(id=build_id).execute()
