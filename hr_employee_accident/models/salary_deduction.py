from odoo import models, api, _, fields
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

MONTHS = {'1':'Jan','2':'Feb','3':'March','4':'April','5':'May','6':'June','7':'July','8':'August','9':'Sep','10':'Oct','11':'Nov','12':'Dec'}

class SalaryDeduction(models.Model):
    _name = "hr.salary.deduction"

    name = fields.Char('Name',compute="_compute_name")
    employee_id = fields.Many2one('hr.employee')
    total_deduction_amt = fields.Float('Total Deduction',tracking=True)
    state = fields.Selection([
        ('draft','Draft'),
        ('done','Done'),
    ],default="draft")
    accident_id = fields.Many2one('employee.accident',ondelete='cascade')
    warning_id = fields.Many2one('hr.employee.warning',ondelete='cascade')
    deduction_date = fields.Date()
    deduction_lines = fields.One2many('hr.salary.deduction.line','deduction_id',ondelete="cascade")
    cost_and_compensation_responsible_ids = fields.Many2many('hr.employee','deduction_emp_rel', 
                                        related="accident_id.cost_and_compensation_responsible_ids")
    department_id = fields.Many2one('hr.department', related="employee_id.department_id")

    @api.onchange('employee_id')
    def _onchange(self):
        for rec in self:
            if rec.warning_id:
                return {'domain':{'employee_id': [('id','=',rec.warning_id.employee_id.id)]}}
            
    def _compute_name(self):
        for rec in self:
            if rec.accident_id:
                rec.name = rec.accident_id.name
            elif rec.warning_id:
                rec.name = rec.warning_id.name
            else:
                rec.name = False

    @api.constrains('employee_id')
    def _check_employee_duplicate(self):
        for rec in self:
            if rec.accident_id:
                if self.search_count([('id','!=',rec.id),('employee_id','=',rec.employee_id.id),('accident_id','=',rec.accident_id.id)]) > 0:
                    raise ValidationError('Salary Deduction for %s is already set' %(rec.employee_id.name))

    def write(self,vals):
        if 'total_deduction_amt' in vals:
            if vals['total_deduction_amt'] != self.total_deduction_amt and self.deduction_lines:
                current_opening_amt = vals['total_deduction_amt']
                for line in self.deduction_lines:
                    line.write({'opening_amt':current_opening_amt})
                    current_opening_amt = current_opening_amt - line.deduction_amt
        return super().write(vals)

    def action_done(self):
        for rec in self:
            rec.state = 'done'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You cannot delete a resign request which is in the %s state',self.state))
        return super().unlink()

    # def create(self, vals):
    #     if 'warning_id' in vals[0]:

    #         warning = self.env['hr.employee.warning'].browse(vals[0]['warning_id'])
    #         vals[0]['employee_id'] = warning.employee_id.id
    #     return super(SalaryDeduction, self).create(vals)
    def action_open_deduction_line(self):
        
        return {
            'name': _('Salary Deduction'),
            'res_model': 'hr.salary.deduction',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'view_mode': 'tree,form',
            'domain': [('id', '=',self.id)],              

        }

class SalaryDeductionLine(models.Model):
    _name = "hr.salary.deduction.line"


    def _get_deduction_years(self):
        current_year = datetime.now().year
        return [(str(current_year - 1),str(current_year - 1)), (str(current_year),str(current_year)), (str(current_year + 1), str(current_year + 1))]

    deduction_id = fields.Many2one('hr.salary.deduction')
    employee_id = fields.Many2one('hr.employee')
    department_id = fields.Many2one('hr.department', related="employee_id.department_id")

    total_deduction_amt = fields.Float('Total Deduction')
    opening_amt = fields.Float()
    deduction_year = fields.Selection(selection=_get_deduction_years,string="Year",default=str(datetime.now().year))
    deduction_month = fields.Selection(selection=[('1','Jan'),('2','Feb'),('3','March'),('4','April'),('5','May'),('6','June'),
                                                 ('7','July'),('8','August'),('9','Sep'),('10','Oct'),('11','Nov'),('12','Dec')],string="Month",default=str(datetime.now().month))
    deduction_amt = fields.Float('Deduction Amount')
    # deduction_type = fields.Selection([
    #     ('accident','Accident'),
    #     ('warning','Warning'),
    #     ('payroll','Payroll')
    # ], default="payroll")
    deduction_type_id = fields.Many2one('deduction.type')
    deduction_type_name = fields.Char(related="deduction_type_id.name")
    description = fields.Char()
    state = fields.Selection([
        ('draft','Draft'),
        ('approve','Approve'),
    ],default="draft")

    @api.onchange('deduction_type_name')
    def _onchange_deduction_id(self):
        for rec in self:
            if rec.deduction_id:
                if rec.deduction_id.accident_id or rec.deduction_id.warning_id:
                    rec.opening_amt = rec.deduction_id.total_deduction_amt - sum(rec.deduction_id.deduction_lines.mapped('deduction_amt'))

    @api.onchange('deduction_amt')
    def _onchange_deduction_amt(self):
        for rec in self:
            if rec.deduction_id:
                rec.employee_id = rec.deduction_id.employee_id
                rec.total_deduction_amt = rec.deduction_id.total_deduction_amt
                if rec.deduction_id.accident_id:
                    
                    deduction_type = self.env['deduction.type'].search([('name','=','Accident')],limit=1)
                    rec.deduction_type_id = deduction_type
                else:
                    deduction_type = self.env['deduction.type'].search([('name','=','Warning')],limit=1)

                    rec.deduction_type_id = deduction_type
                    # rec.deduction_year = rec.deduction_id.warning_id.
            else:
                rec.total_deduction_amt = 0
            
    @api.constrains('deduction_month','deduction_year')
    def _check_deduction_month_year(self):
        for rec in self:
            check_deduction = self.search([('id','!=',rec.id),('deduction_type_id','=',rec.deduction_type_id.id),('employee_id','=',rec.employee_id.id),('deduction_month','=',rec.deduction_month),('deduction_year','=',rec.deduction_year)])
            if check_deduction:
                raise ValidationError('Deduction of %s in %s is already exist.' %(MONTHS[rec.deduction_month], rec.deduction_year))
    
    @api.constrains('deduction_amt')
    def _check_deduction_amt(self):
        for rec in self:
            if rec.deduction_amt <= 0:
                raise ValidationError('Deduction amount must be greater then zero.')

            if rec.deduction_type_name == 'Accident' or rec.deduction_type_name == 'Warning':
                if (rec.deduction_id.total_deduction_amt - sum(rec.deduction_id.deduction_lines.mapped('deduction_amt'))) < 0:
                    raise ValidationError('Deduction Lines can not be greater then total deduction amount')
            
    def action_approve(self):
        for rec in self:
            if rec.deduction_type_name == 'Accident' or rec.deduction_type_name == 'Warning':
                if (rec.deduction_id.total_deduction_amt - sum(rec.deduction_id.deduction_lines.mapped('deduction_amt'))) < 0:
                    raise ValidationError('Deduction Lines can not be greater then total deduction amount')

            rec.state = 'approve'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You cannot delete a deduction which is in the %s state',self.state))
        return super().unlink()
    department_id = fields.Many2one('hr.department')


class DeductionType(models.Model):
    _name = "deduction.type"

    name = fields.Char('Name',required=True)
    code = fields.Char('Code',required=True)
    
    @api.constrains('name','code')
    def check_constraint_ded(self):
        deductions = self.search([])
        if len(deductions.search([('name','=',self.name)]))>1 or len(deductions.search([('code','=',self.code)]))>1:
            raise ValidationError(_("Code and Name must be unique"))