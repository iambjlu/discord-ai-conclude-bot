import asyncio
import json
from renderer import ImageGenerator

async def main():
    gen = ImageGenerator()
    # Dummy weather data mimicking the real one
    dummy_data = [
        {
            "county": "臺北市",
            "time_range": "今日白天",
            "forecasts": [
                {"time": "06:00", "wx": "晴時多雲", "temp": "28", "pop": "10"},
                {"time": "12:00", "wx": "多雲午睡陣雨", "temp": "32", "pop": "60"},
                {"time": "18:00", "wx": "陰天", "temp": "26", "pop": "20"},
            ]
        },
        {
            "county": "新北市",
            "time_range": "今日白天",
            "forecasts": [
                {"time": "06:00", "wx": "晴時多雲", "temp": "28", "pop": "10"},
                {"time": "12:00", "wx": "雨天", "temp": "32", "pop": "80"},
                {"time": "18:00", "wx": "陰天", "temp": "26", "pop": "20"},
            ]
        }
    ]
    
    print("Generating weather card...")
    try:
        img = await gen.generate_weather_card(dummy_data, "Test Server", None, "測試天氣")
        print(f"Generated successfully. Image size: {len(img.getvalue())} bytes")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
