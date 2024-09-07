from odoo import fields,models,api,_ 
from odoo.exceptions import UserError, ValidationError

class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    employee_id = fields.Many2one('hr.employee')
    maintenance_type = fields.Many2one('maintenance.type', string='Maintenance Type', default="corrective")
    schedule_ids = fields.One2many('maintenance.work.schedule','maintenance_id')
    equipment_type = fields.Selection([
        ('fleet','Fleet'),
        ('equipment','Equipment')
        ])
    maintenance_fleet_ids = fields.Many2many('fleet.vehicle','maintenance_fleet_vehicle_rel','maintenance_fleet_id')
    maintenance_equipment_ids = fields.Many2many('account.asset','maintenance_account_asset_rel','maintenance_equipment_id')
    approval_state = fields.Selection([
        ('draft','Draft'),
        ('submit','Submit'),
        ('approve','Approve'),
        ('reject','Reject'),
        ('done','Done'),
    ], default='draft')
    team_members_ids = fields.Many2many('res.users','maintenance_request_team_members_rel',related="maintenance_team_id.member_ids")
    assign_technician = fields.Many2one('res.users',string="Assign Technician")
    
    @api.onchange('stage_id')
    def _onchange_state_id(self):
        for rec in self:
            if rec.stage_id.name != 'New Request' and not self.user_has_groups('maintenance.group_equipment_manager'):
                raise ValidationError(_('You do not have access right to change the maintenance stage.'))

            
    @api.onchange('equipment_type')
    def _onchange_equiment_type(self):
        for rec in self:
            if rec.equipment_type == 'fleet':
                rec.maintenance_equipment_ids = False
                 
            else:
                rec.maintenance_fleet_ids = False
                self.env['account.asset'].search([('fleet_id','=',False)])
                return {
                        'domain': {
                            'maintenance_equipment_ids': [('id','in',self.env['account.asset'].search([('fleet_id','=',False)]).ids)]
                        }
                    }

    def action_submit(self):
        for rec in self:
            rec.approval_state = 'submit'

    def action_approve(self):
        for rec in self:
            rec.approval_state = 'approve'

    def action_reject(self):
        for rec in self:
            rec.approval_state = 'reject'
 
    def action_done(self):
        for rec in self:
            rec.approval_state = 'done'
    
    def unlink(self):
        for rec in self:
            if rec.approval_state != 'draft':
                raise UserError(_('You can not delete a record that is in %s state',self.approval_state))
        return super().unlink()
    
class MaintenanceType(models.Model):
    _name = "maintenance.type"

    name = fields.Char('Name')

class MaintenanceWorkSchedule(models.Model):
    _name = "maintenance.work.schedule"
    
    maintenance_id = fields.Many2one('maintenance.request')
    date = fields.Date()
    gp_leader_id = fields.Many2one('hr.employee',string= 'Leader')
    team_id = fields.Many2one('maintenance.team',related="maintenance_id.maintenance_team_id", string= 'Team')

    member_ids = fields.Many2many('hr.employee',string="Member")
    job_desc = fields.Char('Job Description')
    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')
    duration = fields.Float('Total Hours')
    repair_id = fields.Many2one('repair.order','Repair ID')
    work_location = fields.Many2one('work.location')
    remark = fields.Char("Remark")
    amount = fields.Float('Amount',default=0.0)
    team_member_emp_ids = fields.Many2many('hr.employee','maintenance_work_schedule_member_ids_rel',compute="_compute_team_member_emp_ids")


    def _compute_team_member_emp_ids(self):
        for rec in self:
            if rec.maintenance_id:
                employee_ids = self.env['hr.employee'].search([('user_id','in',rec.maintenance_id.maintenance_team_id.member_ids.ids)])
                rec.team_member_emp_ids = employee_ids.ids

    @api.onchange('team_id')
    def onchange_team_id(self):
        for rec in self:
            if rec.maintenance_id:
                employee_ids = self.env['hr.employee'].search([('user_id','in',rec.maintenance_id.maintenance_team_id.member_ids.ids)])
                rec.team_member_emp_ids = employee_ids.ids

    @api.onchange('start_time','end_time')
    def set_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                rec.duration = abs((rec.start_time - rec.end_time))
