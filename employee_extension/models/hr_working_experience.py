from odoo import fields,models


class HrEmployee(models.Model):
	_inherit = 'hr.employee'

	work_exp_id = fields.One2many('hr.working.experience','employee_id')

class WorkExperience(models.Model):
	_name = 'hr.working.experience'
	_description = 'Working Experience Model'

	employee_id = fields.Many2one('hr.employee')
	name = fields.Char(string="Company Name")
	address = fields.Char(string="Address")
	from_date = fields.Char(string="From Date")
	to_date = fields.Char(string="To Date")
	l_position = fields.Char(string="Last Position")
	l_salary = fields.Float(string="Last Salary")
	currency = fields.Many2one('res.currency',string='Currency')
	desc = fields.Char('Job Description')
