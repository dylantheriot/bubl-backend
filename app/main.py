from flask import Flask
from flask import request
from flask import Response
import urllib
import base64
import requests
import datetime
from urllib.parse import urlencode
from flask import redirect
from .spotifyApi import SpotifyAPI
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
import json
from flask_cors import CORS
import random
import string

# YouTube
import argparse
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# THREE THINGS TO CHANGE WHEN RUNNING LOCALLY:
# 1) add dotenv stuff
# 2) add json.loads() to private_key init
# 3) change redirect_uri in spotifyApi to localhost

# load environment variables
# from dotenv import load_dotenv
# load_dotenv()

# load firebase
cred = credentials.Certificate({
  "type": os.environ['FIREBASE_TYPE'],
  "project_id": os.environ['FIREBASE_PROJECT_ID'],
  "private_key_id": os.environ['FIREBASE_PRIVATE_KEY_ID'],
  "private_key": json.loads(os.environ['FIREBASE_PRIVATE_KEY']),
  # "private_key": os.environ['FIREBASE_PRIVATE_KEY'],
  "client_email": os.environ['FIREBASE_CLIENT_EMAIL'],
  "client_id": os.environ['FIREBASE_CLIENT_ID'],
  "auth_uri": os.environ['FIREBASE_AUTH_URI'],
  "token_uri": os.environ['FIREBASE_TOKEN_URI'],
  "auth_provider_x509_cert_url": os.environ['FIREBASE_AUTH_PROVIDER_X509_CERT_URL'],
  "client_x509_cert_url": os.environ['FIREBASE_CLIENT_X509_CERT_URL']
})
firebase_admin.initialize_app(cred)
db = firestore.client()

# load spotify object
spotify = SpotifyAPI()

# load youtube object
youtube = build('youtube', 'v3', developerKey=os.environ['YOUTUBE_DEVELOPER_KEY'])

giphy_key = os.environ['GIPHY_API_KEY']

# start flask
app = Flask(__name__)
cors = CORS(app, resources={r"*": {"origins": "*"}})

@app.route('/')
def hello_world():
  return 'Hello, World!'

@app.route('/create-user', methods=['POST'])
def create_user():
  new_user_uuid = request.get_json()['uuid']
  name = request.get_json()['name'].lower()
  profile_image = request.get_json()['profile_image']
  new_user = db.collection('users').document(new_user_uuid)
  if new_user.get().exists:
    print('user already exists')
    return 'Already exists', 200
  else:
    bubl_name = '-'.join(name.split()) + '-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    bubl_name_collection = db.collection('bubl-name').document(bubl_name)
    new_user.set({
      u'refresh_token': '',
      u'access_token': '',
      u'is_spotify_connected': False,
      u'expires_in': datetime.datetime.now(),
      u'bio': '',
    })
    bubl_name_collection.set({
      u'google_id': new_user_uuid,
      u'profile_image': profile_image,
      u'name': name,
    })
    search_text = db.collection('search').document('names')
    list_names = search_text.get().to_dict()['list_names']
    list_names.append(bubl_name)
    search_text.set({
      u'list_names': list_names
    })

  return 'Success', 200

@app.route('/users/search')
def search_for_users():
  bubl_search = request.args.get('query')
  search_text = db.collection('search').document('names')
  list_names = search_text.get().to_dict()['list_names']
  potential_users = set()
  bubl_search = bubl_search.split()
  for searchedName in bubl_search:
    for name in list_names:
      if searchedName in name and name not in potential_users:
        potential_users.add(name)
  
  json_res = []
  for name in potential_users:
    curr_person = db.collection('bubl-name').document(name).get().to_dict()
    bio = db.collection('users').document(curr_person['google_id']).get().to_dict()['bio']
    person = {
      'google_id': curr_person['google_id'],
      'profile_image': curr_person['profile_image'],
      'name': curr_person['name'],
      'bio': bio,
      'bubl_name': name,
    }
    json_res.append(person)

  json_res = json.dumps({'result': json_res})
  return Response(json_res, mimetype="application/json")

@app.route('/users/get')
def get_specific_user():
  bubl_name = request.args.get('bubl')
  user = db.collection('bubl-name').document(bubl_name)
  user_data = user.get().to_dict()
  curr_user = {
    'displayName': user_data['name'],
    'photoURL': user_data['profile_image'],
    'uid': user_data['google_id'],
  }
  json_res = json.dumps({'user': curr_user})
  return Response(json_res, mimetype="application/json")


  
# SPOTIFY ENDPOINTS
@app.route('/spotify/connect')
def spotify_connect():
  uuid = request.args.get('uuid')
  
  # check to see if Spotify is already connected
  doc_ref = db.collection(u'users').document(uuid)
  user_data = doc_ref.get().to_dict()
  if user_data['is_spotify_connected']:
    return redirect('/spotify/connect_complete')

  oauth_url = spotify.return_auth_url(uuid)
  return redirect(oauth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    uuid = request.args.get('state')
    res = spotify.request_refresh_token_from_auth_code(code)
    expires_in = datetime.datetime.now() + datetime.timedelta(seconds=res['expires_in'])
    doc_ref = db.collection(u'users').document(uuid)
    doc_ref.update({
        u'refresh_token': res['refresh_token'],
        u'access_token': res['access_token'],
        u'is_spotify_connected': True,
        u'expires_in': expires_in,
    })
    return redirect('/spotify/connect_complete')

@app.route('/spotify/connect_complete')
def spotify_connection_complete():
    return "<h1> Spotify connected successfully! You may now close this tab</h1>"

@app.route('/spotify/search')
def spotify_search():
    query = request.args.get('query')
    search_type = request.args.get('search_type')
    res = spotify.search(query, search_type)
    # return res

    json_res = []
    if search_type == 'track':
      for item in res['tracks']['items']:
        uri = item['uri'].split(':')[2]
        song = {
          'artist': item['artists'][0]['name'],
          'track': item['name'],
          'album': item['album']['name'],
          'track_img': item['album']['images'][0]['url'],
          'embed_url': 'https://open.spotify.com/embed/track/' + uri
        }
        json_res.append(song)
    elif search_type == 'playlist':
      for item in res['playlists']['items']:
        uri = item['uri'].split(':')[2]
        playlist = {
          'name': item['name'],
          'desc': item['description'],
          'playlist_img': item['images'][0]['url'],
          'embed_url': 'https://open.spotify.com/embed/playlist/' + uri
        }
        json_res.append(playlist)
    elif search_type == 'album':
      for item in res['albums']['items']:
        uri = item['uri'].split(':')[2]
        album = {
          'name': item['name'],
          'artist': item['artists'][0]['name'],
          'album_img': item['images'][0]['url'],
          'release_date': item['release_date'],
          'embed_url': 'https://open.spotify.com/embed/album/' + uri
        }
        json_res.append(album)
    json_res = json.dumps({'result': json_res})
    return Response(json_res, mimetype="application/json")

@app.route('/spotify/user/playlists')
def get_spotify_user_playlists():
  uuid = request.args.get('uuid')
  access_token = get_access_token(uuid)
  url = "https://api.spotify.com/v1/me/playlists"
  res = spotify.get_users_data_wrapper(url, access_token)
  # return res

  json_res = []
  for item in res['items']:
    uri = item['uri'].split(':')[2]
    playlist = {
      'name': item['name'],
      'desc': item['description'],
      'playlist_img': item['images'][0]['url'],
      'embed_url': 'https://open.spotify.com/embed/playlist/' + uri
    }
    json_res.append(playlist)
  json_res = json.dumps({'result': json_res})
  return Response(json_res, mimetype="application/json")

@app.route('/spotify/user/saved_albums')
def get_spotify_user_saved_albums():
  uuid = request.args.get('uuid')
  access_token = get_access_token(uuid)
  url = "https://api.spotify.com/v1/me/albums"
  res = spotify.get_users_data_wrapper(url, access_token)
  return res

@app.route('/spotify/user/saved_shows')
def get_spotify_user_saved_shows():
  uuid = request.args.get('uuid')
  access_token = get_access_token(uuid)
  url = "https://api.spotify.com/v1/me/shows"
  res = spotify.get_users_data_wrapper(url, access_token)
  return res

@app.route('/spotify/user/saved_tracks')
def get_spotify_user_saved_tracks():
  uuid = request.args.get('uuid')
  access_token = get_access_token(uuid)
  url = "https://api.spotify.com/v1/me/tracks"
  res = spotify.get_users_data_wrapper(url, access_token)
  # return res

  json_res = []
  for item in res['items']:
    item = item['track']
    uri = item['uri'].split(':')[2]
    song = {
      'artist': item['artists'][0]['name'],
      'track': item['name'],
      'album': item['album']['name'],
      'track_img': item['album']['images'][0]['url'],
      'embed_url': 'https://open.spotify.com/embed/track/' + uri
    }
    json_res.append(song)
  json_res = json.dumps({'result': json_res})
  return Response(json_res, mimetype="application/json")

@app.route('/spotify/user/following')
def spotify_user_following():
  uuid = request.args.get('uuid')
  access_token = get_access_token(uuid)
  url = "https://api.spotify.com/v1/me/following?type=artist"
  res = spotify.get_users_data_wrapper(url, access_token)
  return res

# spotify helper functions
def get_access_token(uuid):
  check_access_token_expired(uuid)
  doc_ref = db.collection(u'users').document(uuid)
  user_data = doc_ref.get().to_dict()
  return user_data['access_token']

def check_access_token_expired(uuid):
    now = datetime.datetime.now().replace(tzinfo=None)
    doc_ref = db.collection(u'users').document(uuid)
    user_data = doc_ref.get().to_dict()
    # TODO: only update access token when necessary
    # if user_data['expires_in'].replace(tzinfo=None) < now:
    #   print('expired')
    update_access_token(uuid)

def update_access_token(uuid):
    doc_ref = db.collection(u'users').document(uuid)
    user_data = doc_ref.get().to_dict()
    res = spotify.request_new_access_token(user_data['refresh_token'])
    expires_in = datetime.datetime.now() + datetime.timedelta(seconds=res['expires_in'])
    refresh_token = user_data['refresh_token']
    if 'refresh_token' in res.keys():
      refresh_token = res['refresh_token']
    doc_ref.update({
        u'access_token': res['access_token'],
        u'refresh_token': refresh_token,
        u'expires_in': expires_in,
    })

@app.route('/youtube/search')
def youtube_search():
  query = request.args.get('query')
  search_response = youtube.search().list(
  q=query,
  part='id,snippet',
  videoEmbeddable='true',
  maxResults=20,
  type='video'
  ).execute()
  
  videos = []
  for search_result in search_response.get('items', []):
    videos.append({'link': 'https://www.youtube.com/watch?v=%s' % (search_result['id']['videoId']), 'title': search_result['snippet']['title']})
  json_res = json.dumps({'videos': videos})
  return Response(json_res, mimetype='application/json')

@app.route('/users/board/get')
def get_users_items():
  uuid = request.args.get('uuid')
  board = db.collection('boards').document(uuid)
  if not board.get().exists:
    json_res = json.dumps({'items': []})
    return Response(json_res, mimetype="application/json")
  else:
    json_res = board.get().to_dict()
    return json_res

@app.route('/users/board/update', methods=['POST'])
def update_users_items():
  post = request.get_json()
  uuid = post['uuid']
  board = db.collection('boards').document(uuid)
  items = post['items']
  board.set({
    'items': items
  })
  return 'Successfully updated items', 200

@app.route('/users/bio/update', methods=['POST'])
def update_users_bio():
  post = request.get_json()
  uuid = post['uuid']
  updated_bio = post['updated_bio']
  user = db.collection('users').document(uuid)
  user.update({
    'bio': updated_bio
  })
  return 'Successfully updated bio', 200

@app.route('/users/bio/get')
def get_users_bio():
  uuid = request.args.get('uuid')
  user = db.collection('users').document(uuid).get().to_dict()
  json_res = json.dumps({'bio': user['bio']})
  return Response(json_res, mimetype="application/json")

@app.route('/giphy/search')
def giphy_search():
    q = request.args.get('query')

    if not q: 
      q = 'taylor swift'

    url = "http://api.giphy.com/v1/gifs/search?q="
    q = q.replace(" ", "+")
    url = url + q + "&api_key=" +giphy_key
    limit = "&limit=20" 
    url = url + limit
    data=json.loads(urllib.request.urlopen(url).read())
    json_res = []
    for obj in data['data']: 
      dicts = {
        'url' : obj['images']['downsized']['url'], 
        'title': obj['title']
      }
      json_res.append(dicts)
    json_res = json.dumps({'result': json_res})
    return Response(json_res, mimetype="application/json")


@app.route('/giphy/trending')
def giphy_trending(): 
  url = "http://api.giphy.com/v1/gifs/trending?&api_key="
  url = url+giphy_key
  offset = "&offset=25"
  url = url+offset
  data=json.loads(urllib.request.urlopen(url).read())

  json_res = []
  for obj in data['data']: 
    dicts = {
      'url' : obj['images']['downsized']['url'],
      'title': obj['title']
    }
    json_res.append(dicts)
  json_res = json.dumps({'result': json_res})
  return Response(json_res, mimetype="application/json")