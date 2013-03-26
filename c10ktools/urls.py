from django.conf.urls import patterns, url


urlpatterns = patterns('c10ktools.views',
    url(r'^$', 'echo'),
    url(r'^ws/$', 'echo_ws'),
    url(r'^wsgi/$', 'basic'),
)
