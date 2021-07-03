# -*- coding: utf-8 -*-
from odoo import http

# class OctCexConector(http.Controller):
#     @http.route('/oct_cex_conector/oct_cex_conector/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/oct_cex_conector/oct_cex_conector/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('oct_cex_conector.listing', {
#             'root': '/oct_cex_conector/oct_cex_conector',
#             'objects': http.request.env['oct_cex_conector.oct_cex_conector'].search([]),
#         })

#     @http.route('/oct_cex_conector/oct_cex_conector/objects/<model("oct_cex_conector.oct_cex_conector"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('oct_cex_conector.object', {
#             'object': obj
#         })