from odoo import models, fields, api,_
from odoo.exceptions import ValidationError

class PrepaidRegisterAdvance(models.Model):
    _name = "prepaid.register.advance"

    date = fields.Date('Date',default=fields.date.today(),required=True)
    company_id = fields.Many2one('res.company',string="Company", required=True, default=lambda self: self.env.company)
    amount = fields.Float('Amount',required=True)
    prepaid_id = fields.Many2one('advance.prepaid',string="Prepaid")
    advance_id = fields.Many2one('account.payment',string="Payment")
    user_id = fields.Many2one('res.users',string="User:")
    ref = fields.Char('Ref.',required=True)
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        store=True,required=True,
        domain="[('company_id', '=', company_id),('type', 'in', ('bank', 'cash'))]")
    
    bill_journal_id = fields.Many2one(
        comodel_name='account.journal',
        store=True,required=False,
        domain="[('company_id', '=', company_id),('type', '=', 'purchase')]")
    
    payment_type = fields.Selection([
        ('outbound', 'Send'),
        ('inbound', 'Receive'),
    ], string='Payment Type', default='inbound', required=True, tracking=True)
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method',
        readonly=False, store=True,
        compute='_compute_payment_method_line_id',
        domain="[('id', 'in', available_payment_method_line_ids)]",
        help="Manual: Pay or Get paid by any method outside of Odoo.\n"
        "Payment Providers: Each payment provider has its own Payment Method. Request a transaction on/to a card thanks to a payment token saved by the partner when buying or subscribing online.\n"
        "Check: Pay bills by check and print it from Odoo.\n"
        "Batch Deposit: Collect several customer checks at once generating and submitting a batch deposit to your bank. Module account_batch_payment is necessary.\n"
        "SEPA Credit Transfer: Pay in the SEPA zone by submitting a SEPA Credit Transfer file to your bank. Module account_sepa is necessary.\n"
        "SEPA Direct Debit: Get paid in the SEPA zone thanks to a mandate your partner will have granted to you. Module account_sepa is necessary.\n")
    available_payment_method_line_ids = fields.Many2many('account.payment.method.line', compute='_compute_payment_method_line_fields')
    advance_account_id = fields.Many2one('account.account',domain="[('company_id', '=', company_id)]",required=True)
    job_code_id = fields.Many2one('job.code',string="Job Code")
    is_internal_transfer = fields.Boolean(string="Is Internal Transfer",
        readonly=False, store=True)    

    # @api.onchange('amount')
    def checking_amount(self):
        if self.prepaid_id.done_amt+self.amount == self.prepaid_id.prepare_amt:
            self.prepaid_id.state='paid'
            self.prepaid_id.payment_status='paided'
            return True
        
        if self.prepaid_id.done_amt+self.amount>0 and self.prepaid_id.done_amt+self.amount < self.prepaid_id.prepare_amt:
            self.prepaid_id.payment_status='partial'
            return True
        if self.amount <= 0.0:
            raise ValidationError('Invalid amount.')
        
      

    def action_register(self):
        for rec in self:
            rec.checking_amount()
            advance_id = rec.prepaid_id.prepaid_advance(rec)
            rec.advance_id = advance_id[0]
            rec.user_id = self.env.user.id
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'Payment Transaction Done!!',
                    'type': 'rainbow_man',
                }
            }


    @api.depends('payment_type', 'journal_id')
    def _compute_payment_method_line_id(self):
        for wizard in self:
            if wizard.journal_id:
                available_payment_method_lines = wizard.journal_id._get_available_payment_method_lines(wizard.payment_type)
            else:
                available_payment_method_lines = False

            # Select the first available one by default.
            if available_payment_method_lines:
                wizard.payment_method_line_id = available_payment_method_lines[0]._origin
            else:
                wizard.payment_method_line_id = False

    @api.depends('payment_type', 'journal_id')
    def _compute_payment_method_line_fields(self):
        for wizard in self:
            if wizard.journal_id:
                wizard.available_payment_method_line_ids = wizard.journal_id._get_available_payment_method_lines(wizard.payment_type)
            else:
                wizard.available_payment_method_line_ids = False