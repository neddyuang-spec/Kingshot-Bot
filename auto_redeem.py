import csv
import io
import time
import requests
from bs4 import BeautifulSoup

# ================= 基礎設定 =================
# 請將這裡替換為你重新從 Google Sheet 複製的完整 CSV 連結
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhIRWwkL585YTtEl9s31cBuA4yk3UVc5xnaOScOk0/pub?output=csv"

# Discord Webhook 網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"

OPTIMIZER_URL = "https://kingshotoptimizer.com/gift-codes/"
REDEEM_API_URL = "https://kingshot-giftcode.centurygame.com/api/gift_code"
# ============================================

def get_players():
    """從 Google 試算表 CSV 讀取盟友資料"""
    print("正在讀取盟友資料...")
    
    # 加上 User-Agent 避免 Google 伺服器拒絕 GitHub Actions 機器人請求
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(SHEET_CSV_URL, headers=headers, timeout=15)
        res.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(f"❌ 讀取 CSV 失敗，請確認 Google 試算表是否已『發布到網路』且網址無誤。錯誤訊息: {err}")
        raise err

    # 避免 UTF-8 BOM 開頭問題
    csv_text = res.content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(csv_text))
    
    players = []
    for row in reader:
        kingdom = row.get("Kingdom", "").strip()
        name = row.get("Name", "").strip()
        player_id = row.get("PlayerID", "").strip()
        
        if player_id:
            players.append({
                "kingdom": kingdom or "1641",
                "name": name,
                "player_id": player_id
            })
    return players

def get_latest_gift_code():
    """爬取 kingshotoptimizer.com 最新禮物碼"""
    print("正在爬取最新禮物碼...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(OPTIMIZER_URL, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        import re
        # 排除非禮物碼關鍵字
        exclude = ["GIFT", "CODES", "COPY", "ACTIVE", "EXPIRED", "OPTIMIZER", "HOME", "GUIDES"]
        matches = re.findall(r'>([A-Z0-9]{4,15})</', res.text)
        for m in matches:
            if m.isupper() and m not in exclude:
                return m
    except Exception as e:
        print(f"⚠️ 爬取禮物碼失敗，使用備用禮物碼: {e}")
        
    return "KS0810"

def redeem_code(player_id, kingdom, gift_code):
    """呼叫官方 API 幫盟友兌換禮物碼"""
    current_time = int(time.time())
    
    payload = {
        "fid": player_id,
        "kid": kingdom,
        "cdk": gift_code,
        "time": str(current_time),
        "sign": ""
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
    """將結果發送到 Discord Webhook 頻道"""
    print("正在傳送結果給 Discord...")
    
    success_count = sum(1 for r in results if r["status"])
    fail_count = len(results) - success_count
    
    details = []
    for r in results:
        status_icon = "✅" if r["status"] else "❌"
        details.append(f"{status_icon} **{r['name']}** (`{r['player_id']}`) - {r['msg']}")
        
    details_str = "\n".join(details)
    if len(details_str) > 3000:
        details_str = details_str[:3000] + "\n...(訊息過長略過)"
        
    embed = {
        "title": "🎁 Kingshot 盟友禮物碼每日自動兌換報告",
        "color": 3066993 if fail_count == 0 else 15158332,
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
    # 1. 讀取 Google 試算表盟友資料 (先讀取試算表，避免試算表壞掉還執行無意義爬蟲)
    players = get_players()
    print(f"👉 成功讀取 {len(players)} 位盟友資料")

    # 2. 爬取最新禮物碼
    gift_code = get_latest_gift_code()
    print(f"👉 取得最新禮物碼：{gift_code}")
    
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
        time.sleep(1)
        
    # 4. 發送 Discord 報告
    send_discord_webhook(gift_code, results)
    print("🎉 任務執行完畢！")

if __name__ == "__main__":
    main()
