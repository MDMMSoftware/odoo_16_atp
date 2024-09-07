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


class DepartmentPartner(models.Model):
    """inherited partner"""
    _inherit = "res.partner"

    department_id = fields.Many2one("res.department", string='Department', store=True,required=False,
                                help='Leave this field empty if the partner is'
                                     ' shared between all departmentes',
                                domain="[('id', 'in', allowed_department_ids)]",
                                )
    allowed_department_ids = fields.Many2many('res.department', store=True,
                                          string="Departmentes",
                                          compute="_compute_allowed_department_ids")


    @api.depends('company_id')
    def _compute_allowed_department_ids(self):
        for po in self:
            if po.is_multiple_company:
                if po.company_id:
                    department_ids = []
                    for rec in po.env.user.department_ids:
                        if rec.company_id == po.company_id:
                            department_ids.append(rec.id)
                    po.allowed_department_ids = department_ids
                else:
                    po.allowed_department_ids = po.env.user.department_ids.ids
            else:
                po.allowed_department_ids = po.env.user.department_ids.ids

   


    