# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from .utils import AppSettings


class ApplicationSettings(AppSettings):
    defaults = [
        ('DB_DEFAULT', {
            'fqn': 'service_status.checks.DatabaseCheck',
            'kwargs': {'model_name': 'sessions.Session'}
        }),
        ('SWAP', {
            'fqn': 'service_status.checks.SwapCheck',
            'kwargs': {'limit': 0}
        })
    ]


conf = ApplicationSettings('SERVICE_STATUS')
