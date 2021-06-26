import xmlrpc.client as xc
import sys
import pandas as pd


url = 'https://grupoley-paralelo-2630664.dev.odoo.com'
db = 'grupoley-paralelo-2630664'
username = 'grupoley@tecnika.com.mx'
password = '1234%&'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

excel_file_arg = sys.argv[1]
sheet_name_arg = sys.argv[2]


def cancelacfdis(excel_file=excel_file_arg, sheet_name=sheet_name_arg):

    try:
        dt = pd.read_excel(excel_file, sheet_name)
        for exl_row in dt.iterrows():
            payment_reference = exl_row[1]['payment_reference']

            domain = [[['name', '=', payment_reference],
                       ['move_type', '=', 'out_invoice']]]
            invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                         {'fields': ['id', 'name', 'state', 'edi_document_ids',
                                                     'attachment_ids', 'invoice_line_ids', 'line_ids']})
            if not invoices:
                print("Factura {} , no encontrada en Odoo".format(payment_reference))
                continue

            for inv in invoices:
                #elimino cualquier attachment
                print("Procesando Factura {}".format(payment_reference), end=', ')

                if inv['state'] == 'posted':
                    for att in inv['edi_document_ids']:
                        models.execute_kw(db, uid, password, 'account.edi.document', 'unlink', [att])
                    try:
                        models.execute_kw(db, uid, password, 'account.move', 'button_draft', [[int(inv['id'])]])
                    except Exception as err:
                        pass

                i = 1
                for line in inv['invoice_line_ids']:
                    if i > 1:
                        models.execute_kw(db, uid, password, 'account.move.line', 'unlink', [line], {'context': {'check_move_validity': False}})
                    i += 1

                domain = [[['id', '=', inv['id']]]]
                newinvoice = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                             {'fields': ['id', 'name', 'line_ids']})[0]

                domain = [[['id', 'in', newinvoice['line_ids']],
                            ['account_id', '=', 127]]]
                movelines = models.execute_kw(db, uid, password, 'account.move.line', 'search_read', domain,
                                              {'fields': ['id', 'account_id', 'debit', 'credit']})[0]

                for line in newinvoice['line_ids']:
                    if line != movelines['id']:
                        models.execute_kw(db, uid, password, 'account.move.line', 'write', [[line], {'debit': movelines['credit']}])

                fnstocall = ['action_post', 'action_process_edi_web_services']
                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'account.move', fnstocall[i], [[int(inv['id'])]])
                    except Exception as err:
                        pass

                cfdi = inv['attachment_ids'][0]
                data = {
                    'attachment_id': cfdi,
                    'state': 'sent',
                    'error': False,
                }
                domain = [[['move_id', '=', inv['id']]]]
                edidoc = models.execute_kw(db, uid, password, 'account.edi.document', 'search_read', domain,
                                           {'fields': ['id', 'name']})
                models.execute_kw(db, uid, password, 'account.edi.document', 'write', [[edidoc[0]['id']], data])


    except Exception as err:
        print(repr(err))

    return


def validadetallecfdis():

    try:
        domain = [[['move_type', '=', 'out_invoice'],
                   ['state', '!=', 'cancel'],
                   ['invoice_date', '<=', '2021-05-31'],
                   ]]
        invoices = models.execute_kw(db, uid, password, 'account.move', 'search_read', domain,
                                     {'fields': ['id', 'name',  'invoice_line_ids']})

        for inv in invoices:

            if inv['invoice_line_ids'] and len(inv['invoice_line_ids']) > 1:

                print('Factura {} con lineas de detalle duplicadas'.format(inv['name']))

    except Exception as err:
        print(repr(err))

    return


if __name__ == "__main__":
    cancelacfdis()
    #validadetallecfdis()