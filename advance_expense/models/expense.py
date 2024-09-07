# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from odoo import api, fields, models, tools, _,Command
from ...generate_code import generate_code
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from textwrap import shorten
from odoo.tools import (
    float_compare,
    format_date,
    formatLang,
    get_lang
)
from odoo.tools import float_is_zero
from collections import Counter

class AccountMove(models.Model):
    _inherit = 'account.move'
    

    is_expense = fields.Boolean(string="Is Expense",default=False,store=True)
    expense_type = fields.Selection([('advance_claim','Advance Claim'),('dir_exp','Direct Expenses')],string="Expense Type")
    contact_id = fields.Many2one('hr.employee',string="Contacts")
    # source_do = fields.Char('Source Document')
    journal_account = fields.Many2one('account.account')
    x_state = fields.Selection([('draft','New'),
                              ('hod_approve','Waiting HOD Approve'),
                              ('check','Waiting Finance Check'),
                              ('finance_approve','Waiting Finance Approve'),
                              ('director_approve','Waiting Approval of Director'),
                              ('waiting_payment','Waiting Payment'),
                              ('paid','Paid'),
                              ('refuse','Refuse'),
                              ('cancel','Cancelled')],string="State",default='draft',required=True,tracking=True,copy=False)
    need_of_dir_approve = fields.Boolean(default=False,string="Need of Director Approval")
    director_id = fields.Many2one('hr.employee',string="Director")    
    desc = fields.Char(string="Description")
    internal_ref = fields.Char(string="Internal Reference", copy=False)
    term_type = fields.Selection([('direct','Cash Sales'),('credit','Credit Sales')],string='Payment Type',default='credit')
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")

    @api.constrains('journal_id', 'move_type')
    def _check_journal_move_type(self):
        for move in self:
            if move.is_purchase_document(include_receipts=True) and move.journal_id.type != 'purchase' and move.is_expense==False:
                raise ValidationError(_("Cannot create a purchase document in a non purchase journal"))
            if move.is_sale_document(include_receipts=True) and move.journal_id.type != 'sale' and move.is_expense==False:
                raise ValidationError(_("Cannot create a sale document in a non sale journal"))
            
    @api.constrains('invoice_line_ids')
    def _auto_copy_and_fill_project_fleet_analytic(self):
        if self.line_ids:
            invoice_line_with_analytic = False
            invoice_lines_without_analytic = []
            if hasattr(self.line_ids, 'project_id'):
                invoice_line_with_analytic = self.line_ids.search([('move_id','=',self.id),('project_id','!=',False)],limit=1)
                # adding default analytic of journal and project and fleet to first line
                default_analytic_from_journals = self.journal_id.default_analytic_account_ids
                if not invoice_line_with_analytic and default_analytic_from_journals:
                    first_line = self.line_ids[0]
                    analytic_dct = {}
                    for analytic_account in default_analytic_from_journals:
                        analytic_dct[analytic_account.id] = 100
                        if hasattr(analytic_account, 'project_id') and analytic_account.project_id:
                            first_line.project_id = analytic_account.project_id.id
                        if hasattr(analytic_account, 'fleet_id') and analytic_account.fleet_id:
                            first_line.fleet_id = analytic_account.fleet_id.id 
                        if hasattr(analytic_account, 'division_id') and analytic_account.division_id:
                            first_line.division_id = analytic_account.division_id.id 
                    first_line.analytic_distribution = analytic_dct
                    invoice_line_with_analytic = first_line
                ## raise validation even if there are no default analytic
                if self.line_ids and not invoice_line_with_analytic:
                    raise UserError("At least one project is required!!")
                invoice_lines_without_analytic = self.invoice_line_ids.filtered(lambda x:not x.project_id)
            elif hasattr(self.line_ids, 'fleet_id'):
                invoice_line_with_analytic = self.line_ids.search([('move_id','=',self.id),('fleet_id','!=',False)],limit=1)
                if not invoice_lines_without_analytic:
                    invoice_lines_without_analytic = self.invoice_line_ids.filtered(lambda x:not x.fleet_id)
            if self.partner_id and self.partner_id.partner_type == 'vendor' and self.partner_id.is_duty_owner:
                for line in invoice_lines_without_analytic:
                    if hasattr(line, 'project_id'):
                        line.project_id = invoice_line_with_analytic.project_id.id
                    if hasattr(line, 'fleet_id'):
                        line.fleet_id = invoice_line_with_analytic.fleet_id.id
                    line.analytic_distribution = invoice_line_with_analytic.analytic_distribution
            
    @api.onchange('partner_id')
    def _oncheck_domain(self):
        if self.expense_type == 'advance_claim':
            return {"domain" : {'partner_id' : [('advance_user','=',True)]}}
            
    @api.onchange('expense_type')
    def _onchange_expense_type(self):
        for m in self:
            if not m.branch_id:
                m.branch_id = self.env.user.branch_id            
            if m.expense_type=='advance_claim':
                # journal = self.env['account.journal'].search([('type','=','general')],limit=1)
                # m.journal_id = journal and journal.id or self.journal_id
                adv_claim_journal = self.env['account.journal'].search([('name','=','Advance Claim'),('company_id','=',self.env.company.id)],limit=1)
                m.journal_id = adv_claim_journal
            if m.expense_type=='dir_exp':
                journal = self.env.user.payment_journal_id
                if not journal:
                    journal = self.env['account.journal'].search([('type','=','cash')],limit=1,order='id asc')
                m.journal_id = journal and journal.id or self.journal_id
                m.journal_account = m.journal_id.default_account_id.id

    @api.onchange('partner_id')
    def onchange_partner_account(self):
        for line in self.line_ids:
            if line.move_id.partner_id and line.account_id.account_type == 'asset_receivable' and line.move_id.is_expense and line.move_id.expense_type=='advance_claim':
                line.account_id = line.move_id.partner_id.property_account_advance_id and line.move_id.partner_id.property_account_advance_id.id or line.account_id.id

    
    @api.constrains('partner_id')
    def check_partner_account(self):
        for line in self.line_ids:
            if line.move_id.partner_id and line.account_id.account_type == 'asset_receivable' and line.move_id.is_expense and line.move_id.expense_type=='advance_claim':
                line.account_id = line.move_id.partner_id.property_account_advance_id and line.move_id.partner_id.property_account_advance_id.id or line.account_id.id
                
    @api.onchange('journal_id')
    def onchange_journal_account(self):
        for res in self:
            if res.journal_id:
                res.journal_account = res.journal_id.default_account_id and res.journal_id.default_account_id.id or False
                
        for line in self.line_ids:
            if line.is_journal_acc:
                line.account_id = line.move_id.journal_account and  line.move_id.journal_account.id or line.account_id.id  

    @api.onchange('expense_type')
    def onchange_expense_type(self):
        if self.expense_type in ('advance_claim','dir_exp'):
            return {"domain": {"line_ids.product_id":[('expense_ok','=',True)]}}                       

    def action_change_status(self):
       
        to_status = self._context.get('to_status')
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
        for_what = self._context.get('default_expense_type')
        if to_status == 'director_approve' and for_what == 'advance_claim':
            self.action_post()
            self.write({'x_state':'paid'})
        elif to_status == 'hod_approve':
            if not self.line_ids:
                raise UserError('Please add at least one line!!')        
            to_status = to_status if for_what == 'dir_exp' else 'check'  
            self.write({'x_state':to_status}) 
            for res in self:
                if not self.ref:
                    sequence = self.env['sequence.model']
                    if res.is_expense and res.expense_type=='advance_claim':
                        res.ref = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.invoice_date,None,'advance_expense.action_move_expense')
                    if res.is_expense and res.expense_type=='dir_exp':
                        res.ref = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.invoice_date,None,'advance_expense.action_move_dir_expense')  
        elif to_status == 'waiting_payment' and for_what == 'dir_exp':
            self.action_dir_approve()     
        elif to_status == 'director_approve' and for_what == 'dir_exp':
            if self.need_of_dir_approve:
                self.write({'x_state':'director_approve'})
            else:
                self.write({'x_state':'waiting_payment'})
        elif to_status == 'paid':
            return {
            'name': _('Direct Expense Payment'),
            'view_mode': 'form',
            'res_model': 'direct.exp.wizard',
            'type': 'ir.actions.act_window',  
            'domain': [],   
            'target': 'new',           
            }
            # self.action_post()
            # self.write({'x_state':'paid'})
        elif to_status == 'refuse':
            super().button_cancel()
            self.write({'x_state':'refuse'})
        elif to_status == 'draft':
            if self.state == 'posted':
                super().button_draft()
            self.write({'x_state':'draft'})   
        elif to_status == 'cancel':
            if self.state == 'posted':
                super().button_draft()
            super().button_cancel()
            self.write({'x_state':'cancel'})       
        else:
            self.write({'x_state':to_status})

    def action_manually_close(self):
        self.write({'state':'paid'})
    

    def action_dir_approve(self):
        if not (self.need_of_dir_approve and self.director_id):
            raise ValidationError(_("Please add Director"))
        else:
            if not self.director_id.user_id:
                raise ValidationError(_("You need to add User in Employee's HR Setting"))
            else:
                if self.env.user != self.director_id.user_id:
                    raise ValidationError('Invalid Action.')
        self.write({'x_state':'waiting_payment'}) 

    def _get_move_display_name(self, show_ref=False):
        ''' Helper to get the display name of an invoice depending of its type.
        :param show_ref:    A flag indicating of the display name must include or not the journal entry reference.
        :return:            A string representing the invoice.
        '''
        self.ensure_one()
        name = ''
        if self.state == 'draft' and not self.expense_type:
            name += {
                'out_invoice': _('Draft Invoice'),
                'out_refund': _('Draft Credit Note'),
                'in_invoice': _('Draft Bill'),
                'in_refund': _('Draft Vendor Credit Note'),
                'out_receipt': _('Draft Sales Receipt'),
                'in_receipt': _('Draft Purchase Receipt'),
                'entry': _('Draft Entry'),
            }[self.move_type]
            name += ' '
        if (not self.name or self.name == '/') and not self.expense_type:
            name += '(* %s)' % str(self.id)
        else:
            name += str(self.name) if not self.expense_type or not self.ref else str(self.ref)
            if self.env.context.get('input_full_display_name'):
                if self.partner_id:
                    name += f', {self.partner_id.name}'
                if self.date:
                    name += f', {format_date(self.env, self.date)}'
        return name + (f" ({shorten(self.ref, width=50)})" if show_ref and self.ref and not self.expense_type else '')
            
    def _post(self, soft=True):
        """Post/Validate the documents.

        Posting the documents will give it a number, and check that the document is
        complete (some fields might not be required if not posted but are required
        otherwise).
        If the journal is locked with a hash table, it will be impossible to change
        some fields afterwards.

        :param soft (bool): if True, future documents are not immediately posted,
            but are set to be auto posted automatically at the set accounting date.
            Nothing will be performed on those documents before the accounting date.
        :return Model<account.move>: the documents that have been posted
        """
   
        if not self.env.su and not (self.env.user.has_group('account.group_account_invoice') or self.env.user.has_group('access_right.group_account_advance_user')):
            raise AccessError(_("You don't have the access rights to post an invoice."))

        for invoice in self.filtered(lambda move: move.is_invoice(include_receipts=True)):
            if invoice.quick_edit_mode and invoice.quick_edit_total_amount and invoice.quick_edit_total_amount != invoice.amount_total:
                raise UserError(_(
                    "The current total is %s but the expected total is %s. In order to post the invoice/bill, "
                    "you can adjust its lines or the expected Total (tax inc.).",
                    formatLang(self.env, invoice.amount_total, currency_obj=invoice.currency_id),
                    formatLang(self.env, invoice.quick_edit_total_amount, currency_obj=invoice.currency_id),
                ))
            if invoice.partner_bank_id and not invoice.partner_bank_id.active:
                raise UserError(_(
                    "The recipient bank account linked to this invoice is archived.\n"
                    "So you cannot confirm the invoice."
                ))
            if float_compare(invoice.amount_total, 0.0, precision_rounding=invoice.currency_id.rounding) < 0:
                raise UserError(_(
                    "You cannot validate an invoice with a negative total amount. "
                    "You should create a credit note instead. "
                    "Use the action menu to transform it into a credit note or refund."
                ))

            if not invoice.partner_id:
                if invoice.is_sale_document() and not invoice.is_expense:
                    raise UserError(_("The field 'Customer' is required, please complete it to validate the Customer Invoice."))
                elif invoice.is_purchase_document() and not invoice.is_expense:
                    raise UserError(_("The field 'Vendor' is required, please complete it to validate the Vendor Bill."))

            # Handle case when the invoice_date is not set. In that case, the invoice_date is set at today and then,
            # lines are recomputed accordingly.
            if not invoice.invoice_date:
                if invoice.is_sale_document(include_receipts=True):
                    invoice.invoice_date = fields.Date.context_today(self)
                elif invoice.is_purchase_document(include_receipts=True):
                    raise UserError(_("The Bill/Refund date is required to validate this document."))

        for move in self:
            if move.state == 'posted':
                raise UserError(_('The entry %s (id %s) is already posted.') % (move.name, move.id))
            if not move.line_ids.filtered(lambda line: line.display_type not in ('line_section', 'line_note')):
                raise UserError(_('You need to add a line before posting.'))
            if not soft and move.auto_post != 'no' and move.date > fields.Date.context_today(self):
                date_msg = move.date.strftime(get_lang(self.env).date_format)
                raise UserError(_("This move is configured to be auto-posted on %s", date_msg))
            if not move.journal_id.active:
                raise UserError(_(
                    "You cannot post an entry in an archived journal (%(journal)s)",
                    journal=move.journal_id.display_name,
                ))
            if move.display_inactive_currency_warning:
                raise UserError(_(
                    "You cannot validate a document with an inactive currency: %s",
                    move.currency_id.name
                ))

            if move.line_ids.account_id.filtered(lambda account: account.deprecated):
                raise UserError(_("A line of this move is using a deprecated account, you cannot post it."))
        
        # Addig default analytic account & project id & fleet id
        for move in self:
            # adding analytic in ap one line for bill , refund
            if move.move_type in ('in_invoice','out_invoice','out_refund','in_refund'):
                if move.partner_id and move.partner_id.partner_type == 'vendor' and self.partner_id.is_duty_owner:
                    first_invoice_line = move.invoice_line_ids[0]
                    if hasattr(first_invoice_line, 'fleet_id'):
                        dct = Counter([line_id.fleet_id.id for line_id in move.invoice_line_ids])
                        if False in dct:
                            raise ValidationError("Found blank fleet in the line..")
                        if len(dct) != 1:
                            raise ValidationError("You must add same fleet in all order lines when it is associated with duty owner - vendor!!")
                        for line in (move.line_ids - move.invoice_line_ids):
                            line.fleet_id = first_invoice_line.fleet_id
                            if hasattr(first_invoice_line, 'project_id'):
                                line.project_id = first_invoice_line.project_id
                            if hasattr(first_invoice_line, 'division_id'):
                                line.division_id = first_invoice_line.division_id
                            line.analytic_distribution = first_invoice_line.analytic_distribution
            no_analytic_move_line_ids = move.line_ids.filtered(lambda x:not x.analytic_distribution)
            if move.journal_id.default_analytic_account_ids and no_analytic_move_line_ids:
                project_id = False
                fleet_id = False
                division_id = False
                project_obj = move.env.get('analytic.project.code',None)
                fleet_obj = move.env.get('fleet.vehicle',None)
                division_obj = move.env.get('analytic.division',None)
                dct = {}
                for analytic_account_id in move.journal_id.default_analytic_account_ids:
                    dct[analytic_account_id.id] = 100
                    if analytic_account_id.plan_id and analytic_account_id.plan_id.name.lower() == 'project' and project_obj is not None and not project_id:
                        project_id = project_obj.search([('analytic_project_id','=',analytic_account_id.id)],limit=1)
                    elif analytic_account_id.plan_id and analytic_account_id.plan_id.name.lower() == 'fleet' and fleet_obj is not None and not fleet_id:
                        fleet_id = fleet_obj.search([('analytic_fleet_id','=',analytic_account_id.id)],limit=1).id
                    elif analytic_account_id.plan_id and analytic_account_id.plan_id.name.lower() == 'division' and division_obj is not None and not division_id:
                        division_id = analytic_account_id.division_id                       
                for move_line in no_analytic_move_line_ids:
                    if not move_line.analytic_distribution:
                        move_line.analytic_distribution = dct
                        if hasattr(move_line, 'project_id') and not move_line.project_id and project_id:
                            move_line.project_id = project_id
                        if hasattr(move_line, 'fleet_id') and not move_line.fleet_id and fleet_id:
                            move_line.fleet_id = fleet_id   
                        if hasattr(move_line, 'division_id') and not move_line.division_id and division_id:
                            move_line.division_id = division_id         

        if soft:
            future_moves = self.filtered(lambda move: move.date > fields.Date.context_today(self))
            for move in future_moves:
                if move.auto_post == 'no':
                    move.auto_post = 'at_date'
                msg = _('This move will be posted at the accounting date: %(date)s', date=format_date(self.env, move.date))
                move.message_post(body=msg)
            to_post = self - future_moves
        else:
            to_post = self

        for move in to_post:
            affects_tax_report = move._affect_tax_report()
            lock_dates = move._get_violated_lock_dates(move.date, affects_tax_report)
            if lock_dates:
                move.date = move._get_accounting_date(move.invoice_date or move.date, affects_tax_report)

        # Create the analytic lines in batch is faster as it leads to less cache invalidation.
        to_post.line_ids._create_analytic_lines()

        # Trigger copying for recurring invoices
        to_post.filtered(lambda m: m.auto_post not in ('no', 'at_date'))._copy_recurring_entries()

        for invoice in to_post:
            # Fix inconsistencies that may occure if the OCR has been editing the invoice at the same time of a user. We force the
            # partner on the lines to be the same as the one on the move, because that's the only one the user can see/edit.
            wrong_lines = invoice.is_invoice() and invoice.line_ids.filtered(lambda aml:
                aml.partner_id != invoice.commercial_partner_id
                and aml.display_type not in ('line_note', 'line_section')
            )
            if wrong_lines:
                wrong_lines.write({'partner_id': invoice.commercial_partner_id.id})

        to_post.write({
            'state': 'posted',
            'posted_before': True,
        })

        # generate sequence for  vendor bills
        for move in to_post:
            if not move.is_expense:
                sequence = self.env["sequence.model"]
                if move.move_type == 'in_invoice':
                    self.ref = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.invoice_date,None,'account.action_move_in_invoice_type') if not self.ref or  self.ref.count("/") != 2 or self.ref.startswith("BILL") else self.ref
                elif move.move_type == 'out_invoice':
                    if self.term_type != 'direct':
                        self.ref = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.invoice_date,None,'account.action_move_out_invoice_type') if not self.ref or self.ref.count("/") != 2 or self.ref.startswith("INV") else self.ref
                elif move.move_type == 'out_refund':
                    self.ref = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.invoice_date,None,'account.action_move_out_refund_type') if not self.ref or self.ref.count("/") != 2 or self.name.startswith("RINV") else self.ref
                elif move.move_type == 'in_refund':
                    self.ref = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.invoice_date,None,'account.action_move_in_refund_type') if not self.ref or self.ref.count("/") != 2 or self.ref.startswith("RBILL") else self.ref
        for invoice in to_post:
            invoice.message_subscribe([
                p.id
                for p in [invoice.partner_id]
                if p not in invoice.sudo().message_partner_ids
            ])

            if (
                invoice.is_sale_document()
                and invoice.journal_id.sale_activity_type_id
                and (invoice.journal_id.sale_activity_user_id or invoice.invoice_user_id).id not in (self.env.ref('base.user_root').id, False)
            ):
                invoice.activity_schedule(
                    date_deadline=min((date for date in invoice.line_ids.mapped('date_maturity') if date), default=invoice.date),
                    activity_type_id=invoice.journal_id.sale_activity_type_id.id,
                    summary=invoice.journal_id.sale_activity_note,
                    user_id=invoice.journal_id.sale_activity_user_id.id or invoice.invoice_user_id.id,
                )

        customer_count, supplier_count = defaultdict(int), defaultdict(int)
        for invoice in to_post:
            if invoice.is_sale_document():
                customer_count[invoice.partner_id] += 1
            elif invoice.is_purchase_document():
                supplier_count[invoice.partner_id] += 1
            elif invoice.move_type == 'entry':
                sale_amls = invoice.line_ids.filtered(lambda line: line.partner_id and line.account_id.account_type == 'asset_receivable')
                for partner in sale_amls.mapped('partner_id'):
                    customer_count[partner] += 1
                purchase_amls = invoice.line_ids.filtered(lambda line: line.partner_id and line.account_id.account_type == 'liability_payable')
                for partner in purchase_amls.mapped('partner_id'):
                    supplier_count[partner] += 1
        for partner, count in customer_count.items():
            (partner | partner.commercial_partner_id)._increase_rank('customer_rank', count)
        for partner, count in supplier_count.items():
            (partner | partner.commercial_partner_id)._increase_rank('supplier_rank', count)

        # Trigger action for paid invoices if amount is zero
        to_post.filtered(
            lambda m: m.is_invoice(include_receipts=True) and m.currency_id.is_zero(m.amount_total)
        )._invoice_paid_hook()

        if self._context.get('move_reverse_cancel'):
            return super()._post(soft)

        # Create additional COGS lines for customer invoices.
        for res in to_post:
            if res.move_type in ['out_invoice','out_refund']:
                self.env['account.move.line'].create(self._stock_account_prepare_anglo_saxon_out_lines_vals())

                if not self.env.context.get('skip_cogs_reconciliation'):
                    res._stock_account_anglo_saxon_reconcile_valuation()
        return to_post

        # return to_post
    
    # -------------------------------------------------------------------------
    # COGS METHODS
    # Inherting COGS method to add project and fleet id 
    # -------------------------------------------------------------------------

    def _stock_account_prepare_anglo_saxon_out_lines_vals(self):
        ''' Prepare values used to create the journal items (account.move.line) corresponding to the Cost of Good Sold
        lines (COGS) for customer invoices.

        Example:

        Buy a product having a cost of 9 being a storable product and having a perpetual valuation in FIFO.
        Sell this product at a price of 10. The customer invoice's journal entries looks like:

        Account                                     | Debit | Credit
        ---------------------------------------------------------------
        200000 Product Sales                        |       | 10.0
        ---------------------------------------------------------------
        101200 Account Receivable                   | 10.0  |
        ---------------------------------------------------------------

        This method computes values used to make two additional journal items:

        ---------------------------------------------------------------
        220000 Expenses                             | 9.0   |
        ---------------------------------------------------------------
        101130 Stock Interim Account (Delivered)    |       | 9.0
        ---------------------------------------------------------------

        Note: COGS are only generated for customer invoices except refund made to cancel an invoice.

        :return: A list of Python dictionary to be passed to env['account.move.line'].create.
        '''
        lines_vals_list = []
        price_unit_prec = self.env['decimal.precision'].precision_get('Product Price')
        for move in self:
            # Make the loop multi-company safe when accessing models like product.product
            move = move.with_company(move.company_id)

            if not move.is_sale_document(include_receipts=True) or not move.company_id.anglo_saxon_accounting:
                continue

            for line in move.invoice_line_ids:

                # Filter out lines being not eligible for COGS.
                if not line._eligible_for_cogs():
                    continue

                # Retrieve accounts needed to generate the COGS.
                accounts = line.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=move.fiscal_position_id)
                debit_interim_account = accounts['stock_output']
                credit_expense_account = accounts['expense'] or move.journal_id.default_account_id
                if not debit_interim_account or not credit_expense_account:
                    continue

                # Compute accounting fields.
                sign = -1 if move.move_type == 'out_refund' else 1
                price_unit = line._stock_account_get_anglo_saxon_price_unit()
                amount_currency = sign * line.quantity * price_unit

                if move.currency_id.is_zero(amount_currency) or float_is_zero(price_unit, precision_digits=price_unit_prec):
                    continue

                # Add interim account line.
                interim_val_dct = {
                    'name': line.name[:64],
                    'move_id': move.id,
                    'partner_id': move.commercial_partner_id.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'quantity': line.quantity,
                    'price_unit': price_unit,
                    'amount_currency': -amount_currency,
                    'account_id': debit_interim_account.id,
                    'display_type': 'cogs',
                    'tax_ids': [],
                }
                default_analytic_from_journals = self.journal_id.default_analytic_account_ids
                if default_analytic_from_journals:
                    analytic_dct = {}
                    for analytic_account in default_analytic_from_journals:
                        analytic_dct[analytic_account.id] = 100
                        if hasattr(analytic_account, 'project_id') and analytic_account.project_id:
                            interim_val_dct['project_id'] = analytic_account.project_id.id
                        if hasattr(analytic_account, 'fleet_id') and analytic_account.fleet_id:
                            interim_val_dct['fleet_id'] = analytic_account.fleet_id.id
                        if hasattr(analytic_account, 'division_id') and analytic_account.division_id:
                            interim_val_dct['division_id'] = analytic_account.division_id.id 
                    interim_val_dct['analytic_distribution'] = analytic_dct                
                lines_vals_list.append(interim_val_dct)



                # Add expense account line.
                credit_expense_dct = {
                    'name': line.name[:64],
                    'move_id': move.id,
                    'partner_id': move.commercial_partner_id.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'quantity': line.quantity,
                    'price_unit': -price_unit,
                    'amount_currency': amount_currency,
                    'account_id': credit_expense_account.id,
                    'analytic_distribution': line.analytic_distribution,
                    'division_id':line.division_id.id,
                    'display_type': 'cogs',
                    'tax_ids': [],
                }
                if hasattr(line, 'project_id'):
                    credit_expense_dct['project_id'] = line.project_id and line.project_id.id or False
                if hasattr(line, 'fleet_id'):
                    credit_expense_dct['fleet_id'] = line.fleet_id and line.fleet_id.id or False
                lines_vals_list.append(credit_expense_dct)

        return lines_vals_list    
    
    def action_print(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename)  + str(birt_suffix) + '.rptdesign&pp_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise ValidationError('Report Not Not Found') 
        
    def unlink(self):
        for rec in self:
            if rec.x_state != 'draft' or rec.state != 'draft' or (rec.ref and rec.ref.count("/") == 2):
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()
    
    def action_regenerate_sequence(self):
        all_invoices = self.env['account.move'].search([('move_type', '=', 'out_invoice')])
        sequence = sequence = self.env['sequence.model']
        for invoice in all_invoices:
            if invoice.state == 'posted' and invoice.term_type != 'driect' and invoice.ref and ( invoice.ref.count("/") != 2 or len(invoice.ref.split("/")[0]) != 3):
                invoice.ref = generate_code.generate_code(sequence,invoice,invoice.branch_id,invoice.company_id,invoice.invoice_date,None,'account.action_move_out_invoice_type') if (not invoice.ref) or len(invoice.ref.split("/")[0]) != 3 or invoice.ref.startswith("INV") else invoice.ref                


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    job_code_id = fields.Many2one(comodel_name='job.code',string="Job Code")
    report_remark_id = fields.Many2one(comodel_name='report.remark',string="Report Remark")
    voucher_type_id = fields.Many2one(comodel_name='voucher.type',string="Voucher Type")
    voucher_no = fields.Char(string="Voucher No.")
    voucher_date = fields.Date(string="Voucher Date")
    remark = fields.Char(string="Remark")
    employee_id = fields.Many2one(comodel_name='hr.employee',string="Employee")
    is_journal_acc = fields.Boolean(default=False)
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")

    @api.onchange('product_id')
    def _remove_account_auto_expense_account(self):
        for line in self:
            if line.move_id.expense_type in ('dir_exp','advance_claim'):
                if not line.product_id and line.account_id:
                    line.account_id = False
                if line.product_id:
                    line.account_id = ( line.product_id.categ_id and line.product_id.categ_id.property_account_expense_categ_id.id ) or False

    @api.onchange('division_id')
    def _onchage_analytic_by_division(self):
        dct = {}
        envv = self.env['account.analytic.account']
        if not self.division_id and len(self.move_id.line_ids) > 1:
            prev_line = self.move_id.line_ids[-2]
            if prev_line.analytic_distribution:
                dct = prev_line.analytic_distribution
            if hasattr(self, 'project_id'):
                self.project_id = prev_line.project_id
            if hasattr(self, 'division_id'):
                self.division_id = prev_line.division_id
            if hasattr(self, 'fleet_id'):
                prev_fleet = prev_line.fleet_id
                if prev_fleet and prev_fleet.analytic_fleet_id and str(prev_fleet.analytic_fleet_id.id) in dct:
                    dct.pop(str(prev_fleet.analytic_fleet_id.id))   
        elif self.division_id:
            if self.analytic_distribution:
                dct = {idd:val for idd,val in self.analytic_distribution.items() if envv.search([('id','=',idd)]).plan_id and envv.search([('id','=',idd)]).plan_id.name.lower() != 'division'}
            if self.division_id.analytic_account_id:
                dct[str(self.division_id.analytic_account_id.id)] = 100
        self.analytic_distribution = dct 

    @api.onchange('analytic_distribution')
    def _onchange_analytic_by_distribution(self):
        envv = self.env['account.analytic.account']
        dct = {}
        if self.analytic_distribution:
            dct = {idd:val for idd,val in self.analytic_distribution.items() if envv.search([('id','=',idd)]).plan_id and envv.search([('id','=',idd)]).plan_id.name.lower() not in ('vehicle','division','project')}        
        if hasattr(self, 'project_id') and self.project_id:         
            if self.project_id.analytic_project_id:
                dct[str(self.project_id.analytic_project_id.id)] = 100  
        if  hasattr(self, 'division_id') and self.division_id:
            if self.division_id.analytic_account_id:
                dct[str(self.division_id.analytic_account_id.id)] = 100 
        if hasattr(self,'fleet_id') and self.fleet_id and self.fleet_id.analytic_fleet_id and self.company_id == self.fleet_id.company_id:
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
        self.analytic_distribution = dct                   

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        for line in self:
            account_type = line.account_id.account_type
            if line.move_id.is_sale_document(include_receipts=True) and  line.move_id.is_expense==False:
                if (line.display_type == 'payment_term') ^ (account_type == 'asset_receivable'):
                    raise UserError(_("Any journal item on a receivable account must have a due date and vice versa."))
            if line.move_id.is_purchase_document(include_receipts=True) and  line.move_id.is_expense==False:
                if (line.display_type == 'payment_term') ^ (account_type == 'liability_payable'):
                    raise UserError(_("Any journal item on a payable account must have a due date and vice versa."))
                
    def create(self, vals_list):
        res = super().create(vals_list)
        for account in res.account_id:
            if account.account_type == 'asset_receivable' and res.move_id.is_expense and res.move_id.expense_type=='advance_claim':
                res.account_id = res.move_id.partner_id.property_account_advance_id and res.move_id.partner_id.property_account_advance_id.id or account.id
            if account.account_type == 'asset_receivable' and res.move_id.is_expense and res.move_id.expense_type=='dir_exp':
                res.account_id = res.move_id.journal_account and res.move_id.journal_account.id or account.id
                res.is_journal_acc = True
        return res
    
    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            if line.display_type == 'payment_term':
                line.name = line.move_id.payment_reference or ''
                continue
            if not line.product_id or line.display_type in ('line_section', 'line_note'):
                continue
            if line.partner_id.lang:
                product = line.product_id.with_context(lang=line.partner_id.lang)
            else:
                product = line.product_id

            values = []
            if product.name:
                values.append(product.name)
            elif product.partner_ref:
                values.append(product.partner_ref)
            if line.journal_id.type == 'sale':
                if product.description_sale:
                    values.append(product.description_sale)
            elif line.journal_id.type == 'purchase':
                if product.description_purchase:
                    values.append(product.description_purchase)
            line.name = '\n'.join(values)

    # def unlink(self):
    #     for line in self:
    #         rec = line.move_id
    #         if rec.x_state != 'draft' or rec.state != 'draft' or (line.product_id or line.price_subtotal > 0.0):
    #             raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
    #     return super().unlink()            

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    income_currency_exchange_account_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.income_currency_exchange_account_id",
        string="Gain Account",
        readonly=False,
        domain="[('deprecated', '=', False), ('company_id', '=', company_id),('account_type', 'in', ('income', 'income_other', 'expense'))]")
    expense_currency_exchange_account_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.expense_currency_exchange_account_id",
        string="Loss Account",
        readonly=False,
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), ('account_type', 'in', ('income', 'income_other', 'expense'))]")            
    


class AccountPaymentRegisterJournal(models.TransientModel):

    _inherit = 'account.payment.register'

    def _create_payments(self):
        self.ensure_one()
        batches = self._get_batches()
        first_batch_result = batches[0]
        edit_mode = self.can_edit_wizard and (len(first_batch_result['lines']) == 1 or self.group_payment)
        to_process = []

        if edit_mode:
            payment_vals = self._create_payment_vals_from_wizard(first_batch_result)
            to_process.append({
                'create_vals': payment_vals,
                'to_reconcile': first_batch_result['lines'],
                'batch': first_batch_result,
            })
        else:
            # Don't group payments: Create one batch per move.
            if not self.group_payment:
                new_batches = []
                for batch_result in batches:
                    for line in batch_result['lines']:
                        new_batches.append({
                            **batch_result,
                            'payment_values': {
                                **batch_result['payment_values'],
                                'payment_type': 'inbound' if line.balance > 0 else 'outbound'
                            },
                            'lines': line,
                        })
                batches = new_batches

            for batch_result in batches:
                to_process.append({
                    'create_vals': self._create_payment_vals_from_batch(batch_result),
                    'to_reconcile': batch_result['lines'],
                    'batch': batch_result,
                })

        payments = self._init_payments(to_process, edit_mode=edit_mode)

        # carry divission , project , analytic
        current_invoice_ids = self.env.context.get('active_ids')
        current_invoices = self.env['account.move'].browse(current_invoice_ids)         
        for payment in payments:
            origin_move = (current_invoices and current_invoices[0]) or False
            first_move_line = (origin_move and origin_move.line_ids and origin_move.line_ids[0]) or False
            if origin_move and first_move_line:
                if hasattr(payment, 'project_id') and first_move_line.project_id:
                    payment.project_id = first_move_line.project_id
                if hasattr(payment, 'division_id') and first_move_line.division_id:
                    payment.division_id = first_move_line.division_id
                if hasattr(payment, 'department_id') and origin_move.department_id:
                    payment.department_id = origin_move.department_id

        self._post_payments(to_process, edit_mode=edit_mode)
        self._reconcile_payments(to_process, edit_mode=edit_mode)
        return payments    

    def action_create_payments(self):
        payments = self._create_payments()

        current_invoice_ids = self.env.context.get('active_ids')
        current_invoices = self.env['account.move'].browse(current_invoice_ids) 

        sequence = self.env['sequence.model']


        # generate seq for invoice when cash sale
        for inv in current_invoices:
            if inv.move_type in ['out_invoice','out_refund']:
                if inv.term_type == 'direct':
                    if inv.move_type == 'out_invoice':
                        inv.ref = generate_code.generate_code(sequence,inv,inv.branch_id,inv.company_id,inv.invoice_date,None,'account.action_move_out_invoice_type') if not inv.ref or inv.ref.startswith("INV") else inv.ref
                    elif inv.move_type == 'out_refund':
                        inv.ref = generate_code.generate_code(sequence,inv,inv.branch_id,inv.company_id,inv.invoice_date,None,'account.action_move_out_refund_type') if not inv.ref or inv.ref.startswith("RINV") else inv.ref


        if self._context.get('dont_redirect_to_payments'):
            return True

        action = {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'context': {'create': False},
        }
        if len(payments) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': payments.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', payments.ids)],
            })
        return action 



class JobCode(models.Model):
    _name = "job.code"
    _description = "Job Code"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'    
    _name = "job.code"
    _description = "Job Code"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'    

    name = fields.Char(string="Code")
    complete_name = fields.Char('Complete Name', compute='_compute_complete_name', recursive=True, store=True)
    parent_id = fields.Many2one('job.code', 'Parent Job Code', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    parent_path = fields.Char(index=True, unaccent=False)
    child_id = fields.One2many('job.code', 'parent_id', 'Child Job Codes')
    description = fields.Char()
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for job_code in self:
            if job_code.parent_id:
                job_code.complete_name = '%s / %s' % (job_code.parent_id.complete_name, job_code.name)
            else:
                job_code.complete_name = job_code.name

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive job code.'))
        
    @api.constrains('name')
    def _check_name_recursion(self):
        count_name = self.env['job.code'].search([('name','=',self.name)])
        if len(count_name)>1:
            raise ValidationError(_('You cannot create recursive job code.'))

    @api.model
    def name_create(self, name):
        return self.create({'name': name}).name_get()[0]

    def name_get(self):
        if not self.env.context.get('hierarchical_naming', True):
            return [(record.id, record.name) for record in self]
        return super().name_get()

class ReportRemark(models.Model):
    _name = 'report.remark'

    name = fields.Char(string="Remark Name")
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)

class VoucherType(models.Model):
    _name = 'voucher.type'

    name = fields.Char(string="Type")
  

class DirExpWizard(models.TransientModel):
    _name = 'direct.exp.wizard'

    date = fields.Date(string="Payment Date",required=True)
    amount = fields.Float(string='Amount',required=True)
    account_id = fields.Many2one('account.account',string="Account")
    division_id = fields.Many2one('analytic.division',string="Division")
    
    def action_dir_exp_payment(self):
        context = self.env.context
        if context.get('active_model') and context.get('active_id'):
            model = self.env[context.get('active_model')].browse(context.get('active_id'))
            diff = abs(abs(model.amount_total) - abs(self.amount))
            if self.amount <= 0:
                raise UserError("Amount must be greater than zero!!")
            elif  round(model.amount_total,2) != round(self.amount,2) and not (self.division_id and self.account_id and ((hasattr(self, 'project_id') and self.project_id) or False)):
                error_string = "Account , Project  & Division " if hasattr(self, 'project_id') else "Account & Division "
                raise ValidationError(error_string + " is required!!!")
            if abs(self.amount)>abs(model.amount_total):
                surplus_invoice_dct = {
                                            'account_id': self.account_id.id,
                                            'name': 'Surplus',
                                            'price_unit': diff,
                                            'quantity': 1,
                                            'division_id': self.division_id.id,
                                        }
                if hasattr(self, 'project_id'):
                    surplus_invoice_dct['project_id'] = self.project_id.id
                model.update({'invoice_date':self.date,
                            'invoice_line_ids': [Command.create(surplus_invoice_dct)],
                                            })
            elif abs(self.amount)<abs(model.amount_total):
                deficit_invoice_dct = {
                                            'account_id': self.account_id.id,
                                            'name': 'Deficit',
                                            'price_unit': -diff,
                                            'quantity': 1,
                                            'division_id': self.division_id.id,
                                        }
                if hasattr(self, 'project_id'):
                    deficit_invoice_dct['project_id'] = self.project_id.id
                model.update({'invoice_date':self.date,
                            'invoice_line_ids': [Command.create(deficit_invoice_dct)],
                                            })
            else:
                model.update({'invoice_date':self.date})
                
            model.action_post()
            model.write({'x_state':'paid'})
            #     if not line.product_id and line.account_id.account_type == 'asset_cash':
            #         diff = self.amount-abs(line.balance)
            #         if line.balance<0:
            #             line.move_id.update({'invoice_date':self.date,
            #                                 # 'line_ids':[Command.create({'balance':1000,
            #                                 #                             'date_maturity': self.date,
            #                                 #                             'account_id': self.account_id.id})]
            #                                 'invoice_line_ids': [Command.create({
            #                                                 'account_id': self.account_id.id,
            #                                                 'name': 'Surplus',
            #                                                 'price_unit': diff,
            #                                                 'quantity': 1,
            #                                             })],
            #                                 })
                        # line.write({'balance':line.balance-diff})
                        
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    description = fields.Char(related='move_id.desc',store=True)
                        

