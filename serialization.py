# -*- coding: UTF-8 -*-
"""
    trytond_async_sqs.serialization

    Backports the 3.4 implementation of JSONEncoder and Decoder.

    :copyright: (c) 2013-2014 by Openlabs Technologies & Consulting (P) LTD
    :copyright: (c) 2014 by Tryton authors
    :license: 3-clause BSD License, see COPYRIGHT for more details
"""
import datetime
from decimal import Decimal
try:
    import simplejson as json
except ImportError:
    import json
import base64
from trytond.model import Model
from trytond.pool import Pool
from trytond.tools import safe_eval


class JSONDecoder(object):

    decoders = {}

    @classmethod
    def register(cls, klass, decoder):
        assert klass not in cls.decoders
        cls.decoders[klass] = decoder

    def __call__(self, dct):
        if dct.get('__class__') in self.decoders:
            return self.decoders[dct['__class__']](dct)
        return dct

JSONDecoder.register(
    'datetime',
    lambda dct: datetime.datetime(
        dct['year'], dct['month'], dct['day'],
        dct['hour'], dct['minute'], dct['second'], dct['microsecond']
    )
)
JSONDecoder.register(
    'date',
    lambda dct: datetime.date(dct['year'], dct['month'], dct['day'])
)
JSONDecoder.register(
    'time',
    lambda dct: datetime.time(
        dct['hour'], dct['minute'], dct['second'], dct['microsecond']
    )
)
JSONDecoder.register(
    'buffer', lambda dct:
    buffer(base64.decodestring(dct['base64']))
)
JSONDecoder.register(
    'Decimal', lambda dct: Decimal(dct['decimal'])
)
JSONDecoder.register(
    'Model', lambda dct: safe_eval(dct['repr'], {'Pool': Pool})
)


class JSONEncoder(json.JSONEncoder):

    serializers = {}

    def __init__(self, *args, **kwargs):
        super(JSONEncoder, self).__init__(*args, **kwargs)
        # Force to use our custom decimal with simplejson
        self.use_decimal = False

    @classmethod
    def register(cls, klass, encoder):
        assert klass not in cls.serializers
        cls.serializers[klass] = encoder

    def default(self, obj):
        if isinstance(obj, Model):
            marshaller = self.serializers[Model]
        else:
            marshaller = self.serializers.get(
                type(obj),
                super(JSONEncoder, self).default
            )
        return marshaller(obj)


JSONEncoder.register(
    datetime.datetime,
    lambda o: {
        '__class__': 'datetime',
        'year': o.year,
        'month': o.month,
        'day': o.day,
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
    })
JSONEncoder.register(
    datetime.date,
    lambda o: {
        '__class__': 'date',
        'year': o.year,
        'month': o.month,
        'day': o.day,
    })
JSONEncoder.register(
    datetime.time,
    lambda o: {
        '__class__': 'time',
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
    })
JSONEncoder.register(
    buffer,
    lambda o: {
        '__class__': 'buffer',
        'base64': base64.encodestring(o),
    })
JSONEncoder.register(
    Decimal,
    lambda o: {
        '__class__': 'Decimal',
        'decimal': str(o),
    })
JSONEncoder.register(
    Model,
    lambda o: {
        '__class__': 'Model',
        'repr': repr(o),
    })
