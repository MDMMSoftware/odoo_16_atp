# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
# from odoo.tools import float_compare, float_is_zero, OrderedSet,float_repr
from collections import defaultdict
from odoo import fields, Command
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
    
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero
class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'
    
    vendor_bill_ids = fields.Many2many(comodel_name='account.move', string='Vendor Bills', copy=False, domain=[('move_type', '=', 'in_invoice'),('state','=','posted')])
    branch_id = fields.Many2one("res.branch",string="Branch")

    def button_validate(self):
        self._check_can_validate()
        cost_without_adjusment_lines = self.filtered(lambda c: not c.valuation_adjustment_lines)
        if cost_without_adjusment_lines:
            cost_without_adjusment_lines.compute_landed_cost()
        if not self._check_sum():
            raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

        for cost in self:
            cost = cost.with_company(cost.company_id)
            move = self.env['account.move']
            move_vals = {
                'journal_id': cost.account_journal_id.id,
                'branch_id': cost.branch_id and cost.branch_id.id or False,
                'date': cost.date,
                'ref': cost.name,
                'line_ids': [],
                'move_type': 'entry',
            }
            valuation_layer_ids = []
            cost_to_add_byproduct = defaultdict(lambda: 0.0)
            for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
                remaining_qty = sum(line.move_id.stock_valuation_layer_ids.mapped('remaining_qty'))
                linked_layer = line.move_id.stock_valuation_layer_ids[:1]
                for s_move in line.move_id:
                    s_move.branch_id = cost.branch_id and cost.branch_id.id or False
                # Prorate the value at what's still in stock
                cost_to_add = (remaining_qty / line.move_id.product_qty) * line.additional_landed_cost
                if not cost.company_id.currency_id.is_zero(cost_to_add):
                    valuation_layer = self.env['stock.valuation.layer'].create({
                        'value': cost_to_add,
                        'unit_cost': 0,
                        'quantity': 0,
                        'remaining_qty': 0,
                        'stock_valuation_layer_id': linked_layer.id,
                        'description': cost.name,
                        'stock_move_id': line.move_id.id,
                        'product_id': line.move_id.product_id.id,
                        'stock_landed_cost_id': cost.id,
                        'company_id': cost.company_id.id,
                        'branch_id': cost.branch_id and cost.branch_id.id or False,
                    })
                    linked_layer.remaining_value += cost_to_add
                    valuation_layer_ids.append(valuation_layer.id)
                    svl_in_vals = {
                        'company_id': line.move_id.company_id.id,
                        'product_id': line.move_id.product_id.id,
                        'description': "Landed Cost",
                        'remaining_qty': 0,
                        'value': cost_to_add,
                        'quantity':0,
                        'unit_cost': 0,
                        'stock_move_id': line.move_id.id,
                        'by_location':line.move_id.location_dest_id.id,
                        'location_id':line.move_id.location_id.id,
                        'location_dest_id':line.move_id.location_dest_id.id,
                        'fleet_id':line.move_id.fleet_id.id or False,
                        'division_id': line.move_id.division_id.id or False,
                        'department_id':line.move_id.department_id.id or False,
                        'fleet_location_id':line.move_id.fleet_location_id.id or False,
                        'branch_id': cost.branch_id and cost.branch_id.id or False,
                    }
                    if hasattr(line.move_id, 'project_id'):
                        svl_in_vals['project_id'] = line.move_id.project_id.id or False
                    if hasattr(line.move_id, 'repair_object_id'):
                        svl_in_vals['repair_object_id'] = line.move_id.repair_object_id.id or False
                    
                    # report_values
                    svl_report_vals = line.move_id._prepare_common_svl_report_vals([svl_in_vals])
                    valuation_report = self.env['stock.location.valuation.report']
                    valuation_report.sudo().create(svl_report_vals)
                # Update the AVCO
                product = line.move_id.product_id
                if product.cost_method == 'average':
                    cost_to_add_byproduct[product] += cost_to_add
                # Products with manual inventory valuation are ignored because they do not need to create journal entries.
                if product.valuation != "real_time":
                    continue
                # `remaining_qty` is negative if the move is out and delivered proudcts that were not
                # in stock.
                qty_out = 0
                if line.move_id._is_in():
                    qty_out = line.move_id.product_qty - remaining_qty
                elif line.move_id._is_out():
                    qty_out = line.move_id.product_qty
                move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)

            # batch standard price computation avoid recompute quantity_svl at each iteration
            products = self.env['product.product'].browse(p.id for p in cost_to_add_byproduct.keys())
            product_location_id = cost.valuation_adjustment_lines.move_id.mapped('location_dest_id')
            if len(product_location_id)>1:
                raise UserError("Please add same destination location for Receipts")
            for product in products:  # iterate on recordset to prefetch efficiently quantity_svl
                product_quant = self.env['stock.quant'].search([('location_id','=',product_location_id.id),('product_id','=', product.id)])
                if not float_is_zero(product_quant.quantity, precision_rounding=product.uom_id.rounding):
                    product.with_company(cost.company_id).sudo().with_context(disable_auto_svl=True).standard_price += cost_to_add_byproduct[product] / product_quant.quantity
                    existed_warehouse_valuation = product.warehouse_valuation.filtered(lambda x:x.location_id.id == product_location_id.id)
                    if existed_warehouse_valuation:
                        existed_warehouse_valuation.write({'location_cost': existed_warehouse_valuation.location_cost+(cost_to_add_byproduct[product] / product_quant.quantity)})
                    else:
                        vals = self.env['warehouse.valuation'].create({'location_id':product_location_id.id,'location_cost':cost_to_add_byproduct[product] / product_quant.quantity})
                        if vals:
                            product.write({'warehouse_valuation':[(4,vals.id)]})
            move_vals['stock_valuation_layer_ids'] = [(6, None, valuation_layer_ids)]
            # We will only create the accounting entry when there are defined lines (the lines will be those linked to products of real_time valuation category).
            cost_vals = {'state': 'done'}
            if move_vals.get("line_ids"):
                move = move.create(move_vals)
                cost_vals.update({'account_move_id': move.id})
            cost.write(cost_vals)
            if cost.account_move_id:
                move._post()
            cost.reconcile_landed_cost()
        return True
    
    
    def reconcile_landed_cost(self):
        for cost in self:
            if cost.vendor_bill_ids and 'draft' not in set(cost.vendor_bill_ids.mapped('state')) and cost.company_id.anglo_saxon_accounting:
                all_amls = cost.vendor_bill_ids.line_ids | cost.account_move_id.line_ids
                for product in cost.cost_lines.product_id:
                    accounts = product.product_tmpl_id.get_product_accounts()
                    input_account = accounts['stock_input']
                    all_amls.filtered(lambda aml: aml.account_id == input_account and not aml.reconciled).reconcile()
                    
                    
    def compute_landed_cost(self):
        AdjustementLines = self.env['stock.valuation.adjustment.lines']
        AdjustementLines.search([('cost_id', 'in', self.ids)]).unlink()
        self['cost_lines'].unlink()
        landed_costs_lines = self.vendor_bill_ids.filtered(lambda x:x.state=='posted').line_ids.filtered(lambda line: line.is_landed_costs_line)
        cost_lines = []
        if not landed_costs_lines:
            raise ValidationError("No landed costs product found in the vendor bills!!")
        for line in landed_costs_lines:
            cost_lines.append([0, 0, {
                'product_id':line.product_id.id,
                'name': line.product_id.name,
                'account_id': line.account_id and line.account_id.id or False,
                # 'price_unit': line.currency_id._convert(line.price_subtotal, line.company_currency_id, line.company_id, line.move_id.date),
                'price_unit': round(line.price_subtotal / line.currency_rate,2),
                'split_method': line.product_id.split_method_landed_cost or 'equal',
            }])
            line.move_id.stock_landed_costs_ids = [(4, self.id),]
            
        self['cost_lines'] = cost_lines
        
        towrite_dict = {}
        for cost in self.filtered(lambda cost: cost._get_targeted_move_ids()):
            rounding = cost.currency_id.rounding
            total_qty = 0.0
            total_cost = 0.0
            total_weight = 0.0
            total_volume = 0.0
            total_line = 0.0
            all_val_line_values = cost.get_valuation_lines()
            for val_line_values in all_val_line_values:
                for cost_line in cost.cost_lines:
                    val_line_values.update({'cost_id': cost.id, 'cost_line_id': cost_line.id})
                    self.env['stock.valuation.adjustment.lines'].create(val_line_values)
                total_qty += val_line_values.get('quantity', 0.0)
                total_weight += val_line_values.get('weight', 0.0)
                total_volume += val_line_values.get('volume', 0.0)

                former_cost = val_line_values.get('former_cost', 0.0)
                # round this because former_cost on the valuation lines is also rounded
                total_cost += cost.currency_id.round(former_cost)

                total_line += 1

            for line in cost.cost_lines:
                value_split = 0.0
                for valuation in cost.valuation_adjustment_lines:
                    value = 0.0
                    if valuation.cost_line_id and valuation.cost_line_id.id == line.id:
                        if line.split_method == 'by_quantity' and total_qty:
                            per_unit = (line.price_unit / total_qty)
                            value = valuation.quantity * per_unit
                        elif line.split_method == 'by_weight' and total_weight:
                            per_unit = (line.price_unit / total_weight)
                            value = valuation.weight * per_unit
                        elif line.split_method == 'by_volume' and total_volume:
                            per_unit = (line.price_unit / total_volume)
                            value = valuation.volume * per_unit
                        elif line.split_method == 'equal':
                            value = (line.price_unit / total_line)
                        elif line.split_method == 'by_current_cost_price' and total_cost:
                            per_unit = (line.price_unit / total_cost)
                            value = valuation.former_cost * per_unit
                        else:
                            value = (line.price_unit / total_line)

                        if rounding:
                            value = tools.float_round(value, precision_rounding=rounding, rounding_method='UP')
                            fnc = min if line.price_unit > 0 else max
                            value = fnc(value, line.price_unit - value_split)
                            value_split += value

                        if valuation.id not in towrite_dict:
                            towrite_dict[valuation.id] = value
                        else:
                            towrite_dict[valuation.id] += value
        for key, value in towrite_dict.items():
            AdjustementLines.browse(key).write({'additional_landed_cost': value})
        return True
                    
                    
                    
    # def compute_landed_cost(self):
#     #     res = super().compute_landed_cost()
class AccountMove(models.Model):
    _inherit = 'account.move'
    
    stock_landed_costs_ids = fields.Many2many(comodel_name='stock.landed.cost',copy=False)
    
    
    def action_view_stock_landed_costs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock_landed_costs.action_stock_landed_cost")
        domain = [('id', 'in', self.stock_landed_costs_ids.ids)]
        context = dict(self.env.context, default_vendor_bill_id=self.id)
        views = [(self.env.ref('stock_landed_costs.view_stock_landed_cost_tree2').id, 'tree'), (False, 'form'), (False, 'kanban')]
        return dict(action, domain=domain, context=context, views=views)
    
    def button_create_landed_costs(self):
        """Create a `stock.landed.cost` record associated to the account move of `self`, each
        `stock.landed.costs` lines mirroring the current `account.move.line` of self.
        """
        if self.move_type != 'in_invoice' or self.state != 'posted':
            raise UserError("To create landed costs , it must be vendor bills and state must be posted!!")
        self.ensure_one()
        landed_costs_lines = self.line_ids.filtered(lambda line: line.is_landed_costs_line)
        landed_costs = self.env['stock.landed.cost'].create({
            'vendor_bill_id': self.id,
            'vendor_bill_ids':[(6,0,[self.id])],
            'branch_id':  self.branch_id and self.branch_id.id or False,
            'cost_lines': [(0, 0, {
                'product_id': l.product_id.id,
                'name': l.product_id.name,
                'account_id': l.product_id.product_tmpl_id.get_product_accounts()['stock_input'].id,
                'price_unit': l.currency_id._convert(l.price_subtotal, l.company_currency_id, l.company_id, l.move_id.date),
                'split_method': l.product_id.split_method_landed_cost or 'equal',
            }) for l in landed_costs_lines],
        })
        action = self.env["ir.actions.actions"]._for_xml_id("stock_landed_costs.action_stock_landed_cost")
        return dict(action, view_mode='form', res_id=landed_costs.id, views=[(False, 'form')])    
        
    @api.depends('line_ids', 'line_ids.is_landed_costs_line')
    def _compute_landed_costs_visible(self):
        for account_move in self:
            if account_move.stock_landed_costs_ids:
                account_move.landed_costs_visible = False
            else:
                account_move.landed_costs_visible = any(line.is_landed_costs_line for line in account_move.line_ids)