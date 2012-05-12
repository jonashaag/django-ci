import shutil
import logging
from collections import OrderedDict

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, DetailView
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from ci.models import Project, Build
from ci.tasks import execute_build

logger = logging.getLogger('ci.buildhook')


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
def build_hook(request, project):
    clone = project.clone_repo(depth=10)
    try:
        branches = clone.get_remote_branches().iteritems()
        configurations = project.configurations.all()
        builds = []

        for branch, latest_commit in branches:
            for config in configurations:
                if not config.should_build_branch(branch):
                    continue

                build, new = config.builds.get_or_create(sha=latest_commit)
                if new:
                    logger.info('Queueing %s/%s', build.sha, config.name)
                    execute_build.delay(build.id, config.builder)
                    builds.append(build)
                else:
                    logger.info('Already built %s/%s', build.sha, config.name)

        return HttpResponse('\n'.join(build.sha for build in builds),
                            mimetype='text/html')
    finally:
        shutil.rmtree(clone.path)
