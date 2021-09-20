import xmlrpc.client as xc
import base64
import xml.etree.ElementTree as ET
import sys
from pathlib import Path
import os
from datetime import timedelta as td
from datetime import datetime as dt


# def get_conexion(host='192.168.0.14', port=5432, dbname='GMM', user= 'openerp', password='0p3n3rp'):
# 	return psql.connect("host='%s' port=%s dbname='%s' user='%s' password='%s'" % (host, port, dbname, user, password))

# url = 'http://localhost:8069'
# db = 'quinval'
# url = 'https://quinval.odoo.com'
# db = 'quinval'
# username = 'quinval@quinval.com'
# password = 'SAQ14122'
url = 'https://siam.odoo.com'
db = 'siam'
username = 'jdavid.paredes@outlook.com'
password = 'jwparedeS'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

move_type_arg = sys.argv[1]
excel_file_arg = sys.argv[2]
sheet_name_arg = sys.argv[3]
serie_doc_arg = sys.argv[4]

CFDIFORMAT = 2

def updatecfdi(move_id, xmlcfdi, sinvoice, l10nmxusage):

    contentraw = open(xmlcfdi).read()

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

    # data = {
    #     'l10n_mx_edi_usage': l10nmxusage,
    # }
    # models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], data])

    return True

# def updatecfdi(attch_id, edi_id, xmlcfdi):

#     contentraw = open(xmlcfdi).read()

#     data = {
#         'raw': contentraw,
#     }
#     models.execute_kw(db, uid, password, 'ir.attachment', 'write', [[attch_id], data])

#     data = {
#             'state': 'sent',
#             'error': False,
#         }
#     models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edi_id], data])

#     return True


def cfdis_update(move_id=int(move_type_arg), excel_file=excel_file_arg, sheet_name=sheet_name_arg, serie_doc=serie_doc_arg):
#out_refund customer_refunds.xlsx FEBRERO NCSAQ-
 
    try:
        xmlfile = excel_file
        if not Path(xmlfile).is_file():
            print("Factura {} con Archivo XML: {}, NO ENCONTRADO".format(move_id, xmlfile))
 
        domain = [[['id', '=', move_id]]]
        invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                        {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                    'attachment_ids', 'edi_document_ids', 'currency_id',
                                                    'company_id', 'payment_reference', 'state', 'ref']})
        if not invoices:
            print("Factura {} , no encontrada en Odoo".format(move_id))

        for inv in invoices:
            #elimino cualquier attachment
            print("Procesando Factura {}".format(inv['payment_reference']), end=', ')

            try:
                updatecfdi(move_id, xmlfile, sheet_name, "")
                #updatecfdi(inv['attachment_ids'][0], inv['edi_document_ids'][0], xmlfile)
                #models.execute_kw(db, uid, password, 'account.move', 'action_process_edi_web_services', [[int(inv['id'])]])
            except Exception as err:
                pass
            print("UUID y XML agregados")
    
    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    cfdis_update()