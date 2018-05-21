# coding=utf-8
from __future__ import absolute_import
from celery import shared_task
from service_status.exceptions import SystemStatusError, SystemStatusWarning


# coloca na task do projeto (service-status)
@shared_task(ignore_result=False,
             track_started=True)
def service_status_run(check):
    result = {
        "status": True,
        "warning": None,
        "error": None
    }
    try:
        check.run()
    except SystemStatusError as e:
        result['status'] = False
        result['error'] = str(e)
    except SystemStatusWarning as e:
        result['warning'] = str(e)
    return result
