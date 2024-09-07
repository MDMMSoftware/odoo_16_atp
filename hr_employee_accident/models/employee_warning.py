from odoo import models,fields,api,_
from odoo.exceptions import ValidationError, UserError

from datetime import datetime

class EmployeeWarning(models.Model):
    _name = "hr.employee.warning"

    def _get_warning_year(self):
        current_year = datetime.now().year
        return [(str(current_year - 1),str(current_year - 1)), (str(current_year),str(current_year)), (str(current_year + 1), str(current_year + 1))]

    name = fields.Char(default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee')

    company_id = fields.Many2one(related='employee_id.company_id', readonly=True, store=True)
    employee_job_position = fields.Many2one('hr.job')
    department_id = fields.Many2one('hr.department')
    employee_join_date = fields.Date(related='employee_id.trial_date_start', string="Join Date")
    warning_year = fields.Selection(selection=_get_warning_year,string="Year",default=str(datetime.now().year))
    by_spoken_warning = fields.Text(string="By Spoken Warning")
    by_spoken_warning_date = fields.Date()
    by_spoken_warning_type = fields.Many2one('hr.warning.type')
    fst_letter_warning = fields.Text(string="First Letter Warning")
    fst_letter_warning_date = fields.Date()
    fst_letter_warning_type = fields.Many2one('hr.warning.type')
    sec_letter_warning = fields.Text(string="Second Letter Warning")
    sec_letter_warning_date = fields.Date()
    sec_letter_warning_type = fields.Many2one('hr.warning.type')
    lst_letter_warning = fields.Text(string="Last Letter Warning")
    lst_letter_warning_date = fields.Date()
    lst_letter_warning_type = fields.Many2one('hr.warning.type')

    state = fields.Selection([
        ('draft','Draft'),
        ('by_spoken','By Spoken Warning'),
        ('fst_warning_letter','First Warning'),
        ('sec_warning_letter','Second Warning'),
        ('lst_warning_letter','Last Warning'),
        ('consider','Consideration'),
    ],default="draft")
    deduction_ids = fields.One2many('hr.salary.deduction','warning_id')

    def _get_employee_domain(self):
        
        return ['|',('user_id','=',self.env.user.id),('department_id', 'in', self.env.user.hr_department_ids.ids)]


    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for rec in self:
            rec.department_id = rec.employee_id.department_id
            rec.employee_job_position = rec.employee_id.job_id

    @api.onchange('by_spoken_warning_date','fst_letter_warning_date','sec_letter_warning_date','lst_letter_warning_date')
    def _check_warning_dates(self):
        for rec in self:
            if rec.by_spoken_warning_date:
                if str(rec.by_spoken_warning_date.year) != rec.warning_year:
                    raise ValidationError(_('Invalid Date'))
            elif rec.fst_letter_warning_date:
                if str(rec.fst_letter_warning_date.year) != rec.warning_year:
                    raise ValidationError(_('Invalid Date'))
            elif rec.sec_letter_warning_date:
                if str(rec.sec_letter_warning_date.year) != rec.warning_year:
                    raise ValidationError(_('Invalid Date'))
            elif rec.lst_letter_warning_date:
                if str(rec.lst_letter_warning_date.year) != rec.warning_year:
                    raise ValidationError(_('Invalid Date'))

    @api.constrains('warning_year')
    def _check_warning_year(self):
        for rec in self:
            check_warning = self.search([('id','!=',rec.id),('employee_id','=',rec.employee_id.id),('warning_year','=',rec.warning_year)])
            if check_warning:
                raise ValidationError('Warning of %s in %s is already exist.' %(rec.employee_id.name, rec.warning_year))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.employee.warning') or _('New')
        res = super(EmployeeWarning, self).create(vals)
        # check_deduction = self.env['hr.salary.deduction'].search_count([
        #     ('warning_id','=',res.id)
        # ])
        # if check_deduction == 0:
        #     self.env['hr.salary.deduction'].create({
        #         'name': res.name,
        #         'employee_id': res.employee_id.id,
        #         'warning_id':res.id
                
        #     })
        return res

    def action_open_deduction_form(self):
        
        return {
            'name': _('Salary Deduction'),
            'res_model': 'hr.salary.deduction',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'view_mode': 'tree,form',
            'domain': [('warning_id', '=',self.id)],              

        }
    def action_by_spoken(self):
        self.ensure_one()
        self.state = 'by_spoken'

    def action_fst_warning(self):
        self.ensure_one()
        self.state = 'fst_warning_letter'

    def action_sec_warning(self):
        self.ensure_one()
        self.state = 'sec_warning_letter'

    def action_lst_warning(self):
        self.ensure_one()
        self.state = 'lst_warning_letter'

    def action_consider(self):
        self.ensure_one()
        self.state = 'consider'
 
    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You cannot delete a resign request which is in the %s state',self.state))
        return super().unlink()

    def create_warning_form_by_year(self):
        employees = self.env['hr.employee'].search([])
        filtered_employees = employees.filtered(lambda emp: not self.env['hr.employee.warning'].search_count([
                 ('employee_id', '=', emp.id),
                ('warning_year', '=', str(datetime.now().year))
                 ]))      
        for emp in filtered_employees:
            self.create({
                'employee_id': emp.id,
                'employee_job_position': emp.job_id.id,
                'department_id': emp.department_id.id,
                'warning_year': str(datetime.now().year)
            })



class HrWarningType(models.Model):
    _name = "hr.warning.type"

    name = fields.Char('Name')