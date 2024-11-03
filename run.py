from tinder import TinderClient
import json
import time
import os
from datetime import datetime
import imghdr  # For validating image files

def debug_response(response, status_code):
    print(f"\nStatus Code: {status_code}")
    print("Raw Response:", response)
    try:
        if response:
            return json.loads(response)
        return None
    except json.JSONDecodeError:
        print("Response is not valid JSON")
        return None

def validate_date(date_text):
    try:
        datetime.strptime(date_text, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def check_image_file(file_path):
    """Validate if file is actually an image and get its details"""
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
            image_type = imghdr.what(None, h=data)
            if image_type in ['jpeg', 'jpg', 'png']:
                return True, data, len(data)
    except Exception as e:
        print(f"Error reading image {file_path}: {str(e)}")
    return False, None, 0

def get_photos_from_folder():
    photos_dir = "photos"
    print(f"\nChecking photos directory: {os.path.abspath(photos_dir)}")
    
    if not os.path.exists(photos_dir):
        print(f"Error: {photos_dir} directory not found!")
        return []
    
    valid_extensions = ('.jpg', '.jpeg', '.png')
    photos = []
    
    print("\nScanning for photos:")
    for file in os.listdir(photos_dir):
        file_lower = file.lower()
        if file_lower.endswith(valid_extensions):
            file_path = os.path.join(photos_dir, file)
            print(f"\nChecking file: {file}")
            print(f"Full path: {os.path.abspath(file_path)}")
            
            is_valid, image_data, size = check_image_file(file_path)
            if is_valid and image_data:
                print(f"Valid image found: {file} (Size: {size/1024:.2f}KB)")
                photos.append(image_data)
            else:
                print(f"Invalid or corrupted image: {file}")
    
    print(f"\nTotal valid photos found: {len(photos)}")
    return photos

def handle_auth_process(client, email):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            phone_number = input("\nEnter phone number (with country code, e.g., +1234567890): ").strip()
            if not phone_number.startswith('+'):
                print("Phone number must start with + and country code")
                continue

            print(f"\nAttempting login with {phone_number}...")
            login_response = client.authLogin(phone_number)
            
            if not login_response:
                print("No response from server")
                retry_count += 1
                continue

            if 'error' in login_response:
                print(f"Login error: {login_response['error']}")
                retry_count += 1
                continue

            # Handle OTP verification
            while True:
                otp = input("\nEnter the OTP received on your phone: ").strip()
                if not otp.isdigit():
                    print("OTP should contain only numbers")
                    continue

                print(f"Verifying OTP: {otp}")
                otp_response = client.verifyOtp(phone_number, otp)
                
                if 'error' not in otp_response:
                    print("Phone verification successful!")
                    
                    # Register email
                    print("\nRegistering email...")
                    email_response = client.useEmail(email)
                    print("Email registration response:", json.dumps(email_response, indent=2))
                    
                    if 'error' not in email_response:
                        print("Email registration successful!")
                        
                        # Dismiss social connection list
                        print("\nDismissing social connections...")
                        dismiss_response = client.dismissSocialConnectionList()
                        print("Dismiss response:", json.dumps(dismiss_response, indent=2))
                        
                        # Get auth token
                        print("\nGetting authentication token...")
                        auth_response = client.getAuthToken()
                        print("Auth token response:", json.dumps(auth_response, indent=2))
                        
                        if 'error' not in auth_response:
                            return True
                        
                print("Authentication step failed. Retrying...")
                break

            retry_count += 1

        except Exception as e:
            print(f"\nError during login process: {str(e)}")
            retry_count += 1

    return False

def upload_photos(client, photos):
    print(f"\nPreparing to upload {len(photos)} photos...")
    
    for i, photo_data in enumerate(photos, 1):
        print(f"\nUploading photo {i}/{len(photos)}...")
        print(f"Photo size: {len(photo_data)/1024:.2f}KB")
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Attempt {retry_count + 1} of {max_retries}")
                response = client.onboardingPhoto(photo_data, len(photos))
                response_data = debug_response(response, client.last_status_code)
                
                if response_data and response_data.get('meta', {}).get('status') == 200:
                    print(f"Successfully uploaded photo {i}")
                    break
                else:
                    print(f"Failed to upload photo {i} - Retrying...")
                    retry_count += 1
                    time.sleep(2)  # Wait before retry
            
            except Exception as e:
                print(f"Error uploading photo {i}: {str(e)}")
                retry_count += 1
                time.sleep(2)
        
        if retry_count >= max_retries:
            print(f"Failed to upload photo {i} after {max_retries} attempts")
        
        time.sleep(3)  # Wait between photos

def main():
    try:
        print("Welcome to Tinder Registration!")
        print("-" * 50)

        # Get user input
        while True:
            name = input("\nEnter your name: ").strip()
            if len(name) >= 2:
                break
            print("Name must be at least 2 characters long")

        while True:
            dob = input("\nEnter your date of birth (YYYY-MM-DD): ").strip()
            if validate_date(dob):
                break
            print("Invalid date format. Please use YYYY-MM-DD format")

        while True:
            print("\nSelect your gender:")
            print("0: Male")
            print("1: Female")
            try:
                gender = int(input("Enter number (0 or 1): "))
                if gender in [0, 1]:
                    break
                print("Please enter 0 or 1")
            except ValueError:
                print("Please enter a valid number")

        while True:
            email = input("\nEnter your email address: ").strip()
            if '@' in email and '.' in email:
                break
            print("Please enter a valid email address")

        # Check photos with detailed logging
        print("\nChecking photos directory...")
        photos = get_photos_from_folder()
        if not photos:
            print("No photos found in the photos directory! Please add some photos and try again.")
            return

        # Initialize client
        client = TinderClient(
            userAgent="Tinder/14.21.0 (iPhone; iOS 14.2.0; Scale/2.00)",
            platform="ios",
            tinderVersion="14.21.0",
            appVersion="5546",
            osVersion=140000200000,
            language="en-US"
        )

        # Initialize session
        print("\nInitializing session...")
        buckets_response = client.sendBuckets()
        if buckets_response:
            print("Session initialized successfully")
        
        time.sleep(1)

        # Device check
        print("\nPerforming device check...")
        client.deviceCheck()
        
        time.sleep(1)

        # Handle authentication
        if not handle_auth_process(client, email):
            print("\nAuthentication failed. Exiting...")
            return

        time.sleep(2)

        # Start onboarding
        print("\nStarting onboarding process...")
        onboarding_response = client.startOnboarding()
        print("Onboarding response:", json.dumps(debug_response(onboarding_response, client.last_status_code), indent=2))

        time.sleep(2)

        # Set basic info
        print("\nSetting basic information...")
        info_response = client.onboardingSuper(name, dob, gender, [0, 1])
        print("User info response:", json.dumps(debug_response(info_response, client.last_status_code), indent=2))

        time.sleep(2)

        # Upload photos with improved handling
        print("\nStarting photo upload process...")
        upload_photos(client, photos)

        time.sleep(2)

        # Complete registration
        print("\nCompleting registration...")
        complete_response = client.endOnboarding()
        print("Registration complete response:", json.dumps(debug_response(complete_response, client.last_status_code), indent=2))

        print("\nRegistration process completed!")

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
