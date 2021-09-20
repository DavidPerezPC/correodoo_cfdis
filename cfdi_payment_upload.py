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
url = 'https://quinval.odoo.com'
db = 'quinval'
username = 'quinval@quinval.com'
password = 'SAQ14122'
# url = 'https://siam.odoo.com'
# db = 'siam'
# username = 'jdavid.paredes@outlook.com'
# password = 'jwparedeS'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

payment_id_arg = sys.argv[1]
xml_file_arg = sys.argv[2]
delete_arg = sys.argv[3]

CFDIFORMAT = 2

def updatecfdi(move, xmlcfdi, company_id, delete=False):

    sname = xmlcfdi[xmlcfdi.rfind("/")+1:]
    move_id = move['move_id'][0]
    contentraw = open(xmlcfdi).read()

    data = {
        'name':  sname,
        'res_name': move['name'],
        'description': "Mexican Payment CFDI generated for the {} document.".format(move['name']),
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
    if delete:
        data.update( {'move_id': move_id, 'edi_format_id': CFDIFORMAT} )
        cfdi = models.execute_kw(db, uid, password, 'account.edi.document', 'create', [data])
    else:
        domain = [[['move_id', '=', move_id]]]
        edidoc = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
                                        {'fields': ['id', 'name']})
        models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edidoc[0]['id']], data])

    return True

def payment_cfdi(payment_id=int(payment_id_arg), xmlfile=xml_file_arg, delete=delete_arg):
 
    try:
        if not Path(xmlfile).is_file():
            print("Pago {} con Archivo XML: {}, NO ENCONTRADO".format(payment_id, xmlfile))
 
        domain = [[['id', '=', payment_id]]]
        payments = models.execute_kw(db, uid, password, 'account.payment', 'search_read', domain,
                                        {'fields': ['id', 'name', 'move_id', 'state', 'company_id'
                                        ]})

        move = False
        if payments:
            move = payments[0]
        else:
            print("El Pago {} , no existe en Odoo".format(payment_id))
            return

        company_id = payments[0]['company_id'][0]        
        print("Procesando Movimiento {}".format(move['name']), end=', ')

        try:
            if delete:
                domain = [[ ['id', '=', move['move_id'][0]] ]]
                moves = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                        {'fields': ['id', 'name', 
                                                    'attachment_ids', 'edi_document_ids']})
                for mov in moves:
                    for att in mov['edi_document_ids']:
                        models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                    for att in mov['attachment_ids']:
                        models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])
            updatecfdi(move, xmlfile, company_id, delete)
        except Exception as err:
            pass
        print("UUID y XML agregados")
    
    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    payment_cfdi()