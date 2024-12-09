# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    exclude_provision_currency_ids = fields.Many2many('res.currency', relation='account_account_exclude_res_currency_provision', help="Whether or not we have to make provisions for the selected foreign currencies.")
    cash_flow_type = fields.Many2one('cash.flow.type')

class CashFlowType(models.Model):
    _name = "cash.flow.type"
    
    name = fields.Char()
    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Owner name must be unique')
    ]