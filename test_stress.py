import os
import requests

# Obtain a token via POST /api/v1/auth/login, or set PIQ_TEST_TOKEN in your environment.
# Never hardcode JWTs in source control.
token = os.getenv('PIQ_TEST_TOKEN')
if not token:
    email = os.getenv('PIQ_TEST_EMAIL', 'test@example.com')
    password = os.getenv('PIQ_TEST_PASSWORD', '')
    if not password:
        raise SystemExit('Set PIQ_TEST_TOKEN or PIQ_TEST_EMAIL + PIQ_TEST_PASSWORD to run this script.')
    login = requests.post('http://localhost:8000/api/v1/auth/login', json={'email': email, 'password': password})
    login.raise_for_status()
    token = login.json()['data']['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Create portfolio
pf = requests.post('http://localhost:8000/api/v1/portfolios', 
    json={'name': 'Test Portfolio', 'description': 'Test', 'benchmark': 'SP500', 'base_currency': 'USD'},
    headers=headers)
print('Portfolio:', pf.status_code, pf.json())

pid = pf.json()['data']['id']
print('Portfolio ID:', pid)

# Add holdings
holdings = [
    {'ticker': 'AAPL', 'quantity': 10, 'average_cost': 150, 'currency': 'USD'},
    {'ticker': 'MSFT', 'quantity': 5, 'average_cost': 300, 'currency': 'USD'},
    {'ticker': 'GOOGL', 'quantity': 3, 'average_cost': 2500, 'currency': 'USD'},
]

for h in holdings:
    h_resp = requests.post(f'http://localhost:8000/api/v1/portfolios/{pid}/holdings', json=h, headers=headers)
    print('Add {}:'.format(h['ticker']), h_resp.status_code, h_resp.json())

# Run stress test
st = requests.post('http://localhost:8000/api/v1/portfolios/{}/stress-test'.format(pid),
    json={'scenarios': ['gfc_2008', 'covid_2020']}, headers=headers)
print('Stress Test:', st.status_code)
import json
print(json.dumps(st.json(), indent=2))