from operator import not_
from collections import OrderedDict

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.views.decorators.csrf import csrf_exempt

from ci.models import Project, Commit, Build
from ci.plugins import BUILD_HOOKS
from ci.tasks import execute_build


def get_project_by_slug(slug):
    return get_object_or_404(Project, slug=slug)


@csrf_exempt
def build_hook(request, project_slug, hook_type):
    project = get_project_by_slug(project_slug)
    if hook_type not in BUILD_HOOKS:
        raise Http404
    hook = BUILD_HOOKS[hook_type](request)
    branches = {branch: project.commits.create(branch=branch)
                for branch in hook.get_changed_branches()}
    configurations = project.configurations.all()
    for branch, commit in branches.iteritems():
        nbuilds = 0
        for build_config in configurations:
            if build_config.should_build_branch(branch):
                nbuilds += 1
                build = commit.builds.create(configuration=build_config)
                execute_build.delay(build.id, build_config.builder)
        if nbuilds < 1:
            # Don't keep empty commits
            commit.delete()
    return HttpResponse()


class ProjectList(ListView):
    model = Project

    def get_context_data(self, **kwargs):
        context = super(ProjectList, self).get_context_data(**kwargs)
        context['projects'] = projects = []
        for project in self.object_list:
            commit_pks = [c.pk for c in project.get_latest_branch_commits()]
            success_values = Build.objects.filter(commit__pk__in=commit_pks) \
                                          .values_list('was_successful', flat=True)
            finished_builds = len(success_values)
            failed_builds = len(filter(not_, success_values))
            state = 'unknown' if not finished_builds else \
                        ('failed' if failed_builds else 'successful')
            projects.append([project, state, finished_builds, failed_builds])
        return context


class ProjectDetails(DetailView):
    model = Project

    def get_context_data(self, **kwargs):
        context = super(ProjectDetails, self).get_context_data(**kwargs)
        context['commits'] = self.object.get_branch_commits()
        return context


class CommitDetails(DetailView):
    model = Commit

    def get_context_data(self, **kwargs):
        context = super(CommitDetails, self).get_context_data(**kwargs)
        # TODO
        assert context['object'].vcs_id
        context['builds'] = self.get_builds_grouped_by_state()
        return context

    def get_builds_grouped_by_state(self):
        state_order = ['failed', 'successful', 'active', 'pending']
        return sorted(self.object.builds.all(),
                      key=lambda build: state_order.index(build.state))
