# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from collections import namedtuple

from django.apps import apps
from django.utils.encoding import python_2_unicode_compatible
from django.utils.module_loading import import_string

from service_status.utils import get_user_swap, GetTime, IterInstanceCheck
from .config import conf
from .exceptions import SystemStatusError, SystemStatusWarning


@python_2_unicode_compatible
class SystemCheckBase(object):
    name = None
    output = None
    error = None
    warning = None
    timing = None

    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs

    def __getattr__(self, name):
        method = object.__getattribute__
        try:
            return method(self, "kwargs")[name]
        except KeyError:
            return method(self, name)

    def __str__(self):
        return f'{self.__class__.__name__} {self.name}: {self.output} ({self.elapsed:.3f}s)'

    def _run(self):
        raise NotImplementedError()  # pragma: no cover

    def run(self):
        try:
            with GetTime() as self.timing:
                self.output = self._run() or 'OK'
        except SystemStatusWarning as e:
            self.warning = e
            self.output = str(e)
            raise
        except SystemStatusError as e:
            self.error = e
            self.output = str(e)
            raise
        except Exception as e:
            self.error = SystemStatusError(repr(e))
            self.output = str(e)
            raise self.error

    @property
    def status(self):
        if self.error:
            return 'error'

        if self.warning:
            return 'warning'

        return 'normal'

    @property
    def elapsed(self):
        return getattr(self.timing, 'elapsed', None)


class DatabaseCheck(SystemCheckBase):
    model_name = 'sessions.Session'
    database_alias = None

    def __init__(self, **kwargs):
        super(DatabaseCheck, self).__init__(**kwargs)
        if 'model_name' in kwargs:
            self.model_name = kwargs['model_name']
        if 'database_alias' in kwargs:
            self.database_alias = kwargs['database_alias']

    def _run(self):
        self.model = apps.get_model(self.model_name)

        if self.database_alias:
            queryset = self.model.objects.using(self.database_alias).all()
        else:
            queryset = self.model.objects.all()

        count = queryset.count()

        return f'{self.model_name} (db: {queryset.db}) {count} OK'


# class SupervisorCheck(SystemCheckBase):
#     """
#     celery                           RUNNING   pid 13835, uptime 0:39:16
#     celery-low-rate                  RUNNING   pid 13838, uptime 0:39:14
#     celery-beat                      RUNNING   pid 13838, uptime 0:39:14
#     nginx                            RUNNING   pid 13836, uptime 0:39:15
#     uwsgi                            RUNNING   pid 13840, uptime 0:39:14
#     """
#
#     def _run(self):
#         command = ['supervisorctl', '-c', '{}/etc/supervisor.ini'.format(os.path.expanduser('~')), 'status']
#         output = subprocess.check_output(command)
#
#         if not output:
#             raise SystemStatusError('`supervisorctl status` command did not respond properly')
#
#         for process in ('celery', 'celery-low-rate', 'celery-beat', 'nginx', 'uwsgi'):
#             if not re.search(r'{}\s+RUNNING'.format(process), output):
#                 raise SystemStatusError('`{}` not found or not running'.format(process))


class SwapCheck(SystemCheckBase):
    limit = 0

    def __init__(self, **kwargs):
        super(SwapCheck, self).__init__(**kwargs)
        if 'limit' in kwargs:
            self.limit = kwargs['limit']
        # TODO handle percentage
        # if str(self.limit)[-1] == '%':
        #     self.is_percent = True
        #     self.limit = self.limit[0:-1]
        # self.limit = int(self.limit)

    def _run(self):
        swap = get_user_swap()
        message = f'the user swap memory is: {swap / 1024:.0f} KB (limit: {self.limit / 1024:.0f} KB)'
        if swap > self.limit:
            e = SystemStatusWarning(message)
            e.log_message = f'the user swap memory is above {self.limit / 1024:.0f} KB'
            raise e
        return message


class CeleryCheck(SystemCheckBase):
    def __init__(self, name, **kwargs):
        super(CeleryCheck, self).__init__(name, **kwargs)
        if 'celery_app_fqn' in kwargs:
            self.celery_app_fqn = kwargs['celery_app_fqn']
        if 'worker_names' in kwargs:
            self.worker_names = kwargs['worker_names']

    def _run(self):
        celery_app = import_string(self.celery_app_fqn)
        for name in self.worker_names:
            response = celery_app.control.ping([name])

            if not response:
                raise SystemStatusError(f'celery worker `{name}` was not found')

            if response[0][name] != {'ok': 'pong'}:
                raise SystemStatusError(f'celery worker `{name}` did not respond')

        return f'got response from {len(self.worker_names)} worker(s)'


def do_check():
    checks = []
    errors = []
    warnings = []

    def run_check(opts):
        for check in IterInstanceCheck(opts):
            try:
                checks.append(check)
                check.run()
            except SystemStatusError as e:
                errors.append(e)
            except SystemStatusWarning as e:
                warnings.append(e)

    run_check(conf.CHECKS)
    run_check(conf.CHECK_FILES)
    return namedtuple('SystemErrors', ('checks', 'errors', 'warnings'))(checks, errors, warnings)
