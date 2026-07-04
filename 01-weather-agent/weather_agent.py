"""
01 - Weather Assistant
Goal: a conversational (multi-turn) weather assistant backed by a real
public API (Open-Meteo, free, no key required), with multi-day forecasts,
choice of units, in-memory caching, and network error handling.

Base pattern (book p.7): Model + Tools + Instructions.
Advanced features added:
- Real geocoding + forecast via the Open-Meteo API (2 endpoints)
- In-memory cache to avoid re-geocoding the same city
- Simple retry on network/timeout errors
- Multi-day forecasts, metric/imperial units
- Multi-turn conversation loop (context memory via to_input_list)

Extra task - Trip Planner:
- compare_weather(city_a, city_b) fetches both forecasts and recommends the
  better destination for an outdoor trip, flagging severe weather days
  (thunderstorms, heavy snow/rain) and comparing average temperatures.
"""

import asyncio
import os

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

from agents import Agent, Runner, function_tool

load_dotenv()

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy",
    3: "overcast", 45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "light rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "moderate snow", 75: "heavy snow",
    77: "snow grains", 80: "light rain showers",
    81: "moderate rain showers", 82: "violent rain showers",
    85: "light snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with light hail", 99: "thunderstorm with heavy hail",
}

# Codes considered unsuitable for outdoor activities, used by compare_weather.
SEVERE_WEATHER_CODES = {65, 66, 67, 75, 82, 86, 95, 96, 99}

_geocode_cache: dict[str, "GeoLocation"] = {}


class GeoLocation(BaseModel):
    name: str
    country: str
    latitude: float
    longitude: float


def _request_with_retry(url: str, params: dict, attempts: int = 2) -> dict:
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"API call failed after {attempts} attempt(s): {last_error}")


def _geocode(city: str) -> GeoLocation | None:
    key = city.strip().lower()
    if key in _geocode_cache:
        return _geocode_cache[key]

    data = _request_with_retry(GEOCODING_URL, {"name": city, "count": 1, "language": "en", "format": "json"})
    results = data.get("results")
    if not results:
        return None

    location = GeoLocation(
        name=results[0]["name"],
        country=results[0].get("country", "?"),
        latitude=results[0]["latitude"],
        longitude=results[0]["longitude"],
    )
    _geocode_cache[key] = location
    return location


@function_tool
def get_current_weather(city: str, units: str = "metric") -> str:
    """Get the real current weather for a city. units is 'metric' (°C, km/h) or 'imperial' (°F, mph)."""
    try:
        location = _geocode(city)
    except RuntimeError as exc:
        return f"Network error while looking up {city}: {exc}"

    if location is None:
        return f"Could not find the city '{city}'. Check the spelling."

    temp_unit = "celsius" if units == "metric" else "fahrenheit"
    wind_unit = "kmh" if units == "metric" else "mph"

    try:
        data = _request_with_retry(FORECAST_URL, {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
            "temperature_unit": temp_unit,
            "wind_speed_unit": wind_unit,
            "timezone": "auto",
        })
    except RuntimeError as exc:
        return f"Network error while fetching the weather: {exc}"

    current = data["current"]
    description = WMO_WEATHER_CODES.get(current["weather_code"], "unknown conditions")
    temp_symbol = "°C" if units == "metric" else "°F"
    speed_symbol = "km/h" if units == "metric" else "mph"

    return (
        f"Current weather in {location.name}, {location.country}: {description}, "
        f"{current['temperature_2m']}{temp_symbol}, wind {current['wind_speed_10m']}{speed_symbol}, "
        f"humidity {current['relative_humidity_2m']}%."
    )


def _fetch_daily_forecast(city: str, days: int, units: str) -> "tuple[GeoLocation, dict] | str":
    """Shared helper: returns (location, daily_data) on success, or an error string."""
    try:
        location = _geocode(city)
    except RuntimeError as exc:
        return f"Network error while looking up {city}: {exc}"

    if location is None:
        return f"Could not find the city '{city}'. Check the spelling."

    temp_unit = "celsius" if units == "metric" else "fahrenheit"

    try:
        data = _request_with_retry(FORECAST_URL, {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "temperature_unit": temp_unit,
            "timezone": "auto",
            "forecast_days": days,
        })
    except RuntimeError as exc:
        return f"Network error while fetching the forecast: {exc}"

    return location, data["daily"]


@function_tool
def get_forecast(city: str, days: int = 3, units: str = "metric") -> str:
    """Get a real multi-day forecast (1-7 days) for a city. units is 'metric' or 'imperial'."""
    days = max(1, min(days, 7))
    result = _fetch_daily_forecast(city, days, units)
    if isinstance(result, str):
        return result
    location, daily = result

    temp_symbol = "°C" if units == "metric" else "°F"
    lines = [f"Forecast for {location.name}, {location.country}:"]
    for date, code, tmax, tmin in zip(daily["time"], daily["weather_code"], daily["temperature_2m_max"], daily["temperature_2m_min"]):
        description = WMO_WEATHER_CODES.get(code, "unknown conditions")
        lines.append(f"- {date}: {description}, {tmin}{temp_symbol} / {tmax}{temp_symbol}")

    return "\n".join(lines)


@function_tool
def compare_weather(city_a: str, city_b: str, days: int = 3, units: str = "metric") -> str:
    """Compare the forecast of two cities over the next 1-7 days to help decide
    which is the better destination for an outdoor trip. Flags severe weather
    (storms, heavy snow/rain) and compares average high temperatures."""
    days = max(1, min(days, 7))

    result_a = _fetch_daily_forecast(city_a, days, units)
    if isinstance(result_a, str):
        return result_a
    result_b = _fetch_daily_forecast(city_b, days, units)
    if isinstance(result_b, str):
        return result_b

    location_a, daily_a = result_a
    location_b, daily_b = result_b

    def _summarize(daily: dict) -> tuple[float, int]:
        avg_max = sum(daily["temperature_2m_max"]) / len(daily["temperature_2m_max"])
        severe_days = sum(1 for code in daily["weather_code"] if code in SEVERE_WEATHER_CODES)
        return avg_max, severe_days

    avg_max_a, severe_a = _summarize(daily_a)
    avg_max_b, severe_b = _summarize(daily_b)

    temp_symbol = "°C" if units == "metric" else "°F"
    lines = [
        f"Comparison over the next {days} day(s):",
        f"- {location_a.name}: avg high {avg_max_a:.1f}{temp_symbol}, {severe_a} day(s) with severe weather",
        f"- {location_b.name}: avg high {avg_max_b:.1f}{temp_symbol}, {severe_b} day(s) with severe weather",
    ]

    comfort_reference = 22 if units == "metric" else 72
    if severe_a != severe_b:
        better = location_a.name if severe_a < severe_b else location_b.name
        lines.append(f"Recommendation: {better} looks safer for an outdoor trip (fewer severe weather days).")
    elif round(avg_max_a, 1) != round(avg_max_b, 1):
        milder = location_a.name if abs(avg_max_a - comfort_reference) < abs(avg_max_b - comfort_reference) else location_b.name
        lines.append(f"Recommendation: {milder} has milder temperatures for outdoor activities.")
    else:
        lines.append("Recommendation: both destinations look similarly suited for an outdoor trip.")

    return "\n".join(lines)


weather_agent = Agent(
    name="Weather assistant",
    instructions=(
        "You are a helpful weather assistant with access to real weather data. "
        "Use get_current_weather for 'now' questions, get_forecast for multi-day "
        "questions about a single city, and compare_weather when the user is "
        "deciding between two cities for a trip or outdoor plans. Default to "
        "metric units unless the user asks for imperial units or mentions "
        "Fahrenheit/mph. Always answer in the same language as the user. "
        "Remember the user's stated unit preference for the rest of the conversation."
    ),
    tools=[get_current_weather, get_forecast, compare_weather],
)


async def main():
    print("Weather Assistant — type 'exit' to quit.")
    print("Try the Trip Planner: \"Should I go to Paris or Rome this weekend?\"\n")
    history: list = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit", "q"}:
            break
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})
        result = await Runner.run(weather_agent, history)
        print(f"Agent: {result.final_output}\n")
        history = result.to_input_list()


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Add your OPENAI_API_KEY to a .env file (see .env.example).")
    asyncio.run(main())
