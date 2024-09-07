# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code
from odoo.tools.float_utils import float_compare, float_is_zero, float_round



class SaleOrder(models.Model):
    """inherited sale order"""
    _inherit = 'sale.order'

    exchange_rate = fields.Float('Exchange Rate',default=1.0)


    def _prepare_invoice(self):
        result = super(SaleOrder, self)._prepare_invoice()
        result.update({'exchange_rate':self.exchange_rate})
        return result