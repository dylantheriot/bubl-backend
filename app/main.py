from flask import Flask
from flask import request
from flask import Response
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

# start flask
app = Flask(__name__)
cors = CORS(app, resources={r"*": {"origins": "*"}})

@app.route('/')
def hello_world():
  return 'Hello, World!'

@app.route('/create-user', methods=['POST'])
def create_user():
  new_user_uuid = request.get_json()['uuid']
  new_user = db.collection('users').document(new_user_uuid)
  if new_user.get().exists:
    print('user already exists')
    return 'Already exists', 200
  else:
    new_user.set({
      u'refresh_token': '',
      u'access_token': '',
      u'is_spotify_connected': False,
      u'expires_in': datetime.datetime.now()
    })

  return 'Success', 200


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
    doc_ref.set({
        u'refresh_token': res['refresh_token'],
        u'access_token': res['access_token'],
        u'is_spotify_connected': True,
        u'expires_in': expires_in
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
        song = {
          'artist': item['artists'][0]['name'],
          'track': item['name'],
          'album': item['album']['name'],
          'track_img': item['album']['images'][0]['url'],
          'embed_url': item['external_urls']['spotify'] 
        }
        json_res.append(song)
    elif search_type == 'playlist':
      for item in res['playlists']['items']:
        playlist = {
          'name': item['name'],
          'desc': item['description'],
          'playlist_img': item['images'][0]['url'],
          'embed_url': item['external_urls']['spotify']
        }
        json_res.append(playlist)
    elif search_type == 'album':
      for item in res['albums']['items']:
        album = {
          'name': item['name'],
          'artist': item['artists'][0]['name'],
          'album_img': item['images'][0]['url'],
          'release_date': item['release_date'],
          'embed_url': item['external_urls']['spotify']
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
    playlist = {
      'name': item['name'],
      'desc': item['description'],
      'playlist_img': item['images'][0]['url'],
      'embed_url': item['external_urls']['spotify']
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
    song = {
      'artist': item['artists'][0]['name'],
      'track': item['name'],
      'album': item['album']['name'],
      'track_img': item['album']['images'][0]['url'],
      'embed_url': item['external_urls']['spotify'] 
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
    now = datetime.datetime.now()
    doc_ref = db.collection(u'users').document(uuid)
    user_data = doc_ref.get().to_dict()
    if user_data['expires_in'].replace(tzinfo=None) < now:
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
    videos.append({'link': 'https://www.youtube.com/watch?v=%s' % (search_result['id']['videoId']) })
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