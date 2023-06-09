import os
import sqlalchemy
from flask import Flask, request, abort
import json
import requests
import datetime

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
    #kwargs['place'] = '東京'#場所の入力
    kwargs['now']=datetime.datetime.utcnow() + datetime.timedelta(hours=9)#最終時刻の取得
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

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='天気アプリを起動します。場所を入力してください。')
             )
        return

    kwargs['state'] = result[0]

    if kwargs['state'] == 'wakeup':
        # 起動した。場所待ち
        kwargs['place'] = text # 発言はおそらく場所名

        # 場所が正しいか判定
        pass

        stmt_text = "UPDATE state_table SET last_update=:now, state='wakeup', place=:place WHERE id=:id"
        success = update(stmt_text, **kwargs)#場所の登録、状態はAPIからの情報待ち
        if not success:
            kwargs['message'] = stmt_text
            reply_message_error(event, str(kwargs))
            return

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='日時を入力してください。')
            )
        return

    elif kwargs['state'] == 'wait_date':
        # 起動した。場所待ち
        success = update("UPDATE state_table SET last_update=:now, state='xxx' WHERE id=:id", **kwargs)#場所の登録、状態はAPIからの情報待ち
    else:
        #状態をwakeupへ変更
        success = update("UPDATE state_table SET last_update=:now, state='wakeup' WHERE id=:id", **kwargs)#場所の登録、状態はAPIからの情報待ち

    # デバッグ用

    line_bot_api.push_message(
        user_id,
        TextSendMessage(text='これはデバッグメッセージです。'+str(kwargs))
        )

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
