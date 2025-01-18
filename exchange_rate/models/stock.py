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
        elif self.purchase_line_id and self.origin_returned_move_id and self.origin_returned_move_id.sudo().stock_valuation_layer_ids and self.origin_returned_move_id.sudo().stock_valuation_layer_ids.mapped('stock_landed_cost_id'):
            layers = self.origin_returned_move_id.sudo().stock_valuation_layer_ids.filtered(lambda x:not x.stock_landed_cost_id)
            # this code piece is from the original code of _get_price_unit() , but we exclude the valuation layer with landed cost 
            # layers = self.origin_returned_move_id.sudo().stock_valuation_layer_ids
            # dropshipping create additional positive svl to make sure there is no impact on the stock valuation
            # We need to remove them from the computation of the price unit.
            if self.origin_returned_move_id._is_dropshipped() or self.origin_returned_move_id._is_dropshipped_returned():
                layers = layers.filtered(lambda l: float_compare(l.value, 0, precision_rounding=l.product_id.uom_id.rounding) <= 0)
            # layers |= layers.stock_valuation_layer_ids
            quantity = sum(layers.mapped("quantity"))
            return sum(layers.mapped("value")) / quantity if not float_is_zero(quantity, precision_rounding=layers.uom_id.rounding) else 0
        return res