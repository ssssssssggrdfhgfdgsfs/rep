import requests
import json
import time
import random
import string
from colorama import init, Fore, Style

init(autoreset=True)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

ROSOLVE_API_KEY = config['rosolve_api_key']
WEBHOOK_URL = config['discord_webhook']
PROXY_FILE = config['proxy_file']
DELAY = config['delay_between_accounts']

# Try to use curl_cffi for better impersonation, fallback to requests
try:
    from curl_cffi import requests as curl_requests
    USE_CURL = True
    print(f"{Fore.GREEN}[+] Using curl_cffi for requests")
except ImportError:
    USE_CURL = False
    print(f"{Fore.YELLOW}[!] curl_cffi not available, using standard requests")

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

def get_session():
    """Create a session with optional impersonation and proxy"""
    if USE_CURL:
        # Try multiple impersonate options – the library may support 'chrome110' or just 'chrome'
        try:
            session = curl_requests.Session(impersonate="chrome110")
        except:
            try:
                session = curl_requests.Session(impersonate="chrome")
            except:
                session = curl_requests.Session()
    else:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    return session

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
    
    resp = requests.post("https://api.rosolve.com/createTask", json=payload)
    result = resp.json()
    if 'taskId' not in result:
        raise Exception(f"Failed to create task: {result}")
    task_id = result['taskId']
    
    for _ in range(30):
        time.sleep(2)
        poll = requests.post("https://api.rosolve.com/getTaskResult", json={"apiKey": ROSOLVE_API_KEY, "taskId": task_id})
        data = poll.json()
        if data.get('status') == 'ready':
            return data['solution']['token']
    raise Exception("CAPTCHA solving timeout")

def create_account():
    username = generate_username()
    password = generate_password()
    
    # Choose random proxy if available
    proxy_dict = None
    if proxies:
        proxy = random.choice(proxies)
        proxy_dict = {"http": proxy, "https": proxy}
    
    session = get_session()
    if proxy_dict:
        session.proxies = proxy_dict
    
    try:
        print(f"{Fore.CYAN}[*] Trying: {username}")
        
        # Step 1: Get XSRF token
        resp = session.get("https://auth.roblox.com/v2/signup")
        xsrf_token = resp.headers.get('x-csrf-token')
        if not xsrf_token:
            raise Exception("No XSRF token")
        
        # Step 2: Validate username
        check_url = f"https://auth.roblox.com/v2/usernames/validate?request.username={username}&request.birthday=2000-01-01&request.context=Signup"
        resp = session.get(check_url)
        if resp.status_code != 200:
            raise Exception("Username validation failed")
        
        # Step 3: Signup with CAPTCHA
        site_key = "476068BF-9607-4799-B53D-966BE98E2B81"
        print(f"{Fore.CYAN}[*] Solving CAPTCHA...")
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
            cookie = None
            if hasattr(session, 'cookies'):
                for c in session.cookies:
                    if c.name == '.ROBLOSECURITY':
                        cookie = c.value
                        break
            if not cookie and hasattr(resp, 'cookies'):
                cookie = resp.cookies.get('.ROBLOSECURITY')
            
            if cookie:
                print(f"{Fore.GREEN}[SUCCESS] {username} | {password}")
                send_to_discord(username, password, cookie)
                return True
            else:
                raise Exception("No cookie received")
        else:
            error_text = resp.text
            try:
                error_json = resp.json()
                error_text = error_json.get('errors', [{}])[0].get('message', str(error_json))
            except:
                pass
            raise Exception(f"Signup failed: {error_text}")
        
    except Exception as e:
        print(f"{Fore.RED}[FAIL] {username}: {str(e)}")
        return False

def send_to_discord(username, password, cookie):
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
        print(f"{Fore.GREEN}[+] Webhook sent")
    except Exception as e:
        print(f"{Fore.RED}[!] Webhook error: {e}")

def main():
    print(f"{Fore.CYAN}{'='*50}")
    print(f"{Fore.GREEN}Roblox Account Generator - Fixed Version")
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
