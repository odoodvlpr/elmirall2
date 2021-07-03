from odoo import fields, models
import uuid
import base64
import tempfile


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    default_printer_id = fields.Many2one(comodel_name='printing.printer', string="Default Printer")

    def send_shipping(self, pickings):
        res = super(DeliveryCarrier, self).send_shipping(pickings)
        print_label = self.env['ir.config_parameter'].sudo().get_param('print_node.print.delivery.labels')
        send_idempotency = self.env['ir.config_parameter'].sudo().get_param('print_node.avoid.duplicity')
        if print_label:
            for picking in pickings:
                if picking.binary_label:
                    printer = self.env.user.default_printer_id or picking.carrier_id.default_printer_id
                    if printer:
                        if send_idempotency:
                            idempotency = str(uuid.uuid5(uuid.NAMESPACE_OID, picking.name))
                        else:
                            idempotency = None
                        fp = tempfile.mktemp(suffix='.pdf')
                        f = open(fp, 'wb')
                        f.write(base64.b64decode(picking.binary_label))
                        f.close()
                        self.env['printing.printer'].submit_job(
                            int(printer.id_printer),
                            "pdf",
                            fp,
                            title=picking.name,
                            idempotency_key=idempotency
                        )
                if picking.url_label:
                    printer = self.env.user.default_printer_id or picking.carrier_id.default_printer_id
                    if not printer:
                        return res
                    if send_idempotency:
                        idempotency = str(uuid.uuid5(uuid.NAMESPACE_OID, picking.name))
                    else:
                        idempotency = None
                    self.env['printing.printer'].submit_job(
                        int(printer.id_printer),
                        "url",
                        picking.url_label
                        ,
                        title=picking.name,
                        idempotency_key=idempotency
                    )

        return res
