from odoo import models, fields, api,_
from ...generate_code import generate_code,data_import
from odoo.exceptions import UserError, ValidationError
import io
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    # TODO saas-17: remove the try/except to directly import from misc
    import xlsxwriter
import logging
import os
import tempfile

HEADER_FIELDS = ['item code','description','quantity']
PICKING_STATE_DCT = {'draft':'Draft','waiting': 'Waiting Another Operation',
                    'confirmed' : 'Waiting', 'assigned': 'Ready',
                    'done': 'Done','cancel' : 'Cancelled'}

HEADER_INDEXES = {}


class Requisition(models.Model):
    _name = "requisition"
    _inherit = ['mail.thread']
    
    def _get_branch_domain(self):
        """methode to get branch domain"""
        company = self.env.company
        branch_ids = self.env.user.branch_ids
        branch = branch_ids.filtered(
            lambda branch: branch.company_id == company)
        return [('id', 'in', branch.ids)]
    
    def _compute_function_for_other_fields(self):
        for res in self:
            res.issue_status = ''
            picking_ids = self.env['stock.picking'].sudo().search([('requisition_id','=',res.id)])
            if picking_ids:
                for picking in picking_ids:
                    res.issue_status += PICKING_STATE_DCT.get(picking.state,"Draft") + ', '
                res.issue_status = res.issue_status[:-2]
            res.computed_field = False

    name = fields.Char("Reference",copy=False)
    internal_ref = fields.Char("Internal Reference")
    request_person_id = fields.Many2one('hr.employee','Request Person',tracking=True,required=True)
    position_id = fields.Many2one('hr.job', 'Position',related="request_person_id.job_id",store=True, tracking=True)
    department_id = fields.Many2one('res.department','Department',related=False,store=True,required=False,readonly=True,tracking=True)
    company_id = fields.Many2one('res.company',string="Company", required=True, default=lambda self: self.env.company)
    
    from_branch = fields.Selection(lambda self:self._get_all_branches(),string='From Branch', store=True, readonly=False,tracking=True)
    to_branch = fields.Selection(lambda self:self._get_all_branches(),string='To Branch', store=True, readonly=False,tracking=True)
    # from_branch = fields.Many2one('res.branch', string='From Branch', store=True,
    #                             readonly=False,domain=_get_branch_domain,required=False)
    # to_branch = fields.Many2one('res.branch', string='To Branch', store=True,
    #                             readonly=False,domain=_get_branch_domain,required=False)
    order_date = fields.Date('Order Date',required=True,default=fields.Datetime.now,tracking=True)
    required_date = fields.Date('Required Date',required=True,tracking=True)
    location_id = fields.Many2one('stock.location', 'To Location',tracking=True,required=False,domain="[('usage', 'in', ['internal','transit'])]")
    transit_location_id = fields.Many2one('stock.location', 'Transit Location',tracking=True,domain="[('usage', 'in', ['transit'])]")
    src_location_id = fields.Many2one('stock.location',string="Main Location",required=False,domain="[('usage', 'in', ['internal','transit'])]",tracking=True)
    journal_id = fields.Many2one('account.journal',string="Journal")
    state = fields.Selection([('draft', 'Draft'),('confirm', 'Confirm'),('check', 'Check'),('all_check','All Check'),('approve', 'Approve'),('close', 'Closed')],tracking=True, default="draft", readonly=True, string="Status")
    requisition_line = fields.One2many('requisition.line','requisition_id',string='Requisition Line',tracking=True)
    picking_ids = fields.Many2many('stock.picking', copy=False)
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")
    requisition_type = fields.Selection(selection=[('transfer','Transfer'),('issue','Issue')],string="Type",default="transfer")
    partner_id = fields.Many2one('res.partner',string="Customer",domain=[('partner_type','=','customer')])
    order_ids = fields.Many2many('sale.order','requisition_sale_order_rel','requisition_id','order_id',ondelete='cascade')
    adjust_ids = fields.Many2many('stock.inventory.adjustment','requisition_adjustment_rel','requisition_id','adjust_id',ondelete='cascade')
    transfer_count = fields.Integer(compute="_compute_transfer_count", string='Transfers Count')
    issue_status = fields.Char("Issue Status")
    computed_field = fields.Boolean("Fields to Compute other fields!!",compute=_compute_function_for_other_fields)
    data = fields.Binary('File',track_visibility='onchange')
    import_fname = fields.Char(string='Filename')    
    
    @api.depends('picking_ids')
    def _compute_transfer_count(self):
        for move in self:
            move.transfer_count = len(move.picking_ids)    
    
    def _get_all_branches(self):
        selections = []
        query = "SELECT id::text,name FROM res_branch ORDER BY name"
        self.env.cr.execute(query)
        selections = self.env.cr.fetchall()

        return selections
    
    def action_confirm(self):
        sequence = self.env['sequence.model']
        self.name = generate_code.generate_code(sequence,self,self.env['res.branch'].browse(int(self.from_branch)),self.company_id,self.order_date,None,None)
        self.state = 'confirm'
        
    def action_reset_to_draft(self):
        self.state = 'draft'

    def action_check(self):
        self.state = 'check'

    def action_all_check(self):
        if (self.from_branch and not self.to_branch ) or (self.to_branch and not self.from_branch):
            raise UserError("Both from branch and to branch is required!!")
        for res in self.requisition_line:
            if not res.product_id:
                raise UserError (_("Product should not be blank in Requisition Line"))          
        self.state = 'all_check'        

    def action_approve(self,partial_line):       
        if self.requisition_type == 'issue':
            if self.partner_id:
                pricelist_id = self.partner_id.property_product_pricelist
                if not pricelist_id:
                    raise UserError("There is no configured pricelist for the customer - ",self.partner_id.name)
                order_line_lst = []
                for res in partial_line:
                    if res.quantity  > 0:
                        pricelist_product_id = self.env['product.pricelist'].search([])[2].item_ids.filtered(lambda x:x.date_start.date() <= self.required_date <= x.date_end.date() and x.product_id.id == res.product_id.id)
                        unit_price = pricelist_product_id[0].fixed_price if pricelist_product_id else 0.0
                        analytic_dct = {}
                        if hasattr(res.requisition_line, 'project_id') and res.requisition_line.project_id.analytic_project_id:
                            analytic_dct[res.requisition_line.project_id.analytic_project_id.id] = 100
                        if res.requisition_line.fleet_id.analytic_fleet_id:
                            analytic_dct[res.requisition_line.fleet_id.analytic_fleet_id.id] = 100
                        if res.requisition_line.division_id.analytic_account_id:
                            analytic_dct[res.requisition_line.division_id.analytic_account_id.id] = 100
                        values =    (0, 0, 
                                            {
                                                'product_id': res.product_id.id,
                                                'name':res.product_id.name,
                                                'custom_part':res.product_id.custom_part,
                                                'fleet_id':res.requisition_line.fleet_id.id  or False  ,  
                                                'division_id':res.requisition_line.division_id.id or False ,
                                                'analytic_distribution':analytic_dct,
                                                'product_uom_qty': res.quantity, 
                                                'product_uom':res.requisition_line.uom_id.id,
                                                'price_unit':unit_price,
                                                'remark':res.requisition_line.remark,
                                            })     
                        if hasattr(res.requisition_line, 'project_id'):
                            values[2]['project_id'] = res.requisition_line.project_id.id 
                        if hasattr(res.requisition_line, 'repair_object_id'):
                            values[2]['repair_object_id'] = res.requisition_line.repair_object_id.id 
                        order_line_lst.append(values)     
                so_id = self.env['sale.order'].create({
                    "partner_id": self.partner_id.id,
                    "location_id": self.src_location_id and self.src_location_id.id or False,
                    "warehouse_id": self.src_location_id and self.src_location_id.warehouse_id.id or False,
                    "internal_ref":self.name,
                    "date_order":self.required_date,
                    "department_id":self.department_id and self.department_id.id or False,
                    "branch_id": int(self.from_branch) and int(self.from_branch) or False,
                    "pricelist_id": pricelist_id.id or False,
                    "exchange_rate":1.0,
                    "order_line":order_line_lst
                })
                self.write({'order_ids':[(4,so_id.id)]})  
            else:
                adjustment_line_lst = []
                for res in partial_line:
                    if res.quantity  > 0:
                        analytic_dct = {}
                        if hasattr(res.requisition_line, 'project_id') and res.requisition_line.project_id.analytic_project_id:
                            analytic_dct[res.requisition_line.project_id.analytic_project_id.id] = 100
                        if res.requisition_line.fleet_id.analytic_fleet_id:
                            analytic_dct[res.requisition_line.fleet_id.analytic_fleet_id.id] = 100
                        if res.requisition_line.division_id.analytic_account_id:
                            analytic_dct[res.requisition_line.division_id.analytic_account_id.id] = 100
                        warehouse_valuation = res.product_id.warehouse_valuation.filtered(lambda x:x.location_id.id == self.src_location_id.id)
                        unit_price = warehouse_valuation and warehouse_valuation[0].location_cost or 0.0
                        values =    (0, 0, 
                                            {
                                                        'product_id': res.product_id.id,
                                                        'uom_id':res.product_id.uom_id.id,
                                                        'desc':res.product_id.name,
                                                        'quantity': -res.quantity,
                                                        'unit_cost':unit_price,
                                                        'fleet_id':res.requisition_line.fleet_id.id,
                                                        'division_id':res.requisition_line.division_id.id,
                                                        'analytic_distribution':analytic_dct,
                                                        'description':res.requisition_line.product_name,
                                            }
                                        )     
                        if hasattr(res.requisition_line, 'project_id'):
                            values[2]['project_id'] = res.requisition_line.project_id.id 
                        if hasattr(res.requisition_line, 'repair_object_id'):
                            values[2]['repair_object_id'] = res.requisition_line.repair_object_id.id                         
                        adjustment_line_lst.append(values)    
                adjust = self.env['stock.inventory.adjustment'].create(
                                    {   
                                        'location_id':self.src_location_id.id,
                                        'date':self.required_date,
                                        "branch_ids": int(self.from_branch) and int(self.from_branch) or False,
                                        'department_id':self.department_id.id,
                                        'journal_id':self.journal_id.id,
                                        'ref':self.name,
                                        'adjustment_line_id':adjustment_line_lst
                                    })  
                self.write({'adjust_ids':[(4,adjust.id)]})   
        else:
            if self.transit_location_id:
                picking_type = self.env['stock.picking.type']
                from_picking_type = picking_type.sudo().search([('warehouse_id','=',self.src_location_id.warehouse_id.id),('code','=','internal')],limit=1)
                from_picking = self._create_requisition_picking(self.src_location_id,self.transit_location_id,from_picking_type,branch=int(self.from_branch))
                from_picking_move_ids_lst = []
                for res in partial_line:
                    if res.quantity  > 0:
                        values =    (0, 0, 
                                            {
                                                'product_id': res.product_id.id,
                                                'name':res.product_id.name,
                                                'product_uom_qty': res.quantity,
                                                'location_id':self.src_location_id.id,
                                                'location_dest_id':self.transit_location_id.id,
                                                'branch_id':int(self.from_branch) and int(self.from_branch) or False ,
                                                'fleet_id':res.requisition_line.fleet_id.id  or False  ,  
                                                'division_id':res.requisition_line.division_id.id or False ,        
                                            })
                        if hasattr(res.requisition_line, 'project_id'):
                            values[2]['project_id'] = res.requisition_line.project_id.id or False
                        from_picking_move_ids_lst.append(values)
                from_picking.write({
                                    'branch_id':int(self.from_branch) and int(self.from_branch) or False,
                                    'internal_ref': self.internal_ref,
                                    'move_ids':from_picking_move_ids_lst
                                    })
                
                to_picking_type = picking_type.sudo().search([('warehouse_id','=',self.location_id.warehouse_id.id),('code','=','internal')],limit=1)
                to_picking = self._create_requisition_picking(self.transit_location_id,self.location_id,to_picking_type,branch=int(self.to_branch))
                to_picking_move_ids_lst = []
                for res in partial_line:
                    if res.quantity  > 0:
                        values = ( 0 , 0 ,
                                    {
                                        'product_id': res.product_id.id,
                                        'name':res.product_id.name,
                                        'product_uom_qty': res.quantity,
                                        'location_id':self.transit_location_id.id ,
                                        'location_dest_id':self.location_id.id,
                                        'branch_id':int(self.to_branch) and int(self.to_branch) or False,
                                        'fleet_id':res.requisition_line.fleet_id.id or False,  
                                        'division_id':res.requisition_line.division_id.id or False , 
                                    }    
                                )
                        if hasattr(res.requisition_line, 'project_id'):
                            values[2]['project_id'] = res.requisition_line.project_id.id or False
                        to_picking_move_ids_lst.append(values)                
                to_picking.write({  
                                    'branch_id':int(self.to_branch) and int(self.to_branch) or False,
                                    'internal_ref': self.internal_ref,
                                    'move_ids':to_picking_move_ids_lst
                                })
                self.write({'picking_ids':[(4, from_picking.id)]})
                self.write({'picking_ids':[(4, to_picking.id)]})
            else:
                picking_type_id = self.env['stock.picking.type']
                picking_type = picking_type_id.sudo().search([('warehouse_id','=',self.src_location_id.warehouse_id.id),('code','=','internal'),('active','=',True)],limit=1)
                picking = self._create_requisition_picking(self.src_location_id,self.location_id,picking_type,branch=int(self.to_branch))
                picking_move_ids_lst = []
                for res in partial_line:
                    if res.quantity  > 0:
                        values = (0, 0,
                                    {
                                        'product_id': res.product_id.id,
                                        'name':res.product_id.name,
                                        'product_uom_qty': res.quantity,
                                        'location_id':self.src_location_id.id ,
                                        'location_dest_id':self.location_id.id,
                                        'fleet_id':res.requisition_line.fleet_id.id or False,  
                                        'division_id': res.requisition_line.division_id.id or False, 
                                        'branch_id':int(self.from_branch) and int(self.from_branch) or False ,
                            
                                    }  
                                )
                        if hasattr(res.requisition_line, 'project_id'):
                            values[2]['project_id'] = res.requisition_line.project_id.id or False 
                        picking_move_ids_lst.append(values)               
                picking.write(
                                { 
                                    'internal_ref': self.internal_ref,
                                    'move_ids':picking_move_ids_lst,
                                    'branch_id':int(self.from_branch) and int(self.from_branch) or False
                                }
                            )
                self.write({'picking_ids':[(4, picking.id)]})
                # self.write({'picking_ids':[(6, 0, picking.ids)]})
            # self.state = 'approve'

    def action_close(self):
        for res in self:
            res.state = 'close'

    def _create_requisition_picking(self,from_loc,to_loc,picking_type_id,branch):
        picking = self.env['stock.picking'].sudo().create({
            'location_id':from_loc.id,
            'location_dest_id':to_loc.id,
            'picking_type_id':picking_type_id.id,
            'branch_id':branch and branch or False,
            'requisition_id':self.id,
            'origin':self.name or False,

        })
        return picking
    
    def action_open_transfers(self):
        return {
            'name': _('Internal Transfer'),
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.picking_ids.ids)],              
        } 
    
    def action_open_adjustments(self):
        return {
            'name': _('Inventory Adjustments'),
            'view_mode': 'tree,form',
            'res_model': 'stock.inventory.adjustment',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.adjust_ids.ids)],              
        } 

    def action_open_orders(self):
        return {
            'name': _('Sale Orders'),
            'view_mode': 'tree,form',
            'res_model': 'sale.order',
            'view_id': False,
            'type': 'ir.actions.act_window',  
            'domain': [('id', 'in',self.order_ids.ids)],              
        }         
    
    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()
    
    # main function
    def action_import_order(self):  
        for res in self:
            all_datas = data_import.read_and_validate_datas(res,HEADER_FIELDS,HEADER_INDEXES)  
            product_obj = self.env['product.product']       
            order_line_obj = self.env['requisition.line'] 
            for data in all_datas:
                excel_row = all_datas.index(data) + 2  
                item_code = data['item code'].strip().encode('utf-8')
                item_description = data['description'].strip().encode('utf-8')
                quantity = data['quantity']
                if not item_code:
                    raise UserError('Item Code must not be blank in excel Line %s.'% str(excel_row))
                product_id = product_obj.search([('product_code', '=', item_code),('company_id','=', self.company_id.id)])
                if not product_id:
                    raise UserError('Item code not found.')
                if len(product_id) > 1:
                    raise UserError('Duplicate item code found.')  
                if abs(quantity) <= 0.0:
                    raise UserError('Invalid Quantity')
                line_id = order_line_obj.search([('requisition_id', '=', self.id), ('product_id', '=', product_id.id), ('qty', '=', quantity)],limit=1)
                if line_id:
                    raise ValidationError("Duplicate product and quantity in order liness!!!")                 
                if not item_description:
                    item_description = product_id.name
                vals = {
                        'product_id': product_id.id,
                        'uom_id':product_id.uom_id.id,
                        'product_desc': item_description,
                        'qty': quantity,
                        'requisition_id':self.id,
                    }
                order_line_obj.create(vals)   
                
    def action_export_requisition_transaction(self):
        output = io.BytesIO()
        file_name = os.path.join(tempfile.gettempdir(), 'Requisition Export.xlsx')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Duty Transactions Export")
        banner_format_small = workbook.add_format({'font_name': 'Arial','bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})
        date_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','num_format': 'dd/mm/yy'})
        time_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','num_format': 'hh:mm'}) 

        y_offset = 0
        x_offset = 0

        sheet.write(x_offset,0,"Reference",header_format)
        sheet.write(x_offset,1,"Order Date",header_format)
        sheet.write(x_offset,2,"Required Date",header_format)
        sheet.write(x_offset,3,"Request Person",header_format)
        sheet.write(x_offset,4,"From Branch",header_format)
        sheet.write(x_offset,5,"To Branch",header_format)
        sheet.write(x_offset,6,"Main Location",header_format)
        sheet.write(x_offset,7,"To Location",header_format)
        sheet.write(x_offset,8,"Transist Location",header_format)
        sheet.write(x_offset,9,"Product Code",header_format)
        sheet.write(x_offset,10,"Product Name",header_format)
        sheet.write(x_offset,11,"Qty",header_format)
        sheet.write(x_offset,12,"Done Qty",header_format)
        sheet.write(x_offset,13,"Description",header_format)
        sheet.write(x_offset,14,"From Remaining Stock",header_format)
        sheet.write(x_offset,15,"To Remaining Stock",header_format)
        sheet.write(x_offset,16,"Transist Remaining Stock",header_format)
        sheet.write(x_offset,17,"Remark",header_format)
        
        
        x_offset+=1
        active_ids = self.env.context.get('active_ids')
        branch_obj = self.env['res.branch'].sudo()
        requisition_lines = self.env['requisition.line'].sudo().search([('requisition_id','in',active_ids)])
        for line in requisition_lines:
            sheet.write(x_offset,0,line.requisition_id.name or "",text_format)
            sheet.write(x_offset,1,line.requisition_id.order_date or "",date_format)
            sheet.write(x_offset,2,line.requisition_id.required_date or "",date_format)
            sheet.write(x_offset,3,line.requisition_id.request_person_id and  line.requisition_id.request_person_id.name  or "",text_format)
            sheet.write(x_offset,4,branch_obj.browse(int(line.requisition_id.from_branch)).name  or "",text_format)
            sheet.write(x_offset,5,branch_obj.browse(int(line.requisition_id.to_branch)).name or "",text_format)
            sheet.write(x_offset,6,line.requisition_id.src_location_id and line.requisition_id.src_location_id.name or "",text_format)
            sheet.write(x_offset,7,line.requisition_id.location_id and line.requisition_id.location_id.name or "",text_format)
            sheet.write(x_offset,8,line.requisition_id.transit_location_id and line.requisition_id.transit_location_id.name or "",text_format)
            sheet.write(x_offset,9,line.product_id and line.product_id.product_code or "",text_format)
            sheet.write(x_offset,10,line.product_id and line.product_id.name or "",text_format)
            sheet.write(x_offset,11,line.qty  or 0,text_format)
            sheet.write(x_offset,12,line.done_qty  or 0,text_format)

            sheet.write(x_offset,13,line.product_name or "",text_format)
            sheet.write(x_offset,14,line.remaining_from or 0,text_format)
            sheet.write(x_offset,15,line.remaining_to or 0,text_format)
            sheet.write(x_offset,44,line.remaining_transit or 0,text_format)
            sheet.write(x_offset,45,line.remark or "",text_format)
        
            x_offset+=1
            
        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)
        

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/binary/download_document?model=requisition&id=%s&file_name=%s" % (self.id, file_name),
            'close': True,
        }                

class RequisitionLine(models.Model):
    _name = "requisition.line"

    product_id = fields.Many2one('product.product','Product Code')
    product_desc = fields.Char(related='product_id.name')
    requisition_id = fields.Many2one('requisition','Material Requisition')
    product_name = fields.Char('Description')
    qty = fields.Float('Qty')
    done_qty = fields.Float('Done Qty',readonly=True)
    from_done_qty = fields.Float('From Done Qty',readonly=True,store=True)
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    uom_id = fields.Many2one('uom.uom',string='Unit',related="product_id.uom_id",domain="[('category_id', '=', product_uom_category_id)]")
    remaining_from = fields.Float(string='Remaining Stock(From)',compute=False,store=True)
    remark = fields.Char('Remark')
    compute_qty = fields.Float(string='Compute Stock')
    remaining_to = fields.Float(string='Remaining Stock(To)',compute=False,store=True)
    remaining_transit = fields.Float(string='Remaining Stock(Transit)',compute=False,store=True)
    remaining_qty_compute = fields.Boolean(string="Compute for Remaining Quantity",compute='_compute_all_remaining_quantity')
    part_id = fields.Char('Part ID')
    state = fields.Selection([('draft', 'Draft'),('confirm', 'Confirm'),('check', 'Check'),('approve', 'Approve'),('close', 'Closed')],related='requisition_id.state',store=True, string="Status")
    division_id = fields.Many2one(comodel_name='analytic.division',string="Division")
    production_move_id = fields.Many2one('stock.move')

    def _compute_all_remaining_quantity(self):
        total_dct = {}
        for picking in self.requisition_id.picking_ids:
            if picking.location_id.id != self.requisition_id.src_location_id.id or picking.state != 'done':
                continue
            for move_id in picking.move_ids:
                if move_id.product_id.id in total_dct:
                    total_dct[move_id.product_id.id] += move_id.quantity_done
                else:
                    total_dct[move_id.product_id.id] = move_id.quantity_done        
        for res in self:
            res.from_done_qty = total_dct.get(res.product_id.id,0)
            res.remaining_from = res.compute_remaining_stock(res.requisition_id.src_location_id)
            res.remaining_to = res.compute_remaining_stock(res.requisition_id.location_id)
            res.remaining_transit = res.compute_remaining_stock(res.requisition_id.transit_location_id)
            res.remaining_qty_compute = False
            
    @api.onchange('product_id')
    def _onchange_qty_by_product(self):
        for res in self:
            if res.product_id:
                if res.requisition_id.src_location_id:
                    res.remaining_from = res.compute_remaining_stock(res.requisition_id.src_location_id)
                elif res.requisition_id.location_id:
                    res.remaining_to = res.compute_remaining_stock(res.requisition_id.location_id)
                elif res.requisition_id.transit_location_id:
                    res.remaining_transit = res.compute_remaining_stock(res.requisition_id.transit_location_id)

    # @api.depends('requisition_id.src_location_id','product_id','uom_id')
    # def compute_stock_from(self):
    #     for rec in self:
    #         qty = rec.compute_remaining_stock(rec.requisition_id.src_location_id)
    #         rec.remaining_from = qty

    # @api.depends('requisition_id.location_id','product_id','uom_id')
    # def compute_stock_to(self):
    #     for rec in self:
    #         qty = rec.compute_remaining_stock(rec.requisition_id.location_id)
    #         rec.remaining_to = qty 

    # @api.depends('requisition_id.transit_location_id','product_id','uom_id')
    # def compute_stock_transit(self):
    #     for rec in self:
    #         qty = rec.compute_remaining_stock(rec.requisition_id.transit_location_id)
    #         rec.remaining_transit = qty         

    def compute_remaining_stock(self,location_id):
        for rec in self:
            qty = 0
            if rec.product_id and location_id:
                quants = self.env['stock.quant'].search([
                        ('product_id', '=', rec.product_id.id),('location_id', '=', location_id.id)
                    ])
                for qt in quants:
                    qty += qt.quantity
            return qty 
        
    def unlink(self):
        for line in self:
            if line.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()


class StockPicking(models.Model):
    """inherited stock.picking"""
    _inherit = "stock.picking"

    requisition_id = fields.Many2one('requisition','Material Requisition')
    
    def _create_backorder(self):
        backorders = super()._create_backorder()
        for backorder in backorders:
            if self.branch_id:
                backorder.write({"branch_id":self.branch_id.id})
            if backorder.requisition_id:
                backorder.requisition_id.sudo().write({'picking_ids':[(4,backorder.id)]})
        return backorders
