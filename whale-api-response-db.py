import time
import datetime
import math
import requests
import os
from dotenv import load_dotenv
import psycopg2

# api_key, db_urlの読み込み
load_dotenv()


### メイン処理
def main():

    #　インスタンス
    api = APIClass()
    alert_class = AlertClass()
    tsc = TimeStampClass()
    rdbc = RegisterDBClass()

    unix_timestamp = '1669957082'
    # unix_timestamp = tsc.new_time_stamp()
    tsc.register_time_stamp(unix_timestamp)
    print(unix_timestamp)


    #
    # 無限ループ開始
    #

    # t_end = time.time() + 60 * 60*24
    t_end = time.time() + 60 * 60*2
    while time.time() < t_end:

      unix_timestamp = tsc.return_old_time_stamp()
      print('古いタイムスタンプを利用 : ' + str(unix_timestamp))
      whale_api_response = api.return_whale_api(unix_timestamp)

      error_flg = 1
      while (error_flg == 1):
        match whale_api_response.json():
            case {"result": 'error', "message": error} if whale_api_response.status_code == 400:
                print(f"timestamp error!: {error}") #value out of range for start parameter. For the Free plan the maximum transaction history is 3600 seconds
                unix_timestamp = tsc.new_time_stamp()
                whale_api_response = api.return_whale_api(unix_timestamp)

            case {"result": 'error', "message": error} if whale_api_response.status_code == 429:
                print(f"requests error: {error}") #usage limit reached
                time.sleep(20)
                whale_api_response = api.return_whale_api(unix_timestamp)

            case {"result": 'success', "count": count} if count == 0:
                print('count : 0')
                whale_api_response = api.return_whale_api(unix_timestamp)

            case {"result": 'success', "count": count} if count > 0:
                error_flg = 0
                # print('トランザクションが1個以上ある')

            case _:
                print('不明なエラー jsonが取得できませんでした')
                print(whale_api_response)
                print(whale_api_response.json())
                error_flg = 0
                # whale_api_response = api.return_whale_api(unix_timestamp)


      print('ok')
      whale_api_json = whale_api_response.json()
      btc_transactions_count = whale_api_json['count']
      print('count : ' + str(btc_transactions_count))


      # 同じタイムスタンプのトランザクションの値を処理する
      sum_buy_btc_amount = 0
      sum_sell_btc_amount = 0
      transactions_list = whale_api_json['transactions']

      # 同じタイムスタンプのトランザクションがある間、処理を行う
      for transaction in transactions_list:
        new_time_stamp = transaction['timestamp']

        # 配列の要素が先頭の場合、初期化処理を行う
        if (transaction == transactions_list[0]):
            tsc.register_time_stamp(new_time_stamp)
            timestamp = tsc.exchange_time_stamp(new_time_stamp) # タイムスタンプを日本時間に直す
            btc_jpy_price = api.return_btc_jpy_price() # BTCの価格を取得する

        # 一つ前のタイムスタンプが、今配列から取り出したトランザクションのタイムスタンプと違う場合、db登録し、処理終了
        if (tsc.return_old_time_stamp() != new_time_stamp):
            #1つ前のタイムスタンプを利用して新しいjsonデータを取得するために、関数に登録しておく
            # tsc.register_time_stamp(old_time_stamp)

            # BTC移動の合計量とBTC価格をdbに登録する
            rdbc.set_db(timestamp, btc_jpy_price, sum_buy_btc_amount, sum_sell_btc_amount)
            break


        btc_id = transaction['id']
        btc_from = transaction['from']['owner_type']
        btc_to = transaction['to']['owner_type']
        btc_amount = transaction['amount']

        if (btc_from == 'exchange' and btc_to == 'unknown'):
            alert_class.buy_alert(btc_amount)
            sum_buy_btc_amount += btc_amount
            print(sum_buy_btc_amount)

        if (btc_from == 'unknown' and btc_to == 'exchange'):
            alert_class.sell_alert(btc_amount)
            sum_sell_btc_amount += btc_amount
            print(sum_sell_btc_amount)

        # 配列の要素が最後の場合（配列の中身がすべて同じタイムスタンプだった場合）db登録
        if (transaction == transactions_list[-1]):
            rdbc.set_db(timestamp, btc_jpy_price, sum_buy_btc_amount, sum_sell_btc_amount)
            break


###
class TimeStampClass:

  def __init__(self):
    self.old_time_stamp = 0

  def new_time_stamp(self):
    return math.floor(time.time())

  def register_time_stamp(self, new_time_stamp):
    print('古いタイムスタンプを登録 : ' + str(new_time_stamp))
    self.old_time_stamp = new_time_stamp

  def return_old_time_stamp(self):
    return self.old_time_stamp

  def exchange_time_stamp(self, timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone(datetime.timedelta(hours=9)))



###
class APIClass:
    def return_whale_api(self, unix_timestamp):
        api_url = 'https://api.whale-alert.io/v1/transactions?'
        payload = {
            'api_key': os.environ['API_KEY'],
            'start': unix_timestamp,
            'currency': 'btc'
            }

        time.sleep(15)
        response = requests.get(api_url, params=payload)

        error_flg = 1
        while (error_flg == 1):
            match response.status_code: #空の500,503エラーを避ける、400系エラー回避はメイン処理に組み込む
                case 200:
                    # print('whale-api success')
                    error_flg = 0

                case 500 | 503:
                    print('500 503 error')
                    time.sleep(10)
                    response = requests.get(api_url)

                case _:
                    print('500 503 以外のerror')
                    error_flg = 0

        return response


    def return_btc_jpy_price(self):
        api_url = 'https://api.bitflyer.com/v1/getticker?product_code=BTC_JPY'
        response = requests.get(api_url)

        error_flg = 1
        while (error_flg == 1):
            match response.status_code:
                case 200:
                    print('btc-jpy success')

                    print('現在の価格' + str(response.json()['ltp']))
                    error_flg = 0

                case 500 | 503:
                    print('500 503 error')
                    time.sleep(10)
                    response = requests.get(api_url)

                case 400 | 401 | 403 | 404 | 408:
                    print('400系 error')
                    time.sleep(15)
                    response = requests.get(api_url)
                case _:
                    print('不明なエラー btc-jpyを取得できませんでした')

        return response.json()['ltp']


###
class AlertClass:
  def buy_alert(self, btc_amount):
    print('buy_amount：' + str(btc_amount))

  def sell_alert(self, btc_amount):
    print('sell_amount：' + str(btc_amount))



###
class RegisterDBClass:
    def __init__(self):
        # self.DATABASES_URL = os.environ['DATABASE_URL']
        # self.USER = os.environ['USER']
        # self.PASSWORD = os.environ['PASSWORD']
        # self.HOST = os.environ['HOST']
        # self.PORT = os.environ['PORT']
        # self.DATABASE = os.environ['DATABASE']
        # self.postgresql = 'postgresql://' + self.USER + ':' + self.PASSWORD + '@' + self.HOST + ':' + self.PORT + '/' + self.DATABASE
        pass

    def db_register(self, timestamp, amount, price, move):
        # with psycopg2.connect(self.DATABASES_URL) as conn:
        # with psycopg2.connect(user=self.USER,password=self.PASSWORD,host=self.HOST,port=self.PORT,database=self.DATABASE) as conn:
        with psycopg2.connect(self.postgresql) as conn:
            with conn.cursor() as curs:
                curs.execute(
                    "INSERT INTO whale(timestamp,amount,price,move) VALUES(timezone('JST' ,%s), %s, %s, %s)", (timestamp, amount, price, move))

        print('db登録しました ' + move)

    def set_db(self, timestamp, btc_jpy_price, sum_buy_btc_amount, sum_sell_btc_amount):
        self.db_register(timestamp, sum_buy_btc_amount, btc_jpy_price, 'buy')
        self.db_register(timestamp, sum_sell_btc_amount, btc_jpy_price, 'sell')


###
if __name__ == '__main__':
    main()