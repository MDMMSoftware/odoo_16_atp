import time
import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _
from odoo.tools import float_is_zero
from odoo.tools import date_utils
import io
import json
import odoorpc

from odoo.exceptions import UserError

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

class CashbookCheckExcelWizard(models.TransientModel):
    _name = "cashbook.check.xlsx.wizard"
    start_date = fields.Datetime(string="Start Date",
                                    default=time.strftime('%Y-%m-01'),
                                    required=True)
    end_date = fields.Datetime(string="End Date",
                                default=datetime.datetime.now(),
                                required=True)
    company_id = fields.Many2many("res.company",domain=lambda self: [('id', '!=', self.env.company.id)])
    server_type = fields.Selection([('all','Export from Both Server'),('same','Compare via Same Server'),('diff','Compare via Different Server')],default='all')
    transfer_company_id = fields.Many2many('transfer.company',domain=lambda self: [('diff_server', '=', True)])


    
    
    def print_xlsx(self):
        output = io.BytesIO()
        file_name = os.path.join(tempfile.gettempdir(), 'Cashbook Check Report.xlsx')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Cashbook Check Report")
        banner_format_small = workbook.add_format({'font_name': 'Arial','bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})
       
        sheet.set_column(0, 0, 40)
        sheet.set_column(1, 1, 40)
        sheet.set_column(2, 2, 40)
        sheet.set_column(3, 3, 40)
        # sheet.set_column(4, 4, 40)
        

        y_offset = 3
        x_offset = 3
        sheet.merge_range(0,0,x_offset,y_offset, _("Cashbook Check Report"), banner_format_small)
        x_offset+=1
        sheet.write(x_offset,0,"From",header_format)
        sheet.write(x_offset,1,self.start_date.strftime("%d-%b-%Y"),header_format)
        sheet.write(x_offset,2,"To",header_format)
        sheet.write(x_offset,3,self.end_date.strftime("%d-%b-%Y"),header_format)
        x_offset+=2
        if self.server_type != 'diff':
        
            # sheet.merge_range(0,0,x_offset,y_offset, _("Cashbook Check Report\nfrom %s to %s Transactions",self.env.company.name,self.company_id.name), banner_format_small)
            

            cashbooks = self.env['account.cashbook'].sudo().search([('date','>=',self.start_date),('date','<=',self.end_date),('state','=','done')])
            sheet.write(x_offset,0,"Payment",header_format)
            x_offset+=1
            for company in self.company_id:
                trans_comp_to = self.env['transfer.company'].search([('name','=',company.name)])
                trans_comp_from = self.env['transfer.company'].search([('name','=',self.env.company.name)])
                cashbook_company_from = cashbooks.filtered(lambda x:x.company_id==self.env.company and x.cash_type=='pay' and x.transfer_company_id==trans_comp_to) 
                cashbook_company_to = cashbooks.filtered(lambda x:x.company_id==company and x.cash_type=='receive' and x.transfer_company_id==trans_comp_from)
                if cashbook_company_to or cashbook_company_from:
                    sheet.write(x_offset,0,"Date",header_format)
                    sheet.write(x_offset,1,_('Payment (%s)',self.env.company.name),header_format)
                    sheet.write(x_offset,2,_('Receipt (%s)',company.name),header_format)
                    sheet.write(x_offset,3,"Balance",header_format)
                    x_offset+=1
                    
                    for date in sorted(set(cashbooks.mapped('date'))):
                        cashbooks_from = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_from.ids)])
                        cashbooks_to = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_to.ids)])
                        from_amount = sum(cashbooks_from.mapped('amount_total')) or 0
                        to_amount = sum(cashbooks_to.mapped('amount_total')) or 0
                        balance = from_amount-to_amount or 0
                        if not (from_amount==0 and to_amount==0):
                            sheet.write(x_offset,0,date.strftime("%d-%m-%Y"),text_format)
                            sheet.write(x_offset,1,from_amount,text_format)
                            sheet.write(x_offset,2,to_amount,text_format)
                            sheet.write(x_offset,3,balance,text_format)
                            x_offset+=1

            x_offset+=1
            sheet.write(x_offset,0,"Receipt",header_format)
            x_offset+=1
            for company in self.company_id:
                trans_comp_to = self.env['transfer.company'].search([('name','=',company.name)])
                trans_comp_from = self.env['transfer.company'].search([('name','=',self.env.company.name)])
                cashbook_company_to = cashbooks.filtered(lambda x:x.company_id==self.env.company and x.cash_type=='receive' and x.transfer_company_id==trans_comp_to) 
                cashbook_company_from = cashbooks.filtered(lambda x:x.company_id==company and x.cash_type=='pay' and x.transfer_company_id==trans_comp_from)
                if cashbook_company_to or cashbook_company_from:
                    sheet.write(x_offset,0,"Date",header_format)
                    sheet.write(x_offset,1,_('Payment (%s)',company.name),header_format)
                    sheet.write(x_offset,2,_('Receipt (%s)',self.env.company.name),header_format)
                    sheet.write(x_offset,3,"Balance",header_format)
                    x_offset+=1
                    
                    for date in sorted(set(cashbooks.mapped('date'))):
                        cashbooks_from = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_from.ids)])
                        cashbooks_to = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_to.ids)])
                        from_amount = sum(cashbooks_from.mapped('amount_total')) or 0
                        to_amount = sum(cashbooks_to.mapped('amount_total')) or 0
                        balance = from_amount-to_amount or 0
                        if not (from_amount==0 and to_amount==0):
                            sheet.write(x_offset,0,date.strftime("%d-%m-%Y"),text_format)
                            sheet.write(x_offset,1,from_amount,text_format)
                            sheet.write(x_offset,2,to_amount,text_format)
                            sheet.write(x_offset,3,balance,text_format)
                            x_offset+=1

            


            # sheet.write(x_offset,0,"Date",header_format)
            # sheet.write(x_offset,1,_('Payment (%s)',self.env.company.name),header_format)
            # sheet.write(x_offset,2,_('Receipt (%s)',self.company_id.name),header_format)
            # sheet.write(x_offset,3,"Balance",header_format)
            # x_offset+=1
            # cashbooks = self.env['account.cashbook'].sudo().search([('date','>=',self.start_date),('date','<=',self.end_date)])
            
            # if cashbooks.mapped('date'):
            #     for date in sorted(set(cashbooks.mapped('date'))):
            #         cashbooks_from = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_from.ids)])
            #         cashbooks_to = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_to.ids)])
            #         from_amount = sum(cashbooks_from.mapped('amount_total')) or 0
            #         to_amount = sum(cashbooks_to.mapped('amount_total')) or 0
            #         balance = from_amount-to_amount or 0
            #         if not (from_amount==0 and to_amount==0):
            #             sheet.write(x_offset,0,date.strftime("%d-%m-%Y"),text_format)
            #             sheet.write(x_offset,1,from_amount,text_format)
            #             sheet.write(x_offset,2,to_amount,text_format)
            #             sheet.write(x_offset,3,balance,text_format)
            #             x_offset+=1

        if self.server_type != 'same':
            parallel_host = self.env['ir.config_parameter'].sudo().get_param('parallel.host')
            if not parallel_host:
                raise ValidationError("Parallel Host Not found!!")
            odoo = odoorpc.ODOO(parallel_host)
            
            # print(odoo.db.list())

            odoo.login('m_auto_go_live', 'admin', 'admin')
            cashbooks = self.env['account.cashbook'].search([('date','>=',self.start_date),('date','<=',self.end_date),('state','=','done')])
            sheet.write(x_offset,0,"Payment",header_format)
            x_offset+=1
            for company in self.transfer_company_id:
                if not company.branch_name:
                    raise UserError(_("Company Branch Name Required for %s",company.name))
                if not odoo.env['res.company'].search([('name','=',company.name)]):
                    raise UserError(_("Company Name doesn't match with Another Server"))
                if not odoo.env['res.branch'].search([('name','=',company.branch_name)]):
                    raise UserError(_("Company Branch doesn't match with Another Server"))
                
                # company = odoo.env['res.company'].search([('name','=',company.name)])
                
                trans_comp_to = self.env['transfer.company'].search([('name','=',company.name),('branch_name','=',company.branch_name)])
                trans_comp_from = self.env['transfer.company'].search([('name','=',self.env.company.name)]).id
                cashbook_company_from = cashbooks.filtered(lambda x:x.company_id==self.env.company and x.cash_type=='pay' and x.transfer_company_id==trans_comp_to) 
                company = odoo.env['res.company'].search([('name','=',company.name)])
                company_obj=odoo.env['res.company'].browse(company)
                cashbook_company_to = odoo.env['account.cashbook'].search([('company_id','in',company),('cash_type','=','receive'),('transfer_company_id','=',trans_comp_from),('date','>=',json.dumps(self.start_date, default = serialize_datetime)),('date','<=',json.dumps(self.end_date, default = serialize_datetime)),('state','=','done')])
                date_arr = []
                cashbook_obj = odoo.env['account.cashbook'].browse(cashbook_company_to)
                for res in cashbook_obj:
                    date_arr.append(res.date)
                # cashbook_company_to = cashbooks.filtered(lambda x:x.company_id==company and x.cash_type=='receive' and x.transfer_company_id==trans_comp_from)
                if cashbook_company_to or cashbook_company_from:
                    sheet.write(x_offset,0,"Date",header_format)
                    sheet.write(x_offset,1,_('Payment (%s)',self.env.company.name),header_format)
                    sheet.write(x_offset,2,_('Receipt (%s)',company_obj.name),header_format)
                    sheet.write(x_offset,3,"Balance",header_format)
                    x_offset+=1
                    
                    for date in sorted(set(cashbooks.mapped('date')+date_arr)):
                        cashbooks_from = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_from.ids)])
                        cashbooks_to = odoo.env['account.cashbook'].search([('date','=',json.dumps(date, default = serialize_datetime)),('id','in',cashbook_company_to),('state','=','done')])
                        cashbooks_to = odoo.env['account.cashbook'].browse(cashbooks_to)
                        from_amount = sum(cashbooks_from.mapped('amount_total')) or 0
                        to_amount = sum(cashbooks_to.mapped('amount_total')) or 0
                        balance = from_amount-to_amount or 0
                        if not (from_amount==0 and to_amount==0):
                            sheet.write(x_offset,0,date.strftime("%d-%m-%Y"),text_format)
                            sheet.write(x_offset,1,from_amount,text_format)
                            sheet.write(x_offset,2,to_amount,text_format)
                            sheet.write(x_offset,3,balance,text_format)
                            x_offset+=1

            x_offset +=2
            sheet.write(x_offset,0,"Receipt",header_format)
            x_offset+=1
            for company in self.transfer_company_id:
                if not company.branch_name:
                    raise UserError(_("Company Branch Name Required for %s",company.name))
                if not odoo.env['res.company'].search([('name','=',company.name)]):
                    raise UserError(_("Company Name doesn't match with Another Server"))
                if not odoo.env['res.branch'].search([('name','=',company.branch_name)]):
                    raise UserError(_("Company Branch doesn't match with Another Server"))
                
                # company = odoo.env['res.company'].search([('name','=',company.name)])
                
                trans_comp_to = self.env['transfer.company'].search([('name','=',company.name),('branch_name','=',company.branch_name)])
                trans_comp_from = self.env['transfer.company'].search([('name','=',self.env.company.name)]).id
                cashbook_company_to = cashbooks.filtered(lambda x:x.company_id==self.env.company and x.cash_type=='receive' and x.transfer_company_id==trans_comp_to) 
                company = odoo.env['res.company'].search([('name','=',company.name)])
                company_obj=odoo.env['res.company'].browse(company)
                cashbook_company_from = odoo.env['account.cashbook'].search([('company_id','in',company),('cash_type','=','pay'),('transfer_company_id','=',trans_comp_from),('date','>=',json.dumps(self.start_date, default = serialize_datetime)),('date','<=',json.dumps(self.end_date, default = serialize_datetime)),('state','=','done')])
                cashbook_obj = odoo.env['account.cashbook'].browse(cashbook_company_from)
                date_arr = []
                for res in cashbook_obj:
                    date_arr.append(res.date)
                # cashbook_company_to = cashbooks.filtered(lambda x:x.company_id==company and x.cash_type=='receive' and x.transfer_company_id==trans_comp_from)
                if cashbook_company_to or cashbook_company_from:
                    sheet.write(x_offset,0,"Date",header_format)
                    sheet.write(x_offset,1,_('Payment (%s)',company_obj.name),header_format)
                    sheet.write(x_offset,2,_('Receipt (%s)',self.env.company.name),header_format)
                    sheet.write(x_offset,3,"Balance",header_format)
                    x_offset+=1
                    
                    for date in sorted(set(cashbooks.mapped('date')+date_arr)):
                        cashbooks_from = cashbooks.sudo().search([('date','=',date),('id','in',cashbook_company_to.ids)])
                        cashbooks_to = odoo.env['account.cashbook'].search([('date','=',json.dumps(date, default = serialize_datetime)),('id','in',cashbook_company_from),('state','=','done')])
                        cashbooks_to = odoo.env['account.cashbook'].browse(cashbooks_to)
                        from_amount = sum(cashbooks_from.mapped('amount_total')) or 0
                        to_amount = sum(cashbooks_to.mapped('amount_total')) or 0
                        balance = from_amount-to_amount or 0
                        if not (from_amount==0 and to_amount==0):
                            sheet.write(x_offset,0,date.strftime("%d-%m-%Y"),text_format)
                            sheet.write(x_offset,1,from_amount,text_format)
                            sheet.write(x_offset,2,to_amount,text_format)
                            sheet.write(x_offset,3,balance,text_format)
                            x_offset+=1
            


        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)
        

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/binary/download_document?model=cashbook.check.xlsx.wizard&id=%s&file_name=%s" % (self.id, file_name),
            'close': True,
        }
    
def serialize_datetime(obj): 
    if isinstance(obj, datetime.datetime): 
        return obj.isoformat() 
    if isinstance(obj, datetime.date): 
        return obj.isoformat() 
    raise TypeError("Type not serializable")
  