from odoo import models,fields,api

class HrEmployee(models.Model):
	_inherit = 'hr.employee'
 
	hr_pro_education_id = fields.One2many('hr.pro.education','employee_id')
	# degree =fields.Text(string='Degree',compute='_onchange_degree')
	# other_qualif = fields.Text(string='Other Qualifications')
	

# Education 				
class HrProEducation(models.Model):
	_name = 'hr.pro.education'
	_description = 'Pro Education History'

	employee_id = fields.Many2one('hr.employee')
	pro_certificate = fields.Many2one('hr.education.certificate',string='Professional Certificate')
	org = fields.Many2one('hr.education.organization',string='Organization')
	issue_date = fields.Date('Issued Date')
	remark = fields.Char(string='Remark')



class HrEducationCertificate(models.Model):
	_name = 'hr.education.certificate'
	_description = 'Education Certificate'

	name = fields.Char(string="Certificate", required=True)


class HrEducationDegree(models.Model):
	_name = 'hr.education.organization'
	_description = 'Education Organization'

	name = fields.Char(string="Organization", required=True)

