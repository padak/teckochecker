#!/bin/bash

# TeckoChecker API Test Script
# This script tests basic API functionality

echo "======================================="
echo "   TeckoChecker API Test Suite"
echo "======================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# API base URL
API_URL="http://127.0.0.1:8000"

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2

    echo -n "Testing $description... "

    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint")

    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✓${NC} OK"
        return 0
    else
        echo -e "${RED}✗${NC} Failed (HTTP $response)"
        return 1
    fi
}

# Function to pretty print JSON
pretty_json() {
    local endpoint=$1
    curl -s "$API_URL$endpoint" | python3 -m json.tool 2>/dev/null || echo "Failed to get response"
}

echo "1. Testing API connectivity..."
echo "-------------------------------"

test_endpoint "/api/health" "Health endpoint"
test_endpoint "/api/stats" "Stats endpoint"
test_endpoint "/docs" "Swagger documentation"
test_endpoint "/redoc" "ReDoc documentation"

echo ""
echo "2. API Response Details"
echo "-------------------------------"

echo "Health Status:"
pretty_json "/api/health"

echo ""
echo "System Statistics:"
pretty_json "/api/stats"

echo ""
echo "3. API Documentation URLs"
echo "-------------------------------"
echo "Swagger UI: $API_URL/docs"
echo "ReDoc:      $API_URL/redoc"
echo "OpenAPI:    $API_URL/openapi.json"

echo ""
echo "======================================="
echo "   Test Complete"
echo "======================================="