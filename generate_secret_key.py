#!/usr/bin/env python3
"""
Generate a secure Flask secret key for production use.
Run this script to generate a new secret key and update your .env file.
"""

import os
import secrets
import uuid
import hashlib
from datetime import datetime

def generate_secure_key_methods():
    """Generate secure keys using different methods"""
    
    print("🔐 Flask Secret Key Generator")
    print("=" * 50)
    
    # Method 1: Using secrets module (recommended)
    method1 = secrets.token_hex(32)  # 64 character hex string
    print(f"Method 1 (secrets.token_hex): {method1}")
    
    # Method 2: Using secrets with URL-safe base64
    method2 = secrets.token_urlsafe(32)  # URL-safe base64 string
    print(f"Method 2 (secrets.token_urlsafe): {method2}")
    
    # Method 3: Using UUID4 (good but shorter)
    method3 = str(uuid.uuid4()).replace('-', '')
    print(f"Method 3 (UUID4): {method3}")
    
    # Method 4: Using os.urandom with hex encoding
    method4 = os.urandom(32).hex()
    print(f"Method 4 (os.urandom): {method4}")
    
    # Method 5: Complex combination (most secure)
    timestamp = str(datetime.now().timestamp())
    random_bytes = os.urandom(32)
    uuid_str = str(uuid.uuid4())
    combined = f"{timestamp}-{random_bytes.hex()}-{uuid_str}"
    method5 = hashlib.sha256(combined.encode()).hexdigest()
    print(f"Method 5 (complex hash): {method5}")
    
    print("\n" + "=" * 50)
    print("✅ RECOMMENDED: Use Method 1 or Method 2 for production")
    print("✅ Method 1 is the most standard approach")
    
    return method1

def update_env_file(secret_key):
    """Update the .env file with the new secret key"""
    env_file_path = ".env"
    
    if not os.path.exists(env_file_path):
        print(f"❌ .env file not found at {env_file_path}")
        return False
    
    try:
        # Read current .env file
        with open(env_file_path, 'r') as f:
            lines = f.readlines()
        
        # Update the SECRET_KEY line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('SECRET_KEY='):
                lines[i] = f"SECRET_KEY={secret_key}\n"
                updated = True
                break
        
        if not updated:
            # Add SECRET_KEY if not found
            lines.append(f"SECRET_KEY={secret_key}\n")
        
        # Write back to file
        with open(env_file_path, 'w') as f:
            f.writelines(lines)
        
        print(f"✅ Successfully updated SECRET_KEY in {env_file_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def main():
    """Main function to generate and optionally update secret key"""
    
    # Generate secure key
    recommended_key = generate_secure_key_methods()
    
    print(f"\n🎯 COPY THIS SECRET KEY TO YOUR .env FILE:")
    print(f"SECRET_KEY={recommended_key}")
    
    # Ask if user wants to automatically update .env file
    response = input("\n🤔 Do you want to automatically update your .env file? (y/n): ").lower().strip()
    
    if response in ['y', 'yes']:
        if update_env_file(recommended_key):
            print("\n🎉 Your .env file has been updated with the new secure secret key!")
        else:
            print("\n💡 Please manually copy the secret key to your .env file.")
    else:
        print("\n💡 Please manually copy the secret key to your .env file:")
        print(f"   SECRET_KEY={recommended_key}")
    
    print("\n📋 Security Tips:")
    print("• Never commit your secret key to version control")
    print("• Use different keys for development and production")
    print("• Regenerate keys periodically for maximum security")
    print("• Keep your .env file in .gitignore")

if __name__ == "__main__":
    main()