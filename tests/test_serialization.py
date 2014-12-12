# -*- coding: UTF-8 -*-
"""
    trytond_async_sqs.serialization

    Test the serialization and deserialization

    :copyright: (c) 2013-2014 by Openlabs Technologies & Consulting (P) LTD
    :copyright: (c) 2014 by Tryton authors
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

import trytond.tests.test_tryton
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT, POOL
from trytond.transaction import Transaction


class TestSerialization(unittest.TestCase):
    '''
    Test serialization and deserialization
    '''

    def setUp(self):
        """
        Set up data used in the tests.
        this method is called before each test function execution.
        """
        trytond.tests.test_tryton.install_module('async_sqs')

    def test_active_records(self):
        '''
        Test serialization and deserialization of active records
        '''
        User = POOL.get('res.user')
        Async = POOL.get('async.async')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            user1, = User.search([], limit=1)
            serialized = Async.serialize_payload({'obj': user1})

            self.assertEqual(
                Async.deserialize_message(serialized)['obj'],
                user1
            )


def suite():
    """
    Define suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestSerialization)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
