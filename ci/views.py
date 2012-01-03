from operator import not_
from collections import OrderedDict

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, DetailView
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from ci.models import Project, Commit, Build
from ci.plugins import BUILD_HOOKS
from ci.tasks import execute_build


def user_view(view):
    def wrapper(request, **kwargs):
        user = kwargs.pop('user')
        user = get_object_or_404(User, username=user)
        return view(request, user, **kwargs)
    return wrapper

def project_view(view):
    @user_view
    def wrapper(request, user, **kwargs):
        project = get_object_or_404(user.projects, slug=kwargs.pop('slug'))
        return view(request, project, **kwargs)
    return wrapper


@csrf_exempt
@project_view
def build_hook(request, project, hook_type):
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


@login_required
def dashboard(request):
    projects = list(get_projects_for_user(request.user))
    return render(request, 'ci/project_list.html', {'projects': projects})

@user_view
def user(request, user):
    pass

def get_projects_for_user(user):
    for project in user.projects.all():
        unfinished_builds = {'active': project.get_active_builds().count(),
                             'pending': project.get_pending_builds().count()}
        commit_pks = [c.pk for c in project.get_latest_branch_commits()]
        success_values = Build.objects.filter(commit__pk__in=commit_pks) \
                                      .values_list('was_successful', flat=True)
        finished_builds = len(success_values)
        failed_builds = len(filter(not_, success_values))
        state = 'unknown' if not finished_builds else \
                    ('failed' if failed_builds else 'successful')

        yield project, state, unfinished_builds, finished_builds, failed_builds


@project_view
def project(request, project):
    return render(request, 'ci/project_detail.html',
                  {'project': project, 'commits': project.get_branch_commits()})


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
