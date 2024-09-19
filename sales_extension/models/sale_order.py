from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from ...generate_code import generate_code
from odoo.tests import Form
from collections import Counter
from datetime import datetime

READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'sale', 'done', 'cancel'}
}

class SaleOrder(models.Model):
    """inherited sale order"""
    _inherit = 'sale.order'

    sale_type = fields.Selection([('counter_sale', 'Counter Sale'),('order_sale', 'Order Sale')],track_visibility='onchange', default="counter_sale",string="Type")
    term_type = fields.Selection([('direct','Cash Sales'),('credit','Credit Sales')],string='Payment Type',default="direct")
    location_id = fields.Many2one('stock.location','Location',required=True,domain=[('usage','=','internal')])
    other_contact_id = fields.Many2one(comodel_name='res.partner',string='Contact Person',domain=[('is_other_contact','=',True)])
    internal_ref = fields.Char(string="Internal Reference")
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Salesperson",
        compute='_compute_user_id',
        store=True, readonly=False, precompute=True, index=True,
        tracking=2,
        domain=lambda self: "[('groups_id', '=', {}), ('share', '=', False), ('company_ids', '=', company_id)]".format(
            self.env.ref("base.group_user").id
        ))
    allow_division_feature = fields.Boolean(string="Use Division Feature?",related="company_id.allow_division_feature")

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        required=True, readonly=False, change_default=False, index=True,
        tracking=1,
        states=READONLY_FIELD_STATES, domain=lambda self:self._get_partner_domain())
    quotation_ref = fields.Char()
    
    def _get_partner_domain(self):
        if self.env.company.allow_partner_domain_feature:
            return [
                ('partner_type','=','customer'),
                ('type','!=','private'),
                '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
                    ]
                        
        return [
            ('type','!=','private'),
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
                ]
    

    @api.depends('partner_id')
    def _compute_user_id(self):
        for order in self:
            if order.partner_id and not (order._origin.id and order.user_id):
                # Recompute the salesman on partner change
                #   * if partner is set (is required anyway, so it will be set sooner or later)
                #   * if the order is not saved or has no salesman already
                order.user_id = (
                    order.partner_id.user_id
                    or order.partner_id.commercial_partner_id.user_id
                    or (self.user_has_groups('base.group_user') and self.env.user)
                )

    @api.onchange('warehouse_id')
    def onchange_location_id(self):
        if self.warehouse_id:
            return {'domain': {'location_id': [('warehouse_id', 'in', self.warehouse_id.ids),('usage','=','internal')]}} 
        
    @api.depends('partner_id')
    def _compute_payment_term_id(self):
        for order in self:
            order = order.with_company(order.company_id)
            if not order.term_type == 'direct':
                term_id = self.env['account.payment.term'].search([('name', '=', 'Immediate Payment')],limit=1)
                if term_id:
                    self.payment_term_id = term_id.id      
        
    @api.onchange('term_type')
    def onchange_payment_term_id(self):
        if self.term_type == 'direct':
            term_id = self.env['account.payment.term'].search([('name', '=', 'Immediate Payment')],limit=1)
            if term_id:
                self.payment_term_id = term_id.id
        elif self.term_type == 'credit':
            self.payment_term_id = self.partner_id.property_payment_term_id.id
            
    @api.onchange('location_id')
    def recompute_remaining_stock(self):
        for line in self.order_line:
            line.compute_remaining_stock()                


    @api.constrains('sale_type')
    def _check_sale_type_for_unit_product(self):
        for rec in self:
            if rec.sale_type == 'counter_sale' and any(rec.order_line.mapped('can_be_unit')):
                raise ValidationError(_('Can not use counter sale for unit products.'))

    @api.constrains('order_line')
    def _auto_save_and_copy_analytic_distribution_for_order_line(self):

        if hasattr(self.order_line, 'project_id'):
            sale_line_with_project = self.order_line.search([('project_id','!=',False),('order_id','=',self.id)],limit=1)
            if sale_line_with_project:
                dct = sale_line_with_project.analytic_distribution
                sale_lines_without_project = self.order_line.filtered(lambda x:not x.project_id)
                for line in sale_lines_without_project:
                    line.write({
                                'project_id':sale_line_with_project.project_id.id,
                                'analytic_distribution':dct,
                                'division_id':sale_line_with_project.division_id and sale_line_with_project.division_id.id,
                            })
            else:
                if  not (self.requisition_id or self.repair_request_id or self.job_order_id) or ((self.requisition_id or self.repair_request_id or self.job_order_id) and self.state != 'draft'):
                    raise UserError("At least one project is required to create sale order")          

    def confirm_generate_code_so(self):
        super().action_confirm()
        sequence = self.env["sequence.model"]
        name = generate_code.generate_code(sequence,self,self.branch_id,self.company_id,self.date_order,None,None) if not self.name or  self.name.startswith("S") else self.name                    
        self.write({"name":name})
        for picking in self.picking_ids:
            picking.write({"origin":name})

    def action_confirm(self):  
        for line in self.order_line:
            if line.can_be_unit and not line.serial_no_id and not line.product_id.tracking == 'none':
                raise ValidationError(_('Serial Number is required for unit product: ') + line.product_id.name)
            if line.can_be_unit and not line.product_id.tracking == 'none':
                unit_lines = self.order_line.filtered(lambda x:x.can_be_unit == True)
                if len(unit_lines) != len(unit_lines.mapped('serial_no_id').ids):
                    raise ValidationError(_('Serial Number must be unique for each product. Check your Serial Numbers!!'))                
                check_serial_number = self.env['sale.order.line'].search_count([('id','!=',line.id),('serial_no_id','=',line.serial_no_id.id),('state','not in',('draft','cancel'))])
                if check_serial_number != 0:
                    raise ValidationError(_('Serial No %s already have a confirmed order!!' % line.serial_no_id.name))

            if line.product_id.detailed_type == 'product':
                line.check_stock()  
        if self.partner_id and self.partner_id.partner_type == 'vendor' and self.partner_id.is_duty_owner:
            if hasattr(self.order_line[0], 'fleet_id'):
                dct = Counter([line_id.fleet_id.id for line_id in self.order_line])
                if False in dct:
                    raise ValidationError("Found blank fleet in the order line..")
                if len(dct) != 1:
                    raise ValidationError("You must add same fleet in all order lines when it is associated with duty owner - vendor!!")
        self.confirm_generate_code_so() 
        if self.sale_type == 'counter_sale':
            for picking in self.picking_ids.filtered(lambda x:x.state != 'cancel'):
                picking.action_assign()
                wiz = picking.button_validate()
                wiz = Form(self.env['stock.immediate.transfer'].with_context(wiz['context'])).save()
                wiz.process()
            self._create_invoices(final=True)
            return self.action_view_invoice()
            
    def action_cancel(self):
        commission_moves = self.env['account.move'].search([('commercial_sale_id','=',self.id)])
        if commission_moves and len(commission_moves) != 2 and commission_moves.reversal_move_id not in commission_moves:
            raise UserError('You can not cancel sale order which has a commission bill.')
        return super().action_cancel()
    
    def _prepare_invoice(self):
        """override prepare_invoice function to include branch"""
        invoice_vals:dict = super()._prepare_invoice()
        invoice_vals.update({"internal_ref":self.internal_ref, "other_contact_id": self.other_contact_id.id,'term_type':self.term_type})
        return invoice_vals
    
    @api.model_create_multi
    def create(self,val_list):
        res = super().create(val_list)
        res.quotation_ref = res.name
        return res
    

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Are you doing something fraudly! Why do you want to delete some records?? 🤔 ")
        return super().unlink()     
    
    def discount_calculator_scheduler(self):
        for sale_order in self:
            for line in sale_order.order_line:
                if line.discount_type in ['percent','amount'] and line.discount != False:
                    dis = line.discount
                    line.discount = dis - 1
                    line.discount = dis
                
        
class SaleOrderLine(models.Model):
    """inherited sale order"""
    _inherit = 'sale.order.line'

    remark = fields.Char(string="Remark")
    division_id = fields.Many2one('analytic.division',string="Division")
    product_variant_ids = fields.Many2many('product.template.attribute.value','sale_order_variant_rel',related="product_id.product_template_variant_value_ids")
    can_be_unit = fields.Boolean()
    # serial_no_id = fields.Many2one('stock.lot', string="Serial Number")
    serial_no_id = fields.Many2one('stock.lot', string="Serial Number", domain="[('product_id', '=', product_id), ('id', 'in', available_lot_ids)]")
    available_lot_ids = fields.Many2many('stock.lot', compute='_compute_available_lot_ids')
    remaining_stock = fields.Float('On hand',compute="compute_remaining_stock")
    
    @api.depends('product_id','order_id.location_id')
    @api.onchange('product_id')    
    def compute_remaining_stock(self):
        for rec in self:
            qty = 0
            location_id = self.order_id.location_id
            if rec.product_id and location_id:
                quants = self.env['stock.quant'].search([
                        ('product_id', '=', rec.product_id.id),('location_id', '=', location_id.id)
                    ])
                for qt in quants:
                    qty += qt._get_available_quantity(rec.product_id, location_id)
            rec.remaining_stock = round(qty,2)     

    @api.depends('product_id')
    def _compute_available_lot_ids(self):
        for line in self:
            if line.product_id and line.can_be_unit:
                stock_lot = self.env['stock.lot'].search([('product_id','=',line.product_id.id),('product_qty','>',0)])
                line.available_lot_ids = stock_lot.filtered(lambda stock: not self.env['sale.order.line'].search_count([
                            ('serial_no_id','=',stock.id),
                            ('state','not in',('cancel','draft'))
                        ]))
                line.order_id.allow_fleet_partner_relationship = False if any(line.order_id.order_line.mapped('can_be_unit')) else line.order_id.company_id.allow_fleet_partner_relationship
            else:
                line.available_lot_ids = self.env['stock.lot']

    @api.onchange('serial_no_id')
    def _onchange_serial_no_id(self):
        for line in self:
            envv = self.env['account.analytic.account']

            analytic_account = self.env['account.analytic.account'].search([('id','=',line.serial_no_id.analytic_account_id.id)])
            if analytic_account:
                line.analytic_distribution = {str(analytic_account.id) : 100}
  
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
        if  hasattr(self, 'serial_no_id') and self.serial_no_id:
            if self.serial_no_id.analytic_account_id:
                dct[str(self.serial_no_id.analytic_account_id.id)] = 100 

        if hasattr(self,'fleet_id') and self.fleet_id and self.fleet_id.analytic_fleet_id and  self.company_id == self.fleet_id.company_id:
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100

        # analytic_distribution_ids = [ int(x) for x in list(self.analytic_distribution.keys())]
        # check_account = self.env['stock.lot'].search([('product_id','=',self.product_id.id),('analytic_account_id','in',analytic_distribution_ids)])
        # if len(check_account) > 1:
        #     raise ValidationError(_('Only one analytic account is allowed.'))
        # elif not check_account:
        #     raise ValidationError(_('Invalid Analytic Distribution.'))
        # self.analytic_distribution[str(check_account.analytic_account_id.id)] = 100

        unit_account_exist = False
        for key,val in dct.items():
            is_unit_account = self.env['stock.lot'].search([('analytic_account_id','=',int(key))],limit=1)
            if is_unit_account:
                if not unit_account_exist:
                    dct[key] = 100 
                    unit_account_exist = True
                else:
                    raise ValidationError('Only One Account is allowed')
        self.analytic_distribution = dct    

    @api.constrains('analytic_distribution')
    def _check_unit_product_analytic(self):
        for rec in self:
            if rec.analytic_distribution and rec.product_id.can_be_unit and not rec.product_id.tracking == 'none':
                # product_analytic_account_ids = self.env['stock.lot'].search([('product_id','=',self.product_id.id)]).mapped('analytic_account_id')
                analytic_distribution_ids = [ int(x) for x in list(rec.analytic_distribution.keys())]
                check_account = self.env['stock.lot'].search([('product_id','=',rec.product_id.id),('analytic_account_id','in',analytic_distribution_ids)])
                if len(check_account) > 1:
                    raise ValidationError(_('Only one analytic account is allowed.'))
                elif not check_account:
                    raise ValidationError(_('Unmatched Analytic account with product'))
                elif check_account.analytic_account_id.id != rec.serial_no_id.analytic_account_id.id:
                    raise ValidationError(_('Unmatched Analytic account with product with serial number.'))

                rec.analytic_distribution[str(check_account.analytic_account_id.id)] = 100
            # self.env['stock.lot'].search([('product_id','=',self.product_id.id)]).mapped('analytic_account_id')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id.can_be_unit and rec.product_id.tracking == 'none':
                dct = {}
                if rec.analytic_distribution:
                    dct = rec.analytic_distribution
                dct[str(rec.product_id.analytic_account_id.id)] = 100
                rec.analytic_distribution= dct
            if rec.product_id.can_be_unit:
                rec.can_be_unit = True 


    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            line.name = line.product_template_id.name 

    def _get_sale_description_report(self):
        self.ensure_one()
        sale_description = ''
        if self.product_id.description_sale:
            sale_description = '<br>' +self.product_id.description_sale.replace('\n', '<br>')
        return sale_description

    def _prepare_invoice_line(self, **optional_values):    
        lines = super()._prepare_invoice_line(**optional_values)
        updated_dct = {"remark": self.remark}
        if hasattr(self, 'project_id'):
            updated_dct["project_id"] = self.project_id.id
        if hasattr(self, 'fleet_id'):
            updated_dct["fleet_id"] = self.fleet_id.id
        if hasattr(self, 'division_id'):
            updated_dct["division_id"] = self.division_id.id
        if hasattr(self, 'repair_object_id'):
            updated_dct["repair_object_id"] = self.repair_object_id.id
        lines.update(updated_dct)
        return lines
    
    def check_stock(self):
        for rec in self:
            rec.compute_remaining_stock()
            if rec.product_uom_qty > rec.remaining_stock:
                raise ValidationError('%s is not available to sale.Please check available stock.'% rec.product_id.name)        
        

class StockPicking(models.Model):
    _inherit = "stock.picking"

    internal_ref = fields.Char(string="Internal Reference")

    @api.model_create_multi
    def create(self, vals_list):
        scheduled_dates = []
        for vals in vals_list:
            defaults = self.default_get(['name', 'picking_type_id'])
            picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id', defaults.get('picking_type_id')))
            if vals.get('name', '/') == '/' and defaults.get('name', '/') == '/' and vals.get('picking_type_id', defaults.get('picking_type_id')):
                if picking_type.sequence_id:
                    vals['name'] = picking_type.sequence_id.next_by_id()

            # make sure to write `schedule_date` *after* the `stock.move` creation in
            # order to get a determinist execution of `_set_scheduled_date`
            scheduled_dates.append(vals.pop('scheduled_date', False))
        ## Update Location which selected in Sale Order #Chunni
        for val_list in vals_list:
            location =self.env['sale.order'].search([('name','=',val_list.get('origin'))]).location_id
            if location and val_list.get('location_id'):
                val_list.update({'location_id':location.id})

        pickings = super().create(vals_list)

        for picking, scheduled_date in zip(pickings, scheduled_dates):
            if scheduled_date:
                picking.with_context(mail_notrack=True).write({'scheduled_date': scheduled_date})
        pickings._autoconfirm_picking()

        for picking, vals in zip(pickings, vals_list):
            # set partner as follower
            if vals.get('partner_id'):
                if picking.location_id.usage == 'supplier' or picking.location_dest_id.usage == 'customer':
                    picking.message_subscribe([vals.get('partner_id')])
            if vals.get('picking_type_id'):
                for move in picking.move_ids:
                    if not move.description_picking:
                        move.description_picking = move.product_id.with_context(lang=move._get_lang())._get_description(move.picking_id.picking_type_id)
        return pickings
    
class ResPartner(models.Model):
    _inherit = "res.partner"

    is_other_contact = fields.Boolean(string="Is Other Contact?",default=False)


class AccountMove(models.Model):
    _inherit = "account.move"

    other_contact_id = fields.Many2one(comodel_name='res.partner',string='Contact Person',domain=[('is_other_contact','=',True)])


    def button_draft(self):
        order_id = self.line_ids.sale_line_ids.order_id.id
        if order_id:
            commission_moves = self.env['account.move'].search([('commercial_sale_id','=',order_id)])
            if commission_moves and len(commission_moves) != 2 and commission_moves.reversal_move_id not in commission_moves:   
                raise UserError('You can not reset to draft the invoice which has a commission bill.')
        return super().button_draft()
    
    def button_cancel(self):
        order_id = self.line_ids.sale_line_ids.order_id.id
        if order_id:
            commission_moves = self.env['account.move'].search([('commercial_sale_id','=',order_id)])
            if commission_moves and len(commission_moves) != 2 and commission_moves.reversal_move_id not in commission_moves:
                raise UserError('You can not reset to draft the invoice which has a commission bill.')
        return super().button_cancel()

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_invoice_description_report(self):
        self.ensure_one()
        sale_description = ''
        if self.product_id.description_sale:
            sale_description = '<br>' +self.product_id.description_sale.replace('\n', '<br>')
        return sale_description