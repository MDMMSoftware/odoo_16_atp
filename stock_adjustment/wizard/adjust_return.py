# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

class ReturnAdjustmentLine(models.TransientModel):
    _name = "stock.return.adjust.line"
    _rec_name = 'product_id'
    _description = 'Return Adjustment Line'

    product_id = fields.Many2one('product.product', string="Product", required=True, domain="[('id', '=', product_id)]")
    quantity = fields.Float("Quantity", digits='Product Unit of Measure', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id')
    wizard_id = fields.Many2one('stock.return.adjust', string="Wizard")
    adjustment_line_id = fields.Many2one('stock.inventory.adjustment.line',string="Adjustment Line")


class ReturnAdjustment(models.TransientModel):
    _name = 'stock.return.adjust'
    _description = 'Return Adjustment'

    @api.model
    def default_get(self, fields):
        res = super(ReturnAdjustment, self).default_get(fields)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'stock.inventory.adjustment':
            if len(self.env.context.get('active_ids', list())) > 1:
                raise UserError(_("You may only return one adjustment at a time."))
            adjust = self.env['stock.inventory.adjustment'].browse(self.env.context.get('active_id'))
            if adjust.exists():
                res.update({'adjust_id': adjust.id})
        return res

    adjust_id = fields.Many2one('stock.inventory.adjustment')
    product_return_moves = fields.One2many('stock.return.adjust.line', 'wizard_id', 'Moves')
    move_dest_exists = fields.Boolean('Chained Move Exists', readonly=True)
    original_location_id = fields.Many2one('stock.location')
    parent_location_id = fields.Many2one('stock.location')
    company_id = fields.Many2one(related='adjust_id.company_id')
    location_id = fields.Many2one(
        'stock.location', 'Return Location',
        domain="['|', ('id', '=', original_location_id), '|', '&', ('return_location', '=', True), ('company_id', '=', False), '&', ('return_location', '=', True), ('company_id', '=', company_id)]")


    @api.onchange('adjust_id')
    def _onchange_adjust_id(self):
        move_dest_exists = False
        product_return_moves = [(5,)]
        if self.adjust_id and self.adjust_id.state != 'done':
            raise UserError(_("You may only return Done pickings."))
        # In case we want to set specific default values (e.g. 'to_refund'), we must fetch the
        # default values for creation.
        line_fields = [f for f in self.env['stock.return.adjust.line']._fields.keys()]
        product_return_moves_data_tmpl = self.env['stock.return.adjust.line'].default_get(line_fields)
        for move in self.adjust_id.adjustment_line_id:
            
            product_return_moves_data = dict(product_return_moves_data_tmpl)
            product_return_moves_data.update(self._prepare_stock_return_picking_line_vals_from_move(move))
            product_return_moves.append((0, 0, product_return_moves_data))
        if self.adjust_id and not product_return_moves:
            raise UserError(_("No products to return (only lines in Done state and not fully returned yet can be returned)."))
        if self.adjust_id:
            self.product_return_moves = product_return_moves
            self.move_dest_exists = move_dest_exists
            location_id = self.adjust_id.location_id.id
            self.location_id = location_id

    @api.model
    def _prepare_stock_return_picking_line_vals_from_move(self, adjust_line):
        quantity = adjust_line.quantity
        return_line = self.env['stock.inventory.adjustment.line'].search([('origin_returned_adjust_line_id','=',adjust_line.id)])
        for line in return_line:
            if line.quantity<0:
                quantity -= line.quantity
            else:
                quantity += line.quantity
        quantity = float_round(quantity, precision_rounding=adjust_line.product_id.uom_id.rounding)
        return {
            'product_id': adjust_line.product_id.id,
            'quantity': quantity>0 and -abs(quantity) or abs(quantity),
            'uom_id': adjust_line.product_id.uom_id.id,
            'adjustment_line_id':adjust_line.id
            
        }

    def _prepare_move_default_values(self, return_line, new_adjust):
        origin_return_line = self.env['stock.inventory.adjustment.line'].browse(return_line.adjustment_line_id.id)
        vals = {
            'product_id': return_line.product_id.id,
            'quantity': return_line.quantity,
            'uom_id': return_line.product_id.uom_id.id,
            'adjustment_line_id':origin_return_line.id,
            'adjust_account_id':origin_return_line.adjust_account_id.id,
            'fleet_id':origin_return_line.fleet_id.id,
            'fleet_location_id': origin_return_line.fleet_location_id.id,
            'description': origin_return_line.description,
            'job_code_id': origin_return_line.job_code_id.id,
            'employee_id': origin_return_line.employee_id.id,
            'analytic_distribution': origin_return_line.analytic_distribution,
            'division_id': origin_return_line.division_id.id or False,
            'unit_cost':return_line.product_id.warehouse_valuation.filtered(lambda x:x.location_id==self.location_id) and return_line.product_id.warehouse_valuation.filtered(lambda x:x.location_id==self.location_id).location_cost or origin_return_line.unit_cost,        
        }
        if hasattr(origin_return_line, 'project_id'):
            vals['project_id'] = origin_return_line.project_id.id or False
        if hasattr(origin_return_line, 'repair_object_id'):
            vals['repair_object_id'] = origin_return_line.repair_object_id.id or False
        return vals

    def _prepare_adjust_default_values(self):
        vals = {
            'state': 'draft',
            'origin_returned_adjust_id': self.adjust_id.id,
            'journal_id':self.adjust_id.journal_id.id,
            'department_id':self.adjust_id.department_id.id,
        }

        if self.adjust_id.location_id:
            vals['location_id'] = self.adjust_id.location_id.id
       
        return vals

    def _create_returns(self):
        # for returned_line in self.product_return_moves:
        #     if returned_line.quantity < self.adjust_id.adjustment_line_id.filtered(lambda x:x.product_id==returned_line.product_id):
        #         raise ValidationError("Quantity must be greater that")
        new_adjust = self.adjust_id.copy(self._prepare_adjust_default_values())
        new_adjust.name = None
        result = []
        returned_lines = 0
        for return_line in self.product_return_moves:
            
            if return_line.quantity:
                returned_lines += 1
                vals = self._prepare_move_default_values(return_line, new_adjust)
                result.append(vals)
        if result:
            adjument_line_id_lst = []
            for res in result:
                values = (0, 0,
                                {
                                        'product_id': res['product_id'],
                                        'quantity': res['quantity'],
                                        'uom_id': res['uom_id'],
                                        'origin_returned_adjust_line_id':res['adjustment_line_id'],
                                        'adjust_account_id':res['adjust_account_id'],
                                        'unit_cost':res['unit_cost'],
                                        'fleet_id':res['fleet_id'],
                                        'fleet_location_id':res['fleet_location_id'],
                                        'description':res['description'],
                                        'job_code_id':res['job_code_id'],
                                        'employee_id':res['employee_id'],
                                        'analytic_distribution':res['analytic_distribution'],
                                        'division_id':res['division_id'],
                                }
                        )
                if hasattr(new_adjust.adjustment_line_id, 'project_id'):
                    values[2]['project_id'] = res['project_id']
                if hasattr(new_adjust.adjustment_line_id, 'repair_object_id'):
                    values[2]['repair_object_id'] = res['repair_object_id']                    
                adjument_line_id_lst.append(values)
            new_adjust.write({'adjustment_line_id':adjument_line_id_lst})
        if not returned_lines:
            raise UserError(_("Please specify at least one non-zero quantity."))

        return new_adjust.id

    def create_returns(self):
        for wizard in self:
            new_adjust_id = wizard._create_returns()
        
        return {
            'name': _('Returned Adjustment'),
            'view_mode': 'form',
            'res_model': 'stock.inventory.adjustment',
            'res_id': new_adjust_id,
            'type': 'ir.actions.act_window',
        }
