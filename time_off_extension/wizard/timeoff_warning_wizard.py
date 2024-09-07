from odoo import models, fields, api,_

class TimeoffWarning(models.Model):
    _name = "timeoff.warning.wizard"

    message = fields.Text()
    hr_leave_id = fields.Many2one('hr.leave',string="Hr Leave")

    def action_approve(self):
        return self.hr_leave_id.action_approve(skip=True)