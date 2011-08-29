from ci.plugins import BUILD_HOOKS
from ci.models import Project, Build
from ci.tasks import execute_build

def get_project_by_slug(slug):
    return get_object_or_404(Project, slug=slug)

def build_hook(request, project, hook_type):
    project = get_project_by_slug(project)
    try:
        get_changed_branches = BUILD_HOOKS[hook_type]
    except KeyError:
        raise Http404

    branches = get_changed_branches(request)
    for build_config in project.build_configurations:
        for branch in branches:
            build_id = build_config.builds.create(branch=branch).id
            execute_build.delay(build_id)
