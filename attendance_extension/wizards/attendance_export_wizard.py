from odoo import models, fields, api, _
from datetime import datetime, timedelta
try:
   from odoo.tools.misc import xlsxwriter
except ImportError:
   import xlsxwriter
import io
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    # TODO saas-17: remove the try/except to directly import from misc
    import xlsxwriter
import os
import tempfile
import calendar

class AttendanceExport(models.TransientModel):
    _name = 'attendance.export.wizard'
    _description = 'Attedance Export Wizard'

    from_date = fields.Date("Start Date",default=datetime.now())
    to_date = fields.Date("End Date",default=datetime.now())
    unit_id = fields.Many2many('hr.department','attendance_export_unit_rel','attendance_export_id','unit_id',string='Unit',domain="[('department_type','=','business')]")
    division_id = fields.Many2many('hr.department','attendance_export_division_rel','attendance_export_id','division_id', string='Division', domain="[('department_type','=','division')]")
    department_id = fields.Many2many('hr.department','attendance_export_department_rel','attendance_export_id','department_id', string='Department', domain="[('department_type','=','department')]")
    branch_id = fields.Many2many('hr.branch','attendance_export_branch_rel','attendance_export_id','branch_id', string="Branch")
    # attendance_only = fields.Boolean("Attendance Only?")
    # horizontal_report = fields.Boolean("Horizontal Report?")
    export_type = fields.Selection([('attendance','Attendance')],string="Export Type",default="attendance")
    report_type = fields.Selection([
        ('attendence','Attendence'),
        ('horizontal','Horizontal Report'),
        ('movement','Movement'),
        ],default='attendence')
    # @api.onchange('horizontal_report')
    # def _onchange_horizontal_report(self):
    #     # if self.horizontal_report:
    #     #     self.attendance_only = False
    #     if self.report_type in ['horizontal','movement']:
    #         self.attendance_only = False

    # @api.onchange('report_type')
    # def _onchange_report_type(self):
    #     for rec in self:
    #         if rec.report_type == 'attendence':
    #             rec.horizontal_report = False   
    #             rec.attendance_only = True
    #         elif rec.report_type in ['horizontal','movement']:
    #             rec.attendance_only = False
                
    # @api.onchange('attendance_only')
    # def _onchange_attendanc_only(self):
    #     if self.attendance_only:
    #         self.horizontal_report = False            

    @api.onchange('unit_id')
    def onchange_business_unit(self):
        for res in self:
            if res.unit_id:
                return {'domain': {'division_id': [('department_type', '=', 'division'),('parent_id','in',res.unit_id.ids)]}}

    @api.onchange('division_id')
    def onchange_division(self):
        for res in self:
            if res.division_id:
                return {'domain': {'department_id': [('department_type','=','department'),('parent_id','in',res.division_id.ids)]}}
            
    @api.onchange('department_id')
    def onchange_department(self):
        for res in self:
            if res.department_id:
                if not res.division_id:
                    res.division_id = (6,0,[dept_id.parent_id.id for dept_id in res.department_id])
                if not res.unit_id:
                    res.unit_id = (6,0,[dept_id.unit_id.id for dept_id in res.department_id])  

    def export_attendance_data(self):
        # params
        unit_id = self.unit_id.ids if self.unit_id else [0]
        division_id = self.division_id.ids if self.division_id else [0]
        department_id = self.department_id.ids if self.department_id else [0]
        branch_id = self.branch_id.ids if self.branch_id else [0]

        # header default format
        output = io.BytesIO()
        file_name = os.path.join(tempfile.gettempdir(), f'Attendance_Export_{self.from_date}_{self.to_date}.xlsx')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Attendance Export")
        banner_format_small = workbook.add_format({'font_name': 'Arial','bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        time_format = workbook.add_format({'num_format': 'hh:mm:ss'})
        sheet.set_column(0, 0, 40)
        sheet.set_column(1, 1, 15)
        sheet.set_column(2, 2, 25)
        sheet.set_column(3, 3, 15)
        sheet.set_column(4, 4, 36)
        sheet.set_column(5, 5, 15)
        y_offset = 5
        x_offset = 3
        sheet.merge_range(0,0,x_offset,y_offset, _("Attendance"), banner_format_small)
        x_offset+=1
        sheet.write(x_offset,0,(_("Unit")),header_format)
        sheet.write(x_offset,1,",".join(self.unit_id.mapped('name')),header_format)
        sheet.write(x_offset,4,(_("Start Date")),header_format)
        sheet.write(x_offset,5,self.from_date.strftime("%d-%m-%Y"),header_format)
        x_offset+=1
        sheet.write(x_offset,0,(_("Division")),header_format)
        sheet.write(x_offset,1,",".join(self.division_id.mapped('name')),header_format)        
        sheet.write(x_offset,4,(_("End Date")),header_format)
        sheet.write(x_offset,5,self.to_date.strftime("%d-%m-%Y"),header_format)
        x_offset+=1
        sheet.write(x_offset,0,(_("Department")),header_format)
        sheet.write(x_offset,1,",".join(self.department_id.mapped('name')),header_format)
        x_offset+=2               


        if self.report_type in ['horizontal','movement']:
            start_date = self.from_date.replace(day=1)
            end_date = self.to_date.replace(day=calendar.monthrange(self.from_date.year, self.from_date.month)[1])
            if self.report_type == 'horizontal':
                query =f""" 
                            WITH all_dates AS (
                                SELECT 
                                    date_trunc('day', dd)::date AS datee
                                FROM generate_series('{start_date.strftime("%Y-%m-%d")}'::timestamp,'{end_date.strftime("%Y-%m-%d")}'::timestamp,'1 day'::interval) AS dd
                            )	,
                            all_leaves AS (
                                SELECT 
                                    l_type.code as code,emp.id AS employee_id,emp.name,generate_series(date_from,date_to,'1 day'::interval)::date as leave_date 
                                FROM hr_leave AS leave
                                INNER JOIN hr_employee AS emp ON leave.employee_id = emp.id
                                INNER JOIN hr_leave_type AS l_type ON l_type.id = leave.holiday_status_id
                                WHERE
                                    CASE WHEN {unit_id[0]} <> 0 THEN emp.unit_id in ({','.join(map(str,unit_id))})  ELSE emp.id <> 0 END AND
                                    CASE WHEN {division_id[0]} <> 0 THEN emp.division_id in ({','.join(map(str,division_id))}) ELSE emp.id <> 0 END AND
                                    CASE WHEN {department_id[0]} <> 0 THEN emp.department_id in ({','.join(map(str,department_id))}) ELSE emp.id <> 0 END AND
                                    CASE WHEN {branch_id[0]} <> 0 THEN emp.branch_id in ({','.join(map(str,branch_id))}) ELSE emp.id <> 0 END AND
                                    leave.state not in ('draft','refuse')
                            )
                            SELECT 
                                emp.employee_id,emp.name as emp_name,unit.name as unit_name,div.name as div_name,dept.name as dept_name,branch.name as branch_name
                                ,CASE WHEN leave.code IS NOT NULL AND (att.check_in IS  NULL OR att.check_out IS NULL) THEN leave.code
                                    WHEN leave.code IS NULL AND (att.check_in IS NOT NULL OR att.check_out IS NOT NULL) THEN 
                                            CASE 
                                                WHEN att.check_in IS NULL THEN '0:00:00' || ' <=> ' ||TO_CHAR(att.check_out+'6:30','HH24:MI:SS')::text
                                                WHEN att.check_out IS NULL THEN TO_CHAR(att.check_in+'6:30','HH24:MI:SS')::text  || ' <=> ' || '0:00:00'
                                                ELSE TO_CHAR(att.check_in+'6:30','HH24:MI:SS')::text  || ' <=> ' ||TO_CHAR(att.check_out+'6:30','HH24:MI:SS')::text
                                            END
                                    ELSE '-'
                                END AS dataa
                            FROM hr_employee AS emp
                            CROSS JOIN all_dates
                            LEFT JOIN hr_attendance AS att
                                ON att.employee_id = emp.id AND  DATE(att.check_in+'6:30') = all_dates.datee 
                            LEFT JOIN hr_department AS unit
                                ON unit.id = emp.unit_id
                            LEFT JOIN hr_department AS div
                                ON div.id = emp.division_id
                            LEFT JOIN hr_department AS dept
                                ON dept.id = emp.department_id
                            LEFT JOIN hr_branch AS branch
                                ON branch.id = emp.branch_id
                            LEFT JOIN all_leaves AS leave
                                ON (leave.leave_date = DATE(all_dates.datee)) AND (leave.employee_id = emp.id)
                            WHERE
                                emp.active = true AND
                                CASE WHEN {unit_id[0]} <> 0 THEN emp.unit_id in ({','.join(map(str,unit_id))})  ELSE emp.id <> 0 END AND
                                CASE WHEN {division_id[0]} <> 0 THEN emp.division_id in ({','.join(map(str,division_id))}) ELSE emp.id <> 0 END AND
                                CASE WHEN {department_id[0]} <> 0 THEN emp.department_id in ({','.join(map(str,department_id))}) ELSE emp.id <> 0 END AND
                                CASE WHEN {branch_id[0]} <> 0 THEN emp.branch_id in ({','.join(map(str,branch_id))}) ELSE emp.id <> 0 END
                            ORDER BY emp.unit_id,emp.division_id,emp.department_id,emp.employee_id,all_dates.datee;		
                        """   
            else:
                start_date = self.from_date.replace(day=1)
                end_date = self.from_date.replace(day=calendar.monthrange(self.from_date.year, self.from_date.month)[1])

                self.from_date = start_date
                self.to_date = end_date
                query =f""" 
                            WITH all_dates AS (
                                SELECT 
                                    date_trunc('day', dd)::date AS datee
                                FROM generate_series('{start_date.strftime("%Y-%m-%d")}'::timestamp,'{end_date.strftime("%Y-%m-%d")}'::timestamp,'1 day'::interval) AS dd
                            )	,
                            all_leaves AS (
                                SELECT 
                                    l_type.code as code,emp.id AS employee_id,emp.name,generate_series(date_from,date_to,'1 day'::interval)::date as leave_date 
                                FROM hr_leave AS leave
                                INNER JOIN hr_employee AS emp ON leave.employee_id = emp.id
                                INNER JOIN hr_leave_type AS l_type ON l_type.id = leave.holiday_status_id
                                WHERE
                                    CASE WHEN {unit_id[0]} <> 0 THEN emp.unit_id in ({','.join(map(str,unit_id))})  ELSE emp.id <> 0 END AND
                                    CASE WHEN {division_id[0]} <> 0 THEN emp.division_id in ({','.join(map(str,division_id))}) ELSE emp.id <> 0 END AND
                                    CASE WHEN {department_id[0]} <> 0 THEN emp.department_id in ({','.join(map(str,department_id))}) ELSE emp.id <> 0 END AND
                                    CASE WHEN {branch_id[0]} <> 0 THEN emp.branch_id in ({','.join(map(str,branch_id))}) ELSE emp.id <> 0 END AND
                                    leave.state not in ('draft','refuse')

                            )
                            SELECT 
                                emp.employee_id,emp.name as emp_name,unit.name as unit_name,div.name as div_name,dept.name as dept_name,branch.name as branch_name
                                ,CASE WHEN leave.code IS NOT NULL AND (att.check_in IS  NULL OR att.check_out IS NULL) THEN leave.code
                                    WHEN leave.code IS NULL AND (att.check_in IS NOT NULL OR att.check_out IS NOT NULL) THEN 
                                        j_location.name::text
                                    ELSE '-'
                                END AS dataa
                            FROM hr_employee AS emp
                            CROSS JOIN all_dates
                            LEFT JOIN hr_attendance AS att
                                ON att.employee_id = emp.id AND  DATE(att.check_in+'6:30') = all_dates.datee 
                            LEFT JOIN hr_job_location AS j_location
	                            ON att.job_location_id = j_location.id
                            LEFT JOIN hr_department AS unit
                                ON unit.id = emp.unit_id
                            LEFT JOIN hr_department AS div
                                ON div.id = emp.division_id
                            LEFT JOIN hr_department AS dept
                                ON dept.id = emp.department_id
                            LEFT JOIN hr_branch AS branch
                                ON branch.id = emp.branch_id
                            LEFT JOIN all_leaves AS leave
                                ON (leave.leave_date = DATE(all_dates.datee)) AND (leave.employee_id = emp.id)
                            WHERE
                                emp.active = true AND
                                CASE WHEN {unit_id[0]} <> 0 THEN emp.unit_id in ({','.join(map(str,unit_id))})  ELSE emp.id <> 0 END AND
                                CASE WHEN {division_id[0]} <> 0 THEN emp.division_id in ({','.join(map(str,division_id))}) ELSE emp.id <> 0 END AND
                                CASE WHEN {department_id[0]} <> 0 THEN emp.department_id in ({','.join(map(str,department_id))}) ELSE emp.id <> 0 END AND
                                CASE WHEN {branch_id[0]} <> 0 THEN emp.branch_id in ({','.join(map(str,branch_id))}) ELSE emp.id <> 0 END
                            ORDER BY emp.unit_id,emp.division_id,emp.department_id,emp.employee_id,all_dates.datee;		
                        """          
            
            range_dates = (self.to_date - self.from_date).days+1

            sheet.write(x_offset,0,(_("Employee Code")),header_format)
            sheet.write(x_offset,1,(_("Employee Name")),header_format)
            sheet.write(x_offset,2,(_("Unit")),header_format)
            sheet.write(x_offset,3,(_("Division")),header_format)
            sheet.write(x_offset,4,(_("Department")),header_format)
            sheet.write(x_offset,5,(_("Branch")),header_format)

            for i in range(range_dates):
                sheet.write(x_offset,i+6,(_((self.from_date+timedelta(days=i)).strftime("%B %d"))),header_format)

            x_offset+=1

            print(query)
            self.env.cr.execute(query)
            all_attendance_lines = self.env.cr.dictfetchall()            
            for i in range(0,len(all_attendance_lines),range_dates):
                attendance_lst = all_attendance_lines[i:i+range_dates]
                sheet.write(x_offset,0,attendance_lst[0].get('employee_id'), text_format)
                sheet.write(x_offset,1,attendance_lst[0].get('emp_name'),text_format)
                sheet.write(x_offset,2,attendance_lst[0].get('unit_name'),text_format)
                
                sheet.write(x_offset,3,attendance_lst[0].get('div_name'),text_format)
                sheet.write(x_offset,4,attendance_lst[0].get('dept_name'),text_format)
                sheet.write(x_offset,5,attendance_lst[0].get('branch_name'),text_format)
                for cnt,res in enumerate(attendance_lst):
                    sheet.write(x_offset,cnt+6,res.get('dataa'),text_format)  
                x_offset += 1  
        else:
            attendance_only =  " check_in IS NOT NULL AND " if self.report_type == 'attendance' else "  "
            query =f""" 
                        WITH all_dates AS (
                            SELECT date_trunc('day', dd)::date AS datee
                            FROM generate_series('{self.from_date.strftime("%Y-%m-%d")}'::timestamp,'{self.to_date.strftime("%Y-%m-%d")}'::timestamp,'1 day'::interval) AS dd
                        )	
                        SELECT 
                            emp.employee_id,emp.name as emp_name,unit.name as unit_name,div.name as div_name,dept.name as dept_name,branch.name as branch_name
                            ,DATE(all_dates.datee) as check_date,TO_CHAR(att.check_in+'6:30','HH24:MI:SS')::text as check_in_time,TO_CHAR(att.check_out+'6:30','HH24:MI:SS')::text as check_out_time,att.check_in_address,att.check_out_address,att.auto_checkout,0 as working_hours
                        FROM hr_employee AS emp
                        CROSS JOIN all_dates
                        LEFT JOIN hr_attendance AS att
                            ON att.employee_id = emp.id AND  DATE(att.check_in+'6:30') = all_dates.datee 
                        LEFT JOIN hr_department AS unit
                            ON unit.id = emp.unit_id
                        LEFT JOIN hr_department AS div
                            ON div.id = emp.division_id
                        LEFT JOIN hr_department AS dept
                            ON dept.id = emp.department_id
                        LEFT JOIN hr_branch AS branch
                            ON branch.id = emp.branch_id
                        WHERE
                            {attendance_only}
                            emp.active = true AND
                            CASE WHEN {unit_id[0]} <> 0 THEN emp.unit_id in ({','.join(map(str,unit_id))})  ELSE emp.id <> 0 END AND
                            CASE WHEN {division_id[0]} <> 0 THEN emp.division_id in ({','.join(map(str,division_id))}) ELSE emp.id <> 0 END AND
                            CASE WHEN {department_id[0]} <> 0 THEN emp.department_id in ({','.join(map(str,department_id))}) ELSE emp.id <> 0 END AND
                            CASE WHEN {branch_id[0]} <> 0 THEN emp.branch_id in ({','.join(map(str,branch_id))}) ELSE emp.id <> 0 END
                        ORDER BY all_dates.datee,emp.unit_id,emp.division_id,emp.department_id,emp.employee_id;
            """
            print(query)
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()

            sheet.write(x_offset,0,(_("Employee Code")),header_format)
            sheet.write(x_offset,1,(_("Employee Name")),header_format)
            sheet.write(x_offset,2,(_("Unit")),header_format)
            sheet.write(x_offset,3,(_("Division")),header_format)
            sheet.write(x_offset,4,(_("Department")),header_format)
            sheet.write(x_offset,5,(_("Branch")),header_format)
            sheet.write(x_offset,6,(_("Date")),header_format)
            sheet.write(x_offset,7,(_("Check In")),header_format)
            sheet.write(x_offset,8,(_("Check Out")),header_format)
            sheet.write(x_offset,9,(_("Check In Address")),header_format)
            sheet.write(x_offset,10,(_("Check Out Address")),header_format)
            sheet.write(x_offset,11,(_("Work Hours")),header_format)
            sheet.write(x_offset,12,(_("Auto CheckOut")),header_format)
            x_offset+=1

            for res in result:
                # print(res)
                sheet.write(x_offset,0,res.get('employee_id'), text_format)
                sheet.write(x_offset,1,res.get('emp_name'),text_format)
                sheet.write(x_offset,2,res.get('unit_name'),text_format)
                
                sheet.write(x_offset,3,res.get('div_name'),text_format)
                sheet.write(x_offset,4,res.get('dept_name'),text_format)
                sheet.write(x_offset,5,res.get('branch_name'),text_format)
                sheet.write(x_offset,6,res.get('check_date'),date_format)
                sheet.write(x_offset,7,res.get('check_in_time'),time_format)

                sheet.write(x_offset,8,res.get('check_out_time'),time_format)
                sheet.write(x_offset,9,res.get('check_in_address'),text_format)
                sheet.write(x_offset,10,res.get('check_out_address'),text_format)
                sheet.write(x_offset,11,res.get('working_hours'),text_format)
                sheet.write(x_offset,12,res.get('auto_checkout'),text_format)
                x_offset+=1     

        x_offset+=1   
        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=attendance.export.wizard&id=%s&file_name=%s' % (self.id, file_name),
            'target':'self',
        }               



# WITH all_dates AS (
#     SELECT date_trunc('day', dd)::date AS datee
#     FROM generate_series('2024-6-1'::timestamp,'2024-6-30'::timestamp,'1 day'::interval) AS dd
# )	,
# all_leaves AS (
# 	SELECT l_type.code,emp.id AS employee_id,emp.name,generate_series(date_from,date_to,'1 day'::interval)::date as leave_date 
# 	FROM hr_leave AS leave
# 	INNER JOIN hr_employee AS emp ON leave.employee_id = emp.id
# 	INNER JOIN hr_leave_type as l_type ON l_type.id = leave.holiday_status_id
# 	WHERE
# 	CASE WHEN 3 <> 0 THEN emp.unit_id = 3  ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.division_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.department_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.branch_id = 0 ELSE emp.id <> 0 END
# )
# SELECT 
#     emp.employee_id,emp.name as emp_name,DATE(all_dates.datee) as check_date
# 	,leave.code
# 	,TO_CHAR(att.check_in+'6:30','HH24:MI:SS')::text  || '<=>' ||TO_CHAR(att.check_out+'6:30','HH24:MI:SS')::text as timme
# FROM hr_employee AS emp
# CROSS JOIN all_dates
# LEFT JOIN hr_attendance AS att
#     ON att.employee_id = emp.id AND  DATE(att.check_in) = all_dates.datee 
# LEFT JOIN hr_department AS unit
#     ON unit.id = emp.unit_id
# LEFT JOIN hr_department AS div
#     ON div.id = emp.division_id
# LEFT JOIN hr_department AS dept
#     ON dept.id = emp.department_id
# LEFT JOIN hr_branch AS branch
#     ON branch.id = emp.branch_id
# LEFT JOIN all_leaves AS leave
# 	ON (leave.leave_date = DATE(all_dates.datee)) AND (leave.employee_id = emp.id)
# WHERE
#     CASE WHEN 3 <> 0 THEN emp.unit_id = 3  ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.division_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.department_id = 0 ELSE emp.id <> 0 END AND
#     CASE WHEN 0 <> 0 THEN emp.branch_id = 0 ELSE emp.id <> 0 END 
# ORDER BY emp.employee_id,all_dates.datee;					