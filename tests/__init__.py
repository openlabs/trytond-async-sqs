# -*- coding: utf-8 -*-
"""
    tests/__init__.py

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import unittest

import trytond.tests.test_tryton

# from tests.test_views_depends import TestViewsDepends
from tests.test_serialization import TestSerialization
from tests.test_async import TestAsync


def suite():
    """
    Define suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests([
        # unittest.TestLoader().loadTestsFromTestCase(TestViewsDepends),
        unittest.TestLoader().loadTestsFromTestCase(TestSerialization),
        unittest.TestLoader().loadTestsFromTestCase(TestAsync),
    ])
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
