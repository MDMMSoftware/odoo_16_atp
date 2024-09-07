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

from odoo import models, fields, api


class StockPicking(models.Model):
    """inherited stock.picking"""
    _inherit = "stock.picking"

    def _get_default_department_id(self):
        if len(self.env.user.department_ids) == 1:
            sp_company = self.company_id if self.company_id else self.env.company
            department_ids = self.env.user.department_ids
            department = department_ids.filtered(
                lambda department: department.company_id == sp_company)
            if department:
                return department
            else:
                return False
        return False

    department_id = fields.Many2one("res.department", string='Department',required=False,tracking=True,
                                readonly=False, store=True,
                                compute="_compute_department_id",
                                default=_get_default_department_id)

    @api.depends('sale_id', 'purchase_id')
    def _compute_department_id(self):
        """methode to compute department"""
        for record in self:
            record.department_id = False
            if record.sale_id.department_id:
                record.department_id = record.sale_id.department_id
            if record.purchase_id.department_id:
                record.department_id = record.purchase_id.department_id
                for move_id in record.move_ids:
                    move_id.department_id = record.purchase_id.department_id


class StockPickingTypes(models.Model):
    """inherited stock picking type"""
    _inherit = "stock.picking.type"

    department_id = fields.Many2one('res.department', string='Department',readonly=True, store=True,required=False,
                                related='warehouse_id.department_id')
