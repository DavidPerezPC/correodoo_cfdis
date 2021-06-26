import xmlrpc.client as xc
import psycopg2 as psql
import base64
import xml.etree.ElementTree as ET
import sys
import pandas as pd
from pathlib import Path
import os
import re
from datetime import timedelta as td


# import numpy as np
from datetime import datetime as dt


url = 'https://grupoley-paralelo-2630664.dev.odoo.com'
db = 'grupoley-paralelo-2630664'
username = 'grupoley@tecnika.com.mx'
password = '1234%&'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

move_type_arg = sys.argv[1]
excel_file_arg = sys.argv[2]
sheet_name_arg = sys.argv[3]

CFDIFORMAT = 2


def get_folio_from_cfdi(xmlcfdi):

    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    #content64 = base64.b64encode(content)
    xmlcfdicontent = ET.fromstring(content)
    sinvoice = xmlcfdicontent.attrib['Folio']

    return sinvoice


def savecfdi(move_id, xmlcfdi, date_doc, date_due):

    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    content64 = base64.b64encode(content)
    xmlcfdicontent = ET.fromstring(content)
    serie = ''
    if 'Serie' in xmlcfdicontent.attrib.keys():
        serie = xmlcfdicontent.attrib['Serie'] + '-'
    elif 'serie' in xmlcfdicontent.attrib.keys():
        serie = xmlcfdicontent.attrib['serie'] + '-'

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

    # data = {
    #     'name': sinvoice,
    #     'payment_reference': sinvoice,
    # }
    if date_due:
        data = {'date': date_doc, 'invoice_date': date_doc, 'invoice_date_due': date_due}
        models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], data])

    return True

def doparalelo():

    try:
        domain = [[['type', '=', 'sale'], ['id', 'not in', [45]]]]
        journals = models.execute_kw(db, uid, password, 'account.journal', 'search_read', domain,
                                     {'order': 'id', 'fields': ['id', 'name']})
        #directorio = "cfdis/GUACAMAYA/PARALELO/"  PARTE 1
        directorio = "cfdis/GUACAMAYA/PARTE2/"  #PARTE 2

        for journal in journals:
            domain = [[['journal_id', '=', journal['id']],
                       ['move_type', '=', 'out_invoice'],
                       ['state', '=', 'draft'],
                       ['invoice_date', '<=', '2021-05-31'],
                       ]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'invoice_date', 'invoice_date_due',
                                                     'attachment_ids', 'edi_document_ids',
                                                     'payment_reference', 'state', 'ref', 'narration']})

            for inv in invoices:
                xmlfile = directorio + inv['narration'].replace("_parte2", "")
                payment_reference = inv['payment_reference']

                filenotfound = not Path(xmlfile).is_file()
                # if filenotfound:
                #     print("Factura {} con Archivo XML: {} en Diario {}, NO ENCONTRADO".format(payment_reference, xmlfile, journal['name']))
                #     continue

                fnstocall = ['action_post', 'action_process_edi_web_services']
                #elimino cualquier attachment
                print("Diario: {}, Procesando Factura {}".format(journal['name'], payment_reference), end=', ')

                # if inv['state'] != 'draft':
                #     print("YA PROCESADA")
                #     continue

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                for att in inv['attachment_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                #guardo la fechas de factura, porque al confirmar se alteran
                invoice_date = inv['invoice_date']
                invoice_date_due = inv['invoice_date_due']

                #valido que tenga error el timbrado y confirmo la factura y genero con el error del CFDI
                dicttoupdate = {}
                if inv['l10n_mx_edi_usage'] or filenotfound:
                    dicttoupdate = {'l10n_mx_edi_usage': False}
                    dicttoupdate.update({'name': payment_reference})

                if dicttoupdate:
                   models.execute_kw(db, uid, password, 'account.move', 'write',
                                     [[inv['id']], dicttoupdate])
                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                    except Exception as err:
                        pass
                    if filenotfound:
                        break
                try:
                    if not filenotfound:
                        savecfdi(inv['id'], xmlfile, invoice_date, invoice_date_due)
                    print("procesada")
                except Exception as err:
                    print("Error: {}".format(repr(err)))

    except Exception as err:
        print(repr(err))

    return

def docfdis(move_type=move_type_arg, excel_file=excel_file_arg, sheet_name=sheet_name_arg):

    try:
        dt = pd.read_excel(excel_file, sheet_name)
        xmlfile = ''
        directorio = "cfdis/"
        for exl_row in dt.iterrows():
            xmlfile = directorio + exl_row[1]['edi_document']
            payment_reference = exl_row[1]['payment_reference']
            if not Path(xmlfile).is_file():
                print("Factura {} con Archivo XML: {}, NO ENCONTRADO".format(payment_reference, xmlfile))
                continue

            domain = [[['payment_reference', '=', str(payment_reference)],
                       ['move_type', '=', move_type]]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'invoice_date', 'invoice_date_due', 'currency_id'
                                                     'attachment_ids', 'edi_document_ids',
                                                     'payment_reference', 'state', 'ref']})
            fnstocall = ['action_post', 'action_process_edi_web_services']
            if not invoices:
                print("Factura {} , no encontrada en Odoo".format(exl_row[1]['payment_reference']))
                continue

            for inv in invoices:
                #elimino cualquier attachment
                print("Procesando Factura {}".format(inv['payment_reference']), end=', ')

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

                #valido que tenga error el timbrado y confirmo la factura y genero con el error del CFDI
                dicttoupdate = {}
                if inv['l10n_mx_edi_usage']:
                    dicttoupdate = {'l10n_mx_edi_usage': False}

                if dicttoupdate:
                   models.execute_kw(db, uid, password, 'account.move', 'write',
                                     [[inv['id']], dicttoupdate])
                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                    except Exception as err:
                        pass

                savecfdi(inv['id'], xmlfile, invoice_date, invoice_date_due)
                print("UUID y XML agregados")

    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    doparalelo()
