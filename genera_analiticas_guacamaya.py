
import sys
import csv
import pandas as pd

COMPANY_NAME = 'Industrias Guacamaya, S.A. de C.V.'
EXT_ID_COMPANY = 'account_analytic_group.2_GUACAMAYA_NUEVO'
EXT_ID_FIXED = 'account_analytic_group.2_'
LINEAS_PROD_CODIGO = ['01', '50']
LINEAS_PROD_NOMBRE = ['SALSAS', 'ESPECIAS']


def doexportcsv():

    try:
        exlfile = 'Estructura_Analitica_Guacamaya.xlsx'
        rubro = pd.read_excel(exlfile, 'RUBRO')
        zona = pd.read_excel(exlfile, 'ZONA')
        ruta = pd.read_excel(exlfile, 'RUTA')

        anagrp_filename = 'cfdis/analytc_group_gucamaya.csv'
        anaacc_filename = 'cfdis/analytc_account_gucamaya.csv'
        anagrp_file = open(anagrp_filename, 'w')
        anaacc_file = open(anaacc_filename, 'w')
        grp_fields = ['id', 'name', 'company_id', 'parent_id/id']
        writer_grp = csv.DictWriter(anagrp_file, fieldnames=grp_fields)
        acc_fields = ['id', 'name', 'code', 'company_id', 'group_id/id']
        writer_acc = csv.DictWriter(anaacc_file, fieldnames=acc_fields)

        writer_grp.writeheader()
        writer_acc.writeheader()

        for rubro_row in rubro.iterrows():

            ext_id_rubro = EXT_ID_FIXED + rubro_row[1]['NOMBRE'].replace(" ", "_")
            dict = {'id': ext_id_rubro,
                    'name': rubro_row[1]['NOMBRE'],
                    'company_id': COMPANY_NAME,
                    'parent_id/id': EXT_ID_COMPANY,
                    }
            writer_grp.writerow(dict)
            rubro_code = str(rubro_row[1]["CODIGO"]).zfill(2)
            print("Rubro: {} {}".format(rubro_code, rubro_row[1]["NOMBRE"]), end=", ")

            for zona_row in zona.iterrows():
                ext_id_zona = ext_id_rubro + '_' + zona_row[1]['NOMBRE'].replace(" ", "_")
                print("Zona: {}".format(zona_row[1]["NOMBRE"]), end=", ")

                dict = {'id': ext_id_zona,
                        'name': rubro_code + " " + zona_row[1]['NOMBRE'],
                        'company_id': COMPANY_NAME,
                        'parent_id/id': ext_id_rubro,
                        }
                writer_grp.writerow(dict)
#ruta[(ruta.ZONA == zona_row[1]["NOMBRE"])]
                ruta_rows = ruta[(ruta.ZONA == zona_row[1]["NOMBRE"])]
                for ruta_row in ruta_rows.iterrows():
                    ext_id_ruta = ext_id_zona + "_" + ruta_row[1]['NOMBRE'].replace(" ", "_")
                    referencia = "{}{}".format(str(ruta_row[1]["CODIGO"]), rubro_code)
                    nombre = "{} {}".format(rubro_code, ruta_row[1]["NOMBRE"])
                    print("Ruta: {} {}".format(referencia, nombre))
                    for i in range(0,2):
                        dict = {'id': "{}_{}".format(ext_id_ruta, LINEAS_PROD_CODIGO[i]),
                                'name': "{} {}".format(nombre, LINEAS_PROD_NOMBRE[i]),
                                'code': "{}{}".format(referencia, LINEAS_PROD_CODIGO[i]),
                                'company_id': COMPANY_NAME,
                                'group_id/id': ext_id_zona,
                                }
                        writer_acc.writerow(dict)

    except Exception as err:
        print(repr(err))


if __name__ == "__main__":
    doexportcsv()