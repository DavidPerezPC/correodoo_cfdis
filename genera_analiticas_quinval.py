
import sys
import csv
import pandas as pd

COMPANY_NAME = 'Soluciones Agroindustriales Quinval SA de CV'
EXT_ID_COMPANY = 'account_analytic_group.1_QUINVAL'
EXT_ID_FIXED = 'account_analytic_group.1_'


def doexportcsv():

    try:
        exlfile = 'Estructura_Analitica_QUINVA.xlsx'
        rubro = pd.read_excel(exlfile, 'RUBRO')
        zona = pd.read_excel(exlfile, 'ZONA')


        anagrp_filename = 'cfdis/analytc_group_quinval.csv'
        anaacc_filename = 'cfdis/analytc_account_quinval.csv'
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
            print("Zona: {}".format(rubro_row[1]["NOMBRE"]), end=", ")

            dict = {'id': ext_id_rubro,
                    'name': rubro_row[1]['NOMBRE'],
                    'company_id': COMPANY_NAME,
                    'parent_id/id': EXT_ID_COMPANY,
                    }
            writer_grp.writerow(dict)
            rubro_code = str(rubro_row[1]['CODIGO']).zfill(2)

            for zona_row in zona.iterrows():
                ext_id_ruta = ext_id_rubro + "_" + zona_row[1]['NOMBRE'].replace(" ", "_")
                referencia = "{}{}".format(rubro_code,  str(zona_row[1]["CODIGO"]).zfill(2))
                nombre = "{} {}".format(rubro_code, zona_row[1]["NOMBRE"])
                print("Ruta: {} {}".format(referencia, nombre))
                dict = {'id': ext_id_ruta,
                        'name': nombre,
                        'code': referencia,
                        'company_id': COMPANY_NAME,
                        'group_id/id': ext_id_rubro,
                        }
                writer_acc.writerow(dict)

    except Exception as err:
        print(repr(err))


if __name__ == "__main__":
    doexportcsv()