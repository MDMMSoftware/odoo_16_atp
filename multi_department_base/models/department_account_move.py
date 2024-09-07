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


class AccountMove(models.Model):
    """inherited account move"""
    _inherit = "account.move"


    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(
            lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]

    department_id = fields.Many2one('res.department', string='Department', store=True,readonly=False,required=False,tracking=True)

    


class AccountMoveLine(models.Model):
    """inherited account move line"""
    _inherit = "account.move.line"

    department_id = fields.Many2one('res.department', related='move_id.department_id',readonly=False,required=False,
                                string='Department', store=True)
   
