import hashlib
import json
import requests
import locale
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError,ValidationError
from datetime import datetime, timedelta
from datetime import date
from odoo.tools.float_utils import float_compare, float_round,float_is_zero

class DirectorReport(models.Model):
    _name = 'director.report'
    _auto = False
    _order = 'date'

    module_id = fields.Integer()
    type = fields.Char('Type')
    date = fields.Date('Date')
    seq_no = fields.Char('Number')
    journal = fields.Many2one('account.journal',string="Journal")
    partner = fields.Many2one('res.partner',string="Partner")
    contact = fields.Many2one('hr.employee',string="Employee")
    company = fields.Many2one('res.company',string="Unit")
    desc= fields.Char('Description')
    amount = fields.Float('Amount')
    currency = fields.Many2one('res.currency',string="Currency")
    state = fields.Char('Status')
    # director_id = fields.Integer(string="Director")

    # def check_validate_user(self,user_ary):
    #     ary = list(dict.fromkeys(user_ary))
    #     if len(ary) == 0:
    #         raise ValidationError('Blank User Permission in selected records.')
    #     if len(ary) > 1:
    #         raise ValidationError('Invalid User in Selected records.')
    #     if self.env.user.id not in ary:
    #         raise ValidationError('Invalid User to approve.')

    # def check_validate(self,ary,status):
    #     ary = list(dict.fromkeys(ary))
    #     print ('ary-->',ary)
    #     if len(ary) > 1:
    #         raise ValidationError('Can not approve for different status.All advance must be %s'% status)

    #     if status not in ary:
    #         raise ValidationError('Invalid State For %s'% status)

    # def divide_ary_type(self,line_ids):
    #     pe_ary = []
    #     de_ary = []
    #     pay_ary = []
    #     for rec in line_ids:
    #         if rec.type == 'Prepaid Expenses':
    #             pe_ary.append(rec.model_id)
    #         elif rec.type == 'Direct Expenses':
    #             de_ary.append(rec.model_id)
    #         else:
    #             pay_ary.append(rec.model_id)
    #     return pe_ary,de_ary,pay_ary

    def action_multi_director_approve(self):
        print ("Hello")
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return ''       
        line_ids = self.env['director.report'].search([('id','in',active_ids)])      
        
        for rec in line_ids:
            if rec.type == 'Advance Prepaid':
                advance = self.env['advance.prepaid'].browse(rec.module_id)
                if advance:
                    advance.action_dir_approve() 
            if rec.type == 'Vendor Payment':
                payment = self.env['account.payment'].browse(rec.module_id)
                if payment:
                    payment.action_change_status() 

            if rec.type == 'Direct Expense':
                expense = self.env['account.move'].browse(rec.module_id)
                if expense:
                    expense.action_dir_approve() 

            if rec.type == 'Vendor Prepayment':
                prepayment = self.env['account.payment.prepaid'].browse(rec.module_id)
                if prepayment:
                    prepayment.action_bod_mng_approve() 
        # data_ary = []
        # pe_ary = []
        # de_ary = []
        # pay_ary = []
        # director_ary = []
        # for rec in line_ids:
        #     data_ary.append(rec.status)
        #     if rec.director_id:
        #         director_ary.append(rec.director_id)
        # self.check_validate(data_ary,'Waiting Director Approval')
        # self.check_validate_user(director_ary)
        # pe_ary,de_ary,pay_ary = self.divide_ary_type(line_ids)       
        # if len(pe_ary) > 0:
        #     pe_ids = self.env['expense.prepaid'].search([('id','in',pe_ary)])
        #     for pe in pe_ids:
        #         pe.action_advance_bod_approve()               
        # if len(de_ary) > 0:
        #     de_ids = self.env['hr.direct.expense'].search([('id','in',de_ary)])
        #     for de in de_ids:
        #         de.expense_director_approve()
        # if len(pay_ary) > 0:
        #     pay_ids = self.env['account.payment'].search([('id','in',pay_ary)])
        #     for pay in pay_ids:
        #         pay.action_bod_mng_approve()
        

    def action_open_model(self):
        for rec in self:
            if rec.module_id and rec.type:
                if rec.type == 'Direct Expense':
                    res_model = 'account.move'
                    res_name = 'Direct Expense'
                elif rec.type == 'Advance Prepaid':
                    res_model = 'advance.prepaid'
                    res_name = 'Advance Prepaid'
                elif rec.type == 'Vendor Payment':
                    res_model = 'account.payment'
                    res_name = 'Vendor Payment'
                else:
                    res_model = 'account.payment.prepaid'
                    res_name = 'Vendor Prepayment'
                return {
                        'name': _(res_name),
                        'view_mode': 'form',
                        'res_model': res_model,
                        'res_id': rec.module_id,
                        'view_id': False,
                        'type': 'ir.actions.act_window',
                        'target': 'current',
                    } 
            else:
                raise ValidationError('Currently Not Linked With Model.')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (select 
                row_number() over () as id,
                a.type,
                a.date,
                a.seq_no,
                a.journal,
                a.partner,
                a.contact,
                a.company,
                a.desc,
                a.amount,
                a.currency,
                a.state,
                a.module_id from (
                select ap.id as module_id,'Advance Prepaid' as type,
                ap.date as date,ap.name as seq_no,null as journal,ap.partner_id as partner,ap.contact_id as contact,ap.company_id as company,ap.desc as desc,
                ap.prepare_amt as amount,ap.currency_id as currency,ap.state as state
                from advance_prepaid ap 
                where ap.need_of_dir_approve='true'

                UNION ALL

                select am.id as module_id,'Direct Expense' as type,
                am.date as date,am.ref as seq_no,am.journal_id as journal,am.partner_id as partner,am.contact_id as contact,am.company_id as company,am.internal_ref as desc,
                am.amount_total as amount,am.currency_id as currency,am.state as state
                from account_move am 
                where am.is_expense='true' and am.expense_type='dir_exp' and am.need_of_dir_approve='true'

                UNION ALL

                select app.id as module_id,'Vendor Prepaidment' as type,
                app.date as date,app.seq_no as seq_no,app.journal_id as journal,app.partner_id as partner,null as contact,app.company_id as company,app.ref as desc,
                app.prepare_amount as amount,app.currency_id as currency,app.state as state
                from account_payment_prepaid app 
                where app.need_of_director_approve='true'
                            
                UNION ALL

                select acc.id as module_id,'Vendor Payment' as type,
                am.date as date,acc.seq_name as seq_no,am.journal_id as journal,acc.partner_id as partner,null as contact,am.company_id as company,acc.desc as desc,
                acc.amount as amount,acc.currency_id as currency,acc.x_state as state
                from account_payment acc 
				LEFT JOIN account_move am on am.id=acc.move_id
                where acc.need_of_dir_approve='true')a
                )''' % (self._table,)
        )