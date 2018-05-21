# coding=utf-8
from celery.result import AsyncResult
from django.utils.module_loading import import_string

from service_status.config import conf
from service_status.tasks import service_status_run
from celery import current_app


def do_check():
    """Verificação assícrona dos checks"""

    class StatusInfo(object):

        def __init__(self, check, task):
            self.check = check
            self.task = task

    for name, params in conf.CHECKS:
        check_init_kwargs = {'name': name}
        check_init_kwargs.update(params.get('kwargs', {}))

        check_class = import_string(params['fqn'])

        check = check_class(**check_init_kwargs)

        yield StatusInfo(check, service_status_run.delay(check))

    raise StopIteration


def is_ready(task_id):
    """Informa se a tarefa está pronta para entregar resultados"""
    task_id = str(task_id)
    async_result = AsyncResult(id=task_id, app=current_app)
    result = {
        'task': {
            'id': async_result.id,
            'ready': async_result.ready(),
        }
    }
    if async_result.failed():
        result['task']['failed'] = True
        result['task']['traceback'] = async_result.traceback
    else:
        result['task']['failed'] = False
        result['task']['output'] = async_result.result
    return result
