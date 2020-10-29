from flask import Flask
from flask import request
import base64
import requests
import datetime
from urllib.parse import urlencode
from flask import redirect
from dotenv import load_dotenv
from .spotifyApi import SpotifyAPI
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
import json

# load environment variables
load_dotenv()

# load firebase
cred = credentials.Certificate({
  "type": os.environ['FIREBASE_TYPE'],
  "project_id": os.environ['FIREBASE_PROJECT_ID'],
  "private_key_id": os.environ['FIREBASE_PRIVATE_KEY_ID'],
  "private_key": json.dumps(os.environ['FIREBASE_PRIVATE_KEY']),
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

# start flask
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/spotify/connect')
def spotify_connect():
  uuid = request.args.get('uuid')
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
    return "<h1> Spotify connected successfully! You may now close this tab</h1>"

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