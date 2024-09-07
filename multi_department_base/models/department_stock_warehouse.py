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


class StockWarehouse(models.Model):
    """inherited stock warehouse"""
    _inherit = "stock.warehouse"

   

    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(
            lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]

    department_id = fields.Many2one('res.department', string='Department',readonly=True, store=True,
                                required=False,
                                help='Leave this field empty if this warehouse '
                                     ' is shared between all departmentes')


class DepartmentStockMove(models.Model):
    """inherited stock.move"""
    _inherit = 'stock.move'

    department_id = fields.Many2one('res.department', readonly=True, store=True,required=False,related=False)


class DepartmentStockMoveLine(models.Model):
    """inherited stock move line"""
    _inherit = 'stock.move.line'

    department_id = fields.Many2one('res.department', readonly=True, store=True,required=False,
                                related='move_id.department_id')


class DepartmentStockValuationLayer(models.Model):
    """Inherited Stock Valuation Layer"""
    _inherit = 'stock.valuation.layer'

    department_id = fields.Many2one('res.department', readonly=True, store=True,required=False,
                                related='stock_move_id.department_id')
