from odoo import models,api, fields

class ResUser(models.Model):
    _inherit = "res.users"

    hr_department_ids = fields.One2many("hr.department","department_approve_user_id")
