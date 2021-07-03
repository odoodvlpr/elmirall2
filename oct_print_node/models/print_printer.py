# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.http import request
from odoo.exceptions import ValidationError
from tempfile import mkstemp
import os
import logging
from .printnodeapi import Gateway
import base64

_logger = logging.getLogger(__name__)


class PrinterPrintNode(models.Model):
    _inherit = "printing.printer"

    company_id = fields.Many2one('res.company', 'Print Node Company')
    user_ids = fields.One2many(comodel_name='res.users', inverse_name='default_printer_id', string='Users')
    carrier_ids = fields.One2many(comodel_name='delivery.carrier', inverse_name='default_printer_id', string='Carriers')
    printer_type = fields.Selection([('print_node', 'Print Node')], required=True, default='print_node')
    id_printer = fields.Char('id Printer')
    print_node_job_ids = fields.One2many(comodel_name='print.node.job',
                                         inverse_name='printer_id',
                                         string='Jobs',
                                         ondelete='cascade')

    def print_document(self, report, content, **print_opts):
        if len(self) != 1:
            _logger.error(
                'Print Node called with %s but singleton is'
                'expected. Check printers configuration.' % self)
            return super(PrinterPrintNode, self).print_document(
                report, content, **print_opts)
        if self.printer_type != 'print_node':
            return super(PrinterPrintNode, self).print_document(
                report, content, **print_opts)

        fd, file_name = mkstemp()
        try:
            os.write(fd, content)
        finally:
            os.close(fd)

        options = self.print_options(report, **print_opts)
        _logger.debug(
            'Going to Print via Print Node Printer %s' % self.system_name)

        try:
            self.submit_job(int(self.id_printer), options.get('format', 'pdf'), file_name, options)
            _logger.info("Printing Job: '%s'" % file_name)
        except Exception as e:
            _logger.error(
                'Could not submit job to Pint Node. This is what we get:\n'
                '%s' % e)
        return True

    @api.model
    def update_print_node_printers(self, company=None):
        server_id = self.env.ref('oct_print_node.printing_server_print_node')
        apiKey = self.env['ir.config_parameter'].sudo().get_param('print_node.api.key')
        gateway = Gateway(url=server_id.address, apikey=apiKey)
        printers = gateway.printers()

        for print_node_printer in printers:
            printer = self.env['printing.printer'].search(
                [('id_printer', '=', print_node_printer.id), ('company_id', '=', company.id)], limit=1)
            if not printer and print_node_printer.state == 'online':
                printer.create({
                    'name': print_node_printer.name,
                    'system_name': print_node_printer.name,
                    'model': print_node_printer.description,
                    'id_printer': print_node_printer.id,
                    'printer_type': 'print_node',
                    'status': self.get_pn_printer_status(print_node_printer.state),
                    'company_id': company.id,
                    'status_message': print_node_printer.state,
                    'server_id': server_id.id,
                })
        return True

    def update_print_node_printers_status(self, company):
        server_id = self.env.ref('oct_print_node.printing_server_print_node')
        apiKey = self.env['ir.config_parameter'].sudo().get_param('print_node.api.key')
        gateway = Gateway(url=server_id.address, apikey=apiKey)
        printers = self.env['printing.printer'].search([('company_id', '=', company.id)])
        for printer in printers:
            print_node_printer = gateway.printers(printer=int(printer.id_printer))
            if print_node_printer:
                printer.write({'status': self.get_pn_printer_status(print_node_printer.state),
                               'status_message': print_node_printer.state})
        return True

    def action_update_print_node_printer_jobs(self):
        self.ensure_one()
        server_id = self.env.ref('oct_print_node.printing_server_print_node')
        apiKey = self.env['ir.config_parameter'].sudo().get_param('print_node.api.key')
        gateway = Gateway(url=server_id.address, apikey=apiKey)
        printer_jobs = gateway._computers.get_printjobs(printer=int(self.id_printer))
        printer_jobs.sort(key=lambda k: k.id)
        for job in printer_jobs:
            job_id = job.id
            existing_job = self.print_node_job_ids.search([('job_id', '=', job_id)])
            if existing_job and existing_job.status != job.state:
                existing_job.write({'status': job.state})
            else:
                job_values = {
                    'name': job.title,
                    'job_id': job.id,
                    'status': job.state,
                    'printer_id': self.id,
                    'job_response': job
                }
                # job status must be updated via webhook
                self.env['print.node.job'].create(job_values)
        return True

    @staticmethod
    def get_pn_printer_status(connectionstatus):
        if connectionstatus == 'online':
            status = 'available'
        elif connectionstatus == 'offline':
            status = 'unavailable'
        else:
            status = 'unknown'
        return status

    def submit_job(self, printerid, jobtype, jobsrc, options=None, title=False, idempotency_key=None):
        """
        Send print jobs to Pint Node API
        :param printerid: Printer ID
        :param jobtype: Job Type: ['qweb-pdf', 'pdf', 'png', 'jpeg'] # qweb-pdf for a rendered qweb report
        :param jobsrc: file path (for jobtype = pdf, png or jpeg) or a
            bytes array with the rendered document (for jobtype = qweb-pdf).
        :param options: To implement: paper size.
        :param title: Job title. Required for jobtype = qweb-pdf.
        :param idempotency_key: Unique key to identify the job and avoid print duplicity.
        :return:
        """
        # Check debug mode to avoid accidentally send print jobs
        server_mode = request.session.debug
        stage = os.environ.get('ODOO_STAGE', False)
        allow_print_dev = self.env['ir.config_parameter'].sudo().get_param('print_node.allow.dev')
        if (server_mode != '' or stage != 'production') and not allow_print_dev:
            raise ValidationError(_("Print jobs not permitted in debug or staging mode. "
                                    "Anyway, if you need to print you must allow printing in debug mode on settings."))

        if jobtype in ['pdf', 'png', 'jpeg']:
            data = self.read_file(jobsrc)
            b64data = base64.b64encode(data).decode('utf-8')
        elif jobtype == 'qweb-pdf':
            b64data = base64.b64encode(jobsrc).decode('utf-8')
        elif jobtype == 'url':
            b64data = jobsrc
        else:
            raise Warning(_('Job type %s not implemented for print node printing') % jobtype)
        server_id = self.env.ref('oct_print_node.printing_server_print_node')
        apiKey = self.env['ir.config_parameter'].sudo().get_param('print_node.api.key')
        gateway = Gateway(url=server_id.address, apikey=apiKey)
        if not title and jobtype != 'qweb-pdf':
            title = jobsrc
        elif not title and jobtype == 'qweb-pdf':
            _logger.error("Is required a job title for a job type qweb-pdf")
            raise ValidationError(_("Is required a job title for a job type qweb-pdf"))
        if idempotency_key:
            # find a job with this idempotency_key to
            job = self.env['print.node.job'].search([('idempotency_key', '=', idempotency_key)])
            if job:
                _logger.error(_("Unable to sent this print job. Another job exist with the same idempotency key If you need to print this document please deactivate de duplicity protection in settings"))
                return False
        if jobtype != 'url':
            print_job = gateway.PrintJob(
                printer=printerid,
                base64=b64data,
                title=str(title),
                options=options,
                idempotency_key=idempotency_key)
        else:
            print_job = gateway.PrintJob(
                printer=printerid,
                uri=b64data,
                title=str(title),
                options=options,
                idempotency_key=idempotency_key)

        if print_job.id:
            # Create local print job
            printer_obj = self.search([('id_printer', '=', str(printerid))])
            job_values = {
                'name': str(title),
                'job_id': print_job.id,
                'status': 'new',
                'printer_id': printer_obj.id,
                'job_response': print_job,
                'idempotency_key': idempotency_key or False
            }
            _logger.info("JOB VALUES: %r", job_values)
            # job status must be updated via webhook
            self.env['print.node.job'].create(job_values)
            return print_job.id
        return False

    @api.model
    def read_file(self, pathname):
        """Read contents of a file and return content.
           Args:
             pathname: string, (path)name of file.
           Returns:
           string: contents of file.
        """
        try:
            f = open(pathname, 'rb')
            try:
                s = f.read()
            except IOError as error:
                _logger.info('Error reading %s\n%s', pathname, error)
            finally:
                f.close()
                return s
        except IOError as error:
            _logger.error('Error opening %s\n%s', pathname, error)
            return None


