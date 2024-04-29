# coding=utf-8
try:
    from django.urls import re_path as url
except ImportError:
    from django.conf.urls import url
from service_status.views import ServiceStatusView

# name this app
app_name = 'service_status'

urlpatterns = [
    url(r'^$', ServiceStatusView.as_view(), name='index'),
]
