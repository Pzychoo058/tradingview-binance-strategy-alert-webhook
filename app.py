import json, config, config_erik
from flask import Flask, request, jsonify, render_template
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

client = Client(config.API_KEY, config.API_SECRET)
client_erik = Client(config_erik.API_KEY, config_erik.API_SECRET)
margin = client.futures_account_balance()
margin_erik = client_erik.futures_account_balance()


def get_positionsize(open_price, cash, leverage=25, risk=2):
    marge = ((cash * risk) / 100) * leverage
    possize = marge / open_price
    return possize


def limit_order(side, quantity, symbol, price, order_type=FUTURE_ORDER_TYPE_LIMIT, tif=TIME_IN_FORCE_GTC):
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        limit_order = client.futures_create_order(symbol=symbol, side=side, type=order_type, quantity=quantity,
                                                  price=price, timeinforce=tif)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return limit_order


def stop_order(side, quantity, symbol, price, order_type=FUTURE_ORDER_TYPE_STOP):
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        stop_order = client.futures_create_order(symbol=symbol, side=side, type=order_type, quantity=quantity,
                                                 stopPrice=price, price=price)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return stop_order


def take_profit_order(side, quantity, symbol, price, time=TIME_IN_FORCE_GTC, order_type=FUTURE_ORDER_TYPE_TAKE_PROFIT):
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        take_profit_order = client.futures_create_order(symbol=symbol, side=side, type=order_type, quantity=quantity,
                                                        stopPrice=price, price=price)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return take_profit_order


@app.route('/')
def welcome():
    return render_template('index.html')


@app.route('/webhook', methods=['POST'])
def webhook():
    # print(request.data)
    data = json.loads(request.data)

    if data['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return {
            "code": "error",
            "message": "Nice try, invalid passphrase"
        }

    side = data['strategy']['order_action'].upper()
    open_price = data['strategy']['entry_price']
    tp_price = data['strategy']['tp_price']
    sl_price = data['strategy']['sl_price']
    cash = float(margin[1]['balance'])
    cash_erik = float(margin_erik[1]['balance'])
    print(cash)
    print(cash_erik)
    ordersize = round(get_positionsize(open_price, cash), 3)
    ordersize_erik = round(get_positionsize(open_price, cash_erik), 3)

    if side == "BUY":
        client.futures_cancel_all_open_orders(symbol="ETHUSDT")
        long_buy_response = limit_order(side, ordersize, "ETHUSDT", open_price)
        long_tp_response = take_profit_order("SELL", ordersize, "ETHUSDT", open_price)
        long_sl_response = stop_order("SELL", ordersize, "ETHUSDT", sl_price)
    elif side == "SELL":
        client.futures_cancel_all_open_orders(symbol="ETHUSDT")
        short_buy_response = limit_order(side, ordersize, "ETHUSDT", open_price)
        short_tp_response = take_profit_order("BUY", ordersize, "ETHUSDT", open_price)
        short_sl_response = stop_order("BUY", ordersize, "ETHUSDT", sl_price)
    elif side == "CLOSE":
        client.futures_cancel_all_open_orders(symbol="ETHUSDT")
    #if long_buy_response:
        return {
            "code": "success",
            "message": "order executed"
        }
    if short_buy_response:
        return {
            "code": "success",
            "message": "order executed"
        }
    else:
        print("order failed")

    return {
        "code": "error",
        "message": "order failed"
    }


