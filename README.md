# whale-api

「[whale-alert.io](http://whale-alert.io/)」のAPIを利用して、ビットコインのトランザクションを取得しています。

whale-graphで、ビットコインの移動量をグラフ化しています。


## 動かし方
1. Pythonの仮想環境をつくる（venv）
2. pip install -r requirements.txt
3. 「.env」ファイルを作成する
4. 「[whale-alert.io](http://whale-alert.io/)」のAPI_KEY、データベース情報（PostgreSQL）、最新のタイムスタンプTIMESTAMPを「.env」に書いておきます。
4. 96行目はラインボットでエラーを投げる処理をしているので、コメントアウトする。利用したい場合、LINE Notifyでトークンを取得してください。そのトークンは「.env」に書いておきます。
5. whale-api-response-db.pyを実行する。24時間サーバー上で動かしたかったので、自分はcronを利用しました。  
参考：[クーロン(cron)をさわってみるお](https://qiita.com/katsukii/items/d5f90a6e4592d1414f99)
