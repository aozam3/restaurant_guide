

import requests
import json

#緯度経度用
import geocoder    
from datetime import datetime, date, timedelta

#位置情報から天気予報を出力するサイト
url = "https://community-open-weather-map.p.rapidapi.com/forecast"



print("知りたい地名を入力してください")
print("例：早稲田大学"+'\n')
place_name = input()

#地名を緯度と経度に変換
ret = geocoder.osm(place_name, timeout=5.0)


Flag = True
while Flag:
  #ret.latingは正しい地名が入力された時に緯度と経度が格納される
  # 存在しない地名が入力された場合，Noneのまま  
  if ret.latlng == None:
      print('入力された地名を表示することは出来ません。')
      print('もう一度入力してください'+ '\n')
      place_name = input()
      #地名を緯度と経度に変換
      ret = geocoder.osm(place_name, timeout=5.0)
  else:
        Flag = False




##ここから
querystring = {"lat":int(ret.latlng[0]),"lon":int(ret.latlng[1])}

headers = {
    'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
    'x-rapidapi-key': "xxxxxxxxxxxxxxxxxxxxxxxxxx"
    }

response = requests.request("GET", url, headers=headers, params=querystring)
j = json.loads(response.text)
##ここまで無視


#天気の出力　無視
def ans_weather(j,input_day,place_name):
    print('\n' + place_name + 'の' + input_day + 'の天気は')
    print('時間  気温 天気')
    for i in range (len(j['list'])):
      if input_day in j['list'][i]['dt_txt']:
            flag = 1   
            x = j['list'][i]['main']['temp']
            y = str(int(x - 273)) + '℃'
            w = j['list'][i]['weather'][0]['main']
            t = j['list'][i]['dt_txt']
            
            print(t[11:16]+' '+str(y)+'  '+w)



#日付処理
while True:
    print('\n' + 'いつの天気を知りたいですか。最大5日間を表示させることが出来ます。')
    print('2020-01-01' + '\n' + 'のように半角で入力してください'+'\n')
    print('今日もしくは明日の天気を知りたい場合は「今日」「明日」「明後日」でも構いません。'+'\n')

    input_day = str(input())

    #先に今日明日の処理('-'含まれてないから)
    if input_day == '今日':
          ans_weather(j,str(datetime.today())[:10],place_name)
          break
    elif input_day == '明日':
          tomorrow = datetime.today() + timedelta(days =1)
          ans_weather(j,str(tomorrow)[:10],place_name)
          break
    elif input_day == '明後日':
          after_tomorrow = datetime.today() + timedelta(days =2)
          ans_weather(j,str(after_tomorrow)[:10],place_name)
          break
    
    input_day_list = input_day.split('-')
    today = datetime.today()
    days_list = []
    for i in range(0, 5):
            i_day = today + timedelta(days = i)
            days_list.append(datetime.strftime(i_day, '%Y-%m-%d'))
    if len(input_day_list) == 3 and input_day in days_list:
        ans_weather(j,input_day,place_name)
        break
    else:
        print('全角の入力、5日間に収まっていない可能性があります。')

