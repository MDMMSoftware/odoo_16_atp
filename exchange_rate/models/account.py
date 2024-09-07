# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from functools import lru_cache



class AccountMove(models.Model):
    """inherited account move"""
    _inherit = 'account.move'

    exchange_rate = fields.Float(string='Exchange Rate',default=1.0,tracking=True,copy=False, precompute=True)

class AccountMoveLine(models.Model):
    """inherited account move line"""
    _inherit = 'account.move.line'

    exchange_rate = fields.Float(related='move_id.exchange_rate', string='Exchange Rate', copy=False, store=True, precompute=True)

    @api.depends('currency_id', 'company_id', 'move_id.date','move_id.exchange_rate')
    def _compute_currency_rate(self):
        @lru_cache()
        def get_rate(from_currency, to_currency, company, date):
            return self.env['res.currency']._get_conversion_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                company=company,
                date=date,
            )
        for line in self:
            if line.currency_id and line.exchange_rate:
                line.currency_rate = 1/line.exchange_rate
            elif line.currency_id:
                line.currency_rate = get_rate(
                    from_currency=line.company_currency_id,
                    to_currency=line.currency_id,
                    company=line.company_id,
                    date=line.move_id.invoice_date or line.move_id.date or fields.Date.context_today(line),
                )
            else:
                line.currency_rate = 1


class AccountPaymentRegister(models.TransientModel): 
    _inherit = 'account.payment.register'

    exchange_rate = fields.Float('Exchange Rate',default=1.0,store=True, readonly=False, precompute=True)
    descriptions = fields.Char("Description")
    
   

    
    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date','exchange_rate')
    def _compute_amount(self):
        for wizard in self:
            if wizard.source_currency_id and wizard.can_edit_wizard:
                batch_result = wizard._get_batches()[0]
                wizard.amount = wizard._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result)[0]
            else:
                # The wizard is not editable so no partial payment allowed and then, 'amount' is not used.
                wizard.amount = None

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def _get_batch_communication(self, batch_result):
        ''' Helper to compute the communication based on the batch.
        :param batch_result:    A batch returned by '_get_batches'.
        :return:                A string representing a communication to be set on payment.
        '''
        labels = set(line.move_id.ref or line.name or line.move_id.name for line in batch_result['lines'])
        return ' '.join(sorted(labels))  
    
    def _create_payment_vals_from_wizard(self, batch_result):
        res = super()._create_payment_vals_from_wizard(batch_result)
        res.update({'exchange_rate': self.exchange_rate,
                    'desc': self.descriptions})
        
        return res              

    def _get_total_amount_in_wizard_currency_to_full_reconcile(self, batch_result, early_payment_discount=True):
        """ Compute the total amount needed in the currency of the wizard to fully reconcile the batch of journal
        items passed as parameter.

        :param batch_result:    A batch returned by '_get_batches'.
        :return:                An amount in the currency of the wizard.
        """
        self.ensure_one()
        comp_curr = self.company_id.currency_id
        if self.source_currency_id == self.currency_id:
            # Same currency (manage the early payment discount).
            return self._get_total_amount_using_same_currency(batch_result, early_payment_discount=early_payment_discount)
        elif self.source_currency_id != comp_curr and self.currency_id == comp_curr:
            # Foreign currency on source line but the company currency one on the opposite line.
            if self.exchange_rate:
                return self.source_amount_currency*self.exchange_rate,False
            else:
                return self.source_currency_id._convert(
                    self.source_amount_currency,
                    comp_curr,
                    self.company_id,
                    self.payment_date,
                ), False
        elif self.source_currency_id == comp_curr and self.currency_id != comp_curr:
            # Company currency on source line but a foreign currency one on the opposite line.
            residual_amount = 0.0
            for aml in batch_result['lines']:
                if not aml.move_id.payment_id and not aml.move_id.statement_line_id:
                    conversion_date = self.payment_date
                else:
                    conversion_date = aml.date
                residual_amount += comp_curr._convert(
                    aml.amount_residual,
                    self.currency_id,
                    self.company_id,
                    conversion_date,
                )
            return abs(residual_amount), False
        else:
            # Foreign currency on payment different than the one set on the journal entries.
            return comp_curr._convert(
                self.source_amount,
                self.currency_id,
                self.company_id,
                self.payment_date,
            ), False
    

class AccountPayment(models.Model):
    _inherit= "account.payment"

    exchange_rate = fields.Float(string='Exchange Rate', store=True, copy=True,default=1.0,tracking=True)
    descriptions = fields.Char("Description")

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        :param write_off_line_vals: Optional list of dictionaries to create a write-off account.move.line easily containing:
            * amount:       The amount to be added to the counterpart amount.
            * name:         The label to set on the line.
            * account_id:   The account on which create the write-off.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}

        if not self.outstanding_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
                self.payment_method_line_id.name, self.journal_id.display_name))

        # Compute amounts.
        write_off_line_vals_list = write_off_line_vals or []
        write_off_amount_currency = sum(x['amount_currency'] for x in write_off_line_vals_list)
        write_off_balance = sum(x['balance'] for x in write_off_line_vals_list)

        if self.payment_type == 'inbound':
            # Receive money.
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            # Send money.
            liquidity_amount_currency = -self.amount
        else:
            liquidity_amount_currency = 0.0

        liquidity_balance = self.currency_id._convert(
            liquidity_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        if self.exchange_rate:
            liquidity_balance = self.exchange_rate*liquidity_amount_currency
        counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
        counterpart_balance = -liquidity_balance - write_off_balance
        currency_id = self.currency_id.id

        # Compute a default label to set on the journal items.
        liquidity_line_name = ''.join(x[1] for x in self._get_liquidity_aml_display_name_list())
        counterpart_line_name = ''.join(x[1] for x in self._get_counterpart_aml_display_name_list())

        line_vals_list = [
            # Liquidity line.
            {
                'name': liquidity_line_name,
                'date_maturity': self.date,
                'amount_currency': liquidity_amount_currency,
                'currency_id': currency_id,
                'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.outstanding_account_id.id,
            },
            # Receivable / Payable.
            {
                'name': counterpart_line_name,
                'date_maturity': self.date,
                'amount_currency': counterpart_amount_currency,
                'currency_id': currency_id,
                'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
                'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.destination_account_id.id,
            },
        ]

        for line in line_vals_list + write_off_line_vals_list:
            account = self.env['account.account'].browse(line['account_id'])
            if self.is_transfer:
                if account.account_type not in ['asset_receivable','liability_payable'] and self.advance_account_id:
                    line.update({'account_id':self.advance_account_id.id})
                else:
                    line.update({'account_id':self.partner_account.id})
            else:
                if account.account_type in ['asset_receivable','liability_payable'] and self.advance_account_id:
                    line.update({'account_id':self.advance_account_id.id})

        # return res
        return line_vals_list + write_off_line_vals_list