# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import formatLang


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type",default='percent', precompute=True)
    discount = fields.Float(
        string="Discount",
        digits='Discount',
        store=True, readonly=False, precompute=True)
    discount_amt = fields.Monetary(string='Discount Amount', store=True,  compute='_compute_amount')      
   
    @api.depends('product_qty', 'price_unit', 'taxes_id','discount','discount_type')
    def _compute_amount(self):
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']
            
            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax
            })

            if line.discount_type=='amount' and line.discount:
                line.update({
                'discount_amt': line.product_qty*line.discount,
                })
            elif line.discount_type=='percent' and line.discount:
                line.update({
                'discount_amt': line.price_subtotal - (line.price_subtotal * (1 - line.discount/100)),
                })
            else:
                line.update({
                'discount_amt': 0,
                })

    

    def _prepare_account_move_line(self, move=False):
        res:dict =  super()._prepare_account_move_line(move=False)
        res.update({'discount':self.discount,'discount_type':self.discount_type})
        return res

class PurchaseOrder(models.Model):
    _inherit = "purchase.order" 

    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type")
    discount = fields.Float(
        string="Discount",
        digits='Discount',
        store=True, readonly=False)
    discount_amt = fields.Monetary(string='Discount Amount', store=True, readonly=True, compute='_amount_all')
    global_discount = fields.Boolean(string="Global Discount",default=False)
    discount_account_id = fields.Many2one('account.account',string="Global Discount Acount")
    line_discount_account_id = fields.Many2one('account.account',string="Line Discount Acount")
    line_discount = fields.Monetary(string='Line Discount', store=True, readonly=True, compute='_amount_all')
    order_discount = fields.Monetary(string='Order Discount', store=True, readonly=True, compute='_amount_all')

    # @api.constrains('global_discount')
    # def check_discount_amt(self):
    #     if self.global_discount:
    #         for line in self.order_line:
    #             line.discount = 0
    #             line.discount_amt = 0
    #             line.discount_type = None
    #     else:
    #         self.discount = 0
    #         self.discount_amt = 0
    #         self.discount_type = None
    

    @api.depends('order_line.price_total','discount_type','discount','order_line.discount_amt')
    def _amount_all(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)

            if order.company_id.tax_calculation_rounding_method == 'round_globally':
                tax_results = self.env['account.tax']._compute_taxes([
                    line._convert_to_tax_base_line_dict()
                    for line in order_lines
                ])
                totals = tax_results['totals']
                amount_untaxed = totals.get(order.currency_id, {}).get('amount_untaxed', 0.0)
                amount_tax = totals.get(order.currency_id, {}).get('amount_tax', 0.0)
            else:
                amount_untaxed = sum(order_lines.mapped('price_subtotal'))
                amount_tax = sum(order_lines.mapped('price_tax'))
                
            order.line_discount = order.order_discount = order.discount_amt = 0

            if sum(order_lines.mapped('discount_amt')) > 0:
                order.line_discount = sum(order_lines.mapped('discount_amt'))
            if order.discount or order.discount_type:
                if order.discount_type=='amount' and order.discount:
                    order.order_discount = order.discount
                elif order.discount_type=='percent' and order.discount:
                    order.order_discount = (amount_untaxed-order.line_discount)*(order.discount / 100.0)
                else:
                    order.order_discount = 0

                order.amount_untaxed = amount_untaxed 
                order.amount_tax = amount_tax
                order.amount_total = order.amount_untaxed + order.amount_tax
                order.discount_amt = order.order_discount+order.line_discount
            else:
                order.discount_amt = order.order_discount+order.line_discount
                order.amount_untaxed = amount_untaxed
                order.amount_tax = amount_tax
                order.amount_total = order.amount_untaxed + order.amount_tax

            

            order.amount_total = order.amount_total - order.discount_amt       


    @api.depends_context('lang')
    @api.depends('order_line.taxes_id', 'order_line.price_subtotal', 'amount_total', 'amount_untaxed','discount_amt')
    def _compute_tax_totals(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            order.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict() for x in order_lines],
                order.currency_id or order.company_id.currency_id,
            )
            if order.discount_amt:
                amt_total = order.tax_totals['amount_total']-order.discount_amt
                order.tax_totals.update({
                    'amount_total': order.currency_id.round(amt_total) if order.currency_id else amt_total,
                    'formatted_amount_total': formatLang(self.env, amt_total, currency_obj=order.currency_id),
                })


    def _prepare_invoice(self):
        result = super(PurchaseOrder, self)._prepare_invoice()        
        result.update({'discount':self.discount,'discount_type':self.discount_type,'global_discount':self.global_discount,'discount_account_id':self.discount_account_id and self.discount_account_id.id or False,'line_discount_account_id':self.line_discount_account_id and self.line_discount_account_id.id or False,'invoice_date':self.date_order})
        return result

                