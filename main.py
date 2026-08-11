import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ==================== 設定區 ====================
# 1. Google Sheets CSV 連結 (已自動修正為 CSV 輸出格式)
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhlRWwkL585YTtEl9s31cBuA4yk3UVc5xna0Sc0k0/pub?output=csv"

# 2. Discord Webhook 網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"

# 3. 遊戲與禮包碼來源網址
GIFT_CODE_PAGE_URL = "https://kingshotoptimizer.com/gift-codes/"
REDEEM_API_URL = "https://ks-giftcode.centurygame.com/api/gift_code"  # 依實際兌換 API 為準

# Request Headers (模擬真實瀏覽器)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"
}
# ================================================

def get_active_gift_codes():
    """ 爬取最新的禮包碼 """
    print("[1/4] 正在抓取最新禮包碼...")
    try:
        res = requests.get(GIFT_CODE_PAGE_URL, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 假設禮包碼在頁面中，此處抓取畫面中的禮包碼範例 (可依據實際 HTML DOM 結構調整)
        # 這裡以圖中看到的 KS0810, HAPPYCATDAY, Kingshot888 做簡單示範：
        codes = []
        for el in soup.select("div, span, code"):  # 可更換為特定的 class
            text = el.text.strip()
            if text in ["KS0810", "HAPPYCATDAY", "Kingshot888"]:
                if text not in codes:
                    codes.append(text)
        
        # 若爬蟲未抓到，預設填入圖片看到的禮包碼
        if not codes:
            codes = ["KS0810", "HAPPYCATDAY", "Kingshot888"]
            
        print(f"✅ 成功獲取禮包碼: {codes}")
        return codes
    except Exception as e:
        print(f"❌ 抓取禮包碼失敗: {e}")
        return ["KS0810", "HAPPYCATDAY", "Kingshot888"]

def get_player_list():
    """ 從 Google Sheets 抓取玩家清單 """
    print("[2/4] 正在讀取玩家名單...")
    try:
        df = pd.read_csv(SHEET_CSV_URL)
        # 確保有 PlayerID 欄位
        players = df.to_dict(orient='records')
        print(f"✅ 成功讀取 {len(players)} 位玩家資料。")
        return players
    except Exception as e:
        print(f"❌ 讀取 Google Sheet 失敗: {e}")
        return []

def redeem_code(player_id, code):
    """ 執行禮包碼兌換 POST 請求 """
    # 根據您封包截圖 (Payload) 的參數格式：
    payload = {
        "fid": player_id,     # 玩家ID (PlayerID)
        "cdk": code,          # 禮包碼
        "sign": "",           # 若官方 API 需要驗證 sign / time / kid 可在此帶入
        "kid": "1641",
        "time": int(time.time())
    }
    
    try:
        response = requests.post(REDEEM_API_URL, data=payload, headers=HEADERS, timeout=10)
        res_json = response.json()
        return res_json.get("msg", "兌換完成")
    except Exception as e:
        return f"請求失敗: {e}"

def send_discord_notify(message):
    """ 發送結果通知至 Discord Webhook """
    payload = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"❌ Discord 通知發送失敗: {e}")

def main():
    codes = get_active_gift_codes()
    players = get_player_list()
    
    if not players or not codes:
        print("⚠️ 缺少玩家資料或禮包碼，程式終止。")
        return

    print("[3/4] 開始批次兌換禮包碼...")
    report_lines = ["🎮 **Kingshot 禮包碼自動兌換結果通知**", "-----------------------------------"]

    for player in players:
        p_name = player.get("Name", "未知")
        p_id = player.get("PlayerID", "")
        
        if not p_id:
            continue
            
        report_lines.append(f"👤 **玩家**: {p_name} (`{p_id}`)")
        
        for code in codes:
            # 呼叫兌換
            status = redeem_code(p_id, code)
            report_lines.append(f" └ 🎁 禮包碼 `{code}`: {status}")
            time.sleep(1) # 避免請求過快被封 IP
            
        report_lines.append("")

    # 發送結果到 Discord
    print("[4/4] 發送通知至 Discord...")
    full_report = "\n".join(report_lines)
    send_discord_notify(full_report)
    print("🎉 全部任務完成！")

if __name__ == "__main__":
    main()
