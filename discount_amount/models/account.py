# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.osv import expression
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools import frozendict
from contextlib import ExitStack, contextmanager

from collections import defaultdict
import math
import re

class AccountTax(models.Model):
    _inherit = 'account.tax'
    _description = 'Tax'

    @api.model
    def _compute_taxes_for_single_line(self, base_line, handle_price_include=True, include_caba_tags=False, early_pay_discount_computation=None, early_pay_discount_percentage=None):
        orig_price_unit_after_discount = base_line['price_unit']
        price_unit_after_discount = orig_price_unit_after_discount
        taxes = base_line['taxes']._origin
        currency = base_line['currency'] or self.env.company.currency_id
        rate = base_line['rate']

        if early_pay_discount_computation in ('included', 'excluded'):
            remaining_part_to_consider = (100 - early_pay_discount_percentage) / 100.0
            price_unit_after_discount = remaining_part_to_consider * price_unit_after_discount

        if taxes:
            taxes_res = taxes.with_context(**base_line['extra_context']).compute_all(
                price_unit_after_discount,
                currency=currency,
                quantity=base_line['quantity'],
                product=base_line['product'],
                partner=base_line['partner'],
                is_refund=base_line['is_refund'],
                handle_price_include=base_line['handle_price_include'],
                include_caba_tags=include_caba_tags,
            )

            to_update_vals = {
                'tax_tag_ids': [Command.set(taxes_res['base_tags'])],
                'price_subtotal': taxes_res['total_excluded'],
                'price_total': taxes_res['total_included'],
            }

            if early_pay_discount_computation == 'excluded':
                new_taxes_res = taxes.with_context(**base_line['extra_context']).compute_all(
                    orig_price_unit_after_discount,
                    currency=currency,
                    quantity=base_line['quantity'],
                    product=base_line['product'],
                    partner=base_line['partner'],
                    is_refund=base_line['is_refund'],
                    handle_price_include=base_line['handle_price_include'],
                    include_caba_tags=include_caba_tags,
                )
                for tax_res, new_taxes_res in zip(taxes_res['taxes'], new_taxes_res['taxes']):
                    delta_tax = new_taxes_res['amount'] - tax_res['amount']
                    tax_res['amount'] += delta_tax
                    to_update_vals['price_total'] += delta_tax

            tax_values_list = []
            for tax_res in taxes_res['taxes']:
                tax_amount = tax_res['amount'] / rate
                if self.company_id.tax_calculation_rounding_method == 'round_per_line':
                    tax_amount = currency.round(tax_amount)
                tax_rep = self.env['account.tax.repartition.line'].browse(tax_res['tax_repartition_line_id'])
                tax_values_list.append({
                    **tax_res,
                    'tax_repartition_line': tax_rep,
                    'base_amount_currency': tax_res['base'],
                    'base_amount': currency.round(tax_res['base'] / rate),
                    'tax_amount_currency': tax_res['amount'],
                    'tax_amount': tax_amount,
                })

        else:
            price_subtotal = currency.round(price_unit_after_discount * base_line['quantity'])
            to_update_vals = {
                'tax_tag_ids': [Command.clear()],
                'price_subtotal': price_subtotal,
                'price_total': price_subtotal,
            }
            tax_values_list = []

        return to_update_vals, tax_values_list

    

    @api.model
    def _convert_to_tax_base_line_dict(
            self, base_line,
            partner=None, currency=None, product=None, taxes=None, price_unit=None, quantity=None,
            discount=None,discount_type=None, account=None, analytic_distribution=None, price_subtotal=None,
            is_refund=False, rate=None,
            handle_price_include=True,
            extra_context=None,
    ):
        return {
            'record': base_line,
            'partner': partner or self.env['res.partner'],
            'currency': currency or self.env['res.currency'],
            'product': product or self.env['product.product'],
            'taxes': taxes or self.env['account.tax'],
            'price_unit': price_unit or 0.0,
            'quantity': quantity or 0.0,
            'account': account or self.env['account.account'],
            'analytic_distribution': analytic_distribution,
            'price_subtotal': price_subtotal or 0.0,
            'is_refund': is_refund,
            'rate': rate or 1.0,
            'handle_price_include': handle_price_include,
            'extra_context': extra_context or {},
        }
    
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type",default='percent')
    discount_amt = fields.Monetary(
        string='Discount Amount',
        compute='_compute_totals', store=True, readonly=True,
        tracking=True,
    )
    disc_key = fields.Binary(compute='_compute_disc_key', exportable=False)
    is_discount = fields.Boolean(default=False)
    add_type = fields.Selection([('amount','Amt'),('percentage','%')],string='Additional Type',default="percentage")
    add_amt = fields.Float('Additional Rate',copy=False)
    account_type = fields.Selection(related='account_id.account_type',store=True)
    

    @api.depends('discount_amt')
    def _compute_disc_key(self):
        for line in self:
            if line.display_type == 'epd' and line.discount_amt:
                line.disc_key = frozendict({
                    'move_id': line.move_id.id,
                    'date_maturity': fields.Date.to_date(line.date_maturity),
                    
                })
            else:
                line.disc_key = False


    @api.depends('quantity', 'discount','discount_type', 'price_unit', 'tax_ids', 'currency_id')
    def _compute_totals(self):
        for line in self:
            if line.display_type != 'product':
                line.price_total = line.price_subtotal = False
            # Compute 'price_subtotal'.
            line_discount_price_unit = line.price_unit
            subtotal = line.quantity * line_discount_price_unit

            # Compute 'price_total'.
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.price_subtotal = taxes_res['total_excluded']
                line.price_total = taxes_res['total_included']
            else:
                line.price_total = line.price_subtotal = subtotal
                if line.discount_type=='amount' and line.discount:
                    line.update({
                    'discount_amt': line.quantity*line.discount,
                    })
                elif line.discount_type=='percent' and line.discount:
                    line.update({
                    'discount_amt': line.price_subtotal - (line.price_subtotal * (1 - line.discount/100)),
                    })
                else:
                    line.update({
                    'discount_amt': 0,
                    })
        

    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.
        :return: A python dictionary.
        """
        self.ensure_one()
        is_invoice = self.move_id.is_invoice(include_receipts=True)
        sign = -1 if self.move_id.is_inbound(include_receipts=True) else 1

        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.partner_id,
            currency=self.currency_id,
            product=self.product_id,
            taxes=self.tax_ids,
            price_unit=self.price_unit if is_invoice else self.amount_currency,
            quantity=self.quantity if is_invoice else 1.0,
            account=self.account_id,
            analytic_distribution=self.analytic_distribution,
            price_subtotal=sign * self.amount_currency,
            is_refund=self.is_refund,
            rate=(abs(self.amount_currency) / abs(self.balance)) if self.balance else 1.0,
        )
    
class AccountMove(models.Model):
    _inherit = "account.move"

    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type",default='percent')
    discount = fields.Float(
        string="Discount",
        digits='Discount',
        store=True, readonly=False)
    discount_amt = fields.Monetary(
        string='Discount Amount',
        compute='_compute_amount', store=True, readonly=True,
        tracking=True,
    )
    amount_add = fields.Float('Additional Amount',compute='_compute_amount',store=True)
    discount_amt_currency = fields.Monetary(string="Discount Amount",compute='_compute_amount_currency',store=True)
    line_discount_amt_currency = fields.Monetary(string="Line Discount Amount",store=True)
    order_discount_amt_currency = fields.Monetary(string="Order Discount Amount",store=True)
    global_discount = fields.Boolean(string="Global Discount",default=False)

    compute_all_disc = fields.Binary(compute='_compute_all_disc', exportable=False)
    compute_all_disc_dirty = fields.Boolean(compute='_compute_all_disc')
    discount_account_id = fields.Many2one('account.account',string="Global Discount Acount")
    line_discount_account_id = fields.Many2one('account.account',string="Line Discount Acount")
    order_discount = fields.Monetary(
        string='Order Discount',
        store=True, readonly=True,
        tracking=True,
    )
    line_discount = fields.Monetary(
        string='Line Discount',
        store=True, readonly=True,
        tracking=True,
    )

    @api.onchange('discount_account_id')
    def onchnage_discount_account(self):
        for line in self.line_ids:
            if line.name=='Discount' and self.discount_account_id:
                line.update({'account_id':self.discount_account_id.id})
    
    def action_post(self):
        if self.commercial_sale_id:
            if len(self.commercial_sale_id.order_line.invoice_lines.move_id.filtered(lambda move:move.state == 'draft')) > 0:
                raise ValidationError('Can not confirm commission bill when invoices are not confiemd yet.')
        return super().action_post()
    
    @contextmanager
    def _sync_dynamic_lines(self, container):
        with self._disable_recursion(container, 'skip_invoice_sync') as disabled:
            if disabled:
                yield
                return
            def update_containers():
                # Only invoice-like and journal entries in "auto tax mode" are synced
                tax_container['records'] = container['records'].filtered(lambda m: (m.is_invoice(True) or m.line_ids.tax_ids and not m.tax_cash_basis_origin_move_id))
                invoice_container['records'] = container['records'].filtered(lambda m: m.is_invoice(True))
                misc_container['records'] = container['records'].filtered(lambda m: m.move_type == 'entry' and not m.tax_cash_basis_origin_move_id)

            tax_container, invoice_container, misc_container = ({} for __ in range(3))
            update_containers()
            with ExitStack() as stack:
                stack.enter_context(self._sync_dynamic_line(
                    existing_key_fname='term_key',
                    needed_vals_fname='needed_terms',
                    needed_dirty_fname='needed_terms_dirty',
                    line_type='payment_term',
                    container=invoice_container,
                ))
                stack.enter_context(self._sync_dynamic_line(
                    existing_key_fname='disc_key',
                    needed_vals_fname='compute_all_disc',
                    needed_dirty_fname='compute_all_disc_dirty',
                    line_type='epd',
                    container=invoice_container,
                ))
                stack.enter_context(self._sync_unbalanced_lines(misc_container))
                stack.enter_context(self._sync_rounding_lines(invoice_container))
                stack.enter_context(self._sync_dynamic_line(
                    existing_key_fname='tax_key',
                    needed_vals_fname='line_ids.compute_all_tax',
                    needed_dirty_fname='line_ids.compute_all_tax_dirty',
                    line_type='tax',
                    container=tax_container,
                ))
                stack.enter_context(self._sync_dynamic_line(
                    existing_key_fname='epd_key',
                    needed_vals_fname='line_ids.epd_needed',
                    needed_dirty_fname='line_ids.epd_dirty',
                    line_type='epd',
                    container=invoice_container,
                ))
                stack.enter_context(self._sync_invoice(invoice_container))
                line_container = {'records': self.line_ids}
                with self.line_ids._sync_invoice(line_container):
                    yield
                    line_container['records'] = self.line_ids
                update_containers()

    @api.depends('discount_amt')
    def _compute_all_disc(self):
        compute_all_disc  = {}
        compute_all_disc2 = {}
        compute_line_disc = {}
        compute_order_disc ={}
        res = {}
        disc_amt = line_disc = order_disc = 0
        for move in self:
            existings = move.line_ids.filtered(lambda x:x.name == 'Global Discount' or x.name == 'Line Discount')
            for existing in existings:
                if move.move_type in ('in_refund','out_refund') and sum(move.line_ids.mapped('debit'))!=sum(move.line_ids.mapped('credit')):
                    existing.unlink()
                elif move.move_type not in ('in_refund','out_refund'):
                    if existing and round(abs(sum(existings.mapped('balance'))),2)!=round(existing.move_id.discount_amt,2):
                        existing.with_context(force_delete=True).unlink()
            move.compute_all_disc = False
            disc_amt=move.discount_amt
            line_disc = move.line_discount
            order_disc = move.order_discount
            move.compute_all_disc_dirty = True
            if line_disc:
                disc_vals = compute_line_disc.setdefault(
                    frozendict({
                        'move_id': move.id,
                        'account_id': move.line_discount_account_id and move.line_discount_account_id.id or False,
                        'display_type': 'epd',
                        'name': _("Line Discount"),

                    }),
                    {

                        'amount_currency': 0.0,
                        'balance': 0.0,
                        'price_subtotal': 0.0,
                        'analytic_distribution':False
                    },
                )

                if move.direction_sign>0:
                    disc_vals['amount_currency'] -= line_disc/move.exchange_rate
                    disc_vals['balance'] -= line_disc
                    disc_vals['price_subtotal'] -= line_disc
                    disc_vals['analytic_distribution'] = move.line_ids and move.line_ids[0].analytic_distribution or False
                else:
                    disc_vals['amount_currency'] += line_disc/move.exchange_rate
                    disc_vals['balance'] += line_disc
                    disc_vals['price_subtotal'] += line_disc
                    disc_vals['analytic_distribution'] = move.line_ids and move.line_ids[0].analytic_distribution or False

            if order_disc:
                order_disc_vals = compute_order_disc.setdefault(
                    frozendict({
                        'move_id': move.id,
                        'account_id': move.discount_account_id and move.discount_account_id.id or False,
                        'display_type': 'epd',
                        'name': _("Global Discount"),

                    }),
                    {

                        'amount_currency': 0.0,
                        'balance': 0.0,
                        'price_subtotal': 0.0,
                        'analytic_distribution':False
                    },
                )

                if move.direction_sign>0:
                    order_disc_vals['amount_currency'] -= order_disc/move.exchange_rate
                    order_disc_vals['balance'] -= order_disc
                    order_disc_vals['price_subtotal'] -= order_disc
                    order_disc_vals['analytic_distribution'] = move.line_ids and move.line_ids[0].analytic_distribution or False
                else:
                    order_disc_vals['amount_currency'] += order_disc/move.exchange_rate
                    order_disc_vals['balance'] += order_disc
                    order_disc_vals['price_subtotal'] += order_disc
                    order_disc_vals['analytic_distribution'] = move.line_ids and move.line_ids[0].analytic_distribution or False
        if disc_amt:  
            compute_all_disc = {k: frozendict(v) for k, v in compute_order_disc.items()}
            compute_all_disc2 = {k: frozendict(v) for k, v in compute_line_disc.items()}
            compute_all_disc.update(compute_all_disc2)    
            move.compute_all_disc = {k: frozendict(v) for k, v in compute_all_disc.items()}
            
            
         

    # @api.constrains('global_discount')
    # def check_discount_amt(self):
    #     for move in self:
    #         if move.global_discount:
    #             for line in move.line_ids:
    #                 line.discount = 0
    #                 line.discount_amt = 0
    #                 line.discount_type = None
    #         else:
    #             move.discount = 0
    #             move.discount_amt = 0
    #             move.discount_type = None
    
    # @api.onchange('discount_account_id')
    # def onchange_discount_account_id(self):
    #     if self.global_discount:
    #         self.discount = 0
    #         self.discount_amt = 0
    #         self.discount_type = None
            
    #     else:
    #         for line in self.line_ids:
    #             line.discount = 0
    #             line.discount_amt = 0
    #             line.discount_type = None
                
    @api.depends('discount_amt')
    def _compute_amount_currency(self):
        for res in self:
            if res:
                if res.discount_amt:
                    if hasattr(res,'exchange_rate'):
                        if res.line_discount:
                            res.line_discount_amt_currency = res.line_discount/res.exchange_rate
                        if res.order_discount:
                            res.order_discount_amt_currency = res.order_discount/res.exchange_rate
                        res.discount_amt_currency = res.discount_amt/res.exchange_rate
                    else:
                        res.discount_amt_currency = res.discount_amt
                        res.line_discount_amt_currency = res.line_discount
                        res.order_discount_amt_currency = res.order_discount
                else:
                    res.discount_amt_currency = 0
                    res.line_discount_amt_currency = 0
                    res.order_discount_amt_currency = 0


    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id',
        'line_ids.discount_amt',
        'discount',
        'discount_type',
        'state',
        'line_ids.add_type',
        'line_ids.add_amt')
    def _compute_amount(self):
        for move in self:
            total_untaxed, total_untaxed_currency = 0.0, 0.0
            total_tax, total_tax_currency = 0.0, 0.0
            total_residual, total_residual_currency = 0.0, 0.0
            total, total_currency = 0.0, 0.0
            amount_add = 0.0
            for inv_line in move.invoice_line_ids:
                amount_add += (inv_line.add_amt*inv_line.quantity) if inv_line.add_type == 'amount' else ((inv_line.price_unit*inv_line.quantity) * (inv_line.add_amt /100))
            for line in move.line_ids:
                if move.is_invoice(True):
                    # === Invoices ===
                    
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type in ('product', 'rounding'):
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total_currency += line.amount_currency
                        total += line.balance
                        
                        
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        # if line.move_id.exchange_rate>1:
                        #     total_currency += line.balance/line.move_id.exchange_rate
                        # else:
                        total_currency += line.amount_currency

            total_discount_amt = total_line_disc = total_order_disc = 0.0
            if sum(move.invoice_line_ids.mapped('discount_amt')) > 0:
                total_line_disc += sum(move.invoice_line_ids.mapped('discount_amt'))*move.exchange_rate

            if move.discount or move.discount_type:
                if move.discount_type=='amount' and move.discount:
                    total_order_disc = move.discount*move.exchange_rate
                elif move.discount_type=='percent' and move.discount:
                    total_order_disc = ((abs(total_untaxed)-total_line_disc) * (move.discount / 100.0))
                else:
                    total_order_disc = 0
            total_discount_amt += total_order_disc+total_line_disc

            exhange_rate = move.exchange_rate != 0.0 and move.exchange_rate or 1.0
            
            sign = move.direction_sign   
            if move.move_type in ('out_refund'):
                total_discount_amt = total_discount_amt*sign
                total_order_disc = total_order_disc*sign
                total_line_disc = total_line_disc*sign

            # if tax_line:
            #     if not move.tax_id:
            #         tax_line.unlink()
            #     else:
            #         tax_amount = (move.tax_id.amount / 100) * ((sign * total_untaxed_currency)-total_discount_amt )                
            #         pp_id = self.env['product.product'].search([('product_tmpl_id','=',move.tax_id.product_template_id.id)]) 
            #         if not pp_id:
            #             raise ValidationError("There is no product associated with the tax!!")
            #         tax_line.product_id = pp_id
            #         tax_line.quantity = 1
            #         tax_line.product_uom_id = pp_id.uom_id
            #         tax_line.price_unit = tax_amount 
            #         tax_amount_signed = sign > 0 and sign * tax_amount or sign * tax_amount            
            #         total_tax += tax_amount_signed 
            #         total_tax_currency += tax_amount_signed
            #         total += tax_amount_signed
            #         total_currency += tax_amount_signed                     
            # else:
            #     if move.tax_id: 
            #         tax_amount = (move.tax_id.amount / 100) * ((sign * total_untaxed_currency)-total_discount_amt )
            #         pp_id = self.env['product.product'].search([('product_tmpl_id','=',move.tax_id.product_template_id.id)]) 
            #         if not pp_id:
            #             raise ValidationError("There is no product associated with the tax!!")                    
            #         move.invoice_line_ids = [Command.create({
            #             "product_id":pp_id.id,
            #             "product_uom_id":pp_id.uom_id.id,
            #             "quantity":1,
            #             "price_unit":tax_amount,
            #             "is_tax_line":True,
            #         })]   
            #         tax_amount_signed = sign > 0 and sign * tax_amount or sign * tax_amount          
            #         total_tax += tax_amount_signed 
            #         total_tax_currency += tax_amount_signed
            #         total += tax_amount_signed
            #         total_currency += tax_amount_signed                                 
            move.order_discount = total_order_disc
            move.line_discount = total_line_disc
            move.discount_amt = total_discount_amt
            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * (total_tax_currency)
            move.amount_total = sign>0 and sign * (total_currency-(total_discount_amt/exhange_rate)) or sign * (total_currency+(total_discount_amt/exhange_rate))
            move.amount_residual = -sign * total_residual_currency
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total-total_discount_amt) if move.move_type == 'entry' else sign>0 and -total+total_discount_amt or sign*(total+total_discount_amt)
            move.amount_residual_signed = total_residual
            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)
            move.amount_add = amount_add
            move.exchange_rate = exhange_rate

    @api.depends('invoice_payment_term_id', 'invoice_date', 'currency_id', 'amount_total_in_currency_signed', 'invoice_date_due')
    def _compute_needed_terms(self):
        for invoice in self:
            is_draft = invoice.id != invoice._origin.id
            invoice.needed_terms = {}
            invoice.needed_terms_dirty = True
            sign = 1 if invoice.is_inbound(include_receipts=True) else -1
            if invoice.is_invoice(True) and invoice.invoice_line_ids:
                if invoice.invoice_payment_term_id:
                    if is_draft:
                        tax_amount_currency = 0.0
                        untaxed_amount_currency = 0.0
                        for line in invoice.invoice_line_ids:
                            untaxed_amount_currency += line.price_subtotal
                            for tax_result in (line.compute_all_tax or {}).values():
                                tax_amount_currency += -sign * tax_result.get('amount_currency', 0.0)
                        untaxed_amount = untaxed_amount_currency
                        tax_amount = tax_amount_currency
                    else:
                        tax_amount_currency = invoice.amount_tax * sign
                        tax_amount = invoice.amount_tax_signed
                        untaxed_amount_currency = invoice.amount_untaxed * sign
                        untaxed_amount = invoice.amount_untaxed_signed
                    invoice_payment_terms = invoice.invoice_payment_term_id._compute_terms(
                        date_ref=invoice.invoice_date or invoice.date or fields.Date.today(),
                        currency=invoice.currency_id,
                        tax_amount_currency=tax_amount_currency,
                        tax_amount=tax_amount,
                        untaxed_amount_currency=untaxed_amount_currency,
                        untaxed_amount=untaxed_amount,
                        company=invoice.company_id,
                        sign=sign
                    )
                    for term in invoice_payment_terms:
                        key = frozendict({
                            'move_id': invoice.id,
                            'date_maturity': fields.Date.to_date(term.get('date')),
                            'discount_date': term.get('discount_date'),
                            'discount_percentage': term.get('discount_percentage'),
                        })
                        values = {
                            'balance': term['company_amount']-(invoice.discount_amt*sign),
                            'amount_currency': term['foreign_amount']-((invoice.discount_amt*sign)/invoice.exchange_rate),
                            'discount_amount_currency': term['discount_amount_currency'] or 0.0,
                            'discount_balance': term['discount_balance'] or 0.0,
                            'discount_date': term['discount_date'],
                            'discount_percentage': term['discount_percentage'],
                        }
                        if key not in invoice.needed_terms:
                            invoice.needed_terms[key] = values
                        else:
                            invoice.needed_terms[key]['balance'] += values['balance']
                            invoice.needed_terms[key]['amount_currency'] += values['amount_currency']
                else:
                    invoice.needed_terms[frozendict({
                        'move_id': invoice.id,
                        'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
                        'discount_date': False,
                        'discount_percentage': 0
                    })] = {
                        'balance': invoice.amount_total_signed,
                        'amount_currency': invoice.amount_total_in_currency_signed,
                    }


    def _reverse_moves(self, default_values_list=None, cancel=False):
        res = super()._reverse_moves(default_values_list, cancel)
        if res:
            for line in res.invoice_line_ids:
                if self.move_type == 'out_invoice' and line.move_id.partner_id.partner_return_account_id:
                    line.update({'account_id':line.move_id.partner_id.partner_return_account_id.id or False})
                if self.move_type == 'out_invoice' and line.product_id.categ_id.account_sale_return_id:
                    line.update({'account_id':line.product_id.categ_id.account_sale_return_id.id or False})
        return res