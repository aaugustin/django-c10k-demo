from django.conf.urls import include, patterns, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = patterns('',
    url(r'^test/', include('c10ktools.urls')),
    url(r'', include('gameoflife.urls')),

)

urlpatterns += staticfiles_urlpatterns()
