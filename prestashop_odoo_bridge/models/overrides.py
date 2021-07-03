#!/usr/bin/env python
# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#    See LICENSE file for full copyright and licensing details.
#################################################################################

from odoo import api, fields, models, _
from odoo import tools
from .prestapi import PrestaShopWebService,PrestaShopWebServiceDict,PrestaShopWebServiceError,PrestaShopAuthenticationError
from odoo.tools.translate import _
from datetime import datetime,timedelta
import logging
_logger     = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def write(self, vals):
        if 'search_default_filter_by_channel_id' not in self._context:
            self.channel_mapping_ids.write({'need_sync':'yes'})
        else:
            self.channel_mapping_ids.write({'need_sync':'no'})
        return super(ProductTemplate, self).write(vals)

class sale_order(models.Model):
    _inherit = "sale.order"


    def multichannel_prestashop_invoice_cancel(self):
        context = self.env.context.copy()
        error_message = ''
        status = 'yes'
        check_order = self.channel_mapping_ids.channel_id
        config_id = check_order
        if not config_id:
            error_message = 'Connection needs one Active Configuration setting.'
            status = 'no'
        else:
            url = config_id.prestashop_base_uri
            key = config_id.prestashop_api_key
            try:
                prestashop = PrestaShopWebServiceDict(url, key)
            except PrestaShopWebServiceError as e:
                error_message = 'Invalid Information, Error %s'%e
                status = 'no'
            except IOError as e:
                error_message = 'Error %s'%e
                status = 'no'
            except Exception as e:
                error_message = "Error,Prestashop Connection in connecting: %s" % e
                status = 'no'
            if prestashop:
                order_id = self.channel_mapping_ids.store_order_id
                if order_id:
                    try:
                        order_his_data = prestashop.get('order_histories', options = {'schema': 'blank'})
                        order_his_data['order_history'].update({
                        'id_order' : order_id,
                        'id_order_state' : 6
                        })
                        state_update = prestashop.add('order_histories', order_his_data)
                    except Exception as e:
                        error_message = "Error %s, Error in getting Blank XML"%str(e)
                        status = 'no'
                else:
                    return True

    def action_cancel(self):
        res = super(sale_order, self).action_cancel()
        config_id = self.channel_mapping_ids.channel_id
        # update_order_cancel = config_id.cancelled
        if 'ecommerce' not in self._context:
            if config_id and config_id.channel == "prestashop":
                self.multichannel_prestashop_invoice_cancel()
        return res

    def multichannel_prestashop_paid(self):
        sale_id = self.channel_mapping_ids
        if sale_id:
            error_message = ''
            status = 'yes'
            config_id = sale_id.channel_id
            if not config_id:
                error_message = 'Connection needs one Active Configuration setting.'
                status = 'no'
            else:
                url = config_id.prestashop_base_uri
                key = config_id.prestashop_api_key
                try:
                    prestashop = PrestaShopWebServiceDict(url, key)
                except PrestaShopWebServiceError as e:
                    error_message = 'Invalid Information, Error %s'%e
                    status = 'no'
                except IOError as e:
                    error_message = 'Error %s'%e
                    status = 'no'
                except Exception as e:
                    error_message = "Error,Prestashop Connection in connecting: %s" % e
                    status = 'no'
                if prestashop:
                    order_id = sale_id.store_order_id
                    if order_id:
                        try:
                            order_his_data = prestashop.get('order_histories', options={'schema': 'blank'})
                            order_his_data['order_history'].update({
                            'id_order' : order_id,
                            'id_order_state' : 2
                            })
                            state_update = prestashop.add('order_histories?sendemail=1', order_his_data)
                        except Exception as e:
                            error_message = "Error %s, Error in getting Blank XML"%str(e)
                            status = 'no'
                    else:
                        return True


class account_payment(models.Model):
    _inherit = "account.payment"


    def post(self):
        res = super(account_payment, self).post()
        sale_obj = self.env['sale.order']
        if 'ecommerce' not in self._context:
            for rec in self:
                invoice_ids = rec.invoice_ids
                for inv_obj in invoice_ids:
                    invoices = inv_obj.read(['invoice_origin', 'state'])
                    if invoices[0]['invoice_origin']:
                        sale_ids = sale_obj.search(
                            [('name', '=', invoices[0]['invoice_origin'])])
                        for sale_order_obj in sale_ids:
                            order_id = sale_order_obj.channel_mapping_ids
                            config_id = order_id.channel_id
                            # update_order_invoice = config_id.invoiced
                            if order_id and config_id and config_id.channel == "prestashop":
                                sale_order_obj.multichannel_prestashop_paid()
        return res
#
#
class StockPicking(models.Model):
    # _name = "stock.picking"
    _inherit="stock.picking"

    def multichannel_prestashop_shipment(self):
        context = self.env.context.copy()
        order_name = self.group_id.name
        sale_id = self.env['sale.order'].search([('name','=',order_name)])
        if sale_id:
            error_message = ''
            status = 'yes'
            check_order = sale_id.channel_mapping_ids
            config_id = check_order.channel_id
            if not config_id:
                error_message = 'Connection needs one Active Configuration setting.'
                status = 'no'
            else:
                url = config_id.prestashop_base_uri
                key = config_id.prestashop_api_key
                try:
                    prestashop = PrestaShopWebServiceDict(url, key)
                except PrestaShopWebServiceError as e:
                    error_message = 'Invalid Information, Error %s'%e
                    status = 'no'
                except IOError as e:
                    error_message = 'Error %s'%e
                    status = 'no'
                except Exception as e:
                    error_message = "Error,Prestashop Connection in connecting: %s" % e
                    status = 'no'
                if prestashop:
                    order_id = check_order.store_order_id
                    if order_id:
                        try:
                            order_his_data = prestashop.get('order_histories',
                                options={'schema': 'blank'})
                            order_his_data['order_history'].update({
                            'id_order' : order_id,
                            'id_order_state' : 4
                            })
                            state_update = prestashop.add('order_histories', order_his_data)
                        except Exception as e:
                            error_message = "Error %s, Error in getting Blank XML"%str(e)
                            status = 'no'

        return True
#
    def action_done(self):
        res = super(StockPicking, self).action_done()
        order_name = self.group_id.name
        sale_id = self.env['sale.order'].search([('name','=',order_name)])
        if 'ecommerce' not in self._context:
            config_id = sale_id.channel_mapping_ids.channel_id
            # shipped = config_id.delivered
            # if shipped:
            if config_id and config_id.channel == "prestashop":
                self.multichannel_prestashop_shipment()
        return res

class PurchaseOrder(models.Model):
    # _name = "stock.picking"
    _inherit = "purchase.order"

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        date_planned = self.date_planned.strftime("%Y-%m-%d")
        for product in self.order_line.product_id:
            if product.channel_mapping_ids:
                config_id = product.channel_mapping_ids.channel_id
                url = config_id.prestashop_base_uri
                key = config_id.prestashop_api_key
                try:
                    prestashop = PrestaShopWebServiceDict(url, key)
                except PrestaShopWebServiceError as e:
                    error_message = 'Invalid Information, Error %s' % e
                if prestashop:

                    id_product_presta = product.channel_mapping_ids.store_product_id
                    id_variant_presta = product.channel_mapping_ids.store_variant_id
                    #_logger.info("==%r=id_variant_presta===" % id_variant_presta)
                    if id_product_presta:
                        if id_variant_presta!='No Variants':
                            combination_presta = prestashop.get('combinations', id_variant_presta)
                            #_logger.info("==%r=combination_presta===" % combination_presta)

                            combination_presta['combination']['available_date'] = date_planned
                            #_logger.info("==%r=combination_presta===" % combination_presta)
                            try:
                                #combination_presta['combination'].pop('manufacturer_name')
                                combination_presta['combination'].pop('quantity')
                                prestashop.edit('combinations', id_variant_presta, combination_presta)


                            except Exception as e:
                                error_message = "Error %s, Error in getting  XML" % str(e)
                                combination_presta = 'no'


                        else:

                            product_presta = prestashop.get('products', id_product_presta)
                            #_logger.info("==%r=product_presta===" % product_presta)
                            product_presta['product']['available_date'] = date_planned
                            #_logger.info("==%r=product_presta===" % product_presta)
                            try:
                                product_presta['product'].pop('manufacturer_name')
                                product_presta['product'].pop('quantity')
                                prestashop.edit('products', id_product_presta, product_presta)


                            except Exception as e:
                                error_message = "Error %s, Error in getting  XML" % str(e)
                                product_presta = 'no'

        return res
