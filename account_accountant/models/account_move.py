# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.osv import expression


class AccountMove(models.Model):
    _inherit = "account.move"

    # Technical field to keep the value of payment_state when switching from invoicing to accounting
    # (using invoicing_switch_threshold setting field). It allows keeping the former payment state, so that
    # we can restore it if the user misconfigured the switch date and wants to change it.
    payment_state_before_switch = fields.Char(string="Payment State Before Switch", copy=False)
    origin_document = fields.Char("Origin Document",compute="_compute_origin_document_of_invoice")

    @api.model
    def _get_invoice_in_payment_state(self):
        # OVERRIDE to enable the 'in_payment' state on invoices.
        return 'in_payment'
    
    def _compute_origin_document_of_invoice(self):
        for res in self:
            source_orders = res.line_ids.sale_line_ids.order_id
            source_purchases = res.line_ids.purchase_line_id.order_id
            if source_orders:
                res.origin_document = ', '.join(source_orders.mapped('name'))
            elif source_purchases:
                res.origin_document = ', '.join(source_purchases.mapped('name'))
            elif hasattr(res, 'repair_quotation_id'):
                if res.repair_quotation_id:
                    res.origin_document = res.repair_quotation_id.name
                else:
                    res.origin_document = False
            else:
                res.origin_document = False
                

    def action_post(self):
        # EXTENDS 'account' to trigger the CRON auto-reconciling the statement lines.
        res = super().action_post()
        if self.statement_line_id and not self._context.get('skip_statement_line_cron_trigger'):
            self.env.ref('account_accountant.auto_reconcile_bank_statement_line')._trigger()
        return res

    def action_open_bank_reconciliation_widget(self):
        return self.statement_line_id._action_open_bank_reconciliation_widget(
            default_context={
                'search_default_journal_id': self.statement_line_id.journal_id.id,
                'search_default_statement_line_id': self.statement_line_id.id,
                'default_st_line_id': self.statement_line_id.id,
            }
        )

    def action_open_business_doc(self):
        if self.statement_line_id:
            return self.action_open_bank_reconciliation_widget()
        else:
            return super().action_open_business_doc()

    def _get_mail_thread_data_attachments(self):
        res = super()._get_mail_thread_data_attachments()
        res += self.statement_line_id.statement_id.attachment_ids
        return res


    def action_reset_to_draft(self):
        for res in self:
            res.button_draft()
            res.action_post()
class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = "account.move.line"

    move_attachment_ids = fields.One2many('ir.attachment', compute='_compute_attachment')

    def _compute_attachment(self):
        for record in self:
            record.move_attachment_ids = self.env['ir.attachment'].search(expression.OR(record._get_attachment_domains()))

    def action_reconcile(self):
        """ This function is called by the 'Reconcile' action of account.move.line's
        tree view. It performs reconciliation between the selected lines, or, if they
        only consist of payable and receivable lines for the same partner, it opens
        the transfer wizard, pre-filled with the necessary data to transfer
        the payable/receivable open balance into the receivable/payable's one.
        This way, we can simulate reconciliation between receivable and payable
        accounts, using an intermediate account.move doing the transfer.
        """
        all_accounts = self.mapped('account_id')
        account_types = all_accounts.mapped('account_type')
        all_partners = self.mapped('partner_id')

        if len(all_accounts) == 2 and 'liability_payable' in account_types and 'asset_receivable' in account_types:

            if len(all_partners) != 1:
                raise UserError(_("You cannot reconcile the payable and receivable accounts of multiple partners together at the same time."))

            # In case we have only lines for one (or no) partner and they all
            # are located on a single receivable or payable account,
            # we can simulate reconciliation between them with a transfer entry.
            # So, we open the wizard allowing to do that, pre-filling the values.

            max_total = 0
            max_account = None
            for account in all_accounts:
                account_total = abs(sum(line.balance for line in self.filtered(lambda x: x.account_id == account)))
                if not max_account or max_total < account_total:
                    max_account = account
                    max_total = account_total

            wizard = self.env['account.automatic.entry.wizard'].create({
                'move_line_ids': [(6, 0, self.ids)],
                'destination_account_id': max_account.id,
                'action': 'change_account',
            })

            return {
                'name': _("Transfer Accounts"),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.automatic.entry.wizard',
                'res_id': wizard.id,
                'target': 'new',
                'context': {'active_ids': self.ids, 'active_model': 'account.move.line'},
            }

        return {
            'type': 'ir.actions.client',
            'name': _('Reconcile'),
            'tag': 'manual_reconciliation_view',
            'binding_model_id': self.env['ir.model.data']._xmlid_to_res_id('account.model_account_move_line'),
            'binding_type': 'action',
            'binding_view_types': 'list',
            'context': {'active_ids': self.ids, 'active_model': 'account.move.line'},
        }
    
    def _prepare_exchange_difference_move_vals(self, amounts_list, company=None, exchange_date=None, **kwargs):
        """ Prepare values to create later the exchange difference journal entry.
        The exchange difference journal entry is there to fix the debit/credit of lines when the journal items are
        fully reconciled in foreign currency.
        :param amounts_list:    A list of dict, one for each aml.
        :param company:         The company in case there is no aml in self.
        :param exchange_date:   Optional date object providing the date to consider for the exchange difference.
        :return:                A python dictionary containing:
            * move_vals:    A dictionary to be passed to the account.move.create method.
            * to_reconcile: A list of tuple <move_line, sequence> in order to perform the reconciliation after the move
                            creation.
        """
        datas = super()._prepare_exchange_difference_move_vals(amounts_list, company, exchange_date, **kwargs)  
        if datas and datas["move_vals"]:
            line_ids = datas["move_vals"]["line_ids"]
            if line_ids and self.move_id and self.move_id.payment_id:
                payment_id = self[0].move_id.payment_id
                datas["move_vals"]["department_id"] = payment_id.department_id.id
                for line_id in line_ids:
                    if line_id[-1]:
                        analytic_dct = {}
                        if payment_id.project_id:
                            line_id[-1]["project_id"] = payment_id.project_id.id
                            if payment_id.project_id.analytic_project_id:
                                analytic_dct[payment_id.project_id.analytic_project_id.id] = 100
                        if payment_id.division_id:
                            line_id[-1]["division_id"] = payment_id.division_id.id
                            if payment_id.division_id.analytic_account_id:
                                analytic_dct[payment_id.division_id.analytic_account_id.id] = 100
                        line_id[-1]["analytic_distribution"] = analytic_dct
        return datas
    
