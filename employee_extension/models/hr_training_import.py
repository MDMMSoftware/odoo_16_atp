from odoo import api, fields, models, _
from xlrd import open_workbook
from odoo.tools.translate import _
import base64
import logging
from datetime import datetime
from datetime import  datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

header_fields = ['description','course','training type','provided/non provided','trainer','training start date','training end date','total training hours','place','amount', 'employee id','employee name']

header_indexes = {}

class training(models.Model):
    _name = 'data_import.training'

    @api.model
    def get_today(self):
        my_date = (datetime.now()-timedelta(hours=6, minutes=30)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        return my_date

    name = fields.Char('Description', required=True)
    import_date = fields.Date('Import Date', readonly=True,default=get_today)
    import_fname = fields.Char('Filename', size=128, required=True)
    import_file = fields.Binary('File', required=True)
    note = fields.Text('Log')
    state = fields.Selection([('draft', 'Draft'),('completed', 'Completed'),('error', 'Error'),], 'States', default='draft')

    err_log = ''

    def _check_file_extension(self):
        for import_file in self.browse(self.ids):
            return import_file.import_fname.lower().endswith('.xls')  or import_file.import_fname.lower().endswith('.xlsx')


    _constraints = [(_check_file_extension, "Please import microsoft excel (.xlsx or .xls) file!", ['import_fname'])]


    # ## Load excel data file
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
    
    def floatHourToTime(self, fh):
        h, r = divmod(fh, 1)
        m, r = divmod(r*60, 1)
        return (
            int(h),
            int(m),
            int(r*60),
        )

    def get_headers(self, line):
        if line[0].strip().lower() not in header_fields:
            raise ValidationError("Error while processing the header line %s.\n\nPlease check your Excel separator as well as the column header fields" %line)
        else:
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
                err_log = ' '
                if header_indexes[header] < 0:                    
                    self.err_log += '\n' + _("Invalid Excel file, Header '%s' is missing !") % header

    def get_line_data(self, line):
        result = {}
        for header in header_fields:                        
            result[header] = line[header_indexes[header]].strip()


    def import_data(self):
        hr_training_obj = self.env['hr.training']
        training_type_obj = self.env['hr.training.type']
        hr_employee_obj = self.env['hr.employee']
        training_line_obj = self.env['hr.training.line']
        training_course_obj = self.env['hr.training.course']
        place_obj = self.env['hr.training.place']
    
        import_file = self.import_file

        header_line = True

        lines = base64.decodestring(import_file)
        wb = open_workbook(file_contents=lines)
        excel_rows = self.get_excel_datas(wb.sheets())
        all_data = []
        create_count = 0
        update_count = 0
        skipped_count = 0
        skipped_data = []
        for line in excel_rows:
            if not line or line and line[0] and line[0] in ['', '#']:
                continue
            if header_line:
                self.get_headers(line)
                header_line = False 

            elif line and line[0] and line[0] not in ['#', '']:
                import_vals = {}
                # ## Fill excel row data into list to import to database
                for header in header_fields:
                    import_vals[header] = line[header_indexes[header]]
                all_data.append(import_vals)

        if self.err_log:
            err = self.err_log
            self.write({'note': err,'state': 'error'})
        else:
            for data in all_data:
                course_id = type_id =  place_id = provided_type = None
                training_end_date =  train_record_id = None
                record_value = {}
                record_line_value = {}
                description = str(data['description']).strip()
                course_name = str(data['course']).strip()
                type_name = str(data['training type']).strip()
                provide = str(data['provided/non provided']).strip()
                if provide=='Provided':
                    provided_type ='porvided' 
                elif provide =='Non Provided':
                    provided_type = 'non_provided'

                trainer = str(data['trainer']).strip()
                training_start_date = str(data['training start date']).strip()
                if training_start_date:
                    excel_date = training_start_date
                    excel_date = float(excel_date)
                    dt_2 = datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(excel_date) - 2)
                    hour, minute, second = self.floatHourToTime(excel_date % 1)
                    start_date = dt_2.replace(hour=hour, minute=minute, second=second)
                else:
                    start_date = None
               
                training_end_date = str(data['training end date']).strip()
                if training_end_date:
                    excel_date = training_end_date
                    excel_date = float(excel_date)
                    dt_2 = datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(excel_date) - 2)
                    hour, minute, second = self.floatHourToTime(excel_date % 1)
                    end_date = dt_2.replace(hour=hour, minute=minute, second=second)
                else:
                    end_date = None

                time = str(int(data['total training hours'])).strip()
                place_name = str(data['place']).strip()
                amount = str(data['amount']).strip()
                
                employee_id = str(data['employee id']).strip()
                employee_name = str(data['employee name']).strip()

                
                if course_name:
                    course_ids = training_course_obj.search([('name','=',course_name)])
                    if course_ids:
                        course_id = course_ids.id
                    else:
                        course_id=training_course_obj.create({'name': course_name}).id
                else:
                    course_id = None

                if type_name:
                    type_ids = training_type_obj.search([('name','=',type_name)])
                    if type_ids:
                        type_id = type_ids.id
                    else:
                        type_id=training_type_obj.create({'name': type_name}).id
                else:
                    type_id = None
                
                if place_name:
                    place_ids = place_obj.search([('name', '=', place_name)])
                    if place_ids:
                        place_id = place_ids.id
                    else:
                        place_id=place_obj.create({'name': place_name}).id
                else:
                    place_id = None

                if employee_name: 
                    emp_ids = hr_employee_obj.search([('name', '=', employee_name),('employee_id','=',employee_id)])                  
                    if emp_ids:
                        emp_id = emp_ids[0]
                        train_record_ids = hr_training_obj.search([('course','=',course_id),('date_start','=',start_date),('date_end','=',end_date),('amt','=',amount),('provided_type','=',provided_type)])  
                        if not train_record_ids:
                            record_value = {
                                'name': description,
                                'course': course_id, 
                                'type': type_id,
                                'provided_type': provided_type,
                                'responsible': trainer,
                                'date_start': start_date,
                                'date_end': end_date,
                                'total_time': time,
                                'place': place_id,
                                'amt': amount
                                
                            }
                            train_record_id = hr_training_obj.create(record_value)
                            train_record_id = train_record_id.id
                            create_count += 1
                        else:
                            train_record_id = train_record_ids[0].id

                if train_record_id:
                    train_record_line_ids = training_line_obj.search([('record_id','=',train_record_id),('employee_id','=',emp_id.id)]) 
                    if not train_record_line_ids:
                        record_line_value = {
                                                'total_time': time,
                                                'responsible': trainer,
                                                'date_start': start_date,
                                                'date_end': end_date,
                                                'course': course_id,
                                                'place': place_id,
                                                'employee_id': emp_id.id,
                                                'record_id': train_record_id,
                                                'type': type_id,
                                                'amt': amount
                                        }
                        train_record_line_id = training_line_obj.create(record_line_value)
                        training_line_obj.write(train_record_line_id)
                    
                        sql = "SELECT hr_training_id,hr_employee_id FROM hr_employee_hr_training_rel WHERE hr_training_id=%s and hr_employee_id=%s"
                        self.env.cr.execute(sql,(train_record_id,emp_id.id))
                        record = self.env.cr.fetchall()
                        rec_id = len(record)
                        if not rec_id:
                            sql = "insert into hr_employee_hr_training_rel (hr_training_id,hr_employee_id) values (%s,%s)"
                            self.env.cr.execute(sql,(train_record_id,emp_id.id))
                        create_count += 1
                    else:
                        record_line_value = {
                                                'total_time': time,
                                                'responsible': trainer,
                                                'date_start': start_date,
                                                'date_end': end_date,
                                                'course': course_id,
                                                'place': place_id,
                                                'employee_id': emp_id.id,
                                                'record_id': train_record_id,
                                                'type': type_id,
                                                'amt': amount
                                        }
                        training_line_obj.write(record_line_value)
                        training_line_obj.write(train_record_line_ids[0])
                        training_line_obj.write({'record_id': train_record_id})
                        sql = "SELECT hr_training_id,hr_employee_id FROM hr_employee_hr_training_rel WHERE hr_training_id=%s and hr_employee_id=%s"
                        self.env.cr.execute(sql,(train_record_id,emp_id.id))
                        record = self.env.cr.fetchall()
                        rec_id = len(record)
                        if not rec_id:
                            sql = "insert into hr_employee_hr_training_rel (hr_training_id,hr_employee_id) values (%s,%s)"
                            self.env.cr.execute(sql,(train_record_id,emp_id.id))
                        update_count += 1              
                          
                skipped_data_str = ''
                for sk in skipped_data:
                    skipped_data_str += str(sk) + ','
                message = 'Import Success at ' + str(datetime.strptime(datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                          '%Y-%m-%d %H:%M:%S'))+ '\n' + str(len(all_data))+' records imported' +'\
                          \n' + str(create_count) + ' created\n' + str(update_count) + ' updated' + '\
                          \n' + str(skipped_count) + 'skipped' + '\
                          \n\n' + skipped_data_str
                          
                self.write({'state': 'completed','note': message})



                       


                


              