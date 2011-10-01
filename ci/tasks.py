from celery.task import task
from ci.models import Build
from ci.plugins import BUILDERS

@task
def execute_build(build_id, builder):
    build = Build.objects.get(id=build_id)
    Builder = BUILDERS[builder]
    try:
        Builder(build).execute_build()
    finally:
        build.save()
        # XXX run this in a SELECT ... FOR UPDATE transaction
        if not build.commit.builds.filter(was_successful=None).exists():
            build.commit.done = True
            build.commit.save()
