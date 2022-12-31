import time
start = time.perf_counter()
import datetime
import math
import requests
import os
from dotenv import load_dotenv
import psycopg2

# api_key, db_urlの読み込み
load_dotenv()

### メイン処理 cronで1分おきに処理を行う
def main():
    try:
        #　インスタンス
        api = APIClass()
        alert_class = AlertClass()
        tsc = TimeStampClass()
        rdbc = RegisterDBClass()

        unix_timestamp = '1672464413'
        # unix_timestamp = tsc.new_time_stamp()
        # unix_timestamp = os.environ['TIMESTAMP']
        tsc.register_time_stamp(unix_timestamp)
        print(unix_timestamp)

        # whale Alert からトランザクション（json）を取得
        whale_api_response = api.return_whale_api(unix_timestamp)

        # トランザクションの有無フラグ
        tx_flg = api.whale_api_error_check(whale_api_response)
        print(tx_flg)

        # value out of range for start parameter.の場合
        if (tx_flg == 2):
            # 新しいタイムスタンプを作成し、.envに登録する
            unix_timestamp = tsc.new_time_stamp()
            tsc.update_timestamp(unix_timestamp)

        # # トランザクションが100件だった場合、タイムスタンプに関係なく、全て値を調べる
        # tx_count = 0

        # トランザクションがある時に処理を行う。
        while (tx_flg == 1):
            # jsonに値があったら処理を継続する
            whale_api_json = whale_api_response.json()
            btc_transactions_count = whale_api_json['count']
            print('count : ' + str(btc_transactions_count))


            # 同じタイムスタンプのトランザクションの値を処理する
            sum_buy_btc_amount = 0
            sum_sell_btc_amount = 0
            transactions_list = whale_api_json['transactions']

            # 同じタイムスタンプのトランザクションがある間、処理を行う
            for transaction in transactions_list:
                tx_time_stamp = transaction['timestamp']

                # 配列の要素が先頭の場合、初期化処理を行う
                if (transaction == transactions_list[0]):
                    tsc.register_time_stamp(tx_time_stamp)
                    timestamp = tsc.exchange_time_stamp(tx_time_stamp) # タイムスタンプを日本時間に直す
                    btc_jpy_price = api.return_btc_jpy_price() # BTCの価格を取得する

                # # 一つ前のタイムスタンプが、今配列から取り出したトランザクションのタイムスタンプと違う場合、db登録し、処理終了。ただし、amountがbuy,sell両方0の場合、db登録しない
                # if (tsc.return_old_time_stamp() != tx_time_stamp):
                #     # 環境変数に1つ前のタイムスタンプを登録する
                #     previous_timestamp = tsc.return_old_time_stamp()
                #     tsc.update_timestamp(previous_timestamp)

                #     if (sum_buy_btc_amount > 0 or sum_sell_btc_amount > 0):
                #         # BTC移動の合計量とBTC価格をdbに登録する
                #         rdbc.set_db(timestamp, btc_jpy_price, sum_buy_btc_amount, sum_sell_btc_amount)
                #         tx_flg = 0
                #         break
                #     else:
                #         tx_flg = 0
                #         break


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
                    tx_flg = 0 #break
                    # 環境変数に今回利用したタイムスタンプを登録する
                    tsc.update_timestamp(tx_time_stamp)


    except Exception as e:
        # エラーが起きたら、LINEに通知する
        print(e)
        send_line_notify(e)
        # 新しいタイムスタンプを作成し、.envに登録する
        unix_timestamp = tsc.new_time_stamp()
        tsc.update_timestamp(unix_timestamp)


### メイン処理　end


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

    def update_timestamp(self, timestamp):
        # .envのタイムスタンプを更新する
        file_env = ".env"
        with open(file_env, encoding="ascii") as f:
            env_data = f.read()

        # 文字列置換
        old_unix_timestamp = os.environ['TIMESTAMP']
        new_unix_timestamp = str(timestamp) #.envなので文字列に変換する
        env_data = env_data.replace(old_unix_timestamp, new_unix_timestamp)

        # 同じファイル名で保存
        with open(file_env, mode="w", encoding="ascii") as f:
            f.write(env_data)

        # 再度.envを読み込む
        load_dotenv()



###
class APIClass:
    def return_whale_api(self, unix_timestamp):
        api_url = 'https://api.whale-alert.io/v1/transactions?'
        payload = {
            'api_key': os.environ['API_KEY'],
            'start': unix_timestamp,
            'currency': 'btc'
            }

        # time.sleep(15)
        response = requests.get(api_url, params=payload)

        return response

    def whale_api_error_check(self, whale_api_response):
        # 500 503 エラーの対策
        if (whale_api_response.status_code == 500 and whale_api_response.status_code == 503):
            print('500 503 error')
            tx_flg = 0

        # 400系エラーの対策、トランザクションカウントのチェック処理
        match whale_api_response.json():
            case {"result": 'error', "message": error} if whale_api_response.status_code == 400:
                print(f"timestamp error!: {error}") #value out of range for start parameter. For the Free plan the maximum transaction history is 3600 seconds
                tx_flg = 2

            case {"result": 'error', "message": error} if whale_api_response.status_code == 429:
                print(f"requests error: {error}") #usage limit reached
                tx_flg = 0

            case {"result": 'success', "count": count} if count == 0:
                print('count : 0')
                tx_flg = 0

            case {"result": 'success', "count": count} if count > 0:
                # print('トランザクションが1個以上ある')
                tx_flg = 1

            case _:
                print('不明なエラー jsonが取得できませんでした')
                print(whale_api_response)
                print(whale_api_response.json())
                tx_flg = 0

        return tx_flg


    def return_btc_jpy_price(self):
        api_url = 'https://api.bitflyer.com/v1/getticker?product_code=BTC_JPY'
        response = requests.get(api_url)

        error_flg = 1
        while (error_flg == 1):
            match response.status_code:
                case 200:
                    # print('btc-jpy success')

                    print('現在の価格' + str(response.json()['ltp']))
                    error_flg = 0

                case 500 | 503:
                    # print('500 503 error')
                    time.sleep(10)
                    response = requests.get(api_url)

                case 400 | 401 | 403 | 404 | 408:
                    # print('400系 error')
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
        self.USER = os.environ['USER']
        self.PASSWORD = os.environ['PASSWORD']
        self.HOST = os.environ['HOST']
        self.PORT = os.environ['PORT']
        self.DATABASE = os.environ['DATABASE']
        self.postgresql = 'postgresql://' + self.USER + ':' + self.PASSWORD + '@' + self.HOST + ':' + self.PORT + '/' + self.DATABASE
        # pass

    def db_register(self, timestamp, amount, price, move):
        with psycopg2.connect(self.postgresql) as conn:
            with conn.cursor() as curs:
                curs.execute(
                    "INSERT INTO whale_table(timestamp,amount,price,move) VALUES(timezone('JST' ,%s), %s, %s, %s)", (timestamp, amount, price, move))

        print('db登録しました ' + move)

    def set_db(self, timestamp, btc_jpy_price, sum_buy_btc_amount, sum_sell_btc_amount):
        self.db_register(timestamp, sum_buy_btc_amount, btc_jpy_price, 'buy')
        self.db_register(timestamp, sum_sell_btc_amount, btc_jpy_price, 'sell')



###
def send_line_notify(error):
    line_notify_token = os.environ['LINE']
    notification_message = 'whale-api-response-db.py : ' + str(error)
    line_notify_api = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization': f'Bearer {line_notify_token}'}
    data = {'message': f'message: {notification_message}'}
    requests.post(line_notify_api, headers = headers, data = data)



###
if __name__ == '__main__':
    main()
    print(time.perf_counter() - start)
