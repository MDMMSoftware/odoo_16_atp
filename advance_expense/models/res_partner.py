# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _


class Partner(models.Model):
    _description = 'Contact'
    _inherit = "res.partner"

    advance_user = fields.Boolean(string="Advance User",default=False)
    property_account_advance_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Advance",
        domain="[('account_type', 'in', ['liability_payable','asset_receivable']), ('non_trade', '=', True), ('company_id', '=', current_company_id)]",
        help="This account will be used instead of the default one as the advance account for the current partner",
        required=True)
    
    

