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

CXC_ACC_ID = 3
CXP_ACC_ID = 3148
ACC_ID = 3453
COMPANY_ID = 1
JOURNAL_ID = 15
XML_DIR = ['3-MARZO', '4-ABRIL', '5-MAYO']
#XML_DIR = ['1-ENERO', '2-FEBRERO', '3-MARZO', '4-ABRIL', '5-MAYO']
IVAS = {'002': {'160000': 10, '000000': 9, '080000': 11},
        '003': {'060000': 15, '090000': 16, '000000': 18}
        }
RETENCIONES = {'002': {'040000': 3, '100000': 4, '106700': 8, '106670': 8, '106667': 8 },
               '001': {'100000': 6}
               }
TAX_RET = {}
# move_type_arg = sys.argv[1]
# excel_file_arg = sys.argv[2]
# sheet_name_arg = sys.argv[3]

CFDIFORMAT = 2
TAX_ID = 25
PRODUCT_ID = 9954 #9965


def read_xml_raw(xmlfile):
    return open(xmlfile).read()


def get_data_from_cfdi(xmlcfdi):

    tfd = {"tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
            "xsi": "http://www.sat.gob.mx/TimbreFiscalDigital http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd"}


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

    conceptos = xmlcfdicontent.findall('cfdi:Conceptos/cfdi:Concepto', tfd)
    for concepto in conceptos:
        impuestos = concepto.findall('cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado', tfd)
        retenciones = concepto.findall('cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion', tfd)
        taxes_ = []
        for tax in impuestos:
            tipo = tax.attrib['Impuesto']
            tasa = tax.attrib['TasaOCuota'][2:]
            taxes_.append(IVAS[tipo][tasa])

        for tax in retenciones:
            tipo = tax.attrib['Impuesto']
            tasa = tax.attrib['TasaOCuota'][2:]
            taxes_.append(RETENCIONES[tipo][tasa])

        inv_info['Detalle'].append([concepto.attrib, taxes_])

    return inv_info


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
                                 {'fields': ['id', 'name']})

    if contact:
        partner_id = contact[0]['id']
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

def invoice_lines(invoice_id, inv):

    lines = inv['Detalle']

    for line in lines:
        data = {
            'move_id': invoice_id,
            'name': line[0]['Descripcion'],
            'quantity': 1,
            'price_unit': float(line[0]['Importe']),
            'tax_ids': [[6, 0, line[1]], ],
            'account_id': ACC_ID,
            'exclude_from_invoice_tab': False,
        }
        models.execute_kw(db, uid, password, 'account.move.line', 'create', [data],
                           {'context': {'check_move_validity': False}})

    return True


def readcfdisfromxml():

    directorio = "/Users/turbo/Downloads/quinvalcfdis/"
    try:
        for dir in XML_DIR:
            xmlfiles = glob('{}{}/*.xml'.format(directorio, dir))
            contacts = {}
            notfound = 0
            total = 0
            for xmlfile in xmlfiles:

                total += 1
                try:
                    inv_data = get_data_from_cfdi(xmlfile)
                except Exception as err:
                    print("Error en el archivo: {}".format(xmlfile))
                    pass
                    continue

                if not inv_data:
                    continue

                rfc = inv_data['Emisor']['Rfc']
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

                    serie_folio = inv_data['Serie']
                    if serie_folio:
                        serie_folio = '{}{}'.format(inv_data['Serie'], inv_data['Folio'])
                    else:
                        serie_folio = inv_data['Folio']

                    if rfc in BLOCKED_RFC:
                        continue

                    if get_expense_inday(partner_id, inv_data):
                        print("El folio {} del RFC {} ya tiene un comprobante el mismo dia".format(serie_folio, rfc))
                        continue

                    print("Procesando {}".format(serie_folio), end=", ")

                    #lleno los datos de la factura y la creo
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
                    }
                    invoice_id = models.execute_kw(db, uid, password, 'account.move', 'create', [inv_dict])

                    invoice_lines(invoice_id, inv_data)

                    print("grabado con ID {}".format(invoice_id))
                    #creo los documentos de XML y los agrego a la factura
                    savecfdi(invoice_id, inv_data, rfc, serie_folio)

                except Exception as err:
                    print("ERROR: {}".format(repr(err)))
                    pass

                #aplico la factura
                #models.execute_kw(db, uid, password, 'account.move', 'action_post', [[invoice_id]])

            print("Encontados {} de {}".format(total-notfound, total))
    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    readcfdisfromxml()
