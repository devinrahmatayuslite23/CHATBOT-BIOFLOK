"""
One-time OAuth authorization script
Run this ONCE to login and generate token
"""
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes yang dibutuhkan
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

def authorize():
    """Authorize and save token"""
    creds = None
    
    # Check if token.pickle exists (sudah login sebelumnya)
    if os.path.exists('token.pickle'):
        print("📂 Found existing token...")
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🔐 Starting OAuth authorization flow...")
            print("   Browser will open for login")
            print("   Login dengan akun Google Anda\n")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'oauth_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save token for future use
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        
        print("\n✅ Authorization successful!")
        print("   Token saved to token.pickle")
        print("   You won't need to login again!")
    else:
        print("✅ Valid token found! Already authorized.")
    
    return creds

if __name__ == '__main__':
    print("=" * 60)
    print("🔑 OAUTH AUTHORIZATION - BIOFLOK CHATBOT")
    print("=" * 60)
    print("\nThis script will:")
    print("1. Open browser for Google login")
    print("2. Ask permission to access Drive & Sheets")
    print("3. Save token for future use")
    print("\nAfter this, uploads will work automatically!\n")
    
    input("Press ENTER to continue...")
    
    try:
        creds = authorize()
        
        # Test credentials
        from googleapiclient.discovery import build
        service = build('drive', 'v3', credentials=creds)
        about = service.about().get(fields="user,storageQuota").execute()
        
        print("\n" + "=" * 60)
        print("📊 ACCOUNT INFO")
        print("=" * 60)
        print(f"User: {about['user']['emailAddress']}")
        print(f"Display Name: {about['user']['displayName']}")
        
        if 'storageQuota' in about:
            quota = about['storageQuota']
            limit = int(quota.get('limit', 0))
            usage = int(quota.get('usage', 0))
            
            limit_gb = limit / (1024**3)
            usage_gb = usage / (1024**3)
            
            print(f"\nStorage Quota:")
            print(f"  Limit: {limit_gb:.2f} GB")
            print(f"  Used: {usage_gb:.2f} GB")
            print(f"  Available: {limit_gb - usage_gb:.2f} GB")
        
        print("\n✅ All set! You can now run the chatbot.")
        print("   Photos will be uploaded to your Google Drive!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure oauth_credentials.json exists")
        print("2. Check internet connection")
        print("3. Try again")
