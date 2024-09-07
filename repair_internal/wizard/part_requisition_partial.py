# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round


class PartsRequisitionPartialLine(models.TransientModel):
    _name = "part.requisition.partial.line"
    _rec_name = 'product_id'
    _description = 'Part Requisition Partial Line'

    product_id = fields.Many2one('product.product', string="Product", required=True, domain="[('id', '=', product_id)]")
    quantity = fields.Float("Quantity", digits='Product Unit of Measure', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id')
    wizard_id = fields.Many2one('part.requisition.partial', string="Wizard")
    requisition_line = fields.Many2one('part.requisition.line',string="Part Requisition Line", store=True)


class PartRequisitionPartial(models.TransientModel):
    _name = 'part.requisition.partial'
    _description = 'Part Requisition Partial'

    @api.model
    def default_get(self, fields):
        res = super(PartRequisitionPartial, self).default_get(fields)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'part.requisition':
            if len(self.env.context.get('active_ids', list())) > 1:
                raise UserError(_("You may only return one adjustment at a time."))
            part_requisition = self.env['part.requisition'].browse(self.env.context.get('active_id'))
            if part_requisition.exists():
                res.update({'part_requisition_id': part_requisition.id})
        return res

    part_requisition_id = fields.Many2one('part.requisition')
    product_return_moves = fields.One2many('part.requisition.partial.line', 'wizard_id', 'Moves')
    company_id = fields.Many2one(related='part_requisition_id.company_id')
   


    @api.onchange('part_requisition_id')
    def _onchange_requisition_id(self):
        product_return_moves = []
        
        line_fields = [f for f in self.env['requisition.partial.line']._fields.keys()]
        product_return_moves_data_tmpl = self.env['requisition.partial.line'].default_get(line_fields)
        for move in self.part_requisition_id.requisition_line:
            
            product_return_moves_data = dict(product_return_moves_data_tmpl)
            product_return_moves_data.update(self._prepare_stock_return_picking_line_vals_from_move(move))
            product_return_moves.append(product_return_moves_data)
        if self.part_requisition_id and not product_return_moves:
            raise UserError(_("No products to return (only lines in Done state and not fully returned yet can be returned)."))
        else:
            requisition = []
            for val in product_return_moves:
                if val.get('quantity')>0:
                    req = self.env['part.requisition.partial.line'].create({
                        'product_id':val.get('product_id'),
                        'quantity':val.get('quantity'),
                        'uom_id':val.get('uom_id'),
                        'requisition_line':val.get('requisition_line')
                    })
                    requisition.append(req.id)

            self.write({'product_return_moves':[(6,0,requisition)]})
        
            

    @api.model
    def _prepare_stock_return_picking_line_vals_from_move(self, requisition_line):
        quantity = requisition_line.issue_qty-requisition_line.done_qty
        quantity = float_round(quantity, precision_rounding=requisition_line.product_id.uom_id.rounding)
        return {
            'product_id': requisition_line.product_id.id,
            'quantity': quantity,
            'uom_id': requisition_line.product_id.uom_id.id,
            'requisition_line':requisition_line.id
            
        }

   

    def _create_returns(self):
        flag = True
        if not self.product_return_moves or sum(self.product_return_moves.mapped('quantity'))==0:
            raise UserError(_("There is No Line for Requisition"))
        for val in self.product_return_moves:
            if val.requisition_line.issue_qty-val.requisition_line.done_qty<val.quantity:
                raise UserError(_("Prepare Qty is not matched with Requisition's Quantity"))
            
        self.part_requisition_id.action_done(self.product_return_moves)
        for val in self.product_return_moves:
            val.requisition_line.write({'done_qty':val.quantity+val.requisition_line.done_qty})

        for req_line in self.part_requisition_id.requisition_line:
            if req_line.done_qty != req_line.issue_qty:
                flag = False
        if flag:
            self.part_requisition_id.write({'state':'done', 'parts_state':'done'})
        # update order
        req_forms =  self.part_requisition_id.job_order_id.requisition_ids + self.part_requisition_id.job_request_id.requisition_ids
        order_part_flag = get_part_flag_from_part_requisition(req_forms)
        self.part_requisition_id.job_request_id.write({'part_state':order_part_flag})
   
    def create_partial_part(self):
        for wizard in self:
            new_requisition_id = wizard._create_returns()

def get_part_flag_from_part_requisition(req_forms):
    order_part_flag = 'done'
    for req_form in req_forms:
        if req_form.state != 'close':
            if req_form.state in ('draft','confirm'):
                order_part_flag = 'request'
            else:
                for req_line in req_form.requisition_line:
                    if  req_line.done_qty != req_line.issue_qty:
                        order_part_flag = 'wait'
                        break    
    return order_part_flag
