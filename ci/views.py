from collections import OrderedDict

from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView

from ci.models import Project, Commit
from ci.plugins import BUILD_HOOKS
from ci.tasks import execute_build


def get_project_by_slug(slug):
    return get_object_or_404(Project, slug=slug)


def build_hook(request, project_slug, hook_type):
    project = get_project_by_slug(project_slug)
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
        for project in self.object_list:
            finished_builds = list(project.get_latest_branch_builds())
            projects.append([
                project,
                len(finished_builds),
                len(filter(lambda b: not b.was_successful, finished_builds)),
                project.get_active_builds(),
                project.get_pending_builds(),
            ])
        return context


class ProjectDetails(DetailView):
    model = Project

    def get_context_data(self, **kwargs):
        context = super(ProjectDetails, self).get_context_data(**kwargs)
        context['commits'] = self.get_latest_branch_builds_grouped_by_commit()
        return context

    def get_latest_branch_builds_grouped_by_commit(self):
        branches = {}
        for build in self.object.get_latest_branch_builds():
            _, builds = branches.setdefault(build.commit.branch,
                                            (build.commit, []))
            builds.append(build)
        branch_order = filter(branches.__contains__, self.object.get_branch_order())
        for commit, builds in [branches.pop(b) for b in branch_order] + branches.values():
            active = commit.get_active_builds_for_branch()
            pending = commit.get_pending_builds_for_branch()
            yield commit, builds, active, pending


class CommitDetails(DetailView):
    model = Commit

    def get_context_data(self, **kwargs):
        context = super(CommitDetails, self).get_context_data(**kwargs)
        context['builds'] = self.get_builds_grouped_by_state()
        return context

    def get_builds_grouped_by_state(self):
        builds = OrderedDict((state, []) for state in
                             ('failed', 'successful', 'active', 'pending'))
        for build in self.object.builds.all():
            if build.done:
                state = 'successful' if build.was_successful else 'failed'
            else:
                state = 'pending' if build.pending else 'active'
            builds[state].append(build)
        return builds
