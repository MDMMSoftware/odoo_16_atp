# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code
from collections import Counter

READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

class PurchaseOrder(models.Model):
    """inherited purchase order"""
    _inherit = 'purchase.order'

    location_id = fields.Many2one('stock.location','Location',required=True,domain=[('usage','=','internal')])
    internal_ref = fields.Char(string="Internal Reference")
    purchase_team_id = fields.Many2one('purchase.team',string="Purchase Team")
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, states=READONLY_STATES, change_default=True, tracking=True, domain=lambda self:self._get_partner_domain())


    def _get_partner_domain(self):
        if self.env.company.allow_partner_domain_feature:
            return [
                    ('partner_type','=','vendor'),
                    '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
                    ]
                        
        return [
                '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
                ]
    

    @api.onchange('picking_type_id')
    def onchange_location_id(self):
        if self.picking_type_id:
            return {'domain': {'location_id': [('warehouse_id', 'in', self.picking_type_id.warehouse_id.ids),('usage','=','internal')]}}
        

    def _get_destination_location(self):
        self.ensure_one()
        if self.location_id:
            return self.location_id.id
        if self.dest_address_id:
            return self.dest_address_id.property_stock_customer.id
        return self.picking_type_id.default_location_dest_id.id
    
    # def button_approve(self, force=False):
    #     result = super(PurchaseOrder, self).button_approve(force=force)
    #     self._create_picking()
    #     return result    
    
    def button_confirm(self):
        for order in self:
            # check condition for ap one line vendor : duty owner
            if self.partner_id and self.partner_id.partner_type == 'vendor' and self.partner_id.is_duty_owner:
                if hasattr(self.order_line[0], 'fleet_id'):
                    dct = Counter([line_id.fleet_id.id for line_id in self.order_line])
                    if False in dct:
                        raise ValidationError("Found blank fleet in the order line..")
                    if len(dct) != 1:
                        raise ValidationError("You must add same fleet in all order lines when it is associated with duty owner - vendor!!")            
            if order.state not in ['draft', 'sent']:
                continue
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()
            # Seq feature
            sequence = self.env['sequence.model']
            order.name = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.date_order,None,None)
            # Deal with double validation process
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
            for picking_id in self.picking_ids:
                for stock_move_id in picking_id.move_ids:
                    if hasattr(stock_move_id, 'project_id'):
                        stock_move_id.write({"project_id":  stock_move_id.purchase_line_id.project_id})
                    stock_move_id.write({"division_id": stock_move_id.purchase_line_id.division_id})
                    stock_move_id.write({"fleet_id":  stock_move_id.purchase_line_id.fleet_id})                
                picking_id.write({'internal_ref': self.internal_ref})
                picking_id.write({"exchange_rate": self.exchange_rate})
        return True
    
    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals.update({"ref":'', "internal_ref":self.internal_ref})
        return invoice_vals  
    
    # def _create_stock_moves(self, picking):
    #     values = []
    #     for line in self.filtered(lambda l: not l.display_type):
    #         for val in line._prepare_stock_moves(picking):
    #             values.append(val)
    #         line.move_dest_ids.created_purchase_line_id = False    

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()

    
class PurchaseOrder(models.Model):
    """inherited purchase order"""
    _inherit = 'purchase.order.line'  

    division_id = fields.Many2one('analytic.division',string="Division")
    remark = fields.Char(string="Remark")
    product_variant_ids = fields.Many2many('product.template.attribute.value','purchase_product_variant_rel',related="product_id.product_template_variant_value_ids")


    @api.onchange('product_template_id')
    def _onchange_product_id(self):
        for rec in self:
            print('i')


    @api.onchange('product_id')
    def _onchange_product_qty(self):
        for rec in self:
            print('product_id change')

    @api.onchange('division_id')
    def _onchage_analytic_by_division(self):
        dct = {}
        envv = self.env['account.analytic.account']
        if not self.division_id and len(self.order_id.order_line) > 1:
            prev_line = self.order_id.order_line[-2]
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
        if hasattr(self,'fleet_id') and self.fleet_id and self.fleet_id.analytic_fleet_id and  self.company_id == self.fleet_id.company_id:
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
        self.analytic_distribution = dct    
    
    def _prepare_account_move_line(self, move=False):
        res:dict =  super()._prepare_account_move_line(move=False)
        updated_dct = {"remark": self.remark}
        if hasattr(self, 'project_id'):
            updated_dct["project_id"] = self.project_id.id
        if hasattr(self, 'fleet_id'):
            updated_dct["fleet_id"] = self.fleet_id.id    
        if hasattr(self, 'division_id'):
            updated_dct["division_id"] = self.division_id.id  
        res.update(updated_dct)
        return res  
    
    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        return name    
