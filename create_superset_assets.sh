#!/bin/sh
set -e

BASE="http://localhost:8088"

# Login
TOKEN=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt -X POST "$BASE/api/v1/security/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin","provider":"db","refresh":true}' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

# CSRF
CSRF=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X GET "$BASE/api/v1/security/csrf_token/" \
  -H "Authorization: Bearer $TOKEN" \
  | grep -o '"result":"[^"]*"' | cut -d'"' -f4)

echo "=== Auth OK ==="

# 1. Get Trino database ID
DB_ID=$(curl -s -b /tmp/jar.txt \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/api/v1/database/?q=(filters:!((col:database_name,opr:DatabaseStartsWith,val:Trino)))" \
  | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

echo "=== Trino DB ID: $DB_ID ==="

# 2. Create dataset from stock_prices
DATASET=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X POST "$BASE/api/v1/dataset/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: $BASE" \
  -d "{
    \"database\": $DB_ID,
    \"schema\": \"demo\",
    \"table_name\": \"stock_prices\"
  }")

echo "=== Dataset response: $DATASET ==="
DATASET_ID=$(echo "$DATASET" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "=== Dataset ID: $DATASET_ID ==="

# Refresh CSRF
CSRF=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X GET "$BASE/api/v1/security/csrf_token/" \
  -H "Authorization: Bearer $TOKEN" \
  | grep -o '"result":"[^"]*"' | cut -d'"' -f4)

# 3. Create chart (line chart: close_price over trade_date by symbol)
CHART=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X POST "$BASE/api/v1/chart/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: $BASE" \
  -d "{
    \"slice_name\": \"Stock Close Price Over Time\",
    \"viz_type\": \"echarts_timeseries_line\",
    \"datasource_id\": $DATASET_ID,
    \"datasource_type\": \"table\",
    \"params\": \"{\\\"metrics\\\":[{\\\"expressionType\\\":\\\"SIMPLE\\\",\\\"column\\\":{\\\"column_name\\\":\\\"close_price\\\"},\\\"aggregate\\\":\\\"AVG\\\",\\\"label\\\":\\\"AVG(close_price)\\\"}],\\\"groupby\\\":[\\\"symbol\\\"],\\\"x_axis\\\":\\\"trade_date\\\",\\\"adhoc_filters\\\":[],\\\"row_limit\\\":10000,\\\"time_grain_sqla\\\":\\\"P1D\\\"}\"
  }")

echo "=== Chart response: $CHART ==="
CHART_ID=$(echo "$CHART" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "=== Chart ID: $CHART_ID ==="

# Refresh CSRF
CSRF=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X GET "$BASE/api/v1/security/csrf_token/" \
  -H "Authorization: Bearer $TOKEN" \
  | grep -o '"result":"[^"]*"' | cut -d'"' -f4)

# 4. Create dashboard
DASH=$(curl -s -c /tmp/jar.txt -b /tmp/jar.txt \
  -X POST "$BASE/api/v1/dashboard/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: $BASE" \
  -d "{
    \"dashboard_title\": \"Stock Prices Dashboard\",
    \"slug\": \"stock-prices\",
    \"published\": true,
    \"position_json\": \"{\\\"DASHBOARD_VERSION_KEY\\\":\\\"v2\\\",\\\"ROOT_ID\\\":{\\\"children\\\":[\\\"GRID_ID\\\"],\\\"id\\\":\\\"ROOT_ID\\\",\\\"type\\\":\\\"ROOT\\\"},\\\"GRID_ID\\\":{\\\"children\\\":[\\\"ROW-1\\\"],\\\"id\\\":\\\"GRID_ID\\\",\\\"type\\\":\\\"GRID\\\"},\\\"ROW-1\\\":{\\\"children\\\":[\\\"CHART-$CHART_ID\\\"],\\\"id\\\":\\\"ROW-1\\\",\\\"meta\\\":{\\\"background\\\":\\\"BACKGROUND_TRANSPARENT\\\"},\\\"type\\\":\\\"ROW\\\"},\\\"CHART-$CHART_ID\\\":{\\\"children\\\":[],\\\"id\\\":\\\"CHART-$CHART_ID\\\",\\\"meta\\\":{\\\"chartId\\\":$CHART_ID,\\\"height\\\":50,\\\"sliceName\\\":\\\"Stock Close Price Over Time\\\",\\\"width\\\":12},\\\"type\\\":\\\"CHART\\\"}}\",
    \"metadata\": \"{\\\"color_scheme\\\":\\\"\\\",\\\"expanded_slices\\\":{},\\\"refresh_frequency\\\":0}\"
  }")

echo "=== Dashboard response: $DASH ==="
DASH_ID=$(echo "$DASH" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "=== Dashboard ID: $DASH_ID ==="

echo "=== DONE: DB=$DB_ID DATASET=$DATASET_ID CHART=$CHART_ID DASHBOARD=$DASH_ID ==="
