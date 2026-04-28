import requests
import json
import time
import random
import string
from colorama import init, Fore, Style

init(autoreset=True)

with open('config.json', 'r') as f:
    config = json.load(f)

ROSOLVE_API_KEY = config['rosolve_api_key']
WEBHOOK_URL = config['discord_webhook']
DELAY = config['delay_between_accounts']

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_username():
    prefixes = ['Cool', 'Pro', 'Mega', 'Super', 'Ultra', 'Fast', 'Epic', 'King', 'Shadow', 'Blaze']
    return random.choice(prefixes) + random_string(4)

def generate_password():
    return random_string(10) + 'A1!'

def solve_captcha(site_key, page_url):
    payload = {
        "apiKey": ROSOLVE_API_KEY,
        "task": {
            "type": "FunCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websitePublicKey": site_key,
            "data": json.dumps({"blob": ""})
        }
    }
    resp = requests.post("https://api.rosolve.com/createTask", json=payload)
    result = resp.json()
    if 'taskId' not in result:
        raise Exception(f"Task creation failed: {result}")
    task_id = result['taskId']
    for _ in range(30):
        time.sleep(2)
        poll = requests.post("https://api.rosolve.com/getTaskResult", json={"apiKey": ROSOLVE_API_KEY, "taskId": task_id})
        data = poll.json()
        if data.get('status') == 'ready':
            return data['solution']['token']
    raise Exception("CAPTCHA timeout")

def create_account():
    username = generate_username()
    password = generate_password()
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
    
    try:
        print(f"{Fore.CYAN}[*] Trying: {username}")
        resp = session.get("https://auth.roblox.com/v2/signup")
        xsrf_token = resp.headers.get('x-csrf-token')
        if not xsrf_token:
            raise Exception("No XSRF token")
        
        check_url = f"https://auth.roblox.com/v2/usernames/validate?request.username={username}&request.birthday=2000-01-01&request.context=Signup"
        resp = session.get(check_url)
        if resp.status_code != 200:
            raise Exception("Username validation failed")
        
        print(f"{Fore.CYAN}[*] Solving CAPTCHA...")
        site_key = "476068BF-9607-4799-B53D-966BE98E2B81"
        captcha_token = solve_captcha(site_key, "https://www.roblox.com/account/signupredir")
        
        signup_data = {
            "username": username,
            "password": password,
            "birthday": "2000-01-15",
            "isTosAgreementChecked": True,
            "captchaToken": captcha_token,
            "captchaProvider": "PROVIDER_ARKOSE_LABS"
        }
        headers = {"X-CSRF-TOKEN": xsrf_token, "Content-Type": "application/json"}
        resp = session.post("https://auth.roblox.com/v2/signup", json=signup_data, headers=headers)
        
        if resp.status_code == 200:
            cookie = resp.cookies.get('.ROBLOSECURITY')
            if not cookie:
                for c in session.cookies:
                    if c.name == '.ROBLOSECURITY':
                        cookie = c.value
                        break
            if cookie:
                print(f"{Fore.GREEN}[SUCCESS] {username} | {password}")
                embed = {
                    "title": "✅ New Roblox Account",
                    "color": 0x57F287,
                    "fields": [
                        {"name": "Username", "value": username, "inline": True},
                        {"name": "Password", "value": f"||{password}||", "inline": True},
                        {"name": "Cookie", "value": f"||{cookie}||", "inline": False}
                    ]
                }
                requests.post(WEBHOOK_URL, json={"embeds": [embed]})
                print(f"{Fore.GREEN}[+] Webhook sent")
                return True
            else:
                raise Exception("No cookie")
        else:
            raise Exception(f"Signup failed: {resp.text}")
    except Exception as e:
        print(f"{Fore.RED}[FAIL] {username}: {str(e)}")
        return False

def main():
    print(f"{Fore.CYAN}{'='*50}")
    print(f"{Fore.GREEN}Roblox Account Generator - Simple Version")
    print(f"{Fore.CYAN}{'='*50}")
    fails = 0
    while True:
        if create_account():
            fails = 0
        else:
            fails += 1
            if fails > 5:
                print(f"{Fore.YELLOW}Waiting 60s...")
                time.sleep(60)
                fails = 0
        time.sleep(2)

if __name__ == "__main__":
    main()
