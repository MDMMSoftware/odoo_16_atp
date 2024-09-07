# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil.relativedelta import relativedelta
from math import copysign

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero, formatLang, end_of
from odoo.exceptions import ValidationError 

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    is_commission = fields.Boolean(string="Is Commission?",default=False)
    amount_commercial = fields.Float('Commission',compute='_compute_amounts',store=True)
    
    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total','order_line.commercial_amt')
    def _compute_amounts(self):
        """Compute the total amounts of the SO."""
        res = super(SaleOrder,self)._compute_amounts()
        for order in self:
            amount_commercial = amount_add = 0.0
            if order.is_commission:
               
                for line in order.order_line:
                    
                    amount_commercial += line.commercial_amt if line.commercial_type == 'amount' else (line.price_subtotal * line.commercial_amt /100)
                    # amount_add += line.add_amt if line.add_type == 'amount' else (line.price_subtotal * line.add_amt /100)
                order.update({
                    'amount_commercial': amount_commercial,
                })
    
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    commercial_type = fields.Selection([('amount','Amt'),('percentage','%')],string='Commission Type',default="percentage")
    commercial_amt = fields.Float('Commission Rate',copy=False)
    