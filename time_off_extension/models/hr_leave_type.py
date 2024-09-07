from odoo import models, fields, api
from odoo.tools.translate import _
from collections import defaultdict
from odoo.addons.resource.models.resource import Intervals
from datetime import time, timedelta
import datetime

class HrLeave(models.Model):
    _inherit = "hr.leave.type"

    allow_allocation_days = fields.Integer('Allow Allocation Days')
    configuration_months = fields.Integer('Configuration Months')
    warning_over_days = fields.Integer('Warning Over Days',default=0)
    is_payroll_related = fields.Boolean(default=True)
    burmese_name = fields.Char(string='Time off Name(Myanmar)',required=True)


    @api.model
    def get_days_all_request(self):
        result = super(HrLeave, self).get_days_all_request()
        for holiday in result:
            holiday[1]['burmese_name'] = self.browse(holiday[3]).burmese_name
        return result
    
    
    def _get_contextual_employee_id(self):
        if 'employee_id' in self._context:
            employee_id = self._context['employee_id']
        elif 'default_employee_id' in self._context:
            employee_id = self._context['default_employee_id']
        else:
            employee_id = self.env.user.employee_id.id or self.env['hr.employee'].search([('user_id','=',self.env.user.id)]).id
        return employee_id