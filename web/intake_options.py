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

COUNTRIES = [
    "United States", "Canada", "Mexico", "United Kingdom", "Germany", "France",
    "Italy", "Spain", "Netherlands", "Sweden", "Poland", "Belgium", "Ireland",
    "Portugal", "Austria", "Switzerland", "Denmark", "Norway", "Finland",
    "Japan", "Australia", "New Zealand", "India", "Singapore", "United Arab Emirates",
    "Saudi Arabia", "Egypt", "Brazil", "South Africa", "Turkey", "China",
    "Hong Kong", "South Korea", "Taiwan", "Israel", "Argentina", "Chile",
    "Colombia", "Czech Republic", "Greece", "Hungary", "Indonesia", "Malaysia",
    "Nigeria", "Pakistan", "Philippines", "Romania", "Russia", "Thailand",
    "Ukraine", "Vietnam",
    "Afghanistan", "Albania", "Algeria", "Angola", "Armenia", "Azerbaijan",
    "Bahrain", "Bangladesh", "Belarus", "Bolivia", "Bosnia and Herzegovina",
    "Bulgaria", "Cambodia", "Cameroon", "Costa Rica", "Croatia", "Cyprus",
    "Dominican Republic", "Ecuador", "El Salvador", "Estonia", "Ethiopia",
    "Georgia", "Ghana", "Guatemala", "Honduras", "Iceland", "Iraq", "Jamaica",
    "Jordan", "Kazakhstan", "Kenya", "Kuwait", "Latvia", "Lebanon", "Lithuania",
    "Luxembourg", "Malta", "Mauritius", "Moldova", "Montenegro", "Morocco",
    "Nepal", "Oman", "Panama", "Paraguay", "Peru", "Qatar", "Rwanda", "Senegal",
    "Serbia", "Slovakia", "Slovenia", "Sri Lanka", "Tanzania", "Tunisia",
    "Uganda", "Uruguay", "Uzbekistan", "Venezuela", "Zambia", "Zimbabwe",
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
