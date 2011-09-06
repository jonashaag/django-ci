from celery.task import task
from ci.models import Build
from ci.plugins import BUILDERS

@task
def execute_build(build_id, builder):
    build = Build.objects.get(id=build_id)
    Builder = BUILDERS[builder]
    Builder(build).execute_build()
    build.save()
    if not build.commit.builds.filter(was_successful=None).exists():
        build.commit.was_successful = all(build.was_successful for build in
                                          build.commit.builds.all())
        build.commit.save()
