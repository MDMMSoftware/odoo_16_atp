# -*- coding: utf-8 -*-
# from odoo import http


# class TimeOffExtension(http.Controller):
#     @http.route('/time_off_extension/time_off_extension', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/time_off_extension/time_off_extension/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('time_off_extension.listing', {
#             'root': '/time_off_extension/time_off_extension',
#             'objects': http.request.env['time_off_extension.time_off_extension'].search([]),
#         })

#     @http.route('/time_off_extension/time_off_extension/objects/<model("time_off_extension.time_off_extension"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('time_off_extension.object', {
#             'object': obj
#         })
