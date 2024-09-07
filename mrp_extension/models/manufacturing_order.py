from odoo import models,fields,api,_
from odoo.exceptions import ValidationError, UserError
from ast import literal_eval

class ManufacturingOrder(models.Model):
    _inherit = "mrp.production"

    request_location = fields.Many2one('stock.location',string="Request Location",required=True)
    request_journal = fields.Many2one('account.journal',string="MRP Journal",required=True)
    requisition_id = fields.Many2one('requisition',string="Requisitions")
    labor_line = fields.One2many(comodel_name='mrp.labor',inverse_name='mrp_id',string="Labor Lines",copy=True)
    labor_valuation_layer = fields.Many2one('stock.valuation.layer')
    mrp_move_id = fields.Many2one('account.move',string="Journal Entry")

    def action_open_requisitions(self):
        return {
            'name': _('Requisitions'),
            'view_mode': 'tree,form',
            'res_model': 'requisition',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.requisition_id.ids)],              
        } 
        
    def action_open_moves(self):
        return {
            'name': _('Journal Entry'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.mrp_move_id.ids)],              
        }    

    def action_confirm(self):
        res = super().action_confirm()
        if self.request_location:
            requisition_id = self.env['requisition'].create({
                                            'request_person_id':self.user_id and self.user_id.employee_id.id or False,
                                            'required_date':self.date_planned_start,
                                            'order_date':self.date_planned_start,
                                            'src_location_id':self.request_location.id,
                                            'location_id':self.location_src_id.id,
                                            'internal_ref':self.name,
                                            'production_id':self.id,
                                            'requisition_line':[(0, 0, {
                                                    'product_id': raw.product_id.id,
                                                    'qty': raw.product_uom_qty,
                                                    'production_move_id':raw.id,
                                                }) for raw in self.move_raw_ids]})
            self.requisition_id = requisition_id and requisition_id.id or False
        return res
    
    
    
    def button_mark_done(self):
        if self.components_availability == 'Not Available' and self.requisition_id:
            raise ValidationError(_("Please done for the requisition first"))
        self._button_mark_done_sanity_checks()

        if not self.env.context.get('button_mark_done_production_ids'):
            self = self.with_context(button_mark_done_production_ids=self.ids)
        res = self._pre_button_mark_done()
        if res is not True:
            return res

        if self.env.context.get('mo_ids_to_backorder'):
            productions_to_backorder = self.browse(self.env.context['mo_ids_to_backorder'])
            productions_not_to_backorder = self - productions_to_backorder
        else:
            productions_not_to_backorder = self
            productions_to_backorder = self.env['mrp.production']

        self.workorder_ids.button_finish()

        backorders = productions_to_backorder and productions_to_backorder._split_productions()
        backorders = backorders - productions_to_backorder

        productions_not_to_backorder._post_inventory(cancel_backorder=True)
        productions_to_backorder._post_inventory(cancel_backorder=True)

        # if completed products make other confirmed/partially_available moves available, assign them
        done_move_finished_ids = (productions_to_backorder.move_finished_ids | productions_not_to_backorder.move_finished_ids).filtered(lambda m: m.state == 'done')
        done_move_finished_ids._trigger_assign()
        
        mo_move_id =self.env['stock.move'].search([('production_id','=',self.id)])
        mo_raw_move_id = self.env['stock.move'].search([('raw_material_production_id','=',self.id)])
        mo_move_ids = mo_move_id+mo_raw_move_id
        for move in mo_move_ids:
            for line in move.move_line_ids:
                line.write({'date': self.date_planned_start})
                
        
        move = self.env['account.move']
        move_vals = {
            'journal_id': self.request_journal.id,
            'date': self.date_planned_start,
            'ref': self.name,
            'line_ids': [],
            'move_type': 'entry',
        }
        if done_move_finished_ids and self.labor_line:
            # remaining_qty = sum(done_move_finished_ids.stock_valuation_layer_ids.mapped('remaining_qty'))
            # linked_layer = self.env['stock.valuation.layer'].search([('stock_move_id','=',done_move_finished_ids.id)])
            # valuation_layer = self.env['stock.valuation.layer'].create({
            #     'value': sum(self.labor_line.mapped('total'))/self.product_uom_qty,
            #     'unit_cost': 0,
            #     'quantity': 0,
            #     'remaining_qty': 0,
            #     'stock_valuation_layer_id': linked_layer.id,
            #     'description': self.name,
            #     'stock_move_id': done_move_finished_ids.id,
            #     'product_id': done_move_finished_ids.product_id.id,
            #     'company_id': self.company_id.id,
            # })
            # linked_layer.remaining_value += sum(self.labor_line.mapped('total'))/self.product_uom_qty
            # self.labor_valuation_layer = valuation_layer.id
            # svl_in_vals = {
            #     'company_id': done_move_finished_ids.company_id.id,
            #     'product_id': done_move_finished_ids.product_id.id,
            #     'description': "Landed Cost",
            #     'remaining_qty': 0,
            #     'value': sum(self.labor_line.mapped('total'))/self.product_uom_qty,
            #     'quantity':0,
            #     'unit_cost': 0,
            #     'stock_move_id': done_move_finished_ids.id,
            #     'by_location':done_move_finished_ids.location_dest_id.id,
            #     'location_id':done_move_finished_ids.location_id.id,
            #     'location_dest_id':done_move_finished_ids.location_dest_id.id,
            #     'fleet_id':done_move_finished_ids.fleet_id.id or False,
            #     'division_id': done_move_finished_ids.division_id.id or False,
            #     'department_id':done_move_finished_ids.department_id.id or False,
            #     'fleet_location_id':done_move_finished_ids.fleet_location_id.id or False,
            # }
            # if hasattr(done_move_finished_ids, 'project_id'):
            #     svl_in_vals['project_id'] = done_move_finished_ids.project_id.id or False
            # if hasattr(done_move_finished_ids, 'repair_object_id'):
            #     svl_in_vals['repair_object_id'] = done_move_finished_ids.repair_object_id.id or False
            
            # report_values
            # svl_report_vals = done_move_finished_ids._prepare_common_svl_report_vals([svl_in_vals])
            # valuation_report = self.env['stock.location.valuation.report']
            # valuation_report.sudo().create(svl_report_vals)
            
            AccountMoveLine = []
            credit_lines = []
            debit_account_id = self.product_id.categ_id.property_stock_account_input_categ_id.id
            if not debit_account_id:
                raise UserError(_('Please configure Stock Expense Account for product: %s.') % (self.product_id.name))
            
            accounts = self.product_id.product_tmpl_id.get_product_accounts()
            # debit_account_id = accounts.get('stock_valuation') and accounts['stock_valuation'].id or False
            base_line = {
                'name': self.name,
                'product_id': self.product_id.id,
                'quantity': 0,
            }
            debit_line = dict(base_line, account_id=debit_account_id)
            diff = sum(self.labor_line.mapped('total'))
            if diff > 0:
                debit_line['debit'] = diff
                # credit_line['credit'] = diff
                for labor in self.labor_line:
                    AccountMoveLine.append([0, 0, {
                        'name': labor.desc,
                        'product_id': labor.product_id.id,
                        'quantity': 0,
                        'account_id': labor.account_id.id,
                        'credit': labor.total,
                        
                    }])
            else:
                # negative cost, reverse the entry
                debit_line['credit'] = -diff
                # credit_line['debit'] = -diff
                for labor in self.labor_line:
                    AccountMoveLine.append([0, 0, {
                        'name': labor.desc,
                        'product_id': labor.product_id.id,
                        'quantity': 0,
                        'account_id': labor.account_id.id,
                        'credit': -labor.total,
                        
                    }])
            AccountMoveLine.append([0, 0, debit_line])


            move_vals['line_ids'] += AccountMoveLine
            
            # move_vals['stock_valuation_layer_ids'] = [(6, None, valuation_layer.ids)]
            # We will only create the accounting entry when there are defined lines (the lines will be those linked to products of real_time valuation category).
            if move_vals.get("line_ids"):
                move = move.create(move_vals)
                self.mrp_move_id = move and move.id or False
                move._post()

        # Moves without quantity done are not posted => set them as done instead of canceling. In
        # case the user edits the MO later on and sets some consumed quantity on those, we do not
        # want the move lines to be canceled.
        (productions_not_to_backorder.move_raw_ids | productions_not_to_backorder.move_finished_ids).filtered(lambda x: x.state not in ('done', 'cancel')).write({
            'state': 'done',
            'product_uom_qty': 0.0,
        })
        for production in self:
            production.write({
                'date_finished': fields.Datetime.now(),
                'product_qty': production.qty_produced,
                'priority': '0',
                'is_locked': True,
                'state': 'done',
            })

        if not backorders:
            if self.env.context.get('from_workorder'):
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'mrp.production',
                    'views': [[self.env.ref('mrp.mrp_production_form_view').id, 'form']],
                    'res_id': self.id,
                    'target': 'main',
                }
            if self.user_has_groups('mrp.group_mrp_reception_report') and self.picking_type_id.auto_show_reception_report:
                lines = self.move_finished_ids.filtered(lambda m: m.product_id.type == 'product' and m.state != 'cancel' and m.quantity_done and not m.move_dest_ids)
                if lines:
                    if any(mo.show_allocation for mo in self):
                        action = self.action_view_reception_report()
                        return action
            return True
        context = self.env.context.copy()
        context = {k: v for k, v in context.items() if not k.startswith('default_')}
        for k, v in context.items():
            if k.startswith('skip_'):
                context[k] = False
        action = {
            'res_model': 'mrp.production',
            'type': 'ir.actions.act_window',
            'context': dict(context, mo_ids_to_backorder=None, button_mark_done_production_ids=None)
        }
        if len(backorders) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': backorders[0].id,
            })
        else:
            action.update({
                'name': _("Backorder MO"),
                'domain': [('id', 'in', backorders.ids)],
                'view_mode': 'tree,form',
            })
        return action
    
    
    def action_view_stock_valuation_layers(self):
        self.ensure_one()
        domain = [('id', 'in', (self.move_raw_ids + self.move_finished_ids + self.scrap_ids.move_id).stock_valuation_layer_ids.ids+self.labor_valuation_layer.ids)]
        action = self.env["ir.actions.actions"]._for_xml_id("stock_account.stock_valuation_layer_action")
        context = literal_eval(action['context'])
        context.update(self.env.context)
        context['no_at_date'] = True
        context['search_default_group_by_product_id'] = False
        return dict(action, domain=domain, context=context)
    
    
    # def _create_accounting_entries(self, move, qty_out):
    #     # TDE CLEANME: product chosen for computation ?
    #     cost_product = self.product_id
    #     if not cost_product:
    #         return False
    #     accounts = self.product_id.product_tmpl_id.get_product_accounts()
    #     debit_account_id = accounts.get('stock_valuation') and accounts['stock_valuation'].id or False
      
    #     already_out_account_id = accounts['stock_output'].id
    #     credit_account_id = cost_product.categ_id.property_stock_account_input_categ_id.id

    #     if not credit_account_id:
    #         raise UserError(_('Please configure Stock Expense Account for product: %s.') % (cost_product.name))

    #     return self._create_account_move_line(move, credit_account_id, debit_account_id, qty_out, already_out_account_id)

    # def _create_account_move_line(self, move, credit_account_id, debit_account_id, qty_out, already_out_account_id):
    #     """
    #     Generate the account.move.line values to track the landed cost.
    #     Afterwards, for the goods that are already out of stock, we should create the out moves
    #     """
    #     AccountMoveLine = []

    #     base_line = {
    #         'name': self.name,
    #         'product_id': self.product_id.id,
    #         'quantity': 0,
    #     }
    #     debit_line = dict(base_line, account_id=debit_account_id)
    #     credit_line = dict(base_line, account_id=credit_account_id)
    #     diff = sum(self.labor_line.mapped('total'))
    #     if diff > 0:
    #         debit_line['debit'] = diff
    #         credit_line['credit'] = diff
    #     else:
    #         # negative cost, reverse the entry
    #         debit_line['credit'] = -diff
    #         credit_line['debit'] = -diff
    #     AccountMoveLine.append([0, 0, debit_line])
    #     AccountMoveLine.append([0, 0, credit_line])

    #     # Create account move lines for quants already out of stock
    #     if qty_out > 0:
    #         debit_line = dict(base_line,
    #                           name=(self.name + ": " + str(qty_out) + _(' already out')),
    #                           quantity=0,
    #                           account_id=already_out_account_id)
    #         credit_line = dict(base_line,
    #                            name=(self.name + ": " + str(qty_out) + _(' already out')),
    #                            quantity=0,
    #                            account_id=debit_account_id)
    #         diff = diff * qty_out / self.quantity
    #         if diff > 0:
    #             debit_line['debit'] = diff
    #             credit_line['credit'] = diff
    #         else:
    #             # negative cost, reverse the entry
    #             debit_line['credit'] = -diff
    #             credit_line['debit'] = -diff
    #         AccountMoveLine.append([0, 0, debit_line])
    #         AccountMoveLine.append([0, 0, credit_line])

    #         if self.env.company.anglo_saxon_accounting:
    #             expense_account_id = self.product_id.product_tmpl_id.get_product_accounts()['expense'].id
    #             debit_line = dict(base_line,
    #                               name=(self.name + ": " + str(qty_out) + _(' already out')),
    #                               quantity=0,
    #                               account_id=expense_account_id)
    #             credit_line = dict(base_line,
    #                                name=(self.name + ": " + str(qty_out) + _(' already out')),
    #                                quantity=0,
    #                                account_id=already_out_account_id)

    #             if diff > 0:
    #                 debit_line['debit'] = diff
    #                 credit_line['credit'] = diff
    #             else:
    #                 # negative cost, reverse the entry
    #                 debit_line['credit'] = -diff
    #                 credit_line['debit'] = -diff
    #             AccountMoveLine.append([0, 0, debit_line])
    #             AccountMoveLine.append([0, 0, credit_line])

    #     return AccountMoveLine
    
    
    
class Requisition(models.Model):
    _inherit = "requisition"
    
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order')   
    
class MRPLabor(models.Model):
    _name = "mrp.labor"
    
    product_id = fields.Many2one('product.product',string="Other Costs",domain="[('detailed_type', '=', 'service')]")
    desc = fields.Char(string="Description",related='product_id.name')
    qty = fields.Float(string="Qty",default=1.0)
    price = fields.Float(string="Price",default=0.0)
    total = fields.Float(string="Total Amt",compute='calculate_total',store=True)
    account_id = fields.Many2one('account.account',required=True,string="Account")
    remark = fields.Char("Remark")
    mrp_id = fields.Many2one('mrp.production')
    
    @api.depends('qty','price')
    def calculate_total(self):
        for res in self:
            res.total = res.qty*res.price
            
            
class ChangeProductionQty(models.TransientModel):
    _inherit = 'change.production.qty'
    _description = 'Change Production Qty'
    
    
    def change_prod_qty(self):
        res = super().change_prod_qty()
        if self.mo_id.requisition_id and not self.mo_id.requisition_id.picking_ids:
            for line in self.mo_id.requisition_id.requisition_line:
                line.write({'qty':line.production_move_id.product_uom_qty,
                            })
        if self.mo_id.requisition_id.picking_ids:
            raise ValidationError(_("Quantity to Produce is invalid when the requisition generate the transfer"))
                
            
        return res
    
    
# class StockMove(models.Model):
#     _inherit = 'stock.move'
    
#     def _action_assign(self, force_qty=False):
#         res = super(StockMove, self)._action_assign(force_qty=force_qty)
        
#         return res