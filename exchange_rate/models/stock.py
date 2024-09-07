# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_price_unit(self):
        res = super()._get_price_unit()
        if self.purchase_line_id and not (self.origin_returned_move_id and self.origin_returned_move_id.sudo().stock_valuation_layer_ids):
            line = self.purchase_line_id
            order = line.order_id
            if order.currency_id != order.company_id.currency_id and order.exchange_rate:
                price_unit = order.company_id.currency_id._convert(
                    res, order.currency_id, order.company_id, fields.Date.context_today(self), round=False)
                price_unit = price_unit*order.exchange_rate
                return price_unit
            
        return res