import calendar
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from requests.auth import HTTPBasicAuth
import hashlib
import json
import requests
import locale

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero
from odoo.osv import expression


class ReconcilePaymentTransfer(models.Model):
    _name = 'account.reconcile.transfer'

    @api.model
    def get_today(self):
        my_date = fields.Datetime.context_timestamp(self, timestamp=datetime.now())
        return my_date

    account_id = fields.Many2one('account.account',string="Account",required=True)
    date = fields.Date('Date',required=True, default=get_today)
    payment_id = fields.Many2one('account.payment',string="Payment")
    amount = fields.Float('Amount')
    contra_account_id = fields.Many2one('account.account',string="Contra Account",required=True)
    reconcile_amt = fields.Float('Reconcile amount')

    def get_advance_balance(self):
        for rec in self:
            balance = 0.0
            re_amt = 0.0
            if rec.payment_id:
                payment_id = rec.payment_id
                arap_id = self.env['account.move.line'].search([('move_id','=',payment_id.move_id.id),('account_id','=',payment_id.destination_account_id.id)],limit=1)
                balance = rec.payment_id.amount
                if payment_id.payment_type == 'inbound':        
                    reconcile_line = self.env['account.partial.reconcile'].search([('credit_move_id','=',arap_id.id)]) 
                else:
                    reconcile_line = self.env['account.partial.reconcile'].search([('debit_move_id','=',arap_id.id)])           
                for re in reconcile_line:
                    re_amt += re.debit_amount_currency
                balance = balance - re_amt
            return balance

    @api.constrains('account_id','payment_id','amount')
    def constrains_payment(self):
        if self.account_id and self.payment_id:
            if self.account_id == self.payment_id.destination_account_id:
                raise ValidationError('Invalid Account Transaction.')
        if self.amount <= 0.0:
            raise ValidationError('Amount must be greater than 0.')
        if self.amount > self.get_advance_balance():
            raise ValidationError('Over Balance Reconcile')

    @api.onchange('payment_id')
    def onchange_payment_id(self):
        if self.payment_id:
            if self.payment_id.payment_type == 'inbound':
                account_id = self.payment_id.partner_id.property_account_receivable_id.id             
            else: 
                account_id = self.payment_id.partner_id.property_account_payable_id.id
            self.amount = self.get_advance_balance()
            self.reconcile_amt = self.payment_id.amount-self.get_advance_balance()
            self.account_id = account_id

    def create_partial_reconcile(self,amount_currency,amount,debit_move_id,credit_move_id):
        out_val = {
                    'amount': amount,
                    'company_id': 1,
                    'debit_amount_currency': amount_currency,
                    'credit_amount_currency': amount_currency,  
                }         
        out_val.update({'debit_move_id': debit_move_id.id,
                        'credit_move_id': credit_move_id.id,}) 
         
        result_id = self.env['account.partial.reconcile'].create(out_val)
        return result_id

    def action_done(self):
        for rec in self:
            if not rec.payment_id:
                raise ValidationError('Reference Payment Not Found')
            payment_id = rec.payment_id
            data_ary = {
                        'department_id': payment_id.department_id.id,                     
                        'description': payment_id.desc,
                        'currency_id':payment_id.currency_id.id,
                        'exchange_rate': payment_id.exchange_rate,
                        'date_maturity': rec.date,
                        'name': str(payment_id.seq_name),
                        'partner_id': payment_id.partner_id.id,
                        }
            
            if payment_id.payment_type == 'inbound':
                debit_acc = payment_id.destination_account_id.id
                credit_acc =rec.contra_account_id.id
                debit_acc2 = rec.contra_account_id.id
                credit_acc2 = rec.account_id.id             
            else: 
                debit_acc = rec.contra_account_id.id
                credit_acc = payment_id.destination_account_id.id
                debit_acc2 = rec.account_id.id
                credit_acc2 = rec.contra_account_id.id
            
            amount = rec.amount
            amount_currency = rec.amount
            if payment_id.currency_id != payment_id.currency_id:
                amount = rec.amount * payment_id.exchange_rate
            res1 = res2 = []
            res1 = rec.prepare_move_line(debit_acc,data_ary,amount,0.0,amount_currency)  
            res2 = rec.prepare_move_line(credit_acc,data_ary,0.0,amount,amount_currency) 
            res = res1 + res2
            m_line = [(0, 0, l) for l in res]
            move_vals = {
                'journal_id': payment_id.journal_id.id,
                'ref': payment_id.move_id.name,
                'internal_ref': payment_id.seq_name,
                'date': rec.date,
                'line_ids': m_line,
                'payment_id': payment_id.id,
                'partner_id': payment_id.partner_id.id,
            }
            move_id = self.env['account.move'].create(move_vals)
            move_id._post()
            msg = 'Reconciliation Transfer: '+ str(move_id.name) + ' is created.'
            payment_id.message_post(body=msg)
            arap_id = self.env['account.move.line'].search([('move_id','=',payment_id.move_id.id),('account_id','=',payment_id.destination_account_id.id)],limit=1)
            arap_id2 = self.env['account.move.line'].search([('move_id','=',move_id.id),('account_id','=',payment_id.destination_account_id.id)],limit=1)
            print ('Checking ARAP--->',arap_id,arap_id2,payment_id.move_id,move_id)
            partial_id = None
            if payment_id.payment_type == 'inbound':
                partial_id = rec.create_partial_reconcile(amount_currency,amount,arap_id2,arap_id)
            else:
                partial_id = rec.create_partial_reconcile(amount_currency,amount,arap_id,arap_id2)
                        
            if rec.get_advance_balance() == 0.0:
                if payment_id.payment_type == 'inbound':        
                    partial_ids = self.env['account.partial.reconcile'].search([('credit_move_id','=',arap_id.id)]) 
                else:
                    partial_ids = self.env['account.partial.reconcile'].search([('debit_move_id','=',arap_id.id)])
                if not partial_ids:
                    raise ValidationError('Full Reconciliation Issue Occur.')
                full_reconcile_id = self.env['account.full.reconcile'].create({
                                'exchange_move_id': None,
                            })    
                for p in partial_ids:        
                    p.credit_move_id.full_reconcile_id = full_reconcile_id.id
                    p.debit_move_id.full_reconcile_id = full_reconcile_id.id
                    p.full_reconcile_id = full_reconcile_id.id
            res1 = res2 = []
            res1 = rec.prepare_move_line(debit_acc2,data_ary,amount,0.0,amount_currency)  
            res2 = rec.prepare_move_line(credit_acc2,data_ary,0.0,amount,amount_currency) 
            res = res1 + res2
            m_line = [(0, 0, l) for l in res]
            move_vals = {
                'journal_id': payment_id.journal_id.id,
                'ref': payment_id.move_id.name,
                'internal_ref': payment_id.seq_name,
                'date': rec.date,
                'line_ids': m_line,
                'payment_id': payment_id.id,
                'partner_id': payment_id.partner_id.id,
            }
            move_id = self.env['account.move'].create(move_vals)
            move_id._post()
            msg = 'Reconciliation Transfer: '+ str(move_id.name) + ' is created.'
            payment_id.message_post(body=msg)

    def prepare_move_line(self,account_id,data_ary,deb_amt,cred_amt,amount_currency):
        for rec in self:   
            res = []
            if cred_amt > 0:
                amount_currency = -1* amount_currency
            move_line = {
                'department_id': data_ary['department_id'],
                'description': data_ary['description'],
                'currency_id':data_ary['currency_id'],
                'exchange_rate': data_ary['exchange_rate'],
                'amount_currency':amount_currency,
                'debit': deb_amt,
                'credit': cred_amt,                
                'date_maturity': data_ary['date_maturity'],
                'name': data_ary['name'],
                'account_id': account_id,
                'partner_id': data_ary['partner_id'],
            }
            res.append(move_line)    
            return res   