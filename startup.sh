#!/bin/bash

# Efficient Trading Platform Startup Script
# Enhanced version with rebalancing support and better error handling

set -e

echo "🚀 Starting Efficient Trading Platform with Rebalancing..."

# Check if we're in the correct directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Please run this script from the project root directory."
    exit 1
fi

# Check Python availability
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ Error: Python not found. Please install Python 3.8 or higher."
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "🐍 Using Python: $($PYTHON_CMD --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🔧 Creating Python virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows
    source venv/Scripts/activate
else
    # Unix/Linux/macOS
    source venv/bin/activate
fi

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install all requirements
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Try to install additional production dependencies
echo "📦 Installing additional production dependencies..."

# Install APScheduler for advanced scheduling
if pip install APScheduler>=3.10.0; then
    echo "✅ APScheduler installed for advanced scheduling"
else
    echo "⚠️  APScheduler installation failed"
fi

# Install python-dotenv for better .env support
if pip install python-dotenv>=1.0.0; then
    echo "✅ python-dotenv installed"
else
    echo "⚠️  python-dotenv installation failed"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cat > .env << EOF
# Binance API Configuration
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET_KEY=your_binance_secret_key_here

# Rebalancing Settings
DEFAULT_TARGET_LTV=74.0
DEFAULT_REBALANCE_THRESHOLD=2.0
MIN_REBALANCE_INTERVAL=300
MAX_BORROW_AMOUNT_USD=10000
MIN_REPAY_AMOUNT_USD=10

# Flask Configuration
FLASK_ENV=production
PORT=8080
LOG_LEVEL=INFO

# Optional: Webhook Settings
WEBHOOK_SECRET=your_webhook_secret_here
ENABLE_AUTO_REBALANCE=false
EOF
    echo "⚠️  Please edit .env file with your actual API keys before starting"
fi

# Create logs directory
mkdir -p logs

# Set environment variables with defaults
export FLASK_ENV=${FLASK_ENV:-production}
export PORT=${PORT:-8080}
export DEFAULT_TARGET_LTV=${DEFAULT_TARGET_LTV:-74.0}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# Check if Gunicorn is available
GUNICORN_AVAILABLE=false
if command -v gunicorn &> /dev/null; then
    GUNICORN_AVAILABLE=true
fi

# Display configuration
echo ""
echo "⚙️  Configuration:"
echo "   Port: $PORT"
echo "   Target LTV: $DEFAULT_TARGET_LTV%"
echo "   Flask Environment: $FLASK_ENV"
echo "   Log Level: $LOG_LEVEL"
echo "   Gunicorn Available: $GUNICORN_AVAILABLE"
echo ""

# Check if API keys are configured
if grep -q "your_binance_api_key_here" .env 2>/dev/null; then
    echo "⚠️  WARNING: Please configure your Binance API keys in .env file"
    echo "   The platform will run with limited functionality"
    echo ""
    echo "📋 Required Environment Variables:"
    echo "   BINANCE_API_KEY - Your Binance API key"
    echo "   BINANCE_SECRET_KEY - Your Binance secret key"
    echo ""
    echo "📋 Optional Environment Variables:"
    echo "   DEFAULT_TARGET_LTV - Target LTV ratio (default: 74.0)"
    echo "   DEFAULT_REBALANCE_THRESHOLD - Rebalance threshold (default: 2.0)"
    echo "   MIN_REBALANCE_INTERVAL - Min seconds between rebalances (default: 300)"
    echo "   LOG_LEVEL - Logging level (default: INFO)"
    echo ""
else
    echo "🔑 API keys configured"
fi

# Validate critical files exist
REQUIRED_FILES=("app.py" "rebalancing_module.py" "templates/index.html" "static/frontend-clientid.js")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Error: Required file $file not found"
        exit 1
    fi
done

echo "✅ All required files present"

# Check if all required Python packages are available
echo "🔍 Checking Python package availability..."
$PYTHON_CMD -c "
import sys
try:
    import flask
    import flask_cors
    import requests
    import hmac
    import hashlib
    print('✅ All core packages available')
except ImportError as e:
    print(f'❌ Missing package: {e}')
    sys.exit(1)
"

echo ""
echo "🌐 Starting server..."
echo "   📊 Dashboard will be available at: http://0.0.0.0:$PORT"
echo "   🔌 Webhook endpoint format: http://0.0.0.0:$PORT/webhook/tradingview/strategy/{strategy_id}"
echo "   ⚖️ Rebalancing engine: Enabled"
echo ""

# Start the application based on environment and availability
if [ "$FLASK_ENV" = "development" ]; then
    echo "🔧 Starting in DEVELOPMENT mode..."
    $PYTHON_CMD app.py
elif [ "$GUNICORN_AVAILABLE" = true ]; then
    echo "🚀 Starting with Gunicorn (Production)..."
    gunicorn app:app \
        --bind 0.0.0.0:$PORT \
        --workers 1 \
        --timeout 120 \
        --access-logfile logs/access.log \
        --error-logfile logs/error.log \
        --log-level info \
        --preload
else
    echo "🚀 Starting with Python development server..."
    echo "⚠️  Note: For production, install Gunicorn: pip install gunicorn"
    $PYTHON_CMD app.py
fi