import xmlrpc.client as xc
import base64
#import xml.etree.ElementTree as ET
from lxml import etree as ET
import sys
from pathlib import Path
import os
import re
from datetime import timedelta as td
from datetime import datetime as dt


# url = 'https://grupoley.odoo.com'
# db = 'grupoley-ley-1910338'
# username = 'grupoley@tecnika.com.mx'
# password = '1234%&'

#url = 'https://25.0.189.81:4344'
#db = 'odoo'
#username = 'desarrollo@gasomarshal.mx'
#password = 'Lynx2021.'

#url = 'https://quinval-testing.odoo.com'
#db = 'quinval-testing'
url = 'https://quinval.odoo.com'
db = 'quinval'
username = 'quinval@quinval.com'
password = 'SAQ14122'

common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

company_id_arg = sys.argv[1]
directory_arg = sys.argv[2]
anyparam_arg = sys.argv[3]

CFDIFORMAT = 2


def check_currency(company_id, currency_id, date_doc, curr_rate):

    domain = [[['currency_id', '=', currency_id],
                ['name', '=', date_doc],
                ['company_id', '=', company_id]
            ]]

    currency = models.execute_kw(db, uid, password, 'res.currency.rate', 'search_read', domain,
                                    {'fields': ['id', 'name', 'rate']})

    rate_id = False
    if currency:
        rate_id = currency[0]['id']
        if 1 / curr_rate != currency[0]['rate']:
            dict = {'rate': 1 / curr_rate}
            models.execute_kw(db, uid, password, 'res.currency.rate', 'write', [[currency[0]['id']], dict])
    else:
        dict = {'currency_id': currency_id, 'name': date_doc, 'rate': 1 / curr_rate, 'company_id': company_id}
        rate_id = models.execute_kw(db, uid, password, 'res.currency.rate', 'create', [dict])

    return rate_id

def get_payment_method(payment_method):

    domain = [[
        ['code', '=', payment_method]
    ]]
    pm = models.execute_kw(db, uid, password, 'l10n_mx_edi.payment.method', 'search_read', 
                            domain)[0]

    return pm['id']

def get_folio_from_cfdi(invoice, xmlcfdi, serie="QVAFC-"):

    tfd = {"tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
            "xsi": "http://www.sat.gob.mx/TimbreFiscalDigital http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd"
            }


    invoice_id = invoice['id']
    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    #content64 = base64.b64encode(content)
    xmlcfdicontent = ET.fromstring(content)
    tipocfdi = xmlcfdicontent.attrib['TipoDeComprobante']
    sinvoice = serie + xmlcfdicontent.attrib['Folio']
    date_doc = xmlcfdicontent.attrib['Fecha'][:10]
    currency = xmlcfdicontent.attrib['Moneda']
    payment_method = False
    related_cfdi = False
    if tipocfdi == 'I':
        payment_method = xmlcfdicontent.attrib['MetodoPago']
    elif tipocfdi == 'E':
        related_node = xmlcfdicontent.findall('cfdi:CfdiRelacionados', xmlcfdicontent.nsmap)[0]
        related_type = related_node.attrib['TipoRelacion']
        related_node = xmlcfdicontent.findall('cfdi:CfdiRelacionados/cfdi:CfdiRelacionado', xmlcfdicontent.nsmap)[0].attrib
        related_cfdi = related_node['UUID']
        related_cfdi = "{}|{}".format(related_type, related_cfdi)
    payment_way = xmlcfdicontent.attrib['FormaPago']
    receptor = xmlcfdicontent.findall('cfdi:Receptor', xmlcfdicontent.nsmap)[0].attrib
    usage = receptor['UsoCFDI']

    curr_rate = 1
    if currency == 'USD':
        curr_rate = float(xmlcfdicontent.attrib['TipoCambio'])
        check_currency(invoice['company_id'][0], invoice['currency_id'][0], date_doc, curr_rate)

    invoice_number = sinvoice
    data = {
        'name': invoice_number,
        #'payment_reference': invoice_number,
        'date': date_doc,
        'invoice_date': date_doc,
        'l10n_mx_edi_payment_method_id': get_payment_method(payment_way),
        'l10n_mx_edi_payment_policy': payment_method,
        'l10n_mx_edi_usage': usage,
        'l10n_mx_edi_origin': related_cfdi,
    }
    models.execute_kw(db, uid, password, 'account.move', 'write', [[invoice_id], data])
    
    return invoice_number

def savecfdi(inv, xmlcfdi, company_id, lcreaedidoc=False, invoice_number=""):

    contentraw = open(xmlcfdi).read()
    if lcreaedidoc:
        sinvoice = invoice_number
    else:
        dicttoupdate = { 
            'invoice_date': inv['invoice_date'],
            'invoice_date_due': inv['invoice_date_due'],
            'l10n_mx_edi_usage': inv['l10n_mx_edi_usage'], 
        }
        sinvoice = inv['name']

    move_id = inv['id']
    #si sinvoice es diferente del payment_referece, eso quiere decir que el docto esta mal relacionado
    data = {
        'name':  "{}.xml".format(sinvoice),
        'res_name': sinvoice,
        'description': "Mexican invoice CFDI generated for the {} document.".format(sinvoice),
        'type': 'binary',
        'res_id': move_id,
        'res_model': 'account.move',
        'raw': contentraw,
        'mimetype': 'application/xml',
        'company_id': company_id,
    }
    cfdi = models.execute_kw(db, uid, password, 'ir.attachment', 'create', [data])
    data = {
        'attachment_id': cfdi,
        'state': 'sent',
        'error': False,
    }

    domain = [[['move_id', '=', move_id]]]
    edidoc = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
                                    {'fields': ['id', 'name']})
    models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edidoc[0]['id']], data])
 
    if not lcreaedidoc:
        models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], data])
   
    return True

#se utiliza cuando se afectan facturas y notas de creditos directas
def cfdi_direct(company_id=int(company_id_arg), directorio=directory_arg, anyparam=anyparam_arg):

    try:
        domain = [[['type', '=', 'sale'],
                    ['company_id', '=', company_id]
                ]]
        journals = models.execute_kw(db, uid, password, 'account.journal', 'search_read', domain,
                                     {'order': 'id', 'fields': ['id', 'name']})

        for journal in journals:
            domain = [[['journal_id', '=', journal['id']],
                       ['move_type', '=', 'out_invoice'],
                        ['state', '=', 'draft'],
                       ['invoice_date', '<=', '2020-12-31'],
                    ]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'invoice_date', 'invoice_date_due', 'currency_id',
                                                     'attachment_ids', 'edi_document_ids', 'company_id',
                                                     'payment_reference', 'state', 'ref', 'narration']})

            for inv in invoices:
                xmlfile = inv['narration'] or ''
                xmlfile = "{}{}.xml".format(directorio, xmlfile.strip())
                payment_reference = inv['payment_reference']

                filenotfound = not Path(xmlfile).is_file()
                if filenotfound:
                    print("Factura {} con Archivo XML: {} en Diario {}, NO ENCONTRADO".format(payment_reference, xmlfile, journal['name']))
                    continue

                fnstocall = ['action_post', 'action_process_edi_web_services']
                #elimino cualquier attachment
                print("Diario: {}, Procesando Factura {}".format(journal['name'], payment_reference), end=', ')

                if inv['state'] != 'draft':
                    print("YA PROCESADA")
                    continue

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                for att in inv['attachment_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                #guardo la fechas de factura, porque al confirmar se alteran
                invoice_date = inv['invoice_date']
                invoice_date_due = inv['invoice_date_due']
                edi_usage = inv['l10n_mx_edi_usage']

                #valido que tenga error el timbrado y confirmo la factura y genero con el error del CFDI
                dicttoupdate = {}
                if edi_usage:
                    dicttoupdate = {'l10n_mx_edi_usage': False}

                if dicttoupdate:
                   models.execute_kw(db, uid, password, 'account.move', 'write',
                                     [[inv['id']], dicttoupdate])
                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                    except Exception as err:
                        pass

                try:
                    savecfdi(inv, xmlfile, company_id)
                    print("procesada")
                except Exception as err:
                    print("Error: {}".format(repr(err)))

    except Exception as err:
        print(repr(err))

    return

#para notas de credito, evaluar si se puede dejar para facturas o notas decredito
def cfdi_direct_nc(company_id=int(company_id_arg), directorio=directory_arg, anyparam=anyparam_arg):

    try:
        domain = [[['type', '=', 'sale'],
                    ['company_id', '=', company_id]
                ]]
        journals = models.execute_kw(db, uid, password, 'account.journal', 'search_read', domain,
                                     {'order': 'id', 'fields': ['id', 'name']})
        journal_type = anyparam
        for journal in journals:
            domain = [[ ['journal_id', '=', journal['id']],
                        ['move_type', '=', journal_type],
                        ['state', '=', 'draft'],
                    ]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'invoice_date', 'invoice_date_due', 'currency_id',
                                                     'attachment_ids', 'edi_document_ids', 'company_id',
                                                     'payment_reference', 'state', 'ref', 'narration'],
                                            'order': 'id'})

            for inv in invoices:
                xmlfile = inv['narration'] or ''
                xmlfile = "{}{}.xml".format(directorio, xmlfile)
                payment_reference = inv['name']

                filenotfound = not Path(xmlfile).is_file()
                if filenotfound:
                    print("CFDI {} con Archivo XML: {} en Diario {}, NO ENCONTRADO".format(payment_reference, xmlfile, journal['name']))
                    continue

                # fnstocall = ['action_post', 'action_process_edi_web_services']

               #elimino cualquier attachment
                print("Diario: {}, Procesando CFDI {}".format(journal['name'], payment_reference), end=', ')

                if inv['state'] != 'draft':
                    print("YA PROCESADA")
                    continue

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                for att in inv['attachment_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                #guardo la fechas de factura, porque al confirmar se alteran
                invoice_date = inv['invoice_date']
                invoice_date_due = inv['invoice_date_due']
                edi_usage = inv['l10n_mx_edi_usage']

                #valido que tenga error el timbrado y confirmo la factura y genero con el error del CFDI
                # dicttoupdate = {}
                # if edi_usage:
                #     dicttoupdate = {'l10n_mx_edi_usage': False}

                # if dicttoupdate:
                #    models.execute_kw(db, uid, password, 'account.move', 'write',
                #                      [[inv['id']], dicttoupdate])
                #for i in range(0, 2):
                try:
                    sinvoice = get_folio_from_cfdi(inv, xmlfile, "NCQVA-")
                    models.execute_kw(db, uid, password, 'account.move', 'action_post', [[int(inv['id'])]])
                except Exception as err:
                    print("Error: {}".format(repr(err)))
                    continue

                try:
                    savecfdi(inv, xmlfile, company_id, True, sinvoice)
                    print("procesada con folio {}".format(sinvoice))
                except Exception as err:
                    print("Error: {}".format(repr(err)))

    except Exception as err:
        print(repr(err))

    return


#se utliza cuando se geneera desde el sale order
def cfdi_from_sale_order(company_id=int(company_id_arg), directorio=directory_arg, anyparam=anyparam_arg):

    try:
        dates = anyparam.split(",") 
        date_from = dates[0]
        date_to = dates[1]      
        xmlfile = ''

        domain = [[
                ['company_id', '=', company_id],
                ['state', '=', 'sale'],            
                ['validity_date', '>=', date_from],
                ['validity_date', '<=', date_to],
                ]]
        sos = models.execute_kw(db, uid, password, 'sale.order', 'search_read', domain,
                {'fields': ['id', 'name', 'partner_id', 'payment_term_id', 
                            'validity_date', 'currency_id', 'date_order', 
                            'invoice_ids', 'note'],
                    'order': 'name'})

        for so in sos:

            xmlfile = so['note']
            if xmlfile:
                xmlfile = "{}{}.xml".format(directorio, xmlfile)
            
            if not xmlfile or not Path(xmlfile).is_file():
                print("No se encontró XML para el Pedido {}".format(so['name']))
                continue

            if not so['invoice_ids']:
                print("El Pedido {} no tiene factura asignada".format(so['name']))
                continue

            print("Procesando Pedido {}.".format(so['name']), end=". ")

            #sale_date = so['validity_date']
            invoices = so['invoice_ids']
            #so_payment_id = so['payment_term_id'][0] or 1
            #domain = [[['id', '=', so_payment_id]]]
            #payment_term = models.execute_kw(db, uid, password, 'account.payment.term', 'search_read', domain,
            #                                 {'fields': ['id', 'line_ids']})
            #term_lines = payment_term[0]['line_ids']

            for invoice_id in invoices:
                domain  = [[['id', '=', invoice_id]]]
                inv = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                        {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                    'attachment_ids', 'edi_document_ids', 'company_id',
                                                    'currency_id', 'state', 'ref']})[0]
                #fnstocall = ['action_post', 'action_process_edi_web_services']

                #elimino cualquier attachment
                if inv['state'] != 'draft':
                    print("Factura {} YA PROCESADA".format(inv['name']))
                    continue

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                for att in inv['attachment_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                date_due = False
                #for i in range(0, 2):
                try:
                    sinvoice = get_folio_from_cfdi(inv, xmlfile)
                    models.execute_kw(db, uid, password, 'account.move', 'action_post', [[int(inv['id'])]])
                except Exception as err:
                    pass


                savecfdi(inv, xmlfile, company_id, True, sinvoice)
                print("UUID y XML agregados")

    except Exception as err:
        print(repr(err))

    return


def deletecfdi(move_id=int(company_id_arg), model=directory_arg, anyparam=anyparam_arg):

    invoice_id = [move_id]
    domain = domain = [[['id', 'in', invoice_id]]]
    invoices = models.execute_kw(db, uid, password, model, 'search_read', domain,
                                   {'fields': ['id', 'name', 'partner_id',
                                          'attachment_ids', 'edi_document_ids'
                                          ]})

    for inv in invoices:
        for att in inv['edi_document_ids']:
            models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

        for att in inv['attachment_ids']:
            models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

if __name__ == "__main__":
    #cfdi_directo()
    #cfdi_direct_nc()
    cfdi_from_sale_order()
    #deletecfdi()

