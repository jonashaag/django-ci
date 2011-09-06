from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('ci.views',
    url('^(?P<project>[\w-]+)/buildhook/(?P<hook_type>[\w-]+)/$', 'build_hook'),
    url('^(?P<project>[\w-]+)/$', 'project', name='project'),
    url('^(?P<project>[\w-]+)/build/(?P<commit>[\w-]+)/$', 'commit', name='commit'),
    url('^$', 'overview')
)
