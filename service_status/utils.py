# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import inspect
import os
import re
from io import StringIO
from time import time

import psutil
import six
from django.core.management import call_command
from django.core.signals import setting_changed
from django.utils.module_loading import import_string


class IterInstanceCheck(object):
    """import check class"""
    def __init__(self, opts):
        self.opts = opts

    @staticmethod
    def _get_obj(name, params):
        check_init_kwargs = {'name': name}
        check_init_kwargs.update(params.get('kwargs', {}))

        check_class = import_string(params['fqn'])

        return check_class(**check_init_kwargs)

    def __iter__(self):
        try:
            for name, params in self.opts:
                yield self._get_obj(name, params)
        except ValueError:  # is a opts of files
            for defs in self.opts:
                try:
                    opts = import_string(defs)
                    for name, params in opts:
                        yield self._get_obj(name, params)
                except ImportError:
                    continue


class CeleryWorker(object):
    ERROR_KEY = "ERROR"

    @classmethod
    def get_inspect_status(cls):
        try:
            from celery.task.control import inspect
            insp = inspect()
            d = insp.stats()
            if not d:
                d = {cls.ERROR_KEY: 'No running Celery workers were found.'}
        except IOError as e:
            from errno import errorcode
            msg = "Error connecting to the backend: " + str(e)
            if len(e.args) > 0 and errorcode.get(e.args[0]) == 'ECONNREFUSED':
                msg += ' Server connection refused.'
            d = {cls.ERROR_KEY: msg}
        except ImportError as e:
            d = {cls.ERROR_KEY: str(e)}
        return d

    @classmethod
    def is_running(cls, name=None):
        """Function that needs to somehow determine if celery is running"""
        output = StringIO()
        # noinspection PyBroadException
        try:
            call_command('supervisor', 'status', stdout=output)
        except Exception as err:
            # There is no way to know in this case.
            return False
        if name is None:
            name = 'celery'
        # If found True
        return bool(re.search(r'{}\s+RUNNING'.format(name), output.getvalue()))


class AppSettings(object):
    defaults = {}

    def __init__(self, prefix, settings=None):
        self.prefix = prefix

        if settings is None:
            from django.conf import settings

        self.django_settings = settings

        for name, default in six.iteritems(self.defaults):
            prefix_name = (self.prefix + '_' + name).upper()
            value = getattr(self.django_settings, prefix_name, default)
            self._set_attr(prefix_name, value)

        setting_changed.connect(self._handler)

    def _set_attr(self, prefix_name, value):
        name = prefix_name[len(self.prefix) + 1:]
        setattr(self, name, value)

    def _handler(self, sender, setting, value, **kwargs):
        if kwargs['enter'] and setting.startswith(self.prefix):
            self._set_attr(setting, value)

    def __getattr__(self, name):
        return getattr(self.django_settings, '_'.join([self.prefix, name]))


class GetTime(object):
    name = None
    t1 = None
    t2 = None
    elapsed = None

    def __init__(self, name=None, doprint=False):
        super(GetTime, self).__init__()
        inspect_stack = inspect.stack()
        self.name = name or inspect_stack[1][3]
        self.doprint = doprint

    def __enter__(self, name=None):
        self.t1 = time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.t2 = time()
        self.elapsed = self.t2 - self.t1
        message = '{}: {:0.3f}'.format(self.name, self.elapsed)
        if self.doprint:  # pragma: no cover
            print(message)


def get_user_swap():
    total = 0
    for process in psutil.process_iter():
        if process.uids()[0] == os.getuid():
            try:
                total += process.memory_full_info().swap
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                pass
    return total


class DummyCeleryApp(object):
    def __init__(self):
        class Control(object):
            response = 'pong'

            def ping(self, names):
                if not self.response:
                    return None
                return [{name: {'ok': self.response}} for name in names]

        self.control = Control()


dummy_celery_app = DummyCeleryApp()
