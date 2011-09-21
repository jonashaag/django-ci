from django.conf.urls.defaults import patterns, url
from django.views.generic import DetailView

from ci.views import ProjectList, ProjectDetails, CommitDetails

urlpatterns = patterns('ci.views',
    url('^$', ProjectList.as_view(), name='overview'),
    url('^(?P<slug>[\w-]+)/$', ProjectDetails.as_view(), name='project'),
    url('^(?P<project_slug>[\w-]+)/builds/(?P<pk>[\w-]+)/$', CommitDetails.as_view(), name='commit'),
    url('^(?P<project_slug>[\w-]+)/buildhooks/(?P<hook_type>[\w-]+)/$', 'build_hook'),
)
