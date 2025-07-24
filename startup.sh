#!/bin/bash

# Simple Trading Platform Startup Script
# Updated version with health checks and better error handling

set -e

echo "🚀 Starting Efficient Trading Platform..."

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

# Install requirements
echo "📦 Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found, installing minimal dependencies..."
    pip install Flask>=3.0.0 flask-cors>=4.0.0 requests>=2.30.0 gunicorn>=22.0.0
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file template..."
    cat > .env << EOF
# Binance API Configuration
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET_KEY=your_binance_secret_key_here

# Flask Configuration
FLASK_ENV=production
PORT=8080
LOG_LEVEL=INFO

# Rebalancing Settings
DEFAULT_TARGET_LTV=74.0
DEFAULT_REBALANCE_THRESHOLD=2.0
MIN_REBALANCE_INTERVAL=300
EOF
    echo "⚠️  Please edit .env file with your actual API keys before starting"
fi

# Load environment variables
if [ -f ".env" ]; then
    echo "🔧 Loading environment variables..."
    export $(grep -v '^#' .env | xargs)
fi

# Set default environment variables
export FLASK_ENV=${FLASK_ENV:-production}
export PORT=${PORT:-8080}

# Create logs directory
mkdir -p logs

# Run health checks
echo "🏥 Running health checks..."
if [ -f "health_check.py" ]; then
    $PYTHON_CMD health_check.py
    if [ $? -ne 0 ]; then
        echo "❌ Health checks failed! Please check the errors above."
        echo "💡 You can still continue, but there may be issues."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo "⚠️  health_check.py not found, skipping health checks"
fi

# Display configuration
echo ""
echo "⚙️  Configuration:"
echo "   Port: $PORT"
echo "   Flask Environment: $FLASK_ENV"
echo "   API Key Set: $([ -n "$BINANCE_API_KEY" ] && [ "$BINANCE_API_KEY" != "your_binance_api_key_here" ] && echo "✅" || echo "❌")"
echo "   Secret Key Set: $([ -n "$BINANCE_SECRET_KEY" ] && [ "$BINANCE_SECRET_KEY" != "your_binance_secret_key_here" ] && echo "✅" || echo "❌")"
echo ""

# Check if API keys are configured
if [ "$BINANCE_API_KEY" = "your_binance_api_key_here" ] || [ -z "$BINANCE_API_KEY" ]; then
    echo "⚠️  WARNING: Please configure your Binance API keys in .env file"
    echo "   The platform will run with limited functionality"
else
    echo "🔑 API keys configured"
fi

echo ""
echo "🌐 Starting server..."

# Start the application
if [ "$FLASK_ENV" = "development" ]; then
    echo "🔧 Starting in DEVELOPMENT mode..."
    $PYTHON_CMD app.py
else
    echo "🚀 Starting with Gunicorn..."
    echo "   Platform will be available at: http://0.0.0.0:$PORT"
    
    # Use wsgi.py if available, otherwise fall back to app.py
    if [ -f "wsgi.py" ]; then
        echo "   Using WSGI entry point: wsgi.py"
        gunicorn wsgi:application \
            --bind 0.0.0.0:$PORT \
            --workers 1 \
            --timeout 120 \
            --access-logfile logs/access.log \
            --error-logfile logs/error.log \
            --log-level info \
            --preload
    else
        echo "   Using direct app import: app.py"
        gunicorn app:app \
            --bind 0.0.0.0:$PORT \
            --workers 1 \
            --timeout 120 \
            --access-logfile logs/access.log \
            --error-logfile logs/error.log \
            --log-level info \
            --preload
    fi
fi