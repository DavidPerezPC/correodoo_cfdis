import xmlrpc.client as xc
import psycopg2 as psql
import base64
import xml.etree.ElementTree as ET
import sys
# import numpy as np
from datetime import datetime


# def get_conexion(host='192.168.0.14', port=5432, dbname='GMM', user= 'openerp', password='0p3n3rp'):
# 	return psql.connect("host='%s' port=%s dbname='%s' user='%s' password='%s'" % (host, port, dbname, user, password))

url = 'http://localhost:8069'
db = 'vedra'
#url = 'https://quinval-capacitacion-2.odoo.com'
#db = 'quinval-capacitacion-2'
username = 'david.perez@pcsystems.mx'
password = 'lze456'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

invoiceid_arg =  sys.argv[1]
CFDIFORMAT = 2

def savecfdi(move_id, xmlcfdi):
    #self.env['ir.attachment'].create(
    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    content64 = base64.b64encode(content)
    xmlcfdicontent = ET.fromstring(content)
    sinvoice = 'F-' + xmlcfdicontent.attrib['Folio']

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
    #cfdi = 314
    data = {
        'attachment_id': cfdi,
        'state': 'sent',
        'error': False,
    }
    domain = [[['move_id', '=', move_id]]]
    edidoc = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
                                      {'fields': ['id', 'name']})
    models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edidoc[0]['id']], data])

    data = {
        'name': sinvoice,
        'payment_reference': sinvoice,
    }
    models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], data])

    return True

def docfdis(invoiceid=int(invoiceid_arg)):

    try:
        domain = [[['id', '=', invoiceid]]]
        invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                      {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                  'attachment_ids', 'edi_document_ids']})

        attcflds = models.execute_kw( db, uid, password, 'ir.attachment', 'fields_get', [])
        ediflds = models.execute_kw( db, uid, password, 'account.edi.document', 'fields_get', [])

        fnstocall = ['action_post', 'action_process_edi_web_services']
        for inv in invoices:
            #primero valido que tenga error el timrado y confirmo la factura y genero con el error del CFDI
            if inv['l10n_mx_edi_usage']:
                models.execute_kw(db, uid, password, 'account.move', 'write',
                                  [[inv['id']], {'l10n_mx_edi_usage': False}])
            for i in range(0, 2):
                try:
                    models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                except Exception as err:
                    pass

            # try:
            #     models.execute_kw(db, uid, password, 'account.move', 'action_post', [[int(inv['id'])]])
            # except Exception as err:
            #     pass
            #
            # try:
            #     models.execute_kw(db, uid, password, 'account.move', 'action_process_edi_web_services',
            #                       [[int(inv['id'])]])
            # except Exception as err:
            #     pass

            cfdifile = '/Users/turbo/Downloads/F-4499.xml'
            savecfdi(inv['id'], cfdifile)
            print("ID: {}. NUMERO: {}. ID CLIENTE: {}".format(inv['id'], inv['name'], inv['partner_id']))
            print("Attachments")
            for att in inv['attachment_ids']:
                domain = [[['id', '=', att]]]
                docto = models.execute_kw(db, uid, password, 'ir.attachment', 'search_read', domain,
                                          {'fields': [x for x in attcflds.keys()]})
                print(docto)

            print("Edis")
            for edi in inv['edi_document_ids']:
                domain = [[['id', '=', edi]]]
                docto = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
                                          {'fields': [x for x in ediflds.keys()]})
                print(docto)

    except Exception as err:
        print(repr(err))

if __name__ == "__main__":
    docfdis()

