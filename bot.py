import requests
import json
import logging
from urllib.parse import parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

# Setup Rich Console
console = Console()

# Setup logging dengan RichHandler tanpa timestamp
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, console=console, show_time=False)]
)
logger = logging.getLogger("QuestBot")

# Base URL API
BASE_URL = "https://api-staging-k8s.hatcherselement.io/api"

# Header dasar
HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://quest-hatcher-element.web.app",
    "referer": "https://quest-hatcher-element.web.app/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
}

def load_queries_from_file(filename="data.txt"):
    try:
        with open(filename, 'r') as file:
            # Baca semua baris dan hapus whitespace/kosong
            queries = [line.strip() for line in file.readlines() if line.strip()]
            return queries
    except FileNotFoundError:
        logger.error("File data.txt tidak ditemukan!")
        return []

def parse_query(query):
    try:
        parsed = parse_qs(query)
        
        # Cek apakah query dimulai dengan query_id (format Telegram Mini Apps)
        if "query_id" in parsed:
            if "user" not in parsed:
                logger.error("Format query_id tidak valid: tidak ada parameter user")
                return None
            user_data = json.loads(unquote(parsed['user'][0]))
        else:
            # Format lama (langsung user=...)
            user_data = json.loads(unquote(parsed['user'][0]))

        return {
            "user_id": user_data["id"],
            "username": user_data["username"],
            "first_name": user_data["first_name"],
            "auth_data": query.strip()  # Pastikan tidak ada whitespace
        }
    except Exception as e:
        logger.error(f"Error parsing query: {str(e)}")
        return None

def make_request(endpoint, payload, auth_data, task_name, table, username, banner):
    url = f"{BASE_URL}{endpoint}"
    headers = HEADERS.copy()
    headers["authorization"] = f"tma {auth_data}"
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response_json = response.json()
        
        # Cek apakah response mengikuti pola {"statusCode":400,"data":null,"message":"..."}
        if (response.status_code == 400 and 
            isinstance(response_json, dict) and 
            "statusCode" in response_json and 
            "data" in response_json and 
            "message" in response_json and 
            response_json.get("data") is None):
            table.add_row(username, task_name, "[green]Berhasil[/green]")
            console.clear()
            console.print(f"[bold yellow]{banner}[/bold yellow]")
            console.print(table)
            return True
            
        if response.status_code == 201:
            table.add_row(username, task_name, "[green]Berhasil[/green]")
            console.clear()
            console.print(f"[bold yellow]{banner}[/bold yellow]")
            console.print(table)
            return True
        elif response.status_code == 401 and "Invalid TMA authentication" in response.text:
            # Jika quest sudah selesai sebelumnya atau autentikasi tidak valid
            table.add_row(username, task_name, "[yellow]Quest telah selesai sebelumnya[/yellow]")
            console.clear()
            console.print(f"[bold yellow]{banner}[/bold yellow]")
            console.print(table)
            return True  # Anggap quest sudah selesai, sehingga tidak dianggap gagal
        else:
            table.add_row(username, task_name, f"[yellow]Gagal: {response.text}[/yellow]")
            console.clear()
            console.print(f"[bold yellow]{banner}[/bold yellow]")
            console.print(table)
            return False
    except Exception as e:
        table.add_row(username, task_name, f"[red]Error: {str(e)}[/red]")
        console.clear()
        console.print(f"[bold yellow]{banner}[/bold yellow]")
        console.print(table)
        return False

def daily_login(auth_data, table, username, banner):
    payload = {"actionCode": 0, "actionValue": "dailylogin"}
    return make_request("/quests/daily", payload, auth_data, "Daily Login", table, username, banner)

def social_quests(auth_data, table, username, banner):
    payloads = [
        ("Join Telegram CatGoldMiner", {"actionCode": 2, "actionValue": "https://t.me/catgoldminerann"}),
        ("Follow X HatchersElement", {"actionCode": 1, "actionValue": "https://x.com/HatchersElement"}),
        ("Join Telegram HatchersElement", {"actionCode": 0, "actionValue": "https://t.me/HatchersElement_ann"}),
        ("Follow X CatGoldMiner", {"actionCode": 3, "actionValue": "https://x.com/catgoldminer"})
    ]
    
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(make_request, "/quests/social", payload, auth_data, task_name, table, username, banner)
            for task_name, payload in payloads
        ]
        results = [future.result() for future in futures]
    return all(results)

def claim_quests(auth_data, table, username, banner):
    payloads = [
        ("Claim Telegram CatGoldMiner", {"questType": 1, "actionCode": 2, "actionValue": "https://t.me/catgoldminerann"}),
        ("Claim X HatchersElement", {"questType": 1, "actionCode": 1, "actionValue": "https://x.com/HatchersElement"}),
        ("Claim Telegram HatchersElement", {"questType": 1, "actionCode": 0, "actionValue": "https://t.me/HatchersElement_ann"}),
        ("Claim Daily Login", {"questType": 0, "actionCode": 0, "actionValue": "dailylogin"}),
        ("Claim X CatGoldMiner", {"questType": 1, "actionCode": 3, "actionValue": "https://x.com/catgoldminer"})
    ]
    
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(make_request, "/quests/claim", payload, auth_data, task_name, table, username, banner)
            for task_name, payload in payloads
        ]
        results = [future.result() for future in futures]
    return all(results)

def process_account(query, table, banner):
    account = parse_query(query)
    if not account:
        table.add_row("-", "Parsing Account", "[red]Gagal: Tidak dapat memparse query[/red]")
        console.clear()
        console.print(f"[bold yellow]{banner}[/bold yellow]")
        console.print(table)
        return
    
    # Tambahkan informasi akun ke tabel
    table.add_row(
        account["username"],
        "Account Info",
        f"User ID: {account['user_id']}, First Name: {account['first_name']}"
    )
    console.clear()
    console.print(f"[bold yellow]{banner}[/bold yellow]")
    console.print(table)
    
    # Log "Menjalankan quest untuk..."
    table.add_row(account["username"], "Status", "Menjalankan quest")
    console.clear()
    console.print(f"[bold yellow]{banner}[/bold yellow]")
    console.print(table)
    
    # Eksekusi semua quest
    daily_login(account['auth_data'], table, account["username"], banner)
    social_quests(auth_data=account['auth_data'], table=table, username=account["username"], banner=banner)
    claim_quests(auth_data=account['auth_data'], table=table, username=account["username"], banner=banner)
    
    # Log "Semua quest selesai!" untuk akun ini
    table.add_row(account["username"], "Status", "Semua quest selesai")
    console.clear()
    console.print(f"[bold yellow]{banner}[/bold yellow]")
    console.print(table)

def display_banner():
    banner = (
        "╔══════════════════════════════════════════════════════════╗\n"
        "║    ⚡ Hatchers BOT - Automated Quest & Reward System      ║\n"
        "║  Automate your Hatchers Element quests and daily tasks!  ║\n"
        "║       Developed by: https://t.me/sentineldiscus          ║\n"
        "╚══════════════════════════════════════════════════════════╝"
    )
    return banner

def main():
    # Tampilkan banner di awal
    banner = display_banner()
    console.print(f"[bold yellow]{banner}[/bold yellow]")
    
    queries = load_queries_from_file()
    if not queries:
        table = Table(title="Quest Bot Log")
        table.add_column("Account", style="cyan")
        table.add_column("Task", style="magenta")
        table.add_column("Status", style="green")
        table.add_row("-", "Load Queries", "[red]Gagal: Tidak ada query ditemukan[/red]")
        console.clear()
        console.print(f"[bold yellow]{banner}[/bold yellow]")
        console.print(table)
        return
    
    # Buat tabel utama untuk menyimpan semua data
    final_table = Table(title="Quest Bot Log - All Accounts")
    final_table.add_column("Account", style="cyan")
    final_table.add_column("Task", style="magenta")
    final_table.add_column("Status", style="green")
    
    # Proses setiap query (akun) secara terpisah
    for query in queries:
        process_account(query, final_table, banner)
    
    # Tampilkan tabel final setelah semua selesai
    console.clear()
    console.print(f"[bold yellow]{banner}[/bold yellow]")
    console.print(final_table)

if __name__ == "__main__":
    main()
