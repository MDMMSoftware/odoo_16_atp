from odoo import models, api, fields, _
import logging
import os
import tempfile
_logger = logging.getLogger(__name__)

import io

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    # TODO saas-17: remove the try/except to directly import from misc
    import xlsxwriter

class StockLedgerReport(models.TransientModel):
    _name = 'stock.ledger.report'

    company_id = fields.Many2one('res.company', string='Company',default=lambda self:self.env.company,required=True)
    location_id = fields.Many2one('stock.location', string='Location',required=True)
    start_date = fields.Date('Beginning Date', required=True, default=fields.Date.context_today)
    end_date = fields.Date('End Date', required=True, default=fields.Date.context_today)
    filter_product_ids = fields.Many2many('product.product', string='Products')
    display_all_products = fields.Boolean('Display All Products?', help="True, if you want to display all products without filter.", default=False)
    detailed_type = fields.Selection(string="Product Type",selection=[('consu','Consuable'),('product','Storable'),('product,consu','All')],default="product")
   
    @api.onchange('company_id')
    def onchange_location_id(self):
        locations = self.env['stock.location'].search([('company_id','=',self.company_id.id)])
        return {'domain': {'location_ids': [('id', 'in', locations.ids),('usage','=','internal')]}}
        
    def print_report(self):
        output = io.BytesIO()
        file_name = os.path.join(tempfile.gettempdir(), 'Stock Ledger Report.xlsx')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Stock Ledger Report")
        banner_format_small = workbook.add_format({'font_name': 'Arial','font_size':20,'bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})

        report_by = "location"
        header_width = 6
        product_ids=None
        first_table_headers = ["Branch","Date","Reference","Type","By Location","From Locataion","To Location","Code","Product Name","UOM","Price","Opening Qty","In Qty","Out Qty","Balance Qty","Amount","Balance Amt"]
        if self.display_all_products or (not self.display_all_products and not self.filter_product_ids):
            product_ids = self.env['product.product'].search([('detailed_type','in',self.detailed_type.split(","))]).ids
        else:
            product_ids = self.filter_product_ids.filtered(lambda x:x.detailed_type in self.detailed_type.split(",")).ids
        
        for i in range(8):
            if i == 0:
                sheet.set_column(i, i, 40)
            else:
                sheet.set_column(i, i, 15)
        y_offset = header_width - 1
        x_offset = 3

        
        sheet.merge_range(0,0,x_offset,y_offset, _("Stock Ledger Report"), banner_format_small)
        x_offset+=1
        sheet.write(x_offset,0,(_("Company")),header_format)
        sheet.write(x_offset,1,self.company_id.name,header_format)
        sheet.write(x_offset,header_width-2,(_("Start Date")),header_format)
        sheet.write(x_offset,header_width-1,self.start_date.strftime("%d-%m-%Y"),header_format)
        x_offset+=1
        sheet.write(x_offset,header_width-2,(_("End Date")),header_format)
        sheet.write(x_offset,header_width-1,self.end_date.strftime("%d-%m-%Y"),header_format)

        x_offset+=2
        for idx,header in enumerate(first_table_headers): 
            sheet.write(x_offset,idx,(_(header)),header_format)
        x_offset+=1

        result_list = []
        for product in product_ids:
            opening_sql = '''
                            select
                COALESCE(SUM(balance),0) as balance,
                COALESCE(SUM(total_amt),0) as balance_amt
                from stock_location_valuation_report slvr
                left join stock_location as sl_by on sl_by.id = slvr.by_location
                where report_date < %s and product_id = %s and sl_by.id = %s
                            '''
            self.env.cr.execute(opening_sql,(self.start_date,product,self.location_id.id))
            opening_result = self.env.cr.dictfetchall()
            
            opening_price = self.env['stock.location.valuation.report'].search([('report_date','<',self.start_date),('product_id','=',product),('by_location','=',self.location_id.id)],order="report_date desc",limit=1)
            
            slvr_sql = '''
                        select
                        rb.name as branch,
                        slvr.report_date,slvr.product_id,
                        CASE 
                            WHEN slvr.report_type = 'adjustment' THEN 'Adjustment'
                            WHEN slvr.report_type = 'adjustment_return' THEN 'Adjustment Return'
                            WHEN slvr.report_type = 'delivery' THEN 'Delivery'
                            WHEN slvr.report_type = 'delivery_return' THEN 'Delivery Return'
                            WHEN slvr.report_type = 'receipt' THEN 'Receipt'
                            WHEN slvr.report_type = 'receipt_return' THEN 'Receipt Return'
                            WHEN slvr.report_type = 'transfer' THEN 'Transfer'
                            WHEN slvr.report_type = 'transfer_return' THEN 'Transfer Return'
                            WHEN slvr.report_type = 'duty' THEN 'Duty'
                            WHEN slvr.report_type = 'landed_cost' THEN 'Landed Cost'
                            WHEN slvr.report_type = 'mrp' THEN 'Manufacturing'
                            WHEN slvr.report_type = 'unknown' THEN 'Unknown'
                            ELSE ''
                        END as report_type,
                        slvr.ref as ref,	
                        slvr.report_date,slvr.product_id,
                        sl_by.name as by_location,
                        sl_l.name as from_location,
                        sl_ld.name as to_location,
                        pp.product_code as product_code,
                        pt.name::jsonb ->> 'en_US' as product_name,
                        slvr.qty_in as qty_in,
                        slvr.qty_out * -1 as qty_out,
                        uu.name::jsonb ->> 'en_US' as uom,
                        slvr.unit_cost as price
                        from stock_location_valuation_report slvr
                        left join res_branch as rb on rb.id = slvr.branch_id
                        left join stock_location as sl_by on sl_by.id = slvr.by_location
                        left join stock_location as sl_l on sl_l.id = slvr.location_id
                        left join stock_location as sl_ld on sl_ld.id = slvr.location_dest_id
                        left join product_product as pp on pp.id = slvr.product_id
                        left join product_template as pt on pt.id = pp.product_tmpl_id
                        left join uom_uom as uu on uu.id = slvr.uom_id
                        where slvr.report_date >= %s and slvr.report_date <= %s and
                        slvr.product_id = %s and slvr.by_location = %s
                        order by slvr.product_id,slvr.report_date
                        '''
            self.env.cr.execute(slvr_sql,(self.start_date,self.end_date,product,self.location_id.id))
            stock_result = self.env.cr.dictfetchall()
            
            opening_unit_cost = 0.0
            op_amt = 0
            if not opening_price:
                if stock_result:
                    opening_unit_cost = round(stock_result[0]['price'],2)
            else:
                opening_unit_cost = round(opening_price.unit_cost,2)
            
            if opening_result:
                op_amt = opening_result[0]['balance_amt']
            # op_amt = round(opening_result[0]['balance'] * opening_unit_cost,2)
            first = 1
            next_opening_amt = 0
            next_opening_qty = 0

            for sl in stock_result:
                temp = {
                    'branch': sl['branch'],
                    'date': sl['report_date'],
                    'ref': sl['ref'],
                    'report_type': sl['report_type'],
                    'by_location': sl['by_location'],
                    'from_location': sl['from_location'],
                    'to_location': sl['to_location'],
                    'product_code': sl['product_code'],
                    'product_name': sl['product_name'],
                    'uom': sl['uom']
                }
                if first == 1:
                    qty_op = opening_result[0]['balance']
                    qty_bal = qty_op + sl['qty_in'] + sl['qty_out']
                    amount = (sl['qty_in'] + sl['qty_out']) * opening_unit_cost
                    balance = round(op_amt + amount,2)
                    temp['qty_op'] = qty_op
                    temp['op_amt'] = op_amt
                    temp['qty_in'] = sl['qty_in']
                    temp['qty_out'] = sl['qty_out']
                    temp['qty_bal'] = qty_bal
                    temp['price'] = opening_unit_cost
                    temp['amount'] = amount
                    temp['balance'] = balance
                    
                    next_opening_amt = balance
                    next_opening_qty = qty_bal
                    result_list.append(temp)
                else:
                    op_amt = next_opening_amt
                    qty_op = next_opening_qty
                    qty_bal = qty_op + sl['qty_in'] + sl['qty_out']
                    
                    amount = round((sl['qty_in'] + sl['qty_out']) * round(sl['price'],2),2)
                    balance = round(op_amt + amount,2)
                    temp['qty_op'] = qty_op
                    temp['op_amt'] = op_amt
                    temp['qty_in'] = sl['qty_in']
                    temp['qty_out'] = sl['qty_out']
                    temp['qty_bal'] = qty_bal
                    temp['price'] = round(sl['price'],2)
                    temp['amount'] = amount
                    temp['balance'] = balance
                    
                    next_opening_amt = balance
                    next_opening_qty = qty_bal
                    result_list.append(temp)

                first += 1
                sheet.write(x_offset,0,temp['branch'],text_format)
                sheet.write(x_offset,1,temp['date'].strftime("%d-%m-%Y"),text_format)
                sheet.write(x_offset,2,temp['ref'],text_format)
                sheet.write(x_offset,3,temp['report_type'],text_format)
                sheet.write(x_offset,4,temp['by_location'],text_format)
                sheet.write(x_offset,5,temp['from_location'],text_format)
                sheet.write(x_offset,6,temp['to_location'],text_format)
                sheet.write(x_offset,7,temp['product_code'],text_format)
                sheet.write(x_offset,8,temp['product_name'],text_format)
                sheet.write(x_offset,9,temp['uom'],text_format)
                sheet.write(x_offset,10,temp['price'],text_format)
                sheet.write(x_offset,11,temp['qty_op'],text_format)
                # sheet.write(x_offset,12,temp['op_amt'],text_format)
                sheet.write(x_offset,11,temp['qty_in'],text_format)
                sheet.write(x_offset,12,temp['qty_out'],text_format)
                sheet.write(x_offset,13,temp['qty_bal'],text_format)
                sheet.write(x_offset,14,temp['amount'],text_format)
                sheet.write(x_offset,15,temp['balance'],text_format)
                x_offset+=1

        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=stock.ledger.report&id=%s&file_name=%s' % (self.id, file_name),
            'target':'self',
        }

