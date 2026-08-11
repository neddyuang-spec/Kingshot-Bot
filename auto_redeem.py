import csv
import io
import time
import requests
from bs4 import BeautifulSoup

# ================= 基礎設定 =================
# 1. Google 試算表 CSV 發布連結（來自你的圖片 1）
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhIRWwkL585YTtEl9s31cBuA4yk3UVc5xnaOScOk0/pub?output=csv"

# 2. Discord Webhook 網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"

# 3. 目標網站與 API 網址
OPTIMIZER_URL = "https://kingshotoptimizer.com/gift-codes/"
REDEEM_API_URL = "https://kingshot-giftcode.centurygame.com/api/gift_code"
# ============================================

def get_players():
    """從 Google 試算表 CSV 讀取盟友資料"""
    print("正在讀取盟友資料...")
    res = requests.get(SHEET_CSV_URL)
    res.raise_for_status()
    
    # 避免 UTF-8 BOM 開頭導致標頭讀取異常
    csv_text = res.content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(csv_text))
    
    players = []
    for row in reader:
        # 讀取王國(Kingdom)、玩家名稱(Name)、玩家ID(PlayerID)
        kingdom = row.get("Kingdom", "").strip()
        name = row.get("Name", "").strip()
        player_id = row.get("PlayerID", "").strip()
        
        if player_id:
            players.append({
                "kingdom": kingdom or "1641", # 預設王國
                "name": name,
                "player_id": player_id
            })
    return players

def get_latest_gift_code():
    """爬取 kingshotoptimizer.com 最新的一個禮物碼"""
    print("正在爬取最新禮物碼...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    res = requests.get(OPTIMIZER_URL, headers=headers)
    res.raise_for_status()
    
    soup = BeautifulSoup(res.text, "html.parser")
    
    # 尋找 Active codes 區塊下的卡片內容
    code_elements = soup.find_all(string=True)
    # 使用 BeautifulSoup 或簡單尋找 Copy 按鈕旁的禮物碼文字
    for el in soup.find_all(['div', 'p', 'span']):
        text = el.get_text(strip=True)
        # 匹配常見的禮物碼格式（如 KS0810, HAPPYCATDAY）
        if text and text.isupper() and len(text) >= 4 and len(text) <= 15:
            if "COPY" not in text and "ACTIVE" not in text:
                return text
                
    # 備用爬取方式：直接正則查找常見按鈕附近的標籤
    import re
    matches = re.findall(r'>([A-Z0-9]{4,15})</', res.text)
    for m in matches:
        if m not in ["GIFT", "CODES", "COPY", "ACTIVE", "EXPIRED"]:
            return m
            
    return "KS0810"  # 預設備用碼

def redeem_code(player_id, kingdom, gift_code):
    """呼叫官方 API 幫盟友兌換禮物碼"""
    current_time = int(time.time())
    
    payload = {
        "fid": player_id,
        "kid": kingdom,
        "cdk": gift_code,
        "time": str(current_time),
        "sign": ""  # 若官方有前端簽名驗證，可帶入或補充加密邏輯
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Origin": "https://ks-giftcode.centurygame.com",
        "Referer": "https://ks-giftcode.centurygame.com/",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        res = requests.post(REDEEM_API_URL, data=payload, headers=headers, timeout=10)
        result = res.json()
        
        # 根據回傳 code 判定結果
        msg = result.get("msg", "未知結果")
        err_code = result.get("err_code", result.get("code", -1))
        
        if err_code == 0 or "success" in msg.lower() or "成功" in msg:
            return True, "兌換成功"
        elif "already" in msg.lower() or "已領取" in msg:
            return True, "重複領取 (已兌換過)"
        else:
            return False, f"失敗: {msg}"
            
    except Exception as e:
        return False, f"請求異常: {str(e)}"

def send_discord_webhook(gift_code, results):
    """將兌換結果整理並發送到 Discord Webhook 頻道"""
    print("正在傳送結果給 Discord...")
    
    success_count = sum(1 for r in results if r["status"])
    fail_count = len(results) - success_count
    
    # 建立回報文字列表
    details = []
    for r in results:
        status_icon = "✅" if r["status"] else "❌"
        details.append(f"{status_icon} **{r['name']}** (`{r['player_id']}`) - {r['msg']}")
        
    details_str = "\n".join(details)
    if len(details_str) > 3000:  # 防止超過 Discord 訊息上限
        details_str = details_str[:3000] + "\n...(訊息過長略過)"
        
    embed = {
        "title": "🎁 Kingshot 盟友禮物碼每日自動兌換報告",
        "color": 3066993 if fail_count == 0 else 15158332, # 全成功綠色，有失敗紅色
        "fields": [
            {"name": "最新禮物碼", "value": f"`{gift_code}`", "inline": True},
            {"name": "兌換統計", "value": f"成功: **{success_count}** 人 / 失敗: **{fail_count}** 人", "inline": True},
            {"name": "詳細兌換清單", "value": details_str or "無資料", "inline": False}
        ],
        "footer": {"text": "自動化排程任務 • 每日 20:00 執行"}
    }
    
    payload = {
        "username": "Kingshot 兌換小幫手",
        "embeds": [embed]
    }
    
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def main():
    # 1. 爬取最新禮物碼
    gift_code = get_latest_gift_code()
    print(f"👉 取得最新禮物碼：{gift_code}")
    
    # 2. 讀取 Google 試算表盟友資料
    players = get_players()
    print(f"👉 成功讀取 {len(players)} 位盟友資料")
    
    # 3. 逐一進行兌換
    results = []
    for p in players:
        print(f"正在為 [{p['kingdom']}服] {p['name']} ({p['player_id']}) 兌換...")
        status, msg = redeem_code(p['player_id'], p['kingdom'], gift_code)
        results.append({
            "name": p['name'],
            "player_id": p['player_id'],
            "status": status,
            "msg": msg
        })
        time.sleep(1) # 間隔 1 秒避免請求過於頻繁
        
    # 4. 發送 Discord 報告
    send_discord_webhook(gift_code, results)
    print("🎉 任務執行完畢！")

if __name__ == "__main__":
    main()
