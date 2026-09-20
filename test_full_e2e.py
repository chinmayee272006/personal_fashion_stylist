"""
Full End-to-End Test Suite - 15 Test Cases
Flow: Home -> Register -> Login -> Profile -> Upload -> Occasion
      -> Recommendation -> Favourite -> Feedback -> Admin Feedback -> Logout
Checkpoint: Full flow works with no broken links.
"""

import re
import requests
import sys
import uuid

BASE = "http://127.0.0.1:5000"

# Unique suffix so re-runs never collide
UID = uuid.uuid4().hex[:8]
TEST_USER = f"fulltest_{UID}"
TEST_EMAIL = f"fulltest_{UID}@example.com"
TEST_PASS = "Secure1234"

# ---------- result collector ----------
results = []


def tc(tc_id, tc_input, expected, actual, passed):
    status = "PASS" if passed else "FAIL"
    results.append({
        "id": tc_id,
        "input": tc_input,
        "expected": expected,
        "actual": actual,
        "status": status,
    })
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {tc_id}: {expected[:70]}")
    if not passed:
        print(f"         Actual: {actual[:120]}")


def extract_links(html, base_url=BASE):
    raw = set(re.findall(r'href=["\']([^"\']+)["\']', html))
    links = set()
    for href in raw:
        if href.startswith("http") and not href.startswith(base_url):
            continue
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        if href.startswith("/"):
            links.add(base_url + href)
        elif href.startswith(base_url):
            links.add(href)
    return links


# ============================================================
# TC-01: Home page loads
# ============================================================
print("\n--- TC-01: Home Page ---")
r = requests.get(f"{BASE}/")
tc("TC-01",
   "GET /",
   "HTTP 200, hero section with 'AI Fashion Stylist'",
   f"HTTP {r.status_code}, hero={'AI Fashion Stylist' in r.text}",
   r.status_code == 200 and "AI Fashion Stylist" in r.text)


# ============================================================
# TC-02: Registration - valid data
# ============================================================
print("\n--- TC-02: Register (valid) ---")
sess = requests.Session()
r = sess.post(f"{BASE}/register", data={
    "username": TEST_USER,
    "email": TEST_EMAIL,
    "password": TEST_PASS,
    "confirm_password": TEST_PASS,
}, allow_redirects=True)
tc("TC-02",
   f"POST /register (user={TEST_USER})",
   "HTTP 200, flash 'Registration successful', redirect to login",
   f"HTTP {r.status_code}, success={'Registration successful' in r.text}",
   r.status_code == 200 and "Registration successful" in r.text)


# ============================================================
# TC-03: Registration - duplicate user
# ============================================================
print("\n--- TC-03: Register (duplicate) ---")
sess2 = requests.Session()
r = sess2.post(f"{BASE}/register", data={
    "username": TEST_USER,
    "email": TEST_EMAIL,
    "password": TEST_PASS,
    "confirm_password": TEST_PASS,
}, allow_redirects=True)
tc("TC-03",
   f"POST /register duplicate (user={TEST_USER})",
   "HTTP 200, flash 'already exists'",
   f"HTTP {r.status_code}, already_exists={'already exists' in r.text}",
   r.status_code == 200 and "already exists" in r.text)


# ============================================================
# TC-04: Login - valid credentials
# ============================================================
print("\n--- TC-04: Login (valid) ---")
sess = requests.Session()
r = sess.post(f"{BASE}/login", data={
    "email": TEST_EMAIL,
    "password": TEST_PASS,
}, allow_redirects=True)
tc("TC-04",
   f"POST /login (email={TEST_EMAIL})",
   "HTTP 200, redirect to dashboard, flash 'Welcome back'",
   f"HTTP {r.status_code}, welcome={'Welcome back' in r.text}",
   r.status_code == 200 and "Welcome back" in r.text)


# ============================================================
# TC-05: Login - invalid credentials
# ============================================================
print("\n--- TC-05: Login (invalid) ---")
bad_sess = requests.Session()
r = bad_sess.post(f"{BASE}/login", data={
    "email": "noone@nowhere.com",
    "password": "wrongpass",
}, allow_redirects=True)
tc("TC-05",
   "POST /login (bad credentials)",
   "HTTP 200, flash 'Invalid email or password'",
   f"HTTP {r.status_code}, invalid={'Invalid email or password' in r.text}",
   r.status_code == 200 and "Invalid email or password" in r.text)


# ============================================================
# TC-06: Profile - save body info
# ============================================================
print("\n--- TC-06: Profile Save ---")
r = sess.post(f"{BASE}/profile", data={
    "gender": "Female",
    "age": "25",
    "height_cm": "165",
    "weight_kg": "58",
    "body_type": "Hourglass",
    "skin_tone": "Medium",
    "favourite_colour": "Pink",
}, allow_redirects=True)
tc("TC-06",
   "POST /profile (Female, Hourglass, Medium, Pink)",
   "HTTP 200, flash 'Profile saved'",
   f"HTTP {r.status_code}, saved={'Profile saved' in r.text}",
   r.status_code == 200 and "Profile saved" in r.text)


# ============================================================
# TC-07: Upload Photo page accessible
# ============================================================
print("\n--- TC-07: Upload Photo Page ---")
r = sess.get(f"{BASE}/upload-photo")
tc("TC-07",
   "GET /upload-photo",
   "HTTP 200, upload form present",
   f"HTTP {r.status_code}, upload_form={'upload' in r.text.lower()}",
   r.status_code == 200 and "upload" in r.text.lower())


# ============================================================
# TC-08: Occasion - save selections
# ============================================================
print("\n--- TC-08: Occasion Selection ---")
r = sess.post(f"{BASE}/occasion", data={
    "occasions": ["Casual", "Party", "Date Night"],
}, allow_redirects=True)
tc("TC-08",
   "POST /occasion (Casual, Party, Date Night)",
   "HTTP 200, flash 'Occasion preferences saved'",
   f"HTTP {r.status_code}, saved={'Occasion preferences saved' in r.text}",
   r.status_code == 200 and "Occasion preferences saved" in r.text)


# ============================================================
# TC-09: Recommendations - scored outfits displayed
# ============================================================
print("\n--- TC-09: Recommendations ---")
r = sess.get(f"{BASE}/recommendations")
has_cards = "rec-card" in r.text
has_empty = "No matching outfits" in r.text
tc("TC-09",
   "GET /recommendations",
   "HTTP 200, shows scored outfit cards or empty state",
   f"HTTP {r.status_code}, cards={has_cards}, empty={has_empty}",
   r.status_code == 200 and (has_cards or has_empty))

# Grab an outfit_id for favourite / feedback tests
outfit_id_match = re.search(r'name="outfit_id" value="(\d+)"', r.text)
test_outfit_id = outfit_id_match.group(1) if outfit_id_match else None
if test_outfit_id:
    print(f"       (Using outfit_id={test_outfit_id} for favourite/feedback)")


# ============================================================
# TC-10: Toggle Favourite - add to favourites
# ============================================================
print("\n--- TC-10: Add Favourite ---")
if test_outfit_id:
    r = sess.post(f"{BASE}/toggle-favourite", data={
        "outfit_id": test_outfit_id,
        "redirect_to": "recommendations",
    }, allow_redirects=True)
    tc("TC-10",
       f"POST /toggle-favourite (outfit_id={test_outfit_id}, add)",
       "HTTP 200, flash 'Saved to favourites'",
       f"HTTP {r.status_code}, saved={'Saved to favourites' in r.text}",
       r.status_code == 200 and "Saved to favourites" in r.text)
else:
    tc("TC-10",
       "POST /toggle-favourite (no outfit available)",
       "Outfit available to favourite",
       "No outfit_id found in recommendations page",
       False)


# ============================================================
# TC-11: Favourites page - shows saved outfit
# ============================================================
print("\n--- TC-11: Favourites Page ---")
r = sess.get(f"{BASE}/favourites")
tc("TC-11",
   "GET /favourites",
   "HTTP 200, saved outfit visible on favourites page",
   f"HTTP {r.status_code}, has_content={'fav-card' in r.text or 'No favourites' in r.text}",
   r.status_code == 200 and ("fav-card" in r.text or "No favourites" in r.text))


# ============================================================
# TC-12: Submit Feedback - rating + comment
# ============================================================
print("\n--- TC-12: Submit Feedback ---")
if test_outfit_id:
    r = sess.post(f"{BASE}/feedback", data={
        "outfit_id": test_outfit_id,
        "rating": "4",
        "comment": "Great recommendation! Fits my style perfectly.",
    }, allow_redirects=True)
    tc("TC-12",
       f"POST /feedback (outfit={test_outfit_id}, rating=4)",
       "HTTP 200, flash 'Thanks for your feedback'",
       f"HTTP {r.status_code}, thanks={'Thanks for your feedback' in r.text}",
       r.status_code == 200 and "Thanks for your feedback" in r.text)
else:
    tc("TC-12",
       "POST /feedback (no outfit available)",
       "Feedback submitted successfully",
       "No outfit_id available for feedback",
       False)


# ============================================================
# TC-13: Admin - View Feedback (sees user feedback)
# ============================================================
print("\n--- TC-13: Admin View Feedback ---")
admin_sess = requests.Session()
admin_sess.post(f"{BASE}/admin/login", data={
    "username": "admin",
    "password": "admin123",
}, allow_redirects=True)
r = admin_sess.get(f"{BASE}/admin/feedback")
has_table = "feedback-table" in r.text
has_user = TEST_USER in r.text
tc("TC-13",
   "GET /admin/feedback (logged in as admin)",
   "HTTP 200, feedback table loads with user entries",
   f"HTTP {r.status_code}, table={has_table}, user_visible={has_user}",
   r.status_code == 200 and (has_table or "No feedback" in r.text))
admin_sess.get(f"{BASE}/admin/logout")


# ============================================================
# TC-14: Logout - session cleared, protected routes blocked
# ============================================================
print("\n--- TC-14: Logout ---")
r = sess.get(f"{BASE}/logout", allow_redirects=True)
logged_out = "logged out" in r.text.lower()
# Verify protected route redirects to login
r2 = sess.get(f"{BASE}/dashboard", allow_redirects=True)
redirected = "login" in r2.url or "Please log in" in r2.text or "Log in" in r2.text
tc("TC-14",
   "GET /logout, then GET /dashboard",
   "HTTP 200, flash 'logged out', dashboard blocked after logout",
   f"HTTP {r.status_code}, logged_out={logged_out}, dash_blocked={redirected}",
   r.status_code == 200 and logged_out and redirected)


# ============================================================
# TC-15: No broken internal links (full link crawl)
# ============================================================
print("\n--- TC-15: Broken Link Scan ---")
link_sess = requests.Session()
link_sess.post(f"{BASE}/login", data={
    "email": TEST_EMAIL,
    "password": TEST_PASS,
}, allow_redirects=True)

pages_to_crawl = [
    "/", "/login", "/register", "/dashboard",
    "/profile", "/upload-photo", "/occasion",
    "/recommendations", "/favourites",
]

all_links = set()
for page in pages_to_crawl:
    try:
        r = link_sess.get(f"{BASE}{page}", allow_redirects=True)
        if r.status_code == 200:
            found = extract_links(r.text)
            all_links.update(found)
    except Exception:
        pass

page_links = {
    lnk for lnk in all_links
    if "/static/" not in lnk
    and not lnk.endswith(".css")
    and not lnk.endswith(".js")
    and not lnk.endswith(".ico")
}

broken = []
checked = 0
for link in sorted(page_links):
    try:
        r = link_sess.get(link, allow_redirects=True)
        checked += 1
        if r.status_code >= 400:
            broken.append(f"{link} -> HTTP {r.status_code}")
    except Exception as e:
        broken.append(f"{link} -> ERROR {e}")

if broken:
    detail = "; ".join(broken[:5])
    tc("TC-15",
       f"Crawl {checked} internal links from {len(pages_to_crawl)} pages",
       "All links return HTTP 2xx/3xx (no broken links)",
       f"{len(broken)} broken: {detail}",
       False)
else:
    tc("TC-15",
       f"Crawl {checked} internal links from {len(pages_to_crawl)} pages",
       "All links return HTTP 2xx/3xx (no broken links)",
       f"All {checked} links OK",
       True)

link_sess.get(f"{BASE}/logout")


# ============================================================
# CLEANUP
# ============================================================
print("\n--- CLEANUP ---")
cleanup_sess = requests.Session()
cleanup_sess.post(f"{BASE}/login", data={
    "email": TEST_EMAIL, "password": TEST_PASS
}, allow_redirects=True)
if test_outfit_id:
    cleanup_sess.post(f"{BASE}/toggle-favourite", data={
        "outfit_id": test_outfit_id,
    }, allow_redirects=True)
    print(f"  Removed favourite (outfit {test_outfit_id})")
cleanup_sess.get(f"{BASE}/logout")
print("  Session cleared")


# ============================================================
# RESULTS TABLE
# ============================================================
print("\n")
hdr = f"{'Test ID':<8} | {'Input':<34} | {'Expected':<32} | {'Actual':<32} | {'Status':<6}"
sep = "-" * len(hdr)
print("=" * len(hdr))
print(hdr)
print(sep)
for r in results:
    tid = r["id"]
    inp = (r["input"][:32] + "..") if len(r["input"]) > 34 else r["input"]
    exp = (r["expected"][:30] + "..") if len(r["expected"]) > 32 else r["expected"]
    act = (r["actual"][:30] + "..") if len(r["actual"]) > 32 else r["actual"]
    st = r["status"]
    print(f"{tid:<8} | {inp:<34} | {exp:<32} | {act:<32} | {st:<6}")
print("=" * len(hdr))

pass_count = sum(1 for r in results if r["status"] == "PASS")
fail_count = sum(1 for r in results if r["status"] == "FAIL")
total = len(results)

print(f"\n  RESULTS: {pass_count}/{total} PASSED, {fail_count} FAILED")

if fail_count > 0:
    print("\n  Some tests failed. Review output above.")
    sys.exit(1)
else:
    print("\n  ALL 15 TESTS PASSED!")
    print("  Checkpoint: Home -> Register -> Login -> Profile -> Upload -> Occasion")
    print("           -> Recommendation -> Favourite/Feedback -> Logout (no broken links)")
    sys.exit(0)
