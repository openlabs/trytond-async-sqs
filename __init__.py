# -*- coding: utf-8 -*-
"""
    __init__.py

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool
from .async import Async, ResultOptions, async_task    # noqa


def register():
    Pool.register(
        Async,
        module='async_sqs', type_='model'
    )
