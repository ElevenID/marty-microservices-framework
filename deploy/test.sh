#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://identity.local:8080"

echo -e "${BLUE}🧪 Testing MMF Identity Service${NC}"

# Test health endpoint
echo -e "${YELLOW}1. Testing health endpoint...${NC}"
if curl -s -f "$BASE_URL/health" > /dev/null; then
    echo -e "${GREEN}✅ Health check passed${NC}"
    curl -s "$BASE_URL/health" | jq .
else
    echo -e "${RED}❌ Health check failed${NC}"
    exit 1
fi

echo ""

# Test users endpoint
echo -e "${YELLOW}2. Getting test users...${NC}"
echo -e "${GREEN}✅ Available test users:${NC}"
curl -s "$BASE_URL/users" | jq .

echo ""

# Test successful authentication
echo -e "${YELLOW}3. Testing successful authentication...${NC}"
response=$(curl -s -X POST "$BASE_URL/authenticate" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}')

if echo "$response" | jq -r '.success' | grep -q true; then
    echo -e "${GREEN}✅ Authentication successful${NC}"
    echo "$response" | jq .
else
    echo -e "${RED}❌ Authentication failed${NC}"
    echo "$response" | jq .
fi

echo ""

# Test failed authentication
echo -e "${YELLOW}4. Testing failed authentication...${NC}"
response=$(curl -s -X POST "$BASE_URL/authenticate" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "wrongpassword"}')

if echo "$response" | jq -r '.success' | grep -q false; then
    echo -e "${GREEN}✅ Failed authentication handled correctly${NC}"
    echo "$response" | jq .
else
    echo -e "${RED}❌ Failed authentication not handled correctly${NC}"
    echo "$response" | jq .
fi

echo ""

# Test events endpoint
echo -e "${YELLOW}5. Checking published events...${NC}"
echo -e "${GREEN}✅ Published events:${NC}"
curl -s "$BASE_URL/events" | jq .

echo ""
echo -e "${GREEN}🎉 All tests completed!${NC}"
