# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from datetime import date
from unidecode import unidecode
import requests
import re
import json
import logging
import base64
#from openerp.exceptions import Warning, UserError

_logger = logging.getLogger(__name__)
class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    package_carrier_type = fields.Selection(selection_add=[('cex', "CEX")])

class oct_cex_conector(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('cex', "CEX")],ondelete={'cex': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})

    cex_url = fields.Char('Correos Express URL')

    cex_username = fields.Char(
        string='Username')
    cex_password = fields.Char(
        string='Password')
    cex_codRte = fields.Char(
        string='Código de cliente')
    cex_solicitante = fields.Char(
        string='Solicitante')
    cex_default_service_type = fields.Selection([('93','EPAQ24'),('90','INTERNACIONAL ESTANDAR'),('92','INTERNACIONAL EXPRES')], string="Service Type", default='93')

    def cex_send_shipping(self, pickings):
        res = []
        for picking in pickings:
            if not picking.carrier_tracking_ref:
                shipping = self._generate_cex_label(picking)
                carrier_tracking_ref = shipping['tracking_number']
                if carrier_tracking_ref:
                    logmessage = (_("Shipment created into Correo Express <br/> <b>Tracking Number : </b>%s") % (
                        carrier_tracking_ref))
                    picking.message_post(body=logmessage, attachments=[
                        ('LabelCorreoExpress-%s.pdf' % (carrier_tracking_ref), shipping['pdf'])])

                    shipping_data = {
                        'exact_price': 0,
                        'tracking_number': carrier_tracking_ref,
                        'pdf': shipping['pdf'] or False
                    }
                else:
                    shipping_data = {
                        'exact_price': 0,
                        'tracking_number': carrier_tracking_ref,
                        'pdf': shipping['pdf'] or False
                    }

            else:
                shipping_data = {
                    'exact_price': 0,
                    'tracking_number': picking.carrier_tracking_ref,
                    'pdf': base64.b64decode(picking.binary_label) if picking.binary_label else False
                }

            res = res + [shipping_data]
        return res

    def cex_get_tracking_link(self, picking):
        return "https://s.correosexpress.com/search?s=" + picking.carrier_tracking_ref

    def number_of_packages_for_cex(self, picking):
        return len(picking.package_ids)

    def _get_cex_label_data(self, picking):

        if picking.picking_type_code == 'incoming':
            partner = picking.partner_id
            number_of_packages = self.number_of_packages_for_cex(picking) or 1
            phone = partner.mobile or partner.phone or ''
            listaBultos = []
            for i in range(0, number_of_packages):
                listaBultos.append({
                    'ancho': '',
                    'observaciones': '',
                    'kilos': '',
                    'codBultoCli': '',
                    'codUnico': '',
                    'descripcion': '',
                    'alto': '',
                    'orden': i + 1,
                    'referencia': '',
                    'volumen': '',
                    'largo': ''
                })
            streets = []
            if partner.street:
                streets.append(unidecode(partner.street))
            if partner.street2:
                streets.append(unidecode(partner.street2))
            data = {
                'solicitante': self.cex_solicitante,
                'canalEntrada': '',
                'numEnvio': '',
                'ref': picking.name[:20],
                'refCliente': '',
                'fecha': date.today().strftime('%d%m%Y'),
                'codRte': self.cex_codRte,
                'nomRte': partner.name,
                'nifRte': '',
                'dirRte': ''.join(streets)[:300],
                'pobRte': partner.city,
                'codPosNacRte': partner.zip,
                'paisISORte': '',
                'codPosIntRte': '',
                'contacRte': partner.name,
                'telefRte': phone[:15],
                'emailRte': partner.email,
                'codDest': '',
                'nomDest': picking.company_id.name[:40] or '',
                'nifDest': '',
                'dirDest': picking.company_id.street[:300],
                'pobDest': picking.company_id.city[:50] or '',
                'codPosNacDest': picking.company_id.zip,
                'paisISODest': '',
                'codPosIntDest': '',
                'contacDest': picking.company_id.name[:40] or '',
                'telefDest': picking.company_id.phone,
                'emailDest': picking.company_id.email[:75] or 'test@test.com',
                'contacOtrs': '',
                'telefOtrs': '',
                'emailOtrs': '',
                'observac': '',
                'numBultos': number_of_packages or 1,
                'kilos': '%.3f' % (picking.weight or 1),
                'volumen': '',
                'alto': '',
                'largo': '',
                'ancho': '',
                'producto': self.cex_default_service_type,
                'portes': 'P',
                'reembolso': '',  # TODO cash_on_delivery
                'entrSabado': '',
                'seguro': '',
                'numEnvioVuelta': '',
                'listaBultos': listaBultos,
                'codDirecDestino': '',
                'password': 'string',
                'listaInformacionAdicional': [{
                    'tipoEtiqueta': '1',
                    'etiquetaPDF': ''
                }],
            }
            return data

        else:
            partner = picking.partner_id
            number_of_packages = self.number_of_packages_for_cex(picking) or 1
            phone = partner.mobile or partner.phone or ''
            listaBultos = []
            for i in range(0, number_of_packages):
                listaBultos.append({
                    'ancho': '',
                    'observaciones': '',
                    'kilos': '',
                    'codBultoCli': '',
                    'codUnico': '',
                    'descripcion': '',
                    'alto': '',
                    'orden': i + 1,
                    'referencia': '',
                    'volumen': '',
                    'largo': ''
                })
            streets = []
            if partner.street:
                streets.append(unidecode(partner.street))
            if partner.street2:
                streets.append(unidecode(partner.street2))
            data = {
                'solicitante': self.cex_solicitante,
                'canalEntrada': '',
                'numEnvio': '',
                'ref': picking.name[:20],
                'refCliente': '',
                'fecha': date.today().strftime('%d%m%Y'),
                'codRte': self.cex_codRte,
                'nomRte': picking.picking_type_id.warehouse_id.partner_id.name,
                'nifRte': '',
                'dirRte': picking.picking_type_id.warehouse_id.partner_id.street,
                'pobRte': picking.picking_type_id.warehouse_id.partner_id.city,
                'codPosNacRte': picking.picking_type_id.warehouse_id.partner_id.zip,
                'paisISORte': '',
                'codPosIntRte': '',
                'contacRte': picking.picking_type_id.warehouse_id.partner_id.name,
                'telefRte': picking.company_id.phone,
                'emailRte': picking.company_id.email,
                'codDest': '',
                'nomDest': partner.name[:40] or '',
                'nifDest': '',
                'dirDest': ''.join(streets)[:300],
                'pobDest': partner.city[:50] or '',
                'codPosNacDest': partner.zip if partner.country_id.code =='ES' else'',
                'paisISODest': partner.country_id.code,
                'codPosIntDest': partner.zip.replace('-','') if partner.country_id.code !='ES' else'',
                'contacDest': partner.name[:40] or '',
                'telefDest': phone.replace(' ','')[:15],
                'emailDest': partner.email or 'test@test.com',
                'contacOtrs': '',
                'telefOtrs': '',
                'emailOtrs': '',
                'observac': '',
                'numBultos': number_of_packages or 1,
                'kilos': '%.3f' % (picking.weight or 1),
                'volumen': '',
                'alto': '',
                'largo': '',
                'ancho': '',
                'producto': self.cex_default_service_type,
                'portes': 'P',
                'reembolso': '',  # TODO cash_on_delivery
                'entrSabado': '',
                'seguro': '',
                'numEnvioVuelta': '',
                'listaBultos': listaBultos,
                'codDirecDestino': '',
                'password': 'string',
                'listaInformacionAdicional': [{
                    'tipoEtiqueta': '1',
                    'etiquetaPDF': ''
                }],
            }
            return data

    def cex_cancel_shipment(self, picking):
        # Obviously you need a pick up date to delete SHIPMENT by MRW. So you can't do it if you didn't schedule a pick-up.
        # picking.message_post(body=_(u"You can't cancel mrw shipping without pickup date."))
        picking.write({'carrier_tracking_ref': '',
                       'carrier_price': 0.0})

    def _generate_cex_label(self, picking):
        dict_response = {'tracking_number': 0.0,
                         'price': 0.0,
                         'currency': False,
                         'pdf': False, }

        url = self.cex_url
        username = self.cex_username
        password = self.cex_password
        try:
            data = self._get_cex_label_data(picking)
            response = requests.post(url, auth=(username, password), json=data, timeout=5)

            rjson = json.loads(re.search('({.*})', response.text).group(1))
            retorno = rjson['codigoRetorno']
            message = rjson['mensajeRetorno']
            if retorno == 0:
                label = rjson['etiqueta'][0]['etiqueta1']
                label_decode = base64.b64decode(base64.b64decode(label))
                dict_response.update({'tracking_number': rjson['datosResultado']})
                dict_response.update({'pdf': label_decode})
            else:
                message = ("CEX Error: %s %s" % (retorno or 999, message or 'Webservice ERROR.'))
                picking.message_post(body=message)
        except requests.exceptions.Timeout:
            picking.message_post(body="El servidor está tardando mucho en responder.")

        except Exception as e:
            message = ("Error creating shipment into correo express %s" %e)
            picking.message_post(body=message)

        return dict_response
