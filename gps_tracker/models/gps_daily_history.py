from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import xlrd
import codecs
from xlrd import open_workbook
from odoo.tools.translate import _
from datetime import datetime,timedelta, date ,time
import base64
import logging
from passlib.tests.backports import skip
from odoo.exceptions import UserError,ValidationError
_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError

header_fields = ['date','machine name','gps','fuel','gps engine hr',
                'gps fuel filled (liter)','gps total fuel usage (liter)','gps total trip (km)','gps fuel drain (litres)','gps status','platform']

def float_to_time(time):
    result = '{0:02.0f}:{1:02.0f}'.format(*divmod(time * 60, 60))
    return result+":00"



def change_time_strTofloat(time_str):
    if time_str!='-':
        h , m , s = time_str.strip().split(":")
        return int(h) + round(int(m)/60, 2) +round(int(s)/3600, 2)
    else:
        return 0

header_indexes = {}
class GPSDailyHistory(models.Model):
    _name = 'gps.daily.history'
    _description = "GPS Daily History"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name',tracking=True)
    date = fields.Date(required=True,string="Date",tracking=True)
    fleet = fields.Many2one('fleet.vehicle',required=True,string="Fleet",tracking=True)
    gps = fields.Boolean(default=False,string="GPS",tracking=True)
    fuel = fields.Boolean(default=False,string="Fuel",tracking=True)
    gps_engine_hr = fields.Char("GPS Engine HR",required=True,tracking=True)
    gps_fuel_filled = fields.Float("GPS Fuel Filled (Liter)",required=True,tracking=True)
    gps_fuel_usage = fields.Float("GPS Total Fuel Usage (Liter)",required=True,tracking=True)
    gps_trip = fields.Float("GPS Total Trip (km)",required=True,tracking=True)
    gps_status = fields.Char("GPS Status",tracking=True)
    gps_fuel_drain = fields.Float("GPS Fuel Drain (Litres)",required=True,tracking=True)
    platform = fields.Selection([
        ('tanz', 'Tanz'),
        ('compumatics', 'Compumatics'),
        ('netpro', 'Netpro'),
        ('none of platform', 'None of Platform'),
    ], required=True,tracking=True)
   

class ImportGPSData(models.Model):
    _name = 'import.gps.data'
    _description = "GPS Data Import File"

    name = fields.Char(string='Description')
    import_date = fields.Date(string='Import Date', readonly=True, default=fields.Date.today())
    import_fname = fields.Char(string='Filename')
    import_file = fields.Binary(string='File', required=True)
    note = fields.Text(string='Log')
    state = fields.Selection([('draft', 'Draft'),('completed', 'Completed'),('error', 'Error')], string='States', default='draft')
    err_log = fields.Text(string='Error Log')

    def _check_file_ext(self):
        for import_file in self.browse(self.ids):
            if '.xls' or '.xlsx' in import_file.import_fname:return True
            else: return False
        return True
    
    _constraints = [(_check_file_ext, "Please import EXCEL file!", ['import_fname'])]


    def get_excel_datas(self, sheets):
        result = []
        for s in sheets:
            # # header row
            headers = []
            header_row = 0
            for hcol in range(0, s.ncols):
                headers.append(s.cell(header_row, hcol).value)
                            
            result.append(headers)
            
            # # value rows
            for row in range(header_row + 1, s.nrows):
                values = []
                for col in range(0, s.ncols):
                    values.append(s.cell(row, col).value)
                result.append(values)
        return result

    def get_headers(self, line):
        self.err_log = ''
        if line[0].strip().lower() not in header_fields:
                    raise ValidationError(_("Error while processing the header line %s.\
                     \n\nPlease check your Excel separator as well as the column header fields") % line)
        else:
            # ## set header_fields to header_index with value -1
            for header in header_fields:
                header_indexes[header] = -1  
                     
            col_count = 0
            for ind in range(len(line)):
                if line[ind] == '':
                    col_count = ind
                    break
                elif ind == len(line) - 1:
                    col_count = ind + 1
                    break
            
            for i in range(col_count):                
                header = line[i].strip().lower()
                if header not in header_fields:
                    self.err_log += '\n' + _("Invalid Excel File, Header Field '%s' is not supported !") % header
                else:
                    header_indexes[header] = i
                                
            for header in header_fields:
                if header_indexes[header] < 0:                    
                    self.err_log += '\n' + _("Invalid Excel file, Header '%s' is missing !") % header


    def import_data(self):
        
        import_file = self.import_file

        header_line = True
        lines = base64.decodebytes(import_file)
        wb = open_workbook(file_contents=lines)
        excel_rows = self.get_excel_datas(wb.sheets())        
        value = {}
        all_data = []
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for line in excel_rows:
            if not line or line and line[0] and line[0] in ['', '#']:
                continue            
            if header_line:
                self.get_headers(line)
                header_line = False                           
            elif line and line[0] and line[0] not in ['#', '']:
                import_vals = {}                
                for header in header_fields:    
                    import_vals[header] = line[header_indexes[header]]              
                all_data.append(import_vals)

        if self.err_log != '':
            err = self.err_log          
            self.write({'note': err,'state': 'error'})

        else:
            for data in all_data:
                vals={}
                fleet = self.env['fleet.vehicle'].search([('name','=',data['machine name'])])
                if not fleet:
                    raise ValidationError(('Need to add Machine Name in Odoo %s')% data['machine name'])
                # project_code_id = self.env['analytic.project.code'].search([('name','=',data['gps location'])],order='id desc',limit=1)
                # if not project_code_id:
                #     raise ValidationError('Need to add GPS Location %s in Odoo'%data['gps location'])
                if data['gps engine hr']!='-':
                    # date_values = xlrd.xldate_as_tuple(data['gps engine hr'], wb.datemode)  
                    # time_value = time(*date_values[3:])
                    time_value = datetime.strptime(data['gps engine hr'],"%H:%M:%S")
                vals= {
                        'date':datetime(*xlrd.xldate_as_tuple(data['date'], 0)).date(),
                        'fleet':fleet.id,
                        # 'project_code_id':project_code_id.id,
                        # 'project_name':project_code_id.name,
                        'gps':data['gps']==1 and True or False,
                        'fuel':data['fuel']==1 and True or False,
                        # 'service_meter':data['service meter']!='-' and data['service meter'] or 0 ,
                        'gps_engine_hr':data['gps engine hr']!='-' and time_value.strftime("%H:%M:%S") or '-',
                        'gps_fuel_filled':data['gps fuel filled (liter)']!='-' and data['gps fuel filled (liter)'] or 0,
                        'gps_fuel_usage':data['gps total fuel usage (liter)']!='-' and data['gps total fuel usage (liter)'] or 0,
                        'gps_trip':data['gps total trip (km)']!='-' and data['gps total trip (km)'] or 0,
                        'gps_status':data['gps status'],
                        'gps_fuel_drain':data['gps fuel drain (litres)']!='-' and data['gps fuel drain (litres)'] or 0,
                        'platform':data['platform'] and data['platform'].lower() or 'none',
                    }
                if vals:
                    self.env['gps.daily.history'].create(vals)            
                    created_count += 1
                else:
                    updated_count += 1

            message = 'Import Success at ' + str(datetime.strptime(datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                    '%Y-%m-%d %H:%M:%S'))+ '\n' + str(len(all_data))+' records imported' +'\
                    \n' + str(created_count) + ' Created'+'\
                    \n' + str(updated_count) + ' Updated'

            self.write({'state': 'completed','note': message})

class DailyGPSReport(models.TransientModel):
    _name = 'daily.gps.report'
    _description = "Daily GPS Report"

    date = fields.Date(string="Start Date",required=True)
    end_date = fields.Date(string="End Date",required=True)

    # def action_submit(self):
    #     gps = self.env['gps.daily.history'].search([('date','=',self.date)])
    #     odoo = self.env['duty.process.line'].search([('date','=',self.date)])
    #     if gps:
    #         return self.env.ref('gps_tracker.action_report_daily_gps').report_action(gps[0])
    #     if odoo:
    #         return self.env.ref('gps_tracker.action_report_daily_duty_odoo').report_action(odoo[0])
    #     if not (gps and odoo):
    #         raise ValidationError(_("There is no data for GPS and Odoo System on %s")% self.date.strftime("%d-%B-%Y"))
        
    def action_submit_excel(self): 
        return self.env.ref("gps_tracker.export_report_xlsx").report_action(self,data={"date":self.date,"end_date":self.end_date})


class ExcelWizardDutyReport(models.AbstractModel):
    _name = 'report.gps_tracker.export_report_xls'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, partners):
        sheet = workbook.add_worksheet("Comparison Report")
        danger_color = workbook.add_format({'bg_color': 'red'})

        header = ['Date','Machine Name','Location','GPS','Fuel','Service Meter','GPS Engine Hour','Ground Engine Hour','Engine Hr Discrepancy','GPS Fuel Filled (Litre)','Ground Fuel Filled (Litre)','Fuel Discrepancy','GPS Fuel Total Usage (Litre)','Ground Fuel Total Usage (Litre)','Fuel Usage Discrepancy','GPS Total Trip (km)','GPS Fuel Drain(Litre)','GPS Status','Platform','Filling No.','Duty Remark']

        query = """ 
                    select 
                        b.date as x_date,b.fleet as x_fleet,b.x_location,COALESCE(b.x_gps,'-') as x_gps,COALESCE(b.x_fuel,'-') as x_fuel,b.x_service_meter,b.x_gps_engine_hr_time,COALESCE(b.x_gps_engine_hr,'-') as x_gps_engine_hr
                        ,COALESCE(b.x_odoo_engine_hr::TEXT,'-') as x_odoo_engine_hr,
                            (
                            CASE 
                                WHEN b.x_gps_engine_hr_time is NULL THEN b.x_odoo_engine_hr::interval
                                WHEN b.x_odoo_engine_hr is NULL THEN b.x_gps_engine_hr_time::interval
                                ELSE 
                                    (CASE WHEN b.x_gps_engine_hr_time-b.x_odoo_engine_hr>'00:00:00' 
                                        THEN b.x_gps_engine_hr_time-b.x_odoo_engine_hr
                                        ELSE b.x_odoo_engine_hr-b.x_gps_engine_hr_time 
                                    END) 
                            END)::time AS x_diff_engine_hr,b.x_gps_fuel_filled,
                        b.x_odoo_fuel_filled,round(abs(b.x_gps_fuel_filled-b.x_odoo_fuel_filled)::numeric,2) as x_diff_fuel_filled,b.x_gps_fuel_usage,round(b.x_odoo_fuel_uasge::numeric,2) as x_odoo_fuel_uasge,
                        ROUND(
                            CASE
                                WHEN b.x_gps_fuel_usage = 0 AND b.x_odoo_fuel_uasge <> 0 THEN b.x_odoo_fuel_uasge
                                WHEN b.x_gps_fuel_usage <> 0 AND b.x_odoo_fuel_uasge = 0 THEN b.x_gps_fuel_usage
                                ELSE b.x_gps_fuel_usage - b.x_odoo_fuel_uasge
                            END::numeric,2
                            ) AS diff_fuel_usage,
                        b.x_gps_trip, b.x_gps_fuel_drain,COALESCE(b.x_gps_status,'-') as x_gps_status,COALESCE(b.x_platform,'-') AS x_platform,b.filling_no,b.duty_remark
                    from 
                        (
                            select 
                                a.id,a.date as date,a.name as fleet,max(a.project) x_location,
                                CASE 
                                    WHEN max(a.gps::varchar) = 'true' THEN '1'  
                                    WHEN max(a.gps::varchar) = 'false' THEN '0'
                                    ELSE max(a.gps::varchar) 
                                END as x_gps,
                                CASE 
                                    WHEN max(a.fuel::varchar) = 'true' THEN '1'
                                    WHEN max(a.fuel::varchar) = 'false' THEN '0'
                                    ELSE max(a.fuel::varchar)
                                END as x_fuel,
                                COALESCE(sum(a.service_meter),0) as x_service_meter,max(a.gps_engine_hr) as x_gps_engine_hr,max(a.gps_engine_hr_time) as x_gps_engine_hr_time,
                                max(a.odoo_engine_hr) as x_odoo_engine_hr,max(a.gps_fuel_filled) as x_gps_fuel_filled,max(a.odoo_fuel_filled) as x_odoo_fuel_filled, max(a.gps_fuel_usage) as x_gps_fuel_usage,
                                max(a.odoo_fuel_uasge) as x_odoo_fuel_uasge,max(a.gps_trip) as x_gps_trip,max(a.gps_fuel_drain) as x_gps_fuel_drain,max(a.gps_status) as x_gps_status,max(a.platform) as x_platform,
                                max(a.filling_no) as filling_no,max(a.duty_remark) AS duty_remark
                            from 
                                ( 
                                    select 
                                        fv.id,dpl.date,fv.name,array_to_string(ARRAY_AGG(DISTINCT apc.name),',') as project,NULL as gps,NULL as fuel,COALESCE(sum(dpl.service_meter),0) as service_meter,NULL as gps_engine_hr,NULL as gps_engine_hr_time,
                                        ((CAST(sum(dpl.run_hr) * 3600 AS INTEGER) || ' second')::interval)::TIME AS odoo_engine_hr,0 as gps_fuel_filled,COALESCE(sum(dpl.fill_fuel),0) as odoo_fuel_filled,0 as gps_fuel_usage,
                                        COALESCE(sum(dpl.total_use_fuel),0) as odoo_fuel_uasge,0 as gps_trip,0 as gps_fuel_drain,NULL as gps_status,NULL as platform,array_to_string(ARRAY_AGG(DISTINCT dffn.name),',') as filling_no,
                                        array_to_string(ARRAY_AGG(DISTINCT remark.name),',') as duty_remark
                                    from fleet_vehicle fv
                                        LEFT JOIN duty_process dp on dp.machine_id=fv.id
                                        LEFT JOIN duty_process_line dpl on dpl.duty_id = dp.id
                                        LEFT JOIN analytic_project_code apc on apc.id= dpl.project_id
                                        LEFT JOIN duty_fuel_filling_no dffn on dffn.id = dpl.transport_distance
                                        LEFT JOIN report_remark remark on remark.id = dpl.report_remark_id
                                    where  dpl.date BETWEEN %s AND %s
                                        group by fv.id,dpl.date,fv.name

                                UNION ALL 

                                    select 
                                        fv.id,gps_history.date,fv.name,NULL,gps_history.gps,gps_history.fuel,0,gps_history.gps_engine_hr,CASE WHEN gps_history.gps_engine_hr<>'-' then TO_TIMESTAMP(gps_history.gps_engine_hr,'HH24:MI:SS')::time
                                        else '00:00:00'::time end as gps_engine_hr_time,NULL as odoo_engine_hr,gps_history.gps_fuel_filled as gps_fuel_filled,0 as odoo_fuel_filled,gps_history.gps_fuel_usage,
                                        0 as odoo_fuel_uasge,gps_history.gps_trip,gps_history.gps_fuel_drain,gps_history.gps_status,gps_history.platform,NULL as filling_no,NULL as duty_remark
                                    from fleet_vehicle fv
                                        LEFT JOIN gps_daily_history gps_history on gps_history.fleet=fv.id
                                    where gps_history.date BETWEEN %s AND %s
                                )	a 
                            GROUP BY a.id,a.date,a.name
                            ORDER BY a.date,a.name
                    ) b
					
        """
		# Write the header row
        sheet.write_row(0,0, header)
        self.env.cr.execute(query,(data['date'],data['end_date'],data['date'],data['end_date']))
        datas = self.env.cr.fetchall()
        for idx,data in enumerate(datas,start=1):
            dt = list(data)
            dt[0] = dt[0].strftime("%d-%m-%Y")
            del dt[6]   
            diff_time = dt[8] 
            dt[8] = '-' if diff_time is None else f"{diff_time.hour:02}:{diff_time.minute:02}:{diff_time.second:02}"    
            if diff_time is None:
                dt[8] = '-'
            if dt[11] is None:
                dt[11] = '-'
            sheet.write_row(idx,0,dt)  
            # if dt[8] != '-' and diff_time.hour > 0:
            if dt[8] != '-' and (diff_time.minute > 30 or diff_time.hour > 0):
                sheet.write(idx,8,dt[8],danger_color)   
            if dt[11] != '-'and dt[11] > 5:
                sheet.write(idx,11,dt[11],danger_color)
            if dt[14] > 5:
                sheet.write(idx,14,dt[14],danger_color)



class DrainedDataInfo(models.Model):
    _name = 'drain.info'
    _description = "Drained Data Info"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    ref = fields.Char(string='Reference',tracking=True)
    date = fields.Date(required=True,string="Date",tracking=True)
    time_widget = fields.Float(required=True,string="Time",tracking=True)
    vehicle_no = fields.Many2one('fleet.vehicle', string="Vehicle No",required=True,tracking=True)
    type = fields.Selection([('drain','Drain'),('other','Other')])
    fuel_drain = fields.Float("Drained Litres",required=True,tracking=True)
    remark = fields.Char("Remark",tracking=True)
    
    
    @api.constrains('fuel_drain')
    def _check_fuel_drain(self):
        for rec in self:
            if rec.type == 'drain' and rec.fuel_drain <= 0:
                raise ValidationError('Fuel Drain Litre be greater than 0 litre!!')
                
