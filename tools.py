import logging
import os
import requests
import smtplib

from datetime import datetime, timedelta, timezone
from typing import Optional

from livekit.agents import function_tool, RunContext
from langchain_community.tools import DuckDuckGoSearchRun
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Try ZoneInfo; if tzdata missing on Windows, we fallback to fixed IST offset.
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore
    ZoneInfoNotFoundError = Exception  # type: ignore


DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Chennai").strip()


# -------------------------
# TIME TOOL (robust on Windows)
# -------------------------

@function_tool()
async def get_local_time(context: RunContext) -> str:  # type: ignore
    """
    Get the current local date and time (IST).
    Works on Windows even if tzdata is missing.
    """
    try:
        if ZoneInfo is not None:
            try:
                now = datetime.now(ZoneInfo("Asia/Kolkata"))
            except ZoneInfoNotFoundError:
                # Fallback if tzdata not installed
                ist = timezone(timedelta(hours=5, minutes=30))
                now = datetime.now(ist)
        else:
            ist = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(ist)

        return now.strftime("Today is %A, %d %B %Y and the time is %I:%M %p.")
    except Exception as e:
        logging.error(f"Error getting local time: {e}")
        return "I’m unable to determine the current time right now, Mr. Wayne."


# -------------------------
# WEATHER TOOL (wttr.in + Open-Meteo fallback + variants)
# -------------------------

def _clean_city(city: Optional[str]) -> str:
    if not city or not str(city).strip():
        return DEFAULT_CITY
    return str(city).strip()

def _wttr(city: str) -> Optional[str]:
    """
    Primary provider: wttr.in
    """
    headers = {"User-Agent": "Mozilla/5.0 (OracleAI)"}
    # More informative format than format=3
    fmt = "%l: %C | Temp %t (feels %f) | Hum %h | Wind %w"
    url = f"https://wttr.in/{city}"

    for attempt, timeout in enumerate([5, 7], start=1):
        try:
            r = requests.get(url, params={"format": fmt}, headers=headers, timeout=timeout)
            if r.status_code == 200:
                text = (r.text or "").strip()
                if text:
                    return text
                logging.warning(f"wttr.in empty response for {city}")
                return None
            logging.error(f"wttr.in status {r.status_code} for {city}")
        except requests.Timeout:
            logging.error(f"wttr.in timed out (attempt {attempt}) for {city}")
        except Exception as e:
            logging.error(f"wttr.in error (attempt {attempt}) for {city}: {e}")
    return None

def _open_meteo(city_query: str) -> Optional[str]:
    """
    Backup provider: Open-Meteo (no API key).
    """
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_query, "count": 1, "language": "en", "format": "json"},
            timeout=7,
        )
        if geo.status_code != 200:
            logging.error(f"Open-Meteo geocode status {geo.status_code} for {city_query}")
            return None

        gj = geo.json()
        results = gj.get("results") or []
        if not results:
            logging.warning(f"Open-Meteo: no geocode results for {city_query}")
            return None

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        place = results[0].get("name", city_query)
        country = results[0].get("country", "")

        wx = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            timeout=7,
        )
        if wx.status_code != 200:
            logging.error(f"Open-Meteo weather status {wx.status_code} for {city_query}")
            return None

        wj = wx.json()
        cur = wj.get("current_weather")
        if not cur:
            return None

        temp = cur.get("temperature")
        wind = cur.get("windspeed")
        time_utc = cur.get("time")

        loc = f"{place}{', ' + country if country else ''}"
        return f"{loc}: Temp {temp}°C | Wind {wind} km/h | Updated {time_utc} (UTC)"

    except requests.Timeout:
        logging.error(f"Open-Meteo timed out for {city_query}")
        return None
    except Exception as e:
        logging.error(f"Open-Meteo error for {city_query}: {e}")
        return None

@function_tool()
async def get_weather(context: RunContext, city: Optional[str] = None) -> str:  # type: ignore
    """
    Weather for a city.
    - wttr.in first
    - Open-Meteo fallback with multiple query variants
    """
    city = _clean_city(city)

    # 1) Try wttr.in
    wt = _wttr(city)
    if wt:
        return wt

    # 2) Try Open-Meteo with variants
    variants = [
        city,
        f"{city}, India",
        "Kanniyakumari, India",   # alt spelling
        "Kanyakumari, Tamil Nadu, India",
        "Nagercoil, India",       # nearby fallback
    ]
    for q in variants:
        om = _open_meteo(q)
        if om:
            return om

    return f"Weather services are unreachable right now for {city}, Mr. Wayne. (Network/DNS issue likely.)"


# -------------------------
# WEB SEARCH TOOL
# -------------------------

@function_tool()
async def search_web(context: RunContext, query: str) -> str:  # type: ignore
    try:
        results = DuckDuckGoSearchRun().run(tool_input=query)
        return results
    except Exception as e:
        logging.error(f"Search error: {e}")
        return "An error occurred while searching the web, Mr. Wayne."


# -------------------------
# EMAIL TOOL
# -------------------------

@function_tool()
async def send_email(
    context: RunContext,  # type: ignore
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None,
) -> str:
    try:
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")

        if not gmail_user or not gmail_password:
            return "Email sending failed: Gmail credentials not configured, Mr. Wayne."

        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = to_email
        msg["Subject"] = subject

        recipients = [to_email]
        if cc_email and cc_email.strip():
            msg["Cc"] = cc_email.strip()
            recipients.append(cc_email.strip())

        msg.attach(MIMEText(message, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipients, msg.as_string())
        server.quit()

        return f"Email sent successfully to {to_email}, Mr. Wayne."
    except smtplib.SMTPAuthenticationError:
        return "Email sending failed: Authentication error. Check your Gmail App Password, Mr. Wayne."
    except Exception as e:
        logging.error(f"Email error: {e}")
        return "An error occurred while sending the email, Mr. Wayne."
