from odoo import models,fields,api

class HrEmployee(models.Model):
	_inherit = 'hr.employee'
 
	hr_education_id = fields.One2many('hr.education','employee_id')
	degree =fields.Text(string='Degree',compute='_onchange_degree')
	other_qualif = fields.Text(string='Other Qualifications')
	
	@api.onchange('hr_education_id')
	def _onchange_degree(self):
		degree_format = ''
		for emp in self:
			for educate in emp.hr_education_id:
				if educate.bol == True:
					if educate.ed_type_id and educate.ed_degree_id and educate.ed_major_id and educate.ed_college_id:
						degree_format += f'{educate.ed_type_id.name}/{educate.ed_degree_id.name}/{educate.ed_major_id.name}/{educate.ed_college_id.name}\n'
			emp.degree = degree_format

# Education 				
class HrEducation(models.Model):
	_name = 'hr.education'
	_description = 'Education History'

	employee_id = fields.Many2one('hr.employee')
	ed_type_id = fields.Many2one('hr.education.type',string='Education Type')
	ed_degree_id = fields.Many2one('hr.education.degree',string='Degree')
	ed_major_id = fields.Many2one('hr.education.major',string='Major')
	ed_college_id = fields.Many2one('hr.education.college',string='College/University')

	from_yrs = fields.Char(string='From')
	to_yrs = fields.Char(string='To')
	bol = fields.Boolean()



# Education Type
class HrEducationType(models.Model):
	_name = 'hr.education.type'
	_description = 'Hr Education Type Model'

	name = fields.Char(string="Education Type", required=True)

# Education Degree
class HrEducationDegree(models.Model):
	_name = 'hr.education.degree'
	_description = 'Hr Education Degree'

	name = fields.Char(string="Degree", required=True)

# Education Major
class HrEducationMajor(models.Model):
	_name = 'hr.education.major'
	_description = 'Hr Education Major'

	name = fields.Char(string="HR Education Major", required=True)

# Education College
class HrEducationCollege(models.Model):
	_name = 'hr.education.college'
	_description = 'Hr Education College'

	name = fields.Char(string='College', required=True)

