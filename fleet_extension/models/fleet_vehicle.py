from odoo import fields, models, api
from odoo.exceptions import ValidationError,UserError
from datetime import timedelta,datetime

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    def _get_selection_m2o_vehicle_type(self):
        options = [('ship','Ship'),('submarine', 'Submarine')]
        return options
    
    type = fields.Selection(selection=[('fleet', 'Fleet')],default='fleet',string="Type", store=True)
    brand_id = fields.Many2one('fleet.vehicle.model.brand', 'Brand', related=False, store=True, readonly=False)
    model_id = fields.Many2one('fleet.vehicle.model', 'Model',tracking=True, required=False)

    allow_analytic = fields.Boolean(string="Create Analytic Account", default=True)
    analytic_plan_id = fields.Many2one(string="Analytic Plan", comodel_name="account.analytic.plan")
    analytic_fleet_id = fields.Many2one('account.analytic.account',string="Analytic Fleet")
    name = fields.Char(string="Name",compute=False,store=True)
    driver_id = fields.Many2one('hr.employee', 'Driver', tracking=True, help='Driver address of the vehicle', copy=False)
    owner_id = fields.Many2one(comodel_name='fleet.owner',string="Owner")
    engine_model_id = fields.Many2one(comodel_name='fleet.engine.model',string="Engine Model")
    engine_serial = fields.Char(string="Engine Serial")
    mc_serial = fields.Char(string="MC Serial")
    smu = fields.Char("SMU")
    onhand_fuel = fields.Float("OnHand Fuel",readonly=True,digits=(16,2))
    service_meter = fields.Float("Service Meter")
    duty_price = fields.Float("Duty Price")
    standard_consumption = fields.Float('Standard Consumption',default=0.0)
    location_id = fields.Many2one('stock.location',string="Fuel Source Location")
    location = fields.Many2one('fleet.vehicle.location',string="Location")
    location_lines = fields.One2many("fleet.vehicle.location.history","fleet_id",string="Location History Lines")
    price_type = fields.Selection([('way', 'Way'),('dm', '1 Duty / 1 Month'), ('hd', '1 Hour / 1 Day')], string='Price Type', default='dm',)
    product_id = fields.Many2one('product.product',string="Ref Product")
    partner_id = fields.Many2one('res.partner',string="Vendor (Owner)")
    vehicle_type = fields.Selection(selection=[('ship','Ship'),('submarine', 'Submarine')],string="Vehicle Type")
    vehicle_type_id = fields.Many2one('vehicle.type',string="Vehicle Type ID")
    short_name = fields.Char("Short Name")
    machine_capacity = fields.Many2one('machine.capacity')
    model_name = fields.Char(related="model_id.name",store=True)
    imei = fields.Char("IMEI")
    owner_type = fields.Selection([('family','Family'),('internal','Internal'),('external','External')],string="Owner Type", default='family',required=True,tracking=True)
    partner_ids = fields.Many2many('res.partner',string="Partners",store=True)
    allow_fleet_partner_relationship = fields.Boolean(string="Fleet Partner Relationship",related="company_id.allow_fleet_partner_relationship")
    default_attachment_id = fields.Many2one("fleet.attachment",string="Default Attachment")
    check_computer = fields.Boolean(string="Compute Function for other calculations",compute="_compute_calculations")

    # Account Setting 
    repair_account_id = fields.Many2one("account.account",string="Repair Account")
    fuel_account_id = fields.Many2one("account.account",string="Fuel Acscount")
    duty_hr_account_id = fields.Many2one("account.account",string="Duty HR Account")
    duty_depreciation_account_id = fields.Many2one("account.account",string="Duty Depreciation Account")

    _sql_constraints = [
        ("unique_fleet_vehilce_name_company", "UNIQUE(name,company_id)", "Fleet Name must be unique within same company!!")
    ]

    @api.model_create_multi
    def create(self, vals_list):
        ptc_values = [self._clean_vals_internal_user(vals) for vals in vals_list]
        analytic_acc = False
        for val_lst in vals_list:
            fleet_name:str = val_lst['name']
            if fleet_name and fleet_name.strip() != '':
                if 'allow_analytic' in val_lst and val_lst['allow_analytic']:
                    analytic_acc = self.env['account.analytic.account'].create({
                            'name': fleet_name,
                            'plan_id':val_lst['analytic_plan_id'],
                            'company_id': self.env.company.id
                    })
                    val_lst['analytic_fleet_id'] = analytic_acc.id
            else:
                raise ValidationError("Invalid Vehicle Name!!")        
        vehicles = super().create(vals_list)
        if analytic_acc and hasattr(analytic_acc, 'fleet_id'):
            analytic_acc.fleet_id = vehicles.id        
        for vehicle, vals, ptc_value in zip(vehicles, vals_list, ptc_values):
            if ptc_value:
                vehicle.sudo().write(ptc_value)
            if 'driver_id' in vals and vals['driver_id']:
                vehicle.create_driver_history(vals)
            if 'future_driver_id' in vals and vals['future_driver_id']:
                state_waiting_list = self.env.ref('fleet.fleet_vehicle_state_waiting_list', raise_if_not_found=False)
                states = vehicle.mapped('state_id').ids
                if not state_waiting_list or state_waiting_list.id not in states:
                    future_driver = self.env['hr.employee'].browse(vals['future_driver_id'])
                    if self.vehicle_type == 'bike':
                        future_driver.sudo().write({'plan_to_change_bike': True})
                    if self.vehicle_type == 'car':
                        future_driver.sudo().write({'plan_to_change_car': True})
        return vehicles 
    
    @api.depends('model_id.brand_id.name', 'model_id.name', 'license_plate')
    def _compute_vehicle_name(self):
        pass   

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|',('name',operator,name),('license_plate',operator,name)]
        search_ids = self._search(domain + args,limit=limit,access_rights_uid=name_get_uid)
        return search_ids    

    def _compute_calculations(self):
        today_date = datetime.now()
        for rec in self:
            # locations = rec.location_lines.filtered(lambda x:x.start_time <= today_date and (not x.end_time or x.end_time >= today_date))
            # rec.location = (locations and locations[0].location_id ) or False
            location = rec.location_lines.search(['&','&',('fleet_id','=',rec.id),('start_time','<=',today_date),'|',('end_time','=',False),('end_time','>=',today_date)], limit=1).location_id
            location = location.id if location else location
            rec.sudo().write({"location":location})
            rec.check_computer = True

    def write(self, vals):
        if 'driver_id' in vals and vals['driver_id']:
            driver_id = vals['driver_id']
            for vehicle in self.filtered(lambda v: v.driver_id.id != driver_id):
                vehicle.create_driver_history(vals)
                if vehicle.driver_id:
                    vehicle.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=vehicle.manager_id.id or self.env.user.id,
                        note= ('Specify the End date of %s') % vehicle.driver_id.name
                    )

        if 'future_driver_id' in vals and vals['future_driver_id']:
            state_waiting_list = self.env.ref('fleet.fleet_vehicle_state_waiting_list', raise_if_not_found=False)
            states = self.mapped('state_id').ids if 'state_id' not in vals else [vals['state_id']]
            if not state_waiting_list or state_waiting_list.id not in states:
                future_driver = self.env['res.partner'].browse(vals['future_driver_id'])
                if self.vehicle_type == 'bike':
                    future_driver.sudo().write({'plan_to_change_bike': True})
                if self.vehicle_type == 'car':
                    future_driver.sudo().write({'plan_to_change_car': True})

        if 'active' in vals and not vals['active']:
            self.env['fleet.vehicle.log.contract'].search([('vehicle_id', 'in', self.ids)]).active = False
            self.env['fleet.vehicle.log.services'].search([('vehicle_id', 'in', self.ids)]).active = False

        su_vals = self._clean_vals_internal_user(vals)
        if su_vals:
            self.sudo().write(su_vals)
        # update analytic plan
        if 'analytic_plan_id' in vals:
            fleet_objs = self.env['fleet.vehicle'].search([('id','=',self.id)])
            if fleet_objs and not fleet_objs.analytic_fleet_id:
                analytic_acc = self.env['account.analytic.account'].create({
                        'name': self.name,
                        'plan_id':vals['analytic_plan_id'],
                        'company_id': self.env.company.id
                })
                self.analytic_fleet_id = analytic_acc.id
        # update name in account analytic
        if 'name' in vals:
            fleet_objs = self.env['fleet.vehicle'].search([('name','=',vals['name']),('id','!=',self.id)])
            if fleet_objs:
                raise ValidationError("Fleet Name is already existed!!")
            if self.analytic_fleet_id:
                self.analytic_fleet_id.name = vals['name']             
        res = super().write(vals)
        return res  

    def unlink(self):
        for rec in self:
            acc_obj = self.env['account.analytic.account'].search([('name','=',rec.name)])
            if acc_obj:
                acc_obj.unlink()
        return super().unlink()     

class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, record.name))
        return res    

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle.model'

    def _get_selection_m2o_vehicle_type(self):
        all_vehicle_types = self.env['vehicle.type'].search([])
        options = [(vehicle_type.name.lower(),vehicle_type.name) for vehicle_type in all_vehicle_types]
        return options  

    vehicle_type = fields.Selection(_get_selection_m2o_vehicle_type, default='car', required=True)     

class FleetVehicleAssignationLog(models.Model):
    _inherit = "fleet.vehicle.assignation.log"

    driver_id = fields.Many2one('hr.employee', string="Driver", required=True)

class FleetOwner(models.Model):
    _name = "fleet.owner"

    name = fields.Char(string="name")

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Owner name must be unique')
    ]


class FleetEngineModel(models.Model):
    _name = "fleet.engine.model"

    name = fields.Char(string="name")

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Fleet Engine Model name must be unique')
    ]    

class FleetVehicleLocation(models.Model):
    _name = "fleet.vehicle.location"

    name = fields.Char(string="Name")

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', 'Fleet Vehicle Location name must be unique')
    ]       

class FleetVehicleLocationHistory(models.Model):
    _name = 'fleet.vehicle.location.history'
    _order = 'start_time'

    fleet_id = fields.Many2one("fleet.vehicle",string="Fleet Vehicle",domain=[("type", "=", "fleet")])
    location_id = fields.Many2one('fleet.vehicle.location',string="Location")
    start_time = fields.Datetime("Start Time")
    end_time = fields.Datetime("End Time")

    @api.constrains("location_id","start_time")
    def _create_location_history_line_in_fleet(self):
        prev_line = None
        for line in self.fleet_id.location_lines.sorted(lambda self:self.start_time):
            if prev_line:
                if prev_line.end_time and (line.start_time <= prev_line.end_time):
                    raise ValidationError(f"Start Time <{line.start_time}> of Location <{line.location_id.name}> must be greater than End Time <{prev_line.end_time}> of previous line!!!")
                prev_line.end_time = line.start_time - timedelta(minutes=1)
            prev_line = line
            


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    fleet_id = fields.Many2one(string="Fleet",comodel_name="fleet.vehicle",domain=[("type", "=", "fleet")]) 
    owner_id = fields.Many2one(comodel_name='fleet.owner',string="Owner",related="fleet_id.owner_id")

    @api.onchange('fleet_id')
    def _onchage_analytic_by_fleet(self):
        if not self.fleet_id:
            active_model =  self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')
            if active_model and active_id and active_model in ('repair.request','repair.order'):
                repair_obj = self.env[active_model].search([('id','=',active_id)],limit=1)
                if repair_obj:
                    self.fleet_id = repair_obj.company_no.id
                else:
                    raise ValidationError("Unknown context or repair object is not found!!!")            
        if self.fleet_id and self.fleet_id.analytic_fleet_id and  self.company_id == self.fleet_id.company_id:
                dct = self.analytic_distribution if self.analytic_distribution else {}
                dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
                self.analytic_distribution = dct            

class AccountCashBookLine(models.Model):
    _inherit = 'account.cashbook.line'    

    fleet_id = fields.Many2one('fleet.vehicle',string="Fleet",domain=[("type", "=", "fleet")])    

    @api.onchange('fleet_id')
    def _onchage_analytic_by_fleet(self):
        if self.fleet_id.analytic_fleet_id and self.company_id == self.fleet_id.company_id:
            dct = self.analytic_distribution if self.analytic_distribution else {}
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
            self.analytic_distribution = dct


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order.line'

    fleet_id = fields.Many2one('fleet.vehicle','Fleet',domain=[("type", "=", "fleet")])

    @api.onchange('fleet_id')
    def _onchage_analytic_by_fleet(self):
        if self.fleet_id.analytic_fleet_id and  self.company_id == self.fleet_id.company_id:
            dct = self.analytic_distribution if self.analytic_distribution else {}
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
            self.analytic_distribution = dct    

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    own_fleet_id = fields.Many2one('fleet.vehicle','Owned Fleet',domain=[("type", "=", "fleet")])
    allow_fleet_partner_relationship = fields.Boolean(string="Fleet-Partner Relationship",related="company_id.allow_fleet_partner_relationship")

    @api.onchange("partner_id")
    def _onchage_fleet_domain_by_partner(self):
        if self.partner_id:
            if self.partner_id.fleet_ids:
                return {"domain": {"own_fleet_id":[('id','in',self.partner_id.fleet_ids.ids)]}}
            return {"domain": {"own_fleet_id":[('id','=',-1)]}}
        return {"domain": {"own_fleet_id":[]}}
        
    @api.onchange("own_fleet_id")
    def _onchage_partner_domain_by_fleet(self):
        if self.own_fleet_id:
            if self.own_fleet_id.partner_ids:
                return {"domain": {"partner_id":[('id','in',self.own_fleet_id.partner_ids.ids)]}}
            return {"domain": {"partner_id":[('id','=',-1)]}}
        if self.env.company.allow_partner_domain_feature:

            return {"domain": {"partner_id":[
                    ('partner_type','=','customer'),
                    ('type', '!=', 'private'), 
                    ('company_id', 'in', (False, self.env.company.id))

            ]}}        
        return {"domain": {"partner_id":[
                    ('type', '!=', 'private'), 
                    ('company_id', 'in', (False, self.env.company.id))

            ]}}        

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    fleet_id = fields.Many2one('fleet.vehicle','Fleet',domain=[("type", "=", "fleet")])  

    @api.onchange('fleet_id')
    def _onchage_analytic_by_fleet(self):
        if not self.fleet_id and len(self.order_id.order_line) > 1:
            analytic_dct = self.order_id.order_line[-2].analytic_distribution
            order_id = self.order_id
            if (hasattr(order_id, 'repair_request_id') and order_id.repair_request_id ) or (hasattr(order_id, 'job_order_id') and order_id.job_order_id) or (hasattr(order_id,'requisition_id') and order_id.requisition_id):
                self.fleet_id = self.order_id.order_line[-2].fleet_id
            else:
                prev_fleet = self.order_id.order_line[-2].fleet_id
                if prev_fleet and prev_fleet.analytic_fleet_id and str(prev_fleet.analytic_fleet_id.id) in analytic_dct:
                    analytic_dct.pop(str(prev_fleet.analytic_fleet_id.id))
            self.analytic_distribution = analytic_dct
        elif self.fleet_id.analytic_fleet_id and  self.company_id == self.fleet_id.company_id:
            dct = self.analytic_distribution if self.analytic_distribution else {}
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
            self.analytic_distribution = dct      

class StockAdjustmentLine(models.Model):
    _inherit = "stock.inventory.adjustment.line"

    fleet_location_id = fields.Many2one('fleet.vehicle','Fleet Location')
    fleet_id = fields.Many2one('fleet.vehicle','Fleet',domain=[("type", "=", "fleet")])   
    fleet_owner_id = fields.Many2one('fleet.owner','Fleet Owner',related="fleet_id.owner_id")

    @api.onchange('fleet_id')
    def _onchage_analytic_by_fleet(self):
        if not self.fleet_id and len(self.adjust_id.adjustment_line_id) > 1:
            analytic_dct = self.adjust_id.adjustment_line_id[-2].analytic_distribution
            adjust_id = self.adjust_id
            if (hasattr(adjust_id, 'repair_request_id') and adjust_id.repair_request_id ) or (hasattr(adjust_id, 'job_order_id') and adjust_id.job_order_id) or (hasattr(adjust_id,'requisition_id') and adjust_id.requisition_id):
                self.fleet_id = adjust_id.adjustment_line_id[-2].fleet_id
            else:
                prev_fleet = adjust_id.adjustment_line_id[-2].fleet_id
                if prev_fleet and prev_fleet.analytic_fleet_id and str(prev_fleet.analytic_fleet_id.id) in analytic_dct:
                    analytic_dct.pop(str(prev_fleet.analytic_fleet_id.id))
            self.analytic_distribution = analytic_dct
        elif self.fleet_id.analytic_fleet_id and  self.company_id == self.fleet_id.company_id:
            dct = self.analytic_distribution if self.analytic_distribution else {}
            dct[str(self.fleet_id.analytic_fleet_id.id)] = 100
            self.analytic_distribution = dct            


class StockMove(models.Model):
    _inherit = 'stock.move'

    fleet_id = fields.Many2one('fleet.vehicle','Fleet',domain=[("type", "=", "fleet")])  
    fleet_location_id = fields.Many2one('fleet.vehicle','Fleet Location') 

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    fleet_id = fields.Many2one('fleet.vehicle','Fleet',related="move_id.fleet_id")
    fleet_location_id = fields.Many2one('fleet.vehicle','Fleet Location',related="move_id.fleet_location_id") 

class StockValuaionLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    fleet_id = fields.Many2one('fleet.vehicle','Fleet') 
    fleet_location_id = fields.Many2one('fleet.vehicle','Fleet Location')     

class StockAdjustmentLine(models.Model):
    _inherit = "stock.location.valuation.report"

    fleet_id = fields.Many2one('fleet.vehicle','Fleet')  
    fleet_location_id = fields.Many2one('fleet.vehicle','Fleet Location')

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    fleet_id = fields.Many2one('fleet.vehicle','Fleet') 

    def _update_fleet_of_account_analytic_account(self):
        datas = self.env['fleet.vehicle'].search([('analytic_fleet_id','!=',False)])
        for data in datas:
            data.analytic_fleet_id.fleet_id = data.id       

class RequisitionLine(models.Model):
    _inherit = 'requisition.line'

    fleet_id = fields.Many2one('fleet.vehicle',string='Fleet',domain=[("type", "=", "fleet")])       

class VehicleType(models.Model):
    _name = "vehicle.type"        

    name = fields.Char("Vehicle Type")   

class MachineCapacity(models.Model):
    _name = "machine.capacity"

    name = fields.Char("Machine Capacity")   

class ResCompany(models.Model):
    _inherit = 'res.company'

    allow_fleet_partner_relationship = fields.Boolean(string="Fleet-Partner Relationship",default=False)
    product_income_type = fields.Boolean("Product Income Type",default=True)

class ResPartnerFleet(models.Model):
    _inherit = 'res.partner' 

    fleet_ids = fields.Many2many(string="Fleet Vehicles",comodel_name="fleet.vehicle",store=True)
    allow_fleet_partner_relationship = fields.Boolean(string="Fleet Partner Relationship", related="company_id.allow_fleet_partner_relationship")


class Picking(models.Model):
    _inherit = "stock.picking"

    fleet_id = fields.Many2one('fleet.vehicle','Fleet',domain=[("type", "=", "fleet")])  
    fleet_owner_id = fields.Many2one('fleet.owner',string="Owner",related="fleet_id.owner_id",store=True,domain=[])
