from odoo import models,fields,api,_
from odoo.exceptions import ValidationError, UserError

AMOUNT_TYPE = [('percentage','Ratio'),('cash','Cash')]
class EmployeeAccident(models.Model):
    _name = "employee.accident"

    name = fields.Char(default=lambda self: _('New'))
    reference = fields.Char(string="Reference")

    employee_id = fields.Many2one('hr.employee')
    employee_phone = fields.Char()
    company_id = fields.Many2one(related='employee_id.company_id', readonly=True, store=True)
    employee_nrc = fields.Char(related="employee_id.nrc_full")
    employee_job_position = fields.Many2one('hr.job')
    department_id = fields.Many2one('hr.department')
    accident_date = fields.Date()
    location = fields.Char()
    reason = fields.Text()
    summary_of_site_manager = fields.Text()
    damages = fields.Char()
    # witness_ids = fields.Many2many('hr.employee','employee_accident_witness_rel','witness_ids')
    witness_person = fields.Char()
    accident_fleet_ids = fields.Many2many('fleet.vehicle','accident_fleet_vehicle_rel','accident_fleet_ids')
    cost_and_compensation_responsible_ids = fields.Many2many('hr.employee','employee_accident_cost_and_com_rel','cost_and_compensation_responsible_ids')

    documentor_id = fields.Many2one('hr.employee')
    head_of_department_id = fields.Many2one('hr.employee')
    site_manager_id = fields.Many2one('hr.employee')
    attachment_ids = fields.One2many('ir.attachment', 'res_id', string="Attachments")
    supported_attachment_ids = fields.Many2many(
        'ir.attachment', string="Attach File", compute='_compute_supported_attachment_ids',
        )
    state = fields.Selection([
        ('draft','Draft'),
        ('report','Report'),
        ('inquiry','Inquiry'),
        ('meeting','Meeting'),
        ('processing','Processing'),
        ('complete','Complete')
    ],default="draft")
    # # Inquiry State
    inquiry_summary = fields.Text('Inquiry Summary')
    insurance_status = fields.Boolean('Insurance Status')
    insurance_remark = fields.Text('Remark')
    inquiry_attachments = fields.Many2many('ir.attachment',)
    insurance_claim_status = fields.Boolean('Is insurance claim?')
    accident_type_id = fields.Many2one('hr.employee.accident.type',string="Accident Type")
    # # Meeting State
    meeting_of_minutes = fields.Text()
    estimate_amt = fields.Float()
    actual_amt = fields.Float()
    accident_amt_type = fields.Selection(AMOUNT_TYPE,default="cash")

    insurement_amt = fields.Float()
    insurement_amt_ratio = fields.Float()
    employee_amt = fields.Float()
    employee_amt_ratio = fields.Float()
    company_amt = fields.Float()
    company_amt_ratio = fields.Float()
    other_department_amt = fields.Float()
    other_department_amt_ratio = fields.Float()

    meeting_decision_date = fields.Date(default=fields.Date().today())

    deduction_ids = fields.One2many('hr.salary.deduction','accident_id')
    accident_emp_ids = fields.Many2many('hr.employee','accident_employee_ids_rel','accident_emp_ids')
    # accident_department_ids = fields.Many2many('hr.department','accident_department_ids_rel','accident_department_ids')


    @api.onchange('employee_id','cost_and_compensation_responsible_ids')
    def _onchange_select_emps(self):
        for rec in self:
            employee_ids = []
            department_ids = []
            employee_ids.append(rec.employee_id.id)
            employee_ids.extend(rec.cost_and_compensation_responsible_ids.ids)
            rec.accident_emp_ids = [[6,0,employee_ids]]

    def _get_employee_domain(self):
        
        return ['|',('user_id','=',self.env.user.id),('department_id', 'in', self.env.user.hr_department_ids.ids)]


    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=0, orderby=False, lazy=True):
        all_states = dict(self.fields_get(allfields=['state'])['state']['selection'])
        
        result = super(EmployeeAccident, self).read_group(domain, fields, groupby, offset, limit, orderby, lazy)
        
        existing_states = [res['state'] for res in result if 'state' in res]
        
        for state in all_states:
            if state not in existing_states:
                result.append({
                    'state': state,
                    '__count': 0,
                })
        sorted_result = sorted(result, key=lambda x: list(all_states.keys()).index(x['state']))
        
        return sorted_result

    @api.onchange('accident_amt_type')
    def _onchange_accident_amt_type(self):
        for rec in self:
            if rec.accident_amt_type == 'cash':
                rec.insurement_amt_ratio = 0
                rec.employee_amt_ratio = 0
                rec.company_amt_ratio = 0
                rec.other_department_amt_ratio = 0
            else:
                rec.insurement_amt = 0
                rec.employee_amt = 0
                rec.company_amt = 0
                rec.other_department_amt = 0

    # @api.constrains('accident_amt_type')
    # def _check_total_amt(self):
    #     for rec in self:
            
    @api.onchange('insurance_status')
    def _onchange_insurance_status(self):
        for rec in self:
            if not rec.insurance_status:
                rec.insurance_claim_status = False
                
    def action_done(self):
        self.ensure_one()
        self.state = 'done'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You cannot delete a resign request which is in the %s state',self.state))
        return super().unlink()

    

    @api.model
    def create(self, vals):
        # assigning the sequence for the record
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.accident') or _('New')
        res = super(EmployeeAccident, self).create(vals)
        return res

    @api.depends('attachment_ids')
    def _compute_supported_attachment_ids(self):
        for rec in self:
            rec.supported_attachment_ids = rec.attachment_ids

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for rec in self:
            rec.employee_phone = rec.employee_id.mobile_phone
            rec.department_id = rec.employee_id.department_id
            rec.employee_job_position = rec.employee_id.job_id
            # rec.employee_nrc = rec.employee_id.nrc_full

    @api.onchange('insurement_amt_ratio','employee_amt_ratio','company_amt_ratio','other_department_amt_ratio')
    def _check_percentage(self):
        for rec in self:
            if rec.accident_amt_type == 'percentage' and (rec.insurement_amt_ratio + rec.employee_amt_ratio + rec.company_amt_ratio + rec.other_department_amt_ratio) > 100:
                raise ValidationError('Invalid Percentage')
            
    @api.constrains('insurement_amt_ratio','employee_amt_ratio','company_amt_ratio','other_department_amt_ratio')
    def _check_percentage_ratio(self):
        for rec in self:
            if rec.accident_amt_type == 'percentage' and (rec.insurement_amt_ratio + rec.employee_amt_ratio + rec.company_amt_ratio + rec.other_department_amt_ratio) != 100:
                raise ValidationError('Invalid Percentage')

    def action_open_deduction_form(self):
        
        return {
            'name': _('Salary Deduction'),
            'res_model': 'hr.salary.deduction',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'view_mode': 'tree,form',
            'domain': [('accident_id', '=',self.id)],              

        }
    def action_report(self):
        self.ensure_one()
        self.state = 'report'

    def action_inquiry(self):
        self.ensure_one()
        self.state = 'inquiry'

    def action_meeting(self):
        self.ensure_one()
        self.state = 'meeting'

    def action_processing(self):
        self.ensure_one()
        self.state = 'processing'

    def action_complete(self):
        self.ensure_one()
        self.state = 'complete'
    




class AccidentType(models.Model):
    _name = 'hr.employee.accident.type'

    name = fields.Char('Name')