from odoo import api, fields, models, _
from odoo.exceptions import UserError,ValidationError
from ...generate_code import generate_code

class ExtPayment(models.Model):
    _inherit = 'account.payment'

    multi_id = fields.Many2one('multi.invoice.reconcile',string="Multi Payment")

class MultiInvoice(models.Model):
    _name = 'multi.invoice.reconcile'
    _description = 'Multi Payment'
    
    name = fields.Char(string="Payment No:")
    journal_id = fields.Many2one('account.journal', string="Journal", domain=[('type','in',['bank','cash'])])
    payment_date = fields.Date(string="Payment Date",default=fields.Datetime.now())
    exchange_rate = fields.Float('Exchange Rate',default=1.0)
    branch_id = fields.Many2one('res.branch',string="Branch")
    calculate_currency_id = fields.Many2one('res.currency',string="Currency")
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    payment_type = fields.Selection([
                            ('receive', 'Receive Money'),
                            ('sent', 'Sent Money'),
                            ], string='Type',required=True)
    invoice_ids = fields.One2many('multi.invoice.line','multi_id',string="Invoice Line IDs")
    state = fields.Selection([
                            ('draft', 'Draft'),                         
                            ('confirm', 'Confirm'),                         
                            ('cancel', 'Cancel'),                         
                            ('validate', 'Finished'),
                            ], string='Status',default="draft",track_visibility='onchange')
    supplier_rank = fields.Boolean('Supplier Rank')
    customer_rank = fields.Boolean('customer_rank')
    memo = fields.Char('Description')
    partner_id = fields.Many2one('res.partner',string="Partner")
    vendor_id = fields.Many2one('res.partner',string="Partner")
    company_id = fields.Many2one('res.company',default=lambda self:self.env.company)
    discount_type = fields.Selection([('amount','Amt'),('percentage','%')],string='Discount Type',default="percentage")
    discount_amt = fields.Float('Rate')
    amount_total = fields.Float('Grand Total',compute='_amount_all')
    discount_note = fields.Char('Discount Note.') 
    amount_extra = fields.Float('Extra Payment',compute='_amount_all')
    has_extra = fields.Boolean(compute='_amount_all')
    discount_account_id = fields.Many2one('account.account','Discount Account')
    amt_discount = fields.Float(string='Total Discount', store=True, readonly=True, compute='_amount_all')
    amt_payment = fields.Float(string='Total Amount', store=True, readonly=True, compute='_amount_all')
    partner_name = fields.Char(compute='get_partner_name')

    def get_partner_name(self):
        for rec in self:
            if rec.customer_rank:
                result = rec.partner_id.name
            else:
                result = rec.vendor_id.name
            rec.partner_name = result

    @api.depends('invoice_ids.discount_amt','invoice_ids.amt','exchange_rate','discount_amt','discount_type')
    def _amount_all(self):
        for rec in self:
            dis_amt = 0
            payment_total = 0
            amt_extra = 0.0
            for inv_id in rec.invoice_ids:
                dis_amt += inv_id.discount_amt * rec.exchange_rate if inv_id.discount_type == 'amount' else ((inv_id.amt*rec.exchange_rate) * (inv_id.discount_amt * rec.exchange_rate) / 100)
                payment_total += inv_id.amt * rec.exchange_rate
                if inv_id.amt > 0.0 and inv_id.amt > inv_id.amount_due:
                    amt_extra += inv_id.amt - inv_id.amount_due
            dis_amt += rec.discount_amt*rec.exchange_rate if rec.discount_type == 'amount' else (payment_total * (rec.discount_amt*rec.exchange_rate) /100)         
            rec.amt_payment = payment_total
            rec.amt_discount = dis_amt
            rec.amount_total = payment_total - dis_amt
            rec.amount_extra = amt_extra
            
            rec.has_extra = False
            if amt_extra:
                rec.has_extra = True    

    def action_confirm(self):
        sequence = self.env['sequence.model']
        self.name = generate_code.generate_code(sequence,self,self.env['res.branch'].browse(int(self.branch_id.id)),self.company_id,self.payment_date,None,None)
        self.state = 'confirm'   
             
    def action_cancel(self):
        self.state = 'cancel'
        
    def _get_pay_info(self):
        name = ''
        payment_amt = 0.0
        for line in self.invoice_ids:
            if line.select and line.amt > 0.0:
                if name:
                    name += ' | '
                name += str(line.move_id.ref)
                payment_amt += line.amt
        return name,payment_amt

    def action_validate(self):
        invoice_ids = self.env['multi.invoice.line'].search([('multi_id','=',self.id),('select','=',True),('amt','>',0.0)])
        self.state = 'validate'
        combine_seq,payment_amount = self._get_pay_info()
        if self.customer_rank:
            partner_type = 'customer'
            partner_id = self.partner_id
            
        else:
            partner_type = 'supplier'
            partner_id = self.vendor_id
        if self.payment_type == 'sent':
            pay_type = 'outbound'
            partner_account_id = partner_id.property_account_payable_id
        else:
            pay_type = 'inbound'
            partner_account_id = partner_id.property_account_receivable_id 

        discount_amt = self.discount_amt if self.discount_type == 'amount' else (payment_amount * self.discount_amt / 100)
        if self.amount_extra > 0.0:
            amount_extra = abs(self.amount_extra)
        payment_amount -= discount_amt
#         inbound_payment_method_line_ids
# outbound_payment_method_line_ids
        payment_methods = pay_type == 'inbound' and self.journal_id.inbound_payment_method_line_ids or self.journal_id.outbound_payment_method_line_ids
        vals = {
            'journal_id': self.journal_id.id,
            'amount': payment_amount,
            'exchange_rate': self.exchange_rate,
            'date': self.payment_date,
            'payment_type': pay_type,
            'partner_type': partner_type,
            'partner_id': partner_id.id,
            'currency_id': self.calculate_currency_id.id,
            'payment_method_id': payment_methods[0].payment_method_id.id,
            'ref': combine_seq,
            'desc': self.memo,
            'multi_id': self.id,
            # 'discount_amt':discount_amt,
            # 'discount_account_id': self.discount_account_id.id,
            # 'discount_note':self.discount_note,
            # 'amount_extra': self.amount_extra,
            'branch_id': self.branch_id.id
        }
        payment_id = self.env['account.payment'].create(vals)
        # payment_id
        payment_id.with_context({'to_status':'paid'}).action_change_status()

        pay_term_lines = payment_id.move_id.line_ids\
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', payment_id.move_id.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

        domain.append(('id','in',invoice_ids.move_id.line_ids.ids))
        for multi_line,line in zip(invoice_ids,self.env['account.move.line'].search(domain)):
            sorted_lines = line
            sorted_lines += payment_id.move_id.line_ids.filtered(lambda x:x.account_id == line.account_id and not x.reconciled)
            sorted_lines._all_reconciled_lines()
            involved_lines = sorted_lines._all_reconciled_lines()
            partial_no_exch_diff = bool(self.env['ir.config_parameter'].sudo().get_param('account.disable_partial_exchange_diff'))
            sorted_lines_ctx = sorted_lines.with_context(no_exchange_difference=self._context.get('no_exchange_difference') or partial_no_exch_diff)
            partials = self._create_reconciliation_partials(sorted_lines_ctx,multi_line)
            multi_line.amount_due = multi_line.move_id.amount_residual

    def _create_reconciliation_partials(self,lines,multi_line):
        prepare_partial_vals_list = [{
                            'record': lines[0],
                            'balance': lines[0].balance,
                            'amount_currency': lines[0].amount_currency,
                            'amount_residual': lines[0].amount_residual,
                            'amount_residual_currency': lines[0].amount_residual_currency,
                            'company': lines[0].company_id,
                            'currency': lines[0].currency_id,
                            'date': lines[0].date,
                        }]
        if self.payment_type == 'sent':
            prepare_partial_vals_list.append({
                            'record': lines[1],
                            'balance': (multi_line[0].amt * self.exchange_rate),
                            'amount_currency': (multi_line[0].amt * self.exchange_rate),
                            'amount_residual': (multi_line[0].amt * self.exchange_rate),
                            'amount_residual_currency': (multi_line[0].amt * self.exchange_rate),
                            'company': lines[1].company_id,
                            'currency': lines[1].currency_id,
                            'date': lines[1].date,
                         })
        else:
            prepare_partial_vals_list.append({
                            'record': lines[1],
                            'balance': -(multi_line[0].amt * self.exchange_rate),
                            'amount_currency': -(multi_line[0].amt * self.exchange_rate),
                            'amount_residual': -(multi_line[0].amt * self.exchange_rate),
                            'amount_residual_currency': -(multi_line[0].amt * self.exchange_rate),
                            'company': lines[1].company_id,
                            'currency': lines[1].currency_id,
                            'date': lines[1].date,
                         })
        partials_vals_list, exchange_data = self.env['account.move.line']._prepare_reconciliation_partials(prepare_partial_vals_list)
        partials = self.env['account.partial.reconcile'].create(partials_vals_list)

        # ==== Create exchange difference moves ====
        for index, exchange_vals in exchange_data.items():
            partials[index].exchange_move_id = self._create_exchange_difference_move(exchange_vals)

        return partials
    @api.constrains('amt_discount','discount_account_id')
    def _check_discount_amt(self):
        if (self.amt_discount > 0.0 or self.amount_extra > 0.0) and not self.discount_account_id:
            raise ValidationError('Pleae define Discount Amount.')
        if self.amt_discount > 0.0 and not self.discount_note:
            raise ValidationError(_('Please define not for discount'))
        if self.amount_extra > 0.0 and not self.discount_note:
            raise ValidationError('Please define note for extra payment')

    def define_invoice_lines(self):
        if not self.from_date or not self.to_date:
            raise ValidationError(_('Please enter From Date and To Date'))
        if (self.partner_id or self.vendor_id) and self.payment_type and (self.branch_id) and self.payment_date: 
            domain = []
            if self.supplier_rank:
                partner_id = self.vendor_id
            else:
                partner_id = self.partner_id
            self.invoice_ids = None
            new_lines = self.env['multi.invoice.line']
            move_type = ''
            if self.customer_rank: # CUSTOMER
                if self.payment_type == "receive": #REIVE
                    move_type = "out_invoice"
                else: # SEND
                    move_type = "out_refund"
                    
            else: ######  VENDOR
                if self.payment_type == "receive":
                    move_type = "in_refund"
                else:
                    move_type = "in_invoice"
            domain.append(('branch_id','=',self.branch_id.id))
            domain.append(('move_type','=',move_type))
            domain.append(('partner_id','=',partner_id.id))
            domain.append(('state','=','posted'))
            domain.append(('amount_residual','>',0))
            domain.append(('invoice_date','>=',self.from_date))
            domain.append(('invoice_date','<=',self.to_date))
            if self.calculate_currency_id:
                domain.append(('currency_id','=',self.calculate_currency_id.id)) 
            move_ids = self.env['account.move'].search(domain,order="invoice_date desc")
            for rec in move_ids:
                # rec._compute_amount()
                vals = {
                        'move_id': rec.id, 
                        'invoice_date': rec.invoice_date,
                        'total_amt': rec.amount_total,
                        'amount_due': rec.amount_residual,
                        'amt': 0.0,
                        'currency_id': rec.currency_id.id,
                        'exchange_rate':rec.exchange_rate,
                        'internal_ref':rec.internal_ref,
                        'payment_ref': rec.payment_reference,
                        'payment_term_id': rec.invoice_payment_term_id.id,
                        'bill_ref': rec.ref,
                    }
                new_line = new_lines.new(vals)                
                new_lines += new_line
            self.invoice_ids += new_lines

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()

class MultiInvoiceLine(models.Model):
    _name = 'multi.invoice.line'
    _description = 'Multi Invoice Line'
    
    name = fields.Char('Description')
    move_id = fields.Many2one('account.move',string="",required=True)
    amt = fields.Float('Payment Amount')
    currency_id = fields.Many2one('res.currency',string="Currency")
    amount_due = fields.Float('Due')
    total_amt = fields.Float('Total')
    multi_id = fields.Many2one('multi.invoice.reconcile',string="Ref Multi Payment")
    exchange_rate = fields.Float('Exchange Rate',default=1.0)
    discount_type = fields.Selection([('amount','Amt'),('percentage','%')],string='Discount Type',default="percentage")
    discount_amt = fields.Float('Rate')     
    discount_label = fields.Char('Discount Label')
    invoice_date = fields.Date('Date')
    ref = fields.Char('Ref.')
    branch_id = fields.Many2one('res.branch',related="multi_id.branch_id")
    internal_ref = fields.Char('Internal Ref.')
    payment_ref = fields.Char('Payment Ref.')
    payment_term_id = fields.Many2one('account.payment.term',string="Payment Term")
    arap_id = fields.Many2one('account.move.line',string="ARAP ID",compute='compute_arap_id')
    bill_ref = fields.Char('Bill Ref.')
    select = fields.Boolean('Select')

    def compute_arap_id(self):
        for rec in self:
            result = None
            if rec.move_id:
                line_id = self.env['account.move.line'].search([('move_id','=',rec.move_id.id),('account_id.account_type','in',['asset_receivable','liability_payable'])],limit=1) 
                if line_id:
                    result = line_id.id
            rec.arap_id = result
            
    @api.onchange('select')
    def onchange_select(self):
        if self.select:
            self.amt = self.amount_due
        else:
            self.amt = 0.0