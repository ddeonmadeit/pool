"""Shared configuration for the Sydney pool-lead pipeline."""

# Overpass mirrors, tried in order. The main overpass-api.de instance is
# frequently rate-limited/blocked; mirrors are more reliable for bulk work.
OVERPASS_MIRRORS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

# Greater Sydney bounding box (south, west, north, east).
SYDNEY_BBOX = (-34.20, 150.50, -33.55, 151.35)

# Grid step in degrees for chunking Overpass queries. Smaller = more requests
# but each one is far less likely to time out in dense suburbs.
GRID_STEP = 0.06

# NSW Spatial Services endpoints (public, no key required).
NSW_ADDRESS_LAYER = (
    "https://portal.spatial.nsw.gov.au/server/rest/services"
    "/NSW_Geocoded_Addressing_Theme/MapServer/1/query"
)
NSW_LOT_LAYER = (
    "https://portal.spatial.nsw.gov.au/server/rest/services"
    "/NSW_Land_Parcel_Property_Theme/MapServer"
)

# Historical aerial imagery tile services. A pool visible in one of these
# is at least (current year - imagery year) old. Verified available years.
HISTORICAL_IMAGERY = {
    2005: "https://portal.spatial.nsw.gov.au/tileservices/Hosted/HistoricalImagery2005/MapServer",
    1998: "https://portal.spatial.nsw.gov.au/tileservices/Hosted/HistoricalImagery1998/MapServer",
    1991: "https://portal.spatial.nsw.gov.au/tileservices/Hosted/HistoricalImagery1991/MapServer",
    1986: "https://portal.spatial.nsw.gov.au/tileservices/Hosted/HistoricalImagery1986/MapServer",
    1978: "https://portal.spatial.nsw.gov.au/tileservices/Hosted/HistoricalImagery1978/MapServer",
}

# Deepest cached zoom on the historical tile services. z18 is ~0.50 m/px at
# Sydney's latitude, which resolves a domestic pool as a ~16x8 px cyan blob.
IMAGERY_ZOOM = 18

# Age threshold: a pool is a "target" if it existed on/before this year.
# 2005 imagery is the workhorse - anything visible there is 20+ years old.
TARGET_BUILT_BEFORE = 2006

USER_AGENT = "sydney-pool-leads/1.0 (landscaping lead research)"
