# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'hr.employee'

    plan_to_change_car = fields.Boolean('Plan To Change Car', default=False)
    plan_to_change_bike = fields.Boolean('Plan To Change Bike', default=False)

    future_driver_id = fields.Many2one('hr.employee', 'Future Driver', tracking=True, help='Next Driver Address of the vehicle', copy=False, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")    