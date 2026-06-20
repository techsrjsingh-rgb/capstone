---
tags: [mcp, geo-risk, server, port-8003]
---

# 🌍 Geo Risk MCP Server

Source: `mcp/mcp_server_geo.py` · Port: **8003** · See also: [[../Architecture]], [[Fraud-DB]], [[Orchestrator-MCP]]

---

## Start

```bash
python mcp/mcp_server_geo.py
# → Starting Geo Risk MCP Server on port 8003...
```

---

## Tools (4)

### `get_country_risk_score`

```bash
curl -X POST http://localhost:8003/tools/get_country_risk_score \
  -H "Content-Type: application/json" \
  -d '{"location": "Lagos, Nigeria"}'
```

Returns: `{location, matched_country, risk_score, risk_tier, is_international, recommendation}`

| Tier | Score Range |
|------|-------------|
| low | 15–25 |
| medium | 35–50 |
| high | 70–85 |
| critical | 90–95 |

---

### `check_ip_location`

```bash
curl -X POST http://localhost:8003/tools/check_ip_location \
  -H "Content-Type: application/json" \
  -d '{"ip_address": "41.0.0.1"}'
```

Returns: `{ip_address, country, city, risk}` — simulated IP-to-location mapping.

---

### `get_high_risk_regions`

```bash
curl -X POST http://localhost:8003/tools/get_high_risk_regions \
  -H "Content-Type: application/json" -d '{}'
```

Returns all regions classified as `high` or `critical`: Nigeria (85), Ghana (70), Cayman Islands (80), Panama (75), Unknown (95), Anonymous (95), Offshore (90).

---

### `verify_domestic_location`

```bash
curl -X POST http://localhost:8003/tools/verify_domestic_location \
  -H "Content-Type: application/json" \
  -d '{"location": "Mumbai, India"}'
```

Returns: `{location, is_domestic, country}` — checks for 17 Indian city/country keywords.

---

## Registration (`.mcp.json`)

```json
"geo-risk": {
  "command": "python",
  "args": ["mcp/mcp_server_geo.py"],
  "description": "Geolocation and country risk data"
}
```
