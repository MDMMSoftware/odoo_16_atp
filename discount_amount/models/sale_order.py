# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import formatLang



class SaleOrderLine(models.Model):
    """inherited sale order line"""
    _inherit = 'sale.order.line'

    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type",default='percent')
    discount_amt = fields.Monetary(string='Discount Amount', store=True,  compute='_compute_amount')
    commercial_type = fields.Selection([('amount','Amt'),('percentage','%')],string='Commission Type',default="percentage")
    commercial_amt = fields.Float('Commission Rate',copy=False)
    add_type = fields.Selection([('amount','Amt'),('percentage','%')],string='Additional Type',default="percentage")
    add_amt = fields.Float('Additional Rate',copy=False)
   
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id','discount_type')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })

            if line.discount_type=='amount' and line.discount:
                line.update({
                'discount_amt': line.discount,
                })
            elif line.discount_type=='percent' and line.discount:
                line.update({
                'discount_amt': line.price_subtotal - (line.price_subtotal * (1 - line.discount/100)),
                })
            else:
                line.update({
                'discount_amt': 0,
                })


    def _prepare_invoice_line(self, **optional_values):    
        lines = super()._prepare_invoice_line(**optional_values)
        if not self.order_id.partner_id.partner_income_account_id:
            updated_dct = {"discount_type": self.discount_type,'add_type':self.add_type,'add_amt': self.add_amt}
        else:
            updated_dct = {"discount_type": self.discount_type,'account_id':self.order_id.partner_id.partner_income_account_id.id or False,'add_type':self.add_type,'add_amt': self.add_amt}
        lines.update(updated_dct)
        return lines
    

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    discount_type =  fields.Selection([('percent','%'),('amount','Amt')],string="Discount Type")
    discount = fields.Float(
        string="Discount",
        digits='Discount',
        store=True, readonly=False)
    discount_amt = fields.Monetary(string='Discount Amount', store=True, readonly=True, compute='_compute_amounts')
    global_discount = fields.Boolean(string="Global Discount",default=False)
    discount_account_id = fields.Many2one('account.account',string="Global Discount Acount")
    is_commission = fields.Boolean(string="Is Commission?",default=False)
    amount_commercial = fields.Float('Commission',compute='_compute_amounts',store=True)
    invisible_commercial = fields.Boolean(compute='compute_invisible_commercial')
    commercial_move_id = fields.Many2one('account.move',string="Commission Bill",copy=False)
    amount_add = fields.Float('Additional Amount',compute='_compute_amounts',store=True)
    extra_amt = fields.Boolean('Additional Amount')
    line_discount = fields.Monetary(string='Line Discount', store=True, readonly=True, compute='_compute_amounts')
    order_discount = fields.Monetary(string='Order Discount', store=True, readonly=True, compute='_compute_amounts')
    
    def action_open_commercial(self):
        return {
            'name': _('Commissions Bills'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.commercial_move_id.ids)],              
        } 
    
    def action_create_commercial(self):
        for record in self:
            if record.partner_id.commission_setting != 'allow':
                raise ValidationError('Commission Bill is not allowed for the customer!')
            if record.amount_commercial > 0.0 and record.is_commission:
                invoice_obj = self.env['account.move']
                invoice_line_obj = self.env['account.move.line']
                journal_obj = self.env['account.journal']
                account_obj = self.env['account.account']
                expense_acc = None
                jr_ids = journal_obj.search([('type','=','purchase'),('company_id','=',self.env.company.id)],limit=1) 
                product = self.env['product.product'].search([('product_tmpl_id.commercial_ok','=',True),('type','=','service')],limit=1)              
                if not product:
                    raise ValidationError('Service Product is not Defined.')
                if product.property_account_expense_id:
                    expense_acc = product.property_account_expense_id
                if not expense_acc and product.categ_id.property_account_expense_categ_id:
                    expense_acc = product.categ_id.property_account_expense_categ_id
                if not expense_acc:
                    raise ValidationError('Expense account is not defined')
                payable_acc = self.partner_id.property_account_payable_id
                # 1) Create invoices.
                invoice_vals_list = []
               
                # Invoice values.
                invoice_vals = {
                    # 'name': 'Draft' + record.name,
                    'ref': False,
                    'internal_ref':record.name,
                    'move_type': 'in_invoice',
                    'currency_id': record.currency_id.id,
                    'exchange_rate':record.exchange_rate,
                    'partner_id': record.partner_id.id,                   
                    'commercial_sale_id':record.id,
                    'journal_id':jr_ids.id,
                    'invoice_line_ids': [],
                    'invoice_date': record.date_order,
                    'company_id':record.company_id and record.company_id.id or False,
                    'branch_id':record.branch_id and record.branch_id.id or False,
                }

                line_vals = {
                    'product_id': product.id,
                    'product_uom_id':product.uom_id.id,
                    'name': str(record.name) + '|' + str(product.product_code)+'|'+payable_acc.name,
                    'quantity': 1,                    
                    'price_unit': record.amount_commercial,
                    'account_id': expense_acc.id,
                }
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

                if not invoice_vals['invoice_line_ids']:
                    raise UserError('Invalid Invoicable Line.')

                invoice_vals_list.append(invoice_vals)                
                moves = self.env['account.move'].sudo().with_context(default_type='out_invoice').create(invoice_vals_list)
                self.commercial_move_id = moves.id
                msg_txt = 'Commercial Bill Created.'
                record.message_post(body=msg_txt)
            else:
                raise ValidationError('Invalid Action.')
    
    def compute_invisible_commercial(self):
        for rec in self:
            result = False
            move_id = self.env['account.move'].search([('commercial_sale_id', '=', rec.id)],limit=1)
            if not rec.is_commission or rec.amount_commercial <= 0.0 or rec.state != 'sale' or move_id:
                result = True
            rec.invisible_commercial = result
            

    @api.onchange('partner_id')
    def onchange_partner_sale_disc(self):
        if self.partner_id:
            if self.partner_id.sale_discount_account_id:
                self.discount_account_id = self.partner_id.sale_discount_account_id.id
            else:
                self.discount_account_id = None
                
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

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total','order_line.discount_amt','order_line.commercial_amt','discount_type','discount')
    def _compute_amounts(self):
        """Compute the total amounts of the SO."""
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
            
            amount_commercial = amount_add = 0.0
            if order.is_commission or order.extra_amt:
               
                for line in order.order_line:
                    
                    amount_commercial += line.commercial_amt if line.commercial_type == 'amount' else (line.price_subtotal * line.commercial_amt /100)
                    amount_add += line.add_amt if line.add_type == 'amount' else (line.price_subtotal * line.add_amt /100)
                order.update({
                    'amount_commercial': amount_commercial,
                    'amount_add': amount_add,
                })

    
    @api.depends_context('lang')
    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed', 'currency_id','discount_type','discount')
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
        result = super(SaleOrder, self)._prepare_invoice()
        dis_acc = False
        if self.date_order:
            result.update({'invoice_date':self.date_order})
        if self.partner_id.sale_discount_account_id:
            dis_acc = self.partner_id.sale_discount_account_id.id
        result.update({'discount':self.discount,'discount_type':self.discount_type,'global_discount':self.global_discount,'discount_account_id':self.discount_account_id and self.discount_account_id.id or dis_acc})
        return result
    
    
class PartnerInherited(models.Model):
    _inherit = 'res.partner'

    commission_setting = fields.Selection([
                            # ('notify', 'Notify'),
                            ('hold', 'Hold'),
                            ('allow', 'Always Allow'),
                            ], string='Commission Type',default="hold")
    
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    commercial_ok = fields.Boolean('Commission Product?',default=False)
    
class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    commercial_ok = fields.Boolean(related='product_tmpl_id.commercial_ok',store=True)
    
    
class AccountMove(models.Model):
    _inherit = 'account.move'

    commercial_sale_id = fields.Many2one('sale.order',string="Commercial Sale")
    

class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def reverse_moves(self):
        moves = self.move_ids
        order_id = self.move_ids.line_ids.sale_line_ids.order_id
        if order_id and order_id.commercial_move_id and not order_id.commercial_move_id.reversal_move_id:
            raise UserError('You cannot cancel the invoice which has a commission bill.')

        for move in moves:
            if move.line_ids.sale_line_ids:
                if move.line_ids.sale_line_ids.order_id.is_commission:
                    if move.partner_id.commission_setting in ['hold'] and move.move_type == 'out_invoice':
                        raise ValidationError('Can not reverse this included commission.')
            
        result = super(AccountMoveReversal, self).reverse_moves()
        return result
    
    def _prepare_default_reversal(self, move=None):
        result = super(AccountMoveReversal, self)._prepare_default_reversal(move=move)
        result.update({'exchange_rate': move.exchange_rate})
        return result