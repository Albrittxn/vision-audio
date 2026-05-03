#!/usr/bin/env python3
import asyncio
import os
import random
import smtplib
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import edge_tts
from google import genai
from google.genai import types

REPO_ROOT = Path(__file__).resolve().parent.parent
VISION_PATH = REPO_ROOT / "vision.md"
AUDIO_DIR = REPO_ROOT / "audio"
RSS_PATH = REPO_ROOT / "rss.xml"
DRAFT_PATH = REPO_ROOT / "scripts" / "last_draft.txt"
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"

LOCAL_TZ = ZoneInfo("America/Los_Angeles")

BASE_URL = "https://albrittxn.github.io/vision-audio"

NARRATIVE_DATE_START = date(2026, 12, 1)
NARRATIVE_DATE_END = date(2027, 5, 31)

DAY_TYPE_WEIGHTS = [
    ("vegas", 60),
    ("travel", 25),
    ("milestone", 10),
    ("disruption", 5),
]

VEGAS_BEATS = [
    "deep work morning at the desk",
    "gym lock-in session",
    "listing appointment",
    "closer 1:1 coaching",
    "closing day at the title office",
    "Henderson scout drive looking at future homes",
    "Saturday morning at home with Karen and Jasmine",
    "quiet Sunday reflection",
    "lunch with another founder",
    "live showing in real time",
    "evening review of the day",
    "morning routine with Jasmine",
    "late-night code session",
    "Compass office day",
    "Keller Williams office day",
    "pool day at home",
    "coffee shop work session",
    "networking event",
    "investor meeting",
    "reading hour at the desk",
    "content recording / filming session",
    "Henderson walking trail",
    "restaurant date night with Karen",
    "tucking Jasmine in for the night",
    "post-deal team celebration",
    "MacDonald Highlands property tour",
    "errand run that turns reflective",
    "long Uber conversation",
    "sunset Z06 drive with Karen — shopping date at Fashion Show Mall",
    "sunset Z06 drive with Karen — shopping date at the Galleria",
]

TRAVEL_DESTINATIONS = [
    {"place": "NYC", "mode": "always_solo", "context": "meeting up with Adam"},
    {"place": "Philly", "mode": "always_solo", "context": "visiting Uncle Matt"},
    {"place": "San Diego", "mode": "always_solo", "context": "visiting Maxwell — beach drives, PCH runs, dinners"},
    {"place": "El Salvador", "mode": "always_family", "context": "Karen's heritage — both her parents born there"},
    {"place": "Paris", "mode": "always_family", "context": "Disneyland Paris with the family"},
    {"place": "LA (Disneyland)", "mode": "always_family", "context": "Disneyland with the family"},
    {"place": "Hawaii", "mode": "always_family", "context": "family vacation"},
    {"place": "Bora Bora", "mode": "karen_or_solo"},
    {"place": "LA", "mode": "karen_or_solo"},
    {"place": "Miami", "mode": "karen_or_solo"},
    {"place": "Houston", "mode": "karen_or_solo"},
    {"place": "Chicago", "mode": "karen_or_solo"},
    {"place": "Tokyo", "mode": "karen_or_solo"},
    {"place": "London", "mode": "karen_or_solo"},
    {"place": "Dubai", "mode": "karen_or_solo"},
    {"place": "Sydney", "mode": "karen_or_solo"},
    {"place": "Singapore", "mode": "karen_or_solo"},
    {"place": "_europe_random", "mode": "karen_or_solo"},
]

EUROPE_CITIES = ["Rome", "Barcelona", "Amsterdam", "Berlin", "Lisbon", "Vienna", "Prague"]

MILESTONES = [
    "biggest deal he's ever closed lands today",
    "first $10k month locks in",
    "first $25k month locks in",
    "anniversary with Karen",
    "Karen's birthday",
    "Jasmine reaches a new developmental milestone",
    "closer team hits a record month",
    "closes on a new investment property",
    "press feature or podcast appearance drops",
    "a new hire's first sale comes through",
    "team hits an annual target ahead of schedule",
    "buys a new car or makes a major personal purchase",
]

DISRUPTIONS = [
    "a top closer quits unexpectedly",
    "a major deal blows up at the last minute",
    "Jasmine is sick",
    "Karen is sick",
    "minor injury at the gym",
    "major tech failure or data loss",
    "legal notice or threat lands",
    "an unexpected major expense surfaces",
]

MOODS = [
    "grinding hard",
    "blissful",
    "restless",
    "frustrated",
    "contemplative",
    "sharp-focused",
    "tired but locked in",
    "anxious",
    "exhilarated",
    "nostalgic",
    "patient and steady",
    "on edge",
]

WILDCARDS = [
    "smell of rain on hot asphalt",
    "a phone call that changes the plan",
    "an old friend texts out of nowhere",
    "a song stuck in his head all day",
    "a stranger's offhand comment lands hard",
    "an unexpected refund or check arrives",
    "the power flickers off briefly",
    "the car needs an unexpected stop",
    "spilled coffee on a key document",
    "a random memory from childhood surfaces",
    "a chance encounter with someone he used to know",
    "a new client cold-emails out of nowhere",
    "the weather flips dramatically",
    "the gym playlist runs out at the wrong moment",
    "Karen sends a photo midday that wrecks him",
    "Jasmine does something new",
    "a podcast line that sticks",
    "a billboard catches his eye",
    "an email from a name he doesn't recognize",
    "the coffee shop barista remembers his order",
    "runs into a former colleague",
    "runs into a competitor at the gym",
    "finds an old note in his car",
    "elevator small talk turns into something",
    "a forgotten promise resurfaces",
    "a deal he'd given up on responds",
    "a referral comes in unannounced",
    "traffic detour through a new neighborhood",
    "an accidental long conversation with an Uber driver",
    "a moment of sudden financial clarity",
    "a calendar conflict he didn't see coming",
    "a number on a screen he has to stare at twice",
    "realizes he hasn't called someone in months",
    "finds a book at a thrift shop",
    "the AC breaks at the office",
    "a sunset he stops to watch",
    "a question Karen asks that lands hard",
    "Jasmine somehow already recognizes a sound",
    "a former mentor's name comes up",
    "an ad targets him with eerie accuracy",
    "a moment of doubt he kicks past",
    "an old voice memo he replays",
    "Spotify recommends something perfectly",
    "a text from his mom out of nowhere",
    "realizes the date — anniversary of something",
    "forgotten laundry, forgotten meal",
    "a power-tripping security guard at a building",
    "sees a Tesla wrap with his old car's plate",
    "runs into a past flake who's doing well now",
    "a specific cloud formation he won't forget",
]

SURPRISE_BUCKETS = [
    ("low — a normal day, no real twist", 60),
    ("medium — one notable thing happens that lingers", 30),
    ("high — an unexpected event reshapes the day", 8),
    ("wild — something genuinely strange or huge happens", 2),
]

VOICE = "en-US-AvaMultilingualNeural"
MODEL = "gemini-2.5-flash"


def weighted_choice(items_with_weights):
    items, weights = zip(*items_with_weights)
    return random.choices(items, weights=weights, k=1)[0]


def format_narrative_date(d):
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y")


def parse_transcript(text):
    """Returns dict {narrative_date, day_type, day_label, body}.

    Header format (top of file, terminated by blank line):
        NARRATIVE_DATE: 2027-03-14
        DAY_TYPE: travel
        DAY_LABEL: Paris with Karen and Jasmine
    """
    lines = text.split("\n")
    headers = {}
    body_start = 0
    for i, line in enumerate(lines):
        if not line.strip():
            body_start = i + 1
            break
        key, sep, val = line.partition(":")
        if sep:
            headers[key.strip()] = val.strip()
    body = "\n".join(lines[body_start:])

    ndate = None
    raw = headers.get("NARRATIVE_DATE")
    if raw:
        try:
            ndate = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass

    return {
        "narrative_date": ndate,
        "day_type": headers.get("DAY_TYPE"),
        "day_label": headers.get("DAY_LABEL"),
        "body": body if headers else text,
    }


def read_recent_transcripts(limit=5):
    if not TRANSCRIPTS_DIR.exists():
        return []
    files = sorted(
        [p for p in TRANSCRIPTS_DIR.glob("*.txt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    out = []
    for p in files:
        meta = parse_transcript(p.read_text(encoding="utf-8"))
        meta["stem"] = p.stem
        out.append(meta)
    return out


def next_vision_number():
    """Highest existing Vision number across audio/ and transcripts/, plus 1.
    Files not matching the 'Vision N ...' pattern are ignored (legacy)."""
    nums = [0]
    for directory, pattern in [
        (TRANSCRIPTS_DIR, "Vision *.txt"),
        (AUDIO_DIR, "Vision *.mp3"),
    ]:
        if not directory.exists():
            continue
        for p in directory.glob(pattern):
            after = p.stem[len("Vision "):]
            head = after.split(" ", 1)[0]
            try:
                nums.append(int(head))
            except ValueError:
                continue
    return max(nums) + 1


def vision_stem(number, real_date):
    return f"Vision {number} - {real_date.strftime('%m.%d')}"


def pick_narrative_date():
    """70% forward motion (1-14 days after most recent transcript's narrative
    date, if known and still in window); 30% fully random in [START, END]."""
    recent = read_recent_transcripts(1)
    if recent and recent[0]["narrative_date"] is not None and random.random() < 0.7:
        last_date = recent[0]["narrative_date"]
        advance = random.randint(1, 14)
        candidate = last_date + timedelta(days=advance)
        if NARRATIVE_DATE_START <= candidate <= NARRATIVE_DATE_END:
            return candidate
    span_days = (NARRATIVE_DATE_END - NARRATIVE_DATE_START).days
    return NARRATIVE_DATE_START + timedelta(days=random.randint(0, span_days))


def _resolve_destination():
    dest = random.choice(TRAVEL_DESTINATIONS)
    place = dest["place"]
    if place == "_europe_random":
        place = random.choice(EUROPE_CITIES)

    mode = dest["mode"]
    context = dest.get("context", "")
    if mode == "always_solo":
        companions = "solo"
    elif mode == "always_family":
        companions = "with Karen and Jasmine"
    else:  # karen_or_solo
        if random.random() < 0.65:
            companions = "with Karen and Jasmine"
        else:
            companions = "solo, traveling with entrepreneur friends"

    label = f"{place} ({companions})"
    extra = f" — {context}" if context else ""
    return place, companions, label, extra


def build_day_plan(narrative_date):
    """Returns dict with day_type, day_label, day_spec.

    Trip continuity: if the most recent narrative was a travel day to X and
    today's narrative date is within 1-3 days of that, today's travel roll
    continues that same trip rather than picking a fresh destination.
    """
    day_type = weighted_choice(DAY_TYPE_WEIGHTS)

    if day_type == "vegas":
        beats = random.sample(VEGAS_BEATS, 2)
        day_label = f"Vegas: {beats[0]} / {beats[1]}"
        day_spec = (
            "Today is a normal Vegas day at home base. The two anchor beats "
            f"are: (1) {beats[0]}; (2) {beats[1]}. Weave them through the day "
            "naturally — they're the spine, the rest of the day fills in around "
            "them."
        )
        return {"day_type": day_type, "day_label": day_label, "day_spec": day_spec}

    if day_type == "travel":
        recent = read_recent_transcripts(1)
        continuing = False
        if recent and recent[0]["day_type"] == "travel" and recent[0]["narrative_date"]:
            days_since = (narrative_date - recent[0]["narrative_date"]).days
            if 1 <= days_since <= 3 and recent[0]["day_label"]:
                day_label = recent[0]["day_label"]
                day_spec = (
                    f"Today is a travel day, continuing the trip from the most "
                    f"recent narrative: {day_label}. Pick whatever day of the trip "
                    "feels right — mid-trip, or possibly heading home today. Lean "
                    "into continuity with what already happened."
                )
                continuing = True
        if not continuing:
            place, companions, day_label, extra = _resolve_destination()
            day_spec = (
                f"Today is a travel day. Ryan is on a trip to {place} {companions}.{extra} "
                "It can be any day of the trip — arrival, mid-trip, or heading home. A "
                "typical trip is 3-7 days. If recent narratives show earlier days of "
                "this same trip, continue from where they left off."
            )
        return {"day_type": day_type, "day_label": day_label, "day_spec": day_spec}

    if day_type == "milestone":
        event = random.choice(MILESTONES)
        return {
            "day_type": day_type,
            "day_label": f"Milestone: {event}",
            "day_spec": (
                f"Today is a milestone day. The defining event: {event}. The "
                "whole day arcs around it — anticipation, the moment itself, "
                "the aftermath."
            ),
        }

    # disruption
    event = random.choice(DISRUPTIONS)
    return {
        "day_type": day_type,
        "day_label": f"Disruption: {event}",
        "day_spec": (
            f"Today is a disruption day. The defining event: {event}. The day "
            "pivots around handling it. Ryan responds the way a focused founder "
            "would — no spiral, but the weight is real."
        ),
    }


def build_spice():
    mood = random.choice(MOODS)
    wildcard = random.choice(WILDCARDS)
    surprise = weighted_choice(SURPRISE_BUCKETS)
    return (
        f"Mood/energy thread: {mood}. "
        f"Wildcard concrete detail (must be woven in concretely, not just name-dropped): {wildcard}. "
        f"Surprise level: {surprise}."
    )


def generate_narrative(vision_text, narrative_date, day_spec, spice):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    formatted_date = format_narrative_date(narrative_date)

    system_prompt = (
        "You write 2500-word first-person POV narratives for Ryan, age 18, "
        "founder of Entheios AI in Las Vegas. The narrative is set once his "
        "vision is fully achieved. Present tense throughout. Heavy sensory "
        "detail (smells, textures, light, sound). Internal monologue interleaved "
        "with action. Reference specific places (Henderson, MacDonald Highlands, "
        "Compass and Keller Williams offices). Cinematic but realistic — no "
        "clichés, no 'I felt grateful'. Show, don't tell.\n\n"
        "PEOPLE RULES (hard):\n"
        "- Karen is Ryan's partner and Jasmine's mother. Refer to her by name "
        "when she's present. Karen's parents were both born in El Salvador.\n"
        "- Tamara is a real person from Ryan's current life and is EXPLICITLY "
        "EXCLUDED from this future vision. Never mention, reference, or imply "
        "Tamara in any narrative under any circumstances.\n\n"
        f"DATE: This narrative takes place on {formatted_date}. Incorporate "
        "season, weather, holidays, and date-appropriate context naturally. "
        "Jasmine was born September 2, 2026 — calculate her exact age based on "
        "the narrative date and depict her behavior to match (3 months: smiles, "
        "holds head up, coos; 4 months: laughs, grabs, rolls; 5 months: rolls "
        "both ways, sits with support; 6 months: sits independently, starting "
        "solids, babbles; 7 months: tries to crawl, says 'mamama'; 8 months: "
        "crawling, pulls up, claps, separation anxiety; 9 months: cruising, "
        "pincer grasp, plays peekaboo).\n\n"
        f"DAY: {day_spec}\n\n"
        f"SPICE: {spice}\n\n"
        "RECENT NARRATIVES: Past entries may inform today's only with a LIGHT "
        "TOUCH. Do not recap. Do not write 'previously...'. Most narratives "
        "stand alone. Occasionally — when natural — reference a recent event "
        "subtly (a smell that lingered, a callback to a moment, a streak). "
        "Each narrative is set on its own date — only reference recent "
        "narratives whose dates plausibly precede today's narrative date. "
        "Less is more."
    )

    user_message = vision_text
    recent = read_recent_transcripts(5)
    if recent:
        user_message += (
            "\n\n## RECENT NARRATIVES (past entries, for subtle continuity only)\n\n"
        )
        for meta in recent:
            label = (
                format_narrative_date(meta["narrative_date"])
                if meta["narrative_date"]
                else "date unknown"
            )
            user_message += (
                f"### Generated {meta['stem']} — set on {label}\n\n"
                f"{meta['body']}\n\n---\n\n"
            )

    response = client.models.generate_content(
        model=MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=1.0,
            max_output_tokens=12000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    return response.text


async def synthesize_audio(text, output_path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(output_path))


def _smtp_send(subject, body):
    sender = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL")
    if not (sender and password and recipient):
        raise RuntimeError(
            "GMAIL_USER, GMAIL_APP_PASSWORD, or RECIPIENT_EMAIL not set"
        )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
        smtp.send_message(msg)
    return recipient


def send_email(narrative, real_date, vision_number, day_type):
    subject = (
        f"Vision {vision_number} · "
        f"{real_date.strftime('%m.%d')} · "
        f"{day_type.title()}"
    )
    try:
        recipient = _smtp_send(subject, narrative)
        print(f"Email sent to {recipient}")
    except Exception as e:
        print(f"Email send failed: {e}")


def send_failure_email(real_date, error_text):
    subject = f"Vision FAILED · {real_date.strftime('%m.%d')}"
    recipient = _smtp_send(subject, error_text)
    print(f"Failure email sent to {recipient}")


def build_rss():
    mp3s = sorted(
        [p for p in AUDIO_DIR.glob("*.mp3")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    now_rfc822 = format_datetime(datetime.now(timezone.utc))

    items = []
    for p in mp3s:
        date_str = p.stem
        mtime_dt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        pub_date = format_datetime(mtime_dt)

        size = p.stat().st_size
        url = f"{BASE_URL}/audio/{quote(p.name)}"
        guid = url
        title = f"Vision — {date_str}"

        items.append(
            f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(title)}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <enclosure url="{escape(url)}" length="{size}" type="audio/mpeg"/>
      <itunes:author>Ryan</itunes:author>
      <itunes:explicit>false</itunes:explicit>
    </item>"""
        )

    items_xml = "\n".join(items)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Project Baseline - Vision</title>
    <link>{BASE_URL}</link>
    <language>en-us</language>
    <description>Daily first-person narratives from a constructed future.</description>
    <itunes:author>Ryan</itunes:author>
    <itunes:summary>Daily first-person narratives from a constructed future.</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="Education"/>
    <itunes:image href="{BASE_URL}/cover.jpg"/>
    <lastBuildDate>{now_rfc822}</lastBuildDate>
{items_xml}
  </channel>
</rss>
"""

    RSS_PATH.write_text(rss, encoding="utf-8")


def main():
    vision_text = VISION_PATH.read_text(encoding="utf-8")
    narrative_date = pick_narrative_date()
    plan = build_day_plan(narrative_date)
    spice = build_spice()

    narrative = generate_narrative(vision_text, narrative_date, plan["day_spec"], spice)

    DRAFT_PATH.write_text(narrative, encoding="utf-8")

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    real_date = datetime.now(LOCAL_TZ).date()
    vision_number = next_vision_number()
    base_stem = vision_stem(vision_number, real_date)
    transcript_content = (
        f"NARRATIVE_DATE: {narrative_date.isoformat()}\n"
        f"DAY_TYPE: {plan['day_type']}\n"
        f"DAY_LABEL: {plan['day_label']}\n"
        f"\n{narrative}"
    )
    transcript_path = TRANSCRIPTS_DIR / f"{base_stem}.txt"
    transcript_path.write_text(transcript_content, encoding="utf-8")

    audio_path = AUDIO_DIR / f"{base_stem}.mp3"
    asyncio.run(synthesize_audio(narrative, audio_path))

    build_rss()

    send_email(narrative, real_date, vision_number, plan["day_type"])

    print(f"Done: {audio_path.relative_to(REPO_ROOT)} — {format_narrative_date(narrative_date)} — {plan['day_label']}")


if __name__ == "__main__":
    if "--rebuild-rss-only" in sys.argv[1:]:
        build_rss()
        print(f"RSS rebuilt at {RSS_PATH.relative_to(REPO_ROOT)}")
        sys.exit(0)
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        try:
            send_failure_email(datetime.now(LOCAL_TZ).date(), tb)
        except Exception as e:
            print(f"Failure email also failed: {e}", file=sys.stderr)
        sys.exit(1)
