# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################

from odoo import api, fields, models, _
from odoo import tools
from odoo.exceptions import UserError
from odoo.tools.translate import _
import logging
from odoo.addons.prestashop_odoo_bridge.models.prestapi import PrestaShopWebService,PrestaShopWebServiceDict,PrestaShopWebServiceError,PrestaShopAuthenticationError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def multichannel_sync_quantity(self, pick_details):
        """ Method to be overriden by the multichannel modules to provide real time stock
        update feature
        """
        message = ''
        product_qty = 0
        map_obj = self.env['channel.product.mappings']
        channel_obj = self.env['multi.channel.sale'].search(
            [('id', 'in', pick_details['channel_ids']),
            ('channel','=','prestashop')])
        if channel_obj:
            for channel in channel_obj:
                if channel.auto_sync_stock:
                    domain = [
                        ('product_name','=', pick_details['product_id'])
                    ]
                    product_map_objs = channel._match_mapping(map_obj, domain)
                    for product_map_obj in  product_map_objs:
                        if product_map_obj:
                            ps_product_id = product_map_obj.store_product_id
                            ps_variant_id = product_map_obj.store_variant_id


                            product_qty = product_map_obj.product_name._compute_quantities_dict(None, None, None).get(
                                product_map_obj.product_name.id).get('free_qty', 0)
                            url = channel.prestashop_base_uri
                            key = channel.prestashop_api_key
                            try:
                                prestashop = PrestaShopWebServiceDict(url, key)
                            except Exception as e:
                                _logger.info(':::  Error : %r ::::::::::::::::::::::::::',e)
                                message = ' Error in connection %s'%(e)
                            try:
                                stock_search = prestashop.get('stock_availables',options={'filter[id_product]':ps_product_id,'filter[id_product_attribute]':ps_variant_id})
                            except Exception as e:
                                _logger.info(':::  Error : %r ::::::::::::::::::::::::::',e)
                                message = ' Unable to search given stock id: %s'%(product_map_obj)
                            if type(stock_search['stock_availables']) == dict:
                                stock_id = stock_search['stock_availables']['stock_available']['attrs']['id']
                                try:
                                    stock_data = prestashop.get('stock_availables', stock_id)
                                except Exception as e:
                                    _logger.info(':::  Error : %r ::::::::::::::::::::::::::',e)
                                    message = ' Error in Updating Quantity,can`t get stock_available data: %s'%(product_map_obj)
                                if type(product_qty) == str:
                                    product_qty = product_qty.split('.')[0]
                                if type(product_qty) == float:
                                    product_qty = int(product_qty)
                                stock_data['stock_available']['quantity'] = int(product_qty)
                                try:
                                    up = prestashop.edit('stock_availables', stock_id, stock_data)
                                except Exception as e:
                                    message = "Error while updating the qty : %s"%(e)
                                    _logger.info(':::  Error : %r ::::::::::::::::::::::::::',[message, stock_id])
                                    pass
                            else:
                                message = ' No stock`s entry found in prestashop for given combination (Product id:%s ; Attribute id:%s)'%(str(ps_product_id),str(ps_variant_id))
        return message
