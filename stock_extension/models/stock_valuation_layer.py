# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
from odoo.tools import float_compare, float_is_zero, OrderedSet,float_repr
from collections import defaultdict
from odoo import fields, Command
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class StockValuationLayer(models.Model):
    """Inherited Stock Valuation Layer"""
    _inherit = 'stock.valuation.layer'

    location_id = fields.Many2one("stock.location",string="From Loaction")
    location_dest_id = fields.Many2one("stock.location",string="To Loaction")
    by_location = fields.Many2one("stock.location",string="By Location")
    adjustment_line_id = fields.Many2one('stock.inventory.adjustment.line',string="Adjustment Line")
    adjust_id = fields.Many2one('stock.inventory.adjustment',string="Adjustment")
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")
    lot_ids = fields.Many2many('stock.lot',"svl_lot_rel",string="Lot/Serial Number")

    def _validate_accounting_entries(self):
        am_vals = []
        for svl in self:
            if not svl.with_company(svl.company_id).product_id.valuation == 'real_time':
                continue
            if svl.currency_id.is_zero(svl.value):
                continue
            move = svl.stock_move_id
            if not move:
                move = svl.stock_valuation_layer_id.stock_move_id
            am_vals += move.with_company(svl.company_id)._account_entry_move(svl.quantity, svl.description, svl.id, svl.value)
            if move.picking_id:
                self.env.cr.execute(
                    'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                    (move.picking_id.scheduled_date,svl.id,)
                )
            elif move.adjust_id:
                self.env.cr.execute(
                    'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                    (move.adjust_id.date,svl.id,)
                ) 
            elif hasattr(move,"production_id") and move.production_id:
                self.env.cr.execute(
                    'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                    (move.production_id.date_planned_start,svl.id,)
                )
            elif hasattr(move,"production_id") and move.raw_material_production_id:
                self.env.cr.execute(
                    'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                    (move.raw_material_production_id.date_planned_start,svl.id,)
                )
                           
        for am in am_vals:
            move = self.env['stock.move'].browse(am['stock_move_id'])
            svl = self.env['stock.valuation.layer'].sudo().sudo().search([('stock_move_id','=',am['stock_move_id'])])
            journal_id, acc_src, acc_dest, acc_valuation = move._get_accounting_data_for_valuation()
            if move.picking_type_id.code=='outgoing' and move.origin_returned_move_id:
                
                if abs(abs(svl.value)-abs(svl.quantity*move._get_price_unit())) >0:
                    # for am in am_vals:
                    am['line_ids'].append((0, 0, {
                        'name': "COGS Adjustment",
                        'product_id': svl.product_id.id,
                        'quantity': svl.quantity,
                        'product_uom_id': svl.product_id.uom_id.id,
                        'ref': "COGS Adjustment",
                        'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                        'balance': abs(abs(svl.value)-abs(svl.quantity*move._get_price_unit())),
                        'account_id': svl.product_id.property_account_expense_id and svl.product_id.property_account_expense_id.id or svl.product_id.categ_id.property_account_expense_categ_id.id,
                    }))

                    am['line_ids'].append((0, 0, {
                        'name': "COGS Adjustment",
                        'product_id': svl.product_id.id,
                        'quantity': svl.quantity,
                        'product_uom_id': svl.product_id.uom_id.id,
                        'ref': "COGS Adjustment",
                        'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                        'balance': -abs(abs(svl.value)-abs(svl.quantity*move._get_price_unit())),
                        'account_id':acc_src,
                    }))
            elif move.picking_type_id.code=='internal' and move.origin_returned_move_id:
                origin_unit_cost = self.env['stock.valuation.layer'].sudo().sudo().search([('stock_move_id','=',move.origin_returned_move_id.id)])
                unit_cost = origin_unit_cost and origin_unit_cost[0].unit_cost or 0
                if abs(abs(svl.value)-abs(svl.quantity*unit_cost)) >0:
                    # for am in am_vals:
                    am['line_ids'].append((0, 0, {
                        'name': "COGS Internal Adjustment",
                        'product_id': svl.product_id.id,
                        'quantity': svl.quantity,
                        'product_uom_id': svl.product_id.uom_id.id,
                        'ref': "COGS Internal Adjustment",
                        'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                        'balance': abs(abs(svl.value)-abs(svl.quantity*unit_cost)),
                        'account_id': svl.product_id.property_account_expense_id and svl.product_id.property_account_expense_id.id or svl.product_id.categ_id.property_account_expense_categ_id.id,
                    }))

                    am['line_ids'].append((0, 0, {
                        'name': "COGS Internal Adjustment",
                        'product_id': svl.product_id.id,
                        'quantity': svl.quantity,
                        'product_uom_id': svl.product_id.uom_id.id,
                        'ref': "COGS Internal Adjustment",
                        'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                        'balance': -abs(abs(svl.value)-abs(svl.quantity*unit_cost)),
                        'account_id':svl.product_id.categ_id.property_account_transfer_id and svl.product_id.categ_id.property_account_transfer_id.id or False,
                    }))
            elif move.adjust_id and move.adjustment_line_id and not move.adjust_id.has_refund:
                value = abs(svl.unit_cost*svl.quantity)
                move.adjustment_line_id.write({'unit_cost':svl.unit_cost})
                if svl.quantity>0:
                    account_move_line_dct_one = {
                                'account_id': move.adjustment_line_id.adjust_account_id.id,
                                'debit': 0.0,
                                'credit': value,
                                'product_id': svl.product_id.id,
                                'quantity': svl.quantity,
                                'product_uom_id': svl.product_id.uom_id.id,
                                'ref': "Inventory Adjustment",
                                'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,\
                                'division_id': move.division_id.id or False,
                                'fleet_id': move.fleet_id.id or False,
                                'analytic_distribution': move.adjustment_line_id.analytic_distribution,
                                'name':move.adjustment_line_id.description,
                                'job_code_id':move.adjustment_line_id.job_code_id.id,
                                'employee_id':move.adjustment_line_id.employee_id.id,
                    }
                    if hasattr(move, 'project_id'):
                        account_move_line_dct_one['project_id'] = move.project_id.id or False
                    if hasattr(move, 'repair_object_id'):
                        account_move_line_dct_one['repair_object_id'] = move.repair_object_id.id or False
                    entry = self.env['account.move'].create({
                        'journal_id':move.adjust_id.journal_id.id,
                        'date':move.adjust_id.date,
                        'stock_move_id':move.id,
                        'ref':move.adjust_id.name,
                        'internal_ref':move.adjust_id.ref,
                        'department_id':move.adjust_id.department_id.id or False,
                        'line_ids': [
                            Command.create({
                                'account_id': acc_src,
                                'debit': value,
                                'credit': 0.0,
                                'product_id': svl.product_id.id,
                                'quantity': svl.quantity,
                                'product_uom_id': svl.product_id.uom_id.id,
                                'ref': "Inventory Adjustment",
                                'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                                
                            }),
                            Command.create(account_move_line_dct_one),
                        ]
                    })
                    # self.env.cr.execute(
                    #     'UPDATE account_move SET date=%s WHERE id=%s',
                    #     (move.adjust_id.date,entry.id,)
                    # ) 
                    if hasattr(entry, 'branch_id') and not entry.branch_id and entry.stock_move_id:
                        entry.branch_id = entry.stock_move_id.branch_id.id                    
                    if entry and move.adjust_id.origin_returned_adjust_id:
                        if move.adjustment_line_id.origin_returned_adjust_line_id.unit_cost!=move.adjustment_line_id.unit_cost:
                            account_move_line_dct_two = {
                                    'account_id': svl.product_id.property_account_expense_id and svl.product_id.property_account_expense_id.id or svl.product_id.categ_id.property_account_expense_categ_id.id,
                                    'debit': 0.0 ,
                                    'credit': abs(value-move.adjustment_line_id.origin_returned_adjust_line_id.unit_value),
                                    'product_id': svl.product_id.id,
                                    'quantity': svl.quantity,
                                    'product_uom_id': svl.product_id.uom_id.id,
                                    'ref': "Inventory Adjustment",
                                    'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                                    'division_id': move.division_id.id or False,
                                    'fleet_id': move.fleet_id.id or False,
                                    'analytic_distribution': move.adjustment_line_id.analytic_distribution,
                                    'name':move.adjustment_line_id.description,   
                                    'job_code_id':move.adjustment_line_id.job_code_id.id,      
                                    'employee_id':move.adjustment_line_id.employee_id.id,
                                }
                            if hasattr(move, 'project_id'):
                                account_move_line_dct_two['project_id'] = move.project_id.id or False
                            if hasattr(move, 'repair_object_id'):
                                account_move_line_dct_two['repair_object_id'] = move.repair_object_id.id or False
                            account_move_line_dct_three ={
                                    'account_id': move.adjustment_line_id.adjust_account_id.id,
                                    'debit':abs(value-move.adjustment_line_id.origin_returned_adjust_line_id.unit_value),
                                    'credit': 0.0,
                                    'product_id': svl.product_id.id,
                                    'quantity': svl.quantity,
                                    'product_uom_id': svl.product_id.uom_id.id,
                                    'ref': "Inventory Adjustment",
                                    'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                                    'division_id': move.division_id.id or False,
                                    'fleet_id': move.fleet_id.id or False,
                                    'analytic_distribution': move.adjustment_line_id.analytic_distribution,   
                                    'name':move.adjustment_line_id.description, 
                                    'job_code_id':move.adjustment_line_id.job_code_id.id, 
                                    'employee_id':move.adjustment_line_id.employee_id.id,                           
                                }
                            if hasattr(move, 'project_id'):
                                account_move_line_dct_three['project_id'] = move.project_id.id or False
                            if hasattr(move, 'repair_object_id'):
                                account_move_line_dct_three['repair_object_id'] = move.repair_object_id.id or False                            
                            entry.update({'date':move.adjust_id.date,
                                          'line_ids': [
                                Command.create(account_move_line_dct_two),
                                Command.create(account_move_line_dct_three),
                            ]})
                            # self.env.cr.execute(
                            #     'UPDATE account_move SET date=%s WHERE id=%s',
                            #     (move.adjust_id.date,entry.id,)
                            # ) 
                else:
                    account_move_line_dct_four = {
                                'account_id': move.adjustment_line_id.adjust_account_id.id,
                                'debit':value,
                                'credit': 0.0,
                                'product_id': svl.product_id.id,
                                'quantity': svl.quantity,
                                'product_uom_id': svl.product_id.uom_id.id,
                                'ref': "Inventory Adjustment",
                                'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                                'fleet_id': move.fleet_id.id or False,
                                'division_id': move.division_id.id or False,
                                'analytic_distribution': move.adjustment_line_id.analytic_distribution,   
                                'name':move.adjustment_line_id.description, 
                                'job_code_id':move.adjustment_line_id.job_code_id.id, 
                                'employee_id':move.adjustment_line_id.employee_id.id,                                    
                            }
                    if hasattr(move, 'project_id'):
                        account_move_line_dct_four['project_id'] = move.project_id.id or False
                    if hasattr(move, 'repair_object_id'):
                        account_move_line_dct_four['repair_object_id'] = move.repair_object_id.id or False
                    entry = self.env['account.move'].create({
                        'journal_id':move.adjust_id.journal_id.id,
                        'stock_move_id':move.id,
                        'date':move.adjust_id.date,
                        'ref':move.adjust_id.name,
                        'internal_ref':move.adjust_id.ref,
                        'department_id': move.department_id.id or False,
                        'line_ids': [
                            Command.create({
                                'account_id': acc_dest,
                                'debit': 0.0,
                                'credit': value,
                                'product_id': svl.product_id.id,
                                'quantity': svl.quantity,
                                'product_uom_id': svl.product_id.uom_id.id,
                                'ref': "Inventory Adjustment",
                                'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                                
                            }),
                            Command.create(account_move_line_dct_four),
                        ]
                    })
                    # self.env.cr.execute(
                    #     'UPDATE account_move SET date=%s WHERE id=%s',
                    #     (move.adjust_id.date,entry.id,)
                    # ) 
                    if hasattr(entry, 'branch_id') and not entry.branch_id and entry.stock_move_id:
                        entry.branch_id = entry.stock_move_id.branch_id.id
                    if entry and move.adjust_id.origin_returned_adjust_id:
                        if move.adjustment_line_id.origin_returned_adjust_line_id.unit_cost!=move.adjustment_line_id.unit_cost:
                            account_move_line_dct_five = {
                                    'account_id': svl.product_id.property_account_expense_id and svl.product_id.property_account_expense_id.id or svl.product_id.categ_id.property_account_expense_categ_id.id,
                                    'debit': abs(value-move.adjustment_line_id.origin_returned_adjust_line_id.unit_value),
                                    'credit': 0.0,
                                    'product_id': svl.product_id.id,
                                    'quantity': svl.quantity,
                                    'product_uom_id': svl.product_id.uom_id.id,
                                    'ref': "Inventory Adjustment",
                                    'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                                    'fleet_id': move.fleet_id.id or False,
                                    'division_id': move.division_id.id or False,
                                    'analytic_distribution': move.adjustment_line_id.analytic_distribution,   
                                    'name':move.adjustment_line_id.description, 
                                    'job_code_id':move.adjustment_line_id.job_code_id.id, 
                                    'employee_id':move.adjustment_line_id.employee_id.id,                                    
                                }
                            if hasattr(move, 'project_id'):
                                account_move_line_dct_five['project_id'] = move.project_id.id or False
                            if hasattr(move, 'repair_object_id'):
                                account_move_line_dct_five['repair_object_id'] = move.repair_object_id.id or False 
                            account_move_line_dct_six =    {
                                    'account_id': move.adjustment_line_id.adjust_account_id.id,
                                    'debit':0.0,
                                    'credit': abs(value-move.adjustment_line_id.origin_returned_adjust_line_id.unit_value),
                                    'product_id': svl.product_id.id,
                                    'quantity': svl.quantity,
                                    'product_uom_id': svl.product_id.uom_id.id,
                                    'ref': "Inventory Adjustment",
                                    'partner_id': move.picking_id.partner_id and move.picking_id.partner_id.id or False,
                                    'fleet_id': move.fleet_id.id or False,
                                    'division_id': move.division_id.id or False,
                                    'analytic_distribution': move.adjustment_line_id.analytic_distribution,   
                                    'name':move.adjustment_line_id.description, 
                                    'job_code_id':move.adjustment_line_id.job_code_id.id, 
                                    'employee_id':move.adjustment_line_id.employee_id.id,                                    
                                }
                            if hasattr(move, 'project_id'):
                                account_move_line_dct_six['project_id'] = move.project_id.id or False
                            if hasattr(move, 'repair_object_id'):
                                account_move_line_dct_six['repair_object_id'] = move.repair_object_id.id or False                                                    
                            entry.update({'date':move.adjust_id.date,
                                          'line_ids': [
                                Command.create(account_move_line_dct_five),
                                Command.create(account_move_line_dct_six),
                            ]})
                            # self.env.cr.execute(
                            #     'UPDATE account_move SET date=%s WHERE id=%s',
                            #     (move.adjust_id.date,entry.id,)
                            # ) 
                entry.action_post()
                
            # for aml in am_vals:
            #     for line in  aml.get('line_ids'):
            #         line[2].get('amount_currency')
        account_moves = self.env['account.move'].sudo().create(am_vals)
        for move in account_moves:
            for res in self.stock_move_id.picking_id:
                res.exchange_rate = 1.0 if res.exchange_rate <= 0.0 else res.exchange_rate
                if res.picking_type_id.code=='incoming':
                    move.write({'date':res.scheduled_date,'exchange_rate':res.exchange_rate})
                else:
                    move.write({'date':res.scheduled_date})
                for line in move.line_ids:
                    if res.picking_type_id.code=='incoming':
                        line.write({'amount_currency':line.balance/res.exchange_rate})
                        
                    if res.picking_type_id.code=='outgoing':
                        for stock_move in self.stock_move_id:
                            
                            if stock_move.product_id.can_be_unit and stock_move.product_id.tracking == 'serial':
                                dct = {}
                                if line.analytic_distribution:
                                    dct = line.analytic_distribution
                            
                                dct [str(line.move_id.stock_valuation_layer_ids.lot_ids.analytic_account_id.id)] = 100
                                line.write({'analytic_distribution': dct})

        account_moves._post()
        for svl in self:
            # Eventually reconcile together the invoice and valuation accounting entries on the stock interim accounts
            if svl.company_id.anglo_saxon_accounting:
                svl.stock_move_id._get_related_invoices()._stock_account_anglo_saxon_reconcile_valuation(product=svl.product_id)



class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        self.order_line._action_launch_stock_rule()
        for picking_id in self.picking_ids:
            for stock_move_id in picking_id.move_ids:
                if hasattr(stock_move_id, 'project_id'):
                    stock_move_id.write({"project_id":  stock_move_id.sale_line_id.project_id.id})
                if hasattr(stock_move_id, 'repair_object_id'):
                    stock_move_id.write({"repair_object_id": stock_move_id.repair_object_id.id})
                stock_move_id.write(
                    { "fleet_id":  stock_move_id.sale_line_id.fleet_id.id, 
                      "division_id": stock_move_id.sale_line_id.division_id.id,
                      "department_id": stock_move_id.sale_line_id.order_id.department_id.id or False,
                    })
            picking_id.write({"internal_ref": self.internal_ref})
            picking_id.write({"exchange_rate": self.exchange_rate})
            
        # for move in self.picking_ids.move_ids:
        #     if move.sale_line_id.analytic_distribution:
        #         analytic_distribution_ids = [ int(x) for x in list(move.sale_line_id.analytic_distribution.keys())]
        #         lot_id = self.env['stock.lot'].search([('product_id','=',move.product_id.id),('analytic_account_id','in',analytic_distribution_ids)],limit=1).id
        #         if move.product_id.can_be_unit:
        #             move.write({'lot_ids':[[6,0,[lot_id]]]})
        
        for move_line in self.picking_ids.move_line_ids:
            if move_line.move_id.sale_line_id.analytic_distribution:
                analytic_distribution_ids = [ int(x) for x in list(move_line.move_id.sale_line_id.analytic_distribution.keys())]
                lot_id = self.env['stock.lot'].sudo().search([('product_id','=',move_line.move_id.product_id.id),('analytic_account_id','in',analytic_distribution_ids)],limit=1).id
                if move_line.move_id.product_id.can_be_unit:
                    move_line.write({'lot_id':lot_id})

            # if move_line.move_id.product_id.can_be_unit:
            #     move_line.write({'lot_id':move_line.move_id.lot_ids.id})
        
        self.picking_ids.move_ids.write({'location_id':self.location_id.id})
        self.picking_ids.move_line_ids.write({'location_id':self.location_id.id})
        return super(SaleOrder, self)._action_confirm()
    

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    exchange_rate = fields.Float(string='Exchange Rate',default=1.0,tracking=True)
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")

    
    def button_validate(self):
        if not self.branch_id and ((self.location_id and self.location_id.warehouse_id and self.location_id.warehouse_id.branch_id) or (self.location_dest_id and self.location_dest_id.warehouse_id and self.location_dest_id.warehouse_id.branch_id) ):
            raise UserError("Branch is required to validate!!!")
        for move_line in self.move_line_ids:
            if move_line.location_id!=self.location_id or move_line.location_dest_id!=self.location_dest_id:
                raise UserError(_("Source Location or Destination Location doesn't match with Move Lines"))
        for move in self.move_ids:
            if hasattr(move, "branch_id") and move.picking_id and move.picking_id.branch_id:
                move.branch_id = move.picking_id.branch_id            
            if move.location_id!=self.location_id or move.location_dest_id!=self.location_dest_id:
                raise UserError(_("Source Location or Destination Location doesn't match with Lines"))
        if hasattr(self, 'duty_line_id') and self.duty_line_id:
            quant = self.env['stock.quant'].sudo().search([('location_id','=',self.location_id.id),('product_id','=',self.duty_line_id.duty_id.fuel_product_id.id)])  
            if not quant:
                raise ValidationError(f"Stock quant is not found with location - {self.location_id.name} and product - {self.duty_line_id.duty_id.fuel_product_id.name} ") 
            calculated_qty = sum([move_id.product_uom_qty for move_id in self.move_ids])
            rm_qty_temp = quant.quantity - calculated_qty
            if rm_qty_temp < 0:
                raise ValidationError("Validating this fuel transfer make remaining stock lower than zero!!")
            res = super().button_validate() 
            if self.state == 'done':                        
                self.duty_line_id.exist_picking = True
                self.duty_line_id.duty_id.machine_onhand_fuel += calculated_qty
                if self.duty_line_id.fill_fuel>0:
                    self.duty_line_id.duty_id.machine_id.write({'onhand_fuel':round(self.duty_line_id.duty_id.machine_id.onhand_fuel + calculated_qty,2)})
                else:
                    self.duty_line_id.duty_id.machine_id.write({'onhand_fuel':round(self.duty_line_id.duty_id.machine_id.onhand_fuel - calculated_qty,2)})
                self.duty_line_id.duty_id.message_post(body=f"Created Stock Transfer - {self.name}  using {calculated_qty} Litre..")                
        else:
            for move_id in self.move_ids:
                move_id.department_id = self.department_id
            res = super().button_validate()
        if hasattr(self,'quotation_id') and self.move_ids and hasattr(self.move_ids[0],'part_line') and self.move_ids.mapped('part_line') and type(res) == bool:
            if self.name and self.name.split("/")[1].lower() == 'ret':
                for move in self.move_ids:
                    move.part_line.state = 'validate'
                    temp_qty = move.part_line.qty - move.product_uom_qty
                    if temp_qty < 0:
                        raise ValidationError("The qty of parts data must not be less than zero even it has been returned.") 
                    move.part_line.qty = temp_qty     
                self.move_ids[0].part_line.quotation_id.total_parts = round(sum(part_line.qty*part_line.unit_price for part_line in self.move_ids[0].part_line.quotation_id.part_lines),2)
            else:
                for move in self.move_ids:
                    move.part_line.state = 'validate'
        valuation = self.env['stock.valuation.layer']
        valuation_report = self.env['stock.location.valuation.report']
        if self.state=='done' and self.picking_type_id.code=='internal':
            if self.requisition_id:
                from_req = self.env['stock.picking'].sudo().search([('requisition_id','=',self.requisition_id.id),('state','!=','cancel')]).filtered(lambda x:x.location_id.usage=='internal').move_ids.filtered(lambda x:not x.origin_returned_move_id).picking_id
                # if from_req.state!='done':
                #     raise ValidationError(_("Please Validate From Requisition First"))
            for move in self.move_ids:
                if move.quantity_done:
                
                    rounding = move.product_id.uom_id.rounding
                    layers = self.env['stock.valuation.layer'].sudo().search([('product_id','=',move.product_id.id),('location_dest_id','=',move.location_dest_id.id),('remaining_qty','>',0)])
                    report_layers = self.env['stock.location.valuation.report'].sudo().search([('product_id','=',move.product_id.id),('by_location','=',move.location_dest_id.id)])
                    product_tot_qty_available = 0
                    amount_tot_qty_available = 0
                    # if layers:
                    #     product_tot_qty_available += sum(layers.mapped('remaining_qty')) or 0
                    #     amount_tot_qty_available += sum(layers.mapped('remaining_value')) or 0
                    if report_layers:
                        product_tot_qty_available += sum(report_layers.mapped('balance')) or 0
                    else:
                        if layers:
                            product_tot_qty_available += sum(layers.mapped('remaining_qty')) or 0
                    valued_move_lines = move._get_in_move_lines()
                    qty_done = 0
                    for valued_move_line in valued_move_lines:
                        qty_done += valued_move_line.product_uom_id._compute_quantity(valued_move_line.qty_done, move.product_id.uom_id)
                    # if float_is_zero(product_tot_qty_available, precision_rounding=rounding):
                    #     new_std_price = move._get_price_unit()
                    # elif float_is_zero(product_tot_qty_available + move.product_qty, precision_rounding=rounding) or \
                    #         float_is_zero(product_tot_qty_available + qty_done, precision_rounding=rounding):
                    #     new_std_price = move._get_price_unit()

                    location_cost = 0
                    amount_unit = 0
                    # else:
                    if not move.picking_id.requisition_id:
                        amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id).location_cost
                        location_cost =move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id) and move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id).location_cost or 0
                        new_std_price = ((amount_unit * product_tot_qty_available) + (location_cost * move.product_qty)) / (product_tot_qty_available + move.product_qty)
                    else:
                        
                        if not move.picking_id.requisition_id.transit_location_id:
                            amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id).location_cost
                            location_cost =move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id) and move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id).location_cost or 0
                            new_std_price = ((amount_unit * product_tot_qty_available) + (location_cost * move.product_qty)) / (product_tot_qty_available + move.product_qty)

                        else:
                            valuation_ids = True
                            if move.location_id.usage!='transit' and move.origin_returned_move_id:
                                amount_unit = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id).location_cost
                                
                            if move.location_id.usage!='transit' and not move.origin_returned_move_id:
                                
                            #     valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id)
                                amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id).location_cost
                            if move.location_dest_id.usage!='transit' and not move.origin_returned_move_id:
                                
                                valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id)
                                # amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.picking_id.requisition_id.src_location_id).location_cost
                                from_req_move = from_req.move_ids.filtered(lambda x:x.product_id==move.product_id)
                                amount_unit = valuation.sudo().search([('stock_move_id','=',from_req_move.id)])[0].unit_cost
                                new_std_price = ((amount_unit * move.product_qty) + (valuation_ids.location_cost * product_tot_qty_available)) / (product_tot_qty_available + move.product_qty)
                                
                            if move.location_dest_id.usage!='transit' and  move.origin_returned_move_id:
                                from_req = self.env['stock.picking'].sudo().search([('requisition_id','=',self.requisition_id.id)]).filtered(lambda x:x.location_id.usage=='internal').move_ids.filtered(lambda x:x.origin_returned_move_id).picking_id
                                valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id)
                                # amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.picking_id.requisition_id.src_location_id).location_cost
                                from_req_move = from_req.move_ids.filtered(lambda x:x.product_id==move.product_id)                            
                                amount_unit = valuation.sudo().search([('stock_move_id','=',from_req_move.id)])[0].unit_cost
                                new_std_price = ((amount_unit * move.product_qty) + (valuation_ids.location_cost * product_tot_qty_available)) / (product_tot_qty_available + move.product_qty)
                            
                            if not valuation_ids:
                                new_std_price = ((amount_unit * move.product_qty)) / (move.product_qty)
                        # if not move.origin_returned_move_id:
                        #     amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.picking_id.requisition_id.location_id).location_cost
                        #     location_cost = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.picking_id.requisition_id.src_location_id) and move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.picking_id.requisition_id.src_location_id).location_cost or 0
                        #     new_std_price = ((amount_unit * product_tot_qty_available) + (location_cost * move.product_qty)) / (product_tot_qty_available + move.product_qty)
                        # else:
                        #     # if move.transit_location_id:
                        #         # need to check trnasit return
                            
                        #     if move.location_id.usage!='transit':
                        #         valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id)
                        #         amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.picking_id.requisition_id.location_id).location_cost
                        #     else:
                        #         valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id)
                        #         amount_unit =  move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.picking_id.requisition_id.src_location_id).location_cost
                        #     new_std_price = ((amount_unit * product_tot_qty_available) + (valuation_ids.location_cost * move.product_qty)) / (product_tot_qty_available + move.product_qty)
                    if move.location_dest_id.usage == 'internal':
                        warehouse_valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id)
                        if not warehouse_valuation_ids:
                            vals = self.env['warehouse.valuation'].create({'location_id':move.location_dest_id.id,
                                                                        'location_cost':new_std_price})
                            if vals:
                                move.product_id.write({'warehouse_valuation':[(4,vals.id)]})
                        else:
                            warehouse_valuation_ids.write({'location_cost':new_std_price})
                    if move.location_id.usage=='transit' and move.picking_id.requisition_id:
                        warehouse_valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id)
                    else:
                        warehouse_valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_id)
                    if move.picking_id.requisition_id and move.picking_id.requisition_id.transit_location_id:
                        # if move.origin_returned_move_id:
                        #     raise ValidationError(_("Return Case Currently Not Available"))
                        svl_in_vals = {
                            'company_id': move.company_id.id,
                            'product_id': move.product_id.id,
                            'description': "Internal Transfer",
                            'remaining_qty': move.product_qty,
                            # 'remaining_value':location_cost*(move.product_qty) or (valuation_ids and (valuation_ids.location_cost*move.product_qty) or (new_std_price*move.product_qty)),
                            # 'value': location_cost*(move.product_qty) or (valuation_ids and (valuation_ids.location_cost*move.product_qty) or (new_std_price*move.product_qty)),
                            'remaining_value': amount_unit * move.product_qty,
                            'value':amount_unit * move.product_qty,
                            'quantity':move.product_qty,
                            # 'unit_cost': location_cost or (valuation_ids and valuation_ids.location_cost or new_std_price),
                            'unit_cost':amount_unit,
                            'stock_move_id': move.id,
                            'by_location':move.location_dest_id.id,
                            'location_id':move.location_id.id,
                            'location_dest_id':move.location_dest_id.id,
                            'fleet_id':move.fleet_id.id or False,
                            'division_id': move.division_id.id or False,
                            'department_id':move.department_id.id or False,
                            'fleet_location_id':move.fleet_location_id.id or False,
                        }
                        if hasattr(move, 'project_id'):
                            svl_in_vals['project_id'] = move.project_id.id or False
                        if hasattr(move, 'repair_object_id'):
                            svl_in_vals['repair_object_id'] = move.repair_object_id.id or False
                        if hasattr(move, 'branch_id'):
                            svl_in_vals['branch_id'] = move.branch_id.id or False
                        in_valuation = valuation.create(svl_in_vals)
                        # report_values
                        svl_report_vals = move._prepare_common_svl_report_vals([svl_in_vals])
                        valuation_report.sudo().create(svl_report_vals)
                        # report_values 
                        self.env.cr.execute(
                            'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                            (move.picking_id.scheduled_date,in_valuation.id,)
                        )
                        in_valuation._validate_accounting_entries()
                        svl_out_vals = {
                            'company_id': move.company_id.id,
                            'product_id': move.product_id.id,
                            'description': "Internal Transfer",
                            'remaining_qty': 0,
                            'remaining_value':0,
                            # 'value': location_cost*-abs(move.product_qty) or (valuation_ids and (valuation_ids.location_cost*-abs(move.product_qty)) or (new_std_price*-abs(move.product_qty))),
                            'value':amount_unit * -abs(move.product_qty),
                            'quantity':-(move.product_qty),
                            # 'unit_cost': location_cost or (valuation_ids and valuation_ids.location_cost or new_std_price),
                            'unit_cost':amount_unit,
                            'stock_move_id': move.id,
                            'by_location':move.location_id.id,                        
                            'location_dest_id':move.location_id.id,
                            'location_id':move.location_dest_id.id,
                            'fleet_id':move.fleet_id.id or False,
                            'division_id':move.division_id.id or False,
                            'department_id':move.department_id.id or False,
                            'fleet_location_id':move.fleet_location_id.id or False,
                        }
                        if hasattr(move, 'project_id'):
                            svl_out_vals['project_id'] = move.project_id.id or False
                        if hasattr(move, 'repair_object_id'):
                            svl_out_vals['repair_object_id'] = move.repair_object_id.id or False
                        if hasattr(move, 'branch_id'):
                            svl_out_vals['branch_id'] = move.branch_id.id or False

                        out_valuation = valuation.create(svl_out_vals)
                        # report_values
                        svl_report_vals = move._prepare_common_svl_report_vals([svl_out_vals])
                        valuation_report.sudo().create(svl_report_vals)
                        # report_values                     
                        self.env.cr.execute(
                            'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                            (move.picking_id.scheduled_date,out_valuation.id,)
                        )
                    else:
                        svl_in_vals = {
                            'company_id': move.company_id.id,
                            'product_id': move.product_id.id,
                            'description': "Internal Transfer",
                            'remaining_qty': move.product_qty,
                            'remaining_value':warehouse_valuation_ids and warehouse_valuation_ids.location_cost*(move.product_qty) or 0,
                            'value': warehouse_valuation_ids and warehouse_valuation_ids.location_cost*(move.product_qty) or 0,
                            'quantity':move.product_qty,
                            'unit_cost': warehouse_valuation_ids and warehouse_valuation_ids.location_cost or 0,
                            'stock_move_id': move.id,
                            'by_location':move.location_dest_id.id,
                            'division_id':move.division_id.id or False,
                            'location_id':move.location_id.id,
                            'location_dest_id':move.location_dest_id.id,
                            'fleet_id':move.fleet_id.id or False,
                            'department_id':move.department_id.id or False,
                            'fleet_location_id':move.fleet_location_id.id or False,
                        }
                        if hasattr(move, 'project_id'):
                            svl_in_vals['project_id'] = move.project_id.id or False
                        if hasattr(move, 'repair_object_id'):
                            svl_in_vals['repair_object_id'] = move.repair_object_id.id or False
                        if hasattr(move, 'branch_id'):
                            svl_in_vals['branch_id'] = move.branch_id.id or False

                        in_valuation = valuation.create(svl_in_vals)
                        # report_values
                        svl_report_vals = move._prepare_common_svl_report_vals([svl_in_vals])
                        valuation_report.sudo().create(svl_report_vals)
                        # report_values                     
                        self.env.cr.execute(
                            'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                            (move.picking_id.scheduled_date,in_valuation.id,)
                        )
                        out_valuation = move._create_out_svl(move.product_qty)
                        self.env.cr.execute(
                            'UPDATE stock_valuation_layer SET create_date=%s WHERE id=%s',
                            (move.picking_id.scheduled_date,out_valuation.id,)
                        )

                    if move.picking_id.requisition_id and move.origin_returned_move_id:
                        move.picking_id.requisition_id.write({'picking_ids':[(4, move.picking_id.id)]})
    

                

        return res
    
    def action_cancel(self):
        if hasattr(self, 'duty_line_id') and self.duty_line_id:
            self.duty_line_id.write({'picking_ids':[(3,self.id)],
                                     'fill_fuel':0})
        self.move_ids._action_cancel()
        self.write({'is_locked': True})
        self.filtered(lambda x: not x.move_ids).state = 'cancel'
        return True
    
    def action_print_picking(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename) + str(birt_suffix) + '.rptdesign&pp_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url :
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise ValidationError('Report Not Not Found')   

class StockMove(models.Model):
    _inherit = "stock.move.line"       

    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")   

    
class StockMove(models.Model):
    _inherit = "stock.move"

    adjustment_line_id = fields.Many2one('stock.inventory.adjustment.line',string="Adjustment Line")
    adjust_id = fields.Many2one('stock.inventory.adjustment',string="Adjustment")
    exchange_rate = fields.Float(related='picking_id.exchange_rate', string='Exchange Rate', copy=True, store=True)
    remark = fields.Char("Remark")
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")
    custom_part = fields.Char(string="Part ID", related= "product_id.product_tmpl_id.custom_part", store=True, readonly=False, required=False)
    product_name = fields.Char(string="Product Name",related="product_id.name")

    def _account_entry_move(self, qty, description, svl_id, cost):
        """ Accounting Valuation Entries """
        self.ensure_one()
        am_vals = []
        if self.product_id.type != 'product':
            # no stock valuation for consumable products
            return am_vals
        if self.restrict_partner_id and self.restrict_partner_id != self.company_id.partner_id:
            # if the move isn't owned by the company, we don't make any valuation
            return am_vals

        company_from = self._is_out() and self.mapped('move_line_ids.location_id.company_id') or False
        company_to = self._is_in() and self.mapped('move_line_ids.location_dest_id.company_id') or False

        journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation()
        # Create Journal Entry for products arriving in the company; in case of routes making the link between several
        # warehouse of the same company, the transit location belongs to this company, so we don't need to create accounting entries
        if self._is_in():
            if self._is_returned(valued_type='in'):
                am_vals.append(self.with_company(company_to).with_context(is_returned=True)._prepare_account_move_vals(acc_dest, acc_valuation, journal_id, qty, description, svl_id, cost))
            else:
                am_vals.append(self.with_company(company_to)._prepare_account_move_vals(acc_src, acc_valuation, journal_id, qty, description, svl_id, cost))

        # Create Journal Entry for products leaving the company
        if self._is_out():
            cost = -1 * cost
            if self._is_returned(valued_type='out'):
                am_vals.append(self.with_company(company_from).with_context(is_returned=True)._prepare_account_move_vals(acc_valuation, acc_src, journal_id, qty, description, svl_id, cost))
            else:
                am_vals.append(self.with_company(company_from)._prepare_account_move_vals(acc_valuation, acc_dest, journal_id, qty, description, svl_id, cost))

        if self.company_id.anglo_saxon_accounting:
            # Creates an account entry from stock_input to stock_output on a dropship move. https://github.com/odoo/odoo/issues/12687
            if self._is_dropshipped():
                if cost > 0:
                    am_vals.append(self.with_company(self.company_id)._prepare_account_move_vals(acc_src, acc_valuation, journal_id, qty, description, svl_id, cost))
                else:
                    cost = -1 * cost
                    am_vals.append(self.with_company(self.company_id)._prepare_account_move_vals(acc_valuation, acc_dest, journal_id, qty, description, svl_id, cost))
            elif self._is_dropshipped_returned():
                if cost > 0 and self.location_dest_id._should_be_valued():
                    am_vals.append(self.with_company(self.company_id).with_context(is_returned=True)._prepare_account_move_vals(acc_valuation, acc_src, journal_id, qty, description, svl_id, cost))
                elif cost > 0:
                    am_vals.append(self.with_company(self.company_id).with_context(is_returned=True)._prepare_account_move_vals(acc_dest, acc_valuation, journal_id, qty, description, svl_id, cost))
                else:
                    cost = -1 * cost
                    am_vals.append(self.with_company(self.company_id).with_context(is_returned=True)._prepare_account_move_vals(acc_valuation, acc_src, journal_id, qty, description, svl_id, cost))
        if self.picking_id.requisition_id and self.picking_type_id.code=='internal' and self.location_id.usage=='internal':
            if self.product_id.product_tmpl_id.categ_id.property_account_transfer_id:
                am_vals.append(self.with_company(self.company_id)._prepare_account_move_vals(acc_valuation, acc_dest, journal_id, qty, description, svl_id, cost))
                lines = self.with_company(self.company_id)._prepare_account_move_vals(acc_dest,self.product_id.product_tmpl_id.categ_id.property_account_transfer_id.id, journal_id, qty, description, svl_id, cost)
                for val in lines.get('line_ids'):
                    am_vals[0]['line_ids'].append(val)
        if self.picking_id.requisition_id and self.picking_type_id.code=='internal' and self.location_dest_id.usage=='internal':
             if self.product_id.product_tmpl_id.categ_id.property_account_transfer_id:
                am_vals.append(self.with_company(self.company_id)._prepare_account_move_vals(acc_src, acc_valuation, journal_id, qty, description, svl_id, cost))
                lines = self.with_company(self.company_id)._prepare_account_move_vals(self.product_id.product_tmpl_id.categ_id.property_account_transfer_id.id,acc_src, journal_id, qty, description, svl_id, cost)
                for val in lines.get('line_ids'):
                    am_vals[0]['line_ids'].append(val)
        for am_val in am_vals:
            move = self.env['stock.move'].browse(am_val['stock_move_id'])
            am_val['department_id'] = move.department_id.id
            if move.adjust_id:
                am_val['date'] = move.adjust_id.date
            if hasattr(move, 'branch_id'):
                am_val['branch_id'] = move.branch_id.id or False
            
        return am_vals


    def _get_in_svl_vals(self, forced_quantity):
        svl_vals_list = []
        for move in self:
            move = move.with_company(move.company_id)
            valued_move_lines = move._get_in_move_lines()
            valued_quantity = 0
            for valued_move_line in valued_move_lines:
                valued_quantity += valued_move_line.product_uom_id._compute_quantity(valued_move_line.qty_done, move.product_id.uom_id)
            unit_cost = move.product_id.standard_price
            if move.product_id.cost_method != 'standard':
                unit_cost = abs(move._get_price_unit()) # May be negative (i.e. decrease an out move).
            if move.product_id.cost_method != 'standard' and hasattr(move,"production_id") and  move.production_id:
                unit_cost = abs(move._get_price_unit()) + (sum(move.production_id.labor_line.mapped('total'))/move.production_id.product_uom_qty)
            if move.product_id.cost_method == 'average' and move.origin_returned_move_id:
                unit_cost = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id).location_cost
            if move.product_id.cost_method == 'average' and move.adjust_id:
                unit_cost = move.adjust_id and move.adjustment_line_id.unit_cost
            svl_vals = move.product_id._prepare_in_svl_vals(forced_quantity or valued_quantity, unit_cost)
            svl_vals.update(move._prepare_common_svl_vals())
            if forced_quantity:
                svl_vals['description'] = 'Correction of %s (modification of past move)' % (move.picking_id.name or move.name)
            svl_vals_list.append(svl_vals)
        return svl_vals_list


    def _prepare_common_svl_vals(self):
        """When a `stock.valuation.layer` is created from a `stock.move`, we can prepare a dict of
        common vals.

        :returns: the common values when creating a `stock.valuation.layer` from a `stock.move`
        :rtype: dict
        """
        self.ensure_one()
        if self.picking_type_id.code == 'internal':
            by_location_id = self.location_id.id
        else:
            by_location_id = self.location_id.id if self.location_id.usage == "internal" else self.location_dest_id.id
        svl_dct = {
            'stock_move_id': self.id,
            'company_id': self.company_id.id,
            'product_id': self.product_id.id,
            'description': self.reference and '%s - %s' % (self.reference, self.product_id.name) or self.product_id.name,
            'location_id':self.location_id.id,
            'division_id':self.division_id.id or False,
            'by_location':by_location_id,
            'department_id':self.department_id.id or False,
            'location_dest_id':self.location_dest_id.id,
            'fleet_id':self.fleet_id.id or False,
            'fleet_location_id':self.fleet_location_id.id or False,  
            'lot_ids': self.lot_ids          
        }
        if hasattr(self, 'project_id'):
            svl_dct['project_id'] = self.project_id.id or False
        if hasattr(self, 'repair_object_id'):
            svl_dct['repair_object_id'] = self.repair_object_id.id or False
        if hasattr(self, 'branch_id'):
            branch_id = self.picking_id.branch_id.id or False
            if not branch_id:
                branch_id = self.branch_id.id or False
            svl_dct['branch_id'] = branch_id
            self.branch_id = branch_id

        return svl_dct
    
    def _prepare_common_svl_report_vals(self, svl_values):
        """When a `stock.valuation.layer.report` is created from a `stock.move`, we can prepare a dict of
        common vals.

        :returns: the common values when creating a `stock.valuation.layer.report` from a `stock.move`
        :rtype: dict
        """
        svlr_values = []
        for svl_val in svl_values:
            stock_move = self.sudo().search([('id','=',svl_val['stock_move_id'])])
            qty_in , qty_out = 0 , 0
            svl_qty = svl_val['quantity']
            desc = stock_move.adjustment_line_id.description if stock_move.adjustment_line_id else stock_move.picking_id.internal_ref
            reference = stock_move.adjust_id.ref if stock_move.adjustment_line_id else stock_move.picking_id.name
            sequence = stock_move.adjust_id.name if stock_move.adjustment_line_id else stock_move.origin
            sequence = stock_move.picking_id[0].origin if not sequence else sequence
            report_date = stock_move.adjust_id.date if stock_move.adjust_id else stock_move.picking_id.scheduled_date
            if svl_qty >= 0:
                qty_in = abs(svl_qty)
            else:
                qty_out = abs(svl_qty)  
            if stock_move.sale_line_id or (stock_move.picking_type_id and stock_move.picking_type_id.code == 'outgoing'):
                report_type = 'delivery_return' if stock_move.picking_id.origin and 'Return' in stock_move.picking_id.origin else 'delivery'
            elif stock_move.purchase_line_id or (stock_move.picking_type_id and stock_move.picking_type_id.code == 'incoming'):
                report_type = 'receipt_return'  if stock_move.picking_id.origin and 'Return' in stock_move.picking_id.origin else 'receipt'
            elif stock_move.adjustment_line_id:
                report_type = 'adjustment_return ' if stock_move.picking_id.origin and 'Return' in stock_move.picking_id.origin  else 'adjustment'
            elif stock_move.picking_type_id.code == 'internal':  
                report_type = 'transfer_return' if stock_move.picking_id.origin and 'Return' in stock_move.picking_id.origin else 'transfer'  
            elif hasattr(stock_move,"production_id") and stock_move.production_id:
                report_type = 'mrp'
            else:
                report_type = 'unknown'
            svlr_dct = {
                'report_type':report_type,
                'stock_move_id':svl_val['stock_move_id'],
                'product_id':svl_val['product_id'],
                'company_id':svl_val['company_id'],
                'location_id': svl_val['location_id'],
                'location_dest_id':svl_val['location_dest_id'],                
                'by_location':svl_val['by_location'],
                'report_date': report_date,
                'ref':reference,
                'seq':sequence,
                'product_id':svl_val['product_id'],
                'product_name': stock_move.product_id.name,
                'fleet_id': svl_val['fleet_id'],
                'division_id':svl_val['division_id'],
                'department_id':svl_val['department_id'],
                'fleet_location_id': svl_val['fleet_location_id'],                
                'desc': desc,
                'qty_in': qty_in,
                'qty_out': qty_out,
                'balance': qty_in - qty_out,
                'uom_id': stock_move.product_uom.id,
                'unit_cost': svl_val['unit_cost'],
                'total_amt': svl_val['value'],
            }
            if svl_val.get('project_id'):
                svlr_dct['project_id'] = svl_val['project_id']
            if svl_val.get('repair_object_id'):
                svlr_dct['repair_object_id'] = svl_val['repair_object_id']
            if svl_val.get('branch_id'):
                svlr_dct['branch_id'] = svl_val['branch_id']

            svlr_values.append(svlr_dct)
        return svlr_values

    def product_price_update_before_done(self, forced_qty=None):
        tmpl_dict = defaultdict(lambda: 0.0)
        # adapt standard price on incomming moves if the product cost_method is 'average'
        std_price_update = {}
        for move in self.filtered(lambda move: move._is_in() and move.with_company(move.company_id).product_id.cost_method == 'average'):
            # product_tot_qty_available = move.product_id.sudo().with_company(move.company_id).quantity_svl + tmpl_dict[move.product_id.id]
            rounding = move.product_id.uom_id.rounding
            product_tot_qty_available = 0
            layers = self.env['stock.valuation.layer'].sudo().search([('product_id','=',move.product_id.id),('location_dest_id','=',move.location_dest_id.id),('remaining_qty','>',0)])
            if layers:
                product_tot_qty_available += sum(layers.mapped('remaining_qty')) or 0
            valued_move_lines = move._get_in_move_lines()
            qty_done = 0
            for valued_move_line in valued_move_lines:
                qty_done += valued_move_line.product_uom_id._compute_quantity(valued_move_line.qty_done, move.product_id.uom_id)

            qty = forced_qty or qty_done
            labor_costs = 0
            if hasattr(move,'production_id'):
                if hasattr(move, "production_id") and move.production_id:
                    if move.production_id.labor_line:
                        if move.production_id.product_uom_qty:
                            labor_costs += sum(move.production_id.labor_line.mapped('total'))/move.production_id.product_uom_qty
            if float_is_zero(product_tot_qty_available, precision_rounding=rounding):
                if move.adjust_id and move.adjustment_line_id:
                    new_std_price = move.adjustment_line_id.unit_cost
                else:
                    new_std_price = move._get_price_unit()+labor_costs
            elif float_is_zero(product_tot_qty_available + move.product_qty, precision_rounding=rounding) or \
                    float_is_zero(product_tot_qty_available + qty, precision_rounding=rounding):
                if move.adjust_id and move.adjustment_line_id:
                    new_std_price = move.adjustment_line_id.unit_cost
                else:
                    new_std_price = move._get_price_unit()+labor_costs
            else:
                # Get the standard price
                if not move.origin_returned_move_id and not (move.adjust_id and move.adjustment_line_id) and (not hasattr(move,"production_id") or not move.production_id):
                    amount_unit = std_price_update.get((move.company_id.id, move.product_id.id)) or move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id).location_cost
                    new_std_price = ((amount_unit * product_tot_qty_available) + (move._get_price_unit() * qty)) / (product_tot_qty_available + qty)
                elif move.adjust_id and move.adjustment_line_id and move.adjustment_line_id.quantity>0:
                    amount_unit = std_price_update.get((move.company_id.id, move.product_id.id)) or move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id).location_cost
                    new_std_price = ((amount_unit * product_tot_qty_available)+(move.adjustment_line_id.unit_cost*move.adjustment_line_id.quantity)) / (product_tot_qty_available+move.adjustment_line_id.quantity)

                else:
                    amount_unit = std_price_update.get((move.company_id.id, move.product_id.id)) or move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id).location_cost
                    if hasattr(move,"production_id") and move.production_id and move.production_id.labor_line:
                        new_std_price = ((amount_unit * product_tot_qty_available)+((amount_unit*qty)+labor_costs)) / (product_tot_qty_available+qty)
                    else:
                        new_std_price = (amount_unit * product_tot_qty_available)/ (product_tot_qty_available)
            tmpl_dict[move.product_id.id] += qty_done
            # Write the standard price, as SUPERUSER_ID because a warehouse manager may not have the right to write on products
            move.product_id.with_company(move.company_id.id).with_context(disable_auto_svl=True).sudo().write({'standard_price': new_std_price})
            if move.location_dest_id.usage == 'internal':
                warehouse_valuation_ids = move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==move.location_dest_id)
                
                if not warehouse_valuation_ids:
                    vals = self.env['warehouse.valuation'].create({'location_id':move.location_dest_id.id,
                                                                'location_cost':new_std_price})
                    if vals:
                        move.product_id.write({'warehouse_valuation':[(4,vals.id)]})
                else:
                    warehouse_valuation_ids.write({'location_cost':new_std_price})
            std_price_update[move.company_id.id, move.product_id.id] = new_std_price

        # adapt standard price on incomming moves if the product cost_method is 'fifo'
        for move in self.filtered(lambda move:
                                  move.with_company(move.company_id).product_id.cost_method == 'fifo'
                                  and float_is_zero(move.product_id.sudo().quantity_svl, precision_rounding=move.product_id.uom_id.rounding)):
            move.product_id.with_company(move.company_id.id).sudo().write({'standard_price': move._get_price_unit()})

    def _create_in_svl(self, forced_quantity=None):
        """Create a `stock.valuation.layer` from `self`.

        :param forced_quantity: under some circunstances, the quantity to value is different than
            the initial demand of the move (Default value = None)
        """
        svl_vals_list = self._get_in_svl_vals(forced_quantity)
        svl_report_vals = self._prepare_common_svl_report_vals(svl_vals_list)
        self.env['stock.location.valuation.report'].sudo().create(svl_report_vals)  
        return self.env['stock.valuation.layer'].sudo().create(svl_vals_list)


    def _create_out_svl(self, forced_quantity=None):
        """Create a `stock.valuation.layer` from `self`.

        :param forced_quantity: under some circunstances, the quantity to value is different than
            the initial demand of the move (Default value = None)
        """
        svl_vals_list = []
        for move in self:
            move = move.with_company(move.company_id)
            valued_move_lines = move._get_out_move_lines()
            valued_quantity = 0
            for valued_move_line in valued_move_lines:
                valued_quantity += valued_move_line.product_uom_id._compute_quantity(valued_move_line.qty_done, move.product_id.uom_id)
            if float_is_zero(forced_quantity or valued_quantity, precision_rounding=move.product_id.uom_id.rounding):
                continue
            svl_vals = move.product_id._prepare_out_svl_vals(forced_quantity or valued_quantity, move.company_id,move.location_id,move.location_dest_id,move)
            svl_vals.update(move._prepare_common_svl_vals())
            if forced_quantity:
                svl_vals['description'] = 'Correction of %s (modification of past move)' % (move.picking_id.name or move.name)
            svl_vals['description'] += svl_vals.pop('rounding_adjustment', '')
            svl_vals_list.append(svl_vals)
        svl_report_vals = self._prepare_common_svl_report_vals(svl_vals_list)
        self.env['stock.location.valuation.report'].sudo().create(svl_report_vals)            
        return self.env['stock.valuation.layer'].sudo().create(svl_vals_list)
    

class ProductProduct(models.Model):
    _inherit = "product.product"

    def _prepare_out_svl_vals(self, quantity, company,location,location_dest,move):
        """Prepare the values for a stock valuation layer created by a delivery.

        :param quantity: the quantity to value, expressed in `self.uom_id`
        :return: values to use in a call to create
        :rtype: dict
        """
        self.ensure_one()
        company_id = self.env.context.get('force_company', self.env.company.id)
        company = self.env['res.company'].browse(company_id)
        currency = company.currency_id
        # Quantity is negative for out valuation layers.
        if location.usage!='transit':
            valuation_ids = self.warehouse_valuation.filtered(lambda x:x.location_id==location)
        else:
            valuation_ids = self.warehouse_valuation.filtered(lambda x:x.location_id==location_dest)
        if self.product_tmpl_id.cost_method=='average' and valuation_ids:
            quantity = -1 * quantity
            vals = {
                'product_id': self.id,
                'value': currency.round(quantity * valuation_ids.location_cost),
                'unit_cost': valuation_ids.location_cost,
                'quantity': quantity,
            }
        else:
            quantity = -1 * quantity
            vals = {
                'product_id': self.id,
                'value': currency.round(quantity * self.standard_price),
                'unit_cost': self.standard_price,
                'quantity': quantity,
            }
        fifo_vals = self._run_fifo(abs(quantity), company,location,location_dest,move)
        vals['remaining_qty'] = fifo_vals.get('remaining_qty')
        # In case of AVCO, fix rounding issue of standard price when needed.
        if self.product_tmpl_id.cost_method == 'average' and not float_is_zero(self.quantity_svl, precision_rounding=self.uom_id.rounding):
            rounding_error = currency.round(
                (self.standard_price * self.quantity_svl - self.value_svl) * abs(quantity / self.quantity_svl)
            )
            if rounding_error:
                # If it is bigger than the (smallest number of the currency * quantity) / 2,
                # then it isn't a rounding error but a stock valuation error, we shouldn't fix it under the hood ...
                if abs(rounding_error) <= max((abs(quantity) * currency.rounding) / 2, currency.rounding):
                    vals['value'] += rounding_error
                    vals['rounding_adjustment'] = '\nRounding Adjustment: %s%s %s' % (
                        '+' if rounding_error > 0 else '',
                        float_repr(rounding_error, precision_digits=currency.decimal_places),
                        currency.symbol
                    )
        if self.product_tmpl_id.cost_method == 'fifo':
            vals.update(fifo_vals)
        return vals
    

    def _run_fifo(self, quantity, company,location,location_dest,move):
        self.ensure_one()

        # Find back incoming stock valuation layers (called candidates here) to value `quantity`.
        qty_to_take_on_candidates = quantity
        candidates = self.env['stock.valuation.layer'].sudo().search([
            ('product_id', '=', self.id),
            ('remaining_qty', '>', 0),
            ('company_id', '=', company.id),
            ('location_dest_id','=',location.id)
        ])
        new_standard_price = 0
        tmp_value = 0  # to accumulate the value taken on the candidates
        for candidate in candidates:
            qty_taken_on_candidate = min(qty_to_take_on_candidates, candidate.remaining_qty)

            candidate_unit_cost = candidate.remaining_value / candidate.remaining_qty
            new_standard_price = candidate_unit_cost
            value_taken_on_candidate = qty_taken_on_candidate * candidate_unit_cost
            value_taken_on_candidate = candidate.currency_id.round(value_taken_on_candidate)
            new_remaining_value = candidate.remaining_value - value_taken_on_candidate

            candidate_vals = {
                'remaining_qty': candidate.remaining_qty - qty_taken_on_candidate,
                'remaining_value': new_remaining_value,
            }

            candidate.write(candidate_vals)

            qty_to_take_on_candidates -= qty_taken_on_candidate
            tmp_value += value_taken_on_candidate

            if float_is_zero(qty_to_take_on_candidates, precision_rounding=self.uom_id.rounding):
                if float_is_zero(candidate.remaining_qty, precision_rounding=self.uom_id.rounding):
                    next_candidates = candidates.filtered(lambda svl: svl.remaining_qty > 0)
                    new_standard_price = next_candidates and next_candidates[0].unit_cost or new_standard_price
                break

        # Update the standard price with the price of the last used candidate, if any.
        if new_standard_price and self.cost_method == 'fifo':
            self.sudo().with_company(company.id).with_context(disable_auto_svl=True).standard_price = new_standard_price

        # If there's still quantity to value but we're out of candidates, we fall in the
        # negative stock use case. We chose to value the out move at the price of the
        # last out and a correction entry will be made once `_fifo_vacuum` is called.
        vals = {}
        if float_is_zero(qty_to_take_on_candidates, precision_rounding=self.uom_id.rounding):
            vals = {
                'value': -tmp_value,
                'unit_cost': tmp_value / quantity,
            }
        else:
            assert qty_to_take_on_candidates > 0
            last_fifo_price = new_standard_price or self.standard_price
            negative_stock_value = last_fifo_price * -qty_to_take_on_candidates
            tmp_value += abs(negative_stock_value)
            vals = {
                'remaining_qty': -qty_to_take_on_candidates,
                'value': -tmp_value,
                'unit_cost': last_fifo_price,
            }
        return vals
    

# class StockLandedCost(models.Model):
#     _inherit = 'stock.landed.cost'
    

#     def button_validate(self):
#         self._check_can_validate()
#         cost_without_adjusment_lines = self.filtered(lambda c: not c.valuation_adjustment_lines)
#         if cost_without_adjusment_lines:
#             cost_without_adjusment_lines.compute_landed_cost()
#         if not self._check_sum():
#             raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

#         for cost in self:
#             cost = cost.with_company(cost.company_id)
#             move = self.env['account.move']
#             move_vals = {
#                 'journal_id': cost.account_journal_id.id,
#                 'date': cost.date,
#                 'ref': cost.name,
#                 'line_ids': [],
#                 'move_type': 'entry',
#             }
#             valuation_layer_ids = []
#             cost_to_add_byproduct = defaultdict(lambda: 0.0)
#             for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
#                 remaining_qty = sum(line.move_id.stock_valuation_layer_ids.mapped('remaining_qty'))
#                 linked_layer = line.move_id.stock_valuation_layer_ids[:1]

#                 # Prorate the value at what's still in stock
#                 cost_to_add = (remaining_qty / line.move_id.product_qty) * line.additional_landed_cost
#                 if not cost.company_id.currency_id.is_zero(cost_to_add):
#                     valuation_layer = self.env['stock.valuation.layer'].create({
#                         'value': cost_to_add,
#                         'unit_cost': 0,
#                         'quantity': 0,
#                         'remaining_qty': 0,
#                         'stock_valuation_layer_id': linked_layer.id,
#                         'description': cost.name,
#                         'stock_move_id': line.move_id.id,
#                         'product_id': line.move_id.product_id.id,
#                         'stock_landed_cost_id': cost.id,
#                         'company_id': cost.company_id.id,
#                     })
#                     linked_layer.remaining_value += cost_to_add
#                     valuation_layer_ids.append(valuation_layer.id)
#                 # Update the AVCO
#                 product = line.move_id.product_id
#                 if product.cost_method == 'average':
#                     cost_to_add_byproduct[product] += cost_to_add
#                 # Products with manual inventory valuation are ignored because they do not need to create journal entries.
#                 if product.valuation != "real_time":
#                     continue
#                 # `remaining_qty` is negative if the move is out and delivered proudcts that were not
#                 # in stock.
#                 qty_out = 0
#                 if line.move_id._is_in():
#                     qty_out = line.move_id.product_qty - remaining_qty
#                 elif line.move_id._is_out():
#                     qty_out = line.move_id.product_qty
#                 move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)

#             # batch standard price computation avoid recompute quantity_svl at each iteration
#             products = self.env['product.product'].browse(p.id for p in cost_to_add_byproduct.keys())
#             if len(cost.valuation_adjustment_lines.move_id.mapped('location_dest_id'))>1:
#                 raise UserError("Please add same destination location for Receipts")
#             for product in products:  # iterate on recordset to prefetch efficiently quantity_svl
#                 if not float_is_zero(product.quantity_svl, precision_rounding=product.uom_id.rounding):
#                     product.with_company(cost.company_id).sudo().with_context(disable_auto_svl=True).standard_price += cost_to_add_byproduct[product] / product.quantity_svl
#                     if product.warehouse_valuation.search([('location_id','=',cost.valuation_adjustment_lines.move_id.mapped('location_dest_id').id)]):
#                         product.warehouse_valuation.write({'location_cost':product.warehouse_valuation.location_cost+(cost_to_add_byproduct[product] / product.quantity_svl)})
#                     else:
#                         vals = self.env['warehouse.valuation'].create({'location_id':cost.valuation_adjustment_lines.move_id.mapped('location_dest_id').id,
#                                                                     'location_cost':cost_to_add_byproduct[product] / product.quantity_svl})
#                         if vals:
#                             product.write({'warehouse_valuation':[(4,vals.id)]})
#             move_vals['stock_valuation_layer_ids'] = [(6, None, valuation_layer_ids)]
#             # We will only create the accounting entry when there are defined lines (the lines will be those linked to products of real_time valuation category).
#             cost_vals = {'state': 'done'}
#             if move_vals.get("line_ids"):
#                 move = move.create(move_vals)
#                 cost_vals.update({'account_move_id': move.id})
#             cost.write(cost_vals)
#             if cost.account_move_id:
#                 move._post()
#             cost.reconcile_landed_cost()
#         return True