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

header_fields = ['balance','location','code','date','price','sequence']
header_indexes = {}

class OTImport(models.Model):
    _name = 'req.import'

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

    err_log = fields.Char()

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
                self.err_log = ''
                if header_indexes[header] < 0:                    
                    self.err_log += '\n' + _("Invalid Excel file, Header '%s' is missing !") % header

    def get_line_data(self, line):
        result = {}
        for header in header_fields:                        
            result[header] = line[header_indexes[header]].strip()
            
    def _get_overtime_years(self):
        current_year = datetime.now().year
        return [str(current_year - 1), str(current_year), str(current_year + 1)]


    def import_data(self):
        
        import_file = self.import_file

        header_line = True

        lines = base64.decodebytes(import_file)
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
            requisition = self.env['requisition'].search([('name','in',('AMG/REQ/000015',
                'AMG/REQ/000016',
                'AMG/REQ/000017',
                'BYN/REQ/000171',
                'BYN/REQ/000178',
                'BYN/REQ/000181',
                'BYN/REQ/000183',
                'BYN/REQ/000186',
                'BYN/REQ/000189',
                'BYN/REQ/000190',
                'BYN/REQ/000192',
                'BYN/REQ/000196',
                'BYN/REQ/000197',
                'BYN/REQ/000216',
                'BYN/REQ/000217',
                'BYN/REQ/000218',
                'BYN/REQ/000219',
                'BYN/REQ/000220',
                'BYN/REQ/000221',
                'BYN/REQ/000223',
                'BYN/REQ/000224',
                'MDY/REQ/000020',
                'MY/REQ/000018',
                'NPT/REQ/000006',
                'SPT/REQ/000251',
                'SPT/REQ/000257',
                'SPT/REQ/000260',
                'SPT/REQ/000264',
                'SPT/REQ/000265',
                'SPT/REQ/000266',
                'SPT/REQ/000268',
                'SPT/REQ/000282',
                'SPT/REQ/000286',
                'SPT/REQ/000287',
                'SPT/REQ/000289',
                'SPT/REQ/000291',
                'SPT/REQ/000292',
                'SPT/REQ/000293',
                'SPT/REQ/000294',
                'SPT/REQ/000295',
                'SPT/REQ/000296',
                'SPT/REQ/000297',
                'SPT/REQ/000299',
                'TGI/REQ/000015',
                'TGI/REQ/000017',
                'TGI/REQ/000018',
                'TGI/REQ/000020',
                'TWN/REQ/000003',
                'TWN/REQ/000010',
                'TWN/REQ/000012',
                'TWN/REQ/000013',
                'TWN/REQ/000014',
                'TWN/REQ/000020',
                'TWN/REQ/000021'))])
            valuation = self.env['stock.valuation.layer']
            report =  self.env['stock.location.valuation.report']
            for req in requisition:
                req_picking = req.picking_ids.filtered(lambda x:x.location_id.usage!='transit' and x.state=='done')
                for req_move in req_picking.move_ids:
                    cost = req_move.product_id.warehouse_valuation.filtered(lambda x:x.location_id==req_move.location_id).location_cost or 0
                    valuations = valuation.search([('stock_move_id','=',req_move.id)])
                    for val in valuations:
                        val.write({'unit_cost':cost,'value':cost*val.quantity})
                    
            # for data in all_data:
                # record_value = {}
                # record_line_value = {}
                
                # overtime_date = str(data['date']).strip()
                # if overtime_date:
                #     excel_date = overtime_date
                #     excel_date = float(excel_date)
                #     dt_2 = datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(excel_date) - 2)
                #     hour, minute, second = self.floatHourToTime(excel_date % 1)
                #     overtime_date = dt_2.replace(hour=hour, minute=minute, second=second)
                # else:
                #     overtime_date = None
                # balance = str(data['balance']).strip()
                # location = str(data['location']).strip()
                # code = str(data['code']).strip()
                # price = str(data['price']).strip()
                # sequence = str(data['sequence']).strip()
                # valuation = self.env['stock.valuation.layer']
                # report =  self.env['stock.location.valuation.report']
                
                # if code: 
                #     product = self.env['product.template'].search([('product_code','=',code)])
                #     if product:
                #         requisition = self.env['requisition'].search([('name','=',sequence)])
                #         req_location = (requisition.location_id+requisition.src_location_id).ids
                #         # if not report.search([('report_date','>',overtime_date.date()),('product_id','=',product.product_variant_id.id),'|',('location_id','in',req_location),('location_dest_id','in',req_location)]):
                #         if requisition:
                #             move_ids = requisition.picking_ids.move_ids.filtered(lambda x:x.product_id==product.product_variant_id and not x.origin_returned_move_id)
                #             valuations=valuation.search([('stock_move_id','in',move_ids.ids)])
                #             location_ids = valuations.location_id.filtered(lambda x:x.usage=='transit')
                #             neg_valuation = valuations.filtered(lambda x:x.location_id==location_ids and x.quantity<0)
                #             pos_valuation = valuations.filtered(lambda x:x.location_id==location_ids and x.quantity>0)
                #             if len(neg_valuation)>1 or len(pos_valuation)>1:
                #                 skipped_data.append(requisition.name+code)
                #                 skipped_count +=1
                #             else:
                #                 neg_valuation_dec = valuations.filtered(lambda x:x.location_dest_id==location_ids and x.quantity<0)
                #                 pos_valuation_dec = valuations.filtered(lambda x:x.location_dest_id==location_ids and x.quantity>0)
                #                 pos_valuation.write({'unit_cost':neg_valuation.unit_cost,'value':-1*neg_valuation.value})
                #                 neg_valuation_dec.write({'unit_cost':pos_valuation_dec.unit_cost,'value':-1*pos_valuation_dec.value})
                #                 # product.product_variant_id.warehouse_valuation.filtered(lambda x:x.location_id==neg_valuation_dec.location_id).write({'location_cost':pos_valuation_dec.unit_cost})
                #                 valuations_report=report.search([('stock_move_id','in',move_ids.ids)])
                #                 location_ids = valuations_report.location_id.filtered(lambda x:x.usage=='transit')
                #                 neg_valuation_report = valuations_report.filtered(lambda x:x.location_id==location_ids and x.balance<0)
                #                 pos_valuation_report = valuations_report.filtered(lambda x:x.location_id==location_ids and x.balance>0)
                #                 neg_valuation_dec_report = valuations_report.filtered(lambda x:x.location_dest_id==location_ids and x.balance<0)
                #                 pos_valuation_dec_report = valuations_report.filtered(lambda x:x.location_dest_id==location_ids and x.balance>0)
                #                 pos_valuation_report.write({'unit_cost':neg_valuation_report.unit_cost,'total_amt':-1*neg_valuation_report.total_amt})
                #                 neg_valuation_dec_report.write({'unit_cost':pos_valuation_dec_report.unit_cost,'total_amt':-1*pos_valuation_dec_report.total_amt})
                #                 pos_valuation.account_move_id.button_draft()
                #                 for line in pos_valuation.account_move_id.line_ids:
                #                     if line.credit:
                #                         query = """
                #                             UPDATE account_move_line
                #                                 SET credit = %s where id IN %s
                #                         """
                #                         self.env.cr.execute(query, [pos_valuation.value,tuple(line.ids)])
                #                     if line.debit:
                #                         query = """
                #                             UPDATE account_move_line
                #                                 SET debit = %s where id IN %s
                #                         """
                #                         self.env.cr.execute(query, [pos_valuation.value,tuple(line.ids)])
                #                 pos_valuation.account_move_id.action_post()
                                
                #                 update_count += 1  
                            
                #                 print("Helo",create_count)
                #     else:
                #         skipped_data.append(requisition.name+' '+code)
                #         skipped_count +=1
                        
                # else:
                #     raise ValidationError(_("Code %s doesn't exist")%code)    
                    
                create_count +=1        
                          
                skipped_data_str = ''
                for sk in skipped_data:
                    skipped_data_str += str(sk) + ','+'\n'
                message = 'Import Success at ' + str(datetime.strptime(datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
                          '%Y-%m-%d %H:%M:%S'))+ '\n' + str(len(all_data))+' records imported' +'\
                          \n' + str(create_count) + ' created\n' + str(update_count) + ' updated' + '\
                          \n' + str(skipped_count) + 'skipped' + '\
                          \n\n' + skipped_data_str
                          
                self.write({'state': 'completed','note': message})



                       


                


              