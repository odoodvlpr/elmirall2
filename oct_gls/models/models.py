# -*- coding: utf-8 -*-
import pytz
from datetime import datetime
from odoo import models, fields, api, _
import xml.etree.ElementTree as etree
import logging
import requests
from odoo.addons.oct_gls.models.gls_api.gls_response import Response
import re
import binascii
import base64

_logger = logging.getLogger(__name__)


class ProviderGLS(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('gls', "GLS")], ondelete={
        'gls': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})

    @staticmethod
    def gls_validate_response_label(result_label, picking, tracking):

        if result_label.get('Envelope').get('Body').get('EtiquetaEnvioResponse') is None:
            message_error = _('Problem Label not found for picking {}'.format(picking.name))
            _logger.info(message_error)
            picking.message_post(body=message_error)
            return False

        try:
            label = result_label.get('Envelope').get('Body').get('EtiquetaEnvioResponse').get(
                'EtiquetaEnvioResult').get('base64Binary', False)
            binary_data = binascii.a2b_base64(str(label))
            if label and binary_data:
                message = _("Label created!<br/> <b>Label Tracking Number : </b>{}".format(tracking))
                picking.message_post(body=message, attachments=[
                    ('Label-{}.{}'.format(picking.origin, "pdf"), binary_data)])
                picking.write({'binary_label': base64.b64encode(binary_data)})
                return binary_data

        except Exception as e:
            message_error = _("Problem with procesing  Label!! for pickign {} E:".format(picking.name, e))
            _logger.info(message_error)
            picking.message_post(body=message_error)
        return False

    @staticmethod
    def gls_validate_response_shipment(response, picking):
        res_error = response.get('Envelope', {}).get('Body', {}).get('GrabaServiciosResponse', {}).get(
            'GrabaServiciosResult', {}).get('Servicios', {}).get('Envio', {}).get('Errores', {})

        if res_error is None or res_error.get('Error', {}) == 'Ya existe el albaran':
            return True
        message_error = _("While send shipping. Bad response from carrier GLS. {}".format(res_error.get('Error', {})))
        _logger.error(message_error)
        picking.message_post(body=message_error)
        return False

    @staticmethod
    def gls_validate_response_tracking(result_tracking, picking):
        # TODO refactor gls_validate_response_tracking

        expediciones = result_tracking.\
            get('Envelope', {}).get('Body', {}).\
            get('GetExpCliResponse', {}).\
            get('GetExpCliResult', {}).\
            get('expediciones', {})

        if expediciones and type(expediciones.get('exp', {})) == list:

            address_send = picking.partner_id.street

            if picking.partner_id.street2:
                address_send = picking.partner_id.street + ' ' + picking.partner_id.street2

            for result_track in expediciones.get('exp', {}):

                address_response = result_track.get('calle_dst', {})

                if re.sub('[^0-9a-zA-Z]+', '', address_response.strip()) != re.sub('[^0-9a-zA-Z]+', '',
                                                                                   address_send.strip())[:58]:
                    continue

                if picking.partner_id.country_id.code == 'ES' or not picking.partner_id.country_id:
                    tracking = result_track.get('codexp', {})
                else:
                    tracking = result_track.get('refGlsN', {})

                return tracking

            message_error = _("error address. in GLS {}".format(re.sub('[^0-9a-zA-Z]+', '', address_send.strip())[:58]))
            _logger.info(message_error)
            picking.message_post(body=message_error)
            return False

        elif expediciones and type(expediciones.get('exp', {})) == dict:
            address_response = expediciones.get('exp', {}).get('calle_dst', {})
            address_send = picking.partner_id.street

            if picking.partner_id.street2:
                address_send = picking.partner_id.street + ' ' + picking.partner_id.street2

            if re.sub('[^0-9a-zA-Z]+', '', address_response.strip()) != re.sub('[^0-9a-zA-Z]+', '',
                                                                               address_send.strip())[:58]:
                message_error = _(
                    "error address. send {} response {}".format(re.sub('[^0-9a-zA-Z]+', '', address_send.strip())[:58],
                                                                re.sub('[^0-9a-zA-Z]+', '', address_response.strip())))
                _logger.info(message_error)
                picking.message_post(body=message_error)
                return False

            if picking.partner_id.country_id.code == 'ES' or not picking.partner_id.country_id:
                tracking = expediciones.get('exp', {}).get('codexp', {})
            else:
                tracking = expediciones.get('exp', {}).get('refGlsN', {})

            return tracking
        message_error = _(
            "Error with expedicion in GLS. Expediciocion {}".format(expediciones))
        _logger.info(message_error)
        picking.message_post(body=message_error)
        return False

    @staticmethod
    def gls_get_tracking_of_response(response, picking):

        tracking = False

        if picking.partner_id.country_id.code == 'ES':
            return response.get('Envelope', {}).get('Body', {}).get('GrabaServiciosResponse', {}).get(
                'GrabaServiciosResult', {}).get('Servicios', {}).get('Envio', {}).get('_codexp', {})

        else:

            referencias = response.get('Envelope', {}).get('Body', {}).get('GrabaServiciosResponse', {}).get(
                'GrabaServiciosResult', {}).get('Servicios', {}).get('Envio', {}).get('Referencias', {}).get(
                'Referencia', {})

            if referencias and type(referencias) == 'list':
                for ref in referencias:
                    if ref.get('_tipo', False) != 'N':
                        continue
                    tracking = ref.get('value', False)

        return tracking

    def _get_gls_service_types(self):
        return [
            ('1', 'Courrier'),
            ('76', 'Euro Bussines Small Parcel'),
        ]

    gls_senderid = fields.Char(string='GLS Sender ID')
    gls_url = fields.Char(string='GLS URL')
    gls_default_service_type = fields.Selection(_get_gls_service_types, string="GLS Service Type", default='1')
    gls_anonimous = fields.Boolean('Envio Anonimo', default=False)

    def gls_send_shipping(self, pickings):

        result = []

        for picking in pickings:
            # if picking has tracking and binary_label not request to gls
            if picking.carrier_tracking_ref and picking.binary_label:
                result.append({
                    'exact_price': 0.0,
                    'tracking_number': picking.carrier_tracking_ref,
                    'pdf': picking.binary_label
                })
                continue

            response = self.gls_send_request_shipment(picking)

            if not response:
                result.append({
                    'exact_price': 0.0,
                    'tracking_number': '',
                    'pdf': False
                })
                continue

            if not ProviderGLS.gls_validate_response_shipment(response, picking):
                result.append({
                    'exact_price': 0.0,
                    'tracking_number': '',
                    'pdf': False
                })
                continue

            tracking = ProviderGLS.gls_get_tracking_of_response(response, picking)

            if not tracking and picking.carrier_tracking_ref:
                tracking = picking.carrier_tracking_ref
            elif not tracking:
                tracking_response = self.gls_send_request_tracking(picking)
                tracking = ProviderGLS.gls_validate_response_tracking(tracking_response, picking)

            if not tracking:
                result.append({
                    'exact_price': 0.0,
                    'tracking_number': '',
                    'pdf': False
                })
                continue

            label_response = self.gls_send_request_label(tracking, picking)

            if not label_response:
                result.append({
                    'exact_price': 0.0,
                    'tracking_number': tracking,
                    'pdf': False
                })
                continue

            pdf = ProviderGLS.gls_validate_response_label(label_response, picking, tracking)

            if not pdf:
                result.append({
                    'exact_price': 0.0,
                    'tracking_number': tracking,
                    'pdf': False
                })
                continue

            result.append({
                'exact_price': 0.0,
                'tracking_number': tracking,
                'pdf': pdf
            })

        return result

    def gls_get_tracking_link(self, picking):
        if picking.partner_id.country_id.code == 'ES' or not picking.partner_id.country_id:
            return 'http://www.asmred.com/extranet/public/ExpedicionASM.aspx?codigo={}&cpDst={}'.format(
                picking.carrier_tracking_ref, picking.partner_id.zip)
        else:
            return 'https://www.gls-spain.es/es/ayuda/seguimiento-envio/?international=1&match={}'.format(
                picking.carrier_tracking_ref)

    def generate_request_data(self, data_label, picking, tracking=False):
        master_node = etree.Element('Envelope')
        master_node.attrib['xmlns'] = "http://schemas.xmlsoap.org/soap/envelope/"
        body_node = etree.SubElement(master_node, 'Body')

        if data_label == 'get shipment':
            receiver_id = picking.partner_id
            sender_id = picking.company_id.partner_id
            if self.gls_anonimous:
                if picking.partner_id.company_type == 'person' and picking.partner_id.parent_id:
                    sender_id = picking.partner_id.parent_id

            if picking.has_packages:
                bultos = str(len(picking.package_ids))
            else:
                bultos = "1"
            if receiver_id.street2:
                direccion = receiver_id.street + ' ' + receiver_id.street2
            else:
                direccion = receiver_id.street
            if picking.retorno:
                retorno = str("1")
            else:
                retorno = str("0")

            graba_servicios_node = etree.SubElement(body_node, 'GrabaServicios')
            graba_servicios_node.attrib['xmlns'] = "http://www.asmred.com/"

            docIn = etree.SubElement(graba_servicios_node, "docIn")
            servicio = etree.SubElement(docIn, "Servicios")
            servicio.attrib['uidcliente'] = self.gls_senderid
            servicio.attrib['xmlns'] = "http://www.asmred.com/"
            # envio tag
            current_date = datetime.strftime(datetime.now(pytz.utc), "%Y-%m-%d")
            root_node = etree.SubElement(servicio, "Envio")
            etree.SubElement(root_node, "Fecha").text = current_date
            etree.SubElement(root_node, "Servicio").text = self.gls_default_service_type
            etree.SubElement(root_node, "Horario").text = ""
            etree.SubElement(root_node, "Bultos").text = bultos
            etree.SubElement(root_node, "Peso").text = "1"
            etree.SubElement(root_node, "Portes").text = "P"
            # importe tag
            importes = etree.SubElement(root_node, "Importes")
            etree.SubElement(importes, "Reembolso").text = "0"
            etree.SubElement(importes, "Retorno").text = retorno
            # remite tag
            remite = etree.SubElement(root_node, "Remite")
            etree.SubElement(remite, "Nombre").text = sender_id.name or ''
            etree.SubElement(remite, "Direccion").text = sender_id.street or ''
            etree.SubElement(remite, "Poblacion").text = sender_id.city or ''
            etree.SubElement(remite, "Pais").text = sender_id.country_id and sender_id.country_id.code or ''
            etree.SubElement(remite, "CP").text = str(sender_id.zip) or ''

            # Destinatario tag
            destinatario = etree.SubElement(root_node, "Destinatario")
            etree.SubElement(destinatario, "Nombre").text = receiver_id.name or ''
            etree.SubElement(destinatario, "Direccion").text = direccion or ''
            etree.SubElement(destinatario, "Poblacion").text = receiver_id.city or ''
            etree.SubElement(destinatario, "Pais").text = receiver_id.country_id.code or ''
            etree.SubElement(destinatario, "CP").text = str(receiver_id.zip) or ''
            etree.SubElement(destinatario, "Telefono").text = receiver_id.phone and receiver_id.phone.replace(' ', '')[
                                                                                    -10:] or ''
            etree.SubElement(destinatario, "Movil").text = receiver_id.phone and receiver_id.phone.replace(' ', '')[
                                                                                 -10:] or ''
            etree.SubElement(destinatario, "Email").text = 'test@test.com'
            etree.SubElement(destinatario, "NIF")
            etree.SubElement(destinatario, "Observaciones")
            # Referencias tag

            referencias = etree.SubElement(root_node, "Referencias")
            referencia = etree.SubElement(referencias, "Referencia")
            referencia.attrib['tipo'] = "C"
            referencia.text = picking.origin if picking.origin != '' else picking.name

        if data_label == 'get label':
            if picking.carrier_tracking_ref:
                code = picking.carrier_tracking_ref
            elif tracking:
                code = tracking
            else:
                code = picking.origin
            # EtiquetaEnvio tag
            etiqueta_envio = etree.SubElement(body_node, 'EtiquetaEnvio')
            etiqueta_envio.attrib['xmlns'] = "http://www.asmred.com/"
            etree.SubElement(etiqueta_envio, 'codigo').text = code
            etree.SubElement(etiqueta_envio, 'tipoEtiqueta').text = "PDF"

        if data_label == 'get tracking':
            getexpedition = etree.SubElement(body_node, 'GetExpCli')
            getexpedition.attrib['xmlns'] = "http://www.asmred.com/"
            etree.SubElement(getexpedition, 'codigo').text = picking.name
            etree.SubElement(getexpedition, 'uid').text = self.gls_senderid
        response = etree.tostring(master_node)
        _logger.info("GSL {} Data : {}".format(data_label, response))
        return response

    def gls_send_request_shipment(self, picking):

        request_shipment = self.generate_request_data("get shipment", picking)
        return self.gls_send_request(request_shipment, "get Shipment", picking)

    def gls_send_request_tracking(self, picking):
        request_tracking = self.generate_request_data('get tracking', picking)
        return self.gls_send_request(request_tracking, 'get Tracking', picking)

    def gls_send_request_label(self, tracking, picking):
        request_label = self.generate_request_data('get label', picking, tracking)
        return self.gls_send_request(request_label, 'get Label', picking)

    def gls_send_request(self, data, type_request, picking):

        try:
            result = requests.post(url=self.gls_url, data=data, headers={
                'charset': 'UTF-8',
                'Content-Type': 'text/xml',
            }, timeout=20)
            _logger.info("GLS {} Response: {}".format(type_request, Response(result).dict()))
            return Response(result).dict()
        except Exception as e:
            message_error = _("GLS Error in Response {} : E: {}".format(type_request, e))
            _logger.error(message_error)
            picking.message_post(body=message_error)
        return False


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    retorno = fields.Boolean("Retorno")
