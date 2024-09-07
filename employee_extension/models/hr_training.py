from odoo import api, models, fields
from odoo.exceptions import ValidationError

class hr_training_wizard(models.TransientModel):
    _name = "hr.training.wizard"

    attachment_ids = fields.Many2many('ir.attachment','hr_training_wizard_ir_attachment_rel','training_wizard_id','attachment_id',string='Attachments')

    def get_data(self):
        hl_active_id = self.env.context.get('active_id')
        sql = "insert into hr_training_employee_ir_attachment_rel (training_id,attachment_id) values (%s,%s)"
        self.env.cr.execute(sql,(hl_active_id,self.attachment_ids.id))      

class HrTrainingRecord(models.Model):
    _name = 'hr.training'
    _order = 'date_start desc'
    _description = 'Employee Training'
    _inherit = ['mail.thread']

    name = fields.Char('Description', required = True,tracking=True)
    course = fields.Many2one('hr.training.course','Course', required = True,tracking=True)
    type = fields.Many2one('hr.training.type','Training Type', required = True,tracking=True)
    responsible = fields.Char('Trainer', required = True)
    place = fields.Many2one('hr.training.place', 'Place', required = True,tracking=True)  
    year = fields.Char('Training Year')  
    date_start = fields.Date('Start Date', required = True,tracking=True)
    date_end = fields.Date('End Date', required = True,tracking=True)
    total_time = fields.Integer('Total Training Hours', required = True)
    record_line = fields.One2many('hr.training.line','record_id','Employees', copy = True)    
    employee_ids = fields.Many2many('hr.employee',string='Employees')
    provided_type = fields.Selection([('porvided', 'Provided'), ('non_provided', 'Non Provided')],"Provided/Non Provided",tracking=True)
    amt  = fields.Float(string='Amount')
   
    @api.model
    def create(self,data):       
        record_id = super(HrTrainingRecord, self).create(data)        
        record_line_obj = self.env['hr.training.line']        
        record = self.browse(record_id)      
        record= record.id
        for emp_id in record.employee_ids:           
            record_line_value = {
                                 'record_id': record_id.id,
                                 'employee_id': emp_id.id,                                 
                            }
            record_line_obj.create(record_line_value)
        return record_id

   
    def write(self, vals):
        record_ids = super(HrTrainingRecord, self).write(vals)
        record = self.browse(self.ids)
        record_line_obj = self.env['hr.training.line']
        record_emp_ids = []
        for rec in record.record_line:
            record_emp_ids.append(rec.employee_id)        
        for emp_id in record.employee_ids:
               
            if emp_id not in record_emp_ids:
                record_line_value = {
                                     'record_id':record.id,
                                     'employee_id':emp_id.id,
                                     }
                
                self.env['hr.training.line'].create(record_line_value)
          
        #print record.employee_ids
        for emp_id in record_emp_ids:
            if emp_id not in record.employee_ids:
                rec_ids = record_line_obj.search([('record_id', '=', record.id),
                                                    ('employee_id', '=', emp_id.id)])
                for rec in rec_ids:
                    rec.unlink()                
              
        return record_ids
          
    
    @api.constrains('date_start','date_end')
    def _check_dates(self):
        if self.date_end < self.date_start:
            raise ValidationError('End date must be greater than Start date!')

class HrTrainingRecordLine(models.Model):
    _name = 'hr.training.line'
    _order = 'date_start desc'
    _description = 'Employee Training Records'

    record_id = fields.Many2one('hr.training','Description')
    course = fields.Many2one('hr.training.course',related = 'record_id.course', store = True)
    type = fields.Many2one('hr.training.type',related = 'record_id.type', store = True)
    responsible = fields.Char('hr.employee',related = 'record_id.responsible', store = True)
    place = fields.Many2one('hr.training.place',related = 'record_id.place', store = True)
    provided_type=fields.Selection([('porvided', 'Provided'), ('non_provided', 'Non Provided')],"Provided/Non Provided",related="record_id.provided_type",store=True)
    year = fields.Char('Training Year', related='record_id.year', store='True')
    date_start = fields.Date(related = 'record_id.date_start', store = True)
    date_end = fields.Date(related = 'record_id.date_end', store = True)
    total_time = fields.Integer(related = 'record_id.total_time', store = True)
    employee_id = fields.Many2one('hr.employee','Employee', required = True)
    result = fields.Many2one('hr.training.result', 'Result')
    remark = fields.Text('Remark')
    amt  = fields.Float(related = 'record_id.amt', store = True)
    attachment_ids = fields.Many2many('ir.attachment','hr_training_employee_ir_attachment_rel','training_id','attachment_id',string='Attachments')
    adminCheck= fields.Boolean(compute='_adminCheck')
    
    def _adminCheck(self):        
        result = False
        group_admin = self.env['res.users'].has_group('base.group_system')
        if group_admin:
            result = True
        self.adminCheck = result

    @api.constrains('record_id','employee_id')
    def _check_record_employee(self):
        records = self.env['hr.training.line'].search([('record_id','=',self.record_id.id),('employee_id', '=' , self.employee_id.id)])
        if len(records) >= 2:
            raise ValidationError('%s' % self.employee_id.name + ' is already in %s' % self.record_id.name)

class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = 'hr.employee'

    record_line = fields.One2many('hr.training.line','employee_id','Training Records', copy = True)
    
class HrTrainingCourse(models.Model):
    _name = 'hr.training.course'
    _description = 'Training Course'

    name = fields.Char('Course Name', required = True)
    
class HrTrainingType(models.Model):
    _name = 'hr.training.type'
    _description = 'Training Type'

    name = fields.Char('Type', required = True)    
    
class HrTrainingPlace(models.Model):
    _name = 'hr.training.place'
    _description = 'Training Place'

    name = fields.Char('Place', required = True)
    place = fields.Text('Description')
    
class HrTrainingResult(models.Model):
    _name = 'hr.training.result'
    _description = 'Training Result'
    
    name = fields.Char('Code', required = True)
    result = fields.Char('Result', required = True)