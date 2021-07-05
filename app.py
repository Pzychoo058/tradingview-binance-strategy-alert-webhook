import json, config, config_erik

from click import get_app_dir
from flask import Flask, request, jsonify, render_template
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

client = Client(config.API_KEY, config.API_SECRET)
client_erik = Client(config_erik.API_KEY, config_erik.API_SECRET)
margin = client.futures_account_balance()
margin_erik = client_erik.futures_account_balance()


def get_positionsize(entry_price, sl_price, risk, equity, long=True):
    if not long:
        sl_diff = sl_price - entry_price
    elif long:
        sl_diff = entry_price - sl_price
    risk_equity = equity * risk
    possize = risk_equity / sl_diff
    return possize


def limit_order(side, quantity, quantity_erik, symbol, price, order_type=FUTURE_ORDER_TYPE_LIMIT,
                tif=TIME_IN_FORCE_GTC):
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        limit_order = client.futures_create_order(symbol=symbol, side=side, type=order_type, quantity=quantity,
                                                  price=price, timeinforce=tif)
        limit_order_erik = client_erik.futures_create_order(symbol=symbol, side=side, type=order_type,
                                                            quantity=quantity_erik,
                                                            price=price, timeinforce=tif)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return limit_order_erik, limit_order


def stop_order(side, quantity, symbol, price, order_type=FUTURE_ORDER_TYPE_STOP_MARKET):
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        stop_order = client.futures_create_order(symbol=symbol, side=side, type=order_type, closePosition=True,
                                                 stopPrice=price, workingType="MARK_PRICE")
        stop_order_erik = client_erik.futures_create_order(symbol=symbol, side=side, type=order_type,
                                                           closePosition=True,
                                                           stopPrice=price, workingType="MARK_PRICE")
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return stop_order_erik, stop_order


def take_profit_order(side, quantity, symbol, price, order_type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET):
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        take_profit_order = client.futures_create_order(symbol=symbol, side=side, type=order_type, closePosition=True,
                                                        stopPrice=price)
        take_profit_order_erik = client_erik.futures_create_order(symbol=symbol, side=side, type=order_type,
                                                                  closePosition=True,
                                                                  stopPrice=price)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return take_profit_order_erik, take_profit_order


sl_hit = 0


@app.route('/')
def welcome():
    return render_template('index.html')


@app.route('/webhook', methods=['POST'])
def webhook():
    # print(request.data)
    data = json.loads(request.data)

    if data['passphrase'] != config_erik.WEBHOOK_PASSPHRASE:
        return {
            "code": "error",
            "message": "Nice try, invalid passphrase"
        }

    market_position = data['strategy']['market_position'].upper()
    open_price = data['strategy']['entry_price']
    tp_price = data['strategy']['tp_price']
    sl_price = data['strategy']['sl_price']
    # ordersize = round(data['strategy']['market_position_size'], 3)
    long_buy_response = False
    short_buy_response = False
    risk = 0.02
    symbol = "ETHUSDT"
    cash = float(margin[1]['balance'])
    cash_erik = float(margin_erik[1]['balance'])
    # print(cash)
    # print(cash_erik)
    # ordersize = round(get_positionsize(open_price, cash), 3)
    # ordersize_erik = round(get_positionsize(open_price, cash_erik), 3)

    if market_position == "LONG":
        possize = round(get_positionsize(open_price, sl_price, risk, cash, True), 3)
        possize_erik = round(get_positionsize(open_price, sl_price, risk, cash_erik, True), 3)
        client_erik.futures_cancel_all_open_orders(symbol=symbol)
        client.futures_cancel_all_open_orders(symbol=symbol)
        long_buy_response = limit_order("BUY", possize, possize_erik, symbol, open_price)
        long_tp_response = take_profit_order("SELL", ordersize, symbol, tp_price)
        long_sl_response = stop_order("SELL", ordersize, symbol, sl_price)
    elif market_position == "SHORT":
        possize = round(get_positionsize(open_price, sl_price, risk, cash, False), 3)
        possize_erik = round(get_positionsize(open_price, sl_price, risk, cash_erik, False), 3)
        client_erik.futures_cancel_all_open_orders(symbol=symbol)
        client.futures_cancel_all_open_orders(symbol=symbol)
        short_buy_response = limit_order("SELL", possize, possize_erik, symbol, open_price)
        short_tp_response = take_profit_order("BUY", ordersize, symbol, tp_price)
        short_sl_response = stop_order("BUY", ordersize, symbol, sl_price)
    elif market_position == "SL":
        open_orders = client.futures_get_open_orders(symbol=symbol)
        open_orders_erik = client_erik.futures_get_open_orders(symbol=symbol)
        if len(open_orders) == 1:
            client.futures_cancel_all_open_orders(symbol=symbol)
        else:
            if open_orders[0]['type'] == "TAKE_PROFIT_MARKET" and open_orders[0]['symbol'] == symbol:
                client.futures_cancel_order(orderId=open_orders[0]['orderId'], symbol=symbol)
            elif open_orders[1]['type'] == "TAKE_PROFIT_MARKET" and open_orders[1]['symbol'] == symbol:
                client.futures_cancel_order(orderId=open_orders[1]['orderId'], symbol=symbol)
        if len(open_orders_erik) == 1:
            client_erik.futures_cancel_all_open_orders(symbol=symbol)
        else:
            if open_orders_erik[0]['type'] == "TAKE_PROFIT_MARKET" and open_orders_erik[0]['symbol'] == symbol:
                client_erik.futures_cancel_order(orderId=open_orders_erik[0]['orderId'], symbol=symbol)
            elif open_orders_erik[1]['type'] == "TAKE_PROFIT_MARKET" and open_orders_erik[1]['symbol'] == symbol:
                client_erik.futures_cancel_order(orderId=open_orders_erik[1]['orderId'], symbol=symbol)
    elif market_position == "TP":
        open_orders = client.futures_get_open_orders(symbol=symbol)
        open_orders_erik = client_erik.futures_get_open_orders(symbol=symbol)
        if len(open_orders) == 1:
            client.futures_cancel_all_open_orders(symbol=symbol)
        else:
            if open_orders[0]['type'] == "STOP_MARKET" and open_orders[0]['symbol'] == symbol:
                client.futures_cancel_order(orderId=open_orders[0]['orderId'], symbol=symbol)
            elif open_orders[1]['type'] == "STOP_MARKET" and open_orders[1]['symbol'] == symbol:
                client.futures_cancel_order(orderId=open_orders[1]['orderId'], symbol=symbol)
        if len(open_orders_erik) == 1:
            client_erik.futures_cancel_all_open_orders(symbol=symbol)
        else:
            if open_orders_erik[0]['type'] == "STOP_MARKET" and open_orders_erik[0]['symbol'] == symbol:
                client_erik.futures_cancel_order(orderId=open_orders_erik[0]['orderId'], symbol=symbol)
            elif open_orders_erik[1]['type'] == "STOP_MARKET" and open_orders_erik[1]['symbol'] == symbol:
                client_erik.futures_cancel_order(orderId=open_orders_erik[1]['orderId'], symbol=symbol)
        # print(open_orders)
        # print(open_orders[0]['type'])
        # print(len(open_orders))
    #     client_erik.futures_cancel_all_open_orders(symbol="ETHUSDT")
    #     client_erik.futures_cancel_order(symbol="ETHUSDT")
    #     client_erik.futures_cancel_orders(symbol="ETHUSDT")

    if long_buy_response:
        return {
            "code": "success",
            "message": "order executed"
        }
    if short_buy_response:
        return {
            "code": "success",
            "message": "order executed"
        }
    # else:
    #     print("order failed")

    return {
        "code": "error",
        "message": "order failed"
    }
