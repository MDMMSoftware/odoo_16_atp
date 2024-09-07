from odoo import models,fields,api,_


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # accident_witness_ids = fields.One2many("employee.accident","witness_ids")
    accident_responsible_ids = fields.One2many("employee.accident","cost_and_compensation_responsible_ids")

    accident_ids = fields.One2many('employee.accident', 'employee_id', string="Accident History") 

    warning_ids = fields.One2many('hr.employee.warning', 'employee_id', string="Warning History") 

