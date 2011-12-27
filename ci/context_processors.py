import os
from django.contrib.sites.models import Site

GIT_REV = None

def site(request):
    return {'current_site': Site.objects.get_current()}

def git_rev(request):
    global GIT_REV
    if not GIT_REV:
        GIT_REV = _get_git_rev()
    return {'ci_git_rev': GIT_REV}

def _get_git_rev():
    repo_root = os.path.join(os.path.dirname(__file__), os.pardir)
    try:
        return open(os.path.join(repo_root, '.git/refs/heads/master')).read()[:7]
    except IOError:
        return
