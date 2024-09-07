from odoo import models,fields
import base64
from io import BytesIO
import pandas as pd
from odoo.exceptions import ValidationError
import re

class FileImportWizard(models.Model):
    _name = "file.import.wizard"

    file = fields.Binary(string='File', required=True)
    file_name = fields.Char(string='File Name')

    def import_file(self):
        self.ensure_one()

        if not self.file:
            return
        
        file_data = base64.b64decode(self.file)
        file_io = BytesIO(file_data)

        df = pd.read_excel(file_io)


        current_department = self.env['hr.department']
        for idx, row in df.iterrows():
            approval_user = None
            if not pd.isna(row['Company']) and not pd.isna(row['Division']) and not pd.isna(row['Name']) and not pd.isna(row['Department Type']) and not pd.isna(row['Approval User']):
                current_department = None

                company = self.env['res.company'].search([('name','=',row['Company'])])
                division_list = row['Division'].split('/')

                if not company:
                    raise ValidationError(f"Company {row['Company']} at row {idx+2} does not exist!")
                business_unit = self.env['hr.department'].search([('name','=',division_list[0].strip()),('department_type','=','business')],limit=1)

                division = self.env['hr.department'].search([('name','=',division_list[1].strip()),('department_type','=','division'),('parent_id','=',business_unit.id)],limit=1)
             
                if not business_unit or not division:
                    raise ValidationError(f"Division {row['Division']} at row {idx+2} does not exist!")
                
                department = self.env['hr.department'].search([('company_id','=',company.id),('department_type','=','department'),('parent_id','=',division.id),('name','=',row['Name'])],limit=1)

                if not department:
                    raise ValidationError(f"Department {row['Name']} at row {idx+2} does not exist!")
               
                
                approval_user = self.env['hr.employee'].search(['|',('name','=',row['Approval User']),('employee_id','=',row['Approval User'])],limit=1)

                if not approval_user:
                    raise ValidationError(f"Employee {row['Approval User']} at row {idx+2} does not exist!")

                current_department = department
                current_department.department_approve_user_id = [[6,0,current_department.department_approve_user_id.ids+[approval_user.user_id.id]]]
            elif pd.isna(row['Company']) and pd.isna(row['Division']) and pd.isna(row['Name']) and pd.isna(row['Department Type']) and not pd.isna(row['Approval User']): 
                
                approval_user = self.env['hr.employee'].search(['|',('name','=',row['Approval User']),('employee_id','=',row['Approval User'])],limit=1)
                
                if not approval_user:
                    raise ValidationError(f"Approval User {row['Approval User']} at row {idx+2} does not exist!")
                    
                if current_department and approval_user:
                    current_department.department_approve_user_id = [[6,0,current_department.department_approve_user_id.ids+[approval_user.user_id.id]]]
        
