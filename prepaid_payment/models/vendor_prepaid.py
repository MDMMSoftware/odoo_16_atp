# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ...generate_code import generate_code


class AccountPaymentPrepaid(models.Model):
    _name = "account.payment.prepaid"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Pre-Payments"
    _order = "date desc, name desc"


    def _get_default_journal(self):
        ''' Retrieve the default journal for the account.payment.
        /!\ This method will not override the method in 'account.move' because the ORM
        doesn't allow overriding methods using _inherits. Then, this method will be called
        manually in 'create' and 'new'.
        :return: An account.journal record.
        '''
        return self.env['account.move']._search_default_journal()
        # return self.env['account.move']._search_default_journal(('bank', 'cash'))
    
    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        if hasattr(self.env.user, 'branch_ids'):
            branch_ids = self.env.user.branch_ids
            branch = branch_ids.filtered(
                lambda branch: branch.company_id == company)
            return [('id', 'in', branch.ids)]
        return []
    
    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(
            lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]

    department_id = fields.Many2one('res.department', string='Department', store=True,required=False,tracking=True,
                                readonly=True,
                                help='Leave this field empty if this account is'
                                     ' shared between all departmentes')

    check_amount_in_words = fields.Char(
        string="Amount in Words",
        store=True,
        compute='_compute_check_amount_in_words',
    )
    seq_no = fields.Char('Seq',copy=False)
    name =  fields.Char('')
    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 store=True, readonly=True,
                                 compute='_compute_company_id') 
    ref = fields.Char(string='Reference', copy=False, tracking=True)
    state = fields.Selection([
                                ('draft','New'),
                                ('check','Waiting Finance Check'),
                                ('finance_approve','Waiting Finance Approve'),
                                ('director_approve','Waiting Approval of Director'),
                                ('waiting_payment','Waiting Payment'),
                                ('paid','Paid'),
                                ('refuse','Refuse'),
                                ('cancel','Cancelled'),
                                ('close', 'Close'),
                            ],string="State",default='draft',required=True,tracking=True,copy=False)
    date = fields.Date(
        string='Date',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        copy=False,
        default=fields.Date.context_today
    )

    journal_id = fields.Many2one('account.journal', string='Journal', required=True, readonly=True,
        states={'draft': [('readonly', False)]},
        default=_get_default_journal)

    payment_type = fields.Selection([
        ('outbound', 'Send Money'),
        ('inbound', 'Receive Money'),
    ], string='Payment Type', default='inbound', required=True)
    is_internal_transfer = fields.Boolean(string="Is Internal Transfer",
        readonly=False, store=True,
        compute="_compute_is_internal_transfer")    
    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
    ], default='customer', tracking=True, required=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer/Vendor",
        store=True, readonly=False, ondelete='restrict',
        compute='_compute_partner_id',
        domain="['|', ('parent_id','=', False), ('is_company','=', True)]",
        check_company=True)
    
    destination_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Destination Account',
        store=True, readonly=False,
        compute=None,
        domain="[('account_type', 'in', ('asset_receivable', 'liability_payable')), ('company_id', '=', company_id)]",
        check_company=True)
    
    prepare_amount = fields.Float('Prepare Amount',track_visibility='onchange')
    amount = fields.Float('Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', store=True, readonly=False,
        compute='_compute_currency_id',
        help="The payment's currency.")
    exchange_rate = fields.Float('Exchange Rate',default=1.0)
    # advance_date = fields.Date('Advance Date')
    bank_reference = fields.Char()
    cheque_reference = fields.Char()
    acc_holder_name = fields.Char('Account Holder Name')
    bank_id = fields.Many2one('res.bank',string="Bank Name")
    amount = fields.Monetary(currency_field='currency_id') 

    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method',
        readonly=False, store=True, copy=False,
        compute='_compute_payment_method_line_id',
        domain="[('id', 'in', available_payment_method_line_ids)]",
        help="Manual: Pay or Get paid by any method outside of Odoo.\n"
        "Payment Providers: Each payment provider has its own Payment Method. Request a transaction on/to a card thanks to a payment token saved by the partner when buying or subscribing online.\n"
        "Check: Pay bills by check and print it from Odoo.\n"
        "Batch Deposit: Collect several customer checks at once generating and submitting a batch deposit to your bank. Module account_batch_payment is necessary.\n"
        "SEPA Credit Transfer: Pay in the SEPA zone by submitting a SEPA Credit Transfer file to your bank. Module account_sepa is necessary.\n"
        "SEPA Direct Debit: Get paid in the SEPA zone thanks to a mandate your partner will have granted to you. Module account_sepa is necessary.\n")
    available_payment_method_line_ids = fields.Many2many('account.payment.method.line',
        compute='_compute_payment_method_line_fields')
    payment_method_id = fields.Many2one(
        related='payment_method_line_id.payment_method_id',
        string="Method",
        tracking=True,
        store=True
    )
    available_journal_ids = fields.Many2many(
        comodel_name='account.journal',
        compute='_compute_available_journal_ids'
    )
    
    desc = fields.Text('Description')
    
    note = fields.Text('Note')
    move_ids = fields.Many2many(
        'account.move','prepaid_account_move_rel','prepaid_id','move_id',
        string='Journal Entries',readonly=True, ondelete='cascade',copy=False,
        check_company=True)
    
    payment_ids = fields.Many2many(
        'account.payment','vendor_prepaid_account_payment_rel','vendor_prepaid_id','payment_id',
        string='Paid Payments',readonly=True, ondelete='cascade',copy=False,
        check_company=True)
    
    need_of_director_approve = fields.Boolean('Need of Director Approval ?',copy=False)
    director = fields.Many2one('hr.employee',string='Director',copy=False)
    branch_ids = fields.Many2one('res.branch', string='Branch', store=True,readonly=False,domain=_get_branch_domain,required=False)
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")
    allow_division_feature = fields.Boolean(string="Use Division Feature?", related="company_id.allow_division_feature")

    ## Deprecated fields from Odoo 14
    # unit_id = fields.Many2one('res.company',string="Business Unit",required=True)
    # analytic_company_id = fields.Many2one('analytic.company',string="Company",required=True)
    # department_id = fields.Many2one('analytic.department',string="Department")
    # shop_id = fields.Many2one('analytic.shop',string="Shop")
    # segment_id = fields.Many2one('analytic.segment',string="Segment")
    # channel_id = fields.Many2one('analytic.channel',string="Channel")
    # discount_amt = fields.Float('Discount Rate')
    # discount_account_id = fields.Many2one('account.account','Discount Account',domain=['|',('is_discount', '=', True),('is_line_discount', '=', True)])
    # discount_note = fields.Char('Discount Note.')
    # other_id = fields.Many2one('analytic.other',string="Folio")  
    # ref_person = fields.Many2one('reference.person',string='Ref Person')  
    


    @api.depends('payment_method_id', 'currency_id', 'prepare_amount')
    def _compute_check_amount_in_words(self):
        for pay in self:
            if pay.currency_id:
                pay.check_amount_in_words = pay.currency_id.amount_to_text(pay.prepare_amount)
            else:
                pay.check_amount_in_words = False

    @api.depends('journal_id')
    def _compute_company_id(self):
        for move in self:
            move.company_id = move.journal_id.company_id or move.company_id or self.env.company
            
    @api.depends('available_payment_method_line_ids')
    def _compute_payment_method_line_id(self):
        ''' Compute the 'payment_method_line_id' field.
        This field is not computed in '_compute_payment_method_line_fields' because it's a stored editable one.
        '''
        for pay in self:
            available_payment_method_lines = pay.available_payment_method_line_ids

            # Select the first available one by default.
            if pay.payment_method_line_id in available_payment_method_lines:
                pay.payment_method_line_id = pay.payment_method_line_id
            elif available_payment_method_lines:
                pay.payment_method_line_id = available_payment_method_lines[0]._origin
            else:
                pay.payment_method_line_id = False

    @api.depends('payment_type', 'journal_id', 'currency_id')
    def _compute_payment_method_line_fields(self):
        for pay in self:
            pay.available_payment_method_line_ids = pay.journal_id._get_available_payment_method_lines(pay.payment_type)
            to_exclude = pay._get_payment_method_codes_to_exclude()
            if to_exclude:
                pay.available_payment_method_line_ids = pay.available_payment_method_line_ids.filtered(lambda x: x.code not in to_exclude)

    @api.depends('payment_type')
    def _compute_available_journal_ids(self):
        """
        Get all journals having at least one payment method for inbound/outbound depending on the payment_type.
        """
        journals = self.env['account.journal'].search([
            ('company_id', 'in', self.company_id.ids), ('type', 'in', ('bank', 'cash'))
        ])
        for pay in self:
            if pay.payment_type == 'inbound':
                pay.available_journal_ids = journals.filtered(
                    lambda j: j.company_id == pay.company_id and j.inbound_payment_method_line_ids.ids != []
                )
            else:
                pay.available_journal_ids = journals.filtered(
                    lambda j: j.company_id == pay.company_id and j.outbound_payment_method_line_ids.ids != []
                )                                            


    @api.depends('journal_id')
    def _compute_currency_id(self):
        for pay in self:
            pay.currency_id = pay.journal_id.currency_id or pay.journal_id.company_id.currency_id
    
    @api.depends('partner_id', 'destination_account_id', 'journal_id')
    def _compute_is_internal_transfer(self):
        for payment in self:
            is_partner_ok = payment.partner_id == payment.journal_id.company_id.partner_id
            is_account_ok = payment.destination_account_id and payment.destination_account_id == payment.journal_id.company_id.transfer_account_id
            payment.is_internal_transfer = is_partner_ok and is_account_ok

    @api.depends('is_internal_transfer')
    def _compute_partner_id(self):
        for pay in self:
            if pay.is_internal_transfer:
                pay.partner_id = pay.journal_id.company_id.partner_id
            elif pay.partner_id == pay.journal_id.company_id.partner_id:
                pay.partner_id = False
            else:
                pay.partner_id = pay.partner_id


    @api.onchange("partner_id")
    def _onchange_destination_by_partner(self):
        for pay in self:
            if pay.partner_id:
                pay.destination_account_id = pay.partner_id.with_company(pay.company_id).property_account_receivable_id if pay.partner_type == 'customer' else pay.partner_id.with_company(pay.company_id).property_account_payable_id                
          
    @api.onchange("partner_id")
    def _onchange_destination_by_partner(self):
        for pay in self:
            if pay.partner_id:
                pay.destination_account_id = pay.partner_id.with_company(pay.company_id).property_account_receivable_id if pay.partner_type == 'customer' else pay.partner_id.with_company(pay.company_id).property_account_payable_id   

    @api.onchange("branch_ids")
    def _onchange_branch_ids(self):
        for res in self:
            if not res.branch_ids:
                res.branch_ids = self.env.user.branch_id             

    def _get_payment_method_codes_to_exclude(self):
        # can be overriden to exclude payment methods based on the payment characteristics
        self.ensure_one()
        return []                    

    def action_payment(self):
        if not (self.env.user.has_group('account.group_account_user') or self.env.user.has_group('account.group_account_manager')):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.ensure_one()
        view_id = self.env['ir.model.data']._xmlid_to_res_id('prepaid_payment.view_prepaid_register_payment')
        for _ in self:
            return {
                'name':"Register Vendor Prepayment",
                'view_mode': 'form',
                'view_id': view_id,
                'view_type': 'form',
                'res_model': 'prepaid.register.payment',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': dict(self.env.context, default_prepaid_id=self.id,default_amount=self.prepare_amount-self.amount,group_by=False),                 
            }

    def action_submit(self):
        for rec in self:
            if rec.prepare_amount <= 0.0:
                raise ValidationError("Prepare amount must be greate than zero !")
            if not rec.seq_no:
                sequence = self.env['sequence.model']
                if self.payment_type=='inbound':
                    rec.name = rec.seq_no = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,'receive',None)
                elif self.payment_type=='outbound':
                    rec.name = rec.seq_no = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,'pay',None)
                else:
                    rec.name = rec.seq_no = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,None,None)
            rec.write({'state': 'check'})  

    def action_cancel(self):
        for rec in self:
            if rec.amount>0:
                raise ValidationError(_("You can't cancel partially done transaction."))
            rec.write({'state': 'cancel'})             

    def action_finance_officer_approve(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        for rec in self:
            rec.write({'state': 'finance_approve'})
        
    def action_bod_mng_approve(self):
        if self.director.user_id != self.env.user:
            raise ValidationError('Invalid Action.You have no access to approve except Director.')
        self.write({'state': 'waiting_payment'})

    def action_finance_mng_approve(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        if self.need_of_director_approve:
            if not self.director:
                raise ValidationError('Director must not be blank.')
            self.write({'state':'director_approve'})
        else:
            self.write({'state': 'waiting_payment'}) 

    def action_refuse(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.write({'state':'refuse'})   

    def action_close(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(("User %s doesn't get Financial Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.write({'state':'close'})  

    def name_get(self):
        return [(rec.id,rec.seq_no) for rec in self]       

    def prepaid_vendor_payment(self,register_id):
        if self.amount+register_id.amount>self.prepare_amount:
            raise ValidationError(_("Amount Exceeded"))
        else:
            val_list = {
                'amount': register_id.amount,
                'date': register_id.date,
                'currency_id': self.currency_id and self.currency_id.id or False,
                'payment_type': self.payment_type,
                'partner_type': self.partner_type,
                'partner_id':self.partner_id and self.partner_id.id or False,
                'destination_account_id':self.destination_account_id and self.destination_account_id.id or False,
                'exchange_rate':self.exchange_rate,
                'bank_reference':self.bank_reference,
                'cheque_reference':self.cheque_reference,
                'acc_holder_name':self.acc_holder_name,
                'bank_id':self.bank_id and self.bank_id.id or False,
                'ref':register_id.ref,
                'journal_id':self.journal_id and self.journal_id.id or False,
                'payment_method_id':self.payment_method_id and self.payment_method_id.id or False,
                'desc':self.desc,
                'journal_id':self.journal_id and self.journal_id.id or False,
                'payment_method_line_id':self.payment_method_line_id and self.payment_method_line_id.id or False,
                'prepaid_id':None,
                'v_prepaid_id':self.id,
                'need_of_dir_approve':self.need_of_director_approve,
                'director_id':self.director and self.director.id or False,
                'branch_id':self.branch_ids and self.branch_ids.id or False,
                'division_id':self.division_id and self.division_id.id or False,
                'department_id':self.department_id and self.department_id.id or False,
                # 'advance_date':self.advance_date,
                # 'note':self.note,
                # 'discount_amt':self.discount_amt,
                # 'discount_account_id':self.discount_account_id and self.discount_account_id.id or False,
                # 'discount_note':self.discount_note,

                # 'unit_id':self.unit_id and self.unit_id.id or False,
                # 'analytic_company_id':self.analytic_company_id and self.analytic_company_id.id or False,
                # 'department_id':self.department_id and self.department_id.id or False,
                # 'shop_id':self.shop_id and self.shop_id.id or False,
                # 'segment_id':self.segment_id and self.segment_id.id or False,
                # 'channel_id':self.channel_id and self.channel_id.id or False,
                # 'other_id':self.other_id and self.other_id.id or False,
                # 'ref_person':self.ref_person and self.ref_person.id or False,
            }
            if hasattr(self, 'project_id'):
                val_list['project_id'] = self.project_id and self.project_id.id or False
            payment = self.env['account.payment'].create(val_list)
            payment.action_post()
            
            self.move_ids = [[6,0,self.move_ids.ids+payment.move_id.ids]]
            self.payment_ids = [[6,0,self.payment_ids.ids+payment.ids]]
            
        return payment.ids,payment.move_id.ids
    
    def unlink(self):
        for rec in self:
            if rec.state != 'draft' or rec.seq_no:
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()
    
    def action_open_payments(self):
        return {
            'name': _('Vendor Payments'),
            'view_mode': 'tree,form',
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.payment_ids.ids)],              
        } 
    
    def action_open_moves(self):
        return {
            'name': _('Journal Entry'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.move_ids.ids)],              
        }
    
    def action_print_prepaidment(self):
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
        
class AccountPayment(models.Model):
    _inherit = 'account.payment'

    v_prepaid_id = fields.Many2one('account.payment.prepaid',readonly=True,string="Vendor Prepaid")        
