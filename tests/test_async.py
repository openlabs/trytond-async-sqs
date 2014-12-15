# -*- coding: UTF-8 -*-
"""
    trytond_async_sqs.async

    Test the serialization and deserialization

    :copyright: (c) 2013-2014 by Openlabs Technologies & Consulting (P) LTD
    :license: 3-clause BSD License, see COPYRIGHT for more details
"""
import sys
import os
if 'DB_NAME' not in os.environ:
    os.environ['DB_NAME'] = ':memory:'
DIR = os.path.abspath(os.path.normpath(os.path.join(
    __file__, '..', '..', '..', '..', '..', 'trytond'
)))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))
import unittest


# Mock SQS out
import boto
from moto import mock_sqs

import trytond.tests.test_tryton
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT, POOL
from trytond.transaction import Transaction
from trytond.modules.async_sqs import ResultOptions


class TestAsync(unittest.TestCase):
    """
    Test the async implementation.

    Remember that most of this requires an AWS account to test
    """
    @mock_sqs
    def setUp(self):
        """
        Set up data used in the tests.
        this method is called before each test function execution.
        """
        trytond.tests.test_tryton.install_module('async_sqs')

        Async = POOL.get('async.async')
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            queue = Async.get_queue()
            if queue is not None:
                queue.delete()

    def test_get_connection(self):
        '''
        Ensure that get connection works
        '''
        Async = POOL.get('async.async')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            connection = Async.get_sqs_connection()
            self.assertTrue(
                isinstance(connection, boto.sqs.connection.SQSConnection)
            )

    def test_execute_task(self):
        """
        Given a payload a task should get executed
        """
        Async = POOL.get('async.async')
        IRUIView = POOL.get('ir.ui.view')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            result = Async.execute_task({
                'model_name': 'ir.ui.view',
                'method_name': 'search',
                'args': [[]],
                'kwargs': {'limit': 10},
                'instance': None,
            })
            self.assertEqual(
                result,
                IRUIView.search([], limit=10)
            )

    def test_execute_task_instance(self):
        """
        Given a payload a task should get executed
        """
        Async = POOL.get('async.async')
        IRUIView = POOL.get('ir.ui.view')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            view, = IRUIView.search([], limit=1)
            result = Async.execute_task({
                'model_name': IRUIView,
                'method_name': 'get_rec_name',
                'args': [None],
                'kwargs': {},
                'instance': view,
            })
            self.assertEqual(result, view.get_rec_name(None))

    @mock_sqs
    def test_defer(self):
        """
        Test the sending of message
        """
        Async = POOL.get('async.async')
        IRUIView = POOL.get('ir.ui.view')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            conn = Async.get_sqs_connection()

            ids = map(int, IRUIView.search([], limit=10))
            Async.defer(
                model=IRUIView,
                method=IRUIView.read,
                args=[ids, ['name']],
            )

            # Chech that there is 1 message int he queue
            queue = Async.get_queue()
            messages = conn.receive_message(queue, number_messages=2)

            self.assertEqual(len(messages), 1)

    @mock_sqs
    def test_defer_instance(self):
        """
        Test the sending of message for instance method
        """
        Async = POOL.get('async.async')
        IRUIView = POOL.get('ir.ui.view')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            conn = Async.get_sqs_connection()

            view, = IRUIView.search([], limit=1)
            Async.defer(
                instance=view,
                method=IRUIView.get_rec_name,
                args=[None],
            )

            # Chech that there is 1 message int he queue
            queue = Async.get_queue()
            messages = conn.receive_message(queue, number_messages=2)

            self.assertEqual(len(messages), 1)

    @mock_sqs
    def test_defer_execution(self):
        """
        Test the sending of message and that it executes as expected
        """
        Async = POOL.get('async.async')
        IRUIView = POOL.get('ir.ui.view')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            conn = Async.get_sqs_connection()

            ids = map(int, IRUIView.search([], limit=10))
            Async.defer(
                model=IRUIView,
                method=IRUIView.read,
                args=[ids, ['name']]
            )

            # Manually send the message to execute
            queue = Async.get_queue()
            message, = conn.receive_message(queue, number_messages=1)
            result = Async.execute_task(
                Async.deserialize_message(message.get_body())
            )

            # Now ensure that the result is same
            self.assertEqual(result, IRUIView.read(ids, ['name']))

    @mock_sqs
    def test_defer_execution_instance(self):
        """
        Test the sending of message and that it executes as expected
        on the instance
        """
        Async = POOL.get('async.async')
        IRUIView = POOL.get('ir.ui.view')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            conn = Async.get_sqs_connection()

            view, = IRUIView.search([], limit=1)
            Async.defer(
                model=IRUIView,
                method=IRUIView.get_rec_name,
                instance=view,
                args=[None]
            )

            # Manually send the message to execute
            queue = Async.get_queue()
            message, = conn.receive_message(queue, number_messages=1)
            result = Async.execute_task(
                Async.deserialize_message(message.get_body())
            )

            # Now ensure that the result is same
            self.assertEqual(result, view.get_rec_name(None))

    @mock_sqs
    def test_defer_result(self):
        """
        Test the sending of message and that it executes as expected
        """
        Async = POOL.get('async.async')
        IRUIView = POOL.get('ir.ui.view')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            conn = Async.get_sqs_connection()

            ids = map(int, IRUIView.search([], limit=10))
            result_async = Async.defer(
                model=IRUIView,
                method=IRUIView.read,
                args=[ids, ['name']],
                kwargs={},
                result_options=ResultOptions(False, 60)
            )
            expected_result = IRUIView.read(ids, ['name'])

            # Manually send the message to execute
            queue = Async.get_queue()
            message, = conn.receive_message(queue, number_messages=100)
            Async.execute_task(
                Async.deserialize_message(message.get_body())
            )

            # Now ensure that the result is same
            self.assertEqual(expected_result, result_async.wait())


def suite():
    """
    Define suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestAsync)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
