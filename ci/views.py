from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView

from ci.models import Project
from ci.plugins import BUILD_HOOKS
from ci.tasks import execute_build

def get_project_by_slug(slug):
    return get_object_or_404(Project, slug=slug)

def build_hook(request, slug, hook_type):
    project = get_project_by_slug(slug)
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

class ProjectList(ListView):
    model = Project

    def get_context_data(self, **kwargs):
        context = super(ProjectList, self).get_context_data(**kwargs)
        context['projects'] = projects = []
        for project in context['object_list']:
            finished_builds = list(project.get_finished_builds())
            projects.append([
                project,
                len(finished_builds),
                len(filter(lambda b: not b.was_successful, finished_builds)),
                project.get_building_commits().count(),
                project.get_pending_commits().count()
            ])
        return context
