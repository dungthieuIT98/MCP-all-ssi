#!/bin/sh
BASE="http://localhost:8088"

get_csrf() {
  curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
    -X GET "$BASE/api/v1/security/csrf_token/" \
    -H "Authorization: Bearer $TOKEN" \
    | grep -o '"result":"[^"]*"' | cut -d'"' -f4
}

TOKEN=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt -X POST "$BASE/api/v1/security/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin","provider":"db","refresh":true}' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

CSRF=$(get_csrf)
echo "Auth OK"

POSITION='{"DASHBOARD_VERSION_KEY":"v2","ROOT_ID":{"children":["GRID_ID"],"id":"ROOT_ID","type":"ROOT"},"GRID_ID":{"children":["ROW-1"],"id":"GRID_ID","type":"GRID"},"ROW-1":{"children":["CHART-1"],"id":"ROW-1","meta":{"background":"BACKGROUND_TRANSPARENT"},"type":"ROW"},"CHART-1":{"children":[],"id":"CHART-1","meta":{"chartId":1,"height":50,"sliceName":"Stock Close Price Over Time","width":12},"type":"CHART"}}'

DASH_RESP=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X POST "$BASE/api/v1/dashboard/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: $BASE" \
  -d "{\"dashboard_title\":\"Stock Prices Dashboard\",\"slug\":\"stock-prices\",\"published\":true,\"position_json\":\"$(echo $POSITION | sed 's/"/\\"/g')\"}")

echo "Dashboard: $DASH_RESP"
