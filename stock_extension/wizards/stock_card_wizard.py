
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

class StockCardReport(models.TransientModel):
    _name = 'stock.card.report'

    company_id = fields.Many2one('res.company', string='Company',default=lambda self:self.env.company,required=True)
    location_ids = fields.Many2many('stock.location', string='Location',required=True)
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
        file_name = os.path.join(tempfile.gettempdir(), 'Stock Card Report.xlsx')
        workbook = xlsxwriter.Workbook(file_name)
        sheet = workbook.add_worksheet("Stock Card Report")
        banner_format_small = workbook.add_format({'font_name': 'Arial','bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,'border':True})
        header_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter','bold': True,'border':True,'bg_color': '#AAAAAA'})
        text_format = workbook.add_format({'font_name': 'Arial','align': 'left', 'valign': 'vcenter'})

        report_by = "location"
        header_width = 6
        product_ids=None
        first_table_headers = ["Stock Code","Description","Internal Reference","Model","Group","Category","Brand","UOM","Opening","In","Out","Closing","Balance"]
        if self.display_all_products or (not self.display_all_products and not self.filter_product_ids):
            product_ids = self.env['product.product'].search([('detailed_type','in',self.detailed_type.split(","))]).ids
        else:
            product_ids = self.filter_product_ids.filtered(lambda x:x.detailed_type in self.detailed_type.split(",")).ids
        if ( product_ids and len(product_ids) == 1 ) and (self.location_ids and len(self.location_ids) > 1):
            report_by = 'product'
            first_table_headers = ["Stock Code","Description","Internal Reference","Model","Group","Category","Brand","UOM"]
            header_width = 8

        for i in range(8):
            if i == 0:
                sheet.set_column(i, i, 40)
            else:
                sheet.set_column(i, i, 15)
        y_offset = header_width - 1
        x_offset = 3

        
        sheet.merge_range(0,0,x_offset,y_offset, _("Stock Card Report"), banner_format_small)
        x_offset+=1
        sheet.write(x_offset,0,(_("Business Unit")),header_format)
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

        if report_by == 'product' and product_ids:
            product = self.env['product.product'].search([('id','=',product_ids[0])])
            sheet.write(x_offset,0,product.product_code or '-', text_format)
            sheet.write(x_offset,1,product.product_code or '-',text_format)
            sheet.write(x_offset,2,product.default_code or '-',text_format)
            
            sheet.write(x_offset,3,product.custom_model_no_id and product.custom_model_no_id.name or '-',text_format)
            sheet.write(x_offset,4,product.group_class_id and product.group_class_id.name or '-',text_format)
            sheet.write(x_offset,5,product.custom_category_id and product.custom_category_id.name or '-',text_format)
            sheet.write(x_offset,6,product.custom_brand_id and product.custom_brand_id.name or '-',text_format)
            sheet.write(x_offset,7,product.uom_id and product.uom_id.name or '-',text_format)

            x_offset += 2     
            another_table_headers = ["Location","","","Opening","In","Out","Closing","Balance"]
            for idx,header in enumerate(another_table_headers): 
                sheet.write(x_offset,idx,(_(header)),text_format)
            x_offset+=1

            

        

        for location in self.location_ids:
        
            sql=''' select 
                        a.id,a.name as product_name,sum(a.opening_qty) as opening_qty,sum(a.opening_amt) as opening_amt,
                        sum(a.in_qty) as in_qty,sum(a.out_qty) as out_qty,sum(a.amt_total) as amt_total 
                    from 
                        (
                            select pp.id,pt.name->>'en_US' as name,0 as opening_qty,0 as opening_amt,
                            COALESCE(sum(slvr.qty_in),0) as in_qty,COALESCE(sum(slvr.qty_out),0) as out_qty,
                            SUM(
                                CASE 
                                    WHEN slvr.qty_in > 0 THEN COALESCE(slvr.unit_cost*slvr.qty_in,0)
                                    WHEN slvr.qty_out > 0 THEN COALESCE(-1*(slvr.unit_cost*slvr.qty_out),0)
                                    WHEN slvr.qty_in = 0 AND slvr.qty_out = 0 THEN COALESCE(slvr.total_amt,0)
                                END
						    )  AS amt_total
                            from stock_location_valuation_report slvr 
                            LEFT JOIN product_product pp on pp.id=slvr.product_id 
                            LEFT JOIN product_template pt on pp.product_tmpl_id=pt.id
                            where slvr.product_id in %s
                            and slvr.report_date between %s and %s and slvr.by_location=%s
                            group by pp.id,pt.name
                        
                                UNION ALL
                        
                            select pp.id,pt.name->>'en_US' as name,COALESCE((sum(slvr.qty_in)-sum(slvr.qty_out)),0) as opening_qty,
                            SUM(
                                CASE 
                                    WHEN slvr.qty_in > 0 THEN COALESCE(slvr.unit_cost*slvr.qty_in,0)
                                    WHEN slvr.qty_out > 0 THEN COALESCE(-1*(slvr.unit_cost*slvr.qty_out),0)
                                    WHEN slvr.qty_in = 0 AND slvr.qty_out = 0 THEN COALESCE(slvr.total_amt,0)
                                END
						    )  AS opening_amt,
                            0 as in_qty,0 as out_qty,0 as amt_total
                            from stock_location_valuation_report slvr 
                            LEFT JOIN product_product pp on pp.id=slvr.product_id 
                            LEFT JOIN product_template pt on pp.product_tmpl_id=pt.id
                            where slvr.product_id in %s
                            and slvr.report_date < %s and slvr.by_location=%s
                            group by pp.id,pt.name
                        ) a 
                    group by a.id,a.name'''
            # print(sql,(tuple(product_ids),self.start_date,self.end_date,location.id,
            #                          tuple(product_ids),self.start_date,location.id))
            self.env.cr.execute(sql,(tuple(product_ids),self.start_date,self.end_date,location.id,
                                     tuple(product_ids),self.start_date,location.id))
            result = self.env.cr.dictfetchall()
            if result and report_by != 'product':
                sheet.merge_range(x_offset,0,x_offset,12,location.name,header_format)
                x_offset+=1
            for res in result:
                closing_qty = closing_amt = 0
                product = self.env['product.product'].browse(res.get('id'))
                closing_qty += res.get('opening_qty')+res.get('in_qty')-res.get('out_qty')
                closing_amt += res.get('opening_amt')+res.get('amt_total')
                if report_by == 'product':
                    sheet.merge_range(x_offset,0,x_offset,2,location.name,header_format)
                    sheet.write(x_offset,3,round(res.get('opening_qty'),2),text_format)
                    sheet.write(x_offset,4,round(res.get('in_qty'),2),text_format)
                    sheet.write(x_offset,5,round(res.get('out_qty'),2),text_format)
                    sheet.write(x_offset,6,round(closing_qty,2),text_format)
                    sheet.write(x_offset,7,round(closing_amt,2),text_format)                
                else:
                    sheet.write(x_offset,0,product.product_code or '-', text_format)
                    sheet.write(x_offset,1,res.get('product_name'),text_format)
                    sheet.write(x_offset,2,product.default_code,text_format)
                    
                    sheet.write(x_offset,3,product.custom_model_no_id and product.custom_model_no_id.name or '-',text_format)
                    sheet.write(x_offset,4,product.group_class_id and product.group_class_id.name or '-',text_format)
                    sheet.write(x_offset,5,product.custom_category_id and product.custom_category_id.name or '-',text_format)
                    sheet.write(x_offset,6,product.custom_brand_id and product.custom_brand_id.name or '-',text_format)
                    sheet.write(x_offset,7,product.uom_id and product.uom_id.name or '-',text_format)

                    sheet.write(x_offset,8,round(res.get('opening_qty'),2),text_format)
                    sheet.write(x_offset,9,round(res.get('in_qty'),2),text_format)
                    sheet.write(x_offset,10,round(res.get('out_qty'),2),text_format)
                    sheet.write(x_offset,11,round(closing_qty,2),text_format)
                    sheet.write(x_offset,12,round(closing_amt,2),text_format)
                x_offset+=1
          
                 
        x_offset+=1   
        workbook.close()
        output.seek(0)
        return self.download_excel_file(file_name)

    def download_excel_file(self, file_name):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=stock.card.report&id=%s&file_name=%s' % (self.id, file_name),
            'target':'self',
        }
    
    def get_opening_qty(self,product_id,location_id):
        opening_qty=0
        sql='''select COALESCE(sum(qty_in),0) as in_qty,COALESCE(sum(qty_out),0) as out_qty,COALESCE(sum(total_amt),0) as amt_total
            from stock_location_valuation_report slvr 
            LEFT JOIN product_product pp on pp.id=slvr.product_id 
            LEFT JOIN product_template pt on pp.product_tmpl_id=pt.id
            where slvr.product_id = %s
            and slvr.report_date < %s and slvr.location_id=%s 
            '''
        self.env.cr.execute(sql,(product_id,self.start_date,location_id))
        res = self.env.cr.dictfetchall()
        for val in res:
            opening_qty += val.get('in_qty')+val.get('out_qty')
            return opening_qty,val.get('amt_total')
    
