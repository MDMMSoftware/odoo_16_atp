# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2022-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    """inherited sale order"""
    _inherit = 'sale.order'
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")

    @api.model
    def _default_warehouse_id(self):
        """methode to get default warehouse id"""
        # !!! Any change to the default value may have to be repercuted
        # on _init_column() below.
        return self.env.user._get_default_warehouse_id()

    department_id = fields.Many2one("res.department", string='Department', store=True,required=False,tracking=True,
                                readonly=False)
    
    allowed_department_ids = fields.Many2many('res.department', store=True,
                                          string="Allowed Departmentes",
                                          compute='_compute_allowed_department_ids')

    @api.depends('company_id')
    def _compute_allowed_department_ids(self):
        for so in self:
            so.allowed_department_ids = self.env.user.department_ids.ids

    @api.depends('company_id')
    def _compute_department(self):
        for order in self:
            order.department_id = False
            if len(self.env.user.department_ids) == 1:
                company = self.env.company
                so_company = order.company_id if order.company_id else self.env.company
                department_ids = self.env.user.department_ids
                department = department_ids.filtered(
                    lambda department: department.company_id == so_company)
                if department:
                    order.department_id = department.ids[0]
                else:
                    order.department_id = False

    
    def _prepare_invoice(self):
        """override prepare_invoice function to include department"""
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        
        invoice_vals['department_id'] = self.department_id.id or False
        
        return invoice_vals

   


class SaleOrderLine(models.Model):
    """inherited purchase order line"""
    _inherit = 'sale.order.line'

    department_id = fields.Many2one(related='order_id.department_id',required=False,
                                string='Department', store=True)
