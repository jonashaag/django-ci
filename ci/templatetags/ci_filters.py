from django.template import Library
register = Library()

@register.filter
def shorten_commit_id(s):
    return s[:7]
