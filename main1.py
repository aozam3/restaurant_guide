import os
import sqlalchemy
from flask import Flask, request, abort
import json
import requests
from datetime import datetime, date, timedelta
import geocoder

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError,
    LineBotApiError
)
from linebot.models import (
    MessageEvent,
    TextMessage, TextSendMessage,
    ImageMessage, ImageSendMessage,
    AudioMessage, VideoMessage, LocationMessage,
    StickerMessage, FileMessage,
    # MessageAction, TemplateSendMessage,
    ButtonsTemplate
)


app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get('LINE_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))


# submethod
def get_username_channel(event):
    username = 'unknown'
    channel = 'random'
    try:
        user_id = event.source.user_id
        if hasattr(event.source,"group_id"):
            group_id = event.source.group_id
            channel = f'{group_id[:10]}'
            profile = line_bot_api.get_group_member_profile(group_id, user_id)
        elif hasattr(event.source,"room_id"):
            room_id = event.source.room_id
            channel = f'{room_id[:10]}'
            profile = line_bot_api.get_room_member_profile(room_id, user_id)
        else: # direct message
            channel = f'{event.source.user_id[:10]}'
            profile = line_bot_api.get_profile(user_id)
        username = profile.display_name
    except LineBotApiError as e:
        print('Error:get_username_channel')
        print(e)
        username = user_id[:5]
    channel = channel.lower()
    return username, channel


@app.route("/callback", methods=['POST'])
def callback():
   # get X-Line-Signature header value
   signature = request.headers['X-Line-Signature']

   # get request body as text
   body = request.get_data(as_text=True)
   app.logger.info("Request body: " + body)

   # handle webhook body
   try:
       handler.handle(body, signature)
   except InvalidSignatureError:
       print("Invalid signature. Please check your channel access token/channel secret.")
       abort(400)

   return 'OK'

def reply_message_error(event, message=''):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='DBへのアクセスに失敗しました。再度実行してください。'+message)
        )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_name, channel = get_username_channel(event)
    text = event.message.text

    kwargs = {}
    kwargs['id'] = user_id
    #kwargs['id'] = 'Ue463742b730f1acc63c7605c37f0466f' #特定のユーザIDを指定することもできる
    kwargs['name'] = user_name
    kwargs['place'] = '' #場所の入力
    kwargs['genre'] = '' #ジャンルの入力
    kwargs['restaurant'] = '' #店名の入力
    ##kwargs['now'] = datetime.utcnow() + timedelta(hours=9)#最終時刻の取得
    #現在の状態を調べる(select_one(返り値))→分岐 (空の時(noneが返ってきたら)insertで行を作成)select構文の使用

    # 現在の状態をSQLから取り出す
    success, result = select_one("SELECT state from state_table WHERE id =:id", **kwargs)

    if not success:
        # DBへのアクセスに失敗
        kwargs['message'] = 'SELECT state from state_table WHERE id =:id'
        reply_message_error(event, str(kwargs))
        return


    if result is None:#空の時の処理(そもそもIDが登録されていない)→sqlに新たな行を追加してあげる
        # そのIDからLINE botに初めて話しかけたので行を作成する
        success = insert("INSERT INTO state_table (id, name, state, last_update) VALUES (:id, :name, 'wakeup', :now)", **kwargs)#idの登録と状態をwakeupへ変更
        if not success:
            kwargs['message'] = "INSERT INTO state_table (id, name, state, last_update) VALUES (:id, :name, 'wakeup', :now)"
            reply_message_error(event, str(kwargs))
            return

    kwargs['state'] = result[0]

    def ans_restaurant(j,place_name):
        text_line = ''
        text_line += place_name + '付近のお店は'
        for i in range (len(j['results']['shop'])):
            x = j['results']['shop'][i]['name']
            u = j['results']['shop'][i]['access']
            y = j['results']['shop'][i]['genre']['catch']
            text_line += '店名: ' + str(x) + '\n' + '住所: ' + str(u)+ '\n' + '概要: ' + str(y)
        return text_line


    if kwargs['state'] == 'wakeup':
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='飲食店アプリを起動します。' + '\n' + '地名を入力してください。')
            )
        success = update("UPDATE state_table SET last_update=:now, state='check_place' WHERE id=:id", **kwargs)
        
   
    elif kwargs['state'] == 'check_place':
        ##APIのURL取得
        url = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"

        kwargs['place'] = text 
        ret = geocoder.osm(kwargs['place'], timeout=5.0)

        ##間違ってたらメッセージ送って終わり(状態そのまま)、あってたら状態かえる
        if ret.latlng == None:
            line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='入力された地名を表示することは出来ません。 '+ '\n' + 'もう一度入力してください。')
            )

        else:
            '''           
            querystring = {"lat":int(ret.latlng[0]),"lon":int(ret.latlng[1])}
            headers = {
                'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
                'x-rapidapi-key': "xxxxxxxxxxxxxxxxxxxxxxxxxx"
                }

            response = requests.request("GET", url, headers=headers, params=querystring)
            j = json.loads(response.text)
            '''
            
            success = update("UPDATE state_table SET last_update=:now, place=:place WHERE id=:id", **kwargs)

            line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='どんな料理を食べたいですか？' + '\n' + '例：洋食、和食、中華、イタリアン、スイーツ、その他から選択してください。')
            )

            success = update("UPDATE state_table SET last_update=:now, state='check_genre' WHERE id=:id", **kwargs)
       
    elif kwargs['state'] == 'check_genre':        
       
        #情報消えるからもっかいやらなきゃ
        url = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
        success, place_name = select_one("SELECT place from state_table WHERE id =:id", **kwargs)
        place_name = place_name[0]
        ret = geocoder.osm(place_name, timeout=5.0)

        kwargs['date'] = text # 発言はジャンル
        #place_name = select_one("SELECT place from state_table WHERE id =:id", **kwargs)
        input_genre = kwargs['date']
        genre = []
        
        #先に今日明日の処理('-'含まれてないから)
        if input_genre == '洋食':
            genre.append('G005')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == '和食':
            genre.append('G004')
            genre.append('G008')
            genre.append('G016')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == '中華':
            genre.append('G007')
            genre.append('G013')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == 'イタリアン':
            genre.append('G006')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == 'スイーツ':
            genre.append('G014')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == 'その他':
            genre.append('G001')
            genre.append('G002')
            genre.append('G003')
            genre.append('G009')
            genre.append('G010')
            genre.append('G011')
            genre.append('G012')
            genre.append('G015')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        else:
            line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='料理のジャンルは洋食、和食、中華、イタリアン、スイーツ、その他から選択してください。' + '\n' + 'もう一度入力してください。')
            )
        
        #check_placeでやってもどうせ情報消えるからここでこの処理
        querystring = {'key' : "xxxxxxxxxxxxxxxxxx", "lat":float(ret.latlng[0]), "lng":float(ret.latlng[1]), "range":5, "format": "json", "genre":[]}
        
        '''
        headers = {
            'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
            'x-rapidapi-key': "xxxxxxxxxxxxxxxxxxxxxxxxxx"
            }
        '''

        for g in genre:
            querystring['genre'].append(g)

        response = requests.request("GET", url, params=querystring)
        j = json.loads(response.text)
        ans_restaurant(j, place_name)

        success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)

    elif kwargs['state'] == 'check_restaurant': 

        url = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
        success, place_name = select_one("SELECT plece from state_table WHERE id =:id", **kwargs)
        success, genre_name = select_one("SELECT genre from state_table WHERE id =:id", **kwargs)

        place_name = place_name[0]
        ret = geocoder.osm(place_name, timeout=5.0)

        #place_name = select_one("SELECT place from state_table WHERE id =:id", **kwargs)
        input_genre = genre_name[0]
        genre = []
        
        #先に今日明日の処理('-'含まれてないから)
        if input_genre == '洋食':
            genre.append('G005')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == '和食':
            genre.append('G004')
            genre.append('G008')
            genre.append('G016')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == '中華':
            genre.append('G007')
            genre.append('G013')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == 'イタリアン':
            genre.append('G006')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == 'スイーツ':
            genre.append('G014')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        elif input_genre == 'その他':
            genre.append('G001')
            genre.append('G002')
            genre.append('G003')
            genre.append('G009')
            genre.append('G010')
            genre.append('G011')
            genre.append('G012')
            genre.append('G015')
            #success = update("UPDATE state_table SET last_update=:now, state='check_resutaurant' WHERE id=:id", **kwargs)
        else:
            line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='料理のジャンルは洋食、和食、中華、イタリアン、スイーツ、その他から選択してください。' + '\n' + 'もう一度入力してください。')
            )
        
        #check_placeでやってもどうせ情報消えるからここでこの処理
        querystring = {'key' : "xxxxxxxxxxxxxxxx", "lat":float(ret.latlng[0]), "lng":float(ret.latlng[1]), "range":5, "format": "json", "genre":[]}
        
        '''
        headers = {
            'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
            'x-rapidapi-key': "xxxxxxxxxxxxxxxxxxxxxxxxxx"
            }
        '''

        for g in genre:
            querystring['genre'].append(g)

        response = requests.request("GET", url, params=querystring)
        j = json.loads(response.text)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='行きたい店の名前を入力してください。'+ '\n' + 'その店に関する詳しい情報を表示します。')
            )

        input_detail = input()

        text_line = ''

        for k in range (len(j['results']['shop'])):
            if input_detail == j['results']['shop'][k]['name']:
                adress = j['results']['shop'][k]['address']
                urls = j['results']['shop'][k]['urls']['pc']
                cost = j['results']['shop'][k]['budget']['name']
                open = j['results']['shop'][k]['open']
                text_line += '住所: ' + str(adress) + '\n' + 'URL: ' + str(urls) + '\n' + '予算: ' + str(cost) + '\n' + '営業時間: ' + str(open) + '\n'
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text= text_line)
                    )
                exit(1)
            
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='入力された店名は上記に含まれません。'+ '\n' + 'もう一度入力してください。')
            )
        input_detail = input()





@app.route('/', methods=['GET'])
def index():
    success, result = select_all(
        "SELECT id, name, state, place, last_update FROM state_table"
        )
    if result is None or len(result) == 0:
        return 'データベースを読みだせませんでした。'
    html = '<table><tr><td>ID</td><td>名前</td><td>状態</td><td>場所</td><td>最終更新日時</td></tr>'
    for row in result:
        html += '<tr>'
        for d in row:
            html += f'<td>{d}</td>'
        html += '</tr>'
    html += '</table>'
    return html

def index_old():
    #いままでのメッセージをSQLから読み出す
    stmt = sqlalchemy.text('SELECT time, user_id, user_name, message FROM history ORDER BY time DESC')
    try:
        with db.connect() as conn:
            result = conn.execute(stmt).fetchall()
    except:
        result = None
    if result is None or len(result) == 0:
        return 'データベースを読みだせませんでした。'

    html = '<table><tr><td>日時</td><td>ID</td><td>名前</td><td>メッセージ</td></tr>'
    for row in result:
        html += '<tr>'
        for d in row:
            html += f'<td>{d}</td>'
        html += '</tr>'
    html += '</table>'
    return html

##### ここからはSQL
def init_connection_engine():
    db_config = {
        # [START cloud_sql_mysql_sqlalchemy_limit]
        # Pool size is the maximum number of permanent connections to keep.
        "pool_size": 5,
        # Temporarily exceeds the set pool_size if no connections are available.
        "max_overflow": 2,
        # The total number of concurrent connections for your application will be
        # a total of pool_size and max_overflow.
        # [END cloud_sql_mysql_sqlalchemy_limit]
        # [START cloud_sql_mysql_sqlalchemy_backoff]
        # SQLAlchemy automatically uses delays between failed connection attempts,
        # but provides no arguments for configuration.
        # [END cloud_sql_mysql_sqlalchemy_backoff]
        # [START cloud_sql_mysql_sqlalchemy_timeout]
        # 'pool_timeout' is the maximum number of seconds to wait when retrieving a
        # new connection from the pool. After the specified amount of time, an
        # exception will be thrown.
        "pool_timeout": 30,  # 30 seconds
        # [END cloud_sql_mysql_sqlalchemy_timeout]
        # [START cloud_sql_mysql_sqlalchemy_lifetime]
        # 'pool_recycle' is the maximum number of seconds a connection can persist.
        # Connections that live longer than the specified amount of time will be
        # reestablished
        "pool_recycle": 1800,  # 30 minutes
        # [END cloud_sql_mysql_sqlalchemy_lifetime]
    }

    if os.environ.get("DB_HOST"):
        return init_tcp_connection_engine(db_config)
    else:
        return init_unix_connection_engine(db_config)


def init_tcp_connection_engine(db_config):
    # [START cloud_sql_mysql_sqlalchemy_create_tcp]
    # Remember - storing secrets in plaintext is potentially unsafe. Consider using
    # something like https://cloud.google.com/secret-manager/docs/overview to help keep
    # secrets secret.
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]
    db_name = os.environ["DB_NAME"]
    db_host = os.environ["DB_HOST"]

    # Extract host and port from db_host
    host_args = db_host.split(":")
    db_hostname, db_port = host_args[0], int(host_args[1])

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
        sqlalchemy.engine.url.URL(
            drivername="mysql+pymysql",
            username=db_user,  # e.g. "my-database-user"
            password=db_pass,  # e.g. "my-database-password"
            host=db_hostname,  # e.g. "127.0.0.1"
            port=db_port,  # e.g. 3306
            database=db_name,  # e.g. "my-database-name"
        ),
        # ... Specify additional properties here.
        # [END cloud_sql_mysql_sqlalchemy_create_tcp]
        **db_config
        # [START cloud_sql_mysql_sqlalchemy_create_tcp]
    )
    # [END cloud_sql_mysql_sqlalchemy_create_tcp]

    return pool


def init_unix_connection_engine(db_config):
    # [START cloud_sql_mysql_sqlalchemy_create_socket]
    # Remember - storing secrets in plaintext is potentially unsafe. Consider using
    # something like https://cloud.google.com/secret-manager/docs/overview to help keep
    # secrets secret.
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]
    db_name = os.environ["DB_NAME"]
    db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
    cloud_sql_connection_name = os.environ["CLOUD_SQL_CONNECTION_NAME"]

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@/<db_name>?unix_socket=<socket_path>/<cloud_sql_instance_name>
        sqlalchemy.engine.url.URL(
            drivername="mysql+pymysql",
            username=db_user,  # e.g. "my-database-user"
            password=db_pass,  # e.g. "my-database-password"
            database=db_name,  # e.g. "my-database-name"
            query={
                "unix_socket": "{}/{}".format(
                    db_socket_dir,  # e.g. "/cloudsql"
                    cloud_sql_connection_name)  # i.e "<PROJECT-NAME>:<INSTANCE-REGION>:<INSTANCE-NAME>"
            }
        ),
        # ... Specify additional properties here.

        # [END cloud_sql_mysql_sqlalchemy_create_socket]
        **db_config
        # [START cloud_sql_mysql_sqlalchemy_create_socket]
    )
    # [END cloud_sql_mysql_sqlalchemy_create_socket]

    return pool

# よくつかうやつ
def update(stmt_text, **kwargs):
    success = True
    stmt = sqlalchemy.text(stmt_text)
    try:
        with db.connect() as conn:
            conn.execute(stmt, **kwargs)
    except:
        success = False
    return success

def insert(stmt_text, **kwargs):
    success = True
    stmt = sqlalchemy.text(stmt_text)
    try:
        with db.connect() as conn:
            conn.execute(stmt, **kwargs)
    except:
        success = False
    return success

def select_one(stmt_text, **kwargs):#IDは一つ
    success = True
    stmt = sqlalchemy.text(stmt_text)
    try:
        with db.connect() as conn:
            result = conn.execute(stmt, **kwargs).fetchone()
    except:
        success = False
        result = None
    return success, result#resultを使う

def select_all(stmt_text, **kwargs):
    success = True
    stmt = sqlalchemy.text(stmt_text)
    try:
        with db.connect() as conn:
            result = conn.execute(stmt, **kwargs).fetchall()
    except:
        success = False
        result = None
    return success, result

# 重要 db初期化
db = init_connection_engine()
##### ここまでSQL


if __name__ == "__main__":
   app.run(host='127.0.0.1', port=8080, debug=True)