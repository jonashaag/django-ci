from django.conf.urls.defaults import patterns, url
from django.views.generic import DetailView

from ci.models import Project, Commit
from ci.views import ProjectList

urlpatterns = patterns('ci.views',
    url('^$', ProjectList.as_view(model=Project), name='overview'),
    url('^(?P<slug>[\w-]+)/$', DetailView.as_view(model=Project), name='project'),
    url('^(?P<slug>[\w-]+)/build/(?P<pk>[\w-]+)/$', DetailView.as_view(model=Commit), name='commit'),
    url('^(?P<slug>[\w-]+)/buildhook/(?P<hook_type>[\w-]+)/$', 'build_hook'),
)
