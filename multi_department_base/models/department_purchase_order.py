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
from odoo.addons.purchase.models.purchase import PurchaseOrder as Purchase
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    """inherited purchase order"""
    _inherit = 'purchase.order'

    department_id = fields.Many2one("res.department", string='Department',tracking=True, store=True,required=False,readonly=False)

    allowed_department_ids = fields.Many2many('res.department', store=True,
                                          string="Allowed Departmentes",
                                          compute='_compute_allowed_department_ids')

    @api.depends('company_id')
    def _compute_allowed_department_ids(self):
        for po in self:
            po.allowed_department_ids = self.env.user.department_ids.ids

    
    def _prepare_invoice(self):
        """override prepare_invoice function to include department"""
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()
        invoice_vals['department_id'] = self.department_id.id or False
        return invoice_vals

    

class PurchaseOrderLine(models.Model):
    """inherited purchase order line"""
    _inherit = 'purchase.order.line'

    department_id = fields.Many2one(related='order_id.department_id', string='Department',
                                store=True)
