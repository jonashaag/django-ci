from django.conf.urls import patterns, url, include
from ci.views import *

# /ci/<username>/<project>/*
project_patterns = patterns('ci.views',
    url('^$', 'project', name='project'),
    url('^builds/(?P<pk>[\w_-]+)/$', CommitDetails.as_view(), name='commit'),
    url('^buildhooks/(?P<hook_type>[\w_-]+)/$', 'build_hook'),
)

# /ci/<username>/*
user_patterns = patterns('ci.views',
    url('^$', 'user', name='user'),
    url('^(?P<slug>[\w_-]+)/', include(project_patterns))
)

# /ci/*
urlpatterns = patterns('ci.views',
    url('^$', 'dashboard', name='dashboard'),
    url('^(?P<user>[\w_-]+)/', include(user_patterns)),
)
