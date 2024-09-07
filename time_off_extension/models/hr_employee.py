from odoo import models,api, fields




class HrDepartment(models.Model):
    _inherit = "hr.department"

    leave_ids = fields.One2many("hr.leave","department_ids")
