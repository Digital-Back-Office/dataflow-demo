# import requests
# import time
# from app.config.settings import BASE_URL, MAX_BILLS


# def fetch_latest_bills():
#     """
#     Fetch latest UK Parliament bills sorted by last update date.
#     Returns a list of bill metadata dictionaries.
#     """

#     all_bills = []
#     page = 1
#     page_size = 50

#     while len(all_bills) < MAX_BILLS:

#         url = f"{BASE_URL}/Bills"
#         params = {
#             "SortOrder": "DateUpdatedDescending",
#             "Page": page,
#             "Take": page_size
#         }

#         print(f"[Ingestion] Fetching page {page}")

#         response = requests.get(url, params=params, timeout=20)
#         response.raise_for_status()

#         items = response.json().get("items", [])
#         if not items:
#             break

#         all_bills.extend(items)
#         page += 1
#         time.sleep(0.2)

#     selected = all_bills[:MAX_BILLS]
#     print(f"[Ingestion] Collected {len(selected)} bills")

#     return selected