from django.conf.urls.defaults import patterns, url
from django.views.generic import DetailView

from ci.models import Commit
from ci.views import ProjectList, ProjectDetails

urlpatterns = patterns('ci.views',
    url('^$', ProjectList.as_view(), name='overview'),
    url('^(?P<slug>[\w-]+)/$', ProjectDetails.as_view(), name='project'),
    url('^(?P<slug>[\w-]+)/build/(?P<pk>[\w-]+)/$', DetailView.as_view(model=Commit), name='commit'),
    url('^(?P<project_slug>[\w-]+)/buildhooks/(?P<hook_type>[\w-]+)/$', 'build_hook'),
)
