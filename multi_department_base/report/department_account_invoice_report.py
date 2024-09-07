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

from odoo import fields, models


class AccountInvoiceReport(models.Model):
    """inherited invoice report"""
    _inherit = "account.invoice.report"

    department_id = fields.Many2one('res.department', 'Department', readonly=True,required=False)

    def _select(self):
        """select"""
        return super(AccountInvoiceReport, self)._select() + ", move.department_id as department_id"

    # def _group_by(self):
    #     """group by"""
    #     return super(AccountInvoiceReport, self)._group_by() + \
    #            ", move.department_id"
