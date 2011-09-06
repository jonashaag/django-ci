from django.template import Library

register = Library()

@register.inclusion_tag('ci/commit_link.html')
def commit_link(commit):
    return {'commit': commit}
