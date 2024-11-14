# device_profiles.py
from dataclasses import dataclass
import random
import base64
import uuid
from typing import Optional, Tuple, Dict, List

@dataclass
class DeviceProfile:
    device_model: str
    os_version: str
    build_id: str
    carrier: Optional[str] = None
    
    def encode(self) -> str:
        return base64.b64encode(self.device_model.encode()).decode()

class DeviceProfileManager:
    # Common iOS devices that support Tinder
    IOS_DEVICES: List[DeviceProfile] = [
        DeviceProfile("iPhone8,1", "14.2", "18B92", "AT&T"),  # iPhone 6s
        DeviceProfile("iPhone8,2", "14.2", "18B92", "T-Mobile"),  # iPhone 6s Plus
        DeviceProfile("iPhone9,1", "14.2", "18B92", "Verizon"),  # iPhone 7
        DeviceProfile("iPhone9,3", "14.2", "18B92", "Sprint"),  # iPhone 7
        DeviceProfile("iPhone9,2", "14.2", "18B92", "AT&T"),  # iPhone 7 Plus
        DeviceProfile("iPhone9,4", "14.2", "18B92", "T-Mobile"),  # iPhone 7 Plus
        DeviceProfile("iPhone10,1", "14.2", "18B92", "Verizon"),  # iPhone 8
        DeviceProfile("iPhone10,4", "14.2", "18B92", "Sprint"),  # iPhone 8
        DeviceProfile("iPhone10,2", "14.2", "18B92", "AT&T"),  # iPhone 8 Plus
        DeviceProfile("iPhone10,5", "14.2", "18B92", "T-Mobile"),  # iPhone 8 Plus
    ]

    # Common carriers and their codes
    CARRIERS: Dict[str, Tuple[int, int]] = {
        "AT&T": (310, 410),
        "T-Mobile": (310, 260),
        "Verizon": (311, 480),
        "Sprint": (310, 120),
        "": (0, 0)  # No carrier
    }

    @staticmethod
    def generate_device_id() -> str:
        """Generate a realistic iOS device ID."""
        return uuid.uuid4().hex[:16]  # iOS uses 16-byte device IDs

    @staticmethod
    def generate_install_id() -> str:
        """Generate an installation ID in UUID format."""
        return str(uuid.uuid4()).upper()

    @staticmethod
    def parse_ios_version(version_str: str) -> int:
        """Convert iOS version string to numeric format."""
        major, minor, patch = map(int, version_str.split('.'))
        return (major * 10000000000) + (minor * 100000000) + (patch * 1000000)

    @classmethod
    def generate_profile(cls) -> Tuple[Dict[str, any], DeviceProfile]:
        """Generate a complete device profile with consistent information."""
        # Select random device profile
        device_profile = random.choice(cls.IOS_DEVICES)
        
        # Generate consistent IDs
        device_id = cls.generate_device_id()
        install_id = cls.generate_install_id()
        session_id = str(uuid.uuid4()).upper()
        
        # Get carrier codes
        mcc, mnc = cls.CARRIERS.get(device_profile.carrier or "", (0, 0))
        
        # Create user agent
        user_agent = (f"Tinder/14.21.0 ({device_profile.device_model}; "
                     f"iOS {device_profile.os_version}; Scale/2.00)")
        
        # Create complete profile
        profile = {
            "userAgent": user_agent,
            "persistentDeviceId": device_id,
            "installId": install_id,
            "appSessionId": session_id,
            "encodedDeviceModel": device_profile.encode(),
            "encodedDeviceCarrier": (base64.b64encode(device_profile.carrier.encode()).decode() 
                                   if device_profile.carrier else ""),
            "mobileCountryCode": mcc,
            "mobileNetworkCode": mnc,
            "osVersion": cls.parse_ios_version(device_profile.os_version),
            "platform": "ios",
            "language": "en-US",
            "tinderVersion": "14.21.0",
            "appVersion": "5546"
        }
        
        return profile, device_profile

    @staticmethod
    def validate_profile(profile: dict) -> bool:
        """Validate that a device profile has consistent information."""
        try:
            # Check that iOS version in user agent matches osVersion
            ua_parts = profile["userAgent"].split()
            ios_version = ua_parts[2].strip("(;")
            numeric_version = DeviceProfileManager.parse_ios_version(ios_version.replace("iOS ", ""))
            
            if numeric_version != profile["osVersion"]:
                return False
            
            # Check device model encoding
            device_model = ua_parts[1].strip("(")
            if base64.b64encode(device_model.encode()).decode() != profile["encodedDeviceModel"]:
                return False
            
            # Validate carrier codes
            if profile["mobileCountryCode"]:
                carrier_pair = (profile["mobileCountryCode"], profile["mobileNetworkCode"])
                if carrier_pair not in DeviceProfileManager.CARRIERS.values():
                    return False
            
            return True
            
        except (IndexError, KeyError):
            return False

# Update tinder.py - modify TinderClient class

class TinderClient:
    def __init__(
            self,
            userAgent: str = None,
            proxy: str = None,
            persistentDeviceId: str = None,
            appSessionId: str = None,
            installId: str = None,
            encodedDeviceModel: str = None,
            encodedDeviceCarrier: str = 'd2lmaQ',
            mobileCountryCode: int = 310,
            mobileNetworkCode: int = 240,
            tinderVersion: str = "14.21.0",
            appVersion: str = "5546",
            storeVariant: str = None,
            osVersion: int = 140000200000,
            platform: str = "ios",
            platformVariant: str = None,
            language: str = "en-us",
            funnelSessionId: str = None,
            appsFlyerId: str = None,
            advertisingId: str = None,
            refreshToken: str = None,
            userId: str = None,
            onboardingToken: str = None,
            xAuthToken: str = None,
            userSessionId: str = None,
            appId: str = None,
            userSessionStartTime: int = 0
    ):
        # Generate device profile if not provided
        if not userAgent:
            profile, device_profile = DeviceProfileManager.generate_profile()
            userAgent = profile["userAgent"]
            persistentDeviceId = profile["persistentDeviceId"]
            appSessionId = profile["appSessionId"]
            installId = profile["installId"]
            encodedDeviceModel = profile["encodedDeviceModel"]
            encodedDeviceCarrier = profile["encodedDeviceCarrier"]
            mobileCountryCode = profile["mobileCountryCode"]
            mobileNetworkCode = profile["mobileNetworkCode"]
            osVersion = profile["osVersion"]
            platform = profile["platform"]
            language = profile["language"]
            tinderVersion = profile["tinderVersion"]
            appVersion = profile["appVersion"]
            
            # Store device profile for future reference
            self.device_profile = device_profile
        
        app_boot_time = random.uniform(40, 50)
        if installId:
            self.first_boot = False
        else:
            self.first_boot = True
        
        # Initialize all attributes
        self.appSessionId = appSessionId or str(uuid.uuid4()).upper()
        self.appSessionStartTime = time.time() - app_boot_time
        self.persistentDeviceId = persistentDeviceId
        self.installId = installId
        self.encodedDeviceModel = encodedDeviceModel
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
        self.userAgent = userAgent
        self.appsFlyerId = appsFlyerId or generateAppsFlyerId()
        self.advertisingId = advertisingId or str(uuid.uuid4())
        self.funnelSessionId = funnelSessionId or os.urandom(16).hex()
        self.onboardingToken = onboardingToken
        self.userId = userId
        self.refreshToken = refreshToken
        self.xAuthToken = xAuthToken
        self.userSessionId = userSessionId
        self.userSessionStartTime = userSessionStartTime
        self.app_id = appId
        
        self.httpProxy = proxy
        self.app_seconds = 0
        self.user_seconds = 0
        self.last_status_code = 0
        self.onboardingPayload = []
        
        # URLs remain the same...
        self.URL_ONBOARDING = 'https://api.gotinder.com/v2/onboarding/fields?requested=name&requested=birth_date&requested=gender&requested=custom_gender&requested=show_gender_on_profile&requested=photos&requested=schools&requested=consents&requested=videos_processing&requested=sexual_orientations&requested=show_same_orientation_first&requested=show_orientation_on_profile&requested=interested_in_gender&requested=user_interests&requested=distance_filter&requested=tinder_rules&requested=relationship_intent&requested=basics&requested=lifestyle'
        self.URL_ONBOARDING_PHOTO = self.URL_ONBOARDING.replace('/fields?', '/photo?', 1)
        self.URL_ONBOARDING_COMPLETE = self.URL_ONBOARDING.replace('/fields?', '/complete?', 1)
        self.URL_DEVICE_CHECK = 'https://api.gotinder.com/v2/device-check/ios'

    def rotate_device(self):
        """Rotate device profile while maintaining session data."""
        profile, device_profile = DeviceProfileManager.generate_profile()
        
        # Update device-specific attributes
        self.userAgent = profile["userAgent"]
        self.encodedDeviceModel = profile["encodedDeviceModel"]
        self.encodedDeviceCarrier = profile["encodedDeviceCarrier"]
        self.mobileCountryCode = profile["mobileCountryCode"]
        self.mobileNetworkCode = profile["mobileNetworkCode"]
        self.osVersion = profile["osVersion"]
        self.device_profile = device_profile
        
        return self

# Update run.py - modify relevant functions

def setup_tinder_client(proxy=None):
    """Initialize Tinder client with device spoofing."""
    profile, device_profile = DeviceProfileManager.generate_profile()
    
    client = TinderClient(
        proxy=proxy,
        **profile
    )
    
    print("\nDevice Profile Configuration:")
    print(f"Device Model: {device_profile.device_model}")
    print(f"iOS Version: {device_profile.os_version}")
    print(f"Carrier: {device_profile.carrier}")
    print(f"User Agent: {profile['userAgent']}")
    
    return client

def main():
    try:
        print("Welcome to Tinder Registration!")
        print("-" * 50)

        # Get proxy settings first
        proxy = get_proxy_settings()

        # Initialize client with enhanced device spoofing
        client = setup_tinder_client(proxy)
        
        # Rest of the main function remains the same...
        # [Previous main function code continues here]

if __name__ == "__main__":
    main()