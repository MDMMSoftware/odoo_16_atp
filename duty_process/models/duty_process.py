from odoo import models, fields,Command, api, _
from datetime import datetime, timedelta, date, time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from ...generate_code import generate_code
import math
from odoo.tests import Form

from odoo.exceptions import ValidationError

try:
   from odoo.tools.misc import xlsxwriter
except ImportError:
   import xlsxwriter

import io
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    # TODO saas-17: remove the try/except to directly import from misc
    import xlsxwriter
import logging
import os
import tempfile

class DutyProcess(models.Model):
    _name = "duty.process"
    _description = 'Duty Process'
    _inherit = ['mail.thread']

    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]    


    name = fields.Char('Reference No',required=True,tracking = True,default=lambda self: _("New") ,readonly=True,copy=False)
    machine_id = fields.Many2one('fleet.vehicle',string="Machine Name",required=True)
    machine_owner_id = fields.Many2one('fleet.owner',string="Owner",related="machine_id.owner_id")
    price_type = fields.Selection([('way', 'Way'),('dm', '1 Duty / 1 Month'), ('hd', '1 Hour / 1 Day')], string='Price Type', related="machine_id.price_type")
    fuel_product_id = fields.Many2one('product.product',string="Fuel Product",required=True)
    period_from = fields.Date('From',required=True)
    period_to = fields.Date('To',required=True)
    fuel_journal = fields.Many2one('account.journal',string="Fuel Journal",required=True)
    duty_journal = fields.Many2one('account.journal',string="Duty Journal",required=True)
    machine_rm_qty = fields.Float("Remaining Stock",readonly=True,digits=(16,2))
    machine_onhand_fuel = fields.Float("Remaining Stock",related="machine_id.onhand_fuel",digits=(16,2))
    fuel_uom = fields.Char(string="UOM",related='fuel_product_id.uom_id.name')

    initial_sm = fields.Float("Initial Service Meter")
    initial_fuel_mark = fields.Float("Initial Fuel Mark")
    initial_rate_per_duty = fields.Float("Initial Rate Per Duty")
    fuel_price = fields.Float("Fuel Price")
    initial_mark_per_liter = fields.Float("Initial Mark Per Liter")
    duty_section = fields.Boolean("Duty Section",default=False)
    fuel_section = fields.Boolean("Fuel Section",default=False)
    duty_line = fields.One2many('duty.process.line','duty_id',string="Duty Line")
    duty_import_person = fields.Many2one('hr.employee',string="Duty Import Person")
    site_supervisor = fields.Many2one('hr.employee',string="Site Supervisor")
    owner_id = fields.Many2one('hr.employee',string="Operator Name")
    edit_initial_fuel = fields.Boolean('To Edit Initial Fuel')
    state = fields.Selection([('draft', 'Draft'),('done', 'Open'),('close', 'Closed')], string='Status', default='draft',tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    
    total_use_fuel = fields.Float("Total Use Fuel")
    duty_amt = fields.Float("Duty Amount")
    fuel_amt = fields.Float("Fuel Amount")
    run_hr = fields.Float('Running Hour')
    walk_hr = fields.Float('Walk Hours')
    general_hr = fields.Float('General Hours')
    total_hr = fields.Float('Total Hours')
    total_amt = fields.Float("Total Amount")
    department_id = fields.Many2one('res.department', string='Department',tracking=True, store=True,domain=_get_department_domain,readonly=True)    
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', domain="[('company_id', '=', company_id)]")

    # done_before = fields.Boolean("Opened Status Before",defaut=False)
    
    @api.constrains("duty_line")
    def _sum_all_line_datas_to_form(self):
        run_hr , walk_hr , general_hr , total_hr , total_use_fuel , duty_amt , fuel_amt , total_amt = 0.0 , 0.0 , 0.0 , 0.0 , 0.0 , 0.0 , 0.0 , 0.0
        for line in self.duty_line:
            run_hr += line.run_hr
            walk_hr += line.walk_hr
            general_hr += line.general_hr
            total_hr += line.total_hr
            total_use_fuel += line.total_use_fuel
            duty_amt += line.duty_amt
            fuel_amt += line.fuel_amt
            total_amt += line.total_amt
        self.run_hr = run_hr
        self.walk_hr = walk_hr
        self.general_hr = general_hr
        self.total_hr = total_hr
        self.total_use_fuel = total_use_fuel
        self.duty_amt = duty_amt
        self.fuel_amt = fuel_amt
        self.total_amt = total_amt

    def action_duty_line(self):
        return {
            'name': _('Duty Transaction'),
            'view_mode': 'tree,form',
            'res_model': 'duty.process.line',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.duty_line.ids)],              
        } 
    
    def action_open_pickings(self):
        return {
            'name': _('Transfers'),
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.duty_line.picking_ids.ids)],              
        } 
    
    def action_open_adjustments(self):
        adjust = []
        for res in self.duty_line:
            if res.adjust_id:
                adjust.append(res.adjust_id.id)
            if res.return_adjust_id:
                adjust.append(res.return_adjust_id.id)

        return {
            'name': _('Adjustments'),
            'view_mode': 'tree,form',
            'res_model': 'stock.inventory.adjustment',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',adjust)],              
        } 
    
    def action_open_bills(self):
        moves = []
        for res in self.duty_line:
            if res.move_id:
                moves.append(res.move_id.id)

        return {
            'name': _('Bills'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',moves)],              
        } 
    
    def action_open_internal_bills(self):
        moves = []
        for res in self.duty_line:
            if res.internal_move_id:
                moves.append(res.internal_move_id.id)

        return {
            'name': _('Journal Entries'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',moves)],              
        } 

    @api.onchange('machine_id')
    def _get_machine_rm_qty(self):
        self.machine_rm_qty = self.machine_id.onhand_fuel
        self.initial_fuel_mark = 0
        # self.initial_rate_per_duty = self.machine_id.duty_price
        
    @api.constrains('initial_fuel_mark')
    def _compute_initial_fuel_mark(self):
        
        duty_line = self.duty_line
        for line in duty_line:
            if line.adjust_id:
                raise ValidationError(_("There is Stock Adjustment in Duty."))
        line_array = sorted(list(set(duty_line.mapped('line_no'))))
        first = 1
        for x in line_array:
            for line in duty_line.filtered(lambda d:d.line_no==x):
                if first:
                    line.initial_fuel = line.duty_id.initial_fuel_mark
                    first = 0
                    initial_fuel = line.balance_fuel
                else:
                    line.initial_fuel = initial_fuel
                    initial_fuel = line.balance_fuel
                    
    @api.constrains('initial_mark_per_liter')
    def compute_initial_mark_per_liter(self):
        duty_line = self.duty_line
        for rec in duty_line.sorted(lambda x:x.date):
            if rec.adjust_id:
                raise ValidationError(_("There is Stock Adjustment in Duty."))
            if rec.line_no==1 and (rec.fill_fuel == 0.0 or rec.increase_fuel_mark == 0.0):
                rec.mark_per_liter = rec.duty_id.initial_mark_per_liter
            else:
                if rec.increase_fuel_mark:
                    if rec.fill_fuel:
                        rec.mark_per_liter = rec.fill_fuel/rec.increase_fuel_mark
                    
                elif rec.increase_fuel_mark==0 or rec.fill_fuel<=0:
                    result = duty_line.search([('increase_fuel_mark','!=',0),('line_no','<',rec.line_no),('duty_id','=',rec.duty_id.id)],order ='line_no desc',limit=1)
                    if result:
                        rec.mark_per_liter = round(result.mark_per_liter,2)
                    else:
                        rec.mark_per_liter = rec.duty_id.initial_mark_per_liter

    def action_open(self):
        sequence = self.env['sequence.model']
        name = generate_code.generate_code(sequence,self,None,self.company_id,self.period_from,None,None)
        if not self.name or self.name.strip() == 'New':
            self.name = name
        self.state = 'done'

    def action_close(self):
        self.state = 'close'

    # def action_reset_to_draft(self):
    #     self.state = 'draft'
    #     self.done_before = True

    def unlink(self):
        for rec in self:
            if rec.state != 'draft' or rec.name:
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()


class DutyProcessLine(models.Model):
    _name = 'duty.process.line'

    date = fields.Date(string="Date",required=True)
    line_no = fields.Float("Line No")
    initial_fuel = fields.Float("Initial Fuel")
    fill_fuel = fields.Float("Filling Fuel(L)",copy=False)
    use_fuel = fields.Float("Use Fuel",copy=False)
    fill_fuel_mark = fields.Float("Fill Fuel Mark",copy=False)
    balance_fuel = fields.Float("Balance Fuel",compute="compute_balance_fuel",store=True,copy=False)
    increase_fuel_mark = fields.Float("Increase Fuel Mark",compute="compute_increase_fuel",store=True,copy=False)
    mark_per_liter = fields.Float("Mark Per Liter",compute="compute_mark_per_liter",store=True,copy=False)
    total_use_fuel = fields.Float("Total Use Fuel",compute="compute_total_use_fuel",store=True,copy=False)
    fuel_consumption = fields.Float("1HR Fuel Consumption",compute="compute_fuel_consumption",store=True)
    over_consumption = fields.Boolean("Over Consumption",default=False)
    rate_per_duty = fields.Float("Rate per Duty")
    rate_per_hour = fields.Float("Rate per Hour",compute="compute_rate_per_hour",store=True)
    fuel_price = fields.Float("Fuel Price")
    duty_amt = fields.Float("Duty Amount",compute='compute_duty_amt',store=True)
    fuel_amt = fields.Float("Fuel Amount",compute="compute_fuel_amt",store=True)
    morg_start = fields.Float('Morning Start',default=0.0)
    morg_end = fields.Float('Morning End',default=0.0)
    aftn_start = fields.Float('Afternoon Start',default=0.0)
    aftn_end = fields.Float('Afternoon End',default=0.0)
    evn_start = fields.Float('Evening Start',default=0.0)
    evn_end = fields.Float('Evening End',default=0.0)
    run_hr = fields.Float('Running Hour',compute='compute_running_hr',store=True)
    walk_hr = fields.Float('Walk Hours',default=0.0)
    general_hr = fields.Float('General Hours',default=0.0)
    total_hr = fields.Float('Total Hours',compute='compute_total_hr',store=True)
    service_meter = fields.Float('Service Meter',default=0)
    sm_formula = fields.Float('SM by Formula')
    total_amt = fields.Float("Total Amount",compute="compute_total_amt",store=True)
    ways = fields.Integer("Ways")
    completion_feet = fields.Float("Completion Feet")
    completion_sud = fields.Float("Completion Sud")
    duty_status_id = fields.Many2one('duty.process.line.status',string="Status")
    remark = fields.Char("Remark")
    job_code_id = fields.Many2one(comodel_name='job.code',string="Job Code")
    project_id = fields.Many2one('analytic.project.code',string="Project")
    duty_import_person = fields.Many2one('hr.employee',string="Duty Import Person")
    site_supervisor = fields.Many2one('hr.employee',string="Site Supervisor")
    location_id = fields.Many2one('stock.location',string="Fuel Main Location",domain="[('usage', '=', 'internal')]",required=True)
    onhand_qty = fields.Float("Onhand Quantity",compute="_get_onhand_qty",store=False)    
    owner_id = fields.Many2one('hr.employee',string="Operator Name")
    transport_distance = fields.Many2one('duty.fuel.filling.no',string="Filling No.")
    report_remark_id = fields.Many2one(comodel_name='report.remark',string="Report Remark")
    duty_id = fields.Many2one('duty.process',string="Duty Process")
    picking_ids = fields.Many2many('stock.picking')
    move_ids = fields.Many2many('stock.move')
    exist_picking = fields.Boolean(default=False)
    adjust_id = fields.Many2one('stock.inventory.adjustment')
    return_adjust_id = fields.Many2one('stock.inventory.adjustment')
    move_id = fields.Many2one('account.move')
    internal_move_id = fields.Many2one('account.move')
    attachment_id = fields.Many2one('fleet.attachment',required=True)
    accounting_status = fields.Boolean(string="Accounting Status", compute="_compute_accounting_status")
    posted_status = fields.Selection([
        ('d_fuel','D-Fuel'),
        ('p_fuel','P-Fuel'),
        ('d_duty','D-Duty'),
        ('p_duty','P-Duty'),
        ('d_duty&d_fuel','D-Duty & D-Fuel'),
        ('d_duty&p_fuel','D-Duty & P-Fuel'),
        ('p_duty&d_fuel','P-Duty & D-Fuel'),
        ('p_duty&p_fuel','P-Duty & P-Fuel'),
    ],string="Status")

    machine_id = fields.Many2one('fleet.vehicle',"Machine",related="duty_id.machine_id")
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")
    warehouse_id = fields.Many2one(related="duty_id.warehouse_id",store=True)
    
    
    @api.onchange('line_no')
    def get_locations(self):
        if self.duty_id.warehouse_id:
            domain = [('warehouse_id', '=', self.duty_id.warehouse_id.id)]
        else:
            domain = []
        return {'domain': {'location_id': domain}}
    
    
    
    def action_export_duty_transaction(self):
        output = io.BytesIO()
        file_name = os.path.join(tempfile.gettempdir(), 'Duty Transactions Export.xlsx')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Duty Transactions Export")
        banner_format_small = workbook.add_format({'font_name': 'Arial','bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})
        date_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','num_format': 'dd/mm/yy'})
        time_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','num_format': 'hh:mm'})
       
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 1, 30)
        sheet.set_column(2, 2, 30)
        sheet.set_column(3, 3, 15)
        sheet.set_column(4, 4, 15)
        sheet.set_column(5, 5, 30)
        sheet.set_column(6, 6, 30)
        sheet.set_column(7, 7, 30)
        sheet.set_column(8, 8, 30)
        sheet.set_column(9, 9, 30)
        sheet.set_column(10, 10, 30)
        sheet.set_column(11, 11, 30)
        sheet.set_column(38, 38, 30)
        sheet.set_column(39, 39, 30)
        sheet.set_column(40, 40, 30)
        sheet.set_column(42, 42, 30)
        

        y_offset = 0
        x_offset = 0

        sheet.write(x_offset,0,"Duty Import Person",header_format)
        sheet.write(x_offset,1,"Site Supervisor",header_format)
        sheet.write(x_offset,2,"Project Code",header_format)
        sheet.write(x_offset,3,"Date",header_format)
        sheet.write(x_offset,4,"Month",header_format)
        sheet.write(x_offset,5,"Type",header_format)
        sheet.write(x_offset,6,"Machine Capacity",header_format)
        sheet.write(x_offset,7,"Default Attachment",header_format)
        sheet.write(x_offset,8,"Machine",header_format)
        sheet.write(x_offset,9,"Operator",header_format)
        sheet.write(x_offset,10,"Project Name",header_format)
        sheet.write(x_offset,11,"Owner",header_format)
        sheet.write(x_offset,12,"Morning Start",header_format)
        sheet.write(x_offset,13,"Morning End",header_format)
        sheet.write(x_offset,14,"Afternoon Start",header_format)
        sheet.write(x_offset,15,"Afternoon End",header_format)
        sheet.write(x_offset,16,"Evening Start",header_format)
        sheet.write(x_offset,17,"Evening End",header_format)
        sheet.write(x_offset,18,"Running Hour",header_format)
        sheet.write(x_offset,19,"Walk Hours",header_format)
        sheet.write(x_offset,20,"General Hours",header_format)
        sheet.write(x_offset,21,"Total Hours",header_format)
        sheet.write(x_offset,22,"Service Meter",header_format)
        sheet.write(x_offset,23,"Initial Fuel(Mark)",header_format)
        sheet.write(x_offset,24,"Filling Fuel(Liter)",header_format)
        sheet.write(x_offset,25,"Filling Fuel(Mark)",header_format)							
        sheet.write(x_offset,26,"Use Fuel(Mark)",header_format)
        sheet.write(x_offset,27,"Balance Fuel(Mark)",header_format)
        sheet.write(x_offset,28,"Increase Fuel(Mark)",header_format)
        
        sheet.write(x_offset,29,"Mark Per Liter",header_format)
        sheet.write(x_offset,30,"Total Use Fuel(Liter)",header_format)
        sheet.write(x_offset,31,"1Hr Fuel Consumption",header_format)
        sheet.write(x_offset,32,"Rate Per Duty",header_format)
        sheet.write(x_offset,33,"Rate Per Hours",header_format)
        sheet.write(x_offset,34,"Fuel Price",header_format)
        sheet.write(x_offset,35,"Duty Amount",header_format)
        sheet.write(x_offset,36,"Fuel Amount",header_format)
        sheet.write(x_offset,37,"Total Amount",header_format)
        sheet.write(x_offset,38,"Ways",header_format)
        sheet.write(x_offset,39,"Completion(Sud)",header_format)
        sheet.write(x_offset,40,"Completion(Feets)",header_format)
        sheet.write(x_offset,41,"Report Remark",header_format)
        sheet.write(x_offset,42,"Remark",header_format)
        sheet.write(x_offset,43,"Status",header_format)
        sheet.write(x_offset,44,"No:",header_format)
        sheet.write(x_offset,45,"Job",header_format)
        
        x_offset+=1
        active_ids = self.env.context.get('active_ids')
        for line in self.env['duty.process.line'].browse(active_ids):
            sheet.write(x_offset,0,line.duty_import_person and line.duty_import_person.name or "",text_format)
            sheet.write(x_offset,1,line.site_supervisor and line.site_supervisor.name or "",text_format)
            sheet.write(x_offset,2,line.project_id and line.project_id.code or "",text_format)
            # sheet.write(x_offset,3,line.date and line.date.strftime("%d-%m-%Y") or "",text_format)
            sheet.write(x_offset,3,line.date  or "",date_format)
            sheet.write(x_offset,4,line.date and line.date.strftime("%B") or "",text_format)
            sheet.write(x_offset,5,line.project_id.pj_type_id and line.project_id.pj_type_id.name or "",text_format)
            sheet.write(x_offset,6,line.duty_id.machine_id.machine_capacity and line.duty_id.machine_id.machine_capacity.name or "",text_format)
            sheet.write(x_offset,7,line.attachment_id and line.attachment_id.name or "",text_format)
            sheet.write(x_offset,8,line.duty_id.machine_id and line.duty_id.machine_id.name or "",text_format)
            sheet.write(x_offset,9,line.owner_id and line.owner_id.name or "",text_format)
            sheet.write(x_offset,10,line.project_id and line.project_id.name or "",text_format)
            sheet.write(x_offset,11,line.duty_id.machine_id.owner_id and line.duty_id.machine_id.owner_id.name or "",text_format)
            # sheet.write(x_offset,12,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.morg_start * 60, 60)),time_format)
            sheet.write(x_offset,12,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.morg_start * 60, 60)),time_format)
            sheet.write(x_offset,13,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.morg_end * 60, 60)),time_format)
            sheet.write(x_offset,14,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.aftn_start * 60, 60)),time_format)
            sheet.write(x_offset,15,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.aftn_end * 60, 60)),time_format)
            sheet.write(x_offset,16,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.evn_start * 60, 60)),time_format)
            sheet.write(x_offset,17,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.evn_end * 60, 60)),time_format)
            sheet.write(x_offset,18,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.run_hr * 60, 60)),time_format)
            sheet.write(x_offset,19,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.walk_hr * 60, 60)),time_format)
            sheet.write(x_offset,20,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.general_hr * 60, 60)),time_format)
            sheet.write(x_offset,21,'{0:02.0f}:{1:02.0f}'.format(*divmod(line.total_hr * 60, 60)),time_format)

            # sheet.write(x_offset,21,time(*map(int,divmod(line.total_hr * 60, 60))),time_format)
            sheet.write(x_offset,22,round(line.service_meter,2),text_format)
            sheet.write(x_offset,23,round(line.initial_fuel,2),text_format)
            sheet.write(x_offset,24,round(line.fill_fuel,2),text_format)
            sheet.write(x_offset,25,round(line.fill_fuel_mark,2),text_format)							
            sheet.write(x_offset,26,round(line.use_fuel,2),text_format)
            sheet.write(x_offset,27,round(line.balance_fuel,2),text_format)
            sheet.write(x_offset,28,round(line.increase_fuel_mark,2),text_format)
            
            sheet.write(x_offset,29,round(line.mark_per_liter,2),text_format)
            sheet.write(x_offset,30,round(line.total_use_fuel,2),text_format)
            sheet.write(x_offset,31,round(line.fuel_consumption,2),text_format)
            sheet.write(x_offset,32,round(line.rate_per_duty,2),text_format)
            sheet.write(x_offset,33,round(line.rate_per_hour,2),text_format)
            sheet.write(x_offset,34,round(line.fuel_price,2),text_format)
            sheet.write(x_offset,35,round(line.duty_amt,2),text_format)
            sheet.write(x_offset,36,round(line.fuel_amt,2),text_format)
            sheet.write(x_offset,37,round(line.total_amt,2),text_format)
            sheet.write(x_offset,38,round(line.ways,2),text_format)
            sheet.write(x_offset,39,round(line.completion_sud,2),text_format)
            sheet.write(x_offset,40,round(line.completion_feet,2),text_format)
            sheet.write(x_offset,41,line.report_remark_id and line.report_remark_id.name or "",text_format)
            sheet.write(x_offset,42,line.remark,text_format)
            sheet.write(x_offset,43,line.duty_status_id and line.duty_status_id.name or "",text_format)
            sheet.write(x_offset,44,line.line_no,text_format)
            sheet.write(x_offset,45,line.job_code_id and line.job_code_id.name or "",text_format)
        
            x_offset+=1
            
        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)
        

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/binary/download_document?model=duty.process.line&id=%s&file_name=%s" % (self.id, file_name),
            'close': True,
        }

    def _get_onhand_qty(self):
        for duty_line in self:
            qty = 0
            if duty_line.location_id and duty_line.duty_id.fuel_product_id:
                quant = duty_line.env['stock.quant'].search([('location_id','=',duty_line.location_id.id),('product_id','=',duty_line.duty_id.fuel_product_id.id)])
                if quant:
                    qty += quant.quantity
            duty_line.onhand_qty = qty    

    @api.onchange('attachment_id','duty_id.machine_id')
    def _compute_rate_per_duty(self):
        for res in self:
            if not res.attachment_id:
                res.attachment_id = self.duty_id.machine_id.default_attachment_id.id
            if len(res.duty_id.duty_line) > 1:
                if not res.attachment_id:
                    res.attachment_id = res.duty_id.duty_line[-2].attachment_id
                if not res.location_id:
                    res.location_id = res.duty_id.duty_line[-2].location_id
                if not res.project_id:
                    res.project_id = res.duty_id.duty_line[-2].project_id  
                    res.division_id = res.duty_id.duty_line[-2].division_id
            if res.duty_id.machine_id.duty_price:   
                res.rate_per_duty = res.duty_id.machine_id.duty_price
            else:    
                if res.attachment_id and res.duty_id.machine_id:
                    attachment_line = res.attachment_id.attachment_lines.search([('date_from','<=',res.duty_id.period_from),('date_to','>=',res.duty_id.period_from),('attachment_id','=',res.attachment_id.id)],limit=1)
                    if res.duty_id.machine_id.owner_type == 'family':
                        res.rate_per_duty = attachment_line.family_price
                    elif res.duty_id.machine_id.owner_type == 'internal':
                        res.rate_per_duty = attachment_line.internal_price
                    else:
                        res.rate_per_duty = attachment_line.external_price

    @api.depends('fill_fuel','increase_fuel_mark','duty_id.initial_mark_per_liter')
    def compute_mark_per_liter(self):
        for rec in self.sorted(lambda x:x.date):
            if rec.line_no==1 and (rec.fill_fuel == 0.0 or rec.increase_fuel_mark == 0.0):
                rec.mark_per_liter = rec.duty_id.initial_mark_per_liter
            else:
                if rec.increase_fuel_mark:
                    if rec.fill_fuel:
                        rec.mark_per_liter = rec.fill_fuel/rec.increase_fuel_mark
                    
                elif rec.increase_fuel_mark==0 or rec.fill_fuel<=0:
                    result = self.search([('increase_fuel_mark','!=',0),('line_no','<',rec.line_no),('duty_id','=',rec.duty_id.id)],order ='line_no desc',limit=1)
                    if result:
                        rec.mark_per_liter = round(result.mark_per_liter,2)
                    else:
                        rec.mark_per_liter = rec.duty_id.initial_mark_per_liter

    @api.depends('mark_per_liter','use_fuel')
    def compute_total_use_fuel(self):
        for rec in self:
            rec.total_use_fuel = rec.mark_per_liter * rec.use_fuel  


    @api.depends('fuel_price','total_use_fuel')
    def compute_fuel_amt(self):
        for rec in self:
            rec.fuel_amt = rec.fuel_price * rec.total_use_fuel
            

    @api.depends('fuel_amt','duty_amt')
    def compute_total_amt(self):
        for rec in self:
            rec.total_amt = rec.fuel_amt + rec.duty_amt


    def _compute_accounting_status(self):
        for duty_line in self:
            lst = []
            if duty_line.move_id:
                if duty_line.move_id.state == 'draft':
                    lst.append('d_duty')
                elif duty_line.move_id.state == 'posted':
                    lst.append('p_duty')
            elif duty_line.internal_move_id:
                if duty_line.internal_move_id.state == 'draft':
                    lst.append('d_duty')
                elif duty_line.internal_move_id.state == 'posted':
                    lst.append('p_duty')         
            if duty_line.adjust_id and not duty_line.return_adjust_id:
                lst.append('p_fuel' if duty_line.adjust_id.state == 'done' else 'd_fuel')
            duty_line.posted_status = '&'.join(lst) if lst else None
            duty_line.accounting_status = True
               

    def action_enter_initial_entry(self):
        self.ensure_one()
        view_id = self.env.ref('duty_process.view_initial_fuel_entry_form').id
        for cancel_rec in self:         
            return {
                'name':_("Initial Fuel Entry"),
                'view_mode': 'form',
                'view_id': view_id,
                'view_type': 'form',
                'res_model': 'duty.initial.entry',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': dict(self.env.context, default_duty_line_id=self.id,default_duty_id=self.duty_id.id,group_by=False),
                 
            }
        
    def action_adjust_transfer(self):
        self.ensure_one()
        view_id = self.env.ref('duty_process.view_fuel_adjust_form').id
        for cancel_rec in self:         
            return {
                'name':_("Fuel Adjust Transfer"),
                'view_mode': 'form',
                'view_id': view_id,
                'view_type': 'form',
                'res_model': 'duty.adjust.transfer',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': dict(self.env.context, default_duty_line_id=self.id,default_duty_id=self.duty_id.id,default_picking_ids=self.picking_ids[0].id,group_by=False),
                 
            }
        
    


    @api.depends('morg_end','morg_start','aftn_end','aftn_start','evn_end','evn_start')
    def compute_running_hr(self):
        for rec in self:
            rec.run_hr =  ((rec.morg_end-rec.morg_start) + (rec.aftn_end-rec.aftn_start) + (rec.evn_end-rec.evn_start))

    @api.depends('run_hr','walk_hr','general_hr')
    def compute_total_hr(self):
        for rec in self:
            rec.total_hr = abs(rec.run_hr-rec.walk_hr)-rec.general_hr


    @api.constrains('duty_import_person','site_supervisor','owner_id','fuel_price')
    def set_up_person(self):
        for rec in self:
            if rec.duty_import_person:
                rec.duty_id.duty_import_person = rec.duty_import_person.id
            if rec.site_supervisor:
                rec.duty_id.site_supervisor = rec.site_supervisor.id
            if rec.owner_id:
                rec.duty_id.owner_id = rec.owner_id.id
            if rec.fuel_price:
                rec.duty_id.fuel_price = rec.fuel_price
                
    
    @api.constrains('date')
    def _compute_line_no(self):
        line_no = 0
        first = 1
        duty_line = self.duty_id.duty_line
        date_array = sorted(list(set(duty_line.mapped('date'))))
        for x in date_array:
            line_no += 1
            for line in duty_line.filtered(lambda d:d.date==x):
                if first:
                    line.initial_fuel = line.duty_id.initial_fuel_mark
                    first = 0
                    initial_fuel = line.balance_fuel
                else:
                    line.initial_fuel = initial_fuel
                    initial_fuel = line.balance_fuel
                frac, whole = math.modf(line.line_no)
                if frac==0:
                    line.line_no = line_no
                for picking in line.picking_ids:
                    picking.write({'origin': self.duty_id.name+'-'+str(line_no)})

    @api.constrains('line_no','fill_fuel','fill_fuel_mark','use_fuel','location_id')
    def _compute_balance(self):
        for res in self:
            duty_line = res.duty_id.duty_line
            line_array = sorted(list(set(duty_line.mapped('line_no'))))
            first = 1
            for x in line_array:
                for line in duty_line.filtered(lambda d:d.line_no==x):
                    if first:
                        line.initial_fuel = line.duty_id.initial_fuel_mark
                        first = 0
                        initial_fuel = line.balance_fuel
                    else:
                        line.initial_fuel = initial_fuel
                        initial_fuel = line.balance_fuel


            picking_id = self.env['stock.picking'].sudo().search([('duty_line_id','=',res.id),('state','!=','cancel')])
            if res.fill_fuel and res.fill_fuel>0:
                picking_id = self.env['stock.picking'].sudo().search([('duty_line_id','=',res.id),('state','!=','cancel')])
                if not res.picking_ids and not picking_id:
                    if not res.duty_id.machine_id.location_id:
                        raise ValidationError(_("Please add Machine Location for %s")%self.duty_id.machine_id.name)
                    picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.location_id.warehouse_id.id),('code','=','internal'),('active','=',True)],limit=1)
                    picking = self.env['stock.picking'].create({
                        'scheduled_date':res.date,
                        'location_id':res.location_id.id,
                        'location_dest_id':res.duty_id.machine_id.location_id.id,
                        'picking_type_id':picking_type_id.id,
                        'duty_line_id':res.id,
                        'fleet_id':res.duty_id.machine_id.id or False,
                        'department_id':res.duty_id.department_id.id or False,
                        'move_ids':[(0, 0, {
                                            'product_id': val.duty_id.fuel_product_id.id,
                                            'name':val.duty_id.fuel_product_id.name,
                                            'product_uom_qty': val.fill_fuel,
                                            'location_id':res.location_id.id ,
                                            'location_dest_id':res.duty_id.machine_id.location_id.id,
                                            'division_id': val.division_id.id or False,
                                            'project_id': val.project_id.id or False,
                                            'fleet_location_id':val.duty_id.machine_id.id or False, 
                                            'fleet_id':val.duty_id.machine_id.id or False,
                                            'department_id':res.duty_id.department_id.id or False,
                                            'duty_line_id':val.id,  
                                            'remark':val.remark,       
                                        }) for val in res]
                        })
                    picking.action_confirm()
                    res.write({'picking_ids':[(4,picking.id)]})
                    res.picking_ids.write({'origin': res.duty_id.name+'-'+str(res.line_no),
                                           'location_id':res.location_id.id,
                                           'location_dest_id':res.duty_id.machine_id.location_id.id,})
                    for move in res.picking_ids.move_ids:
                        move.write({
                                           'location_id':res.location_id.id,
                                           'location_dest_id':res.duty_id.machine_id.location_id.id,})
                    for move_line in res.picking_ids.move_line_ids:
                        move_line.write({
                                           'location_id':res.location_id.id,
                                           'location_dest_id':res.duty_id.machine_id.location_id.id,})
                    if res.picking_ids.state not in ('done', 'cancel'):
                        res.picking_ids.write({'scheduled_date':res.date,})
                    
                else:
                    if len(picking_id)==1:
                        picking_id.write({'origin': res.duty_id.name+'-'+str(res.line_no),
                                           'location_id':res.location_id.id,
                                           'location_dest_id':res.duty_id.machine_id.location_id.id,})
                        for move in picking_id.move_ids:
                            move.write({
                                            'location_id':res.location_id.id,
                                            'location_dest_id':res.duty_id.machine_id.location_id.id,})
                        for move_line in picking_id.move_line_ids:
                            move_line.write({
                                            'location_id':res.location_id.id,
                                            'location_dest_id':res.duty_id.machine_id.location_id.id,})
                        if picking_id.state not in ('done', 'cancel'):
                            picking_id.write({'scheduled_date':res.date,})
                        if picking_id.state in ('draft','assigned','waiting','confirmed'):
                            picking_id.move_ids.write({'product_uom_qty': res.fill_fuel})
            
            
            if res.fill_fuel and res.fill_fuel<0:
                picking_id = self.env['stock.picking'].sudo().search([('duty_line_id','=',res.id),('state','!=','cancel')])
                if not res.picking_ids and not picking_id:
                    if not res.duty_id.machine_id.location_id:
                        raise ValidationError(_("Please add Machine Location for %s")%self.duty_id.machine_id.name)
                    picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.location_id.warehouse_id.id),('code','=','internal'),('active','=',True)],limit=1)
                    picking = self.env['stock.picking'].create({
                        'scheduled_date':res.date,
                        'location_dest_id':res.location_id.id,
                        'location_id':res.duty_id.machine_id.location_id.id,
                        'picking_type_id':picking_type_id.id,
                        'duty_line_id':res.id,
                        'fleet_id':res.duty_id.machine_id.id or False,
                        'department_id':res.duty_id.department_id.id or False,
                        'move_ids':[(0, 0, {
                                            'product_id': val.duty_id.fuel_product_id.id,
                                            'name':val.duty_id.fuel_product_id.name,
                                            'product_uom_qty': abs(val.fill_fuel),
                                            'location_dest_id':res.location_id.id ,
                                            'location_id':res.duty_id.machine_id.location_id.id,
                                            'division_id':val.division_id.id or False,
                                            'project_id': val.project_id.id or False,
                                            'fleet_location_id':val.duty_id.machine_id.id or False, 
                                            'fleet_id':val.duty_id.machine_id.id or False,
                                            'department_id':res.duty_id.department_id.id or False,
                                            'duty_line_id':val.id,  
                                            'remark':val.remark,        
                                        }) for val in res]
                        })
                    picking.action_confirm()
                    res.write({'picking_ids':[(4,picking.id)]})
                    res.picking_ids.write({'origin': res.duty_id.name+'-'+str(res.line_no),
                                           'location_dest_id':res.location_id.id,
                                           'location_id':res.duty_id.machine_id.location_id.id,})
                    for move in res.picking_ids.move_ids:
                        move.write({'location_dest_id':res.location_id.id,
                                           'location_id':res.duty_id.machine_id.location_id.id,})
                    for move_line in res.picking_ids.move_line_ids:
                        move_line.write({'location_dest_id':res.location_id.id,
                                           'location_id':res.duty_id.machine_id.location_id.id,})
                    if res.picking_ids.state not in ('done', 'cancel'):
                            res.picking_ids.write({'scheduled_date':res.date,})
                    
                else:
                    if len(picking_id)==1:
                        picking_id.write({'origin': res.duty_id.name+'-'+str(res.line_no),
                                           'location_dest_id':res.location_id.id,
                                           'location_id':res.duty_id.machine_id.location_id.id})
                        for move in picking_id.move_ids:
                            move.write({'location_dest_id':res.location_id.id,
                                            'location_id':res.duty_id.machine_id.location_id.id,})
                        for move_line in picking_id.move_line_ids:
                            move_line.write({'location_dest_id':res.location_id.id,
                                            'location_id':res.duty_id.machine_id.location_id.id,})
                        if picking_id.state not in ('done', 'cancel'):
                            picking_id.write({'scheduled_date':res.date,})
                        if picking_id.state in ('draft','assigned','waiting','confirmed'):
                            picking_id.move_ids.write({'product_uom_qty': abs(res.fill_fuel)})
            
            if picking_id and res.fill_fuel==0:
                picking_id.move_ids.write({'product_uom_qty': abs(res.fill_fuel)})
                    
    def compute_initial_fuel(self,qty):
        duty_line = self.duty_id.duty_line.filtered(lambda x:x.line_no>=self.line_no)
        line_array = sorted(list(set(duty_line.mapped('line_no'))))
        first = 1
        for x in line_array:
            for line in duty_line.filtered(lambda d:d.line_no==x):
                if first:
                    line.initial_fuel = qty
                    first = 0
                    initial_fuel = line.balance_fuel
                else:
                    line.initial_fuel = initial_fuel
                    initial_fuel = line.balance_fuel

    @api.onchange('project_id')
    def _onchage_analytic_by_project(self):
        if self.project_id and self.project_id.division_id:
            self.division_id = self.project_id.division_id.division_id                   
                
    @api.depends('total_use_fuel','run_hr')
    def compute_fuel_consumption(self):
        for rec in self:
            result = 0.0
            if rec.total_amt > 0 and rec.run_hr > 0:
                result = rec.total_use_fuel / rec.run_hr
            rec.fuel_consumption = result    
            val = False
            if rec.fuel_consumption > rec.duty_id.machine_id.standard_consumption:
                val = True 
            rec.over_consumption = val   

    @api.depends('fill_fuel_mark','use_fuel')
    def compute_balance_fuel(self):
        for rec in self:
            rec.balance_fuel =  rec.fill_fuel_mark - rec.use_fuel 

    @api.depends('fill_fuel_mark','initial_fuel')
    def compute_increase_fuel(self):
        for rec in self:
            rec.increase_fuel_mark =  rec.fill_fuel_mark - rec.initial_fuel

    def action_adjust(self):
        for result in self:
            if not result.adjust_id and result.fuel_amt > 0.0 and result.total_use_fuel > 0.0:
                dct = {}
                if result.project_id and result.project_id.analytic_project_id:
                    dct[str(result.project_id.analytic_project_id.id)] = 100
                if result.duty_id.machine_id and result.duty_id.machine_id.analytic_fleet_id:
                    dct[str(result.duty_id.machine_id.analytic_fleet_id.id)] = 100
                if result.division_id and result.division_id.analytic_account_id:
                    dct[str(result.division_id.analytic_account_id.id)] = 100
                if not result.duty_id.machine_id.fuel_account_id:
                    raise UserError(_("Please Configure for Machine Account"))
                rm_qty_temp = round(self.duty_id.machine_id.onhand_fuel  - result.total_use_fuel,2)
                if rm_qty_temp < 0.0:
                    raise ValidationError(f"Insufficient fuel consumption from machine!!! Available - {round(self.duty_id.machine_id.onhand_fuel,2)} / Consumed - {round(result.total_use_fuel,2)} ")
                adjust_out = self.env['stock.inventory.adjustment'].create({'journal_id':result.duty_id.fuel_journal.id,
                                                            'location_id':result.duty_id.machine_id.location_id.id,
                                                            'date':result.date,
                                                            'duty_line_id':result.id,
                                                            'ref': result.duty_id.name+'-'+str(result.line_no),
                                                            'department_id':result.duty_id.department_id.id or False,
                                                            'adjustment_line_id':[(0, 0, {
                                                                        'product_id': res.duty_id.fuel_product_id.id,
                                                                        'uom_id':res.duty_id.fuel_product_id.uom_id.id,
                                                                        'desc':res.duty_id.fuel_product_id.name,
                                                                        'quantity': -res.total_use_fuel,
                                                                        'unit_cost':res.duty_id.fuel_product_id.warehouse_valuation.filtered(lambda x:x.location_id.id == result.duty_id.machine_id.location_id.id).location_cost,
                                                                        'fleet_location_id':res.duty_id.machine_id.id,
                                                                        'adjust_account_id':res.duty_id.machine_id.fuel_account_id.id, #need to refix after when machine config set up
                                                                        'project_id':res.project_id.id,
                                                                        'division_id':res.division_id.id,
                                                                        'fleet_id':res.duty_id.machine_id.id,
                                                                        'analytic_distribution': dct,
                                                                        'description':res.remark,
                                                                        'job_code_id':res.job_code_id.id,
                                                                }) for res in result]})
                adjust_out.action_confirm()
                adjust_out.action_validate()
                
                self.duty_id.message_post(body=f"Created Stock Adjustment - {adjust_out.name} consuming {result.total_use_fuel} Litre..")
                result.write({'adjust_id':adjust_out.id})

    def action_return_adjust(self):
        for result in self:
            if result.adjust_id:
                adjust_return_form = Form(self.env['stock.return.adjust']
                    .with_context(active_ids=self.adjust_id.ids, active_id=self.adjust_id.sorted().ids[0],
                    active_model='stock.inventory.adjustment'))
                return_wiz = adjust_return_form.save()
                res = return_wiz.create_returns()
                return_adjust = self.env['stock.inventory.adjustment'].browse(res['res_id'])
                return_adjust.action_confirm()
                return_adjust.action_validate()
                calculated_qty = sum([adj_line.quantity for adj_line in return_adjust.adjustment_line_id])
                self.duty_id.machine_id.onhand_fuel += round(calculated_qty,2)
                self.duty_id.message_post(body=f"Created Stock Adjustment Return - {return_adjust.name} from Adjustment {result.adjust_id.name}..")
                self.write({'return_adjust_id':return_adjust.id})
                self.write({'adjust_id':False})
            
    @api.depends('rate_per_duty')
    def compute_rate_per_hour(self):
        for rec in self:
            result = 0.0
            if rec.rate_per_duty > 0:
                if rec.duty_id.machine_id.price_type == 'way':
                    result = rec.rate_per_duty/1
                elif rec.duty_id.machine_id.price_type == 'dm':
                    result = rec.rate_per_duty/30
                else:
                    result = rec.rate_per_duty / 8
            rec.rate_per_hour = result    

    @api.depends('rate_per_hour','run_hr','total_hr')
    def compute_duty_amt(self):
        for rec in self:
            duty_amt = 0.0
            if rec.duty_id.machine_id.price_type == 'way':
                duty_amt = rec.rate_per_hour * rec.way
            elif rec.duty_id.machine_id.price_type == 'dm':
                duty_amt = rec.rate_per_hour * rec.total_hr
            else:
                duty_amt = rec.rate_per_hour * rec.total_hr   
            rec.duty_amt = duty_amt

    def unlink(self):
        if (not self.move_id or self.move_id.state == 'cancel' ) and (not self.internal_move_id or self.internal_move_id.state == 'cancel' ) and (not self.adjust_id or self.return_adjust_id) and not self.picking_ids:
            return super().unlink()
        else:
            raise ValidationError("You can't delet when duty or fuel is posted or tasnfers are made!!")


    def post_duty_entry(self):
        for rec in self:
            if (not rec.move_id or rec.move_id.state=='cancel') and (not rec.internal_move_id or rec.internal_move_id.state== 'cancel'):
                if not rec.duty_id.duty_journal:
                    raise ValidationError('Invalid Duty Journal !')
                if rec.duty_id.machine_id.owner_type != 'internal':
                    if rec.duty_amt > 0.0:
                        
                        exp_acc = None
                        if rec.duty_id.machine_id.product_id.property_account_expense_id: 
                            exp_acc = rec.duty_id.machine_id.product_id.property_account_expense_id
                        if not exp_acc and rec.duty_id.machine_id.product_id.categ_id.property_account_expense_categ_id:
                            exp_acc = rec.duty_id.machine_id.product_id.categ_id.property_account_expense_categ_id

                        # calculate analytic
                        dct = {}
                        if rec.project_id and rec.project_id.analytic_project_id:
                            dct[str(rec.project_id.analytic_project_id.id)] = 100
                        if rec.duty_id.machine_id and rec.duty_id.machine_id.analytic_fleet_id:
                            dct[str(rec.duty_id.machine_id.analytic_fleet_id.id)] = 100
                        if rec.division_id and rec.division_id.analytic_account_id:
                            dct[str(rec.division_id.analytic_account_id.id)] = 100

                        # 1) Create invoices.
                        invoice_vals_list = []
                        pending_section = None
                        partner_id = rec.duty_id.machine_id.partner_id
                        if not partner_id:
                            raise UserError(_("Please Define Partner for Owner Type (Internal)"))
                        # Invoice values.
                        invoice_vals = {
                            'internal_ref': rec.duty_id.name+'-'+str(rec.line_no) or '',
                            'narration': rec.remark,
                            'partner_id': partner_id.id,
                            'invoice_origin': rec.duty_id.name+'-'+str(rec.line_no),
                            'duty_line_id':rec.id,
                            'journal_id':rec.duty_id.duty_journal.id,
                            'department_id':rec.duty_id.department_id.id or False,
                            'invoice_line_ids': [],
                            'date': rec.date,
                            'invoice_date':rec.date,                          
                        }
                        if rec.total_hr > 0:
                            invoice_vals.update({'move_type': 'in_invoice',})
                        else:
                            invoice_vals.update({'move_type': 'in_refund',})
                        
                        line_vals = {
                            'name': rec.remark,
                            'product_id': rec.duty_id.machine_id.product_id.id,
                            'product_uom_id': rec.duty_id.machine_id.product_id.uom_id.id,
                            'quantity': abs(rec.total_hr),
                            'price_unit': rec.rate_per_hour,
                            'account_id': exp_acc.id,
                            'fleet_id':rec.duty_id.machine_id.id,
                            'project_id':rec.project_id and rec.project_id.id or False,
                            'division_id':rec.division_id and rec.division_id.id or False,
                            'analytic_distribution': dct,
                            'job_code_id':rec.job_code_id.id,
                            'report_remark_id':rec.report_remark_id.id,                              
                        }
                        
                        invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

                        if not invoice_vals['invoice_line_ids']:
                            raise UserError(_('There is no invoiceable line. If a product has a Delivered quantities invoicing policy, please make sure that a quantity has been delivered.'))

                        invoice_vals_list.append(invoice_vals)
                        moves = self.env['account.move'].sudo().create(invoice_vals_list)
                        rec.move_id = moves.id
                if rec.duty_id.machine_id.owner_type == 'internal':
                    if rec.duty_id.machine_id.duty_hr_account_id and rec.duty_id.machine_id.duty_depreciation_account_id:
                        # calculate analytic
                        analytic_dct = {}
                        if rec.project_id and rec.project_id.analytic_project_id:
                            analytic_dct[str(rec.project_id.analytic_project_id.id)] = 100
                        if rec.duty_id.machine_id and rec.duty_id.machine_id.analytic_fleet_id:
                            analytic_dct[str(rec.duty_id.machine_id.analytic_fleet_id.id)] = 100
                        if rec.division_id and rec.division_id.analytic_account_id:
                            analytic_dct[str(rec.division_id.analytic_account_id.id)] = 100
                        if rec.duty_amt>0:
                            moves = self.env['account.move'].create([
                                
                                {
                                    'date': rec.date,
                                    'journal_id':rec.duty_id.duty_journal.id,                                
                                    'internal_ref': rec.duty_id.name+'-'+str(rec.line_no) or '',
                                    'department_id':rec.duty_id.department_id.id or False,
                                    'line_ids': [
                                        Command.create({
                                            'name': rec.remark,
                                            'account_id': rec.duty_id.machine_id.duty_hr_account_id.id,
                                            'project_id': rec.project_id.id,
                                            'division_id':rec.division_id.id,
                                            'fleet_id': rec.duty_id.machine_id.id,
                                            'analytic_distribution': analytic_dct,
                                            'job_code_id':rec.job_code_id.id,
                                            'report_remark_id':rec.report_remark_id.id,                                                                                    
                                            'balance': rec.duty_amt,
                                        }),
                                        Command.create({
                                            'name': rec.remark,
                                            'account_id': rec.duty_id.machine_id.duty_depreciation_account_id.id,
                                            'project_id': rec.project_id.id,
                                            'division_id':rec.division_id.id,
                                            'fleet_id': rec.duty_id.machine_id.id,
                                            'analytic_distribution': analytic_dct,
                                            'job_code_id':rec.job_code_id.id,
                                            'report_remark_id':rec.report_remark_id.id,
                                            'balance': -rec.duty_amt,
                                        }),
                                    ]
                                }
                            ])
                            moves.action_post()
                            rec.internal_move_id = moves.id
                        elif rec.duty_amt < 0:
                            moves = self.env['account.move'].create([
                                {
                                    'date': rec.date,
                                    'journal_id':rec.duty_id.duty_journal.id,
                                    'internal_ref': rec.duty_id.name+'-'+str(rec.line_no) or '',     
                                    'department_id': rec.duty_id.department_id.id or False,                               
                                    'line_ids': [
                                        Command.create({
                                            'name': rec.remark,
                                            'account_id': rec.duty_id.machine_id.duty_hr_account_id.id,
                                            'project_id': rec.project_id.id,
                                            'division_id':rec.division_id.id,
                                            'fleet_id': rec.duty_id.machine_id.id,
                                            'analytic_distribution': analytic_dct,
                                            'job_code_id':rec.job_code_id.id,
                                            'report_remark_id':rec.report_remark_id.id,                                            
                                            'balance': rec.duty_amt,
                                        }),
                                        Command.create({
                                            'name': rec.remark,
                                            'account_id': rec.duty_id.machine_id.duty_depreciation_account_id.id,
                                            'project_id': rec.project_id.id,
                                            'division_id':rec.division_id.id,
                                            'fleet_id': rec.duty_id.machine_id.id,
                                            'analytic_distribution': analytic_dct,
                                            'job_code_id':rec.job_code_id.id,
                                            'report_remark_id':rec.report_remark_id.id,                                            
                                            'balance': -rec.duty_amt,
                                        }),
                                    ]
                                }
                            ])
                            moves.action_post()
                            rec.internal_move_id = moves.id
                    else:
                        raise UserError(_("Please Configure Duty Account Setting"))
            # elif rec.move_id and rec.move_id.state!='cancel':
            #     raise UserError(("You need to cancel first Journal Entry %s")%rec.move_id.ref)


class DutyProcessLineStatus(models.Model):
	_name = "duty.process.line.status"

	name = fields.Char("Name")
     

class FuelFillingNo(models.Model):
    _name = 'duty.fuel.filling.no'

    name = fields.Char("Filling No.",required=True)
    increased_mark = fields.Float("Increased Mark")


class DutyLineInitial(models.Model):
    _name = 'duty.initial.entry'

    qty = fields.Float('Initial Fuel')
    duty_line_id = fields.Many2one('duty.process.line',string="line")
    duty_id = fields.Many2one('duty.process',string="Duty Process")

    def action_done(self):
        if self.qty > 0.0 and self.duty_line_id and self.duty_id:
            self.duty_line_id.compute_initial_fuel(self.qty)


class DutyAdjustTransfer(models.Model):
    _name = 'duty.adjust.transfer'

    transfer_type = fields.Selection([('add','Add Transfer'),('remove','Remove Transfer')],default='add')
    qty = fields.Float('Adjust Transfer Qty')
    duty_line_id = fields.Many2one('duty.process.line',string="line")
    duty_id = fields.Many2one('duty.process',string="Duty Process")
    picking_ids = fields.Many2one('stock.picking')
    done_qty = fields.Float('Done Qty',readonly=True,default=0.0)

    @api.onchange('picking_ids')
    def _get_done_qty(self):
        origin_qty = sum(self.picking_ids.move_ids.mapped('product_uom_qty'))
        return_line = self.env['stock.move'].search([('origin_returned_move_id','=',self.picking_ids.move_ids.id)])
        return_qty = sum(return_line.mapped('product_uom_qty')) or 0
        self.done_qty = origin_qty-return_qty

    @api.onchange('duty_line_id')
    def _get_pickings_domain(self):
        pickings = []
        for move in self.duty_line_id.picking_ids.move_ids:
            if not move.origin_returned_move_id:
                pickings.append(move.picking_id.id)
        return {'domain': {'picking_ids': [('id', 'in', pickings)]}}  

    def action_done(self):
        if self.qty > 0.0 and self.duty_line_id and self.duty_id:
            if self.transfer_type=='add':
                new_picking = self.picking_ids.copy()
                new_picking.move_ids.write({'product_uom_qty':self.qty})
                new_picking.write({'state':'draft','scheduled_date':self.picking_ids.scheduled_date})
                new_picking.action_confirm()
                # new_picking.action_assign()
                # action = new_picking.button_validate()
                # wizard = Form(self.env[action['res_model']].with_context(action['context'])).save()
                # wizard.process()
                self.duty_line_id.write({'picking_ids':[(4,new_picking.id)],'fill_fuel':self.duty_line_id.fill_fuel+self.qty})
                # self.duty_id.message_post(body=f"Add {self.qty} Litre  to duty line ID - {self.duty_line_id.id} - and created draft {new_picking.name} ..")
            else:
                origin_qty = sum(self.picking_ids.move_ids.mapped('product_uom_qty'))
                return_line = self.env['stock.move'].search([('origin_returned_move_id','=',self.picking_ids.move_ids.id)])
                return_qty = sum(return_line.mapped('product_uom_qty')) or 0
                done_qty = origin_qty-return_qty        
                if self.qty > done_qty:
                    raise ValidationError("Removed Qty must be less than or equal to Done Qty..")                
                if self.picking_ids:
                    stock_return_picking_form = Form(self.env['stock.return.picking']
                        .with_context(active_ids=self.picking_ids.ids, active_id=self.picking_ids.sorted().ids[0],
                        active_model='stock.picking'))
                    return_wiz = stock_return_picking_form.save()
                    return_wiz.product_return_moves.quantity = self.qty # Return only 2
                    return_wiz.product_return_moves.to_refund = True # Refund these 2
                    res = return_wiz.create_returns()
                    return_pick = self.env['stock.picking'].browse(res['res_id'])

                    # Validate picking
                    return_pick.move_ids.write({'quantity_done': self.qty})
                    # return_pick.button_validate()
                    return_pick.write({'origin':self.picking_ids.origin})
                   
                    self.duty_line_id.write({'picking_ids':[(4,return_pick.id)],'fill_fuel':self.duty_line_id.fill_fuel-self.qty})
                    # self.duty_id.message_post(body=f"Remove {self.qty} Litre  Stock Transfer from duty line ID - {self.duty_line_id.id} - and created {return_pick.name} from return of {self.picking_ids.name} ..")
                else:
                    raise UserError(_("Please select Origin Picking which you want to return"))




class Location(models.Model):
    _inherit = "stock.location"

    machine_location = fields.Boolean('Is a Machine Location?', default=False, help='Check this box to allow using this location to put Fuel to Machine')

class Picking(models.Model):
    _inherit = "stock.picking"

    duty_line_id = fields.Many2one("duty.process.line")
    fleet_id = fields.Many2one('fleet.vehicle','Fleet',domain=[("type", "=", "fleet")])  
    fleet_owner_id = fields.Many2one('fleet.owner',string="Owner",related="fleet_id.owner_id",store=True,domain=[])

class StockMove(models.Model):
    _inherit = "stock.move"

    duty_line_id = fields.Many2one("duty.process.line",related='picking_id.duty_line_id')


class StockAdjustment(models.Model):
    _inherit = "stock.inventory.adjustment"

    duty_line_id = fields.Many2one("duty.process.line")
    is_machine_location = fields.Boolean("Is Machine Location?",related="location_id.machine_location")


class AccountMove(models.Model):
    _inherit = "account.move"

    duty_line_id = fields.Many2one("duty.process.line")








