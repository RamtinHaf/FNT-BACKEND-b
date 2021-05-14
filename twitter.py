from requests_oauthlib import OAuth1
import requests
from urllib.parse import parse_qs
from TwitterAPI import TwitterAPI


class TwitterAPI(object):
    def __init__(self, key, secret):
        self.ck = key
        self.cs = secret


    def requestAccessToken(self):
        r = requests.post(
            url='https://api.twitter.com/oauth/request_token',
            # for now let's use PIN-based auth, later we can adopt regular callback method.
            data={'oauth_callback': 'oob'},
            auth=OAuth1(self.ck, self.cs))

        data = parse_qs(r.content)
        key = data.get(b'oauth_token')[0]
        secret = data.get(b'oauth_token_secret')[0]
        return (key, secret)

    def getAccessToken(self, request_key, request_secret, verifier):
        r = requests.post(
            url='https://api.twitter.com/oauth/access_token', 
            auth=OAuth1(
                self.ck,
                self.cs,
                request_key,
                request_secret,
                verifier=verifier)
        )

        data = parse_qs(r.content)
        key = data.get(b'oauth_token')[0]
        secret = data.get(b'oauth_token_secret')[0]
        return (key, secret)
