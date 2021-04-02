import xmlrpc.client as xc
import sys
# import numpy as np
from datetime import datetime


# def get_conexion(host='192.168.0.14', port=5432, dbname='GMM', user= 'openerp', password='0p3n3rp'):
# 	return psql.connect("host='%s' port=%s dbname='%s' user='%s' password='%s'" % (host, port, dbname, user, password))


url = 'https://quinval.odoo.com'
db = 'quinval'
username = 'quinval@quinval.com'
password = 'SAQ14122'
common = xc.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xc.ServerProxy('{}/xmlrpc/2/object'.format(url))

afecta_fecha_arg = sys.argv[1]

def cancelpo(solofecha=int(afecta_fecha_arg)):

    try:
        domain = [[['state', '=', 'purchase']]]
        pos = models.execute_kw(db, uid, password, 'purchase.order', 'search_read', domain,
                                      {'fields': ['id', 'name', 'partner_id', 'date_order', 'picking_ids']})

        fnstocall = ['button_cancel', 'button_draft']
        for po in pos:
            print("ID: {}. NUMERO: {}. ID CLIENTE: {}. PICKING {}".format(po['id'], po['name'], po['partner_id'],
                                                              po['picking_ids'])),
            if solofecha == 0:
                domain = [[['id', 'in', po['picking_ids']]]]
                pickings = models.execute_kw(db, uid, password, 'stock.picking', 'search_read', domain,
                                             {'fields': ['id', 'name', 'origin']})
                for pick in pickings:
                    print("Recepcion: {}. Origin: {}".format(pick['name'], pick['origin']))
                    models.execute_kw(db, uid, password, 'stock.picking', 'unlink', [[pick['id']]])

                for i in range(0, 2):
                    try:
                        models.execute_kw(db, uid, password, 'purchase.order', fnstocall[i], [[int(po['id'])]])
                    except Exception as err:
                        pass
            else:
                data = {'date_approve': po['date_order']}
                models.execute_kw(db, uid, password, 'purchase.order', 'write', [[po['id']], data])

    except Exception as err:
        print(repr(err))

if __name__ == "__main__":
    cancelpo()