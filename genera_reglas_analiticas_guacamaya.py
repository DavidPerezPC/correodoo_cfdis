import xmlrpc.client as xc
import sys
import csv
import pandas as pd


url = 'https://grupoley-paralelo-2630664.dev.odoo.com'
db = 'grupoley-paralelo-2630664'
username = 'grupoley@tecnika.com.mx'
password = '1234%&'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

COMPANY_NAME = 'Industrias Guacamaya, S.A. de C.V.'
EXT_ID_FIXED = 'account_analytic_default.2_'
CTAS_ANA = [['01', None, None, 127], ['20', None, None, 1090]]
CUENTAS = [['01',  127, None], ['50', 1090, None]]

def doexportcsv():

    try:
        exlfile = 'Reglas_Analitica_Guacamaya.xlsx'
        reglas = pd.read_excel(exlfile, 'Reglas')

        anadefault_filename = 'cfdis/analytc_account_default.csv'
        anadefault_file = open(anadefault_filename, 'w')
        default_fields = ['id', 'analytic_account_id/ID', 'product_id/ID', 'account_id/ID', 'user_id/ID',
                          'company_id']
        writer_default = csv.DictWriter(anadefault_file, fieldnames=default_fields)
        domain = [[['categ_id', '=', 16]]]
        especias_tmpl_ids = models.execute_kw(db, uid, password, 'product.template', 'search', domain)
        domain = [[['categ_id', '=', 15]]]
        salsas_tmpl_ids = models.execute_kw(db, uid, password, 'product.template', 'search', domain)

        domain = [[['product_tmpl_id', 'in', especias_tmpl_ids]]]
        CUENTAS[1][2] = models.execute_kw(db, uid, password, 'product.product', 'search', domain)
        domain = [[['product_tmpl_id', 'in', salsas_tmpl_ids]]]
        CUENTAS[0][2] = models.execute_kw(db, uid, password, 'product.product', 'search', domain)
        writer_default.writeheader()

        for regla in reglas.iterrows():

            for i in range(0, 2):
                for j in range(0, 2):
                    cta_ana = "{}{}{}".format(str(regla[1]["cc"]).strip(), CTAS_ANA[j][0], CUENTAS[i][0])
                    domain = [[['code', '=', cta_ana]]]
                    CTAS_ANA[j][1] = cta_ana
                    ana_ids =  models.execute_kw(db, uid, password, 'account.analytic.account', 'search', domain)
                    if ana_ids:
                        CTAS_ANA[j][2] = ana_ids[0]
                    else:
                        print("No se encontró CuentaAnalitica: {} con Usuario: {} ".format(cta_ana, regla[1]["nombreUsuario"]))
                        continue

                ext_fix_id = "{}{}".format(EXT_ID_FIXED, str(regla[1]["user_id"]).strip())
                for prod in CUENTAS[i][2]:
                    for ana in CTAS_ANA:
                        ext_id = "{}_{}_{}".format(ext_fix_id, ana[1], str(prod))
                        dict = {'id': ext_id,
                            'analytic_account_id/ID': ana[2],
                            'product_id/ID': prod,
                            'account_id/ID': ana[3],
                            'user_id/ID': regla[1]["user_id"],
                             'company_id': COMPANY_NAME,
                            }
                        # dict = {
                        #         'analytic_id': ana[2],
                        #         'product_id': prod,
                        #         'account_id': ana[3],
                        #         'user_id': regla[1]["user_id"],
                        #         'company_id': 2,
                        #         }
                        # try:
                        #    models.execute_kw(db, uid, password, 'account.analytic.default', 'create', [dict])
                        # except Exception as err:
                        #    print(err)
                        #    pass
                        writer_default.writerow(dict)

    except Exception as err:
        print(repr(err))


if __name__ == "__main__":
    doexportcsv()