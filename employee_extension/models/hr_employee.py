from odoo import models, fields, api,_
from odoo.exceptions import AccessError
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
import calendar
import base64
from dateutil.relativedelta import relativedelta

class Employees(models.Model):
    _inherit = 'hr.employee'
    _order = "sequence desc"
    #_order = "employee_id"

    def print_btn(self):      
        # emp=self.ids        
        # if emp:
        #     url = 'http://ec2-13-213-221-73.ap-southeast-1.compute.amazonaws.com:8080/birt/frameset?__report=mmm_inter_cv_report.rptdesign&employee_id=' + str(self.ids[0])
        # if url :
        #     return {
        #     'type' : 'ir.actions.act_url',
        #     'url' : url,
        #     'target': 'new',
        #     }
        # else:
        #     raise ValidationError('Not Found')
        ir_actions_report_sudo = self.env['ir.actions.report'].sudo()
        employee_report_action = self.env.ref('employee_extension.action_report_employee_cv')
       
        return employee_report_action.report_action(docids=self)

    @api.constrains('nrc_no','nrc_desc','nrc_code','nrc_number','passport')
    def _check_update_nrc(self):
        for recs in self:
            nrc_full = None
            if recs.nrc_no and recs.nrc_code and recs.nrc_number and recs.nrc_desc:
                nrc_full = recs.nrc_number.name +'/'+ recs.nrc_code.name + recs.nrc_desc.name + recs.nrc_no
                rec = recs.search([('nrc_full','=',nrc_full),('id','!=',recs.id)])
                if len(rec) > 0:
                   
                    print ("NRC Duplicated")
                recs.nrc_full = nrc_full

    # employee_id = fields.Char(string='Staff ID No',compute='generate_staff_no',store=True)
    employee_id = fields.Char(string='Staff ID No',required=True)
    burmese_name = fields.Char(string='Employee Name(Myanmar)',required=True)
    fingerprint_id = fields.Char(string='Fingerprint ID',tracking=True)
    father_name = fields.Char(string="Father Name",required=False)
    father_dop = fields.Date(string="Father's Date Of Passing")
    mother_name = fields.Char(string="Mother Name",required=False)
    mother_dop = fields.Date(string="Mother's Date Of Passing")
    spouse_occupaction = fields.Char(string="Spouse Occupaction")
    relation_in = fields.Char(string="Relation-In")
    phone_no = fields.Char(string="Phone Number",tracking=True)
    viber_no = fields.Char(string="Viber Number",tracking=True)
    age = fields.Integer('Age',compute="calculate_age")
    religion = fields.Many2one('hr.employee.religion', 'Religion')
    race = fields.Many2one('hr.race', string='Race/Ethnic')
    bank_account_id = fields.Many2one(
        'res.partner.bank', 'Bank Account Number',
        groups="hr.group_hr_user",
        tracking=True,
        help='Employee bank salary account')
    bank_name = fields.Char(related="bank_account_id.bank_id.name", string='Bank Name', readonly=False,tracking=True)
    mail_of_office365 = fields.Char(string='Office365 mail',tracking=True)
    driving_license_no = fields.Char(string='Driving License No.',tracking=True)
    driving_license_type = fields.Char(string="Driving License Type",tracking=True)
    driving_license_expired_date = fields.Date(string="Driving License Expired Date",tracking=True)
    car_machine_name = fields.Char(string="Car Machine Name",tracking=True)
    machine_model = fields.Char(string="Machine Model",tracking=True)
    grading = fields.Char(string="Grading",tracking=True)
    grade_id = fields.Many2one('hr.employee.grading', string='Grading',tracking=True)
    grading2 = fields.Char(string="Grading2",tracking=True)
    hostel_id = fields.Many2one('hr.employee.hostel',string='Hostel',tracking=True)
    ssb_id = fields.Char(string="SSB No",tracking=True)

    brother_ids = fields.One2many('hr.employee.brosis','employee_id',string="Name of Brother and Sister")
    child_id = fields.One2many('hr.employee.child','employee_id',string="Name of Children")

    relationship = fields.Char(string="Relationship")  

    city_id = fields.Many2one('res.country.state','City',groups = "hr.group_hr_user",tracking=True)
    
    nrc_no = fields.Char(string='NRC', required=False)
    nrc_number = fields.Many2one('nrc.no', string='')
    nrc_code = fields.Many2one('nrc.code', string='', domain="[('no_id','=',nrc_number)]")
    nrc_desc = fields.Many2one('nrc.type', string='')
    nrc_full = fields.Char('NRC')

    
    grade_id = fields.Many2one('hr.employee.grade','Grading',tracking=True)

    designation = fields.Char(string="Designation",tracking=True)
    designation_type = fields.Many2one('hr.designation.type','Job Type',tracking=True)

    total_child = fields.Integer(string="Number of Children", store=True, readonly=False)

    rank = fields.Many2one('hr.employee.rank', string="Rank",tracking=True)
    job_location = fields.Many2one('hr.job.location', string="Job Location",tracking=True)

    trial_date_start = fields.Date(string='Joining Date', required=True,tracking=True)
    service_year = fields.Integer('Service', compute="calculate_service",size=5, store=True)
    service_month = fields.Integer('Month', compute="calculate_service",size=20)
    service_day = fields.Integer('Day', compute="calculate_service",size=20)
    service_year_2 = fields.Integer('Service Year')
    unit_id = fields.Many2one('hr.department',string='Business Unit',domain="[('department_type','=','business')]",tracking=True)
    division_id = fields.Many2one('hr.department', string='Division', index=True,tracking=True,domain="[('department_type','=','division')]")
    department_id = fields.Many2one('hr.department', string='Department',tracking=True,domain="[('department_type','=','department')]")
    job_id = fields.Many2one('hr.job', string='Position', domain="[('department_id','=',department_id)]",required=True,tracking=True)
    branch_id = fields.Many2one('hr.branch', string='Branch',tracking=True)
    home_address = fields.Text('Address',tracking=True)
    current_address = fields.Text('Current Address',tracking=True)
    marital = fields.Selection(selection_add=[('diposed', 'Diposed'),], string='Marital Status', groups="hr.group_hr_user", default='single', tracking=True)
    blood_group = fields.Many2one('hr.blood', string="Blood Type")
    user_check_tick = fields.Boolean(default=False)
    #by yma
    leader_id = fields.Many2one('hr.employee', string='Leader',tracking=True)
    remark = fields.Text('Remark')
    sequence_copy = fields.Integer(string="Sequence",compute="compute_rank_sequence")
    sequence = fields.Integer(string="Sequence",tracking=True)
    payroll_calculator_id = fields.Many2one('hr.employee',string='Payroll Calculator',tracking=True)
    # company = fields.Many2one('analytic.company',tracking=True)
    father_name_myanmar = fields.Char(string='')
    mother_name_myanmar = fields.Char(string='')
    live_with_father = fields.Selection([('yes',"Yes"),('no',"No")],string="",default='no')
    live_with_mother = fields.Selection([('yes',"Yes"),('no',"No")],string="",default='no')
    # 17-06-2022
    bank_id = fields.One2many('employee.bank','employee_id',string="Bank")
    image_binary = fields.Text('Sign Binary',store=True,copy=False)
    #by yma
    has_attendance = fields.Boolean('No Attendance')
    has_ot = fields.Boolean('No OT')
    semi_active = fields.Boolean('Semi InActive')
    no_attendance = fields.Boolean('No Attendance ?')
    no_ot = fields.Boolean('No OT ?')
    company_id = fields.Many2one('res.company', required=False)
    is_hr_manager = fields.Boolean(compute="_is_hr_manager")
    
    def _is_hr_manager(self):
      users = self.env['res.users']
      
      self.is_hr_manager = True
      if users.search([('id', '=', self.env.uid)]).is_hr_manager:
        self.is_hr_manager = False
    
    # @api.depends('name')
    # def generate_staff_no(self):
    #     sql = '''select max(SPLIT_PART(employee_id,'-',2)),max(fingerprint_id::int) from hr_employee'''
    #     self._cr.execute(sql,)
    #     max_employee_no = self._cr.fetchone()
    #     if max_employee_no != (None,None):
    #         if not all(str(data).isnumeric() for data in max_employee_no):
    #             raise ValidationError(('Error : Latest MD Code or Fingerprint ID is invalid...'))
    #         if not self.employee_id or ( int(self.employee_id.split("-")[1]) == int(max_employee_no[0])+1):
    #             self.write({
    #                 'employee_id':'MD-'+str(int(max_employee_no[0])+1).zfill(5),
    #                 'fingerprint_id':str(int(max_employee_no[1])+1).zfill(5)
    #             })
    #     else:
    #         self.write({
    #                 'employee_id':'MD-'+str(int(0)+1).zfill(5),
    #                 'fingerprint_id':str(int(0)+1).zfill(5)
    #             })

    _sql_constraints = [
        ('unique_constraint_employee_name','unique(name)', 'Employee name must be unique'),
        ('unique_constraint_employee_code','unique(employee_id)', 'Employee code must be unique'),
    ]

    @api.onchange('unit_id')
    def onchange_business_unit(self):
        for res in self:
            if res.unit_id:
                return {'domain': {'division_id': [('department_type', '=', 'division'),('parent_id','=',res.unit_id.id)]}}

    @api.onchange('division_id')
    def onchange_division(self):
        for res in self:
            if res.division_id:
                return {'domain': {'department_id': [('department_type','=','department'),('parent_id','=',res.division_id.id)]}}
            
    @api.onchange('department_id')
    def onchange_department(self):
        for res in self:
            if res.department_id:
                res.division_id = res.department_id.parent_id
                res.unit_id = res.department_id.parent_id.parent_id
            else:
                res.division_id = None
                res.unit_id = None

    def update_image_binary(self):
        emp_ids = self.env['hr.employee'].search([])
        for rec in emp_ids:
            if self.image_1920:
                image_binary = base64.b64encode(rec.image_1920)
                rec.write({'image_binary': image_binary})

    @api.constrains('image_1920')
    def pass_image(self):
        for rec in self:
            if self.image_1920:
                image_binary = base64.b64encode(self.image_1920)
                rec.write({'image_binary': image_binary})


    def temp_action_t(self):
        for rec in self:
            emp_ids = self.env['hr.employee'].search([('id','!=',None),('rank','!=',None)])
            for l in emp_ids:
                l.compute_rank_sequence()

    @api.depends('rank')
    def compute_rank_sequence(self):
        for rec in self:
            val = 0
            if rec.rank:
                val = int(rec.rank.name)
            rec.sequence_copy = val
            rec.sequence = val    
    # def name_get(self):
       
    #     res = []
    #     for rec in self:
    #         name = rec.employee_id
    #         res.append((rec.id, name))
    #     return res    
        

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|',('name',operator,name),('employee_id',operator,name)]
        search_ids = self._search(domain + args,limit=limit,access_rights_uid=name_get_uid)
        return search_ids    

    def multi_create_user(self):
        for emp in self:
            if emp.user_check_tick == False:
                emp.create_user()

    # error on creating two user 
    def create_user(self):
        if self.env.user.has_group('hr.group_hr_manager'):    
            for record in self:
                if record.user_id:
                    raise ValidationError("User Account is already created!")            
                user_id = self.env['res.users'].sudo().create({'name': record.name,'login': record.employee_id})
                record.user_id = user_id
                record.user_check_tick = True  
                group_employee = self.env.ref('base.group_user')
                attendance_group = self.env.ref('hr_attendance.group_hr_attendance')
                user_id.sudo().write({'password':self.employee_id,'groups_id': [(6, 0, [group_employee.id,attendance_group.id])]})     
            if not self.work_email:
                email = 'example@abc.com'
            else:
                email = self.work_email
            user_id.partner_id.partner_code = user_id.partner_id.partner_code_defined = self.employee_id
            user_id.partner_type = 'employee'
            user_id.partner_id.email = email
            deleted_user = self.env['res.partner'].sudo().search([('name','=',record.name),('id','!=',user_id.partner_id.id)])
            if deleted_user:
                deleted_user.sudo().unlink()

    def _auto_create_user(self,limit_amount):  
        no_user_account_employees = self.env['hr.employee'].search([('user_id','=',False),('employee_id','!=',False)],limit=int(limit_amount)) 
        for no_user_account_employee in no_user_account_employees:
            no_user_account_employee.create_user()          

    def change_md_code_password(self):
        if self.env.user.has_group('hr.group_hr_manager'): 
            for res in self:
                if res.user_id:
                    res.user_id.sudo()._change_password(res.employee_id)
                    res.message_post(body=f"User {self.env.user.name} changed the password of {res.user_id.name} to default password") 
        else:
            raise ValidationError("You don't have that access to change password..")                 


    @api.onchange('user_id')
    def user_checking(self):
        if self.user_id:
            self.user_check_tick = True
        else:
            self.user_check_tick = False


    @api.constrains('job_id','department_id')
    def update_contract(self):
        for rec in self:
            contract_obj = self.env['hr.contract'].search([('employee_id','=',rec.id)])       
            for cont in contract_obj:
                cont.job_id = cont.employee_id.job_id
                cont.department_id = cont.employee_id.department_id

    @api.onchange('marital')
    def do_count_child(self):
        if self.marital == 'single':
            self.total_child = 0
        else:
            self.total_child = len(self.child_id)
            print (len(self.child_id))
    
    @api.onchange('birthday')
    def calculate_age(self):
        for emp in self:
            birth = None
            if emp.birthday:
                birth = emp.birthday
            if birth:
                birth = datetime.strptime(str(birth),"%Y-%M-%d")
                today = datetime.strptime(str(fields.Date.today()),"%Y-%m-%d")
                age = abs((today - birth).days)
                year = round(float(age/365.00),2)
                emp.age = int(year)
            else:
                emp.age=None

    @api.depends('trial_date_start')
    def calculate_service(self):
        for emp in self:
            service_day = service_month = service_year = years = 0
            if emp.trial_date_start:
                print("service_month>>",emp.trial_date_start)
                month = 0
                years = 0
                day = 0
                join_date = emp.trial_date_start
                p_year = datetime.strptime(str(join_date), '%Y-%m-%d').strftime('%Y')
                p_month = datetime.strptime(str(join_date), '%Y-%m-%d').strftime('%m')
                p_day = datetime.strptime(str(join_date), '%Y-%m-%d').strftime('%d')
                today_year = datetime.today().strftime("%Y")
                today_month = datetime.today().strftime("%m")
                today_day = datetime.today().strftime("%d")
                years = int(today_year) -  int(p_year)
                r = calendar.monthrange(int(today_year),int(today_month))[1]
                if today_month < p_month:
                    years-=1
                    month = (int(today_month)+12)-int(p_month)
                else:
                    if today_month == p_month and today_day < p_day:
                        years-=1
                    month = int(today_month)-int(p_month)
                if today_day < p_day:
                    if int(month)>0:
                        month -=1
                    else:
                        month = 11
                    day = (int(today_day)+r)-int(p_day)
                else:
                    day = int(today_day)-int(p_day)
                service_day = day
                service_month = month
                service_year = years
            emp.service_year = int(service_year)
            emp.service_month = int(service_month)
            emp.service_day = int(service_day)
            emp.service_year_2 = years
            
    def create(self,vals):
        if not self.env.user.has_group('hr.group_hr_user'):
            raise ValidationError("You don't have enough access to create employeess!!!")
        if type(vals) == type({}):
            if not vals.get("employee_id",False):
                raise ValidationError("Employee ID is required!!!")
        else:
            for dct in vals:
                if not dct.get("employee_id",False):
                    raise ValidationError("Employee ID is required!!!")
        return super().create(vals)             

class HrReligion(models.Model):
    _name = 'hr.employee.religion'
    _description = 'Religion'

    name = fields.Char('Religion', required=True)

class HrRace(models.Model):
    _name = 'hr.race'
    _description = 'Race'

    name = fields.Char('Name', required=True)

class employee_grade(models.Model):
    _name = 'hr.employee.grade'
    _description = 'Grade'

    name = fields.Char(string="Grading")

class employee_designation_type(models.Model):
    _name = 'hr.designation.type'
    _description = 'Designation Type'

    name = fields.Char(string="Designation Type")

class EmployeeGrading(models.Model):
    _name = 'hr.employee.grading'
    _description = 'Employee Grading'

    name = fields.Char(string="Name", required=True)

class EmployeeHostel(models.Model):
    _name = 'hr.employee.hostel'
    _description = 'Employee Hostel'

    name = fields.Char(string="Name", required=True)

class brohter_sister(models.Model):
    _name = 'hr.employee.brosis'
    _description = 'Brother and Sister'

    name = fields.Char(string="Name",required=True)
    bother_age = fields.Integer(string="Age")
    relation = fields.Char(string="Relationship")

    employee_id = fields.Many2one('hr.employee',string="Employee Name")

class child(models.Model):
    _name = 'hr.employee.child'
    _description = 'Children'

    name = fields.Char(string="Name",required=True)
    child_age = fields.Integer(string="Age")
    education = fields.Char(string="Education")

    employee_id = fields.Many2one('hr.employee',string="Employee Name")

class NRCDescription(models.Model):
    _name = "nrc.code"
    _order = "name asc"
    _description = 'NRC Code'

    name = fields.Char('Name', required=True)
    no_id = fields.Many2one('nrc.no', string='NRC Code', required=True)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        split_name = name.split('/')
        if len(split_name) == 2:
            code = split_name[0].strip()
            nrc_name = split_name[1].strip()
            nrc_no = self.env['nrc.no'].search([('name','=',code)],limit=1)
            if nrc_no:
                domain = [('name',operator,nrc_name),('no_id','=',nrc_no.id)]
        else:
            domain = [('name',operator,name)]
        search_ids = self._search(domain + args,limit=limit,access_rights_uid=name_get_uid)
        return search_ids    

class NRCNUmber(models.Model):
    _name = "nrc.no"
    _order = "name asc"
    _description = "NRC Number"

    name = fields.Char('Number', required=True)

class NRCType(models.Model):
    _name = "nrc.type"
    _order = "name asc"
    _description = "NRC Type"

    name = fields.Char('Type', required=True)


class JobLocation(models.Model):
    _name = "hr.job.location"
    _description = "Job Location"

    name = fields.Char('Name', required=True)
    latti = fields.Char(string='Latitude')
    longi = fields.Char(string='Longitube')


class Rank(models.Model):
    _name = "hr.employee.rank"
    _description = "Rank"

    name = fields.Char('Name', required=True)

class Branch(models.Model):
    _name = "hr.branch"
    _description = "Branch"

    name = fields.Char('Name', required=True)

class Department(models.Model):
    _inherit = 'hr.department'

    name = fields.Char('Name', required=True)
    department_type = fields.Selection([
        ('business','Business Unit'),
        ('division','Division'),
        ('department','Department')
    ],'Department Type',store=True)
    department_approve_user_id = fields.Many2many("res.users","hr_departments_res_approve_users_rel","hr_department_ids","department_approve_user_id",string="Deparment Approval User")

    @api.onchange('department_type')
    def onchange_department(self):
        for res in self:
            department_type = self.env.context.get('dep_type','department')
            res.department_type = department_type
            domain_dct = {'division':'business', 'department':'division', 'business': 'business'}
            return {"domain": {"parent_id":[('department_type','=',domain_dct[department_type])]}}

    @api.constrains('name')
    def check_unique_department_name(self):
        parent_id = self.parent_id.id if self.parent_id else False
        same_names = self.env['hr.department'].search([('name','ilike',self.name),('parent_id', '=', parent_id),('id','!=',self.id)])
        if same_names:
            already_name = same_names[0].name
            if same_names[0].parent_id:
                already_name = same_names[0].parent_id.name + ' / ' + already_name
                if same_names[0].parent_id.parent_id:
                    already_name = same_names[0].parent_id.parent_id.name + ' / ' + already_name
            raise ValidationError(f"{self.department_type.capitalize()} - {already_name} is existed!!!!!")
        
    def unlink(self):
        for res in self:
            linked_obj =  self.env['hr.department'].search([('parent_id','=',res.id)],limit=1)
            if linked_obj:
                raise ValidationError(f"{res.department_type.capitalize()} - {res.name} is alredy linked with {linked_obj.department_type.capitalize()} - {linked_obj.name} !!!!!!")
            return super().unlink()
            
                


class HrBloodType(models.Model):
    _name = 'hr.blood'
    _description = 'Blood Type'

    name = fields.Char('Name', required=True)


class AnalyticCompany(models.Model):
    _name = 'analytic.company'
    _description = 'Analytic Company'

    name = fields.Char('Name', required=True)

# 17-06-2022
class BankName(models.Model):
    _name = "bank.name"
    _description ='Bank Name'

    name = fields.Char('Type', required=True)
    code = fields.Char('Code',required=True)

class Employee_band(models.Model):
    _name = "employee.bank"
    _description = 'Employee Bank'

    bank_name = fields.Many2one('bank.name' , string="Bank Name")
    short_code = fields.Char('Short Code')
    bank_acc_no = fields.Char('Account Number')
    bank_active = fields.Boolean('Active')
    employee_id = fields.Many2one('hr.employee' , string="Employee")
    acc_name = fields.Char('Account Name')
    nrc_no = fields.Char('NRC')
    card_holder_name = fields.Char('Card Holder Name')
    type = fields.Selection([('account','Account'),('password','Password')],'Type')

#start 30-06-2022
class Job_position(models.Model):
    _inherit ="hr.job"
    _description ="Job Position"

    rank_id = fields.Many2one('hr.employee.rank', string="Rank")
    min_amount = fields.Float('Min Amount')
    max_amount = fields.Float('Max Amount')
    is_hr_manager = fields.Boolean(compute="_is_hr_manager")

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        split_name = name.rsplit(' / ', 1)
        if len(split_name) == 2:
            job_name = split_name[1]
            department_id = self.env['hr.department'].search([('complete_name','=',split_name[0])],limit=1)
            if department_id:
                domain = [('department_id','=',department_id.id),('name',operator,job_name)]
        else:
            domain = [('name',operator,name)]
        search_ids = self._search(domain + args,limit=limit,access_rights_uid=name_get_uid)
        return search_ids    
    
    def _is_hr_manager(self):
      users = self.env['res.users']
      
      print ('is_hr_manager ' + str(self.env['res.users'].search([('id', '=', self.env.uid)]).is_hr_manager))
      self.is_hr_manager = True
      if self.env['res.users'].search([('id', '=', self.env.uid)]).is_hr_manager:
        self.is_hr_manager = False
      print (self.is_hr_manager)


class res_user(models.Model):
    _name = 'res.users'
    _inherit = 'res.users'

    is_hr_manager = fields.Boolean('is_hr_manager')

class hr_contract(models.Model):
    _inherit = 'hr.contract'
    _description = 'hr.contract'

    is_hr_manager = fields.Boolean(compute="_is_hr_manager")
    # total_allowance = fields.Monetary('Total Allowance',compute='calculate_other_allowance',store=True,required=True, tracking=True, help="Employee's monthly gross allowance.")
    # total_wage = fields.Monetary('Total Wages',compute='calculate_total_wages',store=True,required=True, tracking=True, help="Employee's monthly gross amount.")
    
    
    # @api.depends("service_year","graduate","nssa" ,"site_living_exp","vehicle_maintain" ,"business_skill" ,"effort" ,"responsible" ,"cooperation" ,"management" ,"ph_bill","att_bonus","exam_result","other_allowance" )
    # def calculate_other_allowance(self):
    #     for res in self:
    #         res.total_allowance = res.service_year+ res.graduate + res.nssa + res.site_living_exp + res.vehicle_maintain + res.business_skill + res.effort + res.responsible + res.cooperation + res.management + res.ph_bill + res.att_bonus + res.exam_result + res.other_allowance 
        
    def _is_hr_manager(self):
      users = self.env['res.users']
      
      print ('is_hr_manager ' + str(self.env['res.users'].search([('id', '=', self.env.uid)]).is_hr_manager))
      self.is_hr_manager = True
      if self.env['res.users'].search([('id', '=', self.env.uid)]).is_hr_manager:
        self.is_hr_manager = False
      print (self.is_hr_manager)
      
    # @api.depends("total_allowance","wage" )
    # def calculate_total_wages(self):
    #     for res in self:
    #         res.total_wage = res.total_allowance + res.wage

