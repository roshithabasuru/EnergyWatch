import requests
import re

s = requests.Session()
r_login = s.post('http://127.0.0.1:5000/auth/login', data={'email': 'operator@energywatch.com', 'password': 'Operator123!'})
print("Login Status:", r_login.status_code)

r = s.get('http://127.0.0.1:5000/demand_response/operator/new')
print("GET Status:", r.status_code)

match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', r.text)
csrf = match.group(1) if match else ''

data = {
    'csrf_token': csrf,
    'zone_id': '1',
    'target_reduction': '10',
    'incentive': '5',
    'event_date': '2026-05-01',
    'start_time': '10:00',
    'end_time': '12:00'
}

r_post = s.post('http://127.0.0.1:5000/demand_response/operator/new', data=data)
print("POST Status:", r_post.status_code)

if 'Error creating event' in r_post.text:
    match2 = re.search(r'Error creating event: ([^\<]+)', r_post.text)
    if match2:
        print('Error found:', match2.group(1))
    else:
        print('Some error found, could not parse.')
elif 'Demand Response Event successfully created' in r_post.text:
    print('Event created successfully via POST!')
else:
    print('No flash message found. Check validation.')
    if 'is-invalid' in r_post.text:
        print('Form validation failed.')
