# This file is part of the stock_supply_sale module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class StockSupplySaleTestCase(ModuleTestCase):
    'Test Stock Supply Sale module'
    module = 'stock_supply_sale'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        StockSupplySaleTestCase))
    return suite
