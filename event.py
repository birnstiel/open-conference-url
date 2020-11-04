#!/usr/bin/env python3

import datetime
import re
import time

import icalendar
import pytz


# The number of hours in a day
HOURS_IN_DAY = 24
# The number of seconds in an hour
SECONDS_IN_HOUR = 3600


class Event(object):

    # A list of conference domains to look for, in order of precedence
    conference_domains = [
        # Zoom
        'zoom.us',
        # Google Meet
        'google.com',
        # UberConference
        'uberconference.com',
        # Microsoft Teams
        'microsoft.com',
        # GoToMeeting
        'gotomeeting.com'
    ]

    # Initialize the Event object by processing a string of the ICS file
    # contents
    def __init__(self, event_str):
        self.calendar = icalendar.Calendar().from_ical(event_str)
        # The last vevent will contain any overrides for recurring events (e.g.
        # normally 9am weekly, but this week, meeting is at 8am); otherwise, it
        # will fall back to the originally-scheduled time slot
        vevent = self.get_vevent_for_today(self.calendar.walk('vevent'))
        self.summary = vevent.get('summary')
        # Handle recurring events by forcing the date of the start date/time
        # object to be today (since the script outputting the event IDs will
        # only fetch today's events anyway)
        self.start_datetime_raw = Event.get_vevent_datetime(vevent).combine(
            date=datetime.datetime.now().date(),
            time=Event.get_vevent_datetime(vevent).time(),
            tzinfo=Event.get_vevent_datetime(vevent).tzinfo)
        self.start_datetime_raw = self.correct_for_dst(self.start_datetime_raw)
        self.start_datetime_utc = pytz.utc.normalize(self.start_datetime_raw)
        self.start_datetime_local = Event.localize_datetime(self.start_datetime_utc)
        self.location = vevent.get('location')
        self.description = vevent.get('description')
        self.raw_url = vevent.get('url')
        self.conference_url = self.parse_conference_url()

    # Retrieve the vevent corresponding to today for this specific iCal event
    def get_vevent_for_today(self, vevents):
        current_date = datetime.datetime.now().date()
        for vevent in reversed(vevents):
            if Event.get_vevent_datetime(vevent).date() == current_date:
                return vevent
        return vevents[0]

    # Retrieve the date; this function handles all-day vevents, as well as
    # vevents with a specific date/time
    @staticmethod
    def get_vevent_datetime(vevent):
        if type(vevent.get('dtstart').dt) == datetime.date:
            # Handle all-day vevents
            current_datetime = datetime.datetime.now().astimezone()
            return current_datetime.combine(
                date=vevent.get('dtstart').dt,
                time=current_datetime.time(),
                tzinfo=current_datetime.tzinfo)
        else:
            # Handle events with a specific date/time
            return vevent.get('dtstart').dt

    # Correct the given datetime object for Daylight Saving Time (DST); if the
    # datetime is exactly an hour behind the current system timezone, the given
    # datetime's timezone is updated to be the current system timezone
    def correct_for_dst(self, raw_datetime):

        current_datetime = datetime.datetime.now().astimezone()
        raw_offset = self.get_rel_utc_offset_in_hours(raw_datetime)
        local_offset = self.get_rel_utc_offset_in_hours(current_datetime)
        if (local_offset - raw_offset) == -1:
            # adjusted_datetime = raw_datetime.combine(
            #     date=raw_datetime.date(),
            #     time=raw_datetime.time(),
            #     tzinfo=current_datetime.tzinfo)
            print('adjust for dst:')
            print(raw_datetime)
            return raw_datetime
        else:
            print('no mods:')
            print(raw_datetime)
            return raw_datetime

    # Return the UTC offset of the given datetime object as a positive or
    # negative integer, representing the number of hours difference from UTC
    def get_rel_utc_offset_in_hours(self, raw_datetime):

        # An absolute positive offset (whereas the absolute offset for UTC is 3600 * 24)
        abs_offset_in_seconds = raw_datetime.utcoffset().seconds
        return (abs_offset_in_seconds // SECONDS_IN_HOUR) - HOURS_IN_DAY

    # Convert the given UTC date/time to equivalent date/time in the local
    # timezone
    @staticmethod
    def localize_datetime(utc_datetime):
        now_timestamp = time.time()
        # Compare the relative timezone offset from the same exact timestamp,
        # so we can avoid any race conditions with the sub-second precision;
        # see <https://stackoverflow.com/a/19238551/560642>
        now_datetime = datetime.datetime.fromtimestamp(now_timestamp).astimezone()
        now_utc_datetime = datetime.datetime.utcfromtimestamp(now_timestamp).astimezone()
        offset = now_datetime - now_utc_datetime
        offset_datetime = utc_datetime + offset
        return offset_datetime.combine(
            date=offset_datetime.date(),
            time=offset_datetime.time(),
            tzinfo=now_datetime.tzinfo)

    # Return the conference URL for the given event, whereby some services have
    # higher precedence than others (e.g. always prefer Zoom URLs over Google
    # Meet URLs if both are present)
    def parse_conference_url(self):
        search_str = f'{self.location}\n{self.description}\n{self.raw_url}'
        for domain in self.conference_domains:
            matches = re.search(
                r'https://(\w+\.)?({domain})/([^><"\']+?)(?=([\s><"\']|$))'.format(domain=domain),
                search_str)
            if matches:
                return matches.group(0)
        return None
