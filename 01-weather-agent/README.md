# 01 — Weather Assistant

## Objective

A conversational weather assistant that answers natural-language questions with **real data** (no mocks), keeps context across multiple turns, and handles network errors gracefully.

## Base pattern (book p.7)

An agent = **Model** + **Tools** + **Instructions**. Here, two tools (`get_current_weather`, `get_forecast`) are wired to the public [Open-Meteo](https://open-meteo.com/) API (free, no API key).

## Advanced features already implemented

- **Real API integration**: geocoding (city name → coordinates) + real forecasts, via 2 HTTP calls with `requests`.
- **In-memory cache**: a city already looked up isn't re-geocoded within the same session.
- **Network retry**: every API call retries once on failure before raising a readable error.
- **Multi-day forecasts** (1 to 7 days), with a lookup table mapping WMO weather codes to human-readable descriptions.
- **Configurable units** (metric °C/km/h or imperial °F/mph), which the agent remembers for the rest of the conversation.
- **Multi-turn conversation**: history is passed on every call (`result.to_input_list()`), so the agent remembers the city or units mentioned earlier.

## Extra task: Trip Planner

A richer, second task on top of simple Q&A: `compare_weather(city_a, city_b, days, units)` fetches both forecasts and **recommends a destination** for an outdoor trip. It counts severe-weather days (storms, heavy rain/snow) in each city and, if that's a tie, compares average high temperatures against a comfortable reference (22°C / 72°F) to break it. This is a genuine reasoning task — not just data retrieval, but a decision built from that data.

## Run the project

```bash
cd 01-weather-agent
python weather_agent.py
```

## Example interaction

```
You: What's the weather like in Casablanca?
Agent: It's currently clear sky in Casablanca, Morocco, 24.3°C, wind 12.1km/h, humidity 45%.

You: And the next 3 days? In Fahrenheit please.
Agent: Forecast for Casablanca, Morocco:
- 2026-07-02: clear sky, 68.4°F / 82.1°F
- 2026-07-03: partly cloudy, 66.9°F / 80.5°F
- 2026-07-04: overcast, 65.1°F / 77.8°F

You: Should I go to Paris or Rome this weekend for a walking tour?
Agent: Comparison over the next 3 day(s):
- Paris: avg high 19.4°C, 1 day(s) with severe weather
- Rome: avg high 24.8°C, 0 day(s) with severe weather
Recommendation: Rome looks safer for an outdoor trip (fewer severe weather days).

You: exit
```

Note: the agent remembered the "Fahrenheit" preference without being told again — that's conversation memory in action.

## What to observe

- The `get_current_weather` tool returns an **already formatted string** on purpose; an LLM works better with clear text than raw JSON it has to reformat.
- Try a city that doesn't exist ("Xyzabc"): the error message reaches the agent, which has to communicate the failure politely to the user — watch how it rephrases it.
- The cache (`_geocode_cache`) avoids an unnecessary network round-trip if you ask for the same city's weather twice in the session.

## Go further

- Add a weather alert: if `weather_code` corresponds to a thunderstorm (95-99), make the agent add a warning.
- Persist the user's favorite cities in a small JSON file across script runs (long-term memory, not just within the session).
- Write a `pytest` unit test for the `_geocode` function by mocking `requests.get`, to verify the caching behavior without calling the real API.
