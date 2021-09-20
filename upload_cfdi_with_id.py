import xmlrpc.client as xc
import base64
import xml.etree.ElementTree as ET
import sys
from pathlib import Path
import os

# url = 'https://grupoley.odoo.com'
# db = 'grupoley-ley-1910338'
# username = 'grupoley@tecnika.com.mx'
# password = '1234%&'
url = 'https://siam.odoo.com'
db = 'siam'
username = 'jdavid.paredes@outlook.com'
password = 'jwparedeS'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

CFDIFORMAT = 2

def savecfdi(move_id, xmlcfdi, dictoupdate):

    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    xmlcfdicontent = ET.fromstring(content)
    serie = ''
    if 'Serie' in xmlcfdicontent.attrib.keys():
        serie = xmlcfdicontent.attrib['Serie']
    elif 'serie' in xmlcfdicontent.attrib.keys():
        serie = xmlcfdicontent.attrib['serie']

    folio = '0000'
    if 'Folio' in xmlcfdicontent.attrib.keys():
        folio = xmlcfdicontent.attrib['Folio']
    elif 'folio' in xmlcfdicontent.attrib.keys():
        folio = xmlcfdicontent.attrib['folio']
    sinvoice = serie + folio
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
        'company_id': 1,
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

    if dictoupdate:
        models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], dictoupdate])

    return True

def updatecfdi():

    directorio = "/Users/turbo/Downloads/"
    doctos = [[77712,"INV-INV2021080117-MX-Invoice-3.3.xml"]]
    try:
        for doc in doctos:
            domain = [[['id', '=', doc[0]]]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'invoice_date', 'invoice_date_due',
                                                     'attachment_ids', 'edi_document_ids',
                                                     'payment_reference', 'state', 'ref', 'narration']})

            for inv in invoices:
                xmlfile = directorio + doc[1]

                filenotfound = not Path(xmlfile).is_file()
                if filenotfound:
                    print("Factura {} con Archivo XML: {}, NO ENCONTRADO".format(inv['name'], xmlfile))
                    continue

                fnstocall = ['action_post', 'action_process_edi_web_services']
                #elimino cualquier attachment
                print("Procesando Factura {}".format(inv['name'], end=', '))

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
                edi_usage = inv['l10n_mx_edi_usage'] or 'P01'

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
                    dicttoupdate = {'l10n_mx_edi_usage': edi_usage,
                                    'invoice_date': invoice_date,
                                    'invoice_date_due': invoice_date_due,
                    }                    
                    savecfdi(inv['id'], xmlfile, dicttoupdate)
                    print("procesada")
                except Exception as err:
                    print("Error: {}".format(repr(err)))

    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    updatecfdi()
