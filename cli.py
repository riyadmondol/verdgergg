import asyncio
import base64
import json
import random
import re
import sys
import logging
from pathlib import Path

from tinder import TinderClient
from log import mklog

logger = mklog("Tinder", level=logging.DEBUG)
logger.warning("TinderBOT")

def mkdirp(directory: str):
    Path(directory).mkdir(parents=True, exist_ok=True)

def saveSession(tinder: TinderClient, json_format: bool = False, filename: str = 'session.json'):
    home_dir = Path('./')  # Path.home()
    tinder_dir = home_dir / ".tinder"
    mkdirp(tinder_dir)
    
    session_file = tinder_dir / filename
    with open(session_file, 'w') as f:
        f.write(tinder.toJSON())

    if not json_format:
        logger.info(f'saved to ~/{session_file.relative_to(home_dir)}')

def loadSession(filename: str = 'session.json') -> TinderClient:
    home_dir = Path('./') # Path.home()
    session_file = home_dir / filename
    
    with open(session_file, 'r') as f:
        tinder = TinderClient.fromJSON(f.read())

    return tinder

def newSession():
    proxyOptions = TinderClient.loadProxy()
    tinder = TinderClient(proxy=proxyOptions)
    
    logger.debug(tinder.checkIp())
    logger.debug(tinder.checkIp())

    logger.info('device details:')
    logger.info(base64.b64decode(tinder.encodedDeviceModel).decode('utf-8'))
    
    logger.info('getting session - first boot')
    r = tinder.healthCheckAuth()
    logger.debug(r)
    
    logger.info('init buckets')
    r = tinder.sendBuckets()

    logger.info('Persistent-Device-Id: ' + tinder.persistentDeviceId)
    return tinder

def ainput(string: str) -> str:
    asyncio.to_thread(sys.stdout.write, f'{string} ')
    return (asyncio.to_thread(sys.stdin.readline)).rstrip('\n')

phoneNumber = "14798582613"
pathFirstImage = "./IMG_1.jpg"
pathSecondmage = "./IMG_2.jpg"
def signup():
    gender = 1 # men=0, women=1
    interested_in_gender = [0] # men=0, women=1
    
    #gender = 0
    #interested_in_gender = [1]

    # random data
    dob_year = str(random.randint(1990, 2005))
    dob_month = str(random.randint(1, 12)).zfill(2)
    dob_day = str(random.randint(1, 28)).zfill(2) # not 29->31
    names = [
        'ary Jane', 'Emily', 'Jennifer', 'Jessica', 'Sophia', 'Jodie', 'Rachel', 'Linda', 'Angell', 'Tiffani'
        'Sherry', 'Barbara', 'Lisa', 'Scarlett', 'Elisabeth', 'Emma', 'Lorissa', 'Krista', 'Jacqueline', 'Yvonne'
    ]
    rand_name = names[random.randint(0, len(names) - 1)]
    name = rand_name
    dob = dob_year + '-' + dob_month + '-' + dob_day # '1999-12-31'
    
    # location_lat = 50.170 + random.uniform(1, 15) # canada
    # location_lon = 230.376 + random.uniform(1, 30) # canada

    location_lat = 42.3751 + random.uniform(1, 10) # US
    location_lon = -71.10561 + random.uniform(1, 10) # US

    profileBio = 'All of my life I was looking for You... ' + str(random.uniform(0, 99))

    tinder = newSession()

    # ip = tinder.checkIp()
    # location_lat, location_lon = tinder.getLocation(ip)
    # location_lat += random.uniform(1, 10)
    # location_lon += random.uniform(1, 10)
    # print("Location: " + str(location_lat) + ', ' + str(location_lon))
    
    # location_lat = float(input("lat"))
    # location_lon = float(input("lon"))
    # location_lat += random.uniform(1, 10)
    # location_lon += random.uniform(1, 10)

    r = tinder.authLogin(phoneNumber)
    logger.debug(r)

    if 'validate_phone_otp_state' in r:
        otp = ainput('opt (1): ') # TODO: use lib
        r = tinder.verifyOtp(phoneNumber, otp) # => get_email_state
        logger.debug(r)
        if 'error' in r: # try again
            otp = ainput('opt (2): ')
            r = tinder.verifyOtp(phoneNumber, otp)
            if 'error' in r:
                return False
        
    if 'get_email_state' in r:
        saveSession(tinder) # after otp
        asyncio.sleep(random.uniform(1, 2))

        email = 'tinder_' + phoneNumber + '@yopmail.com'
        #email = 'tinder_' + phoneNumber + '@maildrop.cc'
        logger.debug('Email: ' + email)
        r = tinder.useEmail(email) # => onboarding_state
    
    if 'social_connection_list' in r:
        saveSession(tinder) # after mail
        asyncio.sleep(random.uniform(1, 2))
        r = tinder.dismissSocialConnectionList()

    if 'onboarding_state' in r:
        saveSession(tinder) # after mail
        asyncio.sleep(random.uniform(1, 3))

        logger.debug('startOnboarding')
        r = tinder.startOnboarding()

        # logger.debug('onboardingSuper') # single payload
        # asyncio.sleep(random.uniform(2, 3))
        # r = tinder.onboardingSuper(name , dob, gender, interested_in_gender)
        # print(r)
        
        logger.debug('Accept tinder_rules')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.setTinderRules()

        logger.debug('First name: ' + name)
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.setName(name)

        logger.debug('Birth date: ' + dob)
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.setBirthDate(dob)

        # gender: women, men, more:... | show?hide
        logger.debug('Gender: ' + json.dumps(gender))
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.setGender(gender)

        logger.debug('interested-in-genders: straight, gay, lesbian, bisexual,...')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.onboardingSkip()
        #r = tinder.setInterestedInGenders(interested_in_genders)

        # show me: women, men, everyone
        logger.debug('interested_in_gender:' + json.dumps(interested_in_gender))
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.setInterestedInGender(interested_in_gender)

        logger.debug('lookling for (UI no skip)')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.setRelationshipIntent()

        # 50Mi (default; skipable)
        logger.debug('distance_filter setDistanceFilter: 50')
        r = tinder.setDistanceFilter()

        logger.debug('schools')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.onboardingSkip()

        logger.debug('consents')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.onboardingSkip()

        logger.debug('user_interests')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.onboardingSkip()

        logger.debug('basics')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.onboardingSkip()

        logger.debug('lifestyle')
        asyncio.sleep(random.uniform(1, 3))
        r = tinder.onboardingSkip()

        # photo (required; 2 images but upload 1)
        logger.debug('Photo: ' + pathFirstImage)
        hfile = open(pathFirstImage, "rb")
        data = hfile.read()
        hfile.close()
        r = tinder.onboardingPhoto(data, 2)
        media_id =  re.search(r'"client_media_id":"(.*?)"', r.decode()).group(1)
        print('x-media-id: ' + media_id)

        # complete
        logger.debug('Complete!')
        r = tinder.endOnboarding()

        logger.debug('getAuthToken - auth/login')
        r = tinder.getAuthToken() # => onboarding_state | login_result
        logger.info(r)
        saveSession(tinder)
        saveSession(tinder, filename="session_" + phoneNumber + ".json") # backup

        tinder.deviceCheck() # IOS FAKE

        # photo (required; 2 images => continue upload)
        logger.debug('Photo: ' + pathSecondmage)
        hfile = open(pathSecondmage, "rb")
        data = hfile.read()
        hfile.close()
        r = tinder.uploadPhoto(data, media_id)
        print(r)

        logger.debug('Location Init')
        r = tinder.locInit()
        print(r)

        logger.debug('updateActivityDate')
        r = tinder.updateActivityDate(True)
        
        logger.debug('Location meta: lat+lon')
        r = tinder.updateLocation(location_lat, location_lon)

        logger.debug('web socket')
        tinder.ws_connect()

        # logger.debug('language_preferences: en')
        # r = tinder.updateLanguagePreferences()

        logger.debug('set bio')
        r = tinder.updateProfileBio(profileBio)

        logger.debug('updateLocalization')
        r = tinder.updateLocalization(location_lat, location_lon)

        logger.debug('exlist')
        r = tinder.exlist()
        print(r)

        logger.debug('getFastMatch')
        r = tinder.getFastMatch()
        print(r)

        logger.debug('getProfileMeter')
        r = tinder.getProfileMeter()
        print(r)

        tinder.startSwipe(logger)

        logger.debug('DONE')
        return True
    
    logger.warning(r)
    return False

def continue_state(tinder: TinderClient, config: dict):
    #tinder.httpProxy = "http://127.0.0.1:8888"
    tinder.httpProxy = TinderClient.loadProxy()
    
    logger.debug(tinder.checkIp())
    logger.debug(tinder.checkIp())

    logger.info('init buckets')
    buckets = tinder.sendBuckets()

    logger.debug('Location Init')
    r = tinder.locInit()
    print(r)

    if tinder.last_status_code != 200:
        tinder.processCaptcha()

    tinder.ws_connect()

    logger.info('get user info')
    r = tinder.getProfileInfo()
    print(r)

    logger.info('update activity')
    r = tinder.updateActivityDate(True)

    # TODO: put location from IP before swipe

    #tinder.startSwipe(logger, config)

    return True

def main():
    #tinder = loadSession("session.json")
    #continue_state(tinder) # we can use sesstion to continue signup
    
    signup()
    pass

if __name__ == "__main__":
    main()