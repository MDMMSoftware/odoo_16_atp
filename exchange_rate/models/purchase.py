# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code
from odoo.tools.float_utils import float_compare, float_is_zero, float_round



class PurchaseOrder(models.Model):
    """inherited purchase order"""
    _inherit = 'purchase.order'

    exchange_rate = fields.Float('Exchange Rate',default=1.0)

    def _prepare_invoice(self):
        result = super(PurchaseOrder, self)._prepare_invoice()        
        result.update({'exchange_rate':self.exchange_rate})
        return result

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _get_stock_move_price_unit(self):
        self.ensure_one()
        order = self.order_id
        if self.order_id.exchange_rate:
            price_unit = self.price_unit * self.order_id.exchange_rate
        else:
            price_unit = self.price_unit
        price_unit_prec = self.env['decimal.precision'].precision_get('Product Price')
        if self.taxes_id:
            qty = self.product_qty or 1
            price_unit = self.taxes_id.with_context(round=False).compute_all(
                price_unit, currency=self.order_id.currency_id, quantity=qty, product=self.product_id, partner=self.order_id.partner_id
            )['total_void']
            price_unit = price_unit / qty
        if self.product_uom.id != self.product_id.uom_id.id:
            price_unit *= self.product_uom.factor / self.product_id.uom_id.factor
        if order.currency_id != order.company_id.currency_id:
            price_unit = order.currency_id._convert(
                price_unit, order.company_id.currency_id, self.company_id, self.date_order or fields.Date.today(), round=False)
        return float_round(price_unit, precision_digits=price_unit_prec)


    def _prepare_account_move_line(self, move=False):
        res:dict =  super()._prepare_account_move_line(move=False)
        res.update({'exchange_rate':self.order_id.exchange_rate})
        return res 