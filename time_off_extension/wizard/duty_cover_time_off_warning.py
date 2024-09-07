from odoo import models, fields, api,_

class DutyCoverWarning(models.Model):
    _name = "dutycover.timeoff.warning.wizard"

    message = fields.Text()
    prepare_id = fields.Many2one('hr.leave.prepare',string="Hr Leave")

    def action_approve(self):
        return self.prepare_id.action_hod_approve(skip=True)