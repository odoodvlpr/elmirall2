from odoo import exceptions, fields, http, _
from odoo.http import request, Controller, route, Response
import json
import logging

_logger = logging.getLogger(__name__)


class PrintNodeWebhookController(Controller):
    @route('/printnode_webhooks', type='json', auth="none", csrf=False, methods=['POST'], save_session=False)
    def print_node(self, **post):
        secret = request.httprequest.headers.get('X-PrintNode-Webhook-Secret')
        webhook_secret = request.env['ir.config_parameter'].sudo().get_param('print_node.webhook.secret')
        if secret == webhook_secret:
            _logger.info("SECRET MATCH")
            # update printer status or print job status
            message = request.jsonrequest
            _logger.info("PRINT NODE MESSAGE: %r", message)
        headers = {'X-PrintNode-Webhook-Status': 'ok'}
        return Response(status=200, headers=headers)
