from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta,datetime

class RepairCall(models.Model):
    _name = "repair.call"
    _description = "Repair Calls"

    name = fields.Char("Call Ref.")
    date = fields.Date("Date")
    call_date = fields.Date("Call Date",default=date.today())
    call_type = fields.Selection([('psfu','PSFU'),('reminder','Reminder')],string="Call Type",default="psfu")
    request_id = fields.Many2one("customer.request.form",string="Customer Request No.")
    quotation_id = fields.Many2one("request.quotation",string="Request Quotation")
    branch_id = fields.Many2one("res.branch",string="Branch",related="quotation_id.branch_id")
    customer_id = fields.Many2one("res.partner",string="Customer",related="quotation_id.customer")
    customer_phone = fields.Char("Customer Phones")
    fleet_id = fields.Many2one("fleet.vehicle",string="Fleet",related="quotation_id.fleet_id")
    fleet_brand_model = fields.Char("Fleet Brand Model")
    customer_requests = fields.Text(string="Customer Requests",related="request_id.description")
    reception_date = fields.Datetime(string="Reception Date",related="request_id.reception_date")
    issued_date = fields.Datetime(string="issued Date",related="request_id.issued_date")
    repaired_jobs = fields.Char(string="Repair Jobs")
    repaired_parts = fields.Char(string="Repair Parts")
    call_status = fields.Many2one("repair.call.status",string="Call Status")
    remark = fields.Char(string="Remark")
    sequence = fields.Integer(string="Sequence")
    state = fields.Selection([('not_call','Not Called'),('call','Called')],string="Status")

    def action_call(self):
        for res in self:
            print("nani")

    def action_call_customer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Repair Call',
            'res_model': 'repair.call',
            'view_mode': 'form',
            'view_id': self.env.ref('repair_external.view_repair_call_form').id,
            'target': 'new',
            'res_id':self.id,
        }

class RepairCallStatus(models.Model):
    _name = "repair.call.status"
    _description = "Repair Call Status"

    name = fields.Char(string="Call Status")

class RequestQuotation(models.Model):
    _inherit = 'request.quotation'

    psfu_call_id = fields.Many2one("repair.call",string="PSFU Call")

    def action_create_invoice(self):
        print("papi")
        super().action_create_invoice()
        psfu_prefix = "PSFU"
        repaired_jobs = " / ".join(self.job_lines.mapped("job_desc"))
        repaired_parts = " / ".join(self.part_lines.mapped("parts_code"))
        issued_date = self.issued_date if self.issued_date else datetime.now()
        if not self.psfu_call_id:
            query = f""" 
                    SELECT sequence FROM repair_call AS call
                    INNER JOIN customer_request_form AS request
                    ON call.request_id = request.id
                    WHERE call_type = 'psfu' AND request.branch_id = '{self.branch_id.id}' 
                    ORDER BY sequence DESC
                    LIMIT 1;
            """
            self.env.cr.execute(query)
            datas = self.env.cr.fetchone()
            if not datas:
                sequence = "1"
            else:
                sequence = str(datas[0] + 1)
            sequence_name = self.branch_id.short_code + "/" + psfu_prefix + "/" + sequence.rjust(6,"0")
            psfu_call_id = self.env['repair.call'].create({
                "name":sequence_name,
                "date":(issued_date  + timedelta(days=3)).date(),
                "call_type":"psfu",
                "request_id": self.request_id.id,
                "quotation_id":self.id,
                "customer_phone": ( self.customer and self.customer.phone and self.customer.phone + ' / ' or '' )  + self.request_id.phone or 'NaN',
                "fleet_brand_model" : ( self.fleet_id.brand_id and self.fleet_id.brand_id.name or 'NaN' ) + ' - ' + ( self.fleet_id.model_id and self.fleet_id.model_id.name or 'NaN') ,
                "sequence" : int(sequence),
                "repaired_jobs":repaired_jobs,
                "repaired_parts":repaired_parts,
                'state':'not_call',
            })
            self.psfu_call_id = psfu_call_id
        else:
            self.psfu_call_id.write({
                "date":(issued_date  + timedelta(days=3)).date(),
                "request_id": self.request_id.id,
                "quotation_id":self.id,
                "customer_phone": ( self.customer and self.customer.phone and self.customer.phone + ' / ' or '' )  + self.request_id.phone or 'NaN',
                "fleet_brand_model" : ( self.fleet_id.brand_id and self.fleet_id.brand_id.name or 'NaN' ) + ' - ' + ( self.fleet_id.model_id and self.fleet_id.model_id.name or 'NaN') ,
                "repaired_jobs":repaired_jobs,
                "repaired_parts":repaired_parts, 
                'state':'not_call',               
            })