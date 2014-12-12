# -*- coding: UTF-8 -*-
"""
    trytond_async_sqs.async

    Call Tryton model methods asynchronously by sending messages. Message Queue
    is powered by Amazon SQS.

    The methods MUST BE classmethods or staticmethods and MUST RETURN
    serializable objects. These methods will be called inside transaction.

    :copyright: (c) 2013-2014 by Openlabs Technologies & Consulting (P) LTD
    :license: 3-clause BSD License, see COPYRIGHT for more details
"""
import time
import functools
from uuid import uuid4
from collections import namedtuple
from datetime import datetime, timedelta

import boto
from trytond.config import CONFIG
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView
from trytond.transaction import Transaction
from .serialization import json, JSONDecoder, JSONEncoder


__metaclass__ = PoolMeta


if 'sqs_region' in CONFIG.options:
    # If a region is specified for SQS use that
    boto.sqs.connect_to_region(CONFIG.options['sqs_region'])


def async_task(model_name=None, ignore_result=True, visibility_timeout=60):
    """
    A decorator to make it convenient to call method both asynchronously
    and synchronously.
    """
    def wrap(function):
        @functools.wraps(function)
        def wrapped_func(*args, **kwargs):
            return function(*args, **kwargs)

        def defer(*args, **kwargs):
            Async = Pool().get('async.async')
            return Async.defer(
                wrapped_func.model_name,
                function.__name__,
                args, kwargs,
                result_options=ResultOptions(ignore_result, visibility_timeout)
            )

        wrapped_func.defer = defer
        wrapped_func.model_name = model_name
        wrapped_func.is_async_task = True
        return wrapped_func
    return wrap


class AsyncResult(object):
    """
    A Class that represents an asynchronous result

    :param result_uuid: The UUID of the result
    """
    def __init__(self, payload):
        self.result_uuid = payload['__result_uuid__']
        self.result_options = ResultOptions._make(
            payload['__result_options__']
        )
        self.result = None

    def wait(self, wait_time_seconds=None, interval_seconds=1):
        """
        Blockingly wait for the results for wait_time_seconds
        """
        Async = Pool().get('async.async')

        if self.result_options.ignore_result:
            raise Async.raise_user_error(
                'Cannot fetch result for tasks where results are ignored'
            )

        if wait_time_seconds:
            end_time = datetime.utcnow() + timedelta(
                seconds=wait_time_seconds
            )
        else:
            end_time = datetime.max

        while datetime.utcnow() < end_time:
            queue = Async.get_queue(self.result_uuid)
            if queue:
                break
            else:
                time.sleep(interval_seconds)
        else:
            return None

        results = Async.get_sqs_connection().receive_message(
            queue, wait_time_seconds=wait_time_seconds,
        )

        if results:
            # The queue's purpose in life is over :(
            queue.delete()

            return Async.deserialize_message(
                results[0].get_body()
            )['result']


ResultOptions = namedtuple(
    'ResultOptions', [
        'ignore_result',
        'visibility_timeout',
    ]
)


class Async(ModelView):
    """
    Asynchronous Execution Helper
    """
    __name__ = 'async.async'

    _result_class = AsyncResult

    @classmethod
    def get_sqs_connection(cls):
        """
        If an access_key is specified in the options then use that to
        authenticate. This may not be required if the environment has the
        following set:

        AWS_ACCESS_KEY_ID -  Your AWS Access Key ID
        AWS_SECRET_ACCESS_KEY - Your AWS Secret Access Key
        """
        return boto.connect_sqs(
            CONFIG.options.get('sqs_access_key'),
            CONFIG.options.get('sqs_secret_key'),
        )

    @classmethod
    def execute_task(cls, payload):
        """
        Execute the task for the given payload
        """
        result_options = ResultOptions._make(
            payload.get('__result_options__', [True, 60])
        )

        result = cls.execute(
            payload['model_name'],
            payload['method_name'],
            payload['args'],
            payload['kwargs'],
        )

        if not result_options.ignore_result:
            # Make the queue first
            queue = cls.get_queue(payload['__result_uuid__'], create=True)
            queue.set_timeout(result_options.visibility_timeout)

            # Send the result as message
            cls.send_to_sqs(queue, {'result': result})

        return result

    @classmethod
    def execute(cls, model, method, args, kwargs):
        """
        Execute the given task and return the result of the execution.
        """
        return getattr(Pool().get(model), method)(*args, **kwargs)

    @classmethod
    def defer(cls, model, method, args=None, kwargs=None,
              delay_seconds=0, attributes=None, result_options=None):
        """Wrapper for painless asynchronous dispatch of method
        inside given model.

        .. note::

            * Works only when called within a transaction.
            * Required only if the menthod is not already decorated as a
              async_sqs_task

        :param model: String representing global name of the model or
                      reference to model class itself.
        :param method: Name or method object
        :param args: positional arguments passed on to method as list/tuple.
        :param kwargs: keyword arguments passed on to method as dict.
        :returns :class:`AsyncResult`:
        """
        if isinstance(model, basestring):
            model_name = model
        else:
            model_name = model.__name__

        if isinstance(method, basestring):
            method_name = method
        else:
            method_name = method.__name__

        payload = {
            'database_name': Transaction().cursor.database_name,
            'user': Transaction().user,
            'model_name': model_name,
            'method_name': method_name,
            'args': args or [],
            'kwargs': kwargs or {},
            'context': Transaction().context,
        }
        return cls.send_to_sqs(
            cls.get_queue(create=True), payload,
            delay_seconds, attributes, result_options
        )

    @classmethod
    def get_queue(cls, name='trytond-async', create=False):
        """
        Retrieves the queue with the given name or None.

        The default name of the queue is `trytond-async`. This can be
        changed by setting the `sqs_queue` option in configuration.

        To specify the owner uses `sqs_queue_owner`
        """
        connection = cls.get_sqs_connection()

        queue_name = '-'.join(
            filter(
                None, [
                    CONFIG.options.get('sqs_queue_prefix', None),
                    Transaction().cursor.dbname.replace(':', ''),
                    CONFIG.options.get('sqs_queue', name),
                ]
            )
        )
        queue = connection.get_queue(
            queue_name,
            CONFIG.options.get('sqs_queue_owner')
        )
        if queue is None and create:
            queue = connection.create_queue(queue_name)

        return queue

    @classmethod
    def send_to_sqs(
            cls, queue, payload, delay_seconds=0,
            attributes=None, result_options=None):
        """
        Send the given payload to the queue.

        :param payload: The dictionary of the message to send
        :param delay_seconds: Number of seconds (0 - 900) to delay this message
                              from being processed.
        :param attributes: Message attributes to set.
        """
        connection = cls.get_sqs_connection()

        if result_options is None:
            result_options = ResultOptions(
                ignore_result=True,
                visibility_timeout=60,
            )
        payload['__result_uuid__'] = str(uuid4())
        payload['__result_options__'] = tuple(result_options)

        connection.send_message(
            queue,
            cls.serialize_payload(payload),
            delay_seconds=delay_seconds,
            message_attributes=attributes,
        )

        return cls._result_class(payload)

    @classmethod
    def get_json_encoder(cls):
        """
        Return the JSON encoder class. Use this if you want to implement your
        own serialization
        """
        return JSONEncoder

    @classmethod
    def serialize_payload(cls, payload):
        """
        Serialize the given payload to JSON
        """
        return json.dumps(payload, cls=cls.get_json_encoder())

    @classmethod
    def get_json_decoder(cls):
        """
        Return the JSON decoder class. Use this if you want to implement your
        own serialization
        """
        return JSONDecoder()

    @classmethod
    def deserialize_message(cls, message):
        """
        Deserialize the given message to a javascript payload
        """
        return json.loads(message, object_hook=cls.get_json_decoder())
