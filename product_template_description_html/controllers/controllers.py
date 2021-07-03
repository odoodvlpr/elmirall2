from odoo import http
from odoo.http import request, Controller, route
from openerp.addons.web.controllers.main import serialize_exception
import datetime
import logging
import base64


_logger = logging.getLogger(__name__)


class ProductCatalog(Controller):
    @route('/shop/product/download/', type='http', auth="user")
    @serialize_exception
    def download_catalog(self, id, **kw):
        product = request.env['product.template'].sudo().search([('id', '=', id)])
        filename = product.recursos_data_file_name
        filecontent = base64.b64decode(product.recursos_extras)
        if not filecontent:
            return request.not_found()
        else:
            return request.make_response(filecontent,
                                     [('Content-Type', 'application/octet-stream'),
                                      ('Content-Disposition', "attachment; filename=%s" % filename)])
