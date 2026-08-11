import csv
import io
import time
import hashlib
import requests

# ================= 基礎設定 =================
# 1. Google 試算表 CSV 發布連結
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhIRWwkL585YTtEl9s31cBuA4yk3UVc5xnaOScOk0/pub?output=csv"

# 2. Discord Webhook 網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"

# 3. 網址設定
OPTIMIZER_URL = "https://kingshotoptimizer.com/gift-codes/"
REDEEM_API_URL = "https://kingshot-giftcode.centurygame.com/api/gift_code"
# ============================================

def get_players():
    """讀取 Google 試算表盟友資料"""
    print("正在讀取盟友資料...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    res = requests.get(SHEET_CSV_URL, headers=headers, timeout=15)
    res.raise_for_status()

    csv_text = res.content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(csv_text))
    
    players = []
    for row in reader:
        kingdom = row.get("Kingdom", "").strip()
        name = row.get("Name", "").strip()
        player_id = row.get("PlayerID", "").strip()
        
        if player_id:
            players.append({
                "kingdom": kingdom or "1641", # 若表格沒填王國號，預設 1641
                "name": name,
                "player_id": player_id
            })
    return players

def get_latest_gift_code():
    """精準爬取 kingshotoptimizer.com 最新的一個禮物碼"""
    print("正在爬取最新禮物碼...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(OPTIMIZER_URL, headers=headers, timeout=15)
        res.raise_for_status()
        
        # 尋找頁面中的最新 Active code（解析網頁原始碼中的第一個禮物碼區塊）
        import re
        # 尋找 KS0810 / HAPPYCATDAY 這類連續大寫字母+數字的代碼
        codes = re.findall(r'([A-Z0-9]{5,15})', res.text)
        
        # 濾掉常規單字，保留真正的禮物碼
        ignore_words = {"OPTIMIZER", "EXPLORE", "GUIDES", "GOVERNOR", "CHARMS", "ACTIVE", "EXPIRED", "COPY", "VERIFIED", "SOURCE", "ADDED"}
        for code in codes:
            if code not in ignore_words and len(code) >= 5:
                # 第一個匹配到的最新代碼 (例如 KS0810)
                return code
    except Exception as e:
        print(f"⚠️ 爬取禮物碼失敗，錯誤: {e}")
        
    return "KS0810" # 備用預設碼

def generate_sign(fid, kid, cdk, time_str):
    """根據官方規範產生 sign 簽名"""
    # 將參數按 key 排序後組合加密 (官方通用 sign 算法)
    raw_str = f"cdk={cdk}&fid={fid}&kid={kid}&time={time_str}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def redeem_code(player_id, kingdom, gift_code):
    """呼叫官方 API 幫盟友兌換禮物碼"""
    current_time = str(int(time.time() * 1000)) # 毫秒級時間戳
    
    # 建立簽名
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
        msg = result.get("msg", result.get("message", "未知結果"))
        
        if err_code == 0 or "success" in str(msg).lower() or "成功" in str(msg):
            return True, "兌換成功！獎勵已發送至郵件"
        elif "already" in str(msg).lower() or "已領取" in str(msg) or "claimed" in str(msg).lower():
            return True, "重複領取 (之前已兌換過)"
        elif "err_cdk" in str(msg).lower() or "invalid" in str(msg).lower():
            return False, "禮物碼無效或已過期"
        else:
            return False, f"失敗 ({msg})"
            
    except Exception as e:
        return False, f"請求失敗: {str(e)}"

def send_discord_webhook(gift_code, results):
    """發送兌換結果到 Discord Webhook"""
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
    
    # 3. 逐一兌換
    results = []
    for p in players:
        print(f"正在為 [{p['kingdom']}服] {p['name']} (ID: {p['player_id']}) 兌換 {gift_code}...")
        status, msg = redeem_code(p['player_id'], p['kingdom'], gift_code)
        results.append({
            "name": p['name'],
            "player_id": p['player_id'],
            "status": status,
            "msg": msg
        })
        time.sleep(1) # 停頓 1 秒避免被伺服器限流
        
    # 4. 發送 Discord 通知
    send_discord_webhook(gift_code, results)
    print("🎉 任務執行完畢！")

if __name__ == "__main__":
    main()
