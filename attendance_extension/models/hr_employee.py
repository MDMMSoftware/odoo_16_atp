from odoo import fields, models, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    att_allow_all_device = fields.Boolean(default=False)