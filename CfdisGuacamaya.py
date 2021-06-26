import xmlrpc.client as xc
import psycopg2 as psql
import base64
#import xml.etree.ElementTree as ET
from lxml import etree as ET
import sys
import pandas as pd
from pathlib import Path
from glob import glob
import os
import re
from datetime import timedelta as td


# import numpy as np
from datetime import datetime as dtime

url = 'https://grupoley-pruebas-2496164.dev.odoo.com'
db = 'grupoley-pruebas-2496164'
username = 'grupoley@tecnika.com.mx'
password = '1234%&'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

receptor = {}
emisor = {}
diarios = {}

move_type_arg = sys.argv[1]
excel_file_arg = sys.argv[2]
sheet_name_arg = sys.argv[3]

CFDIFORMAT = 2
ACC_ID = 127
TAX_ID = 25
COMPANY_ID = 2 #Industrias Guacamaya
PRODUCT_ID = 9954 #9965

def fill_diarios(serie):

    if serie not in diarios.keys():
        domain = [[['code', '=', serie]]]
        diario = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
                                   {'fields': ['id', 'name']})[0]
        diarios.update({serie: diario['id']})

    return diarios[serie]


def fill_clientes():
    return


def fill_receptor():
    #xmlcfdicontent.findall('cfdi:Receptor', xmlcfdicontent.nsmap)[0].attrib['UsoCFDI']
    return


def read_xml_raw(xmlfile):
    contentraw = open(xmlfile).read()
    return contentraw

def get_data_from_cfdi(xmlcfdi):

    contentraw = open(xmlcfdi).read()
    content = contentraw.encode('UTF-8')
    xmlcfdicontent = ET.fromstring(content)
    inv_info = {
        'XmlRaw': contentraw,
        'Serie': xmlcfdicontent.attrib['Serie'],
        'Folio': xmlcfdicontent.attrib['Folio'],
    }
    #recetor_dict = xmlcfdicontent.findall('cfdi:Receptor', xmlcfdicontent.nsmap)[0].attrib

    return inv_info


def savecfdi(move_id, xmlcfdi, sinvoice):

    data = {
        'name':  "{}.xml".format(sinvoice),
        'res_name': sinvoice,
        'description': "Mexican invoice CFDI generated for the {} document.".format(sinvoice),
        'type': 'binary',
        'res_id': move_id,
        'res_model': 'account.move',
        'raw': xmlcfdi,
        'mimetype': 'application/xml',
        'company_id': COMPANY_ID,
    }
    cfdi = models.execute_kw(db, uid, password, 'ir.attachment', 'create', [data])
    data = {
        'attachment_id': cfdi,
        'state': 'sent',
        'error': False,
        'move_id': move_id,
        'edi_format_id': CFDIFORMAT,
    }
    models.execute_kw(db, uid, password, 'account.edi.document', 'create', [data])

    return True

def get_duedate(date_charge, daycredit):
    return dtime.strftime(dtime.strptime(date_charge[:10], "%Y-%m-%d") + td(days=daycredit), "%Y-%m-%d")


def get_partner_id(ref):

    #ESTA LOGICA ES PARA BUSCARLO DIRECTAMENTE EN EL CLIENTE
    # partner_id = None
    # domain = [[['ref', '=', ref], ['company_id', '=', COMPANY_ID]]]
    # customers = models.execute_kw(db, uid, password, 'res.partner', 'search_read', domain,
    #                              {'fields': ['id', 'name']})

    partner_id = None
    account_receivable_id = None
    #domain = [[['name', '=', ref], ['model', '=', 'res.partner']]]
    #customers = models.execute_kw(db, uid, password, 'ir.model.data', 'search_read', domain,
    #                             {'fields': ['id', 'res_id', 'name']})

    domain = [[['vat', '=', ref], ['parent_id', '=', False], ['company_id', '=', COMPANY_ID]]]
    customers = models.execute_kw(db, uid, password, 'res.partner', 'search_read', domain,
                                 {'fields': ['id', 'name']})

    if customers:
        partner_id = customers[0]['id']
        domain = [[['name', '=', 'property_account_receivable_id'],
                   ['res_id', '=', 'res.partner,{}'.format(partner_id)],
                   ['company_id', '=', COMPANY_ID]]]
        accs = models.execute_kw(db, uid, password, 'ir.property', 'search_read', domain,
                                      {'fields': ['id', 'res_id', 'value_reference', 'company_id']})
        if accs:
            account_receivable_id = int(accs[0]['value_reference'].replace('account.account,', ''))
        else:
            account_receivable_id = 98

    return partner_id, account_receivable_id

def readcfdisfromxml(move_type=move_type_arg, excel_file=excel_file_arg, sheet_name=sheet_name_arg):

    try:
        dt = pd.read_excel(excel_file, sheet_name)
        directorio = "/Users/turbo/OneDrive - DAVID ALBERTO PEREZ PAYAN/Proyectos/FILIALES-LEY/Guacamaya/FACTURAS_MUESTREO_ODOO/"
        xmlfiles = glob(directorio+'*.xml')
        domain = [[['type', '=', 'sale']]]
        journals = models.execute_kw(db, uid, password, 'account.journal', 'search_read', domain,
                                   {'fields': ['id', 'code', 'name']})
        customers = {}
        notfound = 0
        total = 0
        for xmlfile in xmlfiles:
            total += 1
            inv_data = get_data_from_cfdi(xmlfile)
            serie_folio = '{}-{}'.format(inv_data['Serie'], inv_data['Folio'])
            rows = dt[dt.isin([serie_folio]).any(1)]
            print("Procesando {}".format(serie_folio), end=", ")
            if len(rows) == 0:
                notfound += 1
                print("NO ENCONTRADO")
                continue

            for exl_row in rows.iterrows():
                print("ENCONTRADO")
                payment_reference = exl_row[1]['payment_reference']

                #busco el diario basado en el serie
                serie = payment_reference[0:payment_reference.find("-")]
                journal_id = next((index for (index, d) in enumerate(journals) if d["code"] == serie), None)
                if journal_id == None:
                    print("Serie {} no encontrada".format(serie))
                    continue

                # #busco si ya tengo el ID del cliente, sino lo encuentro lo agrego al diccionario
                # #customer_ref = exl_row[1]['partner_id'][4:]
                # customer_ref = exl_row[1]['rfc'].strip()
                # #customer_ref = customer_ref[customer_ref.find("_")+1:]
                # if customer_ref in customers.keys():
                #     partner_id = customers[customer_ref][0]
                #     acc_receivable_id = customers[customer_ref][1]
                # else:
                #     partner_id, acc_receivable_id = get_partner_id(customer_ref)
                #     if not partner_id:
                #         print("el cliente {} no esta registrado".format(exl_row[1]['partner_id']))
                #         continue
                #     customers.update({customer_ref: [partner_id, acc_receivable_id]})

                continue
                #lleno los datos de la factura y la creo
                inv_dict = {
                    'journal_id': journals[journal_id]['id'],
                    'invoice_date': dtime.strftime(exl_row[1]['invoice_date'], "%Y-%m-%d"),
                    'invoice_date_due': dtime.strftime(exl_row[1]['invoice_date_due'], "%Y-%m-%d"),
                    'partner_id': partner_id,
                    'payment_reference': payment_reference,
                    'name': payment_reference,
                    'narration': exl_row[1]['narration'],
                    'move_type': move_type,
                    'company_id': COMPANY_ID,
                }
                invoice_id = models.execute_kw(db, uid, password, 'account.move', 'create', [inv_dict])

                #lleno el detalle y lo creo
                inv_line_dict = {
                    'move_id': invoice_id,
                    'product_id': 30899,
                    'quantity': 1,
                    'price_unit': exl_row[1]['invoice_line_ids/price'],
                    'tax_ids': [[6, 0, [TAX_ID]], ],
                    'company_id': COMPANY_ID,
                    'account_id': ACC_ID,
                    'exclude_from_invoice_tab': False,
                    #'name': payment_reference,
                }
                models.execute_kw(db, uid, password, 'account.move.line', 'create', [inv_line_dict],
                                  {'context': {'check_move_validity': False}})

                print("grabado con ID {}".format(invoice_id))
                #creo los documentos de XML y los agrego a la factura
                #savecfdi(invoice_id, xmlfile, serie)

                #aplico la factura
                #models.execute_kw(db, uid, password, 'account.move', 'action_post', [[invoice_id]])

        print("Encontados {} de {}".format(total-notfound, total))
    except Exception as err:
        print(repr(err))

    return


def readcfdis(move_type=move_type_arg, excel_file=excel_file_arg, sheet_name=sheet_name_arg):

    try:
        dt = pd.read_excel(excel_file, sheet_name)
        directorio = "/Users/turbo/OneDrive - DAVID ALBERTO PEREZ PAYAN/Proyectos/FILIALES-LEY/Guacamaya/FACTURAS_ODOO/"
        xmlfiles = os.listdir(directorio)
        domain = [[['type', '=', 'sale']]]
        journals = models.execute_kw(db, uid, password, 'account.journal', 'search_read', domain,
                                   {'fields': ['id', 'code', 'name']})
        customers = {}
        notfound = 0
        total = 0
        for exl_row in dt.iterrows():
            total += 1
            print(total, end=" ")
            payment_reference = exl_row[1]['payment_reference']
            if not payment_reference:
                continue
            print("Procesando {}".format(payment_reference), end=", ")

            #valido que existe el archivo
            if not isinstance(exl_row[1]['edi_document'], str):
                notfound += 1
                continue

            xmlfile = directorio + exl_row[1]['edi_document']
            if not Path(xmlfile).is_file():
                notfound += 1
                #print("Archivo XML: {}, NO ENCONTRADO".format(xmlfile))
                continue

            #busco el diario basado en el serie
            serie = payment_reference[0:payment_reference.find("-")]
            journal_id = next((index for (index, d) in enumerate(journals) if d["code"] == serie), None)
            if journal_id == None:
                print("Serie {} no encontrada".format(serie))
                continue

            #busco si ya tengo el ID del cliente, sino lo encuentro lo agrego al diccionario
            #customer_ref = exl_row[1]['partner_id'][4:]
            customer_ref = exl_row[1]['rfc'].strip()
            if customer_ref == 'XEXX010101000':
                continue
            #customer_ref = customer_ref[customer_ref.find("_")+1:]
            if customer_ref in customers.keys():
                partner_id = customers[customer_ref][0]
                acc_receivable_id = customers[customer_ref][1]
            else:
                partner_id, acc_receivable_id = get_partner_id(customer_ref)
                if not partner_id:
                    print("el cliente {} no esta registrado".format(exl_row[1]['partner_id']))
                    continue
                customers.update({customer_ref: [partner_id, acc_receivable_id]})

            #lleno los datos de la factura y la creo
            inv_dict = {
                'journal_id': journals[journal_id]['id'],
                'invoice_date': exl_row[1]['invoice_date'], #dtime.strftime(exl_row[1]['invoice_date'], "%Y-%m-%d"),
                'invoice_date_due': exl_row[1]['invoice_date_due'], #dtime.strftime(exl_row[1]['invoice_date_due'], "%Y-%m-%d"),
                'partner_id': partner_id,
                'payment_reference': payment_reference,
                'name': payment_reference,
                'narration': exl_row[1]['narration'],
                'move_type': move_type,
                'company_id': COMPANY_ID,
            }
            invoice_id = models.execute_kw(db, uid, password, 'account.move', 'create', [inv_dict])

            #lleno el detalle y lo creo
            inv_line_dict = {
                'move_id': invoice_id,
                'product_id': PRODUCT_ID,
                'quantity': 1,
                'price_unit': exl_row[1]['invoice_line_ids_price_unit'],
                'tax_ids': [[6, 0, [TAX_ID]], ],
                'company_id': COMPANY_ID,
                'account_id': ACC_ID,
                'exclude_from_invoice_tab': False,
                #'name': payment_reference,
            }
            models.execute_kw(db, uid, password, 'account.move.line', 'create', [inv_line_dict],
                              {'context': {'check_move_validity': False}})

            inv_line_dict = {
                'move_id': invoice_id,
                'debit': exl_row[1]['invoice_line_ids_price_unit'],
                'company_id': COMPANY_ID,
                'account_id': acc_receivable_id,
                'exclude_from_invoice_tab': True,
                # 'name': payment_reference,
            }
            models.execute_kw(db, uid, password, 'account.move.line', 'create', [inv_line_dict],
                              {'context': {'check_move_validity': False}})

            #data = {
            #    'l10n_mx_edi_usage': False,
            #}
            models.execute_kw(db, uid, password, 'account.move', 'action_post', [[invoice_id]])
            try:
                models.execute_kw(db, uid, password, 'account.move', 'action_process_edi_web_services', [[invoice_id]])
            except Exception as e:
                pass
            print("grabado con ID {}".format(invoice_id))
            domain = [[['id', '=', invoice_id]]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'partner_id', 'l10n_mx_edi_usage',
                                                     'attachment_ids', 'edi_document_ids',
                                                     'payment_reference', 'state', 'ref']})
            inv = invoices[0]
            for att in inv['edi_document_ids']:
                models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])

            #creo los documentos de XML y los agrego a la factura
            savecfdi(invoice_id, read_xml_raw(xmlfile), payment_reference)

            #aplico la factura
            #models.execute_kw(db, uid, password, 'account.move', 'action_post', [[invoice_id]])

        print("Encontados {} de {}".format(total-notfound, total))
    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    readcfdisfromxml()
    #readcfdis()