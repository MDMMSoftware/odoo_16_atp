# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import random

from babel.dates import format_date
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.release import version


class PurchaseTeam(models.Model):
    _name = "purchase.team"
    _inherit = ['mail.thread']
    _description = "Purchase Team"
    _order = "create_date DESC, id DESC"
    _check_company_auto = True


    # description
    name = fields.Char('Purchase Team', required=True, translate=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        related='company_id.currency_id', readonly=True)
    user_id = fields.Many2one('res.users', string='Team Leader', check_company=True)
    
    member_ids = fields.Many2many(
        'res.users', string='Purchasepersons')
  
   