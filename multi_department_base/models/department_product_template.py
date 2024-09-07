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


class ProductTemplate(models.Model):
    """inherited product"""
    _inherit = 'product.template'

    department_id = fields.Many2one("res.department", string='Department', store=True,required=False,
                                help='Leave this field empty if this product is'
                                     ' shared between all departmentes'
                                )
    allowed_department_ids = fields.Many2many('res.department', store=True,
                                          string="Allowed Departmentes",
                                          compute='_compute_allowed_department_ids')

    @api.depends('company_id')
    def _compute_allowed_department_ids(self):
        for po in self:
            po.allowed_department_ids = self.env.user.department_ids.ids
