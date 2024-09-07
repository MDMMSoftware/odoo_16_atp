from odoo import api, fields, models, tools, _,Command
from odoo.exceptions import ValidationError,UserError
from odoo.tools import float_compare, float_is_zero, OrderedSet,float_repr
from ...generate_code import generate_code
import io
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    # TODO saas-17: remove the try/except to directly import from misc
    import xlsxwriter
import logging
import os
import tempfile

class StockAdjustment(models.Model):
    _name = "stock.inventory.adjustment"
    _inherit = "mail.thread"

    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    
    def _get_department_domain(self):
        """methode to get department domain"""
        company = self.env.company
        department_ids = self.env.user.department_ids
        department = department_ids.filtered(
            lambda department: department.company_id == company)
        return [('id', 'in', department.ids)]

    department_id = fields.Many2one('res.department', string='Department', store=True,tracking=True,
                                
                                help='Leave this field empty if this account is'
                                     ' shared between all departmentes')

    branch_ids = fields.Many2one('res.branch', string='Branch', store=True,
                                readonly=False,domain=_get_branch_domain,required=False)

    name = fields.Char("Name",copy=False)
    date = fields.Date(string="Date",required=True,tracking = True)
    journal_id = fields.Many2one('account.journal',string="Journal",required=True,tracking = True)
    location_id = fields.Many2one('stock.location',string="Location",domain="[('usage', '=', 'internal')]",required=True,tracking = True)
    ref = fields.Char('Reference',tracking = True)
    
    adjustment_line_id = fields.One2many('stock.inventory.adjustment.line','adjust_id',string="Adjustment Lines")
    # Used to search on stock adjustment
    product_id = fields.Many2one('product.product', 'Product', related='adjustment_line_id.product_id', readonly=True)
    # fleet_id = fields.Many2one('fleet.vehicle', 'Fleet', related='adjustment_line_id.fleet_id', readonly=True)

    state = fields.Selection([
        ('draft','Draft'),('confirm','Confirm'),('done','Done'),('return','Return')],string='Status',default="draft",tracking = True)
    valuation_ids = fields.Many2many('stock.valuation.layer','adjustment_valuation_rel','adjust_id','valuation_id',readonly=True, ondelete='cascade',copy=False,
        check_company=True)
    move_ids = fields.Many2many('account.move','adjustment_move_rel','adjust_id','move_id',readonly=True, ondelete='cascade',copy=False,
        check_company=True)
    origin_returned_adjust_id = fields.Many2one(
        'stock.inventory.adjustment', 'Origin Return Adjust', copy=False, index=True,
        help='Move that created the return adjust', check_company=True,readonly=True)
    company_id = fields.Many2one('res.company',string="Company", required=True, default=lambda self: self.env.company)
    has_refund = fields.Boolean(default=False)
    partner_id = fields.Many2one('res.partner',string="Partner")
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")
    
    def action_check_diff(self):
        self = self.search([])
        result = []
        for res in self:
            valuation_amount = round(sum(res.valuation_ids.account_move_id.mapped('amount_total')),2)
            adj_amount = round(sum(res.move_ids.filtered(lambda x:x.id not in res.valuation_ids.account_move_id.ids).mapped('amount_total')),2)
            if valuation_amount!=adj_amount:
                result.append(res.id)
        print ("RESULT",result)
        

    @api.constrains('adjustment_line_id')
    def _auto_save_and_copy_analytic_distribution_for_adjustment_line(self):
        if hasattr(self.adjustment_line_id, 'project_id'):
            adjustment_line_with_project = self.adjustment_line_id.search([('project_id','!=',False),('adjust_id','=',self.id)],limit=1)
            if adjustment_line_with_project:
                dct = adjustment_line_with_project.analytic_distribution
                adjustment_lines_without_project = self.adjustment_line_id.filtered(lambda x:not x.project_id)
                for line in adjustment_lines_without_project:
                    line.write({
                                'project_id':adjustment_line_with_project.project_id.id,
                                'analytic_distribution':dct
                            })
            else:
                if  not (self.requisition_id or self.repair_request_id or self.job_order_id) or ((self.requisition_id or self.repair_request_id or self.job_order_id) and self.state != 'draft'):
                    raise UserError("At least one project is required to create adjustment")          

    def action_open_valuations(self):
        return {
            'name': _('Inventory Valuations(Adjustment)'),
            'view_mode': 'tree,form',
            'res_model': 'stock.valuation.layer',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.valuation_ids.ids)],              
        } 
    
    def action_open_valuation_moves(self):
        return {
            'name': _('Journal Entry(Adjustment)'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.move_ids.ids)],              
        }
    
    def action_open_child_returneds(self):
        returned_adjust_ids = self.env['stock.inventory.adjustment'].search([('origin_returned_adjust_id','=',self.id)]).ids
        return {
            'name': _('Returned Inventory Adjustments'),
            'view_mode': 'tree,form',
            'res_model': 'stock.inventory.adjustment',
            'view_id': False,
            'type' : 'ir.actions.act_window',
            'domain' : [('id', 'in',returned_adjust_ids)]
        }

    def action_confirm(self):
        for res in self.adjustment_line_id:
            if res.unit_cost < 1 or res.unit_value<1:
                raise ValidationError(_("Unit Cost or Unit Value must be positive"))
        sequence = self.env['sequence.model']
        if not self.name:
            self.name = generate_code.generate_code(sequence,self,self.branch_ids,self.company_id,self.date,None,None)
        self.state='confirm'

    def action_reset_to_draft(self):
        if not (self.env.user.has_group('stock.group_stock_user') or self.env.user.has_group('stock.group_stock_manager')):
            raise UserError(("User %s doesn't get Inventory Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        self.state = 'draft'

    
    def action_validate(self):
        if not (self.env.user.has_group('stock.group_stock_user') or self.env.user.has_group('stock.group_stock_manager')):
            raise UserError(("User %s doesn't get Inventory Access")%(self.env.user.name))
        if self.department_id:
            if self.env.user.id not in self.department_id.approve_user_id.ids:
                raise UserError(_("User %s doesn't include in %s Department")%(self.env.user.name,self.department_id.name))
        if self.origin_returned_adjust_id:
            name = 'Product Quantity Updated (Returned)'
        else:
            name = 'Product Quantity Updated'             
        for adj_line in self.adjustment_line_id:
            if not adj_line.move_ids:
                if adj_line.product_id.detailed_type == 'product':
                    sum_of_quantity = adj_line.quantity
                    if sum_of_quantity < 0:
                        available_quantity = 0
                        if adj_line.product_id and self.location_id:
                            quants = self.env['stock.quant'].search([
                                    ('product_id', '=', adj_line.product_id.id),('location_id', '=', self.location_id.id)
                                ])
                            for qt in quants:
                                available_quantity += qt._get_available_quantity(adj_line.product_id, self.location_id)
                        if  abs(sum_of_quantity) > available_quantity or available_quantity == 0.0:
                            raise ValidationError('%s is not available to sale.Please check available stock.'% adj_line.product_id.name)                 
                if adj_line.quantity<0:
                    name = name
                    vals = {
                    'name':  name,
                    'product_id': adj_line.product_id.id,
                    'product_uom': adj_line.uom_id.id,
                    'product_uom_qty': abs(adj_line.quantity),
                    'state': 'confirmed',
                    'location_id': self.location_id.id,
                    'location_dest_id': adj_line.product_id.property_stock_inventory.id,
                    'is_inventory': True,
                    'adjust_id':self.id,
                    'adjustment_line_id':adj_line.id,
                    'division_id':adj_line.division_id.id,
                    'department_id':self.department_id.id or False,
                    'branch_id': self.branch_ids.id or False,
                    'move_line_ids': [(0, 0, {
                        'product_id': adj_line.product_id.id,
                        'product_uom_id': adj_line.uom_id.id,
                        'qty_done': abs(adj_line.quantity),
                        'location_id': self.location_id.id,
                        'location_dest_id': adj_line.product_id.property_stock_inventory.id,
                        'company_id': self.env.company.id,
                        'division_id':adj_line.division_id.id,
                        'department_id':self.department_id.id or False,
                    })]
                }
                    if hasattr(self.env['stock.move'], 'fleet_id'):
                        vals.update({'fleet_id': adj_line.fleet_id.id or False})
                    if hasattr(self.env['stock.move'], 'project_id'):
                        vals.update({'project_id': adj_line.project_id.id or False})
                    if hasattr(self.env['stock.move'], 'repair_object_id'):
                        vals.update({'repair_object_id': adj_line.repair_object_id.id or False})
                    if hasattr(self.env['stock.move'], 'fleet_location_id'):
                        vals.update({'fleet_location_id':adj_line.fleet_location_id.id or False})
                    moves = self.env['stock.move'].with_context(inventory_mode=False).create(vals)
                    moves.write({'adjust_id':self.id})
                    moves._action_done()
                    for valuation in moves.stock_valuation_layer_ids:
                        valuation.write({'adjust_id':self.id,
                                        'adjustment_line_id':adj_line.id,})
                        
                        self.write({'valuation_ids':[(4,valuation.id)]})
                    moves = self.env['account.move'].search([('stock_move_id','=',moves.id)])
                    for move in moves:
                        self.write({'move_ids':[(4,move.id)]})
                        adj_line.write({'move_ids':[(4,move.id)]})

                    self.location_id.write({'last_inventory_date': fields.Date.today()})
                    if self.has_refund:
                        product = self.env['product.product'].browse(adj_line.product_id.id)

                        if product:                        
                            invoice_line_dct = {
                                    'name': adj_line.description,
                                    'price_unit': adj_line.unit_value,
                                    'account_id': product.categ_id.property_stock_account_output_categ_id.id,
                                    'fleet_id':adj_line.fleet_id and adj_line.fleet_id.id or False,
                                    'division_id':adj_line.division_id and adj_line.division_id.id or False,
                                    'analytic_distribution':adj_line.analytic_distribution,
                                }
                            if hasattr(adj_line, 'project_id'):
                                invoice_line_dct['project_id'] = adj_line.project_id.id or False
                            if hasattr(adj_line, 'repair_object_id'):
                                invoice_line_dct['repair_object_id'] = adj_line.repair_object_id.id or False
                            move = self.env['account.move'].create({
                                'move_type': 'in_refund',
                                'partner_id': self.partner_id.id,
                                'invoice_date': self.date,
                                'branch_id': self.branch_ids.id or False,
                                'department_id': self.department_id.id or False,
                                'invoice_line_ids': [Command.create(invoice_line_dct)]
                            })
                            move.action_post()
                            self.write({'move_ids':[(4,move.id)]})
                            adj_line.write({'move_ids':[(4,move.id)]})
                    # moves._create_out_svl(abs(adj_line.quantity))
                else:
                    name = name
                    vals = {
                    'name':  name,
                    'product_id': adj_line.product_id.id,
                    'product_uom': adj_line.uom_id.id,
                    'product_uom_qty': adj_line.quantity,
                    'state': 'confirmed',
                    'location_dest_id': self.location_id.id,
                    'location_id': adj_line.product_id.property_stock_inventory.id,
                    'is_inventory': True,
                    'adjust_id':self.id,
                    'adjustment_line_id':adj_line.id,
                    'division_id':adj_line.division_id.id,
                    'department_id':self.department_id.id or False,
                    'branch_id': self.branch_ids.id or False,
                    'move_line_ids': [(0, 0, {
                        'product_id': adj_line.product_id.id,
                        'product_uom_id': adj_line.uom_id.id,
                        'qty_done': adj_line.quantity,
                        'location_dest_id': self.location_id.id,
                        'location_id': adj_line.product_id.property_stock_inventory.id,
                        'division_id':adj_line.division_id.id,
                        'company_id': self.env.company.id,
                        'department_id':self.department_id.id or False,
                    })]
                }
                    if hasattr(self.env['stock.move'], 'fleet_id'):
                        vals.update({'fleet_id': adj_line.fleet_id.id or False})
                    if hasattr(self.env['stock.move'], 'repair_object_id'):
                        vals.update({'repair_object_id': adj_line.repair_object_id.id or False})
                    if hasattr(self.env['stock.move'], 'project_id'):
                        vals.update({'project_id': adj_line.project_id.id or False})
                    if hasattr(self.env['stock.move'], 'fleet_location_id'):
                        vals.update({'fleet_location_id':adj_line.fleet_location_id.id or False})
                    moves = self.env['stock.move'].with_context(inventory_mode=False).create(vals)
                    moves.write({'adjust_id':self.id})
                    moves._action_done()
                    for valuation in moves.stock_valuation_layer_ids:
                        valuation.write({'adjust_id':self.id,
                                        'adjustment_line_id':adj_line.id,})
                        
                        self.write({'valuation_ids':[(4,valuation.id)]})
                    moves = self.env['account.move'].search([('stock_move_id','=',moves.id)])
                    for move in moves:
                        move.ref = self.name
                        move.internal_ref = self.ref
                        self.write({'move_ids':[(4,move.id)]})
                        adj_line.write({'move_ids':[(4,move.id)]})
                    self.location_id.write({'last_inventory_date': fields.Date.today()})

                    if self.has_refund:
                        product = self.env['product.product'].browse(adj_line.product_id.id)
                        if product:
                            invoice_line_dct = {
                                    'name': adj_line.description,
                                    'price_unit': adj_line.unit_value,
                                    'account_id': product.categ_id.property_stock_account_input_categ_id.id,
                                    'fleet_id':adj_line.fleet_id and adj_line.fleet_id.id or False,
                                    'division_id':adj_line.division_id and adj_line.division_id.id or False,
                                    'analytic_distribution':adj_line.analytic_distribution,
                                }
                            if hasattr(adj_line, 'project_id'):
                                invoice_line_dct['project_id'] = adj_line.project_id.id or False
                            if hasattr(adj_line, 'repair_object_id'):
                                invoice_line_dct['repair_object_id'] = adj_line.repair_object_id.id or False
                            move = self.env['account.move'].create({
                                'move_type': 'in_refund',
                                'partner_id': self.partner_id.id,
                                'invoice_date': self.date,
                                'ref':self.name,
                                'branch_id': self.branch_ids.id or False,
                                'department_id': self.department_id.id or False,
                                'invoice_line_ids': [Command.create(invoice_line_dct)]
                            })
                            move.action_post()
                            self.write({'move_ids':[(4,move.id)]})
                            adj_line.write({'move_ids':[(4,move.id)]})
                        
                    # rounding = moves.product_id.uom_id.rounding
                    # layers = self.env['stock.valuation.layer'].search([('product_id','=',moves.product_id.id),('location_dest_id','=',moves.location_dest_id.id),('remaining_qty','>',0)])
                    # product_tot_qty_available = 0
                    # amount_tot_qty_available = 0
                    # if layers:
                    #     product_tot_qty_available += sum(layers.mapped('remaining_qty')) or 0
                    #     amount_tot_qty_available += sum(layers.mapped('remaining_value')) or 0
                    # valued_move_lines = moves._get_in_move_lines()
                    # qty_done = 0
                    # for valued_move_line in valued_move_lines:
                    #     qty_done += valued_move_line.product_uom_id._compute_quantity(valued_move_line.qty_done, moves.product_id.uom_id)
                    # if float_is_zero(product_tot_qty_available, precision_rounding=rounding):
                    #     new_std_price = moves._get_price_unit()
                    # elif float_is_zero(product_tot_qty_available + moves.product_qty, precision_rounding=rounding) or \
                    #         float_is_zero(product_tot_qty_available + qty_done, precision_rounding=rounding):
                    #     new_std_price = moves._get_price_unit()
                    # else:
                    #     new_std_price = amount_tot_qty_available/product_tot_qty_available

                    # warehouse_valuation_ids = moves.product_id.warehouse_valuation.filtered(lambda x:x.location_id==moves.location_dest_id)
                    # if not warehouse_valuation_ids:
                    #     vals = self.env['warehouse.valuation'].create({'location_id':moves.location_dest_id.id,
                    #                                                 'location_cost':new_std_price})
                    #     if vals:
                    #         moves.product_id.write({'warehouse_valuation':[(4,vals.id)]})
                    # else:
                    #     warehouse_valuation_ids.write({'location_cost':new_std_price})
                if hasattr(self.location_id, 'machine_location') and self.location_id.machine_location:
                    if not adj_line.fleet_location_id:
                        raise ValidationError("Fleet Location must be present for machine located location!!!")
                    adj_line.fleet_location_id.onhand_fuel += round(adj_line.quantity,2)
        self.state = 'done'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft' or (rec.state == 'draft' and rec.name):
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔")
        return super().unlink()
    
    def action_print_adjustment(self):
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        birt_suffix = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.suffix','')
        if self.id:
            url = self.env['ir.config_parameter'].sudo().get_param('birt.report.url.html') + str(filename) + str(birt_suffix) + '.rptdesign&channel_id=' + str(self.id) + "&&__dpi=96&__format=html&__pageoverflow=0&__overwrite=false"
        if url:
            return {
            'type' : 'ir.actions.act_url',
            'url' : url,
            'target': 'new',
            }
        else:
            raise ValidationError('Report Not Not Found')          
    
    # def action_return(self):
        
    #     return_adjust = self.env['stock.inventory.adjustment'].create({
    #         'date':fields.Datetime.now().date(),
    #         'location_id':self.location_id and self.location_id.id or False,
    #         'journal_id':self.journal_id and self.journal_id.id or False,
    #         'origin_returned_adjust_id':self.id,
    #         'adjustment_line_id':[(0, 0, {
    #                         'product_id': res.product_id.id,
    #                         'desc': res.desc,
    #                         'quantity': res.quantity>0 and -res.quantity or abs(res.quantity),
    #                         'uom_id': res.uom_id and res.uom_id.id or False,
    #                         'unit_cost': res.product_id.warehouse_valuation.filtered(lambda x:x.location_id==self.location_id) and res.product_id.warehouse_valuation.filtered(lambda x:x.location_id==self.location_id).location_cost or res.unit_cost,        
    #                         'adjust_account_id':res.adjust_account_id and res.adjust_account_id.id or False,     
    #                         'origin_returned_adjust_line_id':res.id              
    #                     }) for res in self.adjustment_line_id]
    #     })
    #     self.state = 'return'
    #     return {
    #         'name': _('Returned Adjustment'),
    #         'view_mode': 'form,tree',
    #         'res_model': 'stock.inventory.adjustment',
    #         'res_id': return_adjust.id,
    #         'type': 'ir.actions.act_window',
    #     }



class StockAdjustmentLine(models.Model):
    _name = "stock.inventory.adjustment.line"
    _inherit = ['analytic.mixin']

    product_id = fields.Many2one('product.product',string="Item Code",required=True)
    desc = fields.Char('Item Description',related="product_id.name")
    remaining_qty = fields.Float('Remaining Stock',compute='_compute_remain_stock',store=True)
    quantity = fields.Float('Quantity',required=True)
    unit_cost = fields.Float('Standard Cost',required=True)
    unit_value = fields.Float('Value',compute='compute_unit_value',store=True)
    adjust_account_id = fields.Many2one('account.account',string="Adjust Account")
    adjust_id = fields.Many2one('stock.inventory.adjustment')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    uom_id = fields.Many2one('uom.uom',string="UOM",domain="[('category_id', '=', product_uom_category_id)]")
    auto_compute_cost = fields.Boolean('compute_auto_compute_cost',store=True)
    company_id = fields.Many2one('res.company',string="Company", required=True, default=lambda self: self.env.company)
    branch_ids = fields.Many2one('res.branch', string='Branch', store=True,readonly=False,related="adjust_id.branch_ids")
    department_id = fields.Many2one('res.department', string='Department', store=True,readonly=False,related="adjust_id.department_id")
    origin_returned_adjust_line_id = fields.Many2one(
        'stock.inventory.adjustment.line', 'Origin Return Adjust Line', copy=False, index=True,
        help='Move that created the return adjust', check_company=True,readonly=True)
    description = fields.Char(string="Description")
    job_code_id = fields.Many2one(comodel_name='job.code',string="Job Code")    
    employee_id = fields.Many2one(comodel_name='hr.employee',string="Employee")
    move_ids = fields.Many2many('account.move','adjustment_line_move_rel','adjust_line_id','move_id',readonly=True, ondelete='cascade',copy=False,
        check_company=True)
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")
 
    @api.onchange('division_id')
    def _onchage_analytic_by_division(self):
        dct = {}
        envv = self.env['account.analytic.account']
        if not self.division_id and len(self.adjust_id.adjustment_line_id) > 1 > 1:
            prev_line = self.adjust_id.adjustment_line_id[-2]
            adjust_id  = self.adjust_id
            dct = prev_line.analytic_distribution
            if hasattr(self, 'project_id'):
                self.project_id = prev_line.project_id
            if hasattr(self, 'division_id'):
                self.division_id = prev_line.division_id
            if hasattr(self, 'fleet_id'):
                if (hasattr(adjust_id, 'repair_request_id') and adjust_id.repair_request_id ) or (hasattr(adjust_id, 'job_order_id') and adjust_id.job_order_id) or (hasattr(adjust_id,'requisition_id') and adjust_id.requisition_id):
                    self.fleet_id = adjust_id.adjustment_line_id[-2].fleet_id
                else:
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

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.desc = self.product_id.name
            self.uom_id = self.product_id.uom_id.id

    @api.depends('product_id','adjust_id.location_id')
    def _compute_remain_stock(self):
        for rec in self:
            rec.remaining_qty = 0.0
           
            qty = 0
            if rec.product_id:
                quants = self.env['stock.quant'].search([
                        ('product_id', '=', rec.product_id.id),('location_id', '=', rec.adjust_id.location_id.id)
                    ])
                for qt in quants:
                    qty += qt.quantity
                rec.remaining_qty = qty

    @api.depends('quantity','unit_cost')
    def compute_unit_value(self):
        for rec in self:
            
            unit_value = rec.quantity * rec.unit_cost
            rec.unit_value = abs(unit_value)

    @api.onchange('quantity','adjust_id.location_id','product_id')
    def define_auto_unit_cost(self):
        if self.quantity < 0.0:
            valuation = self.product_id.warehouse_valuation.filtered(lambda x:x.location_id==self.adjust_id.location_id)
            unit_cost = 0.0
            if valuation:
                unit_cost = valuation.location_cost
            self.unit_cost = unit_cost
        else:
            self.unit_cost = 0

    def compute_auto_compute_cost(self):
        for rec in self:
            result = False
            if rec.quantity < 0.0:
                result = True
            rec.auto_compute_cost = result   
            
            
class StockAdjustmentDiffReport(models.TransientModel):
    """ Stock Adjustment Diff Report """
    
    _name = "stock.adjustment.diff.report"
    
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    product_ids = fields.Many2many('product.product')
    all_product = fields.Boolean(default=True,string="All Product")
    
    def action_submit_excel(self):
        output = io.BytesIO()
        file_name = os.path.join(tempfile.gettempdir(), 'Stock Adjustment Diff Report')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Stock Adjustment Diff Report")
        banner_format_small = workbook.add_format({'font_name': 'Arial','bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})
       
        sheet.set_column(0, 0, 30)
        
        y_offset = 0
        x_offset = 0
        
        
        sheet.write(x_offset,0,"Adjustment",header_format)
        sheet.write(x_offset,1,"Product",header_format)
        sheet.write(x_offset,2,"Adj Cost",header_format)
        sheet.write(x_offset,3,"Adjust Journal",header_format)
        sheet.write(x_offset,4,"Valuation Journal",header_format)
        sheet.write(x_offset,5,"Valuation Cost",header_format)
        sheet.write(x_offset,6,"Diff Cost",header_format)
        sheet.write(x_offset,7,"Status",header_format)
        x_offset +=1
        
        if self.all_product:
            adjustment_ids = self.env['stock.inventory.adjustment'].search([('date','>=',self.start_date),('date','<=',self.end_date)])
            for line in adjustment_ids.adjustment_line_id:
                adj_journal = line.move_ids.journal_id.filtered(lambda x:x.id == line.adjust_id.journal_id.id)
                stock_journal = line.move_ids.journal_id.filtered(lambda x:x.id != line.adjust_id.journal_id.id)
                adj_move = line.move_ids.filtered(lambda x:x.journal_id == adj_journal)
                valuation_move = line.move_ids.filtered(lambda x:x.journal_id == stock_journal)
                sheet.write(x_offset,0,line.adjust_id.name,text_format)
                sheet.write(x_offset,1,line.sudo().product_id.product_code,text_format)
                sheet.write(x_offset,2,round(line.unit_value,2),text_format)
                # sheet.write(x_offset,3,line.adjust_id.journal_id.name,text_format)
                # sheet.write(x_offset,4,stock_journal and stock_journal.name or "",text_format)
                sheet.write(x_offset,3,(adj_move and len(adj_move)==1) and adj_move.name or "",text_format)
                sheet.write(x_offset,4,(valuation_move and len(valuation_move)==1) and valuation_move.name or "",text_format)
                sheet.write(x_offset,5,(valuation_move and len(valuation_move)==1) and round(valuation_move.amount_total,2) or "",text_format)
                sheet.write(x_offset,6,(valuation_move and len(valuation_move)==1) and abs(round(line.unit_value,2)-round(valuation_move.amount_total,2)) or "",text_format)
                sheet.write(x_offset,7,line.adjust_id.state.capitalize(),text_format)
                x_offset +=1
                
        else:
            adjustment_ids = self.env['stock.inventory.adjustment'].search([('date','>=',self.start_date),('date','<=',self.end_date)])
            for line in adjustment_ids.adjustment_line_id.filtered(lambda x:x.product_id.id in self.product_ids.ids):
                adj_journal = line.move_ids.journal_id.filtered(lambda x:x.id == line.adjust_id.journal_id.id)
                stock_journal = line.move_ids.journal_id.filtered(lambda x:x.id != line.adjust_id.journal_id.id)
                adj_move = line.move_ids.filtered(lambda x:x.journal_id == adj_journal)
                valuation_move = line.move_ids.filtered(lambda x:x.journal_id == stock_journal)
                sheet.write(x_offset,0,line.adjust_id.name,text_format)
                sheet.write(x_offset,1,line.sudo().product_id.product_code,text_format)
                sheet.write(x_offset,2,round(line.unit_value,2),text_format)
                # sheet.write(x_offset,3,line.adjust_id.journal_id.name,text_format)
                # sheet.write(x_offset,4,stock_journal and stock_journal.name or "",text_format)
                sheet.write(x_offset,3,(adj_move and len(adj_move)==1) and adj_move.name or "",text_format)
                sheet.write(x_offset,4,(valuation_move and len(valuation_move)==1) and valuation_move.name or "",text_format)
                sheet.write(x_offset,5,(valuation_move and len(valuation_move)==1) and round(valuation_move.amount_total,2) or "",text_format)
                sheet.write(x_offset,6,(valuation_move and len(valuation_move)==1) and abs(round(line.unit_value,2)-round(valuation_move.amount_total,2)) or "",text_format)
                sheet.write(x_offset,7,line.adjust_id.state.capitalize(),text_format)
                x_offset +=1
      
            
        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)
        

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/binary/download_document?model=stock.adjustment.diff.report&id=%s&file_name=%s" % (self.id, file_name),
            'close': True,
        }