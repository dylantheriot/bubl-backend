import base64
import requests
import datetime
from urllib.parse import urlencode
import os

class SpotifyAPI(object):
  access_token = None
  access_token_expires = datetime.datetime.now()
  access_token_did_expire = True
  client_id = None
  client_secret = None
  token_url = 'https://accounts.spotify.com/api/token'
  redirect_uri = 'http://127.0.0.1:5000/callback'
  # redirect_uri = 'https://bubl-backend.herokuapp.com/callback'
  
  def __init__(self):
    self.client_id = os.environ['CLIENT_ID']
    self.client_secret = os.environ['CLIENT_SECRET']
  
  def get_token_headers(self):
    client_creds = f"{self.client_id}:{self.client_secret}"
    client_creds_b64 = base64.b64encode(client_creds.encode())
    return {"Authorization": f"Basic {client_creds_b64.decode()}"}
  
  def get_access_token_headers(self, access_token):
    headers = {
      'Authorization': f'Bearer {access_token}',
    }
    return headers

  
  def get_token_data(self):
    return {"grant_type": "client_credentials"}
  
  def perform_auth(self):
    token_url = self.token_url
    token_data = self.get_token_data()
    token_headers = self.get_token_headers()
    r = requests.post(token_url, data=token_data, headers=token_headers)
    if r.status_code not in range(200,299):
        return False
    token_response_data = r.json()
    now = datetime.datetime.now()
    access_token = token_response_data['access_token']
    expires_in = token_response_data['expires_in']
    expires = now + datetime.timedelta(seconds=expires_in)
    self.access_token = access_token
    self.access_token_expires = expires
    self.access_token_did_expire = expires < now
    return True
  
  def get_access_token(self):
    auth_done = self.perform_auth()
    token = self.access_token
    expires = self.access_token_expires
    now = datetime.datetime.now()
    if expires < now:
        self.perform_auth()
        return self.get_access_token()
    elif token == None:
        self.perform_auth()
        return self.get_access_token()
    return token
  
  def get_resource_header(self):
    access_token = self.get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    return headers
  
  def get_resource(self, _id, resource_type="albums"):
    endpoint = f"https://api.spotify.com/v1/{resource_type}/{_id}"
    headers = self.get_resource_header()
    r = requests.get(endpoint, headers=headers)
    if r.status_code not in range(200,299):
        return {}
    return r.json()
  
  def get_album(self, _id):
    return self.get_resource(_id, resource_type='albums')
  
  def get_artist(self, _id):
    return self.get_resource(_id, resource_type='artists')
  
  def search(self, query, search_type='artist'):
    headers = self.get_resource_header()
    url = "https://api.spotify.com/v1/search"
    data = urlencode({
        "q": query, 
        "type": search_type
    })

    lookup_url = f"{url}?{data}"
    r = requests.get(lookup_url, headers=headers)
    if r.status_code not in range(200,299):
      return {}
    return r.json()

  def return_auth_url(self, user_id):
    url = "https://accounts.spotify.com/authorize?"
    headers = urlencode({
      "client_id": self.client_id,
      "response_type": "code",
      "redirect_uri": self.redirect_uri,
      "show_dialog": "true",
      "state": user_id,
      "scope": 'user-top-read playlist-read-private playlist-read-collaborative user-follow-read user-library-read'
    })
    new_url = f'{url}{headers}'
    return new_url
  
  def request_refresh_token_from_auth_code(self, auth_code):
    data = {
      'grant_type': 'authorization_code',
      'code': auth_code,
      'redirect_uri': self.redirect_uri
    }
    headers = self.get_token_headers()
    r = requests.post(self.token_url, data=data, headers=headers)
    return r.json()
  
  def request_new_access_token(self, refresh_token):
    data = {
    'grant_type': 'refresh_token',
    'refresh_token': refresh_token,
    }
    headers = self.get_token_headers()
    r = requests.post(self.token_url, data=data, headers=headers)
    return r.json()

  def get_users_data_wrapper(self, url, access_token):
    headers = self.get_access_token_headers(access_token)
    r = requests.get(url, headers=headers)
    return r.json()