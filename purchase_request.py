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
    def _get_origin(cls):
        origins = super(PurchaseRequest, cls)._get_origin()
        origins.add('product.product')
        return origins

    @classmethod
    def create_request_from_sales(cls, **params):
        '''Create requests from sales'''
        pool = Pool()
        Product = pool.get('product.product')
        Request = pool.get('purchase.request')
        Date = pool.get('ir.date')

        transaction = Transaction()
        today = Date.today()
        cursor = transaction.connection.cursor
        context = transaction.context

        warehouse = params['warehouse']
        days_for_average = params.get('days_for_average', 30)
        minimum_days = params.get('minimum_days', 15)
        quantity_average = params.get('quantity_average', 0)
        sporadic_supplier = params.get('sporadic_supplier', [])
        suppliers = params.get('suppliers', [])
        categories = params.get('categories', [])
        products = params.get('products', [])
        manufacturers = params.get('manufacturers', [])

        start_date = today - timedelta(days_for_average)
        sale = Table('sale_sale')
        sale_line = Table('sale_line')
        product = Table('product_product')
        template = Table('product_template')
        category = Table('product_category')
        supplier = Table('purchase_product_supplier')
        manufacturer = Table('party_party')
        query = sale_line.join(sale,
                condition=(sale.id == sale_line.sale)
            ).join(product,
                condition=(sale_line.product == product.id)
            ).join(template,
                condition=(product.template == template.id)
            )
        where = (
            (sale.sale_date > start_date) &
            (sale.sale_date < today) &
            (sale.state == 'done') &
            (template.type == 'goods') &
            (template.purchasable)
            )

        if suppliers:
            query = query.join(supplier,
                condition=template.id == supplier.product)
            where = where & supplier.party.in_([s.id for s in suppliers])

        if categories:
            query = query.join(category,
                condition=template.category == category.id)
            where = where & category.id.in_([c.id for c in categories])

        if manufacturers:
            query = query.join(manufacturer,
                condition=template.manufacturer == manufacturer.id)
            where = where & manufacturer.id.in_([m.id for m in manufacturers])

        if products:
            where = where & product.id.in_([p.id for p in products])

        query = query.select(
                sale_line.product.as_('product'),
                (Sum(sale_line.quantity) / days_for_average).as_(
                    'average_sold'),
            where=where,
            group_by=(
                sale_line.product
                ),
            having=(
                Sum(sale_line.quantity) / days_for_average > quantity_average
                )
            )

        cursor.execute(*query)

        product_average_sold = {p[0]: p[1] for p in cursor.fetchall()}
        if not product_average_sold:
            return
        product_ids = [p for p in product_average_sold]
        products = Product.browse(product_ids)

        if sporadic_supplier:
            suppliers = {p: sporadic_supplier
                for p in products}
        elif not suppliers:
            suppliers = {p: p.template.product_suppliers[0].party
                for p in products if p.template.product_suppliers}
        else:
            suppl = {}
            for product in products:
                suppl[product] = None
                for supplier in product.template.product_suppliers:
                    if supplier.party in suppliers:
                        suppl[product] = supplier.party
            suppliers = suppl

        requests = Request.search([
                    ('purchase_line', '=', None),
                    ('origin', 'like', 'product.product,%'),
                    ])
        cls.delete(requests)

        with transaction.set_context({'locations': [warehouse.id]}):
            product_quantity = Product.get_quantity(products, 'quantity')

        new_requests = []
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
            new_requests.append(request_values)

        cls.create(new_requests)


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
    sporadic_supplier = fields.Many2One('party.party', 'Sporadic Supplier')
    suppliers = fields.Many2Many('party.party', None, None,
        'Suppliers')
    categories = fields.Many2Many('product.category', None, None, 'Categories')
    products = fields.Many2Many('product.product', None, None, 'Products')
    manufacturers = fields.Many2Many('party.party', None, None,
        'Manufacturers')

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
        'stock_supply_sale.'
        'create_purchase_request_sale_wizard_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'request', 'tryton-ok', default=True),
            ])
    request = StateAction('stock_supply_sale.act_purchase_request')

    def do_request(self, action):
        PurchaseRequest = Pool().get('purchase.request')
        params = {
            'days_for_average': self.start.days_for_average,
            'minimum_days': self.start.minimum_days,
            'quantity_average': self.start.quantity_average,
            'warehouse': self.start.warehouse,
            'sporadic_supplier': self.start.sporadic_supplier,
            'suppliers': self.start.suppliers,
            'categories': self.start.categories,
            'products': self.start.products,
            'manufacturers': self.start.manufacturers,
            }

        PurchaseRequest.create_request_from_sales(**params)
        # return all draft purchase requests (not only new requests)
        action['pyson_domain'] = PYSONEncoder().encode([
                ('purchase_line', '=', None),
                ])
        return action, {}

    def transition_request(self):
        return 'end'
