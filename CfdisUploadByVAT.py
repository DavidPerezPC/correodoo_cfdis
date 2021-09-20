import xmlrpc.client as xc
from lxml import etree as ET
import sys
import pandas as pd
from pathlib import Path
from glob import glob
import os
from datetime import timedelta as td
from datetime import datetime as dtime

#url = 'http://localhost:8069'
url = 'http://quinval.odoo.com'
db = 'quinval'
username = 'quinval@quinval.com'
password = 'SAQ14122'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

receptor = {}
emisor = {}
diarios = {}

BLOCKED_RFC = ['PTI820402RJ6', 'AME150630V17', 'APM040824HL3', 'BIO150512AC3', 'AIN9405277K5',
               'OSY111220DM5', 'NAN0307243I9', 'DIT860622TN7', 'ACA070903K59', 'LUX080208DQ2',
               'AAL960229CV2', 'AGR171228B21']

CXC_ACC_ID = 4005 #id de la cuenta por cobrar por defecto
CXP_ACC_ID = 5555 #id de la cuenta por pagar por defecto
ACC_EXPENSE_ID = 4036#id de la cuenta de acreedores
PRODUCT_ID = 1819 #producto al que se le asignan los gastos
COMPANY_ID = 2
JOURNAL_ID = 33
XML_DIR = ['gastos']
#XML_DIR = ['1-ENERO', '2-FEBRERO', '3-MARZO', '4-ABRIL', '5-MAYO']
IVAS = {'002': {'160000': 29, '000000': 28, '080000': 30}, #002=IVA, Llave: Tasa de Iva, Valor: ID en la base de datos
        '003': {'060000': 34, '090000': 35, '000000': 36, '080000': 37},  #003=IEPS, Llave: Tasa de IEPS, Valor: ID en la base de datos
        }
RETENCIONES = {'002': {'040000': 22, '100000': 24, '106700': 27, '106670': 27, '106667': 27 }, #002=IIVA, Llave: Tasa de IVA, Valor. ID en la base datos
               '001': {'100000': 25}, #001=ISR, Llave: Tasa de ISR, Valor: ID en la base de datos
               }

CFDIFORMAT = 2

def read_xml_raw(xmlfile):
    return open(xmlfile).read()


def get_data_from_cfdi(xmlcfdi):

    tfd = {"tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
            "xsi": "http://www.sat.gob.mx/TimbreFiscalDigital http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd"
            }


    contentraw = read_xml_raw(xmlcfdi)
    content = contentraw.encode('UTF-8')
    xmlcfdicontent = ET.fromstring(content)
    tfd.update(xmlcfdicontent.nsmap)
    header = xmlcfdicontent.attrib
    uuid = xmlcfdicontent.findall('cfdi:Complemento/tfd:TimbreFiscalDigital', tfd)[0].attrib['UUID']
    if header['TipoDeComprobante'] != 'I':
        return {}

    inv_info = {
        'XmlRaw': contentraw,
        'Serie': header['Serie'] if 'Serie' in header.keys() else '',
        'Folio': header['Folio'] if 'Folio' in header.keys() else uuid,
        'Fecha': header['Fecha'][:10],
        'Credito': header['CondicionesDePago'] if 'CondicionesDePago' in header.keys() else False,
        'TipoDeComprobante': header['TipoDeComprobante'],
        'Emisor': xmlcfdicontent.findall('cfdi:Emisor', tfd)[0].attrib,
        'Detalle': [],
        'UUID': uuid,
        'Total': header['Total'],
    }
    if "Nombre" not in inv_info['Emisor'].keys():
        inv_info['Emisor'].update({'Nombre': inv_info['Emisor']['Rfc']})

    conceptos = xmlcfdicontent.findall('cfdi:Conceptos/cfdi:Concepto', tfd)
    for concepto in conceptos:
        impuestos = concepto.findall('cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado', tfd)
        retenciones = concepto.findall('cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion', tfd)
        taxes_ = []
        for tax in impuestos:
            tipo = tax.attrib['Impuesto']
            tasa = tax.attrib['TasaOCuota'][2:]
            if tipo not in IVAS.keys():
                print("Impuestos {} no definidos".format(tipo), end=", ")
                continue
            if tasa not in IVAS[tipo].keys():
                print("Tasa {} no esta definido en el Impuesto {}".format(tasa, tipo), end=", ")
                continue
            taxes_.append(IVAS[tipo][tasa])

        for tax in retenciones:
            tipo = tax.attrib['Impuesto']
            tasa = tax.attrib['TasaOCuota'][2:]
            if tipo not in RETENCIONES.keys():
                print("Retenciones {} no definidos".format(tipo), end=", ")
                continue
            if tasa not in RETENCIONES[tipo].keys():
                print("Tasa {} no esta definido en la Retencion {}".format(tasa, tipo), end=", ")
                continue
            taxes_.append(RETENCIONES[tipo][tasa])

        inv_info['Detalle'].append([concepto.attrib, taxes_])

    return inv_info


def _invoice_is_registered(rfc, sinvoice):

    doc_name = "{}_{}.xml".format(rfc, sinvoice)
    domain = [[['name', '=', doc_name],
                ['company_id', '=', COMPANY_ID],
                ['res_model', '=', 'account.move']
            ]]
    doc = models.execute_kw(db, uid, password, 'ir.attachment', 'search_read', domain,
                                 {'fields': ['id', 'name', 'company_id']})

    return len(doc) > 0 

def savecfdi(move_id, inv_data, rfc, sinvoice):

    data = {
        'name':  "{}_{}.xml".format(rfc, sinvoice),
        'res_name': sinvoice,
        'description': "Mexican invoice CFDI received from {}.".format(rfc),
        'type': 'binary',
        'res_id': move_id,
        'res_model': 'account.move',
        'raw': inv_data['XmlRaw'],
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


def get_partner_id(ref, nombre):

    #ESTA LOGICA ES PARA BUSCARLO DIRECTAMENTE EN EL CLIENTE

    account_payable_id = CXP_ACC_ID
    domain = [[['vat', '=', ref]]]
    contact = models.execute_kw(db, uid, password, 'res.partner', 'search_read', domain,
                                 {'fields': ['id', 'name', 'company_id']})

    if contact:
        partner_id = contact[0]['id']
        if contact[0]['company_id'] and contact[0]['company_id'][0] != COMPANY_ID: 
            models.execute_kw(db, uid, password, 'res.partner', 'write',
                    [[partner_id], {'company_id': False}])
            
        domain = [[['name', '=', 'property_account_payable_id'],
                   ['res_id', '=', 'res.partner,{}'.format(partner_id)],
                   ['company_id', '=', COMPANY_ID]]]
        accs = models.execute_kw(db, uid, password, 'ir.property', 'search_read', domain,
                                      {'fields': ['id', 'res_id', 'value_reference', 'company_id']})
        if accs:
            account_payable_id = int(accs[0]['value_reference'].replace('account.account,', ''))

    else:
        data = {'name': nombre, 'vat': ref, 'type': 'contact',
                'company_type': 'company', 'l10n_mx_type_of_operation': '85',
                'country_id': 156}
        partner_id = models.execute_kw(db, uid, password, 'res.partner', 'create', [data])

    return partner_id, account_payable_id

def get_expense_inday(partner_id, inv_data):
    #['amount_total', '=', inv_data['Total']]
    domain = [[['partner_id', '=', partner_id],
               ['invoice_date', '=', inv_data['Fecha']],
               ]]
    expenses = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain)

    return len(expenses) > 0

def invoice_lines(inv):

    lines = inv['Detalle']
    inv_lines = []
    for line in lines:
        inv_lines.append([0,0, 
        {
            #'move_id': invoice_id,
            'product_id': PRODUCT_ID,
            'name': line[0]['Descripcion'],
            'quantity': 1,
            'price_unit': float(line[0]['Importe']),
            'tax_ids': [[6, 0, line[1]], ],
            #'account_id': ACC_EXPENSE_ID,
        }])
        #models.execute_kw(db, uid, password, 'account.move.line', 'create', [data],
        #                   {'context': {'check_move_validity': False}})

    return inv_lines


def readcfdisfromxml():

    directorio = "/Users/turbo/Downloads/quinvalcfdis/quinval/"
    try:
        for dir in XML_DIR:
            xmlfiles = glob('{}{}/*.xml'.format(directorio, dir))
            contacts = {}
            total = 0
            total_processed = 0
            total_wrong = 0
            total_nodata = 0
            total_noadded = 0
            for xmlfile in xmlfiles:

                total += 1
                try:
                    inv_data = get_data_from_cfdi(xmlfile)
                except Exception as err:
                    print("Error en el archivo: {}".format(xmlfile))
                    total_wrong += 1
                    pass
                    continue

                if not inv_data:
                    print("Archivo sin datos suficientes: {}".format(xmlfile))
                    total_nodata += 1
                    continue

                serie_folio = inv_data['Serie']
                if serie_folio:
                    serie_folio = '{}{}'.format(inv_data['Serie'], inv_data['Folio'])
                else:
                    serie_folio = inv_data['Folio']
                rfc = inv_data['Emisor']['Rfc']

                if _invoice_is_registered(rfc, serie_folio):
                    total_processed += 1
                    continue

                try:
                    #busco si ya tengo el ID del cliente, sino lo encuentro lo agrego al diccionario
                    if rfc in contacts.keys():
                        partner_id = contacts[rfc][0]
                        acc_payable_id = contacts[rfc][1]
                    else:
                        partner_id, acc_payable_id = get_partner_id(rfc, inv_data['Emisor']['Nombre'])
                        if not partner_id:
                            print("el contacto {} no se pudo registrar".format(rfc))
                            continue
                        contacts.update({rfc: [partner_id, acc_payable_id]})

                    #if rfc in BLOCKED_RFC:
                    #    continue

                    # if get_expense_inday(partner_id, inv_data):
                    #     print("El folio {} del RFC {} ya tiene un comprobante el mismo dia".format(serie_folio, rfc))
                    #     continue

                    print("Procesando {}".format(serie_folio), end=", ")

                    #lleno los datos de la factura y la creo
                    inv_lines = invoice_lines(inv_data)
                    inv_dict = {
                        'journal_id': JOURNAL_ID,
                        'invoice_date': inv_data['Fecha'],
                        'date': inv_data['Fecha'],
                        'partner_id': partner_id,
                        'narration': inv_data['Credito'],
                        'move_type': 'in_invoice',
                        'company_id': COMPANY_ID,
                        'ref': serie_folio,
                        'payment_reference': serie_folio,
                        'l10n_mx_edi_cfdi_uuid': inv_data['UUID'],
                        'invoice_line_ids': inv_lines,
                    }
   
                    invoice_id = models.execute_kw(db, uid, password, 'account.move', 'create', [inv_dict])

                    print("grabado con ID {}".format(invoice_id))
                    #creo los documentos de XML y los agrego a la factura
                    savecfdi(invoice_id, inv_data, rfc, serie_folio)

                except Exception as err:
                    total_noadded += 1
                    print("ERROR: {}".format(repr(err)))
                    pass

                #aplico la factura
                #models.execute_kw(db, uid, password, 'account.move', 'action_post', [[invoice_id]])

            print("Encontrados {}, Ya Procesados: {}, No Agregados: {}, XML Erroneo: {}, XML diferente Ingreso: {}".format(total, total_processed, total_noadded, total_wrong, total_nodata))
    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    readcfdisfromxml()
