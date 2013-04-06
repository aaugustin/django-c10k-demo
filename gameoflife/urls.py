from django.conf.urls import patterns, url


urlpatterns = patterns('gameoflife.views',
    url(r'^$', 'watch'),
    url(r'^watcher/$', 'watcher'),
    url(r'^reset/$', 'reset'),
    url(r'^worker/$', 'worker'),
)
