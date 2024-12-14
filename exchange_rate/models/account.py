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
    
    def _remove_exchange_partial_reconcile(self):
        for res in self:
            res.env.cr.execute('DELETE FROM account_partial_reconcile WHERE exchange_move_id = %s;',(res.id,))
            res.env.cr.execute('DELETE FROM account_full_reconcile WHERE exchange_move_id = %s;',(res.id,))

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
                
    # @api.model
    # def _prepare_reconciliation_single_partial(self, debit_vals, credit_vals):
    #     """ Prepare the values to create an account.partial.reconcile later when reconciling the dictionaries passed
    #     as parameters, each one representing an account.move.line.
    #     :param debit_vals:  The values of account.move.line to consider for a debit line.
    #     :param credit_vals: The values of account.move.line to consider for a credit line.
    #     :return:            A dictionary:
    #         * debit_vals:   None if the line has nothing left to reconcile.
    #         * credit_vals:  None if the line has nothing left to reconcile.
    #         * partial_vals: The newly computed values for the partial.
    #     """

    #     def is_payment(vals):
    #         return vals.get('is_payment') or (
    #             vals.get('record')
    #             and bool(vals['record'].move_id.payment_id or vals['record'].move_id.statement_line_id)
    #         )

    #     def get_odoo_rate(vals, other_line=None):
    #         if vals.get('record') and vals['record'].move_id.is_invoice(include_receipts=True):
    #             exchange_rate_date = vals['record'].move_id.invoice_date
    #         else:
    #             exchange_rate_date = vals['date']
    #         if not is_payment(vals) and other_line and is_payment(other_line):
    #             exchange_rate_date = other_line['date']
    #         return recon_currency._get_conversion_rate(company_currency, recon_currency, vals['company'], exchange_rate_date)

    #     def get_accounting_rate(vals):
    #         if company_currency.is_zero(vals['balance']) or vals['currency'].is_zero(vals['amount_currency']):
    #             return None
    #         else:
    #             return abs(vals['amount_currency']) / abs(vals['balance'])

    #     # ==== Determine the currency in which the reconciliation will be done ====
    #     # In this part, we retrieve the residual amounts, check if they are zero or not and determine in which
    #     # currency and at which rate the reconciliation will be done.

    #     res = {
    #         'debit_vals': debit_vals,
    #         'credit_vals': credit_vals,
    #     }
    #     remaining_debit_amount_curr = debit_vals['amount_residual_currency']
    #     remaining_credit_amount_curr = credit_vals['amount_residual_currency']
    #     remaining_debit_amount = debit_vals['amount_residual']
    #     remaining_credit_amount = credit_vals['amount_residual']

    #     company_currency = debit_vals['company'].currency_id
    #     has_debit_zero_residual = company_currency.is_zero(remaining_debit_amount)
    #     has_credit_zero_residual = company_currency.is_zero(remaining_credit_amount)
    #     has_debit_zero_residual_currency = debit_vals['currency'].is_zero(remaining_debit_amount_curr)
    #     has_credit_zero_residual_currency = credit_vals['currency'].is_zero(remaining_credit_amount_curr)
    #     is_rec_pay_account = debit_vals.get('record') \
    #                          and debit_vals['record'].account_type in ('asset_receivable', 'liability_payable')

    #     if debit_vals['currency'] == credit_vals['currency'] == company_currency \
    #             and not has_debit_zero_residual \
    #             and not has_credit_zero_residual:
    #         # Everything is expressed in company's currency and there is something left to reconcile.
    #         recon_currency = company_currency
    #         debit_rate = credit_rate = 1.0
    #         recon_debit_amount = remaining_debit_amount
    #         recon_credit_amount = -remaining_credit_amount
    #     elif debit_vals['currency'] == company_currency \
    #             and is_rec_pay_account \
    #             and not has_debit_zero_residual \
    #             and credit_vals['currency'] != company_currency \
    #             and not has_credit_zero_residual_currency:
    #         # The credit line is using a foreign currency but not the opposite line.
    #         # In that case, convert the amount in company currency to the foreign currency one.
    #         recon_currency = credit_vals['currency']
    #         debit_rate = get_odoo_rate(debit_vals, other_line=credit_vals)
    #         credit_rate = get_accounting_rate(credit_vals)
    #         recon_debit_amount = recon_currency.round(remaining_debit_amount * debit_rate)
    #         recon_credit_amount = -remaining_credit_amount_curr

    #         # If there is nothing left after applying the rate to reconcile in foreign currency,
    #         # try to fallback on the company currency instead.
    #         if recon_currency.is_zero(recon_debit_amount) or recon_currency.is_zero(recon_credit_amount):
    #             recon_currency = company_currency
    #             debit_rate = 1
    #             recon_debit_amount = remaining_debit_amount
    #             recon_credit_amount = -remaining_credit_amount

    #     elif debit_vals['currency'] != company_currency \
    #             and is_rec_pay_account \
    #             and not has_debit_zero_residual_currency \
    #             and credit_vals['currency'] == company_currency \
    #             and not has_credit_zero_residual:
    #         # The debit line is using a foreign currency but not the opposite line.
    #         # In that case, convert the amount in company currency to the foreign currency one.
    #         recon_currency = debit_vals['currency']
    #         debit_rate = get_accounting_rate(debit_vals)
    #         credit_rate = get_odoo_rate(credit_vals, other_line=debit_vals)
    #         recon_debit_amount = remaining_debit_amount_curr
    #         recon_credit_amount = recon_currency.round(-remaining_credit_amount * credit_rate)

    #         # If there is nothing left after applying the rate to reconcile in foreign currency,
    #         # try to fallback on the company currency instead.
    #         if recon_currency.is_zero(recon_debit_amount) or recon_currency.is_zero(recon_credit_amount):
    #             recon_currency = company_currency
    #             credit_rate = 1
    #             recon_debit_amount = remaining_debit_amount
    #             recon_credit_amount = -remaining_credit_amount

    #     elif debit_vals['currency'] == credit_vals['currency'] \
    #             and debit_vals['currency'] != company_currency \
    #             and not has_debit_zero_residual_currency \
    #             and not has_credit_zero_residual_currency:
    #         # Both lines are sharing the same foreign currency.
    #         recon_currency = debit_vals['currency']
    #         debit_rate = get_accounting_rate(debit_vals)
    #         credit_rate = get_accounting_rate(credit_vals)
    #         recon_debit_amount = remaining_debit_amount_curr
    #         recon_credit_amount = -remaining_credit_amount_curr
    #     elif debit_vals['currency'] == credit_vals['currency'] \
    #             and debit_vals['currency'] != company_currency \
    #             and (has_debit_zero_residual_currency or has_credit_zero_residual_currency):
    #         # Special case for exchange difference lines. In that case, both lines are sharing the same foreign
    #         # currency but at least one has no amount in foreign currency.
    #         # In that case, we don't want a rate for the opposite line because the exchange difference is supposed
    #         # to reduce only the amount in company currency but not the foreign one.
    #         recon_currency = company_currency
    #         debit_rate = None
    #         credit_rate = None
    #         recon_debit_amount = remaining_debit_amount
    #         recon_credit_amount = -remaining_credit_amount
    #     else:
    #         # Multiple involved foreign currencies. The reconciliation is done using the currency of the company.
    #         recon_currency = company_currency
    #         debit_rate = get_accounting_rate(debit_vals)
    #         credit_rate = get_accounting_rate(credit_vals)
    #         recon_debit_amount = remaining_debit_amount
    #         recon_credit_amount = -remaining_credit_amount

    #     # Check if there is something left to reconcile. Move to the next loop iteration if not.
    #     skip_reconciliation = False
    #     if recon_currency.is_zero(recon_debit_amount):
    #         res['debit_vals'] = None
    #         skip_reconciliation = True
    #     if recon_currency.is_zero(recon_credit_amount):
    #         res['credit_vals'] = None
    #         skip_reconciliation = True
    #     if skip_reconciliation:
    #         return res

    #     # ==== Match both lines together and compute amounts to reconcile ====

    #     # Determine which line is fully matched by the other.
    #     compare_amounts = recon_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
    #     min_recon_amount = min(recon_debit_amount, recon_credit_amount)
    #     debit_fully_matched = compare_amounts <= 0
    #     credit_fully_matched = compare_amounts >= 0

    #     # ==== Computation of partial amounts ====
    #     if recon_currency == company_currency:
    #         # Compute the partial amount expressed in company currency.
    #         partial_amount = min_recon_amount

    #         # Compute the partial amount expressed in foreign currency.
    #         if debit_rate:
    #             partial_debit_amount_currency = debit_vals['currency'].round(debit_rate * min_recon_amount)
    #             partial_debit_amount_currency = min(partial_debit_amount_currency, remaining_debit_amount_curr)
    #         else:
    #             partial_debit_amount_currency = 0.0
    #         if credit_rate:
    #             partial_credit_amount_currency = credit_vals['currency'].round(credit_rate * min_recon_amount)
    #             partial_credit_amount_currency = min(partial_credit_amount_currency, -remaining_credit_amount_curr)
    #         else:
    #             partial_credit_amount_currency = 0.0

    #     else:
    #         # recon_currency != company_currency
    #         # Compute the partial amount expressed in company currency.
    #         if debit_rate:
    #             partial_debit_amount = company_currency.round(min_recon_amount / debit_rate)
    #             # this code snipped is the customized code to avoid conflict the exchange gain / loss jounal when 
    #             # foreign currency is in credit side and company currency is in debit side
    #             if debit_rate == 1 and credit_rate != 1:
    #                 partial_debit_amount = remaining_debit_amount
    #             # customization                
    #             partial_debit_amount = min(partial_debit_amount, remaining_debit_amount)
    #         else:
    #             partial_debit_amount = 0.0
    #         if credit_rate:
    #             partial_credit_amount = company_currency.round(min_recon_amount / credit_rate)
    #             # this code snipped is the customized code to avoid conflict the exchange gain / loss jounal when 
    #             # foreign currency is in debit side and company currency is in credit side                
    #             if credit_rate == 1 and debit_rate != 1:
    #                 partial_credit_amount = -remaining_credit_amount  
    #             # customization                                  
    #             partial_credit_amount = min(partial_credit_amount, -remaining_credit_amount)
    #         else:
    #             partial_credit_amount = 0.0
    #         partial_amount = min(partial_debit_amount, partial_credit_amount)

    #         # Compute the partial amount expressed in foreign currency.
    #         # Take care to handle the case when a line expressed in company currency is mimicking the foreign
    #         # currency of the opposite line.
    #         if debit_vals['currency'] == company_currency:
    #             partial_debit_amount_currency = partial_amount
    #         else:
    #             partial_debit_amount_currency = min_recon_amount
    #         if credit_vals['currency'] == company_currency:
    #             partial_credit_amount_currency = partial_amount
    #         else:
    #             partial_credit_amount_currency = min_recon_amount

    #     # Computation of the partial exchange difference. You can skip this part using the
    #     # `no_exchange_difference` context key (when reconciling an exchange difference for example).
    #     if not self._context.get('no_exchange_difference'):
    #         exchange_lines_to_fix = self.env['account.move.line']
    #         amounts_list = []
    #         if recon_currency == company_currency:
    #             if debit_fully_matched:
    #                 debit_exchange_amount = remaining_debit_amount_curr - partial_debit_amount_currency
    #                 if not debit_vals['currency'].is_zero(debit_exchange_amount):
    #                     if debit_vals.get('record'):
    #                         exchange_lines_to_fix += debit_vals['record']
    #                     amounts_list.append({'amount_residual_currency': debit_exchange_amount})
    #                     remaining_debit_amount_curr -= debit_exchange_amount
    #             if credit_fully_matched:
    #                 credit_exchange_amount = remaining_credit_amount_curr + partial_credit_amount_currency
    #                 if not credit_vals['currency'].is_zero(credit_exchange_amount):
    #                     if credit_vals.get('record'):
    #                         exchange_lines_to_fix += credit_vals['record']
    #                     amounts_list.append({'amount_residual_currency': credit_exchange_amount})
    #                     remaining_credit_amount_curr += credit_exchange_amount

    #         else:
    #             if debit_fully_matched:
    #                 # Create an exchange difference on the remaining amount expressed in company's currency.
    #                 debit_exchange_amount = remaining_debit_amount - partial_amount
    #                 if not company_currency.is_zero(debit_exchange_amount):
    #                     if debit_vals.get('record'):
    #                         exchange_lines_to_fix += debit_vals['record']
    #                     amounts_list.append({'amount_residual': debit_exchange_amount})
    #                     remaining_debit_amount -= debit_exchange_amount
    #                     if debit_vals['currency'] == company_currency:
    #                         remaining_debit_amount_curr -= debit_exchange_amount
    #             else:
    #                 # Create an exchange difference ensuring the rate between the residual amounts expressed in
    #                 # both foreign and company's currency is still consistent regarding the rate between
    #                 # 'amount_currency' & 'balance'.
    #                 debit_exchange_amount = partial_debit_amount - partial_amount
    #                 if company_currency.compare_amounts(debit_exchange_amount, 0.0) > 0:
    #                     if debit_vals.get('record'):
    #                         exchange_lines_to_fix += debit_vals['record']
    #                     amounts_list.append({'amount_residual': debit_exchange_amount})
    #                     remaining_debit_amount -= debit_exchange_amount
    #                     if debit_vals['currency'] == company_currency:
    #                         remaining_debit_amount_curr -= debit_exchange_amount

    #             if credit_fully_matched:
    #                 # Create an exchange difference on the remaining amount expressed in company's currency.
    #                 credit_exchange_amount = remaining_credit_amount + partial_amount
    #                 if not company_currency.is_zero(credit_exchange_amount):
    #                     if credit_vals.get('record'):
    #                         exchange_lines_to_fix += credit_vals['record']
    #                     amounts_list.append({'amount_residual': credit_exchange_amount})
    #                     remaining_credit_amount -= credit_exchange_amount
    #                     if credit_vals['currency'] == company_currency:
    #                         remaining_credit_amount_curr -= credit_exchange_amount
    #             else:
    #                 # Create an exchange difference ensuring the rate between the residual amounts expressed in
    #                 # both foreign and company's currency is still consistent regarding the rate between
    #                 # 'amount_currency' & 'balance'.
    #                 credit_exchange_amount = partial_amount - partial_credit_amount
    #                 if company_currency.compare_amounts(credit_exchange_amount, 0.0) < 0:
    #                     if credit_vals.get('record'):
    #                         exchange_lines_to_fix += credit_vals['record']
    #                     amounts_list.append({'amount_residual': credit_exchange_amount})
    #                     remaining_credit_amount -= credit_exchange_amount
    #                     if credit_vals['currency'] == company_currency:
    #                         remaining_credit_amount_curr -= credit_exchange_amount

    #         if exchange_lines_to_fix:
    #             res['exchange_vals'] = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
    #                 amounts_list,
    #                 exchange_date=max(debit_vals['date'], credit_vals['date']),
    #             )

    #     # ==== Create partials ====

    #     remaining_debit_amount -= partial_amount
    #     remaining_credit_amount += partial_amount
    #     remaining_debit_amount_curr -= partial_debit_amount_currency
    #     remaining_credit_amount_curr += partial_credit_amount_currency

    #     res['partial_vals'] = {
    #         'amount': partial_amount,
    #         'debit_amount_currency': partial_debit_amount_currency,
    #         'credit_amount_currency': partial_credit_amount_currency,
    #         'debit_move_id': debit_vals.get('record') and debit_vals['record'].id,
    #         'credit_move_id': credit_vals.get('record') and credit_vals['record'].id,
    #     }

    #     debit_vals['amount_residual'] = remaining_debit_amount
    #     debit_vals['amount_residual_currency'] = remaining_debit_amount_curr
    #     credit_vals['amount_residual'] = remaining_credit_amount
    #     credit_vals['amount_residual_currency'] = remaining_credit_amount_curr

    #     if debit_fully_matched:
    #         res['debit_vals'] = None
    #     if credit_fully_matched:
    #         res['credit_vals'] = None
    #     return res                

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