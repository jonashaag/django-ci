from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url('^(?P<project>[\w-])/buildhook/(?P<hook_type>[\w-]+)/', 'build_hook')
)
