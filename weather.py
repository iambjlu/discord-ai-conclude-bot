# cwa_weather_forecast.py
import requests

def get_weather_data(api_key):
    # 預報 API 使用的是「縣市名稱」而不是測站 ID
    counties = [
        "臺北市", "新北市", "基隆市", "桃園市", 
        "臺中市", "臺南市", "高雄市", "屏東縣", "宜蘭縣"
    ]
    
    # 36小時天氣預報 API
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        if data.get("success") != "true":
            print("API 請求失敗，請檢查 Key 有沒有填對。")
            return

        locations = data["records"]["location"]

        for county in counties:
            # 從回傳資料中篩選出我們要的縣市
            target = next((loc for loc in locations if loc["locationName"] == county), None)
            
            if target:
                elements = target["weatherElement"]
                
                # 這裡拿的是「第一個時段」(index 0)，即未來 12 小時的預報
                # Wx: 天氣現象, PoP: 降雨機率, MinT: 最低溫, MaxT: 最高溫
                wx = elements[0]["time"][0]["parameter"]["parameterName"]
                pop = elements[1]["time"][0]["parameter"]["parameterName"]
                min_t = elements[2]["time"][0]["parameter"]["parameterName"]
                max_t = elements[4]["time"][0]["parameter"]["parameterName"]
                # CI: 舒適度
                ci = elements[3]["time"][0]["parameter"]["parameterName"]

                start_time = elements[0]["time"][0]["startTime"]
                end_time = elements[0]["time"][0]["endTime"]

                print(f"--- {county} 今日預報 ---")
                print(f"預報時段 : {start_time[5:16]} ~ {end_time[5:16]}")
                print(f"天氣狀態 : {wx} ({ci})")
                print(f"降雨機率 : {pop}%")
                print(f"氣溫區間 : {min_t} °C - {max_t} °C")
                print("-" * 35)
            else:
                print(f"找不到 {county} 的資料。")

    except Exception as e:
        print(f"發生錯誤啦：{e}")

if __name__ == "__main__":
    get_weather_data(os.getenv("WEATHER_KEY"))