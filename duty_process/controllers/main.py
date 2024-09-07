
from odoo import http
from odoo.http import Controller, request, route, content_disposition

class ExcelReports(http.Controller):

    @http.route('/web/binary/download_document', type="http", auth="public")
    def download_document(self, model, id, file_name=None, **kw):
        excel_file = open(file_name, 'rb')
        file_content = excel_file.read()
        excel_file.close()

        if not file_content:
            return request.not_found()
        else:
            filename = file_name.split('/')[-1]
            return request.make_response(file_content, [
                            ('Content-Type', 'application/octet-stream'),
                            ('Content-Length', len(file_content)),
                            ('Content-Disposition', content_disposition('%s.xlsx' % filename))
                        ])


        
