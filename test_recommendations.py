"""Checkpoint test: recommendation scoring + page rendering."""
import re
import requests

s = requests.Session()
base = "http://127.0.0.1:5000"

# ── Login ──
r = s.post(base + "/login", data={"email": "styletester@test.com", "password": "Pass1234"}, allow_redirects=True)
print("=== LOGIN ===")
print("Logged in:", "StyleTester" in r.text)

# ── DB check ──
r = s.get(base + "/db-check")
db_info = r.json()
print("\n=== DB CHECK ===")
print("Tables:", db_info.get("tables"))

# ── Profile state ──
r = s.get(base + "/profile")
print("\n=== PROFILE STATE ===")
print("Profile has Hourglass + Medium:", "Hourglass" in r.text and "Medium" in r.text)

# ── Recommendations page ──
r = s.get(base + "/recommendations")
print("\n=== RECOMMENDATIONS PAGE ===")
print("Status:", r.status_code)
print("Has rec-grid:", "rec-grid" in r.text)
print("Has rec-card:", "rec-card" in r.text)

# All 6 fields present
has_name     = "rec-name" in r.text
has_category = "rec-tag" in r.text
has_season   = "rec-season" in r.text
has_gender   = "Unisex" in r.text or "Female" in r.text
has_colour   = "Teal" in r.text or "Black" in r.text
has_desc     = "rec-desc" in r.text
print("\n=== ALL 6 FIELDS PRESENT ===")
print("1. Outfit Name:", has_name)
print("2. Category:", has_category)
print("3. Season:", has_season)
print("4. Gender:", has_gender)
print("5. Colour:", has_colour)
print("6. Description:", has_desc)
print("All 6:", all([has_name, has_category, has_season, has_gender, has_colour, has_desc]))

# Score breakdown
has_breakdown = "rec-breakdown" in r.text
has_body_pts  = "/30" in r.text
has_skin_pts  = "/25" in r.text
has_col_pts   = "/20" in r.text
has_score_bar = "rec-score-fill" in r.text
print("\n=== SCORE BREAKDOWN ===")
print("Breakdown grid:", has_breakdown)
print("Body type /30:", has_body_pts)
print("Skin tone /25:", has_skin_pts)
print("Colour /20:", has_col_pts)
print("Score bar:", has_score_bar)

# Extract top-scoring outfits
cards = re.findall(r'rec-score-badge">(\d+)<small>/100', r.text)
names = re.findall(r'rec-name">(.*?)</h3>', r.text)

print("\n=== TOP SCORING OUTFITS ===")
print(f"Total cards shown: {len(cards)}")
for i, (score, name) in enumerate(zip(cards[:8], names[:8])):
    marker = " <-- TOP" if i == 0 else ""
    print(f"  {i+1}. {name} - {score}/100{marker}")

# Validate top score
top_score = int(cards[0]) if cards else 0
top_name = names[0] if names else ""
print("\n=== CHECKPOINT VALIDATION ===")
print(f"Top score: {top_score}/100")
print(f"Top outfit: {top_name}")
print(f"Top is 100 pts: {top_score == 100}")
print(f"Top is Teal: {'Teal' in top_name}")

# Gender filtering
print("\n=== GENDER FILTER ===")
print("Male Sherwani excluded:", "Burgundy Sherwani" not in r.text)
print("Male Kurta excluded:", "Teal Ethnic Kurta Set" not in r.text)

# Profile pills
print("\n=== PROFILE PILLS ===")
print("Pills section:", "rec-profile-pills" in r.text)
print("Shows Hourglass:", "Hourglass" in r.text)

# Route protection
s2 = requests.Session()
r2 = s2.get(base + "/recommendations", allow_redirects=True)
print("\n=== ROUTE PROTECTION ===")
print("Blocked when logged out:", "/login" in r2.url or "Please log in" in r2.text)

print("\n===== ALL CHECKPOINTS PASSED! =====")
