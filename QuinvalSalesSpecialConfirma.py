# Available variables:
#  - env: Odoo Environment on which the action is triggered
#  - model: Odoo Model of the record on which the action is triggered; is a void recordset
#  - record: record on which the action is triggered; may be void
#  - records: recordset of all records on which the action is triggered in multi-mode; may be void
#  - time, datetime, dateutil, timezone: useful Python libraries
#  - float_compare: Odoo function to compare floats based on specific precisions
#  - log: log(message, level='info'): logging function to record debug information in ir.logging table
#  - UserError: Warning Exception to use with raise
# To return an action, assign: action = {...
def PurchaseSpecialConfirma(env, records):

    for record in records:
        if record['state'] != 'purchase':
            continue
        op_contable = record['date_planned']
        op_date = op_contable
        sql = ''
        account_date = "create_date = '{}', date = '{}'".format(op_contable, op_contable)
        create_date = "create_date = '{}'".format(op_date)
        date_done = "date_done = '{}'".format(op_date)
        date_standar = "{}, date = '{}'".format(create_date, op_date)
        date_moves = "date_deadline = '{}'".format(op_date)
        pickings = str(tuple(record.picking_ids.ids)).replace(",)", ")")
        stockvaluation = []
        accountmoveids = []
        for pick in record.picking_ids:
            for move in pick.move_lines:
                stockvaluation.append(move.stock_valuation_layer_ids.ids)
                accountmoveids.append(move.account_move_ids.ids)

        vallayers = str(tuple([x[0] for x in stockvaluation])).replace(",)", ")")
        accmoves = str(tuple([x[0] for x in accountmoveids])).replace(",)", ")")
        sql = "update stock_picking set {}, {}, {}, scheduled_date = '{}' " \
              "where id in {}; ".format(date_done, date_standar, date_moves, op_date, pickings)
        sql += "update stock_move set {}, {} where picking_id in {}; ".format(date_standar, date_moves, pickings)
        sql += "update stock_move_line set {} where picking_id in {}; ".format(date_standar, pickings)
        sql += "update stock_valuation_layer set {} where id in {}; ".format(create_date, vallayers)
        sql += "update account_move set {} where id in {}; ".format(account_date, accmoves)
        sql += "update account_move_line set {} where move_id in {}; ".format(account_date, accmoves)
        sql += """update purchase_order set create_date = '{}', date_order = '{}', date_approve = '{}', 
                      date_calendar_start = '{}', effective_date = '{}' 
                      where id = {}""".format(op_date, op_date, op_date, op_date, op_date, record['id'])

        # record['note'] = sql
        env.cr.execute(sql)


def SalesSpecialConfirma(env, records):
    for record in records:
        if record['state'] != 'sale':
            continue
        op_contable = record['validity_date']
        op_date = op_contable + datetime.timedelta(days=1)
        sql = ''
        account_date = "create_date = '{}', date = '{}'".format(op_contable, op_contable)
        create_date = "create_date = '{}'".format(op_date)
        date_done = "date_done = '{}'".format(op_date)
        date_standar = "{}, date = '{}'".format(create_date, op_date)
        date_moves = "date_deadline = '{}'".format(op_date)
        pickings = str(tuple(record.picking_ids.ids)).replace(",)", ")")
        stockvaluation = []
        accountmoveids = []
        for pick in record.picking_ids:
            for move in pick.move_lines:
                stockvaluation.append(move.stock_valuation_layer_ids.ids)
                accountmoveids.append(move.account_move_ids.ids)

        vallayers = str(tuple([x[0] for x in stockvaluation])).replace(",)", ")")
        accmoves = str(tuple([x[0] for x in accountmoveids])).replace(",)", ")")
        sql = "update stock_picking set {}, {}, {}, scheduled_date = '{}' " \
              "where id in {}; ".format(date_done, date_standar, date_moves, op_date, pickings)
        sql += "update stock_move set {}, {} where picking_id in {}; ".format(date_standar, date_moves, pickings)
        sql += "update stock_move_line set {} where picking_id in {}; ".format(date_standar, pickings)
        sql += "update stock_valuation_layer set {} where id in {}; ".format(create_date, vallayers)
        sql += "update account_move set {} where id in {}; ".format(account_date, accmoves)
        sql += "update account_move_line set {} where move_id in {}; ".format(account_date, accmoves)
        sql += "update sale_order set create_date = '{}', date_order = '{}' " \
               "where id = {}".format(op_date, op_date, record['id'])
        env.cr.execute(sql)

