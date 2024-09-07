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

import logging
from odoo import models, fields, api


_logger = logging.getLogger(__name__)


class Branch(models.Model):
    """res branch"""
    _name = "res.branch"
    _description = 'Company Branches'
    _order = 'name'

    name = fields.Char(string='Branch', required=True, store=True)
    short_code = fields.Char(string='Short Code', required=True)
    company_id = fields.Many2one('res.company', required=True, string='Company')
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one(
        'res.country.state',
        string="Fed. State", domain="[('country_id', '=?', country_id)]"
    )
    country_id = fields.Many2one('res.country',  string="Country")
    email = fields.Char(store=True, )
    phone = fields.Char(store=True)
    website = fields.Char(readonly=False)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Branch name must be unique !')
    ]

    def action_view_sequence_model(self):
        sequences = self.env['sequence.model'].search([('branch_id','=',self.id)]).ids
        action = self.env['ir.actions.actions']._for_xml_id('customize_sequence.view_sequence_model_action')
        if len(sequences) > 1 or len(sequences) == 0:
            action['domain'] = [('id', 'in', sequences)]
        elif len(sequences) == 1:
            form_view = [(self.env.ref('customize_sequence.view_sequence_mode_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = sequences[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action