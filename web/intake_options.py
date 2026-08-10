"""Option sets for the lead-intake form.

Single source of truth shared by the route (for rendering + server-side
validation) and the template. Keep labels here in sync with anything that
reads the stored `lead_*` columns downstream.
"""

ROLES = [
    "Owner",
    "Brand Manager",
    "Account Manager/Operator",
    "Agency",
]

CATEGORIES = [
    "Beauty & Personal Care",
    "Health & Wellness (including supplements)",
    "Grocery & Food",
    "Home & Kitchen",
    "Home & Garden",
    "Sports & Outdoors",
    "Office & Business Products",
    "Electronics",
    "Tools & Home Improvement",
    "Automotive",
    "Pet Supplies",
    "Baby",
    "Clothing / Apparel / Fashion",
    "Books / Media",
    "Toys & Games",
    "Arts / Crafts / Sewing",
    "Tactical / Outdoor Gear",
    "Other",
]

MARKETPLACES = [
    "US",
    "Canada",
    "Mexico",
    "UK",
    "Germany",
    "France",
    "Italy",
    "Spain",
    "Netherlands",
    "Sweden",
    "Poland",
    "Belgium",
    "Japan",
    "Australia",
    "India",
    "UAE",
    "Saudi Arabia",
    "Egypt",
    "Brazil",
    "Singapore",
    "South Africa",
    "Turkey",
    "Other",
]

REVENUE_BANDS = [
    "0 - $300k",
    "$300k - $1M",
    "$1M - $5M",
    "$5M - $10M",
    "$10M - $25M",
    "$25M +",
    "Not applicable",
]
