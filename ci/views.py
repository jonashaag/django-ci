from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from ci.plugins import BUILD_HOOKS
from ci.models import Project
from ci.tasks import execute_build

def get_project_by_slug(slug):
    return get_object_or_404(Project, slug=slug)

def build_hook(request, project, hook_type):
    project = get_project_by_slug(project)
    if hook_type not in BUILD_HOOKS:
        raise Http404
    hook = BUILD_HOOKS[hook_type](request)
    branches = {branch: project.commits.create(branch=branch)
                for branch in hook.get_changed_branches()}
    for build_config in project.configurations.all():
        for branch, commit in branches.iteritems():
            if build_config.should_build_branch(branch):
                build = commit.builds.create(configuration=build_config)
                execute_build.delay(build.id, build_config.builder)
    return HttpResponse()
