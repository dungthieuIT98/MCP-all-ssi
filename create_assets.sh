#!/bin/sh
BASE="http://localhost:8088"

# Login + cookies
TOKEN=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt -X POST "$BASE/api/v1/security/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin","provider":"db","refresh":true}' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

get_csrf() {
  curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
    -X GET "$BASE/api/v1/security/csrf_token/" \
    -H "Authorization: Bearer $TOKEN" \
    | grep -o '"result":"[^"]*"' | cut -d'"' -f4
}

CSRF=$(get_csrf)
echo "TOKEN len=${#TOKEN} CSRF len=${#CSRF}"

# 1. Find Trino DB
DB_RESP=$(curl -s -b /tmp/jar.txt \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/api/v1/database/")
echo "Databases: $(echo $DB_RESP | grep -o '"database_name":"[^"]*"')"

DB_ID=$(echo "$DB_RESP" | grep -o '"id":[0-9]*,"uuid"' | head -1 | grep -o '[0-9]*')
echo "Trino DB ID: $DB_ID"

# 2. Create dataset
CSRF=$(get_csrf)
DS_RESP=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X POST "$BASE/api/v1/dataset/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: $BASE" \
  -d "{\"database\":$DB_ID,\"schema\":\"demo\",\"table_name\":\"stock_prices\"}")
echo "Dataset resp: $DS_RESP"
DS_ID=$(echo "$DS_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "Dataset ID: $DS_ID"

# 3. Create chart
CSRF=$(get_csrf)
PARAMS='{"metrics":[{"expressionType":"SIMPLE","column":{"column_name":"close_price"},"aggregate":"AVG","label":"AVG(close_price)"}],"groupby":["symbol"],"x_axis":"trade_date","adhoc_filters":[],"row_limit":10000,"time_grain_sqla":"P1D","x_axis_sort_asc":true,"x_axis_sort_series":"name","x_axis_sort_series_ascending":true}'
CHART_RESP=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X POST "$BASE/api/v1/chart/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: $BASE" \
  -d "{\"slice_name\":\"Stock Close Price Over Time\",\"viz_type\":\"echarts_timeseries_line\",\"datasource_id\":$DS_ID,\"datasource_type\":\"table\",\"params\":$(echo $PARAMS | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))')}")
echo "Chart resp: $CHART_RESP"
CHART_ID=$(echo "$CHART_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "Chart ID: $CHART_ID"

# 4. Create dashboard
CSRF=$(get_csrf)
POSITION="{\"DASHBOARD_VERSION_KEY\":\"v2\",\"ROOT_ID\":{\"children\":[\"GRID_ID\"],\"id\":\"ROOT_ID\",\"type\":\"ROOT\"},\"GRID_ID\":{\"children\":[\"ROW-1\"],\"id\":\"GRID_ID\",\"type\":\"GRID\"},\"ROW-1\":{\"children\":[\"CHART-$CHART_ID\"],\"id\":\"ROW-1\",\"meta\":{\"background\":\"BACKGROUND_TRANSPARENT\"},\"type\":\"ROW\"},\"CHART-$CHART_ID\":{\"children\":[],\"id\":\"CHART-$CHART_ID\",\"meta\":{\"chartId\":$CHART_ID,\"height\":50,\"sliceName\":\"Stock Close Price Over Time\",\"width\":12},\"type\":\"CHART\"}}"
DASH_RESP=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X POST "$BASE/api/v1/dashboard/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: $BASE" \
  -d "{\"dashboard_title\":\"Stock Prices Dashboard\",\"slug\":\"stock-prices\",\"published\":true,\"position_json\":$(echo $POSITION | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))'),\"metadata\":\"{\\\"color_scheme\\\":\\\"\\\",\\\"expanded_slices\\\":{},\\\"refresh_frequency\\\":0}\"}")
echo "Dashboard resp: $DASH_RESP"
DASH_ID=$(echo "$DASH_RESP" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

echo ""
echo "=== DONE: DB=$DB_ID DATASET=$DS_ID CHART=$CHART_ID DASHBOARD=$DASH_ID ==="
