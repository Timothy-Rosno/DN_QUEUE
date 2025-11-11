#!/usr/bin/env bash
set -e

echo "🔧 Fixing Render build/start commands..."
echo ""

# Check if RENDER_API_KEY is set
if [ -z "$RENDER_API_KEY" ]; then
    echo "❌ Error: RENDER_API_KEY environment variable not set"
    echo ""
    echo "To get your API key:"
    echo "1. Go to https://dashboard.render.com/account/settings"
    echo "2. Scroll to 'API Keys' section"
    echo "3. Create a new API key or copy existing one"
    echo ""
    echo "Then run:"
    echo "export RENDER_API_KEY='your-api-key-here'"
    echo "./fix-render-commands.sh"
    exit 1
fi

# Your service details
SERVICE_ID="qhog"
BUILD_COMMAND="pip install -r requirements.txt && python manage.py collectstatic --noinput"
START_COMMAND="./start.sh"

echo "Looking up service ID for: $SERVICE_ID"

# Get all services and find the one named 'qhog'
SERVICES=$(curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
    "https://api.render.com/v1/services?name=$SERVICE_ID")

# Extract the actual service ID from the response
ACTUAL_SERVICE_ID=$(echo "$SERVICES" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$ACTUAL_SERVICE_ID" ]; then
    echo "❌ Error: Could not find service '$SERVICE_ID'"
    echo "Response: $SERVICES"
    exit 1
fi

echo "✅ Found service ID: $ACTUAL_SERVICE_ID"
echo ""
echo "Updating build and start commands..."

# Update the service settings
curl -X PATCH \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"buildCommand\": \"$BUILD_COMMAND\",
        \"startCommand\": \"$START_COMMAND\"
    }" \
    "https://api.render.com/v1/services/$ACTUAL_SERVICE_ID"

echo ""
echo "✅ Commands updated successfully!"
echo ""
echo "Build Command: $BUILD_COMMAND"
echo "Start Command: $START_COMMAND"
echo ""
echo "Now triggering a new deploy..."

# Trigger a deploy
curl -X POST \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"clearCache": "do_not_clear"}' \
    "https://api.render.com/v1/services/$ACTUAL_SERVICE_ID/deploys"

echo ""
echo "✅ Deploy triggered!"
echo "Check your Render dashboard to monitor the deployment."
