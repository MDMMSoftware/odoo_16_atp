# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _,Command
from odoo.exceptions import ValidationError,UserError
from ...generate_code import generate_code
from datetime import datetime, timedelta, time
class AdvancePrepaid(models.Model):
    _name = "advance.prepaid"
    _inherit = "mail.thread"

    

    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(
            lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]

    department_id = fields.Many2one('res.department', string='Department', store=True,readonly=True,required=False,tracking=True,
                                help='Leave this field empty if this account is'
                                     ' shared between all departmentes')

    name = fields.Char(string="Name",copy=False)
    desc = fields.Text(string="Description",required=True)
    company_id = fields.Many2one('res.company',string="Company", required=True, default=lambda self: self.env.company)
    date = fields.Date(string='Date',required=True)
    prepare_amt = fields.Float("Prepare Amount",required=True)
    # virtual_amt = fields.Float("Virtual Amount",invisible=True)
    done_amt = fields.Float("Done Amount",readonly=True,copy=False)
    memo = fields.Char("Memo")
    payment_type = fields.Selection([
        ('outbound', 'Send'),
        ('inbound', 'Receive'),
    ], string='Payment Type', default='outbound', required=True, tracking=True)
    partner_bank_id = fields.Many2one('res.partner.bank', string="Recipient Bank Account",
        readonly=False, store=True, tracking=True,
        compute='_compute_partner_bank_id',
        domain="[('id', 'in', available_partner_bank_ids)]",
        check_company=True)
    available_partner_bank_ids = fields.Many2many(
        comodel_name='res.partner.bank',
        compute='_compute_available_partner_bank_ids',
    )
    contact_id = fields.Many2one('hr.employee',string="Contacts")
    state = fields.Selection([('draft','New'),
                              ('hod_approve','Waiting HOD Approve'),
                              ('check','Waiting Finance Check'),
                              ('finance_approve','Waiting Finance Approve'),
                              ('director_approve','Waiting Approval of Director'),
                              ('waiting_payment','Waiting Payment'),
                              ('paid','Paid'),
                              ('refuse','Refuse'),
                              ('close','Close')],string="State",default='draft',required=True,tracking=True)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency',related='company_id.currency_id', track_visibility='always')
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        readonly=True,
        tracking=True,
        states={'draft': [('readonly', False)]},required=True
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default =lambda self: self.env.company.currency_id.id,
        related='company_id.currency_id', store=True, readonly=False,
        help="The advance's currency.")
    need_of_dir_approve = fields.Boolean(default=False,string="Need of Director Approval")
    director_id = fields.Many2one('hr.employee',string="Director")
    branch_ids = fields.Many2one('res.branch', string='Branch', store=True,
                                readonly=False,domain=_get_branch_domain,required=False)
    payment_ids = fields.Many2many(
        'account.payment','prepaid_account_payment_rel','prepaid_id','payment_id',
        string='Paid Payments',readonly=True, ondelete='cascade',copy=False,
        check_company=True)
    payment_status = fields.Selection([('not_paid','Not Paid'),('partial','Partially Paid'),('paided','Paid')],string="Payment Status",default='not_paid',tracking=True)
    # is_recon = fields.Boolean(string="Is Reconciled?",compute="_check_reconciled_from_payments",store=False)
    is_reconciled = fields.Boolean(string="Is Reconciled?",store=True)
    internal_ref = fields.Char(string="Internal Reference")
    is_internal_transfer = fields.Boolean(string="Is Internal Transfer",
        readonly=False, store=True)    
    transfer_partner_id = fields.Many2one(
        'res.partner',
        string='Transfer Partner',
        readonly=True,
        tracking=True,
        states={'draft': [('readonly', False)]}
    )
    partner_account = fields.Many2one('account.account')
    transfer_partner_account = fields.Many2one('account.account')
    advance_account_id = fields.Many2one('account.account',string="Advance Account")
    transfer_move = fields.Many2many(
        'account.move','advance_prepaid_account_move_rel','prepaid_id','move_id',
        string='Paid Payments',readonly=True, ondelete='cascade',copy=False,
        check_company=True)
    partner_type = fields.Selection([
        ('advance','Advance'),
        ('customer','Customer'),
        ('vendor','Vendor'),
    ],string="Partner Type",default="advance") 
    fleet_id = fields.Many2one(comodel_name='fleet.vehicle', string="Fleet",domain=[("type", "=", "fleet")])   
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division",tracking=True)
    allow_division_feature = fields.Boolean(string="Use Division Feature?", related="company_id.allow_division_feature")

    @api.onchange('partner_id')
    def onchange_partner_account(self):
        if self.partner_id:
            if self.partner_id.partner_type == 'advance':
                self.partner_account = self.partner_id.property_account_advance_id and self.partner_id.property_account_advance_id.id or False
                self.advance_account_id = self.partner_id.property_account_advance_id and self.partner_id.property_account_advance_id.id or False
            elif self.partner_id.partner_type == 'vendor':
                self.partner_account = self.partner_id.property_account_payable_id and self.partner_id.property_account_payable_id.id or False
                self.advance_account_id = self.partner_id.advance_payable_id and self.partner_id.advance_payable_id.id or False   
            elif self.partner_id.partner_type == 'customer':
                self.partner_account = self.partner_id.property_account_receivable_id and self.partner_id.property_account_receivable_id.id or False
                self.advance_account_id = self.partner_id.advance_receivable_id and self.partner_id.advance_receivable_id.id or False
            else:
                self.advance_account_id = self.partner_id.advance_payable_id and self.partner_id.advance_payable_id.id or False            

    @api.onchange('transfer_partner_id')
    def onchange_transfer_partner_account(self):
        if self.transfer_partner_id:
            if self.transfer_partner_id.partner_type == 'advance':
                self.transfer_partner_account = self.transfer_partner_id.property_account_advance_id and self.transfer_partner_id.property_account_advance_id.id or False
            elif self.transfer_partner_id.partner_type == 'vendor':
                self.transfer_partner_account = self.transfer_partner_id.property_account_payable_id and self.transfer_partner_id.property_account_payable_id.id or False
            elif self.transfer_partner_id.partner_type == 'customer':
                self.transfer_partner_account = self.transfer_partner_id.property_account_receivable_id and self.transfer_partner_id.property_account_receivable_id.id or False

    @api.onchange('partner_type')
    def _onchage_partner_domain_by_type(self):
        self.partner_id = False
        return {"domain" : {"partner_id" : ['&',('partner_type', '=', self.partner_type),('company_id', '=', self.company_id.id)]}}   

    @api.onchange("branch_ids")
    def _onchange_branch_id(self):
        for res in self:
            if not res.branch_ids:
                prepaid_company = res.company_id if res.company_id else self.env.company
                branch_id = self.env.user.branch_id
                if not branch_id:
                    branch_ids = self.env.user.branch_ids
                    branch_id = branch_ids.filtered(lambda branch: branch.company_id == prepaid_company)
                res.branch_ids = branch_id and branch_id[0] or False            
    
    @api.depends('available_partner_bank_ids')
    def _compute_partner_bank_id(self):
        ''' The default partner_bank_id will be the first available on the partner. '''
        for pay in self:
            pay.partner_bank_id = pay.available_partner_bank_ids[:1]._origin


    @api.depends('partner_id', 'company_id', 'payment_type')
    def _compute_available_partner_bank_ids(self):
        for pay in self:
            
            pay.available_partner_bank_ids = pay.partner_id.bank_ids\
                .filtered(lambda x: x.company_id.id in (False, pay.company_id.id))._origin
            
    @api.constrains('prepare_amt')
    def constrains_prepare_adv_amount(self):
        for rec in self:
            if rec.prepare_amt <= 0:
                raise ValidationError('Invalid Prepare Amount')            

            
    def action_submit(self):
        if not self.name:
            name = False
            if not self.date:
                raise ValidationError(_("Please insert Date"))
            sequence = self.env['sequence.model']
            if self.is_internal_transfer:
                name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,'transfer',None)
            else:
                if self.payment_type=='inbound':
                    name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,'receive',None)
                elif self.payment_type=='outbound':
                    name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,'pay',None)
                else:
                    name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,None,None)
            if not name:
                raise ValidationError(_("Sequence Not Found.Please Contact to the Administrator."))
            self.write({'name':name})
        self.write({'state':'hod_approve'})

    def action_hod_approve(self):
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.write({'state':'check'})

    def action_check(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.write({'state':'finance_approve'})

    def action_reset_to_draft(self):
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.write({'state':'draft'})

    def action_refuse(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.write({'state':'refuse'})    


    def action_finance_approve(self):
        # if not (self.env.user.has_group('account.group_account_user') or self.env.user.has_group('account.group_account_manager')):
        #     raise UserError(_("Access Denied for Financial Rule"))
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        if self.need_of_dir_approve:
            self.write({'state':'director_approve'})
        else:
            self.write({'state':'waiting_payment'})

    def action_dir_approve(self):
        if not (self.need_of_dir_approve and self.director_id):
            raise ValidationError(_("Please add Director"))
        else:
            if not self.director_id.user_id:
                raise ValidationError(_("You need to add User in Employee's HR Setting"))
            else:
                if self.env.user != self.director_id.user_id:
                    raise ValidationError('Invalid Action.')
        self.write({'state':'waiting_payment'})

    def action_close(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.write({"state": 'close'})

    def action_wait_payment(self):
        self.ensure_one()
        if not (self.env.user.has_group('account.group_account_user') or self.env.user.has_group('account.group_account_manager')):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
            
        # advance_account_id = False
        # if self.partner_type == 'advance':
        #     advance_account_id = self.partner_id.property_account_advance_id and self.partner_id.property_account_advance_id.id or False
        # elif self.partner_type == 'customer':
        #     advance_account_id = self.partner_id.advance_receivable_id and self.partner_id.advance_receivable_id.id or False
        # else:
        #     advance_account_id = self.partner_id.advance_payable_id and self.partner_id.advance_payable_id.id or False
        for _ in self:
            return {
                'name':"Register Advance Prepayment",
                'view_mode': 'form',
                'view_id': self.env.ref('advance_expense.view_prepaid_register_advance').id,
                'view_type': 'form',
                'res_model': 'prepaid.register.advance',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': dict(
                                self.env.context, 
                                default_prepaid_id=self.id,
                                default_amount=self.prepare_amt-self.done_amt,
                                default_payment_type=self.payment_type,
                                default_is_transfer=self.is_internal_transfer,
                                default_advance_account_id=False if self.is_internal_transfer else self.advance_account_id.id,
                                default_journal_id = self.env.user.payment_journal_id.id,
                                group_by=False
                            ),                 
            }
        
    def action_print_advance(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename) + str(birt_suffix) + '.rptdesign&pp_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise ValidationError('Report Not Not Found')       

    def prepaid_advance(self,register_id):
        if self.done_amt+register_id.amount>self.prepare_amt:
            raise ValidationError(_("Amount Exceeded"))
        else:
            val_list = {
                'amount': register_id.amount,
                'date': register_id.date,
                'currency_id': self.currency_id and self.currency_id.id or False,
                'payment_type': self.is_internal_transfer and 'inbound' or self.payment_type,
                'partner_id':self.partner_id and self.partner_id.id or False,
                'ref':self.memo,
                'source_do':register_id.ref,
                'journal_id':register_id.journal_id and register_id.journal_id.id or False,
                'advance_account_id':register_id.advance_account_id.id,
                'desc':self.desc,
                'branch_id':self.branch_ids.id,
                'department_id':self.department_id.id,
                'transfer_partner_id':self.transfer_partner_id and self.transfer_partner_id.id or False,
                'partner_account':self.partner_account and self.partner_account.id or False,
                'transfer_partner_account':self.transfer_partner_account and self.transfer_partner_account.id or False,
                'is_transfer':self.is_internal_transfer,
                'division_id':self.division_id.id or False,
                'department_id':self.department_id.id or False,
                'is_internal_transfer':False #Don't Delete this Parameter....
            }
            if hasattr(self, 'project_id'):
                val_list['project_id'] = self.project_id.id or False
            payment = self.env['account.payment'].create(val_list)
            
            payment.action_post()
            payment.ref = self.memo
            payment.move_id.write({'internal_ref':self.name, 'ref': payment.seq_name})
            for move_line in payment.move_id.line_ids:
                move_line.write({'name':self.desc,'job_code_id':register_id.job_code_id.id})
            
            self.payment_ids = [[6,0,self.payment_ids.ids+payment.ids]]
            if self.is_internal_transfer:
                analytic_distribution_dct = {}
                if self.fleet_id and self.fleet_id.analytic_fleet_id and  self.company_id == self.fleet_id.company_id:
                    analytic_distribution_dct = {self.fleet_id.analytic_fleet_id.id:100}
                invoice_line_dct = {
                                'name': self.desc,
                                'price_unit': register_id.amount,
                                'account_id': register_id.advance_account_id.id,
                                'fleet_id': self.fleet_id.id,
                                'analytic_distribution': analytic_distribution_dct,
                                'division_id': self.division_id.id or False,
                            }
                if hasattr(self, 'project_id'):
                    invoice_line_dct['project_id'] = self.project_id.id or False
                    if self.project_id.analytic_project_id:
                        analytic_distribution_dct[str(self.project_id.analytic_project_id.id)] = 100
                if self.division_id and self.division_id.analytic_account_id:
                    analytic_distribution_dct[str(self.division_id.analytic_account_id.id)] = 100
                move = self.env['account.move'].create({
                    'invoice_date':register_id.date,
                    'move_type': 'in_refund',
                    'partner_id': self.transfer_partner_id.id,
                    'journal_id':register_id.bill_journal_id and register_id.bill_journal_id.id or False,
                    'date':register_id.date,
                    'invoice_date_due':register_id.date,
                    'department_id': self.department_id.id or False,
                    'invoice_line_ids': [
                        Command.create(invoice_line_dct)
                        ]
                })
                line = move.line_ids.filtered(lambda x:x.account_id.account_type not in ['asset_receivable','liability_payable'] )
                if line:
                    line.update({'account_id':register_id.advance_account_id.id})
                # transfer_line = move.line_ids.filtered(lambda x:x.account_id.account_type in ['asset_receivable','liability_payable'] )
                # if transfer_line:
                #     transfer_line.update({'account_id':self.transfer_partner_account.id})
                move.action_post()
                self.transfer_move = [[6,0,self.transfer_move.ids+move.ids]]
            # self.write({'done_amt':self.done_amt+register_id.amount})
            
        return payment.ids
    
    def action_open_payments(self):
        return {
            'name': _('Advance Payments'),
            'view_mode': 'tree,form',
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.payment_ids.ids)],              
        } 

    def action_open_transfer_moves(self):
        return {
            'name': _('Advance Transfer Moves'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.transfer_move.ids)],              
        } 
    
    def unlink(self):
        for rec in self:
            if rec.state != 'draft' or rec.name:
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        super().unlink()

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    source_do = fields.Char('Source Document')
    prepaid_id = fields.Many2one('advance.prepaid',readonly=True)
    advance_account_id = fields.Many2one('account.account',string="Advance Account",domain="[('company_id', '=', company_id),('account_type', 'in', ('asset_receivable','liability_payable')),('non_trade','=',True)]")
    partner_account = fields.Many2one('account.account',string="Partner Account")
    transfer_partner_account = fields.Many2one('account.account',string="Partner Account")
    desc = fields.Char("Description",readonly=False,store=True)
    transfer_partner_id = fields.Many2one(
        'res.partner',
        string='Transfer Partner',
        readonly=True,
        tracking=True,
        states={'draft': [('readonly', False)]}
    )
    is_transfer = fields.Boolean(string="Is Internal Transfer",
        readonly=False, store=True)   
    # description = fields.Char("Description") 
    x_state = fields.Selection([('draft','New'),
                            ('check','Waiting Finance Check'),
                            ('finance_approve','Waiting Finance Approve'),
                            ('director_approve','Waiting Approval of Director'),
                            ('waiting_payment','Waiting Payment'),
                            ('paid','Paid'),
                            ('refuse','Refuse'),
                            ('cancel','Cancelled')],string="State",default='draft',required=True,tracking=True,copy=False)
    bank_reference = fields.Char("Bank Reference")
    cheque_reference = fields.Char("Cheque Reference")
    acc_holder_name = fields.Char('Account Holder Name',copy=False)
    bank_id = fields.Many2one('res.bank',string="Bank Name")
    seq_name = fields.Char("Sequence Name",copy=False)
    need_of_dir_approve = fields.Boolean(default=False,string="Need of Director Approval")
    director_id = fields.Many2one('hr.employee',string="Director")
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division",tracking=True)
    allow_division_feature = fields.Boolean(string="Use Division Feature?", related="company_id.allow_division_feature")
    advance_user_ids = fields.Many2many('res.partner', 'advance_users_rel',
                                compute='_compute_advance_user_ids')
    
    def _compute_advance_user_ids(self):
        for record in self:
            record.advance_user_ids = self.env['res.partner'].search([('partner_type','=','advance')]).ids

    # def _prepare_move_line_default_vals(self, write_off_line_vals=None):
    #     res = super(AccountPayment,self)._prepare_move_line_default_vals(write_off_line_vals=None)

    #     for line in res:
    #         account = self.env['account.account'].browse(line['account_id'])
    #         if self.is_transfer:
    #             if account.account_type not in ['asset_receivable','liability_payable'] and self.advance_account_id:
    #                 line.update({'account_id':self.advance_account_id.id})
    #         else:
    #             if account.account_type in ['asset_receivable','liability_payable'] and self.advance_account_id:
    #                 line.update({'account_id':self.advance_account_id.id})

    #     return res
    
    def _get_valid_liquidity_accounts(self):
        if self.is_transfer:
            return (
                self.journal_id.default_account_id |
                self.payment_method_line_id.payment_account_id |
                self.journal_id.company_id.account_journal_payment_debit_account_id |
                self.journal_id.company_id.account_journal_payment_credit_account_id |
                self.journal_id.inbound_payment_method_line_ids.payment_account_id |
                self.journal_id.outbound_payment_method_line_ids.payment_account_id |
                self.advance_account_id
            )
        else:
            return (
                self.journal_id.default_account_id |
                self.payment_method_line_id.payment_account_id |
                self.journal_id.company_id.account_journal_payment_debit_account_id |
                self.journal_id.company_id.account_journal_payment_credit_account_id |
                self.journal_id.inbound_payment_method_line_ids.payment_account_id |
                self.journal_id.outbound_payment_method_line_ids.payment_account_id 
            )
        
    @api.depends('move_id.line_ids.amount_residual', 'move_id.line_ids.amount_residual_currency', 'move_id.line_ids.account_id')
    def _compute_reconciliation_status(self):
        ''' Compute the field indicating if the payments are already reconciled with something.
        This field is used for display purpose (e.g. display the 'reconcile' button redirecting to the reconciliation
        widget).
        '''
        for pay in self:
            liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

            if not pay.currency_id or not pay.id:
                pay.is_reconciled = False
                pay.is_matched = False
            elif pay.currency_id.is_zero(pay.amount):
                pay.is_reconciled = True
                pay.is_matched = True
            else:
                residual_field = 'amount_residual' if pay.currency_id == pay.company_id.currency_id else 'amount_residual_currency'
                if pay.journal_id.default_account_id and pay.journal_id.default_account_id in liquidity_lines.account_id:
                    # Allow user managing payments without any statement lines by using the bank account directly.
                    # In that case, the user manages transactions only using the register payment wizard.
                    pay.is_matched = True
                else:
                    pay.is_matched = pay.currency_id.is_zero(sum(liquidity_lines.mapped(residual_field)))

                reconcile_lines = (counterpart_lines + writeoff_lines).filtered(lambda line: line.account_id.reconcile)
                pay.is_reconciled = pay.currency_id.is_zero(sum(reconcile_lines.mapped(residual_field)))

                if pay.is_reconciled:
                    if pay.prepaid_id:
                        all_payments = self.env['account.payment'].search([('prepaid_id','=',pay.prepaid_id.id),('state','!=','cancel')])
                        pay.prepaid_id.is_reconciled = all( [data.is_reconciled for data in all_payments] ) if all_payments else False

    @api.onchange("branch_id")
    def _onchange_branch_id(self):
        for res in self:
            if not res.branch_id:
                user_obj = self.env.user
                res.branch_id = user_obj.branch_id
                res.journal_id = user_obj.payment_journal_id

    def action_post(self):
        if self.prepaid_id:
            payments = self.search([('prepaid_id','=',self.prepaid_id.id),('state','=','posted')])
            if sum(payments.mapped('amount'))+self.amount>self.prepaid_id.prepare_amt:
                raise ValidationError(_("Amount is exceeded for Prepaid's Residual Amount"))
            else:
                self.prepaid_id.done_amt = self.prepaid_id.done_amt + self.amount
        if self.v_prepaid_id:
            payments = self.search([('v_prepaid_id', '=', self.v_prepaid_id.id), ('state', '=', 'posted')])
            if sum(payments.mapped('amount')) + self.amount > self.v_prepaid_id.prepare_amount:
                raise ValidationError(_("Amount is exceeded for Prepaid's Residual Amount"))
            else:
                self.v_prepaid_id.amount = self.v_prepaid_id.amount + self.amount

        res = super().action_post()
        for val in self:
            val.write({"x_state":'paid'})
            if not val.seq_name:
                sequence = self.env['sequence.model']
                if val.payment_type=='inbound':
                    val.seq_name = generate_code.generate_code(sequence,val,val.branch_id,val.company_id,val.date,'receive',None)
                elif val.payment_type=='outbound':
                    val.seq_name = generate_code.generate_code(sequence,val,val.branch_id,val.company_id,val.date,'pay',None)
                else:
                    val.seq_name = generate_code.generate_code(sequence,val,val.branch_id,val.company_id,val.date,None,None)
            

            if self.prepaid_id:
                val.move_id.write({'internal_ref':val.prepaid_id.name})
                self.write({'ref':self.prepaid_id.name})
            elif self.v_prepaid_id:
                val.move_id.write({'internal_ref':val.prepaid_id.name})
                self.write({'ref':self.v_prepaid_id.name})            
            if val.move_id:
                analytic_distribution_dct = {}
                if hasattr(val, 'project_id'):
                    if val.project_id.analytic_project_id:
                        analytic_distribution_dct[str(val.project_id.analytic_project_id.id)] = 100
                if self.division_id and self.division_id.analytic_account_id:
                    analytic_distribution_dct[str(val.division_id.analytic_account_id.id)] = 100
                for line in val.move_id.line_ids:
                    if hasattr(line, 'project_id') and val.project_id:
                        line.project_id = val.project_id
                    if val.division_id:
                        line.division_id = val.division_id
                    line.analytic_distribution = analytic_distribution_dct if analytic_distribution_dct else line.analytic_distribution
                val.move_id.write({
                                    'ref':val.move_id.ref,
                                    'department_id':val.department_id.id or False,
                                })
        
    def name_get(self):
        return [(rec.id,rec.seq_name) for rec in self]
    
    def action_draft(self):
        self.x_state = 'draft'
        # res = super().action_draft()
        # if self.prepaid_id:
        #     self.prepaid_id.state = 'waiting_payment'
        #     self.prepaid_id.done_amt = self.prepaid_id.done_amt-self.amount
        #     if self.prepaid_id.done_amt > 0:
        #         self.prepaid_id.payment_status = 'partial'
        #     else:
        #         self.prepaid_id.payment_status = 'not_paid'
        

    def action_change_status(self):
        to_status = self._context.get('to_status',None)
        if to_status=='finance_approve' or to_status=='director_approve' or to_status=='refuse' or to_status=='cancel':
            if not self.env.user.has_group('account.group_account_manager'):
                raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
            if self.department_id:
                if self.env.user.id not in self.department_id.approve_user_id.ids:
                    raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        if to_status=='draft' or to_status=='check':
            if self.department_id:
                if self.env.user.id not in self.department_id.approve_user_id.ids:
                    raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        if not to_status:
            raise ValidationError("Unknown status found!!!")
        if to_status == 'check':
            for val in self:
                if not val.seq_name:
                    sequence = self.env['sequence.model']
                    if val.payment_type=='inbound':
                        val.seq_name = generate_code.generate_code(sequence,val,val.branch_id,val.company_id,val.date,'receive',None)
                    elif val.payment_type=='outbound':
                        val.seq_name = generate_code.generate_code(sequence,val,val.branch_id,val.company_id,val.date,'pay',None)
                    else:
                        val.seq_name = generate_code.generate_code(sequence,val,val.branch_id,val.company_id,val.date,None,None)
        elif to_status == 'director_approve':
            if not self.need_of_dir_approve:
                to_status = 'waiting_payment'
        elif to_status == 'waiting_payment':
            if ( self.director_id ) and ( self.director_id.user_id != self.env.user ):
                raise ValidationError('Invalid Action.You have no access to approve except Director.')
        elif to_status == 'paid':
            self.action_post()
            for val in self:
                if val.move_id:
                    val.move_id.write({'ref':val.seq_name})
        elif to_status == 'refuse':
            for move in self.move_id:
                if move.state == 'draft':
                    move.button_cancel()                    
        elif to_status == 'cancel':
            for move in self.move_id:
                if move.state == 'posted':
                    move.button_draft()
                if move.state != 'cancel':
                    move.button_cancel()
            if self.prepaid_id:
                self.prepaid_id.done_amt -= self.amount
                self.prepaid_id.write({'state':'waiting_payment'})
            if hasattr(self, 'v_prepaid_id') and self.v_prepaid_id:
                self.v_prepaid_id.amount -= self.amount
                self.v_prepaid_id.write({'state':'waiting_payment'})
        self.write({'x_state': to_status})
    
    def unlink(self):
        for rec in self:
            if rec.x_state != 'draft' or rec.seq_name:
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()


# class AccountPaymentMethod(models.Model):
#     _inherit = "account.payment.method"


#     @api.model
#     def _get_payment_method_information(self):
#         """
#         Contains details about how to initialize a payment method with the code x.
#         The contained info are:
#             mode: Either unique if we only want one of them at a single time (payment providers for example)
#                    or multi if we want the method on each journal fitting the domain.
#             domain: The domain defining the eligible journals.
#             currency_id: The id of the currency necessary on the journal (or company) for it to be eligible.
#             country_id: The id of the country needed on the company for it to be eligible.
#             hidden: If set to true, the method will not be automatically added to the journal,
#                     and will not be selectable by the user.
#         """
#         return {
#             'manual': {'mode': 'multi', 'domain': [('type', 'in', ('bank', 'cash','general'))]},
#         }