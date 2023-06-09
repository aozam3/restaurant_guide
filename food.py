
import requests
import json

#緯度経度用
import geocoder    
from datetime import datetime, date, timedelta

#位置情報からお店の情報を出力するサイト
url = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"


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

#ジャンル処理
print('\n' + 'どんな料理を食べたいですか？')
print('例：洋食、和食、中華、イタリアン、スイーツ、その他から選択してください'+'\n')

genre = []

while True:
  input_genre = str(input())

  if input_genre == '洋食':
    genre.append('G005')
    break
  elif input_genre == '和食':
    genre.append('G004')
    genre.append('G008')
    genre.append('G016')
    break
  elif input_genre == '中華':
    genre.append('G007')
    genre.append('G013')
    break
  elif input_genre == 'イタリアン':
    genre.append('G006')
    break
  elif input_genre == 'スイーツ':
    genre.append('G014')
    break
  elif input_genre == 'その他':
    genre.append('G001')
    genre.append('G002')
    genre.append('G003')
    genre.append('G009')
    genre.append('G010')
    genre.append('G011')
    genre.append('G012')
    genre.append('G015')
    break

  print('料理のジャンルは洋食、和食、中華、イタリアン、スイーツ、その他から選択してください。')
  print('もう一度入力してください'+ '\n')


#API処理
querystring = {'key' : "xxxxxxxxxxxxxx", "lat":float(ret.latlng[0]), "lng":float(ret.latlng[1]), "range":5, "format": "json", "genre":[]}

#print(genre)
for g in genre:
  #print(g)
  querystring['genre'].append(g)


response = requests.request("GET", url, params=querystring)
#print(response.url)
#print(response.text)
j = json.loads(response.text)

#お店の出力
def ans_restaurant(j, place_name):
  if j['results']['results_available'] == 0:
    print('お店は存在しません。')
    exit(1)
  else:
    print('\n' + place_name + '付近のお店は')
    for i in range (len(j['results']['shop'])):
      x = j['results']['shop'][i]['name']
      u = j['results']['shop'][i]['access']
      y = j['results']['shop'][i]['genre']['catch']
      print('店名: ' + str(x)+ '\n' + '住所: ' + str(u)+ '\n' + '概要: ' + str(y))
      print()

ans_restaurant(j, place_name)

print("行きたい店の名前を入力してください")
print("その店に関する詳しい情報を表示します。"+'\n')
input_detail = input()

#詳しい情報の出力
while True:
  for k in range (len(j['results']['shop'])):
    if input_detail == j['results']['shop'][k]['name']:
      adress = j['results']['shop'][k]['address']
      urls = j['results']['shop'][k]['urls']['pc']
      cost = j['results']['shop'][k]['budget']['name']
      open = j['results']['shop'][k]['open']
      print('住所: ' + str(adress))
      print('URL: ' + str(urls))
      print('予算: ' + str(cost))
      print('営業時間: ' + str(open))
      exit(1)
  
#  if Flag == False:
#    break

  print('入力された店名は上記に含まれません。')
  print('もう一度入力してください'+ '\n')
  place_name = input()
