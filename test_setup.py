#!/usr/bin/env python3
"""
Test Setup Script for Efficient Trading Platform
Validates configuration and API connectivity
"""

import os
import sys
import time
import requests
from datetime import datetime

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"🔍 {title}")
    print("=" * 60)

def check_environment():
    """Check environment variables"""
    print_header("Environment Configuration")
    
    required_vars = ['BINANCE_API_KEY', 'BINANCE_SECRET_KEY']
    optional_vars = ['DEFAULT_TARGET_LTV', 'DEFAULT_REBALANCE_THRESHOLD', 'LOG_LEVEL', 'PORT']
    
    missing_required = []
    
    print("📋 Required Environment Variables:")
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            masked_value = f"{value[:8]}..." if len(value) > 8 else "***"
            print(f"   ✅ {var}: {masked_value}")
        else:
            print(f"   ❌ {var}: Not set")
            missing_required.append(var)
    
    print("\n📋 Optional Environment Variables:")
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            print(f"   ✅ {var}: {value}")
        else:
            print(f"   ⚪ {var}: Using default")
    
    return len(missing_required) == 0

def check_dependencies():
    """Check if all required Python packages are installed"""
    print_header("Python Dependencies")
    
    required_packages = [
        ('flask', 'Flask'),
        ('flask_cors', 'Flask-CORS'),
        ('requests', 'Requests'),
        ('hmac', 'HMAC (built-in)'),
        ('hashlib', 'Hashlib (built-in)'),
        ('json', 'JSON (built-in)'),
        ('time', 'Time (built-in)'),
        ('datetime', 'Datetime (built-in)')
    ]
    
    optional_packages = [
        ('dotenv', 'python-dotenv'),
        ('apscheduler', 'APScheduler')
    ]
    
    print("📦 Required Packages:")
    all_required_available = True
    for module, name in required_packages:
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} - Missing!")
            all_required_available = False
    
    print("\n📦 Optional Packages:")
    for module, name in optional_packages:
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ⚪ {name} - Not installed (optional)")
    
    return all_required_available

def check_files():
    """Check if all required files exist"""
    print_header("File Structure")
    
    required_files = [
        'app.py',
        'rebalancing_module.py',
        'requirements.txt',
        'templates/index.html',
        'static/frontend-clientid.js'
    ]
    
    optional_files = [
        '.env',
        'railway.json',
        'Procfile',
        'Dockerfile',
        'startup.sh',
        'logging_config.py'
    ]
    
    print("📁 Required Files:")
    all_files_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"   ✅ {file_path} ({size} bytes)")
        else:
            print(f"   ❌ {file_path} - Missing!")
            all_files_exist = False
    
    print("\n📁 Optional Files:")
    for file_path in optional_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"   ✅ {file_path} ({size} bytes)")
        else:
            print(f"   ⚪ {file_path} - Not found (optional)")
    
    return all_files_exist

def test_binance_connectivity():
    """Test Binance API connectivity"""
    print_header("Binance API Connectivity")
    
    # Test public endpoint (no auth required)
    try:
        print("🌐 Testing public API endpoint...")
        response = requests.get(
            "https://api.binance.com/api/v3/ping",
            timeout=10
        )
        if response.status_code == 200:
            print("   ✅ Binance API is reachable")
        else:
            print(f"   ❌ Binance API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Failed to reach Binance API: {str(e)}")
        return False
    
    # Test server time
    try:
        print("🕐 Testing server time synchronization...")
        response = requests.get(
            "https://api.binance.com/api/v3/time",
            timeout=10
        )
        if response.status_code == 200:
            server_time = response.json()['serverTime']
            local_time = int(time.time() * 1000)
            time_diff = abs(server_time - local_time)
            
            print(f"   Server time: {datetime.fromtimestamp(server_time/1000)}")
            print(f"   Local time:  {datetime.fromtimestamp(local_time/1000)}")
            print(f"   Difference:  {time_diff}ms")
            
            if time_diff < 5000:  # 5 seconds
                print("   ✅ Time synchronization OK")
            else:
                print("   ⚠️  Time difference > 5 seconds - may cause auth issues")
        else:
            print(f"   ❌ Failed to get server time: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Failed to check server time: {str(e)}")
    
    return True

def test_local_server():
    """Test if local server can start"""
    print_header("Local Server Test")
    
    try:
        # Import the app to check for import errors
        print("📦 Testing app imports...")
        sys.path.insert(0, os.getcwd())
        
        import app
        print("   ✅ Main app module imports successfully")
        
        import rebalancing_module
        print("   ✅ Rebalancing module imports successfully")
        
        # Check if Flask app can be created
        print("🌐 Testing Flask app creation...")
        test_app = app.app
        print("   ✅ Flask app created successfully")
        
        # Check if critical routes exist
        print("🛣️  Testing route registration...")
        routes = [rule.rule for rule in test_app.url_map.iter_rules()]
        critical_routes = ['/', '/health', '/api/connect']
        
        for route in critical_routes:
            if route in routes:
                print(f"   ✅ Route {route} registered")
            else:
                print(f"   ❌ Route {route} missing")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to test app: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Efficient Trading Platform - Setup Test")
    print(f"⏰ Test started at: {datetime.now().isoformat()}")
    
    tests = [
        ("Environment", check_environment),
        ("Dependencies", check_dependencies),
        ("Files", check_files),
        ("Binance API", test_binance_connectivity),
        ("Local Server", test_local_server)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with error: {str(e)}")
            results[test_name] = False
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n📊 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your setup looks good.")
        print("\n🚀 Next steps:")
        print("   1. Make sure your .env file has valid API keys")
        print("   2. Run: python app.py or ./startup.sh")
        print("   3. Access dashboard at: http://localhost:8080")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above before running the platform.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)