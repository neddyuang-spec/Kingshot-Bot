import csv
import io
import time
import hashlib
import requests

# ================= 基礎設定 =================
# Google 試算表 CSV 連結
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQFecEwf1fYIKawFfBVIZ51q-DrAx-yxeWNMHtwhlRWwkL585YTtEl9s31cBuA4yk3UVc5xna0Sc0k0/pub?output=csv"

# Discord Webhook 網址
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1536658271593828372/lF8PouLi3QYo3gXliwf0qMq_9KnwuxBGQGxiUFUnuKhiq-ujWwqGtPFLAPlGCp9EpaU9"

# 免 Cloudflare 封鎖的官方 API 端點
REDEEM_API_URL = "https://kingshot-giftcode.centurygame.com/api/gift_code"

# 官方 API MD5 簽名金鑰
SALT = "tB87#kPtkxqOS2"
# ============================================

def get_players():
    """讀取 Google 試算表中的盟友資料"""
    print("正在讀取盟友資料...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        res = requests.get(SHEET_CSV_URL, headers=headers, timeout=15)
        res.raise_for_status()
        
        csv_text = res.content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(csv_text))
        
        players = []
        for row in reader:
            row_lower = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k}
            
            kingdom = row_lower.get("kingdom") or row_lower.get("服號") or "1641"
            name = row_lower.get("name") or row_lower.get("名字") or row_lower.get("player") or "盟友"
            player_id = row_lower.get("playerid") or row_lower.get("player_id") or row_lower.get("id") or row_lower.get("玩家id")
            
            if player_id:
                players.append({
                    "kingdom": kingdom,
                    "name": name,
                    "player_id": player_id
                })
        
        if players:
            print(f"👉 成功讀取 {len(players)} 位盟友資料 (來自試算表)")
            return players
            
    except Exception as e:
        print(f"❌ 試算表讀取失敗: {e}")

    print("⚠️ 啟用備用盟友名單")
    return [
        {"kingdom": "1641", "name": "DasLight", "player_id": "246147093"},
        {"kingdom": "1641", "name": "肥豬", "player_id": "264788350"},
        {"kingdom": "1641", "name": "Ogre", "player_id": "279237769"},
        {"kingdom": "1641", "name": "MiniLight", "player_id": "306868384"},
        {"kingdom": "1641", "name": "HinokiMiller", "player_id": "265085587"},
        {"kingdom": "1641", "name": "Flora", "player_id": "327944637"},
        {"kingdom": "1641", "name": "帥光光", "player_id": "347892324"}
    ]

def get_latest_gift_code():
    """爬取最新禮物碼"""
    print("正在爬取最新禮物碼...")
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
                codes = re.findall(r'\b[A-Za-z0-9]{5,15}\b', active_part)
                ignore_list = {"ACTIVE", "EXPIRED", "COPY", "SOURCE", "VERIFIED", "ADDED", "GIFTS"}
                for code in codes:
                    if code.upper() not in ignore_list and not code.isdigit():
                        return code
    except Exception as e:
        print(f"⚠️ 爬取失敗: {e}")
        
    return "KS0810"

def calc_sign(params):
    """標準 Sign 計算：將 cdk, fid, time 字典序排列後拼上 SALT 算出 MD5"""
    sorted_keys = sorted(params.keys())
    query_string = "&".join([f"{k}={params[k]}" for k in sorted_keys if k != "sign"])
    string_to_hash = query_string + SALT
    return hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()

def redeem_code(player_id, gift_code):
    """發送兌換請求（時間採用 10 位數秒）"""
    # 關鍵修正：必須為 10 位數的 Unix 時間戳 (秒)
    t_sec = str(int(time.time()))
    
    params = {
        "cdk": str(gift_code).strip(),
        "fid": str(player_id).strip(),
        "time": t_sec
    }
    params["sign"] = calc_sign(params)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://kingshot-giftcode.centurygame.com",
        "Referer": "https://kingshot-giftcode.centurygame.com/"
    }
    
    try:
        res = requests.post(REDEEM_API_URL, data=params, headers=headers, timeout=12)
        
        try:
            result = res.json()
        except Exception:
            return "failed", f"❌ 伺服器回應異常 (HTTP {res.status_code})"
            
        print(f"DEBUG 原始回應 [{player_id}]: {result}")
        
        err_code = result.get("err_code", result.get("code", -1))
        msg = str(result.get("msg", result.get("message", "未知結果")))
        
        # 精確結果判定（優先檢測錯誤關鍵字）
        if "time expired" in msg.lower():
            return "failed", "❌ 時間戳記過期 (Time Expired)"
        elif "sign error" in msg.lower():
            return "failed", "❌ 簽名錯誤 (Sign Error)"
        elif "cdk expired" in msg.lower() or "cdk error" in msg.lower():
            return "failed", "❌ 禮物碼無效或已過期"
        elif err_code == 20004 or "already" in msg.lower() or "已領取" in msg or "claimed" in msg.lower() or "40008" in msg:
            return "claimed", "⚠️ 已重複領取過"
        elif "success" in msg.lower() or "成功" in msg or (result.get("code") == 1 and msg.upper() == "SUCCESS"):
            return "success", "✅ 兌換成功！"
        else:
            return "failed", f"❌ 失敗 ({msg})"
            
    except Exception as e:
        return "failed", f"❌ 請求發送失敗: {str(e)}"

def send_discord_webhook(gift_code, results):
    """發送 Discord 報告"""
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
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Discord Webhook 發送失敗: {e}")

def main():
    players = get_players()
    gift_code = get_latest_gift_code()
    print(f"👉 取得最新禮物碼：{gift_code}")
    
    results = []
    if players:
        for p in players:
            print(f"正在為 [{p['kingdom']}服] {p['name']} (ID: {p['player_id']}) 兌換 {gift_code}...")
            status, msg = redeem_code(p['player_id'], gift_code)
            results.append({
                "name": p['name'],
                "player_id": p['player_id'],
                "status": status,
                "msg": msg
            })
            time.sleep(1.5)
            
    send_discord_webhook(gift_code, results)
    print("🎉 任務執行完畢！")

if __name__ == "__main__":
    main()
