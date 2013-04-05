from django.conf.urls import patterns, url


urlpatterns = patterns('gameoflife.views',
    url(r'^$', 'watch'),
    url(r'^watcher/$', 'watcher_ws'),
    url(r'^worker/$', 'worker_ws'),
)
