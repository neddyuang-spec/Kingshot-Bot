import csv
import io
import time
import hashlib
import requests

# ================= 基礎設定 =================
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhIRWwkL585YTtEl9s31cBuA4yk3UVc5xnaOScOk0/pub?output=csv"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"

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
    """使用具有 JavaScript 渲染能力的解析 API 抓取最新禮物碼"""
    print("正在爬取最新禮物碼...")
    # 直接請求解析後包含渲染內容的頁面 API / 導出點
    url = "https://r.jina.ai/https://kingshotoptimizer.com/gift-codes/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            text = res.text
            if "Active codes" in text:
                active_part = text.split("Active codes")[1]
                if "Expired codes" in active_part:
                    active_part = active_part.split("Expired codes")[0]
                
                import re
                # 尋找 Active codes 區塊內的第一個獨立大寫禮物碼（如 KS0810）
                codes = re.findall(r'\b[A-Z0-9]{5,15}\b', active_part)
                ignore_list = {"ACTIVE", "EXPIRED", "COPY", "SOURCE", "VERIFIED", "ADDED", "GIFTS"}
                for code in codes:
                    if code not in ignore_list and not code.isdigit():
                        return code
    except Exception as e:
        print(f"⚠️ 爬取失敗，使用預設值: {e}")
        
    return "KS0810"

def generate_sign(fid, kid, cdk, time_str):
    """計算官方 API 驗證簽名"""
    raw_str = f"cdk={cdk}&fid={fid}&kid={kid}&time={time_str}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def redeem_code(player_id, kingdom, gift_code):
    """呼叫官方 API 進行兌換，精準區分『成功』、『已領取過』與『失敗』"""
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
        
        # 精準狀態判斷
        if "already" in msg.lower() or "已領取" in msg or "claimed" in msg.lower() or err_code == 20004:
            return "claimed", "⚠️ 已重複領取過"
        elif err_code == 0 or "success" in msg.lower() or "成功" in msg:
            return "success", "✅ 兌換成功！"
        else:
            return "failed", f"❌ 失敗 ({msg})"
            
    except Exception as e:
        return "failed", f"❌ 請求異常: {str(e)}"

def send_discord_webhook(gift_code, results):
    """發送格式化報告至 Discord"""
    print("正在傳送結果給 Discord...")
    
    success_count = sum(1 for r in results if r["status"] == "success")
    claimed_count = sum(1 for r in results if r["status"] == "claimed")
    fail_count = sum(1 for r in results if r["status"] == "failed")
    
    details = []
    for r in results:
        details.append(f"**{r['name']}** (`{r['player_id']}`) - {r['msg']}")
        
    details_str = "\n".join(details)
    if len(details_str) > 3000:
        details_str = details_str[:3000] + "\n...(筆數過多略過)"
        
    embed = {
        "title": "🎁 Kingshot 盟友禮物碼每日自動兌換報告",
        "color": 3066993 if fail_count == 0 else 15158332,
        "fields": [
            {"name": "最新禮物碼", "value": f"`{gift_code}`", "inline": True},
            {"name": "兌換統計", "value": f"成功: **{success_count}** 人\n重複領取: **{claimed_count}** 人\n失敗: **{fail_count}** 人", "inline": True},
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
    players = get_players()
    print(f"👉 成功讀取 {len(players)} 位盟友資料")

    gift_code = get_latest_gift_code()
    print(f"👉 取得最新禮物碼：{gift_code}")
    
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
            
    send_discord_webhook(gift_code, results)
    print("🎉 任務執行完畢！")

if __name__ == "__main__":
    main()
