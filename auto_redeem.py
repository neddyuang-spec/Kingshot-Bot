import csv
import io
import time
import hashlib
import requests
from bs4 import BeautifulSoup

# ================= 基礎設定 =================
# 1. 你的 Google 試算表 CSV 連結 (請確認已開啟「知道連結的人皆可檢視」或發布)
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhlRWwkL585YTtEl9s31cBuA4yk3UVc5xna0Sc0k0/pub?output=csv"

# 2. Discord Webhook 網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"

OPTIMIZER_URL = "https://kingshotoptimizer.com/gift-codes/"
REDEEM_API_URL = "https://kingshot-giftcode.centurygame.com/api/gift_code"
# ============================================

def get_players():
    """讀取 Google 試算表中的盟友資料"""
    print("正在讀取盟友資料...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(SHEET_CSV_URL, headers=headers, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ 讀取試算表失敗: {e}")
        return []

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
    """精準爬取 Active codes 第一個禮物碼"""
    print("正在爬取最新禮物碼...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(OPTIMIZER_URL, headers=headers, timeout=15)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 尋找按鈕文字為 Copy 的前一個同層/父層元素，或直接匹配禮物碼卡片
        import re
        # 先切出 Active codes 到 Expired codes 之間的文字，避免抓到日期或歷史碼
        content = res.text
        if "Active codes" in content:
            content = content.split("Active codes")[1]
        if "Expired codes" in content:
            content = content.split("Expired codes")[0]
            
        soup_active = BeautifulSoup(content, "html.parser")
        text = soup_active.get_text(separator=" ")
        
        # 匹配獨立出現的英文數字組合（排除日期格式）
        tokens = text.split()
        for token in tokens:
            token = token.strip()
            # 排除純數字、長度不對、或是常見單字
            if re.match(r'^[A-Za-z0-9]{4,15}$', token):
                if token not in {"Copy", "Source", "Verified", "Added", "in-game"} and not token.isdigit():
                    return token
    except Exception as e:
        print(f"⚠️ 爬取失敗，錯誤: {e}")
        
    return "KS0810"

def generate_sign(fid, kid, cdk, time_str):
    """計算官方 API 驗證用的 MD5 sign 簽名"""
    raw_str = f"cdk={cdk}&fid={fid}&kid={kid}&time={time_str}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def redeem_code(player_id, kingdom, gift_code):
    """呼叫官方 API 幫盟友兌換禮物碼"""
    # 官方 API 規範：使用 10 位數 Unix 秒級時間戳 (例如 1786440776)
    current_time = str(int(time.time()))
    
    sign = generate_sign(player_id, kingdom, gift_code, current_time)
    
    payload = {
        "fid": str(player_id),
        "kid": str(kingdom),
        "cdk": str(gift_code),
        "time": current_time,
        "sign": sign
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://ks-giftcode.centurygame.com",
        "Referer": "https://ks-giftcode.centurygame.com/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    try:
        res = requests.post(REDEEM_API_URL, data=payload, headers=headers, timeout=10)
        result = res.json()
        
        err_code = result.get("err_code", result.get("code", -1))
        msg = str(result.get("msg", result.get("message", "未知結果")))
        
        if err_code == 0 or "success" in msg.lower() or "成功" in msg:
            return True, "兌換成功！"
        elif "already" in msg.lower() or "已領取" in msg or "claimed" in msg.lower():
            return True, "重複領取 (已兌換過)"
        else:
            return False, f"失敗 ({msg})"
            
    except Exception as e:
        return False, f"請求異常: {str(e)}"

def send_discord_webhook(gift_code, results):
    """發送兌換報告至 Discord Webhook"""
    print("正在傳送結果給 Discord...")
    
    success_count = sum(1 for r in results if r["status"])
    fail_count = len(results) - success_count
    
    details = []
    for r in results:
        status_icon = "✅" if r["status"] else "❌"
        details.append(f"{status_icon} **{r['name']}** (`{r['player_id']}`) - {r['msg']}")
        
    details_str = "\n".join(details)
    if len(details_str) > 3000:
        details_str = details_str[:3000] + "\n...(筆數過多略過)"
        
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
    # 1. 讀取 Google 試算表盟友資料
    players = get_players()
    print(f"👉 成功讀取 {len(players)} 位盟友資料")

    # 2. 爬取最新禮物碼
    gift_code = get_latest_gift_code()
    print(f"👉 取得最新禮物碼：{gift_code}")
    
    # 3. 逐一進行兌換
    results = []
    if players:
        for p in players:
            print(f"正在為 [{p['kingdom']}服] {p['name']} (ID: {p['player_id']}) 兌換 {gift_code}...")
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
