import os
import time
import hashlib
import requests

# Century Games 通用 Salt (請填入你之前使用的 Salt，例如 tB87#kPtkxqOS2)
SALT = os.getenv("KINGSHOT_SALT", "tB87#kPtkxqOS2") 

# 盟友名單 (根據 image_aa8a82.jpg 的截圖還原)
PLAYERS = [
    {"name": "Light", "fid": "246147093", "kid": "1641"},
    {"name": "肥豬", "fid": "264788350", "kid": "1641"},
    {"name": "Ogre", "fid": "279237769", "kid": "1641"},
    {"name": "MiniLight", "fid": "306868384", "kid": "1641"},
    {"name": "Hinoki", "fid": "265085587", "kid": "1641"},
    {"name": "Flora", "fid": "327944637", "kid": "1641"},
    {"name": "帥光光", "fid": "347892324", "kid": "628"},
]

def generate_sign(cdk, fid, kid, time_sec):
    """
    最新 MD5 簽名演算法：
    必須完全按照 cdk -> fid -> kid -> time 的順序，加上 SALT
    """
    raw_str = f"cdk={cdk}&fid={fid}&kid={kid}&time={time_sec}"
    sign_str = raw_str + SALT
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

def redeem_gift_code(cdk, player):
    url = "https://kingshot-giftcode.centurygame.com/api/gift_code"
    time_sec = str(int(time.time())) # 關鍵：改用秒數
    sign = generate_sign(cdk, player['fid'], player['kid'], time_sec)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://ks-giftcode.centurygame.com",
        "Referer": "https://ks-giftcode.centurygame.com/",
        "Accept": "application/json, text/plain, */*"
    }
    
    data = {
        "cdk": cdk,
        "fid": player['fid'],
        "kid": player['kid'],
        "time": time_sec,
        "sign": sign
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        return response.json()
    except Exception as e:
        return {"code": -1, "msg": f"請求失敗: {str(e)}"}

def main():
    cdk = "KS0810" 
    print(f"👉 取得最新禮物碼：{cdk}")
    
    for p in PLAYERS:
        print(f"正在為 [{p['kid']}服] {p['name']} (ID: {p['fid']}) 兌換 {cdk}...")
        res = redeem_gift_code(cdk, p)
        print(f"回應結果: {res}")
        time.sleep(1.5) # 避免請求過快被阻擋，加入短暫延遲

if __name__ == "__main__":
    main()
