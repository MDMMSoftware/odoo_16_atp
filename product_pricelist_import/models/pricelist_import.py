# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import datetime
from dateutil.relativedelta import relativedelta
import base64
# from xlrd import open_workbook
import xlrd
from datetime import datetime
import collections


class PricelistImport(models.Model):
    _name = "pricelist.import"

    date = fields.Date(default=datetime.now().date(),required=True)
    import_file = fields.Binary("Import File",required=True)
    status = fields.Selection([('not_import','Not Import'),('import','Imported')],string="Status",readonly=True,default='not_import')
    import_id = fields.Many2one('product.pricelist')

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

    def import_pricelist(self):
        lines = base64.b64decode(self.import_file or b'')
        wb = xlrd.open_workbook(file_contents=lines)
        excel_rows = self.get_excel_datas(wb.sheets())
        header = excel_rows[0]
        all_data = []
        for row in excel_rows:
            if row!= header:
                import_vals = {}
                if row[0] and row[1] and row[2] and row[3] and row[4]:
                    import_vals['product'] = row[0]
                    import_vals['qty'] = row[1]
                    import_vals['price'] = row[2]
                    import_vals['start_date'] = row[3]
                    import_vals['end_date'] = row[4]
                

                    all_data.append(import_vals)
        
        product_code_arr = []
        for data in all_data:
            
            if type(data['start_date'])==float:
                data['start_date']=xlrd.xldate_as_datetime(data['start_date'], 0) 
            if type(data['start_date'])==str:
                data['start_date']=datetime.strptime(data['start_date'],"%d/%b/%Y %H:%M:%S")
            if type(data['end_date'])==float:
                data['end_date']=xlrd.xldate_as_datetime(data['end_date'], 0) 
            if type(data['end_date'])==str:
                data['end_date']=datetime.strptime(data['end_date'],"%d/%b/%Y %H:%M:%S")
            if data['product'] in  product_code_arr:
                raise UserError(_("Duplicate Record for Product %s")%data['product'])
            
            existing = self.import_id.item_ids.filtered(lambda x:x.product_tmpl_id.product_code==data['product'])
            if existing:
                existing.write({
                    'min_quantity':data['qty'],
                    'fixed_price':data['price'],
                    'date_start':data['start_date'],
                    'date_end':data['end_date']
                })
            else:
                existing_prod = self.env['product.template'].search([('product_code','=',data['product']), ('company_id','=',self.import_id.company_id.id)])
                if existing_prod:
                    if len(existing_prod) > 1:
                        raise UserError(f"Found Multiple Products in the company of {self.import_id.company_id.name} with the product_code - {data['product']} ")
                    self.import_id.write({'item_ids':[[0 ,0 ,{
                        'product_tmpl_id':existing_prod.id,
                        'min_quantity':data['qty'],
                        'fixed_price':data['price'],
                        'date_start':data['start_date'],
                        'date_end':data['end_date']
                    }]]})
                else:
                    raise UserError(_("There is no product code %s in this system")%data['product'])

            product_code_arr.append(data['product'])

        self.status = 'import'
            
 
                

class Pricelist(models.Model):
    _inherit = "product.pricelist"

    import_ids = fields.One2many("pricelist.import",'import_id',string="Pricelist Import")

 
