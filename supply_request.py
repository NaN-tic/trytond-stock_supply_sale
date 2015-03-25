# This file is part stock_supply_sale module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from datetime import timedelta
from math import ceil
from sql import Table
from sql.aggregate import Sum
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button

__all__ = ['PurchaseRequest', 'CreatePurchaseRequestSaleWizardStart',
    'CreatePurchaseRequestSaleWizard']
__metaclass__ = PoolMeta


class PurchaseRequest:
    __name__ = 'purchase.request'

    @classmethod
    def get_origin(cls):
        pool = Pool()
        IrModel = pool.get('ir.model')
        origins = super(PurchaseRequest, cls).get_origin()
        model, = IrModel.search([
                ('model', '=', 'product.product'),
                ])
        origins.append((model.model, model.name))
        return origins

    @classmethod
    def create_request_from_sales(cls, warehouse, days_for_average=30,
            minimum_days=15, quantity_average=0):
        '''Create requests from sales
        @param warehouse: obj
        @param days_for_average: Default 30
        @param minimum_days: Default 12
        @param quantity_average: Default 0
        '''
        pool = Pool()
        Product = pool.get('product.product')
        Request = pool.get('purchase.request')
        Date = pool.get('ir.date')

        transaction = Transaction()
        today = Date.today()
        cursor = transaction.cursor
        context = transaction.context

        start_date = today - timedelta(days_for_average)
        sale = Table('sale_sale')
        sale_line = Table('sale_line')
        product = Table('product_product')
        template = Table('product_template')
        query = sale_line.join(sale,
                condition=(sale.id == sale_line.sale)
            ).join(product,
                condition=(sale_line.product == product.id)
            ).join(template,
                condition=(product.template == template.id)
            ).select(
                sale_line.product.as_('product'),
                (Sum(sale_line.quantity) / days_for_average).as_(
                    'average_sold'),
            where=(
                (sale.sale_date > start_date) &
                (sale.sale_date < today) &
                (sale.state == 'done') &
                (template.type == 'goods')
                ),
            group_by=(
                sale_line.product
                ),
            having=(
                Sum(sale_line.quantity) / days_for_average > quantity_average
                )
            )
        cursor.execute(*query)

        product_average_sold = {p[0]: p[1] for p in cursor.fetchall()}
        product_ids = [p for p in product_average_sold]
        products = Product.browse(product_ids)
        suppliers = {p: p.product_suppliers[0].party
            for p in products if p.product_suppliers}

        with transaction.set_context(locations=warehouse):
            product_quantity = Product.get_quantity(products, 'quantity')
        requests = {p.product: p for p in Request.search([
                    ('purchase_line.moves', '=', None),
                    ('purchase_line.purchase.state', '!=', 'cancel'),
                    ('origin', 'like', 'product.product,%'),
                    ])}

        for product in products:
            party = suppliers.get(product, None)
            if product.id in product_quantity:
                quantity = ceil(product_average_sold[product.id] *
                    minimum_days -
                    product_quantity[product.id])
            else:
                quantity = ceil(product_average_sold[product.id] *
                    minimum_days)
            if quantity <= 0.0:
                continue

            request_values = {
                'product': product,
                'party': party or None,
                'quantity': quantity,
                'uom': product.default_uom,
                'computed_quantity': quantity,
                'computed_uom': product.default_uom,
                'stock_level': product_quantity.get(product.id, 0.0),
                'warehouse': warehouse,
                'origin': 'product.product,%s' % product.id,
                'state': 'draft',
                'purchase_line': None,
                'company': context['company'],
                }
            if not requests.get(product, None):
                request, = Request.create([request_values])
                requests[product] = request
            else:
                request = requests[product]
                Request.write([request], request_values)
        requests = [requests[r].id for r in requests]
        return requests


class CreatePurchaseRequestSaleWizardStart(ModelView):
    'Create Purchase Request Sale Wizard Start'
    __name__ = 'create.purchase.request.sale.wizard.start'
    days_for_average = fields.Integer('Days for Average Compute',
        required=True, help='Days to compute the average daily sales.')
    minimum_days = fields.Integer('Minimum Days', required=True,
        help='Minimum days of stock you want.')
    quantity_average = fields.Float('Quantity Average', digits=(16, 2),
        required=True,
        help='Minimum quantity average of daily sales of product.')
    warehouse = fields.Many2One('stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], required=True)

    @staticmethod
    def default_days_for_average():
        return 30

    @staticmethod
    def default_minimum_days():
        return 15

    @staticmethod
    def default_quantity_average():
        return 0

    @staticmethod
    def default_warehouse():
        Warehouse = Pool().get('stock.location')
        warehouses = Warehouse.search([
                ('type', '=', 'warehouse'),
                ])
        if len(warehouses) == 1:
            return warehouses[0].id


class CreatePurchaseRequestSaleWizard(Wizard):
    'Create Purchase Request Sale Wizard'
    __name__ = 'create.purchase.request.sale.wizard'
    start = StateView('create.purchase.request.sale.wizard.start',
        'stock_supply_sale.create_purchase_request_sale_wizard_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'request', 'tryton-ok', default=True),
            ])
    request = StateAction('stock_supply_sale.act_purchase_request')

    def do_request(self, action):
        PurchaseRequest = Pool().get('purchase.request')

        days_for_average = self.start.days_for_average
        minimum_days = self.start.minimum_days
        quantity_average = self.start.quantity_average
        warehouse = self.start.warehouse

        PurchaseRequest.create_request_from_sales(
            warehouse,
            days_for_average,
            minimum_days,
            quantity_average,
            )
        # return all draft purchase requests (not only new requests)
        action['pyson_domain'] = PYSONEncoder().encode([
                ('purchase_line', '=', None),
                ])
        return action, {}
            
    def transition_request(self):
        return 'end'
