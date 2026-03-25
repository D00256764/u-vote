#!/usr/bin/env python3
"""Create UVote Platform Logs dashboard in Kibana 8.5.1"""
import json
import os
import sys
import urllib.request
import urllib.error
import base64

BASE = "http://localhost:5601"
USER = "elastic"
PASS = os.environ.get("ES_PASSWORD", "a0MmngBaLXa3Dba1")
DV_ID = "f0a18b54-cb47-4ad5-b544-1da0ae22da4f"

# Stable UUIDs
P1   = "11111111-1111-1111-1111-111111111111"
P2   = "22222222-2222-2222-2222-222222222222"
P3   = "33333333-3333-3333-3333-333333333333"
P4   = "44444444-4444-4444-4444-444444444444"
P5   = "55555555-5555-5555-5555-555555555555"
P6   = "66666666-6666-6666-6666-666666666666"
DASH = "77777777-7777-7777-7777-777777777777"

CREDS = base64.b64encode(f"{USER}:{PASS}".encode()).decode()

def post(path, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={
            "kbn-xsrf": "true",
            "Content-Type": "application/json",
            "Authorization": f"Basic {CREDS}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)

# ── helpers ──────────────────────────────────────────────────────────────────

def dv_ref(name="kibanaSavedObjectMeta.searchSourceJSON.index"):
    return [{"name": name, "type": "index-pattern", "id": DV_ID}]

def search_source(query="", extra=None):
    d = {
        "query": {"query": query, "language": "kuery"},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    }
    if extra:
        d.update(extra)
    return json.dumps(d)

def make_vis(vid, title, vis_type, aggs, params, query=""):
    return {
        "type": "visualization",
        "id": vid,
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": vis_type,
                "aggs": aggs,
                "params": params,
            }),
            "uiStateJSON": "{}",
            "description": "",
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)},
        },
        "references": dv_ref(),
    }

def make_search(sid, title, query, columns, sort):
    return {
        "type": "search",
        "id": sid,
        "attributes": {
            "title": title,
            "description": "",
            "hits": 0,
            "columns": columns,
            "sort": sort,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)},
        },
        "references": dv_ref(),
    }

# ── common agg fragments ──────────────────────────────────────────────────────

COUNT = {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}

DATE_HIST = {
    "id": "2", "enabled": True, "type": "date_histogram",
    "params": {
        "field": "@timestamp",
        "useNormalizedEsInterval": True,
        "scaleMetricValues": False,
        "interval": "auto",
        "drop_partials": False,
        "min_doc_count": 1,
        "extended_bounds": {},
    },
    "schema": "segment",
}

def terms_agg(agg_id, field, size=10, schema="group"):
    return {
        "id": str(agg_id), "enabled": True, "type": "terms",
        "params": {
            "field": field, "orderBy": "1", "order": "desc",
            "size": size, "otherBucket": False, "otherBucketLabel": "Other",
            "missingBucket": False, "missingBucketLabel": "Missing",
        },
        "schema": schema,
    }

# ── axis / series params ──────────────────────────────────────────────────────

def xy_params(series_type):
    return {
        "type": series_type,
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear"},
            "labels": {"show": True, "filter": True, "truncate": 100}, "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value",
            "position": "left", "show": True, "style": {},
            "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": "Count"},
        }],
        "seriesParams": [{
            "show": True, "type": series_type, "mode": "normal",
            "data": {"label": "Count", "id": "1"},
            "valueAxis": "ValueAxis-1",
            "drawLinesBetweenPoints": True, "lineWidth": 2,
            "interpolate": "linear", "showCircles": True,
        }],
        "addTooltip": True, "addLegend": True, "legendPosition": "right",
        "times": [], "addTimeMarker": False,
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
        "labels": {},
    }

PIE_PARAMS = {
    "type": "pie", "addTooltip": True, "addLegend": True,
    "legendPosition": "right", "isDonut": False,
    "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
}

# ── build objects ─────────────────────────────────────────────────────────────

# Panel 1 — Error Volume Over Time (line, split by service)
p1 = make_vis(P1, "Error Volume Over Time", "line",
    [COUNT, DATE_HIST, terms_agg(3, "name.keyword", schema="group")],
    xy_params("line"),
    'levelname: "ERROR"',
)

# Panel 2 — Auth Failure Rate (bar)
p2 = make_vis(P2, "Auth Failure Rate", "histogram",
    [COUNT, DATE_HIST],
    xy_params("histogram"),
    'name: "auth-service" AND (message: *invalid* OR message: *failed* OR message: *401*)',
)

# Panel 3 — Vote Submission Rate (line)
p3 = make_vis(P3, "Vote Submission Rate", "line",
    [COUNT, DATE_HIST],
    xy_params("line"),
    'name: "voting-service" AND message: *vote*',
)

# Panel 4 — Email Failures (saved search / data table)
p4 = make_search(P4, "Email Failures",
    'name: "admin-service" AND levelname: "ERROR"',
    ["@timestamp", "message", "kubernetes.pod_name"],
    [["@timestamp", "desc"]],
)

# Panel 5 — Top Error Messages (pie, top 10 by message.keyword)
p5 = make_vis(P5, "Top Error Messages", "pie",
    [COUNT, terms_agg(2, "message.keyword", size=10, schema="segment")],
    PIE_PARAMS,
    'levelname: "ERROR"',
)

# Panel 6 — Live Log Stream (saved search, all services, 50 rows)
p6 = make_search(P6, "Live Log Stream",
    "",
    ["@timestamp", "name", "levelname", "message", "kubernetes.pod_name"],
    [["@timestamp", "desc"]],
)

# ── dashboard ─────────────────────────────────────────────────────────────────

panels_json = [
    {"version": "8.5.1", "type": "visualization", "panelIndex": "1",
     "gridData": {"x": 0,  "y": 0,  "w": 24, "h": 15, "i": "1"},
     "embeddableConfig": {"enhancements": {}}, "panelRefName": "panel_1"},
    {"version": "8.5.1", "type": "visualization", "panelIndex": "2",
     "gridData": {"x": 24, "y": 0,  "w": 24, "h": 15, "i": "2"},
     "embeddableConfig": {"enhancements": {}}, "panelRefName": "panel_2"},
    {"version": "8.5.1", "type": "visualization", "panelIndex": "3",
     "gridData": {"x": 0,  "y": 15, "w": 24, "h": 15, "i": "3"},
     "embeddableConfig": {"enhancements": {}}, "panelRefName": "panel_3"},
    {"version": "8.5.1", "type": "search",        "panelIndex": "4",
     "gridData": {"x": 24, "y": 15, "w": 24, "h": 15, "i": "4"},
     "embeddableConfig": {"enhancements": {}}, "panelRefName": "panel_4"},
    {"version": "8.5.1", "type": "visualization", "panelIndex": "5",
     "gridData": {"x": 0,  "y": 30, "w": 24, "h": 15, "i": "5"},
     "embeddableConfig": {"enhancements": {}}, "panelRefName": "panel_5"},
    {"version": "8.5.1", "type": "search",        "panelIndex": "6",
     "gridData": {"x": 24, "y": 30, "w": 24, "h": 15, "i": "6"},
     "embeddableConfig": {"enhancements": {}}, "panelRefName": "panel_6"},
]

dash = {
    "type": "dashboard",
    "id": DASH,
    "attributes": {
        "title": "UVote Platform Logs",
        "description": "U-Vote platform log analysis dashboard",
        "panelsJSON": json.dumps(panels_json),
        "optionsJSON": json.dumps({
            "useMargins": True, "syncColors": False, "hidePanelTitles": False,
        }),
        "version": 1,
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"}, "filter": [],
            }),
        },
    },
    "references": [
        {"name": "panel_1", "type": "visualization", "id": P1},
        {"name": "panel_2", "type": "visualization", "id": P2},
        {"name": "panel_3", "type": "visualization", "id": P3},
        {"name": "panel_4", "type": "search",        "id": P4},
        {"name": "panel_5", "type": "visualization", "id": P5},
        {"name": "panel_6", "type": "search",        "id": P6},
    ],
}

# ── POST ──────────────────────────────────────────────────────────────────────

objects = [p1, p2, p3, p4, p5, p6, dash]
status, result = post("/api/saved_objects/_bulk_create?overwrite=true", objects)

print(f"HTTP {status}")
if status not in (200, 201):
    print("FATAL:", json.dumps(result, indent=2))
    sys.exit(1)

all_ok = True
for obj in result.get("saved_objects", []):
    err = obj.get("error")
    title = obj.get("attributes", {}).get("title", obj.get("id"))
    if err:
        print(f"  ERROR  {obj['type']:15s} '{title}': {err}")
        all_ok = False
    else:
        print(f"  OK     {obj['type']:15s} '{title}' -> {obj['id']}")

if all_ok:
    print(f"\nDashboard URL: http://localhost:5601/app/dashboards#/view/{DASH}")
else:
    sys.exit(1)
