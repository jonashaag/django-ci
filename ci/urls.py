from django.conf.urls.defaults import patterns, url
from django.views.generic import ListView, DetailView
from ci.models import Project, Commit

urlpatterns = patterns('ci.views',
    url('^$', ListView.as_view(model=Project), name='overview'),
    url('^(?P<slug>[\w-]+)/$', DetailView.as_view(model=Project), name='project'),
    url('^(?P<slug>[\w-]+)/build/(?P<pk>[\w-]+)/$', DetailView.as_view(model=Commit), name='commit'),
    url('^(?P<slug>[\w-]+)/buildhook/(?P<hook_type>[\w-]+)/$', 'build_hook'),
)
