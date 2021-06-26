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


# def get_conexion(host='192.168.0.14', port=5432, dbname='GMM', user= 'openerp', password='0p3n3rp'):
# 	return psql.connect("host='%s' port=%s dbname='%s' user='%s' password='%s'" % (host, port, dbname, user, password))

#url = 'http://localhost:8069'
#db = 'vedra'
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

move_type_arg = sys.argv[1]
excel_file_arg = sys.argv[2]
sheet_name_arg = sys.argv[3]
serie_doc_arg = sys.argv[4]

CFDIFORMAT = 2


def get_folio_from_cfdi(xmlcfdi):

    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    #content64 = base64.b64encode(content)
    xmlcfdicontent = ET.fromstring(content)
    sinvoice = xmlcfdicontent.attrib['Folio']

    return sinvoice


def savecfdi(move_id, xmlcfdi, seriedoc, date_doc, date_due):
    #self.env['ir.attachment'].create(
    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    content64 = base64.b64encode(content)
    xmlcfdicontent = ET.fromstring(content)
    sinvoice = seriedoc + xmlcfdicontent.attrib['Folio']

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

    data = {
        'name': sinvoice,
        'payment_reference': sinvoice,
    }
    if date_due:
        data.update({'date': date_doc, 'invoice_date': date_doc, 'invoice_date_due': date_due})
    models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], data])

    return True


def dopandas():

    try:
        dt = pd.read_excel('customer_invoices.xlsx', 'DOLARES')
        xmlfile = ''
        for exl_row in dt.iterrows():
            xmlfile = "cfdis/" + exl_row[1]['Nombre XML'] + ".xml"
            if not Path(xmlfile).is_file():
                print("Factura {} con Archivo XML: {}, NO ENCONTRADO".format(exl_row[1]['edi_document'],
                                                                             xmlfile))
                continue

            domain = [[['payment_reference', '=', exl_row[1]['edi_document']],
                       ['move_type', '=', 'out_invoice']]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'attachment_ids', 'edi_document_ids',
                                                     'payment_reference', 'state']})
            fnstocall = ['action_post', 'action_process_edi_web_services']
            if not invoices:
                print("Factura {} , no encontrada en Odoo".format(exl_row[1]['edi_document']))
                continue

            for inv in invoices:
                #elimino cualquier attachment
                print("Procesando Factura {}".format(inv['payment_reference']), end=', ')

                if inv['state'] != 'draft':
                    print("YA PROCESADA")
                    continue

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                for att in inv['attachment_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                #valido que tenga error el timbrado y confirmo la factura y genero con el error del CFDI
                #if inv['l10n_mx_edi_usage']:
                #    models.execute_kw(db, uid, password, 'account.move', 'write',
                #                      [[inv['id']], {'l10n_mx_edi_usage': False}])
                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                    except Exception as err:
                        pass

                savecfdi(inv['id'], xmlfile)
                print("UUID y XML agregados")

    except Exception as err:
        print(repr(err))

    return


def getoriginalcfdiuuid(ref):

    ref = 'SAQFC-' + ref
    domain = [[['name', '=', ref],
               ['move_type', '=', 'out_invoice']]]
    invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'l10n_mx_edi_cfdi_uuid',
                                                     'payment_reference', 'state', 'ref']})
    original_cfdi = False
    if invoices:
        inv = invoices[0]
        original_cfdi = inv['l10n_mx_edi_cfdi_uuid']
        original_cfdi = "01|{}".format(original_cfdi) if original_cfdi else False

    return original_cfdi


def docfdis(move_type=move_type_arg, excel_file=excel_file_arg, sheet_name=sheet_name_arg, serie_doc=serie_doc_arg):
#out_refund customer_refunds.xlsx FEBRERO NCSAQ-
    try:
        dt = pd.read_excel(excel_file, sheet_name)
        xmlfile = ''
        directorio = "cfdis/"
        for exl_row in dt.iterrows():
            xmlfile = directorio + exl_row[1]['Nombre XML'] + ".xml"
            payment_reference = exl_row[1]['edi_document']
            if not Path(xmlfile).is_file():
                print("Factura {} con Archivo XML: {}, NO ENCONTRADO".format(payment_reference, xmlfile))
                continue

            domain = [[['payment_reference', '=', str(payment_reference)],
                       ['move_type', '=', move_type]]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'attachment_ids', 'edi_document_ids',
                                                     'payment_reference', 'state', 'ref']})
            fnstocall = ['action_post', 'action_process_edi_web_services']
            if not invoices:
                print("NC {} , no encontrada en Odoo".format(exl_row[1]['edi_document']))
                continue

            for inv in invoices:
                #elimino cualquier attachment
                print("Procesando NC {}".format(inv['payment_reference']), end=', ')

                if inv['state'] != 'draft':
                    print("YA PROCESADA")
                    continue

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                for att in inv['attachment_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                #valido que tenga error el timbrado y confirmo la factura y genero con el error del CFDI
                #dicttoupdate = {'l10n_mx_edi_usage': False}
                dicttoupdate = {}
                originalcfdiuuid = False
                #if move_type == 'out_refund':
                #    originalcfdiuuid = getoriginalcfdiuuid(inv['ref'])
                #    dicttoupdate.update({'l10n_mx_edi_origin': originalcfdiuuid})

                if originalcfdiuuid:
                   models.execute_kw(db, uid, password, 'account.move', 'write',
                                     [[inv['id']], dicttoupdate])
                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                    except Exception as err:
                        pass

                savecfdi(inv['id'], xmlfile, serie_doc, '2021-03-16',  '2021-06-14')
                print("UUID y XML agregados")

    except Exception as err:
        print(repr(err))

    return


def get_duedate(date_charge, daycredit):
    return dt.strftime(dt.strptime(date_charge[:10], "%Y-%m-%d") + td(days=daycredit), "%Y-%m-%d")


def update_movelines(invoice_id, term_ids, partner_account_id, date_order, payment_reference):
    #account_move_line.name
    #account_move_line.date
    #account_move_line.date_maturity
    domain = [[['id', 'in', term_ids]]]
    terms = models.execute_kw(db, uid, password, 'account.payment.term.line', 'search_read', domain,
                                 {'fields': ['id', 'days', 'value'], 'order': 'sequence'})

    date_due_ = []
    for i in range(0, len(terms)):
        date_due_.append(get_duedate(date_order, terms[i]['days']))
    date_return = date_due_[0]

    domain = [[['id', '=', invoice_id]]]
    invoice = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                 {'fields': ['id', 'name', 'line_ids']})[0]

    domain = [[['id', 'in', invoice['line_ids']],
               ['account_id', '=', partner_account_id]
            ]]
    mlines = models.execute_kw(db, uid, password, 'account.move.line', 'search_read', domain,
                                 {'fields': ['id', 'name']})

    for i in range(0, len(mlines)):
        lineid = mlines[i]['id']
        models.execute_kw(db, uid, password, 'account.move.line', 'write',
                          [[lineid], {'date': date_order, 'name': payment_reference,
                                      'date_maturity': date_due_[i]}])

    return date_return


def docfdisprod(move_type=move_type_arg, excel_file=excel_file_arg, sheet_name=sheet_name_arg, serie_doc=serie_doc_arg):
#out_invoice ventas_marzo.xlsx Sheet1 SAQFC-
    try:
        directorio = "cfdis/MARZO 21"
        dt = pd.read_excel(excel_file, sheet_name)
        xmlfile = ''
        xmlfiles = os.listdir(directorio)

        for exl_row in dt.iterrows():
            folio_excel = str(int(exl_row[1]['Factura']))
            if not folio_excel:
                print("El Pedido {} no tiene factura asignada".format(exl_row[1]['Referencia del pedido']))
                continue
            xmlfile = "2021-03 F-{}".format(folio_excel)
            r = re.compile(xmlfile)
            lstxml = list(filter(r.match, xmlfiles))
            if not lstxml:
                print("Factura {} sin Archivo XML, NO ENCONTRADO".format(xmlfile))
                continue
            xmlfile = "{}/{}".format(directorio, lstxml[0])

            sfolio = get_folio_from_cfdi(xmlfile)
            if sfolio != str(folio_excel):
                print("La factura {} en la orden de Compra {} "
                      "no coincide con la del XML {}".format(folio_excel, exl_row[1]['Referencia del pedido'],
                                                             sfolio))
            else:
                print("Compra {}, con Factura {} OK".format(exl_row[1]['Referencia del pedido'],
                                                            sfolio), end=", ")

            domain = [[['id', '=', exl_row[1]['ID']]]]
            so = models.execute_kw(db, uid, password, 'sale.order', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'payment_term_id',
                                                     'currency_id', 'date_order', 'invoice_ids']})[0]

            # if so['currency_id'][1] != 'MXN':
            #     print("es en moneda extranjera")
            #     continue

            sale_date = so['date_order']
            partner_id = so['partner_id'][0]
            if not so['invoice_ids']:
                print( "NO tiene factura generada")
                continue
            invoice_id = so['invoice_ids'][0]
            so_payment_id = 1
            if so['payment_term_id']:
                so_payment_id = so['payment_term_id'][0]

            domain = [[['id', '=', partner_id]]]
            partner = models.execute_kw(db, uid, password, 'res.partner', 'search_read', domain,
                                     {'fields': ['property_payment_term_id', 'property_account_receivable_id']})
            partner_payment_id = partner[0]['property_payment_term_id'][0]
            partner_account_id = partner[0]['property_account_receivable_id'][0]
            payment_reference = "{}{}".format(serie_doc, exl_row[1]['Factura'])
            dicttoupdate = {'payment_reference': payment_reference}
            term_lines = False
            if so_payment_id != partner_payment_id:
                domain = [[['id', '=', partner_payment_id]]]
                dicttoupdate.update({'invoice_payment_term_id': partner_payment_id})
            else:
                domain = [[['id', '=', so_payment_id]]]
            payment_term = models.execute_kw(db, uid, password, 'account.payment.term', 'search_read', domain,
                                             {'fields': ['id', 'line_ids']})
            term_lines = payment_term[0]['line_ids']
            domain = domain = [[['id', '=', invoice_id]]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'attachment_ids', 'edi_document_ids',
                                                     'payment_reference', 'state', 'ref']})
            fnstocall = ['action_post', 'action_process_edi_web_services']
            if not invoices:
                print("Factura {} , no encontrada en Odoo".format(exl_row[1]['Factura']))
                continue

            for inv in invoices:
                #elimino cualquier attachment
                if inv['state'] != 'draft':
                    print("YA PROCESADA")
                    continue

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                for att in inv['attachment_ids']:
                    models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

                #valido que tenga error el timbrado y confirmo la factura y genero con el error del CFDI
                #dicttoupdate.update({'l10n_mx_edi_usage': False})
                originalcfdiuuid = False
                if move_type == 'out_refund':
                    originalcfdiuuid = getoriginalcfdiuuid(inv['ref'])
                    dicttoupdate.update({'l10n_mx_edi_origin': originalcfdiuuid})

                models.execute_kw(db, uid, password, 'account.move', 'write',
                                  [[inv['id']], dicttoupdate])
                date_due = False
                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                        date_due = update_movelines(inv['id'], term_lines, partner_account_id, sale_date,
                                                    payment_reference)
                    except Exception as err:
                        pass

                savecfdi(inv['id'], xmlfile, serie_doc, sale_date, date_due)
                print("UUID y XML agregados")

    except Exception as err:
        print(repr(err))

    return



def deleteborrado():

    invoice_id = [2904]
    #[2410, 2430]
    #[2092]
    #[4069]
    #[2226]
    #[4955]
    #[5174]
    #[3199]
    #[3198, 4883, 2343, 2647]
    domain = domain = [[['id', 'in', invoice_id]]]
    invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                   {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                          'attachment_ids', 'edi_document_ids',
                                         'payment_reference', 'state', 'ref']})

    for inv in invoices:
        for att in inv['edi_document_ids']:
            models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

        for att in inv['attachment_ids']:
            models.execute_kw(db, uid, password, 'ir.attachment', 'unlink', [att])

        #for att in inv['edi_document_ids']:
        #     models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[att], {'state': 'sent'}])

#    models.execute_kw(db, uid, password, 'account.move', 'write', [[invoice_id], {'name': 'NCSAQ-1767'}])


def readxml(inv, xmlcfdi, cfdi=None):

    move_id = inv['id']
    if cfdi:
        data = {
            'attachment_id': cfdi,
            'state': 'sent',
            'error': False,
        }
        domain = [[['move_id', '=', move_id]]]
        edidoc = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
                                          {'fields': ['id', 'name']})
        models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edidoc[0]['id']], data])
    else:
        contentraw = open(xmlcfdi).read()
        content = contentraw.encode('UTF-8')
        xmlcfdicontent = ET.fromstring(content)
        serie = 'SAQFC-'
        sinvoice = serie + xmlcfdicontent.attrib['Folio']
        tipocambio = float(xmlcfdicontent.attrib['TipoCambio'])
        date_doc = xmlcfdicontent.attrib['Fecha'][:10]
        condiciones = int(xmlcfdicontent.attrib['CondicionesDePago'].replace(" dias", ""))
        date_due = dt.strftime(dt.strptime(date_doc, "%Y-%m-%d") + td(days=condiciones), "%Y-%m-%d")

        domain = [[['currency_id', '=', inv['currency_id'][0]],
                   ['name', '=', date_doc],
                   ['company_id', '=', inv['company_id'][0]]
                   ]]

        currency = models.execute_kw(db, uid, password, 'res.currency.rate', 'search_read', domain,
                                     {'fields': ['id', 'name', 'rate']})

        if currency:
            if 1 / tipocambio != currency[0]['rate']:
                dict = {'rate': 1 / tipocambio}
                models.execute_kw(db, uid, password, 'res.currency.rate', 'write', [[currency[0]['id']], dict])
        else:
            dict = {'currency_id': currency[0]['id'], 'name': date_doc, 'rate': 1 / tipocambio}
            models.execute_kw(db, uid, password, 'res.currency.rate', 'create', [dict])
        data = {
            'name': sinvoice,
            'payment_reference': sinvoice,
        }
        data.update({'date': date_doc, 'invoice_date': date_doc, 'invoice_date_due': date_due})
        if inv['l10n_mx_edi_usage']:
            data.update({'l10n_mx_edi_usage': False})
        models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], data])

    return True


def cfdis_usd(move_type=move_type_arg, excel_file=excel_file_arg, sheet_name=sheet_name_arg, serie_doc=serie_doc_arg):
#out_refund customer_refunds.xlsx FEBRERO NCSAQ-
    try:
        dt = pd.read_excel(excel_file, sheet_name)
        xmlfile = ''
        directorio = "cfdis/QUINVALUSD/"
        for exl_row in dt.iterrows():
            payment_reference = exl_row[1]['edi_document']
            xmlfile = "{}{}.xml".format(directorio, payment_reference)
            if not Path(xmlfile).is_file():
                print("Factura {} con Archivo XML: {}, NO ENCONTRADO".format(payment_reference, xmlfile))
                continue

            domain = [[['name', '=', payment_reference],
                       ['move_type', '=', move_type]]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'attachment_ids', 'edi_document_ids', 'currency_id',
                                                     'company_id', 'payment_reference', 'state', 'ref']})
            fnstocall = ['action_post', 'action_process_edi_web_services']
            if not invoices:
                print("Factura {} , no encontrada en Odoo".format(exl_row[1]['edi_document']))
                continue

            for inv in invoices:
                #elimino cualquier attachment
                print("Procesando Factura {}".format(inv['payment_reference']), end=', ')

                for att in inv['edi_document_ids']:
                    models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

                if inv['state'] == 'posted':
                    try:
                        models.execute_kw(db, uid, password, 'account.move', 'button_draft', [[int(inv['id'])]])
                    except Exception as err:
                        pass

                try:
                    readxml(inv, xmlfile)
                except Exception as err:
                    pass

                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                    except Exception as err:
                        pass

                try:
                    readxml(inv, xmlfile, inv['attachment_ids'][0])
                except Exception as err:
                    pass
                print("UUID y XML agregados")

    except Exception as err:
        print(repr(err))

    return


# def updatecfdi(move_id, xmlcfdi, sinvoice, l10nmxusage):
#
#     contentraw = open(xmlcfdi).read()
#
#     data = {
#         'name':  "{}.xml".format(sinvoice),
#         'res_name': sinvoice,
#         'description': "Mexican invoice CFDI generated for the {} document.".format(sinvoice),
#         'type': 'binary',
#         'res_id': move_id,
#         'res_model': 'account.move',
#         'raw': contentraw,
#         'mimetype': 'application/xml',
#         'company_id': 1,
#     }
#     cfdi = models.execute_kw(db, uid, password, 'ir.attachment', 'create', [data])
#     data = {
#         'attachment_id': cfdi,
#         'state': 'sent',
#         'error': False,
#     }
#     domain = [[['move_id', '=', move_id]]]
#     edidoc = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
#                                       {'fields': ['id', 'name']})
#     models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edidoc[0]['id']], data])
#
#     data = {
#         'l10n_mx_edi_usage': l10nmxusage,
#     }
#     models.execute_kw(db, uid, password, 'account.move', 'write', [[move_id], data])
#
#     return True

def updatecfdi(attch_id, edi_id, xmlcfdi):

    contentraw = open(xmlcfdi).read()

    data = {
        'raw': contentraw,
    }
    models.execute_kw(db, uid, password, 'ir.attachment', 'write', [[attch_id], data])

    data = {
            'state': 'sent',
            'error': False,
        }
    models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edi_id], data])

    return True


def cfdis_update(move_type=move_type_arg, excel_file=excel_file_arg, sheet_name=sheet_name_arg, serie_doc=serie_doc_arg):
#out_refund customer_refunds.xlsx FEBRERO NCSAQ-
    try:
        dt = pd.read_excel(excel_file, sheet_name)
        xmlfile = ''
        directorio = "/Users/turbo/Downloads/"
        for exl_row in dt.iterrows():
            payment_reference = int(exl_row[1]['edi_document'])
            xmlfile = "{}{}.xml".format(directorio, exl_row[1]['Nombre XML'])
            if not Path(xmlfile).is_file():
                print("Factura {} con Archivo XML: {}, NO ENCONTRADO".format(payment_reference, xmlfile))
                continue

            domain = [[['id', '=', payment_reference]]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'attachment_ids', 'edi_document_ids', 'currency_id',
                                                     'company_id', 'payment_reference', 'state', 'ref']})
            if not invoices:
                print("Factura {} , no encontrada en Odoo".format(exl_row[1]['edi_document']))
                continue

            for inv in invoices:
                #elimino cualquier attachment
                print("Procesando Factura {}".format(inv['payment_reference']), end=', ')

                try:
                    updatecfdi(inv['attachment_ids'][0], inv['edi_document_ids'][0], xmlfile)
                    #models.execute_kw(db, uid, password, 'account.move', 'action_process_edi_web_services', [[int(inv['id'])]])
                except Exception as err:
                    pass
                print("UUID y XML agregados")

    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    docfdis()
    #docfdisprod()
    #cfdis_usd()
    #deleteborrado()
    #cfdis_update()