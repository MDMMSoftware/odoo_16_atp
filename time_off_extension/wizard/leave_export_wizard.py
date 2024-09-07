from odoo import fields,models
from odoo.exceptions import ValidationError

class AttendanceExport(models.TransientModel):
    _inherit = 'attendance.export.wizard'
    
    export_type = fields.Selection(selection_add=[("leave", "Leave")],string="Export Type")
    
    def generate_leave_report_data(self):
        unit_id = self.unit_id.ids if self.unit_id else [0]
        division_id = self.division_id.ids if self.division_id else [0]
        department_id = self.department_id.ids if self.department_id else [0]
        branch_id = self.branch_id.ids if self.branch_id else [0]    
        report_date = self.from_date.strftime("%Y-%m-%d")
        
        filename = self.env.context.get('filename')
        if not filename:
            raise ValidationError('Filename Not found!!!')
        birt = self.env['ir.config_parameter'].sudo().get_param('birt.report.url','')
        
        if unit_id and report_date and birt:
            url = birt + str(filename) + '.rptdesign&report_date=' + report_date + "&unit_id=" + ",".join(map(str,unit_id)) + "&division_id=" + ",".join(map(str,division_id)) +  "&department_id=" + ",".join(map(str,department_id)) + "&branch_id=" + ",".join(map(str,branch_id))
            return {
                'type' : 'ir.actions.act_url',
                'url' : url,
                'target': 'new',
            }            
        else:
            raise ValidationError('Report Not Not Found')           
                 