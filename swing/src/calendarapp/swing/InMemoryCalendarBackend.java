package calendarapp.swing;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.*;

/**
 * Simple in-memory backend for the Swing client. Useful for demos and tests.
 */
public final class InMemoryCalendarBackend implements CalendarBackend {
    private final List<CalendarEvent> events;
    private final Map<String, CalendarEvent> eventsById;

    public InMemoryCalendarBackend(List<CalendarEvent> events) {
        Objects.requireNonNull(events, "events");
        this.events = new ArrayList<>();
        this.eventsById = new HashMap<>();
        for (CalendarEvent event : events) {
            upsertEvent(event);
        }
    }

    @Override
    public List<CalendarEvent> listEvents() {
        return Collections.unmodifiableList(filterCanceled(events, false));
    }

    @Override
    public List<CalendarEvent> listEventsIncludingCanceled() {
        return Collections.unmodifiableList(events);
    }

    @Override
    public List<CalendarEvent> listEventsForDate(LocalDate date) {
        return listEventsForCalendarOnDate(null, date);
    }

    @Override
    public List<CalendarEvent> listEventsForCalendar(String calendarId) {
        return Collections.unmodifiableList(
                filterByCalendarAndDate(calendarId, null, false));
    }

    @Override
    public List<CalendarEvent> listEventsForCalendarOnDate(String calendarId, LocalDate date) {
        return Collections.unmodifiableList(
                filterByCalendarAndDate(calendarId, date, false));
    }

    @Override
    public CalendarEvent upsertEvent(CalendarEvent event) {
        Objects.requireNonNull(event, "event");
        eventsById.put(event.getId(), event);
        events.removeIf(existing -> existing.getId().equals(event.getId()));
        events.add(event);
        events.sort(Comparator.comparing(CalendarEvent::getStart));
        return event;
    }

    @Override
    public CalendarEvent cancelEvent(String eventId) {
        CalendarEvent existing = eventsById.get(eventId);
        if (existing == null) {
            throw new IllegalArgumentException("Unknown event id: " + eventId);
        }
        CalendarEvent canceled = existing.withCancellation(true);
        upsertEvent(canceled);
        return canceled;
    }

    @Override
    public CalendarEvent rescheduleEvent(String eventId, ZonedDateTime start, ZonedDateTime end, String timezone) {
        CalendarEvent existing = eventsById.get(eventId);
        if (existing == null) {
            throw new IllegalArgumentException("Unknown event id: " + eventId);
        }
        CalendarEvent updated = existing.withSchedule(start, end, timezone);
        upsertEvent(updated);
        return updated;
    }

    private List<CalendarEvent> filterByCalendarAndDate(String calendarId, LocalDate date, boolean includeCanceled) {
        List<CalendarEvent> matches = new ArrayList<>();
        for (CalendarEvent event : events) {
            if (calendarId != null && !calendarId.equals(event.getCalendarId())) {
                continue;
            }
            if (date != null && !event.getStart().toLocalDate().equals(date)) {
                continue;
            }
            if (!includeCanceled && event.isCanceled()) {
                continue;
            }
            matches.add(event);
        }
        return matches;
    }

    private List<CalendarEvent> filterCanceled(List<CalendarEvent> source, boolean includeCanceled) {
        if (includeCanceled) {
            return new ArrayList<>(source);
        }
        List<CalendarEvent> filtered = new ArrayList<>();
        for (CalendarEvent event : source) {
            if (!event.isCanceled()) {
                filtered.add(event);
            }
        }
        return filtered;
    }

    public static InMemoryCalendarBackend sampleData() {
        ZoneId utc = ZoneId.of("UTC");
        List<CalendarEvent> seed = List.of(
                new CalendarEvent(
                        "kickoff",
                        "team",
                        "Kickoff Meeting",
                        ZonedDateTime.of(2025, 1, 10, 15, 0, 0, 0, utc),
                        ZonedDateTime.of(2025, 1, 10, 16, 0, 0, 0, utc),
                        "UTC",
                        "Product kickoff",
                        false),
                new CalendarEvent(
                        "retro",
                        "team",
                        "Retrospective",
                        ZonedDateTime.of(2025, 1, 20, 12, 0, 0, 0, utc),
                        ZonedDateTime.of(2025, 1, 20, 13, 0, 0, 0, utc),
                        "UTC",
                        "Sprint retro",
                        false),
                new CalendarEvent(
                        "planning",
                        "team",
                        "Planning",
                        ZonedDateTime.of(2025, 1, 17, 18, 0, 0, 0, utc),
                        ZonedDateTime.of(2025, 1, 17, 19, 30, 0, 0, utc),
                        "UTC",
                        "Iteration planning",
                        false),
                new CalendarEvent(
                        "canceled",
                        "ops",
                        "Outdated Event",
                        ZonedDateTime.of(2025, 1, 11, 9, 0, 0, 0, utc),
                        ZonedDateTime.of(2025, 1, 11, 9, 30, 0, 0, utc),
                        "UTC",
                        "Should not display by default",
                        true));
        return new InMemoryCalendarBackend(seed);
    }
}
