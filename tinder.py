import random
import base64
import uuid
import os
import json
import time
import re
import urllib.parse
import asyncio
from logging import Logger
from datetime import datetime, timezone
from curl_cffi.requests import AsyncSession, WebSocket, Session
from threading import Thread

from deviceId_iOS import generateDeviceToken
#from deviceId_iOS_remote import generateDeviceToken

# TODO: blackboxprotobuf => protoc instead
import blackboxprotobuf
import blackboxprotobuf.lib.protofile as protofile
from blackboxprotobuf.lib.config import Config
config = Config()
typedef_map = protofile.import_proto(config, input_filename='./proto/tinder.proto')
config.known_types = typedef_map

# headers order: https://github.com/lexiforest/curl_cffi/issues/335
http_async_sesion = Session(
    verify=False,
    default_headers=False,
    impersonate="safari17_2_ios", # its not 14.2
    #http_version=2 # HTTP 1.1 (prevent HTTP2 framing layer error)
)

def generateAppsFlyerId() -> str:
    part1 = str(random.randint(0, int(1e13))).zfill(13)[:13]
    part2 = str(random.randint(0, int(1e16))).zfill(16) + str(random.randint(0, int(1e3))).zfill(3)
    return f"{part1}-{part2[:19]}"

def bytes2base64(b: bytes) -> str:
    return base64.b64encode(b).decode('utf-8')

# iOS     Tinder (max version)
# 14.2    14.21 (14.22+ require ios 15.0+;) | 13.24.0+- =>ios14.0+
class TinderClient:
    def __init__(
            self,
            userAgent: str = None, # Tinder/15.16.0 (iPhone; iOS 17.6; Scale/2.00) | Tinder Android Version 15.16.0
            proxy: str = None,
            persistentDeviceId: str = None, # hex: ios=16bytes, android=8bytes
            appSessionId: str = None, # ios=UUID, android=uuid => random each boot
            #appSessionStartTime: int = None, # ios=float, android=float:.3f
            installId: str = None, # ios=UUID, android=8bytes
            encodedDeviceModel: str = None, # base64: ios=iPhone16,2|iphone9,2, android=wp11
            encodedDeviceCarrier: str = 'd2lmaQ', # ios=EMPTY, android='wifi'<=>d2lmaQ=bytes2base64("wifi".encode()); QVQmVA== <=> AT&T
            mobileCountryCode: int = 310, # EMPTYable (MCC): United States of America
            mobileNetworkCode: int = 240, # EMPTYable (MNC): T-Mobile
            tinderVersion: str = "14.21.0",
            appVersion: str = "5546",
            storeVariant: str = None, # android only: Play-Store
            osVersion: int = 140000200000, # android=API_Level, ios=150000800002 (15.8.2) -> 140000200000 (14.2.0)
            platform: str = "ios", # ios, android
            platformVariant: str = None, # android only: Google-Play
            language: str = "en-us", # accept-language: en-GB,en;q=0.9
            funnelSessionId: str = None, # ios=16bytes, android=uuid => random each boot
            appsFlyerId: str = None, #ios=EMPTY
            advertisingId: str = None, # nullable
            refreshToken: str = None,
            userId: str = None,
            onboardingToken: str = None,
            xAuthToken: str = None,
            userSessionId: str = None,
            appId: str = None,
            userSessionStartTime: int = 0
    ):
        app_boot_time = random.uniform(40, 50) # random boot time
        if installId: # only when reload
            self.first_boot = False
        else:
            self.first_boot = True
        
        self.appSessionId = appSessionId or str(uuid.uuid4()).upper()
        #self.appSessionStartTime = appSessionStartTime or time.time() # null\
        self.appSessionStartTime = time.time() - app_boot_time
        self.persistentDeviceId = persistentDeviceId or os.urandom(16).hex()
        self.installId = installId or str(uuid.uuid4()).upper()
        self.encodedDeviceModel = encodedDeviceModel or bytes2base64(b"iphone9,2") # 7+ TODO: random model
        self.encodedDeviceCarrier = encodedDeviceCarrier
        self.mobileCountryCode = mobileCountryCode
        self.mobileNetworkCode = mobileNetworkCode
        self.tinderVersion = tinderVersion
        self.appVersion = appVersion
        self.storeVariant = storeVariant
        self.language = language
        self.platformVariant = platformVariant
        self.platform = platform
        self.osVersion = osVersion
        self.userAgent = userAgent or f"Tinder/{self.tinderVersion} (iPhone; iOS 14.2.0; Scale/2.00)" # TODO: osVersion
        #self.appsFlyerId = appsFlyerId or '' # generateAppsFlyerId() # ios=EMPTY
        self.appsFlyerId = appsFlyerId or generateAppsFlyerId() # ios=EMPTY or Value
        self.advertisingId = advertisingId or str(uuid.uuid4()) # android only?
        self.funnelSessionId = funnelSessionId or os.urandom(16).hex()
        self.onboardingToken = onboardingToken
        self.userId = userId
        self.refreshToken = refreshToken
        self.xAuthToken = xAuthToken
        if xAuthToken:
            # logged only (onboarding complete)
            self.userSessionId = userSessionId or str(uuid.uuid4()).upper()
            self.userSessionStartTime = time.time() - app_boot_time
        else:
            # skip it empty
            self.userSessionId = userSessionId
            self.userSessionStartTime = userSessionStartTime

        # NOTE: login will set app_id value (using phonenumber)
        # this need for ios_device_id spoof (pass Tinder but not Apple)
        self.app_id = appId or None
        
        self.httpProxy = proxy
        self.app_seconds = 0
        self.user_seconds = 0
        #self.x_device_ram = '3' # TODO: random RAM (android only)
        self.last_status_code = 0

        # on iOS, payload joined with previous
        self.onboardingPayload = []
        
        # android
        #self.URL_ONBOARDING = 'https://api.gotinder.com/v2/onboarding/fields?requested=tinder_rules&requested=name&requested=birth_date&requested=gender&requested=custom_gender&requested=show_gender_on_profile&requested=photos&requested=email&requested=allow_email_marketing&requested=consents&requested=schools&requested=interested_in_gender&requested=interested_in_genders&requested=show_same_orientation_first&requested=show_orientation_on_profile&requested=sexual_orientations&requested=user_interests&requested=relationship_intent&requested=distance_filter&requested=basics&requested=lifestyle'
        #self.URL_ONBOARDING_COMPLETE = 'https://api.gotinder.com/v2/onboarding/complete'
        
        # ios 14.21.0
        self.URL_ONBOARDING = 'https://api.gotinder.com/v2/onboarding/fields?requested=name&requested=birth_date&requested=gender&requested=custom_gender&requested=show_gender_on_profile&requested=photos&requested=schools&requested=consents&requested=videos_processing&requested=sexual_orientations&requested=show_same_orientation_first&requested=show_orientation_on_profile&requested=interested_in_gender&requested=user_interests&requested=distance_filter&requested=tinder_rules&requested=relationship_intent&requested=basics&requested=lifestyle'
        self.URL_ONBOARDING_PHOTO = self.URL_ONBOARDING.replace('/fields?', '/photo?', 1)
        self.URL_ONBOARDING_COMPLETE = self.URL_ONBOARDING.replace('/fields?', '/complete?', 1)

        self.URL_DEVICE_CHECK = 'https://api.gotinder.com/v2/device-check/ios'

    @staticmethod
    def fromObject(o: dict) -> 'TinderClient':
        return TinderClient(**o)
    
    def toObject(self) -> dict:
        o = {
            'appId': self.app_id,
            'userId': self.userId,
            'onboardingToken': self.onboardingToken,
            'refreshToken': self.refreshToken,
            'xAuthToken': self.xAuthToken,
            'persistentDeviceId': self.persistentDeviceId,
            'installId': self.installId,
            'userAgent': self.userAgent,
            'tinderVersion': self.tinderVersion,
            'appVersion': self.appVersion,
            'osVersion': self.osVersion,
            'platform': self.platform,
            #'platformVariant': self.platformVariant, # ANDROID only
            #'storeVariant': self.storeVariant, # ANDROID only
            #'appSessionId': self.appSessionId, # reload => new session => no need save
            #'appSessionStartTime': self.appSessionStartTime, # same as appSessionId
            'encodedDeviceModel': self.encodedDeviceModel,
            'encodedDeviceCarrier': self.encodedDeviceCarrier,
            #'mobileCountryCode': self.mobileCountryCode,
            #'mobileNetworkCode': self.mobileNetworkCode,
            'appsFlyerId': self.appsFlyerId,
            #'advertisingId': self.advertisingId, # looklike ANDROID only
            #'funnelSessionId': self.funnelSessionId, # reload => new session => no need save
            #'userSessionId': self.userSessionId, # reload => new session => no need save
            'language': self.language,
            #'userSessionStartTime': self.userSessionStartTime, # same as appSessionId
            'proxy' : self.httpProxy
        }

        return o

    def toJSON(self) -> str:
        return json.dumps(self.toObject(), indent=2)

    @staticmethod
    def fromJSON(s: str) -> 'TinderClient':
        return TinderClient.fromObject(json.loads(s))

    def loadProxy():
        print("fetch proxy...")
        ### C Proxy (local debug)
        #return None
        #return 'http://127.0.0.1:8080' # mitm
        #return 'http://192.168.1.188:8080' # burp
        #return 'http://127.0.0.1:8888' # fidder
        
        ### Kiran oxylabs
        # s = 'http://customer-kiranhi-cc-us-sessid-0721593567-sesstime-30:Simpletest1_@pr.oxylabs.io:7777'
        # lst = list(range(1, 40))
        # random.shuffle(lst)
        # for iter in lst:
        #     proxy = s.replace('721593567', str(721593567 + iter - 1))
        #     print(proxy)
        #     try:
        #         response = http_async_sesion.get(url="https://api64.ipify.org?format=text", proxy=proxy)
        #         ip = response.text
        #         print(ip)

        #         scamalytics_response = http_async_sesion.get(url="https://scamalytics.com/ip/" + ip)
        #         match = re.search(r'Fraud Score:\s*(\d+(?:\.\d+)?)', scamalytics_response.text, re.DOTALL)
        #         fraud_score = int(match.group(1))
                
        #         print("fraud_score: " + str(fraud_score))
        #         if fraud_score < 4:
        #             return proxy
        #     except: continue
        #     finally: print('--')
        # raise Exception()
        
        return None # TODO: 

    def getAppSessionTimeElapsed(self) -> float:
        self.app_seconds = time.time() - self.appSessionStartTime # Real delay with sleep
        #self.app_seconds += random.uniform(30, 90) # Fake appSessionStartTime
        return self.app_seconds

    def getUserSessionTimeElapsed(self) -> float:
        if self.userSessionStartTime == 0: return None # not yet
        self.user_seconds = time.time() - self.userSessionStartTime
        return self.user_seconds

    def assignDecodedValues(self, response: dict):
        data = next(iter(response.values()))
        if type(data) is not dict:
            return
        
        if 'refresh_token' in data:
            self.refreshToken = data['refresh_token']
            if type(self.refreshToken) is dict: self.refreshToken = self.refreshToken['value']
            print("refresh_token: " + self.refreshToken)

        if 'user_id' in data:
            self.userId = data['user_id']
            if type(self.userId) is dict: self.userId = self.userId['value']
            print("userId: " + self.userId)

        if 'onboarding_token' in data:
            self.onboardingToken = data['onboarding_token']
            if type(self.onboardingToken) is dict: self.onboardingToken = self.onboardingToken['value']
            print("onboardingToken: " + self.onboardingToken)
        if 'auth_token' in data:
            self.xAuthToken = data['auth_token']
            if type(self.xAuthToken) is dict: self.xAuthToken = self.xAuthToken['value']
            print("xAuthToken: " + self.xAuthToken)
            self.onboardingToken = None # registered
        
        if 'auth_token_ttl' in data: # LoginResult login_result
            self.userSessionId = str(uuid.uuid4()).upper()
            self.userSessionStartTime = time.time()
            print("userSessionId: " + self.userSessionId)

    def _getHeaders_POST_Protobuf(self):
        headers = {
            "Accept": "application/x-protobuf", # ios only
            "persistent-device-id": self.persistentDeviceId,
            "User-Agent": self.userAgent,
            "encoded-device-carrier": self.encodedDeviceCarrier,
            "x-hubble-entity-id": str(uuid.uuid4()), # ios only
            "os-version": str(self.osVersion),
            "Locale": "en",
            "app-session-time-elapsed": None,
            "encoded-device-model": self.encodedDeviceModel,
            "Content-Length": None, # order
            "x-supported-image-formats": "webp, jpeg",
            "platform": self.platform,
            "install-id": self.installId,
            'appsflyer-id': self.appsFlyerId,
            "user-session-time-elapsed": None,
            'mobile-country-code': '',
            "Accept-Language": self.language,
            "tinder-version": self.tinderVersion,
            'funnel-session-id': self.funnelSessionId, # only: proto, onboarding
            'mobile-network-code': '',
            "Accept-Encoding": "gzip, deflate, br",
            "supported-auth-options": "apple,facebook,line,sms",
            "Content-Type": 'application/x-google-protobuf',
            "app-version": str(self.appVersion),
            "user-session-id": None,
            "app-session-id": None,
            #"X-Auth-Token": None, proto not include
        }

        # continue onboarding
        if self.xAuthToken:
            #headers['X-Auth-Token'] = self.xAuthToken
            headers['app-session-id'] = self.appSessionId
            headers["app-session-time-elapsed"] = f"{self.getAppSessionTimeElapsed()}"
            headers['user-session-id'] = self.userSessionId
            headers["user-session-time-elapsed"] = f"{self.getUserSessionTimeElapsed()}"
        else:
            headers['app-session-id'] = self.appSessionId
            headers["app-session-time-elapsed"] = f"{self.getAppSessionTimeElapsed()}"
        
        l = list(headers.items())
        r = random.randint(0, 1)
        if r == 1:
            index1 = [i for i, (k, _) in enumerate(l) if k == "User-Agent"][0]
            index2 = [i for i, (k, _) in enumerate(l) if k == "persistent-device-id"][0]
            tmp = l[index1]
            l[index1] = l[index2]
            l[index2] = tmp

        headers = dict(l)
        return headers

    def _getHeaders_POST_JSON(self):
        headers = {
            "os-version": str(self.osVersion),
            "persistent-device-id": self.persistentDeviceId,
            "User-Agent": self.userAgent,
            "support-short-video": None, # only: boot, leads
            "x-refresh-token": None,
            "x-hubble-entity-id": str(uuid.uuid4()), # ios only
            "app-session-time-elapsed": None,
            "Content-Length": None, # order
            "X-Auth-Token": None, # SWIPE
            "x-supported-image-formats": "webp, jpeg",
            "token": None, # ONBOARDING
            "platform": self.platform,
            "appsflyer-id": None, # ONBOARDING complete only
            "user-session-time-elapsed": None,
            "Accept-Language": self.language,
            "tinder-version": self.tinderVersion,
            "Accept": "application/json", # ios only
            "Content-Type": 'application/json; charset=UTF-8',
            "app-version": str(self.appVersion),
            "user-session-id": None,
            "funnel-session-id": None, # only: proto, onboarding
            "Accept-Encoding": "gzip, deflate, br",
            "app-session-id": None,
        }

        # continue onboarding
        if self.xAuthToken:
            headers['X-Auth-Token'] = self.xAuthToken
            headers['app-session-id'] = self.appSessionId
            headers["app-session-time-elapsed"] = f"{self.getAppSessionTimeElapsed()}"
            headers['user-session-id'] = self.userSessionId
            headers["user-session-time-elapsed"] = f"{self.getUserSessionTimeElapsed()}"
        elif self.onboardingToken:
            headers['app-session-id'] = self.appSessionId
            headers["app-session-time-elapsed"] = f"{self.getAppSessionTimeElapsed()}"
        
        ### random swap index
        l = list(headers.items())
        r = random.randint(0, 1)
        if r == 1:
            index1 = [i for i, (k, _) in enumerate(l) if k == "app-session-id"][0]
            index2 = [i for i, (k, _) in enumerate(l) if k == "os-version"][0]
            tmp = l[index1]
            l[index1] = l[index2]
            l[index2] = tmp
        headers = dict(l)

        return headers

    def _getHeaders_GET_JSON(self):
        headers = self._getHeaders_POST_JSON()
        headers.pop("Content-Type", None)
        headers.pop("Content-Length", None)
        return headers

    # fake appId to pass ios_device_token check
    def _get_appId(phoneNumber: str):
        #return "825DDA558L.com.cardify.tinder"
        return "825DDA558L.com.cardify.tinder" + phoneNumber

    def _request(self, method: str, url: str, headers: dict, data: bytes = None, http_version=None, retry=0) -> bytes:
        try:
            response = http_async_sesion.request(
                method=method,
                url=url,
                headers=headers,
                data=data,
                proxy=self.httpProxy,
                http_version=http_version,
                timeout=60*5 # 300 seconds (better for photo upload)
            )

            self.last_status_code = response.status_code
            print("CALL_STATUS: " + str(response.status_code))

            return response.content
        except Exception as e:
            print(e)
            #logger.error(json.dumps(error, indent=2))
            if retry < 1:
                retry = retry + 1

                print(">> New proxy")
                self.httpProxy = TinderClient.loadProxy()
                print(self.checkIp())
                return self._request(method, url, headers, data, http_version, retry)
            else:
                return None

    ### Init
    def sendBuckets(self):
        url = "https://api.gotinder.com/v2/buckets"
        bodyBytes = b'{"experiments":[], "device_id":' + json.dumps(self.installId).encode() + b'}'
        
        headers = self._getHeaders_POST_JSON()
        headers.pop('X-Auth-Token', None)
        headers.pop('app-session-id', None)
        headers.pop('app-session-time-elapsed', None)
        headers.pop('user-session-id', None)
        headers.pop('user-session-time-elapsed', None)

        response = self._request("POST", url, headers, bodyBytes)

        return json.loads(response)

    def healthCheckAuth(self) -> dict:
        url = "https://api.gotinder.com/healthcheck/auth"
        headers = {
            "x-supported-image-formats": "webp, jpeg",
            "Accept": "application/json", # ios only
            "x-hubble-entity-id": str(uuid.uuid4()), # ios only
            "tinder-version": self.tinderVersion,
            "app-version": str(self.appVersion),
            "persistent-device-id": self.persistentDeviceId,
            "Accept-Language": self.language,
            "platform": self.platform,
            "Accept-Encoding": "gzip, deflate, br",
            "app-session-time-elapsed": f"{self.getAppSessionTimeElapsed()}",
            "User-Agent": self.userAgent,
            "app-session-id": self.appSessionId,
            "os-version": str(self.osVersion),
            #"platform-variant": self.platformVariant, # android only
            #"store-variant": self.storeVariant, # android only
            #"x-device-ram": self.x_device_ram, # android only
            ### ios not include (its move to _call)
            # "install-id": self.installId,
            # "encoded-device-model": self.encodedDeviceModel,
            # "encoded-device-carrier": self.encodedDeviceCarrier,
            # "mobile-country-code": str(self.mobileCountryCode),
            # "mobile-network-code": str(self.mobileNetworkCode),
        }

        response = self._request("GET", url, headers)

        return json.loads(response)
    
    def checkIp(self):
        response = http_async_sesion.request(
            method="GET",
            url="https://api64.ipify.org?format=text",
            proxy=self.httpProxy
        )
        
        r = response.text
        return r

    def getLocation(self, ip: str= None):
        if ip is None:
            ip = self.checkIp()
        
        bodyBytes = b'{"search":"' + ip.encode() + b'"}'
        response = http_async_sesion.request(
            method="POST",
            url="https://geo.ipify.org/api/web",
            proxy=self.httpProxy,
            data=bodyBytes
        )
        
        r = response.json()
        lat = r['location']['lat']
        lng = r['location']['lng']

        return lat, lng

    ### PROTO: TODO: blackboxprotobuf => protoc
    def authLogin(self, phoneNumber: str):
        appId = TinderClient._get_appId(phoneNumber)
        self.app_id = appId

        bodyBytes = blackboxprotobuf.encode_message({
            "phone": {
                "phone": phoneNumber,
                # "ios_device_token": {
                #     "value": generateDeviceToken(appId) # StringValue
                # }
            }
        }, message_type="AuthGatewayRequest", config=config)
        print('AuthGatewayRequest (authLogin)')

        headers = self._getHeaders_POST_Protobuf()
        response = self._request("POST", "https://api.gotinder.com/v3/auth/login", headers, bodyBytes)

        decoded = blackboxprotobuf.decode_message(response, message_type="AuthGatewayResponse", config=config)[0]
        return decoded

    def verifyOtp(self, phoneNumber: str, otp: str):
        bodyBytes = blackboxprotobuf.encode_message({
            "phone_otp": { # phoneOtp => phone_otp
                "phone": {
                    "value": phoneNumber
                }, # StringValue
                "otp": otp
            }
        }, message_type="AuthGatewayRequest", config=config)
        print('AuthGatewayRequest (verifyOtp): ' + bodyBytes.hex())

        headers = self._getHeaders_POST_Protobuf()
        response = self._request("POST", "https://api.gotinder.com/v3/auth/login", headers, bodyBytes)

        decoded =  blackboxprotobuf.decode_message(response, message_type="AuthGatewayResponse", config=config)[0]
        self.assignDecodedValues(decoded)
        return decoded
    
    # login only
    def verifyEmail(self, otp: str):
        bodyBytes = blackboxprotobuf.encode_message({
            "email_otp": { # emailOtp => email_otp
                "refresh_token": { # refreshToken => refresh_token
                    "value": self.refreshToken,
                },
                "otp": otp
            }
        }, message_type="AuthGatewayRequest", config=config)
        print('AuthGatewayRequest (verifyEmail): ' + bodyBytes.hex())

        headers = self._getHeaders_POST_Protobuf()
        response = self._request("POST", "https://api.gotinder.com/v3/auth/login", headers, bodyBytes)

        decoded =  blackboxprotobuf.decode_message(response, message_type="AuthGatewayResponse", config=config)[0]
        self.assignDecodedValues(decoded)
        return decoded
    # register only
    def useEmail(self, email: str):
        bodyBytes = blackboxprotobuf.encode_message({
            "email": {
                "email": email,
                "refresh_token": { # refreshToken => refresh_token
                    "value": self.refreshToken,
                }
            }
        }, message_type="AuthGatewayRequest", config=config)
        print('AuthGatewayRequest (useEmail): ' + bodyBytes.hex())

        headers = self._getHeaders_POST_Protobuf()
        response = self._request("POST", "https://api.gotinder.com/v3/auth/login", headers, bodyBytes)

        decoded =  blackboxprotobuf.decode_message(response, message_type="AuthGatewayResponse", config=config)[0]
        self.assignDecodedValues(decoded)
        return decoded
    
    def dismissSocialConnectionList(self):
        bodyBytes = blackboxprotobuf.encode_message({
            "dismiss_social_connection_list": {
                "refresh_token": self.refreshToken # refreshToken => refresh_token
            }
        }, message_type="AuthGatewayRequest", config=config)
        print('AuthGatewayRequest (dismiss_social_connection_list): ' + bodyBytes.hex())

        headers = self._getHeaders_POST_Protobuf()
        response = self._request("POST", "https://api.gotinder.com/v3/auth/login", headers, bodyBytes)

        decoded =  blackboxprotobuf.decode_message(response, message_type="AuthGatewayResponse", config=config)[0]
        self.assignDecodedValues(decoded)
        return decoded

    def getAuthToken(self):
        ### with STANDARD
        # obj, tdf = blackboxprotobuf.decode_message(base64.decodebytes(b'UlIKUGV5SmhiR2NpT2lKSVV6STFOaUo5Lk1UTXdNekkxTnpZNE16ay42RmNiRFpENWJmQjJOOTctamNYVnRLVVZUcUpBWTRxUi1kMEFRYkJnUkdJugEKCghTVEFOREFSRA=='), message_type="AuthGatewayRequest", config=config)
        # obj['refresh_auth']['refresh_token'] = self.refreshToken
        # bodyBytes = blackboxprotobuf.encode_message(obj, tdf)

        bodyBytes = blackboxprotobuf.encode_message({
            "refresh_auth": { # refreshAuth => refresh_auth
                "refresh_token": self.refreshToken # refreshToken => refresh_token
            }
        }, message_type="AuthGatewayRequest", config=config)
        print('AuthGatewayRequest (getAuthToken): ' + bodyBytes.hex())

        headers = self._getHeaders_POST_Protobuf()
        response = self._request("POST", "https://api.gotinder.com/v3/auth/login", headers, bodyBytes)

        decoded =  blackboxprotobuf.decode_message(response, message_type="AuthGatewayResponse", config=config)[0]
        self.assignDecodedValues(decoded)
        return decoded
    
    def _merge_onboardingPayload(self, field: dict):
        for i, old in enumerate(self.onboardingPayload):
            if old['name'] == field['name']:
                self.onboardingPayload[i] = field
                return
        self.onboardingPayload.append(field)

    ### JSON flows: onboarding
    def _onboarding_set(self, bodyBytes):
        if bodyBytes:
            # merge with previous
            obj = json.loads(bodyBytes)
            fields: list[dict]= obj['fields']
            if len(self.onboardingPayload) == 0:
                self.onboardingPayload = fields
            else:
                for field in fields:
                    self._merge_onboardingPayload(field)
                obj['fields'] = self.onboardingPayload
                bodyBytes = json.dumps(obj).encode()
        else:
            bodyBytes = json.dumps({
                "fields": self.onboardingPayload
            }).encode()

        headers = self._getHeaders_POST_JSON()
        headers.update({
            "token": self.onboardingToken,
            "funnel-session-id": self.funnelSessionId,
            #'appsflyer-id': None # remove it
        })
        response = self._request("POST", self.URL_ONBOARDING, headers, bodyBytes)
        
        print(json.dumps(json.loads(response)['meta']))

        return response

    def endOnboarding(self):
        bodyBytes = b'{"fields":[]}'

        headers = self._getHeaders_POST_JSON()
        headers.update({
            "token": self.onboardingToken,
            'x-refresh-token': self.refreshToken,
            "funnel-session-id": self.funnelSessionId,
            'appsflyer-id': self.appsFlyerId,
        })
        response = self._request("POST", self.URL_ONBOARDING_COMPLETE, headers, bodyBytes)
        
        print(json.dumps(json.loads(response)['meta']))

        return response

    def startOnboarding(self):
        headers = self._getHeaders_GET_JSON()
        headers.update({
            "token": self.onboardingToken,
            "funnel-session-id": self.funnelSessionId
            #'appsflyer-id': None # remove it
        })
        response = self._request("GET", self.URL_ONBOARDING, headers)

        print(json.dumps(json.loads(response)['meta']))
        
        return response

    ### Skip (send previous payload)
    def onboardingSkip(self):
        return self._onboarding_set(None)

    ### One payload fill all
    def onboardingSuper(self, name: str, dob: str, gender: int, interested_in_gender: list[int]):        
        bodyStr = b'{"fields":[{"name":"name","data":' + json.dumps(name).encode() + b'},{"data":"' + dob.encode() + b'","name":"birth_date"},{"data":' + str(gender).encode() + b',"name":"gender"},{"name":"show_orientation_on_profile","data":true},{"name":"tinder_rules","data":{"checked":true}},{"name":"sexual_orientations","data":[{"checked":true,"description":"A person who is exclusively attracted to members of the opposite gender","name":"Straight","id":"str"},{"name":"Gay","checked":false,"id":"gay","description":"An umbrella term used to describe someone who is attracted to members of their gender"},{"id":"les","description":"A woman who is emotionally, romantically, or sexually attracted to other women","name":"Lesbian","checked":true},{"description":"A person who has potential for emotional, romantic, or sexual attraction to people of more than one gender","name":"Bisexual","id":"bi","checked":true},{"name":"Asexual","id":"asex","checked":false,"description":"A person who does not experience sexual attraction"},{"id":"demi","description":"A person who does not experience sexual attraction unless they form a strong emotional connection","checked":false,"name":"Demisexual"},{"name":"Pansexual","id":"pan","description":"A person who has potential for emotional, romantic, or sexual attraction to people regardless of gender","checked":false},{"id":"qur","name":"Queer","description":"An umbrella term used to express a spectrum of sexual orientations and genders often used to include those who do not identify as exclusively heterosexual","checked":false},{"id":"ques","checked":false,"name":"Questioning","description":"A person in the process of exploring their sexual ZZZZZ"}]},{"data":' + json.dumps(interested_in_gender).encode() + b',"name":"interested_in_gender"}]}'
        bodyStr = bodyStr.replace(b'ZZZZZ', base64.b64decode('b3JpZW50YXRpb24gYW5kXC9vciBnZW5kZXI=')) # orientation and\/or gender

        return self._onboarding_set(bodyStr)

    ### Step by step
    def setTinderRules(self):
        # TODO: GET URL_ONBOARDING => parse tinder_rules (value: body, title)
        #bodyBytes = b'{"fields":[{"data":{"body":"Please follow these House Rules.","checked":true,"title":"Welcome to Tinder."},"name":"tinder_rules"}]}'
        bodyBytes = b'{"fields":[{"name":"tinder_rules","data":{"checked":true}}]}' # ios style
        return self._onboarding_set(bodyBytes)

    def setName(self, value: str):
        #bodyBytes = b'{"fields":[{"data":"Chris","name":"name"}]}'
        bodyBytes = b'{"fields":[{"data":' + json.dumps(value).encode() + b',"name":"name"}]}'

        return self._onboarding_set(bodyBytes)

    def setBirthDate(self, value: str):
        #bodyBytes = b'{"fields":[{"data":"1999-12-27","name":"birth_date"}]}'
        bodyBytes = b'{"fields":[{"data":' + json.dumps(value).encode() + b',"name":"birth_date"}]}'

        return self._onboarding_set(bodyBytes)

    def setGender(self, value: int):
        #bodyBytes = b'{"fields":[{"data":1,"name":"gender"},{"name":"custom_gender"},{"data":true,"name":"show_gender_on_profile"}]}'
        bodyBytes = b'{"fields":[{"data":' + json.dumps(value).encode() + b',"name":"gender"},{"name":"custom_gender"},{"data":true,"name":"show_gender_on_profile"}]}'

        return self._onboarding_set(bodyBytes)

    # required=False
    def setInterestedInGender(self, value: list[int]):
        #bodyBytes = b'{"fields":[{"data":[0],"name":"interested_in_gender"},{"data":{"checked":false,"should_show_option":false},"name":"show_same_orientation_first"}]}'
        bodyBytes = b'{"fields":[{"data":' + json.dumps(value).encode() + b',"name":"interested_in_gender"},{"data":{"checked":false,"should_show_option":false},"name":"show_same_orientation_first"}]}'

        return self._onboarding_set(bodyBytes)

    # required=False
    def setInterestedInGenders(self, value):
        pass

    # required=False
    def setRelationshipIntent(self):
        bodyBytes = b'{"fields":[{"data":{"selected_descriptors":[{"choice_selections":[{"id":"1"}],"id":"de_29"}]},"name":"relationship_intent"}]}'
        #bodyBytes = b'{"fields":[{"data":' + json.dumps(value).encode() + b',"name":"interested_in_gender"},{"data":{"checked":false,"should_show_option":false},"name":"show_same_orientation_first"}]}'

        return self._onboarding_set(bodyBytes)

    def setDistanceFilter(self):
        bodyBytes = b'{"fields":[{"data":50,"name":"distance_filter"}]}'

        return self._onboarding_set(bodyBytes)

    ### Upload
    def onboardingPhoto(self, data: bytes, total_image):
        url = self.URL_ONBOARDING_PHOTO
        filename = str(uuid.uuid4()).upper() + ".jpg"
        boundary = "Boundary-" + str(uuid.uuid4()).upper()

        total_image = total_image - 1 # 2nd image => num_pending_media => uploadPhoto
        contentType = "multipart/form-data; boundary=" + boundary
        bodyBytes = b'--' + boundary.encode() + b'\r\nContent-Disposition: form-data; name="photo"; filename="' + filename.encode() + b'"\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data + b'\r\n--' + boundary.encode() + b'\r\nContent-Disposition: form-data; name="num_pending_media"\r\nContent-Transfer-Encoding: binary\r\nContent-Type: application/json; charset=UTF-8\r\nContent-Length: 1\r\n\r\n' + str(total_image).encode() + b'\r\n--' + boundary.encode() + b'--'
        bodyBytes = b'--' + boundary.encode() + b'\r\nContent-Disposition: form-data; name="type"\r\n\r\nphoto\r\n' + bodyBytes

        #self.httpProxy = "http://127.0.0.1:8888" # debug

        http_version=2 # HTTP 1.1 (prevent HTTP2 framing layer error)
        headers = self._getHeaders_POST_JSON()
        headers.update({
            "Content-Type": contentType,
            "token": self.onboardingToken,
            "funnel-session-id": self.funnelSessionId
            #'appsflyer-id': None # remove it
        })
        response = self._request("POST", url, headers, bodyBytes, http_version)
        
        try:
            print(json.dumps(json.loads(response)['meta']))
        except:
            response = self.onboardingPhoto(data, total_image + 1)
        
        return response

    def uploadPhoto(self, data: bytes, media_id: str):
        url = "https://api.gotinder.com/mediaservice/photo"
        filename = str(uuid.uuid4()).upper()
        boundary = str(uuid.uuid4()).upper()

        contentType = "multipart/form-data; boundary=" + boundary
        bodyBytes = b'--' + boundary.encode() + b'\r\nContent-Disposition: form-data; name="image"; filename="' + filename.encode() + b'"\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data + b'\r\n--' + boundary.encode() + b'--'
        
        #self.httpProxy = "http://127.0.0.1:8888" # debug

        http_version=2 # HTTP 1.1 (prevent HTTP2 framing layer error)
        headers = self._getHeaders_POST_JSON()
        headers.update({
            "Content-Type": contentType,
            "x-media-id": media_id,
            #'appsflyer-id': None # remove it
        })
        response = self._request("POST", url, headers, bodyBytes, http_version)
        
        return response
    
    #### JSON
    def updateLocation(self, lat: float, lon: float):
        url = "https://api.gotinder.com/v2/meta"
        bodyBytes = b'{"lat":' + json.dumps(lat).encode() + b',"lon":' + json.dumps(lon).encode() + b',"background":false,"force_fetch_resources":true}'
        print('updateLocation: ' + bodyBytes.decode())

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        print(json.dumps(json.loads(response)['meta']))
        return response
    
    def updateLocalization(self, lat: float, lon: float):
        url = "https://api.gotinder.com/v2/rosetta/localization"
        bodyBytes = b'{"lat":' + json.dumps(lat).encode() + b',"lon":' + json.dumps(lon).encode() + b',"locale":"en","keys":["rosetta_test_string","coins_2_0_intro_modal_title","coins_2_0_intro_modal_get_coins_cta","coins_2_0_intro_modal_earn","coins_2_0_intro_modal_use","coins_2_0_intro_modal_stock_up","permissions.push_soft_prompt_main_text","permissions.push_soft_prompt_detail_text","permissions.push_soft_prompt_primary_button_title","permissions.push_soft_prompt_secondary_button_title","selfie_v2_biometric_consent_description_one","selfie_v2_biometric_consent_description_two","selfie_v2_modal_unverify_description"]}'
        print('updateLocalization: ' + bodyBytes.decode())

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        print(json.dumps(json.loads(response)['meta']))
        return response

    def locInit(self):
        url = "https://api.gotinder.com/v1/loc/init"
        bodyBytes = b'{"deviceTime":' + str(int(time.time() * 1000)).encode() + b',"eventId":"' + str(uuid.uuid4()).upper().encode() + b'"}'

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        return response

    def updateActivityDate(self, sendTime = False):
        url = 'https://api.gotinder.com/updates?is_boosting=false'
        if sendTime:
            #s = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z' # deprecated
            #s = datetime.now(timezone.utc).isoformat(timespec='milliseconds') + 'Z' # +00:00
            s = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            bodyBytes = b'{"nudge":"true","last_activity_date":"' + s.encode() + b'"}'
        else:
            bodyBytes = b'{}' # first time it submit empty

        headers = self._getHeaders_POST_JSON()
        headers.update({
            'support-short-video': '1'
        })
        response = self._request("POST", url, headers, bodyBytes)
        
        return response
    
    def updateProfileLanguagePreferences(self):
        url = 'https://api.gotinder.com/v2/profile/user'
        bodyBytes = b'{"global_mode":{"display_language":"en","language_preferences":[{"language":"en","is_selected":true}]}}'

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)
        
        return response
    
    def updateProfileBio(self, bio: str):
        url = 'https://api.gotinder.com/v2/profile/user'
        bodyBytes = b'{"bio":' + json.dumps(bio).encode() + b'}'

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        print(json.dumps(json.loads(response)['meta']))
        
        return response

    def updateProfileJobTitle(self, jobTitle: str, jobCompany: str = None):
        url = 'https://api.gotinder.com/v2/profile/job'
        if jobCompany is str:
            bodyBytes = b'{"jobs":[{"company":{"name":' + json.dumps(jobCompany) + b',"displayed":true},"title":{"name":' + json.dumps(jobTitle).encode() + b',"displayed":true}}]}'
        else:
            bodyBytes = b'{"jobs":[{"company":{"displayed":false},"title":{"name":' + json.dumps(jobTitle).encode() + b',"displayed":true}}]}'
        # ^-- this include previous job company (if set first)

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)
        # {"jobs":[{"company":{"displayed":false},"title":{"name":"freelancer_test123","displayed":true}}]}

        print(json.dumps(json.loads(response)['meta']))
        
        return response
    
    def updateProfileJobCompany(self, jobCompany: str, jobTitle: str = None):
        url = 'https://api.gotinder.com/v2/profile/job'
        if jobTitle is str:
            bodyBytes = b'{"jobs":[{"company":{"name":' + json.dumps(jobCompany).encode() + b',"displayed":true},"title":{"name":' + json.dumps(jobTitle).encode() + b',"displayed":true}}]}'
        else:
            bodyBytes = b'{"jobs":[{"company":{"name":' + json.dumps(jobCompany).encode() + b',"displayed":true},"title":{"displayed":false}}]}'
        # {"jobs":[{"company":{"name":"company test","displayed":true},"title":{"name":"freelancer_test123","displayed":true}}]}
        # ^-- this include previous job title (if set first)

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        print(json.dumps(json.loads(response)['meta']))
        
        return response
    
    def autocompleteProfileSchool(self, value: str):
        q_value = urllib.parse.quote(value)
        url = 'https://api.gotinder.com/v2/profile/autocomplete?type=school&q=' + q_value
        headers = self._getHeaders_GET_JSON()
        response = self._request("GET", url, headers)
        # results = json.loads(response)["data"]["results"]
        # name = results[0]["name"]
        # id = results[0]["id"]
        # ^-- use this to get school name+id

        return response

    def updateProfileSchool(self, name: str, id: str = None):
        url = 'https://api.gotinder.com/v2/profile/school'
        if id is str:
            bodyBytes = b'{"schools":[{"name":' + json.dumps(name).encode() + b',"school_id":' + json.dumps(id).encode() + b',"displayed":true}]}'
        else:
            bodyBytes = b'{"schools":[{"name":' + json.dumps(name).encode() + b',"displayed":true}]}'
        ### name+id (dropdown, autocomplete) OR name (only)
        # {"schools":[{"name":"Mitchell College","school_id":"ope_139300","displayed":true}]}
        # {"schools":[{"name":"Mitchell","displayed":true}]}
        # ^--- we can set any school without id (TODO: school list)

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        print(json.dumps(json.loads(response)['meta']))
        
        return response

    def getProfileLiftStyleFields(self):
        url = 'https://api.gotinder.com/dynamicui/configuration/content?component_id=sec_1_bottom_sheet'
        headers = self._getHeaders_GET_JSON()
        headers["Accept"] = "application/x-protobuf"
        response = self._request("GET", url, headers)

        decoded = blackboxprotobuf.decode_message(response)[0]
        # fields = decoded["1"]["4"]["3"] # [de_3: Pets, de_22: Drinking, ...]
        # field0_id = fields[0]["1"] # id: de_3
        # field0_values = fields[0]["7"] # value: []
        # field0_value0_id = fields[0]["7"][0]['1'] # id: 1
        # field0_value0_value = fields[0]["7"][0]['2'] # value: Dog

        return decoded

    def updateProfileLiftStyle(self, bodyBytes: bytes = None):
        url = 'https://api.gotinder.com/v2/profile/user'
        if bodyBytes is None:
            bodyBytes = b'{"selected_descriptors_append":[{"choice_selections":[{"id":"1"}],"id":"de_3"},{"id":"de_22","choice_selections":[{"id":"8"}]},{"id":"de_11","choice_selections":[{"id":"1"}]},{"id":"de_10","choice_selections":[{"id":"4"}]},{"choice_selections":[{"id":"1"}],"id":"de_7"},{"choice_selections":[{"id":"1"}],"id":"de_4"},{"id":"de_17","choice_selections":[{"id":"1"}]}]}'
        # ^-- {"selected_descriptors_append":[{"choice_selections:[id:"1"], id:"de_3"}, ...}
        # descriptors_sec_1
        # de_3: Pets
        # [("1", "Dog"), ("2", "Cat"), ("3", "Reptile"), ("4", "Amphibian"), ...]
        # ^--- use getProfileLiftStyleFields to grab a list then build bodyBytes

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        print(json.dumps(json.loads(response)['meta']))
        
        return response

    def addNewProfilePhoto(self, data: bytes):
        # requestPhotoXMediaId
        url = 'https://api.gotinder.com/mediaservice/placeholders'
        bodyBytes = b'\x08\x01'
        headers = self._getHeaders_POST_Protobuf()
        response = self._request("POST", url, headers, bodyBytes)
        decoded = blackboxprotobuf.decode_message(response)[0]
        # ex response: blackboxprotobuf.decode_message(bytes.fromhex('0a1c0a0c08dd9299b80610fc97e6c701120c08dd9299b80610abc285c2018201260a2435636265373237642d383966362d343035622d613138372d316364636332656232623064'))
        media_id: str = decoded['16']['1']

        url = 'https://api.gotinder.com/mediaservice/details'
        # ex bodyBytes: blackboxprotobuf.decode_message(bytes.fromhex('0a2435636265373237642d383966362d343035622d613138372d316364636332656232623064120e1a080a0012001a00220022020801')
        bodyBytes = b'\x0a\x24' + media_id.encode() + b'\x12\x0e\x1a\x08\x0a\x00\x12\x00\x1a\x00\x22\x00\x22\x02\x08\x01'
        response = self._request("PUT", url, headers, bodyBytes)
        #decoded = blackboxprotobuf.decode_message(response)[0] # no need

    def deviceCheck(self):
        headers = self._getHeaders_GET_JSON()
        response = self._request("GET", self.URL_DEVICE_CHECK, headers)

        obj = json.loads(response)
        print(response)

        if 'data' in obj:
            # obj = {
            #     "data": {
            #         "ios_device_token": generateDeviceToken(self.app_id),
            #         "version": 1
            #     }
            # } # old style
            obj = {
                "version": 1,
                "ios_device_token": generateDeviceToken(self.app_id)
            }
            bodyBytes = json.dumps(obj).encode()

            headers = self._getHeaders_POST_JSON()
            response = self._request("POST", self.URL_DEVICE_CHECK, headers, bodyBytes)
            
            print(response)
        else:
            print("deviceCheck SKIPPED")

    def exlist(self):
        url = 'https://api.gotinder.com/v2/profile/exlist'
        bodyBytes = b''
        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)

        return response

    # Mozilla/5.0 (iPhone; CPU iPhone OS 14_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148
    def challengeVerifyArkose(self, token: str, answer: str):
        url = 'https://api.gotinder.com/challenge/verify'
        bodyBytes = b'{"challenge_type":"arkose","challenge_token":"' + token.encode() + b'","challenge_answer":' + json.dumps(answer).encode() + b'}'

        headers = self._getHeaders_POST_JSON()
        response = self._request("POST", url, headers, bodyBytes)
        
        return response

    def getProfileInfo(self):
        url = 'https://api.gotinder.com/v2/profile?include=experiences,account,onboarding,campaigns,spotify,tappy_content,instagram,travel,paywalls,tutorials,notifications,available_descriptors,misc_merchandising,purchase,likes,plus_control,offerings,feature_access,super_likes,tinder_u,user,boost,contact_cards,email_settings,readreceipts'
        
        headers = self._getHeaders_GET_JSON()
        response = self._request("GET", url, headers)
        
        return response
    
    def getProfileMeter(self):
        url = 'https://api.gotinder.com/v2/profile?include=profile_meter'
        
        headers = self._getHeaders_GET_JSON()
        response = self._request("GET", url, headers)
        
        return response
    
    def getFastMatch(self):
        url = 'https://api.gotinder.com/v2/fast-match/count'
        
        headers = self._getHeaders_GET_JSON()
        response = self._request("GET", url, headers)

        return response
    
    ### BOT ENGINE
    def processCaptcha(self):
        tinder = self
        if tinder.last_status_code != 200:
            r = tinder.getAuthToken()
            pretty_json = json.dumps(r, indent=4)
            print('AuthToken:\r\n' + pretty_json)
            token: str = r['error']['ban_reason']['ban_appeal']['challenge_token']
            tokenUP = token.upper()

            # https://demo.arkoselabs.com/?key=DF9C4D87-CB7B-4062-9FEB-BADB6ADA61E6
            # https://tinder-api.arkoselabs.com/v2/EBC0462E-1FD4-25CD-A21E-A68A0E5DDB23/api.js
            print('Token:\r\n' + tokenUP)
            #print('file:///R:/zcaptcha.html?key=' + tokenUP)
            print('https://192.168.1.188/zcaptcha.html?key=' + tokenUP)
            answer = input("anwser: ")
            r = tinder.challengeVerifyArkose(token, answer)
            print(r)

            r = tinder.getAuthToken() # only if onboarding or banned=>after captcha
            print(r)
            return True
        return False

    def _ws_on_message(ws, message):
        print("_ws_on_message")
        print(message) # b'\x0f\xa0'

    def _ws_thread_async(self):
        headers = self._getHeaders_GET_JSON()
        headers["Origin"] = 'https://keepalive.gotinder.com'
        headers["Authorization"] = f'Token token="{self.xAuthToken}"'
        headers["Sec-WebSocket-Version"] = "13"
        headers["Sec-WebSocket-Key"] = base64.b64encode(os.urandom(16)).decode()
        

        http_async_sesion = Session(
            verify=False,
            default_headers=False,
            impersonate="safari17_2_ios",
            #http_version=2 # HTTP 1.1 (prevent HTTP2 framing layer error)
        )
        ws = http_async_sesion.ws_connect(
            url="wss://keepalive.gotinder.com/ws",
            headers=headers,
            on_message=TinderClient._ws_on_message
            #proxy=self.httpProxy
        )
        ws.run_forever()

    def _ws_thread(self):
        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        # loop.run_until_complete(TinderClient._ws_thread_async(self))
        # loop.close()

        headers = self._getHeaders_GET_JSON()
        headers["Origin"] = 'https://keepalive.gotinder.com'
        headers["Authorization"] = f'Token token="{self.xAuthToken}"'
        headers["Sec-WebSocket-Version"] = "13"
        headers["Sec-WebSocket-Key"] = base64.b64encode(os.urandom(16)).decode()
        with Session(
            verify=False,
            default_headers=False,
            impersonate="safari17_2_ios"
        ) as s:
            ws = s.ws_connect(
                url="wss://keepalive.gotinder.com/ws",
                headers=headers,
                on_message=TinderClient._ws_on_message,
                proxy=self.httpProxy
            )
            print("WS CONNECTED")
            ws.run_forever()

    def ws_connect(self):
        thread = Thread(target=TinderClient._ws_thread, args=[self])
        thread.start()